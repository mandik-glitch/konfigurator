# Hlavní web: košaté texty kategorií mimo hliníkové profily (bot7, 2026-10-05)

Zadal Robert („Vše doplnit, zajímají nás košaté texty v ostatních kategoriích než hliníkové profily“). Zapsáno do `content_pages` (úvod, text, FAQ s FAQPage JSON-LD, související stránky) a podle potřeby do meta v `content_categories` u **74 kategorií**: vestavby do dodávek (48 bez hotových 206/311), balicí/ergonomické/montážní stoly, návody. Texty jsou editovatelné v adminu (pravidlo 55).

- **Záloha původních textů:** `backups/2026-10-05_kategorie_texty_pred_zapisem_2026-10-05_041327.json`.
- **Návrhy agentů s poli `zdroje` a `nejiste`:** `backups/2026-10-05_kategorie_texty_navrh/*.json` (u každé kategorie vypsáno, co se vědomě NEpsalo, protože není ověřené).
- **Metodika:** složeno z živého textu, výrobního programu, DB a návrhu z logiman.cz (SEO_STANDARD_TEXTY_KATEGORII.md, TEXT_FILTR 1–3, 6, 9/9a, 10–12, 16–17). Existující meta se měnila jen tam, kde chyběla, byla příliš krátká/dlouhá nebo duplicitní.
- **Zachováno:** video (183), 3D model (212), obrázky (219, 242, 243); špatné alt texty obrázků opraveny.
- **Ověřeno na živém webu:** všech 74 stránek vrací 200, má FAQ + FAQPage JSON-LD, H1 a meta description; všech 83 odkazů „Související stránky“ funguje.

## Co jsem při kontrole VYŘADIL (neověřené)
- Číslo homologace HP-0579 u Toyoty ProAce (294): je ověřené jen pro Fiat Ducato/Doblò; živý text 294 ho měl chybně a nový text ne.
- Technické údaje zvedacích sloupků (194, 201: rychlost, síla, teplota, zatěžovací cyklus, rozměr sloupku): jen z jednoho dokumentu, nepotvrzené datasheetem.
- Objemy nákladového prostoru (Iveco 287), nosnost 20–25 kg a rozměr přepravek (248), věty o dopravě „podle vzdálenosti a objemu“ (182, 183).

## K potvrzení Robertem (zůstalo v textech, bylo ze živých textů)
1. **Kategorie 193:** živý text uvádí shodu s ČSN EN ISO 6385 / ISO 14738 a nosnost 150–600 kg, produktivitu „až o 20–30 %“. Ověřit nebo zmírnit (pravidlo 3).
2. **219:** nosnost vozíku UNI.ALU45 „120 kg nebo 200 kg“ (živý text).
3. **243:** „připravujeme dveře křídlové i posuvné“ může být zastaralé. **289, 290:** výklad Řezacích stojanů a Kontrolních stolů je odvozen z umístění v nabídce.
4. **Kategorie 12 „Katalog profilů (PDF)“:** na stránce není nahraný žádný PDF; text netvrdí, kde se soubor stahuje. Nahrát PDF, nebo upravit název.
5. **TECNO** (295, 210, 184) je v názvu kategorie, nechán. **233:** HP-0579 ponecháno (živý text, ověřeno pro Ducato/Jumper/Boxer).
6. **Peugeot Expert (310):** text o zápisu do TP a homologaci je obecný z 184; potvrdit, že platí i pro Expert.
7. **Počty sestav** u modelů (Jumpy 120, Doblò 15) se do textů záměrně nepsaly (mění se, ukazuje je výpis).
8. **267:** živý úvod tvrdil „dvacet značkových přehledů“, je jich 10 (opraveno v novém textu).

## Přehled (id, název, viditelný text v znacích, FAQ, související)
- 184 Vestavby do dodávek, aut: 3799 zn., FAQ 6, související 5
- 247 Regály do auta: 3633 zn., FAQ 6, související 5
- 220 Ukládání kufrů: 1767 zn., FAQ 4, související 5
- 274 Regál na euroboxy: 2014 zn., FAQ 5, související 5
- 210 Ocelové šuplíky do aut: 1624 zn., FAQ 4, související 4
- 248 Výsuvný systém euroboxů: 1797 zn., FAQ 3, související 4
- 277 Univerzální regál: 1596 zn., FAQ 4, související 4
- 233 Vestavby pro Ducato, Jumper, Boxer: 1737 zn., FAQ 6, související 5
- 249 Úložný prostor v podlaze dodávky: 1841 zn., FAQ 4, související 5
- 260 Kotvení vestaveb do auta: 1785 zn., FAQ 5, související 4
- 244 Přívěsný vozík s úložným systémem: 1683 zn., FAQ 4, související 4
- 278 Podlahy a ložné plochy: 3533 zn., FAQ 4, související 5
- 254 Výsuvné podlahy do dodávek: 1843 zn., FAQ 4, související 4
- 246 Vyjímatelná přídavná ložná plocha dodávky: 1812 zn., FAQ 5, související 4
- 295 Šuplíkové vestavby do aut TECNO: 2230 zn., FAQ 6, související 4
- 296 Vestavby dodávek pro elektrikáře: 2053 zn., FAQ 4, související 5
- 297 Vestavby dodávek pro instalatéra: 2464 zn., FAQ 4, související 5
- 292 Výsuvy z dodávky na míru: 1873 zn., FAQ 4, související 5
- 267 Vestavby podle vozidla: 3830 zn., FAQ 6, související 5
- 268 Vestavby pro Citroën: 2971 zn., FAQ 5, související 5
- 269 Vestavby pro Fiat: 2853 zn., FAQ 5, související 5
- 270 Vestavby pro Mercedes: 2811 zn., FAQ 5, související 5
- 271 Vestavby pro Volkswagen: 2872 zn., FAQ 5, související 5
- 279 Vestavby pro Ford: 2656 zn., FAQ 5, související 5
- 281 Vestavby pro Toyota: 2486 zn., FAQ 5, související 5
- 288 Vestavby pro Peugeot: 2474 zn., FAQ 5, související 5
- 285 Vestavby pro Renault: 2138 zn., FAQ 5, související 5
- 286 Vestavby pro Opel: 2341 zn., FAQ 5, související 5
- 287 Vestavby pro Iveco: 2120 zn., FAQ 4, související 5
- 272 Vestavby pro Citroën Jumpy: 1487 zn., FAQ 4, související 4
- 273 Vestavby pro Fiat Doblò: 1725 zn., FAQ 4, související 5
- 280 Vestavby pro Ford Transit Connect: 1573 zn., FAQ 4, související 5
- 282 Vestavby pro Toyota Proace Long: 1463 zn., FAQ 4, související 4
- 283 Vestavby pro Mercedes Vito: 1543 zn., FAQ 4, související 4
- 284 Vestavby pro Volkswagen Caddy: 1381 zn., FAQ 4, související 4
- 305 Vestavby pro Renault Master: 1466 zn., FAQ 4, související 4
- 307 Vestavby pro Opel Movano: 1442 zn., FAQ 4, související 4
- 309 Vestavby pro Iveco Daily: 1479 zn., FAQ 4, související 4
- 310 Vestavby pro Peugeot Expert: 1461 zn., FAQ 4, související 4
- 293 Vestavba dodávky Ford Custom: 1558 zn., FAQ 4, související 4
- 294 Vestavby pro Toyota ProAce: 1407 zn., FAQ 4, související 4
- 300 Vestavby pro Fiat Ducato: 1521 zn., FAQ 4, související 4
- 301 Vestavby pro Mercedes Sprinter: 1504 zn., FAQ 4, související 5
- 302 Vestavby pro Volkswagen Crafter: 1446 zn., FAQ 4, související 4
- 306 Vestavby pro Renault Trafic: 1528 zn., FAQ 4, související 4
- 308 Vestavby pro Opel Vivaro: 1459 zn., FAQ 4, související 4
- 303 Vestavby pro Volkswagen Transporter: 1432 zn., FAQ 4, související 4
- 304 Vestavby pro Ford Transit: 1542 zn., FAQ 4, související 5
- 182 Balicí stoly a pracoviště na míru: 3532 zn., FAQ 6, související 5
- 183 Ergonomické balicí stoly SSE: 2340 zn., FAQ 5, související 5
- 226 Příslušenství balících stolů: 2150 zn., FAQ 5, související 5
- 289 Řezací stojany: 1182 zn., FAQ 4, související 4
- 193 Ergonomické pracovní stoly: 4341 zn., FAQ 6, související 5
- 194 Elektrické ergonomické stoly ESSE: 1834 zn., FAQ 4, související 5
- 200 Komponenty, polotovary a části stolů: 1769 zn., FAQ 4, související 5
- 207 Laminovaná dřevotříska: 1404 zn., FAQ 5, související 5
- 238 Zvedací elektrické police na míru: 1300 zn., FAQ 4, související 4
- 201 Zvedací sloupky: 1087 zn., FAQ 4, související 5
- 290 Kontrolní stoly a pracoviště: 1483 zn., FAQ 4, související 4
- 212 Montážní stoly a pracoviště: 3648 zn., FAQ 6, související 4
- 243 Bezpečnostní ochranné oplocení: 2116 zn., FAQ 6, související 4
- 213 Montážní linky na míru: 1937 zn., FAQ 6, související 4
- 239 Montážní stůl Light-30-A: 1620 zn., FAQ 6, související 4
- 240 Pojízdné pracovní stoly: 1753 zn., FAQ 5, související 4
- 241 Pracovní stoly na míru: 2150 zn., FAQ 6, související 5
- 242 Robustní pracovní stůl 45: 1962 zn., FAQ 5, související 4
- 222 Specializované pracovní stoly: 1147 zn., FAQ 4, související 4
- 219 Vozíky a stojany: 1869 zn., FAQ 6, související 4
- 291 Kuličkové ložiskové stoly: 1270 zn., FAQ 4, související 4
- 5 Návody a postupy: 2478 zn., FAQ 6, související 4
- 12 Katalog profilů (PDF): 1848 zn., FAQ 5, související 5
- 10 Instruktážní videa: 1235 zn., FAQ 4, související 4
- 9 Ukázky konfigurátoru: 1259 zn., FAQ 4, související 4
- 7 Montáž konstrukce: 1635 zn., FAQ 6, související 4
