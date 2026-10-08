-- Řemeslo - hlasový zápis zakázky, doplnění o hlasové potvrzení
-- (bot3, 2026-08-19). Robert: "předpokládám/doufám že naše appka
-- může na řemeslníka mluvit" + "chci to od startu zkoušet zcela
-- vlastní takže včetně Piper" - appka po úspěšném přepisu vygeneruje
-- MÍSTNÍ hlasové potvrzení (Piper TTS, hlas cs_CZ-jirka-medium,
-- žádný cloud) a uloží ho vedle přepisu.

ALTER TABLE remeslo_voice_notes
  ADD COLUMN confirmation_audio_filename VARCHAR(255) NULL AFTER transcript;
