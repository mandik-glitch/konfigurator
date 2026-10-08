-- bot3 2026-08-09 (Robert: "dokonci poctive moznost prirezu u vsech
-- profilu") - privirezy (cut pieces) byly na product.html nabizeny jen
-- kdyz mel produkt cfg_dily_id (3D model pro scenu) - to je ale signal
-- "ma hotovy 3D model", ne "prodava se na delku/da se rezat". Jen 22
-- ze 101 realnych profilu melo cfg_dily_id, zbylych 79 tak nemelo
-- prirezy vubec k dispozici.
--
-- Novy sloupec je nezavisly signal "tohle je hlinikovy profil prodavany
-- na delku" (stejny vzor jako existujici is_board_material), oddeleny
-- od pritomnosti 3D modelu.
ALTER TABLE shop_products
    ADD COLUMN is_profile_material TINYINT(1) NOT NULL DEFAULT 0 AFTER is_board_material;
