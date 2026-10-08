-- Komentare (vyhrady) Roberta ke konkretni sestave ve fronte ke schvaleni
-- (bot10, zadani bot3 koordinace 2026-09-11, puvodne Robert: "dej moznost
-- napsat komentar, ulozi se to k tomu do prehledu stavu sestav a ktery
-- kolik bot si to muze vybrat jako dalsi ukol").
--
-- TRI VLASTNOSTI, na kterych to stoji (Robert pres bot3):
--   1. Historie, ne jedno pole - HISTORIE = kazdy zapis je NOVY RADEK,
--      zadny UPDATE existujiciho `body` (na rozdil od `production_card_
--      blockers`, kde novy text prepisuje/uzavira predchozi - tady muze
--      byt soucasne otevrenych vic nezavislych vyhrad k tez sestave).
--   2. Musi jit uzavrit - `resolved_at` NULL = otevrena, vyplnene = vyresena.
--      Zavira ji VZDY ten, kdo ji opravil (`resolved_by`), s poznamkou
--      (`resolution_note`) co se udelalo - Robert u schvaleni vidi
--      odpoved, ne jen zmizely radek.
--   3. Zapis komentare NESAHA na geometrii/technicky_ok - samostatna
--      tabulka, zadna vazba na `product_assemblies.data`.
--
-- Stane se ukolem, ktery si bot muze vzit pres JIZ EXISTUJICI
-- `production_work_claims` (bot9, sql/2026-09-11j_*.sql) - zadna druha
-- fronta prace vedle prvni: target_type='sestava_komentar',
-- target_id=<production_comments.id>, step_key='vyrizeni'.
CREATE TABLE IF NOT EXISTS production_comments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  assembly_id INT NOT NULL,
  body VARCHAR(2000) NOT NULL,
  author VARCHAR(120) NOT NULL COMMENT 'jmeno/email stafu, ktery napsal (current_user())',
  created_at DATETIME NOT NULL,
  resolved_at DATETIME NULL,
  resolved_by VARCHAR(80) NULL COMMENT 'BOT_ID - sebe-hlaseny, stejny model duvery jako production_work_claims.held_by (koordinace, ne pruvodni stopa)',
  resolution_note VARCHAR(1000) NULL,
  KEY idx_assembly (assembly_id, resolved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
