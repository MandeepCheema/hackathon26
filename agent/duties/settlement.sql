-- agent/duties/settlement.sql
-- missing = register card − expected fee − deposit − LOGGED ADJUSTMENTS (refund/chargeback/
-- terminal/timing — world.fin_settlement_adjustments). An adjustment-explained gap is the
-- engineered decoy: the tool says flag only what is unexplained AFTER fees and adjustments.
with fee as (
  select cm.store_id, cm.business_date,
    sum(cm.gross_cents*fs.mdr_bps/10000.0 + cm.txn_count*fs.per_txn_fee_cents) ef
  from world.fin_card_mix cm join world.fin_fee_schedule fs on fs.card_type=cm.card_type
  group by 1,2),
adj as (
  select store_id, business_date, sum(amount_cents) adj_cents
  from world.fin_settlement_adjustments group by 1,2)
select rt.store_id, rt.business_date::text as business_date,
  rt.card_cents::bigint as register_card_cents,
  round(f.ef)::bigint as expected_fee_cents,
  s.net_deposit_cents::bigint as deposit_cents,
  coalesce(a.adj_cents,0)::bigint as adjustment_cents,
  round(rt.card_cents - f.ef - s.net_deposit_cents - coalesce(a.adj_cents,0))::bigint as missing_cents
from world.fin_register_totals rt
join world.fin_bank_settlements s on s.store_id=rt.store_id and s.covers_date=rt.business_date
join fee f on f.store_id=rt.store_id and f.business_date=rt.business_date
left join adj a on a.store_id=rt.store_id and a.business_date=rt.business_date
where abs(rt.card_cents - f.ef - s.net_deposit_cents - coalesce(a.adj_cents,0)) > 200;
