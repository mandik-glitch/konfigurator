-- Cislovani nabidek RM00xx -> Logiman00xx (bot4, Robert 2026-08-06:
-- "Cislovani nabidek zmen na Logiman00xx"). Prefix je Python konstanta
-- QUOTE_PREFIX v api/quotes.py (zmenena "RM" -> "Logiman"); tady jen
-- rozsireni sloupce - "Logiman0052" ma 11 znaku, VARCHAR(10) by
-- neprosel. Existujici nabidky si ponechavaji sva RM cisla (historie
-- se neprepisuje), nove dostanou Logiman.
ALTER TABLE scene_offers MODIFY COLUMN offer_number VARCHAR(20) NOT NULL;
