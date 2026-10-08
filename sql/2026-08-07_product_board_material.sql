-- 2D protahovani desek ve 3D scene (bot7, 2026-08-07).
--
-- Robert: "postavit 2D protahovani pro desky (novy typ dilu)" - navazuje
-- na color_hex (2026-08-07_product_scene_color.sql) a PR10 (deskovy
-- material 1000x1000x10mm, viz AGENTS_LOG). Priznak rika scene.html,
-- ze ma pro tenhle produkt pouzit computeBoardEdgeConnectors() misto
-- bezneho computeConnectorsLocal() - deska pak ma 4 hranove ("edge")
-- konektory (2 nezavisle protahovaci osy - sirka a vyska), na rozdil
-- od profilu s 1 delkovou osou. Tloustka (3. rozmer) se nikdy nemeni.
ALTER TABLE shop_products ADD COLUMN is_board_material TINYINT(1) NOT NULL DEFAULT 0 AFTER color_hex;
