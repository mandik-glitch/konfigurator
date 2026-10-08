-- bot5, 2026-09-16 - Robert primo: "proc si neudelas script nebo jinou
-- automatiku, ktera detekuje hotove rendery cimz se vse aktivuje
-- autonomne" - viz scripts/2026-09-16_card_auto_activate.py.
--
-- `activated_at` rika, jestli karta uz NEKDY byla aktivni (bez ohledu
-- na to, jestli je aktivni PRAVE TED) - odlisuje "nova karta, jeste
-- nikdy nezverejnena" (activated_at IS NULL, smi ji aktivovat
-- automat) od "byla zverejnena a Robert ji pak SCHVALNE vypnul"
-- (activated_at vyplnene, i kdyz active=0 - automat se ji uz nikdy
-- nedotkne, jinak by "vzkrisil" kartu, kterou nekdo umyslne stahl
-- z prodeje).
ALTER TABLE shop_products
  ADD COLUMN activated_at TIMESTAMP NULL DEFAULT NULL AFTER active;

-- Backfill: vsechny UZ TED aktivni karty povazujeme za "uz nekdy
-- aktivni" (presny puvodni cas prvni aktivace neznáme, created_at je
-- nejlepsi dostupna aproximace a pro ucel "uz se jich automat nema
-- dotykat" staci).
UPDATE shop_products SET activated_at = created_at WHERE active = 1 AND activated_at IS NULL;
