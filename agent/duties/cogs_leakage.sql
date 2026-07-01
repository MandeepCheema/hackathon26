-- agent/duties/cogs_leakage.sql
with rev as (select store_id, sum(cash_cents+card_cents) rev from world.fin_register_totals group by 1),
spend as (select po.store_id, sum(gr.received_qty*pl.agreed_unit_cost_cents) cogs,
            count(distinct gr.received_at::date) rdays
          from world.fin_goods_receipts gr
          join world.fin_po_lines pl on gr.po_line_id=pl.id
          join world.fin_purchase_orders po on pl.po_id=po.id group by 1)
select r.store_id, r.rev::bigint as revenue_cents,
  coalesce(s.cogs,0)::bigint as cogs_cents,
  round(100.0*coalesce(s.cogs,0)/nullif(r.rev,0),1)::float as cogs_pct,
  coalesce(s.rdays,0)::bigint as receipt_days
from rev r left join spend s on s.store_id=r.store_id;
