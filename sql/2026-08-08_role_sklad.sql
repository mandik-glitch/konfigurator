-- Nova role "Skladník" (Robert 2026-08-08: "v rolích přidejme roli
-- Skladník"). Puvodni enum hodnota 'skladnik' uz znamena "Mistr" (viz
-- drivejsi prejmenovani, commit 3b11dc3) - nova role proto dostava
-- odlisny literal 'sklad', at nekoliduje se stavajicim vyznamem.
ALTER TABLE app_users
  MODIFY COLUMN role ENUM('admin','manager','user','skladnik','ucetni','monter','sklad') NOT NULL DEFAULT 'user';
