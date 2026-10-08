-- Modul 11 (bot13, 2026-08-19) - REMESLO_KONCEPT.md
-- Nova role pro samoobsluzne ucty remeslniku, oddelena od e-shopovych
-- roli (user/manager/skladnik/ucetni/monter/sklad jsou vsechno interni
-- role, zadna neodpovida externimu remeslnikovi s vlastnim uctem).
ALTER TABLE app_users
  MODIFY role ENUM('admin','manager','user','skladnik','ucetni','monter','sklad','remeslnik')
  NOT NULL DEFAULT 'user';
