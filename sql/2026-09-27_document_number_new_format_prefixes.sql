-- bot5, 2026-09-27 (Robert primo, presny format ze screenshotu): novy
-- format cisla dokladu pro invoice/proforma_invoice/payment_tax_document
-- (viz api/documents.py NEW_FORMAT_DOCUMENT_TYPES + _next_document_number)
-- pouziva "prefix" sloupec jako KOD TYPU (2 cislice nebo pismena) mezi
-- rokem a poradim, ne jako volny textovy prefix pred cislem jako drive.
-- payment_tax_document uz "VDD" ma spravne, meni se jen tyhle dva:
UPDATE shop_document_sequences SET prefix='01' WHERE document_type='invoice';
UPDATE shop_document_sequences SET prefix='08' WHERE document_type='proforma_invoice';
