-- agent/duties/settlement.sql
-- Two candidate families:
--  A. DEPOSIT PRESENT, gap unexplained: missing = card − expected fee − deposit − LOGGED
--     ADJUSTMENTS (world.fin_settlement_adjustments: refund/chargeback/terminal/timing).
--     An adjustment-explained gap is the engineered decoy — flag only the residual.
--  B. DEPOSIT MISSING entirely (no bank row for the day): days_pending tells timing from
--     trouble — a recent day (<= 2 business days before the data edge) is normal T+1/T+2
--     lag → timing_pending; an old missing deposit is a real shortfall of the full net.
with fee as (
  select cm.store_id, cm.business_date,
    sum(cm.gross_cents*fs.mdr_bps/10000.0 + cm.txn_count*fs.per_txn_fee_cents) ef
  from world.fin_card_mix cm join world.fin_fee_schedule fs on fs.card_type=cm.card_type
  group by 1,2),
adj as (
  select store_id, business_date, sum(amount_cents) adj_cents
  from world.fin_settlement_adjustments group by 1,2),
edge as (select max(covers_date) last_covered from world.fin_bank_settlements)
select rt.store_id, rt.business_date::text as business_date,
  rt.card_cents::bigint as register_card_cents,
  round(f.ef)::bigint as expected_fee_cents,
  s.net_deposit_cents::bigint as deposit_cents,
  coalesce(a.adj_cents,0)::bigint as adjustment_cents,
  round(rt.card_cents - f.ef - coalesce(s.net_deposit_cents,0) - coalesce(a.adj_cents,0))::bigint as missing_cents,
  case when s.id is null then (select last_covered from edge) - rt.business_date end::bigint as days_pending
from world.fin_register_totals rt
left join world.fin_bank_settlements s on s.store_id=rt.store_id and s.covers_date=rt.business_date
join fee f on f.store_id=rt.store_id and f.business_date=rt.business_date
left join adj a on a.store_id=rt.store_id and a.business_date=rt.business_date
where s.id is null
   or abs(rt.card_cents - f.ef - s.net_deposit_cents - coalesce(a.adj_cents,0)) > 200;
