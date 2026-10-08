-- Kotveni jako VLASTNI zakaznicke pole, oddelene od montaze.
--
-- TEXT_FILTR.md pravidlo 14b (Robert pres bot9, 2026-09-13): "Kotvení je
-- vlastní oddělená, dynamická část popisu" - stejne zachazeni jako montaz
-- (pravidlo 12) a zbytek popisu (pravidlo 13).
--
-- Puvodni `montaz_zakaznicky` (2026-09-13f) obsahoval DVE vety v jednom
-- poli: "Konstrukce se kotvi..." (KOTVENI - KAM) + "Montaz zahrnuje
-- vrtani..." (MONTAZ - JAK). Rozdeleno na dve samostatna pole, at kazde
-- nese jednu soudrznou informaci - stepeni textu regexem na frontendu by
-- bylo krehke a rozpadlo by se pri jakekoli zmene formulace.

ALTER TABLE regal_umisteni
  ADD COLUMN kotveni_zakaznicky TEXT NULL
  COMMENT 'Zakaznicka veta o kotveni (KAM se pripevnuje) - oddelena od montaz_zakaznicky (JAK se montuje), TEXT_FILTR.md pravidlo 14b';
