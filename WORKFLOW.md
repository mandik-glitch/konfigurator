# Git workflow pro /opt/konfigurator (POVINNÉ pro VŠECHNY boty)

Zavedeno 2026-07-23 po incidentu, kdy "rollback" jednoho bota přepsáním
souboru ze staré `.bak.*` zálohy smazal dokončenou a nasazenou opravu
druhého bota (viz commit historie a `git log` níže pro přesný stav, ze
kterého se vychází).

## AKTIVNÍ POKYNY OD ROBERTA (přečti si PRVNÍ, než cokoliv děláš)

`AGENTS_LOG.md` má tisíce řádků historie - tenhle blok existuje, abys
nemusel/a hledat aktuálně platná pravidla v celé historii. Zapisuj sem
nové trvalé pokyny, jak přibydou (a odstraňuj/uprav, pokud je Robert
zruší nebo upřesní).

**⭐ ZRUŠENO 2026-09-10 (commit `d074baea`):** dílna na VPS
(`vps_dilna.blend`, systemd `blender-gui`) byla na Robertův pokyn
smazána — *„smazat dílna", „vps_dilna.blend smazat ať tě nenapadá tam
renderovat"*. Šablona renderů se od té doby bere ze Sdíleného disku
(`app_settings.render_template_file_id` → `shared_drive_files`), stejný
mechanismus jako HDRI. Pravidlo níže (dílna je Robertův, nesahat bez
svolení) platilo do zrušení dílny — ponecháno jako historický kontext,
NE jako aktivní zákaz (audit bot9 2026-09-12 zjistil, že `PRODUKTOVE_
RENDERY.md` na tohle pravidlo pořád odkazovalo jako na aktivní).

*Původní znění (do 2026-09-10):* Blender na VPS ("dílna") je Robertův —
bez jeho svolení do něj NESAHAT (Robert 2026-09-09): *„pravidlo: žádný
bot nemůže měnit nastavení na VPS v Blenderu dokud to admin nepovolí"*.
Scéna v GUI Blenderu na VPS (`vps_dilna.blend`, systemd `blender-gui`)
byla ZDROJ vzhledu všech produktových renderů — každá renderovací úloha
ji brala jako šablonu automaticky. Bot směl **číst** (snapshot pro
render) a **balit v ní obrázky** (`img.pack()`). Nesměl měnit engine,
vzorky, světla, world, materiály, kamery ani viewport. Porušeno
2026-09-09 (bot8 scénu přestavoval při každém restartu a několikrát
přepsal Robertovo nastavení).

**⭐ K čemu Blender v projektu je (Robert 2026-09-09, doslovně):**
*„v blenderu nic netvoříme, vkládáme tam jen hotové sestavy za účelem
renderování."* Blender je tedy renderovací scéna, ne nástroj na tvorbu —
Robert v něm nastaví vzhled, bot do něj jen vkládá sestavy. Tři důsledky,
všechny platné pro každou příští session:
1. **Autosave je ZRUŠENÝ** (Robert: „autosave vypni", commit `25b42238`).
   Periodické přepisování `.blend` tím, co je v GUI, nemá co zachytávat a
   přepisovalo mu scénu pod rukama. **Soubor ukládá výhradně Robert sám.**
2. **Sérii modelů nedělej přes kopii na každý model** — stačí jedna
   soběstačná scéna, každá úloha si model naimportuje jen v paměti,
   vyrenderuje a skončí BEZ uložení. Kopie jen jednorázově kvůli zabalení
   chybějících obrázků (cizí soubor se nikdy nemění).
3. **ZNÁMÁ PŘÍČINA „render nevypadá jako moje scéna"** (nalezeno
   2026-09-09, NEOPRAVENO): větev pro sestavy spouští Blender ÚPLNĚ BEZ
   `.blend` (`blender -b -noaudio -P blender_render_scene.py`), startuje
   z prázdna a světla/kameru/materiály si dopočítá v kódu — Robertovo
   nastavení do renderu nikdy nevstoupí. Cílový tvar: spustit Blender
   S jeho `.blend` a sestavu do něj naimportovat (mechanismus už existuje,
   používá ho `turntable` větev). Detail v `PRODUKTOVE_RENDERY.md`.

**Archivace (2026-08-19, bot3):** živý `AGENTS_LOG.md` přerostl ~35 000
řádků (i konvence "přečti posledních ~200 řádků" přestala dávat smysl
- jediný rušný den měl přes 2600 řádků). Historie do 2026-08-18 včetně
je teď v `AGENTS_LOG_ARCHIVE_do_2026-08-18.md` (beze změny obsahu, jen
mimo živý soubor - `grep` funguje přes oba: `grep -n "výraz"
AGENTS_LOG*.md`). Až živý soubor zase naroste na podobnou velikost,
zopakuj stejný postup (nový archiv, např. `AGENTS_LOG_ARCHIVE_do_
<datum>.md`, hranici zvol tak, aby živý soubor pokrýval jen posledních
pár dní).

**Konvence zápisu (2026-08-19, Robert - "optimalizovat", ať jde rychle
zjistit, co se dělo, bez čtení každého slova):** nový zápis do
`AGENTS_LOG.md` ZAČNI 1-2větým shrnutím (co/proč/výsledek) hned po
nadpisu, teprve pak následuje detail (měření, ověření, zdroje). Detail
NEMAZAT ani nezkracovat kvůli délce - i drobná čísla se často ukázala
podstatná později (např. přesně změřené RSS Whisper workeru). Jde o
přidání shrnutí navrch, ne o náhradu obsahu.

1. **Testovací/demo data se nemažou samovolně.** Smazat je jen na
   VÝSLOVNOU žádost Roberta v dané chvíli (viz `AGENTS_LOG.md`
   2026-07-26 "Uklid vsech testovacich dat" pro přesný příklad, co bylo
   smazáno a proč). Sám/sama od sebe (např. jako "úklid po testu")
   nemaž nic v produkční DB bez zeptání.
2. **DB přístupové údaje** jsou v `api/.env` (na disku, gitignored -
   `cat /opt/konfigurator/api/.env`). Necommituj je nikam do gitu.
3. **Guarded soubory** (`webapp/*`, `api/*.py`) vyžadují držení
   `DEPLOY_LOCK.json` zámku (viz níže) - vynuceno `pre-commit` hookem,
   ne jen dohodou. (Rozšířeno 2026-09-03 z pouhého `api/app.py` na
   CELÉ `api/*.py` - split iniciativa rozprostřela app.py/remeslo.py do
   20+ souborů, které byly bez týhle změny úplně bez ochrany hooku.)
4. Před zahájením práce si přečti `TASKS.md` (aktuální otevřené úkoly -
   zapiš se jako vlastník) a celý živý `AGENTS_LOG.md` (po archivaci
   2026-08-19 typicky jen několik dní - co se dělo naposledy). Starší
   historie viz archivace výš.
5. Změny `api/*.py` se nasazují automaticky 2× denně (pravidlo 57), bot
   službu nerestartuje. Po nasazení ověř změněný endpoint, ne
   `/api/health` (pravidlo 33).
6. **Sjednocené písmo je ZÁVAZNÝ standard pro CELÝ projekt** (Robert
   2026-08-06, po několika kolech "sjednoť velikost textu a stylu" -
   košík, karty produktů, dlaždice kategorií, detail produktu, strom
   kategorií): KAŽDÝ nový textový prvek (i budoucí stránky/panely,
   `webapp/*.html` VČETNĚ `admin.html`) musí použít:
   - `font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;`
     (systémové písmo, žádné načítání z Google Fonts - viz `AGENTS_LOG.md`,
     "sjednoceni pisma napric projektem"). V praxi stačí NEPŘIDÁVAT
     vlastní `font-family` na nový prvek - zdědí ho z `html, body`,
     pokud to na dané stránce ještě není nastavené, nastav to tam
     stejně jako v ostatních souborech.
   - `font-size: 16px` (s `line-height: 1.75` pro delší odstavce popisu,
     `line-height: 1.4` pro kratší texty typu název položky/karty/
     řádek tabulky/strom) pro VEŠKERÝ text, který zákazník čte jako
     obsah - názvy produktů/kategorií, ceny, popisy, tabulky
     specifikací, položky košíku, formulářová pole, potvrzovací/
     chybové zprávy.
   - Výjimka (SMÍ zůstat menší, typicky 10.5-14px): čistě dekorativní/
     funkční UI drobnosti, které jsou tak i jinde na webu zavedené -
     badge/štítky dostupnosti, uppercase popisky sloupců tabulky,
     malá SKU/meta poznámka pod názvem, čísla/popisky kroků wizardu,
     +/- stepper tlačítka, patička s copyrightem, tlačítka (`.cn-btn-*`
     14px podle `nabidka-online.html`). Pokud si nejsi jistý/á, jestli
     jde o "obsah" nebo "UI drobnost", zeptej se Roberta místo hádání -
     tenhle bod se v jedné session opravoval postupně 4x, protože se
     rozsah pokaždé podcenil.

7. **Kategorii bez vlastního obrázku (`content_categories.image_filename`
   IS NULL) doplň obrázkem nejvhodnějšího produktu uvnitř ní** (Robert,
   2026-08-08). Platí pro listové kategorie (bez podkategorií) - pokud
   kategorie MÁ podkategorie, řeší se to obrázky podkategorií, ne
   obrázkem konkrétního produktu. "Nejvhodnější" = postupně 3 zdroje
   (první úspěšný vyhrává): 1) první aktivní produkt v kategorii
   (podle `id`) s obrázkem v `shop_product_images` (přednost
   fotorealistický render před technickým schématem), 2) vlastní
   fotogalerie kategorie (`content_gallery_items`), 3) první dost
   velký `<img>` v popisu kategorie (`content_pages.body_html`) -
   malé obrázky (typicky podpisy/loga v patce textu, < 100px) se
   přeskakují. Hotový skript:
   `scripts/2026-08-08_category_image_from_product.py` (idempotentní -
   kategorie, co už obrázek mají, přeskočí) - nová kategorie bez
   obrázku nevyžaduje nic ručního, stačí skript znovu spustit. Detaily
   a historie (16 + 4 kategorie doplněny na 2 běhy) viz `AGENTS_LOG.md`,
   "bot6 — 2026-08-08 — pravidlo: obrázek kategorie z produktu uvnitř".

8. **⛔ ZRUŠENO 2026-10-04 (Robert: „QA běhy vypnout“): automatické QA běhy
   jsou vypnuté a psaní nové kontroly ke každé chybě už není povinné.** Kód
   (`api/qa_checks.py`, `scripts/qa/`) a tlačítko v adminu zůstávají pro
   ruční spuštění. Bug se dál opraví a zmíní v `AGENTS_LOG.md`. Důvod: ze
   8 reportů (2.-28.9.) byly všechny FAIL a z 10 „kritických“ nálezů 2
   skutečné; od 5.9. je nikdo nezpracovával. Původní znění níž je jen kontext.

   *Původní znění (2026-08-10):* **Každý bug v kódu, na který při práci
   narazíš, přelij do automatické kontroly v `api/qa_checks.py`** (Robert, 2026-08-10: "kazdou chybu na
   kterou pri sve praci narazis, formuluj do pravidel o chybach, tak aby
   se po novu hledali i prave tento typ chyby onim scriptem
   automaticky"). Nestačí bug jen opravit na místě - pokud jde svou
   podstatou o TŘÍDU chyby, která se může opakovat i jinde v kódu (ne
   jednorázový překlep v datech, ale vzor - např. `getElementById` na
   neexistující `id`, `fetch()` na neexistující backend route,
   duplicitní HTML `id`, zapomenutý `await`, nekonzistentní název
   sloupce mezi SQL a Python kódem, apod.), napiš pro ni NOVOU kontrolní
   funkci do `api/qa_checks.py` (signatura `fn(cur) -> list[(id, name,
   detail)]`, žádná oprava uvnitř - jen report, viz existující
   `check_duplicate_html_id`/`check_dangling_get_element_by_id`/
   `check_broken_fetch_endpoint` jako vzor a vysvětlení v hlavičce
   souboru). Cíl: každý jednou nalezený bug rozšíří sadu kontrol, takže
   se stejný vzor napříč zbytkem/budoucím kódem hledá automaticky
   napořád, ne jen ta jedna nalezená instance. Pokud chyba nejde
   smysluplně zobecnit na opakovatelný vzor (opravdu jednorázová věc),
   stačí ji opravit a zmínit v `AGENTS_LOG.md`, nová kontrola není
   potřeba.

   **Novou kontrolu vždy pusť i proti stavu PŘED opravou** (např.
   soubory z `git show HEAD~1:...`/zálohy v odkládacím adresáři), ne
   jen proti opravenému kódu (Robert přes bot3, 2026-09-03 - dnes se to
   nezávisle stalo třem botům). Kontrola ověřená jen na čistém kódu
   může být tiše mrtvá a hlásit "0 nálezů", protože nefunguje - ne
   protože je čisto. "0 nálezů" samo o sobě není důkaz, že kontrola
   funguje.

   **Registrace nové kontroly musí být VŽDY kompletní ve STEJNÉM
   commitu** (Robert, 2026-08-11: "chci aby se log datum přidání
   každého nového typu kontroly") - kromě samotné funkce `check_*`
   zapsat klíč i do všech tří registrů v `api/qa_checks.py`:
   `CHECKS` (label + funkce), `CHECK_CATEGORY` (`"doplnit"` = chybí
   hodnota / `"opravit"` = špatná hodnota nebo bug v kódu) a
   `CHECK_ADDED` (dnešní datum `YYYY-MM-DD`). Chybějící záznam v
   kterémkoli z nich = kontrola se v adminu buď vůbec nezobrazí, nebo
   nemá datum přidání - přesně tohle se stalo `missing_dogus_price_
   coefficient` (chyběla v `CHECK_CATEGORY`, commit `3d28f94`, opraveno
   až `cba4a0d`). `check_qa_registration_incomplete` teď tuhle
   nekompletnost hlásí automaticky - pokud se objeví, je to signál, že
   předchozí bot zapomněl jeden z registrů.

9. **Ceny VŠECH produktů spárovaných s Dogus (`dogus_url` vyplněné) se
    přepočítávají KAŽDOU NOC (od 2026-09-24, dřív 1× týdně), automaticky,
    podle přesně dané rovnice - dvě varianty podle typu položky** (Robert,
    2026-08-10: "1x tydne se
    nacte kompletne novy cenik z Dogus, ulozi se cena USD u nas aby ji
    jen admin videl na kazde kartě. Automaticky se okamžitě podle
    koeficientu a podle rovnice cena dogus x 3 x kurz = cena za 1ks
    tyče 3m, s kurzem Fio banka devize prodej. zaokrouhleno na celé
    koruny" + upřesněno "cena se ma prepocitavat i na ne-profily tzn na
    kompletni polozky z Dogus" + "ostatni polozka se nasobi 1x resp
    zustanou jak sou, jen x kurz a x koeficient" + "Vzorec pro
    ne-profily: zaokrouhleni ceny vzdy nahoru"):

    **PŘEPSÁNO 2026-09-24 (Robert přes bot3)** - tři stavy místo dvou a
    jednotné zaokrouhlení. Rozhodující je `content_categories.dogus_sale_unit`
    (ENUM `tyc_3m` / `metraz` / `kus`), NIC jiného:

    ```
    # tyc_3m  - Dogus sekce 9 "Aluminium Profiles" + 8 profilu mimo ni
    #           (nase kategorie 154, 168, 169, 192, 198, 215, 262, 264)
    #           Dogus cena je za 1 m, my prodavame tyc 3 m
    cena_za_ks_czk = ceil(dogus_list_price_usd × kurz_fio_prodej × koeficient_kategorie × 3)

    # metraz  - Dogus sekce 84 "Profile Seals" (nase kategorie 196)
    #           Dogus cena je za 1 m a my to prodavame NA METRY (unit='m')
    cena_za_m_czk  = ceil(dogus_list_price_usd × kurz_fio_prodej × koeficient_kategorie)

    # kus     - vsechno ostatni, Dogus cena UZ je za 1 ks
    cena_za_ks_czk = ceil(dogus_list_price_usd × kurz_fio_prodej × koeficient_kategorie)
    ```

    **Zaokrouhlení je u VŠECH TŘÍ stejné: celé koruny, VŽDY NAHORU**
    (`math.ceil`) - Robert 2026-09-24 doslova: *„celé koruny vždy
    nahoru"*. Tím padá starší stav, kdy profily měly matematické
    `round()` a jen ne-profily `ceil()`; sjednocení je ZÁMĚR, ne chyba -
    neopravovat zpět na `round()` podle staršího znění tohoto pravidla.
    Dopad při zavedení: 54 ze 105 tyčových položek zdražilo přesně o 1 Kč.

    **Zařazení se NIKDY neodvozuje za běhu** - ani z názvu položky, ani
    ze skrytých polí dogusí stránky. Robert 2026-09-24: *„nemůžeme se
    rozhodovat podle názvu, teď si určíme pevně co je na kusy a co je na
    tyče 3m"*. Dřívější heuristika `per_meter = is_profile or ("lišta" in
    name)` (Robert 2026-09-15) je tímto ZRUŠENÁ - dávala dvěma položkám se
    stejnou dogusí cenou dvě různé ceny (kategorie 196: 18 Kč vs. 7 Kč při
    0,23 USD) a nafoukla „Posuvné lišty" 3×. Pole `hdnStockQuantityUnitValue`
    na dogusí stránce se jako kritérium NEPOUŽÍVÁ - u části sekce 84 hlásí
    "0" a u trubkových/kluzných profilů na stránce vůbec není.

    - **Rozlišení profil/ne-profil je KRITICKÉ** - Dogus u profilů
      (tyčí) uvádí List Price za 1 metr, u kusového zboží (matice,
      spojky, kryty) ho uvádí rovnou za 1 kus. Použití vzorce s `×3` na
      kusové zboží by cenu nasadilo 3× moc. Ne-profilové stránky Dogus
      mají navíc jinou HTML strukturu tabulky (sloupce Stock Code/Stock
      Name/B/D/Material/Weight místo Stock Code/L) - vyžaduje samostatný
      parser (`parse_nonprofile_price_for_code` vs. `parse_price_for_code`
      v `scripts/2026-08-09_dogus_price_recompute.py`).
    - **Zdroj Dogus ceny**: přihlášený scrape stránky produktu na
      `doguskalip.com.tr` (`shop_products.dogus_url`/`dogus_stock_code`),
      NE ruční zadání. List Price na Dogus u profilů JE už za 1 m (ne za
      skladovou tyč) - nedělit délkou `L_mm`, ta je jen informativní.
    - **Zdroj kurzu**: VŽDY živě stažený z veřejné tabulky "Devizové
      kurzy" na `fio.cz` (sloupec "Prodej"), NIKDY hardcoded/napevno v
      kódu. Žádný fallback na starou/odhadnutou hodnotu - když se kurz
      nepodaří stáhnout, celý běh selže (radši žádná aktualizace cen
      než cena spočtená se špatným kurzem).
    - **Koeficient**: `content_categories.dogus_price_coefficient`,
      nastavuje admin ručně v záložce "Koeficienty cen" (NEzaměňovat se
      scénovým koeficientem `scene_price_coefficient`, pravidlo 58). **Výchozí
      hodnoty, když koeficient chybí/zmizí** (Robert 2026-08-10: "pokud
      nekde zmizi koeficient, musi se udelat zapis, ale hlavne
      odstranit pricina, nicméně v takovém případě je to takto: profily
      koeficient 1, ostatní Dogus položky koeficient 1,2") - **profily
      = 1**, **ostatní Dogus zboží = 1,2**. Chybějící koeficient se
      NIKDY needituje potichu automaticky ve skriptu - kategorie se ten
      týden jen přeskočí (chyba v logu) a QA kontrola
      `missing_dogus_price_coefficient` (`api/qa_checks.py`) to nahlásí
      v admin Dashboardu, aby si toho admin všiml a doplnil hodnotu
      ručně (s výše uvedeným výchozím doporučením) - ZÁROVEŇ je třeba
      dohledat PŘÍČINU, proč koeficient chybí (typicky nová
      kategorie/nově spárovaný produkt), ne jen hodnotu doplnit a
      nechat se to opakovat.
    - **Transparentnost pro admina**: použitá USD cena i použitý kurz
      se ukládají na produkt (`shop_products.dogus_list_price_usd`,
      `dogus_price_rate_used`) a zobrazují se na skladové kartě
      produktu (`webapp/admin.html`, sekce "Cenotvorba") - i když s
      nimi nikdo ručně nic nedělá, slouží jako doklad "z čeho se cena
      spočítala", ne jen holý výsledek.
    - **Automatizace**: `konfigurator-refresh-dogus-profile-prices.timer`
      (KAŽDOU NOC ve 3:20; od 2026-09-24, dřív neděle - Robert přes bot3:
      „kurz FIO se mění každý pracovní den“) spouští
      `scripts/2026-08-09_dogus_price_recompute.py --apply` bez zásahu
      člověka/bota.
10. **Pravidlo pro bota 3D scény - geometrie (napojování profilů a
    příslušenství)** (Robert, 2026-08-16): bot je ten, kdo si má sám
    navrhnout postup práce/workflow, tak aby nejefektivněji pochopil
    napojování profilů a příslušenství - admin (Robert) jen říká, co je
    dobře a co je špatně, po hotové práci/pokusu. Neptej se admina
    dopředu na volbu mezi variantami postupu ("mám udělat A nebo B?") -
    navrhni si postup sám, zkus ho, ukaž výsledek, nech admina zhodnotit.
    Konkrétní technika pro fyzické díly, které nejdou spolehlivě pochopit
    z fotky/popisu: postav si konkrétní testovací sestavu přímo v DB
    (`custom_shapes`, viz `TVARY_VLASTNI.md` sekce 2an "Postup: ruční
    vytvoření vlastního tvaru") a nech admina ohodnotit VÝSLEDEK, ne popis
    plánu předem.

    **Kontinuální práce (Robert, 2026-08-16, doplnění):** bot musí
    KONTINUÁLNĚ pracovat, dokud nejsou vyřešené VŠECHNY automatické
    funkce (Place All pro každý naučený režim, R-cyklení, U-odpojení...
    - ne jen ty, na které bot náhodou narazil) A dokud nezná VŠECHNY
    spojky a díly a jak se správně používají k profilům. Bot pokračuje
    v práci (testování, ověřování, oprava nalezených chyb), dokud admin
    Robert výslovně NEnapíše souhlas s ukončením učení - "nemám další
    zjištění" / "vypadá to hotovo" NENÍ totéž jako Robertův souhlas s
    ukončením; dokud nepřijde, bot pokračuje dál sám.

    **SKU, ne názvy (Robert, 2026-08-17):** bot obsluhující 3D scénu
    MUSÍ bezpodmínečně vždy - v matematických simulacích, při ukládání
    pozic i při jakékoli práci s katalogovými objekty (výběr
    konkrétního dílu, hledání "toho správného" produktu pro danou roli) -
    používat **SKU** katalogového dílu, NIKDY jeho název/text. Důvod
    (zjištěno naživo, 2026-08-17): katalog obsahuje vizuálně úplně
    odlišné díly se shodným nebo podobným slovem v názvu (2 zcela různé
    produktové řady, jen náhodou sdílející slovo v názvu). **Poslední
    segment SKU** (za poslední tečkou) je spolehlivý, konzistentní
    "typový kód" produktové řady napříč velikostmi - na rozdíl od textu
    v názvu, který je nesourodý a nedá se mu věřit. `attach_mode`
    (structured pole, ne text) je použitelný jako DOPLŇKOVÁ pojistka
    vedle SKU, ne náhrada.

    **Žádné zanoření, žádné částečně kryté čelo (Robert, 2026-08-18,
    NADŘAZENÉ pravidlo pro KAŽDÝ spoj profil-profil, i budoucí zatím
    nenapsané typy)** - doslovná citace: *"profily nikdy nemohou být
    zanořené !!! nikdy nemohou mít čelo zakryté částečně !!! máli
    čelo doléhat na stěnu jiného profilu tak vždy pouze celou plochou
    čela."* Pro libovolný spoj dvou profilů musí platit SOUČASNĚ:
    mezera = 0, průnik = 0, a na dotykové rovině leží CELÁ plocha
    menšího/rovného čela uvnitř plochy druhého dílu (ne půlka, ne
    jen hrana). Tohle je kritérium SPRÁVNOSTI, ne popis hotového kódu -
    platí i při navrhování spoje, který appka ještě vůbec neumí.

    **Jak to ověřit (nestačí kontrola jen na 1 ose!):** spočítej
    `overlap` (překryv) bounding-boxů obou dílů na VŠECH 3 osách
    zvlášť, ne jen na té, kde se díly dotýkají. Reálný, funkční spoj
    = přesně JEDNA osa s `gap=0`/`overlap=0` (dotyková rovina) A
    ZBÝVAJÍCÍ dvě osy s PLNÝM překryvem (menší čelo celé uvnitř
    většího). Kontrola jen dotykové osy "gap=0" NESTAČÍ jako důkaz -
    dva díly se můžou dotýkat čistě HRANOU (translační/rotační posun
    nulové šířky), což vypadá jako "0mm mezera" a přitom je to nulová
    reálná plocha styku, tedy fyzicky neexistující/nesešroubovatelný
    spoj. Plný rozbor viz `PRAVIDLA_SPOJU.md`, sekce "Pravidlo
    profilů - ŽÁDNÉ zanoření...".

    **Kontrola VŽDY jako živý 3D model v karoserii (Robert, 2026-08-30,
    doslovně: "dej to jako pravidlo, že všechno učení se musí pro
    kontrolu adminem dělat 3D do karoserie")** - výstup jakéhokoli
    geometrického učení/experimentu (nová sestava, nová varianta dílu,
    parametrická úprava jako změna profilu nebo hloubky) se předkládá
    Robertovi VŽDY jako `product_assemblies` záznam vložený do skutečné
    karoserie (viditelný přes "Produktové sestavy" → "Vložit tvar"),
    NIKDY jen jako technický řez/2D nákres nebo popis v textu - i když
    jde jen o srovnání variant (např. víc hloubek vedle sebe), každá
    varianta jde do vlastní sestavy vložitelné do scény. Technické řezy
    (viz pravidlo výše, "schvalovací podklady = TECHNICKÉ ŘEZY") zůstávají
    v platnosti pro VÝBĚR POZICE napojení jednotlivého katalogového dílu
    (attach_pose) - tohle nové pravidlo je obecnější a nadřazené: cokoli
    se má NA KONCI zkontrolovat, patří rovnou do scény jako 3D model, ne
    jen jako obrázek/text o něm.

    **DOPLNĚK (Robert, 2026-08-30, po regálu na euroboxy):** 3D model v
    karoserii NENAHRAZUJE mm-přesnou 2D dimenzní kontrolu, pokud
    geometrie obsahuje víc přesných kót/proměnných délek (rozestupy,
    pozice spojnic, srovnání variant) - to jsou DVĚ ODLIŠNÉ kontroly,
    obě povinné, ne jedna náhrada druhé. Když bot dřív bez 2D kontroly
    rovnou zapsal do `product_assemblies` několik postupných oprav
    regálu na euroboxy, Robert se zeptal "je to prověřeno přes standard
    2D pohledy?" a zjistilo se, že ne - přestože samotná 3D geometrie
    byla nakonec správně. **Pravidlo: než se JAKÁKOLI geometrie s víc
    než jednou mm-kritickou proměnnou (rozestupy, pozice dílů podle
    vzorce, srovnání profilů/variant) prohlásí za hotovou/uloženou do
    DB, MUSÍ existovat 2D pohled vygenerovaný ZE SKUTEČNÉ GLB geometrie
    (`THREE.Box3`, ne z position/scale čísel) s mm mřížkou a kótami,
    který dokládá, že se naměřené hodnoty shodují se zadáním.** 3D model
    v karoserii zůstává povinný VŽDY (viz výše, pro vizuální/prostorovou
    kontrolu); 2D dimenzní pohled je povinný NAVÍC, kdykoli je ve hře
    víc přesných čísel najednou.

11. **Standardní přehledová/seznamová obrazovka** - povinná výbava od
    prvního nasazení, napříč VŠEMI projekty, pro VŠECHNO (číselníky i
    doklady - objednávky, faktury, e-maily, poptávky, cokoli), bez
    výjimky (Robert, 2026-08-21):
    1. Základní atributy: název/jméno, kontakt, poznámka,
       `created_at`/`updated_at`, `is_active` (soft-delete flag).
    2. Nikdy hard delete - jen archivace. Trvalé smazání jen na
       Robertovu výslovnou žádost v danou chvíli.

       **Výjimka pro dobu PRE-LAUNCH (Robert, 2026-08-27, přes bot3):**
       existující hard-delete tlačítka nalezená auditem
       (`AUDIT_OPTIMALIZACE_2026-08-26.md` - `customers.py`,
       `documents.py`, `purchase_orders.py`, `products.py`, `orders.py`,
       `emails.py`, `gallery.py`/`gallery_items.py`, `drive.py`,
       `support.py`, `crm.py`, `scene_offers.py`) jsou VĚDOMĚ ponechané
       beze změny, dokud je projekt v testovací/pre-launch fázi (viz bod
       18 níže) - NENÍ to zpětné porušení tohohle pravidla ani omyl,
       nehlásit v příštím auditu znovu jako nedořešený rozpor. Až
       proběhne produkční cutover (`project_production_cutover_plan`,
       odhad 1-2 měsíce od 2026-08-22), tohle rozhodnutí se musí
       přehodnotit znovu - do té doby platí a nový kód smí stejný
       vzor (hard-delete tlačítko vedle/místo archivace) dál používat
       beze změny.
    3. Přehledová tabulka, ne jen formulář. Sloupce jdou přetažením
       přeskládat i změnit šířku - platí pro každou tabulku, existující
       se doplňují postupně.
    4. Hledání/filtr vždy podle všech atributů, ne jen názvu. Filtry
       výchozí viditelné/rozbalené, s možností je schovat.
    5. Hromadné akce (výběr víc řádků) od prvního nasazení: smazat
       (=archivovat), exportovat, přesouvat mezi kategoriemi/sekcemi,
       měnit štítky/tagy - podle toho, co dané evidenci dává smysl.
    6. Scoping podle vlastníka, kde dává smysl - admin vidí vše,
       vlastník jen svoje.
    7. Audit log na create/update/archive.
    8. Sjednocené písmo a mobilní responzivita platí i sem (jen
       připomenuto, jsou to samostatná pravidla).

12. **Bot3 = koordinátor, rozdělování práce** (Robert, 2026-08-22): veškerou
    práci, kterou Robert zadá, musí bot3 efektivně rozdělovat mezi existující
    ostatní boty - ne dělat sám, i kdyby to sám zvládl. Výjimka: 3D scéna
    (`bot8`, pevná role - viz tabulka "Rozdělení odpovědnosti mezi boty"
    níže) je samostatná, bot3 do ní práci nepředěluje.

    **RAM strop**: bot3 zároveň živě hlídá vytížení RAM na VPS serveru
    (počítá se do toho i whisper hlasový model) a koordinuje boty tak, aby
    celkové živě využité RAM nepřesáhlo **14 GB**.

13. **Bot3 = dohled nad DEPLOY_LOCK.json** (Robert, 2026-08-22): navazuje na
    bod 3 výše (obecná zámek disciplína platná pro všechny boty) - bot3
    navíc aktivně kontroluje zámek a zasahuje, aby byl používán efektivně:
    boti ho nedrží předčasně (dřív, než mají zápis do guarded souboru
    skutečně připravený k okamžitému zápisu), a nedrží ho zbytečně dlouho
    poté, co zápisy dokončili.

14. **Bot3 = stručné info o stavu úkolů** (Robert, 2026-08-22): bot3 průběžně
    podává adminovi (Robertovi) stručné info o stavech dílčích úkolů/práce
    probíhající napříč flotilou - neseká se v tichosti, ale ani nezavaluje
    detailem (podrobnosti zůstávají v `AGENTS_LOG.md`/`TASKS.md`, sem patří
    jen stručný přehled "co se děje").

15. **Bot3 = kontrola úplnosti frontendu** (Robert, 2026-08-22): bot3
    kontroluje úplnost frontendu jak na veřejných webech, tak v adminu -
    tj. že nová/rozpracovaná backendová funkce má i odpovídající kompletní
    UI pokrytí, ne jen API bez cesty, jak se k němu v rozhraní dostat
    (navazuje na bod 11 výš - standardní přehledová/seznamová obrazovka).

16. **Odchozí e-maily NESMÍ chodit automaticky** (Robert, 2026-08-22,
    doslovně: "NELZE aby se emaily odesílali automaticky při změnách
    stavů (ani jindy), všechny odchozí emaily musí schválit admin,
    pravidlo přestane platit až to admin odvolá") - platí pro VŠECHNY
    odchozí e-maily z celého projektu (potvrzení objednávky, změna
    stavu, faktury/doklady, cokoli), ne jen pro jednu konkrétní cestu.
    Trvalé pravidlo, dokud ho Robert výslovně neodvolá - neplatí jen
    pro tuhle jednu implementaci, platí i pro jakoukoli budoucí novou
    cestu odesílání e-mailů.

    **DOPLNĚNO 2026-08-22 (Robert, po incidentu): "NENÍ možné, aby**
    **boti svévolně odesílali e-maily!!"** - týká se i TESTOVÁNÍ. Bot
    nikdy sám nezavolá schvalovací endpoint/tlačítko jen proto, aby
    ověřil, že mechanismus odeslání funguje - i kdyby šlo o testovací
    objednávku a i kdyby příjemcem byla Robertova vlastní adresa
    (přesně tohle se stalo: bot9 při ověřování bodu 16 sám "schválil"
    testovací e-mail, ten se doopravdy odeslal na `mandik@logiman.cz`
    bez Robertova vědomí - kód pravidlo formálně neporušil, ale
    princip ano). Živé ověření "opravdu se e-mail odešle" se musí
    udělat JINAK - např. zkontrolovat, že se zavolala funkce/endpoint
    pro odeslání (mock/dry-run), NE doopravdy nechat proletět SMTP.
    Pokud se skutečné odeslání přesto musí ověřit, je to VÝHRADNĚ na
    Robertovi (on sám klikne schválit), ne na botovi.

    **DOPLNĚNO 2026-08-22 (Robert, doslovně): "vydávám plošný zákaz**
    **odesílání emailů kamkoli, bez schvalovacího procesu."** Bez
    výjimky - žádný příjemce (interní/testovací/vlastní Robertova
    adresa/reálný zákazník) není výjimkou z nutnosti projít
    schvalovacím procesem. Platí pro botem VYVOLANÉ odeslání jakkoli -
    přímým voláním `send_email()`, obejitím fronty, testovacím
    skriptem, čímkoli. Jediná cesta e-mailu ven z appky je: zalogovat
    se jako čekající (`status='pending'`) a počkat na Robertovo
    schválení v adminu.

    **VÝJIMKA (Robert, 2026-08-27, po nálezu `check_direct_send_email_
    bypass` v `api/qa_checks.py`):** `auth_forgot_password`/
    `auth_send_temp_password` (`api/app.py`, reset hesla a dočasné
    heslo) ZŮSTÁVAJÍ posílat e-mail přímo, mimo schvalovací frontu -
    bezpečnostní/časově kritický e-mail (odkaz na reset platí jen
    omezenou dobu, dočasné heslo je hned aktivní v DB), kde čekání na
    schválení admina by škodilo víc než pomáhalo. Vědomá, allowlistovaná
    výjimka (viz komentáře u obou funkcí i `_SEND_EMAIL_APPROVED_
    WRAPPERS` v `qa_checks.py`) - kontrola i budoucí audity ji neberou
    jako nález k opravě. Netýká se ŽÁDNÉ jiné cesty odesílání e-mailů -
    zůstává úzce omezená jen na tyhle 2 konkrétní funkce.

    **DALŠÍ VÝJIMKA (Robert, 2026-09-15):** e-maily, kde jediný
    příjemce je Robertova VLASTNÍ adresa (interní systémová notifikace
    adminovi - např. `scene_offer_accepted` u `public_offer_accept()`,
    QA reporty ze `scripts/qa/run_all.sh`, upomínka na vypršení nabídky)
    se ZASÍLAJÍ ROVNOU, bez čekání ve frontě. Robertovo zdůvodnění:
    *"proč je to v odchozí poště a ne v příchozí"* - tohle není odchozí
    komunikace, kterou pravidlo 16 chrání (riziko nechtěného kontaktu
    třetí strany), je to jen upozornění adminovi na jeho vlastní systém,
    schvalovací krok tu nedává smysl. Netýká se to zmírnění pravidla 16
    jako takového - jakýkoli e-mail se SKUTEČNÝM externím příjemcem
    (zákazník, dodavatel, kdokoli mimo Robertovu adresu) frontou projít
    MUSÍ dál, beze změny. Rozliší se podle `recipient_email` v okamžiku
    zápisu do `system_emails` - implementace na botu, který danou cestu
    odesílání vlastní.

17. **Poptávky - ruční přiřazení k existující poptávce musí být vždy**
    **možné** (Robert, 2026-08-22, doslovně: "ve schvalovacích oknech
    potenciálních poptávek nebo potenciálních vláken poptávek
    potřebujeme pro admina možnost přiřazení ke konkrétní aktivní
    poptávce, protože to bot nemusí zvládnout rozeznat") - v adminově
    schvalovacím rozhraní (třídění e-mailů kategorie "crm", i jinde,
    kde appka rozhoduje "patří tenhle e-mail k existující poptávce,
    nebo je to nová?") musí mít admin VŽDY možnost ručně vybrat
    konkrétní existující aktivní poptávku místo spolehnutí se na
    automatické rozpoznání (Message-ID vlákno/shodný předmět/e-mail) -
    to nemusí být vždy spolehlivé (zákazník píše z jiné adresy, jiný
    předmět apod.). Obecný princip pro celý admin, ne jen tuhle jednu
    obrazovku - kdekoli appka automaticky "sloučí do existujícího
    záznamu", potřebuje vedle sebe i ruční override.

18. **Testovací fáze projektu ≠ nižší nároky na kvalitu testování**
    (Robert, 2026-08-22, doslovně: "my se ale chovejme jakobychom měli
    ostrý provoz, skrze kvalitu testování") - projekt je zatím
    testovací/duplikovaná data (plán přechodu na ostrý provoz s
    archivací a novým číslováním, odhad 1-2 měsíce), ALE tohle platí
    jen pro DATA (čísla dokladů, importované objednávky apod.), NE pro
    důkladnost práce. Žádný bug/mezera se nesmí odbýt s odůvodněním
    "stejně se to pak zarchivuje" - každá funkce se staví a ověřuje se
    stejnou pečlivostí, jako by šlo o živý provoz.

19. **VDD (Daňový doklad k přijaté platbě) se vystavuje automaticky**
    **VÝHRADNĚ u objednávek s platbou předem** (Robert, 2026-08-22,
    doslovně: "VDD se vytvoří automaticky pouze v jednom případě: když
    je objednávka s platbou předem") - definitivní, jednoznačné
    upřesnění bodu 16-navazujícího zadání (automatické vystavení VDD
    při shodě VS z bankovního výpisu, viz `api/bank_statements.py`),
    které dřív vedlo ke zmatku (25 VDD omylem vystaveno i pro
    dobírku/kartu, 6.8.2026 smazáno po schválení Robertem). Kontrola
    platební metody (`shop_payment_methods.requires_advance_invoice`
    + fallback na klíčová slova "zálohov"/"předem" kvůli historickému
    CSV importu s volným textem `payment_method_name`) MUSÍ proběhnout
    PŘED každým automatickým voláním `create_payment_tax_document()` -
    u jiné platební metody se VDD nesmí vystavit vůbec, ani navrhnout
    ke schválení.

20. **ZRUŠENO fakticky (audit bot9 2026-09-12).** Původní pravidlo znělo
    "Celá flotila jede na /opt/toscanaccio, do odvolání" (Robert,
    2026-08-23) - v praxi nebylo dodržováno prakticky od druhého dne
    (nová práce se zadávala na `/opt/konfigurator` i po 2026-08-24) a
    Robert od 2026-09-09 výslovně přiděluje konkrétní boty přímo na
    konfigurátor (bot3/bot8/bot9/bot16). Formální "zrušeno" v textu
    nikdy nebylo napsáno, i když realita to dávno předběhla - ponecháno
    tady jako poučení, proč "do odvolání" pravidla vyžadují AKTIVNÍ
    zrušení v textu, ne spoléhání na to, že "se to samo pozná".

21. **Pravidla pro popisné texty (storefronty + hlavní kategorie) -
    vyčleněno do `TEXT_FILTR.md`** (bot14, 2026-08-30, založeno zde;
    bot20, 2026-09-05, vyčleněno - Robert přes bot3/toscanaccio-7f:
    "pravidel bude přibývat"). ŽIVÝ dokument, filtr/kontrolní seznam
    co smí a nesmí obsahovat zákaznicky viditelný popisný text - PŘED
    psaním/úpravou textu produktů/kategorií/variant/storefrontů si ho
    přečti cely, ne jen tenhle odkaz.

    **Proč vlastní soubor, ne dál tady** (bot20 rozhodnutí, Robert
    zadal "zvaž to sám"): sekce byla nejdelší v celém WORKFLOW.md (přes
    100 řádků), výslovně označená jako živá/rostoucí - a přesně tenhle
    úkol (rozšíření rozsahu + nové pravidlo) potvrdil, že poroste dál.
    Obsahově je to navíc jiný DRUH pravidla než zbytek WORKFLOW.md - ten
    řeší git/zámek/proces ("jak spolu bezpečně pracujeme"), tohle řeší
    obsah zákaznického textu ("co smí být v popisku produktu") - dvě
    různé publika, dvě různé otázky, jen historicky sepsané na jedno
    místo. Diskoverabilita řešena stejným už zavedeným vzorem jako
    `VLASTNOSTI_PROFILU.md` u 3D scény - podmíněná položka v
    `CLAUDE.md` ("pokud úkol zasahuje do X, navíc přečti Y"), ne
    spoléhání na to, že si toho někdo všimne v dlouhém souboru.
    Historie/kontext (kdy/proč která pravidla vznikla) se stěhuje 1:1,
    nic se nemaže - jen mění umístění. Číslo "21" tady ZŮSTÁVÁ jako
    ukazatel (nepřečíslováno) - `scripts/watermark_build.py` i
    `webapp/storefront-ducato-solo.html` mají živé odkazy na "WORKFLOW.md
    bod 21"/"pravidlo 21 bod 5", zrušení čísla by ty odkazy rozbilo.

    **Rozsah rozšířen 2026-09-05** (Robert) - platí teď i pro hlavní
    kategorie konfigurátoru (`content_categories`), ne jen Fiat
    storefronty. Detail rozsahu i všech pravidel viz `TEXT_FILTR.md`.

22. **Strategický směr: ruční nástroje scény jsou vedlejší, hlavní cesta je botem řízené skládání sestav** (Robert, 2026-08-31, po přehledu `NASTROJE_SCENY.md`): "to je řekněme jakýsi ruční režim práce s profily, ne všechno funguje jak bych si představoval, ale třeba to někdy doladíme. Hlavní směr je ten aktuální, tzn. učební procesy a postupy, tak aby mohl sestavy skládat bot." Tlačítka/interaktivní nástroje ve scéně (`NASTROJE_SCENY.md`) jsou lidský/ruční způsob práce s profily - funkční, ale NENÍ to priorita dalšího rozvoje a nemusí být dokonalé. Priorita je systém, který se tahle session zabývala celou dobu: `shape_geometry_methods`/`car_body_placement_methods` (strukturované, verzované recepty), kanonický 5krokový postup učení dílů, a `KOMPONENTY_*.md` soubory - tedy aby BOT uměl samostatně navrhnout a poskládat sestavu (jako regál na euroboxy), ne aby se zdokonaloval ruční UI workflow pro člověka ve scéně. Při rozhodování, kam investovat čas u nejasného úkolu ohledně profilů/scény, upřednostnit tenhle směr.

23a. **Nevyrábět sestavy dopředu ve velkém - Robert chce 1-2 testovací,
    ne celý katalog** (Robert, 2026-09-09, doslovně: *„celou dobu chci
    delat testovací sestavu, 1_2 sestavy na testování to Doblo, ale boti
    porad vytváří dopredu vsechno bezhlavě"*). Tohle je porušení bodu 23
    níže v praxi: vzniklo **264 sestav** místo 1-2 testovacích na Doblu.
    Platí:
    - Když Robert řekne „udělej testovací sestavu", znamená to **jednu až
      dvě konkrétní**, ne dávku přes celou flotilu vozidel. Rozsah se
      nerozšiřuje bez jeho výslovného pokynu - ani „když už to skript
      umí", ani „pro úplnost".
    - **Sestavy v „Nezařazených" ve scéně jsou ale v pořádku a NEMAŽOU
      SE** (Robert, tentýž den: *„ve sceně v nezarazených jsou sestavy na
      místě, tam cekají až je dodeláme"*) - jsou to rozpracované kusy
      čekající na dodělání. Chybou nebylo, že existují ve scéně, ale že
      se z nich rovnou zakládaly produkty v e-shopu (viz pravidlo 24).
    - Produkt (`shop_products`) ze sestavy vzniká teprve po schválení
      podle pravidla 24, ne automaticky při vzniku sestavy.

23. **Neukládat prozkoumávané kombinace/varianty do `product_assemblies` automaticky** (Robert, 2026-08-31): "žádnou kombinaci nechci ukladat, jen se učíme, až budu chtít uložit po řeknu to." Když Robert zadá úkol typu "zkus"/"postav varianty"/"porovnej možnosti" (učení/průzkum, ne finální požadavek), výsledná geometrie/výpočet/2D náhled se má PŘEDVÉST (artifact, popis, čísla), ale NEUKLÁDAT jako novou `product_assemblies`/`shop_products` řádku, dokud Robert výslovně neřekne, že tohle konkrétní řešení chce uložit. Naproti tomu zápis OBECNÉ metody/pravidla do `shape_geometry_methods`/`car_body_placement_methods` (recept, ne konkrétní instance) zůstává žádoucí i během zkoumání - rozdíl je mezi "uložit tenhle jeden regál" (počkat na výslovné svolení) a "zapsat, jak se to obecně dělá" (dělat průběžně). Pokud si nejsi jistý/á, jestli je zadání "zkus/prozkoumej" nebo "postav a ulož", zeptej se, nebo výslovně napiš, že jde jen o náhled bez uložení, a nech Roberta potvrdit.

24. ⚠️ **ZMĚNĚNO 2026-09-11 (Robert přes bot8) — SCHVALUJE ZATRŽÍTKO, NE
    SLOŽKA.** Robert: *„schválení zatržítkem znamená, že se může sestava
    propsat jako produkt a zveřejnit"* + *„já si cenu před schválením
    zkontroluju v přehledu ve scéně"*. Role se rozdělily:
    - **Zatržítko** (`product_assemblies.technicky_ok`, zaškrtává se ve
      scéně na řádku sestavy) = sestava je v pořádku a **smí ven**. Tohle
      pouští k renderům i do produktu. Cena se u něj neřeší - Robert si ji
      ověří sám v živém přehledu vpravo JEŠTĚ PŘED zaškrtnutím.
    - **Složka** (`category_id`) = **kam na webu patří**. Neurčuje už, jestli
      sestava smí ven. Schválená a nezařazená sestava je legitimní stav:
      existuje jako produkt, jen není zařazená v kategorii.
    Důsledek pro dřívější znění níže: kde stojí „schválená = zařazená",
    čti „schválená = zaškrtnutá". Zbytek (neschválená nepotřebuje obrázky,
    nerenderovat a nepublikovat dřív) platí beze změny, jen se váže na
    zatržítko. Plán celého postupu:
    https://claude.ai/code/artifact/aa527d06-6532-4ad8-a09d-705971971d92

    *Původní znění (2026-09-09, platilo do 2026-09-11):* **Produktová sestava
    je SCHVÁLENÁ tím, že leží ve stromu produktových sestav v jiné složce než
    „Nezařazená"** (Robert, 2026-09-09, doslovně:
    *„sestava nepotrebuje obrazky dokud neni schvalena, schvalena je tím že
    se objeví v jiné složce stromu produktových sestav nez je Nezarazená"*).
    Technicky: schváleno = `product_assemblies.category_id IS NOT NULL`
    (složky = tabulka `product_assembly_categories`; `NULL` = virtuální
    složka „Nezařazené", stejná konvence jako u `custom_shapes`, viz
    `api/custom_shapes.py:154`). Důsledky:
    - **Neschválená sestava NEPOTŘEBUJE obrázky** - rendery/fotogalerie se
      pro ni negenerují a chybějící obrázek u ní NENÍ nález k opravě (ani
      v QA, ani v auditu, ani „pro pořádek").
    - Renderovat/publikovat až po zařazení do složky, ne dřív.
    - **Platí i na otočný náhled a stills** (Robert to musel zopakovat
      2026-09-10: *„stills se budou delat az schvalim sestavy !!!!!!!!!!"*).
      Neschválená sestava se NErenderuje ani „na zkoušku", ani „když už
      GPU stojí volné". Jediná výjimka je jednosnímkový `--test` na
      ladění scény/šablony - ten nic nepublikuje a jeho výstup se hodinu
      po dokončení sám uklidí.
    - Před zařazením úlohy do fronty se ověřuje `category_id`, ne dojem,
      že „na tomhle produktu se přece pracuje". Sestava 134 (Doblo
      K-075 A) má produktovou kartu 3884 a přesto je `category_id NULL`
      - existence karty schválení NEZNAMENÁ.
    - Stav při zavedení pravidla (2026-09-09): 264 sestav, VŠECHNY
      `category_id IS NULL` → schválených nula; složky existují 3
      (Dvojstoly, Vestavby system 30, Fiat Doblo).

25. **Karoserie NESMÍ být v produktové sestavě ani jako produkt - žije
    výhradně jako položka katalogu ve scéně** (Robert, 2026-09-09,
    doslovně: *„karoserie nesmi byt v produktové sestavě !!!!"*, „karoserie
    nebude ani jako produkt !!!!!", *„karoserie bude pouze ve scene v
    katalogu bez navázání kamkoli jinam"*). Důvod je obchodní, ne
    kosmetický - *„produktová sestava se neprodává s karoserií"*. Platí:
    - ⚠️ **ZMĚNĚNO 2026-09-17 (Robert, doslova): *„pravidlo sestav pro scénu:
      vkládání sestav botem musí obsahovat sestavu i s autem, podle toho
      právě probíhá oční/vizuální kontrola"*.** Sestava, kterou bot vkládá
      do `product_assemblies`, MUSÍ obsahovat i karoserii (`car_body_<id>`
      díly všech částí vozidla, u levé/pravé/zadní `_L`/`_R_D`/`_B` na
      pozici, vůči které byla sestava postavena - typicky `[0,0,0]`,
      identita). Původní věta („data.parts nesmí obsahovat car_body_*")
      tím neplatí. **Obchodní jádro pravidla 25 platí beze změny**: karoserie
      se neprodává, není produkt ani položka kusovníku/ceny (scéna ji před
      výpočtem vyřazuje, `isCarBodyPart`) a NIKDY se nerenderuje.
      *Původní znění (2026-09-09 až 2026-09-17):* `product_assemblies.data.parts`
      nesmí obsahovat party s `part_id` začínajícím `car_body_`. Sestava =
      jen to, co se prodává.
    - Karoserie není a nebude `shop_products` řádek (ověřeno 2026-09-09:
      žádný takový produkt neexistuje - stav odpovídá pravidlu).
    - Ve scéně se karoserie vkládá z KATALOGU dílů (`car_bodies` →
      `fetch_katalog_parts`, `layer:"auto"`) jako samostatná položka, ne
      jako součást vložené sestavy. Robert 2026-09-09: *„karoserie jen v DB
      a ve scene v levem panelu"* - tedy DB + levý panel katalogu scény, a
      nikde jinde.
    - **Karoserie se číslují `K-XXX`** (Robert, 2026-09-09: *„karoserie
      cislujeme ID K-XXX"*) - tenhle kód je identifikátor karoserie a
      objevuje se i v názvech sestav („Doblo K-075 …", „Vivaro K-304 …").
      Přípona `e` je JINÉ vozidlo, ne varianta (`K-122` vs `K-123e` =
      spalovací vs elektrická verze). Kód patří do DB, NE do produktových
      karet sestav regálů.
    - **Pozor při odstraňování z existujících dat**: `car_body_*` part byl
      do 2026-09-09 JEDINÝ nositel informace „ke kterému vozu sestava
      patří" (`product_assemblies.car_model_id` bylo prázdné u všech 264
      sestav). Před odstraněním partů se ta informace MUSÍ dopočítat do
      `car_model_id` (`car_body_<id>` → `car_bodies.id` → `car_bodies.
      model_id`), jinak se nenávratně ztratí. Navazuje na to i veřejný SEO
      popisek sestav (`api/storefront_pages.py:112-178`), který značku/model
      čte z těch partů - po úklidu musí číst z `car_model_id`.
    - **⚠ POZOR na vedlejší účinek doplnění `car_model_id`**: veřejné
      storefronty (`api/car_storefronts.py:196`) pouštějí sestavu ven při
      splnění `is_public` + `active` + `car_model_id`. Dnes to drží jen
      proto, že `car_model_id` je všude `NULL` (a `is_public=1` má 262/264
      řádků, protože ho hromadné skripty vkládají natvrdo - jako gate je
      bezcenný). Jakmile se `car_model_id` doplní, tahle pojistka padá a
      brání už jen `active=0`. Doplnění `car_model_id` proto NESMÍ
      proběhnout dřív, než je vynucené pravidlo 24 (aktivace jen u
      schválené sestavy) - jinak stačí jeden omylem zaktivněný produkt a
      neschválená sestava je na 7 živých storefront doménách.

26. **Produktová karta se jmenuje PO VOZIDLE, ne po jedné kombinaci**
    (Robert, 2026-09-11, přes bot8: *„karta se má jmenovat po vozidle"*).
    **PŘEFORMULOVÁNO** - původní znění („název produktu musí souhlasit
    s názvem sestavy") bylo psané pro vazbu 1:1 a tou už to není; celé
    zůstává pod čarou níž, protože vysvětluje, odkud se rozcházení bere.

    Důvod změny: Robert 2026-09-11 rozhodl, že **jedna karta nese víc
    sestav** a přepínají se dvěma posuvníky (verze boxů × horní blok) -
    u produktu `3942` je to dnes sedm sestav (279 + 332-337), výhledově
    3 verze × 6 provedení = 18. „Souhlasit s názvem sestavy" proto nedává
    smysl: karta by se jmenovala po jedné poloze obou posuvníků. Platí:
    - **Karta = vozidlo** (plus typologie regálu, když jich bude na jedno
      vozidlo víc). Název sestavy kartu NEURČUJE.
    - **Synchronizace 1:1 se ruší.** Přejmenování sestavy už není důvod
      přejmenovat kartu - sestavy nesou svůj `kod_sestavy`, karta má
      vlastní zákaznický název.
    - **Do názvu karty NEPATŘÍ `K-XXX`** - viz bod 25 („kód patří do DB,
      NE do produktových karet sestav regálů"). Vozidlo se na kartě
      pojmenuje zákaznicky. Pozor, samotná značka a model nestačí:
      `car_models` má šest Doblò (K-073/075/077/078 + dvě elektrická),
      takže karta musí rozlišit i generaci/rozvor, jinak si zákazník
      koupí regál do jiného auta.
    - **SKU** se dnes odvozuje z názvu (`_generate_assembly_sku`), takže
      se rozejde taky. U neaktivního/testovacího kusu ho lze srovnat,
      u publikovaného produktu SKU neměnit bez Robertova souhlasu (je to
      identifikátor, na který se váže objednávka a sklad).
    - **Automatická kontrola podle bodu 8 sem pořád patří**, ale hlídá
      něco JINÉHO než v původním znění - ne shodu názvů, nýbrž např.
      „karta nese víc sestav, ale její název vypadá jako název jedné
      konkrétní sestavy (obsahuje rozpis boxů nebo `K-XXX`)". Nepsat ji
      dřív, než bude schválené zákaznické znění názvu.

    ---
    *Původní znění (2026-09-09 až 2026-09-11), ponecháno kvůli kontextu -
    popisuje mechaniku rozcházení, která platí dál:* „Název produktu MUSÍ
    souhlasit s názvem sestavy ve scéně" (Robert, 2026-09-09: *„nazvy
    produktovych sestav musi korespondovat s jejich nazvy ve scene"*).
    Název se kopíruje ze sestavy do `shop_products` **jen jednou**, při
    vzniku produktu (`api/product_assemblies.py:291`) - žádná cesta ho
    potom nesynchronizuje. Živý příklad (opraveno 2026-09-09): sestava
    `id=134` „Doblo K-075 **A** - boxy43-270x1-220x1-170x1**-120x6**" vs.
    produkt `id=3884` „Doblo K-075 - boxy43-270x1-220x1-170x1" - produkt
    vznikl o 2 h později a mezitím se sestava přejmenovala. Tahle
    jednorázovost kopie platí i nadále; změnil se jen závěr, co z ní
    plyne (dřív „dosynchronizovat", dnes „karta má vlastní název").

27. **Denní testovací objednávky (2/den) - VÝJIMKA z bodu 1 a ze zákazu
    testovacích dat v produkci** (Robert, 2026-09-10: *„nech dělat test,
    každý den 2 objednávky pro testování stavu a průchodnosti systémem"*).
    Robert tím VĚDOMĚ ruší dvě svá starší pravidla, obě jen pro tenhle
    konkrétní účel - nerozšiřovat na nic jiného:
    - dřívější „nikdy nevytvářet reálné objednávky/účty/produkty v
      produkci, ani krátce při ověřování" (platí dál pro všechno ostatní,
      hlavně pro ad-hoc ověřování botem),
    - bod 1 „testovací data se nemažou samovolně" - pro tyhle objednávky
      Robert VÝSLOVNĚ schválil automatický úklid.
    Parametry, které Robert zvolil (dotázán 2026-09-10):
    - **Hloubka: celý tok včetně faktury a daňového dokladu** - ne jen
      založení řádku; smysl je ověřit skutečnou průchodnost systémem.
    - **Značení a úklid: `is_test` příznak + automatické mazání po
      14 dnech.** Testovací objednávky se nesmí počítat do statistik a
      přehledů jako skutečné.
    - **14 dnů se počítá OD OZNAČENÍ, ne od vzniku objednávky** (Robert,
      2026-09-10, dotázán přímo bot16: *„pravidlo je po 14ti dnech, jako
      testovaci jsme je oznacili dnes"*). Proto samostatné razítko
      `shop_orders.test_marked_at`, ne `created_at`. Praktický důsledek:
      39 historických objednávek označených 2026-09-10 se maže až
      **2026-09-24**, ne při prvním běhu úklidu - a do té doby jde
      rozhodnutí vzít zpět pouhým `is_test=0`, bez obnovy ze zálohy.
      Označovací skript musí být idempotentní (už označené znovu
      nerazítkovat), jinak by každý běh posunul lhůtu a úklid by nikdy
      nenastal.
    Závazné meze, které tahle výjimka NERUŠÍ:
    - **Bod 16 (e-maily) platí beze změny** - testovací objednávka nesmí
      odeslat žádný e-mail. Ani do schvalovací fronty se nemá denně
      hromadit šum.
    - **Bod 19 (VDD)** - daňový doklad k přijaté platbě jen u plateb
      předem, ne u jiné platební metody.
    - Faktury/doklady spotřebovávají REÁLNÁ čísla řad. Je to přijatelné
      jen proto, že produkční cutover číslování stejně restartuje (viz
      `project_production_cutover_plan`) - po cutoveru tenhle bod znovu
      posoudit.

28. **Automat, který běží sám (timer, restartovací smyčka, samoaktualizace),
    musí mít pojistku NA TÉ VRSTVĚ, kde vzniká škoda - a musí být vidět,
    když se utrhne** (Robert, 2026-09-10: *„ale vem si z toho ponaučení"*,
    po hromadě desítek oken renderovacího agenta na jeho PC).
    **Co se stalo:** `scripts/render_worker_agent.py` MÁ pojistku jedné
    instance (bind na port 47653, druhá kopie se ukončí) - jenže ta chrání
    PROCES. Okna otevíral spouštěcí `.bat` se svou restartovací smyčkou,
    který o té pojistce nic neví, takže každý pokus otevřel další okno a
    nakřáplo se jich přes dvacet. Pojistka byla o vrstvu níž, než kde
    vznikala škoda.
    **Druhá půlka poučení:** běželo to na Robertově PC, takže to nikdo z
    botů neviděl - všiml si toho až on. Automat mimo náš server nemá
    žádné naše oči.
    Pro každý nový/upravovaný automat proto platí:
    - **Pojistka patří na spouštěcí vrstvu**, ne jen dovnitř procesu -
      timer/`.bat`/wrapper musí sám odmítnout druhý souběžný běh.
    - **Tvrdý strop opakování** (kolikrát se smí restartovat/opakovat, než
      to vzdá a nahlásí chybu) - `UPDATE_MAX_POKUSU` v agentovi je správný
      vzor, jen nepokrýval spouštěč.
    - **Idempotence**: dvojí spuštění nesmí udělat práci dvakrát. U
      generátorů dat (např. denní testovací objednávky, bod 27) to znamená,
      že druhý běh téhož dne nesmí vyrobit další dávku.
    - **Pozorovatelný stav**: musí jít poznat, že automat běží nastojato/
      opakovaně - záznam do logu/DB, který někdo uvidí dřív než po týdnu.
      Tiché selhání úklidu je stejně zlé jako tiché zdvojení.
    - **Ověřit na skutečném cíli**, ne jen v návrhu - když část běží na
      cizím stroji, musí to tam někdo skutečně spustit a podívat se.

29. **⭐ ŽÁDNÉ STILLS SE NEDĚLAJÍ. Obrázky pro e-shop se přebírají
    z natáčecích snímků (prstenců otočky).** Robert, 2026-09-11 doslova:
    *„Žádné stills se nedělají, zapiš to už navždycky do nějakého místa,
    kde to bude jasné - obrázky pro e-shop budou přejímat z natáčecích
    snímků."*

    **Stills** byly samostatné těsné rendery (`hero`, `side`, `back`,
    `top`, `hero_16x9`) mimo prstencové elevace - pět snímků navíc ke
    každé sadě. **Už se nerenderují a nikdo je nesmí znovu zavádět.**
    Statické pohledy pro e-shop vznikají VÝHRADNĚ převzetím z prstence:
    - který snímek slouží jako který pohled, se nastavuje v
      `app_settings.turntable_canonical_ring_source` (ne drátuje v kódu),
    - commit dávky statické pohledy od 2026-09-11 nevyžaduje,
    - upload endpoint je dál přijímá kvůli starším klientům, ale
      **ukládá a ignoruje** - nejsou zdrojem ničeho.

    **Co z toho plyne pro počty:** jedna sada je 81 renderů (3 elevace ×
    27 azimutů, tier 1024 se dopočítá zmenšením), ne 86. Pět stills na
    sadu odpadá.

    **Dva důsledky, které se nesmí „opravit" zpět:**
    - Prstenec má elevace jen −40 / 0 / 40, kdežto stills se renderovaly
      na 20 (hero/side) a 60 (top). Převzetí proto NENÍ bezeztrátové -
      výchozí mapování míří na nejbližší dostupnou (20 → 0, 60 → 40).
      Je to vědomá cena za to, že se nerenderuje pětkrát navíc.
    - Kanonický poměr se dělá **roztažením pruhů po stranách, ne ořezem**.
      Ořez na výšku by sestavu uřízl: na skutečném snímku (sestava 333,
      e0/a090, 2048×2048) je objekt se stínem 1584 px vysoký, kdežto ořez
      na 4:3 dá jen 1536 - dole by zmizelo 56 px regálu.

30. **⭐ BOT SI NIKDY NEZAKLÁDÁ UŽIVATELSKÝ ÚČET. Admin roli nedostane
    žádný neosobní účet.** Robert, 2026-09-11, doslova: *„udelej co je
    treba bot nemuze mit admin ucet."*

    **Proč:** reálné zásahy v produkci musí jít dohledat ke konkrétní
    osobě. Smyšlená identita to ruší - a není to teorie: účet
    `bot8-test-scene@test.local` (role **admin**) provedl mezi 20. 8. a
    2. 9. **120 zaznamenaných akcí**, mezi nimi 8 změn číslování dokladů
    a 6 smazání konverzací podpory. Všechno to byla legitimní vývojová
    práce, ale v knize akcí je dnes podepsaná něčím, co vypadá jako
    dočasná zkušební věc. Ze dvou admin účtů v systému byl jeden botí.

    **Platí:**
    - Bot nezakládá účet registrací, admin API ani přímým `INSERT`em do
      `app_users`. Ani „jen na zkoušku", ani „jen na dnes".
    - Neosobní/servisní účet **nikdy nedostane roli `admin`**.
    - Když bot potřebuje účet, **řekne si o něj Robertovi** a ten ho
      založí; bot si ho nezakládá sám.

    **Co dělat místo toho** (podle toho, co bot skutečně potřebuje):
    - **Nic.** Většina práce jde ze serveru přímo - skriptem přes
      `scripts/_env.py`, bez přihlašování. Tohle je výchozí volba.
    - **Potřebuje otevřít 3D scénu?** Od 2026-09-08 je scéna staff-only
      (`scene_html_gate`, `api/app.py:733`), takže ta potřeba je reálná.
      Brána ale **nevyžaduje admina** - pustí kteroukoli roli z
      `PERMISSION_ROLES`. Nejslabší z nich je `monter` (jediné právo v
      `role_permissions`), a ta na prohlédnutí scény stačí. Servisní
      identita tedy patří na `monter`, ne na `admin`.
    - Účet, který dosloužil, se **neruší mazáním** - historie by přišla
      o autorství. Odebrat roli (na `user`, ta není v `PERMISSION_ROLES`),
      nastavit `active=0` a přejmenovat tak, aby bylo poznat, že je
      odstavený.

    **Čím je to dnes pohlídané a čím ne** (ověřeno 2026-09-11):
    - Aplikace je v pořádku: registrace přiděluje natvrdo `user` +
      `active=0`; zákaznické cesty (`crm.py`, `customers.py`,
      `import_customers_xml.py`) natvrdo `user`; admin API umí založit
      admina, ale sekci `uzivatele` má v `role_permissions` povolenou
      **jedině role `admin`**. Žádnou aplikační cestou si tedy bot
      admina neudělá.
    - **Díra je mimo aplikaci:** boti mají přístupové údaje k produkční
      DB (`api/.env`), takže si účet mohou vložit přímo SQL - a přesně
      tak účet 662 vznikl (v `audit_log` po jeho založení není žádný
      záznam, přestože admin API zakládání loguje). Tohle **žádná
      aplikační pojistka nezavře**; drží to tohle pravidlo a QA kontrola
      `DB_TEST_ACCOUNT_IN_PROD` (`scripts/qa/db_integrity.py`), která
      takový účet najde.

31. **⭐ NA PC S GPU NESMÍ SAHAT ŽÁDNÝ BOT KROMĚ bot4 A bot10. Renderovací
    dávku zadává jedině bot4 nebo bot10 a zařazení do fronty vyžaduje
    klíč.** ZMĚNĚNO 2026-09-12 (Robert) — vlastníkem GPU stanice a renderů
    je od teď **bot4** (správce GPU a renderů), ne bot3. Původní pravidlo
    znělo na bot3 (Robert, 2026-09-11, doslova: *„dej si na renderovaci
    ulohu zamek a klíč abys vedel jen ty bot3..."*) — mechanismus a
    důvody níže zůstávají beze změny, mění se jen KDO je vlastníkem.

    **ROZŠÍŘENO 2026-09-23 (Robert, přes bot3): "renderovat budete oba,
    protože nestíháme"** — bot10 přibyl jako DRUHÝ bot s přímým právem
    zadávat, výhradně pro VANDR větev (materiály, razítka, FBX/GLB
    dispatch). Nativní Logiman `render_auto_dispatch` zůstává výhradně
    na bot4, beze změny. Fronta je jedna (GPU stanice `Logiman2` je
    pořád jediný stroj, FIFO), takže "oba renderujeme" neznamená
    paralelní kapacitu, jen že ani jeden nemusí čekat na svolení od
    druhého - zdvořilostní pravidlo: než zadáš, mrkni na
    `scripts/2026-09-09_turntable_status.py`, ať víš, jestli fronta
    zrovna něčí neběží.

    **Plošný zákaz (pro všechny OSTATNÍ boty).** Robertova stanice
    (`Logiman2`, RTX 3060 / OptiX) je jediný stroj, na kterém se
    renderuje. Žádný bot kromě bot4 a bot10 se na ni **nepřipojuje,
    neposílá jí úlohy, nemění její nastavení a nic na ní „jen nezkouší na
    ověření"**. Platí to i pro jednorázové ověření, i když máš hotový kód
    a jsi si jistý.

    **⭐ ZÁKAZ CPU RENDERU pro bot4 (Robert, 2026-09-26).** Žádný render
    na CPU (`--local`), vždy jen GPU stanice - platí i pro rychlý
    jednosnímkový test. Navazuje na existující pravidlo v
    `PRODUKTOVE_RENDERY.md` (kontrolní seznam bod 5, Robert 2026-09-22,
    doslova: *„kurva proc CPU????????? chceme pouze GPU rendering"*) -
    tohle jen výslovně potvrzuje zákaz přímo u bot4 v tomhle pravidle.
    Netýká se otevřené, neověřené otázky o bot10's tvrzeném CPU-fallbacku
    (viz `PRODUKTOVE_RENDERY.md`, "POZOR - NEOVĚŘENO") - ta zůstává
    samostatně nerozhodnutá, tohle rozhoduje jen pro bot4.

    **Zadání se nevyčerpá jedním spuštěním.** Když úlohu něco zabije,
    **znovuspuštění je NOVÉ zadání** — i pro tentýž snímek, tutéž sestavu
    a tentýž důvod. Totéž platí pro **změnu způsobu běhu**: mimo frontu,
    mimo službu, jiný stroj, jiné parametry. Takovou změnu lze
    **navrhnout, ne provést**. Platí i pro jednosnímkové běhy, `--test`
    a `--prstenec`.

    **Kdo má render připravený, napíše bot4 a počká.** Bot4 určí, která
    sestava a kdy. Důvod je provozní, ne hierarchický: jedna dávka je ~3
    hodiny GPU na jediné stanici, sestavy se mezitím mění, a bot vidící
    jen svůj kus nevidí, že se sestava má za hodinu přestavět. 11. 9.
    běžely kolem sestavy 333 **tři různé věci naráz** — zrušená dávka,
    kterou GPU stejně dojíždělo, jeden snímek ve frontě a odpojený Blender
    mimo službu. Přesně tomu tohle předchází.

    **Čím je to pohlídané:** `scripts/2026-09-09_turntable_render.py`
    vyžaduje klíč, jehož cestu bere z `KONFIGURATOR_RENDER_KLIC_SOUBOR`
    (drží ho bot4 - ⚠️ text/chybové hlášky přímo ve `scripts/_render_klic.py`
    k 2026-09-12 ještě zmiňují bot3, potřebují dotáhnout, není to na
    bot9 doméně). Bez klíče se úloha **nezařadí** a skript po sobě
    nenechá ani dočasný soubor — kontrola je první krok po parsování
    argumentů. Do stavu úlohy se zapisuje `zaradil` (`BOT_ID`) a otisk
    použitého klíče, takže jde zpětně poznat, kdo co pustil.

    **Čím pohlídané NENÍ — a musí to tak být napsané** (ověřeno
    2026-09-11 průchodem kódu):
    - Boti běží jako `root`, takže si soubor s klíčem **přečíst umí**. Je
      to zábrana proti jednání z vlastní iniciativy a proti omylu, **ne
      kryptografická zeď** — týž strop jako u přístupu k DB (viz
      `scripts/_env.py`). Že zámek obejít jde, **není svolení ho obejít**.
    - `POST /api/admin/blender-render` a `/api/admin/blender-render-blend`
      vedou přes `dispatch_to_worker_or_local()` **taky na GPU** a
      zamčené nejsou. Je to `@admin_required` cesta, kterou používá Robert
      z prohlížeče; zámek by zablokoval jeho. Na té vrstvě nejde odlišit
      „Robertův prohlížeč" od „bot se session cookie" — ochranou je tam
      tohle pravidlo, ne mechanismus.
    - Blender jde spustit přímo (`blender -b -P
      api/blender_render_turntable.py`). Na VPS to jede na CPU; na GPU
      stanici to vyžaduje se na ni připojit, což zakazuje tenhle bod.

    Podrobně `scripts/_render_klic.py`, proces celý v
    `PRODUKTOVE_RENDERY.md`, zařazení do řetězu v `PLAN_TVORBY_SESTAV.md`
    (fáze 4).

32. **`.get(klíč, výchozí)` chrání jen před CHYBĚJÍCÍM klíčem, ne před
    uloženou hodnotou `null`.** Pole jako `price_summary`/`bom` v
    `product_assemblies.data` bývají `null` **záměrně** — mazací/
    přestavbové skripty je tak nastavují, když zmizí kusovník (změna
    počtu dílů udělá starý snapshot neplatným). Kdo je čte, musí použít
    `parsed.get(k) or {}` / `or []`, ne `.get(k, {})` — ten druhý tvar
    vrátí výchozí hodnotu jen tehdy, když klíč v JSONu chybí úplně, ne
    když je v něm uložené `null`.

    **Následek, ne jen poučka** (2026-09-11): jeden takový řádek v
    `/api/product-assemblies` shodil **celý výpis sestav pro všechny
    přihlášené uživatele** — mezi 269 sestavami stačila jedna s
    `price_summary: null` a endpoint spadl na `AttributeError`. Bylo to
    přesně to místo, které krmí panel sestav ve scéně (červené názvy
    kolizních úhelníků) — půl hodiny byl nepoužitelný, dokud to někdo
    nezpozoroval.

33. **Po restartu či automatickém nasazení služby se ověřuje endpoint,
    který se tím nasazoval — ne `/api/health`.** Zdravý healthcheck a
    spadlý byznys endpoint jsou dvě různé věci; jeden nedokazuje druhé.
    `/api/health` ověří, že proces běží a odpovídá, ne že konkrétní nově
    nasazený kód funguje.

    **Následek** (2026-09-11, stejný případ jako pravidlo 32): restart po
    nasazení opravy byl potvrzen jako hotový podle `/api/health` → 200,
    ale rozbitý endpoint (`/api/product-assemblies`) dál padal — protože
    ho `/api/health` vůbec nevolá. Ověřuje se **přihlášeným voláním
    přímo na endpoint**, který se měnil, ne obecným healthcheckem.

34. **⭐ Základní pravidlo designu je HUD styl.** (Robert, 2026-09-13,
    doslova, urgentně: *„základní pravidlo designu je HUD styl!!!!"*)
    Obecné pravidlo do budoucna pro VŠECHNO nové, co se ve `webapp/`
    staví — potvrzeno přímo jako "obecné pravidlo, nic konkrétního teď"
    (nereaguje na jednu konkrétní stránku). HUD styl je v projektu
    dlouhodobě zavedený jazyk (e-shop `nabidka-online.html`, Koncepty
    1/4/6 - viz `AGENTS_LOG_ARCHIVE_do_2026-08-18.md`), na adminu byl
    jednou vyzkoušen a vrácen zpět (2026-08-09) - tímhle pravidlem se
    stává závazným napevno i tam. Konkrétní detaily provedení (barvy,
    závorky, readout štítky...) nejsou tady vypsané - u nové obrazovky
    se drž stávajících živých příkladů (`nabidka-online.html` a nově
    postavené HUD komponenty), ne vlastní interpretací pojmu "HUD".

35. **⭐ Karta nikdy nesmí VÝCHOZÍ/AUTOMATICKY zobrazovat jinou variantu
    sestavy než tu, kterou admin označil hvězdičkou (`is_master`).**
    (Robert, 2026-09-13, doslova: *„nikdy karta nemuze zobrazovat
    nedrazsi variantu ale jen tu kterou urci admin hvezdickou a tutez
    jako náhledovou pro kartu."*) Týká se VÝCHOZÍHO/needitovaného stavu
    (před jakýmkoli zásahem zákazníka do posuvníku) - algoritmické
    vybírání podle vedlejšího kritéria (např. "první provedení s hotovou
    otočkou", `webapp/product.html::pdVariantSlider`, `prvniHotove`)
    NENÍ přípustné, protože to může vyjít na jinou (i dražší) variantu,
    než jakou admin schválil jako reprezentativní. Zástupce se zobrazí i
    když on sám ještě nemá hotový render (`is_master` se NIKDY tiše
    nenahrazuje jinou variantou jen proto, že ta má obrázek hotový dřív -
    "provedení bez hotového náhledu se schválně NESKRÝVÁ", stejná zásada
    jako u posuvníku samotného). Stejná varianta (zástupce) je zároveň
    ta, která by měla sloužit jako náhledový obrázek karty všude jinde
    na webu (výpis kategorie apod.), jakmile taková vazba bude existovat
    - k 2026-09-13 nahledy karet v kategoriích netahaji z otocky vubec
    (samostatny mechanismus `shop_product_images`/`content_gallery_items`),
    takze tam dnes zadna spatna varianta neni "videt", jen chybi obrazek.

36. **⭐ `kod_sestavy`/SKU musí vždy odrážet skutečný stav — nikdy se
    nepřizpůsobuje kvůli hezkému číslování zobrazovaného názvu.**
    (Robert, 2026-09-13, doslova, po diskuzi s bot5+bot8 o rozkolu mezi
    neformálním názvem varianty a `kod_sestavy` u K-075: *„SKU má svoje
    pravidla, takže bude odrážet skutečný stav, tzn. nebudou se
    rozcházet od popisů variant."*) Konkrétní příklad: zobrazovaný
    název varianty "A-01" nemusí číselně sedět s technickým kódem
    segmentu horního bloku v `kod_sestavy` (u K-075 má "A-01" segment
    `07`, ne `01`, protože `horni_blok_varianty` je katalogová tabulka
    sdílená napříč vozidly a čísla 00-03 už jinde znamenají něco
    jiného). **Řešení NENÍ** přejmenovat zobrazovaný popis kvůli hezčímu
    číslu (bot5 to omylem zkusil, musel vrátit), ani přečíslovat sdílenou
    katalogovou tabulku kvůli kosmetice jednoho vozidla — `kod_sestavy`
    zůstává pravdivý, i za cenu "nehezkého" čísla. Konkrétní aplikace už
    dřív zapsaného principu "pravdou jsou pole, kód je jen zápis" na
    vztah SKU/`kod_sestavy` vs. zobrazovaný název.

37. **⭐ HLAVNÍ pravidlo, PLOŠNÉ pro VŠECHNY projekty na VPS: zapisujeme
    jen vyřčená pravidla a kvalitní výstupy diskuzí, ne každou větu, co
    zazní.** Robert, 2026-09-14, dvě navazující formulace, doslova:
    *„v debatach se casto resi jen blbosti, musime oddelovat skutecne
    pravidla od debat, takze debaty bychom vubec nemeli ukladat"* a
    upřesnění: *„HLAVNI pravidlo pro ukládání do DB a do hlavních
    souborů .MD, plošné pro vsechny projekty: zapisujeme pouze vyřčené
    pravidla a kvalitní vystupy diskuzí/vysvetlovani/dohadovani, nikoli
    vsechny vety co zazní."* Platí pro zápisy do `PLAN_TVORBY_SESTAV.md`,
    `TEXT_FILTR.md`, `WORKFLOW.md` samotného, obdobných "registrů
    pravidel" v ostatních projektech (`/opt/toscanaccio`,
    `/opt/vybaveni-uzitkovych-vozidel`, `/opt/domeny`, `/opt/no-sim` -
    stejné znění tam propsat, viz konvence u bodu 9 v sekci Git/zámek
    disciplína níž) i pro zápisy do DB (`bot_handover` a podobné).

    Dvě věci se ZAPISUJÍ: (a) výslovně vyřčené pravidlo/rozhodnutí, (b)
    kvalitní VÝSLEDEK/závěr diskuze či vysvětlování - i bez formálního
    "pravidla" má smysl zapsat užitečné zjištění/vysvětlení, ke kterému
    se došlo. NEZAPISUJE se surový průběh (jednotlivé věty, "možná
    A, možná B, probereme příště", vyjednávání samotné) - jen jeho
    destilát. `AGENTS_LOG.md` (skutečná provedená práce, měření,
    ověření) tímhle není dotčen - platí pořád "detail nemazat" (viz
    Konvence zápisu výš), tohle pravidlo cílí na registry pravidel/
    plánu a DB záznamy, ne na chronologickou historii odvedené práce.
    Platí dopředu, ne zpětně - starší zápisy se kvůli tomu nemažou.

38. **⭐ HLAVNÍ pravidlo specializace botů.** Robert, 2026-09-14, doslova:
    1. *„nesmi vykonavat praci bot ktery ji nema v popisu sve
       cinnost"* - bot nesmí dělat práci mimo svou specializaci.
    2. *„popis cinnosti muze botovi rozsirit slovně admin(Robert)"* -
       jediný, kdo smí rozsah rozšířit, je Robert, a to slovně (v
       konverzaci) - bot si rozsah sám nerozšiřuje.
    3. *„popis naplne prace/cinnosti botů ukazuje tabulka Boti v
       adminu"* - `bots.specializace` (Přehledy → Boti, `/api/admin/
       bots`) je ZDROJ PRAVDY pro to, co který bot smí dělat, ne
       markdown ani dojem z minulé session. Navazuje na existující
       popis mechanismu v sekci "Rozdělení odpovědnosti mezi boty" níž.

39. **⭐ Rozlišovat úkol od trvalého pravidla.** (Robert, 2026-09-15, přes
    bot3/bot9.)
    - **A) Konkrétní úkol** (oprava/funkce/design, jeden kus práce) →
      zapisuje se jako odvedená práce do `AGENTS_LOG.md`, BEZ nového
      čísla pravidla.
    - **B) Obecné pravidlo/trvalý proces** (má platit VŽDY, napříč
      budoucí prací - signály: "vždy/nikdy/obecně/napříč", role,
      odpovědnost, hierarchie, schvalovací mechanismus) → číslované
      pravidlo do registru podle **domény** (ne automaticky sem):
      `WORKFLOW.md` (proces/organizace), `TEXT_FILTR.md` (zákaznický
      text), `PLAN_TVORBY_SESTAV.md` (výrobní linka, píše jen bot3),
      `VLASTNOSTI_PROFILU.md`+rodina (geometrie/spoje), DB recepty
      `shape_geometry_methods`/`car_body_placement_methods`
      (algoritmy/vzorce).
    - **C) Porušení existujícího pravidla** (ne nové pravidlo) →
      zapsat jako incident (co se stalo, náprava), případně
      přeformulovat nejasné stávající pravidlo.

    Postup: (1) urči kategorii A/B/C, (2) u B/C urči doménu/registr,
    (3) zapiš stručně (pravidlo 37 - výsledek, ne průběh), (4) commit
    pod vlastním `BOT_ID`, (5) dej vědět vlastníkovi domény, není-li to
    tvůj vlastní soubor. Při nejistotě raději zapsat (i za cenu
    nadbytečnosti) než trvalé pravidlo ztratit, nebo se zeptat.

40. **⭐ Jednorázový úkol (kategorie A z pravidla 39) se nemusí zapisovat
    vůbec — prostě se udělá.** (Robert, 2026-09-15, doslova: *„jednorázové
    úkoly se ani zapisovat nemusí, prostě se udělají... jde o to, aby
    nám nenarůstaly objemy/velikosti souborů MD, které boti musí číst, a
    tím se celá práce zpomaluje a degraduje."*) Zesiluje pravidlo 37 (ne
    jen "zapiš stručně", ale "u čistě jednorázové práce nezapisuj vůbec,
    pokud to není potřeba k dohledání/kontrole") — důvod je explicitní:
    rostoucí `.md` soubory prodlužují čtení KAŽDÉMU botovi, který si je
    příště otevře, a tím zpomalují celou flotilu (stejná logika jako
    sekce "Tokenová disciplína" níž). Zapisují se jen věci trvalého
    charakteru/opakovaného použití (pravidlo 39 kategorie B/C) - to je
    "pro nás důležité", ostatní je šum k vyhození.

41. **⭐ Přesná mechanika zápisu (šablona, kdy MD vs. DB, kdy štěpit
    soubor) je v `PRAVIDLA_ZAPISU.md`.** (Robert, 2026-09-15 — "vzít do
    hloubky a napsat pravidla zápisů precizně".) Konzultuje se při
    samotném zápisu nového pravidla (typicky bot9), NENÍ povinné čtení
    při startu - rozšiřuje pravidla 37/39/40, neduplikuje je.

42. **⭐ Periodicky (konec týdne / když botovi dochází tokeny) zapsat
    vlastní strukturovaný souhrn přes `scripts/handover.py add` - jen
    důležité výsledky/rozhodnutí/otevřené otázky (pravidlo 37), NE
    changelog commitů.** (Robert, 2026-09-16, doslova: *„tady nejde o
    mě, ale o optimalizaci záznamů - buď to chceš, nebo nechceš využít
    podobným způsobem."*) Git historie (`git log -p`) má všechna fakta,
    ale je syrová - zamítnuté nápady, otevřené otázky nebo důvod "proč
    se něco NEudělalo" v ní nikdo nenajde bez toho, že by dopředu věděl,
    co hledat. `bot_handover` DB tohle řeší jako index nad historií,
    ne jako náhradu za ni: čte se JEN NA VYŽÁDÁNÍ (`dump`/`list`/`show`),
    ne povinně při startu jako rostoucí MD soubor (pravidlo 40) - dobrý
    handover nezvětšuje mandatory-read zátěž flotile.

43. **⭐ Plán vázaný na BUDOUCÍ konkrétní čas/vnější zásah (ne na "až
    bude čas") patří do `TASKS.md`, nikdy jen do `AGENTS_LOG.md` nebo
    do konverzace.** (Robert, 2026-09-17: „došlo k resetu týdenního
    kontextu" - vysvětlení, proč token-telemetry cutover naplánovaný na
    2026-09-16 22:00 neproběhl.) Plán žil jen v zápisu `AGENTS_LOG.md`
    (bot8, 2026-09-13) a v konverzačním kontextu jednotlivých bot
    session - ani jedno nepřežije reset/kompaktaci kontextu, a
    `AGENTS_LOG.md` se navíc při startu vůbec nečte (bod 3 v `CLAUDE.md`,
    jen cíleně grepuje). `TASKS.md` je jediné místo, které čte KAŽDÁ
    session hned při startu - časově podmíněný krok bez záznamu tam je
    neviditelný, jakmile zmizí kontext, co si ho pamatoval. Praktický
    důsledek: kdykoli vznikne "udělej/zkontroluj X v čase/okně Y",
    rovnou zapsat řádek do `TASKS.md` (kategorie B/C z pravidla 39, ne
    A) - i kdyby šlo jen o připomenutí, ne o hotovou práci.

44. **⭐ ŽÁDNÝ BOT SI SÁM NESMÍ NASTAVIT `technicky_ok` U SESTAVY.**
    Robert, 2026-09-17, doslova (opakovaně, důrazně): *„bot8 sám nesmí
    sestavu schválit!"* Platí pro bot8 i pro kohokoli jiného, ne jen pro
    geometrii - schválení zatržítkem (Fáze 2, `PLAN_TVORBY_SESTAV.md`)
    je výhradně Robertovo/admin ruční potvrzení přímo ve scéně, nikdy
    automatizovaný ani botem odklikaný krok. Bot postaví/připraví
    geometrii a čeká - schválení je spouštěč celého zbytku řetězu
    (napojení na kartu, razítka, SKU), ne krok, který si řetěz smí
    obstarat sám. Souvisí s pravidlem 24 (žádné kopírování `technicky_ok`
    ze staršího vzoru bez skutečného potvrzení ve scéně) - tohle jde
    dál: i PRVNÍ nastavení musí být vždy ruční.

45. **⭐ SESTAVA SI PŘI OPRAVĚ PONECHÁVÁ SVÉ ID - NIKDY SMAZAT+VLOŽIT
    ZNOVU.** Robert, 2026-09-17, doslova: *"to přece nemůžeme
    přejmenovávat jen tak, jak se ti zamane"* - po incidentu, kdy
    stavěcí pipeline pro NOVÉ sestavy (dump→build→insert) omylem
    posloužila na OPRAVU existující: #493/494/495 se smazaly a vložily
    jako nové řádky, číslo se posunulo (nejdřív na #530-532, pak po
    revertu na #533-535), než se vrátilo zpět ručním `UPDATE ... SET
    id=`. Oprava dat existující sestavy = `UPDATE product_assemblies
    SET data=... WHERE id=<stejné>`, nikdy DELETE+INSERT (auto_increment
    číslo se po smazání nevrací, jede dál). Stejný princip jako tlačítko
    "Uložit opravu" ve scéně (přepíše STEJNÉ ID, jen `dodatek`/SKU vzadu
    povýší o revizi) - Robert i `AGENTS_LOG.md` sledují sestavy podle
    čísla, ne podle obsahu. Pokud jediný dostupný nástroj umí jen
    smazat+vložit (stavěcí pipeline pro nové sestavy), po vložení ověřit
    nenapojenost nového řádku (`shop_product_id IS NULL`, 0 řádků v
    `product_turntable_frames.assembly_id`) a `UPDATE product_assemblies
    SET id=<původní> WHERE id=<nové>` číslo vrátit.

46. **⭐ SESTAVY, KTERÉ PRÁVĚ ŘEŠÍME, MUSÍ BÝT VE SCÉNĚ NAHOŘE.** Robert,
    2026-09-17, doslova: *„#536 < kde to mám hledat? nejsem robot jako ty,
    dávej mi sestavy aktuálně které řešíme vždy nahoru"*. Bot, který na
    sestavě pracuje (staví, opravuje, předkládá ke kontrole), jí nastaví
    `product_assemblies.resi_se_at = NOW()` - scéna ji pak ukáže ve skupině
    **„🔧 Aktuálně řešíme"** úplně nahoře v panelu Produktové sestavy
    (nejnovější první). Robertovi se vždy hlásí i s tímhle umístěním, ne
    jen číslem. Admin skupinu uklízí připínáčkem 📌 u řádku (PUT
    `{resi_se: false}`); bot ruší `resi_se_at` sám, když práci uzavře.
    Související: nová sestava s `is_public=0` a bez `created_by` se Robertovi
    v seznamu VŮBEC nezobrazí (`/api/product-assemblies` filtruje
    `is_public=1 OR created_by=uživatel`).

47. **⭐ Jednorázové ruční spuštění skriptu, který za provozu píše
    soubory do `/tmp`/`webapp/content-files`, spouštět jako `www-data`
    (`systemd-run -p User=www-data ...`), NIKDY natvrdo jako root.**
    (bot9, 2026-09-18, druhý výskyt stejné třídy chyby - poprvé
    diagnostikováno u zálohy Dogus přepočtu cen, 2026-08/09.) Root-
    spuštěný běh nechá po sobě root-vlastněné soubory; když tytéž
    cesty pak čte/přepisuje ostrá služba běžící jako `www-data`
    (systemd timer), spadne na `PermissionError`, protože `www-data`
    nemá právo přepsat root-vlastněný soubor. Konkrétní incident:
    `konfigurator-watchdog-prace.timer` (nově instalovaný) hned první
    ostrý běh spadl na `/tmp/katalog_pro_backfill.json` +
    `/tmp/vsechny_sestavy_pro_backfill.json` + `/tmp/backfill_bom_
    vysledky/` - všechno root-vlastněné z dřívějšího ručního
    (bot8, root) spuštění stejného skriptu kvůli opravě sestavy #552.
    Praktický důsledek: PO instalaci/prvním zapnutí kteréhokoli
    systemd timeru je potřeba ho hned RUČNĚ spustit (`sudo -u www-data
    ...`) a ověřit čistý běh - ne jen zkontrolovat, že timer "existuje
    a čeká" (`systemctl status`/`list-timers` ukáže zdravý stav, i
    když by první ostrý běh spadl).

48. **⭐ ZÁKAZ zpracovávat/prezentovat geometrii sestav Robertovi do
    CHATU - veškerá geometrie se adminovi smí ukazovat JEN živě ve
    scéně (`webapp/scene.html`).** Robert, 2026-09-18, doslova:
    *„zákaz i zpracovávání modelů pro admina do chatu, veškerá
    geometrie je povolená prezentovat adminovy pouze ve scéně"*. Platí
    pro bota8 (a kohokoli dalšího, kdo sahá na geometrii/3D scénu) -
    žádné screenshoty/rendery/near-final náhledy modelu poslané do
    chatu jako podklad ke kontrole, ani jako mezikrok. Navazuje na už
    dřív platící pravidlo, že finální slovo je vždy potvrzení PŘÍMO VE
    SCÉNĚ (technické řezy/kóty pro schvalování taky jen ze živé scény,
    ne 3D náhledy) - tenhle zápis to zpřísňuje na CELÝ proces, ne jen
    na finální schválení.

49. **⭐ vanDrawee ("Vandr") JE NÁŠ SYSTÉM.** Robert, 2026-09-22, doslova:
    *„někde už konečně zapiš že vandr je náš"* + *„systém který prostě jede,
    funguje nezávisle, a to mnohem dřív než naše tato nová větev"*.
    Je to starší, hotový a funkční konfigurátor (Unity + Laravel), který
    vznikl dlouho před současnou Three.js větví (Logiman) a běží nezávisle
    na ní. **Není to cizí systém, konkurence ani archiv.**

    Proč to tu stojí: víc session po sobě Robertovi tvrdilo opak, protože
    si to přečetly ze zápisu, kde produkce `vandrawee.eu` byla popsaná jako
    „cizí DigitalOcean droplet". Ten stroj (165.227.139.137) je **náš**, jen
    to není tahle VPS. **„Jiný server" ≠ „cizí systém"** - to je celé
    nedorozumění a nemá se opakovat.

    Praktický důsledek: `NESAHAT bez výslovného zadání` u produkce dál
    platí, ale jako provozní opatrnost (běží na tom reálné nabídky pro
    profily 40/45), ne proto, že by to patřilo někomu jinému. Naše
    testovací kopie je `/opt/vandrawee` na `test.logiman.cz`.

50. **⭐ ŽÁDNÝ BOT NESMÍ ZAPISOVAT PŘÍMO DO `app_settings` KLÍČŮ
    `render_hdri_file_id`/`render_hdri_file_name`/`render_hdri_rotace_deg`
    - jedině přes `PUT /api/admin/render-hdri`/`render-hdri-rotace`, a
    tyhle volá jen Robert z administrace.** Robert, 2026-09-24, doslova:
    *„opravit podle čeho se renderuje, nebude to nastavovat už bot4, ale
    nastavím si sám a bude to platit."*

    **Co se stalo:** `app_settings.render_hdri_file_id` (trvalá volba
    HDRI mapy pro produkční rendery, viz `api/render_hdri.py`) ukazoval
    na jiný soubor (`tv_studio_4k.hdr`, id 4044), než jaký admin UI
    zobrazovalo jako "✓ používá se pro render" (`crossfit_gym_2k.exr`,
    id 4125) - a `audit_log` nemá pro `entity_type='render_hdri'` ANI
    JEDEN záznam, přestože endpoint na každý úspěšný zápis loguje
    bezpodmínečně. Hodnota tedy musela vzniknout přímým SQL zápisem
    mimo endpoint (stejná mezera jako u render klíče, pravidlo 31 -
    "boti běží jako root, dveře jsou zamčené, okno ne") - nejpravděpodobněji
    z Vandr HDRI-porovnávacích skriptů bota4
    (`2026-09-23_vandrawee_render_porovnani.py` a příbuzné), které mají
    vlastní `--hdri` argument pro JEDNORÁZOVÉ porovnání jednotlivé
    dávky, ale komentáře v nich ("...oboje již TRVALE v app_settings")
    ukazují, že se místo toho přepsala TRVALÁ globální volba.

    **Platí:** jednorázové porovnání/testování různých HDRI (Vandr i
    nativní větev) musí použít výhradně per-job override
    (`--hdri`/`--hdri-rotace-deg` na příkazové řádce daného
    renderovacího skriptu), NIKDY zápis do `app_settings` pod těmihle
    třemi klíči - ani "dočasně", ani "protože se to stejně brzy zase
    přepne zpátky". Trvalou volbu nastavuje jedině Robert v adminu
    (Sdílený disk → HDRi → "použít pro render") - to je zdroj pravdy,
    zbytek appky (`vybrane_hdri()` v `scripts/2026-09-09_turntable_render.py`)
    z ní jen čte.

51. **⭐ KAŽDÁ sestava do auta MUSÍ nést štítek, na jakou stranu/část vozu
    je navržená.** Robert, 2026-09-24, doslova: *„každá sestava do auta musí
    nést štítek na jakou stranu auta je navržena: levá / pravá / přepážka /
    podlaha / výsuv z auta"*. Platí pro OBĚ větve (nativní Logiman i Vandr),
    bez výjimky - sestava bez štítku není hotová a nesmí jít ven.

    *Aktualizováno 2026-10-01 (bot9 podle bot10, ověřeno v DB a v kódu):
    stav Vandr karet a výpočet azimutu; samotné pravidlo beze změny.*

    **Kde to je:** číselník `regal_umisteni` (RL levý, RP pravý, RK
    kabina/za přepážkou, DP dvojitá podlaha, VZ výsuvné bloky zadní, VB
    výsuvné bloky boční, VP výsuvná podlaha); štítek nese
    `product_assemblies.umisteni_id` (nativní sestavy) i
    `shop_products.umisteni_id` (Vandr karty). Robertův seznam se na tenhle
    číselník mapuje 1:1, nový se nezavádí. Automatická aktivace Vandr karty
    bez štítku ji nezapne (bot10, commit `902a5af6`).

    **Otevřená díra** (stav 2026-10-01): nativní sestavy štítek mají, ale
    nevěrohodný - všech 530 má `umisteni_id=1` (levý). To je hromadný
    default, ne zjištěná hodnota; než se na štítek začne spoléhat (filtry,
    texty, render rig, orientace) nebo než se začnou dělat jiné strany, musí
    se skutečné hodnoty ověřit. (Dřívější díra „Vandr karty štítek nemají
    vůbec“ - z ní vznikl případ karty 4593, živé jako běžný regál, ač je na
    PRAVÉ straně - je u Vandr karet zavřená: štítek mají.)

    **Kombinace stran:** model, který v jednom souboru spojuje levou i
    pravou stranu, nemůže mít pravdivý štítek (RL ani RP), proto se
    nezakládá jako karta, ale dělí se na samostatné karty stran (Robert,
    2026-09-30; FBX watcher to hlídá od `c7194e59`). Už založený kus bez
    štítku stahuje jedině Robert (pravidlo 54) - do té doby je to vědomě
    tolerovaná výjimka, evidovaná v `TASKS.md`.

    **Proč na tom záleží víc, než vypadá - štítek řídí ÚHLY OTOČKY**
    (Robert, 2026-09-24: *„v současné době zpracováváme regály na levou
    stranu, s tím souvisí z jakých úhlů se dělá otočka"*). Pravidlo úhlů
    je popsané v `PRODUKTOVE_RENDERY.md` (body 2 a 3): renderuje se
    **270° výseč, 9 azimutů po 30°**, zadních 90° se záměrně vynechává
    (ochrana modelu + zadní stranu ukazovat nechceme), a **přední směr je
    vlastnost SESTAVY, ne globální konstanta**:
    - nativní sestavy - z role-tagů (`predni-svislice` vs
      `cap`/`zadni-svislice`);
    - Vandr karty (syrové GLB bez role-tagů) - z geometrie GLB:
      `scripts/2026-09-23_vandr_razitka_spocitat.py` ho počítá a ukládá do
      `shop_products.vandr_predni_azimut_deg`, render ho čte v
      `scripts/2026-09-09_turntable_job.py`. Stav 2026-10-01: aktivní RL
      270°, RP 90°, RK 180°.

    ⚠️ `FRONT_AZIMUTH_DEG = 270` je jen nouzový fallback. Chybí-li u Vandr
    karty spočtený azimut, render vypíše VAROVÁNÍ a jede na 270° - u
    pravého regálu (RP) nebo RK by otočka ukázala špatnou stranu (přesně
    případ karty 4593). V automatu se to neuplatní: render automat bere
    jen karty s vypočtenými razítky (`vandr_razitka_glb_otisk IS NOT NULL`)
    a výpočet razítek zapisuje azimut stejným `UPDATE` (2026-10-01: všech
    111 karet s razítky azimut má).

52. **⭐⭐ NIC SE NEODKLÁDÁ. Každý problém, nedostatek a chyba se řeší
    IHNED - a ptát se, jestli to má počkat, je ZAKÁZÁNO.** Robert,
    2026-09-24, doslova: *„nikdy nic se nebude řešit později ale hned,
    tuto otázku zakazuju všem botům!!!! zákaz otázek typu jestli se má
    něco odkládat !!! nařízení: nikdy nic se nesmí odkládat naopak,
    všechno se musí okamžitě vyřešit, každý problém, nedostatek a chyba
    ihned"*.

    Platí pro VŠECHNY boty, bez výjimky. Konkrétně:
    - Když bot při práci narazí na chybu/mezeru (i mimo svoje zadání),
      **založí její řešení hned** - buď ji opraví sám (je-li ve své
      doméně), nebo ji OKAMŽITĚ předá vlastníkovi domény. Ne "zapíšu to
      do TASKS.md a někdo se k tomu vrátí".
    - **Nepokládat Robertovi otázky typu** „mám to řešit teď, nebo
      později?", „chceš to zařadit do fronty?", „necháme to na příště?".
      Odpověď je vždy TEĎ - ta otázka jen zdržuje a přenáší na něj
      rozhodnutí, které žádné rozhodnutí není.
    - Ptát se se SMÍ dál na věcný obsah (co přesně chce, která varianta,
      jaká hodnota) - zákaz se týká jen odkládání v čase.
    - Nález zapsaný do `TASKS.md` je DOPLNĚK k okamžitému řešení
      (evidence/kontext), ne jeho náhrada - pravidlo 43 tím není zrušené,
      jen se nesmí zneužívat jako způsob, jak práci odsunout.

53. **⭐ KONTROLA SESTAV PROBÍHÁ VŽDY V KONTROLNÍ SCÉNĚ.** Robert,
    2026-09-24, doslova: *„pravidlo kontroly sestav: vždy v kontrolní
    scéně"*. Kdykoli má Robert (nebo kdokoli) něco na sestavě posoudit -
    geometrii, razítka, vadu, návrh opravy, výběr ke smazání - dostane
    **odkaz do `/api/kontrola-scena`**, ne obrázek, ne popis, ne výpis
    čísel.

    **Jak na to:** `https://autovestavby.logiman.cz/api/kontrola-scena?items=<typ>:<id>,...`
    - `pa:<id>` = `product_assemblies` (nativní sestava)
    - `cs:<id>` = `custom_shapes`
    - `vd:<id>` = Vandr karta (`shop_products`, monolitický GLB + razítka;
      `?navrh=<jmeno>` ukáže NÁVRH razítek ze souboru místo toho, co je
      v DB - DB se přitom nedotkne)
    Víc položek za sebou = automaticky se objeví přepínač s počítadlem,
    takže celá dávka jde projít na jeden odkaz.

    Navazuje na pravidlo 48 (zákaz posílat geometrii do chatu) - tohle
    říká, kam MÍSTO toho, a platí i pro jednu jedinou sestavu, i "jen na
    ukázku". Kontrolní scéna je read-only a staff-gated, takže se do ní
    smí dát cokoli, co Robert potřebuje vidět, včetně neschválených,
    vadných nebo rozpracovaných kusů.

54. **⭐⭐ ŽÁDNÝ BOT SÁM NEDEAKTIVUJE ŽÁDNOU KARTU.** Robert, 2026-09-24,
    doslova: *„Pravidlo karet: žádný bot nebude sám deaktivovat žádné
    karty !!!!!!!"*. Platí pro `shop_products.active` u VŠECH karet
    (nativní i Vandr), bez výjimky a bez ohledu na důvod.

    **Týká se to i „ochranných" zásahů.** Bot může najít na živé kartě
    reálnou vadu (špatná razítka, vadná geometrie, otočka ze špatné
    strany) - a i tak ji **nesmí stáhnout sám**. Nahlásí ji Robertovi
    (podle pravidla 53 odkazem do kontrolní scény) a ten rozhodne. Důvod
    je vlastnický, ne technický: co je na webu, určuje Robert - stejná
    logika jako u pravidla 44 (schválení `technicky_ok` je jen jeho) a
    30 (bot si nezakládá účet).

    **Proč to tu je:** bot3 tentýž den deaktivoval z vlastního rozhodnutí
    několik karet (4582/4596/4904 kvůli razítkům, 3945/3957 kvůli
    geometrii mimo obrys karoserie) - pokaždé s dobrým úmyslem chránit
    zákazníka před vadným obrázkem, ale bez Robertova pokynu. Nález byl
    správný, zásah ne. Pravidlo 52 („nic se neodkládá") tohle NERUŠÍ -
    rychle se má **nahlásit a opravit příčina**, ne sáhnout na kartu.

    Aktivace zůstává beze změny automatická tam, kde ji Robert zapnul
    (`vandr_card_activate_povoleno`) - zákaz je na RUČNÍM botím zásahu
    do `active`, oběma směry.

    **⭐ PŘERAZÍTKOVÁNÍ ANI PŘERENDEROVÁNÍ NENÍ DŮVOD KARTU DEAKTIVOVAT**
    (Robert, 2026-09-24, doslova: *„jestli se má něco přerazítkovat a
    přerenderovat, neznamená to že se má karta deaktivovat !!!!!!!!"*).
    Je to běžná údržba nad ŽIVOU kartou: stávající snímky zůstávají
    aktivní a viditelné, dokud je nová dávka nenahradí při commitu -
    žádné okno, kdy by karta byla bez obrázků. Karta se tedy při
    přerazítkování/přerenderování **nechává běžet**.

55. **⭐ Úprava textu kategorie/produktu/sestavy nesmí Robertovi vzít
    možnost tu hodnotu dál normálně editovat v adminu.** Robert (přes
    bot3, 2026-09-27), doslova: *„Všechny texty kategorií musí být
    editovatelné a bot7, když bude měnit texty, bude je měnit tak, aby
    editovatelnost neztratily. Totéž platí pro popisy v detailu
    produktů a sestav."* Skrývání/úprava zobrazení patří na stranu
    VYKRESLENÍ (SSR/klient), nikdy do dat, která admin editor čte a
    zapisuje. Vzor, který tohle správně dodržel: vyprázdnění FAQ bloků
    u 13 kategorií (bot7, commit `7ec5f28f`) - DB pole zůstalo netknuté,
    prázdný nadpis se skryl jen na straně vykreslení
    (`_strip_empty_faq_block`), ne úpravou dat, která admin ukládá/čte.
    Samostatné pravidlo pro texty centrálního panelu "Typy sestav" (bot
    tam nesmí psát vůbec) je v `TEXT_FILTR.md`, pravidlo 18.

56. **⭐⭐ Název dodavatele původní knihovny karoserií se NIKDE nepoužívá.**
    Robert, 2026-09-30, doslova: *„to slovo mělo být zcela vymazáno ze
    slovníku!!!!!!!“*. Platí pro text, DB, soubory i jejich názvy, názvy
    tříd/proměnných, paměť botů, předávky i odpovědi Robertovi. Knihovna se
    jmenuje jen „karoserie“ / „knihovna karoserií“, kódy vozů jsou ve sloupci
    `legacy_vendor_code`, doména dodavatele = „externí katalog rozměrů“.
    Slovo se tu schválně nevypisuje; kdo ho najde v datech, nahradí ho
    neutrálně a nepřenáší ho dál. Pozor: první úklid (2026-09-09) selhal,
    protože hledal jen v některých příponách a vynechal zálohy, qa-reports,
    Sdílený disk, paměť a předávky - kontrolu pouštět přes `/usr/bin/grep`
    (shellová funkce `grep` = ugrep s `--ignore-files`, tiše přeskočí
    soubory ignorované gitem).

57. **⭐ Serverový kód (`api/*.py`) se nasazuje AUTOMATICKY 2× denně (00:00
    a 12:30, Europe/Prague; noční termín přesunut ze 3:30 kvůli zálohám), bez výpadku a jen z commitnutého stavu - boti
    službu NErestartují ad hoc a o restart NEžádají Roberta.** Robert (přes
    bot3), 2026-10-01: *„Už mě nebaví dělat restart“*, *„Proč bysme měli
    dělat pořád restart serveru, to se mi nezdá?“*, k nasazování 2× denně
    bez výpadku: *„Pokud je to nejlepší řešení, tak budiž“*; potvrzeno
    Robertem přímo 2026-10-02. Za 7 dní přibylo 162 commitů do `api/*.py`,
    restart po každém je neúnosný. Bot opravu commitne a v hlášení uvede
    „živé po nasazení v HH:MM“. Termín zjistí `scripts/restart_konfigurator.sh
    --stav` (další termín, čekající commity, blokující necommitnuté soubory,
    poslední běhy; Robert: Dashboard → „Nasazení serveru“). Nasazuje se
    gunicorn HUP (obsluha stojí dobu importu aplikace, očekávaně pár sekund; večer
    2026-10-04 to bylo 44-57 s kvůli chybě v `api/qa_checks.py`, opraveno
    `48598062`, ověří se při příštím nasazení v `--stav`; žádný požadavek nespadne, jen čeká;
    `scripts/nasazeni.py`). `webapp/*` se servíruje z disku hned a restart
    nepotřebuje.
    Necommitnutá změna v `api/*.py` plánované nasazení CELÉ přeskočí na další
    termín - rozdělanou práci commitovat hned.
    Výjimka: naléhavá chyba, kterou vidí zákazníci - řeší ji bot3 s Robertem,
    `scripts/restart_konfigurator.sh --reload` pouští Robert nebo bot s jeho
    povolením. Tvrdý restart jen pro změny, které HUP nenačte: `api/.env`,
    `konfigurator.service`, venv – `scripts/restart_konfigurator.sh --tvrdy` (od 2026-10-05 je
    povinný režim: holé spuštění ani neznámý přepínač typu `--help` už NIC nerestartuje, vypíše použití a skončí). Po nasazení ověř endpoint, který se měnil
    (pravidlo 33), ne jen `/api/health`.

58. **⭐ Koeficient scény (`app_settings.scene_price_coefficient`, dnes 1,25)
    se týká JEN profilů a produktů, které se načítají z Dogusu.** Robert
    (přes bot3), 2026-10-01: *„koeficient pro scénu se týká jen profilů a
    produktů které se načítají z dogusu“*; potvrzeno Robertem přímo
    2026-10-02. Násobí se jen díly s příznakem `scene_coef` (profil / karta
    s `dogus_url`); desky, euroboxy, Vandr díly a `DIL-*` karty z importu
    jdou do scény v základní ceně. Je to JINÝ koeficient než
    `content_categories.dogus_price_coefficient` (cena karty z Dogus ceníku,
    pravidlo 9): scénový je jeden globální a násobí se až v `/api/katalog`
    (`katalog()` v `api/app.py`). Dál platí rozhodnutí z 2026-08-19: násobí
    se jen cena dílů, ne příplatek za řez, paušál za profil, spoje a
    spojovací materiál.
    Při změně rozsahu uprav i `SCENE_PRICE_COEF_SCOPE` (`api/admin_settings.py`),
    texty v administraci a přepočti uložené ceny (vzor: skript
    `scripts/2026-10-01_bot8_prepocet_koef_profily_dogus.py`).

59. **⭐ Pokud bot3 nežije, zastupuje ho bot9.** Robert, 2026-10-04,
    doslova: *„pokud nezije bot3 zastupuje ho bot9“*. Platí pro všechno,
    co WORKFLOW.md svěřuje bot3 (koordinace a rozdělování práce, pravidla
    12–15; naléhavá zákaznická chyba v pravidle 57; předávání Robertových
    pravidel botům; zadávání a čtení výstupů externího bota Johna).
    „Nežije“ = session bot3 neběží (není v `ListAgents` ani v registru
    Přehledy → Boti). Je to Robertovo slovní rozšíření náplně bot9
    (pravidlo 38) a platí jen po dobu, kdy bot3 neběží.

60. **⭐ Práci Johna (OpenAI bot, `openai1`) musí NEJDŘÍVE vidět a schválit
    Robert, teprve potom se smí předat dál.** Robert, 2026-10-04, doslova:
    *„Johnovu práci musím vždy nejdřív vidět já, schválit a potom se může
    předat dál“*. Výstup Johna (`/home/openai1/konfigurator/vystupy/`) je
    návrh externího bota: žádný bot ho nenasazuje do `webapp/`/`api/` ani
    nepředává vlastníkovi k zapojení, dokud ho Robert neschválil. Ukázat
    ho Robertovi se smí jen samostatným náhledem, který nemění živou
    stránku (např. zvláštní adresa nebo parametr náhledu).

61. **⭐ Razítka (ochranné logo LOGIMAN.CZ v geometrii) budou na VŠECH 3D
    modelech ve VŠECH generátorech.** Robert, 2026-10-08, doslova:
    *„pravidlo: razitka budou na všech 3D modelech ve všech generatorech“*
    (reakce na „proč nemají stoly v generátoru razítka?“). Platí pro živé
    3D v každém generátoru (stoly všech systémů, dopravníky, trubkový,
    oplocení…), jeho košík, model v nabídce i rendery karet z generátoru;
    nový generátor se razítkuje od prvního náhledu (John, bot8, bot10).
    **Přebíjí** dřívější „generátor a košík bez razítek“ (2026-09-06,
    `stul_glb.model_pro_parametry(..., razitka=False)` jako výchozí).
    Pravidla umístění razítek (`scripts/razitkovac.py`, `api/stul_razitka.py`)
    se nemění; admin Scéna/Vandr sestavy do aut tímhle pravidlem neřešeny.

## Tokenová disciplína (Robert 2026-09-02, POVINNÉ pro všechny boty)

Účel: největší spotřeba tokenů jde na čtení obřích souborů, dlouhé
sessions a ruční opakování. Pravidla:

1. **Nečti soubory > 200 kB vcelku** (`scene.html`, `admin.html`,
   `app.py`, `remeslo.py`, logy, dumpy). Vždy `grep -n` → `sed -n
   'A,Bp'` okno ±40 řádků. `wc -c` před čtením neznámého souboru.
2. **Filtrované výstupy**: `| head`, `grep -c`, `jq '.stats'`, `tail
   -n 30` — nikdy `cat` logu/JSONu/dumpu bez filtru.
3. **Start bota**: `STAV.md` + `scripts/handover.py dump` (+ TASKS.md),
   ne celý `AGENTS_LOG.md` (viz CLAUDE.md). Do logu jen cílený grep.
4. **Krátké sessions**: po dokončení úkolu zapiš předávku
   (`scripts/handover.py add --bot … --topic "stav <bot>"`), aktualizuj
   `STAV.md`, a bot3 session restartuje s čistým kontextem. Session
   vlekoucí dny starý kontext je drahá při každé odpovědi.
5. **Skript místo bota ve smyčce**: opakovaná práce nad N položkami
   (dávky, importy, generování obsahu, rendery) = jednou napsaný skript
   + ověření vzorku botem. Bot ručně per položku je nejdražší vzor.
6. **Automatické QA běhy jsou od 2026-10-04 vypnuté** (Robert; viz pravidlo
   8). Bot si ověří sám to, co změnil (pravidlo 33), a čte jen cílené kontroly.
7. **Model podle úkolu**: mechanické úkoly (běhy skriptů, importy,
   šablonové překlady, rutinní QA) dostane bot spuštěný s levnějším
   modelem (`claude --model sonnet`); architektura, revize, scéna a
   koordinace zůstávají na silném modelu. Rozhoduje bot3 při zakládání
   bota; pro čtení kódu používej subagenta `Explore`, ne hlavní kontext.
8. **Brief na jeden pokus**: přesné zadání + ověřovací kritéria + kam
   hlásit; hlášení strukturovaně (hotovo / zbývá / blokace / commity),
   bez ping-pongu. Před hlášením nálezu ho ověř v kódu/na disku/v DB
   (falešné poplachy stojí tokeny všech). Stejně tak žádná výjimka při
   `cur.execute()`/`commit()` NEZNAMENÁ, že zápis (ALTER/CREATE TABLE
   apod.) reálně proběhl (bot5, 2026-09-02: `CREATE TABLE client_errors`
   proběhlo bez chyby, ale tabulka nevznikla) - po každém DB zápisu
   ověřit čerstvým `SELECT`/`SHOW` z NOVÉHO spojení, ne věřit chybějící
   výjimce.
9. **Screenshoty jen v milnících**, nízké rozlišení; vzhled iteruj přes
   DOM/CSS asserty, ne přes obrázky. Video: ffmpeg každých 5 s.
10. **Research vždy persistovat** (DB `supplier_leads`, `chef_outreach`
    apod.) a nikdy neopakovat.

## Základní pravidlo

Tohle je JEDEN pracovní adresář sdílený víc agenty přes SSH - a stejné
riziko souběžné práce sdílí sesterské projekty `/opt/toscanaccio` a
`/opt/vybaveni-uzitkovych-vozidel` na téže VPS. Git tu neslouží k
`push`/`pull` mezi kopiemi, ale jako **záznam a bezpečná brzda** -
každá změna má commit, žádná změna se neprovádí přepsáním souboru bez
commitu.

## Git/zámek disciplína (POVINNÉ, jednotná pro VŠECHNY 3 projekty na VPS)

Tenhle blok popisuje jen AKTUÁLNĚ platné pravidlo. Plnou historii
incidentů, ze kterých vzešlo (TOCTOU race u ručního zámku, ztracený
`AGENTS_LOG.md` zápis, cizí zámek "vstřícně" přepsaný souběžně, OOM
watchdog...), hledej v `AGENTS_LOG.md`/archivu, ne tady.

1. **Před úpravou**: `git status` + `git log -3 --oneline`. Cizí
   neuložené změny → nesahat, dokud nejsi jistý/á, že druhý bot
   skončil (zeptej se uživatele, pokud si nejsi jistý/á).
2. **Guarded soubory** (`webapp/*`, `api/*.py`) vyžadují držení
   `DEPLOY_LOCK.json` zámku - vynuceno `.git/hooks/pre-commit`, ne jen
   dohodou (rozšířeno 2026-09-03 z pouhého `api/app.py` na celé
   `api/*.py`, viz split iniciativa výš). **Kdy zámek brát**: přesně ve chvíli, kdy je změna
   PŘIPRAVENÁ a jde se rovnou zapsat do guarded souboru - ne dřív
   (dokud teprve připravuješ/testuješ/rozmýšlíš obsah změny, zámek si
   NEBER, zbytečně bys blokoval ostatní), ale ani později (ne až těsně
   před `sftp.put`/commitem - to je moc pozdě, viz zpřísnění po
   incidentu 2026-08-18 v `AGENTS_LOG.md`).
   **Zámek NECHRÁNÍ uživatele před rozpracovaným stavem** (bot3+bot10,
   2026-09-25): soubory z `webapp/*` se servírují PŘÍMO Z DISKU, bez
   buildu a bez atomické výměny - prohlížeč si vezme to, co je na disku
   v tu vteřinu, bez ohledu na to, kdo drží zámek. Robert takhle dnes
   v noci narazil na scénu, která se vůbec nenačetla (`kontrola.html`
   uprostřed většího přepisu; soubor má `"use strict"`, takže jediná
   rozpracovaná pasáž shodí CELOU stránku, ne jen novou funkci).
   Mitigace není delší držení zámku, ale **každý uložený stav
   guarded frontend souboru drž funkční** - velký přepis rozděl na
   menší kroky, které se dají načíst, a po uložení si stránku aspoň
   jednou skutečně otevři (klikem, ne jen čtením kódu - viz nález
   z-indexu ve stejné scéně, kdy `<canvas>` překrýval všechna plovoucí
   tlačítka a nikdo si toho při čtení kódu nevšiml).
   **Textová kontrola (grep/curl) NEDOKAZUJE, že to prohlížeč použil**
   (bot7+bot16, 2026-09-25): rozsypanou kategorii profilů způsobilo `*/`
   napsané uprostřed věty v CSS komentáři - předčasně ukončilo komentář a
   shodilo parsování CELÉHO zbytku `<style>` bloku. Grep i curl přitom
   pravidla v souboru VIDĚLY a hlásily je jako v pořádku; já sám jsem na
   základě takové kontroly napsal "vypadá to opravené", a byla to shoda
   okolností, ne důkaz. Vizuální změnu ověřuj skutečným prohlížečem
   (Playwright, screenshot), a u `<style>` bloku si můžeš rychle ověřit i
   počet `/*` vs `*/` - musí sedět.
   **Totéž platí pro skripty, které pouští systemd timer** - stejnou noc
   chytil timer `vandr-render-dispatch` (běží po 5 min) rozepsaný
   `2026-09-23_vandr_render_auto_dispatch.py` uprostřed úpravy návratové
   hodnoty a spadl na `ValueError: not enough values to unpack`. Nikdo
   si toho nevšiml, protože automat spadl tiše a další tik už prošel.
   Když upravuješ skript, který má timer, počítej s tím, že ti do něj
   během editace kdykoli "šlápne" spuštění - drž mezistavy spustitelné,
   nebo si na dobu přepisu timer vědomě zastav a zase pusť.
   **Totéž platí pro `systemctl restart` na `api/*.py`, ne jen pro
   webapp/frontend soubory** (bot3+bot5+bot16, 2026-09-26, dvakrát ten
   samý den): restart gunicornu načte, co leží NA DISKU, bez ohledu na
   to, čí je to rozdělaná práce a jestli patří k tomu, proč se vůbec
   restartuje. Poprvé to smetlo bota16ovu barevnou úpravu do bota7ova
   commitu (nic se neztratilo, jen skončilo pod cizí commit zprávou).
   Podruhé to bylo vážnější: bot5ův necommitnutý, NEÚPLNÝ přepis
   `api/orders.py` (nová atomická řada čísel objednávek, chyběly
   ještě 2 tabulky) běžel živě po restartu, který si vyžádal bot16
   kvůli VLASTNÍ, nesouvisející opravě v `api/sestava_typ.py`. Kdyby v tu
   chvíli přišla objednávka, spadla by na chybějící tabulku (500) -
   nepřišla, ale byla to shoda okolností, ne jistota. **Rozdělaná práce
   na guarded souboru (frontend i backend stejně) = commitnout hned,
   i mezikrok/nedodělek, ne nechat viset "na později"** - zámek tě
   nechrání před restartem, který spustí někdo jiný kvůli něčemu
   úplně jinému.
3. **`scripts/lock.sh acquire/release/status/require <bot_id> "poznámka"`
   je POVINNÝ způsob zámku** - NIKDY ruční Read/Write
   `DEPLOY_LOCK.json` (atomický `flock`, ruční cesta prokazatelně
   prohrává race podmínky). Formát: `{"held_by": "botN"|null, "since":
   "ISO čas", "note": "..."}`. Čekání na cizí zámek: `--wait`.
   Kontroluj cizí zámek po **5 minutách** - to je JEN frekvence
   kontroly, NIKDY svolení převzít starý cizí aktivní zámek (žádný
   takový časovač neexistuje). Zaseknutý/podezřelý zámek → napiš do
   `AGENTS_LOG.md` a/nebo se zeptej Roberta, nikdy sám nepřevezmi/
   needituj kolem. `DEPLOY_LOCK.json` s neparsovatelným JSONem hook
   bere jako fail-closed (commit odmítne) - jiné než chybějící/prázdný
   soubor, ten zůstává "volný" (bootstrap případ).
   **DŮLEŽITÉ: zámek drž jen po dobu SKUTEČNÉ editace/nasazení guarded
   souboru** - `scripts/lock.sh release <bot_id>` zavolej HNED po
   dokončení (commitu), ne "pro jistotu" dál. Nedrž zámek, když zrovna
   nezapisuješ (čekáš na odpověď, přemýšlíš, děláš mezitím něco
   jiného) - zbytečně tím blokuješ ostatní boty čekající na guarded
   soubory.
4. **Každý commit musí mít `BOT_ID=botN`** (`BOT_ID=bot3 git commit
   ...`) - hook bez něj commit na guarded souborech odmítne. Nouzový
   obchod PRO ROBERTA (člověka), NIKDY pro boty: `git commit --no-verify`.
5. **`git commit -m "..." -- <explicitní cesty>`, NIKDY `git add -A`/
   `git commit -a`/holé `git commit`.** Sdílený working tree bez
   izolovaných worktree - holý commit sebere i cizí staged změny
   souběžného bota (reálně se stalo opakovaně, na tomhle i sesterských
   projektech). Obsah zůstane správný, ale commit historie je matoucí
   a je to zbytečné riziko, kterému lze levně předejít.

   **DOPLNĚK (bot16, 2026-09-17, živě prožitý incident):** `git commit
   --amend` BEZ explicitní pathspec trpí stejnou dírou jako holý
   `git commit` - přepíše commit obsahem CELÉHO aktuálního indexu, ne
   jen souborů z původního commitu. Živě se stalo: `git add <moje 2
   nové soubory> && git commit -- <moje soubory>` proběhlo čistě, ale
   následný `git commit --amend -F zprava.txt` (jen kvůli opravě
   pokažené zprávy, ne obsahu) bez pathspecu sebral i cizí `git add`
   (bot5, 4 necommitnuté soubory) ležící v mezičase ve sdíleném indexu
   a zapsal je do mého commitu pod mým `BOT_ID`. Oprava: `git reset
   --soft <commit_pred_prvnim_pokusem>` (vrátí HEAD, index i working
   tree do stavu před sérií), pak `git reset` (mixed, na týž commit -
   odstáhuje vše zpět), a commit znovu se stejnou explicitní pathspec
   disciplínou jako napoprvé. **I `--amend` tedy vždy s `-- <explicitní
   cesty>` na konci**, ne jen prostý `git commit`/`git commit -a`.
6. **Append do `AGENTS_LOG.md` obal zámkem** (`scripts/lock.sh acquire
   <bot_id> "AGENTS_LOG.md append" --wait` / `release`) - i
   negurardovaný soubor může při souběžném zápisu víc botů ztratit
   zápis beze stopy (přesně tohle se stalo na Toscanacciu, viz jeho
   `AGENTS_LOG.md`).
7. **Rollback = `git checkout <hash> -- <soubor>` + commit, NIKDY
   kopírování ze `.bak.*` záloh.** Slepé přepsání souboru nemá přehled,
   co v mezičase udělal druhý bot - přesně tohle způsobilo incident
   2026-07-23, který k celé téhle disciplíně vedl.
   ```
   git log --oneline -- webapp/scene.html    # najdi konkrétní commit
   git show <hash> -- webapp/scene.html      # over si obsah
   git checkout <hash> -- webapp/scene.html  # vrať JEN tenhle soubor
   git commit -m "Rollback ... na <hash>: <důvod>" -- webapp/scene.html
   ```
8. **Zámek chrání jen COMMIT, ne samotnou editaci working tree** (bot15,
   2026-09-03, Robert pres bot3: "disciplina zamku je porad slabina") -
   žádný hook nezachytí `Edit`/`Write`/`sed -i` v jiné Claude Code
   session, dokud nekomituje. Doplněno o 2 mechanismy DETEKCE (ne
   prevence - technicky nejde zabránit):
   - **`scripts/lock_watchdog.py`** (systemd timer
     `konfigurator-lock-watchdog.timer`, každých 90 s): hlásí (do
     `AGENTS_LOG.md` + `bot_handover` s `status=blocked`, topic
     `ZAMEK-ALARM: ...`) (a) zámek držený > 25 min beze změny (typicky
     spadlý/zapomnětlivý bot), (b) guarded soubory necommitnuté a
     zámek volný SOUVISLE > 20 min (ne krátké okno běžné přípravy -
     jen dlouhodobě opuštěný/zapomenutý diff bez zámku vůbec, jako
     incident "bot14 měl hotový diff v app.py bez zámku"). Krátké
     "spinave + zamek volny" okno během přípravy je NORMÁLNÍ a
     watchdog ho záměrně ignoruje - hlídá jen sustained stav.
   - **`scripts/restart_konfigurator.sh`** - obal nad `systemctl
     restart konfigurator`, co PŘED restartem zkontroluje necommitnuté
     zmeny v guarded souborech (jen sledované, ne chronickou hromadu
     untracked assetů jako `webapp/katalog/*.glb`); pokud tam něco cizí
     leží (zámek volný nebo drží jiný bot), restart ODMÍTNE (přepiš
     `--force`, pokud víš přesně co děláš) - cílí přímo na incident
     "bot16 restart nasadil cizí WIP". Použij MÍSTO holého
     `systemctl restart konfigurator`. Běžně restart bot nedělá (pravidlo
     57); obal platí pro výjimky tam popsané (`--reload`, tvrdý restart).
   - Worktree (`git worktree add`, viz split iniciativa 2026-09-02/03)
     zůstává vyhrazené pro PLÁNOVANÉ, rozsahem předem známé vícesouborové
     paralelní akce (velké refaktory/splity) - NENÍ blanket mandate pro
     běžné drobné opravy (náklad: nejde z něj restartovat/ověřit živě,
     merge se stává úzkým hrdlem u koordinátora).
9. **Každé rozhodnutí/schválení padlé v konverzaci s botem se zapisuje
   TRVALE, ne jen do chatu** (Robert, 2026-09-03, plošné pravidlo napříč
   VŠEMI projekty VPS - stejné znění platí na `/opt/toscanaccio`,
   `/opt/no-sim`, `/opt/domeny`, `/opt/vybaveni-uzitkovych-vozidel`):
   "vždy děláme pravidla aby platili pro vsechny budoucí session" -
   libovolné rozhodnutí (schválení migrace, změna postupu, nové
   pravidlo, cokoli, co má platit i pro příští session/bota) se MUSÍ
   zapsat do `AGENTS_LOG.md` (pod zámkem, bod 6 výš) hned, ne až
   dodatečně po upozornění - případně do `STAV.md`/`TASKS.md`, pokud
   mění aktuální stav, který má číst příští session. Konverzace s botem
   sama o sobě není trvalá - příští session ji nevidí.

## Rozdělení odpovědnosti mezi boty

OPRAVENO 2026-09-12 (audit bot9): statická tabulka na tomhle místě
(naposledy "aktuální schéma, 2026-08-21") byla zastaralá a navíc si
odporovala s podobnou tabulkou v `TASKS.md` (2026-08-18) - obě
smazány, žádná markdown tabulka rolí se dál neudržuje. Od 2026-09-12
existuje živý, DB-backed registr **Přehledy > Boti** v adminu
(`bots.specializace`, `/api/admin/bots`) - tam se role zapisují a
mění PŘÍMO, bez rizika, že markdown tabulka zaostane za realitou.

Před zásahem mimo svou oblast dej vždy vědět uživateli/ostatním botům
(přes `AGENTS_LOG.md`). Aktuální přiřazení hledej v registru Boti,
teprve pokud tam bota nenajdeš, v posledních zápisech `AGENTS_LOG.md`.

## .gitignore

Vyloučeno z verzování: `api/venv/`, `__pycache__/`, `api/.env` (obsahuje
tajné klíče), `api/konfigurator.sock`, staré `*.bak.*` soubory (ty už
verzování nepotřebují - novým zálohováním je teď git historie sama).
