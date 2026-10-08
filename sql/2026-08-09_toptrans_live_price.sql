-- Robert: "stisk toptransu nic neudelal, musi vyvolat dotaz na PSC a
-- vypsat živou cenu" - zakaznik v online nabidce (nabidka-online.html,
-- "Vaše volby k objednávce") si vybere dopravu Toptrans, zada PSC dodaci
-- adresy a uvidi zive dopocitanou cenu (podle hmotnosti sestavy + PSC,
-- stejny cenik jako v e-shopu, viz api/orders.py::_resolve_toptrans_price).
-- Ulozeni PSC + vypocitane ceny primo do radku voleb objednavky, at
-- prezije reload stranky a je videt i v adminu (admin_scene_offer_stats).
ALTER TABLE scene_offer_order_prefs
  ADD COLUMN delivery_zip VARCHAR(6) NULL AFTER delivery_state,
  ADD COLUMN toptrans_price_czk INT NULL AFTER delivery_zip;
