# Razítka loga na všech 3D modelech generátorů stolu (bot8, 2026-10-08)

**Zadání:** WORKFLOW pravidlo 61 – Robert 2026-10-08: *„razítka budou na všech 3D modelech ve všech generátorech“* (přebíjí „generátor a košík bez razítek“ z 2026-09-06). Úkol od bot9: výchozí razítka v živém 3D
generátoru stolů i v košíku pro všech 5 systémů (30 / 35 / 40 / 41 SSE / 45), cache nesmí servírovat staré modely bez razítek, hlídat váhu a rychlost, výběr / kóty / ovládání ve 3D nesmí být rozbité, regrese bit po bitu.

## Co se změnilo (jen `api/stul_glb.py` + hlavička `api/stul_razitka.py` + dokumentace)
* `stul_glb.model_pro_parametry(parametry, razitka=None)`: `None` = výchozí nastavení generátoru `RAZITKA_VYCHOZI = True`; `razitka=True/False` se předává výslovně (`False` = holý model: testy geometrie, srovnání).
  Pravidla umístění razítek (`api/stul_razitka.py`, `scripts/razitkovac.py`) se **nemění**; razítka nejsou součástí hashe konfigurace (jsou z něj odvozená), `RULES_VERSION` se **nemění** (cena, kusovník, platnost, odpovědi API beze změny).
* Model s razítky plní i **společné vedlejší cache** (posun, rozsahy dílů, extra rozsahy): `vodici` (úchyty ve 3D, payload luxů, živé tažení) a dřív se dělaly nad holým modelem; razítka žádný díl neposouvají
  (výplně drážek jsou připojené na konec materiálu hliník, loga jsou instance uzlů na konci seznamu uzlů) → regrese dokazuje shodu.
* Komprimovaná cache GLB (`zakoduj_pro_klienta`) se klíčuje i délkou dat: model s razítky a bez nich mají STEJNÝ hash, ale jiná data (jinak by po nasazení mohl dostat prohlížeč nekomprimovaný starý model z cache).
* Už hotovo jinými boty (neměněno): `konfigurator_registr.glb_bytes(razitka=None)` a `stul_shop.glb_bytes(razitka=None)` předávají výchozí hodnotu generátoru (2bf8b4c5), dopravník je vždy s razítky, karta
  `STUL-S…` ukládá model s razítky (74a8e2f0, bot10), nabídka (`nabidka_z_konfigurace`) razítka měla od 2026-10-06.

## Důkazy
| co | výsledek |
|---|---|
| `regrese.py` (873 konfigurací, systémy 30 / 35 / 40 / 41 / 45): holý model = dřívější bajty, výchozí = dřívější model s razítky, vedlejší cache = dřívější, počet razítek, hash | 0 chyb |
| `regrese_resolve.py` (90 odpovědí veřejného resolve: cena, kusovník, options, vodicí značky, odkaz na model) | 0 rozdílů |
| `test_razitka_vychozi.py` (hermeticky: GLB struktura, spec, vedlejší cache, `vodici`, cache, komprimovaná cache, váha, meze loga) | 298 kontrol OK (na kódu bez změny padá) |
| `test_razitka_shop.py` (veřejná routa `/glb/<token>` z resolve i `/model/<hash>`, br / gzip / identity, kolize komprimované cache, staff `model.glb`; 5 systémů) | 220 kontrol OK (bez změny 92 chyb) |
| mutace `mutace.py` (12: výchozí False, ignorovaný `razitka=False`, model bez razítek, chybějící posun / rozsahy / extra, neuložený model, cache bez kontroly vedlejších cache, neomezená cache, klíč komprimované cache jen hash, dvojí skládání) | 12/12 zachyceno |
| váha | +515–529 KB surově (sdílený mesh loga, nezávisle na počtu razítek 2–19), po brotli +115–120 KB, skládání +30–60 ms |

## Spuštění
```
api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/test_razitka_vychozi.py                       # hermeticky
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
  api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/test_razitka_shop.py                       # DB se jen čte
api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/regrese.py porovnej                          # proti zaklad_pred_zmenou.json (GLB před změnou, 873 konfigurací)
scripts/2026-10-08_razitka_generatory/prepare_cand.sh [adresář]    # kandidátní strom (patches/*.py na živé soubory) pro testy bez zámku; STUL_API_OVERRIDE=<adresář>/api
api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/mutace.py [kandidát]   # mutace zaplaty
api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/render_obrazky.py [výstup]   # obrázky před / po (Chromium + three.js)
```
`zaklad_pred_zmenou.json` a `zaklad_resolve_pred_zmenou.json` jsou otisky ZE STAVU PŘED zavedením razítek (jednorázová regrese „nic jiného se nezměnilo“); po další úmyslné změně geometrie stolu (např. nový díl) nebudou
platit a nahradí se novým otiskem (`regrese.py zaklad`) – jako u zlatých otisků dřívějších sad.

## Poznámky pro další boty
* **Razítka na živém modelu mění místo s každou změnou rozměru** – umístění se odvozuje z hashe konfigurace (pravidlo 61 říká „pravidla umístění se nemění“); při tažení posuvníku se logo na novém modelu objeví jinde.
  Kdyby to Roberta rušilo, jde o rozhodnutí o pravidlu (např. nezávislé na rozměru), ne o chybu.
* Oplocení / kryty strojů (`scripts/2026-10-08_oploceni/`, POZASTAVENO) se budou razítkovat od prvního náhledu až po Robertově odblokování (zobecnit `stul_razitka` na recept → modul).
* Nový generátor se razítkuje hned od prvního náhledu (pravidlo 61): volat model s `razitka=None` a nepřidávat vlastní „bez razítek“ výchozí.
