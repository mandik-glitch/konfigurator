-- Robert: "2D pohledy nech maji 2 rezimy zobrazeni, drateny a ghosted,
-- nikoli v roletce ale vedle sebe tlacitka prepinatka" - nárys/bokorys/
-- půdorys se ted pri generovani nabidky (scene.html::generateSceneOffer)
-- ukladaji ve DVOU stylech (drateny + poloprůhledny "ghost"), zakaznik
-- v online nabidce mezi nimi prepina tlacitky. Sloupce NULL (nepovinne)
-- - stare nabidky vygenerovane pred timhle datem ghost variantu nemaji,
-- prepinac se u nich jen skryje/deaktivuje (viz nabidka-online.html).
ALTER TABLE scene_offers
  ADD COLUMN view_narys_ghost VARCHAR(255) NULL AFTER view_narys,
  ADD COLUMN view_bokorys_ghost VARCHAR(255) NULL AFTER view_bokorys,
  ADD COLUMN view_pudorys_ghost VARCHAR(255) NULL AFTER view_pudorys;
