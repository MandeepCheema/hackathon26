-- agent/duties/three_way_match.sql
with j as (
  select pl.po_id, il.po_line_id,
    il.billed_qty, coalesce(gr.rq,0) rq, il.billed_unit_cost_cents bc, pl.agreed_unit_cost_cents ac,
    (il.billed_qty*il.billed_unit_cost_cents) line_val,
    (il.billed_qty-coalesce(gr.rq,0))*pl.agreed_unit_cost_cents qty_over,
    il.billed_qty*(il.billed_unit_cost_cents-pl.agreed_unit_cost_cents) price_over
  from world.fin_invoice_lines il
  join world.fin_po_lines pl on il.po_line_id=pl.id
  left join (select po_line_id,sum(received_qty) rq from world.fin_goods_receipts group by 1) gr on gr.po_line_id=pl.id)
select po_id, po_line_id,
  case when qty_over>500 and qty_over>0.005*line_val then 'over_billed_qty'
       when (bc-ac)>0 and (bc-ac)>0.005*ac and price_over>500 then 'price_variance' end as exception_type,
  round(greatest(qty_over, price_over))::bigint as amount_cents
from j
where (qty_over>500 and qty_over>0.005*line_val)
   or ((bc-ac)>0 and (bc-ac)>0.005*ac and price_over>500);
