# Produktové rendery — sférický (otočný) náhled sestav

Jak vznikají obrázky produktových sestav pro e-shop. **Živý dokument** —
doplňuj, nepřepisuj historii.

Rozcestník: [`VLASTNOSTI_PROFILU.md`](VLASTNOSTI_PROFILU.md) (geometrie
spojů), [`KAROSERIE_UMISTENI.md`](KAROSERIE_UMISTENI.md) (orientace
regálu / přední směr), [`VANDR_RENDER_HOWTO.md`](VANDR_RENDER_HOWTO.md)
(rendery Vandr komponent — jiný systém, nemíchat).

---

## ⭐ Nadřazená pravidla

1. **Úložné schéma a widget se NEMĚNÍ.** Počty snímků, názvy polí,
   rozměry, cesty i veřejné API (`api/turntable.py`) jsou KONTRAKT —
   navazuje na ně widget produktu, JSON-LD, OG obrázky a sitemapa.
   Mění se jen to, **co snímky vyrobí**.
2. **Veřejně jde ven JEN turntable**, nikdy geometrie.
   3 prstence (−40/0/+40°) × 9 azimutů (270° výseč, krok 30° - OPRAVENO
   audit bot9 2026-09-12, bylo 27×10°, změněno commitem `9313f97f`
   2026-09-11) — Robert 2026-09-06, ochrana 3D modelů. Zezadu se nerenderuje.
   Viz `project_ochrana_3d_modelu_sestav`.
3. **Přední směr je vlastnost SESTAVY, ne globální konstanta.**
   Počítá se z role-tagů (`predni-svislice` vs `cap`/`zadni-svislice`);
   `FRONT_AZIMUTH_DEG = 270` je jen fallback pro sestavy bez tagů.
4. **Nová dávka nic nerozbije, dokud neproběhne commit.** Snímky se
   nahrávají s `is_active=0`; teprve `/turntable/commit` je přepne a
   starou dávku jen deaktivuje (fyzicky mizí až po 24 h grace).

---

## ⭐⭐ K ČEMU JE BLENDER V TOMHLE PROJEKTU (Robert 2026-09-09, čti první)

Doslovně: **„v blenderu nic netvoříme, vkládáme tam jen hotové sestavy
za účelem renderování."**

Z toho plyne všechno ostatní:

1. **Blender je renderovací scéna, ne nástroj na tvorbu.** Robert v něm
   nastaví vzhled (HDRI, světla, kamera, engine, vzorky) a ten vzhled se
   pak jen **používá**. Bot do něj sestavy vkládá, nic v něm nenavrhuje.
2. **Žádný autosave.** Zrušen 2026-09-09 na Robertův výslovný pokyn
   („autosave vypni") — periodické přepisování `.blend` tím, co je zrovna
   v GUI, nemá co zachytávat a jen mu přepisovalo scénu pod rukama.
   **Soubor ukládá výhradně Robert sám (File > Save).**
3. **Sérii modelů NEDĚLEJ přes kopii na každý model.** Stačí JEDNA
   soběstačná scéna (zabalené HDRI). Každá úloha si do ní model
   naimportuje **jen v paměti**, vyrenderuje a skončí **bez uložení** —
   originál tím zůstane nedotčený i bez kopírování. Kopie se dělá jen
   jednorázově, když je potřeba do souboru zabalit chybějící obrázky.

### ⚠️ ZNÁMÁ PŘÍČINA „render nevypadá jako moje scéna" (nalezeno 2026-09-09, NEOPRAVENO)

Renderování sestav dnes Blender spouští **úplně bez `.blend` souboru**:

```
sestava     →  blender -b -noaudio -P blender_render_scene.py -- cfg.json   ŽÁDNÝ .blend
blend       →  blender -b <soubor.blend> -P blender_render_blend_local.py
turntable   →  blender -b [sablona.blend] -P blender_render_turntable.py
```

Větev pro sestavy startuje z **prázdného** Blenderu a světla, kameru i
materiály si dopočítá sama v kódu (`api/blender_render_scene.py`).
Robertovo nastavení do renderu tedy nikdy nevstoupí — nejde o to, že se
„ztratí", ono se nikdy nepoužije.

**Cílový tvar** (schválený směr, zatím neimplementovaný): spustit Blender
**S Robertovým `.blend`**, naimportovat do něj GLB sestavy
(`bpy.ops.import_scene.gltf`, už se používá), vyrenderovat, skončit bez
uložení. Mechanismus „vzít šablonu na příkazové řádce" v kódu **už
existuje** — používá ho `turntable` větev, jen ho větev pro sestavy
nevyužívá.

### ⚠️ Dílna nemá správce oken (nalezeno 2026-09-09)

Na displeji `:50` neběží žádný window manager. Důsledek: Blender otevře
dialog jako samostatné okno, kterému nikdo nepředá klávesnici — **`Esc`
nefunguje a okno nemá zavírací tlačítko**. Jediná spolehlivá cesta ven je
dnes restart `blender-gui.service`. Trvalá oprava = doinstalovat lehký WM
(openbox) nebo přepnout Blender preferenci *Temporary Editors → File
Browser: Full Screen*. Nezadáno, jen nabídnuto.

---

## ⭐ PRAVIDLA RENDEROVÁNÍ (Robert 2026-09-09, po dni plném chyb)

Každý bod tu je, protože jeho porušení dnes stálo čas nebo hotový render.
Projdi je, **než** něco pustíš.

### Kontrolní seznam před každým renderem

```
1. Běží agent?        scripts/2026-09-09_turntable_status.py  → WORKER: ONLINE
2. Co je v šabloně?   světla, world, vzorky — sedí to na očekávání?
3. Jsou obrázky uvnitř?  chybějící = fialový render (doplní se automaticky)
4. Nejdřív --test     jeden snímek, ne 54 (OPRAVENO audit bot9 2026-09-12, bylo 162+5)
5. VÝHRADNĚ GPU        nikdy --local/CPU pro cokoli, co jde ukázat Robertovi
   (Robert 2026-09-22, přímo: "kurva proc CPU????????? chceme pouze GPU
   rendering") — i rychlý jednosnímkový test patří do GPU fronty.
```

**⭐ Gatekeeper rozšířen 2026-09-23 (Robert, přes bot3): "renderovat
budete oba, protože nestíháme".** bot10 přibyl jako druhý bot s přímým
právem zadávat do GPU fronty (`WORKFLOW.md` pravidlo 31), výhradně pro
VANDR větev (materiály, razítka, FBX/GLB dispatch) — nativní Logiman
`render_auto_dispatch` zůstává jen u bot4. Fronta je pořád jedna
(FIFO), takže se navzájem kontrolujeme přes
`scripts/2026-09-09_turntable_status.py`, ne přes čekání na svolení.

**POZOR - NEOVĚŘENO, tady zapsáno JEN jako otevřená otázka:** bot10
2026-09-23 tvrdí, že mu Robert přímo řekl "pokud je GPU obsazená,
renderuj na CPU serveru" pro svoje vlastní (materiálové/FBX) rendery.
To je v přímém rozporu s bodem 5 výše, který vznikl z Robertovy vlastní
ostré reakce na CPU render TÉHOŽ DNE dřív. Nepřebíral jsem to jako
platné pravidlo (slyšel jsem to jen zprostředkovaně od bot10, ne přímo)
- bod 5 zůstává v plné platnosti pro bot4. Kdyby to Robert potvrdil i
mně/obecně, sem patří jako výjimka s podmínkou ("jen když fronta
obsazená", ne default).

## ⭐ ZÁVAZNÉ pravidlo (Robert, 2026-09-23) — testovací náhledy VŽDY s úplným nastavením

**"Pravidlo testovacích renderů: testovací náhledy musí být komentovány
přesným veškerým nastavením scény."** Netýká se to jen azimutu/elevace/
počtu vzorků (to už bylo zvykem) — u KAŽDÉHO testovacího renderu, co
jde k Robertovi, musí být u obrázku napsáno VŠECHNO, co se v tu chvíli
o vzhledu rozhoduje, ne jen to, co se zrovna měnilo:

* HDRI soubor + síla
* stav ambientního světla (zapnuto/vypnuto, typ, energy, směr)
* materiál hliníku (aktuální stav/verze)
* materiál razítka (poměr sklo/diffuse, barva)
* verze mechanismu razítek, pokud se týká (orientace, rozestup, hlavní
  profil vs. všechny profily)
* počet vzorků

Důvod: Robert dělá rozhodnutí porovnáním víc renderů najednou (viz
"potřebuju vidět rendery... abych se rozhodl") - bez úplného výčtu
nejde zpětně poznat, KTERÁ kombinace nastavení konkrétní obrázek
vyrobila, obzvlášť když se mezi jednotlivými testy mění víc věcí
najednou (běžný stav při ladění materiálů).

**⭐ Vzorky u ostrých (finálních) renderů = 500** (Robert 2026-09-11,
zopakováno 2026-09-22: "ostre rendery mají mít 500 vzroků"). Zdroj
pravdy pro produkční dávky (`scripts/2026-09-14_render_auto_dispatch.py`)
je vzorek zapečený PŘÍMO v `.blend` šabloně — ten mění VÝHRADNĚ Robert
sám (viz pravidlo "Soubor ukládá výhradně Robert sám" níže), automat
žádné CLI přepínače nepřidává schválně. Pro JEDNORÁZOVÉ testovací dávky
spouštěné botem (`--samples N` u `2026-09-09_turntable_render.py`)
plati: diagnostický/rychlý test může mít nižší číslo, ale jakmile jde o
snímek, který má Robert brát jako ostrý/finální posudek materiálu, vždy
`--samples 500`.

### 1. Šablona musí být soběstačná

Blender obrázky do `.blend` **neukládá — ukládá cestu k nim**. Šablona
jde na cizí počítač, kde ta cesta neexistuje → **fialový render**.

Poznávací znamení: `img.size == (0, 0)` u nezabaleného obrázku.

Dnes to udeřilo **oběma směry**: dílna odkazovala na cestu na VPS
(fialová na Robertově PC), Robertův X30 na jeho notebook (fialová na GPU
stanici). Řeší `priprav_sablonu.py` automaticky — dohledá podle názvu na
Sdíleném disku, přepojí a zabalí.

### 2. Cizí soubor se NIKDY nemění

Robertův `.blend` je jeho. Pracuje se na **kopii**
(`sablona_<hash>.blend`). Ráno jsem mu „opravil" X30 včetně přepojení
Worldu — právem to odmítl. Doplnit chybějící soubor ano, přestavět
zapojení ne.

### 3. Dílna na VPS je Robertova (viz `WORKFLOW.md`)

Bez jeho svolení do ní nesahat. Restart služby ano — **přestavba scény
ne**. Startovní skript smí scénu stavět od nuly jen když
`vps_dilna.blend` ještě neexistuje.

### 4. V Blenderu nenačítat soubor uprostřed startovního skriptu

`bpy.ops.wm.open_mainfile()` **ukončí zbytek skriptu**. Autosave se pak
nezaregistruje, šablona zamrzne a renderu chodí zastaralá data — navenek
to vypadá, že se Robertovo nastavení ignoruje. Soubor se předává
Blenderu **na příkazové řádce**.

Kontrola: `stat` na šabloně musí ukazovat čerstvý čas.

### 5. Před zrušením renderu zjisti, jestli už neběží nebo nedoběhl

Označení `cancelled` **zahodí i hotový výsledek**. Dnes takhle zmizelo
167 vyrenderovaných snímků z GPU. Rušit má smysl jen render, který
opravdu ještě běží.

### 6. Bez agenta se nic nestane

Server nemá komu práci předat; úloha čeká. Není to chyba, jen to není
vidět. **Vždy zkontrolovat `WORKER: ONLINE` před zařazením.**

Úlohy ve stavu `waiting_worker` se **nesmí** rušit při startu aplikace —
gunicorn si nahazuje workery sám a zabíjelo to legitimně čekající práci.

### 7. Práva: co založí root, do toho `www-data` nezapíše

Dispatcher běží jako root, výsledek zapisuje Flask jako `www-data`.
Adresář pro snímky proto **zakládá až server**. Jinak `PermissionError`,
HTTP 500 a hotový GPU render je pryč.

### 8. Scéna je v MILIMETRECH

Regál má přes 2000 jednotek. Bez zvednutí `clip_end` je za ořezovou
rovinou — ve viewportu i u kamery. Platí ve **všech** layoutech.

### 9. Výchozí hodnoty rendereru jsou nouzovka, ne cíl

Když šablona nemá world nebo světla, renderer dosadí jedno slunce a
plochou šeď. Výsledek je plochý a **není to Robertovo nastavení**. Vždy
říct, že se dosazovalo.

### 10. Měřítko: jeden snímek napřed

`--test` vyrenderuje jen hero. 54 snímků (OPRAVENO audit bot9 2026-09-12, bylo 162+5) se pouští až když jeden
sedí. Vzorky ze šablony rozhodují o čase víc než cokoli jiného
(4096 ≈ 300 s, 256 ≈ 120 s na RTX 3060).

### 11. ⭐ HDRI je JEN na odlesky, NIKDY jako pozadí

Robert 2026-09-09, nad prvním povedeným renderem z X30: *„render je ok,
jen nechceme to samotné pozadí HDRI vidět, slouží pouze pro odlesky."*

HDRI mapa má **svítit a zrcadlit se v hliníku** — to je celý důvod, proč
tam je. Ale **fotka té mapy se nesmí objevit za sestavou**. Produktová
fotka na skladové kartě nemá stát na londýnském nábřeží.

Kde je to zařízené (obě renderovací větve, ať pustíš kteroukoli):

| Větev | Soubor | Jak |
|---|---|---|
| Naše sestavy (GLB) | `api/blender_render_scene.py` | Light Path trik — `MixShader` na `Is Camera Ray`: kamera vidí plochou barvu/přechod, odrazy berou skutečnou mapu. Vypínač `hdri_as_background`. |
| Robertův `.blend` — vzdálený worker | `scripts/render_worker_agent.py::run_blend_job` | `-P` skript nad **staženou kopií**: `film_transparent = True` |
| Robertův `.blend` — lokální záloha | `api/blender_render_blend_local.py` | totéž, `film_transparent = True` |

Proč u `.blend` větve `film_transparent` a ne Light Path trik: do cizího
souboru se **nesahá do zapojení nodů** (pravidlo 2 výše). `film_transparent`
je jeden přepínač na už načtené kopii — osvětlení ani odrazy nemění vůbec,
jen paprsky z kamery, které proletí kolem sestavy do prázdna, končí
průhlednou alfou místo obrázku mapy. PNG s alfou je navíc přesně to, co
fotogalerie skladové karty chce.

**Otočný náhled** (`blender_render_turntable.py`) má `film_transparent =
False` a **Light Path trik** — nasazuje si ho sám na world ze šablony
(`_bg_linear()` + `MixShader` na `Is Camera Ray`, ~ř. 429–454), takže
odrazy a osvětlení dál berou HDRI ze šablony, ale kamera vidí plochou
barvu pozadí. (Do 2026-09-09 tu HDRI opravdu tvořila pozadí — ten stav
už neplatí.)

### 11a. Jak to nastavit ručně v Blenderu (GUI)

Robert 2026-09-10: *„kde nastavim v blenderu aby se hdri nezobrazovalo,
jen na odrazy"*. **Pro naši pipeline netřeba nic** — obě větve si to
nasazují samy (tabulka výše). Tohle je pro ruční rendery a viewport.

Tři možnosti, všechny **ověřené headless na Blenderu 5.2.1** (jasně
červený world, změřený pixel pozadí):

| Postup | Co uvidí kamera | Naměřeno |
|---|---|---|
| **Light Path trik** (doporučeno) | plochou barvu, jakou zvolíš | `R .749 G .741 B .753 A 1.0` |
| Render Properties → Film → **Transparent** | průhledno | `A 0.0` → v JPEGu **černá**, nutné PNG nebo převod |
| World Properties → Ray Visibility → **Camera** odškrtnout | **černou** | `R 0 G 0 B 0 A 1.0` |

Třetí varianta je past — zní to jako „skryj HDRI před kamerou", ale
nedá průhledno ani plochou barvu, jen černou. Je jen pro Cycles.

**Light Path trik krok za krokem:**

1. Properties → **World** (ikona zeměkoule) → zapnout **Use Nodes**.
2. Editor přepnout na **Shader Editor**, nahoře typ z `Object` na **`World`**.
3. `Add → Input → **Light Path**`
4. `Add → Shader → **Mix Shader**`
5. `Add → Shader → **Background**` (druhý) — jeho **Color** = barva
   pozadí (u produktových renderů `#f2f3f5`).
6. Zapojit:
   * Light Path → **Is Camera Ray** → **Fac** Mix Shaderu
   * **původní** Background (ten s Environment Texture) → **první** Shader vstup
   * **nový plochý** Background → **druhý** Shader vstup
   * Mix Shader → **World Output → Surface**

Proč zrovna takhle: `Fac = 0` bere první vstup, `Fac = 1` druhý.
`Is Camera Ray` je 1 jen pro paprsek letící přímo z kamery — ten tedy
dostane plochou barvu, zatímco odrazy, lomy a osvětlení mají `Fac = 0`
a berou dál skutečnou HDRI mapu. Přesně tohle dělá kód v obou větvích.

Nejdřív jsem to Robertovi předložil jako volbu „buď JPEG, nebo skryté
pozadí". **Byla to falešná volba a Robert ji hned rozebral** („otočný
náhled proč nemůže být jpg?"). JPEG vadí jen *průhlednému* pozadí, ne
skrytí mapy. Skrýt HDRI před kamerou jde dvěma způsoby a jen jeden z nich
potřebuje alfu:

| Způsob | Co uvidí kamera | Formát |
|---|---|---|
| Light Path trik (`blender_render_scene.py`) | plnou barvu / přechod | JPEG i PNG |
| `film_transparent` (větev `.blend`) | průhledno | jen PNG (nebo převod) |

Takže otočný náhled **může zůstat JPEG** — buď dostane Light Path trik,
nebo se bude renderovat průhledně do PNG a převádět. Převod je hotový:
`api/png_jpg.py` + `scripts/png_na_jpg.py` (Robert: *„tak udelej prevadec
z png na jpg"*) — průhledná místa podloží zvolenou barvou, protože samotné
uložení do JPEGu by z nich udělalo **černá**. Používá ho i ukládání do
fotogalerie skladové karty (`render_gallery.py`), aby render nebyl jediná
PNG fotka mezi JPEGy.

```bash
python3 scripts/png_na_jpg.py render.png                       # bílé pozadí
python3 scripts/png_na_jpg.py slozka/ --pozadi "#f5f5f5"       # celá složka
python3 scripts/png_na_jpg.py slozka/ --kvalita 95 --smazat-png
```

Kvalita 92 a `subsampling=0` (4:4:4) schválně — vychozí 4:2:0 dělá kolem
ostrých hran hliníku barevné třepení.

### 11b. ⭐ Jen snímky z otáčení — statické pohledy se nerenderují

Robert 2026-09-11: *„vypusť hero snímek, vymaž, zapomeň"*, *„budeme
používat pouze snímky z otáčení"*, *„převezmou se z otáčkových snímků,
které určím"*.

Do 2026-09-11 se pět statických pohledů (hero, bok, zezadu, shora,
hero 16×9) renderovalo **samostatně**, vlastní těsnější kamerou. Teď se
nerenderují vůbec — každý kanonický obrázek je **odvozený ze snímku
prstence**.

**Pohled „zezadu" je zrušený.** V 270° výseči neexistuje (zadních 90° se
záměrně nerenderuje) a zadní stranu ukazovat nechceme. Zbyly čtyři:
`hero`, `side`, `top`, `hero_16x9`.

**Který snímek slouží jako který pohled, se nastavuje**, ne drátuje —
`app_settings.turntable_canonical_ring_source`, JSON
`{"hero": {"el": 0, "az": 0}, ...}` (azimut je odchylka od předního
azimutu dávky). Nesmyslná hodnota se chová jako výchozí a validuje se, že
elevace i azimut v prstenci **skutečně existují** — jinak by commit tiše
vyrobil pohled bez zdroje.

⚠️ **Mění to úhel pohledu.** Stills se renderovaly na elevaci **20**
(hero/side) a **60** (top), jenže prstenec má jen **−40, 0, 40**. Tyhle
elevace v něm nejsou, takže převzetí není bezeztrátové — výchozí mapování
míří na nejbližší dostupnou (20 → 0, 60 → 40).

⚠️ **Ořez na výšku by sestavu uřízl — proto se rám rozšiřuje do stran.**
Změřeno na skutečném snímku prstence (sestava 333, e0/a090, 2048×2048):
objekt včetně stínu je **1584 px vysoký**, kdežto ořez na 4:3 ze čtverce
dává jen 1536 — dole by zmizelo 56 px regálu. Kamera prstence je totiž
nastavená tak, aby se sestava vešla do čtverce z **nejhoršího úhlu celé
otočky**, takže svisle zabírá skoro celý rám.

`_na_kanonicky_pomer()` proto místo ořezu **dopočítá pruhy po stranách**
roztažením krajních sloupců. Pozadí je čistě **svislý** přechod (ověřeno:
levá a pravá hrana se v žádném řádku neliší víc než o 4/255, průměrně
0,8), takže je to vizuálně nerozeznatelné a neztratí se ani pixel.

**Commit dávky už statické pohledy nevyžaduje.** Do 2026-09-11 je
kontroloval a bez nich vracel 409; ta kontrola by teď zablokovala každou
dávku. Upload endpoint je dál přijímá kvůli starším klientům — uloží se a
ignorují.

### ⭐ ŽÁDNÉ STILLS SE NEDĚLAJÍ — rozhodnuto natrvalo

Robert, 2026-09-11 doslova: *„Žádné stills se nedělají, zapiš to už
navždycky do nějakého místa, kde to bude jasné — obrázky pro e-shop budou
přejímat z natáčecích snímků."*

Není to tedy jen „zbytečná práce navíc, kterou někdo někdy odstraní" —
**je to zavřená otázka.** Statické pohledy pro e-shop vznikají výhradně
převzetím z prstence (viz mapování výše). Stills se nerenderují a nikdo
je nesmí znovu zavádět; upload endpoint je dál přijímá kvůli starším
klientům, ale uloží a ignoruje — nejsou zdrojem ničeho.

Totéž je zapsané jako **pravidlo 29 ve `WORKFLOW.md`**, aby na to narazil
i ten, kdo tenhle dokument nečte.

**Sada je tím pádem 27 renderů** (OPRAVENO audit bot9 2026-09-12, bylo
81 - platilo jen při 27 azimutech/krok 10°, viz oprava výše), ne
54 (3 elevace × 9 azimutů; tier 1024 se dopočítá zmenšením masteru,
nerenderuje se).

Zbývá jen úklid kódu, který je pořád vyrábí — `webapp/scene.html::
ttStillsForFront` a renderovací pipeline. Není to chyba (server je
ignoruje), jen zbytečné snímky; kdo bude scénu upravovat, ať to vypne.

### 12. Render bez uložení do fotogalerie je za hodinu pryč

`private-files/blender-renders/<job>.png` je **dočasná odkládací složka**,
ne úložiště. `_cleanup_stale_jobs()` (`JOB_RETENTION_S = 3600`) smaže
každou hotovou úlohu hodinu po dokončení.

Trvalé místo pro hotový render = **fotogalerie skladové karty**
(`content_gallery_items`, `owner_type='product'`, soubory v
`private-files/gallery-items/`) — Robert 2026-09-09: *„chci je ukládat do
obrázků / fotogalerie skladových karet."* Žádná nová tabulka, žádné nové
úložiště: skladová karta svou fotogalerii dávno má, render je z jejího
pohledu další fotka. Zařizuje `api/render_gallery.py`, dvěma cestami:

```
automaticky   settings["gallery_product_id"] = <id skladové karty>
              → ulozit_po_dokonceni() zavolá blender_render.py (lokální render)
                i render_worker.py (render na GPU stanici) hned po "done"
              → tohle je cesta pro HROMADNÉ rendery, kde u toho nikdo nesedí

ručně         POST /api/admin/blender-render/<job>/do-galerie
              {"product_id": N, "caption": "...", "is_public": 0|1}
              → dokud běží ta hodinová lhůta
```

Zdrojový `<job>.png` se **nemaže** — v gallery-items vzniká nezávislá
kopie, aby smazání fotky z galerie nevzalo výsledek, který si okno
renderu ještě nemuselo stihnout stáhnout.

---

## CELÝ POSTUP: od složení sestavy po obrázek na e-shopu

Sedm fází. Fáze 1–3 dělá bot, který sestavu staví; 4–7 renderovací
řetězec. Detaily každého dílu jsou v sekcích níže.

```
1. bot složí sestavu ve scéně
2. uloží ji do product_assemblies
3. naváže na e-shopový produkt        ← bez toho nejde renderovat
4. zařadí do renderovací fronty
5. GPU počítač vyrenderuje 54 snímků (OPRAVENO audit bot9 2026-09-12, bylo 162+5)
6. snímky se nahrají a commitnou k produktu
7. zákazník vidí otočný náhled
```

---

### Fáze 1 — Bot složí sestavu ve scéně

Řídí se skillem **`3d-scena-spoje`** a **`VLASTNOSTI_PROFILU.md`**
(rozcestník na 8 tematických souborů). Pro regál do auta navíc
**`KAROSERIE_UMISTENI.md`** — kanonický postup je **kolizní krokování**,
ne modelování tvaru stěny.

Povinné výstupy téhle fáze, na kterých render stojí:

* **role dílů** (`parts[i].role`) — `predni-svislice`, `cap` /
  `zadni-svislice*`. Z nich se počítá **přední azimut** sestavy. Bez
  rolí spadne render na globální fallback 270° a může sestavu ukázat
  ze špatné strany.
* **geometrická platnost** — `node scripts/2026-08-19_regression_scene/run_all.js`
  musí skončit „VSECH 10 SKRIPTU OK".

### Fáze 2 — Uložení do `product_assemblies`

`data` je JSON s `parts[]` (`part_id`, `position`, `quaternion`,
`scale`, `role`), dále `bom`, `price_summary`, `join_groups`,
`frame_groups`, `_note`. Zápis hotového, **předem ověřeného** návrhu:
`scripts/2026-09-03_apply_assembly_parts.py` (bez `--apply` jen vypíše
plán; s `--apply` vždy nejdřív zálohuje původní `data` do `backups/`).

`position` jsou **světové souřadnice v mm**, v konvenci prohlížeče
(Y nahoru) — render si je převede sám.

### Fáze 3 — Navázání na e-shopový produkt

`product_assemblies.shop_product_id` **musí být vyplněné.** Otočný
náhled se ukládá k PRODUKTU, ne k sestavě — bez vazby nemá kam patřit
a rozpad úlohy skončí chybou.

> Dnes má vazbu [ověřit živě: `SELECT COUNT(*) FROM product_assemblies WHERE shop_product_id IS NOT NULL`] z [ověřit živě: `SELECT COUNT(*) FROM product_assemblies`] sestav (OPRAVENO audit bot9 2026-09-12 - číslo bylo silně zastaralé, 123/264, a mění se denně, viz sekce "Rozsah práce").

### Fáze 4 — Zařazení do fronty

```bash
api/venv/bin/python3 scripts/2026-09-09_turntable_render.py <assembly_id> \
    [--template /cesta/sablona.blend]
```

Zapíše `<job>.json` + `<job>.status.json` (`waiting_worker`) do
`private-files/blender-renders/`. Nic dalšího se nespouští — agent na
GPU počítači si úlohu vyzvedne sám při nejbližším dotazu (à 3 s).

Skript rovnou vypíše kontrolu: počet dílů, chybějící díly, přední
azimut a jestli byl spočítán z rolí nebo z fallbacku.

### Fáze 5 — Render na vzdáleném GPU

Agent stáhne job JSON, renderovací skript, **unikátní** `.glb` dílů
(128 dílů ≈ 9 souborů) a volitelnou šablonu. Spustí Blender **jednou**
na celou sestavu (`-b`, bez okna) a vrátí **jeden ZIP**.

Server ho rozbalí do `<job>.frames/`: 54 snímků prstenců (OPRAVENO audit
bot9 2026-09-12, bylo 162 - 3 elevace × 9 azimutů × 2 tiery, ne 27
azimutů) + `manifest.json` (stills od 2026-09-11 nevyžadovány, viz
`api/turntable.py`).

Průběh: `api/venv/bin/python3 scripts/2026-09-09_turntable_status.py --watch`

### Fáze 6 — Uložení k produktu ✅ AUTOMATIZOVÁNO od 2026-09-11 (OPRAVENO audit bot9 2026-09-12)

```
POST /api/product-assemblies/<id>/turntable/frames   (dávka po dávce)
POST /api/product-assemblies/<id>/turntable/commit   {"batch", "camera"}
```

Nahrané snímky mají `is_active=0` — **na e-shopu se nic nemění, dokud
neproběhne commit.** Commit ověří kompletnost (54 souborů na
disku, stills nevyžadovány) + `manifest.json`, vyrobí kanonické obrázky, přepne novou dávku
jako aktivní a starou jen deaktivuje (fyzicky mizí po 24 h grace).

**`api/turntable_ingest.py`** (volané z `api/render_worker.py` po
rozbalení ZIPu) volá tenhle upload + commit automaticky - ruční krok
zůstává jen jako záložní varianta z příkazové řádky.

### Fáze 7 — Co uvidí zákazník

* **otočný widget** na stránce produktu (`webapp/js/turntable.js`) —
  čte `GET /api/shop/products/<id>/turntable`
* **kanonické obrázky** (`<slug>-zepredu.jpg`, `-bok`, `-zezadu`,
  `-shora`, `-zepredu-16x9`) — Google Images, `og:image`, SSR hero
* **skok do scény** („fáze C") — z náhledu do 3D scény se stejnou
  kamerou, podle `camera.json`

---

### ⭐ Dvě pravidla, která render NESMÍ porušit

1. **NIKDY nerenderovat karoserii** (Robert 2026-09-08: *„pravidlo:
   NIKDY nerenderujeme karoserii !!!!!!!!"*). Do obrázku smí jen
   sestava samotná — profily, boxy, MDF výplně, doplňky. Ani průhledně
   „pro kontext". Rozpad úlohy proto díly `car_body_*` zahazuje.
   Měřit se karoserie samozřejmě dál smí (kolize, pozice dílů) — jen
   se nekreslí. Viz `KAROSERIE_UMISTENI.md`.
2. **Nikdy nerenderovat zezadu** (Robert 2026-09-06). Přední strana =
   nejdelší svislý profil nohy (`predni-svislice`), zadní = noha
   s výřezem (`cap`). Azimutová výseč 270° vynechává 90° kolem zadní
   strany. Přední směr se počítá **z rolí dílů**, nikdy pevným úhlem
   ani ze znaménka X.

---

## Dvě cesty, jak snímky vyrobit

| | **A) prohlížeč (WebGL)** | **B) Blender na vzdálené GPU** |
|---|---|---|
| kde běží | scene.html v adminovi | Robertův PC s GPU přes worker |
| kód | `webapp/scene.html` `paRenderTurntable` | `api/blender_render_turntable.py` |
| kvalita | Three.js MeshStandard + VSM stíny | Cycles, HDRI, shadow catcher |
| stav | funkční, používá se | **staví se, 2026-09-09** |

Obě zapisují do **stejného** úložiště přes stejné endpointy. Dají se
používat vedle sebe a kdykoli se vrátit k A.

> Robert 2026-09-09: *„tento blender na VPS budu já obsluhovat z hlediska
> nastavení 3D scény, zapojím nový pc s GPU do sítě a ty budeš dělat
> rendery na naše produktové sestavy podle nastavení VPS blenderu a na
> vzdáleném GPU, a ty rendery si rovnou ukládat k těm produktovým
> sestavám."*

---

## Kontrakt otočného náhledu (platí pro OBĚ cesty)

Zdroj pravdy: `api/turntable.py` (konstanty), `webapp/scene.html`
(`TT_*`, render pass). Nedublovat — číst odtamtud.

* **Prstence**: elevace `(-40, 0, 40)` × azimuty `_azimuths_for_front(front)`
  (OPRAVENO audit bot9 2026-09-12: 9 hodnot, krok 30°, ne 27×10° -
  `STEP_DEG=30` od commitu `9313f97f` 2026-09-11) × tiery
  `{2048: 2048×2048, 1024: 1024×1024}` = **54 snímků**
* **Stills** (od 2026-09-11 NEVYŽADOVÁNY - kanonické obrázky se dnes berou
  z prstence, ne ze stillů; `STILL_VIEWS` v kódu zůstává jen kvůli
  zpětné kompatibilitě se staršími klienty, kteří stills ještě posílají):
  `hero` (el 20, az front, 2048×1536), `side` (+90°), `back` (+180°),
  `top` (el 60, 2048×1536), `hero_16x9` (1920×1080)
* **Pole při uploadu**: `frame_e<el:02d>_a<az:03d>_t<tier>` (záporná
  elevace `e-40`), `still_<key>`
* **FOV** 45° svisle, okraj prstenců 1.04, stills 1.06, pozadí `#f2f3f5`
* **JPEG q92**

### ⚠️ Past: `STILL_VIEWS` elevace nejsou závazné
`api/turntable.py::STILL_VIEWS` má u stillů elevace `0`/`40`, kdežto
`scene.html::ttStillsForFront` renderuje `20`/`60`. **Řídící je
scene.html** — server u stillů validuje jen klíč a ROZMĚR
(`_validate_jpeg(raw, STILL_VIEWS[key][3])`); el/az z té tabulky se
používá výhradně ve fallbacku `_write_canonical` pro staré dávky bez
stillů. Nesjednocovat naslepo, je to nefunkční duplicita, ne chyba.

---

## Cesta B: Blender na vzdálené GPU

### Rozdělení na dva díly (a proč)

```
scripts/2026-09-09_turntable_job.py   (server, api/venv — MÁ DB, NEMÁ bpy)
        │  sestava → job JSON: absolutní cesty .glb, transformace, materiály, kamerový plán
        ▼
api/blender_render_turntable.py       (uvnitř Blenderu — MÁ bpy, NEMÁ DB)
        │  job JSON + šablona.blend → 54 snímků + manifest.json (OPRAVENO
        │  audit bot9 2026-09-12, bylo 162+5 stills)
        ▼
POST /api/product-assemblies/<id>/turntable/frames  →  /commit
```

Dělba je nutná: na Robertově GPU stanici **žádné DB spojení není**.
Worker si stáhne JSON + `.glb` soubory a to mu stačí.

### Spuštění

```bash
# 1) rozpad sestavy na úlohu
api/venv/bin/python3 scripts/2026-09-09_turntable_job.py 134 -o /tmp/job134.json

# 2) render (šablona je volitelná, ale bez ní se použijí vestavěné defaulty)
/opt/blender-5.2/blender -b -noaudio sablona.blend \
    -P api/blender_render_turntable.py -- /tmp/job134.json
```

### Zařazení do fronty (běžný provoz)

```bash
api/venv/bin/python3 scripts/2026-09-09_turntable_render.py 134 \
    [--template /cesta/sablona.blend] [--local]
```

Zapíše jen `<job>.json` + `<job>.status.json` se stavem `waiting_worker`
do `private-files/blender-renders/`. Agent na GPU stanici si úlohu
vyzvedne sám při nejbližším pollu (à 3 s) — nic dalšího se nespouští.
Skript **záměrně neimportuje Flask aplikaci**, aby šel pustit i z cronu.
`--local` = render na tomhle serveru (CPU, hodiny), jen pro ladění.

Výsledek: `<job>.frames/` (54 JPEGů + `manifest.json`, OPRAVENO audit bot9 2026-09-12, bylo 162+5).

### Worker protokol — typ úlohy `turntable`

Vedle stávajících `glb` a `blend`. Poll vrací:

| pole | co to je |
|---|---|
| `job_url` | job JSON s cestami přepsanými na **klíče** (serverové cesty ven nejdou) |
| `script_url` | `blender_render_turntable.py` — agent tak nikdy nemá starou verzi |
| `template_url` | volitelná šablona `.blend` (nebo `null`) |
| `glb_files` | seznam **unikátních** `.glb` — sestava o 128 dílech bývá jen ~9 souborů |
| `result_url` | příjem výsledku: **jeden ZIP**, ne 167 POSTů |

Blender se spouští **jednou** na celou sestavu: import 128 dílů a příprava
materiálů trvá déle než jeden snímek, spouštět ho 167× by byl nesmysl.
Skript si kameru přesouvá sám.

Bezpečnost: klíč `.glb` se **neskládá do cesty** — hledá se mezi díly
úlohy, takže projde jen soubor, který úloha opravdu používá. ZIP se
rozbaluje po položkách s kontrolou názvu (žádné cesty, žádné `../`).

Agent si od 2026-09-09 **Blender najde sám** (env `BLENDER_EXE` → `blender`
v PATH → nejnovější instalace v obvyklých adresářích), aby se na novém GPU
počítači nemuselo nic ručně nastavovat.

### Proč DVA Blendery (VPS i GPU počítač)

Robert 2026-09-09: *„ale Blender je přece na VPS"*. Ano — a přesto musí
být i na GPU počítači. Nejsou to konkurenti, každý dělá něco jiného:

| | **Blender na VPS** | **Blender na GPU počítači** |
|---|---|---|
| k čemu | Robert **nastavuje** scénu (světla, HDRI, materiály) | **renderuje** produktové sestavy |
| jak se ovládá | GUI v prohlížeči (noVNC) | nijak, jede na pozadí pod agentem |
| výkon | žádné GPU, jen CPU — hodiny na sestavu | RTX 3060 / OPTIX |

**Blender neumí renderovat na cizí GPU po síti.** Musí běžet na stroji,
kde ta karta fyzicky je. Proto se nepřenáší výpočet, ale **nastavení**:
Robert uloží šablonu `.blend` z VPS Blenderu, server ji přiloží ke každé
úloze (`template_url`) a GPU počítač renderuje **přesně podle ní**.

Nastavení tedy cestuje, rendering zůstává u karty.

### Jak se pozná počítač s GPU

**Ne přes IP.** Worker se připojuje **sám ven** (poll à 3 s + heartbeat
à 20 s), server na něj nikdy nevolá. Proto funguje za NATem, s měnící se
IP, z jakékoli sítě — a nepotřebuje port forwarding, pevnou IP ani
zásah do firewallu na Robertově straně.

| co | odkud | k čemu |
|---|---|---|
| **autentizace** | hlavička `X-Worker-Token` | jediná bezpečnostní hranice |
| **identita** | `platform.node()` = hostname stroje | popisek v přehledu |
| **GPU** | **skutečná detekce z Blenderu** (od 2026-09-09) | volba backendu + přehled |
| **IP** | `X-Real-IP` (nginx) | **jen kontrola**, neblokuje |

Server si drží **jeden** `.worker_heartbeat.json` (`{ts, name, gpu, ip}`)
a workera považuje za online, dokud je heartbeat mladší než 90 s.
Přehled: `GET /api/admin/render-worker/status`.

#### Detekce GPU je skutečná, ne deklarovaná

Do 2026-09-09 agent hlásil natvrdo `"OPTIX"` bez ohledu na to, co
v počítači je. Kdyby měl nový stroj AMD (HIP) nebo Intel (ONEAPI),
**Cycles by tiše spadl na CPU** a admin by pořád hlásil „OPTIX" — render
by byl jen záhadně pomalý a nikdo by nevěděl proč.

Teď agent při startu jednou spustí Blender (`--factory-startup`),
projde `OPTIX → CUDA → HIP → ONEAPI → METAL`, vezme první, které má
skutečná zařízení, a hlásí i jejich jména
(např. `OPTIX: NVIDIA GeForce RTX 4090`). Env `GPU_BACKEND` zůstává jako
nouzové přebití. Bez GPU vrátí `NONE` + „render pojede na CPU".

#### Kontrola IP

`RENDER_WORKER_EXPECTED_IP` v `api/.env` (není v gitu) — dnes
`81.162.200.49`, počítač s GPU. Přehled pak ukazuje `ip_matches`
true/false, takže je poznat starý notebook od nového stroje.

⚠️ **Záměrně to NEBLOKUJE.** Kdyby se IP změnila (dynamická IP, jiná
síť, VPN), rendery by tiše přestaly jezdit a nikdo by nevěděl proč.
Autentizační hranice je a zůstává token.

#### Víc počítačů: výchozí + cílené (od 2026-09-29)

- **Výchozí worker** (jméno = env `RENDER_WORKER_VYCHOZI` na serveru, dnes
  Logiman2) bere všechny úlohy bez cíle a drží `.worker_heartbeat.json`.
- **Jakýkoli jiný název** (notebook „Omen") bere **jen úlohy s
  `target_worker` = jeho jméno** (bez ohledu na velikost písmen) a píše
  heartbeat do `.worker_heartbeat.<jméno>.json`. Bez cíle mu server nedá nic,
  takže si s výchozím strojem nepřebírají práci.
- Cíl se dá zadat **jen u testovacího renderu** (panel Rendering → HDRi →
  „renderovat na", `render_na` v otisku `nastaveni_json`; dispatch skript
  pak přidá `--worker`). Automat/produkce cíl nikdy nedostanou.
- Server cíl ověří při zařazení (stroj musí být online, jinak 4xx s důvodem);
  cílená úloha na stroji, který je > 600 s offline, se změní na chybu
  (`uklidit_mrtve_ulohy_workera`), neblokuje testovací kartu.
- Seznam strojů: `GET /api/admin/render-worker/cile`. Jméno se ukáže až po
  prvním pollu agenta (= hostname, nebo env `WORKER_NAME`). Agent, který
  notebook používá pro online nabídky (Robert 2026-08-11), stačí jen spustit
  (`SPUSTIT_AGENTA.bat`): od 2026-09-09 se při startu sám aktualizuje ze
  serveru (`/api/render-worker/agent-version`). Jen verze starší než
  2026-09-09 se sama nepřepíše — tu je nutné jednou nahradit ručně.
  **Nejdřív reload serveru, pak spustit agenta na notebooku** (starý kód
  serveru zná jen jeden slot a notebook by bral i automatové úlohy).
- Nový kód v `api/*.py` se projeví až po `systemctl reload konfigurator`.

### Agent musí běžet bez dozoru

Robert 2026-09-09: *„agenta si musíš spouštět a kontrolovat sám program,
protože to může spadnout a já u toho nebudu sedět pořád"* +
*„u toho PC musíme zároveň pohlídat aby neusnul"*.

Tři vrstvy:

1. **Nespat.** Agent na Windows zavolá `SetThreadExecutionState`
   (`ES_CONTINUOUS | ES_SYSTEM_REQUIRED`) — PC se neuspí **po dobu běhu
   agenta**, a po jeho ukončení se zase uspává normálně. Záměrně se
   nepřenastavují systémová schémata napájení. `ES_DISPLAY_REQUIRED`
   schválně NE — obrazovka klidně zhasne.
2. **Restart po pádu.** `SPUSTIT_AGENTA.bat` běží ve smyčce: spadne-li
   agent, po 10 s ho spustí znovu. Návratové kódy: `1` = restartovat,
   `2` = už běží jiná kopie (nerestartovat), `3` = chyba nastavení
   (nerestartovat, opravit).
3. **Hlídač zaseknutí.** Horší než pád je, když Blender žije, ale nic
   nedělá (zamrzlý ovladač GPU). Když 15 minut nevypíše ani řádek, agent
   ho zabije a ohlásí chybu — úloha se vrátí serveru místo tichého visení.

**Autostart: běží jako Windows služba** (zdroj: Robert přímo v chatu,
2026-09-11, při výpadku stanice ve 12:25 — "to jsme davno zrusili a jede
to jako sluzba", v reakci na to, že jsme ho podle starého postupu
poslali hledat okno konzole s `.bat` souborem, které už neexistovalo a
stálo to čas uprostřed výpadku). **Přesný název služby a příkaz na
restart tady nejsou zapsané** — nikdo z botů je zatím neověřil z první
ruky. Při výpadku se na ně zeptej přímo Roberta, nehádej podle staršího
postupu.

**Kontrola ze serveru:** `scripts/2026-09-09_turntable_status.py`
(`--watch` = obnovuje à 10 s) — ukáže, jestli je worker online, z jaké
IP, s jakým GPU, a co dělá fronta. Čte jen soubory, žádná DB ani token.

### Šablona `.blend` — co si Robert nastavuje ve VPS Blenderu

**PŘEBÍRÁ se ze šablony:**
* World (HDRI / pozadí / síla) — celý, jak je uložený
* všechna světla (objekty typu `LIGHT`)
* render engine, vzorky, denoise, color management (Filmic/AgX…)
* objekt jménem **`TT_FLOOR`** — podlaha/shadow catcher (jen se posune
  pod sestavu); když chybí, vyrobí se rovina přes půdorys
* materiály jménem **`TT_ALU`, `TT_ZINC`, `TT_BLACK`, `TT_GUMA`,
  `TT_PLAST`** — když existují, díly dostanou JE (naladěné vizuálně
  v GUI) místo procedurálně postaveného Principled BSDF

**ZAHAZUJE se ze šablony:** mesh geometrie a kamery (jinak by v
produktovém renderu zůstala zkušební scéna).

**NEPŘEBÍRÁ se:** rozlišení a poměr stran — to je kontrakt widgetu
(viz výše), šablona ho nesmí přebít, jinak commit dávku odmítne.

### Materiály — kde se berou

Barva/kovovost/drsnost se řeší **na serveru**, ne v shaderu: je to
vlastnost katalogu. Přesný port `catalog-panels.js` (tabulky) +
`hdri-panels-ui.js::materialForLayer()` (pořadí rozlišení):

```
barva     = color_hex  ||  partMaterialColor[layer]  ||  #9aa0a6
kovovost  = HEX_TO_METALNESS[barva]  ??  partMaterialMetalness[layer]  ??  0.35
drsnost   = HEX_TO_ROUGHNESS[barva]  ??  partMaterialRoughness[layer]  ??  0.4
```

`shop_products` **nemá sloupec `layer`** (API vrací natvrdo `"produkt"`),
takže u produktových dílů rozhoduje výhradně `color_hex` přes `HEX_TO_*`.

**Neklasifikované zbytky** (spadnou na 0.35/0.4): u sestavy 134 je to
`#9aa0a6` ×14 (produkt bez `color_hex`) a `#26282c` ×7 (skoro černá, ale
mimo paletu `#242424`). Render tím odpovídá živé scéně — sjednotit se má
`color_hex` v DB, ne fallback v rendereru.

### Panel „Rendering → HDRi": jak se z kliknutí stane argument rendereru (bot4, 2026-09-30)

Jeden panel v adminu (`webapp/admin/js/render-panel.js`, od 2026-09-30 vlastní
soubor — dřív uvnitř `crm-nabidky.js`; `renderDriveFolderContents()` z něj
volá `renderPanelHtml()` + `renderPanelInit()`) řídí materiály, náhrady dílů,
HDRI i **světla ze souboru**. Je to jediné místo, kde Robert mění vzhled rendrů — tok je vždy
stejný a nemá se obcházet:

```
panel (JS) ──PUT──► app_settings["render_prirazeni_materialu"] (JSON)
                          │
        ┌─────────────────┴──────────────────┐
  testovací render                     automat (časovač)
  (kliknutí; otisk panelu               čte ŽIVÝ stav při KAŽDÉM zařazení,
   `nastaveni_json` jde s úlohou)       jen je-li zaškrtnuto „aktivni_pro_automat"
        └─────────────────┬──────────────────┘
        scripts/_render_prirazeni_lib.py  →  CLI argumenty turntable skriptu
```

* **API** (`api/render_hdri.py`): `GET/PUT /api/admin/render-prirazeni`,
  `GET …/rodiny`, `GET …/materialy`, `GET …/svetla?soubor=` (vrací
  `{soubor, svetla:[{jmeno,typ,vykon,vychozi}], preskoceno}`). **PUT staví
  stav od nuly z těla** — klíč, který klient nepošle, se ztratí, proto panel
  posílá celý stav. Validace: čísla se ořežou do rozsahu, `svetla_vybrana`
  musí být neprázdný seznam textů (≤ 64, jinak 400), při ukládání se ověří i
  `svetla_args` (soubor existuje a má aspoň jedno světlo).
* **Nikdy přímý zápis do `app_settings`** a **žádné automatické uložení při
  načtení panelu** (samotné otevření panelu nesmí nic změnit — hlídá test H2).
* **Překlad stavu na CLI** dělá jen `scripts/_render_prirazeni_lib.py`
  (`material_args_z_nastaveni`, `nahrady_args`, `svetla_args`). Testovací
  dispatch (`scripts/2026-09-24_render_hdri_test_dispatch.py`) i automat
  (`scripts/2026-09-23_vandr_render_auto_dispatch.py`) volají tutéž knihovnu —
  novou volbu panelu přidej **do knihovny**, ne do jednoho z nich.
* **Testovací render drží své nastavení:** dispatch bere otisk panelu
  z okamžiku kliknutí, pozdější změna panelu ho neovlivní.

**Světla ze souboru** (Robert 2026-09-29/30): zatržítko `svetla_aktivni`
(ZAPNUTO/VYPNUTO je v panelu vidět jasně), soubor `svetla_soubor` (např.
`X1_SCENA.blend` ze Sdíleného disku), násobek `svetla_sila`, a výběr
`svetla_vybrana` = jména světel. **Bez výběru platí 2 nejsilnější světla**
(`svetla_vychozi_jmena`, při shodě výkonu dřívější v souboru) — Robert: „nech
jen 2 světla". Seznam světel čte Blender (`/opt/blender-5.2/blender
--background --factory-startup` + `scripts/2026-09-09_vps_dilna/extrahuj_svetla.py`)
a cachuje do `private-files/render_materialy_v_knihovnach.json`, klíč
`svetla2|cesta|mtime` (změna souboru = nové čtení). Na CLI:
`--svetla-blend CESTA --svetla-jen=JMENO` (opakovat) `--svetla-sila X`;
`--svetla-jen` bez `--svetla-blend` = chyba parseru, neexistující jméno =
`SystemExit` (worker `api/blender_render_turntable.py` dál čte jen
`JOB["svetla"]`, beze změny).

**Kontrakt „neshoda = hlasitá chyba" (platí i pro automat):**

* Panel uložený s přejmenovaným/smazaným světlem nebo chybějícím souborem se
  **nerenderuje bez světel** — `nacti_nastaveni_pro_automat` vyhodí
  `PrirazeniNeplatne`, `zarad_render` vrátí `(False, "prirazeni v panelu je
  neplatne (automat nezarazuje, oprav panel): …")`, `main()` zapíše
  `pwc.release(…, "chyba", poznámka)` a `MAX_FAIL` automat zastaví.
  Tichý návrat `[]` je **jen** pro výpadek DB, vypnutý automat nebo
  neexistující nastavení.
* Panel totéž ukazuje: varování „NEZAŘAZUJE" ve stavu automatu + poznámka u
  seznamu světel; po opravě výběru a uložení zmizí.
* Testovací dispatch při chybě u zapnutých světel zapíše chybu do karty testu
  (nezařadí render bez světel).

**Pozor při zapnutí:** uložený stav má `svetla_aktivni=False`. Jakmile Robert
zatrhne „světla ze souboru" **a** má zapnuto `aktivni_pro_automat`, použijí se
ta 2 světla i v **produkčních automatových** renderech — je to záměr, ale
první dávku po zapnutí zkontroluj.

**Testy (spusť po každé změně panelu, knihovny nebo dispatche):**
`scripts/2026-09-30_render_panel_testy/run_all.sh` — `test_panel_svetla.js`
(20 kontrol, Playwright nad blokem panelu vyříznutým ze živého
`render-panel.js`, server je maketa v `harness.js`; hází chybu, když se
kotvy bloku v JS změní, a pak je třeba upravit extrakci v harnessu),
`test_panel_sestaveni.js` (33 kontrol: skutečná šablona + logika + falešný server,
vč. kliku na „světla ze souboru", volby stroje, fronty testů a 3D náhledu),
`test_admin_nacteni.js` (12 kontrol: celý `admin.html`, skutečná
`renderDriveFolderContents()`; `PRINT_ERRORS=1` vypíše chyby stránky k porovnání
se stavem před změnou) a `test_automat_hlasita_chyba.py` (7 kontrol,
`api/venv/bin/python3`, bez DB a Blenderu; předkontroluje, že X1_SCENA.blend je
na Sdíleném disku).

### Automat a víc strojů: Logiman2 + notebook (bot4, 2026-09-30)

Robert 2026-09-30 („má automat cílit i na notebook Omen?" — „ano"): oba automaty
(`2026-09-14_render_auto_dispatch.py` nativní, `2026-09-23_vandr_render_auto_dispatch.py`
Vandr) smějí zařadit úlohu i na notebook s renderovacím agentem. Volí to
`scripts/_render_stroje.py::vyber_stroj_pro_automat()` těsně před zařazením a výsledek jde
do `2026-09-09_turntable_render.py --worker JMÉNO` (bez cíle = Logiman2).

- **Stroj pro nabídky je pro automat VYHRAZENÝ** (od 2026-10-01, dnes Omen, env `RENDER_NABIDKY_STROJ`,
  viz další sekce): automat ho nevybere nikdy, ani volného při vytížené Logiman2. Proč: agent bere úlohy
  FIFO po jedné, nabídku čeká člověk — kdyby na stroji běžela otočka na desítky minut, nabídka by čekala za
  ní. Pravidla níže tedy platí pro **další** pomocné stroje (jiné než nabídkový); prázdná proměnná = nic
  není vyhrazeno a Omen pomáhá jako původně (Robert 2026-09-30 „ano").
- **Logiman2 má přednost.** Je-li online, volný a nepřehřátý, úloha jde na něj beze změny.
- **Notebook POMÁHÁ**, jen když je Logiman2 vytížený (něco na něm běží/čeká), přehřátý nebo offline
  **a** notebook je online (tep do 90 s, agent bere práci), agent hlásí **Blender ≥ 5.2** (šablona
  je z 5.2, starší ji nepřečte; starý agent bez verze v `gpu` tepu se nevybere), je **volný** (ani
  na něj nečeká cílená úloha — vč. Robertova testu z panelu), není přehřátý (80 °C jako brzda) a
  **posledních 50 min neskončila chybou cílená úloha** na něj (stav `error` zůstává hodinu vidět,
  `JOB_RETENTION_S`). Jinak vždy Logiman2.
- **Vypnout notebook pro automat = vypnout jeho agenta** (offline stroj se nevybere). Žádné
  nastavení v panelu není; panel jen ukazuje větu „Stroje automatu: …" pod zatržítkem automatu.
- Cílená úloha se **nikdy nepřebírá** jiným strojem ani serverem (CPU): zmizí-li notebook po
  zařazení, server ji po 10 min uzavře chybou a další běh automatu ji zařadí znovu (kandidát bez
  aktivní úlohy) — bez ručního zásahu.
- Modul jen čte (tepy `.worker_heartbeat*.json`, `*.status.json`); `python3 scripts/_render_stroje.py`
  vypíše stav strojů a kam by automat teď zařadil, `--dry-run` obou automatů totéž.
- Konstanty (`ONLINE_S`, `POLL_STALE_S`, prah teploty, pauza po chybě, jméno výchozího stroje) jsou
  kopie hodnot z `api/render_worker.py`/`_render_health_config.py`/`api/blender_render.py`; shodu
  hlídá `scripts/2026-09-30_render_panel_testy/test_vyber_stroje.py` (45 kontrol).
- **Neověřeno v provozu:** notebook dosud neběžel otočku (celý `turntable` job s ZIPem); první
  automatová úloha na něm je první skutečná zkouška → sledovat (viz `TASKS.md`).

### Rendery nabídek a testů ze scény → Omen (bot4, 2026-10-01)

Robert přes bot5, 2026-10-01: *„Online nabídky se musí renderovat na Omen."* Co se děje:

- **Kontrakt scény:** `webapp/js/scene/path-traced-preview.js` posílá v nastavení renderu `ucel: "nabidka"`
  **jen** u renderu nabídky („📄🖼 + rendery") a u testovacích renderů; živý náhled ne (jde výchozí cestou).
  Server (`api/blender_render.py::blender_render()`) čte `ucel` z formuláře a volá
  `render_worker.dispatch_to_worker_or_local(job, cfg, out, cil=render_worker.stroj_pro_ucel(ucel))`.
  Varianta `.blend` ze Sdíleného disku se nemění.
- **Omen dostane úlohu jen když je použitelný:** online (tep ≤ 90 s, agent si chodí pro práci), `gpu` tep hlásí
  **Blender ≥ 5.2** a nemá jinou práci (cílená čekající ani běžící úloha). Jinak jde render **výchozí cestou**
  (Logiman2, při jejím výpadku server) a do stavu úlohy se zapíše `note` proč.
- **Hlídač cílené úlohy** (`_hlidac_cileneho`): nevyzvedne-li ji Omen do `WORKER_CLAIM_TIMEOUT_S` (25 s; usnul,
  agent skončil), cíl se **výslovně zruší** (`target_worker=None` — je to „lepivý" klíč stavu, bez zrušení by
  úlohu nevzal nikdo; hlídá to mutační kontrola testu) a úloha jde výchozí cestou. Dál se hlídá postup jako
  u výchozího workera (240 s bez pingu → chyba). Cílená úloha se CPU serveru nikdy nepřebírá.
- **Okno renderu** už ukazuje „⚡ Omen (GPU)" (z `worker_name`), odpověď POST nese `target: "worker"` jako dřív
  + `stroj`. `/api/admin/render-worker/cile` má u stroje příznak `nabidky`.
- **Vyhrazení:** automat Omen nepoužívá (sekce výše). **Jedna proměnná** `RENDER_NABIDKY_STROJ` (výchozí `Omen`)
  řídí obě strany (server `NABIDKY_STROJ`, automat `NABIDKY_JMENO`; oba berou prostředí z `api/.env`, shodu
  hlídá test); prázdná = nabídky se nesměrují a nic není vyhrazeno.
- **Omen musí mít běžícího agenta.** Spouštěč `deploy/windows/SPUSTIT_AGENTA_NOTEBOOK.bat` (v2: agent, který
  skončí do 2 min po startu, se počítá jako pád, 5 pádů za sebou = konec s vysvětlením místo nekonečné smyčky;
  pravidlo 28) nebo služba stejným `NAINSTALOVAT_SLUZBU.bat` jako na Logiman2 (jméno stroje z `platform.node()`).
  Bez agenta jde nabídka na Logiman2 jako dosud — nikdy nevisí. Skripty jsou ve složce „Renderovací agent (PC GPU)"
  na Sdíleném disku (`scripts/2026-10-01_agent_skripty_na_disk.py` je tam nahraje z `deploy/windows/`).
- **Probouzení agenta z webu** (`wakeRenderAgent`, odkaz `logimanrender://start`): od 2026-10-01 jen když
  `/api/admin/render-worker/status` hlásí **výchozí** stroj `offline` (dřív při každém kliku → smyčka černých oken,
  viz níže). Omen web nebudí (odkaz je registrovaný na konkrétním PC, nevíme, na kterém stroji by agenta spustil).
  **Past (Robert 2026-09-30):** starý lokální `SPUSTIT_AGENTA.bat` s natvrdo zapsanou cestou k Blenderu a smyčkou
  „restartuji za 3 s" bez stropu → nekonečné černé okno „RenderAgent - C:\Temp\rende…". Odebrání odkazu na PC:
  `ODINSTALOVAT_PROTOKOL.bat` (smaže jen `HKCU/HKLM\Software\Classes\logimanrender`).
- **Testy:** `scripts/2026-10-01_render_agent_testy/` — `test_nabidky_na_omen.py` (47: výběr stroje, přesměrování,
  skutečný `/poll`, klient), `test_wake_render_agent.js` (11), `test_bat_skripty.py` (23, statická kontrola; Windows
  zde není). Změna `api/*.py` se projeví **po nasazení** — samo ve 0:00 a 12:30 (gunicorn HUP,
  `scripts/restart_konfigurator.sh --stav`), bot nerestartuje; `webapp/*` je živé hned.
- **Neověřeno v provozu:** první nabídkový render na skutečném Omenu (sleduj v okně „⚡ Omen (GPU)"; při chybě
  `*.worker_log.txt`).

### Online nabídka = stejná cesta jako karty (bot4, 2026-10-01)

Robert 2026-10-01: *„renderování v online nabídce musí mít i stejné pozadí jako automat na karty“*, *„propojit“* materiály
s panelem Rendering, *„materiály stejně jako na Vandru“*. Dřív šly obrázky nabídky (2 pohledy, „📄🖼 + rendery“ a „Test
renderů“) přes `api/blender_render_scene.py` z GLB ze scény: bez šablony `X30-02.blend`, HDRI z okna renderu, materiály podle
barev ve scéně. Teď (kdy to jde) přes **tentýž job jako nativní karta**:

- **Tok:** scéna pošle k renderu i `recipe` = `placed.map(serializeEntryForSave)` (zápis dílů jako u uložené sestavy,
  `buildRenderRecipe()`) → `blender_render()` zavolá `api/nabidka_kartova_cesta.py::zarad` → ta vybere stroj (Omen, je-li
  použitelný a volný; jinak VOLNÁ výchozí stanice), vezme volby panelu **stejnou funkcí jako automat**
  (`_render_prirazeni_lib.nacti_nastaveni_pro_automat`, vč. zatržítka „aktivní pro automat“) a spustí CLI
  `2026-09-09_turntable_render.py --nabidka-dily …` (env `KONFIGURATOR_NABIDKA_Z_API=1`, nastavuje jen API; **klíč ani pauza
  se na to nevztahují** - stejná nezamčená vrstva jako `POST /api/admin/blender-render`, běžná cesta CLI má zámek beze změny, test).
  CLI postaví job `tj.build_job_nabidka` (stejný `resolve_parts` = materiál z vrstvy/barvy katalogu, stejné pozadí
  #f2f3f5→#000000, FOV, stín; šablona, HDRI, světla, `--alu-material`, `--vd-*` z panelu) a zařadí ho jako úlohu typu
  `turntable` s `ucel: "nabidka"`. **Agent ani PC se nemění** (agent bere turntable úlohy a skript si stahuje ze serveru).
  `render_worker_tt_result` pozná `ucel` v konfiguraci úlohy, snímek převede na `<job>.png` (`vysledek_na_png`, cesta
  se kontroluje) a nastaví `done` s `job_type=None` (**sticky klíč!** bez toho by koncovka stavu nevrátila obrázek);
  klientská koncovka a galerie nabídky tedy zůstaly beze změny.
- **Co se od karty záměrně liší:** jeden snímek v tieru 1024 (ne prstenec), **bez ochranných razítek**, bez karoserie
  (jako u karet se nerenderuje), **barvy dílů ze scény (`customColor`) se ignorují** - materiál je z katalogu jako u karty.
- **Azimut:** scéna `camera_azimuth_deg` = úhel od +X (Blender), otočkový skript od +Z k +X → `a_otočka = a_scéna + 90`
  (`tj.azimut_sceny_na_otocku`, ověřeno proti vzorcům obou skriptů; mutační kontrola testu).
- **Kdy se kartová cesta NEpoužije** (pak stará cesta GLB beze změny, s poznámkou ve stavu): vypnuto
  (`RENDER_NABIDKY_KARTOVA_CESTA=0`), žádný online GPU stroj, **GPU stanice je vytížená** (před nabídkou by stála fronta;
  stará cesta si po 25 s bere úlohu na CPU), díl není v katalogu / neplatný zápis, panel Rendering neodpovídá realitě,
  CLI selže nebo nestihne 120 s (příprava šablony po změně HDRI). Po zařazení: nevyzvedne-li stroj úlohu do 90 s → chyba;
  **klient pak SÁM zkusí starou cestu** (`renderViewWithFallback`, jen kdyby selhala; zastavený render se nevrací).
  Prakticky: kartová cesta jede hlavně na **Omenu** (vyhrazený pro nabídky) nebo na volné Logiman2.
- **Materiály katalogu = Vandr (bot10, Robertovo rozhodnutí 2026-10-01):** přiřazení `render_materialy`/`render_material_key`
  zapojí bot10 do `resolve_parts`/`_render_prirazeni_lib` - protože nabídka jde přes stejný `resolve_parts`, projeví se
  v obrázcích nabídky samo, **bez úpravy exportu GLB ve scéně**.
- **Testy:** `scripts/2026-10-01_nabidka_kartova_cesta_testy/` - `test_nabidka_cli.py` (26), `test_nabidka_api.py` (46: handler,
  skutečné CLI, `/poll`, `/tt-result`, koncovka stavu, fallbacky), `test_klient_kartova_cesta.js` (23). **Past:** po mutační
  kontrole se souborem STEJNÉ délky (`+90`→`-90`) zůstal zastaralý `__pycache__/*.pyc` a test vracel starou hodnotu - po mutaci
  smazat `.pyc`.
- **Cache sloučených knihoven materiálů (2026-10-02, disk!):** `_render_prirazeni_lib.sestav_material_knihovnu` dřív pro KAŽDÉ
  zařazení (karta i každý pohled nabídky) vyrobila nový `private-files/alu_test/tmp*.blend` (13-25 MB, ~10 s Blenderu) a nikdy
  ho nesmazala: za 4 dny 303 souborů / 5,4 GB, disk `/opt` na 97 %. Teď `knihovna_<otisk>.blend` (otisk = cesty+čas+velikost
  zdrojů) se používá znovu (cache hit 0 s, obnovuje čas), nepoužívané se po 7 dnech uklidí; dispatcher testů deleguje na stejnou
  funkci. Jednorázový úklid: `scripts/2026-10-02_uklid_sloucenych_knihoven.py` (smazáno 289 souborů, 5,3 GB, jen neodkazované).
  Test `scripts/2026-10-02_knihovny_cache_testy/`. Ověřeno i jako `www-data` (uživatel API). Disk je dál z 96 % plný:
  `shared-drive` 139 GB, `blender-renders` 17 GB (603 `*.frames` složek po otočkách).
- **Neověřeno v provozu:** první skutečný GPU render nabídky touto cestou (tlačítko „Test renderů“, v okně „vzhled jako u karet“).

### Jednotná dlaždice karty: stejně velká sestava, jeden formát (bot4, 2026-09-30)

Robert 2026-09-25 „PODRUHÉ": náhledy sestav na kartách musí být všechny stejně velké a ve stejném formátu.
**Co zákazník vidí na dlaždici kategorie** je první veřejná položka galerie karty (`content_gallery_items`, ne
`thumbnails/product-<id>.jpg`, na které se cílila dřívější normalizace z 26. 9.); po najetí myší
`shop_product_images` `sort_order=1` (hover).

- **`scripts/_nahled_dlazdice.py`** vyrobí z existujícího snímku (bez renderu) čtverec **1024×1024**, kde
  **delší strana sestavy = 85 %** (šířka u dlouhé, výška u vysoké úzké; „stejná šířka" nejde, poměr stran je
  0,46–1,6), vycentrovanou, s pozadím dokresleným týmž svislým přechodem. Na všech 122 kartách: rozptyl
  2,1 p.b., 0 u hrany, jeden formát (před: 63–90 %, dva formáty). Dlaždice i hover.
- **Detekce sestavy** (verze `nd.VERZE`=2): pozadí řádku z krajních sloupců + práh 30 + min. 12 pixelů
  v řádku/sloupci. **Nepoužívat medián řádku** (selže, když sestava zabírá víc než půlku šířky → „100 % / u hrany")
  ani práh 18 (měkký stín podlahy nafoukl obálku široké sestavy o 27 p.b.). Změna algoritmu = zvýšit `VERZE`;
  verze je v názvu souboru (`…-t1024v2.jpg`), podle ní generátory přegenerují staré.
- **Kdo dlaždici vyrábí:** Vandr `2026-09-24_vandr_hlavni_nahled_z_otocky.py::zajisti_hlavni_nahled_z_otocky`
  (volá ho i `card_activate` při aktivaci nové karty); nativní `api/turntable.py::_fill_gallery_and_thumbnail`
  (`_uloz_galerijni_dlazdici`, z `hero_1x1`, při chybě záloha = kopie hero) — **nasazeno 2026-10-01**;
  jednorázové přepnutí existujících karet + hover:
  `2026-09-30_dlazdice_nativni_a_hover.py [--apply] [--znovu]` (jako `www-data`, hover jde do nové složky
  `gallery/vestavby-hover-t1024v2/`, stará `vestavby-hover/` je root-vlastněná).
- Staré soubory zůstávají na disku (surové snímky), původní řádky DB jsou v
  `backups/2026-09-30_dlazdice_pred_normalizaci.json` — návrat = vrátit `filename` z té zálohy.
- **Nedotčeno (zatím):** storefrontové karty (`api/car_storefronts.py`, `card_image_url` z `canonical.json`
  aktivní dávky: `hero`/`hero_1x1`, hover `hero_1024`/`side_1024`) pořád ukazují surové kanonické snímky.
- Testy: `scripts/2026-09-30_nahledy_karet_testy/run_all.sh` (29 + 10 kontrol).

### Pasti, které už stály čas

1. **`cam.clip_end`** — výchozích 100 jednotek je pro scénu
   v MILIMETRECH (regál ~2000) daleko málo, model skončí za clip rovinou.
2. **`flatShading` / `shade_flat`** — GLB profily mají průměrované vertex
   normály přes hrany průřezu; bez toho vypadají ostré 90° hrany zaoblené.
   Není to vada zdrojáku, je to artefakt hladkého stínování.
3. **Souřadnice** — prohlížeč Y-nahoru, Blender Z-nahoru, glTF importer
   převádí `(x,y,z) → (x,-z,y)`. Transformace dílu je zapsaná
   v souřadnicích PROHLÍŽEČE, musí se tedy konjugovat:
   `M_blender = C · M_three · C⁻¹`.
4. **Bez šablony se MUSÍ zahodit Blenderova startovní scéna**
   (`read_factory_settings(use_empty=True)`) — jinak se její tmavý world
   a slabé bodové světlo tváří jako „šablona, co už world i světlo má",
   fallbacky se nespustí a render vyjde skoro černý. (Nalezeno
   2026-09-09 při prvním zkušebním běhu.)

### Kamerová matematika

Doslovný port `scene.html`: `ttCameraPosition`, `ttComputeDistance`,
`ttFitStill` (OPRAVENO audit bot9 2026-09-12: řádkové odkazy tu byly
zastaralé o ~700 řádků a časem se rozejdou znovu - hledej `grep -n
"function ttCameraPosition\|function ttComputeDistance\|function
ttFitStill" webapp/scene.html` místo pevného čísla). Odvození vzorců je
okomentované tam — sem se nekopíruje, aby nevznikly dvě verze pravdy.
Prstence sdílejí JEDNU vzdálenost pro všech 27 směrů (OPRAVENO audit bot9 2026-09-12, bylo 81 - 9 azimutů × 3 elevace, ne 27×3); stills mají každý
vlastní těsný fit včetně posunu cíle kamery (8 iterací).

---

## Ochranné logo v geometrii (LOGIMAN.CZ)

Robert 2026-09-08: *„logo nebude červené ale jakoby součást profilu"*,
*„nechá vystupuje z profilu"*. Není to nálepka ani 2D vodoznak přes
obrázek — je to **skutečná 3D geometrie vložená do sestavy**, takže
vodoznak nejde odstranit ořezem ani přebarvením a je v každém z 54
snímků (OPRAVENO audit bot9 2026-09-12, bylo 162). Zapadá do `project_ochrana_3d_modelu_sestav` (3 stupně důvěry).

### Jak je to uložené

Logo je běžný díl sestavy — `part_id = "logo_logiman_cz"`
(`cfg_dily`, `layer='alu'`, GLB `webapp/katalog/logo_logiman_cz.glb`),
s rolí **`logo-ochrana-<N>`** v `product_assemblies.data.parts`.
Renderovací pipeline ho proto bere automaticky jako každý jiný díl,
žádná zvláštní větev v kódu není potřeba.

### Pravidlo umístění (z dema `scripts/2026-09-08_logo_3d/`)

* GLB je v přirozené orientaci: řádek textu podél **X**, výška podél
  **Y**, tloušťka rytiny podél **Z**
* otočí se o **90° kolem Z** → řádek běží podél **délky** profilu,
  výška textu (4,5 mm) napříč šířkou profilu (30 mm)
* posadí se na vnější stěnu profilu tak, aby **vnitřní plocha lícovala
  s povrchem** → celá tloušťka vystupuje ven (vypadá jako vytlačená
  část profilu)
* **materiál výplně drážky = stejný jako hliníkový profil** (`#c9cdd1`,
  metal 0,60, rough 0,35) — vychází samo z `layer='alu'`, žádné zvláštní
  ošetření. **Logo samo od 2026-09-11 NE** — má vlastní barvu, viz
  "Barva loga" níže (dřívější tvrzení tady platilo jen do té doby).

### Stav — ✅ HOTOVO (OPRAVENO audit bot9 2026-09-12, popis níže platil jen do vzniku `scripts/razitkovac.py`)

**`scripts/razitkovac.py` (`OTISK_VERZE=6`) je hotový, nasazený nástroj** - automaticky umísťuje logo (+ výplň drážky pod ním) na profily podle pravidel v `RAZITKOVAC_PLAN.md`. K 2026-09-12 aplikován na 10 sestav (134, 340-347, 369). Zbývající otevřené otázky (čitelnost reliéfu, barva loga) viz aktuální poznámky, ne jako nedodělaný úkol - text pod touto poznámkou je historický popis PŘED vznikem nástroje:

1. **Bylo neautomatické do vzniku razítkovače.** Logo mělo **1 sestava z 264** (id 134, Doblo A,
   4 instance `logo-ochrana-0..3`), umístěné ručně. Pro zbytek
   chyběl algoritmus: které profily logo dostanou, kolik instancí a jak
   je rozmístit, aby bylo vidět ze všech 27 azimutů × 3 elevací.
   Rozmístění u 134 pokrývá zadní rovinu (0, 1), podlahovou úroveň (2)
   a přední rovinu (3) — to byl tehdy jediný vzor, ze kterého se dalo
   pravidlo odvodit.
2. **Reliéf je při plochém světle nečitelný.** Ověřeno renderem
   2026-09-09: logo se správně vytlačí z profilu a má správný materiál,
   ale bez šikmého (grazing) světla nemá kontrast a text splyne
   s profilem. Řeší se **v šabloně** (HDRI + směr klíčového světla) —
   je to důvod navíc, proč šablonu ladit vizuálně a ne od stolu.
3. Nerozhodnuto: má logo být i na snímcích prstenců, nebo jen na
   veřejných kanonických obrázcích? (Dnes je v geometrii, takže ve
   všech.)

### Zadání: razítkovač profilů (Robert 2026-09-09)

Nástroj, který bod 1 výše vyřeší — **automaticky** posadí logo na profily
sestavy místo dnešního ručního umístění u jediné sestavy.

**⭐ Podmínka, kterou Robert doplnil hned k zadání:** *„3D logo nech má pod
sebou i vyplněnou drážku."* Logo nesmí viset nad prázdným profilem drážky,
pod ním má být plný materiál. Tím se úkol mění z „umísti jeden díl" na
**„umísti dvojici: logo + výplň drážky"**.

Co k té výplni už je zjištěno (ověřeno 2026-09-09):

* **Jako díl neexistuje.** V `cfg_dily` není žádná krytka ani lišta do
  drážky a v `webapp/katalog/` k tomu není GLB. Bude se muset generovat
  jako geometrie na míru, ne vybírat z katalogu.
* **Není to jeden rozměr** — drážka se liší podle profilu
  (`PROFILY_KATALOG.md`, vše potvrzené Robertem proti konkrétním produktům):

  | drážka | profily |
  |---|---|
  | 6 mm | 20×20, 20×40, 20×80, 10×40 |
  | 8 mm | 30×30 (Light), 30×60, 35×35 |
  | 10 mm | 40×40 SuperLight S10, 40×80 S10 |

  Výplň proto musí být parametrická podle profilu, na který logo dosedne.
* Logo je 223,22 × 28,0 × 1,39 mm, stěny profilů mají 30–45 mm — logo
  drážku **vždy** přejde napříč. Není to okrajový případ, je to pravidlo.

**Pozor na souběh:** běží úkol bot9 (`TASKS.md`) — nové číslování sestav
`K-XXX <verze> XXXXY` + číselník, rozpis boxů se má z názvu přesunout do
atributu. Cokoli, co se opírá o **název** sestavy, se po tom přejmenování
rozejde. Razítkovač se tedy nesmí opírat o názvy.

**Plán: `RAZITKOVAC_PLAN.md`** (kořen repa) — změřené podklady, postup po
krocích a otázky k rozhodnutí. Předávka se zadáním: `scripts/handover.py show 101`.

Dva nálezy z přípravy plánu, které patří rovnou sem, protože opravují
tvrzení výše:

* Pravidlo „otočí se o **90° kolem Z**" v odstavci o umístění **neplatí** pro
  žádnou ze 4 uložených instancí — je to jen speciální případ z dema. Obecně
  je orientace `makeBasis(T, N×T, N)`, kde `T` je dlouhá osa profilu a `N`
  vnější normála stěny; ověřeno na všech 4 s odchylkou 0,000°.
* Vnější stěna profilu 30×30 **není plochých 30 mm** — materiál je 2 × 9,57 mm
  a mezi tím otevřená drážka, takže **8,20 mm z 28mm loga přemosťuje prázdno**.
  `Box3` to hlásí jako lícující dotyk, žádný stávající test to nezachytí. Právě
  proto je Robertova podmínka s vyplněnou drážkou oprava vady, ne kosmetika.

### Barva loga — patří do `cfg_dily`, ne do dat sestavy (bot16, 2026-09-11)

⚠️ **HODNOTA SE MĚNÍ V ŘÁDU HODIN (OPRAVENO audit bot9, 2026-09-12 - vlastní zápis "#D4863F" psaný o pár hodin dřív už stihl zestárnout, mezitím na "#EB8E23"): NEPIŠ sem konkrétní hex/metalness/roughness číslo, vždycky zestárne.** Aktuální hodnoty vždy přímo v `scripts/razitkovac.py` (`LOGO_BARVA_HEX`/`LOGO_METALNESS`/`LOGO_ROUGHNESS`/`LOGO_TRANSMISSION`/`LOGO_IOR`, i s komentovanou historií kandidátů). Mechanismus a princip popsaný níže (barva patří do `cfg_dily`, ne do dat sestavy) je to, co tady má zůstat platné - ne konkrétní čísla.

Robert (přes bot3): *„na razítka musíme přidat barvu, lehce oranžovou."*
Logo dostalo (PŮVODNĚ, viz upozornění výše pro aktuální hodnotu)
`LOGO_BARVA_HEX = "#C97A3D"` (`scripts/razitkovac.py`).

**⭐ Obecné pravidlo, které to odhalilo:** `razitkovac.orazitkuj_data_sestavy()`
→ `prerazitkuj()` VÝSLOVNĚ odstraňuje `color_hex`/`base_color`/`metalness`/
`roughness` z dílů, než je uloží do `product_assemblies.data.parts`
(`_JEN_PRO_RENDER`) — je to SPRÁVNĚ pro každý běžný díl, protože materiál
se má vždy znovu odvodit z katalogu podle `part_id` (`resolve_parts()` /
`fetch_katalog_parts()`), ne konzervovat jako zamrzlá kopie v datech
konkrétní instance. **Jinak řečeno: cokoli v tomhle projektu, co má mít
vlastní/pevnou barvu odlišnou od `layer`, tu barvu MUSÍ mít zapsanou
v `cfg_dily.color_hex` (katalogový řádek), NIKDY jen jako override
postavený za běhu v generátoru dílu** (razítkovač, nebo cokoli
podobného v budoucnu) — takový override přežije jen jednorázový živý
náhled, po prvním uložení a znovunačtení zmizí a nahradí ho katalogový
default.

Přesně tahle past logo chytla: barva byla zapojená jen v
`_razitko_pro_profil()` (dict stavěný za běhu), zatímco
`cfg_dily.logo_logiman_cz.color_hex` zůstávalo `NULL`
(`layer='alu'`, nastaveno 2026-09-09 záměrně jako "vypadá jako hliník" -
platné do téhle změny). Po prvním `--zapsat` by tedy barva na chvíli
"byla vidět" (živý náhled), ale po dalším renderu/zobrazení by zmizela
zpátky na hliníkovou — chyba, která se neprojeví hned, ale až při druhém
čtení, takže se typicky odhalí draze/pozdě.

**Oprava:** `cfg_dily.color_hex = '#C97A3D'` pro `logo_logiman_cz`
(`scripts/2026-09-11_logo_barva_katalog.py`), plus stejný hex doplněný
do `HEX_TO_METALNESS`/`HEX_TO_ROUGHNESS` na obou stranách
(`scripts/2026-09-09_turntable_job.py` a JS protějšek
`webapp/js/scene/catalog-panels.js`), aby přesně seděly
`LOGO_METALNESS`/`LOGO_ROUGHNESS` (PŮVODNĚ 0,65/0,30, hodnota se od té
doby měnila víckrát - viz upozornění na aktuální hodnotu výše, vždy
ověřit živě v kódu) místo fallbacku na vrstvu
`alu` (0,6/0,35). `vypln_drazky_30.color_hex` zůstává `NULL` záměrně —
výplň drážky má dál barvu hostitelského profilu, Robert chtěl barvu jen
na logu.

---

## GUI Blender na VPS (kde Robert ladí scénu)

Blender běží headless na virtuálním displeji a je dostupný v prohlížeči
přes noVNC. Řetězec:

```
prohlížeč → nginx :8300 → websockify :6950 → x11vnc :5950 → Xvfb :50 → blender
```

Přístup: `http://75.119.132.164:8300/vnc.html` (OPRAVENO bot9
2026-09-13: stará IP `80.211.210.103` na tomhle serveru neplatí, server
se přestěhoval, viz `PRISTUPY.md`; vhost
`/etc/nginx/sites-available/blender-vnc`, `satisfy any` — Robertova IP
projde bez hesla, jinak basic auth `/etc/nginx/.htpasswd-blender-vnc`).

### Restart

Od 2026-09-09 běží jako **systemd jednotky**, ne jako procesy Claude
session — přežijí konec session i pád jednotlivého bota:

```bash
systemctl restart blender-xvfb blender-x11vnc blender-websockify blender-gui
systemctl status blender-gui          # kontrola
```

Když jednotky neexistují (čerstvý server), založ je znovu:

```bash
systemd-run --unit=blender-xvfb       /usr/bin/Xvfb :50 -screen 0 1600x900x24 -nolisten tcp
systemd-run --unit=blender-x11vnc     /usr/bin/x11vnc -display :50 -rfbport 5950 -localhost -forever -shared -nopw -noxdamage -quiet
systemd-run --unit=blender-websockify /usr/bin/websockify --web=/usr/share/novnc 127.0.0.1:6950 127.0.0.1:5950
systemd-run --unit=blender-gui -p Environment=DISPLAY=:50 -p Environment=LIBGL_ALWAYS_SOFTWARE=1 \
    /opt/blender-5.2/blender --python <cesta>/gui_setup.py
```

### Pasti

* **`-noxdamage` u x11vnc je povinné** — bez něj dává Xvfb černou
  obrazovku (známá nekompatibilita).
* **`LIBGL_ALWAYS_SOFTWARE=1`** — server nemá GPU, jede Mesa softwarově.
* **htpasswd musí být `$apr1$`** (`openssl passwd -apr1`), ne `$1$`
  z Pythoního `crypt` — nginx ten druhý neověří ("password mismatch").
* **RAM.** 2026-09-09 celý stack spadl na nedostatek paměti, když vedle
  něj běžely CPU rendery. Server má 23 GB, ale sdílí ho víc projektů a
  botů (viz `SERVER_RAM_WATCHDOG.md`). GUI Blender s lehkou scénou bere
  ~800 MB, se 70MB `.blend` a zabalenými texturami několik GB.
  **Proto se produktové rendery mají dělat na vzdálené GPU, ne tady** —
  VPS Blender je nástroj na *nastavení* scény, ne na rendering.

### Sdílený disk v souborovém dialogu

`/root/Sdileny_disk` → symlink na
`private-files/shared-drive-named/` — zrcadlo Sdíleného disku se
skutečnými názvy složek a souborů (na disku jsou uložené pod hashem).
Blender má „Home" mezi záložkami, takže se tam Robert proklikne bez
psaní cesty. **Zrcadlo je jednorázový snímek** (144 složek, 954
symlinků, vytvořeno 2026-09-09) — nové soubory se v něm neobjeví samy.

---

## Rozsah práce

⚠️ **OPRAVENO (audit bot9, 2026-09-12): čísla níže byla zastaralá o
řád (264/123/5), navíc se tahle čísla mění denně - psát sem fixní
hodnotu je zaručený způsob, jak ji zase nechat zestárnout.** Místo
zapamatovaného čísla ověř živě:
  ```sql
  SELECT COUNT(*) FROM product_assemblies;                                    -- celkem
  SELECT COUNT(*) FROM product_assemblies WHERE shop_product_id IS NOT NULL;  -- s produktem
  SELECT COUNT(DISTINCT assembly_id) FROM product_turntable_frames WHERE is_active=1;  -- s aktivní dávkou
  ```
  (k 2026-09-12 vyšlo 294 / 7 / 0 - jen pro ilustraci, NE k citování jako
  aktuální stav v budoucnu)

---

## Stav k 2026-09-09

Hotovo: rozpad úlohy, Blender renderer, kamerový rig, materiály, ověřený
zkušební render sestavy 134 (geometrie, kompozice, těsný ořez i materiály
sedí), ověřeno i vykreslení ochranného loga.

Hotov i **worker protokol** — úloha dojede až na vzdálené GPU. Ověřeno
protokolovým testem proti živému API (bez GPU): poll vrátí správný tvar,
**9 unikátních GLB pro 128 dílů**, job JSON nese klíče místo serverových
cest, `.glb` se stáhne, pokus o cizí cestu vrací 404.

Zbývá:
1. ~~automatický upload do `/turntable/frames` + `/commit`~~ **VYŘEŠENO** (OPRAVENO audit bot9 2026-09-12, viz Fáze 6 výše - `api/turntable_ingest.py`)
2. Robertova šablona `.blend` z VPS Blenderu (`TT_FLOOR`, `TT_*` materiály)
3. ~~automatické umístění ochranného loga~~ **VYŘEŠENO** (`scripts/razitkovac.py`, viz sekce výše) + čitelnost reliéfu (zůstává otevřené)
4. dávkové projetí 118 sestav na vzdálené GPU

### ⚠️ Verze Blenderu musí sedět na VŠECH třech místech (2026-09-09)

Robert ukládá v **5.2.1**. Starší Blender novější `.blend` odmítne hláškou
**„not a blend file"** — což vypadá jako poškozený soubor a svede na
scestí. Dnes to stálo hodinu a Roberta zbytečné znovunahrávání souboru.

Sedět musí:
1. **server** — `/opt/blender-5.2` (starý 4.2.9 z `/opt/blender-official` smazán 2026-09-29 na Robertův pokyn)
2. **agent na GPU stanici** — `SPUSTIT_AGENTA.bat` si dřív sám stahoval
   **4.2.23**; opraveno na 5.2.1 + varování při startu, když najde 4.2
3. **soubor od Roberta** — ten určuje minimum

Poznat verzi jde z hlavičky souboru bez otevírání:
`head -c 16 soubor.blend | xxd` → `BLENDER17-01v0502` = 5.0.2,
`28 b5 2f fd` = Zstd (4.x komprimovaný).

### ⚠️ HDRI se do .blend neukládají (2026-09-09)

Blender si pamatuje jen **cestu** k obrázku. Robertovy soubory odkazují
na `C:\Users\...\Downloads\` nebo `//rendering/...`, což na serveru ani
na GPU stanici neexistuje → tmavý/fialový render. Řeší
`priprav_sablonu.py`: dohledá podle názvu na Sdíleném disku, přepojí a
**zabalí dovnitř kopie** (originál se nikdy nemění).

Pozor: `world_check` vypíše všechny `TEX_ENVIRONMENT` uzly, ale platí
jen ten **zapojený do Background** — Robert jich měl ve World tři a
render bral `canary_wharf_8k.hdr`.

### ⚠️ Render na GPU nikam nedoputoval — chybějící převzetí (2026-09-11)

Řetěz otočného náhledu měl **díru přesně uprostřed** a nebylo to vidět,
protože úloha přitom hlásila „hotovo":

```
scéna (scene.html)  -> /turntable/frames -> /turntable/commit -> e-shop
GPU (render_worker) -> <job>.frames/     -> ??? ----------------> nic
```

`render_worker_tt_result` rozbalil ZIP od agenta do `<job>.frames/`,
napsal `state="done"` a tím to skončilo. Endpointy `/turntable/frames`
a `/turntable/commit` volá **výhradně prohlížeč** (`scene.html`) — GPU
větev do nich nikdy nevstoupila. Stav k 2026-09-11: **40 hotových sad
snímků na disku, 0 řádků v `product_turntable_frames`.**

Doplnil bot8: **`api/turntable_ingest.py`**. Volá ho `render_worker`
hned po rozbalení ZIPu a používá **tytéž funkce jako upload z
prohlížeče** (`zkontroluj_snimek` / `ulozit_snimky` / `commit_batch`,
vyčleněné z `api/turntable.py`) — žádná druhá implementace týchž
pravidel.

**Přední azimut se NEDOSAZUJE.** Manifest musí nést
`camera.front_azimuth_deg`; chybí-li, ingest skončí chybou a snímky
nechá ležet. Důvod je konkrétní: manifesty úloh na disku mají `front=90`,
takže tiše dosazených globálních `270` by posunulo celou 270° výseč a
commit by hlásil **54 ze 162 snímků chybějících** (číslo platí pro tehdejší
parametry před opravou `STEP_DEG` 2026-09-11, viz "Kontrakt otočného
náhledu" výše - dnes by šlo o jiný poměr, princip chyby je ale stejný),
přestože dávka je kompletní. Od 2026-09-11 platí totéž pro upload z prohlížeče — chybějící
`front_azimuth_deg` je `400`, ne fallback. Jedna dávka = jeden přední
azimut (druhý chunk s jinou hodnotou dostane `409`).

Na co si dát pozor příště:
* **„hotovo" musí znamenat „je to na e-shopu"**, ne „leží to ve složce".
  Úloha teď nese `ingest_ok` + `ingest_batch`; když převzetí selže, je
  `state="error"` s důvodem a **snímky se nemažou** (jsou to hodiny GPU).
* `blender_render_status` u hotové úlohy četl `<job>.png`, který otočná
  úloha **nikdy nemá** → vracel `404 „Výsledek renderu už na serveru
  není"` a ještě úlohu uklidil. Otočné úlohy teď vrací stav rovnou.
* `_cleanup_job` umí jen `os.remove`, takže **adresář `.frames/`
  neuklidil nikdy** — odtud 40 sirotků. Maže se až po ÚSPĚŠNÉM commitu,
  kdy je to prokazatelně duplikát úložiště.
* Hlavička `turntable.py` popisovala „5 prstenců × 36 = 360 souborů"
  dávno po zúžení na 162 a **svedla odhad času renderu na dvojnásobek**.
  Zdroj pravdy jsou konstanty `ELEVATIONS × AZIMUTHS × TIERS`.

### ⚠️ Kontrakt otočky žije na TŘECH místech, ne na jednom (2026-09-11)

Táž pravidla dávky jsou naprogramovaná třikrát a musí se měnit **naráz**:

| kde | co drží |
|---|---|
| `api/turntable.py` | `STILL_VIEWS`, `ELEVATIONS`, `AZIMUTHS`, `TIERS` — server, zdroj pravdy |
| `webapp/scene.html` | `ttStillsForFront`, `ttAzimuthsForFront` — render v prohlížeči |
| `scripts/2026-09-09_turntable_job.py` | `stills_for_front`, `azimuths_for_front` — render na GPU |

Jak to prasklo: Robert zrušil pohled `back`, ten se odstranil ze
`STILL_VIEWS`, ale **dvojčata zůstala**. Job skript pak odmítal postavit
jakoukoli úlohu (kontrola konzistence — správně), zatímco `scene.html`
poslal `back` na server a dostal **HTTP 400 „Neznámý still"**. Protože
prstencové snímky jdou zvlášť a projdou, vypadalo to jako „něco se na
konci nepovedlo", ne jako tvrdá chyba — a nikdo to nenahlásil.

Poučení: **kontrola konzistence musí hlídat správný invariant.** Když
pravidlo 29 říká „žádné stills", je správná kontrola „seznam je prázdný",
ne „seznam se rovná `STILL_VIEWS`" — druhá varianta projde i pro pět
snímků, které nikdo nečte. A pozor na past při opravě: samotné
vyprázdnění seznamu pošle upload bez jediného souboru a server odpoví
400 „Žádné soubory" — prázdný seznam se musí přeskočit.
