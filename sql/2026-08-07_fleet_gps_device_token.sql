-- Kniha jizd: GPS pozice z externi appky misto vlastniho watchPosition na
-- pozadi (Robert 2026-08-07: "Vzit si proste GPS z jine apky na mobilu" -
-- vlastni PWA sledovani na pozadi nefunguje, kdyz je apka/tab zavreny;
-- misto vlastniho reseni se pouzije existujici nativni GPS tracker appka
-- (napr. Traccar Client), ktera umi spolehlive bezet na pozadi a posilat
-- polohu OsmAnd protokolem na URL, kterou ovladame - viz api/fleet.py
-- /api/fleet/gps-ping).
ALTER TABLE app_users ADD COLUMN gps_device_token VARCHAR(64) NULL UNIQUE AFTER magic_token_hash;
