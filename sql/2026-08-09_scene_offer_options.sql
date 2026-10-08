-- Robert: "u nabídky online, při její tvorbě konkretniho cisla, chci
-- mit moznsot vzdy nektere prvky odebrat, napr QR kod, nebo naopak
-- doplnit: Termin dodani"
--
-- Volitelne prvky nabidky, vybrane v okamziku jejiho vytvoreni
-- (scene.html generateSceneOffer()) - JSON, aby sla sada v budoucnu
-- rozsirit o dalsi prvky beze zmeny schematu. NULL u starych nabidek
-- pred timhle datem - public_offer_get() dopocitava vychozi hodnoty
-- (show_qr=true, delivery_term=null), takze se chovani stareho odkazu
-- nezmeni.
ALTER TABLE scene_offers
  ADD COLUMN offer_options JSON NULL AFTER hdri_json;
