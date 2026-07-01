-- agent/duties/loss_prevention.sql
-- Per-cashier void/refund/no-sale rates vs peer baseline.
-- All fractional outputs cast to ::float (MCP JSON serialises numeric as strings).
-- All integer aggregates cast to ::bigint.
with s as (
  select staff_id, store_id,
    sum((txn_type='sale')::int)    as sales,
    sum((txn_type='void')::int)    as voids,
    sum((txn_type='refund')::int)  as refunds,
    sum((txn_type='no_sale')::int) as no_sales
  from world.fin_register_txns group by staff_id, store_id),
r as (select *, voids::numeric/nullif(sales+voids,0) as void_rate from s),
peer as (select avg(void_rate) pm, stddev_pop(void_rate) ps from r),
store as (select store_id,
            sum(voids)::numeric/nullif(sum(sales+voids),0) as store_void_rate
          from r group by store_id)
select r.staff_id,
       r.store_id,
       r.sales::bigint                                                      as sales,
       r.voids::bigint                                                      as voids,
       r.refunds::bigint                                                    as refunds,
       r.no_sales::bigint                                                   as no_sales,
       round(r.void_rate::numeric,3)::float                                 as void_rate,
       round(peer.pm::numeric,3)::float                                     as peer_mean,
       round(peer.ps::numeric,3)::float                                     as peer_sd,
       round(((r.void_rate-peer.pm)/nullif(peer.ps,0))::numeric,2)::float  as z_void,
       round(store.store_void_rate::numeric,3)::float                      as store_void_rate
from r cross join peer join store on store.store_id=r.store_id;
