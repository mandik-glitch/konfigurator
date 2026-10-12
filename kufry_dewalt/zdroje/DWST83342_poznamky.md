# DeWalt ToughSystem 2.0 DS400 (DWST83342-1) – poznámky k modelu

Model: `kufr_DWST83342.mjs` (sdílená skořepina `ts2_kufr.mjs` + `ts2_korpus.mjs`, `ts2_vicko.mjs`, `ts2_par.mjs`, `ts2_zaklad.mjs`; výška H = 408 mm je jediný parametr, půdorys 554 × 371 mm je společný s druhým kufrem téže řady – DS300 / DS400), sestavení `node kufry_dewalt/vytvor_ts2.mjs` → `modely/DWST83342.glb` (obálka 371 × 554 × 408 mm, odchylka 0/0/0 mm; kontrola ±1 mm je ve `vytvor_ts2.mjs`).
Souřadnice: X = hloubka 371 (čelo s logem a západkami do +X, pant vzadu), Y = délka 554 (konce s madly do ±Y), Z = výška; počátek ve středu obálky. Zadání: ZAVŘENÁ verze, vnější pohled; vnitřek hladký (nemodelováno), otevřené pohledy sloužily k tvaru víka/pantu/západek.
Uzly: `korpus` (spodní díl + západky + logo), `vicko` (pivot na ose pantu x = −181, z' = 348, `extras.osa = [0,−1,0]`, `max_uhel` 105; otevření: `--pose vicko=100`) a v něm `drzadlo` (sklopné madlo v horní ploše víka, pivot na zadní hraně kapsy, osa [0,−1,0]; složené = 0°, zvednuté ≈ 90° – jako na fotografii c01).
Materiály: `cerna` (korpus, víko), `cerna_mat` (madla, páky, panty), `zluta` (těsnicí linka, logo, štítek, čepy na koncích víka), `seda_svetla` (drátové třmeny západek, očko). Barvy vybrány podle fotografií (žlutá DeWalt ≈ RGB 250/198/40, plast tmavě šedý až černý).

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL viz `../fotky_url.tsv`)
Použity studiové záběry c01–c03 (`DWST83342-1`): c01 zavřený šikmo (madlo zvednuté), c02 zavřený šikmo z druhé strany (madlo složené), c03 otevřený s vnitřkem. c04–c07 jsou aplikační snímky ze stavby (kufr je malý, jen orientačně: potvrzují sklopné madlo na koncích, stohovací západky a žlutý nálepkový štítek na čele – ten model nemá, je to odstranitelná nálepka). Fotografie nemají kóty; měřítko = datasheet výrobce 554 × 371 × 408 mm (sekundární oficiální zdroj, viz `../README.md`).

## Výsledky porovnání (IoU obrysu; `nastroje/fit_ts2.mjs`, `nastroje/iou_ts2.mjs`)
| pohled | fotografie | co | IoU | chyba landmarků | kamera / poznámka |
|---|---|---|---:|---|---|
| `sikmo-c01` | c01 | zavřený, šikmo zepředu zprava, **madlo na víku zvednuté** (póza `drzadlo=90`); kamera = obrys + landmarky | **0.871** | 4–166 px (průměr 55) | az 46.1°, el 14.2°, fov 15°, roll -1.3° – foto c01 nesedí s datasheetem, viz níže |
| `sikmo-c02` | c02 | zavřený, šikmo zepředu zleva, madlo složené; kamera = obrys + landmarky | **0.940** | 0–50 px (průměr 20) | az -42.8°, el 12.5°, fov 15°, roll -0.2° |
| `otevreny-c03` | c03 | víko otevřené (póza `vicko=100`), pohled šikmo zleva; kamera jen z obrysu | **0.936** | – | az -48.5°, el 22.7°, fov 15°, roll 4.1° – úhel víka odhad |
| `obrys-c01` | c01 | jako c01, kamera **jen z obrysu** (ohnisko 12°, bez landmarků) | **0.901** | 22–286 px (průměr 146) | az 33.7°, el 7.2°, fov 12°, roll 2.4° |
| `obrys-c02` | c02 | jako c02, kamera **jen z obrysu** (ohnisko 12°, bez landmarků) | **0.965** | 51–86 px (průměr 69) | az -43.5°, el 14.9°, fov 12°, roll -1.4° |

Dvě varianty kamery: (a) **obrys + landmarky** (hlavní řádky; kamera hledá shodu obrysu a zároveň ručně odečtených bodů, ohnisko 15°) – ta je věrohodnější, protože obrys sám kameru neurčuje jednoznačně (azimut/ohnisko/roll se vzájemně zastupují); (b) **jen obrys** (volná kamera, ohnisko 12°) – dává vyšší IoU, ale s landmarky se neshoduje (chyba landmarků desítky až stovky px), takže je to horní odhad. Postup: maska fotografie (bílé pozadí) × silueta modelu při volné kameře (azimut, elevace, vzdálenost, ohnisko pevně 12°, posuv, roll) – **kamera je odhad z obrysu, ohnisko není změřené, IoU je proto optimističtější než u kamery z ručních bodů**. Nezávislá kontrola: ručně odečtené landmarky (rohy žluté těsnicí linky a spodní roh korpusu, `zdroje/landmarky/DWST83342_*.json`) promítnuté touto kamerou; chyba je uvedena v pixelech fotografie (zobrazení 2000 px na šířku), tedy 10 px ≈ 0,5 % šířky snímku ≈ 3–6 mm. Dvojice foto | model | rozdíl obrysů byly prohlédnuty (nejen IoU). Vlastní rendery a json s kamerou jsou v `kufriky_cloud/srovnani/DWST83342/` (cizí fotografie v repu nejsou).

## Pozor: fotografie c01 kufru DS400 nesedí s datasheetem
Studiové záběry c01 obou kufrů (DS300 i DS400) jsou téměř shodné snímky; tělo kufru DS400 je na c01 jen o ~10 % vyšší než u DS300, ne o 32 % (408 : 308 mm). Fotografie c02/c03 jsou s výškou 408 mm v souladu (IoU obrysu 0,94–0,97), proto je model postaven podle datasheetu a c01 je u DS400 jen **orientační** (landmarky se na c01 nevejdou: chyba ≈ 55 px, IoU s landmarkovou kamerou nízké).

## Změřeno (z fotografií, ±5–8 mm) / odvozeno
- Celkové rozměry 554 × 371 × 408 mm: datasheet DeWalt (ne z fotografií). Poměr víko : spodní díl: výška víka nad žlutou těsnicí linkou **62 mm** (spára z' = 346) – odhad z fitu kamery (landmarky + obrys), citlivost: 76 mm dávalo horší shodu obrysu, 96 mm podstatně horší. U DS400 je celý přírůstek výšky (100 mm) ve spodním dílu (víko a západky jsou na fotografiích obou kufrů viditelně shodné).
- Čelo: dvě svislé západky (drátový třmen + černá páka) v kapsách rohových sloupků na ose Y = ±188; vybrání se štítkem a logem mezi nimi (Y ±125, hloubka 12 mm). Vodorovně polohy z poměrů v c01/c02 (±8 mm).
- Konce (±Y): kapsa sklopného madla X −160…+78, hloubka 7 mm, od z' 260 po spáru; madlo je v ní složené (černé).
- Víko: horní plocha o ~10 mm výš v pásu mezi rohovými sloupky západek (|Y| < 150) než na rohových a koncových blocích, kapsa sklopného madla v horní ploše (X ±56, Y ±140, hloubka 26 mm), žlutý čep na každém konci víka (X −82…22), štítek na čele (Y ±78) s očkem pro zámek.
- Svislé rohy korpusu: zkosení 13 mm (z silueta/landmarků – ostřejší než odhad z prvního pohledu).

## Odhady (v souladu s fotografiemi, ale neměřeno)
- Tloušťky stěn (korpus 3,5, víko 3 mm), zaoblení hran víka (poloměry ≈ 8–15 mm), spodní zkosení korpusu (9 mm), výška zvednutého madla (≈ 57 mm nad víkem, délka smyčky 78 mm), rozměry západek (páka 62 × 116, hlava 66 × 43), polohy a rozměry loga a štítku, žlutá linka (tloušťka 5,5 mm).
- Úhel otevření víka v c03 (100°) – odhad z fotografie.

## Neověřeno / zjednodušeno
- **Vnitřek je hladká vana** (stěna 3,5 mm, rovné dno) a hladké víko; nemodelovány: vnitřní vložka s přihrádkami, žebrování a komory ve víku, držák v víku, vnitřní profil spodního dílu, držáky pro Tool Connect/Tracker.
- **Spodek a zadní (pantová) strana nejsou na fotografiích vidět** (c02/c03 ukazují jen kus pantu): tvar spodní plochy (rovná, zkosená hrana 9 mm; patky/stohovací zámky nemodelovány), zadní stěna a články pantu (4 + 3 válcové články, čep) jsou **odhad**.
- Horní plocha víka je zjednodušená (skutečná má stohovací zámky, žebra a rohové bloky); stohovací západky na bocích (auto-connect) a nápisy kromě loga (DEWALT, TOUGHSYSTEM 2.0 – schematické ploché pásy a písmena z obdélníků) nemodelovány; jemná textura povrchu (zrnění) nemodelována.
- Západky, drátové třmeny a madla jsou **pevné díly** (jediné pohyblivé uzly: `vicko`, `drzadlo`); jak se západky/drát při otevírání pohybují, nemodelováno (drát je rozdělen na dolní část v korpusu a horní na víku).
- Hmotnost, vnitřní rozměry výrobce neuvádí; model je jen vnější tvar.

## Zbylé viditelné rozdíly proti fotografii
- Horní plocha víka: skutečné rohové „hlavice“ a stupně jsou jen naznačeny (plató + nižší koncové bloky); žebrování zadní hrany víka není.
- Dno korpusu: skutečná patka/stohovací výstupky (viz c02: koncové zarážky pod panely) chybí; obrys dole je proto až ~10–20 px (≈ 4–8 mm) vyšší než na fotografii.
- Vzdálený pravý roh čela v c02: landmark (roh žluté linky) je ve fitu vždy ~40–50 px od fotografie – skutečný svislý roh je ostřejší/jinak umístěný než zkosení 13 mm v modelu.
- Logo je schematické (písmena z obdélníků), štítek bez čirého krytu.
