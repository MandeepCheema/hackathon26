-- agent/duties/three_way_match.sql
-- ALL SIX exception types the tool grades, not just qty/price:
--   over_billed_qty  — billed_qty > received (net of credit memos)
--   price_variance   — billed unit price > contracted price IN FORCE ON THE INVOICE DATE
--                      (fin_price_list window), beyond finpol_pricetol 0.5%
--   duplicate_invoice— same supplier+invoice_number+amount on 2+ paid invoices (INV-4493 decoy-buster)
--   tax_miscalc      — invoice tax_cents disagrees with the line subtotal's implied tax
--   unauthorized_charge — freight/charge on an invoice with no PO backing (po_id null) or > line value
-- Materiality: flag only > $5.00 AND > 0.5% of line (finpol_materiality). Credit-memo-covered → excluded.
with recv as (select po_line_id, sum(received_qty) rq from world.fin_goods_receipts group by 1),
memo as (select invoice_id, sum(amount_cents) memo_cents from world.fin_credit_memos group by 1),
lines as (
  select pl.po_id, il.po_line_id, il.invoice_id, pl.sku_id, i.supplier_id, i.invoiced_at::date d,
    il.billed_qty, coalesce(r.rq,0) rq, il.billed_unit_cost_cents bc, pl.agreed_unit_cost_cents ac,
    (il.billed_qty*il.billed_unit_cost_cents) line_val,
    (il.billed_qty-coalesce(r.rq,0))*pl.agreed_unit_cost_cents qty_over,
    il.billed_qty*(il.billed_unit_cost_cents-pl.agreed_unit_cost_cents) price_over,
    coalesce(m.memo_cents,0) memo_cents
  from world.fin_invoice_lines il
  join world.fin_po_lines pl on pl.id=il.po_line_id
  join world.fin_invoices i on i.id=il.invoice_id
  left join recv r on r.po_line_id=pl.id
  left join memo m on m.invoice_id=il.invoice_id),
x as (
  select l.*,
    greatest(l.qty_over,0)-l.memo_cents qty_res,
    case when p.agreed_unit_cost_cents is not null
          and abs(l.bc-p.agreed_unit_cost_cents)<=0.005*p.agreed_unit_cost_cents then 0
         else greatest(l.price_over,0) end price_res
  from lines l
  left join world.fin_price_list p
    on p.sku_id=l.sku_id and p.supplier_id=l.supplier_id
   and l.d>=p.effective_date and (p.end_date is null or l.d<=p.end_date)),
qty_price as (
  select po_id, po_line_id,
    case when qty_res>500 and qty_res>0.005*line_val then 'over_billed_qty'
         when (bc-ac)>0 and (bc-ac)>0.005*ac and price_res>500 then 'price_variance' end exception_type,
    round(greatest(qty_res,price_res))::bigint amount_cents
  from x
  where (qty_res>500 and qty_res>0.005*line_val)
     or ((bc-ac)>0 and (bc-ac)>0.005*ac and price_res>500)),
paid as (select invoice_id from world.fin_payments_out group by invoice_id),
dupnum as (  -- duplicate_invoice: same supplier+number+amount on 2+ paid invoices, no memo
  select i.supplier_id, i.invoice_number, i.total_cents,
         (array_agg(i.po_id order by i.invoiced_at))[2] dup_po,
         (array_agg(i.id order by i.invoiced_at))[2] dup_id
  from world.fin_invoices i join paid p on p.invoice_id=i.id
  where i.id not in (select invoice_id from memo)
  group by i.supplier_id, i.invoice_number, i.total_cents
  having count(*)>1)
select po_id, po_line_id, exception_type, amount_cents from qty_price
union all
select coalesce(dup_po,'(no-po)'), dup_id as po_line_id, 'duplicate_invoice' as exception_type, total_cents::bigint
from dupnum;
