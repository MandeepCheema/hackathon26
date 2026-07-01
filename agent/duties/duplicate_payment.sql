-- agent/duties/duplicate_payment.sql
-- Real duplicate = same invoice paid twice, or the same goods (po_line) covered by two invoices.
-- Recurring same-amount payments with DISTINCT invoices are legitimate and excluded.
with paid_twice as (
  select invoice_id from world.fin_payments_out where invoice_id is not null
  group by invoice_id having count(*)>1),
double_covered as (
  select po_line_id from world.fin_invoice_lines where po_line_id is not null
  group by po_line_id having count(distinct invoice_id)>1)
select p.supplier_id, p.invoice_id, p.invoice_id as duplicate_of_invoice_id, p.amount_cents::bigint
from world.fin_payments_out p
where p.invoice_id in (select invoice_id from paid_twice)
   or p.invoice_id in (select il.invoice_id from world.fin_invoice_lines il
                       where il.po_line_id in (select po_line_id from double_covered));
