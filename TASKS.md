# Aktuální backlog (task board)

Zapsáno 2026-07-26 (bot2), na Robertovu žádost - sdílený seznam
rozpracovaných/otevřených úkolů, aby nový bot (i ten spuštěný přímo na
serveru) věděl, co je k dispozici, bez nutnosti brífinku od jiného bota.

Jak to funguje: `AGENTS_LOG.md` je chronologická historie ("co se
stalo"), tenhle soubor je aktuální snímek ("co ještě zbývá"). Když úkol
vezmeš, zapiš se do sloupce "Vlastník" a commitni (stejná disciplína
jako `DEPLOY_LOCK.json` - jde jen o vlákno, ne o soubory, takže zámek
`DEPLOY_LOCK.json` tu potřeba není, dokud sám neupravuješ `webapp/*`
nebo `api/app.py`). **Po dokončení řádek SMAŽ** (ne přesunout do
"Hotovo" - žádná taková sekce už není, viz `PRAVIDLA_ZAPISU.md` bod 6:
jednorázová dokončená práce nás nezajímá, stačí zápis do
`AGENTS_LOG.md`; git historie tohohle souboru je záloha, kdyby bylo
někdy potřeba přesné znění).

## Otevřené úkoly

- **[bot10] TRUBKOVÝ GENERÁTOR (Dynamic Ø28; Robert přes bot9 2026-10-07: „bot 10 může potom dělat trubkový generátor“): ČEKÁ NA POKYN, NIC ZATÍM NEZAČATO.** Tři části: 01 kompatibilita se stoly, 02 výchozí FBX dodá Robert později, 03 policové vozíky. Podklady jen ke čtení (nezapisovat do `/home/openai1`): náhled `nahled-john/dynamic-komponenty-v1/`, GLB + STEP v `/home/openai1/konfigurator/vystupy/dynamic/`, poznámky `…/poznamky_generatory.md`. Dopravníky vede bot8 (ne bot10). Generátor stolu 05 (system 45 Robustní) a okno Vzhled jsou hotové (commit 4cb56b16, API část nasazena 22:19 na Robertovo „nasadit hned“), start po potvrzení od bot9 / Roberta; předávka bot10 = `scripts/handover.py list --bot bot10` (otevřený záznam, nejnovější).
- **GENERÁTOR VÁLEČKOVÝCH DOPRAVNÍKŮ (zadal Robert 2026-10-07; „generátor dopravníku udělá John“ – John od 18:17 dostal celý generátor od bot9; bot5 drží jen serverovou část): ČEKÁ NA JOHNŮV NÁHLED A ROBERTOVO SCHVÁLENÍ.**
  Návrh a rozhodnutí Roberta: `docs/NAVRH_GENERATOR_DOPRAVNIKU.md`; Johnův náhled `nahled-john/generator-dopravniku-v1/` a popis rozhraní `vystupy/generator_dopravniku.md` (bot9). Robert 2026-10-07 večer: generátor po schválení Johnova náhledu PŘEVEZME GEOMETR = bot8 (až dokončí multiboxy; ne bot10, ten dělá generátor stolů systém 45 a potom trubkový/Dynamic generátor 01/02/03); bot16 UI až po schválení. Do té doby geometrii/UI nikdo nedělá (stop 2026-10-07, nic z toho nezačali nebo je commitnuto).
  bot5 (hotovo a commitnuto): rozcestník `api/konfigurator_registr.py` + delegace tras v `stul_shop.py`, `api/dopravnik_shop.py` (schéma, resolve, cena = recept, pro_objednavku, glb_bytes; test 33/33 se zástupným konfigurátorem), košík a nabídka z konfigurace přes rozcestník. Zbývá po Robertově schválení Johnova náhledu: napojit jeho pravidla/díly (`dopravnik_konfigurator`) a GLB (`dopravnik_glb`) na shop, karta generátoru (neaktivní) + `app_settings.configurator_products`, texty de/hu (bot7), nasazení API 0:00/12:30. Boční vodítka až po zjištění držáku u dodavatele.
- **[bot8] HORNÍ POLICE MEZI ZADNÍ STOJKY (Robert 2026-10-07: „přidat do generátoru různé typy polic mezi zadní stojky“; zaškrtl VŠE: rovná z laminodesky, rámová bez desky, šikmá na boxy, s lemem + „rám s překližkou v drážce u 40/45 a u 30/35 kromě laminodesky 18 mm i 12 mm, také do drážky MDF 8 mm“ + „police jako rám s přepážkami z překližky 10 mm kotvená úhelníky, viz stůl SSE“):** **HOTOVO v repu 2026-10-08** (`110b03d3` + šikmá `5ac1c6bb`, 6 typů, mutace 149/151; API reload 12:30; **čeká:** Robertovo QA a body z AGENTS_LOG, cena a aktivace karty #5360). Karta laminodesky 12 mm = **#5360 založena NEAKTIVNÍ** (orientačně 1 050 Kč/m², Robert upraví cenu a aktivuje; pravidlo 54). Hotovo týž večer: vzpěry `ccf00d96`, LED 600 model `79110369` + generátor `fe7213d4`/`7059180d` (volba délky `led_delka`), spodní police bez desky `87480305` – API reload 12:30; **čeká:** překlady de/hu nových řetězců (bot7/bot16, `scripts/miniweb_jazyk_zdroj.py --lang de|hu`).**
- **[bot8] DOPRAVNÍKY – PŘEVZETÍ GEOMETRIE (Robert přes bot9 2026-10-07: generátor vede geometr; plán poslán Robertovi; Robert chtěl STEP vzorek ke kontrole konstrukce – HOTOVO, odkaz mu poslán):** rozpracováno v `scripts/2026-10-07_dopravnik_geometrie/` (README = předávka): kandidátní `dopravnik_konfigurator.py` hotový (parita s Johnovým `resolve` 1588/1588), STEP sestavovač hotový. **Zbývá:** `api/dopravnik_glb.py` + přesun modulů do `api/` (guarded) + testy shopu (bot5), opravy `dims` a `valid_geometry`, potom 4 konstrukční rozhodnutí Roberta (patka, spoj spodního rámu, uložení válečků, zajištění nohy; po jednom s obrázky). **Pozor:** Johnova CAD knihovna `dily.glb` je veřejně stažitelná (`/nahled-john/generator-dopravniku-v1/dily.glb`) – řešit s Robertem.**
- **[bot10] DESKA POKRAČUJE DOZADU, KDYŽ SE ODEBEROU ZADNÍ STOJKY (Robert 2026-10-08: „stoly generator, když se odejmou zadní stojky (zkrátí), deska musí pokračovat dozadu překrýt svislé profily“): HOTOVO V KÓDU A TESTECH, API ČEKÁ NA NASAZENÍ (reload).** Stůl BEZ zadních stojek: pracovní deska o tloušťku profilu delší (30 / 35 / 40 / 40 mm u systémů 30 / 35 / 40 / 45), zadní hrana v rovině zadního líce zadních noh, překrývá zadní svislé profily i zadní příčku; záslepky na horních koncích zadních noh zmizí samy; se stojkami a SSE beze změny. `RULES_VERSION` se NEMĚNÍ – kanonický hash stolu bez stojek nese značku `_deska_zad` (nový hash a kód jen u něj), hashe stolů se stojkami beze změny. Kód: `api/stul_konfigurator.py` `deska_zadni_pokracovani`, `api/stul_shop.py` (meze výřezů), `api/stul_glb.py` (hash). Testy: `scripts/2026-10-08_deska_pres_nohy/` (README; test proti stavu před změnou na pseudonáhodném vzorku systémů 30 / 35 / 40 / 45) + celá sada generátoru nad kopií; upraveno: očekávaná hloubka desky v `test_stul_koty.py` a položky `stojky: false` ve zlatých fixturách `golden_head.json` (panely, LED 600, LED ručně, police, police bez desky – jen ty položky, ostatní beze změny).
- **[bot10] VÝCHOZÍ ÚHEL POHLEDU 3D V GENERÁTORECH (Robert 2026-10-08: „chci nastavit výchozí úhel pohledu 3D v generátorech“): HOTOVO V KÓDU A TESTECH, statika živá po commitu, API ČEKÁ NA NASAZENÍ (0:00 / 12:30 nebo Robertovo „nasadit hned“; do té doby se v okně „Výchozí konfigurace“ blok neukáže).** Jedno nastavení pro všechny generátory (30 / 35 / 40 / 41 / 45, karty, mini-shopy, vložený generátor): admin natočí model a klikne „Uložit aktuální pohled jako výchozí“ (dvoukrokově; `app_settings.configurator_view_default` = `{az, el}`, `PUT` / `DELETE /api/shop/configurator/view`, jen admin, audit v téže transakci); viewer3d.js 1.17.0 (`isoAngles`, `setIsoAngles`, `currentAngles`); bez uložení platí 35° / 25°. Soubory a testy: `scripts/2026-10-08_vychozi_pohled/README.md`, `api/stul_pohled.py`. **Pozn.:** při vývoji testu vzniklo v živém `audit_log` 6 zkušebních řádků (id 6878–6883, `configurator_view`, 2026-10-08 09:15:21) – smazání mi systém zakázal, smí je smazat Robert.
- **[bot10] SCÉNA: PATKY = ŠROUB S MATICÍ + ČERNÝ KUŽEL, STŮL S PATKOU M8 SE DO SCÉNY VKLÁDÁ CELÝ (Robert 2026-10-08: „když udělám nabídku z generátoru, 3D scéna není ta nová ale stará“): HOTOVO A ŽIVĚ (statika, commit viz AGENTS_LOG).** Výkresy a 3D pohledy online nabídky z generátoru dělá Scéna z katalogových dílů, ne z GLB generátoru (ten měl černý kužel od nasazení API). `webapp/js/scene/patky-kuzel.js` (nový) rozdělí katalogové GLB patek 3251 / 3283 na šroub s maticí a kužel `#242424`; nález při opravě: patka M8 (3251, systémy 30 a 35) má `visible_in_scene=0`, Scéna ji neznala a stůl s patkami vložila napůl (21 z 51 dílů, alert, výkresy z neúplného stolu) → `stul-konfigurator.js` chybějící díl doplní z karty produktu a stůl nikdy nevloží napůl. Staré nabídky, uložené výkresy a už hotové rendery mají původní patky (přerenderovat jen na Robertův pokyn). **Otevřené:** karta patky M10 (#3283) má od 10:46 barvu `#ff0000` (Robert, zřejmě „Obarvit díl“ – ukládá se jako výchozí barva dílu; původně `#4d4d4d`), šroub s maticí ji ve Scéně drží → zeptat se Roberta, zda ji vrátit. Soubory a testy: `scripts/2026-10-08_patky_kuzel/README.md` (část Scéna), `test_patky_scena.js`, `scripts/2026-10-02_stul_testy/test_stul_panel.js` (T6c–T6e), `docs/NABIDKA_VYKRESY_ZE_STOLU.md`.
- **[bot10] KARTY HOTOVÝCH STOLŮ Z GENERÁTORU – TLAČÍTKO „Vytvořit kartu“ V GENERÁTORECH (Robert 2026-10-07: „přidat do generátorů: tlačítko které z aktuální sestavy vytvoří aktivní kartu“, dřív přes bot4 „budu vyrábět sestavy stolů z generátoru (karty) stejně jako u Vandr sestav“; převzato od bot8): HOTOVO v kódu a testech (commit viz AGENTS_LOG), statika živá, API čeká na nasazení (0:00 / 12:30 nebo Robertovo „nasadit hned“; do té doby se tlačítko neukáže).** Tlačítko v „Cena a scéna“ generátorů 01–05 (jen s právem `sklad_karty/vytvorit`) založí AKTIVNÍ kartu `STUL-S<systém>-<hash8>` (konfigurátor s uloženou konfigurací, model bez razítek v `webapp/katalog/stul/`, záznam `stul_karta_<id>`); kontrakt, rozhodnutí, endpoint a pasti: `docs/KONTRAKT_KARTA_Z_KONFIGURACE.md`. **Zbývá:** nasazení API; první kartu založí Robert → pošlu bot4 její ID (jeho automat otoček, výchozí VYPNUTO; CLI `scripts/stul_karta_glb.py` je hotové); kategorie pro systém 45 neexistuje (karta bez kategorie, v dialogu jde zvolit); cena v kartě je snímek (stránka ukazuje živou).
- **GENERÁTORY STOLU 01/02: panely vsazené do profilů, vestavěný rám, výška stojek, elektrožlab (bot8, zadal Robert 2026-10-05): NASAZENO NAŽIVO 2026-10-05 07:38 (Robertův klik), ČEKÁ NA ROBERTOVU KONTROLU.**
  Skici (schváleno, platí 1. verze rámu): Sdílený disk → Vlastní tvary → Stul system 30 (`skica_1_panel_mezi_stojkami`, `skica_2_dva_panely_plna_stredni_noha`, `skica_3_vestaveny_ram`).
  Hotovo: výchozí stůl 1280 mm s 1 panelem VSAZENÝM mezi zadní stojky (profil nad/pod, mezera 1 mm, nejmenší šířka z délky panelu 1252 / 1272); panely po jednom kuse (vedle sebe s plnou střední nohou, jinak řada nad, max. 2 řady),
  posun panelů po stojkách, `stredni_opora` auto/noha/ram (vestavěný rám mezi 4 celými podélníky, jen se spodní policí), výška zadních stojek 200–1500, elektrožlab se dotýká panelu/profilu a je pohyblivý (svisle, do stran),
  veřejné sloty `panelcount`, `panelpos`, `midsupport`, `posth`, `socketup`, `socketside` (cs/en/sk), 3D ovládání, cena/kusovník/výrobní výpis, `rules_version` 2026-10-05.1 (všechny kódy STL-… jiné). Kontrakt: `docs/KONTRAKT_KONFIGURATOR_UI.md` (sekce 2026-10-05).
  Testy: `run_all.sh` 20 sad (nová `test_stul_panely.py`) + nad systémem 40 `spust_v_systemu.py 40 …`; `test_prejimka_system40.py` a `test_shop_system40.py` (bot10) upraveny na nový výchozí stůl; `test_regrese_system30.py` (bot10) už z podstaty neplatí (systém 30 se vědomě změnil).
  Otevřené: (a) u spodního profilu panelu se na úzkém stole (do 1303 mm v systému 30, do 1341 mm v 40; tedy i na výchozím 1280) rožky nevejdou (narazily by do panelu) a nedávají se – spoj se počítá, rožek ne; Robert rozhodne, zda to chce jinak (např. rožky POD spodním profilem, panel o ~30 mm výš); (b) náhled tažení šířky nechává desku police s výřezem pro rám, dokud se tah nepustí;
  (c) rychlost: `odpoved()` výchozí stůl ~0,27 s, rám se 3 policemi ~0,46 s (nové tahy přidaly sondy živého tažení, `_aabb` dostal paměť `_AABB_MEMO`); veřejné `resolve` nové konfigurace 0,35–0,8 s.

- **OCELOVÉ ŠUPLÍKY 1 / 2 / 3 v generátorech stolu (bot8, zadal Robert 2026-10-05 přes bot5; údaje od Roberta): V KÓDU HOTOVO, ČEKÁ NA NASAZENÍ (12:30 / 0:00), karty neaktivní.**
  Robert: 1 šuplík výška vnější 180 mm, SKU `Suplik.ocel.440136`, 3 900 Kč bez DPH; 3 šuplíky 450 mm, SKU `Trojsuplik.ocel.440138`, 5 900 Kč; 2 šuplíky (karta 4930) 280 mm. Hotovo: modely `product_4956.glb` / `product_4957.glb` (z kandidátů bot5, přepočtené na skutečnou výšku, vrch vždy na příčkách; commit 6285472d, skripty `scripts/2026-10-05_suplik_varianty_final.py`, `scripts/2026-10-05_suplik_karty.py`), karty **#4956** a **#4957** založené NEAKTIVNÍ (`visible_in_scene=1`, kategorie 200, cena z karty; pravidlo 54 – aktivuje Robert),
  parametr `suplik_pocet` (1/2/3, výchozí 2; hash výchozího stolu beze změny), nevejde-li se vyšší box, počet se snižuje 3 → 2 → 1 (`suplik_orez`), veřejný slot `drawercount` (cs/en/sk, oznámení o snížení, token klíč `D`, BOM „šuplíkový box (1 šuplík)“…), 3D menu „Box s N šuplíky“, test sada 22 `test_stul_supliky.py` + bloky v `test_stul_shop.py`. Kontrakt: `docs/KONTRAKT_KONFIGURATOR_UI.md` („Počet šuplíků“).
  Otevřené: (a) SK/EN texty (`help_drawercount`, `SUPLIKY_OREZANO`, menu v `stul_ovladani_verejne.py`) k pročtení bot7; (b) karty #4956/#4957 jsou 1:1 jako sourozenci 4928–4932 (kategorie 200: bez fotek a textů, dostupnost „3 - 5 týdnů“ jako 4930; ověřila bot5) – zbývá jen HMOTNOST (`weight_g` NULL u všech dílů kat. 200): bez ní je u konfigurací s těmito díly doprava `weight_incomplete` = „cena ke schválení“ (nic se nerozbije, řeší zaměstnanec), doplní Robert po hmotnostech od dodavatele; (c) skutečné rozměry hloubky/šířky boxů 1 a 3 šuplíků od dodavatele neznáme (pudorys 565 × 583,1 mm převzat z dvojšuplíku, výška přesně podle Roberta); (d) nové chování pro dosavadní výběr: výchozí 2 šuplíky na velmi nízkém stole (≤ ~600 mm s policí) se sníží na 1 místo odebrání boxu.

- **KÓTY VE 3D NÁHLEDU generátorů stolu 01–03 (bot8, zadal Robert 2026-10-05: „doplnit do generátorů ve 3D náhledu … musí tam být kóty v drátěném pohledu“): HOTOVO v kódu a testech; část „panely pohyblivé“ ROZPRACOVANÁ.**
  Seznam od Roberta: celková výška od podlahy po poslední konec profilu · délka a hloubka pracovní desky · výška horní roviny desky od podlahy · vzdálenosti perforovaných panelů od všech noh (panely chce pohyblivé, mají-li mezi nohama mezeru) · vnitřní výška ke spodní hraně podélníku nesoucího desku · mezery mezi spodními policemi · výška horní roviny každé spodní police od podlahy.
  Hotovo: `api/stul_koty.py` (výpočet z výsledku generátoru) → spec v3d `dims` v GLB (`stul_glb.poskladej_glb(…, koty)`; commit 229dbb53; hash a `rules_version` beze změny), viewer: volitelné `dims[].m` (poloha popisku), `product-configurator.js` (`viewerOpts.hudKoty:true` smí přebít `dims:0`; kóty se při tažení ve 3D vypnou a vrátí), `stul-host.js` zapíná přepínač Kóty jen na stránkách Generátor stolu 01–03 (veřejné stránky `dims:0` beze změny). Testy: `test_stul_koty.py` (1976 kontrol × 3 systémy, nezávislé vzorce z parametrů a `police_meze`, GLB, mutace), `test_stul_koty_stranka.js` (prohlížeč, 01/02/03, drátěný vzhled, tažení), `test_stul_koty_verejne_bez.js`; `run_all.sh` kroky 27–29.
  Otevřené: (a) ~~panely vodorovně pohyblivé~~ HOTOVO (`panely_z` / veřejný slot `panelside`, viz níže); (b) Robert může chtít kóty i na veřejných stránkách (dnes ne: `dims:0`) – zapnutí = `viewerOpts.hudKoty:true` v mini-shopu/embedu; (c) hloubka desky v systémech 35/40 je fyzická deska (795 / 790 mm), ne zadaná hloubka stolu 800.
- **PANELY VODOROVNĚ POHYBLIVÉ, mají-li mezi nohama mezeru (bot8, Robertova závorka u kót 2026-10-05: „panely chceme pohyblivé pokud mají mezeru mezi nohama“): V KÓDU HOTOVO, ČEKÁ NA NASAZENÍ (API 00:00 nebo ručně).**
  Generátor: parametr `panely_z` (mm od středu úseku mezi nohama, + = doprava, výchozí 0 = beze změny hashe i modelu; společný pro všechny panely a řady, elektrožlab jede s panelem, profily nad/pod stojí), od každé nohy zůstane aspoň 1 mm (mez ± (mezera − 1 mm) na celé mm; užší úsek u dvou panelů u střední nohy určuje společnou mez; mimo meze se ořízne). Veřejně slot `panelside` (posuvník po 1 mm, `options.panelside {min,max,value}`, cs/en/sk, token klíč `X`, souhrn jen ≠ 0); 3D úchyt `panely_z` s měřením mezer od VŠECH noh + položka „Panely vrátit doprostřed mezi nohy“; živé tažení (`posun` ze sondy s kroky 10/5/2/1 mm). Kóty ve 3D ukazují mezery od noh a drží krok. Mini-shop i vložený generátor dostanou slider taky (sdílené schéma), skrytý když panel žádnou mezeru nemá.
  Testy: nová sada 30 `test_stul_panely_z.py` (81 kontrol × 3 systémy: nezávislé měření z AABB, meze, hash, tah, živé operace), 31 `test_stul_panely_z_stranka.js` (prohlížeč 14 kontrol), bloky v `test_stul_shop.py` (1288), úpravy `test_stul_ovladani.py` (úzké rozsahy tahů) a `test_stul_panely.py` (menu).
  Otevřené: (a) SK/EN texty `panelside` + `help_panelside` + menu/štítky ve 3D k pročtení bot7; (b) `scripts/2026-10-04_system40/test_regrese_*` (bot10) hlásí jen očekávané rozdíly v metadatech (`parametry` +`panely_z`, `panely_info`, `ovladani_*`, `volby`, `rozsah`), geometrie/hash/problémy/výrobní výpis beze změny – případně doplnit seznam očekávaných rozdílů.
- **PRAVIDLA STOLU PO SYSTEMECH 30 / 35 / 40 + jen admin (bot8, zadal Robert 2026-10-05 obrázkem okna „Pravidla stolu“: „konkrétní hodnoty chci mít nastavitelné pro jednotlivé systémy zvlášť, 30/35/40, každému zadám individuálně; tyto pravidla vidí jen admin“): V KÓDU HOTOVO; STATIKA ŽIVÁ, API ČEKÁ NA NASAZENÍ (00:00 nebo na Robertův pokyn).**
  Všech šest pravidel (hloubka pro podpěry, šířka pro střední nohu, délka ramene LED pro vzpěry, cena výřezu, ceny návleku 200/400 mm) má pro každý systém vlastní hodnotu: generátor `PRAVIDLA_SYSTEMU` + pohled `PRAVIDLA` na aktivní systém, `pravidlo(klíč, systém)`, `prah_sirky/hloubky(systém)`, `nastav_pravidla(sada, system=…)` (bez `system` všem – dosavadní chování), cena výřezu/návleku podle systému sestavy (`system_z_dilu`), hash nese prahy systému konfigurace (hash výchozích stolů beze změny), veřejné API po systému produktu. Uložení `app_settings` `stul_pravidla`: starý plochý JSON (dnes `{"cena_vyrez": 2800}`) platí pro všechny systémy; po první změně po systémech `{"35": {…}}`. API: `GET/PUT /api/stul/pravidla` JEN ADMIN (`@admin_required`; i s oprávněním `nastaveni` ne-admin 403), PUT `{system, pravidla}`, starý plochý PUT jen dokud jsou systémy stejné (jinak 409). Okno na stránkách Generátor stolu: přepínač 30 / 35 / 40 (předvolen systém stránky), Uložit / Výchozí jen pro zvolený systém, neuložená změna zabrání přepnutí; ukazuje se a načítá jen adminovi; se starším API zůstává jeden formulář jako dosud.
  Testy: nová sada 32 `test_stul_pravidla_systemy.py` (91 kontrol, 8 mutací chyceno), 33 `test_stul_pravidla_stranka.js` (16, atrapy API – nic se nezapisuje), `test_stul_pravidla.py` (172) a ostatní sady zelené (1–22, 27–31, DB `test_stul_api` 84, `test_stul_shop` 1288, systémy 35/40 od bot10).
  Otevřené: (a) **nasazení API** – do té doby okno ukazuje jednu sadu (starý tvar) bez přepínače systémů; (b) Robert zadá hodnoty pro 35 a 40 (dnes mají shodné výchozí, cena výřezu 2 800 Kč platí pro všechny systémy).
- **GENERÁTORY STOLU 01/02: formáty tabulí laminodesky, DĚLENÍ DESEK u střední nohy / vestavěného rámu (bot8, zadal Robert 2026-10-05): HOTOVO A COMMITNUTO; API se nasadí samo ve 12:30 (plánovaná služba; viewer `v3d-ovladani.js` a `?v=` hashe jsou živé hned), pak čeká na Robertovu kontrolu.**
  Zadání: *„formáty tabulí lamino desky jako jedno kritérium, deska musí být dělená v místě středové nohy resp. vestavěného rámu“*; upřesnění: *„zkrátit je potřeba pouze spodní desky u verze vestavěný rám, není potřeba zkracovat ty, co na sebe průběžně navazují“*.
  Hotovo: tabule 2070 × 2800 mm (karta 4933 `board_sheet_*`, prázdné = výchozí) jako kritérium – pracovní deska i každá spodní police jsou u střední opory DVĚ desky (levá/pravá část), práh šířky má strop 2800, poloha střední nohy se omezí tak, aby obě části byly v tabuli (`options.mid` 7–93 % u 3000 mm), problém `deska_mimo_tabuli` u menší tabule;
  na sebe navazují bez mezery pracovní deska (i u rámu) a police u střední nohy, JEN spodní police u rámu jsou obě kratší o mezeru profil + 2 × 1 mm (dřívější výřez 32 × 32 mm v jedné desce je pryč); výřez přes spáru = zářez v obou částech (v ceně jednou), ložiska se u spáry vynechávají; výrobní výpis/list a kusovník po deskách (levá/pravá část, `deska_id`); oznámení o dělení u stolu se střední oporou (cs/en/sk);
  ve 3D jedna část na polici/pracovní desku, živé tažení střední nohy natahuje části desek; `v3d-ovladani.js` `liveApply`: vrcholy PŘESNĚ uprostřed dílu (mesh desky má střed plochy) → `natahni` o d/2, `roztahni` nic (zpřesnilo i náhled šířky/hloubky desek). `rules_version` 2026-10-05.2 (všechny kódy STL-… jiné). Kontrakt: `docs/KONTRAKT_KONFIGURATOR_UI.md` (sekce „Formáty tabulí laminodesky“), `docs/OVLADANI_3D.md`.
  Testy: `run_all.sh` 21 sad (nová `test_stul_desky_tabule.py`, mřížka 288 konfigurací, mutace chycené) + upravené `test_stul_vyroba/podpery/panely/loz/zive/konfigurator.py`; nad systémem 40 `spust_v_systemu.py 40 …` (`test_stul_glb` a část `test_stul_konfigurator` jsou jen pro 30, viz README systému 40).
  Otevřené: (a) texty cs/en/sk oznámení o dělení (`text_desky_deleny`, `DESKA_MIMO_TABULI`) zrevidoval bot7 (4873d30a); (b) hotfix GLB (kusy rozřezaných desek po hladinách, 4d1008bb) jede s tímto nasazením; (c) tabule se čte z karty 4933 (pole prázdná = výchozí 2070 × 2800) – Robert může na kartě vyplnit skutečný formát.
  (d) VYŘEŠENO (bot5 + bot8): pravidla stolu i formát tabule se nově načítají v `before_request` (`stul_api._STUL_CESTY`) i pro košík, objednávky, `/api/shop/stul/`, mini-shop quote/orders, schéma konfigurátoru a admin objednávky (dřív jen `/api/stul/*` a `/api/shop/configurator*`, takže worker obsluhující jen košík mohl počítat s výchozími pravidly); NE uvnitř `pro_objednavku` (sdílené spojení, `close()` = rollback). Test `test_stul_pravidla.py` 3e.


- **Druhý generátor stolu = systém 40 (bot10, 2026-10-04): HOTOVO a živě** (karta #4954 aktivní, kategorie 311 „Robustní balicí stůl system 40“ s generátorem, interní stránka `/stul-konfigurator-40.html`, vč. šikmých vzpěr; zákaznický přepínač 30 ↔ 40 hotový a živý (bot16, 2026-10-05); systém 30 beze změny; viz `scripts/2026-10-04_system40/README.md`).
  **Zbývá:** (1) Robert: SKU a délka zápustného šroubu ke šikmé spojce 3220; (2) ověřit šroub M6×16 ke spojce 3176; (3) uchycení PET/LED/elektrožlabu/panelů do drážky 10 (v kusovníku zatím jen spojky).
- **Třetí generátor stolu = systém 35 (bot10, 2026-10-05): HOTOVO a živě v API, karta #4955 AKTIVNÍ (Robert 2026-10-05 08:06), kategorie #312 „Ergonomický balicí stůl system 35“ založena** (profil 35×35 `profil_35x35`, drážka 8; rohové spojky 3158, patky 3251 a šikmé spojky 3254 ze systému 30 vystředěné na střed drážky – Robert; záslepka 3090 35×35; stránka `/stul-konfigurator-35.html` = Generátor stolu 03; viz `scripts/2026-10-05_system35/README.md`). Kategorie #312 (Robert 2026-10-05: „na každém webu novou kategorii: Ergonomický balicí stůl system 35“; kostra bez textu pod 182, `/ergonomicky-balici-stul-system-35`, `scripts/2026-10-05_system35/zaloz_kategorii_system35.py`; obrázek karty mini-shopu `webapp/miniweb/img/produkt-4955.jpg`). **Zbývá:** (1) bot7: CS texty #312, mini-shop EN+SK JSON (kategorie `ergonomic-packing-table-system-35`, PWB-003, karta 4955), štítek `pdc.sys35`, `.multi` texty domovské stránky pro 3 produkty, popis karty 4955; (2) bot16: `CATEGORY_GENERATORS[312]` (`card: 4955`) + `PRODUCT_GENERATORS[4955]`, import mini-shop draftů, 3 tlačítka přepínače na 360 px; (3) Robert: schválení mini-shop draftů (NÁVLEK nohou je v generátoru od 2026-10-05, viz další položka); (4) ověřit na fyzické sestavě: spojka 3158 na profilu 35 vystředěná, patka M8 (3251) v profilu 35 (jinak M10), šroub M6×12 ke spojce; (4) animace „Připni cokoli“ pro 35 není (dlaždice se u 35 schová); po bot16 doplnit `test_kategorie_generator.js` o 312.
- **Návlek nohou (jekl 40×40×2) v generátoru systému 35 (bot10, 2026-10-05, Robert): HOTOVO v kódu, API se zapne nasazením.** Robert: „Navlek/jekl nastavitelné délky od 200 do 400 mm se nasadí namísto koleček, záslepek nebo patek jako další volba resp. jako výchozí volba … alespoň 70 mm nohou stolu zajelo do jeklu, na jehož spodním konci bude jeklová záslepka“, „v úrovni návleku nemůže být jiný komponent, žádný“, cena 200 mm 370 Kč / 400 mm 550 Kč. Po skice (Robert 2026-10-05 odpoledne: „jinak ok“): **minimální mezera nad jeklem 3 mm**, **vnější rohy jeklu sražené 2 mm jako jekl stolu SSE**, **barva tmavá šedočerná RAL 7016, lesk** (commit viz AGENTS_LOG; živě po nasazení 00:00). Volba `navlek` + `navlek_delka` (veřejně sloty `sleeve`, `sleevelen`), **výchozí v systému 35 zapnutá (300 mm, bez koleček)**, cena lineárně 370 → 550 Kč za kus (pravidla `cena_navlek_200/400`), kusovník, výrobní výpis a list, 3D ovládání, token, texty cs/en/sk; systémy 30 a 40 beze změny (regrese bit po bitu); detaily `scripts/2026-10-05_system35/README.md`, `docs/KONTRAKT_KONFIGURATOR_UI.md`. **Zbývá:** (1) Robert: potvrdit předpoklady (cena v Kč bez DPH za 1 návlek vč. záslepky, výchozí zapnutý, zásun přesně 70 mm v nejvyšší poloze), způsob zajištění výšky (aretace, šrouby, SKU jeklu); (2) bot7: zkontrolovat texty slotů a upravit text kategorie 312 / karty 4955, obrázek karty mini-shopu `produkt-4955.jpg` přegenerovat (výchozí stůl má teď návlek); (3) návlek ve Scéně („Vložit do Scény“ ho nevkládá): chce-li ho Robert i tam, potřebuje `cfg_dily` řádek + GLB; (4) fyzické ověření.
- **Čtvrtý generátor stolu = ergonomický stůl SSE, systém 41 (bot8, 2026-10-05, Robert: „postav nový generátor, kompatibilní jako ostatní, v podstatě jde o system 40, jen nohy … jeklové s vnitřním profilem 35×35“): HOTOVO, NASAZENO 2026-10-05 17:52 (Robert: „Nasadit hned“; živá je stránka `/stul-konfigurator-41.html`, veřejné API `stul_system41`); karta #4959 `STUL.SYSTEM41.KONF` založena NEAKTIVNÍ a zapsána do `configurator_products` (recept `stul_system41`), kategorie zatím NEZAŘAZENA.** Vlastní jádro `api/stul_sse.py` (podélníky 40×40 + nohy SSE, spodní police na spojnicích, šuplíky jako v systému 40, střední noha nad prahem 2000 mm), veřejné API `api/stul_shop_sse.py`, stránka `/stul-konfigurator-41.html` (Generátor stolu 04), recept `stul_system41`; rozsah v1 (Robertova volba): základ + police + šuplíky, hloubka = spojnice 400–1100 + 80 mm, deska max 3000, mezera mezi nohami 1570 u desky 2000; do Scény se zatím nevkládá. Testy `scripts/2026-10-05_sse/` (viz tamní README). **Zbývá / čeká na Roberta:** (1) ceny nohy SSE (Pravidla stolu → SSE: `cena_noha_sse_400` / `_1100`, dokud nejsou, je cena stolu BEZ noh a výpis to hlásí); (2) předpoklady k potvrzení: deska 18 mm (vzor SSE má 25 mm), vnitřní profil zajíždí do jeklu ≥ 100 mm → výška desky 700–1000 mm, police 20 mm od zadního jeklu, výchozí výška 830 mm; (3) případně kategorie pod 182 (Robert nežádal) + záznamy pro kartu #4959 v `product.html` / `category.html` (`PRODUCT_GENERATORS` / `CATEGORY_GENERATORS`), snímek karty a texty od bot7; aktivace karty jen Robert (pravidlo 54); (4) další kroky: stojky se zadními panely, LED, elektrožlab, PET, výřezy, ložiska; vložení do Scény (nohy SSE ve Scéně); 3D ovládání je jen základní (výška, šířka, hloubka, posun šuplíků).
- **Pátý generátor stolu = hluboký stůl, systém 45 (bot10, 2026-10-07, Robert: „postav generátor stolů system 45, profil 1.1.10.040040.03, hloubka stolu až 2500 mm, možná tam musíme lehce změnit konstrukci“, „kompatibilita s předešlými generátory“): HOTOVO, NASAZENO 2026-10-07 20:56 (Robertovo „nasadit hned“); karta #5353 založena neaktivní, Robert ji 21:00 aktivoval a přejmenoval; system 45 nazýváme též „Robustní“ (štítek přepínače `pdc.sys45`).** Druhá dávka (Robert: „každý systém stolů má pravidla svoje … všechny zlomové míry“): zlomové míry po systémech jako pravidla (`hloubka_stredni_noha` jen 45, `podpera_max_rozpon`, `min_odstup_stredni_noha`; výchozí = dřívější konstanty), viz `docs/KONTRAKT_KONFIGURATOR_UI.md`. Profil jako systém 40 (SuperLight S10 40×40), hloubka 400–2500 mm; do 1500 mm bit po bitu jako 40, nad 1500 mm střední noha na každé straně + příčka pod podpěrami desky a polic; stránka `/stul-konfigurator-45.html` (Generátor stolu 05), recept `stul_system45`, karta `STUL.SYSTEM45.KONF` NEAKTIVNÍ (`scripts/2026-10-07_system45/zaloz_kartu_system45.py`); viz `scripts/2026-10-07_system45/README.md`. **Zbývá (Robert):** kategorie + texty pro systém 45 (bot7) jen na jeho pokyn (pravidlo 54), cena (zatím součet dílů jako u 40).
- **Vzhled online nabídek v každém generátoru stolů a u každé karty (bot10, 2026-10-07, Robert: „to nemá být jen v jedné kartě, ale automaticky v každé“, „ať se to negeneruje pořád dokola, může to být propojené do generátorů stolů a tam to může sídlit“): HOTOVO v kódu a testech, statika živá hned po commitu.** Okno „Vzhled online nabídek“ (barvy, lesk, AO, HDRI, hliník; jedno nastavení pro všechny nabídky) je ve všech generátorech stolů 01–05 (jen admin; iframe kontrolní scény nad modelem generátoru, nic se nestaví na serveru) a odkaz „Vzhled online nabídek…“ je u KAŽDÉ karty produktu (jen admin; Vandr karta → kontrolní scéna, jiná → generátor). Viz `docs/KONTRAKT_NABIDKA_3D.md` 5m, `scripts/2026-10-07_vzhled_generator/README.md`. Přesun kódu okna do sdíleného modulu zatím NENÍ (kód je v `kontrola.html`, aby zůstaly testy a mutace).
- **Výchozí konfigurace generátoru – admin tlačítko „Uložit jako výchozí“ (bot8, 2026-10-05, Robert: „postav mi admin tlačítko v generátoru, kterým uložím konfiguraci jako výchozí“): HOTOVO v kódu a testech, okno na stránce je živé hned, ukládání se zapne nasazením API (0:00 / 12:30).** Okno „Výchozí konfigurace“ (jen admin, 3. sloupec stránek Generátor stolu 01–04): [Uložit jako výchozí] (dvoukrokové potvrzení) pošle aktuální výběr na `PUT /api/shop/products/<id>/configurator/default`, server ho znormalizuje a přepočítá (neplatný = 409, nic se neuloží), uloží do `app_settings.configurator_default_<id>` a zapíše `audit_log`; [Vrátit původní výchozí] = `DELETE`. Schéma nese `default_selection` (vestavěné přepsané uloženým) a `default_saved`, platí všude, kde se generátor otevře bez odkazu (stránka produktu, mini-shop, embed, interní stránka); vestavěné výchozí se nemění. Pozor: odkazy nesoucí jen odchylky od výchozí se otevřou s novou výchozí. Testy `scripts/2026-10-05_vychozi_konfigurace/` (139 kontrol, 28 mutací) + `test_stul_host.js` sekce H; popis `docs/KONTRAKT_KONFIGURATOR_UI.md`. **Zbývá:** Robert vyzkouší po nasazení a uloží výchozí; ukládání pak ověřit na živé stránce (PUT proběhl, schéma `default_saved: true`).
- **OpenAI bot „John“ (účet `openai1`, Codex CLI, model gpt-6-sol, úsilí xhigh) = nezávislý kontrolor + geometrie, pilot od 2026-10-03 (bot3).** Izolovaný unix účet, kopie kódu bez hesel a záloh v `/home/openai1/konfigurator`
  (pravidla a role v jejím `AGENTS.md`). První kontrola mini-shopu: 16 nálezů (`docs/kontrola_openai1_minishop_2026-10-03.md`), bot5 opravil backend (6b1dbc44),
  zbývá bot16 (front: DIČ ve formuláři, náhled objednávky, země v kontaktu, poškozený košík, vzorová config.*.json, sitemap přes `?slug=`).
  **Blokováno: spouštění bez okna** (`codex exec`) potřebuje AppArmor profil pro bwrap (`/etc/apparmor.d/bwrap-userns`), klasifikátor ho mi zablokoval – nainstaluje Robert příkazem v rootu.
  Do té doby jen interaktivně v terminálu. Boti z OpenAI s ostatními nemluví přímo: úkoly přes soubory, výsledky čte bot3.

- **HOTOVO V REPU 2026-10-02, ČEKÁ NA NASAZENÍ 3:30/12:30 (bot10): 3D model online nabídky z karty Vandr + náhradní obrázky.**
  Tlačítko „Vytvořit online nabídku“ (bot16, admin pruh na produktu) volá `POST /api/admin/vandr-vyroba/<id>/nabidka`; endpoint nově staví
  interaktivní 3D model (pohyby, dorazy, druhy boxů) a při jakémkoli selhání 3D vytvoří nabídku dosavadní cestou (`v3d:false` + důvod).
  **Chybějící Vandr obrázky už nejsou 400** (Robert: #4053, #4482): náhrada = naše snímky otáčky + kótovaný nárys/bokorys vyrobený ze 3D modelu
  (`obrazky_zdroj` v odpovědi). Vandr příkaz `vandr:offer-data --v3d` nasazen (commit v `/opt/vandrawee`). Kontrakt: `docs/KONTRAKT_VANDR_NABIDKA_ENDPOINT.md`,
  `docs/KONTRAKT_NABIDKA_3D.md`, postup/rollback: `docs/V3D_NABIDKA_NASAZENI.md` (okamžitý vypínač 3D: `touch private-files/v3d-vypnuto`).
  Zbývá: (1) ~~bot5 vloží snippet do `nabidka-online.html`~~ HOTOVO 2026-10-06 (bot10 přímo do stránky na Robertův pokyn po nabídce Logiman0122, kde 3D s pohyby chybělo; harness 33 kontrol),
  (2) první skutečná nabídka z karty ověří (v odpovědi `v3d:true`), (3) **NEVIDITELNÉ ZNAČENÍ JE VYPNUTÉ, dokud Robert u počítače nespustí jednorázový příkaz
  na uložení klíče (`V3D_MARK_SECRET` do `api/.env`, příkaz v `docs/V3D_NABIDKA_NASAZENI.md`, sekce „Jednorázový příkaz pro klíč“) a služba se nerestartuje.**
  Do té doby se NIC neslibuje jako forenzní stopa. Viditelné razítko u konfigurovaných stolů: Robert nerozhodl.

- **HOTOVO A NASAZENO 2026-10-06 21:07 (bot10, commit b53e3be5): vzhled online nabídek + společná nabídka z více karet Vandr.**
  (a) **Vzhled** (HDRI, povrch hliníku, AO) se ukládá v kontrolní scéně (`?items=vd:<karta>&rezim=nabidka` → tlačítko „Vzhled nabídek“) a platí pro VŠECHNY nabídky i už vytvořené
  (`api/v3d_vzhled.py`: `GET /api/public/v3d-vzhled`, `PUT /api/admin/v3d-vzhled`; docs `KONTRAKT_NABIDKA_3D.md` 5f). Materiály dílů podle role zůstávají v panelu Rendering → HDRi (platí pro nově stavěné modely).
  (b) **Společná nabídka** levá + pravá + přepážka: `POST /api/admin/vandr-vyroba/nabidka-spolecna` `{"karty":[id,id,(id)]}` (karty téhož vozu, každá jiná strana; jedna 3D scéna, řádek ceny za kartu, kótovaný výkres ke každé straně),
  náhled v kontrolní scéně `items=vd:<a>+<b>+<c>` (docs 5g). Společné nabídky se skládají při VYTVOŘENÍ, ne přes PUT (bot8: PUT drží obyčejné řádky); `scene_offers.py` propouští `offer_options.vandr_drawings` a úprava nabídky je nesmaže.
  **UI sloučení (Robert: „nebudu nic přidávat do řádku URL“): HOTOVO 2026-10-06** – na kartě Vandr produktu (web, admin pruh) odkaz „Společná nabídka…“ → kontrolní scéna; v horní liště select „+ přidat stranu“ (sourozenci téhož vozu z `/api/admin/vandr-vyroba/prehled`) a u skupiny karet tlačítko „Vytvořit společnou nabídku“ (`?items=vd:<a>+<b>&rezim=nabidka`).
  **Robert 2026-10-06/07 – požadavky na 3D v kontrolní scéně / nabídce (kóty a úpravy pro Vandr urgentně): HOTOVO.** (1) kóty společné nabídky po stranách, ne za celek (`v3d_merge.py`, živě 23:12); (2) tlačítka pohybů ve více řadách podle strany (Levá / Pravá / Přepážka; `motions[].g`, `v3d_glb` bot4 f3a27754, strany z endpointu bot4 ba407061, číslování po stranách) a vybraný díl ukáže své rozměry (`selDims`) – viewer 1.11.0; (3) sytost a barvy materiálů v „Vzhled nabídek“ (jezdec + vzorky původních barev, uloží se pro všechny nabídky: `app_settings.v3d_nabidka_vzhled` {env, alu, ao, sat, barvy}) – viewer 1.12.0 + `api/v3d_vzhled.py`. Docs `KONTRAKT_NABIDKA_3D.md` 5f/5g/5h; testy `scripts/2026-10-06_v3d_rady_testy/` + `v3d_vzhled_testy`. Statika živá po commitu, API (sat/barvy v PUT) po nasazení api. **(4) Výzva ke kliknutí při najetí myší na pohyblivý díl** (Robert 2026-10-07: „nech se nabídne při najetí myší na dynamický komponent pobídka kliknout intuitivně“): `hoverHint` ve vieweru 1.13.0 – díl se podsvítí oranžově, kurzor ruka, u kurzoru popisek „Šuplík 2 · Levá strana / Kliknutím otevřete|zavřete“; zapnuto v nabídce a kontrolní scéně, jen myš; docs 5i, testy `scripts/2026-10-07_v3d_hover_testy/` (42 kontrol + 16 mutací). **(5) Odlesky materiálů, hliníku a AO + (6) HDRI ze Sdíleného disku** (Robert 2026-10-07 večer: „řešit odlesky materiálů, jejich AO a také možnost přidat další HDRI ze sdíleného disku“): okno „Vzhled nabídek“ má posuvníky Lesk u každé barvy, Hliník odlesky / matnost, AO síla / dosah a „+ Přidat HDRI ze Sdíleného disku…“ (viewer 1.14.0 / 1.15.0, `api/v3d_vzhled.py` + nové `api/v3d_env_import.py` a `api/v3d_env_prevod.py`, docs 5j / 5k). **NASAZENO 12:30 a Robert import ze Sdíleného disku vyzkoušel (16:18 `berg_inner_2`, ostrý server);** `.exr` zatím ne (chtělo by OpenEXR do sdíleného venv – schválit bot9 / Robert). **(7) AO po komponentech + automatické ukládání vzhledu** (Robert 2026-10-07 16:20: „nenašel jsem AO pro jednotlivé komponenty, jen pro hliníkové profily, doplnit“ a „úpravy barev a lesků chci aby se uložily i pro ostatní další nabídky“): viewer 1.16.0 – posuvník **AO u každé barvy** (`matConfig.ao`, váha 0–200 % podle původní barvy) a **Hliník – AO** (`aluConfig.ao`), dřívější „AO – síla / dosah“ je „AO celkově“; váha se přikládá k AO v extra průchodu do `rtW` (jen když nějaká váha ≠ 1); změny barev, lesku, AO a hliníku v okně se **ukládají samy** pro všechny nabídky (0,9 s po poslední změně, hláška „Uloženo pro všechny nabídky“; HDRI a volba hliníku / AO z rohu 3D zůstávají na tlačítku „Uložit vzhled pro nabídky“), seznam „Uloženo i pro barvy, které v této scéně nejsou“; API `ao_mat` + `alu_cfg.ao` (`api/v3d_vzhled.py`; do nasazení API je AO po komponentech jen náhled – probe `ao_mat`). Docs `KONTRAKT_NABIDKA_3D.md` 5l, testy `scripts/2026-10-07_v3d_aomat_testy/` (65 kontrol + mutace), `test_vzhled_api.py` 30 + 38 mutací, harness 9h. Uložené úpravy platí podle PŮVODNÍ barvy materiálu (materiály v modelech jsou anonymní `m01`…): barva, kterou jiná sada modelů nemá (karty 4964 / 4965 nemají modré #0700ff / #00039a), se v ní neprojeví – nejde o chybu ukládání.
  **Zbývá:** automatické dělení kombinací stran z FBX (11 stran čeká na ruční export), zapnutí značení modelů (viz výše, čeká na Roberta), **razítka loga v 3D modelu nabídky** (Robert 2026-10-06 přes bot5/bot9: build je zatím nevkládá; polohy jsou v `shop_products.vandr_razitka_json`).

- **ZADÁNO 2026-10-02 (Robert přes bot3), NAPŘED NÁVRH: živé 3D modely sestav NE do auta s interaktivní volbou komponent.**
  Robert: „sestavy které nejsou určené do auta budeme vystavovat jako živé 3D modely, a to tak že interaktivní živou volbou
  komponent". **Je to VĚDOMÁ VÝJIMKA z pravidla ochrany 3D modelů (2026-09-06: veřejně jen otočka)**, platí JEN pro sestavy ne do auta
  (stoly, nábytek, SSE…); sestavy do aut (Vandr, regály) zůstávají veřejně jen jako otočný náhled. Rozhodnuto (klikací volby):
  **bez stahování + zploštělá jména uzlů** (jako stupeň 2 v online nabídce); zákazník **vybírá komponenty, model se přeskládá, cena
  se přepočítává živě a hotová konfigurace jde do košíku**. Veřejný pohled NESMÍ jít přes `scene.html` (staff-only brána), potřebuje
  vlastní prohlížeč. Dělení: **bot10** (scéna 2/stoly, prohlížeč + parametrické komponenty, vychází z 3D scény online nabídky),
  **bot5** (cena konfigurace, košík/objednávka nese zvolené komponenty, kusovník), **bot16** (produktová stránka/UI). Napřed
  **krátký společný návrh** (které sestavy jsou „ne do auta", jak se definuje volba komponent, jak se ukládá konfigurace do
  košíku, co přesně se posílá do prohlížeče z hlediska ochrany), pošlete ho bot3 před kódováním. S dealerským programem
  zatím NEPROPOJOVAT (widget etapy 1 ukazuje jen otočný náhled).


- **ZADÁNO 2026-10-02 (Robert přes bot3), ETAPA 1 - NÁVRH NEJDŘÍV: dealerský program (prodej našich produktů přes weby dealerů).**
  Robert: dealer má „na pár kliknutí" přidat naše produkty do svého portfolia na svém webu. Rozhodnuto (Robert, klikací volby):
  napojení = **vložený katalog (kousek kódu na jedno kliknutí) + soubor/feed pro dealery s vlastním e-shopem**; objednávka
  **dealer si vybere**: (a) dokončí se U NÁS → **provize** dealerovi, (b) dokončí se NA WEBU DEALERA → dealer nakupuje za
  **dealerskou cenu** (sleva, ne provize); **bez značky Logiman** na dealerově webu (TEXT_FILTR pravidlo 5, QA `static_page_brand_leak`);
  provize **výchozí 10 %** z ceny bez DPH a bez dopravy, měnitelná u dealera (případně podle kategorie), přiřazení objednávky
  **30 dní** od prokliku, vyplácí se **měsíčně** ze zaplacených objednávek po **14 dnech** na vrácení (vrácení = provize se ruší),
  doklad: **dealer vystaví fakturu** podle našeho vyúčtování (doladit s účetní). Obrázky pro dealery jen otočný náhled, NIKDY
  stažitelný 3D model (ochrana 3D modelů).
  Dělení: **bot5** backend (dealer jako entita/role, dealerská cena, přiřazení objednávek, provize + měsíční vyúčtování, objednávka
  z webu dealera, feed produktů), **bot16** partnerský panel (tlačítko „Přidat na můj web", správa dealerů v adminu) a vložený
  katalog (widget, klíč dealera + povolené domény + limity požadavků). Domluvte se spolu přímo, napřed napište **krátký návrh**
  (datový model, tok objednávky, bezpečnost klíče) a pošlete ho bot3, než začnete kódovat.
  **ETAPA 2 (až po etapě 1): vlastní logo dealera na renderech sestav** (Robert: zdarma BEZ limitu, před renderem VŽDY ruční
  schválení loga ve 3D; rendery zadává jen bot4, logo jako díl sestavy po vzoru `logo_logiman_cz` + razítkovač, bot8/bot10).
  **UPŘESNĚNÍ 2026-10-02 (Robert): dealeři budou PŘEDEVŠÍM nabízet SESTAVY/KONFIGURACE, tj. různé pracovní stoly, stojany a vozíky.**
  To je hlavní obsah dealerského programu. Etapa 1 (produkty a díly, odkaz+provize, cesta b, feed) je hotový základ. Etapa 2 se tím
  stává KLÍČOVOU a splývá s živými 3D modely sestav ne do auta: do dealerova vloženého katalogu patří živý konfigurátor stolů,
  stojanů a vozíků (výběr komponent, živá cena, objednávka cestou a/b) s LOGEM DEALERA v modelu a na renderech. Pořadí: nejdřív
  živý konfigurátor (bot10 + bot5 + bot16, pilotní stůl teprve vznikne), potom jeho vložení do dealerova widgetu s dealerskou cenou
  a logem dealera. Sestavy dealerům zatím NEvydávat, dokud neexistuje konfigurátor i logo.
  **ROZHODNUTO 2026-10-02 (Robert, klikací volba): univerzální ZÁKLAD = naše vlastní stránka s konfigurátorem a LOGEM DEALERA +
  odkaz/tlačítko na dealerově webu** (dealeři mají různé systémy, vložený blok funguje jen u některých). Vložený blok na cizí web a feed se
  NENABÍZÍ A NEROZVÍJÍ (Robert 2026-10-02: „nebudeme to vkládat na jejich web, protože je to složité, každý má jiný systém"; zvolil
  variantu bez bonusu). Hotový kód zůstává nevyužitý. Stránka je na neutrální doméně (bez značky Logiman), stejná neutrální doména jako pro
  widget/feed, později možnost dealerovy vlastní subdomény.
  **UPŘESNĚNÍ 2026-10-02 (Robert): e-shopy dealerů PROVOZUJEME MY na NAŠICH doménách; dealer dostane přístup do administrace až když se
  naváže spolupráce.** Dealer tedy nic nevkládá na svůj web, má od nás hotový e-shop s konfigurátorem a svým logem. Výchozí řešení
  (Robert na doplňující otázky neodpověděl, platí doporučení, změnitelné jedním slovem): adresa = podadresa jedné neutrální domény
  (dealer přidaný v adminu, bez zásahu do nginx), přístup = vlastní PARTNERSKÝ PANEL (ne náš admin), vložený blok a feed se nenabízí a nerozvíjí (Robert).
  **WHITE LABEL (Robert 2026-10-02: „souhlasím s tím, že tam nebude naše logo, bude to no name, tzv. white label"):** dealerský e-shop
  bez značky Logiman (vzhled, adresa, texty, modely, rendery); logo dealera, dokud ho nemá, žádné. Ochranné logo LOGIMAN.CZ v geometrii se
  v dealerských modelech nahrazuje logem dealera nebo vynechává. Prodejce na pokladně, v podmínkách a na dokladu zůstává zákonně
  Logiman s.r.o. (ověřit s účetní/právníkem před prvním ostrým dealerem).
  **VÍCEJAZYČNOST (Robert 2026-10-02: „budou to mini shopy jaké jsme plánovali, 3D konfigurátory, pro každý evropský jazyk připravíme
  separátně doménu"):** dealerský/konfigurátorový e-shop = mini-shop jako storefronty aut, pro KAŽDÝ evropský jazyk samostatná doména.
  Dopad na návrh od začátku: žádný pevně zapsaný český text v konfigurátoru a na kartě (překladové klíče), jazyk/měna/DPH/doprava
  podle domény, hreflang a SEO texty po jazycích (TEXT_FILTR pro každý jazyk). Které jazyky první a jaká měna/DPH/doprava = k rozhodnutí
  Roberta až s návrhem od bot16.
  **OBJEDNÁVKY BEZ DEALERA (Robert 2026-10-02: „kdyby tam někdo něco objednal, spadne to na nás; jakmile se přihlásí zájemce o
  spolupráci, upravíme to"):** mini-shop může běžet bez dealera. Objednávka bez dealera je naše (dealer_id prázdné), zpracování jako
  každá jiná objednávka. Dealer a provize se napojí až po navázání spolupráce. Objednávky před přiřazením zůstávají naše, zpětná
  provize jen na Robertův pokyn. U objednávky musí být vidět doména a jazyk, odkud přišla. Objednávka se dokončí u nás (náš košík, prodejce Logiman, dealer provize nebo dealerská cena).
  **DOMÉNY (Robert 2026-10-02: „jen pokud dealer projeví zájem mít to na vlastní doméně, tak mu to uděláme, do té doby to bude na naší doméně"):** výchozí = NAŠE domény (jedna na jazyk, základní doména = náš shop bez dealera), dealer dostane vlastní subdoménu na naší doméně daného jazyka (host určuje storefront). VLASTNÍ doménu dealera děláme jen na jeho žádost: nový host ukazuje na tentýž storefront (alias), objednávky a přiřazení dealera se tím nemění.
  **MINI-WEBY NA TÉMATA (Robert 2026-10-02: „tak jak máme pro auta ty miniweby fiat.top, uděláme i na stoly, packstations nebo podobná formulace, a ve všech EU jazycích každá svou doménu, .top"):** vedle mini-webů aut vzniknou stejným způsobem mini-weby pro konfigurovatelné sestavy: pracovní stoly, packstationy (balicí stanice) a podobné (přesné pojmenování rodiny určí Robert), v každém evropském jazyce vlastní doména `.top`, bez značky Logiman. Návrh názvů domén po jazycích, kontrola dostupnosti, seznam jazyků a pořadí spuštění = bot7 (SEO/texty), mechanismus storefrontů a návrh mini-shopu = bot16, objednávky bot5. Do rozhodnutí o jazycích, měně, DPH a dopravě se objednávat nebude, jen poptávka.
  **ZAČÁTEK JEN ANGLICKY (Robert 2026-10-02: „na začátku schválíme jenom anglickou verzi, pak je budeme kopírovat"):** nejdřív vznikne a Robert schválí JEDNA anglická verze mini-webu, ostatní jazyky se z ní potom kopírují (překlad textů + vlastní doména .top). Šablona a překladové klíče tedy musí jít naklonovat do dalšího jazyka bez zásahu do kódu. Návrh domén a názvů dělat nejdřív pro angličtinu, ostatní jazyky až po schválení.
  **PORADÍ JAZYKŮ ZMĚNĚNO (Robert 2026-10-03: „může se udělat kompletní slovenská verze, anglickou uděláme jako druhou"):** PRVNÍ je KOMPLETNÍ SLOVENSKÁ verze mini-shopu (doména `baliace-stoly.top`, zaregistrovaná), anglická (`packing-tables.top`) je druhá. Slovensko = zahraničí: stůl jen rozložený bez montáže, měna EUR, ceny zatím skryté, jen poptávka. Texty SK píše bot7, jazykový soubor sk.json bot16, import a schvalování bot5. Anglické texty a EN verze zůstávají hotové, jen se nespouští první.
  **JEN FIRMÁM (Robert 2026-10-03: „vždy jen firmám"):** mini-shopy (SK, EN a další jazyky) prodávají VÝHRADNĚ podnikatelům (B2B), nikdy spotřebitelům. Dopad: poptávkový formulář vyžaduje firmu a IČO (u zahraničí i DIČ/IČ DPH), stránka a podmínky říkají „pouze pro podnikatele", odpadají spotřebitelská práva (14denní odstoupení, spotřebitelská reklamace), ceny bez DPH, u firem v EU s platným IČ DPH přenesená daňová povinnost (ověřit s účetní).
  **STAV 2026-10-02 (bot5): BACKEND ETAPY 1 HOTOVÝ A ŽIVÝ (nasazeno 12:30)**: klíče+atribuce, provize, měsíční vyúčtování (c429ec4b, e90baeb9, d3dbae48, testy `scripts/2026-10-02_dealeri_testy/`).
  **ODLOŽENO (Robert): objednávka přes API (cesta b, be6c760d, 8e39b6a3) a feed (7fef8924, 5d3a4b3a) - nenabízet, nerozvíjet, nemazat** (popis `DEALER_API.md`).
  **Pro dealerský e-shop na našich doménách (bot16 navrhuje stránku) čeká na rozhodnutí:** (1) cenový režim dealera: A = veřejná cena + provize % (hotovo), B = cena zákazníka =
  dealerská cena x (1 + přirážka dealera), zisk dealera = přirážka (vyplatí se ve vyúčtování); kdo přirážku nastavuje (admin/dealer v panelu); (2) dodací list a balík u e-shop objednávek (dnes neutrální
  jen u API cesty, e-shop = běžný s naší značkou); (3) kontext e-shopu na serveru (podepsaná cookie z vstupní cesty, ne parametr od zákazníka), cesta musí být existující proxovaný prefix (nginx se nemění).
  Moje část po rozhodnutí: serverový kontext dealera, JEDNA cenová funkce pro katalog/košík/objednávku/konfiguraci, snímek přirážky na objednávce, zisk dealera ve vyúčtování. Konfigurace (stoly, stojany, vozíky) čeká na bot10 (`compose`/`canonical_hash`/`price_for_selection`).
  **PŮVOD OBJEDNÁVKY + ALIASY HOSTŮ + PŘIŘAZENÍ MINI-SHOPU DEALEROVI (bot5, návrh schválil bot3): migrace JSOU V DB (a1f8c3a6, 321a434b), kód a test HOTOVÉ, NENASAZENO** - čeká na návrh e-shopu od bot16.
  Nasazení: `scripts/2026-10-02_dealeri_testy/nasazeni_puvod_objednavky/deploy_puvod_objednavky.sh` (README tamtéž: co je hotové, návrh zpětné provize a admin endpointů, nginx/TLS pro aliasy = infrastruktura Robert/bot14).
  **MINI-SHOP PACKSTATIONS - SERVEROVÉ API `/api/miniweb/*` + IMPORT A SCHVALOVÁNÍ TEXTŮ (bot5): NASAZENO NAŽIVO 2026-10-02 22:56** (commit 68b04808, Robertovo spuštění; sondy v pořádku: `/api/miniweb/*` 404 shop_not_found jako JSON, admin 401). Robert přes bot3 2026-10-02: **SLOVENSKÝ shop se spouští ŽIVĚ (baliace-stoly.top), nejdřív SK, EN druhá; prodej VŽDY JEN FIRMÁM; kontakt = údaje z `company_info` (jméno, adresa, telefon), e-mail nikde; žádný e-mail zákazníkovi.** SK katalog (B2B, bot7 b348a1bd) je naimportovaný jako DRAFT (čeká na schválení Robertem na `/miniweb-schvaleni.html`), SK shop je v DB jako KONCEPT (storefront 16 `packstations-sk`, EUR, SK, tyrkysová, kontakt z firmy).
  Nasazení: `scripts/2026-10-02_miniweb_testy/nasazeni/deploy_miniweb.sh` (`api/miniweb.py`, `api/miniweb_admin.py`, `webapp/miniweb-schvaleni.html`, importy v `app.py`, QA kontrola `miniweb_text_brand_leak`; na ostro při plánovaném nasazení); README tamtéž = kontrakt pro bot16. Poptávka jde jen do CRM, **potvrzení zákazníkovi e-mailem je VYPNUTÉ** (rozhodnutí Roberta přes bot3: společné SMTP odesílá jako "Logiman s.r.o." z Robertovy adresy, neutrální odesílatel až bude doména a schránka shopu), ceny se nevydávají, žádný živý e-mail na webu.
  Texty: bot7 dodá soubor JSON, `scripts/miniweb_import.py` ho nahraje jako draft (nahled, záloha), Robert schválí na `/miniweb-schvaleni.html` z mobilu; spuštění shopu (storefront `live`) je zvlášť.
  **SADA „PRAVNI“ (bot5, commit 89de57a8, NENASAZENO, čeká na Roberta: `! bash scripts/nasad_cekajici_bot5.sh`):** poptávka JEN FIRMÁM (`company`, `company_id` IČO, `b2b_confirm` povinné, `vat_id` DIČ nepovinné se syntaxí SK/CZ/EU, VIES = otevřený bod, země se u shopu s jedinou zemí doplní, údaje do CRM), právní dokumenty (tabulka `miniweb_documents` JE v DB; import klíčem `documents`, schválení Robertem na stejné stránce, výdej `legal.documents`; zástupné značky [DOPLNIŤ]/[OVERIŤ] blokují schválení i výdej, povolený je jen zákonný název prodejce), kontakt shopu z `company_info` (`use_company`), skript `scripts/miniweb_shop.py` (založení storefrontu jako koncept + řádek shopu, `--go-live` s podmínkami: nainstalovaný vhost domény, země, poptávky, schválený katalog, schválené terms/privacy/returns; `--take-offline`). README = kontrakt pro bot16/bot7: `scripts/2026-10-02_miniweb_pravni_testy/nasazeni/README.md`.
  **SK ke spuštění živě chybí:** právní texty po právníkovi (bot7 má návrh s [DOPLNIŤ], nesmí ven), nginx vhost domény (bot16: `scripts/miniweb_domena.py` + root krok `scripts/miniweb_nginx_install.sh baliace-stoly.top`), schválení textů Robertem, pak `scripts/miniweb_shop.py --slug packstations-sk --go-live --apply`. EN texty (druhé) naimportuji na pokyn bot3.
  **KONFIGURACE SESTAVY V KOŠÍKU A OBJEDNÁVCE (bot5, zelená bot3 2026-10-02): kód a testy HOTOVÉ (54 + regrese 63/69/62), NENASAZENO (2. spuštění v 22:25 utnulo odpojení Robertova terminálu těsně před commitem, vráceno do čistého stavu, skripty jsou teď odolné proti odpojení; spustí se znovu v jednom řádku s mini-shopem)** - čeká na PŘÍMÉ povolení Roberta (commit `api/cart.py`, `api/orders.py` = nasazení při 3:30/12:30). Žádné DDL (sloupce v DB).
  Server výběr vždy znovu ověří přes konfigurátor stolu (bot8), cenu počítá sám (skupinová sleva, montáž % jen v ČR, do zahraničí jen rozložený), řádek objednávky = výroba na zakázku (`product_id` NULL, žádný sklad) se snímkem (kusovník, kód STL-xxxxxx); zákazník kód+souhrn voleb, zaměstnanec vše.
  Nasazení: `scripts/nasad_cekajici_bot5.sh` (konfigurace + pravni po sobě, jeden řádek pro Roberta) nebo `scripts/2026-10-02_konfigurace_kosik_testy/nasazeni/deploy_konfigurace_kosik.sh`; README tamtéž = kontrakt pro bot16 (e-shopová karta). Další krok: nabídka z konfigurace po kontraktu od bot10/bot8.
  **Fáze 3 (objednávky, měna, DPH, doprava) zůstává ZAVŘENÁ do rozhodnutí Roberta** (zdroj cen v EUR = z Kč kurzem + marží v adminu, rozhodl Robert 2026-10-02; zbývá výše dopravy a DPH/VAT ID s účetní).
  **MINI-SHOP PACKSTATIONS - FRONT-END (bot16, 2026-10-02): kostra HOTOVÁ, staff náhled ŽIVÝ** (`/miniweb/index.html?shop=packstations&lang=en&demo=1`, jen přihlášený staff, noindex): úvod, strom kategorií, karta stolu s DEMO konfigurátorem a 3D, košík (objednávkový i poptávkový), kontakt, právní. Vše přes `miniweb/i18n/en.json`, bez značky; test 68/68 (desktop + mobil 390 px, fake odpovědi ve tvaru API od bot5). Kontrakt: `docs/KONTRAKT_MINISHOP.md`. Robert 2026-10-02: tyrkysový akcent, zatím bez domény (IP/staff náhled), dodání 2–3 týdny.
  **ČESKÁ VERZE ŽIVĚ (bot16, 2026-10-02 večer, Robert: první verze česky):** `/miniweb/index.html?shop=packstations&lang=cs&demo=1` (staff) s konfigurátorem stolu bot8 (karta 4934, `api/stul_shop.py`, nasazeno ručně #11 po Robertově kliknutí): jezdce rozměrů, příslušenství, cena v Kč bez DPH ze skutečného ceníku, 3D model z podepsaného odkazu, TAŽENÍ STŘEDNÍ NOHY v 3D (slot `mid`), poptávka jen jako náhled. Testy `scripts/2026-10-02_miniweb_frontend_testy/` (cs 27/27 nad skutečným API, en 70/70). Katalog/texty jsou ukázkové do nasazení API bot5 + textů bot7. Závislost na `window.__v3d.camera()` (ladicí hook) - bot10 požádán o oficiální API.
  Až bude API od bot5 nasazené, stránky se přepnou samy (config ze serveru; `?demo=1` zůstává jen pro staff). **Čeká na:** bot5 nasazení `/api/miniweb/*` + anglické texty/produkt (bot7, draft → schválení Robertem); bot10 konfigurátor (schema/resolve/model, `configurator.product_id`); **Robert: zdroj cen v EUR (DB má Kč) a výše dopravy** (bez toho zůstává poptávka, objednávka = fáze 3); anglické přihlašovací stránky; nginx/doména až s doménou.
  **MINI-SHOP SK - ADMIN + SEO (bot16, 2026-10-03):** admin záložka „Mini-shopy“ + panel „Doprava ke schválení“ + sloupec Původ ŽIVÉ. SEO v gitu (546de107, 2ba95ee7: `api/miniweb_seo.py`, hezké adresy, sitemap, robots, JSON-LD; testy `scripts/2026-10-03_miniweb_seo_testy/`), **ČEKÁ**: plánované nasazení api (12:30), pak Robert root: `bash scripts/miniweb_nginx_install.sh baliace-stoly.top --index sk` (skript sám odmítne, dokud API není nasazené). Zbývá: produkty v sitemap (API produktů zatím prázdné - bot5/bot7), og:image po renderu bez loga (bot4), `price_mode shown`/`checkout_mode order` po bot5, EN verze packing-tables.top, `nginx_cf_realip_install.sh` pro Roberta.


- **NALEZ (bot16, 2026-10-01): storefront domény servírují přímou cestou 13 stránek se značkou Logiman - bot3 to předává Robertovi k rozhodnutí, do té doby nginx NEMĚNIT (pokyn bot3 22:1x).**
  `location /` storefront vhostů servíruje celý `webapp/`, takže na `doblo.fiat-autovestavby.top` (a ostatních 6
  doménách) vrací 200 např. `/kontakt.html` (13 zmínek značky), `/index.html`, `/realizace.html`, `/404.html`,
  `/product.html`, `/category.html`, `/blok.html`, `/poptavka-stul.html`, `/moje-objednavky.html`,
  `/nabidka-online.html` a navíc `/admin.html`, `/kontrola.html`, `/capture.html` (curl 2026-10-01). Z mini-webů na
  ně nic neodkazuje, ale přímá URL značku prozradí = porušení TEXT_FILTR pravidla 5. Návrh: ve storefront vhostech
  povolit jen to, co mini-weby potřebují (formuláře přihlášení, `/css/`, `/js/`, `/content-files/`, `/api/`,
  `@storefront_ssr`) a ostatní `.html` vrátit 404 - stejně jako bot10 2026-10-01 u `/katalog/vandr/`. Je to změna
  nginx ve 7 vhostech, bez pokynu ji nedělám. Formuláře (login…) jsou od 2026-10-01 bez značky v HTML, takže ty
  zůstat smí.

- **OTÁZKA PRO ROBERTA (bot16, 2026-10-01): písmo webu na statických stránkách bez SSR.** `kontakt.html`,
  `realizace.html`, `poptavka-stul.html` a `404.html` nedostávají `--font-main` z volby písma, takže veškerý jejich
  text je v systémovém písmu (homepage je v Manrope). Logo jsem na nich srovnal (`6722ac2d`, natvrdo Manrope jen na
  logu, hlídá QA `static_page_font_stale`), zbytek textu jsem NEměnil. Chce-li Robert písmo i na text těch stránek:
  buď je převést na SSR (`site_font_ssr_head`, jako index/category/product), nebo stejné natvrdo jako
  `moje-objednavky.html`; SSR je lepší, protože sleduje volbu admina. Do rozhodnutí nic nedělat.

- **KOEFICIENT SCÉNY - popisky v administraci jsou NASAZENÉ (2026-10-01 17:17, běh #3 nasazení), zbývá úklid (bot16).**
  Robert 2026-10-01: *„koeficient pro scénu se týká jen profilů a produktů které se načítají z dogusu"*. Záložka
  Koeficienty cen ukazuje nový text, protože `GET /api/admin/settings` vrací `scene_price_coefficient_scope`
  (commit `4d3808cf`, backend bot8 `c77795b5`). Ověřeno: živé statické soubory nesou nový text a workery naběhly po
  commitu; v Robertově přihlášené relaci to nikdo neviděl. Úklid, až to Robert potvrdí (nebo při příští práci v
  `ceny.js`): smazat přechodový blok `SCENE_COEF_TEXTY_STARE` + `aplikujScenePriceCoefTexty` (i volání v
  `loadJointPrice` a podmínku v příkladu) - slouží jen jako záloha pro starší backend. Ostatní místa mají jiné
  vlastníky: popisky koeficientu Doguskalip u kategorií (admin.html ~3474 a ~6133) bot5 - HOTOVO `0532c032`, PLAN_TVORBY_SESTAV.md:1001 bot3.

- **⏸ ODLOŽENO (Robert 2026-09-30: *„zatím určitě nic nedělat"*) - NIKDO
  na tom nepracuje, dokud to Robert sám znovu neotevře (bot7):
  logiman.cz → autovestavby.logiman.cz propojení.** Připraveno 111řádkové CSV mapování
  starých URL logiman.cz (Shoptet) na nové kategorie, pro Shoptet
  Marketing > Základní SEO > Přesměrování adres (poslán soubor + rozbor
  27 nejasných případů). Robert zpochybnil smysl "jen přesměrovat"
  (`"k cemu to bude na shoptetu kdyz to bude kompletne smerovane na
  nas?"`) - otevřená otázka: zůstat u Shoptet-redirect jako zkušební
  krok, nebo jít rovnou na plné přestěhování domény (DNS primo na náš
  server, Shoptet vypnout)? Taky nezodpovězeno: používá se Shoptet ještě
  k něčemu jinému (fakturace/e-mail), co by bránilo ho vypnout hned?
  Detaily/CSV v chatu s Robertem, bot7 čeká na rozhodnutí než pokračuje.
  Samostatně čeká i: kam přesměrovat "Rámy strojů a zařízení" (žádný
  jasný cíl, patří k nedefinovanému "konstrukce strojů" z oboru 4).

- **ČEKÁ NA ROBERTA 2026-09-30 (bot7): potvrdit, jestli vidí záložku
  "Sociální sítě"** (Nastavení > Sociální sítě > Výchozí náhled při
  sdílení) - tam je editovatelný meta popis homepage. Robert napsal
  "nevidím ten metapopis k editaci", ale needal dál upřesnění (vidí
  záložku vůbec? jsou pole prázdná?). Kód prošel statickou kontrolou bez
  zjevné chyby, ale nešlo ověřit živě (bot nemá přihlášení do adminu).

- **ZBÝVÁ 2026-09-30 (bot4, zeď #20 „PODRUHÉ" - jednotné náhledy karet):** dlaždice kategorií a hover jsou HOTOVÉ
  (122 karet: jeden formát 1024², delší strana sestavy 83–85 %, rozptyl 2,1 p.b., 0 u hrany; popis v
  `PRODUKTOVE_RENDERY.md`). `api/turntable.py` (nové nativní karty) je NASAZENÝ (služba běží od 2026-10-01 09:34,
  commit z 30. 9. 23:23; v provozu neověřeno - až vznikne první nová nativní karta, zkontrolovat, že galerijní
  náhled je čtverec 1024²). ČEKÁ: (1) **storefrontové karty** (`api/car_storefronts.py`, 7 domén) berou surové
  kanonické snímky otočky - stejná oprava vyžaduje dlaždicové varianty v `_write_canonical` + výběr ve storefrontu
  + backfill canonical.json; (2) chybí hover u 25 karet (jednorázový skript z 27. 9.), nové karty ho nedostávají.
- **ROZPRACOVÁNO 2026-10-07 (bot4, Robertův pokyn): 2 rendery pro každý aktivní produkt BEZ obrázku.** 19 produktů (`scripts/2026-10-07_produkty_bez_obrazku.py seznam`):
  15 s `glb_file` ve frontě (30 renderů zařazeno jako držitel klíče `/root/.konfigurator_render_klic`, přes `turntable_render.py --nabidka-dily`, stav `backups/2026-10-07_produkty_bez_obrazku/joby.json`,
  výstup tamtéž `<id>_<pohled>.png`; pohled 1 = ČELNÍ (u plochých dílů kolmo na plochu, Robert), pohled 2 = 3/4 shora), 4 stoly z generátoru (#4934/4954/4955/5353) bez GLB - bot8 dodal GLB
  v `/tmp/stoly_glb_pro_bot4/` (jen 30/35/40; 45 chybí). ZBÝVÁ: `... sber` (sebrat hotové PNG do 1 h, než je uklidí), ukázat Robertovi 1 panel + 1 těleso (SendUserFile, pravidlo „otázka = obrázek“),
  po schválení NAHRÁT jako dlaždice 1024² (`_nahled_dlazdice.uloz_dlazdici`, www-data) do `content_gallery_items` + thumbnail + hover (`vestavby-hover-t1024v2`) - skript na nahrání ještě NENÍ napsán;
  `active` nikdy neměnit (p. 54). Vzorek `vzorek_puvodni/` (špatný pohled panelu) ignorovat.
- **ČEKÁ NA Robertovo první založení karty (tlačítko je hotové, čeká na nasazení API) → pak bot4: automat pro karty stolů z generátoru** (`STUL-S<systém>-<hash8>`, kontrakt bot8 (1)-(4) v handoveru): karty ještě neexistují (funkce „Založit kartu z konfigurace“ čeká na Robertovo schválení); až bot8 pošle první ID + `scripts/stul_karta_glb.py`, postavit automat jako Vandr větev (výchozí VYPNUTO).
- **HOTOVO 2026-10-06 (20302409), ŽIVÉ PO NASAZENÍ 07.10. 00:00 - ověřit na nové nabídce z karty (bot5) / `kontrola.html?items=vd:4965&rezim=nabidka`:** razítka loga v 3D modelu ONLINE NABÍDKY (popis `docs/KONTRAKT_NABIDKA_3D.md` 5h; původní zadání níže, od bot10 po Robertovi) (nabídky #116/#117 je
  nemají; Robertovo pravidlo 2026-09-06: razítkování = stupeň 2 = model v nabídce). Data hotová: `shop_products.vandr_razitka_json`
  (18 záznamů). Vkládat do `scripts/v3d/vandr_offer_build.py` (Blender CPU) PŘED slučováním `_sluc()`, přiřadit skupině/pivotu podle
  AABB profilu pod razítkem, převod souřadnic `_three_to_blender_matrix`; sanitizér `api/v3d_glb.py` odmítá jména logo|vandr|… →
  neutrální jména r1…, barva z `razitkovac.LOGO_BARVA_HEX`; cache `private-files/v3d-cache` (0600 www-data) - klíč s otiskem razítek
  + verze buildu; testy `scripts/2026-10-02_v3d_testy/` (V3D_TEST_REPO), ověřit jako www-data; vizuálně
  `kontrola.html?items=vd:4965&rezim=nabidka`. Soubory `api/vandr_scene_offers.py`, `scripts/v3d/*` jsou nově moje (bot10 už nepracuje).
- **NASAZENO 2026-10-01 23:02 + klient, ČEKÁ NA OVĚŘENÍ ROBERTEM (bot4, render): obrázky online nabídky = vzhled jako karty**
  (Robert: „propojit“, „stejné pozadí jako automat na karty“, „materiály stejně jako na Vandru“). Rendery nabídky a „Test
  renderů“ jdou kartovou cestou (šablona X30-02, pozadí, HDRI, materiály z panelu), při jakémkoli selhání sám stará cesta;
  popis a omezení v `PRODUKTOVE_RENDERY.md` („Online nabídka = stejná cesta jako karty“). Ověřit: ve scéně Ctrl+F5, „Test
  renderů“ → v okně „vzhled jako u karet“ + vzhled proti kartě. **Materiály katalogu po dílech = bot10** (`render_materialy`,
  DDL přes Roberta): zapojí se do `resolve_parts`, export GLB ve scéně se nemění. Neověřeno: první skutečný GPU render.
  **Dohoda bot4↔bot10 (2026-10-02):** `resolve_parts` přidá k dílu `render_material: {"nazev","knihovna"}` | None
  (funkce `render_material_pro_dil` v `_render_prirazeni_lib.py`, flag vypnutý, do Robertova DDL + odsouhlasení sporných
  skupin se nic nemění; knihovny cub_seda/bila na Sdíleném disku zatím NEEXISTUJÍ → None). **bot4 dluží Blender stranu**:
  `blender_render_turntable.py::_material_for` přečte pole a vezme materiál z knihovny (sloučené s `--vd-knihovna`) + test -
  až bot10 pošle pole/diff. Dnešní stůl z DB: laminodeska = hliník (layer alu), MDF/plast metal 0.35 (rozbor 2026-10-02).
  **Stav 2026-10-02:** pole `render_material` v `resolve_parts` je (None, flag vypnutý), knihovny cub_seda/bila nahrané (Sdílený disk
  složka 45). Při psaní Blender strany: (1) kolize jmen - existuje-li v bpy.data už `CUB seda` (jediný Vandr GLB), načte se knihovní
  jako `CUB seda.001` a `materials.get` tiše vrátí nativní → pro `render_material` načíst knihovnu PŘED importem GLB nebo brát
  knihovní variantu; (2) nález bot10: Vandr baseColorFactor je gamma (Unity m_ActiveColorSpace 0), Blender čte lineárně → šedý plast
  může být světlejší (~208 místo 150-170), vizuálně neověřeno - posoudit na renderu, nic neměnit bez Roberta.
- **ČEKÁ NA ROBERTA 2026-10-01 (bot4, render): nabídky a testy ze scény na Omen.** Hotovo a commitnuto
  (`4e0c3811`, `daa54de5`; `PRODUKTOVE_RENDERY.md` „Rendery nabídek a testů ze scény → Omen"): scéna u
  „📄🖼 + rendery" a testovacích renderů posílá `ucel: "nabidka"`, server pošle render na Omen, je-li online
  (Blender ≥ 5.2) a volný, jinak na Logiman2 jako dosud (nikdy nevisí); Omen je **vyhrazený** (automat ho
  nepoužívá, jinak by nabídka čekala za otočkou). Server (`api/*.py`) se nasadí SÁM 02.10. ve 3:30
  (`scripts/restart_konfigurator.sh --stav`; dřív jen domluvou s bot3/Robertem, bot sám nerestartuje); web
  (scéna, panel) je živý už teď. Zbývá na tobě: (1) nic k restartu; (2) na notebooku spustit agenta - nový `SPUSTIT_AGENTA_NOTEBOOK.bat` ze Sdíleného disku „Renderovací agent
  (PC GPU)" (nebo ho nainstalovat jako službu stejným `NAINSTALOVAT_SLUZBU.bat` jako Logiman2 → startuje sám,
  bez okna); (3) na PC s černým oknem „RenderAgent" okno zavřít a pustit `ODINSTALOVAT_PROTOKOL.bat` (odebere
  starý odkaz `logimanrender://`); (4) rozhodnutí: nechat Omen vyhrazený pro nabídky (nastaveno), nebo ať ho
  automat využívá i mimo nabídky (přepínač do panelu doplním). Pak bot4 ověří první nabídkový render
  (v okně „⚡ Omen (GPU)"; výsledek dorazí). První automatová otočka na Omenu platí jen, kdyby se vyhrazení zrušilo
  (notebook dosud NIKDY neběžel celou otočku). Rozhodnuto „ne" (neptat se znovu): zápis modré do
  `modrecelo.blend`, přerender karty 4911.
- **ČEKÁ NA ROBERTA 2026-09-30 (bot4): časovač „dohrání archivu otoček Vandr" zapnout nebo ne.**
  Nález (zeď #18): archiv `vanDrawee sestavy/<id> - <název>/` na Sdíleném disku se zapisuje jen při
  commitu dávky, kdy je Vandr karta ještě neaktivní → u nových karet se nikdy nespustil (72 ze 110
  aktivních karet bez složky). Jednorázově dohráno (72 karet × 27 snímků + manifest, vlastník `www-data`).
  Aby to platilo i pro budoucí karty, je připraven automat `scripts/2026-09-30_vandr_archiv_dohnat.py` +
  `deploy/konfigurator-vandr-archiv-dohnat.{service,timer}` (po 15 min, `www-data`, idempotentní, jen
  přidává). Časovač je nainstalovaný, ale VYPNUTÝ, soubory necommitnuté (bezpečnostní filtr commit
  zablokoval jako „persistence", bez tvého ano to nedokončuju). Zapnout: `sudo systemctl enable --now
  konfigurator-vandr-archiv-dohnat.timer`; commit: `cd /opt/konfigurator && BOT_ID=bot4 git add
  scripts/2026-09-30_vandr_archiv_dohnat.py deploy/konfigurator-vandr-archiv-dohnat.service
  deploy/konfigurator-vandr-archiv-dohnat.timer && BOT_ID=bot4 git commit -m "feat(vandr): automat
  dohrava archiv otocek" -- scripts/2026-09-30_vandr_archiv_dohnat.py
  deploy/konfigurator-vandr-archiv-dohnat.service deploy/konfigurator-vandr-archiv-dohnat.timer`.
  Průběžné ukládání snímků BĚHEM renderu pro Vandr se nedělá (vyžaduje změnu pravidla „archivuje se jen
  aktivní karta" + zásah do horkého `render_worker_tt_frame` + restart) - jen pokud to Robert chce.
- **ČEKÁ NA ROBERTA 2026-09-30 (bot4, render): 2 věci.** (1) Zatrhnout fajku
  „světla ze souboru" v panelu Rendering → HDRi (Robert „ano"; panel se uloží
  jedním klikem, bot to zapsat nesmí - pravidlo 50) → pak bot4 zkontroluje
  první automatovou dávku se 2 světly. (2) Model id 672 (1d2bd83b) ve Vandru:
  kliknout znovu Export, FBX fyzicky chybí, bez něj watcher kartu nezaloží.
  K tomu karta 4004 (razítka „predni 0/2", bot_ukoly #19): odkaz do kontrolní
  scény předán Robertovi, čeká na jeho rozhodnutí, `active` se nemění
  (pravidlo 54). Mechanismus panelu: `PRODUKTOVE_RENDERY.md` („Panel Rendering → HDRi").

- **ČEKÁ NA ROBERTA 2026-09-30: název nových Vandr karet bez prefixu
  "Regálová vestavba – ".** Karty založené v posledních dnech (VW Crafter
  L3H3 FWD id 4917-4923, Ford Transit, Fiat Ducato) mají holý název bez
  prefixu, starší sourozenci (stejné auto, starší datum) ho mají. Netuší
  se, jestli je to záměrná změna konvence, nebo regrese v
  `2026-09-22_vandr_fbx_watcher.py`/`card_auto_link.py`. Nedělat nic, dokud
  Robert neřekne, který stav je správný.

- **K ODKLIKNUTÍ ROBERTEM 2026-10-01 (bot5): adresy produktů (SEO) se tvoří strojově.** Mechanismus je
  hotový a NASAZENÝ (`a0fa46c2`: `api/product_slug.py`, `POST /api/shop/products/normalize-slugs`, QA `product_slug_not_from_name`;
  backend běží od 12:30, ověřeno 1. 10. po 17:00: POST bez přihlášení → 401). Tlačítko „Sjednotit adresy (SEO)“ v Produktech
  (vedle Export/Import CSV) funguje: Robert klikne, nejdřív NÁHLED (108 veřejných produktů, z toho 92 s interním názvem
  dodavatele v adrese), po potvrzení se adresy přepíšou z názvu a staré se přesměrují (301). Ověření bez zápisu:
  `curl -s -o /dev/null -w "%{http_code}" -X POST https://autovestavby.logiman.cz/api/shop/products/normalize-slugs`
  → 401/403 (ne 404). Pravidlo pro skripty zakládající karty: `product_slug.slug_for_name(cur, name)`, ne vlastní
  slugify (pravidlo zapíše bot9 přes Robertovo potvrzení). Kategorie a stránky stejný mechanismus zatím nemají
  (SEO/bot7). Po odkliku řádek smazat.

- **ČEKÁ NA ROBERTA 2026-10-01 (bot5): PR10 převést na cenu za 1 m².** Karta vede desku jen za 1 m² (commit `ebeaf46a`,
  živé, přepínač „za tabuli“ zrušen). Laminodeska 3671 je HOTOVÁ (Robert zadal 1 400 Kč/m² = 8 114,40 Kč za tabuli
  2070×2800, ověřeno 1. 10.). Zbývá PR10 (3539, v DB stále cena za tabuli 3 093,75 Kč = 990 Kč/m²): Robert ji převede
  tlačítkem „Převést na cenu za 1 m²“ v kartě. Hlídá to QA `board_price_not_per_m2` (v dashboardu, nasazeno).
  Po převodu PR10 řádek smazat.

- **K ODKLIKNUTÍ ROBERTEM 2026-10-01 (bot5): duplikace produktů.** Backend je po restartu (00:27) nasazený
  (routa `POST /api/shop/products/<id>/duplicate` odpovídá 401 místo dřívějších 404, dohlédnuto bot5),
  stejně tak validace názvu/SKU při úpravě karty a QA kontrola `product_duplicate_unclassified_table`.
  V adminu ⋮ → „Duplikovat“ v seznamu produktů nebo tlačítko v hlavičce karty: vznikne NEAKTIVNÍ kopie
  (kopii bot nemaže, nechat na Robertovi). Po jeho odkliku řádek smazat.

- **ONLINE NABÍDKA: montáž zatržením u KAŽDÉ nabídky + RUČNÍ POLOŽKY (bot8, zadal Robert 2026-10-06: „zatrhávací službu montáž (a kde Praha / Slavičín)“, „admin připíše ručně položku z katalogu včetně 3D modelu, parametrů a ceny“, „ručně jen volný text s načtením obrázku (1–2 ks) a ceny“): HOTOVO A ŽIVÉ (API obnoveno 2026-10-06 22:52; testy na HEADu 79/7/59/19 zelené).**
  (1) Montáž (od 22:46 zúžil bot5, `22dc0d52`: jen sestavy do aut, vylučuje dopravu; stránka po bot5): zákazník u každé nabídky zatrhne Montáž + místo (Praha / Slavičín); cena = % z ceny zboží (`offer_options.montaz_pct`, jinak výchozí z nastavení, `_offer_montaz_net`), promítá se do součtu, QR, poznámky v objednávce a e-mailu (commit `db12872e`). Stránka volbu ukáže jen
  když backend nese `montaz_volba`. **Tím je vyřešená dřívější otázka bota5 (montáž do ceny, nebo tlačítka) - Robert odpověděl „zatrhávací službu“; sazba v % z 2026-10-02 platí dál (nabídka / nastavení).**
  (2)+(3) Ruční položky: v adminu „Upravit nabídku“ editor pod tabulkou (z katalogu s hledáním a 3D modelem / volný text s 1–2 obrázky; cena, množství, popis); jdou na konec kusovníku, zákazník je vidí v tabulce a v kartách „Doplňující položky“,
  do objednávky jdou jako běžné řádky. Admin editor se ukáže jen když `edit-data` nese `rucni_polozky` (statika je živá dřív než API). Kontrakt `docs/KONTRAKT_NABIDKA_RUCNI_POLOZKY.md`, testy `scripts/2026-10-06_nabidka_montaz_polozky_testy/README.md`.
  **Robert ověří po nasazení:** u nabídky Upravit → přidat položku z katalogu i volný text s obrázkem → otevřít zákaznickou stránku. Po ověření řádek smazat.

- **GENERÁTORY STOLU: záslepky na VOLNÉ KONCE profilů + razítka loga v modelu nabídky (bot8, zadal Robert 2026-10-06: „v generátorech … na volné konce profilů se musí automaticky dávat záslepky“, doplnil „jsou to zatím jen profily na rampě pro LED“; razítka přes bot5 / bot9): HOTOVO A ŽIVÉ (API obnoveno 2026-10-06 22:52); razítka v nabídce zapíná bot5.**
  (1) Záslepky: generátor (`_volne_konce`, klíč dílu `("zasl", profil, "+"/"-")`) dá záslepku systému (3071 / 3090 / 3091) na každý konec profilu, kterého se nic nedotýká – dnes 4 ks na rampě LED (konce ramen nad zadními stojkami, oba konce příčky nad LED; bez LED horní konce zadních noh), další volné konce samy. Přibývají kusy v kusovníku a cena → `RULES_VERSION 2026-10-06.1` (nové kódy STL-xxxxxx); vnější rozměry stolu beze změny, živé tažení v pořádku (záslepky jedou s profilem).
  (2) Razítka: `stul_shop.glb_bytes(selection, system, razitka=True)` → `api/stul_razitka.py` (pravidla razítkovače sestav: každý 3. profil na každé exponované stěně, výplň drážky, oranžové logo jako instance jednoho meshe, +0,5 MB, projde `v3d_glb.sanitize` + `final_check`); veřejný generátor a košík beze změny; **zapnout v `nabidka_z_konfigurace._zakaznicky_glb` má bot5** (písu mu po commitu).
  Doc `docs/STUL_ZASLEPKY_A_RAZITKA.md`, testy `scripts/2026-10-06_zaslepky_konce/` a `scripts/2026-10-06_razitka_stolu/` (+ `mutace.py`), `run_all.sh` kroky 41–42; ostatní testy sady upraveny (počty dílů bez záslepek, kotvy hashů).
  Robert po nasazení: na rampě LED v generátoru jsou černé záslepky; razítka po zapnutí u bot5 na nabídce ze stolu. Po ověření řádek smazat.
- **VANDR MODEL VE SCÉNĚ A V KAROSERII (bot8, Robert 2026-10-06/07: „VD-2c24d107… tuto sestavu potřebuji vložit do scény a do karoserie MAN L3H3“ → hlavní scéna, celý model): HOTOVO.** Panel „▸ Vandr model“ ve Scéně + odkaz „Do scény…“ na Vandr kartě (`/scene.html?vandr=<id>&karoserie=K-227`): celý Vandr GLB jako kontrolní pomůcka v karoserii z knihovny (mimo kusovník, cenu a uložení), zarovnání otočením o 180° + podlaha + přepážka; K-227 + levý regál #4967 bez kolize, 271 mm od přepážky; ponk #4969 jde stejně. Dokument `docs/VANDR_MODEL_VE_SCENE.md`, test `scripts/2026-10-07_vandr_ref_testy/test_vandr_ref.js` 19/19. **Robert ověří:** otevřít [Scénu s regálem #4967 v MAN L3H3](https://autovestavby.logiman.cz/scene.html?vandr=4967&karoserie=K-227), pak v panelu přidat ponk (4969). Po ověření řádek smazat.
- **VANDR KARTA #4969 „Přepážka s ponkem a výsuvným svěrákem – MAN TGE L3H3“ (bot8, Robert 2026-10-06: „přidej tento stůl do auta, ke karoserii MAN L3H3 na přepážku jako nová karta … pokračuj s tím stejně, jako bych to vyexportoval z Vandr systému“): ZALOŽENA, NEAKTIVNÍ, razítka hotová, render běží (automat).** FBX mimo Vandr admin → nástroj `scripts/2026-10-06_vandr_cizi_fbx_na_kartu.py` (viz `VANDR_RENDER_HOWTO.md`, sekce „FBX MIMO Vandr admin“); GLB `vandr/vd_export_prepazka_…_9494dabe.glb`, štítek RK, přední azimut 180°. **Čeká na Roberta / bot7 / bot5:** cena (karta neaktivní, aktivuje automat po ceně + renderu) a **kategorie** (MAN není v mapování značek `ZNACKA_ID_TO_CATEGORY`; MAN TGE = dvojče VW Crafter - patří pod 302, nebo nová MAN kategorie?); úkol na zeď bot5 zapsán. Neřešeno, dokud Robert neřekne: FWD/RWD (K-227 / K-228) se nerozlišuje, 2D kótovaný výkres (u Vandr karet se jen přejímá, tady žádný není), sestava na přepážce karoserie ve scéně. Po ověření řádek smazat.
- **VÝKRESY S KÓTAMI V NABÍDCE ZE STOLU (bot5 → bot8, 2026-10-06, Robert: „v online nabídce z generátoru chybí 2D kótovací systém“): HOTOVO ve scéně (bot8), čeká na bot16 (otevřít scénu v nové záložce po vytvoření nabídky) a ostré ověření.** Endpoint bot5 (`aefcbff5`) i API jsou živé od 22:52. Režim `scene.html?stul=<query>&nabidka_vykresy=<offer_id>` (query = `vyrobni_list_url`, offer_id z odpovědi vytvoření): scéna vloží stůl a bez kliků vyrobí `narys` (čelo stolu) / `bokorys` / `pudorys` s kótami + `view3d_a` / `view3d_b`, pošle na endpoint (staff cookie, 24 h od vytvoření nabídky) a ukáže „Výkresy uloženy“. Popis, pravidla a testy: `docs/NABIDKA_VYKRESY_ZE_STOLU.md`.

- **ČEKÁ NA ROBERTA (nespěchá, bot7): 2 drobnosti z Vandr kategorizace
  300-310** (viz AGENTS_LOG 2026-09-30, kategorizace samotná je HOTOVÁ a
  potvrzená bot8 jako správná, žádná kategorie nemíchá generace):
  (1) kategorie "Fiat Ducato" (300) obsahuje i Peugeot Boxer produkty
  (sdílená platforma) - přejmenovat/rozdělit, nebo nechat? (2) "Ford
  Custom" (293, 5 produktů) - Vandr interně značí "L1H1 3300mm", naše
  karoserie_model_reference řadí 3300mm pod "L2H1". Robert potvrdil
  přímo, že rozvor (číslo v mm) z Vandru je spolehlivý ("máte špatné
  informace" když jsme o tom pochybovali) - jde tedy jen o to, jestli
  přeznačit produkty na "L2H1", nebo Vandr má vlastní L-konvenci a nechat
  beze změny. NENÍ to úkol pro bot7 dál sám aktivně řešit (doména bot8 -
  karoserie referenční data), jen čeká na Robertovo ano/ne.

- **⛔ ČEKÁ NA ROBERTA 2026-09-23 (bot8): pravidlo „30 mm nad euroboxem" je pro
  varianty 05/06/07 ŠPATNĚ — a já podle něj sáhl na schválenou sestavu.**
  Změřeno nad 54 schválenými sestavami: pravidlo porušuje #548 (vzor var. 06,
  gap 12 mm) a #550 měla původně také 12 mm — Robert tedy schválil 12 mm
  dvakrát. 30 mm je pravidlo pásmové konstrukce 01-04, ne rámu nad úhelníky.
  **Dvě rozhodnutí:** (a) vrátit generátorům `2026-09-17_horni_blok_var05.js`/
  `_var06.js` původní kotvení `yDol = uhelnik+5` (moje změna z 21. 9. je proti
  schválené realitě); (b) vrátit **#550** do schváleného stavu ze zálohy
  `backups/2026-09-21_horni_blok_30mm_pred_opravou.json`. Do sestav jsem
  nesahal — čeká se. Pozor: původní ZÁPORNÉ mezery (až −76 mm) vadné byly,
  správná mez ale není 30 mm, nýbrž „nesmí zasahovat do boxu".

- **HOTOVO/K TŘÍDĚNÍ 2026-09-23 (bot8): konfrontace všech receptů se schválenými
  sestavami — 57 rozporů ze 164 tvrzení.** Výsledek uložen v
  `backups/2026-09-23_pravidla_vs_schvalene/` (`ROZPORY.md` = čitelný přehled,
  `vysledek_workflow.json` = plný výstup). Měřeno nad 54 schválenými sestavami,
  6 061 dílů. Rozpory v 16 receptech, nejvíc v `#3 ukladani-euroboxu-do-luzek`
  a `#10 razitkovani-profilu-ochranne-logo`.
  ⚠️ **57 rozporů NENÍ 57 chybných pravidel** — nejdřív roztřídit na (a) pravidlo
  má špatná čísla (např. „čisté šířky 430/832/**1232**" — 1232 se nepostavilo ani
  jednou, všech 33 tříboxových sloupců má **1224**; „hloubka nohy D=326" platí jen
  pro Jumpy/Caddy, Ford/Doblo/Vito/Proace mají **349**, 25 schválených sestav) a
  (b) pravidlo popisuje nenasazený záměr (celé `#10` „porušuje" 54/54 jen proto,
  že razítka zatím nikde nejsou). Část potřebuje Robertovo rozhodnutí — např.
  který ze čtyř naměřených vzorů rozteče příčných spojnic u 1224mm sloupce platí.
  **Zatím neopraveno žádné pravidlo.**

- **ČEKÁ NA ROBERTOVO ROZHODNUTÍ 2026-09-21 (bot8): 7 sestav má dva horní
  bloky naráz** (#662–#668, kód 06) — rám varianty 06 leží POD pásmem „01"
  a pod vrchem nejvyššího euroboxu (#664: box 951,5 / rám 875,5 / pásmo
  992,5 mm). Mechanický posun to neřeší, je to konstrukční střet: kam má rám
  06 jít, když v tom prostoru už je pásmo 01? Souvisí s dřívějším blokátorem
  „var07 koliduje s konstrukcí 01 pásmo" (13 rodin, `AGENTS_LOG.md`
  2026-09-19). Nezkoušeno obcházet. Všech 7 má `resi_se_at` nastavené,
  jsou tedy ve scéně nahoře ve skupině „🔧 Aktuálně řešíme".

- **ČEKÁ NA ROBERTA 2026-09-21 (bot8): #548 a #560 mají 20 kolizí regálu se
  stěnou karoserie** — vada JE STARŠÍ než dnešní oprava a netýká se horního
  bloku (kolidují role `spojnice`/`nosnik`/`eurobox`/`uhelnik`). Není to
  vlastnost karoserie: 14 jiných sestav na téže CI25 je čistých. **#548 je
  přitom `technicky_ok=1` a slouží jako vzor kódu 06** v číselníku
  `horni_blok_varianty`, takže schválený vzor má regál zanořený do auta.
  Odškrtnout `technicky_ok` sám nesmím (pravidlo 44). Obě mají
  `resi_se_at` nastavené, jsou tedy ve scéně nahoře.

- **DROBNOST 2026-09-21 (bot8): číselník `horni_blok_varianty` má mrtvé
  odkazy** — `sestava_vzoru` u kódů 02/03/04 ukazuje na sestavy #335/336/337,
  které jsou smazané. Funkční ekvivalenty jsou #343/345/347 (Doblo K-075 C),
  ale zapsané nejsou.

- **ČEKÁ NA ROBERTŮV TEST (bot8, 2026-10-01): univerzální import objektu
  (FBX → rozpojená skladba dílů → Vlastní tvar)** - panel „Import objektu (FBX)"
  ve scéně (`webapp/js/scene/universal-import.js`, `api/universal_import.py`).
  Díly zůstávají na místě, ruční mapování na katalog, nové díly jako neaktivní
  karty `<kód>.DIL-NNN`, spoje profil-profil předpočítané, import nemaže scénu.
  Postup, pasti, invarianty: skill `import-fbx-scena`, `TVARY_VLASTNI.md` 2xx.
  - **Robertův první build stolu (2026-09-30, tvary #573/#574) se rozletěl** -
    OPRAVENO commity `9ee23b1c` … `6643ae0b` (6 commitů, 5 kol adversariální
    kontroly, 13+15+10+7+4 nálezů, vše s testem): sestavení u existujících karet počítalo
    s vycentrovaným GLB v osách scény, karty nahrané přes admin FBX ale leží na
    souřadnicích z Rhina. Nově umístění z geometrie/povrchu GLB karty (vč.
    transformací uzlů), desky dopočítané do rozměru dílu v libovolném
    natočení, profily natočené podle průřezu, výrobek rozdělený v FBX vložen
    jednou, karta bez modelu = chyba, skupina ×N v panelu přiřadí všechny.
    Test `scripts/2026-10-01_universal_import_umisteni_test.py` (151 kontrol)
    + harness 22. QA kontrola `flung_shape_part` (`8b456bfe`) hlásí #573/#574.
    **Vyřízeno 2026-10-01:** Robert stůl přestavěl jako tvar #576 (11:06, 72 dílů,
    desky 4933 přesně 800×1200 a 650×1200); staré tvary #573/#574 jsou smazané;
    karta 4933 je deskový materiál (m², 1 200 Kč/m²) a má stejnou barvu jako 3671
    (`#a5a5a5`, nastavil bot8 na Robertův pokyn, záloha
    `backups/2026-10-01_laminodeska_barva/`). Zbývá jen Robertův test v prohlížeči
    (cena/kusovník tvaru #576, Krok zpět).
  - **Rozpracováno:** hermetický selftest backendu
    `scripts/2026-09-30_universal_import_selftest.py` - hotové části 1-2
    (izolace prostředí + striktní FakeDB), chybí fixtures, syntetická scéna a
    testy; detailní plán je v DB handoveru bota8 („STAV bot8 k 2026-09-30").

- **lic_peers vlastních tvarů podle definice spoje (bot8, 2026-10-02):** nález bot10 (scéna po
  načtení víc spojů než geometrie). **Rozhodnuto podle definice** (Robert 2026-08-31,
  `PRAVIDLA_SPOJU.md`): `lic_peers` měly páry s dotykem jen HRANOU, generoval je
  `dimension_match_fbx._profiles_touch` (opraveno `b6bfd27f`, test + QA kontrola
  `lic_peers_neni_spoj`). **HOTOVO** (bot3 schválil): #577 a #572 −6 párů (26 spojů, −660 Kč
  v souhrnu scény), záloha `backups/2026-10-02_lic_peers_definice_spoje/`, audit_log.
  - **OTEVŘENÉ - rozhodne Robert:** tvar **#524 „Regal 40A01 Doblo“** (postavil ho Robert ručně
    ve scéně 2026-08-23, ne import) má 18 nevyhovujících párů (53 → 35 spojů, −1 980 Kč v
    souhrnu): 14 dotyků hranou (volnější detekce dotyku ve scéně před opravou 2026-08-31) a 4
    páry s dílem #14 (`#0↔#14, #2↔#14, #4↔#14, #5↔#14` - díly 269-1227 mm od sebe, zastaralé).
    Neměnit bez Roberta (ručně umístěná referenční geometrie); `--shapes=524` ve skriptu
    `scripts/2026-10-02_bot8_lic_peers_definice_spoje.py` je připravené.
  - **OTEVŘENÝ NÁLEZ k rozhodnutí Roberta (žádný kód): sestava #503** (K-289-RL-EB-30): 4 příčky
    (#33-#36, 289 mm) leží vůči noze #32 posunuté o 20,7 mm (překryv čela 9,3 z 30 mm =
    částečně kryté čelo, porušení nadřazeného pravidla). Uložených 87 spojů vs 88 podle definice,
    cena sedí - jde o geometrii. #374 (8 zastaralých párů v `lic_peers`, cena sedí) neřešit.

- **KONFIGURÁTOR STOLU #577 - NÁVRH (bot8, 2026-10-02, čeká na Robertovo schválení rozsahu):** Robert potvrdil
  pilot = custom_shapes **#577** „Stul system 30 SP002“ (statický snímek jako sestavu NEUKLÁDAT - bude parametrická).
  Zadání: FIXNÍ jsou perforovaný panel (2× 1190×460), šuplíkový box (565×594×280), LED 1,2 m; MĚNIT jde šířka a hloubka
  desky, výška pracovní desky, spodní police ano/ne, ostatní příslušenství zap/vyp (panely, šuplíky, LED, elektrožlab, držák
  PET, kolečka); profily se přepočítají samy, celkové rozměry živě; ovládání v duchu „pohybovače komponent“ bot10 u Vandr
  sestav (zdroj návrhu bot10 neznám - dotaz poslán). Odvozeno z #577: příčky rámu = rozteč nohou − 30; přední nohy = výška
  desky − 120 (kolečka 101), zadní = přední + 1073 (panely+LED); police drží výšku 330 od podlahy, deska police = hloubka − 150;
  2 střední příčky pod deskou jedou s šuplíkovým boxem. **Past:** model šuplíkového boxu (`product_4930.glb`) má podle tvaru
  vysunutý šuplík (~50 cm před stůl) - pro konfigurátor potřeba zavřená poloha. Architektura: JEDNA serverová funkce
  „pravidla stolu“ (díly + kusovník + cena), zlatý test = výchozí hodnoty dají přesně #577, matice kombinací projde QA
  kontroly spojů/zanoření/kolizí. Etapy: 1 pravidla+test (bot8) → 2 panel ve scéně pro Roberta (bot8) → 3 cena/košík
  (bot5) → 4 zákaznický prohlížeč (bot10/bot16).
  **ROZHODNUTO 2026-10-02 (Robert, klikací volby):** šířka 500–3000, výška pracovní desky 140–1200; nad 1500 mm šířky
  přibývá střední noha vpředu I vzadu, posunovatelná blíž k levé/pravé noze; panely a LED se přidávají podle šířky (ne jeden
  posunovatelný kus); šuplík zavřít zkusí bot8. **Šuplík:** kandidát `backups/2026-10-02_suplik_4930/product_4930_zavreny_kandidat.glb`
  (vysunutý šuplík = 98 samostatných komponent, posun +513 mm v lokálním Y, čelo v rovině čela druhého šuplíku; topologie i ostatní
  vrcholy beze změny, 0 průniků s tělem boxu; originál zálohován vedle). Katalogový `webapp/katalog/product_4930.glb` zatím NEPŘEPSÁN
  (slíbeno: jen po Robertově schválení; používá ho jen #577; v gitu soubor není). Robert: „kdyby to dělalo problém, nakreslím šuplíky
  znovu jednodušeji." **Hloubka (Robert 2026-10-02): 400–1500; nad 900 mm se do KAŽDÉ bočnice přidá profil doprostřed mezi přední a zadní nohu
  a mezi obě příčky** (výklad bot8: svislý profil uprostřed hloubky mezi horní a spodní podélnou příčkou bočnice, tj. 2 nové profily,
  každý se 2 T-spoji + spojkami; u police-less stolu viz otevřená otázka). Box potřebuje hloubku ≥ ~640 (zavřený 583 + panel).
  **Otevřeno:** bez police a hloubka > 900 (spodní příčky bočnic zůstanou, nebo profil jde až na podlahu?); max. formát lamina při šířce nad ~2,8 m (dvě desky?); co s panely/LED při šířce
  pod 1200 mm (nevejdou se); sjednotit s receptem/compose() bot10 (bot3: server skládá GLB, kanonický hash, deklarativní recept -
  v repu ani DB ho nevidím, čekám na bot10).
  **STAV 2026-10-02 večer (bot8, Robert: „nečekej na žádný recept, vytvoř ho“):** recept HOTOV jako kód - `api/stul_konfigurator.py`
  (`sestav_stul(**parametry)`, zmrazená šablona `api/stul_sablona_577.json`; commit 8007ce94), zlatý test = výchozí hodnoty dají přesně #577;
  testy `scripts/2026-10-02_stul_testy/run_all.sh` (generátor 16 413 kontrol, z toho napojení 864 konfigurací NEZÁVISLE ověřeno kódem
  projektu `dimension_match_fbx` + QA `lic_peers_neni_spoj`; API 21; panel ve scéně 12, mutace chyceny). Hotové: rozsah 500–3000 /
  400–1500 / 140–1200, střední nohy nad 1500, profil doprostřed bočnic nad 900, panely+LED podle šířky, spínače, závislosti, kontrola
  napojení (každý konec profilu, který v #577 dosedal, musí dosedat; spojky na uzlech; zanoření; obrys příslušenství). Panel ve scéně:
  `webapp/js/scene/stul-konfigurator.js` + routa `GET /api/stul/konfigurace` (`api/stul_api.py`, jen zaměstnanci) - **NASAZENO
  2026-10-02 17:11 ručně na Robertův klik** (běh #9, obsluha stála 5,6 s; sonda bez přihlášení 401, ne 404). Scéna: Ctrl+F5, plovoucí okno „Konfigurátor stolu“. **Předpoklady k potvrzení Robertem:** střední noha min. 150 mm od krajní,
  noha min. 60 mm (s kolečky H ≥ 180), elektrožlab jen s panelem, deska police má v rohu výřez 30×30 pro profil bočnice, horní rám/zadní
  nastavba nohou i bez LED (jen s panely), LED 1247 mm / panel 1190 mm po jednotkách, bez police a hloubka > 900 zůstávají spodní
  příčky bočnic. **Čeká:** schválení nahrazení `product_4930.glb` zavřeným šuplíkem (do té doby šuplíky v konfigurátoru hlásí
  „mimo obrys“); 8 spojů bez rohové spojky; max. formát lamina; cena/košík (bot5, `configurator_price.price_entries` bere `dily`).
  **E-SHOP / MINI-SHOP (2026-10-02 večer, bot8 + bot16):** Robert: konfigurátor patří na e-shop, ne do plné scény; „ve spojení s bot16 nasaďte na první
  mini shop“ (Packstations, česky, náhled staff). Hotovo a NASAZENO (běh #11, 18:17): veřejné API `api/stul_shop.py` (kontrakt
  `docs/KONTRAKT_KONFIGURATOR_UI.md`), karta **#4934 `STUL.SYSTEM30.KONF`** (neaktivní, pravidlo 54) + `app_settings.configurator_products`
  `{"4934":"stul_system30"}` (vypnutí = smazat záznam; pak vše 404), stránka `webapp/stul-konfigurator.html`. NÁSLEDUJE (commit `42c4c922`,
  nasadí se 3:30, Robert klik na dřívější zamítl): přesah desky vpředu 0–100 mm (výchozí 30), zpřísnění (přátelské texty bez technických
  údajů, kompaktní token, hodinové stropy, brána 404 i pro glb). Košík/objednávka s `configuration{selection,hash,rules_version}` (bot5) HOTOVÉ, NENASAZENO (viz blok Konfigurace sestavy v košíku výše),
  cenu bere ze serveru (`stul_shop.resolve` / `configurator_price`), měna Kč (mini-shop EUR přepočte sám), EN texty hotové, výkon (resolve 0,3–0,6 s, GLB 5 MB:
  zvážit kompresi), „Montáž“ slot zatím není, zadní nohy se zkracují jen když je vypnuto vše na nich (panely+LED).
  **Konstrukce #577 (rozbor 2026-10-02, pro pravidla):** 26 spojů profil-profil, 20 rohových spojek (`product_3158`, vazba
  `attached_to` na rodiče; odsazení od osy 15/13,5 mm, od konce profilu 29,1 mm nebo na výšce styku s příčkou); **8 spojů je BEZ spojky**
  (zadní horní příčka 2↔6/11/12/13, police 7↔13, 9↔12, 7↔19, 9↔19) - ověřit u Roberta, zda záměr. Mez výšek (výška desky H): kolečka
  nohy = H − 120 (při H 140 jen 20 mm → bez koleček), šuplíkový box visí 280 pod rámem (dno H − 328,5 → s kolečky H ≥ ~430), police
  (horní hrana 363) + box zároveň od H ≥ ~692; zavřený box = X −143…440, Z 115…680 (střední noha nesmí do jeho Z-pásma).

- **PILOT STŮL → typ STUL_SKLAD (bot8, 2026-10-02, pilot potvrzen Robertem: #577):**
  uložení sestavy typ vůbec nezapisovalo (`sestava_typ_id` NULL u nových). Hotovo: backend
  `0638f88f` (`sestava_typ` v POST, výchozí AUTO, `GET /api/product-assemblies/typy`) +
  scéna `88268495` (výběr „Typ nové sestavy“, skrytý dokud backend typy nevrací). Backend se
  nasadí 3:30 / ručně; pak: Ctrl+F5, vybrat typ, označit stůl, Ctrl+Shift+S. `technicky_ok`
  a `live_3d` nastavuje jen Robert; kolizní příznak u stolu
  spočítá časovač do 15 min po uložení (sweep opraven 2026-10-02, `63538531`; dřív padal na pantu 3219). Testy: `scripts/2026-10-02_sestava_typ_testy/run_all.sh`.

- **HOTOVO 2026-10-01 (bot8): ceny sestav - koeficient jen profily + Dogus, balné 3 %,
  rozpis dílů.** Robert: „koeficient pro scénu se týká jen profilů a produktů které
  se načítají z dogusu" → kód `c77795b5` (`/api/katalog`, příznak `scene_coef`;
  nasazení automaticky 3:30 / ručně přes bot3), uložené ceny přepočteny skriptem
  `scripts/2026-10-01_bot8_prepocet_koef_profily_dogus.py` (530 sestav, 12 karet,
  rozpis `data.bom` vč. „bez boxů"; záloha `backups/2026-10-01_prepocet_koef_profily_dogus/`).
  Starší skripty `2026-09-25_…_1_25.py` a `2026-10-01_…_balne_3pct.py` už NESPOUŠTĚT.

- **bot8 PRACUJE 2026-09-17: K-020 (Caddy Cargo Maxi PHEV) verze A -
  smazat stávající sestavu a postavit NOVOU podle pravidel** (Robert:
  "K-020 je misto kde chceme smazat sestavu ktera tam je a vytvorit
  spravnou novou", "mas to postavit podle pravidel ktere si nastudoval",
  "zadne hotove sestavy te ted nemaji zajimat", "b/c vubec ted neresit").
  Stav: průzkum pravidel/karoserie/nástrojů, pak stavba od nuly (ne
  z existujících sestav), ověření 3D v karoserii + 2D kóty, teprve pak
  smazání staré (#127, odvozené horní bloky #493/494/495 bez platného
  zdroje) se zálohou. Verze B/C (karta 3955) se NEŘEŠÍ.
  Odloženo, bez rozhodnutí Roberta: dalších 12 karoserií na "užším"
  modelu (1 box/patro) - K-017, K-018, K-019, K-021, K-022, K-075, K-078,
  K-237..K-242; K-237/K-239 a K-075 (karta 3943) mají živé karty.

- **ZADÁNO 2026-10-08 (Robert přímo bot7): kompletní IT verze našeho
  webu na `vandrawee.it` + kompletní EN verze na `vandrawee.eu`
  (odpauzováno, předchozí záznam níže PŘEKONÁN).** Robertovy volby
  (klikací otázky): **první vlna = KOMPLETNÍ E-SHOP hned** (košík,
  objednávky, platby, faktury v EUR, ne jen katalog), **ceny v EUR bez
  DPH, kurzem z Kč + marže** (jako mini-shopy: `miniweb_shops.eur_rate`,
  `margin_pct`, `miniweb_cena.py`). Stejný backend/DB/vizuál jako
  autovestavby.logiman.cz, jen host→locale→měna. Stav domén (ověřeno
  2026-10-08): **`vandrawee.eu`** – DNS u DigitalOcean (ns1-3) míří na
  CIZÍ server 216.158.238.178 (Interserver) a ukazuje indonéský hazardní
  spam (!). Robert opravuje v DO: A `@` a `www` → 75.119.132.164, ostatní
  A (`*`/`configurator`/`mail`) smazat; vhost `vandrawee-eu-it` na VPS je
  zatím jen 301 → autovestavby (HTTP, bez certifikátu → po propagaci
  `certbot --nginx -d vandrawee.eu -d www.vandrawee.eu`). **`vandrawee.it`**
  – NS Forpsi, A → 62.149.189.6 (Aruba), dnes tam běží STARÝ italský web
  (Wix-like, kontakt+WhatsApp); DNS se přepíná až bude nový web hotový,
  Robert. Rozdělení: **bot7** překlady obsahu (kategorie, stránky, karty,
  homepage, právní texty, e-maily) + glosář IT/EN + SEO (title/meta,
  slugy, hreflang) → `docs/web_jazyky/<en|it>/`; **bot16** host→locale,
  i18n vrstva UI (webapp ~31k řádků hardcoded CZ), resolver s fallbackem
  na CZ + „vše nebo nic“ gate před indexací; **bot5** `*_i18n` tabulky,
  import překladů, EUR/DPH v objednávkách/dokladech (VAT_RATE hardcoded
  na 2 místech, `CC:CZK` v SPAYD), IT/EN e-maily; **bot9** koordinace,
  certbot/nginx po Robertově DNS. **Robert 2026-10-08 (klikací otázka): prodej JEN FIRMÁM** (jako mini-shopy:
  registrace s názvem firmy + VAT ID, žádná spotřebitelská práva; soukromé
  osoby případně až později po právní kontrole). **STAV 2026-10-08 večer (bot7): překlady obsahu EN+IT HOTOVÉ** (12 sešitů
  `docs/web_jazyky/`, 6 053 položek, kontrola 0 chyb; IT drážka = scanalatura, Robert),
  `vandrawee.eu` DNS u Forpsi + certifikát hotov (jen 301), `.it` se nepřepíná, dokud
  web není schválen. Čeká: schválení EN názvu webu, nativní kontrola, bot16 náhled/brána,
  bot5 model měny po účetní. OTEVŘENÉ pro Roberta/účetní:
  DPH při objednávce (firma s VAT ID bez DPH / bez VAT ID?), doprava do IT/EU,
  platby, fakturace.

- ~~**POZASTAVENO 2026-09-17 (Robert přes bot7): vandrawee.it — čeká na
  dokončení ČESKÉHO obsahu, NEZAČÍNAT stavět.**~~ (PŘEKONÁNO 2026-10-08, viz
  výše) Robert: "italii budeme
  resit az budeme mít čestinu" — bot7 mezitím dělá kompletní přepis
  českého obsahu kategorií/produktů od nuly ("obsah nemá zatím hodnotu,
  chci ho celý udelat od piky"), teprve pak dává smysl se vrátit k
  Itálii (viz i dřívější zjištění bot7: 639/644 produktů má jen
  placeholder text, překládat teď = překládat 2×). Bot16 schema
  (locale/měna/hub-vztah) může počkat na tuhle prioritu, nerozjíždět
  naplno. Zbytek zadání (1:1 překlopení autovestavby.logiman.cz do
  italštiny) — Robert přímo: "prostě jen
  překlopíme autovestavby.logiman.cz webovou část na vandrawee.it
  italsky" (NENÍ to miniweb ani samostatný plán, viz
  `PLAN_TVORBY_MINIWEBU.md` pro architekturu domén/jazyků obecně, tenhle
  konkrétní úkol se tam už dál nerozepisuje). Stejný backend/DB jako
  hlavní web, stejný vizuál/branding jako Logiman, jen jiná
  doména/jazyk/měna (EUR/IVA - reálná změna cenové logiky, ne jen
  zobrazení). NE oživení starého `/opt/vandrawee` Unity systému. Bot16
  fázuje: nejdřív routing+schema skeleton na 1-2 kategoriích (ověřit
  cenu/branding/hreflang od základu), teprve pak bot7 škáluje italský
  překlad na celý katalog. Bot16 aktuálně zkoumá současnou cenovou/DPH
  logiku a i18n vzor z Toscanaccia, návrh schématu ještě nepředložen.

- **OTEVŘENO 2026-09-09 (bot8): razítkovač profilů 3D logem — čeká na 5
  rozhodnutí od Roberta** — Plán hotový v **`RAZITKOVAC_PLAN.md`**
  (podklady změřené nad reálnou geometrií, ne odhad). Robertova podmínka:
  *„3D logo nech má pod sebou i vyplněnou drážku"* — a je to oprava vady,
  ne kosmetika: vnější stěna profilu 30×30 není plochých 30 mm, takže
  8,20 mm z 28mm loga dnes přemosťuje prázdno a `Box3` to hlásí jako
  lícující dotyk. Výplň drážky jako díl neexistuje, musí se generovat.
  **Nezačínat implementaci**, dokud Robert nerozhodne: kolik log na
  sestavu (3 stačí u 259 z 263, 4 u všech), co s bookkeeping validátorem
  (počítá každé logo jako spoj za 110 Kč), a pořadí vůči běžícímu úkolu
  bot9 (přepisuje tytéž `data.parts`).
  ⚠️ **Přednost před razítkováním má jiná věc ze stejného průzkumu:**
  jediné místo, kde skutečná geometrie odchází nepřihlášenému příjemci,
  je `GET /api/public/offers/<token>/model` — a všechny 3 dnešní živé
  nabídky jsou neorazítkované. Vedle toho veřejný turntable payload vrací
  přesné vnější rozměry sestavy v mm (samostatná díra, razítko na ni
  nemá vliv).

- **AKTUALIZACE 2026-09-10 (bot8): veřejná půlka JE POSTAVENÁ, na produktu
  3942 místo 3884.** Robert 2026-09-10: *"kdo staví ten detail produktové
  sestavy na webu? postavit"*. Commit `aa050117`: veřejný
  `GET /api/shop/products/<id>/assemblies` (jen id/název/`has_turntable` —
  bez geometrie, bez kusovníku a cen), `?assembly=<id>` u turntable
  endpointu a `pdInitAssemblyVariants()` v `webapp/product.html` (tlačítka
  „Provedení", mění POUZE obrázek). **Přepíná po SESTAVÁCH jedné karty**,
  ne po produktech jako `pdInitVariantSwitcher` — protože našich šest
  variant visí na jednom produktu.
  ⚠️ **Tlačítka jsou zatím neaktivní: `product_turntable_frames` je
  PRÁZDNÁ (0 řádků pro všechny produkty).** Dávka se přijme jen
  KOMPLETNÍ — **162 snímků** (3 elevace × 27 azimutů 270° výseče × 2
  velikosti); statické pohledy se od 2026-09-11 nevyžadují (berou se
  z prstence). Hero snímek sám commit neprojde (409). Cesta z GPU do
  tabulky už existuje (`api/turntable_ingest.py`, bot8 2026-09-11) —
  chybí projet dávku, ne kód. Změřeno
  2026-09-10 na RTX 3060: ~150 s na snímek 2048×1536 při 924 vzorcích ze
  šablony → řádově hodiny na variantu. Hero snímky všech 6 variant
  vyrenderované a Robertovi předložené. **Zbývá: admin půlka (záložka s
  kusovníky) + naplnit otočky.**
- **ZADÁNO 2026-09-09 (Robert přes bot3), NEZAČATO: varianty sestavy —
  admin záložka s kusovníky + veřejný přepínač obrázků (produkt 3884)** —
  plné zadání v `scripts/handover.py show 102`, souhrn v `AGENTS_LOG.md`
  zápisu bot3 z téhož dne. Robert výslovně: *"už to nevytvářej, jen popis
  a ulož pro dalšího bota"* — proto je to popis, ne rozdělaná práce.
  **Rozsah: JEDEN produkt** `shop_products.id=3884` ↔
  `product_assemblies.id=134` (Doblo K-075 A), Robert: *"resime jen 1
  produkt !!!"*. Dvě místa, různý obsah:
  1. **Admin, skladová karta → nová záložka „Varianty produktu"**: seznam
     variant, každá s malým CPU renderem a **vlastním kusovníkem včetně
     ceny**.
  2. **Veřejná produktová stránka**: přepínač variant **jen s obrázky**,
     bez kusovníku a cen — mechanismus už existuje
     (`pdInitVariantSwitcher` + `webapp/js/product-variant-groups.json`,
     bot8 2026-09-06), stačí doplnit skupinu, až budou odvozené produkty.
  **Proč to rozdělení** (dvě závazná pravidla, neporušit): kusovník a ceny
  nesmí na e-shop (Robert 2026-08-08), a veřejně smí jen statické snímky,
  žádná geometrie (`project_ochrana_3d_modelu_sestav`, 2026-09-06).
  **Rendery**: GPU stanice není k dispozici → malé dočasné CPU rendery,
  znovupoužít `scripts/2026-09-09_turntable_job.py` (režim jednoho snímku:
  prázdné `elevations`/`azimuths`) + `api/blender_render_turntable.py`,
  Blender `/opt/blender-5.2/blender`. **Filtrovací logika variant** (port
  `sc3dVyberDily` + `polo` transformace + geometrický test vodorovného
  panelu `abs(quaternion[0])>0.5`) je v handoveru rozepsaná řádek po řádku.
  **Nedělat**: mazat `car_body_*` z dat, zakládat produkty dopředu, psát
  QA kontroly/Playwright (Robert dnes 2× zakázal), spoléhat na text receptu
  `shape_geometry_methods.id=9` (je zastaralý — nepopisuje prostřední polici).

- **OTEVŘENO 2026-09-09 (bot8): renderovací řetězec — jednorázový ruční
  krok u GPU počítače + neověřená šablona** — K té stanici **nemáme
  přístup** (Robert), takže "restartuj agenta" nesmí být krok, který
  pipeline potřebuje. Server si proto úlohu, kterou si worker do 10 minut
  nevezme, převezme sám (ověřeno naostro na sestavě 209 Doblo B) a nová
  verze agenta `2026-09-09c` se umí aktualizovat sama. **Zbývá:**
  (1) jednou u toho počítače stáhnout ze Sdíleného disku / Rendering
  `render_worker_agent_2026-09-09c.py` k agentovi, zavřít okno a spustit
  `SPUSTIT_AGENTA.bat` — od té chvíle už ruční krok potřeba nebude
  (pozor: `.bat` vyhodnotí cestu k agentovi jen jednou před smyčkou
  restartu, proto se nová verze zapisuje přes sebe samu);
  (2) **ověřit, jestli přebírající server předává Blenderu šablonu** —
  render Dobla B doběhl, ale materiály na něm vypadají na vestavěné
  výchozí hodnoty, ne na Robertovo nastavení, přestože úloha
  `template_blend` zapsanou má;
  (3) plný otočný náhled se pořád commituje k e-shopovému produktu, jenže
  všechny karty `SEST-*` jsou smazané — publikovat tedy dnes nelze žádnou
  sestavu (zkušební `--test` snímek už produkt nevyžaduje).
  Detaily: `AGENTS_LOG.md` (dva zápisy z 2026-09-09 večer),
  `PRODUKTOVE_RENDERY.md` pravidla 11 a 12, `handover.py show 97`.

- **ČÍSELNÍKY HOTOVÉ 2026-09-11 (bot9) — kód sestavy `K-075-E30A72`** —
  Robert přes bot3, rozšířeno přes bot8. Migrace
  `sql/2026-09-11_kod_sestavy_ciselniky.sql` **APLIKOVÁNA**, seed
  `scripts/2026-09-11_kod_sestavy_seed.py --apply` **PROBĚHL** (commit
  `85b2d4bf`, záloha `backups/2026-09-11_kod_sestavy_pred_seedem.json`).
  Ověřeno z nového spojení: `regal_typologie` 4 (E/U/S/V) ·
  `boxy_kombinace` 97 · `typologie_varianty` 97 · `horni_blok_varianty`
  7 (kódy 0-6) · **269 sestav otagováno**.
  Formát: karoserie · typologie · profil · varianta typologie (2 znaky) ·
  horní blok (0-6) · dodatek (jen když ≠ 0). Každá složka = vlastní
  sloupec na sestavě, kód se z nich **generuje**, nikdy zpětně neparsuje —
  přidání další typologie je proto nový ŘÁDEK, ne přeformátování kódů.
  Předchozí návrh z 2026-09-09 (`boxy_kombinace_ciselnik.sql` +
  `boxy_kombinace_seed.py`) byl nahrazen a smazán — nikdy se neaplikoval.
  - **Vzorky Dobla C vycházejí** `K-075-E??1R1` … `K-075-E??1R6`
    (`??` = profil, doplní admin), základní sestava 279 → `…1R0`.
  - ⚠️ **`kod_sestavy` je zatím u všech prázdný** a schválně: generuje se
    až z `profil_mm`, který se **nehádá z geometrie** (Robert: „velikost
    profilu je jen pro orientaci, profil určuje admin"). Dokud ho admin
    nevyplní, kód se nevygeneruje — radši chybějící než uhodnutý.
  - **7 starých bloků zůstalo bez kódu** (134/135/182/189/209/219/289),
    `horni_blok_varianta_id IS NULL` — čekají na přestavbu podle vzoru.
    Sestava 279 mezitím o starý blok přišla (bot8), takže má správně `0`.
  - **ROZHODNUTO Robertem 2026-09-11 (přes bot8), ČTI PŘED POKRAČOVÁNÍM:**
    *„kódy variant horního bloku budou čísla, postupně po sobě."* Číselník
    `horni_blok_varianty` se má **přeobsadit na ŠEST řádků** číslovaných
    vzestupně podle provedení, která skutečně existují (sestavy 332-337 na
    produktu 3942): 1 jedno pásmo jen rám · 2 jedno pásmo rám+dna [základ] ·
    3 dvě pásma jen rám bez police · 4 dvě pásma police jen příčky ·
    5 dvě pásma plné výplně bez police · 6 dvě pásma plné výplně s policí.
    Dnešních 5 kódů (`bez`/`eko`/`plné`/`polo`/`dvířka`) pochází ze starých
    DOPOČÍTÁVANÝCH os, které Robert 2026-09-10 odmítl a které byly z
    ekvalizéru odstraněny (commit `51768661`) - **nezná osu „jedno/dvě
    pásma"**, takže by „1/6 jedno pásmo jen rám" a „3/6 dvě pásma jen rám"
    dostaly OBĚ kód `2` a přestaly by být rozlišitelné. Formát
    `K-XXX <verze> XXXXY` se nemění. Tím padá i původní otázka, jestli osa
    `rám` patří do `Y`.
  - **Otevřené, čeká na Roberta:** jaký kód dostane „bez horního bloku"?
    Původní číselník na to měl `1`, ta je teď první provedení. Navrženo `0`;
    Robertovi položeno 2026-09-11.
  - ⚠️ **PAST V DETEKCI „má horní blok" (bot8 2026-09-11, přeměřeno):**
    dry-run z 2026-09-09 uváděl 7/263. Dnes je to **14/269** - přibylo šest
    variant (332-337) a v původních osmi nejsou jen Dobla: **Jumpy L2 má
    čtyři** (182, 189, 219, 289) a Doblo Maxi jednu (135).
    ⭐ **Robert 2026-09-11: „staré horní bloky neplatí, vzorový horní blok
    děláme na Doblu C."** Těch osm starších (134/135/182/189/209/219/279/289)
    se tedy NEČÍSLUJE jako provedení, nerenderuje a nepublikuje - přestaví se
    podle vzoru, až bude hotový. Vzor = šest provedení na produktu 3942.
    Hlavně ale: **detekce podle výplní nebo rolí `*-horni` NEFUNGUJE.**
    Jednopásmový blok je celý z rolí `podelnik-*-spodni` + `pricka-spodni-*`;
    „horni" v názvu role znamená DRUHÉ PÁSMO, ne horní blok. Sestava
    `id=332` („1/6 jedno pásmo - jen rám") tak vypadá jako „bez horního
    bloku", i když ho má - dostala by kód `0` místo `1`.
    Spolehlivý predikát je **`role.startsWith("podelnik")`** - podélník se
    mimo horní blok nevyskytuje. Ověřeno nad všemi 269 sestavami: 14 s
    blokem, 255 bez.
  - ⚠️ **ROZŠÍŘENÍ KÓDU, Robert 2026-09-11 (přes bot8) - VYŘEŠIT PŘED SEEDEM:**
    *„bude mnoho typů regálů, na euroboxy je jen jeden z nich, máme základní
    3 velikosti profilů ze kterých se staví regály do auta 30, 40, 45,
    musíme do kódu sestavy zavést víc věcí."* Dnešní formát mlčky
    předpokládá euroboxový regál - chybí v něm **typ regálu** a **velikost
    profilu (30/40/45)**, a segment rozpisu boxů je u jiného typu regálu
    bezvýznamný. Doporučení: nepřidávat další znaky do řetězce, ale dát
    každému rozměru **vlastní sloupec + číselník** a kód z nich generovat -
    přidání typu je pak nový řádek číselníku, ne přeformátování všech
    dosavadních kódů. Návrh bot9 tím směrem už míří (číselníky + FK), stačí
    rozšířit DŘÍV, než se seed pustí; potom by to znamenalo přečíslovat.
    Otevřeno pro Roberta: jaké typy regálů existují; může mít sestava víc
    velikostí profilu zároveň; je velikost profilu osa posuvníku, nebo jiná
    karta.
  - **Souvislost (bot8 2026-09-11):** Robert chce A/B/C přepínat DRUHÝM
    posuvníkem na TÉŽE kartě, ne samostatnými kartami - varianta je tedy
    dvojice souřadnic (verze × horní blok), 3 × 6 = 18 sestav na kartu.
    Osy proto musí být uložené jako POLE, ne dolované z názvu sestavy.
    Plán: https://claude.ai/code/artifact/aa527d06-6532-4ad8-a09d-705971971d92
  - **AKTUALIZOVÁNO 2026-09-11 — Robert určil PŘESNÝ tvar** (přes bot8),
    který vyhrává nad dřív odvozeným zkráceným návrhem:
    `K-075-EB-30-A-0001-2-0` = karoserie · typologie (**2 znaky**) ·
    profil · **verze (samostatná složka)** · rozpis boxů (**4 číslice**) ·
    horní blok · dodatek, oddělené pomlčkami. Zapracováno a aplikováno
    (commit `19d8104b`, migrace `sql/2026-09-11b_kod_sestavy_format_
    roberta.sql`, skript `scripts/2026-09-11_kod_sestavy_format.py`,
    záloha `backups/2026-09-11_kod_sestavy_format_pred_zmenou.json`).
    Verze doplněna u **268 z 269** sestav (ověřeno dvěma nezávislými
    regexy s 0 konflikty; 6 variant vzoru zdědilo `C` od základní 279).
    **Vzor Dobla C očíslován a přejmenován:** 279 → `K-075-EB-30-C-0063-0-0`
    (název nezměněn), 332-337 → `…-1-0` až `…-6-0`.
  - **ZBÝVÁ:** (1) admin vyplní `profil_mm` u zbytku katalogu — dnes má
    kód jen **7 sestav vzoru**, protože profil se nehádá (Robert: „profil
    určuje admin"); (2) po doplnění profilů dogenerovat kódy;
    (3) přidat QA kontrolu k pravidlu 26 („produkt navázaný na sestavu má
    jiný název než ta sestava") do `api/qa_checks.py` — vyžaduje zámek,
    guarded. **Na zbytek nesahat** (pravidlo 23a).
  - **Otevřené pro Roberta:** (a) dvouznakové kódy pro zbylé 3 typologie —
    zatím jednoznakové `U`/`S`/`V`, návrh `UN`/`OS`/`EV`; (b) sestava
    `189` (Jumpy L2 K-123e) nemá verzi a z názvu ji nelze odvodit —
    zůstává NULL, tedy i bez kódu; (c) odvozuje se název produktu 3942 od
    sestavy 279? (proto se 279 nepřejmenovala); (d) uzavřít seznam
    typologií.

- **PROBÍHÁ 2026-10-01 (bot10): výmaz názvu dodavatele knihovny karoserií.**
  Robert 2026-09-30: slovo má být vymazáno ÚPLNĚ, ze všeho (soubory, zálohy,
  paměť botů, předávky); nepoužívat ho ani v odpovědích. Hotovo: paměť botů,
  předávka #90. Zbytek viz předávka #90; nevratné kroky (git historie, archivy
  záloh, binlogy MySQL) čekají na Robertovo rozhodnutí o konkrétní podobě.

- **OTEVŘENO 2026-09-05/06 (bot15): vodoznak - rozhodnout o kraji značek
  u plno-záběrových fotek, PAK stavět derivovaný strom** — navazuje na
  bot22 2026-09-04 "Vodoznak na obrázky" a bot8 2026-09-05 nález chyby
  pozicovacího algoritmu (`AGENTS_LOG.md`, hledej "kand.sort"). Algoritmus
  opraven (`scripts/watermark_build.py`, farthest-point sampling místo
  směrově zkresleného tie-breaku), Robert schválil variantu B (2 značky
  na produktu + 2 mimo) na A/B náhledu. Změřeno na korpusu (300 souborů,
  Dogus materiál vyloučen - 648/717 souborů `gallery/products/` je Dogus,
  NESMÍ dostat vodoznak): směrová chyba opravena, "0 značek" 15,2%→0%,
  ALE `gallery/vestavby_dodavek` (98 %) a `gallery/realizace_stolu`
  (95 %) mají značku "u kraje" - fotky bez čistého pozadí (produkt
  pokrývá 54-84 % plochy) nemají kam značku dát jinam. **Robert
  (2026-09-06): NESTAVĚT `wm/content-files/` derivovaný strom, dokud
  tohle není rozhodnuté** (je to fyzikálně nevyhnutelné a OK, nebo
  potřeba dalšího doladění?). Plný detail (tabulka po složkách, čísla)
  v `AGENTS_LOG.md` zápisu bot15 2026-09-05/06. Neblokováno technicky,
  čeká na Robertovo rozhodnutí přes bot3.

- **HOTOVO 2026-09-06 (bot9): firemní údaje `kontakt.html` z DB místo
  natvrdo v HTML** — Robert (přes bot3), commit `7a3278b8`. `app_settings`
  klíč `company_info` (JSON, ne nová tabulka - konzistentní s existujícím
  vzorem `og_site_defaults`/`smtp_config`) + admin formulář (`admin.html`,
  tab Nastavení) + SSR `GET /kontakt.html` (`api/company_info.py`) čte
  meta description/OG/JSON-LD i viditelné řádky z DB. E-mail zůstal jako
  obrázek, ale generovaný za běhu (`/api/contact-email-image`) podle DB
  hodnoty, statické `.png` smazány. **Pozor**: SSR funguje JEN na vhostech
  s `location = /kontakt.html` proxy (`logiman-autovestavby` +
  `konfigurator`, mimo git) - Fiat storefronty/`remeslnik-pro` dál
  servírují statický soubor beze změny (vědomě, jiné brandy). Detail +
  judgment-call flag (admin formulář ukazuje plain-text e-mail, viz
  memory `feedback_no_live_email_on_any_website`) v `AGENTS_LOG.md`.
  Vedlejší 2 schválené drobné opravy stejným zadáním: brand
  "Vandrawee"->"Logiman" v title/og:title (HOTOVO, commit `b1e63868`) a
  www→apex redirect na `logiman-autovestavby`+`konfigurator` vhostech
  (HTTP hotovo a live; **HTTPS blok pro `www` ZBÝVÁ** - čeká čistě na
  DNS negative-cache expiraci u Let's Encrypt, 3× ověřeno stále NXDOMAIN
  u Google/LE resolverů i po hodině, přesný retry příkaz i další krok
  viz `AGENTS_LOG.md` 2026-09-06 "bot9 — pokr.").

- **PODKLAD 2026-09-06 (bot10): extrakce katalogu vanDrawee (3D objekty,
  ceny/hmotnosti, kusovníky, komponenty, nohy)** — Robertovo zadání
  "nasát know-how z vandrawee.eu, ne přesypat systém" (viz `AGENTS_LOG.md`
  2026-09-06 pro plný kontext debaty). 41 CSV/TSV/SQL souborů v
  `backups/2026-09-06_vandrawee_katalog_extrakce/` — kompletní export
  (ne vzorek) z databází `vandrawee`/`vandrawee_work` (import produkčního
  dumpu z 5.9., ne živá produkce) + inventura 336 FBX z Unity projektu.
  **Klíčový nález pro nohy profilu 30/40/45**: profil 30 pro nohy ve
  vanDrawee VŮBEC NEEXISTUJE (ani v datech, ani v Unity kódu) - naše
  "noha profilu 30" vznikla přímo jako nová geometrie v `konfigurator.
  profily`/`komponenta_profil_recept`, mimo vanDrawee úplně. Kusovník
  nohou 40x40 vs 45x45 (srovnáno na Caddy+Jumpy) má STEJNOU kostru
  kategorií dílů, ale přebrání profilu 45 vyžaduje ruční práci na
  5 místech (přeměřit 5 řezaných kusů na jinou délku, 1 zcela jiný
  kotevní díl, 3 položky navíc jen u 45, jen 3 drobné díly projdou 1:1,
  auto-specifické polohové výjimky se nedědí mezi profily). Detailní
  srovnávací tabulka: `nohy-kusovnik-srovnani-40-vs-45.csv`.
  Vedlejší nálezy: potvrzena "cunt/count" chyba v PHP exportu (2 soubory,
  ne v DB), 3 aktivní komponenty (id 107/108/124) s nulovou cenou i
  hmotností k prověření. **Zbývá**: navrhnout a implementovat ekvivalentní
  strukturu (kompatibilní seznamy, dvojí náhledy s/bez kót, sdílené
  `unity_id` napříč sourozeneckými auty) v našem katalogu/scéně - zatím
  jen podklad, ne hotová implementace.

- **AKTUALIZACE 2026-09-07 (bot10): Vandr algoritmus + render postup
  zdokumentovány, zatím NE implementováno do produkčního Three.js.**
  Tři oddělené soubory v rootu repa (rozcestník v `CLAUDE.md` bod 6):
  `VANDR_SKLADANI_REGALU.md` (algoritmus z C# kódu + ověřené
  geometrické pravidlo "čelo profilu komponenty musí dolehat na stěnu
  profilu nohy" — platí vodorovně i svisle, plus červené plošky =
  tvrdé dorazy pro stohování komponent na sebe), `VANDR_RENDER_HOWTO.md`
  (postup + ⭐ povinná pravidla — barevná konvence, 2D kontrola
  automaticky pro každý díl), `VANDR_DILY_ZNACENI.md`. Ověřeno reálným
  renderem a měřením na Sprinter H1 1580 a Movano H1 1490 (nohy +
  police/dvířka/šuplíky/top komponenta), víc oprav skutečně nalezených
  chyb (ne jen teorie) zapsáno přímo do pravidel. **Render kód JE
  commitnutý** (`scripts/2026-09-07_vandr_render/vandr_geometry_lib.js`
  + `render_movano_assembly.html`, otestováno ze svého trvalého
  umístění, ne jen ve scratchpadu) — FBX zdroje samotné (vendor assety
  z `/opt/vandrawee`) commitnuté NEJSOU, cesty k nim jsou v komentáři
  na začátku render skriptu. **Zbývá**: implementace do produkčního
  `webapp/scene.html`.

- ~~Cutover produkčních DB Forpsi → lokální MySQL~~ **VŠECHNY 4 PROJEKTY
  HOTOVÉ** (ověřeno bot3 2026-09-09 přes `information_schema.processlist`:
  `konfigurator_app`→`konfigurator_v3`, `toscanaccio_app`→`toscanaccio`,
  `vestavby_app`→`vestavby_vozidel`, `/opt/remeslo` → `remeslo`, vše na
  `127.0.0.1`). Toscanaccio dodělal bot3 2026-09-09 (Robert: "okamžite
  prepnout"), post-cutover delta 0 rozdílů - viz `AGENTS_LOG.md` a
  `/opt/toscanaccio/AGENTS_LOG.md` 2026-09-09.
  **ZBÝVÁ POUZE ROBERTOVI**: smazat samotné DBaaS služby na Forpsi
  (Remeslnik, vestavby_vozidel, Configurator, Toscanaccio) - technicky
  všechny 4 bezpečné, u Toscanaccia doporučeno počkat pár dní ověřeného
  provozu. Forpsi je zatím nechána živá jako pojistka.
  **Poučení pro editaci `.env`**: `/opt/toscanaccio/api/.env` musí být
  `root:www-data 640` (appka ho čte sama jako `www-data`, unit NEMÁ
  `EnvironmentFile=`) - editace nástrojem, který soubor přepíše, mu vezme
  vlastnictví a service se zacyklí na `PermissionError`.

- **ČEKÁ NA ROBERTA (bot3, 2026-09-09): jedno živé ověření vstupu do
  scény po zabezpečení.** `webapp/scene.html` byl do 2026-09-08 úplně
  veřejný (statický servírovaný nginxem bez kontroly) - viz `AGENTS_LOG.md`
  2026-09-08. Teď prochází přes `scene_html_gate()` (staff-only) na všech
  9 vstupních bodech (hlavní doména, `IP:8090`, 7 generovaných Fiat
  storefrontů). Negativní cesta ověřena živě (neprihlášený → 302 na
  login), ale **pozitivní cestu jsem netestoval** (nechtěl jsem zakládat
  testovací účet) - chce to jeden klik-through přihlášeného staffa na
  mobilu i desktopu, že se scéna pořád normálně otevře.

- **ČEKÁ NA ROBERTOVO ROZHODNUTÍ (bot3, 2026-09-09): má nahrávání na
  Sdílený disk přežít ZAVŘENÍ záložky?** Současný stav: přežije přepnutí
  záložky v adminu i odfokusování okna, ale zavření prohlížeče přenos
  ukončí (běží v stránce). Nabídnuté cesty: (a) chunked/resumable upload
  (po znovuotevření pokračuje od místa, kde skončil - funguje všude),
  (b) Background Fetch API (opravdu běží i po zavření, ale jen Chrome/
  Edge), (c) stahování na straně serveru (odkaz/složka, na prohlížeči
  nezávislé). Nikdo nezačal, čeká se na volbu.

- **ROZPRACOVÁNO 2026-09-06 (bot8): ochrana 3D modelů sestav (3 stupně) + konfigurovatelnost na webu - MECHANISMUS HOTOVÝ, čeká se na kvalitní sestavy.**
  Viz `AGENTS_LOG.md` 2026-09-06 21:45 "Predni azimut otocky per-sestava +
  konfigurovatelnost na webu + DULEZITA oprava" pro plný detail. Shrnutí:
  - **Hotovo a funkční:** přední azimut otočky se počítá per-sestava
    (`api/turntable.py` `_azimuths_for_front`, `webapp/scene.html`
    `computeFrontAzimuthDeg` z role tagů `predni-svislice`/`cap`) - žádná
    globální konstanta, komity `bd5b2f31`+`b53faee3`. Konfigurovatelnost
    na produktové stránce (`webapp/js/product-variant-groups.json` +
    `pdInitVariantSwitcher`/`pdSwitchToProduct` v `product.html`) - AJAX
    přepnutí varianty bez reloadu, jen JPEG snímky, žádná geometrie ven
    (komity `fd6c0392`+`a4fa15ad`).
  - **DŮLEŽITÉ zjištění (oprav pokud narazíš znovu):** kód s příponou "e"
    (`[K-123e]`) = ELEKTRICKÁ verze vozidla (`Citroën ë-Jumpy`), NE
    varianta horní sekce/zrcadlení - `[K-122]` (bez "e") je JINÉ vozidlo
    (obyčejný Jumpy). Shodná skladba boxů mezi nimi je náhoda kvůli
    podobné karoserii, ne důvod je řadit do jedné konfigurovatelné
    skupiny.
  - **Robertovo rozhodnutí 2026-09-06 21:4x: "nejdřív chci připravit
    kvalitně veškeré sestavy a jejich varianty" + "stávající rendery se
    stejně smažou".** Další práce na konfigurátoru/webu čeká, až budou
    sestavy pro jednotlivá vozidla pořádně postavené (ne jen K-123e
    pilot). 3 testovací produkty (3932/3937/3941, aktivované jen pro
    ověření mechanismu) jsou POČÍTANÉ KE SMAZÁNÍ - nerozvíjet kolem nich
    další práci.
  - Menší restY: `webapp/js/turntable.js` drag neomezuje na 270° výseč
    (neopraveno); bracket-collision fix horního bloku (sestava 189) pořád
    nezapsán do živých dat, čeká na Robertovo schválení nezávisle na
    tomhle vlákně; stupeň 2 ochrany (podepsaný odkaz, zploštění GLB jmen,
    razítko) nezačato.
  - **HOTOVO 2026-09-06 22:45: druhá varianta výšky boxů pro všech 70
    karoserií s jen 1 variantou** (Robert: "Všude kde máš pouze 1
    variantu musíš přidat aspoň 2", "maximálně odlišné"). Metoda,
    ověření, výsledek viz `AGENTS_LOG.md` 2026-09-06 22:45 - shrnutí:
    znovupoužit ověřený algoritmus `tmp_2026-09-02_bot16_de_build.js`
    (jen výšky boxů se mění, kostra sloupců/noh beze změny), varianta
    "vše 120mm" (nejmenší třída, vždy prokazatelně odlišná od originálu),
    každé patro ověřeno reálnou kolizí s GLB karoserie. Zapsáno přímo do
    `product_assemblies` (INSERT, id 192-261), `category_id`/
    `shop_product_id` zůstávají `NULL` (nezařazené, bez e-shop karty).
    Skript uložen `scripts/2026-09-06_gen_second_box_height_variant.js`,
    seznam vložených id `backups/2026-09-06_druha_varianta_vysek_boxu/
    inserted_ids.json`. Artefakt "Skladby boxů" (https://claude.ai/code/
    artifact/8de66e07-54cb-4ea6-bd12-d6c98833afa3) aktualizován na stav
    po vložení - **zbývá**: totéž zvážit i pro 11 karoserií, co už měly
    víc variant, ale s duplicitní skladbou (viz filtr v artefaktu).

- **DOKONČENO 2026-09-06, čeká jen na restart: odstranění původního vendor označení karoserií z DB.**
  Vše zapsáno a ověřeno (viz `AGENTS_LOG.md` "Karoserie: přejmenování
  DOKONČENO" + navazující "Sestavy: starý kód nahrazen novým"):
  `car_models.name` (304/304, formát `[K-0XX]`/`[K-0XXe]` pro
  elektrické varianty, číslováno abecedně), `car_bodies.name` (912/912),
  `karoserie_model_reference` + `custom_shapes` přepnuty na stabilní
  `car_models_id`/`car_model_id` (FK), `product_assemblies.name` +
  `shop_products.name`/`slug`/`sku` (110+1 sestav, přímá náhrada kódu -
  Robert: "CI25 > nahrazeno novým kodem, to je logické"), `scene.html`/
  `api/cars.py`/`api/custom_shapes.py` upraveny (commit `168d114e`),
  veřejný SEO popisek sestavy žádný kód neukazuje (jen značka+model+rok).
  **Vyžaduje `systemctl restart konfigurator.service`** (sandbox
  blokuje, potřeba Robert/jiný bot) - do restartu jsou živé jen DB
  změny + `scene.html` (servíruje se přímo z disku).

- **ARCHITEKTURA (budoucí, NEZAČÍNAT bez Roberta) - taxonomie TYPŮ VESTAVBY**
  **v autě** (Robert, 2026-09-06, doslovně: "Ještě to zkomplikuju víc...
  poměrně propletená struktura, která se nyní bude vytvářet, ujasňovat" →
  "zapiš to někde na nástěnku, ale pojďme řešit věci postupně, Jumpy a
  regál na euroboxy"). Zapsáno jako poznámka pro budoucí práci, ŽÁDNÁ DB
  změna zatím neproběhla (pokus o CREATE TABLE stažen zpět na Robertův
  pokyn "přece jsem říkal že jsme na začátku" - `sql/2026-09-06_vestavby_
  typy_verze.sql` zůstává v repu jen jako NEAPLIKOVANÝ návrh k diskuzi).

  **Zadání (Robert, doslovně):** "Jedna karoserie mohla obsahovat více
  typů vestaveb." Typy: 1) regál levý, 2) regál pravý, 3) regál na
  přepážku, 4) regál na levou stranu i na přepážku spojený, 5) výsuvný
  modul (např. z bočních dveří), 6) dvojitá podlaha/druhá podlaha (uložný
  prostor v podlaze, většinou velké šuplíky, do zadních dveří / bočních
  dveří / obou). Uvnitř typu 1 (regál levý) víc VERZÍ, např. a) regál na
  euroboxy, b) regál univerzální (mnoho různých komponent), c) další verze
  mohou přibývat. Navíc: podle velikosti auta se volí různá velikost
  profilu na stejnou konstrukci.

  **Nález (bot8):** v DB už existují `komponenty`/`komponenty_varianty`
  (bot16, 2026-08-31) - ale je to JINÁ, jemnější vrstva (konkrétní stavební
  vzor "Regál na euroboxy" + jeho rozměrové varianty lůžka, 1 komponenta/
  3 varianty). Nezaměňovat s tímhle vyšším "typ vestavby" konceptem -
  obě vrstvy budou muset koexistovat, ne se nahradit.

  **2 otevřené otázky pro Roberta, zatím nezodpovězené** (bot8 se zeptal,
  Robert odpověděl "pojďme postupně" - platí dál, jen odloženo):
  1. Je "regál levý + přepážka spojený" (typ 4) VLASTNÍ konstrukční vzor
     (jeden souvislý roh, jiný spoj než 2 oddělené regály vedle sebe), nebo
     KOMBINACE typu 1+3 (dva samostatné regály jen fyzicky navazující)?
     **ODLOŽENO Robertem (2026-09-06): "to budeme dělat až jako poslední,
     neřešme to nyní"** - typ 4 se řeší AŽ NAKONEC, po zbytku taxonomie.
  2. Je včerejší "horní blok pro dlouhé předměty" (`shape_geometry_methods.
     id=9`) SVŮJ VLASTNÍ typ vestavby (7. v seznamu), nebo DOPLNĚK
     přidatelný k libovolnému regálu (levému/pravému/přepážce)?
     **ROZHODNUTO Robertem (2026-09-06): DOPLNĚK** - "bude se opakovat
     pravděpodobně v různých verzích regálů levá pravá", tedy modulární
     přídavek k libovolné verzi regálu, ne samostatný typ v seznamu.

  **Navržený (NEAPLIKOVANÝ) datový návrh** viz `sql/2026-09-06_vestavby_
  typy_verze.sql` - dvě nové tabulky `vestavby_typy`/`vestavby_verze` +
  2 nové nullable FK sloupce na `product_assemblies` (`vestavba_typ_id`,
  `vestavba_verze_id`, analogicky k už existujícímu `car_model_id`).
  Nerozhodnuto: má `vestavby_verze.shape_geometry_method_id` ukazovat na
  JEDEN "kotevní" recept (eurobox regál dnes používá 6 receptů najednou -
  id=3/5/6/7/8/9), nebo se má "velikost profilu podle velikosti auta"
  řešit jako admin-editovatelná tabulka (vzor `dogus_price_coefficient`)
  místo odvozování uvnitř receptu z reálných rozměrů karoserie (dosavadní
  konvence projektu - nikdy nezadrátovávat, vždy měřit).

  **AKTUÁLNÍ SCOPE (Robert, 2026-09-06, přísně): "řešíme to jedno Jumpy**
  **jako vzor"** - opakovaně upřesněno (STOP na testování napříč celou
  Jumpy rodinou) - pracuje se VÝHRADNĚ na `product_assemblies.id=189`
  (Jumpy L2 CI25). Generalizace na zbytek rodiny/jiné značky POČKÁ, dokud
  vzor není hotový.

  **Formát popisu větve (Robert, 2026-09-06, šablona pro pojmenování**
  **konkrétní rozpracované kombinace):**
  ```
  Systém: 30                    (profil 30x30 - velikostní rodina; "systém 30",
                                  budoucí větší auta = "systém 40" apod.)
  Karoserie: Jumpy (vzor)        (libovolná karoserie, teď zrovna Jumpy jako pilot)
  Verze regálu: euroboxy
  Vlastnost/pravidlo: Horní regálový blok (hloubka odvozená ze zúžení
                                  karoserie nahoře - viz níže)
  ```

  **Horní regálový blok - OFICIÁLNÍ NÁZEV** (dřív "horní blok pro dlouhé
  předměty", `shape_geometry_methods.id=9`) - Robert potvrdil jako OBECNÝ,
  téměř univerzální požadavek, ne edge-case: "podle karoserie, které jsou
  většinou nahoře užší, musíme mít: horní regálový blok" - karoserie se
  směrem k Y (výšce) typicky ZUŽUJE (viz `scripts/2026-09-05_profil_
  zuzeni.js`), takže horní regálový blok musí mít MENŠÍ hloubku než hlavní
  police pod ním - to je zapisováno jako rozšíření receptu `id=9`
  (`horni-blok-hloubka-dle-zuzeni-karoserie`), právě rozpracováno na
  CI25, viz `AGENTS_LOG.md`.

  **STAV 2026-09-06 (bot8): hloubková adaptace hotová a bezkolizní na
  CI25** (`scripts/2026-09-05_horni_ram.js`, `asm187.json`) - 0 kolizí
  s díly, 0 kolizí s karoserií, regresní sada `2026-08-19_regression_
  scene/run_all.js` zelená. Mimochodem opravena i chybná mezera nad boxy
  (4mm -> povinných 30mm, viz Robertova poznámka výše). `shape_geometry_
  methods.id=9` zapsán jako version=2 (algoritmus 8/9 + kritická past
  "bracket práh T"), `KOMPONENTY_EUROBOXY.md` doplněno. **ZATÍM
  NEZAPSÁNO do `product_assemblies.id=189`** - čeká na Robertovo
  schválení výsledku (viz `AGENTS_LOG.md` pro detail). Bracket-větev
  (potřebná jen když by posun > 30mm) je napsaná, ale na CI25 se
  neuplatnila (posun 14,2mm) - zůstává neověřená na reálném autě.

  **NOVĚ 2026-09-06 (bot8): živý 3D náhled + přepínání variant horního**
  **bloku ZABUDOVÁNO do skladové karty** (Robert: "zhmotni na frontendu
  to, co jsi měl v artefaktu"), ne jen v samostatném demu (`regal3d.
  html`). Admin → Produkty → skladová karta → záložka "3D model"
  (`webapp/admin.html` + `webapp/admin/js/sklad-produkty.js`, ~390
  nových řádků). Živě přepočítává 3D scénu i kusovník/cenu podle
  zvolené varianty (bez/eko/plné/poloviční/dvířka + rám). Bezpečnostní
  nález cestou opraven před commitem: karoserie (`car_body_*`) se ve
  3D správně zobrazuje (staff nástroj, stejně jako scene.html), ale
  omylem se počítala i do kusovníku - opraveno, teď se vylučuje stejně
  jako v produkční `computeAssemblyBomAndPrice`. Logika ověřena
  standalone Node testem nad reálnými daty sestavy 189 (0 kolizí s
  produkčním BOM). **NEOVĚŘENO VIZUÁLNĚ** - autentizovaný screenshot
  zablokoval sandbox (odmítl "mint" session i pro existující admin
  účet), potřeba Robertovo přímé kliknutí ve skladové kartě produktu
  #3937 pro potvrzení, že se 3D scéna vykresluje a přepínače fungují.

- **Party model backfill existujících identit - BLOKOVÁNO klasifikátorem, čeká na Roberta** (bot18, 2026-09-05; nezávisle ověřeno 2026-09-05 read-only SELECT - `parties`=0, `party_id` na všech tabulkách stále 0, beze změny). Schéma + živý kód (fáze 2-5) nasazeny a fungují pro VŠECHNY BUDOUCÍ záznamy, commit `648e230`. Zbývá: Robert přes `!` spustí `scripts/2026-09-05_parties_backfill.py --apply` (dry-run ověřen: 4 identity z `app_users`, propojí 3 `shop_customers` + 5 `crm_leads`), poté `scripts/2026-09-05_remeslo_party_sync.py --apply` (fáze 5). Detail a zdůvodnění: `AGENTS_LOG.md` "Party model: schéma + živý kód nasazeny".

- **OTEVŘENÉ OTÁZKY, ne k řešení teď: Scudo "tabulka rozměrů" na**
  **standalone doméně neúplná** (bot18, 2026-09-05, viz `AGENTS_LOG.md`
  "Doblò subdoména: doplněna tabulka rozměrů") - dvě samostatné
  otázky pro Roberta:
  1. `car_storefront_models` u `fiat-scudo-vestavby.top` (storefront_id
     15) nabízí varianty E-Scudo L1 [FI29] a Scudo L1 22- [FI19], ale
     `backups/2026-08-22_official_only_door_and_wheelarch_dims.json`
     má u obou výslovnou poznámku "not offered - absent from CZ list"
     - mají tyhle konfigurace vůbec být volitelné na webu, když se v ČR
     neprodávají?
  2. Zbylé 3 chybějící variantě (Scudo L1H1/L2H1/L2H2 -16, generace
     2007-2016) nemají v backup souboru dost čísel na doplnění
     strukturované věty o rozměrech (chybí výška zadních dveří u
     všech, u L2H2 i šířka bočních dveří) - potřeba buď nový zdroj
     dohledat, nebo mezeru v obsahu vědomě přiznat/nechat.
  Ducato NEŘEŠIT (rozhodnuto bot3, 2026-09-05) - informace o výšce
  zadního nakládacího otvoru tam v próze reálně je, jen jinou
  formulací než standalone strukturovaná věta, sjednocení formátu
  nestojí za riziko/čas.

- **NÍZKÁ PRIORITA, k budoucímu zvážení: `shop_orders.billing_state` odvozovat z existence faktury, ne jen ze `status`** (bot18, 2026-09-05, nález z Odoo srovnání, artefakt "Odoo jako zrcadlo" poslán bot3/Robertovi) - **ANALÝZA, NEIMPLEMENTOVAT bez schválení** (bot3, 2026-09-05: "doporučení k analýze, ne schválená implementace"). `billing_state` (`_states_for_status()` v `api/orders.py`) je ručně nastavený štítek odvozený jen ze `status`, nic ho nekontroluje proti reálné existenci řádku `shop_documents.document_type='invoice'` - vystavení faktury a přepnutí `status` na `fakturovana` jsou dvě nezávislé admin akce. Živě ověřeno: všech 19 objednávek `status='fakturovana'` má 0 řádků faktury v `shop_documents` (historický CSV import před migrací, neškodné) - žádná živá objednávka dnes mezerou netrpí, jde o robustnost do budoucna. Navrhované řešení: malý ověřovací `EXISTS(...)` dotaz místo čistě `status`-odvozeného pole - čeká na schválení, nikdo zatím neimplementoval.

- **ROTACE `DB_PASSWORD` - ZBÝVÁ, blokováno klasifikátorem** (bot18, 2026-09-03, schválil Robert přes bot3) - audit hotový, 6krokový postup + záloha `.env` připraveny (`AGENTS_LOG.md` 2026-09-03), ale `ALTER USER` na produkční DB auto-mode klasifikátor nepustil. **Musí spustit Robert přes `!`** (nebo botovi povolit). Ověřeno 2026-09-05: `api/.env` beze změny od 2026-09-03, rotace stále neproběhla. Zbývá i smazat `/root/.env.bak.1788412531` (živé heslo v plaintextu, stále na disku) a v Anthropic konzoli smazat mrtvý `ANTHROPIC_API_KEY` (řeší bot3). Přepis git historie se NEDĚLÁ (rozhodnuto). Oprava hardcoded hesla v sesterském `/opt/toscanaccio` už proběhla (viz Hotovo).



- **Produktové rendery přes Blender na vzdálené GPU** (bot8, 2026-09-09) - **ROZPRACOVÁNO**. Postup a kontrakt nově v `PRODUKTOVE_RENDERY.md` (odkaz z `CLAUDE.md` bod 7). Hotov rozpad úlohy (`scripts/2026-09-09_turntable_job.py`) + Blender renderer (`api/blender_render_turntable.py`), ověřeno reálným renderem sestavy 134. Zbývá: (1) typ úlohy `turntable` ve worker protokolu (`api/render_worker.py` + `scripts/render_worker_agent.py`, analogicky k `job_type="blend"`), (2) ~~automatický upload do `/turntable/frames` + `/commit`~~ **HOTOVO 2026-09-11 (bot8, commit `3adf36f6`)** — `api/turntable_ingest.py`, volá ho `render_worker` po rozbalení ZIPu; přední azimut musí nést manifest (nedosazuje se), stav úlohy nese `ingest_ok`, (3) Robertova šablona `.blend` z VPS Blenderu (`TT_FLOOR`, `TT_ALU`/`TT_ZINC`/`TT_BLACK`/`TT_GUMA`/`TT_PLAST`), (4) **automatické umístění ochranného loga** (dnes ručně na 1 sestavě z 264) + čitelnost reliéfu při plochém světle, (5) dávkové projetí 118 sestav.

  **Stav GPU stanice k 2026-09-10: HOTOVO** - agent běží jako služba Windows
  (`LogimanRenderAgent`, NSSM), naběhne sám po zapnutí stroje, úlohu vyzvedne
  bez čekání, výsledek doručí, `cancelled` respektuje. Ovladač povýšen
  560.94 → 616.92 (CUDA 12.6 → 13.4), čímž se odblokoval OptiX
  (`OPTIX_ERROR_INTERNAL_COMPILER_ERROR`). Naměřeno na 1 stillu 2048×1536
  sestavy 134: **CUDA 110 s** (starý ovladač), **OptiX 164 s / 160 s** - OptiX
  je tu ~45 % POMALEJŠÍ, ne rychlejší; CUDA je potřeba přeměřit na novém
  ovladači, než se backend zvolí natvrdo.

  **Razítkovač loga - ZPŘESNĚNÍ ZADÁNÍ (Robert, 2026-09-10): pod razítkem se
  musí zároveň VYPLNIT PROSTOR DRÁŽKY (slotu).** Doloženo na renderu sestavy
  134: logo `logo_logiman_cz` (4 ks, role `logo-ochrana-0..3`, ručně vložené)
  leží přes otevřenou T-drážku profilu, takže se reliéf písmen v místě slotu
  propadá a text se láme napůl. Razítkovač tedy není jen "umísti logo na
  plochu", ale **dvojice: výplň drážky pod otiskem + logo na ní**.

  **Zbývá ověřit před dávkovým během** (bot3, 2026-09-10, čtením kódu):
  jedna sada = 86 skutečných renderů (81 prstenců + 5 stills; tier 1024 se
  dopočítá zmenšením v `_downscale`, nerenderuje se). Odhad ~5 h na OptiX /
  ~3,5 h na CUDA - ODHAD z jednoho snímku, ne měření. Dozorce dlouhý běh
  neshodí (agent tluče progress á 15 s, `WORKER_STALE_RUNNING_S` = 1200 s).
  Rizika: (a) **po pádu se nenavazuje** - spadne-li to u 80. snímku, celá
  dávka je pryč; (b) při vypnutém PC si sadu vezme `prevzit_opustenou_ulohu()`
  na serverové CPU, kde by 86 snímků běželo dny a blokovalo frontu;
  (c) nikdy neběželo dýl než 3 min, takže chování Blenderu při 86 renderech
  v jednom procesu na 8GB kartě a upload celé dávky jsou neověřené.
- **Karoserie 180° flip** (Robert 2026-09-02, nástroje bot22/bot8 2026-09-05) - pilot CI18 hotov a živý (commit `44db286`, nástroje `5fb3c30`), **čeká na Robertovo vizuální potvrzení ve scéně**, pak spustit `--all` na zbylých 189 `NEEDS_FLIP` z 304 modelů; 5 zbylých Jumpy sestav (181,183,185,186,188) má hotový cílový stav už předpočítaný v `backups/2026-09-03_car_body_jumpy_l1_l3_crew_180_flip/assemblies_post/`, zbývá zapsat + přerenderovat 2D/turntable. (Turntable/otočný náhled samotný je hotový, viz Hotovo.)
- **Grid vzhled karoserie jen na CI26** (Robert 2x 2026-09-02) - default OFF hotový (`18ad72d`), zbytek **NETKNUTO** (ověřeno v kódu 2026-09-05): `applyCarBodyGridMaterials()` v `webapp/js/scene/hdri-panels-ui.js:3354` pořád bez podmínky na CI26, persistence `localStorage.konfCarBodyGrid` (ř.3824+3828-3836) pořád nutná odstranit. Potřeba zámek na `webapp/*`.

- **Eurobox pipeline třída 3 "Y-offset regrese"** (VW31/32, regál by "letěl" ~1650mm nad podlahou) - kořenová příčina: `tmp_2026-08-31_batch_engine.js::createEngine()` a `tmp_2026-09-01_bot16_env_factory.js::makeEnv()` nenormalizují raw GLB Y-bbox před kolizním krokováním, takže karoserie s neobvyklým raw počátkem (VW31/32: 1641-2881mm) by dostaly pozice počítané v syrové, ne floor=0 souřadnici. Bezpečná oprava vyžaduje současně upravit i zápis `car_body_*` dílu (dnes vždy identity `position=[0,0,0]`) - riziko rozbití 17/22 už fungujících vozidel bez ověření na celém katalogu (304 karoserií), proto NEOPRAVENO narychlo. Okamžitá pojistka (`assertSaneRackYPositions()`, throw mimo `[-500,2500]`mm) už je ve 3 zápisových cestách, takže žádná další tichá špatná data neprojdou. **Čeká na Robertovo rozhodnutí** (bot27, zapsáno 2026-09-03) - beze změny podle AGENTS_LOG dodnes (ověřeno 2026-09-05, doplňuje `bot26`'s audit dat níže; opravu 5 z 6 tříd chyb viz Hotovo).

- **Audit tříd chyb eurobox regálů - zbývající otevřené body** (bot26 a návazní boti, 2026-09-03 až 09-05):
  1. **Třída 6, `id=59/60/63/64` (Proace)** - Robertův pokyn "170mm" nejde splnit beze ztráty patra (varianty A/B dají 170mm nahoře, ale jen 8 boxů místo 11; varianta C udrží 11 boxů, ale jen 2 distinct výšky). Podklad hotov (`backups/2026-09-05_TO21_varianty_ABC/`, commit `0a92b17`), DB nezměněna. **Čeká na Robertovo rozhodnutí.**
  2. **Třída 5, `id=176/178`** - mají jen JEDNU výšku boxů (ne dvě, jak se dřív myslelo). Rozhodnutí stojí mezi ponecháním jedné výšky nebo smazáním (jako už u `id=172/174/180`). **Čeká na Roberta**, netknuto.
  3. **Třída 4, 48 kandidátů** - oprava stále NEZADÁNA. Navíc zjištěna vada zdrojového auditu (`2026-09-03_class4_doorvoid_audit.js` testuje napevno jen `_R_D.glb`, ignoruje skutečnou stěnu regálu) - na Jumpy dala 6/8 falešných pozitivů. Seznam je nutné před jakoukoli opravou přepočítat s kontrolou správné stěny (ideálně raycast ground-truth).
  4. **Třídy 2 (noha v podlahovém hrbu) a 3 (box neseřazený s příčkami)** - celokatalogový sken (~110 zbývajících řádků) dosud neproběhl. **Nezadáno, čeká na volného bota.**
  5. Vedlejší: existující (nezměněné) sloupce s nevyužitou výškovou rezervou vůči nově dohledané oficiální výšce dveří (RE28/RE29 +70mm, FO11 +32mm, FO21 výrazný rozdíl) - samostatné rozhodnutí, neaplikováno. CI24 door-height zůstává `NULL` (nedohledatelný zdroj).

  Detail všech bodů a historie auditu: `KOMPONENTY_EUROBOXY.md` sekce "Celokatalogový audit tříd chyb 1-6", `AGENTS_LOG.md`. Hotové dílčí kroky (třída 1 fix, door-height backfill) viz Hotovo.


- **Audit zbylých ~113 eurobox regálů - noha v otvoru bočních dveří** (bot16→bot26→bot28, 2026-09-01/03) - OPEN, beze změny od zápisu (ověřeno grep AGENTS_LOG.md + git log, žádná navazující práce nenalezena). Zdrojový kód pipeline už opraven (viz Hotovo). Zbývá: (1) **klíčové** - bot26's seznam 48 kandidátů testoval napevno jen `_R_D.glb` bez ohledu na to, proti které stěně regál skutečně stojí; bot28 na Jumpy vzorku ukázal 0/8 skutečných porušení ze 6 nahlášených (raycast ground-truth) - seznam se MUSÍ přepočítat s kontrolou správné stěny (+ideálně raycast) dřív, než se z něj cokoli opraví. (2) Samotná datová oprava potvrzených případů zůstává nezadaná. (3) `planColumn()` v `tmp_2026-08-31_batch_pipeline.js` pořád nepoužívá efektivní strop `min(TOP_Y,physCeil)` pro všechna patra, jen pro poslední (ověřeno čtením kódu) - riziko pro budoucí vozidla s nízkým `physCeil`.

- **Robertovo vizuální potvrzení ve scéně - FO31/VW25 po opravě dveřního otvoru** (bot16, 2026-09-02) - **ČEKÁ NA ROBERTA**, beze změny k 2026-09-05. 10 přestavěných řádků (`product_assemblies.id=111/153/154/175/176/118/155/156/177/178`) prošlo kompletní numerickou verifikací (kolize/self-kolize/sanity/fresh-read), ale žádný z nich ještě nemá Robertovo vizuální potvrzení ve scéně (skill `3d-scena-spoje` bod 8). 2D artefakt: https://claude.ai/code/artifact/71736625-e0ae-47cd-9630-4894fc6ccaf9. (Podezření na zaboření nohy `id=111` do podběhu prošetřeno a vyvráceno - viz Hotovo.) Riziko: zapisující skript `scripts/2026-09-05_fix_fo31_111_noha.js` zůstává untracked a stojí na nespolehlivé metodě - kdokoli ho spustí naslepo, poškodí sestavu.


- **Mini-eshopy per model auta - Fiat, zbývající dodělávky** (bot14, 2026-08-30; ověřeno beze změny 2026-09-05) - `fiat-autovestavby.top` (hub + ducato./doblo./scudo. subdomény, 22 variant) živé od 2026-08-30, viz `AGENTS_LOG.md`. Zbývá, vše potvrzeno stále otevřené:
  1. **2 Cloudflare dashboard kroky** (SSL mód Full/strict + AOP enable, jen dashboard, ne API - postup v `PRISTUPY.md`) - weby fungují i bez nich. **Rozsah narostl**: od 2026-09-01 přibyly 3 další zóny (fiat-{ducato,doblo,scudo}-vestavby.top), které potřebují stejné 2 kroky navíc.
  2. Ostatní značky mimo Fiat (stejný postup/kód, jen DB řádky + subdomény + obsah) - nezapočato.
  3. 3-5 dalších vizuálně odlišných šablon PRO PŮVODNÍ subdomény (ducato./doblo./scudo.fiat-autovestavby.top pořád jen 1 vzhled) - pozor, nezaměňovat s nesouvisejícími `-solo.html` šablonami z 2026-09-01, ty patří k jiným (standalone) doménám.
  4. Product_assemblies/sestavy pro žádnou z 22 Fiat variant pořád neexistují (produktový grid = "kontaktujte nás") - samostatný větší úkol (3D umístění sestav do karoserií).
  5. `fiat-autovestavby.top` parkovací vhost (port 8095) - živě ověřeno 2026-09-05, pořád enabled a odpovídá HTTP 200, stále nepoužívaný pozůstatek čekající na úklid - nekonfliktuje, jen zbytečný.


- **SLEDOVAT: neshody mezi přijatou platbou a `total_czk` u spárovaných objednávek** (Robert, 2026-08-22 – trvalý sledovací bod, ne jednorázový úkol). Po revertu chybné DPH diagnózy (viz AGENTS_LOG ř. 12937-13174) mělo 8 z prvních 25 spárovaných objednávek genuinní neshodu (tabulka tamtéž) – 4 z nich vypadaly na částečné/zálohové platby. Bot14 2026-09-03 (`bank_statements.py`, "bod 10 varianta b") od teď takové částečné platby vůbec neoznačí jako `bank_paid`, což by mělo tenhle typ falešné neshody do budoucna odstranit. Zbývá dál sbírat nové případy z běžícího párování a vyhodnotit, jestli u zbylých (nečástečných) neshod jde o systémový vzorec – nikdo to zatím nevyhodnotil.

- **Sledovat neshody částky u spárovaných bankovních plateb (běžící evidence, ne bug)** (Robert přes bot3, od 2026-08-22, PRŮBĚŽNÉ, bez vlastníka) - domnělý nález o podfakturování DPH byl omyl a revertován (viz AGENTS_LOG.md 2026-08-22 "OMYL, REVERT"); `match_bank_payments_to_orders()` teď porovnává platbu přímo s `total_czk`, neshody jen zapisuje do `amount_warnings`, nic neblokuje. Aktuální stav: 8 z 25 spárovaných objednávek má neshodu (tabulka v AGENTS_LOG.md 2026-08-22) - vypadá na jednorázové částečné platby/úpravy dopravy, ne systémový vzorec. Čeká se, jestli se objeví OPAKOVANÝ vzorec napříč více objednávkami (signál ke znovuotevření) - dosud (k 2026-09-05) žádný další případ nezaznamenán. Kdokoli další neshodu zaznamená, doplní ji do AGENTS_LOG.md.

- **Sjednocení Podpora/E-maily - zbytek volitelný** (bot3/bot10, 2026-08-22) - etapy 1-2 HOTOVO (viz Hotovo, commit `1b338de`). Zbývá jen: Etapa 3 (přejmenovat 5 DB tabulek `shop_support_*`/`support_email_triage_*` + všechny SQL dotazy, co je referencují) a Etapa 4 (přejmenovat `api/support.py`, mění import chain) - obě čistě volitelné, klidně přeskočit natrvalo. JS identifikátory v `admin.html` a triage hodnota `'podpora'` jsou vědomě mimo rozsah (jiná osa - klasifikace emailu, ne RBAC).

- **Řemeslo - Srovnávač: match_groups - rozšíření na další kategorie** - BLOCKED_ON_ROBERT (konzervativní vs. shovívavější párování, produktové rozhodnutí). Pilotní skript umí `--category-id N`/`--all`, ale `CATEGORY_RULES` má vyplněnou jen kategorii 3 (PPR trubky) - žádná další kategorie od 2026-08-20 nepřibyla (ověřeno git historií souboru i k 2026-09-05). bot11 byl k úkolu přiřazen, ale nepokročil (jiné priority). Čeká na Roberta.

- **Řemeslo - Kalkulace → Zakázka: chybějící převod** (bot10, 2026-08-20, ověřeno stále platné 2026-09-05) - `POST /api/remeslo/jobs` (`api/remeslo.py:2285-2328`) pořád nemá `calculation_id`/import položek, žádné tlačítko "založit zakázku z kalkulace" (na rozdíl od Nabídky a Faktury, které tenhle mechanismus mají). Vyžaduje Robertovo rozhodnutí o rozsahu (co z kalkulace do zakázky předvyplnit) - **čeká na Roberta**, žádný bot bez tohohle rozhodnutí nesmí sám navrhnout implementaci.


- **Řemeslo - zakázka: `price_czk` se nikdy automaticky nepřevezme z nabídky/faktury** (bot11, 2026-08-20, potvrzeno bot9 2026-08-22) - na rozdíl od `costs_czk` (auto-součet z materiálu/práce) nemá `price_czk` žádný ekvivalentní zdroj, zůstává jen na ručním přepsání řemeslníkem (bez něj se zakázka vůbec nezapočítá do KPI dashboardu). Čeká na Robertovo rozhodnutí, KTERÝ dokument (nabídka při přijetí? faktura při vystavení/zaplacení? víc faktur na jednu zakázku?) by měl `price_czk` nastavovat, nebo jestli má cenu vždy ručně potvrzovat řemeslník. Beze změny od zápisu. Detaily: `AGENTS_LOG.md` "bot11 — Hloubková kontrola, DRUHÁ VRSTVA".

- **Řemeslo - Pokrytí Srovnávače vs. reálná potřeba instalatéra (Modul 1)** (Robert 2026-08-20) - zjišťovací úkol HOTOVÝ (bot11), plný rozbor + tabulka v `AGENTS_LOG.md` "bot11 — Pokrytí Srovnávače vs. reálná potřeba běžného instalatéra". Výsledek: z 36 typických položek jen 15 (42 %) plnohodnotně srovnáno, 3 chybí úplně (komínová vložka/kouřovod, rozdělovač podlahového topení, systémová deska). **Čeká jen na Robertovo rozhodnutí, co dál (doplnit/opravit katalog) - dosud beze změny, znovu potvrzeno auditem bot10 2026-08-22.**

- **INFRA: gunicorn `--workers 2` → `4`** (bot14, 2026-08-20) - **ČEKÁ NA ROBERTA**, beze změny (ověřeno živě 2026-09-05: service soubor stále `--workers 2`). Analýza hotová: live měření ukázalo 2× zpomalení při 3 souběžných požadavcích Srovnávače kvůli frontě na uvolnění workeru; navýšení na 4 je bezpečné (RAM ~9,2 GB volných, MySQL `max_connections=10000`/186 využitých). Úprava `/etc/systemd/system/konfigurator.service` (mimo git, vyžaduje sudo) je mimo dosah bota - klasifikátor auto módu zásah blokuje. Zbývá jen: Robert/člověk provede `--workers 2` → `4` v `ExecStart`, pak `systemctl daemon-reload && systemctl restart konfigurator`.

> **STOP - kalkulačky (Robert, 2026-08-20):** "kalkulačky bych nechal
> být, řemeslník pošle podklady, jak to dělá, a my mu to přizpůsobíme,
> tzn. až potom." Veškerá další práce na `_calc_*` funkcích/UI polích
> kalkulaček (retrofit odvození/zdroje, nová pole, rozšiřování počtu
> položek) se ODKLÁDÁ, dokud nedodá skutečný řemeslník reálné podklady
> o svém postupu - nemá smysl dál ladit naslepo. Neplatí pro
> Betonáž-pilot a "Vlastní položky navíc" infrastrukturu (ta je HOTOVÁ
> a odevzdaná, viz níže v Hotovo) - týká se ROZŠIŘOVÁNÍ obsahu/položek
> jednotlivých kalkulaček. Otevřené položky níže (UI pole, rozšíření
> profesí) zůstávají zapsané pro budoucí kolo, ale NEZAČÍNEJ na nich,
> dokud Robert kalkulačky znovu neotevře.



- **Kalkulačky: rozšířit zbývajících 11 profesí** (Robert 2026-08-20) - **BLOKOVÁNO na Robertovi.** Noc 2026-08-19/20 (bot10/11/13/14) fakticky prošla/rozšířila VŠECHNY dotčené kalkulačky: zdění, voda/topení, malování, zámková dlažba, obklady a dlažby, podlahy, sádrokarton, fasáda a zateplení dostaly nové položky (commity `e73fb06`, `a7b19df`, `860a4c5`, `713fce4`, `9c79326`, `a7d7cf0`, `53a4772`, `30c23a3`, `e7e5b6e`, `4fc1c41`, `b690fa4`, UI pole `e5e5e87`/`63210e7`); betonáž/zemní práce/pergoly/elektroinstalace/střechy potvrzeny hotové jinde v Hotovo; zdění a zemní práce prošly adversariálním research-workflow beze změny (žádný další kandidát neobstál). Živě přeověřeno bot14 (AGENTS_LOG "AUDIT ÚPLNOSTI všech 14 kalkulaček"). V 08:33 téhož dne ale Robert vydal STOP ("kalkulačky bych nechal být, řemeslník pošle podklady, jak to dělá") - žádné DALŠÍ rozšiřování položek se nemá dělat, dokud nedodá reálné podklady od řemeslníka a kalkulačky znovu neotevře (viz STOP box nahoře v TASKS.md). Bot10 audit 2026-08-22 tuto položku vědomě ponechal otevřenou jako placeholder ze stejného důvodu. Beze změny k 2026-09-05 - čeká čistě na Robertovo rozhodnutí/podklady, ne na bota.


- **Řemeslo - self-service CRM (Modul 3, `api/crm.py`) pro roli `remeslnik`** - vlastník zatím nepřiřazen, čeká na Robertovo/bot3 produktové rozhodnutí "má řemeslník vidět leady, které mu admin přiřadil?" (`craftsman_id` na `crm_leads` je jen volitelný štítek, ne vlastnictví záznamu, takže nejde o mechanickou konverzi jako zbytek Modulu 11 - ten už je hotový, viz Hotovo). Potvrzeno beze změny auditem bot10 2026-08-22 i opětovnou kontrolou 2026-09-05. Admin akce Ověřování (`/verification/manual`) a správa cizích řemeslníků zůstávají ZÁMĚRNĚ admin-only natrvalo (REMESLO_KONCEPT.md Modul 4 zásada 1) - to není otevřená otázka.

- **3D scéna - automatické napojování profilů a příslušenství** (WORKFLOW.md bod 11) - trvalý mandát "ověřit VŠECHNY automatické funkce a poznat všechny spojky/díly" **nekončí, dokud Robert výslovně neřekne konec** - žádný takový souhlas dosud nezaznamenán, práce pokračuje (role Scéna mezitím přešla z bot8 na bot22, viz log 2026-09-05 "Úhelníky na spoje noh všech sestav"). Zbývá i dílčí bod ze stavu 2026-08-20: **levý díl z Robertova screenshotu** (SKU zatím neznámé) čeká, až Robert označí zelené plochy - beze změny od zápisu.

- **Řemeslo modul 1 - zbývá**: (1) autentizovaný live UI test K&V Elektro přes `/api/remeslo/compare` dosud NEPROVEDEN (jen DB-úroveň ověřena) - stačí rychlý průchod v UI; (2) 3 osamocené DEK.cz řádky ve staré kategorii id=3 "PPR trubky a tvarovky" - úklid (`DELETE ... category_id=3 AND source_id=7`) blokuje permission classifier, čistě kosmetické, nefunkční dopad; (3) propojení cen ze srovnávače (`remeslo_material_prices`) do Ceníku Modul 9 (`remeslo_pricelist_items`, odkud kalkulačky reálně čtou Kč) zůstává SAMOSTATNÝ, dosud nikomu nezadaný navazující úkol. Cílový počet ~10 dodavatelů zůstává na 9 beze změny od 2026-08-21.

- **Řemeslo - Cena na vyžádání: asynchronní obnova na pozadí** - **POZOR, skript už NENÍ v tomhle repu** (bot3, 2026-09-09): přenesen do `/opt/remeslo/scripts/2026-09-05_remeslo_price_background_refresh.py` (tam commit `646fd0a`) v rámci dokončení separace Řemesla, z konfigurátoru smazán (`30bc02d3`) i s nepoužitým systemd unitem `remeslo-price-background-refresh.service` (`rm` + `daemon-reload`). Věcný stav beze změny: skript funkční a živě ověřený (`--dry-run`, 3398 kandidátů), **nasazení (systemd timer) dál odloženo Robertem/bot3 (2026-09-05)**, dokud Srovnávač cen jako celek není hotový. Dál se řeší v `/opt/remeslo`, ne tady. Samostatně mimo rozsah 1. iterace beze změny: dohledávání `product_url` při chybě extrakce.

- **Vynutit HTTP→HTTPS přesměrování na veřejném e-shopu**, jakmile bude
  vybraná finální doména a vystavený certifikát (viz SEO audit
  2026-08-03 - konkurence bott.cz/regaz.cz/do-dodavky.cz/alfavaria.cz/
  topcentrum.cz má HTTPS vynucené, my zatím ne, port 8090 je jen HTTP;
  8091 HTTPS je vyhrazený jen pro fotoaparát v adminu). Nejde nasadit
  teď - dokud doména neexistuje, nemá kam přesměrovat.

- **Platba kartou v online nabídce** - čeká na Roberta: založení účtu u platební brány (GoPay/Comgate/Stripe...) + získání API klíčů (žádná brána v projektu zatím neexistuje). QR platba bankovním převodem už funguje (bot6, 2026-08-05). Až budou klíče, napojit do `api/scene_offers.py` vedle QR.

- **Fotoapka: rozdělení naskenovaných dokladů na proudy hotově/kartou** do složek "přijaté doklady" v administraci - stále neimplementováno, čeká na Robertovo potvrzení (kontext viz sekce Hotovo, "skener dokladu V3", bot6, 2026-07-31).

- **Řemeslo - modul Kalkulačky + Ceník - formální uzavření** (Robert 2026-08-19, bot11) - kód/DB/testy jsou hotové (14 kalkulaček, Ceník s verzováním cen, revize, napojení na zakázku - viz Hotovo výše), zbývá jen: (1) aktualizovat hlavičku `REMESLO_KONCEPT.md` Modul 9 z „návrh, čeká na schválení", (2) jeden souhrnný „HOTOVO" zápis do `AGENTS_LOG.md`, protože bot10ův audit 2026-08-22 tuhle položku vědomě nechal otevřenou jen kvůli chybějícímu formálnímu verdiktu, ne kvůli chybějící funkčnosti.

- **Watchdog automat (production_work_claims) - `scripts/2026-09-06_backfill_bom_price.js` má natvrdo dané sdílené cesty v `/tmp`** (`KATALOG_DUMP`/`ASM_DUMP`/`OUT_DIR`), bez atomického zápisu (žádný `.tmp` + `os.rename`). Posouzeno bot4/bot3 2026-09-11 jako únosné - nejhorší dopad je selhání jednoho běhu automatu (skript narazí na částečně zapsaný soubor), ne tichá špatná cena - **není to blokátor zapnutí**, jen věc k doladění. Bot8 souhlasil opravu přidat, až se dostane zpátky k té části skriptu (vlastník `2026-09-06_backfill_bom_price.js`).

- **Vandr karta 4593 (`VD-52c208fe-6a7c-43d2-8fcf-e4dc705a6b0f`, Regálová vestavba Mercedes Sprinter L2H2) - je na PRAVOU stranu auta, čeká na přerenderování** (Robert, 2026-09-24, doslova: *„toto je na pravou stranu auta... musí se to deaktivovat a přerenderovat jako pravá strana až budeme dělat pravé strany auta"*). Karta je od 2026-09-24 **deaktivovaná** (bot3) a NESMÍ se aktivovat zpátky, dokud se nepřerenderuje se správnou orientací pro pravou stranu. Až přijde dávka pravých stran, tahle karta patří do ní. Souvisí s orientací render rigu (viz pravidlo o přední/zadní straně regálu).

- **ROZPRACOVÁNO (bot10, 2026-10-01): 3D scéna online nabídky - kóty, materiály a světlo jako
  na renderech, ovládání (pohledy/přiblížení/otáčení) a animace reálných pohybů (výsuv šuplíku,
  sklopení dvířek po odjištění pinu, vyzvednutí boxu).** Robert: zákazníkům místo odkazů na
  test.logiman.cz posílat online nabídku. Platí ochrana 3D modelů (stupeň 2: jen nabízená sestava,
  zploštělá jména uzlů). Soubory: `webapp/nabidka-online.html`, `api/vandr_scene_offers.py`.

- **ČEKÁ NA ROBERTŮV EXPORT FBX (bot10, 2026-10-01): Vandr #4366 (VW Crafter L3H3 FWD,
  levá+pravá v jednom modelu) - Robert 2026-09-30 rozhodl „rozdělit na 2 karty“.**
  Obě karty stran UŽ existují (shoda kusovníku, ceny a váhy): levá = #4368
  `VD-55677dd8-1d41-4a82-821e-7aad28d85511` (RL, 50 593 Kč), pravá = #4367
  `VD-7ece7ed2-1601-4374-94a3-2e87fe7705f0` (RP, 32 837 Kč); 4366 = jejich součet.
  Zbývá jen: Robert ve Vandr adminu vyexportuje FBX pro UUID 55677dd8… a 7ece7ed2…
  (NE 8db32bcb…), zbytek linky (GLB → razítka → render → aktivace) doběhne sám.
  4366 zůstává neaktivní; automat ji nezapne (pojistka `umisteni_id`, commit
  `902a5af6`), o archivaci rozhodne Robert. Stejný případ je ŽIVÁ #4917 (bez štítku):
  samostatné strany k exportu 0f5a99fc-4802-4f3e-b389-a9d43076ce27 (levá) a
  34bf55d7-562d-40c0-bac8-8a5edfd9e9ef (pravá); kartu smí stáhnout jen Robert (p. 54).
  Watcher kombinace stran už jako kartu nezakládá (commit `c7194e59`).

- **Vandr systém u nás - první komponenta (bot10, 2026-10-05, Robert „začneme postupně přetahovat vandr system k nám“ + „nemíchat Vandr s první větví“): STRUKTURA HOTOVÁ, čeká na rozhodnutí o prodejním toku.** Samostatný prostor mimo 1. větev: tabulky `vd_komponenty` / `vd_komponenty_dily`, `api/vandr_system.py` (cena podle rozměru), modely v chráněné `webapp/katalog/vandr/komponenty/` (nginx 401), SKU `VDK-<KÓD>` (nechytá se na `VD-%` automatů Vandru); postup + hranice `docs/VANDR_SYSTEM.md`, skripty `scripts/vandr_system/` (`pridej_komponentu.py`, `zaloz_kartu.py`, `test_vandr_system.py` 154 + `test_kontrola_komponenta.js` 44 kontrol; náhled s posuvníkem šířky: `/api/kontrola-scena?rezim=param&komponenta=kufrik-3x43-vysuv-d459`, jen zaměstnanci). První komponenta = natahovací výsuv `kufrik-3x43-vysuv-d459` (světlá šířka 359–1589 mm, 4 677,59 Kč při 967 mm, +1,328 Kč na mm; kontrolní scéna `rezim=param` zůstává), karta #4966 `VDK-KUFRIK-3X43-VYSUV-D459` NEAKTIVNÍ (bez kategorie, ceny a modelu). Robert 2026-10-05: komponenty se neprodávají samostatně, slouží generátorům → prodejní tok, kategorie a text karty se NEŘEŠÍ (karta #4966 je jen evidenční, zůstane neaktivní, aktivace jen Robert, p. 54). Zbývá: (a) další komponenty stejným postupem (pořadí určí Robert); (b) mechanická vhodnost nad 1357 mm (Vandr má pro 1357 variantu 4×43).

- **Kontrolní scéna s pohyby se staví sama (bot10, 2026-10-06, Robert „automatizovat bez zásahu ručně botem na každou FBX“): HOTOVO, trasa živě po nasazení API 0:00 (stránka už nasazená, do té doby záloha = staré soubory).** Řetěz FBX → karta → GLB → razítka → render → aktivace už běží sám (ověřeno na #4962–4965); 3D s pohyby pro online nabídku se staví při „Vytvořit online nabídku“ na kartě (~4–7 s, cache; ověřeno nanečisto na 7 kartách i jako www-data), kontrolní scéna `rezim=nabidka` si teď model staví sama přes `GET /api/kontrola-scena/v3d/<karta>.glb` (`docs/KONTRAKT_NABIDKA_3D.md` 5e). Otevřené: (a) Robert rozhodne o zapnutí neviditelného značení modelů v nabídkách (klíč `V3D_MARK_SECRET` + plný restart; dnes VYPNUTO, příkaz `docs/V3D_NABIDKA_NASAZENI.md`); (b) první ostrá nabídka z karty s 3D (zkusí Robert, od nasazení žádná nevznikla); (c) kombinace stran: 6 kombinací, 11 stran čeká na ruční export ve Vandru – lze automatizovat rozřezáním exportu kombinace, rozhodne Robert.

- **Počítadlo luxů (John v2) v generátoru stolu - HOTOVO a živě (bot10, 2026-10-05), zbývá drobnost:** revize textů tlačítka cs/en/sk (bot7; jsou v `webapp/js/stul-luxy.js`) a konfirmační běh kroku 19 `run_all.sh` (`test_stul_host.js`, trvá přes 40 min) nad finálním stavem; výpočet je orientační (svítící délka a fotometrie LED jsou hypotéza Johna).
  **Panel v3 (John, Robert schválil 2026-10-06 přes bot9): NASAZENO (bot10, 2026-10-06 ~22:15)** – horní slovní verdikt „Lze / Nelze“, dvě skupiny činností (13) s důvody, Požadováno / Máte, pomoc výkon/rozložení; tlačítko „přehled“ v souhrnu otevře panel i na mobilu (`lux-plugin.js`, `lux-data.js` blok `clearPanelTexts`, `lux.css`; piny v `stul-luxy.js` + stránky přes `stul_verze.py` / `miniweb_verze.py`). Výchozí stav zůstává VYPNUTO. Při převzetí opraven jediný řádek Johnova `lux.css`: vrátil globální `[hidden]{display:none!important}` (past z 2026-10-05 – přebije `hidden` na celé stránce generátoru) → zpět `.lux-overlay [hidden]`.

## Poznámky k rozdělení práce

OPRAVENO 2026-09-12 (audit bot9): tabulka rolí na tomhle místě
(naposledy "aktualizace 2026-08-18") byla zastaralá a odporovala si s
podobnou tabulkou ve `WORKFLOW.md` (2026-08-21) - obě smazány. Od
2026-09-12 existuje živý, DB-backed registr **Přehledy > Boti** v
adminu (`bots.specializace`, `/api/admin/bots`), kde se role zapisují
přímo - žádná markdown tabulka se dál neudržuje.

`bot1` zůstává vyhrazený na Robertově PC (mimo serverové schéma).
Zakládání/připojení nového serverového bota dělá Robert sám (autonomní
spouštění nové `claude` relace je bezpečnostně blokovaná akce, kterou
bot nesmí spustit sám) - detaily viz `SERVER_BOTS_SETUP.md`.

## QA oblast G — bezpečnost, otevřené

- **Čeká na Roberta:** rotace produkčního DB hesla (natvrdo ve starých
  skriptech) a `ANTHROPIC_API_KEY` z `PRISTUPY.md`.
- **Zbývá:** `pip-audit` ve `scripts/qa/.venv`, `npm audit`, ruční projití
  21 nálezů `SEC_SQL_INTERPOLATION_UNKNOWN_ORIGIN`.


- **[bot5] Mini-shop SK: košík a objednávka (fáze 3), 2026-10-03.** Kód nasazen (API po HUP), objednávky VYPNUTÉ (`miniweb_shops.orders_enabled=0`). Zbývá: (1) `bash scripts/nasad_cekajici_bot5.sh doklady` (DPH 0 % + doložka; znění k potvrzení účetní, přímé ano Roberta); (2) Robert doplní hmotnosti dílů stolu (4933 laminodeska počítat z plochy, 4930, 4931, 4929, 4932, 4928, 4916, 3025) a SK tarif Toptrans, do té doby doprava ke schválení ručně; (3) import nových právních textů bot7 (cf2532e3) a schválení Robertem + `miniweb_shop.py --slug packstations-sk --orders on --apply` JEDNOU dávkou (jinak by terms zmizely/neodpovídaly); (4) admin API Mini-shopy + RBAC `miniweb`/`miniweb_schvalovani` HOTOVÉ a otestované (17/17), sada `adminmw` čeká na nasazení po `doklady`, UI dělá bot16; (5) sitemap + FAQ do DB (bot7). README: `scripts/2026-10-03_miniweb_objednavky_testy/nasazeni/`.

- **[bot5] Mini-shop 2026-10-03 odpoledne:** SK shop živý s košíkem (orders_enabled=1). ČEKÁ: (1) DDL `sql/2026-10-03_miniweb_url_slug.py` (bot3) → `nasad_cekajici_bot5.sh slugy` → bot7 doplní `url_slug` do SK JSONu → import + schválení + ověření slug_alt (301 dělá web/bot16); (2) EN shop packing-tables.top je KONCEPT, chybí nginx vhost domény (bot16/Robert) → `miniweb_shop.py --slug packstations-en --go-live`; před EN košíkem importovat „Operator and orders“ (311a369b); (3) hmotnosti 7 dílů stolu (4930 4931 4929 4932 4928 4916 3025) → Toptrans se zapne sám; (4) test změny v `scripts/2026-10-02_miniweb_testy/test_miniweb.py` a `test_miniweb_admin.py` jsou rozdělané (čekají na nasazení sady slugy, commit dělá deploy skript).

- **[bot16] Uložit konfiguraci stolu (Robert 2026-10-05), kód HOTOVÝ a nasazený (statika živě, commit ba3be278), funkce VYPNUTÁ.** Zapnutí: (1) HOTOVO – API s modulem je nasazené od 5.10. 07:38 (probe vrací JSON 503 `unavailable`); (2) schválený text ochrany osobních údajů (e-mail, telefon, IČO; bot7/bot9); (3) bot3/Robert spustí `sql/2026-10-05_stul_ulozene_konfigurace.py` (jen CREATE TABLE IF NOT EXISTS, sám se nic nezapne dřív) → tlačítko „Uložit konfiguraci“ se objeví v embedu i v mini-shopech. Živé ověření po zapnutí = první skutečné uložení (testovací záznamy v produkci jsou zakázané), do té doby jen `probe` a testy nad dočasnými tabulkami. Detail: `docs/EMBED_STUL.md`.

- **[bot16] Systém 35 v UI: HOTOVO (commit dcf2a70c, 2026-10-05).** Zbývá mimo mě: schválení draftů mini-shopu Robertem (SK produkt 2 a 3, EN 1–3, kategorie 2/3; bot7), SK produkt 1 s opravou 1280 × 800 a montáží přes bot5 `--items`; serverová část `.multi3` (`api/miniweb_seo.py`) se nasadí s API 12:30 – ověřit až budou veřejné 3 produkty (`test_miniweb_multi.js`, bridge).

- **[bot16] Stránka ochrany osobních údajů hlavního webu (Robert 2026-10-05: „založit ochranu osobních údajů“) – kód HOTOVÝ a NASAZENÝ (API ručně 13:21, bot9 rozhodl); čeká na Robertovo schválení textu.** `api/legal_pages.py` + CZ `privacy` naimportován jako draft (`miniweb_documents` id 5; `terms` ne). Zveřejní se po Robertově schválení cs/privacy (bot7, `--items`); do té doby /ochrana-osobnich-udaju = 404 „Stranka nenalezena.“ (ověřeno živě). Nepřijde-li schválení do rána, napsat bot9 (skryje tlačítko Uložit na hlavním webu). Pak ověřit: `https://autovestavby.logiman.cz/ochrana-osobnich-udaju` 200, na anonymní doméně 404, odkaz u formuláře Uložit konfiguraci v embedu (HEAD probe, `test_pravni_stranky.py`). Do té doby běží formulář Uložit na hlavním webu bez odkazu na ochranu údajů (v mini-shopech odkaz je).

- **[bot16] Prvky generátorů STEJNÉ na všech místech (Robert 2026-10-05) – KÓD HOTOVÝ A ŽIVÝ, čeká OBSAH:** kóty, Hlavní profil a Připni cokoli mají interní stránky Generátor stolu 01–04, mini-shopy i iframe na logiman.cz (sdílený kód `pdc-layout.js` + modul voleb; nové prvky generátoru přidávat TAM, ne do jedné stránky; testy `scripts/2026-10-05_prvky_napric_testy/run_all.sh`). **Chybí obsah (John přes bot9, schvaluje Robert, pravidlo 60):** animace + schéma průřezu pro 35×35; krok „Spoj šroubem“ živě pro 30×30 (náhled `spoj-sroubem-v2`) a varianta 40×40 (SSE používá 40×40). Hotová varianta = záznam v `webapp/pripni-cokoli/texty.json` (`_profily`, `zive`) + model + schéma; stránky se nemění.

- **[bot5] Nabídka z konfigurace stolu - tlačítko „promítnout konfiguraci do online nabídky“ v KAŽDÉM generátoru 30/35/40/41 (Robert 2026-10-06, vedení bot5).** BACKEND HOTOVÝ (commity 9c422069, b8549968; `api/nabidka_z_konfigurace.py`, `POST /api/admin/konfigurace/nabidka`, sonda `GET`; kontrakt `docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md`; testy `scripts/2026-10-06_nabidka_z_konfigurace_testy/` 54/54), jen zaměstnanec s právem nabidky/vytvorit (Robert), snímek v `offer_options` bez DDL, 3D přes sanitizer, montáž % jako snímek, Toptrans 409 při neúplné hmotnosti, snímek konfigurace na řádek objednávky. ČEKÁ: (1) nasazení API (0:00 plánovaně; v `api/` nesmí zůstat necommitnutý soubor - dnes `vandr_scene_offers.py` rozdělaný bot10); (2) stránka `nabidka-online.html` větev „configurator“ (V3D, souhrn voleb, bez výkresů; kandidát z 2. 10. + test `scripts/2026-10-02_konfigurace_nabidka_testy/test_nabidka_konfigurace_stranka.js`) - bot5, po API; (3) tlačítko + dialog v sdíleném kódu generátorů - bot16 (UI za sondou, až endpoint odpoví 200); (4) hmotnosti dílů kat. 200 (Robert) - bez nich je Toptrans u konfigurací „cena individuálně“; (5) `v3d_glb.validate_spec` neumí `dims[].m` (bot10, nepovinné; teď se odebírá). Starší sada `scripts/2026-10-02_konfigurace_nabidka_testy/` (DDL varianta) NAHRAZENA, viz NAHRAZENO.md.
- **[bot16] Nabídka z konfigurace - UI tlačítko „Do online nabídky“ HOTOVÉ a nasazené (2026-10-06; bod 3 záznamu bot5 výše).** Sdílený modul `webapp/js/stul-nabidka.js` + napojení `stul-host.js` v okně „Cena a scéna“ všech 4 generátorů (30/35/40/41), jen zaměstnanec; tlačítko se ukáže až po sondě `GET /api/admin/konfigurace/nabidka` = 200, takže naskočí samo po nasazení API (0:00), do té doby je skryté. Testy `scripts/2026-10-06_nabidka_tlacitko_testy/` (UI + kontrakt se skutečným backendem bez zápisu). ZBÝVÁ: po 0:00 ověřit u přihlášeného zaměstnance, že se tlačítko ukáže a dialog otevře; zkušební nabídku v ostré DB NEVYTVÁŘET (každá je skutečná) - první skutečné vytvoření ověří zaměstnanec při reálné nabídce (bot5/Robert). **VÝKRESY (Robert přes bot5/bot8 2026-10-06, commit 402be009, živě):** po úspěšném vytvoření (201) se do záložky otevřené při kliknutí načte `/scene.html?stul=<query>&nabidka_vykresy=<id nabídky>` (query = `StulDoSceny.dotaz()`, stejný řetězec jako „Vložit do Scény“, zakódovaný; id jen číslice), Scéna (bot8) sama vyrobí kótované výkresy + 2× 3D a pošle je na `POST /api/admin/konfigurace/nabidka/<id>/vykresy`; dialog ukáže „Výkresy ve Scéně ↗“ a větu „Výkresy s kótami se dokončují ve Scéně (nová záložka)“, zákaznická stránka zůstává jako odkaz. Blokátor oken → varování + odkaz; neplatné id nabídky → záložka rovnou na stránku nabídky; stůl SSE (systém 41) se do Scény nevkládá (`bezSceny`) → bez výkresů + věta. Jen zaměstnanec (scéna je za staff bránou), do veřejného embedu/mini-shopu se odkaz nedává. UI test `test_nabidka_tlacitko.js` 101 + sekce E 7 kontrol (nová sekce E: blokátor oken, neplatné id, SSE, zakódování query); ověření skutečným vytvořením nabídky + uložením výkresů zbývá zaměstnanci při reálné nabídce.
- **[bot16] Sloučení kategorií Ducato / Jumper / Boxer - HOTOVO a živě (2026-10-06; Robert spustil `--apply`, záloha `backups/2026-10-06_slouceni_ducato_jumper_boxer_pred_zmenou.json`, vrácení `--rollback`).** Kat. 233 `/vestavby-pro-ducato-jumper-boxer` je ve stromu „Vestavby podle vozidla“ (dlaždice se 3 logy Fiat/Citroën/Peugeot, SSR i klient), 116 sestav Vandr (14 aktivních, `active` beze změny) je primárně v 233 a sekundárně ve značkových 268/269/288 (stránka Fiat je dál ukazuje), kat. 300 je smazána, 301 `vestavby-pro-fiat-ducato` → 233, texty bez odkazu na starou adresu (bot7), watcher bot5 dává nové karty Ducato/Jumper/Boxer do 233. Ověřeno živě v Chromiu (3 loga, 14 karet, drobečky, 301, bez chyb JS).
- **[bot16] Online nabídka - banner „Celková cena (bez DPH)“: popisek i cena zelené, stejné písmo, jeden řádek - HOTOVO a živě (2026-10-06, commit b16bab0f; Robert: „je matoucí, zda je zelená cena bez DPH“).** `webapp/nabidka-online.html`: první řádek = popisek + hlavní cena (mono 900, zelená, společná velikost `--tb-size`), pod ním tlumeně rozpis a „k úhradě vč. DPH“; na telefonu se popisek zalomí „Celková cena“ / „(bez DPH)“. Test `scripts/2026-10-06_nabidka_cena_banner_testy/` 157/157, existující testy nabídky beze změny. Mimo rozsah: nabídka ze scény v PDF/HTML (`api/scene_offers.py`) má vlastní banner s oranžovou cenou.
- **[bot16] Online nabídka: zakreslování změn jako na webu (Vandr + stoly z generátoru) - KÓD HOTOVÝ A NASAZENÝ, živé s nasazením API (dnes 12:30; Robert 2026-10-07: „zakreslování změn komplet je na webu hotové, jen to přenést do online nabídky a to i pro stoly z generátoru“).** Stejný modul `webapp/js/image-markup.js` jako `product.html` (tužka, kroužek, škrtnout, šipka, text, barvy): `✏️ Zakreslit změnu` u každého výkresu / 3D náhledu / renderu a pod živým 3D prohlížečem (snímek pohledu), po „Hotovo“ formulář (popis + e-mail + telefon), víc pohledů najednou (max 6) → `POST /api/public/offers/<token>/markup-requests` (backend 9e02dfa3, `api/offer_markup_requests.py`) → CRM poptávka (source `offer_markup`) s obrázky ve Fotkách + poznámka u nabídky + 2 e-maily čekající na schválení. Zapíná se jen s příznakem `markup_requests` v API (nabídky z karty Vandr a z konfigurace stolu; ze scény zůstává starý štětec); u takových nabídek je starý štětec skrytý. Dokumentace `docs/NABIDKA_ZAKRESLENI_ZMEN.md`, testy stránka 32 + backend 95. **ZBÝVÁ po nasazení API:** otevřít klientský odkaz nabídky z Vandr karty / ze stolu, zakreslit, odeslat → poptávka v CRM, e-maily ve frontě (ostrou nabídku/poptávku kvůli testu nezakládat). Bonus: `OFFER_PAGE_KEYS` má `drawings_vandr` (dřív backend odmítal Dotaz/značky/statistiky ze stránky výkresů Vandr nabídky).
- **[bot16] Online nabídka: 2D výkresy z Vandru jsou velké - HOTOVO a živě (2026-10-07, commit 45f7edc9; Robert: „2D pohledy převedené z vandr systému jsou moc malé, chce to zvětšit“).** Karty výkresů na stránce `drawings_vandr` jsou pod sebou na plnou šířku (max 1600 px), výška podle obrázku, obrázek nejvýše tak vysoký, aby se vešel na obrazovku (u více výkresů o něco nižší, aby bylo pod prvním vidět okraj dalšího); viditelná šířka z 618 na ~1400 px (1920×1080). Tisk a nabídky ze scény beze změny. Test `scripts/2026-10-07_nabidka_vandr_vykresy_testy/` 89 kontrol.
- **[bot16] KÓTY VE VÝKRESECH STOLU V ONLINE NABÍDCE: bez duplicit a překryvů, využít volné místo - HOTOVO a živé (2026-10-07, nová volba `kotaAvoid`, commit 66cf9b87).** Robert (nabídka č. 126 z generátoru): „kóty se nesmí takto překrývat ani být příliš blízko“, „musí se umísťovat rozumně rovnoměrně“, „nad stolem nad deskou je spousta volného místa“. Jen výkresy ze stolu; nabídky ze scény beze změny (pixel po pixelu), `kotaAvoid: true` lze předat i jim na Robertovo slovo. Test `scripts/2026-10-07_koty_stul_testy/test_koty_stul.js` 56/56, `docs/NABIDKA_VYKRESY_ZE_STOLU.md`. Platí pro NOVĚ vytvořené výkresy; starou nabídku obnoví znovu otevřená adresa `scene.html?stul=…&nabidka_vykresy=<id>`.
- **[bot16] NÁZEV WEBU: „Hliníkový konstrukční stavebnicový systém s drážkami“ místo „… pro užitková vozidla“ - HOTOVO (2026-10-07, Robert přes bot9/bot7).** Logo, patička, titulky; API část (`<title>`, og, JSON-LD, předměty e-mailů) naskočí s plánovaným nasazením 0:00; na telefonu 360 px se název v hlavičce zalomí na 5 řádků místo 4 (snímek poslán Robertovi). Po nasazení API ověřit `curl -s https://autovestavby.logiman.cz/ | grep -c "konstrukční stavebnicový"` (title + og + JSON-LD).
- **[bot16] MINI-SHOP: EN 1:1 se SK + kopie v němčině a maďarštině (Robert 2026-10-07: „dodělat mini shop anglicky jedna ku jedné se slovenským, dále vytvořit další kopii shopu v němčině“ + „chceme taky maďarskou verzi“) - HOTOVO, všechny čtyři shopy ŽIVÉ s objednávkami (EN 12:55, DE + HU 13:25, objednávky DE/HU zapnul bot5 po Robertově „Ano, zapnout oba“), zbývá jen nasazení sad 342/342 v 0:00 (kontrola naplánovaná na 0:17).** Shopy: SK `baliace-stoly.top` #16, EN `packing-tables.top` #17, DE `packtische.top` #18 (DE, AT), HU `csomagoloasztalok.top` #19 (HU); hreflang mezi všemi (x-default = EN), jeden kombinovaný Origin CA certifikát, nginx vhosty (Robert, jeden řetězený příkaz), `miniweb_domena.py overit --origin` VŠE OK, živý kouřový test bez chyb JS. Role: texty/domény/SEO = bot7, DB/import/objednávky = bot5, schvalování = Robert/bot9, mechanismus + domény + nginx + testy + go-live = bot16. Postup `docs/MINISHOP_NOVY_JAZYK.md`, serverové jazykové sady `docs/jazyky/README.md`. **Vědomě přijaté riziko (Robert přes bot7):** DE a HU texty a právní dokumenty schváleny hned, bez právníka a bez nativní kontroly; německé Impressum nemá e-mail a jméno jednatele (zákonný požadavek § 5 DDG, Ekertv. 4. §, riziko Abmahnung/pokuty) - kdyby se Robert rozhodl doplnit, upraví bot7 dokument a bot5 ho revizí schválí. **Brány a kontroly (bot16):** `--go-live` kontroluje jazykovou úplnost včetně úplnosti serverové sady vůči kódu a varuje, když sada ještě není v běžícím API; `PATHS` de/hu, zalamování dlouhých slov `:lang(de|hu)`, jazyk dlaždice „Připni cokoli“ z `_aktivni`, plánované nasazení sleduje `api/jazyky/*.json`, x-default i na EN stránce; testy `scripts/2026-10-07_miniweb_jazyky_testy/` (cesty+vhost 30, název země 7, frontend sk/en/de/hu 106, podmínky go-live 26, SEO en/de/hu 66, dlaždice 38, nasazení 11) a `scripts/2026-10-07_jazyky_testy/test_jazyky.py` 97. **Do budoucna:** po každé změně textů/voleb generátoru (nová volba, hláška) znovu `api/venv/bin/python3 scripts/miniweb_jazyk_zdroj.py --lang de|hu` a doplnit sešity (bot7), jinak `miniweb_jazyk_parita.py` ukáže mezeru a u zákazníka se nová volba objeví anglicky; další jazyk = postup v `docs/MINISHOP_NOVY_JAZYK.md`.
- **[bot16] OVĚŘIT PŘIHLÁŠENÝM (2026-10-06):** API se nasadilo ručním reloadem v 21:07 (Robertův pokyn „nasadit hned“), cesty žijí (`/api/admin/konfigurace/nabidka` a `/api/admin/john/stav` anonymně 401). Zbývá jen vizuálně: (1) panel Přehledy → John (`admin.html#john`) ukazuje i živé „běží právě teď“ ze `systemctl` a v Role a oprávnění je sekce „Přehledy: Johnova práce“; (2) tlačítko „Do online nabídky“ se u přihlášeného zaměstnance ukáže v Generátorech stolu 01–04 (Ctrl+F5; zkušební nabídku v ostré DB NEVYTVÁŘET); (3) záložka Prodej → E-maily účetní (API je od 22:01 živé; adresy zatím nikdo nezadal, hák bota5 dává doklady jen do fronty `pending`, nic se neodesílá sám - ověřeno čtením DB a kódu). Testy: `scripts/2026-10-06_john_panel_testy/`, `scripts/2026-10-06_nabidka_tlacitko_testy/`.
- **[bot16] Admin: tabulka „E-maily účetní“ - kam posílat SCHVÁLENÉ doklady podle typu (Robert 2026-10-06: „chceme schválené doklady automaticky posílat na emaily účetní, budou to různé emaily podle typu dokladu, postav na to tabulku v adminu“), HOTOVÁ A NASAZENÁ (API načteno ručním reloadem 2026-10-06 22:01, Robert).** Záložka Prodej → „E-maily účetní“ (`admin/js/ucetni-emaily.js`) + `api/ucetni_emaily.py` (`app_settings` `ucetni_emaily`, bez DDL), RBAC sekce `ucetni_emaily` (jen admin, dokud Robert nezaškrtne). Testy `scripts/2026-10-06_ucetni_emaily_testy/`. **ODESÍLÁNÍ NENÍ ZAPOJENO, ROZHODNUTO (Robert 2026-10-06, volba v okně bot16): DO FRONTY KE SCHVÁLENÍ** - doklad se zařadí do „Emaily odchozí“ (`pending`) a odejde po Robertově schválení, pravidlo 16 platí beze změny (žádná výjimka). ČEKÁ: bot5 zapojí hák na schválení dokladu (`approvals.py` vydané, `incoming_documents.py` přijaté; adresy z `ucetni_emaily.prijemci(cur, typ)`) a po zapojení nastaví `ucetni_emaily.ODESILANI_ZAPOJENO = True` (čte se za běhu → v UI zmizí upozornění „Odesílání zatím není zapojené“).

- **[bot5] Online nabídka: montáž jen u aut + Vandr 2D jen přebírat + 2D u stolů (Robert 2026-10-06 „opravte to“, přes bot9).** (1) HOTOVO: montáž Praha/Slavičín jen u sestav do aut (ruční příznak NEBO Vandr nabídka), zvolená montáž vylučuje dopravu (QR/objednávka bez Toptransu, server 400 `montaz_doprava_vylouceno`, stránka skryje řádek Doprava); u stolů a ostatních jen informační řádek. Backend `22dc0d52` (čeká na nasazení API), stránka `b8f282c4` (živá). (3) HOTOVO v kódu: Vandr 2D se jen přebírá, bez Vandr výkresu nabídka BEZ stránky Výkresy (`offer_options.vandr_bez_vykresu`), společná nabídka vynechá stranu bez výkresu (1–3 výkresy); backend `ad4108f1` (čeká na nasazení API), stránka v `b8f282c4`; testy `scripts/2026-10-06_vandr_2d_jen_prevzit_testy/` + upravené bot10 `scripts/2026-10-02_v3d_testy/` (44/30/40). Stávající ostré nabídky s vyrobeným výkresem nejsou (jediná, #119, už neexistuje). (2) Stoly 2D kóty: endpoint `POST /api/admin/konfigurace/nabidka/<id>/vykresy` + stránka HOTOVÉ a živé; scéna `scene.html?stul=…&nabidka_vykresy=<offer_id>` HOTOVÁ (bot8 `a3bb9a40`); ČEKÁ bot16 (otevření scény po vytvoření nabídky) + ostré ověření na skutečné nabídce ze stolu. Zbývá: nasazení API (0:00 / ruční na pokyn Roberta), po něm ověřit na skutečné Vandr nabídce bez výkresu (starší karty id 4053…4604 ho nemají) a na nabídce ze stolu.

- **[bot5] Kontrola po nasazení 2026-10-07 00:10:** montáž jen auta (`22dc0d52`) a Vandr 2D jen přebírat (`ad4108f1`) ŽIVÉ; ostré nabídky #123 (Vandr, auto) a #124 (stůl, ne-auto) odpovídají pravidlům. ČEKÁ: (1) plánovaný běh #66 visí na cizím necommitnutém `api/v3d_vzhled.py` → `c2337c8e` (stav razítek v přehledu výroby Vandr) a formálně `27bec43c` nejsou nasazené; (2) 2D kóty stolu (#124 je nemá) – bot16 otevře `scene.html?stul=…&nabidka_vykresy=<id>` po vytvoření nabídky; (3) ostré ověření `vandr_bez_vykresu` na první skutečné Vandr nabídce z karty bez Vandr výkresu.

- **[bot8] Perforované panely 1481 / 1671 / 1975 mm v generátorech (Robert 2026-10-07: „integruj do generátorů další velikosti perforovaných panelů“; rozměry 1481 a 1671 upřesnil, 1975 × 460 „ten si musíš vyrobit“).** HOTOVO, ŽIVÉ a ověřené i veřejně (kontrakt `docs/KONTRAKT_KONFIGURATOR_UI.md`, sekce 2026-10-07; AGENTS_LOG bot8 2026-10-07); API (parametr `panely_delka`, slot `panellen`) běží od plánovaného nasazení 12:30. Karty **#4972 (1481 × 460), #4973 (1671 × 455 – výška podle modelu, Robert potvrdil), #4974 (1975 × 460)** jsou od 2026-10-07 AKTIVNÍ (Robert) s cenami 2 120 / 2 360 / 2 820 Kč bez DPH (moje orientační, beze změny); veřejnost (mini-shop, embed, e-shop) proto dostává všechny čtyři délky (kontrola veřejným resolve: stůl 2100 mm s panelem 1190 = 31 968 Kč, s 1975 = 33 122 Kč bez DPH). **ČEKÁ: bot7 – kontrola textů cs/en/sk (slot „Délka panelu“, důvody, oznámení o snížení délky) + překlad do dalších jazyků (nové klíče panellen*, hlášky PANELY_ZKRACENO, PANELLEN_NEVEJDE*, NENI_V_NABIDCE).** Nezahrnuto: rozdíl ceny rovnou v nabídce selectu, smíšené délky panelů v jednom stole.

- **[bot8] Příčky do Multiboxů v online nabídce Vandr (Robert 2026-10-07: „multiboxy mají možnost dělících příček … v online nabídce systém pro přiobjednání příček … ať jsou vidět ceny“; sety vždy pro celou polici / šuplík, HOTOVÉ MIXY místo klikání po boxech; max příček 4 / 6 / 8 podle délky boxu 288 / 395 / 500; jen příčné).** HOTOVO a otestováno (kontrakt `docs/KONTRAKT_NABIDKA_PRICKY.md`, testy `scripts/2026-10-07_multibox_pricky/run_all.sh`, AGENTS_LOG bot8 2026-10-07). Nasazení: statika (plugin, stránka) živá hned, `api/*.py` po restartu API (0:00 / 12:30 nebo `restart_konfigurator.sh --reload` na Robertovo slovo); **`scripts/v3d/vandr_offer_build.py` (detekce `mbx`) commitnout AŽ po nasazení API** (commitne bot8 po nasazení API) – do té doby nové Vandr nabídky příčky nemají. Karty `MBX-PRICKA-PRICNA-186|91` (dvě, neaktivní, bez kategorie, ORIENTAČNÍ ceny 39 / 29 Kč bez DPH, cena se bere ŽIVĚ z karty): **ČEKÁ: Robert – ceny + aktivace obou karet (pravidlo 54); do té doby sekci vidí jen admin přes „Zobrazit online“ u nové Vandr nabídky; bot7 – kontrola textů sekce a názvů karet.** **Příčky do ocelových ŠUPLÍKŮ (v5; Robert: „v šuplíku jsou sloty po 100 mm, směr jen zepředu dozadu“, jen ocelové s modrým čelem): HOTOVO v kódu, testech i kartách (kontrakt `docs/KONTRAKT_NABIDKA_PRICKY.md` oddíl 10) – 5 nových NEAKTIVNÍCH karet `SUP-PRICKA-PRICNA-<hloubka>x<výška>` (332×137, 332×210, 384×101, 384×137, 384×210; orientační ceny 59 / 79 / 59 / 69 / 89 Kč bez DPH). Skupiny šuplíků se nabízejí veřejnosti, až když mají aktivní karty všechny jejich díly (po skupinách, nezávisle na multiboxech). ČEKÁ: nasazení API (plánovaně 0:00 / 12:30 nebo `--reload` na Robertovo slovo), POTOM bot8 commitne Blender build (`scripts/v3d/vandr_offer_build.py` – detekce podnosů); Robert – ceny a aktivace karet (pravidlo 54).** Nezahrnuto: příčky v nabídkách z nativní scény (karty Multibox 3958 / 3959), výběr po jednotlivých boxech (Robert nechce), typ boxu 500 mm (délka je předpoklad).

- **[bot16] ONLINE NABÍDKA: PDF jako volba Stručné / Kompletní + montáž s místem (Praha / Slavičín) v PDF a v adminu + Vandr výkresy ve stručném PDF - HOTOVO a živé (statika 2026-10-07 18:57, commit 72dfa858; Robert: „PDF stažitelnou verzi dejme jako volbu i plnohodnotnou se vším komplet“, „zase tam chybí montáž KDE Praha/Slavičín“).** Tlačítko PDF → `#pdfMenu`, kompletní = `body.print-full` jen po dobu tisku. **API část (Volby klienta v adminu: ks + montáž + místo) a SLEVA (`offer_options.discount_pct`, pole v „Upravit nabídku“ se zapne až s příznakem `sleva`) ČEKAJÍ na nasazení API (0:00 / ruční reload) → OVĚŘIT po nasazení:** start workerů po mtime `api/scene_offers.py`, v „Upravit nabídku“ je pole Sleva, v detailu nabídky u zvolené montáže „Montáž – Slavičín“; u 0133 si Robert % slevy nastaví sám (nezadal). Vandr nabídka vzniká dvěma cestami (1 strana / z více stran) – úpravy ověřovat pro obě (`test_pdf_volba.js` scénáře vandr1 / vandrN). **OVĚŘENO po nasazení API (2026-10-08 00:25): workery od 00:00:14 (běh #75 ok), nad živým kódem sleva 21/21 a volby klienta v adminu 7/7, `pdfMenu` je v živé stránce nabídky.**

- **[bot16] ONLINE NABÍDKA: místo montáže (Praha / Slavičín) u sestav do aut (Vandr, obě cesty tvorby) je vidět HNED - HOTOVO a živé (2026-10-07 19:16, commit 3a67b089; Robert: „Vandr je do auta a co je do auta má montáž volitelnou v Praze / Slavičíně“).** Klik na místo montáž zapne, „Bez montáže“ místo zruší; test `test_montaz.js` 36/36.

- **[bot16] KATEGORIE #324 VÁLEČKOVÉ DOPRAVNÍKY: NÁHLED tabulky a štítků-filtrů - HOTOVO a živý (2026-10-07, commity 2f431753 / 8ea95e8e / 80d42e4e; Robert přes bot9: „štítky pro rychlé filtrování podle délky … desítky stejných obrázků“, „proč už nemají tu tabulku?“).** https://autovestavby.logiman.cz/nahled-tabulka/dopravniky-324.html (živá data `?include=specs`; Tabulka/Karty, štítky Délka / Šířka / Typ válečku, řazení, mobil, sdílitelné odkazy; texty zkontroloval bot7). **ČEKÁ na Robertovo „OK“ (relay bot9) → vložit do `webapp/category.html` (guarded) jen pro kategorie se specs: #324, pak #325 / #327 (druhý fetch `/api/shop/products?category_id=…&include=specs`); do té doby kategorie beze změny.** Testy `scripts/2026-10-07_kategorie_tabulka_testy/` (51 + 20 mutací). Generátor dopravníků dělá John.

- **[bot16] KATEGORIE #324 VÁLEČKOVÉ DOPRAVNÍKY: tabulka variant + štítky-filtry NASAZENA na ostrý web - HOTOVO (2026-10-07 19:53, commit 04b52344; Robert „Ano, nasadit“).** `/valeckove-dopravniky`: 78 variant v tabulce (typ válečku, Ø, šířka, délka, cena bez DPH / s DPH, Detail), štítky Délka / Šířka / Typ, řazení, Tabulka/Karty, mobil. **ČEKÁ na Robertovo slovo: #325 a #327** (přidat id do `KATEGORIE_TABULKA` v category.html po ověření specs). Náhled `nahled-tabulka/dopravniky-324.html` po potvrzení smazat.
- **[bot16] PŘÍKLADY REALIZACÍ: 4 reálné fotky + odkaz na fotogalerii u sestav do aut a stolů (karty, online nabídky, storefronty) - HOTOVO a živé (2026-10-07, commity 83203cb1 + 034c8a29; Robert: „v každé sestavě do aut i v online nabídce musí být ukázána reálná fotografie 4ks a odkaz na fotogalerie vestaveb, … stolů; ty 4 fotky se musí točit kolovat“; storefronty „Dej i s vodoznakem“).** Modul `webapp/js/realizace-foto.js` (výběr podle id karty / čísla nabídky + posun po týdnech; seznam `VYLOUCENE` = rendery a produktové snímky mimo „reálné fotografie“, údržba `scripts/2026-10-07_realizace_foto_testy/kontaktni_arch.py`), testy ve stejné složce (modul 30 / produkt 18 / nabídka 16 / storefront 13). OTEVŘENO: mini-shopy SK/EN/DE/HU blok nemají; galerie stolů má jen 21 veřejných fotek z 81 (Robert zatím neodpověděl, zda zveřejnit víc); storefronty zatím nemají zveřejněnou sestavu, blok na kartě poběží s první. Detail: `AGENTS_LOG.md` „PŘÍKLADY REALIZACÍ“.
- **[bot16] PŘEDÁNÍ 2026-10-07 večer – zbývá PDF z telefonu: (A) VĚTA O HOMOLOGACI v online nabídce aut – HOTOVO a živé (2026-10-07 21:57, commit a990fdf3: věta nad blokem fotek, na telefonu odsazená; příčina byla blok fotek, který ji na telefonu odsunul pod okraj); (B) „PDF ke stažení ořezává úvodní text“ – nezreprodukováno, stopa `table.items` min. šířka 423 px v tisku na telefonu.** Postup, soubory a pořadí kroků: `AGENTS_LOG.md` „PŘEDÁNÍ: věta o homologaci pod fotkami“ a paměť `project_homologace_veta_poradi_a_pdf_orez_rozpracovano`. Session-only crony 00:17 / 00:23 / 00:41 zanikly – API se slevou je živé od reloadu 21:22:12, ručně ověřit admin Slevu / Volby klienta, mini-shop DE/HU a zakreslení.
- **[bot16] ADMIN OBECNÉ → MONTÁŽ: tři sazby vedle sebe + „Uložit a přepočítat vše“ - HOTOVO a živé (2026-10-07, commity 84aff74e + f4c3573d, API nasazeno HUP 22:57 na Robertovo „Nasadit hned“; Robert přes bot9 + přímo).** Karty: „Vestavby – 1. větev“ (`montaz_pct`), „Vestavby – 2. větev (Vandr)“ (`vandrawee_montaz_pct`), „Stoly z generátoru“ (`stul_montaz_pct` přes stávající API); tlačítko přepočítá montáž uloženou na 530 kartách AUTO (mají 20 %, nastavení 12 %). OPRAVENO 23:10 po Robertově snímku: tlačítko přepočtu je jen u „Vestavby – 1. větev“ (u Vandr a Stolů jen Uložit); Robert přepočet spustil 23:04 (12 %) a 23:05 (15 %) – všech 530 karet AUTO má teď montáž při 15 %, ověřeno v DB, zálohy v `audit_log`; nic dalšího nečeká. Detail: `AGENTS_LOG.md` „Uložit a přepočítat vše“, paměť `project_montaz_prepocet_vsech_karet`.
- **[bot16/bot7] MINI-SHOP DE/HU: 69 nových serverových řetězců generátorů stolu čeká na překlad (nalezeno 2026-10-08 05:08, FYI od bot8; znění píše bot7).** Commity 87480305 (spodní police `shelfboard`), fe7213d4 (délka LED `ledlen*`), 110b03d3 + 5ac1c6bb (horní police `upshelf*`, vč. šikmé): `scripts/miniweb_jazyk_parita.py --lang de|hu --ref sk --bez-db` hlásí vrstvu „server“ MEZERA (chybí 69 položek `stul_shop.TEXTY.*`), ostatní vrstvy OK. Zdroj řetězců `api/venv/bin/python3 scripts/miniweb_jazyk_zdroj.py --lang de|hu`, doplnit do `api/jazyky/de.json` / `hu.json` + `docs/jazyky/…` (vzor commit ec462154); do reloadu API 12:30 ukazují DE/HU mini-shopy u nových voleb anglickou zálohu. Hotovo, až paritní skript vrátí „Mezer 0 z 14“ pro de i hu. bot7 upozorněn. **PŘELOŽENO (bot7, commit 9fa6dad8, 2026-10-08 05:12): ověřeno paritním skriptem pro de i hu = Mezer 0 z 14 (server OK, vyplněno 411 vůči 409 z kódu); do API jde plánovaným HUP 12:30, kontrola po nasazení je naplánovaná na 12:41 (session cron) – pokud session do té doby skončí, ověřit ručně: živé schéma `/api/shop/products/4934/configurator?lang=de|hu` má sloty shelfboard / upshelf / ledlen v němčině / maďarštině.** **NASAZENO a OVĚŘENO (2026-10-08 12:41): řetězce jely s reloadem API 09:47 (plán 12:30 se přeskočil – zámek bot8 / bot16 a necommitnutý `api/stul_shop.py` bot10; další plán 00:00); živé schéma `/api/shop/products/4934|4955/configurator?lang=de|hu` na packtische.top / csomagoloasztalok.top má německé / maďarské štítky slotů shelfboard, ledlen, upshelf*, paritní skript de i hu = Mezer 0 z 14 (437 položek).**
- **[bot8] Generátor stolu: svítidla LED jen ručně a posuvná podél profilu (Robert 2026-10-08: „svítidla v generátoru se přidávají automaticky za sebe podle délky, ale chceme aby se přidávala jen ručně a mohla se posouvat podél profilu“).** HOTOVO a NASAZENO (commit 47061e92, API živé od reloadu 2026-10-08 13:36 – ověřeno živým schématem #5353: sloty `ledcount`, `ledpos1…4`; testy 4445 + 266 + 29, zlatý otisk 873 konfigurací, mutace 109/111; kontrakt `docs/KONTRAKT_KONFIGURATOR_UI.md` sekce „Svítidla LED ručně“). Překlady de/hu hotové (bot7, commit cc041f83). Nově: výchozí 1 svítidlo i u širokých stolů (LED 1200 od 2447 mm, LED 600 od 1247 mm → výchozí cena o svítidlo nižší), slider počtu a poloh, ve 3D tah podél profilu + „Přidat / Odebrat svítidlo“. **ČEKÁ: Robert – zda nechat posuvník „Poloha svítidla LED 1“ i u jediného svítidla (zatím ponechán).**
- **[bot8] Generátor ochranného oplocení a krytování strojů z profilů 40×40 (Robert 2026-10-08, fotka klece kolem stroje) – POZASTAVENO, čeká na Robertovy informace.** Fáze 1 (jádro, 3D model, cena, 603 testů, 143 mutací, obrázky) je v repu `scripts/2026-10-08_oploceni/` (commit 01a0b56b), nic veřejného. Fáze 2 (shop vrstva, registr recept→modul, stránka, karty výplní) ~65 % hotová, záloha zdrojů `scripts/2026-10-08_oploceni/faze2_rozpracovano/` (`STAV_POZASTAVENO.md`). Robert 2026-10-08: „neschválil jsem ti zatím oplocení, musím k tomu dát ty informace“ → nic neaplikovat, karty nezakládat, dokud Robert informace nedodá a neschválí.
- **[bot16] GENERÁTOR STOLU SYSTÉM 45 NAPASOVANÝ NA KATEGORII 330 „Robustní balicí stůl system 45“ + KARTU #5353 - HOTOVO a živé (2026-10-08; Robert: „sem napasovat generátor stolu system 45“, adresa /robustni-balici-stul-system-45).** `category.html` CATEGORY_GENERATORS 330 → `/embed/stul.html?p=5353`, `product.html` PRODUCT_GENERATORS 5353, `api/stul_karta.py` výchozí kategorie karty systému 45 = 330 (API naběhne plánovaným reloadem); přepínač systémů z 30 / 35 / 40 sem teď vede (dřív tlačítko „45“ nic neudělalo); testy `scripts/2026-10-08_system45_kategorie_testy` (živě 16/16). **VYŘEŠENO (bot10, commit 927929f0, API nasazeno reloadem 13:36 na Robertovo „Nasadit hned“; ověřeno živě: resolve #5353 options.d 400..2500, #4954 / #4934 1500, v generátoru jde hloubka 2000 i 2500, test K13 17/17): dřív v e-shopové vrstvě nešla hloubka nad 1500 mm** - `resolve()` v `api/stul_shop.py` (~ř. 1721) bere `S.ROZSAH[par]` místo `S._rozsahy(system)`, takže `options.d.max = 1500` pro systém 45 (schéma má správně 2500); bot10 upozorněn 2026-10-08, kontrola K13 v testu (hloubka 2000 musí jít nastavit) po opravě projde.
- **[bot16] PŘÍKLADY REALIZACÍ: fotky se mění při KAŽDÉM načtení (F5) - HOTOVO a živé (2026-10-08 14:46; Robert přes bot9: „mají rotovat, ale když reloaduju F5 načtou se stále tytéž“).** Původní výběr byl stabilní podle karty a týdne; teď čítač `rf:n:<seed>` v localStorage posouvá okno o 4 fotky při každém načtení (bez opakování do projití celé galerie, ~30 načtení), v rámci stránky se nepřehazuje, bez localStorage náhodně; cache nic neblokovala. Ověřeno živě (3 načtení = 3 různé sady), testy modul 37 / karta 19 / nabídka 16 / storefront 13; použité jen už veřejné fotky (stoly dál 21 z 81 - Robertovo rozhodnutí).
- **[bot8] Razítka loga na VŠECH 3D modelech generátorů stolu (WORKFLOW pravidlo 61; Robert 2026-10-08: „razítka budou na všech 3D modelech ve všech generátorech“, přes bot9).** HOTOVO v repu (commit 3b7d5076): `stul_glb.model_pro_parametry(..., razitka=None)` má razítka VÝCHOZÍ (`RAZITKA_VYCHOZI = True`) → živý model `/api/shop/configurator/glb/<token>` (tedy i košík a odkaz na konfiguraci), nabídka, karta a staff `model.glb` nesou logo LOGIMAN.CZ u všech 5 systémů (30 / 35 / 40 / 41 SSE / 45; 2–19 razítek), `razitka=False` = holý model; pravidla umístění, `RULES_VERSION`, hash, cena a odpovědi API beze změny; vedlejší cache (úchyty ve 3D, luxy, živé tažení) společné, komprimovaná cache klíčovaná i délkou dat. Regrese bit po bitu 873 konfigurací + 90 odpovědí resolve 0 rozdílů, testy 298 + 220, mutace 12/12; váha +0,52 MB surově / +115 KB brotli, skládání +30–60 ms (`scripts/2026-10-08_razitka_generatory/`). **API se projeví při reloadu (0:00, nebo na Robertovo „nasadit hned“, reload pouští bot10). ČEKÁ: Robert – potvrdit na obrázcích před / po; logo se odvozuje z hashe, takže na živém modelu mění místo s každou změnou rozměru (pravidlo umístění beze změny) – nechat? Oplocení (pozastaveno) se razítkuje od prvního náhledu až po odblokování.**
- **[bot8] SSE se viditelně nejmenuje „systém 41“ (Robert přes bot9 2026-10-08: „tak mu neříkej 41 když je to SSE“) – HOTOVO v repu (commit 3f68f82a), statika živá hned.** Vnitřní klíč 41 (hash, SKU `STUL-S41-…`, RULES_VERSION, `stul_pravidla`) beze změny; přejmenováno: stránka generátoru 04 („Generátor stolu 04 – ergonomický stůl SSE“), odkaz přepínače, hlášky okna Pravidla stolu, info v kartách / nabídkách / Scéně, výrobní list (to až po reloadu API), dokumentace; DB a zákaznické texty (bot7 ověřil) „systém 41“ nemají. Test `scripts/2026-10-08_sse_nazev/`.
- **[bot8] Razítka při živém tažení se hýbou s dílem (Robert 2026-10-08: „razítka na generátoru při tažení zůstávají na místě“) – HOTOVO v repu (commit e45888a3): JS (`v3d-ovladani.js` 1.2.0) živý hned, popis razítek v API (`vodici.ovladani.razitka`) až po reloadu (0:00 / Robertovo „nasadit hned“).** Testy `scripts/2026-10-08_razitka_tazeni/` (536 + Chromium 14/14, mutace server 8/8). **ČEKÁ: Robert – po puštění tažení se přesný model přestaví a razítka se na novém hashi umístí jinde (pravidlo umístění beze změny); chce stabilní umístění nezávislé na rozměrech?**
- **[bot16] ADMIN E-MAILY: SKUTEČNÝ ČAS ODESLÁNÍ (sloupce „Zařazeno“ + „Odesláno“) - HOTOVO a živé (2026-10-08 17:39; Robert přes bot9, řádek id 201).** UI e4bac8a5 (hlavní seznam, historie v objednávce, Systémové e-maily; „Odesláno“ se zapíná samo podle pole `sent_at`), backend bot5 49467408 (`sent_at` + zpětné doplnění z audit_logu), API nasazeno HUP 17:39 na Robertovo „Nasadit hned“; ověřeno skutečným GET z ostré DB (201: zařazeno 28. 9. 0:42:08, odesláno 29. 9. 9:32:42) + testy 44/44. Odkaz: https://autovestavby.logiman.cz/admin.html#emails. **Čeká (bot16):** po „hotovo“ od bot8 vizuálně ověřit razítka (pravidlo 61) v generátorech a v košíku (načítání, rychlost, viditelnost loga, mobil); těžké GLB hlásit bot8.
- **[bot16] E-MAIL S DOKLADEM JEN PO SCHVÁLENÍ DOKLADU (Robert PŘÍMO 2026-10-08) – UI hotové, backend bot5 rozpracován.** Příčina na doklad 26VDD00001: e-mail se zařadil hned po vystavení, doklad se schválil až 8. 10. (e-mail s ním odešel už 29. 9.). UI: „Poslat e-mail“ se u neschváleného dokladu nenabízí (přehled Doklady, detail objednávky, příloha vlastního e-mailu), test 14/14. **Čeká:** bot5 (`documents/approvals/emails` + `approval_status` v API), pak Robertovo „nasadit hned“ (s obrázkem) nebo 0:00.
- **[bot16] IT/EN WEB – kostra (viz blok bot7 výše):** `docs/web_jazyky/README.md` (architektura), tabulky `web_sites` + `web_i18n` v ostré DB (hosty jen `draft`), import sešitů bot7 (10 604 řádků), `10_ui.json` (611 UI vět; překládá bot7), `webapp/js/i18n.js`, `api/web_i18n.py` (dormantní, bez `import` v app.py do schválení náhledu). **Dál (bot16):** SSR title/meta/hreflang + homepage, E2E „žádný český text“, náhled Robertovi (obrázky), `PATHS` + 301 z .it; ceny EUR / objednávky bot5; nginx + certifikát bot9.
