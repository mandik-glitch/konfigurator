-- bot5 2026-08-11
-- Robert: "tato dlaždice není o novinkách ale pro hlášky, dlaždici pro
-- novinky udeláme extra jinou další" - puvodni "news_items" tabulka
-- (postavena pro plnohodnotne clanky s vlastni SEO strankou) byla
-- prekopana na jednoduche kratke "hlasky" (bez detailu, odkazy primo v
-- textu) - prejmenovano na announcement_items, at nazev nekoliduje se
-- skutecnou budouci "Novinky" dlazdici (ta uz bude potrebovat vlastni
-- tabulku/nazvy). slug/meta_description sloupce zaniky uzitecnost -
-- slug byl jen pro /novinka/<slug> route (uz neexistuje), meta_description
-- pro <meta> tag na te strance (take uz neexistuje) - oba odstraneny.
RENAME TABLE news_items TO announcement_items;
ALTER TABLE announcement_items
  DROP COLUMN slug,
  DROP COLUMN meta_description;
