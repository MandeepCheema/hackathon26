-- agent/duties/loss_prevention.sql
-- Per-cashier rates vs peer baseline for ALL FIVE loss signals the tool grades:
--   void_rate, refund_to_card, no_sale_opens, discount_abuse, refund_no_sale.
-- All fractional outputs cast to ::float (MCP JSON serialises numeric as strings).
with s as (
  select staff_id, store_id,
    sum((txn_type='sale')::int)     as sales,
    sum((txn_type='void')::int)     as voids,
    sum((txn_type='refund')::int)   as refunds,
    sum((txn_type='refund' and card_last4 is not null)::int) as refunds_card,
    sum((txn_type='refund' and card_last4 is null)::int)     as refunds_no_sale,
    sum((txn_type='no_sale')::int)  as no_sales,
    sum((txn_type='discount')::int) as discounts
  from world.fin_register_txns group by staff_id, store_id),
r as (select *,
    voids::numeric/nullif(sales+voids,0)      as void_rate,
    refunds_card::numeric/nullif(sales,0)     as refund_card_rate,
    refunds_no_sale::numeric/nullif(sales,0)  as refund_nosale_rate,
    no_sales::numeric/nullif(sales,0)         as no_sale_rate,
    discounts::numeric/nullif(sales,0)        as discount_rate
  from s),
peer as (select
    avg(void_rate) vm, stddev_pop(void_rate) vs,
    avg(refund_card_rate) rcm, stddev_pop(refund_card_rate) rcs,
    avg(refund_nosale_rate) rnm, stddev_pop(refund_nosale_rate) rns,
    avg(no_sale_rate) nm, stddev_pop(no_sale_rate) ns,
    avg(discount_rate) dm, stddev_pop(discount_rate) ds
  from r),
store as (select store_id,
    sum(voids)::numeric/nullif(sum(sales+voids),0) as store_void_rate
  from r group by store_id)
select r.staff_id, r.store_id,
  r.sales::bigint as sales, r.voids::bigint as voids, r.refunds::bigint as refunds,
  r.no_sales::bigint as no_sales, r.discounts::bigint as discounts,
  round(r.void_rate::numeric,3)::float          as void_rate,
  round(peer.vm::numeric,3)::float              as peer_mean,
  round(peer.vs::numeric,3)::float              as peer_sd,
  round(((r.void_rate-peer.vm)/nullif(peer.vs,0))::numeric,2)::float          as z_void,
  round(((r.refund_card_rate-peer.rcm)/nullif(peer.rcs,0))::numeric,2)::float as z_refund_card,
  round(((r.refund_nosale_rate-peer.rnm)/nullif(peer.rns,0))::numeric,2)::float as z_refund_nosale,
  round(((r.no_sale_rate-peer.nm)/nullif(peer.ns,0))::numeric,2)::float       as z_no_sale,
  round(((r.discount_rate-peer.dm)/nullif(peer.ds,0))::numeric,2)::float      as z_discount,
  round(store.store_void_rate::numeric,3)::float as store_void_rate
from r cross join peer join store on store.store_id=r.store_id;
