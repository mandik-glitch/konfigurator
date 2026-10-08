-- Kniha jizd (Robert 2026-08-05: "mala kniha jizd, mame 3 firemni auta,
-- vytvor DB ja to doplnim VIN SPZ Nazev, sledovat budeme pozici GPS
-- mobilniho telefonu pres nasi fotoapku, uzivatel z administrace (co
-- ma roli) ma apku v mobilu, tam vznikne nove tlacitko Jizda a
-- nasledne si vybere auto kterym jede, tabulka bude sledovat kdo jede
-- cim jede a hlavne pocitat km, snimani pozice GPS automaticky kazde
-- 2 kilometry").
--
-- fleet_vehicles: firemni auta - Robert je rucne doplni v adminu
-- (VIN/SPZ/nazev), zadny seed dat zde zamerne.
CREATE TABLE fleet_vehicles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  spz VARCHAR(20) NOT NULL,
  vin VARCHAR(32) NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- fleet_trips: jedna jizda = jeden radek, od "Jizda" v mobilni fotoapce
-- do "Ukoncit jizdu". distance_km pocita mobilni klient prubezne
-- (soucet vzdalenosti mezi po sobe jdoucimi GPS body, ne jen rovna
-- cara start->konec) a server ho jen uklada - stejny duveryhodnostni
-- model jako zbytek fotoapky (INBOX_ROLES), zadna serverova validace
-- proti podvrzeni; pro interni evidenci km dostatecne.
CREATE TABLE fleet_trips (
  id INT AUTO_INCREMENT PRIMARY KEY,
  vehicle_id INT NOT NULL,
  user_id INT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ended_at DATETIME NULL,
  start_lat DECIMAL(10,7) NULL,
  start_lng DECIMAL(10,7) NULL,
  end_lat DECIMAL(10,7) NULL,
  end_lng DECIMAL(10,7) NULL,
  distance_km DECIMAL(8,2) NOT NULL DEFAULT 0,
  KEY idx_ft_vehicle (vehicle_id),
  KEY idx_ft_user (user_id),
  KEY idx_ft_status (status),
  CONSTRAINT fk_ft_vehicle FOREIGN KEY (vehicle_id) REFERENCES fleet_vehicles(id),
  CONSTRAINT fk_ft_user FOREIGN KEY (user_id) REFERENCES app_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- fleet_trip_points: GPS "checkpointy" behem jizdy - mobilni klient
-- posila novy bod pri kazdem prekroceni dalsiho 2km nasobku ujete
-- vzdalenosti (ne kazdou GPS zmenu polohy, aby to nezahltilo API/DB).
CREATE TABLE fleet_trip_points (
  id INT AUTO_INCREMENT PRIMARY KEY,
  trip_id INT NOT NULL,
  lat DECIMAL(10,7) NOT NULL,
  lng DECIMAL(10,7) NOT NULL,
  distance_km DECIMAL(8,2) NOT NULL,
  recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_ftp_trip (trip_id),
  CONSTRAINT fk_ftp_trip FOREIGN KEY (trip_id) REFERENCES fleet_trips(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
