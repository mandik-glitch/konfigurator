> POZNAMKA: cesty `<P>/...` v tomto textu = pracovni slozka bot10 mimo repo (scratchpad). Integracni patch je od 2026-10-02 aplikovany a commitnuty, Vandr patch nasazen; zbytek je postup overeni, rollback a klic znaceni.

# Integrace 3D modelu online nabídky z karty Vandr: repo-ready balíček (bot10, 2026-10-02)

Připraveno k nasazení pro bot10 (zámek, commit). **Nic nebylo nasazeno ani commitnuto**, do `/opt/konfigurator` ani `/opt/vandrawee` jsem nezapsal,
do DB jsem nezapsal (jen read-only `SHOW COLUMNS`/`SELECT` pro ověření schématu a SKU), nic se neodeslalo ven, žádný Cycles/GPU render, `api/.env` jsem nečetl ani nevypsal.

## Obsah

| co | kde |
|---|---|
| strom nových/změněných souborů v cílových cestách | `repo/` |
| patch proti HEAD `/opt/konfigurator` (`git apply` z kořene; nové soubory jako `new file`, binární fixtury `--binary`) | `integrace.patch` |
| patch Vandr strany (`vandr:offer-data --v3d`) | `vandrawee_patch/VandrOfferData.php` (celý soubor) a `VandrOfferData.diff` (pro `git -C /opt/vandrawee apply`) |
| kontrakt pro bot16 a bot5 (3D doplněk k `KONTRAKT_VANDR_NABIDKA_ENDPOINT.md`) | `repo/docs/KONTRAKT_NABIDKA_3D.md` |
| vložitelný kus kódu pro `nabidka-online.html` (**neaplikováno**) | `nabidka-online.snippet.html` (kopie je i v `repo/docs/`, používá ji harness) |
| volitelná migrace (**nepoužitá**) | `optional/2026-10-02_scene_offers_v3d.sql` |
| ukázkové výstupy náhradních obrázků (pro oko: kótovaný výkres + 3D pohledy karet #4053, #4482 a v3d karty #4910) | `shots/` |

### Co patch mění (43 souborů, ~21 900 řádků, z toho většina jsou kandidáti 3D + testy + fixtury)
- **Nové:** `api/vandr_vykres_nahrada.py` (**náhradní obrázky nabídky**, viz níže), `api/v3d_glb.py` (sanitizer + final_check), `api/v3d_mark.py` (neviditelné značení), `scripts/v3d/{build_ctx,offer_model,vandr_motions,vandr_offer_build,v3d_mark_detect}.py`,
  `scripts/v3d/pohyby-vychozi.json`, `scripts/2026-10-02_v3d_testy/` (testy + `run_all.sh`), `docs/KONTRAKT_NABIDKA_3D.md`, `docs/nabidka-online.snippet.html`.
  `vandr_motions.py` a `vandr_offer_build.py` jsou **dnešní build s dorazy dvířek** (`dorazy_dvirek/`), ostatní z `v3d/`.
- **`api/vandr_scene_offers.py`** (přepsané tělo endpointu, dosavadní texty chyb a statusy beze změny): pořadí „nejdřív model, pak nabídka“, `v3d:false` + důvod při jakémkoli
  selhání 3D (dosavadní statický model jako dnes), `--v3d` s návratem na staré volání, rozpočet 55 s, cache + zámek (přes `offer_model`), brána `sanitize`+`final_check`
  před uložením (i pro cache), volitelné značení, záznam do `audit_log`, `can_create_offer(karta_row) -> (bool, duvod)` (na žádost bot10), vypínač souborem.
- **Chybějící Vandr obrázky už nejsou 400** (Robert 2026-10-02, karty #4053, #4482: Vandr generuje obrázky jen z Unity klienta, u poloviny karet jsou prázdné). `vandr_vykres_nahrada.py` + `vandr_scene_offers._dopln_obrazky`:
  kde Vandr obrázek existuje, ponechá se (přednost Vandr, kombinace povolena); jinak **`narys`** = kótovaný 2D výkres vyrobený serverem z čistého GLB (numpy + PIL, nárys + bokorys, kóty šířky/výšky/hloubky v mm, ~1 s, bez Blenderu/GPU)
  a **`view3d_a/b`** = naše snímky otočky karty (`product_turntable_frames`: přední azimut ±35°, elevace nejbližší 17,5°, největší tier ≥1024 do 1,5 MB, soubor musí existovat) → jinak první dvě fotky galerie → jinak stínovaný pohled z modelu.
  Odpověď přidává `obrazky_zdroj`, `poznamka` (text pro admina) a `obrazky_rozmery_mm`. 400 zůstává jen pro: bez GLB, bez ceny, SKU není `VD-`, GLB chybí na disku (404 karta neexistuje). Stránka nabídky se nemění (stejné klíče `views`).
  Nález při tom: dosavadní **statický** GLB (Blender geometrie bez v3d) ještě obsahuje logo a podlahu, takže jeho `rozmer_mm` je nafouknutý (karta #4053: `rozmer_mm` 861×1623×1192, skutečný produkt 371×780×1183); výkres je proto kreslí bez nich a skutečné rozměry vrací v `obrazky_rozmery_mm`.
- **`api/scene_offers.py`** (minimální zásah, 2 místa): `public_offer_model` posílá `Cache-Control: private, no-cache` + `ETag` (304); `CLICK_TARGETS` + `v3d_view/v3d_dims/v3d_mode/v3d_anim`.
  `save_offer_model_bytes`, nativní upload modelu a zbytek souboru jsou **beze změny**. Do DB se nic nepřidává (migrace není potřeba).
- **Neměním:** `api/app.py`, `webapp/*` (stránka nabídky = bot5, `viewer3d.js` už v repu je), DB schéma, `api/.env`.

## Pořadí nasazení

1. **Vandr strana nejdřív** (zpětně kompatibilní: bez `--v3d` je výstup příkazu stejný - stejné klíče i pořadí, podle čtení kódu):
   `cd /opt/vandrawee && git apply --check <P>/vandrawee_patch/VandrOfferData.diff && git apply <P>/vandrawee_patch/VandrOfferData.diff` (pod zámkem Vandr repa), pak commit.
   Ověřeno jen: `php -l` OK, `git apply --check` proti živému souboru OK, sloupce všech 8 dotazovaných tabulek existují (`SHOW COLUMNS`). **Za běhu neověřeno** (nesmím spouštět proti živé Vandr DB zapisovatelně
   ani nasazovat); kdyby příkaz s `--v3d` selhal, konfigurátor to zvládne (`v3d:false`, důvod „Vandr příkaz s --v3d selhal: …“), nabídky se tvoří dál.
   Ověření po nasazení viz níže (bod „Ověření na živu bez zápisu“).
2. **Konfigurátor pod zámkem** (`api/*.py` jsou guardované; `scripts/`, `docs/` ne):
   ```
   cd /opt/konfigurator
   scripts/lock.sh acquire bot10 "3D model online nabidky z karty Vandr (integrace.patch)" --wait
   git apply --check <P>/integrace.patch && git apply <P>/integrace.patch      # HEAD se mezitim mohl posunout; patch se meni jen 2 api soubory, --check to ukaze
   install -d -o www-data -g www-data -m 750 private-files/v3d-cache            # cache 3D; sluzba bezi jako www-data
   scripts/2026-10-02_v3d_testy/run_all.sh --rychle                             # povinne pred commitem (import/staticka/endpoint, ~3 min; bez --rychle +build 7 karet, harness stranky)
   git add api/v3d_glb.py api/v3d_mark.py api/vandr_scene_offers.py api/scene_offers.py scripts/v3d scripts/2026-10-02_v3d_testy docs/KONTRAKT_NABIDKA_3D.md docs/nabidka-online.snippet.html
   git commit -m "feat(nabidky): 3D model online nabidky z karty Vandr (...)" -- <stejne cesty>     # explicitni pathspec (pravidla v pameti)
   scripts/lock.sh release bot10
   ```
   Nasazení `api/*.py` udělá plánovaná služba 12:30/3:30 (HUP, bez restartu, jen z commitnutého stavu) - **neresetovat ručně**. Chyba importu = pád služby, proto je povinný `test_import.py` (v `run_all.sh`).
   Žádná migrace, žádný zápis do DB mimo to, co endpoint dělal dosud + jeden řádek `audit_log` na nabídku.
3. **Stránka `nabidka-online.html`** (bot5, guardovaný soubor): vložit 4 bloky ze `nabidka-online.snippet.html` podle kotev v jeho hlavičce. Dokud se nevloží, nabídky s `v3d:true` se na stránce
   zobrazí **dosavadním** prohlížečem (model je platný GLB, jen bez pohybů) - nic se nerozbije.
4. **Klíč značení** (volitelné, až Robert řekne): viz „Jednorázový příkaz pro klíč“.
5. **Předehřátí cache** (volitelné): první nabídka z každé karty po nasazení je „studená“ (build 7-16 s v klidu; při zatížení serveru déle). Cache se předehřeje CLI (jako uživatel služby, aby soubory a zámky patřily jí):
   `runuser -u www-data -- /opt/konfigurator/api/venv/bin/python /opt/konfigurator/scripts/v3d/offer_model.py <shop_product_id>` (jen čtení DB; potřebuje Vandr patch z bodu 1; `runuser` jsem neověřil).
   Spuštěné jako root vznikne cache vlastněná rootem: pak `chown -R www-data:www-data /opt/konfigurator/private-files/v3d-cache`.

## Ověření na živu bez zápisu (read-only)

- Vandr příkaz (SELECT-only): `cd /opt/vandrawee/web && runuser -u www-data -- php artisan vandr:offer-data <uuid karty bez "VD-"> --v3d | python3 -c 'import json,sys; d=json.load(sys.stdin); v=d["v3d"]; print(sorted(d), v["v"], len(v["komponenty"]), len(v["strany"]))'`.
  Bez `--v3d` musí být výstup stejný jako před patchem (`car_name`, `parts`).
- Konfigurátor CLI (jen SELECT přes READ ONLY spojení, cache mimo produkci): `api/venv/bin/python scripts/v3d/build_ctx.py 4910 --strict -o /tmp/ctx.json` a
  `api/venv/bin/python scripts/v3d/offer_model.py 4910 --cache /tmp/v3d-cache-test -o /tmp/offer.glb --geom /tmp/geom.json`. (Pozn.: `ctx_sha8` se oproti snímku může lišit, snímky mají starší `pohyby-vychozi.json`.)
- **První skutečná nabídka z karty** (ne testovací: produkce testovací data nesmí mít): v odpovědi `v3d:true`, `v3d_znacka`; `SELECT id, entity_id, detail FROM audit_log WHERE action='v3d_model' ORDER BY id DESC LIMIT 5;`;
  `curl -sI https://<web>/api/public/offers/<token>/model` → `Cache-Control: private, no-cache`, `ETag`, `Content-Type: model/gltf-binary`.
- Poznámka k uživateli služby: testy i build jsem pouštěl jako **root**; v produkci běží služba jako `www-data` (Blender/PHP/cache). Dosavadní cesta spouští Blender stejně (`env={PATH}`), proto očekávám stejné chování, ale
  **jako www-data neověřeno**. První nabídka to ukáže (`v3d_duvod` by obsahoval chybu práv).

## Jednorázový příkaz pro klíč značení (Robert)

Značení je **vypnuté**, dokud služba nemá v prostředí `V3D_MARK_SECRET` (min. 16 znaků; doporučeno 64 hex). Bez klíče se nic neznačí a nic se nehlásí jako forenzní stopa (`v3d_znacka:"vypnuto"`).
Klíč musí zůstat tajný a **nikdy se nesmí ztratit ani změnit** (model na Sdíleném disku se po smazání nabídky nemaže; po změně klíče by se staré značky přestaly číst). Do repa, logu, AGENTS_LOG ani chatu ho nepsat.
```
cd /opt/konfigurator/api
grep -q '^V3D_MARK_SECRET=' .env && echo "klic uz je nastaven - NEPREPISOVAT" || { [ -n "$(tail -c1 .env)" ] && echo >> .env; echo "V3D_MARK_SECRET=$(openssl rand -hex 32)" >> .env; echo "klic ulozen"; }
```
(Výstup příkazu hodnotu klíče nevypíše. Zálohu klíče si Robert uloží do správce hesel.) **`api/.env` se čte jen při STARTU služby (`EnvironmentFile=`), `HUP` z plánovaného nasazení ho nenačte** - značení se zapne až po plném restartu služby
(rozhodnutí o restartu je na Robertovi; do té doby `v3d_znacka:"vypnuto"`, což je bezpečný stav). Čtení značky z uniklého souboru: `api/venv/bin/python scripts/v3d/v3d_mark_detect.py SOUBOR.glb` (klíč si vezme z prostředí nebo z `api/.env`, hodnotu nevypisuje).
Značka se vkládá až po založení nabídky (nese číslo nabídky) do kopie modelu té nabídky; sdílený model karty v cache zůstává bez značky.

## Rollback

- **Okamžitě, bez nasazení a bez restartu:** `touch /opt/konfigurator/private-files/v3d-vypnuto` → nové nabídky vznikají dosavadní cestou (`v3d:false`, důvod v odpovědi). `rm` souboru to vrátí. Už vzniklé nabídky se nemění.
- Trvale: `git revert` commitu (4 `api` soubory se vrátí na HEAD před integrací), další plánované nasazení ho vezme. Vandr patch se vracet nemusí (bez `--v3d` je výstup stejný).
- Úklid cache: `rm -rf /opt/konfigurator/private-files/v3d-cache` (nic jiného ji nepoužívá; poškozená/podvržená položka se smaže sama a další požadavek ji postaví znovu).
- Nabídky vzniklé s 3D zůstávají platné i po rollbacku (model je běžný GLB uložený jako dosud); pohyby se bez nového prohlížeče na stránce jen nezobrazí.

## Známá omezení a neověřené věci (poctivě)

- **Studený build** 7-16 s v klidu (karty 4910 7 s, 4453 9,5 s, 4917 16 s, měřeno při zátěži serveru load ~9-12), strop požadavku 55 s; build dostane 27 s minus čas Vandr příkazu (rezerva 20 s na dosavadní statický model a 8 s na značení/zápis).
  Při velké zátěži serveru se build může nevejít → `v3d:false` (důvod „…překročilo N s“), další pokus to zopakuje; předehřátí cache to řeší.
- **Soubory do `private-files/v3d-cache/`:** ~0,7-1,9 MB na kartu a verzi kódu/dat; stará verze se sama nemaže (README: `find … -mtime +30 -delete`). Disk `/opt` byl dle logu zaplněný z ~97 %.
- Značení: omezení schématu jsou v docstringu `api/v3d_mark.py` (bez originálu se čte jen v soustavě souboru; svar/remesh/šum ≥ 0,04 mm ho zničí; kdo má dvě kopie téže karty, vidí rozdíly). Značení trvá 3-4 s na nabídku.
- `ETag`/`Cache-Control` na modelu platí pro **všechny** modely nabídek (i nativní 103), tělo se nemění.
- Nativní větev (upload modelu ze scény, `save_offer_model_bytes`) je **beze změny, bez sanitizeru** (to je práce bot8 + schválení); sanitizer chrání jen Vandr větev (zákaznický GLB se ukládá až po `sanitize`+`final_check`).
- `rozmer_mm` v odpovědi je u `v3d:true` rozměr regálu bez obalu/loga (z buildu), u `v3d:false` dosavadní hodnota - nesrovnávat.
- Výchozí parametry pohybů (`scripts/v3d/pohyby-vychozi.json`) jsou částečně `overeno:false` (pin, boxy, podlahová dvířka); varování buildu to hlásí jen adminovi (`v3d_varovani`), do GLB nejdou.
- `v3d_mark.get_secret` má v knihovně zálohu z `FLASK_SECRET_KEY`; **integrace ji nepoužívá** (testováno). CLI `v3d_mark_detect.py` ji při čtení ještě umí, nevadí (bez klíče nic nenajde).
- **Zakázané slovo (pravidlo 56):** neznám ho (pravidlo ho nevypisuje), proto jsem grep `-i` na něj nemohl pustit. `scripts/2026-10-02_v3d_testy/kontrola_staticka.py` ho hledá ze seznamu v `V3D_ZAKAZANA_SLOVA=slovo1,slovo2`
  (hlásí jen názvy souborů, slovo nevypisuje); doporučuji pustit i nad `integrace.patch`, `README.md` a `repo/`. Texty jsem psal bez dodavatele knihovny karoserií.
- Náhradní obrázky: snímky otočky mají elevace jen −40/0/40 (vybírá se 0, nejblíž 17,5°); při `kombinace` je Vandr obrázek PNG a náš JPEG (stránka i uložení oboje zvládají). Fotky z galerie se berou jak jsou (webp apod. převede PIL na JPEG).
  Snímky otočky jsou naše rendery (LOGIMAN.CZ), nikoli Vandr, takže v nich není logo dodavatele; **kótovaný výkres je schematický** (světlé plochy, hrany dílů), ne detailní výkres z Unity. Dosavadní statický model (v3d:false) obsahuje logo vanDrawee na podlaze (stávající stav, beze změny) - ve výkresu ani v rozměrech není.
  Reálné `product_turntable_frames` a soubory jsem četl jen ze souborů/DB read-only; test na kartách #4053/#4482 používá skutečné GLB z `webapp/katalog/vandr` a skutečné snímky z `webapp/content-files/turntable-frames`.
- Hermetický import nemůže nahradit načtení skutečného `api/app.py` (ten se nespouští): ověřeno, že všechny nové importy jsou líné nebo čisté, že `from app import log_audit` existuje (`app.py:501`) a že skutečné `scene_offers.py` + `vandr_scene_offers.py` se pod atrapami načtou a zaregistrují trasy.
- Stránka (`harness_page.js`) je ověřená Chromiem (SwiftShader) proti kopii **živé** `nabidka-online.html` + snippet; skutečná fyzická zařízení/mobilní prohlížeče ne.

## Testy (`scripts/2026-10-02_v3d_testy/run_all.sh [--rychle] [--full]`)

Výsledky posledního běhu jsou v dodávce jako `VYSLEDKY_TESTU.txt` (níže shrnutí v mé zprávě). Co pokrývají: `test_sanitize` + `_mutace` (sanitizer, whitelist, utoky), `test_motions_sub` (druhy boxů), `test_vykres` (náhradní výkres: rozměry vs. geom.json a nezávislý výpočet AABB, 4 kóty, bez názvů dílů, deterministický; výběr snímků otočky),
`test_mark` (značení, odolnost; `--full` +node/Blender), `test_import` (hermetický import všech modulů), `test_endpoint` (Flask test client + FakeDB + skutečný Blender build: úspěch, selhání, `--v3d`, cache, značení, souběh,
otrávená cache, rozpočet, vypínač), `_mutace_endpoint` (rozbití pravidel musí shodit testy), `kontrola_staticka` (kompilace, tajemství, SQL zápisy, cesty, zakázaná slova), `harness_page.js` (stránka v prohlížeči).
Všechno jede nad atrapou DB (`_fakes.py`: zápis do neznámé tabulky = chyba testu), výstupy mimo repo (`V3D_TEST_OUT`, vychozi `<tmp>/v3d_testy`), klíč značení jen v `os.environ` procesu testu.
