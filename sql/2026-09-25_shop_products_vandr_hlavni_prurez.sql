-- Perzistence "hlavniho profilu" (rozmer nosneho prurezu, mm) Vandr
-- karty - Robert primo, 2026-09-25: sestavy maji na karte nest stitky
-- jako GRAFICKE prvky (hlavni profil + strana auta), ne jen text.
-- Umisteni (strana) uz shop_products.umisteni_id ma, hlavni profil
-- NIKDE - `overit_final_glb()` (scripts/2026-09-23_vandr_fbx_konverze_
-- auto_dispatch.py) ho jen POCITA za behu konverze jako bezpecnostni
-- brzdu (OVERENE_PROFILY) a vysledek zahodi. Nativni vetev ma analogii
-- na `product_assemblies.profil_mm` (SMALLINT, jedno cislo - profily
-- jsou ctvercove, "40" znamena "40x40") - stejny typ a format tady,
-- kvuli sdilenemu stitkovaciho komponentu na frontendu (bot7).
--
-- NULL = jeste nespocitano/nezaplneno (karta bez GLB, nebo pred timhle
-- patchem, nez probehne zpetny backfill). Plni se VYHRADNE ze
-- SKUTECNEHO vysledku overit_final_glb() (ten uz beztak GLB kontroluje
-- pri kazde konverzi) - zadny novy/druhy vypocet vedle, presne proto
-- to je SMALLINT ne VARCHAR "40x40": format "NxN" pro zobrazeni si
-- dopocita frontend, DB drzi jen cislo.
ALTER TABLE shop_products
  ADD COLUMN vandr_hlavni_prurez_mm SMALLINT NULL;
