-- Ulozene oznaceni/kresba klienta v online nabidce (bot4, 2026-08-05).
-- Robert: "udelej mi stetec primo v online nabidce kde ti zakrouzkuju a
-- ocisluju problem, popisu potom v chatu" + "oznacovani nech napric
-- celym dokumentem, kresleni jen v casti vykresy" + "na konci dej nejak
-- tlacitko ulozit at vidis co jsem kreslil".
--
-- JEDEN ulozeny set znacek na nabidku (tlacitko "Ulozit oznaceni"
-- prepise cely set) - vektorova data v JSON, NE obrazky: znacky se
-- vykresluji nad zivou strankou u kohokoli, kdo nabidku otevre (klient
-- i admin pres "Zobrazit online"), spravne pri jakemkoli rozliseni
-- (souradnice jsou ulozene jako zlomky 0..1 vuci obrazku vykresu /
-- obsahu stranky).
--
-- data: [{"kind":"pen"|"number","page":"<page_key>","view":"<view_key>"|null,
--         "number":<int>|null,"points":[{"x":0..1,"y":0..1},...]}, ...]
CREATE TABLE scene_offer_markups (
  offer_id INT PRIMARY KEY,
  guest_id VARCHAR(64) NULL,
  data JSON NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_som_offer FOREIGN KEY (offer_id) REFERENCES scene_offers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
