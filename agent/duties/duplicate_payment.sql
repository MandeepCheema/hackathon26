-- agent/duties/duplicate_payment.sql
-- Real duplicate = the same goods/charge paid twice. Three detection paths:
--   1. same invoice_id paid more than once
--   2. same po_line covered by two+ distinct invoices
--   3. same supplier + same invoice_number + SAME amount on distinct invoice_ids,
--      both paid (the reused-invoice-number double-pay — e.g. INV-4493 booked to
--      two POs and paid twice). DIFFERENT amounts on a shared number = a reused
--      number for different goods → NOT a duplicate (decoy, e.g. meat INV-4471).
-- Excluded: recurring same-amount payments with DISTINCT invoice numbers (cadence),
--   and any invoice carrying a credit memo (voided/re-issued).
with memoed as (select distinct invoice_id from world.fin_credit_memos),
paid as (select invoice_id, count(*) n, min(paid_at) first_paid
         from world.fin_payments_out where invoice_id is not null group by invoice_id),
paid_twice as (select invoice_id from paid where n>1),
double_covered as (select po_line_id from world.fin_invoice_lines where po_line_id is not null
                   group by po_line_id having count(distinct invoice_id)>1),
dupnum as (  -- reused invoice number, same amount, all paid, no memo
  select i.supplier_id, i.invoice_number, i.total_cents,
         array_agg(i.id order by i.invoiced_at) ids
  from world.fin_invoices i
  join paid p on p.invoice_id=i.id
  where i.id not in (select invoice_id from memoed)
  group by i.supplier_id, i.invoice_number, i.total_cents
  having count(*)>1)
-- path 1 & 2
select p.supplier_id, p.invoice_id, p.invoice_id as duplicate_of_invoice_id, p.amount_cents::bigint
from world.fin_payments_out p
where p.invoice_id not in (select invoice_id from memoed)
  and (p.invoice_id in (select invoice_id from paid_twice)
   or  p.invoice_id in (select il.invoice_id from world.fin_invoice_lines il
                        where il.po_line_id in (select po_line_id from double_covered)
                          and il.invoice_id not in (select invoice_id from memoed)))
union
-- path 3: reused invoice number, same amount → flag the later id as dup of the earlier
select d.supplier_id, (d.ids)[2] as invoice_id, (d.ids)[1] as duplicate_of_invoice_id, d.total_cents::bigint
from dupnum d;
