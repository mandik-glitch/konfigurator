# Generátory stolu: záslepky na volné konce profilů + razítka loga v modelu nabídky (bot8, 2026-10-06)

## 1) Záslepky na volné konce profilů (Robert 2026-10-06: „v generátorech … na volné konce profilů se musí automaticky dávat záslepky“)

Generátor (`api/stul_konfigurator.py`, `_volne_konce` + krok 3b v `_sestav_jadro_systemu`) dá záslepku systému (3071 / 3090 / 3091) na **každý konec profilu, kterého se nedotýká žádný jiný díl**
(profil, deska, spojka, kolečko / záslepka pod nohou…): v pásu 1,5 mm pod koncovou plochou až 2,5 mm za ní, v průřezu zmenšeném o 1 mm, není AABB jiného dílu. Dnes jsou to jen **profily rampy pro LED**
(konce ramen nad zadními stojkami a oba konce příčky nad LED; u stolu bez LED horní konce zadních noh) – kód je ale obecný, takže další volné konce (nový komponent) dostanou záslepku sami.

- Poloha jako u záslepek pod nohami: koncová plocha profilu = vnitřní plocha příruby (`konec + vnější směr · zaslepka_vyska`), zátka (lokální +Z) do profilu (`_q_zaslepky`).
- Klíč dílu `("zasl", klíč profilu, "+" | "-")`, díly jsou **až na konci seznamu** (indexy ostatních dílů se nemění), role `("zaslepka", "záslepka volného konce profilu")`, montážní krok 8.
- Vnější rozměry stolu (`rozmery`) jsou BEZ záslepek (3 mm příruby nemění výšku ani hloubku); kontrola „spojka × komponenta“ je záslepky nepočítá; živé tažení: záslepky jedou s profilem, který se hýbe celý
  (`zasl_hostu` v `_zive_operace`), u tahů ze sondy samy.
- SSE stůl (system 41) má vlastní jádro (`stul_sse`, záslepky podélníků tam jsou).
- Mění se cena a kusovník (přibývají kusy záslepek) → `RULES_VERSION = 2026-10-06.1` (nový hash a kód STL-xxxxxx; kotvy hashů v testech přepsány).
- Test: `scripts/2026-10-06_zaslepky_konce/test_zaslepky_konce.py` (nezávislé vzorkování dotyku na 46 konfiguracích, poloha / otočení, žádné vedlejší účinky, GLB), mutace `mutace.py` (16).

## 2) Razítka loga na VŠECH 3D modelech generátoru (Robert přes bot5 / bot9, 2026-10-06 pro nabídku; od 2026-10-08 VÝCHOZÍ všude – WORKFLOW pravidlo 61: „razítka budou na všech 3D modelech ve všech generátorech“)

`stul_glb.model_pro_parametry(parametry, razitka=None)` → `api/stul_razitka.py`; `None` = výchozí nastavení generátoru `RAZITKA_VYCHOZI = True` (živý model `/api/shop/configurator/glb/<token>` a tím i košík a odkaz na konfiguraci,
nabídka, karta `STUL-S…`, staff `/api/stul/model.glb`; stejně `stul_shop.glb_bytes(…, razitka=None)` a `konfigurator_registr.glb_bytes`), `razitka=False` = holý model (testy geometrie, srovnání). Model s razítky a bez nich mají každý svou cache
a komprimovaná cache (`zakoduj_pro_klienta`) se klíčuje i délkou dat; vedlejší cache (posun, rozsahy dílů, extra rozsahy) jsou společné – razítka žádný díl neposouvají, takže uchyty ve 3D, payload luxů a živé tažení
fungují nad modelem s razítky stejně. Hash konfigurace, `RULES_VERSION`, cena, kusovník a odpovědi API se nemění (razítka jsou jen v GLB). Váha: +~0,52 MB surově (jeden sdílený mesh loga, nezávisle na počtu razítek),
po brotli +~115 KB, skládání +30–60 ms. Test a regrese bit po bitu: `scripts/2026-10-08_razitka_generatory/` (873 konfigurací, systémy 30 / 35 / 40 / 41 / 45).

Pravidla jsou Robertova pro sestavy (`scripts/razitkovac.py`, 2026-09-10 / 11 / 17), uplatněná na díly stolu: kterákoli ze 4 stěn profilu, na které je souvislý volný úsek na celé logo (40 mm od konce) a před ní
(do 4 m) nic neleží (= exponovaná ven); **každý třetí** profil z kandidátů každé stěny (posun z hash konfigurace), logo na náhodném místě úseku (deterministicky z hash), nejméně 500 mm volné mezery mezi logy na
profilu, text se čte správně (pravidlo gravitace z razítkovače), **pod logem vyplněná drážka** (šířka a hloubka drážky zjištěné z GLB profilu: 30 → 8,2 × 10; 35 → 8,2 × 11,667; 40 → 10,2 × 13,332).
Nemají je šikmé vzpěry. Výchozí stoly mají 9–11 razítek ze všech stran.

V GLB: **logo = instance JEDNOHO sdíleného meshe** (`logo_logiman_cz.glb`, uzly `n<i>` s `translation` + `rotation`, vlastní oranžový materiál #EB8E23 jako neprůhledný elox, ne sklo jako v Blenderu), výplň = kvádr ve skupině
materiálu hliník. Soubor naroste o ~0,5 MB (ne desítky MB), `spec.box` stejný, projde `v3d_glb.sanitize` + `final_check` (žádný uzel ani materiál se jménem „logo“).
- Test: `scripts/2026-10-06_razitka_stolu/test_razitka_stolu.py` (nezávislé měření z meshe loga, nezanoření, expozice, pravidla, GLB, všechny systémy), mutace `mutace.py` (15).
- Zatím neověřeno na živém modelu v prohlížeči nabídky – po zapnutí u bot5 ukázat Robertovi.
