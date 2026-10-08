-- Přehledy > Pravidla/Postupy (bot9, 2026-09-12) - JEDINÁ věc, která se
-- ukládá do DB: Robertovo zaškrtnutí "zobrazit ano/ne" pro daný kandidát.
-- Text pravidla/postupu se sem NIKDY nekopíruje - i u vybraných položek
-- se čte živě z .md souboru (viz api/pravidla.py, modul docstring).
-- `klic` je stabilní identifikátor kandidáta (buď název souboru, nebo
-- `SOUBOR#sekce[#index]` u položek rozpadlých na jednotlivé body).
CREATE TABLE IF NOT EXISTS pravidla_vyber (
  klic VARCHAR(300) NOT NULL PRIMARY KEY,
  zobrazit TINYINT(1) NOT NULL DEFAULT 0,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
