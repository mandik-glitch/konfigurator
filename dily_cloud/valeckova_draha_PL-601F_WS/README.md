# Válečková dráha Rollers.PL-601F_WS – 3D model

**Kód:** `Rollers.PL-601F_WS` · **Délka kusu:** 4000 mm · **Prodejní cena:** **1 290 Kč / ks bez DPH** (zadal uživatel 2026-10-10; cena je jen údaj v metadatech modelu, do e-shopu/DB se tímto nezapisuje).

Soubor: `PL-601F_WS_4000.glb` (mm; X = šířka 60, Y = délka 4000 vystředěná, Z = výška, spodek těla = 0). Jiná délka: `node generuj.mjs --delka 1000`. Tělo = pozinkovaný plech (průřez podle výkresu: stěna kolmo nahoru → zalomení šikmo dovnitř → přeložený obdélníkový žlábek „háček“, v němž sedí osa válečku; dno se 2 prolisy 2,8 mm při krajích), 216 plastových válečků Ø16 × 46 mm s roztečí 18,5 mm na ocelových osách. Díly: `telo_pozink`, `valecek_N`, `osa_N`.

## Kóty z výkresu × naměřeno v modelu
| kóta | výkres | model |
|---|---:|---:|
| šířka těla | 60 | 59,90 |
| výška těla (s háčky) | 23 | 23,00 |
| celková výška (po válec) | 27 | 27,00 |
| válec nad stěnu (osa ve výšce 19) | 8 | 8,00 |
| Ø válečku | 16 | 16,00 |
| délka válečku | 46 | 46,00 |
| rozteč válečků | 18,5 | 18,50 |

## Neověřeno / zjednodušeno
- Tloušťka plechu na výkresu není: model má 0,8 mm (odhad z tloušťky čar).
- Průřez je z výkresu (odečteno z obrázku, přesnost zhruba ±0,3 mm); lomená čára bez poloměrů ohybů; háček je zjednodušen na lomenou čáru, přehyb plechu v místě zalomení není rozlišen na dvě vrstvy.
- Řada otvorů ve stěnách (viditelná na fotografii) a koncové úpravy těla nejsou modelovány.
- Válečky mají jen chamfery a mělkou drážku uprostřed (podle fotografie), osy jsou zjednodušené.
- Materiály: pozinek a bílý plast jsou vizuální náhrada (barvy, ne naměřené).
