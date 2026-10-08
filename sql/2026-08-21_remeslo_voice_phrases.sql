-- Admin-editovatelne fraze hlasoveho Moderatora (Robert, 2026-08-21:
-- "chci menit fraze kdykoli... musi to byt flexibilni"). Sparse tabulka -
-- radek existuje jen pro fraze, ktere admin skutecne prepsal; chybejici
-- radek = appka pouziva vychozi text zapsany primo v kodu
-- (webapp/remeslo-hlas.js), zadna migrace/seed neni potreba.
CREATE TABLE IF NOT EXISTS remeslo_voice_phrases (
  phrase_key VARCHAR(64) NOT NULL PRIMARY KEY,
  phrase_text TEXT NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_by VARCHAR(120) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
