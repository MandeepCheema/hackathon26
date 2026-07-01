-- agent/duties/duplicate_payment.sql
-- Candidate-net query for the duplicate_payment duty.
--
-- Stage 1: Exact-match candidates — same invoice_id paid more than once.
-- Stage 2: Coarse-match candidates — same supplier + amount + date proximity (different invoice_id).
--
-- Most Stage 2 candidates are legitimate recurring payments (distinct invoice IDs, weekly cadence).
-- skill_fuzzy_disambiguation filters to true duplicates.
--
-- Run Stage 1 first. Only run Stage 2 if Stage 1 yields no results.
--
-- Run via: run_sql(query=<this file>, purpose="duplicate payment candidate net — exact match stage 1")

-- ============================================================
-- STAGE 1: Exact same invoice_id paid more than once
-- ============================================================
SELECT
  supplier_id,
  invoice_id,
  COUNT(*)                          AS payment_count,
  SUM(amount_cents)                 AS total_paid_cents,
  MIN(paid_at)                      AS first_payment_at,
  MAX(paid_at)                      AS last_payment_at,
  ROUND(
    EXTRACT(EPOCH FROM (MAX(paid_at) - MIN(paid_at))) / 86400.0,
  1)                                AS days_between_payments,
  array_agg(id ORDER BY paid_at)    AS payment_ids,
  array_agg(reference ORDER BY paid_at) AS references
FROM world.fin_payments_out
GROUP BY supplier_id, invoice_id
HAVING COUNT(*) > 1
ORDER BY total_paid_cents DESC;

-- ============================================================
-- STAGE 2 (run separately if Stage 1 finds nothing):
-- Same supplier + same amount + within 30 days, different invoice_id
-- ============================================================
-- Run via: run_sql(query=<stage2 query below>, purpose="duplicate payment coarse match — stage 2")
/*
SELECT
  a.id              AS payment_id_1,
  b.id              AS payment_id_2,
  a.supplier_id,
  a.invoice_id      AS invoice_id_1,
  b.invoice_id      AS invoice_id_2,
  a.amount_cents,
  a.paid_at         AS paid_at_1,
  b.paid_at         AS paid_at_2,
  ROUND(
    ABS(EXTRACT(EPOCH FROM (b.paid_at - a.paid_at))) / 86400.0,
  1)                AS days_apart
FROM world.fin_payments_out a
JOIN world.fin_payments_out b
  ON  a.supplier_id  = b.supplier_id
  AND a.amount_cents = b.amount_cents
  AND a.id < b.id
  AND ABS(EXTRACT(EPOCH FROM (b.paid_at - a.paid_at))) / 86400.0 <= 30
ORDER BY a.supplier_id, days_apart;
*/
