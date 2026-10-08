-- Stav kilometru na tachometru (Robert 2026-08-05: "pridej sloupec
-- stav km, to se doplnuje povinne na konci jizdy"). Na rozdil od
-- distance_km (dopocitane z GPS behem jizdy) jde o RUCNI odectenou
-- hodnotu z tachometru vozidla v okamziku ukonceni jizdy - slouzi ke
-- krizove kontrole/evidenci, ne k vypoctu.
ALTER TABLE fleet_trips
  ADD COLUMN odometer_km INT NULL AFTER distance_km;
