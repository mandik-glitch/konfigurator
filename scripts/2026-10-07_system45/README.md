# Generátor stolu 05 – systém 45 „Robustní“ (hluboký stůl až 2500 mm, profil 40×40)

Zadání (Robert 2026-10-07): „Postav generátor stolů system 45, profil 1.1.10.040040.03, hloubka stolu až 2500 mm, možná tam musíme lehce změnit konstrukci.“ a „kompatibilita s předešlými
generátory“. Profil 1.1.10.040040.03 = karta #3468 SuperLight S10 40×40 (`Object_11`), tedy **tentýž profil jako systém 40**; mění se jen rozsah hloubky a konstrukce nad 1500 mm.

## Co je systém 45
- **Do hloubky 1500 mm (včetně) je stůl bit po bitu stejný jako ve 40** (stejné díly, stejná cena, stejný kusovník; liší se jen `system` = 45 v kódu konfigurace). Díky tomu jde
  konfiguraci přepínat mezi generátory 01 / 02 / 03 / 05 odkazem „Přepnout na systém …“ (stejný hash). Z 45 do 40 se hloubka nad 1500 mm zkrátí na 1500 (`_cislo` ořezává).
- **Hloubka 400–2500 mm** (`S._rozsahy(45)["hloubka"]`; ostatní systémy dál 400–1500; mimo rozsah = `StulChyba`, veřejná vrstva ořezává).
- **Nad 1500 mm hloubky (`HLOUBKA_STREDNI_NOHA`) přibývá STŘEDNÍ ŘADA NOH** (blok 2c-45 v `_sestav_jadro_systemu`):
  - na každé straně (L / P) **střední noha** = svislý profil Object_11 uprostřed hloubky (x přesně v půlce mezi přední a zadní nohou, z v ose boční nohy) od podlahy po spodní líc nejnižší boční
    příčky; je to prodloužený spodní segment svislého profilu bočnice (`("bok", strana, "dno")`, ten ve 40 nad 900 mm končil nad podlahou); konec jako u ostatních noh: kolečko (stejného typu
    jako rohová, `("bok_kolecko", strana)`), patka nebo záslepka;
  - pod podpěrami pracovní desky i každé police **příčka přes šířku** mezi oběma středními nohami (`("zmid", j)`, Object_11, vodorovně v ose Z, délka = světlá šířka mezi nohami), o jeden profil
    pod bočními průvlaky, takže podpěry (podélné profily) přes ni jen přecházejí; konce příček na boky svislých segmentů (spojky 42 / 45 jako konce příček panelů);
  - velmi nízký stůl (střední noha by byla kratší než `MIN_DELKA_STREDNI_NOHY` = 50 mm, tj. výška desky pod ~190 mm) střední řadu nemá a je jako ve 40 (zjištěno měřením: od ~42 mm je sestava
    bez problému, kratší noha → spojka přesahuje záslepku); příčka, která se nevejde nad díl pod ní (`_pricka_vejde`), se vynechá;
  - informace pro zákazníka `stredni_rada_noh` (`info` generátoru → oznámení u posuvníku hloubky v cs / en / sk, ostatní jazyky anglicky).
- **Pravidla stolu = zlomové míry po systémech** (Robert 2026-10-07: „každý systém stolů má pravidla svoje, tzn limitní rozměry pro středovou nohu apd“, „všechny zlomové míry má mít každý systém svoje“):
  systém 45 má vlastní sadu (tlačítko „45“ v okně Pravidla stolu, ukazuje se jen když API systém zná). Práh střední řady noh je pravidlo `hloubka_stredni_noha` (výchozí 1500, rozsah 400–2500, jen
  systémy `hluboky`), a protože zlomové míry mají být VŠECHNY po systémech, přibyla i `podpera_max_rozpon` (800; počet podpěr, dřív konstanta `PODPERA_MAX_ROZPON`) a `min_odstup_stredni_noha`
  (150; limit polohy střední nohy, dřív `MIN_ODSTUP_STREDNI_NOHY`) – pro VŠECHNY systémy (SSE čte limit polohy střední nohy z pravidel systému 41). Výchozí hodnoty = dosavadní konstanty, takže
  nic se nemění, dokud admin hodnotu systému neupraví; hash konfigurace zahrnuje míru jen když je jiná než výchozí. Přepínání téže konfigurace mezi systémy přenáší jen výběr, každý systém ho
  normalizuje podle svých zlomů a mezí (střední noha podle prahu systému, `mid` se ořízne do limitu systému, hloubka na rozsah systému).
- **Cena podle systému stolu, ne podle dílů** (`stul_shop.py` / `stul_api.py`): systém 45 má díly jako 40, takže `S.system_z_dilu` by ho poznal jako 40 a cena výřezů by četla pravidla 40.
  Volání `cena_konfigurace(dily, system)` teď dostává systém parametrů (u 30 / 35 / 40 beze změny výsledku).

## Změněné soubory
`api/stul_konfigurator.py` (SYSTEM_45, `_rozsahy`, blok 2c-45, role dílů, konce, info, odpověď), `api/stul_shop.py` (RECEPT_45, rozsah hloubky po systémech ve schématu / výřezech / normalizaci,
text střední řady, cena podle systému), `api/stul_api.py` (cena staff trasy), `api/stul_vyrobni_list.py` (číslo generátoru 05), `api/miniweb.py` (rodina drážek profilu 40),
`webapp/stul-konfigurator-45.html` (kopie 02), `webapp/js/stul-host.js` (GEN, přepínač, Pravidla stolu 45, šířka profilu), `webapp/js/scene/stul-konfigurator.js` (GENERATORY),
`scripts/stul_verze.py`, `scripts/miniweb_verze.py` (nová stránka), piny `?v=` v ostatních stránkách generátorů (změnil se `stul-host.js`).
Karta: `zaloz_kartu_system45.py` (náhled; `--apply` přes systemd-run; neaktivní karta `STUL.SYSTEM45.KONF` + záznam `stul_system45` v `configurator_products`; pravidlo 54 – aktivuje Robert).
Kategorie ani texty pro systém 45 se nezakládají (jen na Robertův pokyn). **Karta #5353 je od 2026-10-07 21:00 aktivní** (Robert ji aktivoval a přejmenoval v adminu); zákaznický štítek přepínače systémů `pdc.sys45` = „Robustní 45 – hluboký“ (cs / sk / en / de / hu v `webapp/miniweb/i18n/`, texty dál věc bot7).

## Testy
- `test_s45_jadro.py [--rychle]` (bez DB): rozsahy po systémech; **45 ≡ 40 bit po bitu do hloubky 1500 mm** (mřížka ~1080 konfigurací + rozšířené volby); hluboký stůl 1501–2500 mm (mřížka 960
  konfigurací): bez problémů, střední nohy přesně v půlce hloubky a v ose bočních noh, příčky přesně mezi nimi pod bočními průvlaky, konce noh, počty dílů proti 40, informace; práh 1500 / 1510;
  nastavitelný práh podpěr jen pro 45; náhodné sady voleb (semeno) – hluboký stůl je platný vždy, když je platný 40 o hloubce 1500.
- `test_s45_regrese.py [rev]`: **systémy 30 / 35 / 40 jsou po zavedení 45 bit po bitu stejné jako ve staré revizi** (3519 porovnání: díly, problémy, rozměry, spoje, ovládání, výrobní výpis,
  kusovník, `odpoved()`; v `systemy` smí přibýt jen záznam 45).
- `test_s45_shop.py` (veřejné API nad fiktivními kartami 9877 = 40, 9878 = 45; DB jen čte): schéma, posuvník hloubky 400–2500, stejný výběr do 1500 = stejná cena a kusovník, hluboký stůl
  (oznámení cs / en / sk / de, víc dílů a koleček, vyšší cena), ořez hloubky, token `y=45`, GLB, košík `vyres`, výrobní sestava a list (generátor 05), staff trasa, cena výřezu podle pravidel
  systému 45, tah hloubky ve 3D 400–2500.
- `test_s45_pravidla.py` (API s falešnou DB): ukládání pravidel PO SYSTÉMECH (PUT `{system, pravidla}` se uloží po systémech, ploché PUT 30 / 35 / 40 se 45 nedotkne, ztráta hodnot 45 by shodila test),
  nové zlomové míry (rozsahy, `hluboke_systemy`, hash), a **převod téhož výběru mezi systémy s různými zlomy** (veřejné API, fiktivní karty): šířka 1700 má ve 40 s prahem 1800 bez střední nohy a ve 45 s
  výchozím prahem se střední nohou, `mid` v mezích systému, oznámení o střední řadě nese práh systému.
- `test_s45_zive.py`: živé tažení rozměrů hlubokého stolu = model ze serveru po dílech (≤ 0,05 mm).
- `mutace_s45.py`: 22 záměrných chyb v jádru, API a e-shopu; všech 22 zachyceno (jedna ekvivalentní nahrazena).
- `test_s45_stranka.js` (přes most `scripts/2026-10-02_stul_testy/_most_stul.py`, proměnné `PID40`, `PID45`, `PRAVIDLA_TEST={}`; prohlížeč Chromium): stránka 05, karta ze `schema.systems`,
  posuvník do 2500, kusovník profil 40×40, token 45, tlačítko 45 v Pravidlech stolu, hluboký stůl odkazem + informace, přepnutí 45 → 40 (hloubka na 1500) a 40 → 45 (stejná cena), starší odkaz
  se střední nohou v mm počítá rozpětí s profilem 40.
- Celá sada `scripts/2026-10-02_stul_testy/run_all.sh` (45 kroků, všechny systémy) nad kandidátním stromem před nasazením.

## Nasazení
Hotovo a nasazeno 2026-10-07 20:56 (ruční reload na Robertovo „nasadit hned“, 0 z 47 požadavků selhalo); karta založená `zaloz_kartu_system45.py --apply`. Druhá dávka (zlomové míry po systémech, okno Vzhled
v generátorech) jde stejnou cestou: statika živá hned po commitu, API (`stul_*`) 0:00 / 12:30 nebo „nasadit hned“; do nasazení API se nová pole Pravidel neukazují (probe: starý server je nezná).
