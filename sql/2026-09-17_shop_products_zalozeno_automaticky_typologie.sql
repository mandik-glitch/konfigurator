-- bot5, 2026-09-17 - Robert primo (pres bot3/bot9): vizualni schvaleni
-- auto-zalozenych karet se dela JEDNOU ZA TYPOLOGII (regal_typologie),
-- ne za kazdou kartu/vozidlo. Jakmile Robert jednou vizualne potvrdi
-- vzhled PRVNI auto-zalozene karty dane typologie, dalsi karty stejne
-- typologie se zakladaji dal automaticky bez cekani na dalsi schvaleni.
--
-- Tenhle sloupec rozlisuje "auto-zalozena kartou card_auto_link.py"
-- (NOT NULL = id typologie, pro ktera byla zalozena) od "zalozena
-- rucne" (NULL, vsechny dosavadni karty K-020/K-289/K-170/Ford Connect/
-- Doblo/Jumpy atd.) - bez tohohle rozliseni by se nedalo spocitat
-- "existuje uz AUTO-zalozena karta teto typologie", protoze rucne
-- zalozenych karet stejne typologie uz existuje hodne a jejich
-- existence NEZNAMENA schvaleni AUTOMATICKY GENEROVANE sablony.
ALTER TABLE shop_products
  ADD COLUMN zalozeno_automaticky_typologie_id INT NULL AFTER category_id;
