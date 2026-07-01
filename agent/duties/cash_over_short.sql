-- agent/duties/cash_over_short.sql
with v as (
  select rt.store_id, rt.business_date,
    cc.counted_cash_cents - (rt.cash_cents - coalesce(po.amt,0)) as var_cents
  from world.fin_register_totals rt
  join world.fin_cash_counts cc
    on cc.store_id=rt.store_id and cc.business_date=rt.business_date
  left join (select store_id, business_date, sum(amount_cents) amt
             from world.fin_paid_outs group by 1,2) po
    on po.store_id=rt.store_id and po.business_date=rt.business_date)
select store_id,
  count(*)::bigint                                                        as days,
  sum(case when var_cents<>0 then 1 else 0 end)::bigint                  as nonzero_days,
  round(avg(var_cents))::bigint                                           as avg_var_cents,
  round(stddev_pop(var_cents))::bigint                                    as sd_cents,
  sum(var_cents)::bigint                                                  as net_cents,
  round(((avg(var_cents)/nullif(stddev_pop(var_cents),0))*sqrt(count(*)))::numeric, 2)::float as tstat
from v group by store_id;
