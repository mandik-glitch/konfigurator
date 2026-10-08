-- Cislovani jizd podle vozidla (Robert 2026-08-05: "jízdy číslujme") -
-- kazde vozidlo ma vlastni sekvenci od 1 (stejny princip jako papirova
-- kniha jizd - kazde auto svuj sesit, vlastni cislovani radku).
ALTER TABLE fleet_trips
  ADD COLUMN trip_number INT NULL AFTER vehicle_id;

UPDATE fleet_trips t
JOIN (
  SELECT id, ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY started_at, id) AS rn
  FROM fleet_trips
) x ON x.id = t.id
SET t.trip_number = x.rn;

ALTER TABLE fleet_trips
  MODIFY COLUMN trip_number INT NOT NULL,
  ADD UNIQUE KEY uq_ft_vehicle_tripnum (vehicle_id, trip_number);
