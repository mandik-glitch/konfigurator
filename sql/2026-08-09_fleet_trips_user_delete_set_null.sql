-- bot4, 2026-08-09. Robert: "nemuzu to smazat" - uzivatel foto-test@logiman.cz
-- (id 321) sel smazat, ale API vratilo nepouzitelnou chybu. Pricina:
-- fleet_trips.user_id byl JEDINA FK na app_users(id) bez ON DELETE SET NULL
-- (viz sql/2026-08-05_fleet_trips.sql - vsech ostatnich ~25 FK na app_users
-- ma SET NULL, tahle chybela, obycejny oversight pri zavadeni Knihy jizd).
-- MySQL default ON DELETE je NO ACTION/RESTRICT - user 321 mel 2 radky v
-- fleet_trips, DELETE FROM app_users tak spadl na FK constraint violation,
-- kterou api/app.py::admin_users_delete() nezachytavalo (zadny try/except),
-- takze frontend dostal nepouzitelnou/zadnou chybovou hlasku.
ALTER TABLE fleet_trips MODIFY user_id INT NULL;
ALTER TABLE fleet_trips DROP FOREIGN KEY fk_ft_user;
ALTER TABLE fleet_trips ADD CONSTRAINT fk_ft_user FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE SET NULL;
