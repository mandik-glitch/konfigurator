-- HDRI odlesky zapecene do online nabidky (Robert 2026-08-06: "zapec").
-- Pri generovani nabidky ze sceny se ulozi aktualni HDRI nastaveni
-- (soubor mapy, otoceni, sila/hrubost odlesku) - verejny prohlizec
-- nabidky pak model ukaze presne tak nablyskany, jak byl ve scene.
-- NULL = nabidka bez HDRI (starsi, nebo HDRI nebylo aktivni).
ALTER TABLE scene_offers ADD COLUMN hdri_json TEXT NULL;
