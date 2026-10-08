# api/jazyky/ – jazykové sady serveru

Sem patří **jen** soubory `<jazyk>.json` (dvoupísmenný kód: `de`, `hu`, `pl` …), které vznikají nástrojem `scripts/miniweb_jazyk_sestav.py --lang <jazyk> --apply`
z vyplněných souborů `docs/jazyky/<jazyk>/`. **Ručně se neupravují** (opraví se zdroj a sestaví znovu). Jazyky cs / en / sk tu mít sadu nesmí – jejich texty jsou v kódu.

- Načítá je `api/jazyky.py` při startu API (moduly `stul_shop*.py`, `stul_ovladani_verejne.py`, `miniweb_objednavky.py`, `miniweb.py`); adresář lze přepsat env `JAZYKY_DIR`.
- Vadná sada se ignoruje (varování `jazyky: …` v logu), chybějící položka = anglický text.
- Formát: `lang`, `verze`, `plural`, `zdroj`, `ano_ne`, `stul_shop{TEXTY, DUVODY, NAZVY_SLOTU, TEXTY_AKCI, zpravy, info}`, `stul_shop_sse`, `ovladani`, `objednavky`, volitelně `potvrzeni`.
- Celý postup (zdroj → vyplnění bot7 → sestav → parita), pravidla textů a pasti: **`docs/jazyky/README.md`**.
- ⚠ Samotný commit JSON plánované nasazení API zatím nespustí (`scripts/nasazeni.py` sleduje jen `api/*.py`) – viz past 1 v `docs/jazyky/README.md`.
