# Vzhled online nabídek v generátorech stolů a u každé karty (bot10, 2026-10-07)

Robert 2026-10-07: „to nemá být jen v jedné kartě, ale automaticky v každé“, „ať se to negeneruje pořád dokola, může to být propojené do generátorů stolů a tam to může sídlit“.
Popis, kontrakt a pasti: `docs/KONTRAKT_NABIDKA_3D.md` oddíl 5m. Okno se NEPŘESUNULO do modulu: kód zůstal v `webapp/kontrola.html` (testy a mutace `_mutace_vzhled.py` / `_mutace_aomat.py` /
`_mutace_lesk.py` mají kotvy tam), generátor ho ukazuje jako iframe nad svým modelem.

- `test_kontrola_mu.js` – `kontrola.html?items=mu:<adresa GLB>&rezim=nabidka[&embed=1][&vzhled=1]` (atrapa serveru, skutečný viewer): model z adresy bez stavby serverem, okno Vzhled, ukládání barev,
  embed bez horního popisku, odmítnutí cizích adres. `WEB_DIR=<překryv webapp> node scripts/2026-10-07_vzhled_generator/test_kontrola_mu.js`.
- `test_vzhled_okno_generator.js` – okno „Vzhled online nabídek“ ve stránkách generátorů (01 / 02 / 05; most `_most_stul.py`, `PID40`, `PID45`, `PRAVIDLA_TEST={}`): jen admin, sbalené, lazy iframe, adresa modelu =
  adresa GLB generátoru, Načíst aktuální model, `?vzhled=1`. Návod ke spuštění je v hlavičce souboru; `SHOTS=<adresář>` uloží snímek okna.
- Odkaz u každé karty: `scripts/2026-10-02_nabidka_tlacitko_testy/offer_button_test.js` (T15–T28).
- Při testu kandidáta před nasazením: překryv `webapp` ze symlinků na živý strom + skutečné kopie měněných souborů (VŽDY `rm -f` před `cp`, jinak se zapíše přes symlink do živého stromu).
