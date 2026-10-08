# Plán rozsekání scene.html a admin.html (bot5, 2026-09-02)

Cíl (Robert/bot3, "optimalizace procesů"): `webapp/scene.html` (1,64 MB,
30 726 řádků) a `webapp/admin.html` (1,14 MB, 21 789 řádků) čte při
každém úkolu celý bot, i když potřebuje jen zlomek. Mapa níže vznikla
JEN z `grep -n`/`wc -c` hlaviček (`<script>`, `function `, `// ====`
sekční komentáře, `data-tab=`) - přesné hranice bloků se doladí až při
samotné extrakci (diff musí být 1:1 přesun, ne přepis).

## scene.html - bloky (jeden `<script id="app-script">`, ř. 2629-30724)

| Blok (řádky) | Obsah (dle nejbližšího `function`/komentáře) | ~kB | Cíl |
|---|---|---|---|
| 1-2628 | theme toggle, importmap, CDN `<script src>` (three.js) | 60 | zůstává inline (bootstrap) |
| 2629-5783 | katalog dílů, wizard vlastního tvaru, support chat, panely | 165 | `webapp/js/scene/catalog-panels.js` |
| 5784-11452 | HDRI env mapy, drag/magnet panelů, tools menu | 300 | `webapp/js/scene/hdri-panels-ui.js` |
| 11453-12219 | automatické vsazení desky (bot4) | 40 | `webapp/js/scene/auto-deska.js` |
| 12220-16291 | interaktivní umístění vloženého tvaru na rastr | 215 | `webapp/js/scene/shape-placement.js` |
| 16292-22724 | UhelnikAut - osazení profilů úhelníky (největší geometrický blok) | 340 | `webapp/js/scene/uhelnik-automation.js` |
| 22725-25593 | path-traced 3D náhledy pro nabídku | 150 | `webapp/js/scene/path-traced-preview.js` |
| 25594-26987 | "Větrníkový" rám/čtverec | 74 | `webapp/js/scene/vetrnikovy-ram.js` |
| 26988-30724 | "Roztahuj" - živé protažení příčky | 200 | `webapp/js/scene/roztahuj.js` |

## admin.html - bloky (`<script id="app-script">` cca ř. 4867-21786)

Souvislé `// ==================== NÁZEV ====================` sekce (přes
40 nalezeno, 1 modul = 1 sekce, poměrně čistě oddělené) - seskupit podle
záložky (`data-tab=`) do souborů `webapp/admin/js/<modul>.js`:
`ceny.js` (Ceny/Spoje, ř. ~4873-6212), `crm-nabidky.js` (CRM/Nabídky/
Disk/Pipeline, ~6528-9848), `sklad-produkty.js` (Sklad/Kategorie/
Fotogalerie/Foto koš, ~9926-13442), `uzivatele-role.js` (Uživatelé/RBAC,
~13443-16083), `objednavky-doklady.js` (Objednávky/Doklady/Přijaté
doklady/Bankovní výpisy, ~16512-17631+), zbytek (`dashboard.js`, Skladové
pohyby/Nákupní objednávky/Fleet atd.) doplnit ve stejném stylu při
extrakci - přesný rozsah dohledat `grep -n "// ====" webapp/admin.html`
až se na blok dojde (netvrdit teď, co jsem nečetl vcelku).

## Pořadí extrakce (nejmenší riziko první)

1. `auto-deska.js` (scene, malé, izolované, 2026-08-09 uzavřená feature)
2. `vetrnikovy-ram.js`, `path-traced-preview.js` (scene, tematicky uzavřené)
3. `ceny.js`, `objednavky-doklady.js` (admin, stabilní staré moduly)
4. `roztahuj.js`, `shape-placement.js` (scene, aktivně používané - opatrně)
5. `catalog-panels.js`, `hdri-panels-ui.js` (scene, hodně sdílených helperů)
6. `uhelnik-automation.js` (scene, NEJVĚTŠÍ a nejsložitější - poslední)
7. `sklad-produkty.js`, `uzivatele-role.js`, `crm-nabidky.js` (admin, zbytek)

## Ověření (pro každý blok)

1. `node --check` extrahovaného souboru + `webapp/scene.html`/`admin.html`
   po vyjmutí (žádná syntax chyba).
2. `scripts/qa/e2e/run.cjs --browser chromium --viewport desktop` - žádný
   nový `E2E_PAGE_ERROR`/`E2E_CONSOLE_ERROR` na `/scene.html`, `/produkt/*`
   (scene) resp. na adminu (až bude e2e admin sekci umět).
3. Ruční smoke: otevřít stránku, projet 2-3 akce dané sekce (podle bloku -
   např. u `uhelnik-automation.js` osadit úhelník, u `roztahuj.js`
   protáhnout příčku), zkontrolovat konzoli.
4. Diff extrakce musí být `git diff` = jen přesun (smazaný blok ze
   starého souboru + `<script src="js/scene/xxx.js">`/nový soubor),
   ŽÁDNÁ souběžná refaktorizace v tomtéž commitu.

## Pravidlo

**Jeden blok = jeden commit, zámek (`scripts/lock.sh`) držený ≤ 10 min**
(vše připravené/extrahované do nového souboru PŘED acquire, zámek jen na
samotný zápis do guardovaných `webapp/scene.html`/`webapp/admin.html` +
nového `webapp/js/scene/*.js` resp. `webapp/admin/js/*.js`). Mezi bloky
release, ať nikdo nečeká. Log do `AGENTS_LOG.md` po každém bloku, ne
souhrnně na konci.
