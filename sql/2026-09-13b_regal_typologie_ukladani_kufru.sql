-- Novy radek regal_typologie: "Ukladani kufru" (bot9, 2026-09-13, Robert
-- primo v chatu). Osa system/obsah (viz sql/2026-09-11_kod_sestavy_ciselniky.sql),
-- ne osa umisteni (sql/2026-09-13_regal_umisteni.sql) - je to DALSI typ
-- toho, co regal obsahuje/uklada, vedle EB/UN/OS/EV.
--
-- Obsah zatim neurcen, stejny vzor jako u puvodnich placeholderu
-- UN/OS/EV pri jejich zalozeni 2026-09-11.
INSERT INTO regal_typologie (kod, klic, nazev, popis, sort_order) VALUES
  ('UK', 'ukladani_kufru', 'Ukládání kufrů', 'Zatím jen pojmenováno, obsah neurčen (Robert 2026-09-13).', 50);
