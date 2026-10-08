# LED 600 (karta #5359, SKU LED600) – model zkrácením LED 1200 (bot8, 2026-10-07)

Robert: „přidal jsem nové LED 600, do karty, udělej mu 3D model zkrácením LED 1200“.

- **Model:** `webapp/katalog/product_5359.glb` = `product_4929.glb` (LED 1200, 1247,001 mm) s PŘESNĚ vyříznutými 600 mm ze středu → 647,001 mm; průřez (85,013 × 81,049 mm) a **střed bboxu zůstává stejný** jako u LED 1200
  (stejná lokální souřadnicová soustava: X = délka), takže šablona generátoru stolu (`stul_sablona*.json`, člen LED = klon se stejnou polohou/otočením) dá 600 na stejné místo jako 1200.
  Koncovky a montážní drážky u konců jsou zachované (2 ze 3 středních drážek 324–356 / 605–637 / 884–916 mm se vyřízly se středem; zůstávají krajní 45–77 a 1170–1202 → 570–602 mm).
- **Postup:** `led_zkrat.py` (numpy, bez knihoven): přesný řez rovinami X1 = 320 a X2 = 920 mm od začátku (mimo drážky), pravý díl posunut o −600, vrcholy řezu pravého dílu přichycené na okraj levého (max 0,0052 mm –
  povrch je tesselovaný tenkými trojúhelníky s nepatrnými zlomy, průřezy ve dvou rovinách nejsou přesně shodné), vložené chybějící vrcholy do hran (bez T-spojů), sloučení vrcholů se shodnou polohou a normálou.
  Kontroly: otevřené hrany po sloučení podle polohy 64 → 42 (všechny zbylé jsou původní otevřené hrany LED 1200 u konců/drážek, na švu 0), orientace 100 % shodná s normálami, žádný degenerovaný trojúhelník,
  `trimesh` model načte (2200 trojúhelníků, 4614 vrcholů, 138 kB).
- **Karta:** `nastav_karta.py` (náhled bez `--apply`) nastaví `glb_file`, `visible_in_scene=1` (jako LED 1200; `active` se nemění – pravidlo 54) a opraví texty zkopírované z LED 1200
  (1,2 m / 33 W / 3960 lm → 600 mm / 16 W / 1920 lm; jen když jsou přesně zkopírované). Zápis: porovnej-a-nastav, rowcount, kontrola z nového spojení, `audit_log` s původními texty.
- Napojení do generátoru stolu (délka LED 1200 | 600) je samostatný krok (viz `AGENTS_LOG.md` / `docs/KONTRAKT_KONFIGURATOR_UI.md`).
