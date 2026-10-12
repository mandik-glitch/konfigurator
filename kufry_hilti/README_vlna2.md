# Kufry Hilti pro vrtačky a aku šroubováky – podklady pro 3D modely, vlna 2 (2026-10-12)

Navazuje na `README.md` (vlna 1, ProKit). Data: `vrtacky_hilti.csv` (stejné sloupce jako `kufriky_hilti.csv`), odkazy na fotografie: `fotky_url_vlna2.tsv` (sloupce: číslo, soubor, URL, stav, rozlišení). Fotografie se do repa neukládají (jen do scratchpadu session).

## Výběr – a co NENÍ doloženo

**Prodejnost kufrů Hilti v ČR doložit nelze.** hilti.cz neuvádí pořadí prodejnosti ani hodnocení u kufrů. Na zbozi.cz (Seznam) se Hilti kufry vyskytují jen jako součást strojů („Hilti SF 6-22 Nuron + kufr“, „TE 6-22 Nuron … + kufr“ ap.), samostatný kufr s počtem hodnocení tam není. Výběr je proto **věcný, ne podle žebříčku**:

- hilti.cz má v kategorii „Kufry na nářadí“ 176 položek. Pro vrtačky/šroubováky řady 22 V (Nuron) a vrtací kladiva jsou to kufry `SF 4(H)-22`, `SF 6(H)-22`, `SF 8M-22`, `SF 10W-22`, `SF 30M-22`, `SID 6-22`, `SIW …`, `TE 2/4/6-22` a víceúčelové „2-tools / 3-tools“.
- **Zjištění:** jednoúčelové kufry jsou jen několik fyzicky shodných skořepin (liší se vložka, ne vnější tvar). Vybral jsem proto po jednom zástupci pro odlišný vnější rozměr a pro typy, které Robert jmenoval (SF/SFH, SID, TE):

| číslo | kufr | D × Š × V [mm] | stejné vnější rozměry mají také |
|---|---|---|---|
| 2284143 | SF 6(H)-22 | 444 × 395 × 122 | SF 4(H)-22 (2273024, výška 119), SID 6-22 (2264731), TE 4-A22 (2295550), SIW 8-22 ½" S (2251538) – všechny 444 × 395 × 119 |
| 2273022 | SF 4(H)-22 | 395 × 362 × 119 | ¼" SID 22V (2315464) |
| 2294834 | TE 6-22 | 495 × 395 × 149 | TE 2-A22 (2207527), TE 6-A22 (2281311), SIW 8-22 ½" L (2278588) |
| 2329229 | 2-tools (S) SF/SI | 495 × 395 × 149 | (stejná skořepina jako 2294834; vejdou se SF 4/4H/6/6H-22, SID 6-22, SIW 4AT/6/8-22, C4/C6-22 podle hilti.cz) |
| 2329206 | 2-tools (M) SF/SI + TE | 595 × 461 × 175 | (TE 2/4/6-22 + SF/SID/SIW + C4/C6 + B22 akumulátory podle hilti.cz) |

- To, že jde o kufry nejčastěji dodávané s vrtačkami, **není ověřeno** (nepodařilo se dohledat, který kufr je v balení konkrétní sady v ČR).
- Rezerva (nevybráno): `2441704` Kufr 3-tools (L) 695 × 486 × 175 a `2441703` Kufr 3-tools (XL) 795 × 439 × 195 (obojí 4 fotografie), `2264499` TE 30-22 595 × 461 × 149.
- U `SF 8M-22`, `SF 10W-22`, `SF 30M-22`, `TE 2-22`, `TE 4-22`, `SID 6-22 (02)`, `TE 8-22` hilti.cz **rozměry vůbec neuvádí**, proto nejsou vybrány.

## Co je a není z oficiálních zdrojů

| údaj | stav |
|---|---|
| vnější D × Š × V | hilti.cz, parametr „Rozměry (D x Š x V)“ na stránce produktu (kufr jako celek; zda je to vnější rozměr, stránka výslovně neříká) |
| vnitřní rozměry | **hilti.cz neuvádí** (sloupce prázdné) |
| hmotnost | **hilti.cz neuvádí** (sloupec prázdný) |
| orientační cena (hilti.cz, 2026-10-12) | 2284143 1 160 Kč, 2273022 1 005 Kč, 2294834 1 384 Kč, 2329229 1 532 Kč, 2329206 1 949 Kč |

## Fotografie (staženo do scratchpadu, `scratchpad/kufry2/<číslo>/cNN.jpg`)

Oficiální `productdata.hilti.com/APQ_HC_f2000/…`; **největší dostupné rozlišení je 1200 px** (stejně jako ve vlně 1).

| číslo | kufr | fotek | rozlišení | obsah |
|---|---|---|---|---|
| 2284143 | SF 6(H)-22 | 1 | 1200 × 940 | čelo, zavřený (L137214) |
| 2273022 | SF 4(H)-22 | 1 | 1200 × 940 | **stejný soubor L137214** – Hilti nemá pro jednoúčelové kufry vlastní fotku, je to generický záběr kufru s logem |
| 2294834 | TE 6-22 | 1 | 1200 × 940 | totéž (L137214) |
| 2329229 | 2-tools (S) | 4 | 1200 × 974, 902 × 1200 (3×) | čelo, otevřený s vložkou (3 varianty, jedna s popisem přihrádek) |
| 2329206 | 2-tools (M) | 4 | 1200 × 940, 933 × 1200 (3×) | totéž |

Hilti u jednoúčelových kufrů nenabízí víc než jednu fotku, takže **požadovaných 4–9 fotek není u tří kufrů splnitelné**. Žádná fotografie nemá kóty.

## Vhodnost pro model

- **Vhodné:** `2329229`, `2329206` – čelo (logo HILTI, madlo na víku, dvě černé západky) a pohled shora na otevřený kufr (pant, víko, vložka).
- **Použitelné s omezením (jen čelo):** `2284143`, `2273022`, `2294834`. Skořepina 495 × 395 × 149 je shodná u `2294834` a `2329229`, takže otevřený pohled lze převzít z `2329229`. Foto L137214 je generické (poměr 1200 × 940) a nemusí přesně odpovídat rozměrům 444 × 395 × 122 ani 395 × 362 × 119 – rozměr platí z hilti.cz, foto je jen vizuální předloha.
- **Problémové:** chybí pohled zezadu/zespodu a kóty; vnitřní vložky jsou na fotkách jen tvarovaný černý plast bez rozměrů.
