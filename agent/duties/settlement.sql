-- agent/duties/settlement.sql
with fee as (
  select cm.store_id, cm.business_date,
    sum(cm.gross_cents*fs.mdr_bps/10000.0 + cm.txn_count*fs.per_txn_fee_cents) ef
  from world.fin_card_mix cm join world.fin_fee_schedule fs on fs.card_type=cm.card_type
  group by 1,2)
select rt.store_id, rt.business_date::text as business_date,
  rt.card_cents::bigint as register_card_cents,
  round(f.ef)::bigint as expected_fee_cents,
  s.net_deposit_cents::bigint as deposit_cents,
  round(rt.card_cents - f.ef - s.net_deposit_cents)::bigint as missing_cents
from world.fin_register_totals rt
join world.fin_bank_settlements s on s.store_id=rt.store_id and s.covers_date=rt.business_date
join fee f on f.store_id=rt.store_id and f.business_date=rt.business_date
where abs(rt.card_cents - f.ef - s.net_deposit_cents) > 200;
