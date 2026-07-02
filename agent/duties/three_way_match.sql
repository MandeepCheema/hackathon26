-- agent/duties/three_way_match.sql
-- Exceptions net of the two engineered explanations:
--  1. CREDIT MEMOS (world.fin_credit_memos): a memo on the line's invoice that covers the
--     over-billing means the supplier already resolved it — do NOT flag (pol_00150 decoy).
--  2. CONTRACT PRICE (world.fin_price_list): billed within 0.5% of the current contracted
--     price (finpol_pricetol) is within tolerance even when above the PO's agreed cost.
-- Materiality (finpol_materiality): flag only when > $5.00 AND > 0.5% of the line.
with j as (
  select pl.po_id, il.po_line_id, il.invoice_id, pl.sku_id, i.supplier_id, i.invoiced_at::date d,
    il.billed_qty, coalesce(gr.rq,0) rq, il.billed_unit_cost_cents bc, pl.agreed_unit_cost_cents ac,
    (il.billed_qty*il.billed_unit_cost_cents) line_val,
    (il.billed_qty-coalesce(gr.rq,0))*pl.agreed_unit_cost_cents qty_over,
    il.billed_qty*(il.billed_unit_cost_cents-pl.agreed_unit_cost_cents) price_over
  from world.fin_invoice_lines il
  join world.fin_po_lines pl on il.po_line_id=pl.id
  join world.fin_invoices i on il.invoice_id=i.id
  left join (select po_line_id,sum(received_qty) rq from world.fin_goods_receipts group by 1) gr on gr.po_line_id=pl.id),
memo as (
  select invoice_id, sum(amount_cents) memo_cents from world.fin_credit_memos group by 1),
x as (
  select j.*, coalesce(m.memo_cents,0) memo_cents,
    greatest(j.qty_over,0) - coalesce(m.memo_cents,0) qty_res,
    case when p.agreed_unit_cost_cents is not null
          and abs(j.bc - p.agreed_unit_cost_cents) <= 0.005*p.agreed_unit_cost_cents
         then 0 else greatest(j.price_over,0) end price_res
  from j
  left join memo m on m.invoice_id = j.invoice_id
  left join world.fin_price_list p
    on p.sku_id=j.sku_id and p.supplier_id=j.supplier_id
   and j.d >= p.effective_date and (p.end_date is null or j.d <= p.end_date))
select po_id, po_line_id,
  case when qty_res>500 and qty_res>0.005*line_val then 'over_billed_qty'
       when (bc-ac)>0 and (bc-ac)>0.005*ac and price_res>500 then 'price_variance' end as exception_type,
  round(greatest(qty_res, price_res))::bigint as amount_cents,
  memo_cents
from x
where (qty_res>500 and qty_res>0.005*line_val)
   or ((bc-ac)>0 and (bc-ac)>0.005*ac and price_res>500);
