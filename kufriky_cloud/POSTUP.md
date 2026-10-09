# Postup a pravidla – vlastní generátor organizérů PACKOUT (cloud, větev `cloud/kufriky-vlastni-cloud`)

Zadal Robert přes uživatele (2026-10-09): pět organizérů postavit **vlastním generátorem podle fotografií**, ne podle tvarů bota John.

## Tvrdá pravidla (platí pro každého, kdo sem píše)
1. **Nepoužívat Johnovy tvary.** Nečíst ani nekopírovat `kufriky_john/geometrie_organizery_v*.js`, `vytvor_doladene_tvary_v*.js`, `kufriky_john/nahled-modely-v6/modely/*`. Z `kufriky_john/` smí zdroj jen: `kufriky.csv` (rozměry – referenční), `zdroje/fotografie.csv`, `fotky/` (fotografie + `fotky/index.tsv` s URL).
2. **Žádné americké verze** (červené 48-22-xxxx z milwaukeetool.com, US katalog). Jen evropské SKU 4932xxxxxx.
3. **Fotografie se jen čtou** (`kufriky_john/fotky/<SKU>/cNN.jpg`, mapování na URL v `fotky/index.tsv`). Další fotografie nalezené na webu se stahují JEN do scratchpadu (mimo repo) a do repa se zapisuje jen jejich URL (`zdroje/<SKU>_dalsi_fotky.tsv`). Do repa nepatří žádná cizí fotografie ani její kopie/miniatura/překryv.
4. Zapisuje se jen do `kufriky_cloud/` (vlastní soubory). `jadro/` neupravovat (potřebuješ-li funkci, napiš si ji do vlastního souboru a řekni to v hlášení). Nic nesmí na `main`, nepushovat, necommitovat (to dělá koordinátor).
5. **Nic nehádat.** Co nejde ověřit z fotografií, se označí „neověřeno“ v `zdroje/<SKU>_poznamky.md`. Rozměry mimo katalog (`kufriky.csv`, obálka L×Š×V) se odvozují z fotografií (měřítko = známý celkový rozměr); u každého napsat, odkud je (číslo fotografie).
6. Obálka modelu (bounding box celého GLB) = rozměry z `kufriky.csv` (tolerance ≤ 1 mm), **model se nenatahuje** – tvary se navrhnou tak, aby obálku vyplnily.
7. Nic nevykukuje, nic nelítá: každý díl musí být ukotvený (dotýká se / zapadá do jiného dílu) a uvnitř obálky.
8. Do výstupů nesmí jít jméno dodavatele původní knihovny karoserií. České texty, stručně.

## Souřadnice a konvence souboru (katalog)
Jednotky **mm**. `X` = šířka (Š), `Y` = délka (L), `Z` = výška (V, nahoru). Počátek = střed obálky. Čelo (strana s držadlem a zámky) míří do **+X** (u kompaktního 1065 do **+Y**). Zadní (pantová) strana je opačná.

| SKU | L (Y) | Š (X) | V (Z) | vnitřní prostor Š×L×V |
|---|---|---|---|---|
| 4932471064 slim | 500 | 414 | 64 | 305×457×46 |
| 4932464082 standard | 500 | 386 | 117 | 305×457×99 |
| 4932471065 kompakt slim | 411 | 249 | 64 | 203×305×46 |
| 4932478625 hluboký | 507 | 386 | 178 | 305×457×139 |
| 4932498323 výklopné boxy | 500 | 386 | 170 | – |

(Přesné řádky `kufriky_john/kufriky.csv`.)

## Jádro generátoru (`jadro/`, JS ES moduly, bez závislostí)
- `mesh.js`: `Part(name, material)`; `roundedBox(mat,name,{x0,x1,y0,y1,z0,z1,rc,re|reB|reT,seg,fs})` zaoblené těleso (rc = poloměr svislých rohů, re = zaoblení hran); `box(mat,name,x0,x1,y0,y1,z0,z1)` ostrý kvádr; `hollowBox(mat,name,{x0..z1,rc,re,wall,floor})` dutá nádoba otevřená nahoře; `prism(mat,name,polygonXY,z0,z1)` hranol z libovolného polygonu v rovině XY (ear-clipping, bez děr); `lathe(mat,name,[[r,z]...],n,center)`, `cylinder(mat,name,r,z0,z1,n,[cx,cy])` rotační těleso kolem osy Z; `tube(mat,name,path3D,r,n)` trubka/drát po cestě; `shell`/`loftRings`/`rrRing`/`ellipseRing`/`lift` – nízkoúrovňový loft prstenců (pravidlo orientace v komentáři). `Part` má `.move(dx,dy,dz)`, `.rot('x'|'y'|'z',°,[px,py,pz])`, `.scale(sx,sy,sz)`, `.mirror('x'|'y'|'z',at)`, `.clone()`, `.bbox()`, `.append(part)`. Díly se tvoří v **souřadnicích modelu** (ne v místních), pak se přesouvají/otáčejí.
- `Group(name,{pivot,extras})`: uzel s pivotem; `.add(part…)`, `.addGroup(g)`. Pohyblivé díly (víko, výklopné boxy, držadlo) = samostatná `Group` s `pivot` na ose otáčení a `extras:{osa:[x,y,z]}` (osa otáčení v souřadnicích uzlu); díly uvnitř skupiny se stavějí ve světových souřadnicích a při zápisu se vztáhnou k pivotu.
- `glb.js`: `writeGLB(rootGroup, 'soubor.glb', meta)` a `readGLB(file)` (nezávislé čtení pro kontroly); materiály `MATERIALY`: `cerna, cerna_mat, seda, cervena, cira, cira_kour, ocel, bila, cervena_pruhl`.
- Zaoblené rohy `rrRing` mají `4*(seg+1)` bodů; zaoblení se dá volit i velmi malé (`rc: 0.5`).

## Render a srovnání
- `render/render.mjs`: `new Renderer().open(w,h)`, `.load(glb)`, `.pose({jmenoUzlu: uhel°})` (otevře víko/klopné boxy kolem `extras.osa`), `.hide([prefixy])`, `.png(kamera, soubor)`; `kamera({azim,elev,dist,fov,target,roll})` (azim 0 = pohled z +X, 90 = z +Y; elev nad horizontem).
- `render/fit.mjs`: odhad kamery z obrysu fotografie (IoU); `render/srovnej.mjs` – **celý postup jedním příkazem** (viz hlavička souboru):
  `KUF_SCRATCH=<scratchpad>/kuf node render/srovnej.mjs --glb modely/<SKU>.glb --foto ../kufriky_john/fotky/<SKU>/cNN.jpg --sku <SKU> --pohled <nazev> [--fov 20] [--pose vicko=100] [--start az,el] [--reuse]`
  → do repa `srovnani/<SKU>/<pohled>.png|json` (jen náš render + kamera + odkaz na fotku), do scratchpadu dvojice `<SKU>_<pohled>_dvojice.png` (fotografie | model | překryv obrysu) – tu si prohlédni (Read) a opravuj model, dokud nesedí. Vyšší IoU než ~0.97 je cíl; sám IoU ale nestačí – porovnej i detaily (zámek, držadlo, čelní vybrání, rohy).
- `nastroje/foto_maska.py`, `nastroje/porovnej.py` – pomocné. Výřez/zvětšení fotografie k měření: `python3 -c` s PIL (crop + resize + mřížka), vše do scratchpadu.

## Zápisky
Každý SKU: `zdroje/<SKU>_poznamky.md` – (1) které fotografie (cNN) ukazují který pohled, (2) změřené rozměry s odkazem na fotku, (3) **co je neověřeno**, (4) známé rozdíly model vs. fotografie.
