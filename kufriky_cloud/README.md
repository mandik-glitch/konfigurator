# kufriky_cloud – vlastní generátor organizérů PACKOUT (cloudová session „Karel“, 2026-10-09)

Pět organizérů Milwaukee PACKOUT postavených **vlastním generátorem** podle fotografií výrobce. Nepoužívá tvary bota John (`kufriky_john/geometrie_*`, `nahled-modely-v6` se nečetly ani nekopírovaly); z `kufriky_john/` se použily jen katalogové rozměry (`kufriky.csv`) a fotografie (`fotky/`, `zdroje/fotografie.csv`). Americké (červené) verze se nepoužily. **Fotografie jsou jen čtené, v tomto adresáři žádná není** – jen naše rendery a odkazy (URL).

Stav je návrh pro Roberta (pravidlo 60): nic není nasazeno do `webapp/` ani `api/`.

| SKU | typ | obálka L×Š×V [mm] | model | 3D náhled | poznámky (neověřeno) |
|---|---|---|---|---|---|
| 4932464082 | standard, 10 nádob | 500 × 386 × 117 | `modely/4932464082.glb` | `nahled/4932464082.html` | `zdroje/4932464082_poznamky.md` |
| 4932471064 | nízký (slim), 10 nádob | 500 × 414 × 64 | `modely/4932471064.glb` | `nahled/4932471064.html` | `zdroje/4932471064_poznamky.md` |
| 4932471065 | kompaktní slim, 5 nádob | 411 × 249 × 64 | `modely/4932471065.glb` | `nahled/4932471065.html` | `zdroje/4932471065_poznamky.md` |
| 4932478625 | hluboký, 8 oddílů, 6 děličů | 507 × 386 × 178 | `modely/4932478625.glb` | `nahled/4932478625.html` | `zdroje/4932478625_poznamky.md` |
| 4932498323 | výklopné boxy (10 boxů) | 500 × 386 × 170 | `modely/4932498323.glb` | `nahled/4932498323.html` | `zdroje/4932498323_poznamky.md` |

GLB: jednotky mm, X = šířka, Y = délka, Z = výška, počátek ve středu obálky; čelo +X (u 4932471065 +Y). Pohyblivé uzly (`vicko`, `trmen_P/L`, `box_N`, `rukojet`) mají pivot a `extras.osa`. Obálka každého GLB = katalogová obálka (odchylka ≤ 0,4 mm), model není natahován.

## Srovnání fotografie × model ze stejného úhlu
`srovnani/<SKU>/<pohled>.png|json`: **náš render** ze stejné kamery, jakou má fotografie (odhad z obrysu, IoU) + `json` s kamerou, odkazem na fotografii (`foto_repo_cesta`, `foto_url`) a nastavením pozice. Dvojice „fotografie | model | překryv“ se generují jen lokálně do scratchpadu (cizí fotografie se nevkládá do repa). Znovu: `node render/srovnej.mjs --glb modely/<SKU>.glb --foto ../kufriky_john/fotky/<SKU>/cNN.jpg --sku <SKU> --pohled <nazev>`.

Souhrn shody obrysu (IoU; `node render/kontrola.mjs`, výsledek `srovnani/kontrola.json`): 41 pohledů, 35 ≥ 0,95. Pod 0,95: 4932464082 `bok-konec-2` 0,91, `otevreny-1` 0,94, `vrsek-konec-1` 0,948; 4932471065 `otevreny-c02` 0,94, `spodek-c13` 0,94 (fotografie skloněná); 4932498323 `otevrene-boxy` 0,949. **IoU je jen shoda obrysu**, ne důkaz shody detailů do 2 mm.

## Co zůstává neověřeno (shrnutí; podrobně v poznámkách u každého SKU)
- Absolutní výšky/hloubky prvků čela ±2–3 mm (kamera je odhadnutá z obrysu, ohnisko ~10° volné); chybí přímé čelní a boční pohledy.
- Spodek, zadní strana a bok u 4932471064, 4932478625, 4932498323 nemají fotografii (odhad, nic se nepřebírá z jiného SKU bez poznámky).
- Tloušťky stěn, poloměry, úkosy, vnitřní žebrování, nápisy a logo (jen obrysy/plochy), úhly otevření a tvar třmenů v otevřeném stavu.
- 4932471064: hloubka nízkého držadla – rozpor mezi katalogovou obálkou (414 mm) a horním pohledem; 4932478625: vnitřek (dno, poloha děličů) odhad, rozpor „10 nádob“ v některých listech se nepotvrdil (na fotografiích je 8 oddílů).

## Opakování
`cd kufriky_cloud && node vytvor.mjs` (sestaví a zkontroluje obálku všech GLB); 3D náhled `node nastroje/zabal_prohlizec.mjs modely/<SKU>.glb nahled/<SKU>.html`; postup a pravidla `POSTUP.md`.
Knihovna three.js (MIT) v `vendor/`.
