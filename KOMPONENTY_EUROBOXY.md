# Komponenta: regál na euroboxy

⭐ **SOUVISLÝ POSTUP STAVBY (Robert 2026-09-17: „přidej tedy všechno do původního postupu“):** `shape_geometry_methods.id=3`, klíč `postup_stavby_regalu_krok_za_krokem_2026_09_17` - 14 kroků od karoserie po zápis do scény, ověřeno na `product_assemblies.id=127` (K-020 A). **Čti ho PRVNÍ**; kde se níže uvedená historie s ním rozchází, platí postup. Body NEROZHODNUTO v něm rozhoduje Robert.

Noha Jumpy 30x30/40x40, změna hloubky nohy, matice ukládání euroboxů do lůžek (rozestupy, spojnice), kompletní postup vložení produktu eurobox na lůžko. Vydělené z `VLASTNOSTI_PROFILU.md` 2026-08-31. Recepty jsou zapsané i strukturovaně v DB: `shape_geometry_methods.id=1` (`prevod-profilu-zachovanim-rozmeru`), `id=2` (`zmena-hloubky-nohy`), `id=3` (`ukladani-euroboxu-do-luzek`), `id=4` (`dokonceni-nohy-zaslepky-a-uzavreni`). **Obsahuje i obecné pravidlo `id=5` (`regal-sloupcova-struktura`), které NENÍ specifické jen pro euroboxy - platí pro VŠECHNY typy regálů v autech.** Viz taky `KAROSERIE_UMISTENI.md`.

⚠️ **UPOZORNĚNÍ (audit bot9, 2026-09-12):** dokument níže odkazuje na desítky konkrétních `product_assemblies.id=N` jako "kontrolní checkpointy"/vzorové sestavy. Namátkou ověřeno (`id=29-39`, `47-50`) - VŠECHNY tyhle konkrétní řádky jsou dnes v DB smazané (postupný úklid testovacích/checkpointových sestav). Text níže zůstává platný jako HISTORICKÝ ZÁZNAM PRŮBĚHU odvození metody (co bylo ověřeno, jakým postupem, s jakým výsledkem) - jen konkrétní ID už většinou nejdou dohledat v živé DB. Obecná, dál platná metoda je zapsaná strukturovaně v `shape_geometry_methods` (id=1-9), na tu se spolehni přednostně, ne na konkrétní `product_assemblies.id` čísla v textu.

## Pravidlo profilů - ZMĚNA HLOUBKY nohy/regálu (Robert, 2026-08-30, PRACOVNÍ VERZE - neověřeno)

Zapsáno do DB jako `shape_geometry_methods.name='zmena-hloubky-nohy'` (`id=2`, `verified_by=NULL` - Robert vyjádřil nejistotu, jestli pravidlo sedí přesně, zejména část o "přeskoku"). Týká se osy KOLMO od stěny do prostoru (dřív označované "šířka 349" = "hloubka police").

**Pravidlo doslovně (Robert, 2026-08-30):** "všechny zadní svislé profily zůstávají na místě; spojnice svislých profilů se zkracují/natahují; přední svislé profily (přední noha) se posunují podél spojnic směrem k zadním svislým profilům, ale do maximální pozice dotýkat se nejbližšího zadního svislého profilu, případně ještě může přeskočit namísto něho (tzn. namísto nejbližšího svislého profilu, který je většinou nejníže ve svislé ose), a jakmile na jeho místo přední profil přeskočí, tento zadní profil se odstraní."

**Aplikace na nohu Jumpy 30x30** (T=30, výška H=1180): přední svislice vždy na lokální X:[0,T]. Zadní prvky kotvené ke stěně (u nové hloubky D): zadní svislice X:[D−T,D], cap díl kotven FIXNÍ vzdáleností 70mm od stěny ~~(30mm od kraje příčníku)~~ (nezávislé na D — **OPRAVENO 2026-08-30, viz níže**), u výřezové nohy navíc zúžený sloupek před podběhem kotvený FYZICKOU vůlí od stěny (u Jumpy 124mm, nezávislá na D). Spojnice = D−2T, vynechána (nulová) při D≤2T.

**OPRAVA (2026-08-30):** tenhle skript (`tmp_2026-08-30_build_depth_variants_both.js`) měl STEJNOU chybu jako `prevod-profilu-zachovanim-rozmeru` výše - cap byl kotven k T-závislé vnitřní hraně (`rungHi − 30 = D−T−30`) místo k fixní vzdálenosti od stěny. Opraveno na `CAP_OFFSET_FROM_WALL=70`, `capRight = D − 70`. Prahy hloubky se s opravou posunuly (viz níže).

**Prahy hloubky (Jumpy noha 30x30), OPRAVENÉ hodnoty:**
- **D≤184mm**: přední noha narazí na zúžený sloupek před podběhem — JEN u výřezové nohy, ale je to LIMITUJÍCÍ práh pro celou sestavu (plná noha samotná by snesla až 130mm) — Robert: "musíš brát v potaz i nohu s výřezem, která bude limitní".
- **D≤130mm** (dřív chybně 120mm): přední noha narazí na cap díl (obě nohy).
- **D≤70mm** (dřív chybně 60mm): přední noha narazí na zadní/horní svislici — absolutní MATEMATICKÉ minimum (obě nohy, spojnice nulové délky) — Robert označil původní hodnotu za prakticky nesmyslnou ("to je nějaký nesmysl těch 60mm") — reálný praktický rozsah je nejspíš omezen JINAK, závisí na konkrétním autě/noze ("záleží jakou máme nohu pro jaké auto, v tom se liší"), NE čistým geometrickým minimem.

**Uloženo k prohlédnutí** (`product_assemblies`, karoserie CI14, žádný z nich nepotřebuje "přeskok"): D=300mm (id=35), D=250mm (id=34), D=184mm (id=33, přesně na limitujícím prahu) — OPRAVENÉ verze, nahrazují dřívější id=29/30/31, které Robert smazal jako testovací. Ověřeno bez vnitřní kolize (self-collision) i bez kolize s karoserií CI14 s opravenou geometrií.

**Důležité upřesnění (Robert, 2026-08-30):** "toto byl jen příklad hloubek... v provozu bude hloubka nohy (tzn. hl. regálu) plynule nastavitelná." D=300/250/184mm NEJSOU fixní produktové varianty ani uzavřený výčet - byly to jen VZORKY pro ověření vzorce (300mm bezpečně nad všemi prahy, 184mm přesně na limitujícím prahu výřezové nohy). Vzorce výše jsou funkcí LIBOVOLNÉHO D (nad absolutním minimem) - v provozu se hloubka zadává jako plynulý parametr, stejně jako u obecné funkce `buildShelf()` (parametrizovaný "police builder" pro Lx×Ly, viz výše). `product_assemblies.id=33/34/35` zůstávají v DB jako KONTROLNÍ CHECKPOINTY metody (důkaz bezkolizní funkčnosti na 3 různých bodech včetně limitního prahu), NE jako katalog podporovaných hloubek.

**Otevřené**: část pravidla TÝKAJÍCÍ SE PŘESKOKU (pod 184mm) NENÍ ověřena Robertem ve scéně - nezavádět do produkce, dokud nepotvrdí. **Skutečná chyba nalezená po cestě**: v prvním pokusu byl zúžený sloupek u výřezové nohy umístěný na STEJNÝ X jako spojnice k němu vedoucí (copy-paste chyba vzorce středu) - způsobilo to 30mm×30mm×30mm překryv (self-collision check to odhalil). Poučení: i při odvozování NOVÉHO parametrického pravidla vždy spustit self-collision kontrolu na KAŽDÉM segmentu, ne jen věřit vzorci.

**Pojmenovaná hloubka: D=326mm pro euroboxy podélně (Robert, 2026-08-30):** i když je D obecně plynulý parametr (viz upřesnění výše), tahle konkrétní hodnota má vlastní produktový význam - Robertovo pravidlo doslovně: "vnější hloubka 326mm bude určená pro ukládání euroboxů v podélném směru". Postaveno opraveným vzorcem (cap 70mm od stěny), ověřeno bez vnitřní kolize i bez kolize s karoserií CI14, uloženo jako `product_assemblies.id=36` ("Nohy Jumpy 30x30 hloubka 326mm, euroboxy podélně"). Zapsáno i do `shape_geometry_methods.id=2` (`pojmenovane_hloubky.D_326mm_euroboxy_podelne`) - tam se zapisují i další podobné produktově pojmenované hodnoty D, pokud přibudou.

## Pravidlo profilů - UKLÁDÁNÍ EUROBOXŮ do lůžek (Robert, 2026-08-30, POTVRZENO PŘÍMO VE SCÉNĚ)

Zapsáno do DB jako `shape_geometry_methods.name='ukladani-euroboxu-do-luzek'` (`id=3`, `version=3`, `verified_by='robert'`). Rozhodovací matice pro to, jak se v konfigurátoru řeší regálové "lůžko" pro euroboxy.

**Matice podle velikosti dodávky:**
- **Velké dodávky** — řešeno ZATÍM MIMO konfigurátor (Robert: "zatím řešíme mimo konfigurator") - nezavádět, dokud nebude explicitní zadání.
- **Malé dodávky** — mohou mít nohy z profilu 40x40 NEBO 30x30 (Robert: "mohou mít profily 40x40 nebo 30x30").

**Pravidlo doslovně (Robert, 2026-08-30):** "hloubka 326mm pro profily 30x30, čisté vzdálenosti mezi nohama mohou být mm 404, 808, nebo 1212, mezi nohy se vloží 2 podélné profily vodorovně jako spojnice nohou a zároveň jako lůžko pro euroboxy, vodorovné profily (nosníky) se provážou spojnicemi, spojnice z profilu 30x30 pro nosníky 808mm(přední zadní v urovni profilů nohou) se umístí na střed nosníků." **OPRAVA #1 rozestupů (Robert, 2026-08-30, po zhlédnutí prvního 3D pokusu):** "oprava pravidla vzdálenosti mezi nohama musí být větší. pro 1ks eurobox střední velikosti (400x300mm) 426mm, pro 2ks euroboxy střední velikosti (400x300mm) 832mm, pro 3ks euroboxy střední velikosti (400x300mm) 1238mm." **OPRAVA #2, PŘESNÉ KOTY Z CAD (Robert, 2026-08-30):** "ještě jednou oprava, oprava pravidla vzdálenosti mezi nohama musí být větší. pro 1ks eurobox střední velikosti (400x300mm) 430mm, pro 2ks euroboxy střední velikosti (400x300mm) 832mm, pro 3ks euroboxy střední velikosti (400x300mm) 1232mm. tzn. že vrtací koty od začátku profilu, tj na nosnících pro spojnice (tj na střed spojnic) jsou následující: pro 1ks 15mm, 415mm; pro 2ks 15mm, 415mm, 816mm; pro 3ks 15mm, 415mm, 816mm, 1217mm."

**Rozklad pravidla:**
- Hloubka nohy 30x30 = 326mm — STEJNÁ hodnota jako u pojmenované hloubky výše (`shape_geometry_methods.id=2`), tady jen znovu potvrzená v kontextu lůžka.
- Čisté vzdálenosti mezi nohama: **430 / 832 / 1232mm** pro 1/2/3 euroboxy střední velikosti (400×300mm) — FINÁLNÍ hodnoty přesně z CAD kót (nahrazují mezistupeň 426/832/1238mm i původní chybné 404/808/1212mm).
- Přesné koty středů příčných spojnic OD ZAČÁTKU NOSNÍKU (ne rovnoměrné rozdělení, jak bot první odhadl): 1ks → 15/415mm; 2ks → 15/415/816mm; 3ks → 15/415/816/1217mm. První a poslední spojnice vždy 15mm od kraje nosníku (T/2, dotyk s nohou), VNITŘNÍ spojnice přibývají v pevném kroku ~401mm (délka eurobxu 400mm + malá vůle) NEZÁVISLE na celkovém N - ne přepočtem na rovnoměrné rozdělení celého rozpětí.
- Lůžko pro euroboxy = mezi každý pár nohou (na zvolenou vzdálenost) se vloží 2 podélné VODOROVNÉ profily - fungující SOUČASNĚ jako (a) spojnice/výztuha mezi nohama a (b) nosná ložná plocha ("lůžko") pro euroboxy.
- Dva vodorovné nosníky (rovnoběžné) se navzájem provazují DALŠÍMI spojnicemi (příčné prvky mezi nimi, ne jen s nohama).
- Speciální případ při rozpětí nosníků 832mm (2ks): DALŠÍ spojnice (z profilu 30x30, ve stejné úrovni jako profily nohou - tedy "přední"/"zadní" pozice) se umístí NA STŘED nosníků (ne jen na jejich konce u nohou).

**Stav: ROBERT POTVRDIL PŘÍMO VE SCÉNĚ** ("poslední umístění nové je správně") - `product_assemblies.id=37` ("NAVRH: Lůžko pro euroboxy 832mm - 2ks"), 2 páry nohou (přední plná na Z=1258, zadní výřezová na Z=420, čistá mezera přesně 832mm podél délky vozidla Z), 2 podélné nosníky + 3 příčné spojnice (přední/střed/zadní, T-styl, délka D−2T=266mm). Nosníky ve výšce 410mm nad podlahou (CUTOUT_H+T/2 - kde na zadní noze začíná horní část nad zářezem, jen aby nevisely ve vzduchu - přesnou výšku si Robert nastaví ručně).

**Skutečná chyba nalezená Robertem z pohledu SHORA (2026-08-30, v1 → v2):** první verze kolizně krokovala přední a zadní nohu NEZÁVISLE na sobě (každá svůj vlastní `stepUntilCollision`) - noha s výřezem pak nelícovala s přední nohou (různý X: 415 vs 425, rozdíl 10mm, protože se stěna karoserie mezi jejich Z pozicemi mírně prohýbá). **Root cause:** porušené už dřív zapsané pravidlo `car_body_placement_methods.id=1` ("prohnutí stěny neznamená posun noh vůči sobě, jen jiný kolizní bod, PLATÍ PRO NOHY JAKO CELEK") - u původní "Nohy Jumpy" sestavy to nevadilo, protože tam nohy nic tuze nespojovalo (byly daleko od sebe, samostatné). TADY jsou ale obě nohy TUZE SPOJENÉ rovnými nosníky do JEDNÉ tuhé sestavy - podle stejného pravidla proto MUSÍ kolizní krokování proběhnout na CELÉ TUHÉ SESTAVĚ (obě nohy + nosníky + spojnice) JAKO NA JEDNOM OBJEKTU, ne zvlášť na každé noze. **Oprava (v2):** sdílený `offsetX`/`offsetY` pro celou skupinu (obě nohy mají identický X rozsah 424–750mm, nosníky flush na obou koncích, ověřeno bez vnitřní kolize i bez kolize s CI14). **Obecné pravidlo:** kdykoli je víc noh spojeno TUHÝMI díly do jedné sestavy (nosníky, rámy, lůžka), kolizní krokování vůči karoserii se dělá na CELÉ SESTAVĚ najednou - nezávislé krokování je správné JEN pro opravdu samostatné, nespojené nohy.

**Ještě druhá chyba nalezena stejným pohledem shora - v ROBERTOVĚ vlastním zadání rozestupů** (404/808/1212mm), oprava na 426/832/1238mm výše - vzdálenost mezi nohama musí zohlednit skutečnou délku eurobxu (400mm) + vůli, ne jen hrubý odhad. **Třetí upřesnění** (Robert, po kontrole ve scéně, s přesnými kotami z CAD výkresu): finální hodnoty 430/832/1232mm + přesné koty spojnic 15/415/816/1217mm (viz "Rozklad pravidla" výše) - bot mezitím u N=1/N=3 sám odhadoval rovnoměrné rozdělení spojnic, což bylo nesprávně, skutečné koty mají pevný krok ~401mm od předchozí spojnice, ne dělení celého rozpětí.

**Otevřené**: orientace průřezu nosníků (která strana profilu 30x30 je nahoru jako ložná plocha eurobxu) - zatím neřešeno, nosník má čtvercový průřez takže nehraje roli; přesná výška nosníků (410mm je pracovní hodnota) - Robert si ji nastaví ručně.

**Kompletní regál postaven pro všechny 3 varianty s finálními kotami (2026-08-30):** `product_assemblies.id=38` (1ks, 430mm, spojnice 15/415mm), `id=37` (2ks, 832mm, spojnice 15/415/816mm, POTVRZENO Robertem ve scéně), `id=39` (3ks, 1232mm, spojnice 15/415/816/1217mm) - všechny stejným postupem (kolizní krokování celé tuhé sestavy najednou), bez vnitřní kolize, bez kolize s CI14. Přesné koty spojnic pocházejí přímo z Robertova CAD výkresu, ne z botova odhadu (viz "Rozklad pravidla" výše pro vzorec kroku).

**Procesní chyba (Robert, 2026-08-30, "ty nedodržuješ pravidla?"):** bot zapsal opravenou geometrii přímo do `product_assemblies` několikrát po sobě BEZ doprovodné 2D dimenzní kontroly ze skutečné geometrie - jen na dotaz "je to prověřeno přes standard 2D pohledy?" se ukázalo, že ne (výsledná čísla se nakonec shodovala, ale to byla shoda, ne ověřený postup). **Doplněk pravidla "3D model vždy"** (viz `WORKFLOW.md`, bod 10): 3D model v karoserii je povinný VŽDY, ale NENAHRAZUJE 2D dimenzní kontrolu, kdykoli je v geometrii víc mm-kritických proměnných (rozestupy, pozice spojnic podle vzorce, srovnání variant) - obě kontroly jsou povinné, ne jedna náhradou druhé. 2D pohled musí vzniknout ze skutečné `Box3` geometrie (ne z position/scale čísel) s mm mřížkou a kótami, PŘED tím, než se práce prohlásí za hotovou.

## Postup vložení eurobxu (reálný produkt) na lůžko (Robert, 2026-08-30, po 3 kolech oprav)

Zapsáno kompletně do `shape_geometry_methods.name='ukladani-euroboxu-do-luzek'` (`id=3`, `version=6`, `verified_by='robert'`), klíč `postup_vkladani_euroboxu_na_luzko_2026_08_30`. Shrnutí (detail v DB):

1. **ZMĚŘ skutečnou geometrii** (`Box3` na reálném GLB, ne z názvu produktu) - pivot eurobxu byl stovky mm mimo vlastní geometrii. Zkontroluj i unikátní Z/Y hodnoty vrcholů (schodovitý profil = varovný signál na stohovací/nesting detail jako nožka).
2. **Otočení:** eurobox má délku (400mm) na místní ose Y, výšku (120mm, s 12mm "nožkou" na jednom konci) na místní ose Z - stejná konvence jako profily. Rotace 90° kolem osy X je nutná pro natočení delší stranou podél světové Z, ALE existují dvě opačná znaménka (+90/−90) a jen JEDNO dává správnou orientaci (nožka dolů) - **nelze uhodnout, ověřuj empiricky**: po otočení musí "nožkový" schodek vyjít na `box.min.y` (absolutní minimum), ne na maximu. Pro tenhle konkrétní eurobox: `quaternion = [-0.707107, 0, 0, 0.707107]`.
3. **Pozice X/Z:** X = střed mezi oběma nosníky (`offsetX + D/2`), Z = střed KAŽDÉHO slotu mezi sousedními příčnými spojnicemi (spojnice = hranice jednotlivých boxů).
4. **Pozice Y - NEJDŮLEŽITĚJŠÍ A NEJČASTĚJI ŠPATNĚ:** není správné posadit `box.min.y` (absolutní spodek VČETNĚ nožky) přesně na horní hranu nosníku - to dá box o 12mm VÝŠ, než má být (jen špička nožky se "klepe" o nosník, hlavní skořepina visí nad ním). Robert doslovně: "posunou o 12 milimetrů níže tak se vlastně budou dotýkat nosníků a příček" - správný vzorec: `ty = (RAIL_Y_CENTER + offsetY + T/2) − probe.box.min.y − 12`.
5. **Po kroku 4 vznikne ZÁMĚRNÝ `Box3` přesah ~12mm na ose Y** mezi eurobxem a nosníkem/spojnicí - to NENÍ chyba, `Box3` nerozliší vnoření do dutiny (schodek) od vnoření do plného materiálu. Finální kontrola u takových dílů je VŽDY Robertovo vizuální potvrzení ve scéně (viz `.claude/skills/3d-scena-spoje/SKILL.md`, bod 8), ne numerický 0-přesah test.

**Kontext otočené karoserie:** po tomhle postupu Robert nechal ještě otočit celou karoserii CI14 o 180° (viz sekce výše) - postup vkládání eurobxu (kroky 1-5) je na orientaci karoserie NEZÁVISLÝ, mění se jen absolutní světové souřadnice stěn, ne tenhle vzorec.

## Dokončení regálu: záslepky nahoru + uzavření výřezové nohy (Robert, 2026-08-31)

Robert: "zkus ve scéně produktové sestavy, na ty regály v autě doplnit záslepky, tzn na profily, ale jen nahoru. Členité noze zkus doplnit příčku aby se stala uzavřenou strukturou."

**Záslepky (endcap) na volné horní konce:** katalogový díl `shop_products.id=3071` (SKU `2.3.001.3030.01`, `product_3071.glb`). Žádná uložená naučená póza pro tenhle SKU (`attach_pose`/`attach_pose_source` = `NULL`) - vzorec dopočítán přímo z geometrie.

**OPRAVA orientace (Robert, po vizuální kontrole ve scéně):** "zobáky se musí zanořit do profilů, takže otoč o 180 stupňů a posun aby na čelo profilu doléhala rovná obvodní plocha záslepky." Detailní rozbor GLB po Z-vrstvách odhalil, že záslepka NENÍ jednotný 9mm blok - má širokou PŘÍRUBU (plná šířka 30×30, lokálně `z=[0,3]`, tloušťka 3mm) a užší "zobák"/spigot (cca 7×7mm, `z=[3,9]`, hloubka 6mm). První verze měla spigot směrem VEN z profilu (špatně) - opraveno na `quaternion = setFromUnitVectors((0,0,-1), N)` (BEZ `.negate()`, tj. o 180° otočeno vůči první verzi) = konstanta `[0.7071068, 0, 0, 0.7071068]` pro horní konce se world normálou `N=(0,1,0)`. Pozice navíc posunuta o `+3mm` (tloušťka příruby) podél normály: `position_zaslepky = position_dilu + (0, delka_dilu/2 + 3, 0)` - tak aby přechod příruba/spigot (lokální z=3) dopadl přesně na konec profilu, příruba zůstala VNĚ (viditelná, dosedající čelem) a spigot (6mm) zajel DO profilu. Ověřeno na reálné geometrii: profil končí přesně tam, kde začíná spigot (žádná mezera, žádný přesah přes přírubu). Aplikováno na 3 volné horní konce na noze (přední svislice, zadní svislice/zadní svislice nad zářezem, cap) × 2 nohy = 6 záslepek na regál.

**Uzavření výřezové nohy:** "sloupek před podběhem" (0 až 395mm) a "zadní svislice nad zářezem" (395 až 920mm) na sebe navazují STEJNOU výškou, ale RŮZNOU plochou (jsou v jiném X kvůli úskoku před podběhem kola) - podle Robertovy definice spoje ("celá plocha čela...") se nemůžou přímo dotknout. Řešeno DALŠÍM profilem (`pricka-uzavreni-vyrezu`) POLOŽENÝM SHORA na sloupek (T-styl/cap-styl dosed na horní čelo sloupku, stejný princip jako "cap" jinde v konstrukci) a NATAŽENÝM až k boku zadní svislice nad zářezem (T-styl boční dotyk).

**OPRAVA délky (Robert): "protáhni na dotek k přednímu svislému profilu, neřekl jsem že máš tu příčku zkrátit, má být stejně dlouhá jako ta horní."** První verze končila na sloupku (`colLeft`), nedosahovala k přední svislici. Opraveno na STEJNÝ rozsah jako "spojnice-horni" (`rungLo=T` až `rungHi=D-T`, délka `D-2T`) - cestou přes sloupek před podběhem na něm dál dosedá shora (cap-styl), jen už nekončí na jeho hraně, ale pokračuje až k přední svislici (T-styl boční dotyk). Ověřeno touchReportem na reálné geometrii: všechny 3 spoje (sloupek, zadní svislice, přední svislice) přesně `gap=0/overlap=0` na dotykové ose, plný `30mm` přesah na obou zbylých.

Obojí doplněno do `product_assemblies.id=43/44/45` (přepočítáno + otočeno stejnou 180° transformací jako zbytek sestavy), ověřeno bez kolize s karoserií i bez neočekávané vnitřní kolize (spigot-do-profilu nesting je záměrný, stejná gotcha jako u eurobxu).

**Uloženo jako postup do DB** (Robert: "ty záslepky a doplnění příčky nohám přidej do DB jako postup dokončení nohou, pokud stavíme regál s lůžky na euroboxy") - `shape_geometry_methods.name='dokonceni-nohy-zaslepky-a-uzavreni'` (`id=4`, `version=2`, `verified_by='robert'`), navazuje na `id=3` (`ukladani-euroboxu-do-luzek`).

**Důležité omezení rozsahu** (Robert: "u jiných typů regálů se příčka doplňovat nebude, protože ji zastoupí příčka komponentu, např šuplík") - záslepky na volné konce (část A) jsou obecný krok, ale uzavírací příčka (část B) je specifická PRO REGÁL NA EUROBOXY. U jiných komponent (např. šuplík) mezeru uzavírá VLASTNÍ konstrukční prvek dané komponenty - krok B se v tom případě VYNECHÁVÁ, nepřidává se samostatná "uzavírací příčka" nohy navíc.

## Sloupcová struktura regálu (Robert, 2026-08-31, OBECNÉ pravidlo - platí pro VŠECHNY typy regálů v autech, ne jen euroboxy)

Zapsáno do DB jako `shape_geometry_methods.name='regal-sloupcova-struktura'` (`id=5`, `version=2`). Robert doslovně: "první 2 nohy vytváří tzv základní sloupec regálu, když přidáme třetí nohu, jedná se o druhý sloupec regálu, když přidáme čtvrtou nohu, jedná se o třetí sloupec regálu, jejichž šířka závisí na požadavcích zákazníka resp co tam bude ukládat."

**Definice:** "sloupec" = úsek mezi DVĚMA sousedními nohami podél délky vozidla. Základní sloupec = první pár noh (noha 1+2). KAŽDÁ DALŠÍ noha přidává JEDEN DALŠÍ sloupec a SDÍLÍ jednu nohu s předchozím sloupcem (noha 3 + už existující noha 2 = druhý sloupec, noha 2 je společná hranice). Obecně: N noh = (N-1) sloupců. Šířka KAŽDÉHO sloupce je nezávislá - určuje se podle toho, co se v daném úseku bude ukládat (různé sloupce téhož regálu mohou mít různou šířku).

**Limit kolize s karoserií** (Robert, doplněno stejný den): "pokud narazíme na kolizi s karoserií dříve než dokončíme požadovanou mezeru mezi posledníma nohama, sloupec se nepřidá, nebo se musí zvolit jiný typ komponentu mezi posledníma nohama." Při postupném přidávání sloupců (délka vozidla je fixní a konečná) je nutné PRŮBĚŽNĚ (sloupec po sloupci, ne až na konci) ověřovat kolizním krokováním CELÉ tuhé sestavy (viz `car_body_placement_methods.id=1`), jestli poslední noha nového sloupce nenarazí do karoserie dřív, než se dosáhne celé požadované šířky. Při kolizi: (a) sloupec se vůbec nepřidá, NEBO (b) pro poslední mezeru se zvolí jiný typ/menší varianta komponenty, která se do zbývajícího prostoru vejde.

**Optimalizace využití stěny** (Robert, 2026-08-31, specifické pro euroboxy - zapsáno i v `shape_geometry_methods.id=3`): "vždy je potřeba vybrat nejoptimálnější variantu lůžek tak aby byla stěna auta co nejvíce obsazená/využitá." Při návrhu regálu (počet sloupců, šířka každého z variant 1/2/3ks) je cílovou funkcí maximalizovat využitou délku stěny vozidla v rámci limitu kolize výše - přesná kombinatorika/algoritmus zatím NEIMPLEMENTOVÁN, jen zapsán cíl pro budoucí automatický návrh sestavy.

**První živá aplikace pravidla (Robert: "zkus podle toho přidat další sloupec regálu v Jumpy, máš k dispozici 3 šířky"):** k existujícímu sloupci 1 (2ks eurobox, 832mm, sdíleno s `product_assemblies.id=44`) přidán sloupec 2, sdílející s ním nohu. Postup dle obou pravidel výše - zkoušeno sestupně od největší varianty (3box 1232mm), pak 2box (832mm), až 1box (430mm): **3box i 2box NEPROŠLY** kolizní kontrolou celé dvousloupcové tuhé sestavy (narazily by na zadní stěnu karoserie CI14 dřív, než by se dokončila požadovaná šířka) - zvolen **1box (430mm)** jako největší, co se do zbývajícího prostoru vejde. Uloženo jako `product_assemblies.id=46` ("Regál na euroboxy - 2 sloupce (2ks + 1ks)"), ověřeno bez kolize s karoserií i bez neočekávané vnitřní kolize.


## Stavba od přepážky (bulkhead-first), obrácený směr (Robert, 2026-08-31)

Robert po zkoušce sloupce 2 výše (`id=46`) zásadně opravil přístup: "tak jinak, potřebujeme zaplnit maximálně stěnu euroboxama" a odhalil, že se dosud NIKDY neověřilo, kde skutečně leží přední stěna (přepážka) karoserie - všechna dosavadní práce byla kotvena poblíž podběhu kola, ne od přepážky. Zadání: "stavajici regály jsou ok [zůstávají, tohle je nové samostatné zadání] ... začni totéž od přepážky ... v podstatě ted musís začít v obráceném směru ... od přepážky, pokracujes pres podběh a koncís tam kde dostaneš ještě nějaký sloupec aniž bys byl v kolizi."

**Identifikace přepážky:** rozbor bounding boxů stěn karoserie CI14 (po otočení o 180°, viz sekce výše) - stěna `B` (flipped X=[-807,807] celá šířka, Z úzký plátek [-2562,-2024]) je PŘEDNÍ PŘEPÁŽKA (celá šířka/výška, úzký v Z, na jednom extrému délky) - NE boční stěna. Stěny `L`/`R_D` jsou boční (táhnou se po celé délce). Opačný (otevřený) konec kolem flipped Z=147 nemá žádnou stěnu (zadní dveře).

**Bezpečná startovní pozice první nohy** dohledána kolizním krokováním (1mm krok/2mm odskok): pre-flip Z≈2007mm (přiblížení k přepážce), tj. vzdálená hrana nohy (dotyk na `B`) na pre-flip Z≈2037.

**MIRROR_C trik** pro znovupoužití existujících stavebních funkcí (které předpokládají RostoucÍ lokální Z = "dál do sloupce", tj. směr OD přepážky K podběhu) při stavbě v OPAČNÉM reálném směru (od přepážky k podběhu = KLESAJÍCÍ pre-flip Z): zavedena lokální souřadnice `zPrime` (vždy rostoucí, jako dosud), převedená na skutečné `Z_real = MIRROR_C − zPrime` (`MIRROR_C=3000`) těsně před finální 180° transformací. Po složení s flipem (`x,z → −x,−z`) vzniká čistý lineární vztah `final_z = zPrime − MIRROR_C` (žádná další kompenzace potřeba pro díly, jejichž lokální počátek = geometrický střed, což platí pro `Object_7`).

**Chyba a oprava při umísťování eurobxů:** centrovací "probe" (kompenzace mimostředého pivotu eurobxu vůči cílovému středu slotu, viz krok 2-4 postupu `ukladani-euroboxu-do-luzek` výše) byl původně spočítán pod PŘED-FLIP kvaternionem (`Q_ALONG_Z`), ale pak se na hotový díl (pozice I kvaternion) navíc aplikoval `MIRROR_C` převod a 180° flip - tím se kompenzace zneplatnila (na rozdíl od `Object_7`, eurobox MÁ mimostředý pivot, takže na kvaternionu záleží). Důsledek: 2 ze 4 eurobxů vyšly ~700mm za nohou 0, hluboko v přepážce, mimo celou konstrukci. **Oprava:** centrovací probe se musí počítat pod FINÁLNÍM (již 180°-otočeným) kvaternionem a cílová pozice slotu se musí počítat přímo ve FINÁLNÍM světovém rámci (`final_z = zPrime − MIRROR_C` pro hranice slotu), ne v pre-flip rámci s dodatečným přepočtem až po centrování. Obecná poučka: centrovací kompenzace mimostředého pivotu je vždy vázaná na KONKRÉTNÍ kvaternion, kterým se díl nakonec vykresluje - nelze ji spočítat v jedné transformační fázi a použít v jiné.

**Výsledný plán (kolizní krokování + sloupcová struktura + limit kolize, viz `shape_geometry_methods.id=5`):** 3 nohy, 2 sloupce.

| Noha | Typ | Z_real (pre-flip) | Poznámka |
|---|---|---|---|
| 0 | plain | ≈2037 | u přepážky, bezpečná blízká hrana |
| 1 | vyrez | ≈775 | obchází podběh kola |
| 2 | vyrez | ≈315 | další sloupec, dál už kolize s karoserií |

Sloupec 1 (noha 0↔1): šířka 3box, 3 euroboxy. Sloupec 2 (noha 1↔2): šířka 1box, 1 eurobox. Celkem 4 euroboxy. Další sloupec už nejde přidat bez kolize s karoserií (ověřeno, kolizní limit z `id=5` zabránil pokračování).

**Uloženo jako `product_assemblies.id=47`** ("Regál na euroboxy od přepážky (Jumpy CI14, profil 30x30, D=326mm)"), `shop_products.id=3792`. Ověřeno: bez kolize s karoserií CI14 (`collidesWithWalls`), bez neočekávaných vzájemných průniků dílů (jen očekávané zanoření eurobox/záslepka do profilu, 25 očekávaných nestingů, 0 neočekávaných, 42 dílů rozestavěné konstrukce + 3 díly karoserie). Celkové rozměry: šířka 326mm, délka 1752mm (přepážka→podběh), výška 1183mm. 2D technický výkres (půdorys + nárys, generovaný přímo z reálných `Box3` rozměrů, ne odhadem): https://claude.ai/code/artifact/327e9d5b-989e-49df-9c31-392a3e24063a

**Poznámka ke stavu DB:** při této práci byla tabulka `product_assemblies` nalezena PRÁZDNÁ (0 řádků, id 32-46 zmizela) - nejde o akci provedenou v rámci tohoto zadání, stav byl zjištěn při pokusu o kontrolu kolize s "existující" sestavou. Robert toto smazání potvrdil jako záměrné ("bozinku stary regál nepotřebujeme pokud už ho umíme skládat") - staré ukázkové sestavy nahradily obecné postupy v `shape_geometry_methods`, samostatné DB záznamy pro ně už nejsou potřeba.

## Výškové varianty eurobxu (120/170/220/270/320mm) a pravidlo vertikálních pater (Robert, 2026-08-31)

Robert: "do sceny v katalogu přibyly další střední boxy, takže tam jsou ted vsechny výšky: 120, 170, 220, 270, 320mm." Katalog nyní obsahuje 5 výškových variant eurobxu střední velikosti (půdorys 400×300mm konstantní): `shop_products.id=3788` (…x120, dosud jediný použitý), `3793` (…x170), `3794` (…x220), `3795` (…x270), `3796` (…x320).

**Ověření geometrie (dle kroku 1 postupu `ukladani-euroboxu-do-luzek`, nikdy nevěřit názvu produktu):** půdorys skutečně 299×399mm shodný u všech 5 variant. "Nožkový" schodek (nesting foot) hluboký ~12mm od absolutního minima je přítomný a stejně hluboký (11.9–12.2mm) u VŠECH 5 variant - konstanta `-12` ve vzorci pozice Y (krok 4) tedy platí beze změny pro libovolnou výškovou variantu.

**Zjištěná past:** `product_3793` (170mm) má JINOU konvenci místního počátku (pivotu) než ostatní 4 varianty (asymetrický pivot u 3788/3794/3795/3796, symetrický kolem nuly u 3793) - i v rámci jedné produktové řady "stejný produkt, jiná velikost" NEZARUČUJE stejnou konvenci pivotu. Stávající kód to zvládá správně, protože počítá centrovací "probe" dynamicky za běhu z KAŽDÉ konkrétní GLB, ne z hardcodovaného offsetu - žádná změna kódu není potřeba, ale je to konkrétní důkaz pro budoucí bota, aby vždy měřil každou SKU zvlášť.

**Nové pravidlo vertikálních pater** (Robert, doslovně): "lůžko je pro vsechny výšky totožné / stejné; jednotlivé lůžka nad sebou mají takovou mezeru aby vždy byla mezi boxem a lůžkem nad ním mezera 30mm." Fyzická konstrukce lůžka (nosníky+spojnice) je nezávislá na tom, jakou výškovou variantu eurobxu do ní zákazník vloží - stejný návrh pro 120mm i 320mm box. Rozdíl mezi výškovými variantami se promítá VÝHRADNĚ do svislé mezery k dalšímu patru nad ním:

```
Y_rail_top(patro N+1) = Y_rail_top(patro N) + H_box(patro N) + 30mm (mezera) + T (30mm, tloušťka profilu)
```

⚠️ **PŘEKONÁNO (2026-09-17, souvislý postup krok 9):** správně `Y_rail_top(N+1) = Y_rail_top(N) + (H_box − 12) + 30 + 30` - deklarovaná výška boxu zahrnuje 12mm nožku zapadající pod horní hranu nosníku; vzorec výše dává mezeru 42 mm místo 30 (viz „Univerzální +12mm chyba“ níže).

(box sedí skořápkou přímo na rail top - nožka zapadá 12mm POD rail top, takže viditelná výška nad rail top = plná deklarovaná výška boxu, ne "probe" výška minus nožka.)

**Pořadí výšek odspoda nahoru** (Robert, doslovně): "vysoké boxy jsou vždy vespod, směrem nahoru se boxy mohou/nemusí snižovat, např první lůžka boxy 320mm, druhé lůžka nad tím s boxy 220mm, atd." Výška boxu v každém dalším patře musí být menší nebo rovna výšce patra pod ním (posloupnost H(1) ≥ H(2) ≥ H(3)... odspoda nahoru) - nikdy obráceně.

**Limit maximální výšky, po kterou lze patra přidávat** (Robert, doslovně): "výška po kterou lze lůžka přidávat je daná tím, že žádné čelní plocha profilu nosníku nesmí zůstat ani setinu milimetru volná mimo plochu svislých profilů nohou." Tohle je přímá aplikace základního pravidla spoje (viz `PRAVIDLA_SPOJU.md` - "[spoj] existuje pouze pokud se celá plocha čela jednoho profilu dotýká buď celé plochy čela druhého profilu nebo kterékoli stěny") jako STOP-podmínky pro přidávání dalších pater: nosník ("lůžko") se T-stylem dotýká boku svislého profilu nohy na obou koncích - validní spoj vyžaduje, aby celý 30mm průřez konce nosníku ležel CELÝ uvnitř Y-rozsahu, kde na daném X SKUTEČNĚ existuje svislý profil (ne kdekoli mezi 0 a celkovou výškou nohy H). Konkrétně u naší CI14-Jumpy nohy: strana X=T/2 (přední svislice) sahá celou výšku 0–1180mm, ale strana X=D-T/2 (zadní) sahá jen do Y=920mm u `plain` nohy, resp. jen Y=[397,922]mm u `vyrez` nohy (nad/pod tím na tomhle X žádný svislý profil není - `cap` je na jiném X, blíž stěně). Maximální střed nejvyššího nosníku = horní hranice tohoto kratšího rozsahu − T/2, BEZE ZBYTKU TOLERANCE (i 0.01mm přesah je nepřípustný) - vždy ověřit na skutečné geometrii dané nohy, ne odhadem z celkové výšky nohy H=1180mm.

**Důsledek pro kratší nohy** (Robert, doslovně): "možné kombinace výšek boxů jsou o to nižší čím kratší je výška nohou." Přímý důsledek limitu výše - počet dostupných kombinací výškových variant NENÍ konstanta napříč vozidly/typy noh, musí se přepočítat vždy znovu ze skutečné geometrie konkrétní nohy (stejná výstraha jako u `car_body_placement_methods.id=1` "upozornění na univerzálnost" - žádné číslo se nesmí převzít jako univerzální).

**Diverzifikace napříč sloupci** (Robert, doslovně): "kombinace výšek euroboxů v ruzných sloupcích nemusí být synchronní, naopak preferuje se diverzifikace, tzn jiné výšky boxů napříč sloupci." Výškové patrování (posloupnost výšek odspoda nahoru výše) se řeší NEZÁVISLE pro každý sloupec zvlášť - sloupec A může mít patra 320/220/120mm a sousední sloupec B současně 270/170mm, aniž by bylo nutné (nebo žádoucí) mít stejnou kombinaci výšek po celém regálu. Diverzifikace je PREFEROVANÁ, ne jen tolerovaná - různé sloupce budou v praxi skladovat různý materiál, uniformní výška po celém regálu by byla zbytečně omezující. **Důsledek pro algoritmus:** limit maximální výšky/kombinace pater (viz výše) se počítá SAMOSTATNĚ pro každý sloupec (daný dvěma páry noh na jeho okrajích), NE jednotně pro celou sestavu.

Zapsáno do `shape_geometry_methods.id=3` (`ukladani-euroboxu-do-luzek`, `version` 7→11). **Stav: pravidlo zapsáno, zatím NEAPLIKOVÁNO na žádnou konkrétní vícepatrovou sestavu** - čeká na konkrétní zadání (kolik pater, jaké výškové varianty v kterém patře/sloupci).

**OPRAVA VÝKLADU (Robert, 2026-08-31, po chybné aplikaci na Jumpy L1/L2):** "toto bylo zadání: ... boxy musí být pouzity vsechny velikosti z výšek 120, 170, 270 ... ale u Jumpy L1,L2 se nedodržela podmínka pouzití vsech velikostí boxů uvedenych." Když zadání vyjmenuje VÍCE povolených výšek s dovětkem "poměr počtu boxů libovolně pro optimalizaci prostoru", NEZNAMENÁ to "vyber si svobodně, klidně i jen jednu výšku, pokud to matematicky maximalizuje počet kusů" (takhle to bylo dřív chybně vyloženo u Jumpy L1 `id=50` a L2 `id=51` - obě skončily se stejnou výškou 120mm na všech patrech). Vyjmenování více výšek je POŽADAVEK NA ROZMANITOST - všechny vyjmenované výšky se mají NĚKDE v hotové sestavě objevit alespoň jednou. "Poměr libovolný" se týká POMĚRU MEZI NIMI, ne toho, jestli se některá smí zcela vynechat. Čistá matematická maximalizace počtu kusů (=vždy nejmenší dostupná výška) NENÍ správný cíl, pokud zadání vyjmenovává víc výšek - diverzita má přednost před čistým počtem. Zapsáno do `shape_geometry_methods.id=3` (`vyklad_seznamu_povolenych_vysek_2026_08_31`, `version` 11→12, `verified_by='robert'`).

## Úhelníkové spojky na spojích noh (Robert, 2026-08-31: "zkus aplikovat na všechny spoje nohou v aktuálním regále v autě Jumpy > uhelníky")

Aplikováno na regál od přepážky (`product_assemblies.id=47`, viz sekce výše). "Spoje noh" = spoje UVNITŘ konstrukce každé jednotlivé nohy (přední/zadní svislice, spojnice-dolní/horní, sloupek před podběhem, příčka uzavření výřezu, cap) - NE rámová konstrukce lůžka mezi dvěma nohami (nosníky/spojnice rámu), to nebylo součástí tohoto zadání.

**Díl:** `shop_products.id=3045` ("Úhelníková spojka 30×30", SKU `2.2.001.08.3030.01`, GLB `product_2895.glb`) - jediný katalogový úhelník pro profil 30×30, má uloženou naučenou pozici (`uhelnik_pose = {"face":1,"q":[0.5,0.5,-0.5,-0.5]}`) i geometricky rozpoznané dosedací plochy (`geo_faces_json`, 2 kolmé plochy).

**Postup:** živá logika tlačítka "⟂ Automat → Úhelník" (`uhelnikAutPlaceForPair`/`uhelnikAutPlaceOne` a jejich závislosti - `findAccessoryToProfileCandidates(AllSpins)`, `uhelnikCornerFrameQuat`, `applyFaceToFaceCandidate`, `uhelnikAutAlignAxial`, `geoFaceSnapToCornerWalls`, `uhelnikLugAlignToSlots` - vše ve `webapp/scene.html`, plus sdílené `computeConnectorsLocal`/`worldConnectorsOf`/`isProfilePart` z `webapp/js/scene-geometry-shared.js`) byla **portována 1:1 do Node.js** a spuštěna nad reálnou geometrií (`Object_7.glb`, `product_2895.glb`) a reálnými daty z `product_assemblies.id=47`, omezeně jen na páry profilů uvnitř jedné nohy (19 dílů, 3 nohy). Beze změny scény/UI - čistě dávkové zpracování nad uloženou sestavou.

**Nalezená a opravená chyba při portování:** `computeConnectorsLocal` se MUSÍ počítat na síti PŘED nastavením finální pozice/rotace/škály (přesně jak to dělá `loadCustomShapePartEntry` ve scene.html - `Box3().setFromObject` bere AKTUÁLNÍ transformaci objektu, takže volání AŽ PO umístění dílu by transformaci aplikovalo dvakrát: jednou do "lokálních" souřadnic konektorů, podruhé přes `worldConnectorsOf`). První pokus (spočítáno až po umístění) dal 0 nalezených spojů ze 21 očekávaných (obě strany každého spoje vyšly rovnoběžné misto kolmé). Oprava: `connectorsLocal` se počítá na čerstvě načtené síti PŘED `obj.position/quaternion/scale.set(...)`.

**Výsledek:** všech 21 očekávaných spojů (5 u plné nohy, 8 u každé z 2 členitých noh) nalezeno a ověřeno numericky (kolmost os, `profilesStillTouching` s 2mm tolerancí, stejně jako živá scéna) - **31 úhelníkových spojek** celkem (některé spoje dostaly úhelník na obě strany rohu, jiné jen na jednu, podle toho, kam se úhelník podél osy nohy vejde - `uhelnikAutAlignAxial` stejně jako v živé scéně). Žádné NaN/neplatné pozice, rozměry úhelníků odpovídají skutečné geometrii (~29×29×28mm), pozice numericky ověřeny u vzorku (leží přesně v rozích jednotlivých spojů). Zapsáno zpět do `product_assemblies.id=47.data.parts` (45→76 dílů). 2D výkres (artifact) i celkové rozměry (326×1752×1183mm) beze změny - úhelníky jsou malé a leží uvnitř existující obálky.

**Poznámka k rozsahu:** rámová konstrukce lůžka (nosníky+spojnice mezi nohami) úhelníky zatím NEVYBAVENA - Robertovo zadání explicitně mluvilo o "spojích nohou", ne o celém regálu. Pokud bude potřeba i tam, jde o STEJNÝ postup (stejná funkce `uhelnikAutPlaceForPair`, jen spuštěná na jiné dvojici profilů), jen nebyl součástí tohoto zadání.

**Zobecněno na znovupoužitelnou metodu (bot16, 2026-09-01):** `product_assemblies.id=47` (sestava zmíněná výše) mezitím zanikla při běžném úklidu session - výše popsaný postup je tu zachován jako HISTORIE prvního úspěšného nasazení, ale už není spustitelný na živá data (ta smazaná sestava). Postup byl mezitím zobecněn do parametrické, znovupoužitelné metody nezávislé na jedné konkrétní sestavě/průřezu - `shape_geometry_methods.id=7` (`uhelniky-na-spoje-nohy`), reusable engine `scripts/2026-09-01_uhelniky_leg_joints_lib.js`, ověřeno na 30×30 (plain i vyrez, D=326mm) i na 40×40 (a bonusem 45×45), vždy se správným katalogovým dílem podle skutečného průřezu a ~0mm odchylkou dosedacích ploch. Detail viz `PRISLUSENSTVI_PRIPOJENI.md`, sekce "Zobecnění na znovupoužitelnou METODU `uhelniky-na-spoje-nohy`".

## Regál na celou levou stěnu — vícepatrová aplikace pravidla (Robert, 2026-08-31)

Robert: "zkus tedy postavit regál s euroboxy nějakou kombinaci na celou levou stěnu do max výšky dle pravidla." Cíl: první živá aplikace `pravidlo_vertikalni_patra_2026_08_31` (viz sekce výše) na skutečnou sestavu.

**Délka stěny je už plně využitá stávající strukturou.** Vyplnění "celé levé stěny" znamená STEJNÝ půdorys jako `product_assemblies.id=47` (3 nohy, 2 sloupce — 3box a 1box) — za nohou 2 (Z_real≈315mm) zbývá do skutečné kolize s karoserií jen ~260mm (ověřeno jemným kolizním krokováním s 20mm odskokem, konvence `car_body_placement_methods.id=1` `max_rozpon_nohou`), ale na další (byť jen 1box) sloupec je potřeba minimálně 460mm — délkově tedy už není kam sloupec přidat.

**"Do max výšky dle pravidla"** = přidání 2. vertikálního patra do KAŽDÉHO sloupce, diverzifikovaně (Robert: "preferuje se diverzifikace"):
- Sloupec 1 (3box, u přepážky): patro 1 = 270mm box, patro 2 = 120mm box.
- Sloupec 2 (1box, u podběhu): patro 1 = 220mm box, patro 2 = 170mm box.

Obě kombinace nerostoucí odspoda nahoru, obě respektují stop-podmínku (rail-center musí zůstat v rozsahu, kde na X=D−T/2 skutečně existuje svislý profil nohy — průsečík plain nohy [0,920mm] a vyrez nohy [395,920mm] = [395,920mm], tj. rail center max 905mm): sloupec 1 patro 2 vychází na center=740, sloupec 2 na center=690 — obě bezpečně pod stropem.

**Zpřesnění stropu** (oproti prvotnímu odhadu): box-top NEKOLIDUJE s "spojnice-horni"/"cap" dané nohy, i kdyby box zasahoval do jejich Y-rozsahu — tyhle díly patří vždy JEDNÉ konkrétní noze (tenký Z-plátek přesně v Z pozici nohy), zatímco euroboxy stojí v Z-mezeře MEZI nohama — reálně se nikdy nepotkají v X/Z zároveň. Limitující je tedy VÝHRADNĚ joint-containment pravidlo výše, ne fyzická kolize s vlastními díly nohy. Oba sloupce mají 165–195mm rezervu k teoretickému stropu — 3. patro by se teoreticky vešlo, zámerně ponecháno na 2 pro tuhle ukázku.

Uloženo jako `product_assemblies.id=48` ("Regál na euroboxy celá levá stěna, vícepatrový"), `shop_products.id=3797`. Ověřeno: bez kolize s karoserií CI14, bez neočekávaných průniků dílů, celkové rozměry beze změny oproti `id=47` (326×1752×1183mm — patra se vejdou do stávající obálky nohy). 8 euroboxů celkem (3+1 na patro 1, 3+1 na patro 2). Úhelníkové spojky (viz samostatná sekce) na tuhle sestavu zatím NEJSOU aplikované. 2D výkres (půdorys + nárys barevně podle výšky boxu): https://claude.ai/code/artifact/5167a7b3-592a-4967-adc8-a888c6da82b9

## Protažení zadní svislice členité (výřezové) nohy směrem dolů (Robert, 2026-08-31)

Robert, doslovně: *"musíme se ještě naučit zvětšovat prostor/výšku do které lze euroboxy vkládat. Jednoduchá většinou ta první noha u prepazky nemá limity, prakticky by mohla obsahovat lůžka už od podlahy, resp od uplného spodního okraje nohy. Členitá noha z výřezem pro podběh je vždy ta limitní směrem dolu. Členité noze podle typu karoserie / výšky podběhu lze nejvdálenější svislý profil protáhovat směrem dolů dokud nenarazí na kolizi a odtud od kolize zpět 20mm. Zároveň nejspodnější zadní svislý profil členité nohy se zkrátí právě o tu délku o kterou se protáhl ten profil nejzadnější. Spolu s tím se jen posune příčka."*

**Interpretace:** "nejvzdálenější/nejzadnější svislý profil" = role `zadni-svislice-nad-zarezem` (X=[D−T,D], nejblíž stěně). "Nejspodnější zadní svislý profil" = role `sloupek-pred-podbehem` (jediný díl zadní-strany rodiny, který začíná od podlahy Y=0). Příčka = `pricka-uzavreni-vyrezu`, jen se posune na nový šev, role/připojení beze změny.

**Reálné 1mm kolizní krokování** (skutečná geometrie karoserie CI14, NE fixní konstanta `CUTOUT_H=395`) - drženo horní konec `zadni-svislice-nad-zarezem` fixně na Y=920 (`H−CAP_H`), spodní konec posouván dolů z 395mm po 1mm, testováno `collidesWithWalls` (1:1 produkční kolizní logika) na jedné z dříve ověřených "vyrez" noh (Z_real po flipu = −760mm, tatáž pozice jako v dřívějším `id=47`):

- Kolize nalezena při `bottomY=179mm` (poslední bezkolizní krok `bottomY=180mm`), potvrzeno stabilní (koliduje nepřetržitě od 179mm až po podlahu 0mm - reálný povrch karoserie/podběhu, ne šum vzorkování).
- 20mm zpět (Robertem explicitně zadaná hodnota pro tenhle konkrétní krok, NE obvyklé 2mm používané jinde v této metodice) → **Y_new = 199mm**. Ověřeno, že na Y_new=199 už skutečně nekoliduje.
- **ΔY = CUTOUT_H(395) − Y_new(199) = 196mm** zisku oproti původní konzervativní konstantě.

**Aplikace:** `sloupek-pred-podbehem` zkrácen na `[0, 199]` (dřív `[0, 395]`), `zadni-svislice-nad-zarezem` prodloužen na `[199, 920]` (dřív `[395, 920]`, horní konec beze změny), `pricka-uzavreni-vyrezu` přesunuta na nový šev Y=214mm (`Y_new + T/2`, dřív 410mm).

**Ověřeno** na upravené noze: (a) celá noha bez kolize se skutečnou karoserií CI14, (b) bez neočekávané self-kolize mezi díly nohy, (c) všechny 3 spoje příčky (↔sloupek, ↔zadní-svislice, ↔přední-svislice) stále plní Robertovu definici spoje (celá plocha čela na 2 osách, gap/overlap≈0 na dotykové ose).

Uloženo jako samostatný validační checkpoint `product_assemblies.id=49` ("Noha vyrez - protazeni zadni svislice, D=326mm, validace"), `shop_products.id=3798`, `active=0`. **Záměrně NEAPLIKOVÁNO na `id=47`/`id=48`** (produkční sestavy s úhelníky a vícepatrovou strukturou postavené na staré geometrii nohy) - kaskádování do reálných regálů je samostatný budoucí krok. Zapsáno do `shape_geometry_methods.id=6` (`protazeni-zadni-svislice-vyrezove-nohy`, nová metoda - odlišná osa/scope od `id=2` `zmena-hloubky-nohy`).

**Upozornění na univerzálnost** (stejný princip jako `car_body_placement_methods.id=1`): Y_new=199mm/ΔY=196mm NENÍ univerzální konstanta - platí výhradně pro Citroën Jumpy CI14 na testované Z-pozici nohy. U jiného modelu karoserie/výšky podběhu je nutné kolizní krokování zopakovat na reálné GLB geometrii toho konkrétního auta.

**Potvrzeno Robertem přímo ve scéně (2026-08-31):** po vizuální kontrole checkpointu `id=49` - "noha v autě paráda." `shape_geometry_methods.id=6` aktualizováno na `verified_by='robert'` (`version` 1→2).

**Postup prohlášen za OBECNĚ VALIDNÍ, ne jen pro tenhle případ** (Robert, doslovně): "zapiš ten postup jako validní do DB prakticky tato uprava clenite nohy lze aplikovat obecne pro libovolne komponenty i karoserie protoze se prizpusobuje podbehu v danem libovolnem miste." Rozlišení: **konkrétní číslo** (Y_new=199mm/ΔY=196mm) zůstává specifické pro Jumpy CI14 (viz upozornění výše, beze změny) - ale **samotný ALGORITMUS** (reálné 1mm kolizní krokování limitujícího svislého profilu proti skutečné geometrii podběhu na dané Z-pozici, s 20mm odskokem) je obecný a funguje pro JAKOUKOLI karoserii a JAKÝKOLI typ komponenty (ne jen eurobox regál) - přizpůsobí se automaticky tvaru/výšce podběhu kdekoli, protože vstupem je vždy reálná GLB geometrie té konkrétní karoserie, ne pevná konstanta. `shape_geometry_methods.id=6` zapsán jako VALIDNÍ OBECNÝ POSTUP (`version` 2→3) - připraven k opakovanému použití na budoucích komponentách/karoseriích bez dalšího schvalování principu, jen s novým kolizním krokováním pro danou geometrii.

**Vysvětlení k `id=47`/`id=48` mizení (vyjasněno):** zjištěno v paralelně běžící úloze - `product_assemblies` byla nalezena prázdná v půli téhle práce, nešlo o neznámou anomálii. Robert v hlavní konverzaci mezitím explicitně zadal "vymaž vsechno z auta" a hlavní session smazala `id=47`/`id=48` (a jejich `shop_products` 3792/3797) přesně v tu chvíli - shoda v čase je vysvětlením, ne záhadou. Dokumentace výše popisující `id=47`/`id=48` zůstává jako HISTORICKÝ záznam ověřeného postupu (geometrie/vzorce platí beze změny), jen ty konkrétní DB řádky už neexistují.

## Konvence pojmenování sestav: krátký název, karoserie + skladba boxů (Robert, 2026-08-31)

Robert: "názvy tech sestav chci kratší, vycházející spíše z nazvu karoserie a pouzité velikost boxů a počty." Zpřesnění (Robert): "v názvech ale neuvádět opakovaně 400x300 ... stačí např Jumpy XXX.boxy43-120x8-170x4-270x2." **DALŠÍ OPRAVA (Robert, po prvním chybném výkladu):** "43" NENÍ celkový počet kusů (jak bylo první verzi téhle konvence chybně pochopeno) - je to ZKRÁTKA půdorysného rozměru euroboxu 400×300mm (4 a 3 = první číslice každého rozměru). "boxy43" je tedy PEVNÁ, neměnná součást názvu u každé sestavy s euroboxy střední velikosti (400×300mm) - ne dynamické číslo závislé na počtu kusů. Dosavadní dlouhé popisné názvy (např. "Regal na euroboxy - leva stena, maximalni obsazeni (Jumpy L1 CI24, profil 30x30, D=326mm)") nahrazeny formátem:

```
<Karoserie krátce> - boxy43-<H1>x<N1>[-<H2>x<N2>-<H3>x<N3>...]
```

Příklady: `Jumpy L2 CI25 - boxy43-120x15` (jednotná výška), `Jumpy L2 CI25 - boxy43-220x3-170x4-120x5` (smíšená skladba, výšky sestupně), `Jumpy CI14 - noha vyrez protazeni (validace)` (pro sestavy bez boxů, jen popis co se ověřuje). Platí pro `product_assemblies.name` i navázaný `shop_products.name` (SKU se neupravuje, jen zobrazovaný název). Aplikováno na `id=53/54/55` (a zpětně opraveno z dřívější chybné `boxyCELKEM` varianty), platí pro všechny další nově ukládané sestavy.

## Regál na euroboxy — Jumpy L1 (CI24), maximální obsazení levé stěny (2026-08-31)

Robert: "postav znovu v prazdnem Jumpy L1 a L2 levou stěnu na maximum euroboxů velikostí 400x300x120/170/220mm poměr počtu boxů libovolně pro optimalizaci prostoru." Tato sekce popisuje L1 (CI24, car_bodies 126/127/128) — L2 (CI25) je samostatná paralelní práce.

**Zásadní zjištění: CI24 NEBYLA otočena o 180°** (na rozdíl od CI14) — nativní GLB rámec karoserie odpovídá přesně PRE-FLIP rámci CI14 (přepážka na vysokém Z, otevřený konec na nízkém Z, levá stěna "L" na kladné straně X). Stavba proto proběhla PŘÍMO v nativním rámci, bez jakékoli 180°/MIRROR_C transformace.

**Hranice stěn CI24** (reálná GLB geometrie): L (levá) X∈[0,807], Z∈[-147,1915]; R_D X∈[-807,0], Z∈[-147,2212]; B (přepážka) X∈[-807,807] (celá šířka), Z∈[1674.5,2212.0] (úzký plátek na horní Z hranici) — stejná konvence jako CI14, jen jiná konkrétní čísla.

**Přední noha (plain) u přepážky**: kolizním krokováním (1mm/2mm) nalezeno `offsetX=424, offsetY=2, zCenter=1657.74` (blízká hrana dotýká přepážky na Z=1672.74) — TOTOŽNÉ offsetX/offsetY jako u CI14, což potvrzuje, že obě varianty karoserie Jumpy sdílí stejný příčný profil (liší se jen délkou).

**Zadní hranice (sloupcová struktura, shape_geometry_methods.id=5, greedy nejširší-první)**: postaven jen **1 sloupec** (3box, rozpětí 1232mm) mezi nohou 0 (plain, Z=1657.74) a nohou 1 (vyrez, Z=395.74). Další sloupec (i nejmenší 1box, potřeba 460mm) se nevejde — jemné kolizní krokování s 20mm odskokem (konvence `car_body_placement_methods.id=1.max_rozpon_nohou`) našlo jen 358mm volného prostoru za poslední nohou. Výrazně méně euroboxů než u delší varianty (L2/CI25) — očekávané, L1 je zkrácený rozvor.

**Protažení vyřezové nohy (shape_geometry_methods.id=6)**: jediná vyřezová noha (Z=395.74) protažena kolizním krokováním — kolize nalezena při `bottomY=293mm`, 20mm zpět → **Y_new=313mm, ΔY=82mm** (zisk oproti CUTOUT_H=395mm). Výrazně MENŠÍ zisk než u CI14 (Y_new=199/ΔY=196) — potvrzuje dřívější upozornění (`shape_geometry_methods.id=6.upozorneni_univerzalnost`), že konkrétní číslo je specifické pro danou karoserii/pozici, ne univerzální.

**Vertikální patra (shape_geometry_methods.id=3)**: floor sloupce = 313mm (vázáno vyřezovou nohou, plná noha sama nelimituje), strop rail-center = 905mm (H−CAP_H−T/2). Vyšlo **4 patra**, všechna s nejmenší dostupnou variantou 120mm — protože počet slotů na patro (3ks, dáno šířkou sloupce) je nezávislý na výšce boxu, maximalizace počtu pater přímo maximalizuje celkový počet uskladněných boxů (na rozdíl od dřívějších sestav id=47/48, kde šlo o demonstraci diverzifikace, ne o čisté maximum).

**Výsledek**: 2 nohy, 1 sloupec, 4 patra × 3 boxy = **12 euroboxů** (všechny 120mm), rozměry sestavy 326×1292×1183mm (šířka×délka×výška). Uloženo jako `product_assemblies.id=50` ("Regal na euroboxy - leva stena, maximalni obsazeni (Jumpy L1 CI24, profil 30x30, D=326mm)"), `shop_products.id=3799`, `active=0`, `is_public=1`. Ověřeno: bez kolize s karoserií CI24 (`collidesWithWalls` na všech `Object_7` profilech), bez neočekávaných vzájemných průniků dílů (54 očekávaných nestingů eurobox/záslepka do profilu, 0 neočekávaných, 54 dílů celkem). 2D výkres (půdorys + nárys, ze skutečné `Box3` geometrie): https://claude.ai/code/artifact/6a3bca3d-6992-451e-886c-2aa48c662163

## Regál na euroboxy — Jumpy L2 (CI25), maximální obsazení levé stěny (2026-08-31)

Robert: "postav znovu v prazdnem Jumpy L1 a L2 levou stěnu na maximum euroboxů velikostí 400x300x120/170/220mm poměr počtu boxů libovolně pro optimalizaci prostoru." Tato sekce popisuje L2 (CI25) — L1 (CI24) je zdokumentován v sekci výše.

**Karoserie CI25 nebyla otočena** (GLB identické s CI14 pred-flip zálohou, viz `KAROSERIE_UMISTENI.md`) — stavba proběhla v nativním rámci. Přepážka na Z∈[2024.4,2562.0], přední noha (plain) na anchorZ=1993. Max. rozpon (20mm odskok): REAR_ANCHOR_Z=25.

**Sloupce (greedy nejširší-první):** 2 sloupce - 3box (1232mm) a 1box (430mm). 3 nohy: leg0 plain@Z=1993 (přepážka), leg1 vyrez@Z=731, leg2 vyrez@Z=271.

**Protažení vyřezových noh (shape_geometry_methods.id=6), NEJEDNOTNÉ podél stěny:** leg1 Y_new=214 (ΔY=181), leg2 Y_new=279 (ΔY=116) - různé hodnoty na různých Z pozicích potvrzují, že tvar podběhu NENÍ podél stěny konstantní - Y_new se musí zjišťovat PER NOHA, ne jednou pro celé auto.

**Nový nález - podlaha lůžka není jen max() z Y_new obou noh sloupce:** viz `KAROSERIE_UMISTENI.md` sekce "Karoserie CI25..." a `shape_geometry_methods.id=6` (`DULEZITA_OPRAVA_METODY_2026_08_31_rail_floor`) - nosník+spojnice sloupce mezi nohou1/nohou2 kolidovaly s karoserií i při floor=max(214,279)=279, skutečná bezpečná podlaha vyšla 318mm po dalším kolizním krokování PŘÍMO na nosníku/spojnicích (ne jen v bodech noh).

**Volba výškové varianty pro "maximum euroboxů" — RETRAKCE dřívější "vždy nejmenší dostupná výška" úvahy (Robert, 2026-08-31):** první verze téhle sekce tvrdila, že "režie na patro roste s H_box, tedy nejmenší dostupná výška na každém patře vždy maximalizuje počet" a na základě toho postavila `id=51` s 3+3 patry, VŠE 120mm. Robert po prohlédnutí ve scéně: *"nohy výborně, skladba boxů nic moc, šlo aplikovat vyšší boxy někde a 1.sloupec od prepazky šla aplikovat i další lůžka."* Matematika o rostoucí režii na patro zůstává platná (viz vzorec níže), ale ZÁVĚR "tedy vždy jen nejmenší výška" byl chybný ze dvou důvodů:
1. **Strop použitý pro výpočet počtu pater byl špatný.** Použité `box-top<=890mm` (odvozeno ze "spojnice-horní") bylo příliš PŘÍSNÉ na jednom místě (viz further nález o joint-containment stropu 920/905mm) A ZÁROVEŇ příliš VOLNÉ na jiném (viz bod 2 níže) — číslo bylo prostě špatně odvozené, ne "konzervativní ale bezpečné". Se správně ověřeným stropem měl sloupec 1 (u přepážky) prostor pro **4. patro**, ne jen 3 — přesně to, co Robert postrádal.
2. **"Maximalizovat počet" NENÍ totéž jako "ignorovat diverzitu"** — i při cíli "maximum boxů" zůstává v platnosti obecná preference diverzifikace (`shape_geometry_methods.id=3.diverzifikace_napric_sloupci_2026_08_31`) a Robertův explicitní požadavek na použití vyšších variant "někde". Řešení není "vždy jen 120mm", ale volba kombinace, která reálně využije dostupný prostor A obsahuje výškovou variaci — viz 3 varianty níže.

**Nový nález — box-top strop NENÍ jen joint-containment na nosníku, je to SAMOSTATNÁ fyzická hranice (zapsáno do `shape_geometry_methods.id=6`, `DULEZITA_OPRAVA_METODY_2026_08_31_box_top_strop`, version 5→6):** eurobox je široký přes CELOU hloubku D (na rozdíl od tenkého 30mm nohového profilu) a může narazit na skutečné zaklonění boku karoserie směrem ke střeše NEZÁVISLE na tom, kde má nosník svůj joint-containment limit (920/905mm). Fresh 1mm kolizní krokování širokého sondovacího objektu (ne tenkého nohového profilu) přes celou délku obou sloupců našlo skutečný strop **Y≈923–924mm** — prakticky identický pro oba sloupce (na rozdíl od floor/Y_new, který se lišil sloupec od sloupce) — tedy tenhle konkrétní strop JE podél stěny rovnoměrný, floor NENÍ. Reálný box na nominálním box-top=1008mm (naivní 4. patro se vším 120mm a floor=318 u sloupce 2) SKUTEČNĚ KOLIDOVAL s karoserií — ověřeno přímo na reálné eurobox mesh geometrii přes `collidesWithWalls`, ne teoreticky.

**Sloupec 1 floor explicitně znovu ověřen (Robert požádal o potvrzení, že to nebylo přehlédnuto):** stejný test jako u sloupce 2 (nosník+spojnice přes celé rozpětí sloupce, ne jen v bodě nohy) proveden i na sloupci 1 (floor kandidát 214mm, `railYCenter=229`) — **žádná kolize**, floor sloupce 1 zůstává 214mm beze změny.

**S opraveným stropem (~923-924mm) sloupec 1 (floor=214) unese až 4 patra, sloupec 2 (floor=318) zůstává na 3 patrech** (na 4. patro by zbylo jen ~48mm, méně než nejnižší dostupný box). Připraveny a REÁLNĚ ověřeny (kolize s karoserií VČETNĚ euroboxů, self-kolize) 3 varianty skladby — Robert řekl "žádnou kombinaci nechci ukládat, jen se učíme" (2026-08-31), takže ŽÁDNÁ z nich není v `product_assemblies` — jde čistě o srovnávací návrh:

| Varianta | Sloupec 1 (3box, odspoda) | Sloupec 2 (1box, odspoda) | Celkem boxů | Poznámka |
|---|---|---|---|---|
| **A — max. počet** | 120·120·120·120 (4 patra) | 120·120·120 (3 patra) | **15** | žádná diverzita |
| **B — max. diverzita** | 220·170·120 (3 patra) | 170·120·120 (3 patra) | **12** | plný gradient výšek v obou sloupcích, přesně co Robert postrádal |
| **C — vyváženo** | 120·120·120·120 (4 patra) | 220·120·120 (3 patra) | **15** | sloupec 1 (širší) na počet, sloupec 2 (užší) diverzifikován |

Všechny 3 varianty ověřeny: 0 kolizí s karoserií CI25 (test zahrnuje i samotné euroboxy, ne jen nohy/nosníky — nutné kvůli nálezu o box-top stropu výše), 0 neočekávaných self-kolizí. Srovnávací 2D náčrt (elevace všech 3 variant vedle sebe): https://claude.ai/code/artifact/859e77be-715e-4e41-9ceb-299106a4c89f

**Stav `product_assemblies.id=51`:** ponechán BEZE ZMĚNY na žádost Roberta (viz výše) — obsahuje původní, dnes už known-suboptimální skladbu 3+3 patra × 120mm (12 boxů), NE žádnou z výše uvedených korigovaných variant. Až Robert vybere/potvrdí variantu, uloží se jako nová řádka (nebo přepíše `id=51`) na jeho výslovný pokyn — momentálně žádná uložená sestava CI25 nereflektuje opravenou skladbu.

**Výsledek (historicky, `id=51`, NEAKTUÁLNÍ skladba boxů — ponecháno jako je):** 3 nohy, 2 sloupce, oba 3 patra × 120mm = 12 euroboxů celkem, rozměry 326×1183×1752mm (hloubka×výška×délka), 73 dílů celkem. Původní 2D výkres (odpovídá aktuálnímu stavu `id=51`): https://claude.ai/code/artifact/95adc5f4-b8e3-4e63-9483-b929e5edbc75

## Regál na euroboxy — Movano L2H1 (OP28) — POKUS ZAMÍTNUT, NEULOŽEN (2026-08-31)

**Stav: Robert označil výsledek jako špatný ("movano špatně" → "ale regál mel být přes podběh až dozadu" - regál se u podběhu zastavil, místo aby ho výřezovou nohou obešel a pokračoval dál ke skutečné zadní hranici vozu), poté řekl "movano neopravovat" a "movano neukládat".** `product_assemblies.id=52` a `shop_products.id=3801` byly SMAZÁNY, oprava se NEPROVÁDÍ. Sekce níže je ponechána jen kvůli jednomu obecně platnému nálezu (izolovaný podběh, viz níže) - CELKOVÝ PŮDORYS/ROZSAH SESTAVY (jen 1 sloupec, zastavení u podběhu) je PŘÍKLAD ŠPATNÉHO ŘEŠENÍ, ne vzor k použití.

Robert: "aplikujme regály na euroboxy z profilů 30 do Movano L2H1 levá stěna, boxy musí být pouzity vsechny velikosti z výšek 120, 170, 270." První aplikace metod na JINOU značku vozidla než Citroën Jumpy - Opel/Vauxhall/Renault Movano L2H1, DB model `OP28` (`car_bodies` 639/640/641).

**Orientace:** karoserie NENÍ otočená (stejná nativní konvence jako Jumpy CI24/CI25), ověřeno strukturálně na tvaru 3 stěn. Přepážka "B": X∈[-945,945] (celá šířka), Z∈[2750,2986] (úzký plátek na horní Z hranici). Levá stěna "L": X∈[0,945], Z∈[-145,2986].

**Přední noha (plain):** anchorZ=2728, offsetX=607, offsetY=2.

**Nový typ nálezu - podběh jako IZOLOVANÝ OSTROV** (zapsáno i do `car_body_placement_methods.id=1`, klíč `clenita_noha.podbeh_muze_byt_izolovany_ostrov_2026_08_31`, `version` 7→8): na rozdíl od Jumpy, kde podběh sahá souvisle až k zadní hranici vozu, u Movana je podběh izolovaný na úseku Z≈[285,1085] - PŘED i ZA ním je volná rovná podlaha. Druhá noha (anchorZ=1466) leží 381mm PŘED podběhem, a je tedy správně typu **plain, ne vyrez** - typ nohy se musí určovat podle toho, jestli KONKRÉTNÍ Z pozice té nohy skutečně překrývá zónu podběhu, ne podle pořadí ("první noha=plain, zbytek=vyrez" NEPLATÍ obecně). Diagnostický signál chybného typu: vyrez-noha na místě bez reálného podběhu dá nesmyslně malé Y_new (~20mm) a geometricky zaručenou self-kolizi (spojnice-dolní vs příčka-uzavření-výřezu).

**Sloupce:** jen **1 sloupec** (3box, 1232mm) mezi oběma (plain) nohami. Druhý sloupec by musel přemostit celý podběh a narazil by na kolizi bez ohledu na šířku - za podběhem zbývá jen ~260mm, málo i na 1box (430mm).

**Kontrola podlahy nosníku přes celý rozpon** (dle nově zavedeného povinného kroku, `shape_geometry_methods.id=6` verze 5): explicitně ověřeno - sloupec leží celý mimo zónu podběhu, floor=0mm prošel bez kolize, žádné další kolizní krokování nebylo potřeba.

**Vertikální patra, povinně všechny 3 výšky (120/170/270mm):** floor=0, strop (box-top) ≤890mm. Odspoda nahoru: 270mm (box-top 300) → 170mm (530) → 120mm (710) → 120mm (890, přesně na stropu). 4 patra, obsahuje všechny 3 povinné výšky, matematicky maximální počet pater při splnění požadavku na diverzitu.

**Výsledek (NEPOUŽITELNÝ - regál se měl táhnout přes podběh dál k zádi, ne se u něj zastavit):** 2 nohy (obě plain), jen 1 sloupec, 4 patra × 3 boxy = 12 euroboxů. Geometricky bez kolize, ale ROZSAHOVĚ špatné řešení - `product_assemblies.id=52`/`shop_products.id=3801` smazány, artifact ponechán jen jako doklad chyby (ne jako vzor): https://claude.ai/code/artifact/b23be32d-291b-43c3-9c70-8195c3e52e6b

## Jumpy L2 CI25 — 3 varianty uloženy do scény na výslovnou žádost (2026-08-31)

Po vizuálním srovnání 3 variant skladby boxů (viz sekce výše) Robert: "L2 ABC chci videt ve scene" - výslovné svolení k uložení (viz `WORKFLOW.md` bod 23 - jinak se prozkoumávané varianty neukládají). Uloženy všechny 3 jako samostatné `product_assemblies` řádky, krátké názvy dle konvence (`Karoserie - boxy43-H1xN1-...`):

- **`id=53`** `Jumpy L2 CI25 - boxy43-120x15` (varianta A, max počet)
- **`id=54`** `Jumpy L2 CI25 - boxy43-220x3-170x4-120x5` (varianta B, max diverzita)
- **`id=55`** `Jumpy L2 CI25 - boxy43-220x1-120x14` (varianta C, vyvážená)

**Důležitá výhrada zapsaná i do `_note` každé sestavy:** orientace karoserie CI25 (potřeba 180° flipu?) je předmětem samostatně běžícího auditu všech karoserií (viz `KAROSERIE_UMISTENI.md`) - tyhle 3 sestavy byly uloženy v AKTUÁLNÍ (zatím neotočené) orientaci CI25. Pokud audit potvrdí, že CI25 flip potřebuje, geometrie všech tří variant se bude muset přepočítat stejnou transformací jako ostatní dotčené sestavy.

## PILOT: Regál na euroboxy — Vivaro OP18 (bot16, 2026-08-31) — nohy 40→30, ≥3 výšky, stavba přes podběh k reálné zádi, box smí přesahovat zadní profil nohy

**Shrnutí:** Robert zadal 2 NOVÁ pravidla naráz (nohy 40→30 na všech "malých" autech s nohou 40 připravenou, box smí přesahovat zadní profil členité nohy nahoře, i když lůžko nemůže) a požádal o PILOT na jednom autě (Vivaro OP18) před aplikací na 11 dalších. Výsledek: `product_assemblies.id=57` ("Vivaro OP18 - boxy43-270x2-220x2-120x12"), `shop_products.id=3806`, `active=0`. 3 nohy, 2 sloupce, 16 euroboxů (3 různé výšky: 120/220/270mm), bez kolize s karoserií, bez neočekávané self-kolize. Karoserie Vivaro OP18 MUSELA být fyzicky otočena o 180° (stejná vada jako 273/304 modelů v katalogu). Artefakt (2D půdorys+nárys + shrnutí nálezů): https://claude.ai/code/artifact/80886bb6-a9d5-4448-9fc6-4b3fa084020c

### Postup jako reprodukovatelný recept (pro dalších 11 vozidel)

**Krok 1 — převod nohy 40×40 → 30×30** (`shape_geometry_methods.id=1`): `custom_shapes.id=516` (plná) / `517` (výřezová) načteny, zjištěno, že jejich `data` JSON je BYTE-IDENTICKÝ s Jumpy CI14 `503`/`504` (stejný leg design "H1.1180.349" sdílený mezi modely). Protože vzorec převodu závisí jen na `T` a fixních rozměrech `W=349/H=1180/CAP_H=260/CUTOUT_H=395/uskok=225` (identické), výsledná 30×30 geometrie vyšla numericky identická s Jumpy `526`/`527` — **znovu nezávisle ověřeno** přes `touchReport` na reálné `Object_7.glb` geometrii (`scripts/tmp_2026-08-30_build_leg_30x30.js`, všechny spoje `gap=0/overlap=0` flush, "VSE OK: true"), ne jen převzato bez ověření. Uloženo jako nové `custom_shapes.id=528` (plná) / `529` (výřezová). **Poučení pro dalších 11 aut:** pokud dvě karoserie sdílejí stejný vstupní 40×40 leg design, převod stačí spočítat jednou, ALE ověření (touchReport) se přesto musí spustit znovu na cílovém shape ID — nepředpokládat shodu bez kontroly.

**Krok 2 — orientace karoserie** (`car_body_placement_methods.id=1`, kritérium `zMidB` z `KAROSERIE_UMISTENI.md`): Vivaro OP18 (`car_bodies` 642 L / 643 R_D / 644 B) změřeno nezávisle (`scripts/2026-08-31_glb_position_bbox.js`) — B wall `Z∈[2374.5,2911.96]`, `zMidB=+2643.2` (kladné) → **NEEDS_FLIP**, potvrzeno i nezávislým auditem katalogu (`Opel_Vivaro_OP18_2019-` je v seznamu 273/304 vadných modelů). Fyzicky otočeno (`(x,y,z)→(-x,y,-z)` na POSITION+NORMAL, binární patch, beze změny velikosti souboru) — zálohy originálů `backups/2026-08-31_car_body_vivaro_op18_pre_180_flip/`. Po opravě: B wall `Z∈[-2911.96,-2374.52]`, `zMidB=-2643.2` (záporné) → OK, stejný vzor jako opravená CI14. Stěna L po opravě `X∈[-807,0]` (záporná strana X).

**Krok 3 — KRITICKÁ past objevená v tomto pilotu: zrcadlení osy X pro stěnu na záporné straně.** Existující stavební kód pro nohy (`buildPlainAtDepth`/`buildVyrezAtDepth` + `worldX = offsetX + localX`) byl vyvinutý a ověřený na karoseriích se stěnou L na KLADNÉ straně X (CI24, CI25, Movano — všechny NEotočené). Po 180° flipu (Vivaro, stejně jako CI14/opravená CI25) je stěna L na ZÁPORNÉ straně X — se stejnou konvencí `+` vyjde role dílu OBRÁCENĚ: část určená jako "u stěny" (zadní svislice/cap/zúžený sloupek před podběhem) skončí FYZICKY DÁL od stěny než "přední svislice" (má být daleko, plná výška bez výřezu) — protože `offsetX+localX` je rostoucí zobrazení nezávislé na tom, kde reálně leží stěna. **Detekční signál:** plná i výřezová noha kolidují IDENTICKY na stejném Z (výřez nepřináší žádnou výhodu), protože zúžený sloupek skončil na ŠPATNÉ (vzdálené) straně, ne tam, kde je skutečný podběh. **Diagnostika:** nízká sonda (výška 0..CUTOUT_H) po celém `local-X∈[0,D]` odhalí, na které straně skutečně dochází ke kolizi s podběhem. **Oprava:** `worldX = offsetX − localX` (mirror) — aplikováno VŠUDE, kde se `localX` používá pro pozici (nohy, nosníky, spojnice, centrování euroboxu), ne jen v jedné funkci. Po opravě: `offsetX` se změnilo z (chybných) −688 na (správných) −425 a výřezová noha už skutečně čistí reálný podběh. **Tohle je nejdůležitější nález celého pilota — týká se KAŽDÉ z dalších 11 karoserií, která po 180° flipu skončí se stěnou L na záporné straně X** (což je typický důsledek flipu vozidel, která měla L původně na kladné straně — prakticky všech 273 nahlášených modelů). Před stavbou na dalším autě VŽDY nejdřív zjisti `sign` strany stěny L a podle toho zvol `+` nebo `−` konvenci — nikdy nekopírovat kód beze změny jen proto, že fungoval na předchozím (neotočeném) autě.

**Krok 4 — kolizní krokování + podběh jako dlouhý souvislý úsek, pokračování přes něj (`car_body_placement_methods.id=1`, `shape_geometry_methods.id=5`):** noha 0 (plain, u přepážky) `anchorZ=-2373` (`offsetX=-425, offsetY=2`). Diagnostický sken (`scripts/tmp_2026-08-31_vivaro_scan_wall.js`) odhalil, že podběh Vivara je DLOUHÝ souvislý úsek (~1190mm) — plná noha koliduje od `anchorZ≈-1223` dál (směrem k otevřenému konci), výřezová noha projede až po `anchorZ≈-33`. `max_rozpon_nohou`: kolize nalezena při `anchorZ=-35`, 20mm zpět → `REAR_ANCHOR_Z=-55` (maxSpan=2318mm od přepážky). Sloupcové plnění (hladově nejširší-nejdřív): **sloupec 0** (N=3, 1232mm) mezi nohou 0 (plain) a nohou 1 (vyrez, `anchorZ=-1111` — HLUBOKO uvnitř zóny podběhu); **sloupec 1** (N=2, 832mm) mezi nohou 1 a nohou 2 (vyrez, `anchorZ=-249` — také v zóně podběhu). Za nohou 2 zbývá jen 164mm do `REAR_ANCHOR_Z` — nestačí ani na nejmenší (1box, 430mm) sloupec. **Potvrzuje obecnost Movano poučení "nezastavovat se u podběhu"** — kdyby se plnění zastavilo u první kolize plné nohy, sestava by měla jen 1 nohu/0 sloupců místo 3 noh/2 sloupců.

**Krok 5 — protažení výřezových noh + rail-floor přes celý rozpon (`shape_geometry_methods.id=6`):** noha 1 `Y_new=213mm` (`ΔY=182`), noha 2 `Y_new=139mm` (`ΔY=256`) — opět nejednotné podél stěny (stejný vzor jako CI25: 214/279). Rail-floor kontrola přes celý rozpon sloupce: sloupec 0 floor=213 (leg-based kandidát prošel bez kolize), sloupec 1 floor=213→**318** po fresh krokování (leg-based kandidát KOLIDOVAL na nosníku/spojnicích přes celý rozpon, potvrzuje znovu CI25 nález, že floor sloupce může být vyšší než `max(Y_new)` obou krajních noh).

**Krok 6 — výšková variabilita, ≥3 velikosti (`shape_geometry_methods.id=3`):** fyzický strop (nová kontrola, viz krok 7) sloupec 0 = 922mm, sloupec 1 = 924mm. Zvoleno: sloupec 0 = 4 patra × 120mm (12 boxů, topBox=903mm), sloupec 1 = 270mm + 220mm (4 boxy, topBox=898mm). Celkem **3 různé výšky použité v celé sestavě (120/220/270)** — splňuje "minimálně 3 velikosti v autě", diverzifikováno napříč sloupci (sloupec 0 uniformní pro maximální počet, sloupec 1 diverzifikovaný).

**Krok 7 — NOVÉ pravidlo: box smí přesahovat zadní profil členité nohy (lůžko nesmí)** (nový klíč `shape_geometry_methods.id=3.box_muze_presahovat_zadni_profil_2026_08_31`): Robertovo zadání doslovně "box samotný může zadní profil členité nohy přesahovat (lůžko nemůže dle pravidel)". **Co zůstává beze změny:** RAIL/LŮŽKO (nosníky+spojnice) je omezeno existujícím pravidlem `limit_maximalni_vysky_patra` — `railYCenter ≤ TOP_Y−T/2` (905mm u naší nohy, `TOP_Y=H−CAP_H=920mm`), pro KAŽDÉ patro včetně posledního. **Co je NOVÉ:** eurobox v NEJVYŠŠÍM patře smí svým vlastním horním povrchem přesáhnout `TOP_Y=920mm`, až do SKUTEČNÉHO fyzického stropu (kolize s karoserií/střechou), protože box není strukturálně podepřen shora (jen zdola, sedí na rail top) — přesah nad místo, kde profil nohy strukturálně končí, je fyzicky bezpečný, pokud nekoliduje se skutečnou geometrií. **Přesný postup ověření:** (1) fresh 1mm kolizní krokování (2mm zpět) ŠIROKÉ sondy (celá hloubka `D` sloupce, ne tenký 30mm nohový profil) proti reálné karoserii, pro každý sloupec zvlášť (`scripts/tmp_2026-08-31_vivaro_step7_ceiling.js`) → fyzický strop; (2) ověřit i SKUTEČNOU hotovou eurobox GLB geometrii (ne jen syntetickou sondu) proti karoserii přes `collidesWithWalls` — v tomhle pilotu provedeno explicitně na všech 16 eurobxech samostatně; (3) zkontrolovat, že box nekoliduje s "cap" dílem nohy — v praxi bezproblémové, protože cap existuje jen v tenkém Z-slabu na pozici KAŽDÉ nohy, zatímco box stojí v Z-mezeře MEZI nohama (různý Z rozsah, nepotkají se), ale ověřit numericky, ne předpokládat.

**Poctivý (nikoliv "vylepšený") výsledek pro Vivaro:** fyzický strop vyšel jen 922/924mm — pouze 2-4mm nad starým `TOP_Y=920mm` limitem (bok/střecha karoserie se u Vivara začíná zaklánět těsně nad 920mm, což dává smysl — `CAP_H=260` byl už v původním designu nohy zjevně navržen tak, aby noha sama dosahovala blízko skutečného stropu). Při hrubosti dostupné diskrétní sady výšek boxů (120/170/220/270, kroky ~50mm) **žádná dosažitelná kombinace nespadla do tohoto úzkého 2-4mm okna** — nejlepší nalezené kombinace (topBox=903mm a 898mm) vyhovují i staré, konzervativnější hranici 920mm. Mechanismus byl správně implementován a numericky ověřený (exhaustivní prohledání všech nerostoucích kombinací výšek potvrdilo, že žádná legitimní kombinace neleží v pásmu (905,922]/(905,924]), ale u TÉTO karoserie se numericky neprojevil. **Negeneralizovat "2-4mm" jako univerzální číslo** — u jiné karoserie s větší rezervou střechy nad úrovní 920mm může být zisk výrazně větší (a u jiné, s menší rezervou, prakticky nulový nebo dokonce záporný, což by ukázalo, že i STARÁ 920mm hranice byla dřív příliš optimistická a měla by se také ověřovat kolizně, ne jen vzorcem).

**Sumarizace čísel:** karoserie Vivaro OP18 (642/643/644, otočena o 180°), noha 30×30 (H=1180, W=349→D=326 přestavěno na hloubku pro euroboxy podélně), 3 nohy (0 plain @ Z=-2373, 1 vyrez @ Z=-1111, 2 vyrez @ Z=-249, vše ve finálním/otočeném rámci), 2 sloupce (3box 1232mm + 2box 832mm), 16 euroboxů (12×120mm + 2×220mm + 2×270mm), celkové rozměry 326×2154×1183mm (šířka×délka×výška), 81 dílů celkem v `product_assemblies.data.parts` (vč. 3 car_body referencí). Ověřeno: bez kolize s karoserií (profily i euroboxy samostatně), bez neočekávané self-kolize (73 očekávaných zanoření eurobox/záslepka do profilu, 0 neočekávaných, 78 vlastních dílů sestavy).

**Skripty (pro reprodukci na dalších 11 vozidlech):** `scripts/tmp_2026-08-31_place_vivaro.js` (kolizní modul, šablona pro další auta — jen přepsat cesty ke GLB), `scripts/tmp_2026-08-31_vivaro_step1_bulkhead_floor_wall.js` … `_step7_ceiling.js` (kroky metody), `scripts/tmp_2026-08-31_vivaro_diag_arch.js`/`_diag_arch2.js`/`_scan_wall.js` (diagnostika mirror-X pasti a tvaru podběhu), `scripts/tmp_2026-08-31_vivaro_plan_levels.js` (návrh pater vč. exhaustivního hledání demo-případu přesahu), `scripts/tmp_2026-08-31_vivaro_build_full.js` (finální sestavení + kontroly), `scripts/tmp_2026-08-31_vivaro_insert_rack.py` (DB insert), `scripts/tmp_2026-08-31_vivaro_gen_svg_data.js` (2D data pro artefakt).

## Batch: Peugeot Expert (11 variant) + Mercedes Vito (7 variant), levá stěna (bot16, 2026-09-01)

Navazuje na Vivaro OP18 pilot výše. Stejný recept aplikován na `car_bodies`: Peugeot Expert PE12/13/14 (2007-2015), PE15/16/17/20/21 (2016-), PE25/26/27 (e-Expert 2021-); Mercedes Vito MB17/18/19/24 (Compact/Long/Extra Long/Mixto Long) a MB25/46/47.

- Všech 18 karoserií potřebovalo 180° flip (audit `NEEDS_FLIP`) - fyzicky provedeno, MIRROR_X (`worldX=offsetX-localX`) ověřen nezávisle na každé z 18 (ne převzat).
- Noha 30x30: Expert sdílí identický design s Jumpy/Vivaro (`custom_shapes.id=508/509` byte-identické s `503/504`/`516/517`) → přímo zkopírována ověřená 30x30 verze jako `id=530/531`. Vito má vlastní rozměry (H=1200, CAP_H=300, CUTOUT_H=350, uskok=175, cap_offset=79mm) → nová geometrie `id=532/533`, ověřena touchReportem.
- Door-height (Expert 1220mm, Vito 1261mm, web zdroj, zapsáno do `karoserie_model_reference`) nikdy limitující (nohy 1180/1200mm < obě kóty) - zkrácení nohy nikde nebylo potřeba.
- 12/18 variant: 2 sloupce. 6/18 (kratší PE15/PE20/PE21/PE25, Vito MB24/MB25): 1 sloupec (platné dle "jeden sloupec stačí u menších variant"). Žádná "nic se nevejde".
- Protažení vyrezové nohy (`shape_geometry_methods.id=6`) počítáno fresh na KAŽDÉ noze zvlášť - zisky se liší i v rámci téhož vozidla (např. e-Expert L3: noha1 Y_new=213mm, noha2 Y_new=139mm).
- Výšky: 2sloupcové varianty použily 3-4 z {120,170,220,270}mm, 1sloupcové jen 2 (fyzický strop kratší nohy to jinak nedovolí).
- Celkem uloženo `product_assemblies.id=66-83` (`shop_products.id=3815-3832`, `active=0`, `is_public=1`), naming `<Karoserie krátce> - boxy43-<H>x<N>-...`. 2D verifikační artefakt (všech 18, plán+nárys, mm mřížka): https://claude.ai/code/artifact/c93aa99f-867c-4bf4-9637-0c5b926b8d2b

Detail (přesná čísla, rozsah zjednodušení oproti Vivaro pilotu) v `AGENTS_LOG.md`, bot16 2026-09-01.

## ProAce rodina (bot16, 2026-08-31) — 19 karoserií, generalizovaný pipeline, 15/19 sestav

Navazuje na Vivaro OP18 pilot výše, ale místo 19 samostatných skriptů psaný jako 6 znovupoužitelných modulů (`scripts/2026-08-31_proace_*.js/py`), parametrizovaných D/H/T/CUTOUT_H per vehicle. Noha 30x30: `custom_shapes.id=506/507` (D=349, H=1180, T=40 před převodem) — rozebráno přímo z uložených dat, přesně odpovídá `buildPlainAtDepth`/`buildVyrezAtDepth` vzorcům (žádný samostatný "převodní krok" nebyl potřeba).

**Nový bug nalezený a opravený** (`proace_leg_builder.js::buildVyrezAtDepthExtended`): když skutečný `Y_new` (fresh kolizní krokování, rule id=6) vyjde MALÝ (≤T=30mm — reálný podběh zasahuje skoro k podlaze), dosavadní "spojnice-dolni" (fixní pozice odvozená z nominálního `CUTOUT_H`, nezávislá na `Y_new`) a repozicovaná "pricka-uzavreni-vyrezu" (na `Y_new+T/2`) se vertikálně SRAZÍ — objeveno na všech 7 Proace Max variantách (`unexpected self-collision`). Oprava: při `Y_new <= T` se oba dva díly úplně vynechají (degenerate case, protažená `zadni-svislice-nad-zarezem` už sama pokrývá skoro celou výšku). **Relevantní pro každou budoucí kartu s velmi nízkým podběhem, ne jen ProAce.**

**Skupina A (mid-size Compact/Medium/Long/CrewCab, TO07/08/09/12/17/21/22/23), H=1180 beze změny** (< známá výška zadních dveří 1220mm) — všech 8 dostalo sestavu (`product_assemblies.id=58-65`). TO07: jen 2 distinct výšky (270+220) místo min. 3 — spočítáno explicitně: dostupný budget 611mm, 3 nejmenší výšky (120+170+220) + rámy + mezery = 660mm > 611mm, fyzicky nejde (pravidlo min. 3 výšky je zde neaplikovatelné, ne porušené).

**Skupina B (Proace City, TO10/TO11/TO19/TO20) — VŠECHNY 4 "no fit"**, ne z lenosti: kolize začíná ve STEJNÉM Z bodě (~950mm od přepážky) nezávisle na hloubce nohy D (testováno 349/300/250/200/150mm), a "vyrez" tvar nepomáhá o nic víc než "plain" — jde o strukturální zúžení PO CELÉ VÝŠCE nohy blízko zadních dveří, ne o lokální podběh řešitelný stávajícím výřezem (`WALL_CLEARANCE_ARCH=124mm`/`CUTOUT_H=395mm`). Zbývá jen ~411mm od přepážky, nestačí ani na nejmenší 1-box sloupec (potřeba 460mm). **Potřeba bespoke užší/mělčí noha specificky navržená pro tuhle menší karoserii — mimo rozsah téhle session, zapsáno jako TODO v `AGENTS_LOG.md`.**

**Skupina C (Proace Max, TO14/15/16/18/24/25/26), H=1180 beze změny** (výška dveří NULL v `karoserie_model_reference` — rule 2 dle zadání "NULL se nekontroluje") — po opravě výše uvedeného bugu všech 7 postaveno bez kolize (`product_assemblies.id=84-90`).

Celkem uloženo `product_assemblies.id=58-65,84-90` (15 sestav, `shop_products` `active=0`, `is_public=1`), naming `<Karoserie krátce> - boxy43-<výšky>`. 2D SVG verifikace (Box3 půdorys+nárys, rule 8) vygenerována pro všech 15 před insertem. Detail v `AGENTS_LOG.md`, bot16 2026-08-31.

## Batch: Citroën Berlingo (6 variant) + Peugeot Partner (6 variant) + Renault Trafic (2 variant), levá stěna (bot16, 2026-08-31)

Stejný recept jako Vivaro/Expert+Vito/ProAce výše, `car_bodies`: Berlingo CI03/CI04 (2008-2018), CI16/CI17 (L1/L2, 19-), CI22/CI23 (ë-Berlingo L1/L2); Partner PE02/PE03 (2008-2018), PE18/PE19 (L1/L2, 19-), PE23/PE24 (e-Partner L1/L2); Trafic Van E-Tech RE28/RE29 (L1/L2 - jediné Trafic varianty v katalogu, žádná neelektrická nenalezena).

- Všech 14 karoserií potřebovalo 180° flip (audit `NEEDS_FLIP`, živě ověřeno na 3 vzorcích CI16/PE18/RE28 před hromadnou aplikací) - `scripts/tmp_2026-08-31_flip_bpt_180.js`, zálohy `backups/2026-08-31_car_body_berlingo_partner_trafic_180_flip/`. MIRROR_X (`worldX=offsetX-localX`) použit od začátku.
- **Berlingo/Partner OVĚŘENO bez významného podběhu** (Robert to čekal, ale ověřeno reálným A/B kolizním testem, ne převzato): plný profil (celá výška H) vs. jen horní část (Y>400mm) dávají IDENTICKOU zadní hranici (`diff=0mm`) na CI03/CI16/PE02 - potvrzeno na obou generacích obou značek. Použit `plain` profil po celé délce, žádná `vyrez` varianta uložena jako potřebná.
- **Trafic MÁ nízký podběh/výstupek na RE28** (L1): stejný A/B test dal `diff=929mm` (plný profil koliduje už ~1007mm od předního rohu, jen-horní část dojede skoro až k otevřenému konci) - potvrzuje, že Trafic (na rozdíl od Berlingo/Partner) skutečně má nízkou překážku (pravděpodobně vyvýšení podlahy pro baterii u E-Tech elektromobilu). `WALL_CLEARANCE_ARCH=70mm` určeno vlastním kolizním skenem (50mm už stačilo, 70mm použito s rezervou) - NEPŘEVZATO z Jumpy/Vivaro (124mm). V praxi ale u RE28 i RE29 vyšel jediný sloupec CELÝ před zónou podběhu (první další noha ~1217mm od předního rohu, podběh začíná ~1007mm) - všechny uložené nohy tedy vyšly typem `plain`; `vyrez` builder zůstává připravený (`tmp_2026-08-31_bpt_leg_builder.js::buildVyrezAtDepth`, se stejnou opravou "pricka-uzavreni-vyrezu" jako Jumpy/Vivaro) pro budoucí sestavu s delším rozpětím.
- **RE29 (L2) zvláštnost**: kolizní krokování stěny u předního rohu skončilo na `offsetX=+805` (kladná strana X), zatímco RE28 skončilo na `offsetX=-325` (záporná strana) - ověřeno, že to NENÍ chyba stranovosti/MIRROR_X (prázdný prostor bez kolize existuje od -325 do +600 na dané Z) - jde o reálnou geometrii "L" GLB u RE29, které obsahuje strukturu (pravděpodobně B-sloupek/kolejnice posuvných dveří specifická pro delší variantu) zasahující blíž ke středu vozu těsně u přepážky. Sestava je tím pádem posazená blíž ke středu vozu než u RE28 - platná, bezkolizní pozice, ale méně hluboko využitý prostor u samotné přepážky. Zapsáno jako otevřený bod ke zlepšení (jemnější/užší sonda schopná "objet" izolovaný sloupek by mohla najít hlubší pozici).
- Noha 30x30: **žádný z existujících custom_shapes (492 Berlingo/505 Partner/510+511 Trafic) neměl "cap" díl ani horní příčník** (jednodušší topologie než Jumpy/Vivaro/Expert/ProAce - jen 2 plnovýškové svislice + spodní příčník u podlahy, "U" tvar otevřený nahoru). Převod 40x40→30x30 (`shape_geometry_methods.id=1`) zachoval tuto topologii 1:1. Nové 30x30 tvary: `custom_shapes.id=539` ("Noha.1.Berlingo-Partner.H1.1080.349.30x30", sdílená Berlingo+Partner - obě karoserie mají byte-shodné B/L/R_D bounding boxy, ověřeno) a `id=540` ("Noha.1.Trafic.H1.1250.349.30x30"). `touchOk` ověřeno (T-styl spoj svislice/příčník: gap=0 na jedné ose, plný přesah na zbylých dvou).
- **Door-height check (pravidlo 2)**: `karoserie_model_reference.official_door_opening_height_mm` vyplněno JEN pro CI16/17/22/23 (1137mm) - noha 1080mm < 1137mm, žádné zkrácení. Pro CI03/CI04/PE02/03/18/19/23/24 chybí oficiální kóta - použit `cargo_height_mm` (1200-1270mm dle varianty) jako konzervativní proxy, vždy > 1080mm, žádné zkrácení. **Pro RE28/RE29 chybí OBOJÍ** (`official_door_opening_height_mm` i `cargo_height_mm` NULL) - zapsáno jako mezera v datech, leg H=1250mm použito beze změny (opřeno o to, že reálná kolize s karoserií po celém profilu prošla, což nepřímo potvrzuje že se noha do interiéru vejde, ale nepotvrzuje konkrétně výšku zadního otvoru dveří) - doporučeno doplnit oficiální kótu při příští příležitosti.
- Všech 14 vyšlo **1 sloupec** (D=349mm noha je vzhledem k rozměrům těchto malých/středních dodávek relativně hluboká - i L2 varianty měly po 1. sloupci už jen 350-400mm volného místa, pod limitem i pro nejužší 1-box sloupec 460mm). Žádná "nic se nevejde" - všech 14 dostalo reálnou funkční sestavu.
- Výškový plán (pravidlo 6, cyklus 270→220→170→120 sestupně, opakuj nejmenší, s bonusovým navýšením posledního patra pokud se vejde pod fyzický strop): Berlingo/Partner staré (CI03/04, PE02/03) 4 patra (270,220,170,170) = 8ks; Berlingo/Partner nové L1/L2 (CI16/17/22/23, PE18/19/23/24) 4 patra (270,220,170,170) = 12ks (širší sloupec N=3); Trafic RE28 5 pater (270,220,170,120,120) = 10ks; Trafic RE29 (jen N=1 sloupec) 5 pater (270,220,170,120,120) = 5ks. Všechny ≥3 distinct výšky.
- 2D kontrolní měření (pravidlo 8, skutečný `Box3` ze GLB, `scripts/tmp_2026-08-31_bpt_verify2d.js`): 0 chyb na všech 14 (žádné NaN/degenerované boxy, všechny svislice na podlaze, eurobox výšky 100-300mm rozumné, celkové rozměry v mezích).
- Uloženo `product_assemblies.id=91-104` (`shop_products.id=3840-3853`, `active=0`, `is_public=1`), naming `<Karoserie krátce> - boxy43-<H>x<N>-...`. Mapování id→karoserie a přesná čísla (`step1`/`step2`/sloupce) viz `AGENTS_LOG.md`, bot16 2026-08-31.

## Batch: Ford Custom/Transit Custom (11/13) + VW Transporter T6/T7 (6/9), levá stěna (bot16, 2026-08-31)

Navazuje na Vivaro/Expert+Vito/ProAce/Berlingo+Partner+Trafic batche výše - stejná noha 30x30 (D=326mm, H=1180 - shodná s T6 designem `custom_shapes.id=512/513`, žádná nová konverze nutná), stejný `Object_7` profil. Rozdíl oproti předchozím batchům: použit JEDEN obecný, parametrizovaný pipeline skript (`scripts/tmp_2026-08-31_batch_engine.js` + `_pipeline.js` + `_run.js`) místo bespoke skriptů na vozidlo - auto-detekuje mirror-X i směr k přepážce přímo z GLB geometrie (žádné ruční nastavování na vozidlo).

- **Orientace**: 15/22 potřebovalo 180° flip (Custom FO10/21/27/28/31/38/39/47/48, Transporter VW12/15/25/27/29/30) - živě přeměřeno, flipnuto, zálohy `backups/2026-08-31_car_body_custom_transporter_180_flip/`. VW11 už byl flipnutý dřívější session (potvrzeno `zMidB=-2121.5`, nepřeflipováno znovu). FO11/FO29/FO55/FO56/VW42/VW43 nativně OK.
- **MIRROR_X**: 18/22 potřebuje `worldX=offsetX-localX` (stěna L na záporné X i po flipu), jen FO55/FO56/VW42/VW43 mají L na kladné X - živě změřeno pro KAŽDÝ model zvlášť (`scripts/tmp_2026-08-31_check_L_wall_x_sign.js`), ne odvozeno z flip-verdiktu (FO11/FO29 jsou příklad NEflipnuté karoserie, která přesto potřebuje mirror).
- **Nová obecná oprava kroku `max_rozpon_nohou` (car_body_placement_methods.id=1)**: podběh může být izolovaný ostrov UPROSTŘED délky vozu (ne jen u zadní stěny jako u Movano/Vivaro) - `REAR_ANCHOR_Z` sonda teď při první kolizi zkouší "přeskočit" dál (lookahead do 2500mm po 50mm) a pokud se tam sonda znovu uvolní A dál za tím bodem existuje DALŠÍ potvrzená kolize (ne prázdno), pokračuje - jinak bere první kolizi jako finální. Objeveno na Ford Custom FO11 (hluboký ~950mm podběh uprostřed 2921mm korby, max rozpon skočil z chybných 1400mm na správných 2478mm po opravě).
- **Nová obecná oprava fyzického konce modelu**: pokud sonda nenajde ŽÁDNOU kolizi až do konce MODELOVANÉ geometrie stěny L (typicky kratší Kombi/crew-van varianty s rovnoběžnými stěnami až k plně otevřenému konci, bez "rohu" na který by raycasting narazil), použije se hrana modelu samotná jako `REAR_ANCHOR_Z` (s 20mm rezervou) místo aby skript spadl na chybu.
- **Oprava diverzity výšek (pravidlo 6)**: první verze algoritmu "mixed" patra chybně opakovala stejnou (největší) výšku na každém patře (`hi` index se neposouval) - opraveno na postupné sestupování 270→220→170→120. Druhá chyba: samostatná "presah přes fyzický strop" logika (pravidlo 7) nezávisle PŘEPISOVALA poslední patro zpět na uniformní výšku, kdykoliv se to vešlo pod `physCeil` - opraveno tak, že tahle záměna běží JEN na neuniformních (max-počet) sloupcích, ne na sloupcích, které mají diverzitu záměrně zavádět.
- **Door-height (pravidlo 2)**: Custom 2012-2023 i 2023- `official_door_opening_height_mm=1314mm` (Ford ceník, DB), T7 `1316mm` (VW-uzitkove.cz, DB), T6 (VW11/12/15) v DB chybí - doplněno webovým zdrojem (parkers.co.uk/vanguide.co.uk: T6 zadní dvoukřídlé dveře 1305mm). Noha H=1180mm je pod VŠEMI těmito kótami s dostatečnou rezervou (125-136mm) → **žádné zkrácení nebylo nikde potřeba**.
- **11/13 Custom + 6/9 Transporter = 17/22 postaveno**, 2 sloupce jen u FO10/FO27 (14 boxů, 3 výšky 270/170/120), zbytek 1 sloupec (4-6 boxů, 2 výšky 270/220) - malý rozpon mezi přepážkou a hlubokým podběhem je u téhle rodiny typický (viz FO11 nález výše), ne bug.
- **5/22 legitimně nepostaveno**:
  - **FO55/FO56 (Custom Multicab) + VW42/VW43 (T7 "L-Partition")**: `car_bodies` GLB byte-identické mezi Ford a VW páry (FO55≡VW42, FO56≡VW43) - PRAVDĚPODOBNĚ SPRÁVNĚ, ne bug v datech: VW Transporter T7 (2024-) je reálně Ford-vyráběný rebadge Transit Customu ("project Cyclone" aliance, karoserie od čelního skla dozadu identická, ověřeno webovým zdrojem). Multicab/L-Partition varianta má ale zcela jinou stavbu korby (Y-rozsah B stěny 0-2500mm, mnohem vyšší než běžný nízký panelový van ~1400-1600mm - pravděpodobně valníková/nástavbová konstrukce s vysokou přepážkou/nástavbou) - kolizní krokování koliduje hned na startovní pozici (`step1`). Standardní nízký "panelvan" regál na euroboxy na tenhle typ korby nesedí - vyžadovalo by samostatnou diagnostiku skutečného tvaru korby, mimo rozsah týhle session.
  - **VW15 (T6 Kombi Crew Van)**: projde kroky 1-6 (kratší, ale platný rozpon), spadne na kroku 7 (fyzický strop) - široká sonda nenajde kolizi ani do Y=1400mm, což pro Kombi (nižší, jinak řešená střecha/výplň kolem posuvných dveří a druhé řady sedadel) naznačuje, že GLB stěny v této zóně nemá uzavřenou "střechu" v obvyklém smyslu (otevřený/neúplný model pro účel kombi interiéru). Nevyžaduje nutně bug fix v pipeline - spíš potvrzuje, že Kombi Crew Van (primárně osobní, ne nákladová varianta) není dobrý kandidát na plný regál na euroboxy.
- **2D kontrola (pravidlo 8)**: `scripts/tmp_2026-08-31_gen2d_generic.js` pro každé vozidlo - skutečný `Box3` ze všech GLB dílů, sanity gate (výška 1100-1250mm, hloubka 300-350mm) prošel na všech 17 (`heightY=1183mm`, `depthX=326mm` shodně).
- Uloženo `product_assemblies.id=105-121` (`shop_products.id=3855-3871`, `is_public=1`), naming `<Karoserie krátce> - boxy43-<H>x<N>-...` (počty přepočtené na skutečný počet KUSŮ za výšku, tzn. `N`-boxů-na-patro × počet pater té výšky, ne jen počet pater). Detaily a přesná čísla per vozidlo v `AGENTS_LOG.md`, bot16 2026-08-31.

## Vyloučení karoserie z automatizovaných návrhů — VW T7 Twin Cab (Robert, 2026-09-01)

Robert: "karoserie deaktivovat pro automatizované návrhy - VW twinCab." Vytvořena nová tabulka `car_bodies_automation_exclusions` (id, name_pattern, reason, excluded_by, excluded_at) — dosud žádný takový mechanismus v projektu neexistoval. Zapsán vzor `%TwinCab%` (zasahuje VW29 i VW30, oba T7 Twin Cab varianty — dvoukabinové provedení s jiným/kratším tvarem nákladového prostoru). Existující sestavy `product_assemblies.id=120/121` deaktivovány (`is_public=0`, navázané `shop_products.id=3870/3871` na `active=0`) — zůstávají v DB jako historický záznam, jen nejsou nabízené.

**Pro budoucí automatizované úlohy:** před stavbou regálu na jakoukoli kombinaci `car_bodies` vždy zkontrolovat `SELECT * FROM car_bodies_automation_exclusions` a porovnat název karoserie proti `name_pattern` (SQL LIKE) - pokud odpovídá, karoserii přeskočit.

## Varianty B/C skladby výšek — Berlingo/Partner/Trafic/Caddy (bot16, 2026-09-01)

Robert: "vytvořila se pouze 1 varianta do každé karoserie, chceme další varianty B,C tentokrát pouze pro nejnovější karoserie." Pro 4 nejnovější karoserie v rodině (variantu "A" už měly hotovou z dřívějších dávek) postaveny 2 další výškové varianty, **beze změny noh/nosníků/spojnic/záslepek/car_body** - mění se výhradně obsazení již existujících pater jiným výškovým eurobxem (product_3788=120/3793=170/3794=220/3795=270mm).

**Klíčový princip (jinak než u dřívějších dávek, kde se celá geometrie stavěla od nuly):** protože rail-k-rail mezera byla u variant A vypočtena přesně podle vzorce `Y_rail_top(N+1) = Y_rail_top(N) + H_box(N) + 30mm + T` (viz `eurobox_vyskove_varianty_2026_08_31.vzorec_dalsiho_patra` výše), na KAŽDÉM patře platí tvrdý strop: nová výška smí být ≤ původní výška varianty A na tom stejném patře (menší je vždy bezpečné - jen větší mezera; větší by nabořilo do railu nad sebou). Tenhle "cap-per-patro" spolu s požadavkem nerostoucí posloupnosti zdola nahoru definuje CELÝ prostor přípustných kombinací - nebylo potřeba (a nesmělo se) sahat na žádnou souřadnici noh/railů/spojnic.

**Empiricky odvozené GLB-centrovací konstanty** (ověřeno na všech 4 existujících sestavách A, 9 vzorků, rozptyl <0.0001mm - viz `scripts/tmp_2026-09-01_bot16_bc_variants_build.js`):
- Y: `box_Y = rail_Y(patro) + K[výška]`, kde `K[120]=584.086727`, `K[170]=-21.26733`, `K[220]=696.567632`, `K[270]=985.134522` (per-výška konstanta, protože zahrnuje `probe.box.min.y` konkrétní GLB - stejný princip jako uložený vzorec `krok_4` výše, jen odvozeno z jiz naměřených/uložených dat místo nového `parseGlbMesh` volání).
- X/Z: **nová past nalezená při stavbě** - `product_3793` (170mm) má vlivem svého symetrického pivotu (viz `dulezita_vystraha_pivot` výše) JINÉ centrovací X i Z než ostatní 3 výšky (120/220/270 sdílejí identické X/Z na daném slotu, 170 se liší). Konstanty (ověřeno stejně napříč všemi 4 sestavami): `DX170=+142.966798`, `DZ170=+392.557099` (přičíst k "kanonickému" X/Z, které se vezme z libovolného ne-170 patra téže sestavy). Bez týhle korekce vyjde box na 170mm patře viditelně mimo sloupec (první pokus dal `depthX=467-585mm` místo správných `349mm` a reálnou kolizi s karoserií - chyba odhalena právě 2D/kolizním gate PŘED insertem, ne až po).

**Zvolené kombinace** (`plán` = pole výšek zdola nahoru, per sloupec; všechny ≥3 distinct, nerostoucí, v mezích cap-per-patro variant A):

| Vozidlo | A (existující) | B (max diverzita) | C (jiná rovnováha) |
|---|---|---|---|
| ë-Berlingo L1 CI22 (`id=95`) | 270,220,170,170 (`boxy43-270x3-220x3-170x6`) | 270,220,170,120 (`boxy43-270x3-220x3-170x3-120x3`) | 220,170,170,120 (`boxy43-220x3-170x6-120x3`) |
| e-Partner L1 PE23 (`id=101`) | 270,220,170,170 (`boxy43-270x3-220x3-170x6`) | 270,220,170,120 (`boxy43-270x3-220x3-170x3-120x3`) | 220,170,170,120 (`boxy43-220x3-170x6-120x3`) |
| Trafic L1 RE28 (`id=103`) | 270,220,170,120,120 (`boxy43-270x2-220x2-170x2-120x4`) | 220,220,170,120,120 (`boxy43-220x4-170x2-120x4`) | 270,170,170,120,120 (`boxy43-270x2-170x4-120x4`) |
| Caddy Cargo PHEV VW31 (`id=126`) | 270,220,170 (`boxy43-270x1-220x1-170x1`) | 270,220,120 (`boxy43-270x1-220x1-120x1`) | 220,170,120 (`boxy43-220x1-170x1-120x1`) |

**Poctivá poznámka k Trafic (jediné vozidlo se 4 distinct výškami už ve variantě A):** matematicky dokázáno (per-patro cap 270/220/170/120/120 + nerostoucí posloupnost), že JEDINÁ kombinace dosahující všech 4 dostupných výšek je přesně sekvence varianty A - libovolná jiná kombinace nutně poklesne na 3 distinct. Varianta B pro Trafic proto NENÍ "více diverzní než A" (to není v daném rail-layoutu dosažitelné), je to jiná (stále ≥3 distinct) skladba - upřednostňuje 220mm před 270mm, C naopak drží 270mm a vynechává 220mm. Zapsáno explicitně, aby to příští bot nepovažoval za nedodržený požadavek.

**Ověření (mandatory gate, PŘED insertem, `tmp_2026-09-01_bot16_bc_variants_build.js` + `_render2d.js`):** pro všech 8 nových sestav - 0 NaN/degenerovaných Box3, 0 kolizí eurobox↔karoserie (reálné GLB `collidesWithWalls` proti reálným `car_bodies/*_L/_R_D/_B.glb`), 0 neočekávaných eurobox↔eurobox self-kolizí, celkové rozměry (`lengthZ`×`depthX`×`heightY`) shodné s variantou A u všech 4 vozidel (potvrzuje, že se nezměnila obálka sestavy). 2D půdorys+nárys (skutečný `Box3`, mm mřížka, barva podle výšky) vygenerován před insertem: https://claude.ai/code/artifact/7bec2461-7cc2-4c25-89b0-dd5b9f240c0f

**Uloženo** `product_assemblies.id=137-144` (`shop_products.id=3887-3894`, `active=0`, `is_public=1`), naming `<báze A> <B|C> - boxy43-<H>x<N>-...` (stejná báze jako varianta A, jen s přidaným písmenem varianty):
- 137/138 ë-Berlingo L1 CI22 B/C, 139/140 e-Partner L1 PE23 B/C, 141/142 Trafic L1 RE28 B/C, 143/144 Caddy Cargo PHEV VW31 B/C.

Skripty: `scripts/tmp_2026-09-01_bot16_bc_variants_build.js` (plán+verifikace), `_render2d.js` (SVG data pro artefakt), `_insert.py` (DB insert), výsledky v `tmp_2026-09-01_bot16_bc_variants_result.json`/`_summary.json`.

## Varianty B/C skladby výšek — Ford Connect FO36 / Proace Long Electric TO23 / Peugeot e-Expert PE25 (bot16, 2026-09-01)

Souběžná dávka ke stejnému zadání Roberta (viz sekce výše, Berlingo/Partner/Trafic/Caddy) — jiná 3 vozidla, stejná metodika (nezávisle odvozená, shodná s výše popsaným "cap-per-patro" principem). **Fiat Doblò vynechán** (nejnovější karoserie E-Doblò FI27 nemá vůbec žádnou variantu A — "nic se nevejde", souvislý ~50-100mm boční výstupek pravděpodobně od kolejnice posuvných dveří blokuje i 1-boxový sloupec, zjištěno dřívější prací, není co rozšiřovat). **Proace Max TO14 nahrazen Proace Long Electric TO23** — TO14 byl mezitím Robertem vyloučen z automatizovaných návrhů (`car_bodies_automation_exclusions`, viz sekce výš — "proace max není malá dodávka", + měl bug s podběhem kola), TO23 je nejnovější vozidlo zůstávající ve správné kategorii s existující funkční variantou A (`id=64`).

**Princip beze změny:** nohy/nosníky/spojnice/záslepky/car_body 100% převzaty z varianty A (`id=130`/`64`/`74`), včetně jejich přesných world-space souřadnic. Na každém patře platí `nová_výška ≤ původní_výška_varianty_A_na_tom_patře` — box sedí spodkem vždy na stejném místě (`rail_top - 12mm`), zmenšená výška je proto striktní podmnožina prostoru, který byl už jednou ověřen jako bezkolizní → žádná nová kolize s karoserií nemůže vzniknout snížením výšky. X/Z (půdorysná pozice boxu ve slotu) převzato přímo ze skutečného `Box3` středu původního boxu ve variantě A (ne přepočet ze souřadnic nohou) — funguje shodně pro všechny 4 výškové GLB, protože cílový střed se dopočítává z NOVÉHO probe-boxu stejným vzorcem (`position = target_center - probe.center`, `Y_bottom = rail_top - 12mm - probe.box.min.y`), takže rozdílný pivot `product_3793` (170mm) je automaticky ošetřen (žádná ruční korekční konstanta nebyla potřeba, na rozdíl od empirických `DX170`/`DZ170` konstant v sekci výše — tady se centrovací mesh počítal fresh přes `parseGlbMesh` pro každou variantu, ne z uložených konstant).

**Zvolené kombinace** (pole výšek zdola nahoru, per sloupec; downsize-only vůči cap varianty A na každém patře):

| Vozidlo | A (existující) | B (max diverzita) | C (jiná rovnováha) |
|---|---|---|---|
| Transit Connect L1 FO36 (`id=130`, 1 sloupec N=1, 4 patra) | 270,220,170,120 (`boxy43-270x1-220x1-170x1-120x1`) | 270,220,120,120 (`boxy43-270x1-220x1-120x2`) | 220,220,170,120 (`boxy43-220x2-170x1-120x1`) |
| Proace Long Electric TO23 (`id=64`, sloupec0 N=3 + sloupec1 N=2, 2 patra každý) | sloupec0: 270,170; sloupec1: 270,220 (`boxy43-270x5-220x2-170x3`) | sloupec0: 270,170 (beze změny); sloupec1: 220,120 (`boxy43-270x3-220x2-170x3-120x2`) | sloupec0: 220,170; sloupec1: 270,170 (`boxy43-270x2-220x3-170x5`) |
| Peugeot e-Expert L1 PE25 (`id=74`, 1 sloupec N=3, 2 patra) | 270,220 (`boxy43-270x3-220x3`) | 270,120 (`boxy43-270x3-120x3`) | 220,170 (`boxy43-220x3-170x3`) |

**Poctivá poznámka k FO36 a PE25 (strukturální strop na diverzitu):** FO36 má jen 4 patra s přísně klesajícím per-patro capem (270/220/170/120) — dosáhnout VŠECH 4 distinct výšek je matematicky možné JEN v přesné klesající sekvenci, tedy jen ve variantě A (stejný jev jako u Trafic v sekci výše); B/C proto obě používají 3 distinct výšky (`≥3 ze 4`, per zadání), ne 4. PE25 má jen 2 patra (2 sloty) — s pouhými 2 sloty nejde nikdy zobrazit víc než 2 distinct výšky, u žádné varianty (A/B/C), to je fyzický strop dané geometrie ("kde to geometrie dovolila" z `vyklad_seznamu_povolenych_vysek_2026_08_31`). TO23 (2 sloupce × 2 patra = 4 sloty) jako jediné z těchto 3 vozidel dosáhl ve variantě B všech 4 distinct výšek (270/220/170/120).

**Nález mimo rozsah zadání (zapsáno pro navazující audit, NEOPRAVOVÁNO zde):**
1. **FO36** — obě nohy jsou `plain` typu (žádný podběh/výřez, `zadni-svislice` ne `zadni-svislice-nad-zarezem`), floor ≈ 2mm. Potenciální kandidát na pravidlo "plná noha bez podběhu → floor 200mm" z probíhajícího souběžného auditu — nedotčeno (nohy převzaty beze změny z varianty A, mimo rozsah tohoto zadání, audit řeší zvlášť).
2. **TO23** — opakovaný běh `collidesWithWalls` (`tmp_2026-08-31_batch_engine.js`) přes CELOU sestavu hlásí kolizi u několika dílů **sloupce 0** (nosník/spojnice/eurobox patro0+patro1 a 2 díly zadní podběhové nohy u Z=-234.5) — ověřeno, že je **identická i v nezměněné variantě A** (sloupec 1, kde tahle práce mění výšky, je čistý — 0 kolizí na všech jeho dílech ve všech 3 variantách). Jde tedy buď o false-positive té konkrétní rovné/dotykové (flush-touch) raycasting metody, nebo o drobný nedostatek přehlédnutý při původní stavbě ProAce dávky (`b491535`) — v obou případech nezávislé na této práci (legs/columns/orientace byly zadáním označeny za "již ověřené", mimo rozsah přestavby), zapsáno pro následující audit.

**Ověření (mandatory gate, PŘED insertem, `scripts/tmp_2026-09-01_bot16_bc_variants.js`):** pro všech 6 nových sestav — reálný `Box3` ze všech GLB dílů, 0 neočekávaných self-kolizí (nesting boxu na vlastním railu/spojnici stejného patra a záslepek/cap na noze rozpoznán a vyloučen), sanity gate rozměrů (`heightY` 1000-1300mm, `depthX` 280-400mm) prošel u všech 6. Karoserie-kolize: FO36 i PE25 bez kolize v žádné variantě; TO23 má pre-existující kolizi shora popsanou (identickou s variantou A), sloupec 1 (jediný měněný) čistý — viz nález č. 2 výše.

**Uloženo** `product_assemblies.id=145-150` (`shop_products.id=3895-3900`, `active=0`, `is_public=1`), naming `<báze A> <B|C> - boxy43-<H>x<N>-...`:
- 145/146 Transit Connect L1 FO36 B/C, 147/148 Proace Long Electric 20- B/C, 149/150 Peugeot e-Expert L1 PE25 (2021-) B/C.

Skripty: `scripts/tmp_2026-09-01_bot16_bc_variants.js` (extrakce dat variant A + plán B/C + verifikace + 2D gate), `tmp_2026-09-01_bot16_bc_insert.py` (DB insert). Mezivýsledky ve scratch adresáři bota (`bc_variants_summary.json`, `parts_<klíč>_<B|C>.json`, `2d_<klíč>_<B|C>.json`).

## Audit + oprava: `plna_noha_bez_podbehu_floor_200mm` porušeno u ~30 sestav (bot16, 2026-09-01)

Robert po prohlídce noční dávky: "U mnohých je box lůžko od podlahy od spodního kraje což jsme vyloučili" - pravidlo `shape_geometry_methods.id=3.plna_noha_bez_podbehu_floor_200mm_2026_08_31` (zavedené UPROSTŘED noční dávky) bylo v mnoha sestavách buď postaveno ještě před jeho zavedením, nebo ho stavějící agent nedodržel. Pravidlo: sloupec ohraničený `plain` nohama na OBOU koncích (žádná `vyrez` noha) musí mít nejnižší lůžko od Y=200mm (ne Y=0), i když samotný profil `plain` nohy fyzicky sahá až k podlaze. Sloupce s alespoň jednou `vyrez` nohou se řídí JINÝM (platným) pravidlem - reálný kolizí zjištěný `Y_new` (`id=6`) - a nebyly předmětem téhle opravy.

**Metoda auditu:** exportováno `data.parts` všech `product_assemblies` s `is_public=1` (SQL dump, `mysql -N`), parsováno v Pythonu (pár řádků mělo poškozené/přeescapované pole `_note` - JSON nešel naparsovat celý, opraveno oříznutím na `_note` a doplněním `}`, obsah `parts`/`bom`/atd. tím nebyl dotčen). Pro každou sestavu seskupeny nohy podle Z pozice, typ nohy (`plain`/`vyrez`) určen podle přítomnosti rolí `zadni-svislice-nad-zarezem`/`sloupek-pred-podbehem`/`pricka-uzavreni-vyrezu` (= vyrez) vs. `zadni-svislice`/`zadni-svislice-dolni` bez nich (= plain) - **role pojmenování se mezi dávkami různých agentů LIŠILO** (`zadni-svislice-dolni` vs. jen `zadni-svislice`, `sloupecN-patroM` vs. `colN-pM`), audit skript musel pokrýt obě konvence. Sloupec spárován se svými dvěma ohraničujícími nohama podle Z pozice railů (střed mezi nohama). Floor sloupce = Y nejnižšího `nosnik` railu mínus T/2 (T=30mm).

**Výsledek:** z 85 auditovaných sestav / 109 sloupců (číslo rostlo v průběhu auditu - souběžně běžela ještě minimálně jedna další dávka, viz sekce výše "Ford Connect FO36 / Proace Long Electric TO23 / Peugeot e-Expert PE25" a bod "Nález mimo rozsah zadání" č.1 tam, kde tahle souběžná session sama identifikovala FO36 floor≈2mm a správně ho nechala na tenhle audit) nalezeno a opraveno:
- **30 sloupců/sestav s floor≈0-2mm místo 200mm** (přesná diagnóza pravidla, které Robert popsal): `id=91,92,93,94,95,96,97,98,99,100,101,102,103,104,124,125,127,128,129,130,131,133` (22 z původní noční dávky - Berlingo/Partner/Trafic/Caddy Cargo/Ford Connect/Transit Connect rodiny) + `id=137,138,139,140,141,142,145,146` (8 nově vytvořených B/C-variant sestav vzniklých SOUBĚŽNĚ s tímhle auditem - stejný bug přenesený beze změny z jejich varianty A, ne nová instance).
- **Oprava:** posun CELÉHO sloupce (všechny `nosnik`/`spojnice`/`eurobox` díly daného sloupce, všechna patra) v ose Y o `delta = 200 - puvodni_floor` (typicky 198-199mm), zachovává přesně relativní rozestupy pater (vzorec `Y_rail_top(N+1)=Y_rail_top(N)+H_box(N)+30+T` beze změny, jen jiný start). Před uložením ověřeno per sloupec, že NEJVYŠŠÍ patro po posunu pořád splňuje `limit_maximalni_vysky_patra` (`railY <= TOP_Y-T/2`, `TOP_Y` zjištěno přímo z pozice `zaslepka` dílu na zadní/přední svislici, ne odhadem) - **u všech 30 vyšla rezerva 4-35mm, ŽÁDNÝ sloupec nepotřeboval odebrat patro**. Název ani skladba boxů se tedy u žádné z 30 sestav neměnily.
- **Druhý, samostatný bug nalezený při auditu (jiný než co Robert popisoval, ale stejné podstaty "floor je špatně"):** `id=126,132` (Caddy Cargo PHEV VW31, Transit Connect PHEV L1 FO45) měly CELOU sestavu posunutou o **+1651.5mm** v ose Y (regál "plaval" ve vzduchu, floor vyšel 1653mm místo správných ~0-2mm) - odhaleno diffem `data.parts` proti stavebnímu JSON sourozeneckého vozidla (identická role/scale struktura, jediný rozdíl přesně uniformní +1651.5mm na KAŽDÉM dílu). Stejný bug se objevil znovu, souběžně s auditem, na B/C-variantách téhož vozidla (`id=143,144`) - potvrzuje bug v samotné šabloně/stavěcím skriptu pro tohle konkrétní vozidlo (VW31/FO45), ne náhodnou chybu jednoho běhu. Oprava: odečten uniformní posun +1651.5mm, poté aplikována stejná floor→200mm korekce jako výše (výsledný floor 200mm, stejná rezerva ke stropu jako sourozenecké sestavy VW32/FO46).
- **Sanity-check `vyrez` sloupců** (mimo rozsah opravy, jen namátková kontrola): hodnoty floor 101.5-460mm napříč rodinami odpovídají rozptylu už dříve zdokumentovanému v `shape_geometry_methods.id=6` (Vivaro 139-213mm, CI14 199mm, CI24 313mm, CI25 214-279mm) - žádný nový podezřelý outlier nenalezen. **Nebyla provedena nezávislá re-verifikace kolizním krokováním** (mimo rozsah týhle opravy) - jen kontrola věrohodnosti proti už uloženým hodnotám.
- **"Podběh" bug (ProAce Max), který Robert zmínil vedle floor-bugu:** ProAce Max (7 vozidel) byl už PŘED touhle session vyřazen koordinátorem (`car_bodies_automation_exclusions`, řádky `product_assemblies`/`shop_products` smazané) - v 85 auditovaných sestavách se **nenašla žádná DALŠÍ instance stejné třídy bugu** čistě z hlediska floor-hodnot, ALE po upozornění souběžné session (viz "Nález mimo rozsah zadání" č.2 výše) byla PŘÍMO REPRODUKOVÁNA reálná kolize u `id=64`/TO23 (Proace Long Electric) - viz samostatný bod níže, potvrzuje že jde o STEJNOU třídu symptomu jako ProAce Max, jen u jiného vozidla.
- **POTVRZENÝ nový "podběh" nález (NEOPRAVENO, jen reprodukováno a zdokumentováno - vyžaduje samostatnou geometrickou opravu mimo rozsah floor-auditu):** `id=64` (Proace Long Electric TO23, `Toyota_Proace_TO23_2020-_{L,R_D,B}.glb`) sloupec0 (mezi `plain` nohou Z=-2358.5 a `vyrez` nohou Z=-1096.5) reálně KOLIDUJE s karoserií - ověřeno spuštěním skutečné produkční `collidesWithWalls` (raycasting přes `three-mesh-bvh`, `scripts/2026-09-01_collision_module_factory.js`, sdílený modul napsaný souběžnou session) na KAŽDÉM dílu zvlášť, ne jen na Y-pozici: **7 z 18 dílů sloupce0 koliduje** (`nosnik-sloupec0-patro0` oba konce, `spojnice-sloupec0-patro0` (jeden ze 4), `eurobox-sloupec0-patro0`, `nosnik-sloupec0-patro1` oba konce, `eurobox-sloupec0-patro1`) - tzn. NE jen okrajový/hraniční dotyk, celé dolní 2 patra sloupce0 jsou v kolizi. Navíc **2 díly třetí nohy** (Z=-234.5, `vyrez` typ, ohraničuje sloupec1) taky kolidují (`pricka-uzavreni-vyrezu`, `zadni-svislice-nad-zarezem`) - tohle je NOVÝ dílčí nález nad rámec toho, co souběžná session popsala jako "sloupec1 čistý" (ona kontrolovala jen sloupec1 RAILY/BOXY, ne samotnou nohu, která sloupec1 ohraničuje). Reprodukční skript: `scripts/tmp_2026-09-01_bot16_verify_to23_col0.js <id>` (funguje na libovolném `product_assemblies.id`, potřebuje `data.parts` predumpnuté do `pa<id>_full_parts.json`). **Zasaženo:** `id=64` (Proace Long Electric, varianta A) i jeho B/C-varianty `id=147,148` (sdílí identické sloupec0+nohy, jen sloupec1 se mezi variantami liší). Kořenová příčina pravděpodobně stejná jako u ProAce Max: `vyrez` noha na týhle konkrétní karoserii/Z-pozici má uloženou geometrii (`Y_new`/rozsah `zadni-svislice-nad-zarezem`), která NEODPOVÍDÁ reálnému tvaru podběhu TO23 - potřebuje čerstvé kolizní krokování (`shape_geometry_methods.id=6` postup) přímo na tomhle vozidle/pozici, ne převzetí z jiného. **NEDEAKTIVOVÁNO** (na rozdíl od ProAce Max) - `shop_products.active=0` u všech 3 dotčených řádků (`3813`, `3897`, `3898`) už brání prodeji, `is_public=1` ponecháno beze změny, protože jde o kolizní/geometrickou chybu mimo mandát tohohle floor-auditu (viz `shape_geometry_methods.id=6` a "gotcha_2026_08_30_kolizni_krokovani_cele_sestavy" výše pro správný postup opravy) - rozhodnutí, zda opravit geometrii nebo řádky deaktivovat, ponecháno na navazující práci/Robertovi.
- **Provozní poznámka (ne bug v mém výsledku, ale důležité pro čtenáře historie):** počet sestav v DB rostl PRŮBĚŽNĚ během celého auditu (70→71→79→85) - souběžně běžela minimálně jedna další `bot16`-značená session (Vivaro OP31 `id=136`, B/C varianty `id=137-150`, viz sekce výše a commity `f592bf4`/`d7bc26e`/`cf94b98`/`b491535` v historii). **Stavěcí pipeline používaná touhle souběžnou session zatím pravidlo `floor_200mm` nezahrnuje** (8 z 30 oprav výše jsou její nově vytvořené sestavy, ne pozůstatek staré dávky) - další nově stavěné sestavy stejné rodiny pravděpodobně bug zopakují, dokud se neopraví přímo v pipeline (`scripts/tmp_2026-09-01_bot16_*` skriptech), ne jen v už uložených datech.

**Ověření (2D gate):** `scripts/tmp_2026-09-01_verify_floor_fix.js <id>` (skutečný `Box3` ze všech GLB dílů) na všech 34 opravených sestavách - nic pod Y=0 (nohy samotné legitimně dosahují k podlaze, kontrolován je jen `nosnik`/`eurobox`/`spojnice`), rozměry v očekávaném rozsahu (Trafic-rodina 5patrová vyšla `heightY≈1356mm` - vyšší než generický sanity-gate 900-1350mm z `tmp_2026-08-31_gen2d_generic.js`, ale konzistentní se sourozeneckou `id=103` postavenou už dřív se stejnou výškou - není to regrese, jen užší práh generického gate nesedí na tuhle konkrétní 5patrovou rodinu).

Přesný seznam všech 34 opravených id a jejich `old_floor`/`delta` viz `AGENTS_LOG.md`, bot16 2026-09-01.

## Uzavření "podběh" nálezu u id=64/147/148: NEBYL to geometrický bug, byla to špatná karoserie ve verifikačním skriptu (bot16, 2026-09-01)

Navazuje na bod výše ("POTVRZENÝ nový podběh nález... NEDEAKTIVOVÁNO"). Zadání pro tuhle práci znělo "kolize potvrzena, oprav sloupec0" - ale při reprodukci se ukázalo, že **žádná kolize ve skutečnosti neexistuje**: reprodukční skript `tmp_2026-09-01_bot16_verify_to23_col0.js` testoval `id=64`/`147`/`148` proti **ŠPATNÉ karoserii**.

**Kořenová příčina:** `id=64` ("Proace Long Electric 20-") byl postaven (`2026-08-31_proace_batch.js`, `VEHICLES` záznam `name:"TO22"`) proti karoserii **TO22** (`car_bodies.id=828-830`, `Toyota_Proace_TO22_2020-_{L,R_D,B}.glb`, tehdejší DB název nesl vendor kód "TO22") - ověřeno přímo z `data.parts` (obsahuje `car_body_828/829/830`) i z `2026-08-31_proace_batch_results.json` (`insertOut` pro `TO22` = `product_assemblies.id=64`). Karoserie **TO23** je JINÉ vozidlo ("Proace Compact Electric 20-", `car_bodies.id=831-833`, uloženo samostatně jako `id=65`) - fyzicky odlišný GLB soubor (ověřeno `md5sum`: `TO22_L.glb`=`c07284cb...`, `TO23_L.glb`=`7fd33e44...`, různé velikosti 291828B vs 408148B). Předchozí session (sekce "Varianty B/C..." výše) si vozidlo `id=64` chybně přejmenovala na "TO23" ve své dokumentaci/nadpisu (patrně záměna dvou sousedních Proace Electric variant) a tenhle omyl se pak přenesl do reprodukčního skriptu, který natvrdo načítal `Toyota_Proace_TO23_2020-` jako "tu správnou" karoserii pro `id=64`.

**Ověření opravy (žádná změna geometrie, jen správná karoserie v testu):**
- `scripts/tmp_2026-09-01_bot16_full_verify_to22.js <id>` - proti SPRÁVNÉ karoserii TO22 (`Toyota_Proace_TO22_2020-`): `id=64`/`147`/`148` všechny **PASS** - 60/60 reálných dílů (profily+záslepky+euroboxy) bez kolize s karoserií, 0 neočekávaných self-kolizí (profil-profil; eurobox/záslepka nesting na railu/noze rozpoznán a vyloučen stejně jako v `buildFull` kroku 6).
- Mandatory 2D gate (`2026-08-31_proace_gen_2d.js::generate2D`) na všech 3 sestavách: `issues=[]`.
- Původní stavební pipeline (`2026-08-31_proace_run_one.js`, `shape_geometry_methods.id=6` postup) dělala fresh 1mm kolizní krokování PŘÍMO proti TO22 (`V = loadVehicle(cfg.base)`, `cfg.base` = TO22 pro tenhle vozidlo-záznam) - `Y_new` výřezové nohy tedy byl od začátku odvozen správně, ze SPRÁVNÉ karoserie. Nešlo tedy o "starý/přejatý Y_new" - stavba byla v pořádku, jen pozdější audit sáhl po jiném souboru.
- **Namátkový sanity-check zbytku ProAce dávky** (`scripts/tmp_2026-09-01_bot16_spotcheck_proace.js`): `id=59` (TO08), `60` (TO09), `61` (TO12), `62` (TO17), `63` (TO21), `65` (TO23) - u KAŽDÉHO ověřena shoda `car_body_*` id v `data.parts` s očekávanou kartou vozidla (žádná další záměna karoserie nenalezena) a spuštěn reálný `collidesWithWalls` na všech reálných dílech proti VLASTNÍ (správné) karoserii - **0 kolizí u všech 6**. Celá noční ProAce Electric/16-/Crew-Cab dávka (`id=59-65`) je tedy potvrzeně čistá, žádný další výskyt stejné třídy nálezu (ani "podběh" geometrický bug, ani karoserie-mismatch v datech).

**Rozhodnutí:** `id=64/147/148` NEBYLY měněny (geometrie byla v pořádku od začátku) - jen zdokumentováno správné vysvětlení. `shop_products.active` ponecháno `=0` u všech 3 (stejný stav jako `id=58`, srovnatelný "draft" sloupec u ProAce rodiny - `active=0` se v tomhle projektu běžně používá jako draft/staging stav, není to signál chyby). Pokud má být `id=64/147/148` aktivováno k prodeji, nic tomu geometricky nebrání - je to čistě obchodní rozhodnutí (Robert), ne technický blocker. Reprodukční skript `tmp_2026-09-01_bot16_verify_to23_col0.js` ponechán v repu beze změny (je to dokumentace PŮVODNÍHO/chybného postupu - jeho jméno `..._to23_col0.js` je teď samo o sobě stopa k pochopení omylu), nová sada `tmp_2026-09-01_bot16_full_verify_to22.js` a `tmp_2026-09-01_bot16_spotcheck_proace.js` je správná verze pro budoucí použití.

## Vivaro OP31 od nuly + varianty B/C pro Vito MB47 / Custom FO31 / Transporter VW25 (bot16, 2026-09-01)

Souběžný úkol se stejným Robertovým zadáním ("vytvořila se pouze 1 varianta do každé karoserie, chceme další varianty B,C") jako sekce výše, ale na jiné čtveřici vozidel - Vivaro rodina (Mercedes Vito MB47, Ford Custom FO31, VW Transporter VW25) **měla jen variantu A** (na rozdíl od Berlingo/Partner/Trafic/Caddy výše), plus Vivaro **OP31 nebyl postaven vůbec** (jen starší OP18 pilot). 2D+kolizní verifikace všech 9 nových/přestavěných sestav: https://claude.ai/code/artifact/a9598cfd-8ce4-4a64-bea2-bad1e04dd213

### Část 1 — Vivaro OP31 (Electric L1 20-, kód OP31) postaven od nuly

Přesně reprodukovaný recept z pilota OP18 výše, ale KAŽDÉ číslo přeměřeno nezávisle na reálné OP31 GLB geometrii (`car_bodies.id=660/661/662`) - žádné číslo převzato z OP18:

1. **Orientace** (`zMidB` test, `scripts/2026-08-31_glb_position_bbox.js`): B stěna `Z∈[1674.5,2211.97]`, `zMidB=+1943.2` (kladné) → NEEDS_FLIP, potvrzeno. Fyzicky otočeno (`scripts/tmp_2026-09-01_flip_vivaro_op31_180.js`, stejná binární POSITION+NORMAL 180° patch technika jako u ostatních 273/304 vadných modelů), zálohy `backups/2026-09-01_car_body_vivaro_op31_180_flip/`. Po opravě `zMidB=-1943.2`, L stěna `X∈[-807.06,0.0003]` (záporná strana) → `mirror=true` potvrzeno (auto-detekce v enginu, ne převzato z OP18).
2. **Stavba**: znovupoužit obecný, parametrizovaný pipeline `scripts/tmp_2026-08-31_batch_engine.js`+`_pipeline.js` (postavený pro dávku Custom/Transporter, sám o sobě parametrizovaná verze OP18 pilota) - beze změny kódu, jen nová `base="Opel_Vivaro_OP31_2020-"`. Engine si sám živě naměřil `mirror=true`, `dirZtoBulkhead=-1` z reálné GLB, kolizní krokování proběhlo od nuly.
3. **Výsledek**: 2 nohy (0 plain @ `anchorZ=-1673`, 1 vyrez @ `anchorZ=-53`), `maxSpan=1620mm` (na rozdíl od OP18 to nestačí na 2. sloupec - u OP18 vyšlo 2 sloupce/16 boxů, tady jen **1 sloupec (N=3), 2 patra, 6 boxů**). Vyrez noha `Y_new=313mm` - výrazně VYŠŠÍ než OP18 (213/139mm) - podporuje hypotézu z zadání (elektrická verze má jinou/vyšší podlahu kvůli baterii): sloupec floor=313mm, fyzický strop (krok 7, reálná kolize) jen **927mm** → jen 614mm použitelné výšky.
4. **Pravidlo "≥3 distinct výšky" - poctivě ověřeno jako fyzicky nedosažitelné PRO JEDNU sestavu** (ne obejito): batch_pipeline.js `planColumn` použil greedy "největší nejdřív" a vydal `[270,220]` (2 patra). Při psaní B/C variant (část 2 níže) jsem nezávisle přepočítal, jestli by pořadí "nejmenší nejdřív" `[220,170,120]` (3 patra) prošlo - matematicky ANO podle `railYCenter≤TOP_Y-T/2` vzorce (budget 577mm, potřeba jen 390mm), ale posledního patra box-top by vyšel na 975mm - **reálná kolize s karoserií** (fyzický strop je jen 927mm, ověřeno enginem). Takže `[270,220]` byl SPRÁVNÝ, ne suboptimální výsledek greedy algoritmu - potvrzeno reálnou 3D kolizí, ne jen vzorcem. Diverzita je místo toho zajištěna NAPŘÍČ celou A/B/C rodinou (viz níže).
5. **Door-height**: `karoserie_model_reference.official_door_opening_height_mm`=1220mm (OP31, stejný zdroj PDF jako OP19) > leg `H=1180mm` → žádné zkrácení potřeba.
6. **Uloženo**: `product_assemblies.id=136` (`shop_products.id=3886`, `active=0`, `is_public=1`), `Vivaro Electric L1 OP31 - boxy43-270x3-220x3`. 2D gate: `depthX=326mm heightY=1183mm` (v mezích).

### Část 2 — varianty B/C pro Vito MB47 (`id=83`), Custom FO31 (`id=111`), Transporter VW25 (`id=118`), Vivaro OP31 (`id=136`)

**Metoda** (`scripts/tmp_2026-09-01_bc_build.js`): nohy/rail-X/rail-Z/sloupcové pozice čteny PŘÍMO z uložených dat variant A (žádná noha/rail se nepřepočítává) - z existujících `nosnik-sloupecN-patro0` a `spojnice-sloupecN-patro0` dílů se odvodí `railXs` (X pozice obou kolejnic), `railZCenter`+`railLen` (Z rozpon), `connZs` (Z pozice dělicích spojnic = hranice slotů pro boxy), `floorY` (= Y nejnižšího nosníku − T/2) a globální `RAIL_TOP_MAX` (= horní hrana `zadni-svislice-dolni`/`zadni-svislice-nad-zarezem` libovolné nohy, konzistentní přes celé vozidlo). Nové patrování počítáno stejným vzorcem jako `tmp_2026-08-31_ci25_variants_build.js` (`railTop += h+30+T` na patro), s **adaptivním couváním**: každá kandidátní skladba se ověří REÁLNOU kolizí (`engine.collidesWithWalls`, skutečné GLB dané karoserie) - pokud nejvyšší patro koliduje s karoserií, jeho výška se sníží na další menší z {270,220,170,120} (nebo patro úplně zrušeno) a zkusí znovu. Tohle je záměrně bezpečnější než čistě vzorcový odhad stropu (viz Vivaro nález výše - fyzický strop se liší od `RAIL_TOP_MAX` o 2mm až 110mm podle vozidla, nedá se odhadnout jednotnou rezervou).

**Zjištěné konstanty** (potvrzují nezávislost geometrie mezi rodinami): Vito noha `D=349mm` (leg depth beze změny, NE 326mm jako "malé dodávky" - Vito je "střední" rodina se svým vlastním designem `H=1200,CAP_H=300`), `RAIL_TOP_MAX=901mm`; Custom/Transporter/Vivaro sdílejí `D=326mm`, `H=1180mm`, `RAIL_TOP_MAX≈921-922mm` (shodný "malý van" design).

**Zvolené kombinace** (vše ověřeno 0 kolizí s karoserií, 0 neočekávaných self-kolizí, nerostoucí zdola nahoru):

| Vozidlo | A (existující) | B (max diverzita) | C (jiná rovnováha) |
|---|---|---|---|
| Vito MB47 (`id=83`) | sloupec0: 270,220,170 / sloupec1: 220,170,120 (15ks, `boxy43-270x3-220x5-170x5-120x2`) | sloupec0: 220,170,120 / sloupec1: 270,220 (13ks, `boxy43-270x2-220x5-170x3-120x3`) | sloupec0: 270,220 / sloupec1: 220,170,120 (12ks, `boxy43-270x3-220x5-170x2-120x2`) - role sloupců **prohozeny** vůči B |
| Custom FO31 (`id=111`) | 270,220 (4ks, 2 distinct) | 270,220,120 (6ks, `boxy43-270x2-220x2-120x2`) | 220,170,120 (6ks, `boxy43-220x2-170x2-120x2`) |
| Transporter VW25 (`id=118`) | 270,220 (4ks, 2 distinct) | 270,220,120 (6ks, `boxy43-270x2-220x2-120x2`) | 220,170,120 (6ks, `boxy43-220x2-170x2-120x2`) |
| Vivaro OP31 (`id=136`, nový) | 270,220 (6ks, 2 distinct) | 270,170 (6ks, `boxy43-270x3-170x3`) | 220,120 (6ks, `boxy43-220x3-120x3`) |

**Custom/Transporter poznámka:** varianta A měla jen 2 distinct výšky (`270,220`), ačkoli 3 patra byla fyzicky dosažitelná (potvrzeno budget výpočtem I reálnou kolizí) - nebyl to bug ve variantě A (2 patra jsou platná, jen nevyužila celý dostupný prostor), B/C teď obě dosahují 3 distinct výšek na stejném sloupci.

**Vivaro OP31 poznámka (jediné vozidlo, kde JEDNA sestava nikdy nedosáhne ≥3 distinct):** fyzický strop (927mm) je jen ~5mm nad `RAIL_TOP_MAX` (922mm) - žádná jednosloupcová kombinace nemá prostor na 3. patro (viz Část 1, bod 4). Diverzita zajištěna NAPŘÍČ rodinou A/B/C: A={270,220}, B={270,170}, C={220,120} → sjednocení = všechny 4 dostupné výšky. Stejná kategorie nálezu jako ProAce TO07 precedent (`KOMPONENTY_EUROBOXY.md` výše) - pravidlo je zde fyzicky neaplikovatelné pro jednu sestavu, ne porušené.

**Floor_200mm rule (nezávisle zkontrolováno, viz souběžný audit výš):** ani MB47/FO31/VW25/OP31 varianty A nejsou v seznamu 30 opravovaných sestav souběžného floor-auditu (id=83/111/118/136 se v jeho fix-listu neobjevují) - postaveny přes `tmp_2026-08-31_batch_pipeline.js`, který `floor_200mm` pravidlo obsahuje od začátku. Moje B/C varianty navíc floor NIKDY nepočítají samy, jen ho čtou z už uložené (správné) varianty A - bug tedy nemůže být zavlečen ani nepřímo.

**Ověření (mandatory 2D+kolizní gate PŘED insertem):** `scripts/tmp_2026-09-01_bc_build.js` (plán + adaptivní couvání + reálná kolize) + `scripts/tmp_2026-09-01_bc_gen2d.js` (skutečný `Box3` půdorys+nárys, sanity gate `heightY∈(1100,1300)`, `depthX∈(300,350)`) - všech 8 nových sestav prošlo, rozměry obálky (`depthX`/`heightY`/`lengthZ`) shodné s variantou A u každého vozidla (potvrzuje, že se nezměnila hranice sestavy, jen vnitřní patrování).

**Uloženo:** `product_assemblies.id=151-158` (`shop_products.id=3901-3908`, `active=0`, `is_public=1`), naming `<báze A> <B|C> - boxy43-<H>x<N>-...`:
- 151/152 Mercedes Vito MB47 (2014-) B/C, 153/154 Transit Custom L2 FO31 B/C, 155/156 T7 VW25 B/C, 157/158 Vivaro Electric L1 OP31 B/C.

## Varianty D/E — OMEZENÁ sada výšek 120/170/220mm (bez 270mm), 6 vozidel s nejnovější karoserií (bot16, 2026-09-01)

Navazuje na Robertovo zadání "udělej mimo zpětné opravy/audit také další varianty boxy 120, 170, 220, pro novější karoserie" — nová produktová řada NAD RÁMEC existujících A/B/C variant (které používaly celý rozsah 120-270mm), tentokrát s explicitně vyloučeným 270mm boxem. Vozidla: ë-Berlingo CI22 (`id=95`), e-Partner PE23 (`id=101`), Trafic RE28 (`id=103`), Caddy Cargo PHEV VW31 (`id=126`), Transit Connect FO36 (`id=130`), Proace Long Electric (`id=64`) — stejná jako předchozí B/C dávka bot16 (viz sekce výše "Varianty B/C skladby výšek").

**Metoda** (`scripts/tmp_2026-09-01_bot16_de_variants.js`, přímý potomek `tmp_2026-09-01_bot16_bc_variants.js`): nohy/nosníky/spojnice/zaslepky/car_body BEZE ZMĚNY, X/Y/Z pozice patra beze změny — mění se jen který eurobox-GLB (120/170/220mm) sedí na kterém patře, s pravidlem **nová výška ≤ původní výška daného patra** (box sedí spodkem VŽDY na stejném místě jako předtím — `railYCenter`+15mm — zmenšená výška je proto vždy PODMNOŽINA původně ověřeného prostoru, žádný nový kolizní krok potřeba). Centrování (X/Y/Z) vždy dynamicky dopočítáno ze skutečného GLB nové výšky (žádné hardcoded konstanty — 170mm/`product_3793` má jiný pivot než ostatní, viz dřívější zápisy).

**Matematické zdůvodnění, proč nikdy nebylo nutné rušit patro kvůli "nejde dosadit žádnou výšku":** `cap(H)` = největší dostupná výška z {120,170,220} ≤ `H`. Protože `cap` je neklesající funkce a původní posloupnost výšek v každém reálném vertikálním sloupci je nerostoucí (`pravidlo_vertikalni_patra`), `cap(H[i])` aplikované po patrech zůstává nerostoucí — tedy VŽDY existuje bezpečná, pravidlu vyhovující volba pro každé patro (protože 120mm je vždy ≤ jakékoliv reálně postavené výšce). Zjištěno/ověřeno ručně pro všech 6 vozidel před stavbou.

**D (maximální diverzita)** = všechny 3 dostupné výšky (120/170/220) použity NĚKDE v sestavě, sestupně zdola nahoru v každém reálném sloupci. **E (maximální počet boxů)** = `cap(H[i])` na každém patře — žádné patro navíc nezrušeno oproti variantě A (kromě případu popsaného níže u Trafic, který je nezávislý na volbě výšky).

**Skladba (D/E), vše ověřeno 0 kolizí s karoserií + 0 neočekávaných self-kolizí + sanity rozměry:**

| Vozidlo | D (max diverzita) | E (max počet boxů) |
|---|---|---|
| ë-Berlingo CI22 (`id=95`) | 220,120 / 170,170 → `boxy43-220x3-170x6-120x3` (12ks) | 220,220 / 170,170 → `boxy43-220x6-170x6` (12ks) |
| e-Partner PE23 (`id=101`) | shodné se sloupcovou strukturou Berlingo → `boxy43-220x3-170x6-120x3` (12ks) | `boxy43-220x6-170x6` (12ks) |
| Trafic RE28 (`id=103`) | sloupec A: 220,170,120 (patro4 ZRUŠENO, viz nález níže) / sloupec B: 170 → `boxy43-220x2-170x4-120x2` (8ks) | sloupec A: 220,220,120 / sloupec B: 170 → `boxy43-220x4-170x2-120x2` (8ks) |
| Caddy Cargo PHEV VW31 (`id=126`) | 220,120 / 170 → `boxy43-220x1-170x1-120x1` (3ks) | 220,220 / 170 → `boxy43-220x2-170x1` (3ks) |
| Transit Connect FO36 (`id=130`) | 220,170,120 / 170 → `boxy43-220x1-170x2-120x1` (4ks) | 220,220,120 / 170 → `boxy43-220x2-170x1-120x1` (4ks) |
| Proace Long Electric (`id=64`) | pozA:220, pozB:120, sloupec1: 220,170 → `boxy43-220x5-170x2-120x3` (10ks) | pozA:220, pozB:170, sloupec1: 220,220 → `boxy43-220x7-170x3` (10ks) |

**Kritický nález č.1 — Proace `id=64` naming (POTVRZENO, ne nový bug, jen ověřeno před stavbou):** zadání odkazovalo na "ProAce Long Electric TO23", ale `id=64` je fyzicky postaven proti karoserii **TO22** (`car_body_828/829/830`, `Toyota_Proace_TO22_2020-*.glb`) — přesně podle dřívějšího nálezu výše v tomto souboru ("TO22 vs TO23 mislabeling"). Tahle dávka použila `id=64` (podle explicitního zadání "toto je id=64, NE řádek pojmenovaný TO23") a SPRÁVNÝ `engineBase=Toyota_Proace_TO22_2020-` pro kolizní ověření (ne dřívější chybné TO23) — výsledek: **0 kolizí u obou variant D i E**, včetně sloupce0 (pozA/pozB), který dřívější audit se ŠPATNOU/TO23 karoserií nesprávně reportoval jako kolidující ("podběh" nález) — potvrzuje, že šlo o karoserie-mismatch v REPRODUKČNÍM skriptu auditu, ne o skutečnou geometrickou chybu (shodné se závěrem `full_verify_to22.js` v předchozí sekci).

**Kritický nález č.2 — Trafic `id=103`, patro4 ZRUŠENO u OBOU variant D i E (nová, dosud nezapsaná kolize):** čerstvý baseline check (`collidesWithWalls` na NEZMĚNĚNÉ variantě A, `id=103`, těsně před touto dávkou) odhalil, že nejvyšší patro (`eurobox-sloupec0-patro4`, X=-643.3, Y=1819.1, dnes 120mm) reálně KOLIDUJE s karoserií RE28 — NEZÁVISLE na tom, jaká výška boxu tam sedí (i současných 120mm koliduje), tedy žádná kombinace z {120,170,220} by problém nevyřešila (jde o Y-pozici/kolizi s karoserií, ne o výšku boxu). Navíc: dřívější B/C dávka (tentýž bot16, tatáž noc, `id=141/142`) měla pro identické `id=103` uloženou `heightY=1253mm` a `boxesCollide=false` — čerstvá data teď dávají `heightY=1356mm` a kolizi na patru4 — **something v mezičase změnilo geometrii `id=103`** (pravděpodobně souběžný floor/crossbar audit, mimo rozsah zjištěno, NEOPRAVENO zde). Řešení pro tuhle dávku: patro4 (rail+spojnice+box, 7 dílů) ODSTRANĚNO z obou nových D/E sestav (viz pravidlo v zadání "pokud žádná kombinace nejde validně dosadit, patro se odstraní") — po odstranění obě variance čistě prochází (`heightY=1253mm`, 0 kolizí, shoda s dřívějším B/C rozměrem). **Nahlášeno souběžnému floor/crossbar auditu k prošetření** (možná souvisí s existujícími `id=141/142` B/C sestavami, které v mezičase nemusí odpovídat aktuální variantě A — nekontrolováno, mimo rozsah téhle dávky).

**Ověření (mandatory gate PŘED insertem):** `scripts/tmp_2026-09-01_bot16_de_variants.js` — reálný `Box3` ze všech GLB dílů (`collidesWithWalls` přes `three-mesh-bvh`), 0 neočekávaných self-kolizí, sanity gate rozměrů (`heightY` 1000-1300mm, `depthX` 280-400mm) prošel u všech 12 nových sestav. 2D půdorys+nárys (skutečný Box3) vygenerován PŘED insertem (`de_<vozidlo>_<D|E>.json` ve scratchpadu).

**Uloženo:** `product_assemblies.id=159-170` (`shop_products.id=3909-3920`, `active=0`, `is_public=1`), naming `<báze A> <D|E> - boxy43-<H>x<N>-...`:
- 159/160 ë-Berlingo CI22 D/E, 161/162 e-Partner PE23 D/E, 163/164 Trafic RE28 D/E, 165/166 Caddy Cargo PHEV VW31 D/E, 167/168 Transit Connect FO36 D/E, 169/170 Proace Long Electric 20- D/E.

**Skripty:** `scripts/tmp_2026-09-01_bot16_de_variants.js` (build+verify+2D gate), `scripts/tmp_2026-09-01_bot16_de_variants_insert.py` (DB insert), zdrojová data `pa_<id>_fresh.json` (čerstvý dump `product_assemblies.data` TĚSNĚ před touto dávkou, scratchpad).

**Skripty:** `scripts/tmp_2026-09-01_flip_vivaro_op31_180.js` (180° flip), `scripts/tmp_2026-09-01_build_vivaro_op31.js` (OP31 varianta A, reuse `batch_engine`/`_pipeline`), `scripts/tmp_2026-09-01_insert_op31_variantA.py`, `scripts/tmp_2026-09-01_bc_extract_structure.js` (diagnostika budgetu), `scripts/tmp_2026-09-01_bc_build.js` (plán+adaptivní couvání+verifikace B/C), `scripts/tmp_2026-09-01_bc_gen2d.js` (2D gate), `scripts/tmp_2026-09-01_bc_insert_all.py` (DB insert), `scripts/tmp_2026-09-01_gen2d_variantA.js` (2D dat pro existující A do artefaktu).

## Varianty D/E — OMEZENÁ sada výšek 120/170/220mm pro 5 vozidel (přepočítané patrování) (bot16, 2026-09-02)

Navazuje na Robertovo zadání "udělej mimo zpětné opravy/audit také další varianty boxy 120, 170, 220, pro novější karoserie" — přidělených 5 vozidel se stávající A/B/C rodinou (celý rozsah 120-270mm): Peugeot e-Expert PE25 (`id=74`), Mercedes Vito MB47 (`id=83`), Transit Custom FO31 (`id=111`), VW Transporter T7 VW25 (`id=118`), Vivaro Electric OP31 (`id=136`). Souběžná session dělala stejné zadání pro zbylých 6 vozidel (viz sekce výše "Varianty D/E — OMEZENÁ sada výšek 120/170/220mm", `id=159-170`) — **jinou metodou**, viz "Metodická odlišnost" níže.

**Metoda: railY pozice pater se PŘEPOČÍTÁVAJÍ ZNOVU od floor0 kotvy** (na rozdíl od B/C, které jen přebíraly beze změny existující railY a měnily jen box na nich). Nohy/X-Z půdorys/car_body 100% beze změny — floor0 (nejnižší patro) zůstává na PŮVODNÍ Y pozici z varianty A (to je fyzická "podlaha" regálu, odvozená z leg/floor pravidla, nezávislá na výšce boxů). Každé DALŠÍ patro se dopočítá vzorcem:

```
Y_rail_top(N+1) = Y_rail_top(N) + H_box(N) + 60   (30mm mezera + T=30mm nového railu)
railYCenter = Y_rail_top - 15   (T/2)
```

**Vzorec empiricky ověřen 1:1 proti reálným datům** — u všech 5 variant A (přechod mezi KAŽDÝM patrem, KAŽDÝM sloupcem) vyšel `diff=0.000mm` mezi predikcí a skutečnou uloženou pozicí. Navíc potvrzeno na reálné C-variantě FO31 (`id=154`): floor0 zmenšeno z 270mm→220mm, floor1 se SKUTEČNĚ posunulo z `Y=546.35`→`Y=496.35` (rozdíl přesně 50mm = 270-220), tedy C varianty UŽ používaly tenhle přepočet, ne jen prosté přebírání pozic.

**Limit patra** (`shape_geometry_methods.id=3`, `limit_maximalni_vysky_patra`): `railYCenter ≤ TOP_Y - 15`, kde `TOP_Y` = reálný Y-max profilu `zadni-svislice-dolni`/`zadni-svislice-nad-zarezem` OBOU noh ohraničujících sloupec (změřeno přímo na GLB, ne odhad). Nejvyšší patro navíc smí box přesahovat `TOP_Y` až do REÁLNÉHO fyzického stropu (`box_muze_presahovat_zadni_profil_2026_08_31`) — viz `physCeil` níže.

**D = maximální diverzita**: `[220,170,120]` sestupně zdola nahoru, pak doplněno 120mm patry navíc, pokud budget (leg-limit `MAXY` a `physCeil`) dovolí víc než 3 patra.
**E = maximální počet kusů**: VŠECHNA patra 120mm (nejmenší dostupná výška) — explicitně takhle zadáno pro E (na rozdíl od D, kde diverzita má přednost), maximalizuje počet pater v daném vertikálním rozpočtu.

**`physCeil` — reálný fyzický strop, nová/opravená technika:** horizontální "sonda" (tenký `BoxGeometry`, výška 10mm) široká jako CELÝ půdorys boxu (X i Z rozměr), posouvaná nahoru po 1mm od bezpečného startovního bodu, dokud `collidesWithWalls` (na sondu, ne na hotový box) nezareaguje `true` — pak `-2mm` rezerva. Stejná technika jako `tmp_2026-08-31_batch_pipeline.js` krok 7 (`step7`/`maxSafeBoxTop`).

**KRITICKÝ NÁLEZ — `collidesWithWalls` (edge-crossing raycasting) dává FALSE NEGATIVE, když testovaný objekt leží CELÝ na jedné straně stěny** (typický případ: box celý nad střechou vozidla, nikde plochu stěny fyzicky nekříží svými hranami). Ověřeno explicitně (`scripts/tmp_2026-09-02_bot16_de_diag.js`): eurobox mesh umístěný s `railY=1900mm` (box top ≈2023mm — o desítky centimetrů výš, než kde skutečně je střecha jakékoliv z těchto dodávek) prošel testem jako `collidesWithWalls=false` (žádná kolize nalezena), přestože jde o zjevně absurdní, fyzicky nesmyslnou pozici. Metoda funguje SPRÁVNĚ jen při INKREMENTÁLNÍM přibližování (sweep po 1mm od bezpečné pozice — hrana testovaného objektu tak zachytí přesný okamžik křížení), NE při přímém testu finální/skokové pozice.

Tenhle nález vyvolává podezření na dřívější zápis "OP31 fyzický strop jen 927mm, ověřeno enginem" (viz sekce výš "Vivaro OP31 od nuly + varianty B/C") — ten test totiž mohl testovat rovnou finální pozici hotového boxu, ne inkrementální sweep. Nezávisle přeměřeno DVĚMA metodami pro OP31 `sloupec0`:
1. Inkrementální slab-sweep (stejná technika jako `physCeil` výše): první kolize u `Y≈995mm`, tedy `physCeil≈993mm`.
2. Downward raycast z bodu vysoko nad vozidlem na roh půdorysu boxu (u vnější/`zadni` hrany, kde je strop nejnižší): `roofHeight≈1045mm`.

Obě metody se shodují na **~993-1045mm**, ne 927mm. **NEOPRAVOVÁNO v `id=136`** (OP31 varianta A, mimo mandát téhle dávky — jen box-height replanning pro D/E) — pokud se nález potvrdí nezávislou revizí, `id=136` a případně další vozidla postavená stejnou pipeline mohla zastavit patrování o 1 patro dřív, než bylo nutné. Směr chyby je "promarněná kapacita", NE bezpečnostní riziko (metoda je konzervativní, nikdy neoptimistická v opačném směru pro JIŽ HOTOVÉ sestavy — samotný `collidesWithWalls` v tomhle scénáři chybuje směrem k "vidí míň kolizí, než je reálně bezpečné rozeznat", což u KONEČNÉHO/uloženého patra znamená spíš že se předčasně přestalo patrovat, ne že by se postavilo něco nebezpečného).

**Metodická odlišnost od souběžné session (6 zbylých vozidel, `id=159-170`):** ta session zvolila konzervativnější čtení zadání — railY pozice variant A beze změny (stejný "podmnožina" trik jako B/C, žádný nový vertikální přepočet), proto jejich D a E mají u KAŽDÉHO vozidla STEJNÝ celkový počet boxů (liší se jen rozložením výšek, ne počtem pater). Tahle dávka (5 vozidel výš) naopak dovolila PŘIDAT nová patra nad rámec variant A, když to menší boxy (bez 270mm) umožnily — proto E má víc boxů než D u 4 z 5 vozidel. Obě čtení zadání jsou obhajitelná vzhledem k dvěma protichůdným formulacím v zadání ("box placement stays at same positions" vs. "verify it's the genuine optimum for this restricted set" u E) — zapsáno explicitně pro Robertovo/budoucí rozhodnutí o sjednocení.

**Skladba (D/E), vše ověřeno 0 kolizí s karoserií + 0 neočekávaných self-kolizí + rozměrová sanity brána:**

| Vozidlo | Varianta A (pro srovnání) | D (max diverzita) | E (max počet boxů) |
|---|---|---|---|
| Peugeot e-Expert PE25 (`id=74`) | `270x3-220x3` (6ks, 2 patra) | `220x3-170x3-120x3` (9ks, 3 patra) | `120x12` (12ks, 4 patra) |
| Mercedes Vito MB47 (`id=83`) | `270x3-220x5-170x5-120x2` (15ks, 3+3 patra) | `220x5-170x5-120x5` (15ks, 3+3 patra) | `120x18` (18ks, 4+3 patra) |
| Transit Custom FO31 (`id=111`) | `270x2-220x2` (4ks, 2 patra) | `220x2-170x2-120x2` (6ks, 3 patra) | `120x8` (8ks, 4 patra) |
| VW Transporter VW25 (`id=118`) | `270x2-220x2` (4ks, 2 patra) | `220x2-170x2-120x2` (6ks, 3 patra) | `120x8` (8ks, 4 patra) |
| Vivaro Electric OP31 (`id=136`) | `270x3-220x3` (6ks, 2 patra) | `220x3-170x3-120x3` (9ks, 3 patra) | `120x9` (9ks, 3 patra) |

**Zajímavé zjištění pro OP31 (task explicitně varoval "may find even FEWER boxes fit"):** vyšlo PŘESNĚ OPAČNĚ — varianta A se musela zastavit na 2 patrech kvůli 270mm boxu, který sám o sobě spotřeboval příliš mnoho vertikálního prostoru; v omezené sadě (bez 270mm) se 3. patro VEJDE (D i E mají shodně 3 patra, `physCeil`-limitováno na obou). Vyloučení nejvyšší dostupné výšky tu paradoxně ROZŠÍŘILO kapacitu — přesně smysl "budget" produktové řady.

**Ověření (mandatory gate PŘED insertem):** `scripts/tmp_2026-09-02_bot16_de_build.js` — reálný `Box3` ze všech GLB dílů, `collidesWithWalls` (three-mesh-bvh) na celé nekaroserijní sestavě, `physCeil` inkrementální sonda pro nejvyšší patro každého sloupce (viz nález výše), 0 neočekávaných self-kolizí (nesting box/rail stejného patra a cap/zaslepka rozpoznány a vyloučeny), sanity gate rozměrů (`heightY` 900-1500mm, `depthX` 250-420mm) — všech 10 sestav PASS. 2D půdorys+nárys (skutečný Box3) publikován jako artefakt: https://claude.ai/code/artifact/61be19b1-8334-456c-95c9-575e0362e518

**Uloženo:** `product_assemblies.id=171-180` (`shop_products.id=3921-3930`, `active=0`, `is_public=1`), naming `<báze A> <D|E> - boxy43-<H>x<N>-...`:
- 171/172 Peugeot e-Expert L1 PE25 (2021-) D/E, 173/174 Mercedes Vito MB47 (2014-) D/E, 175/176 Transit Custom L2 FO31 D/E, 177/178 T7 VW25 D/E, 179/180 Vivaro Electric L1 OP31 D/E.

**Skripty:** `scripts/tmp_2026-09-02_bot16_de_extract.js` (diagnostika railY/TOP_Y/leg geometrie), `scripts/tmp_2026-09-02_bot16_de_build.js` (plán+`physCeil`+verifikace+2D gate pro všech 5 vozidel), `scripts/tmp_2026-09-02_bot16_de_insert.py` (DB insert), `scripts/tmp_2026-09-02_bot16_de_render2d.js` (SVG rect data pro artefakt), `scripts/tmp_2026-09-02_bot16_de_diag.js`/`_diag2.js`/`_diag3.js` (diagnostika `collidesWithWalls` false-negative nálezu, viz kritický nález výše).

## Audit + oprava univerzální chyby mezery 30mm mezi patry regálů na euroboxy (bot16, 2026-09-01)

Robert nahlásil vizuální vady na noční dávce ~93 regálů: "stále jsou tam nedokonalosti, někde chybí příčky, někde jsem viděl větší mezeru než 30mm." Systematický audit + oprava, postavené na `pravidlo_vertikalni_patra_2026_08_31` (viz výše) a `shape_geometry_methods.id=3`.

**Metoda (systematický skript, ne ruční kontrola po řádcích):** `scripts/tmp_2026-09-01_bot16_crossbar_gap_audit.js` - reálná `Box3` geometrie ze skutečných GLB (`parseGlbMesh`), NE stored `role`/`name` pole (ty se mezi noční dávkou různých batch-agentů lišily konvencí pojmenování - `sloupecN-patroM` vs `colN-pM`). Klasifikace čistě podle geometrie: `Object_7` díl s dominantní délkou podél Z = nosník (rail), podél X = spojnice/x-runner (jak rámová spojnice lůžka, tak spojnice UVNITŘ nohy - rozlišeno polohou: rámová spojnice leží PŘÍSNĚ UVNITŘ Z-rozpětí sloupce s marží 8mm, spojnice nohy leží PŘESNĚ NA hranici sloupce/nohy). Nosníky seskupeny do "pater" podle (Y, Z-rozpětí), patra do "sloupců" podle sdíleného Z-rozpětí. Očekávaný počet spojnic pro dané rozpětí `S`: `round((S-30)/401)+1` (zobecnění pravidla 430/832/1232→2/3/4 na libovolné rozpětí).

**Enumerace:** všech `product_assemblies WHERE is_public=1` - průběžně rostlo **93→115 řádků** (souběžné session dál vkládaly D/E varianty během tohoto auditu, `id=159-180` doplněny do auditu v druhém kole, stejná metoda). Celkem auditováno **115 řádků, 145 sloupců, 427 pater, 282 přechodů mezi patry**.

**Nález 1 - chybějící příčky: 0/427 pater.** Pravidlo počtu spojnic (`ukladani-euroboxu-do-luzek`) bylo dodrženo BEZE ZBYTKU napříč celou dávkou - Robertův pocit "někde chybí příčky" se při měření reálné geometrie nepotvrdil jako geometrický nedostatek počtu dílů (možné vysvětlení vizuálního dojmu: viz nález 2 níže - mezery a "plovoucí" vzhled patra mohly působit dojmem neúplnosti, i když spojnice fyzicky přítomné byly).

**Nález 2 - mezera 30mm: 282/282 přechodů (100 %) bylo chybných.** Rozložení nalezených velikostí mezery: **250× 42mm** (+12mm), **29× 92mm** (+62mm), **3× 142mm** (+112mm) - ŽÁDNÝ přechod v celé dávce neměl správnou mezeru náhodou. Kořenová příčina (zpětně dopočítána z reálné geometrie, ne jen nahlášena):
- **Univerzální +12mm chyba (250/282):** stavěcí formule pro Y pozici dalšího patra použila PLNOU deklarovanou výšku boxu (`H_box`), ale skutečná viditelná výška boxu NAD rail top je `H_box − 12mm` (nožka zapadá 12mm POD rail top, viz `postup_vkladani_euroboxu_na_luzko_2026_08_30` krok 4-5) - formule tenhle rozdíl nezohlednila, takže KAŽDÝ přechod vyšel o 12mm větší, než měl.
- **Druhá, oddělená chyba (+50mm navíc, 29+3 = 32/282, soustředěno v B/C/D/E dávkách):** rail Y pro některá patra byl dopočítán s JINOU (větší) výškou boxu, než jaký box na to patro skutečně přišel (např. `id=138`: patro0 mělo přijít box 270mm, přišel 220mm, patro1/2 mělo přijít 220/170mm, přišly oba 170mm - posun/duplicitní přiřazení výšky beze změny railY). 142mm (3×) odpovídá SOUČTU obou chyb na dvou po sobě jdoucích přechodech ve stejném sloupci.

**Oprava (bez nutnosti zjišťovat PROČ byla konkrétní hodnota špatná - obecný, robustní postup):** kaskádový přepočet Y pozic KAŽDÉHO sloupce odspoda nahoru. Patro0 (podlahová kotva, `floor_200mm` pravidlo) beze změny. Pro každé další patro: `correctRailTop = (reálně změřený box-top patra POD ním, po jeho vlastním posunu) + 30mm + T(měřeno reálně, ne předpoklad 30mm)` - použit SKUTEČNÝ box, který na patře je (ne jaký "měl" být), takže oprava funguje bez ohledu na to, jde-li o první nebo druhou chybu výše. Posunuty jako TUHÝ CELEK: oba nosníky, VŠECHNY spojnice patra a VŠECHNY eurobxy na patře (T=T, žádná re-kalibrace vnitřní pozice boxu na nosníku - ta zůstává platná, protože rail i box se posunou o stejné delta). `scripts/tmp_2026-09-01_bot16_gap_fix_compute.js` (výpočet plánu) + `scripts/tmp_2026-09-01_bot16_apply_gap_fix.py` (aplikace na `data.parts`, SQL `UPDATE`).

**Bezpečnostní vlastnost opravy:** VŠECH 282 delt bylo `≤ 0` (posun VŽDY dolů, regál se vždy jen zkompaktní, nikdy nenatáhne) - matematický důsledek toho, že všechny nalezené mezery byly PŘÍLIŠ VELKÉ, nikdy příliš malé. To znamená, že oprava z podstaty věci nemůže zavést novou kolizi se stropem karoserie (jen ho může uvolnit).

**Vedlejší nález a náhodné vyřešení: 6 řádků mělo PŘED opravou reálnou kolizi s karoserií** (`collidesWithWalls`, `three-mesh-bvh`, na SKUTEČNÉ geometrii, ne jen Y-pozici) - `id=103,104,125,127,141,142` (nejvyšší patro `eurobox-sloupec0-patro4`/`patro2` koliduje se stropem). Tohle NEBYLA chyba způsobená tímto auditem (živá DB data před jakoukoli mojí úpravou nezávisle přeměřena a shodovala se s tím, co nahlásila souběžná D/E-varianty session - `id=103` `heightY=1356mm`, 2 kolidující díly na patru4). Kaskádová oprava mezery 30mm (viz výše, VŽDY posouvá dolů) vyřešila všech 6 kolizí jako VEDLEJŠÍ EFEKT - po opravě `id=103` `heightY=1308mm`, 0 kolizí; `id=141/142` `heightY=1258mm`, 0 kolizí. Nezávisle ověřeno explicitně pro `id=103/141/142` k dotazu souběžné session i pro celou dávku 115 řádků (`scripts/tmp_2026-09-01_bot16_full_collision_check.js`) - **0 nových kolizí zavedeno, 0 kolizí zbývá po opravě, u žádného ze 115 řádků.**

**Re-verifikace po opravě (celá dávka, 115/115 řádků):** `crossbar_gap_audit.js` znovu spuštěn nad opravenými daty - **0/427 pater chybí spojnice, 0/282 přechodů má chybnou mezeru** (přesně `30.00mm ±0.01` všude). Rozměrová sanity brána (`heightY` 900-1500mm, `depthX` 250-420mm, žádný díl pod `Y=0`) - 115/115 PASS. Kolizní re-verifikace (viz výše) - 0/115 kolizí.

**Rozsah zásahu:** 115/115 řádků upraveno, 282 pater posunuto, **2098 dílů** (nosníky+spojnice+eurobxy) přemístěno v ose Y. Beze změny X/Z pozic, počtu dílů, výběru katalogových produktů nebo `role` polí - čistě korekce Y.

**Otevřený, mimo mandát tohoto auditu ponechaný nález:** druhá chyba (+50mm, "špatná výška boxu na patru") ukazuje, že u ~10 řádků (B/C/D/E dávky) byl box PŘIŘAZEN patru, které nebylo pro něj postavené (patro bylo naplánováno pro jinou výšku, ale dostalo jinou) - typicky posun/vynechání jedné velikosti v řadě (`id=138`: chybí 270mm box, 170mm duplicitně na dvou patrech). Tahle oprava NEŘEŠILA/nepřerovnávala, KTERÝ box na kterém patře je (to je otázka výběru/diverzity výšek, ne geometrické korektnosti mezery) - jen zaručila, že mezera k dalšímu patru je 30mm bez ohledu na to, jaký box tam je. Pokud má být řešeno i přiřazení výšek (aby odpovídalo původnímu záměru "sestupně 270→220→170→120"), je to samostatný úkol pro navazující práci.

**Podezření na systémový zdroj chyby:** vzhledem k tomu, že +12mm chyba se objevila NAPŘÍČ VŠEMI batch-agenty noční dávky (Proace, Expert, Vito, Berlingo/Partner, Trafic, Custom/Transporter, Caddy/Doblo/Ford Connect, Vivaro, i pozdější B/C/D/E dávky) bez jediné výjimky, jde o chybu SDÍLENOU stavěcí knihovnou/vzorcem (pravděpodobně `railTop += H_box + 30 + T` bez odečtení 12mm nožky), ne o chybu jednotlivého agenta/vozidla - pokud se bude v budoucnu stavět další patrovaný regál stejnou pipeline (`tmp_2026-08-31_batch_pipeline.js`/`tmp_2026-09-01_bc_build.js`/`tmp_2026-09-02_bot16_de_build.js` a příbuzné), je potřeba OPRAVIT vzorec přímo v těchto skriptech, jinak se bug bude opakovat u každé nově postavené sestavy (tahle oprava sanovala jen už uložená data, ne stavěcí kód).

**Skripty:** `scripts/tmp_2026-09-01_bot16_crossbar_gap_audit.js` (audit, real Box3), `scripts/tmp_2026-09-01_bot16_gap_fix_compute.js` (kaskádový výpočet opravy), `scripts/tmp_2026-09-01_bot16_apply_gap_fix.py` (aplikace + SQL generování), `scripts/tmp_2026-09-01_bot16_full_collision_check.js` (before/after kolizní re-verifikace na reálné karoserii, per-řádek `car_bodies` base path odvozen z `car_body_*` id v `data.parts`).

## Zpětný audit + aplikace `shape_geometry_methods.id=8` (výška nohy podle výšky dveří) (bot16, 2026-09-02)

**Shrnutí:** Robertovo nové pravidlo (`prizpusobeni-vysky-nohy-vysce-dveri`, id=8, zapsáno 2026-09-01) žádalo zpětný audit VŠECH hotových eurobox noh - horní konec `predni-svislice` a nejvyššího zadní/wall-side kusu nohy (`cap` pokud existuje, jinak `zadni-svislice-dolni`/`zadni-svislice-nad-zarezem`/generický `zadni-svislice`) má skončit PŘESNĚ na `H_cíl = official_door_opening_height_mm - 30`, spodní okraj (podlaha) beze změny, obousměrně (prodloužení i zkrácení). Výsledek: **115 `is_public=1` řádků zkontrolováno, 74 mělo dostupnou oficiální výšku dveří, z toho 51 opraveno (124 noh), 23 řádků (46 noh) zablokováno skutečnou kolizí s karoserií a NEBYLO změněno, 41 řádků přeskočeno pro chybějící `official_door_opening_height_mm`.**

**Klasifikace geometrie:** stejně jako u předchozích auditů (viz `tmp_2026-09-01_bot16_crossbar_gap_audit.js`) NE podle názvu role, ale podle skutečné Box3 geometrie - napříč 74 řádky se ukázalo, že role `zadni-svislice-dolni`/`zadni-svislice-nad-zarezem` mají u některých dávek generickou variantu `zadni-svislice` (38×, plain noha bez cap kusu, kde zadní svislice má stejnou výšku jako přední) a endcap `zaslepka-*` má někdy generickou variantu `zaslepka` (135×) bez specifické přípony - výběr "nejvyššího wall-side kusu" proto dělán geometrickým argmaxem horního Y mezi kandidáty (`cap`/`zadni-svislice-dolni`/`zadni-svislice-nad-zarezem`/`zadni-svislice`), s `cap` jako preferovanou volbou pokud existuje (přesně podle znění pravidla). Odpovídající `zaslepka` koncovka nalezena geometrickou proximitou (stejný leg-cluster, shodné X, Y blízko aktuálního konce profilu) - offset zaslepky vůči konci profilu zjištěn EMPIRICKY z existujících dat před opravou (vyšlo konzistentně +3mm napříč desítkami vzorků), ne hardcodován, a při přesunu zachován.

**Seskupení do noh:** díly patřící jedné noze sdílejí přesně stejnou Z souřadnici (ověřeno na vzorcích) - použito jako klastrovací klíč místo role-based `sloupecN` (leg-specifické role tenhle index nemají, jen shelf/patro role ho mají).

**Kolizní blokace (23 řádků, 46 noh, vše směr "extend"):** u těchto řádků by protažení nejvyššího wall-side kusu přesně na `H_cíl` způsobilo SKUTEČNOU kolizi s reálnou geometrií karoserie (ověřeno `collision_module_factory.js` proti skutečným `car_bodies` GLB, ne teoreticky) - `predni-svislice` nekolidovala NIKDY, jen kus blíž stěně. Postižená vozidla: Berlingo/e-Berlingo CI16/17/22/23, Transit/E-Transit Custom FO31/38/39/47/48, VW T7 VW25/27 (+ jejich B/C/D/E box-variantové duplikáty). Hypotéza: `official_door_opening_height_mm` je výška u ZADNÍCH dveří, ale tyto nohy sedí na Z-pozici podél boku karoserie dál od dveří, kde strop/střecha může být níž (zakřivení směrem k přídi/nad kolovými oblouky) - 30mm rezerva na těchto konkrétních Z-pozicích nestačí. Tyto řádky ZŮSTÁVAJÍ beze změny (původní geometrie) a čekají na Robertovo rozhodnutí - možný postup: kolizní krokování per-noha stejné jako `shape_geometry_methods.id=6`, místo přímého vzorce `H_cíl`.

**Přeskočeno pro chybějící data (41 řádků):** `official_door_opening_height_mm` je `NULL` v `karoserie_model_reference` (Proace/TO22/TO23 varianty, Berlingo CI03/04, Partner PE02/03/18/19/23/24, Trafic RE28/29, Ford Custom FO21/27/28/29, VW T6/T7 VW11/12, Caddy VW13/14/21/22/31/32 + jejich B/C/D/E duplikáty) - ponecháno beze změny, ŽÁDNÝ neoficiální/webový odhad nepoužit (per zavedená konvence "jen oficiální zdroj u tohoto pole").

**Lůžko-interakce (id=6 princip):** u všech 16 zkracovaných noh (delta ~9.5-10mm, jen Ford Transit/E-Transit Connect FO36/37/45/46) zkontrolováno, zda nejvyšší rail (spojnice/nosník sloupce) nezůstane trčet nad novým koncem nohy - **0 porušení nalezeno** (malé delty, dostatečná rezerva).

**Ověření:** before/after kolizní re-test (jen NOVÉ kolize blokující, pre-existující by byly jen reportovány) na všech 74 kandidátech → zápis do DB pro 51 čistých řádků → nezávislý druhý průchod na FRESH datech z DB potvrdil (a) všech 51 řádků má nyní front-top==wall-top==H_cíl (±2mm), (b) 0 nových kolizí s karoserií, (c) self-kolizní sken (248 kontrolovaných párů) nenašel žádnou neočekávanou profil-profil ani profil-eurobox kolizi, jen očekávané flush styky profil↔vlastní zaslepka. **2D vizuální gate (Robertovo potvrzení ve scéně) NEBYLO touto session provedeno** - `shape_geometry_methods.id=8.verified_by` proto nastaveno na `'bot16'` (numerické ověření), NE na `'robert'` (to je vyhrazeno pro skutečné vizuální potvrzení, viz konvence u id=3/4/6 vs. id=1/2/5/7).

**Rozsah zásahu:** 51 řádků, 124 noh (= 248 měněných dílů: 124× `predni-svislice` + 124× wall-top kus), + odpovídající `zaslepka` koncovky přesunuty spolu s nimi. Beze změny X/Z pozic, ostatních pater/spojnic/přiček, `bom`/`price_summary` (u všech dotčených řádků prázdné, žádná návaznost na přepočet).

**Skripty:** `scripts/tmp_2026-09-02_bot16_leg_height_compute_plan.js` (výpočet plánu - klasifikace noh, H_cíl, delta), `scripts/tmp_2026-09-02_bot16_leg_height_apply_verify.js` (kandidátní mutace + before/after kolizní ověření proti karoserii, zápis `updated_rows.json` jen pro řádky bez nové kolize), `scripts/tmp_2026-09-02_bot16_leg_height_self_collision_check.js` (post-write self-kolizní sken).

## Pokračování `shape_geometry_methods.id=8` na 17 nově doplněných kódech (bot16, 2026-09-02)

**Shrnutí:** Navazuje na výše popsaný zpětný audit id=8 (74 řádků řešeno tehdy, 41 přeskočeno pro chybějící `official_door_opening_height_mm`). Mezitím jiná session (viz `AGENTS_LOG.md` "bot16 — 2026-09-01 — Doplnění chybějících `official_door_opening_height_mm`") dohledala oficiální výšku dveří pro 17 z 23 relevantních kódů. Tato session aplikovala stejné pravidlo id=8 na těchto 17 kódů (čerstvě přečteno z DB, ne přebráno ze staré session). **Nalezeno 29 `product_assemblies` řádků (`is_public=1`, včetně B/C/D/E box-variant duplikátů). Z toho 17 řádků (9 kódů, 41 noh) úspěšně opraveno, 12 řádků (8 kódů, 24 noh) NOVĚ zablokováno skutečnou kolizí s karoserií.**

**Kódy a výsledek:**

| Kód | H_dveří | H_cíl (H−30) | Před | Po | Δ | Řádků | Noh | Výsledek |
|---|---|---|---|---|---|---|---|---|
| OP18 | 1220 | 1190 | 1182.0 | 1190.0 | +8.0 | 1 (id=57) | 3 | opraveno |
| TO22 | 1220 | 1190 | 1182.0 | 1190.0 | +8.0 | 5 (id=64,147,148,169,170 = A/B/C/D/E) | 15 | opraveno |
| TO23 | 1220 | 1190 | 1182.0 | 1190.0 | +8.0 | 1 (id=65) | 2 | opraveno |
| VW13 | 1134 | 1104 | 1082.0 | 1104.0 | +22.0 | 1 (id=122) | 2 | opraveno |
| VW14 | 1134 | 1104 | 1082.0 | 1104.0 | +22.0 | 1 (id=123) | 3 | opraveno |
| VW21 | 1122 | 1092 | 1082.0 | 1092.0 | +10.0 | 1 (id=124) | 2 | opraveno |
| VW22 | 1122 | 1092 | 1081.5 | 1092.0 | +10.5 | 1 (id=125) | 2 | opraveno |
| VW31 | 1122 | 1092 | 1081.5 | 1092.0 | +10.5 | 5 (id=126,143,144,165,166 = A/B/C/D/E) | 10 | opraveno |
| VW32 | 1122 | 1092 | 1081.5 | 1092.0 | +10.5 | 1 (id=127) | 2 | opraveno |
| PE02 | 1148 | 1118 | 1081.0 | — | +37.0 | 1 (id=97) | 2 | **NOVĚ blokováno kolizí** |
| PE03 | 1148 | 1118 | 1081.0 | — | +37.0 | 1 (id=98) | 2 | **NOVĚ blokováno kolizí** |
| PE18 | 1196 | 1166 | 1082.0 | — | +84.0 | 1 (id=99) | 2 | **NOVĚ blokováno kolizí** |
| PE19 | 1196 | 1166 | 1082.0 | — | +84.0 | 1 (id=100) | 2 | **NOVĚ blokováno kolizí** |
| PE23 | 1196 | 1166 | 1082.0 | — | +84.0 | 5 (id=101,139,140,161,162 = A/B/C/D/E) | 10 | **NOVĚ blokováno kolizí** |
| PE24 | 1196 | 1166 | 1082.0 | — | +84.0 | 1 (id=102) | 2 | **NOVĚ blokováno kolizí** |
| VW11 | 1299 | 1269 | 1181.2 | — | +87.8 | 1 (id=116) | 2 | **NOVĚ blokováno kolizí** |
| VW12 | 1299 | 1269 | 1181.7 | — | +87.3 | 1 (id=117) | 2 | **NOVĚ blokováno kolizí** |

Všechny změny směr "extend" (žádné zkrácení mezi těmito 17 kódy) - u čistě prodlužovaných noh odpadá lůžko/rail-containment kontrola (`id=6` princip, relevantní jen při zkracování; `shape_geometry_methods.id=8`-skript to i explicitně přeskakuje pro `direction!=="shorten"`).

**Nově nalezené blokované kódy (8 kódů, 12 řádků, 24 noh):** Peugeot Partner/e-Partner PE02/03/18/19/23/24 a VW Transporter T6 VW11/12 - u všech by protažení nejvyššího wall-side kusu přesně na `H_cíl` způsobilo SKUTEČNOU kolizi s reálnou geometrií karoserie (ověřeno `collision_module_factory.js` proti skutečným `car_bodies` GLB dané konkrétní varianty, ne teoreticky) - stejný vzorec jako u dřívějších 23 blokovaných řádků: `predni-svislice` nekolidovala nikdy, jen kus blíž stěně (`cap`). Tyto řádky **ZŮSTÁVAJÍ beze změny** (původní geometrie, `predni-svislice`/wall-top na 1081-1181mm dle vozidla). Delty u těchto kódů jsou nápadně velké (37-87.8mm) oproti úspěšným kódům (8-22mm) - konzistentní s hypotézou z předchozí session, že u těchto karoserií je 30mm rezerva vůči `official_door_opening_height_mm` nedostatečná na Z-pozici, kde noha skutečně sedí (podél boku, ne přímo v rovině zadních dveří). Přidáno do stejné fronty jako předchozích 23 řádků (Berlingo CI16/17/22/23, Custom FO31/38/39/47/48, VW T7 VW25/27) - čeká na Robertovo rozhodnutí / navazující kolizní-krokovací session (`id=6`-styl řešení).

**Metodika (identická s předchozí 51-řádkovou aplikací, skripty znovupoužity beze změny logiky):**
1. Vendor kód per řádek zjištěn JOINem `car_body_<id>` part refs → `car_bodies.name` → regex zachytávající kód v závorce (tehdejší formát před přejmenováním karoserií 2026-09-06, dle zadání, ne `original_filename` jako u dřívější `leg_ceiling_prep.py` varianty - ověřeno, že obě metody dávají shodné kódy).
2. Klasifikace nohy geometrickým argmaxem horního Y (Box3, ne role-string) mezi `cap`/`zadni-svislice-dolni`/`zadni-svislice-nad-zarezem`/generický `zadni-svislice` - `cap` preferován, pokud existuje.
3. Kandidátní mutace (scale/position přepočet z reálné base-Y-délky dílu) → before/after kolizní test vůči skutečné karoserii (`collision_module_factory.js`) → zápis do DB PROVEDEN JEN pro noze bez nově zavedené kolize.
4. Po zápisu do DB čerstvý re-export z DB (`rows_full_postupdate.json`) → nezávislý druhý průchod potvrdil pro všech 9 úspěšných kódů: (a) nejvyšší bod nohy (`front`/wall-top) == `H_cíl` na reprezentativním řádku každého kódu (±1mm), (b) self-kolizní sken (82 kontrolovaných párů) nenašel žádnou neočekávanou profil-profil kolizi, jen očekávané flush styky profil↔vlastní zaslepka (`zaslepka-predni-svislice`/`zaslepka-cap` vůči rodičovskému profilu - stejný vzorec jako u předchozí 51-řádkové dávky), (c) žádné NaN/invertované Box3.
5. **2D vizuální gate (Robertovo potvrzení ve scéně) NEBYLO touto session provedeno** - stejně jako u předchozí dávky se pro numerické ověření (top-Y přesně na `H_cíl`, žádná kolize, žádná self-kolize) používá `bot16`, ne `robert`, jako `verified_by` konvence - `shape_geometry_methods.id=8.verified_by` beze změny (`'bot16'`, nastaveno již předchozí session, nepřepisováno).

**Rozsah zásahu:** 17 řádků, 41 noh (= 82 měněných dílů: 41× `predni-svislice` + 41× wall-top kus), + odpovídající `zaslepka` koncovky přesunuty spolu s nimi (offset zachován). Beze změny X/Z pozic, ostatních pater/spojnic/přiček, `bom`/`price_summary`.

**Skripty (znovupoužity beze změny z předchozí 51-řádkové dávky, jen s novou vstupní sadou 29 řádků):** `scripts/tmp_2026-09-02_bot16_leg_height_compute_plan.js`, `scripts/tmp_2026-09-02_bot16_leg_height_apply_verify.js`. Nové pomocné skripty pro tuto dávku: `scripts/tmp_2026-09-02_bot16_17codes_selfcollision.js` (post-write self-kolizní sken, adaptace `leg_height_self_collision_check.js` na 17 nových id), `scripts/tmp_2026-09-02_bot16_17codes_gate2d_v2.js` (per-leg top-Y ověření vůči `H_cíl` na reprezentativním řádku každého z 9 úspěšných kódů, NaN/inverted-box sanity).

## Rozřešení blokovaných řádků reálným kolizním krokováním - 35 řádků celkem (bot16, 2026-09-02)

**Shrnutí:** Robert zadal "aplikujme úpravy výšek nohou na příslušné sestavy ve scéně" pro 23 řádků zablokovaných plochým vzorcem `H_cíl` (viz sekce výš, "Zpětný audit + aplikace `shape_geometry_methods.id=8`"). Metoda: přesně stejná jako `shape_geometry_methods.id=6` (protažení zadní svislice výřezové nohy proti podběhu), jen aplikovaná na HORNÍ konec nohy proti skutečné střeše/karoserii místo na spodní konec proti podběhu kola. V půlce práce koordinátor přidal dalších 12 řádků (Peugeot Partner/e-Partner PE02/03/18/19/23/24, VW Transporter T6 VW11/12) nalezených souběžnou relací se stejným blokujícím symptomem - stejná metoda aplikována i na ně beze změny principu. **Celkem 35 řádků, 70 noh:**

- **18 z 35 řádků (36 noh) zůstalo BEZE ZMĚNY** - celá rodina Berlingo/e-Berlingo (CI16/17/22/23) a Partner/e-Partner (PE02/03/18/19/23/24): skutečná kolize je jen 6-13mm nad původním topem, takže po 20mm zpětném odskoku vychází bezpečný strop NÍŽE než původní geometrie (reálný zisk = 0).
- **17 z 35 řádků (34 noh) bylo skutečně prodlouženo** na nový, reálně ověřený `H_max_safe`: Transit/E-Transit Custom (FO31/38/39/47/48) a VW T7 (VW25/27) - 15 řádků; VW T6 (VW11/12) - 2 řádky.

**Metoda kolizního krokování (per noha, per kus):** drž SPODNÍ konec wall-side kusu (`cap`/`zadni-svislice-dolni`/`zadni-svislice-nad-zarezem`/generický `zadni-svislice`) fixní, posouvej HORNÍ konec nahoru po 1mm od současného topu, testuj `collidesWithWalls` (`scripts/2026-09-01_collision_module_factory.js`, stejný produkční modul jako celá tahle rodina auditů) na reálné GLB karoserii, až po `H_cíl` (hard cap - dál nemá smysl chodit, i kdyby nekolidovalo). Při první kolizi (`collideY`) `Y_new = collideY - 20` (20mm zpět), ověřeno, že `Y_new` skutečně nekoliduje (a pokud náhodou ano, dojet dál 1mm dolů, dokud čisté). `H_max_safe = min(Y_new, H_cíl)`. **Nezávisle totéž i pro `predni-svislice`** (úkol výslovně žádal neověřovat naslepo předchozí zjištění "přední svislice nikdy nekoliduje") - potvrzeno, že drží i tady: na všech 70 nohou `frontCeiling == H_cíl` (přední svislice nikdy nenarazila dřív než `H_cíl`), takže `H_max_safe` je vždy určen wall-side kusem.

**Volba 20mm, ne 2mm zpětného odskoku:** tahle operace je "protáhni profil nohy k reálné kolizní hranici", stejná třída jako `id=6` (explicitně 20mm, "Robert explicitne zadal 20mm pro tenhle konkretni krok") a `car_body_placement_methods.id=1.max_rozpon_nohou` (taky explicitně 20mm, "POZOR: tady 20mm, ne standardnich 2mm") - NE stejná třída jako `id=1`'s základní 4 kroky jednorázového umístění UŽ hotového tvaru do karoserie (tam 2mm, pro těsné dosednutí na plochu/podlahu/stěnu). Zadání úkolu samo odkazovalo na `id=6` jako přesný vzor k použití, takže 20mm je jednoznačná volba, potvrzená oběma existujícími precedenty.

**Front a wall stejné nohy se zvedají na STEJNÝ finální top** (drženo level, jako před zpětným auditem), ale **dvě nohy TÉHOŽ sloupce/regálu mohou skončit na RŮZNĚ vysoké úrovni** - ověřeno před aplikací, že v této sestavě žádný nosník/spojnice nespojuje samotné TOPY sousedních noh (jen nižší patrové spojnice, hluboko pod novými topy), takže nerovnoměrné konce jsou bezpečné a neporušují žádný spoj.

**Reálná čísla (H_max_safe vs. blokovaný H_cíl), potvrzují hypotézu "strop klesá směrem od dveří" - a ukazují, že klesá VELMI nerovnoměrně mezi modely i mezi nohama téhož vozidla:**

| Vozidlo (starý kód) | noha z≈ | původní top | H_cíl (blokováno) | **H_max_safe (reálné)** | reálný zisk |
|---|---|---|---|---|---|
| Berlingo/e-Berlingo CI16/17/22/23 | obě nohy | 1082 | 1107 | **1082 (beze změny)** | 0mm |
| Partner PE02/PE03 | obě nohy | 1081 | 1118 | **1081 (beze změny)** | 0mm |
| Partner/e-Partner PE18/19/23/24 | obě nohy | 1082 | 1166 | **1082 (beze změny)** | 0mm |
| Transit/E-Transit Custom FO31/38/39/47/48, VW T7 VW25/27 | noha blíž kabině (z≈-2250/-2650) | 1181.3 | 1284/1286 | **1186-1187** | +4.7 až +5.7mm |
| Transit/E-Transit Custom FO31/38/39/47/48, VW T7 VW25/27 | noha dál od kabiny (z≈-1388/-1787) | 1181.3 | 1284/1286 | **1257** | +75.7mm |
| VW T6 VW11/VW12 | obě nohy | 1181.2-1181.7 | 1269 | **1213** | +31.3 až +31.8mm |

U Berlingo/e-Berlingo/Partner rodiny je zjištění extrémnější, než hypotéza čekala - není to jen "menší rezerva", ale prakticky ŽÁDNÁ rezerva (6-13mm skutečné vzdálenosti do kolize, méně než samotný 20mm bezpečnostní odskok). U Transit/VW T7 rodiny hypotéza platí v mírnější podobě, ALE s velkým rozdílem MEZI dvěma nohama téhož vozidla (5mm vs. 76mm). U VW T6 je zisk naopak ROVNOMĚRNÝ mezi oběma nohama (~31-32mm na obou) - potvrzuje, že i SAMOTNÁ nerovnoměrnost zisku mezi nohama je vlastnost konkrétního modelu karoserie, ne univerzální pravidlo (stejný princip jako `id=6`'s zjištění, že se tvar podběhu mění noha od nohy, tady navíc platí i pro TVAR nerovnoměrnosti samotné).

**Ověření:** `collidesWithWalls` before/after na všech 4 dotčených kusech (front/wall/2×zaslepka) každé měněné nohy - 0 nových kolizí. Self-kolizní sken (`shrink(2mm)` box overlap proti všem ostatním ne-karoserie dílům v řádku) - jediné nalezené překryvy jsou očekávané vlastní flush styky profil↔zaslepka (stejná konvence jako předchozí audity), 0 neočekávaných. Nezávislý druhý průchod na FRESH datech přímo z DB (ne z mezivýsledků) potvrdil u všech 34 změněných noh: `front-top == wall-top == H_max_safe` (±1mm), 0 kolizí s karoserií, 0 neočekávaných self-kolizí. Lůžko/rail-containment (princip `id=6`) se u téhle dávky netýká - všech 70 noh je směr `extend` (top se jen zvedá), což nikdy nemůže odtrhnout rail nad koncem nohy (kontrola relevantní jen pro `shorten`, viz `compute_plan.js`); navíc ověřeno, že žádný rail v této sestavě nespojuje TOPY sousedních noh napříč Z (viz výš). **2D půdorys+nárys gate** (reálný Box3, before/after, per vozidlo) vygenerován a publikován JAKO ARTEFAKT před zápisem do DB, aktualizován po rozšíření o batch 2: https://claude.ai/code/artifact/18044b68-1fa6-44e9-924b-7e3050ec9c6c

**`shape_geometry_methods.id=8`:** `version` 2→3→4 (batch 1, pak batch 2), přidán klíč `refinement_2026_09_02_bot16_kolizni_krokovani_23_radku` (+ vnořený `dodatek_batch2_partner_vw_t6_2026_09_02`) s plným rozpisem metody a výsledků obou dávek. `verified_by` beze změny (`'bot16'`, ne `'robert'`) - **Robertovo vizuální potvrzení ve scéně této konkrétní dávky 17 řádků ještě NEPROBĚHLO**, jen numerické ověření.

**Rozsah zásahu:** 17 řádků skutečně změněno (34 noh = 136 měněných dílů: 34× `predni-svislice` + 34× wall-top kus + 68× odpovídající `zaslepka`), 18 řádků (36 noh) ověřeno a ponecháno beze změny (žádný reálný prostor k prodloužení). Beze změny X/Z pozic, ostatních pater/spojnic/přiček, `bom`/`price_summary`.

**Skripty batch 1 (23 řádků: Berlingo/e-Berlingo, Custom, VW T7):** `scripts/tmp_2026-09-02_bot16_leg_ceiling_prep.py`, `_stepping.js`, `_apply.js`, `_selfcollision.js`, `_render2d.js`, `_write_db.py`, `_verify_fresh.js`, `_update_sgm8.py`, `_diag*.js` (spolehlivostní diagnostika `collidesWithWalls`, viz níže). **Skripty batch 2 (12 řádků: Partner/e-Partner, VW T6, přidané v půlce session):** stejné skripty se suffixem `2` (`_prep2.py`, `_compute_plan2.js`, `_stepping2.js`, `_apply2.js`, `_selfcollision2.js`, `_write_db2.py`, `_verify_fresh2.js`, `_update_sgm8_batch2.py`) - použity unikátní `bot16d_*` názvy mezisouborů od začátku (viz poznámka o souběžnosti níže).

**Poznámka ke spolehlivosti `collidesWithWalls` (ověřeno explicitně před důvěrou ve výsledky):** hraně-křížící raycasting metoda má známý false-negative artefakt při objektu CELÉM za hranicí (viz nález "de_diag" v `AGENTS_LOG.md`, 2026-09-02) - netýká se ale kolizního krokování ZDOLA (vždy startuje ze známé bezkolizní pozice a jde po 1mm nahoru, takže se nemůže "přeskočit" přes tenkou stěnu bez zachycení). Spot-check na CI16 noze (z=-1358.2): `collidesWithWalls` na Y=[1080,1082,...,1093]=false, Y=[1094,...,1200]=true - čistý, stabilní přechod přesně v jednom bodě, potvrzuje, že jde o skutečnou fyzickou hranici (boční stěna se zakřivuje dovnitř směrem ke střeše), ne o ojedinělý falešný zásah jednoho trojúhelníku.

**Souběžnost a poučení o sdílených mezisouborech:** tahle session sdílela `scratchpad` adresář s jinou souběžně běžící `bot16` relací (dohledávala chybějící `official_door_opening_height_mm` u ~41 jiných vozidel, viz `TASKS.md`/commity `3fa0a06` a následující) - obě relace zdědily STEJNÉ obecné skripty z předchozí 74/115-řádkové dávky (`rows_full.json`/`rows_meta.json`/`car_body_glb.json`/`plan.json` jako pevně zapsané generické názvy uvnitř sdílených skriptů), což způsobilo, že tyhle mezisoubory byly v půlce práce přepsány druhou relací jejími vlastními daty. Nezpůsobilo to žádnou chybu v zápisu (DB zápis `write_db.py`/`write_db2.py` čte kandidátní data z vlastních `ceiling_updated_rows*.json` souborů, které kolize nepotkaly, a navíc vždy čte FRESH `data` z DB těsně před zápisem a mění jen konkrétní dotčené indexy), ale VYŽÁDALO si přejmenování zbylých mezikroků na kolizi-odolné `bot16c_*` názvy pro nezávislé druhé ověření batch 1. Batch 2 proto od začátku použil unikátní `bot16d_*` názvy. Poučení pro příště: sdílené obecné skripty používající pevně zapsané generické názvy souborů ve `scratchpad` NEJSOU bezpečné pro souběžné použití dvěma relacemi zároveň - nový bot přebírající tenhle vzor by měl svoje mezisoubory pojmenovávat jedinečně od začátku.

## OPRAVA: přední noha (celý 1. sloupec) uvnitř otvoru bočních posuvných dveří - FO31 + VW25, 10 řádků (bot16, 2026-09-02)

**Shrnutí:** Nezávisle ověřený nález - Ford Transit Custom L2 FO31 a VW Transporter T7 VW25 (5 výškových variant A-E každé, `product_assemblies.id=111/153/154/175/176` a `118/155/156/177/178`) měly CELÝ první sloupec regálu (obě nohy, nosníky, spojnice, boxy) postavený uvnitř SKUTEČNÉHO otvoru bočních posuvných dveří v `_R_D.glb` - žádný materiál v místě nohou, ne jen "volný prostor u zdi". Celá sestava u obou vozidel přestavěna od nového předního kotevního bodu (konec dveřního otvoru + 30mm) směrem k reálné zadní kolizi karoserie, se stejnou metodikou jako všechny předchozí regály (`shape_geometry_methods.id=1/3/4/5/6/7/8`), a znovu zapsána do všech 10 řádků. Nová obecná detekční metoda (mezera v `_R_D` meshi) zapsána do `car_body_placement_methods.id=1` jako trvalé pravidlo pro VŠECHNY budoucí regály na bočních stěnách, ne jen tahle dvě vozidla.

**Root cause - proč tohle `car_body_placement_methods.id=1` kolizní krokování samo o sobě neodhalilo:** dosavadní postup (`tmp_2026-08-31_batch_pipeline.js`, STEP1) kotví přední nohu kolizním krokováním PROTI PŘEPÁŽCE B (`dirZtoBulkhead` směr) - najde přesně konec přepážky a zastaví se těsně u ní. U FO31/VW25 ale hned ZA přepážkou (ve směru od kabiny) následuje otvor bočních posuvných dveří (žádný materiál), takže noha umístěná "těsně u přepážky" skončila hluboko uvnitř tohohle otvoru. Kolizní test (`collidesWithWalls`) na tomhle místě SPRÁVNĚ hlásí "žádná kolize" - fyzicky tam opravdu nic není - ale "žádná kolize" tady neznamená "bezpečné místo pro nohu", znamená "funkční otvor pro dveře". Tohle je odlišná třída chyby než dosavadní `id=1` nálezy (proházené X-znaménko, izolovaný ostrov podběhu) - není to chyba VE výpočtu kolize, je to chybějící DRUHÝ typ omezení (vyloučená zóna), který kolizní test principiálně nemůže sám odhalit.

**Nezávislé ověření vstupních čísel (ne převzato naslepo ze zadání):** vlastní sken `_R_D.glb` obou vozidel (Y∈[200,900], hledání mezery >150mm mezi Z-seřazenými vertexy) potvrdil zadání téměř přesně:

| Vozidlo | dveřní otvor Z (nalezeno) | šířka | konec přepážky `_B.glb` |
|---|---|---|---|
| Ford Custom FO31 | [-2666.11, -1695.75] | 970.36mm | -2666.04 |
| VW Transporter VW25 | [-2266.08, -1295.75] | 970.33mm | -2266.04 |

Nový přední kotevní bod = vzdálenější hrana otvoru + 30mm: **FO31 Z=-1665.75, VW25 Z=-1265.75** (obojí ~0.05mm od zadání - v mezích přesnosti vertex-skenu).

**Přestavba (`scripts/tmp_2026-09-02_doorvoid_pipeline.js` + `_assemble.js`):** kroky 2-7 (max rozpon vč. lookahead přes izolovaný ostrov podběhu, sloupcové plnění nejšíršího-nejdřív, protažení výřezové zadní nohy, rail floor přes celý rozpon, fyzický strop) jsou 1:1 převzaté z `tmp_2026-08-31_batch_pipeline.js`, jen STEP1 (Z-kotva) nahrazen fixní hodnotou z dveřního skenu místo kolizního hledání přepážky. Výsledek u obou vozidel: **jen 1 sloupec** (širší než dřív - FO31 N=3/1232mm rozpětí, VW25 N=2/832mm), 2 nohy (přední `plain` u nového kotevního bodu, zadní `vyrez` u podběhu, obě vozidla shodně na Z≈-403.7 - stejná platforma "project Cyclone").

**Nový nález, mimo dosavadní zkušenost s touhle rodinou regálů - fyzický strop NÍŽ než standardní `TOP_Y`=920mm limit:** na nové (posunuté) pozici vyšel `physCeil` FO31=863mm, VW25=887mm - OBOJÍ POD 920mm, na rozdíl od všech dosavadních vozidel/pozic (kde `physCeil` byl vždy ≥920mm, typicky 922-1045mm). Původní `planColumn()` z `tmp_2026-08-31_batch_pipeline.js` tohle nepočítalo se správně (kontrolovala `physCeil` jen pro POSLEDNÍ patro, neposlední patra jen proti `TOP_Y`) - opraveno v `tmp_2026-09-02_doorvoid_assemble.js::planColumn` na `effLimit = min(TOP_Y, physCeil)` platný pro VŠECHNA patra. **Důsledek zjištěný nezávislým vyčerpávajícím prohledáním všech nerostoucích kombinací výšek**: v tomhle užším prostoru (480mm FO31, 505mm VW25 rozpočtu mezi podlahou a stropem) NELZE fyzicky dosáhnout 3 různých výšek boxů v jednom sloupci současně (minimální součet 3 různých výšek z {120,170,220,270} je 510mm, nad rozpočtem obou vozidel) - zdokumentováno jako fyzický limit, ne jako nedodržený požadavek (viz `WORKFLOW.md` bod o kapacitě "uprav počet pater podle skutečné kapacity").

**`shape_geometry_methods.id=7` (úhelníky) a `id=8` (výška nohy dle výšky dveří) aplikovány na NOVOU geometrii** (ne převzaty ze staré) - `applyUhelnikyToLeg()` na obou nohách všech 10 řádků (4 spoje/noha nalezeny a umístěny), a id=8 reálným 1mm kolizním krokováním (20mm odskok, strop `H_cíl=official_door_opening_height_mm-30`) na `predni-svislice` i `cap` každé nohy. **Zajímavý kontrast oproti dřívější aplikaci id=8 na STARÉ (chybné) pozici** (viz sekce výš "Rozřešení blokovaných řádků..."): tam noha blíž kabině dosáhla jen `H_max_safe≈1186mm` (zisk 5mm) a vzdálenější noha `≈1257mm` (zisk 76mm), obě POD `H_cíl`. Na NOVÉ pozici (za dveřním otvorem) OBĚ nohy OBOU vozidel dosáhly PLNÉHO `H_cíl` (1284mm FO31, 1286mm VW25) BEZ JAKÉKOLI kolize - výrazně víc rezervy na střeše než blíž kabině/dveřím, fyzikálně smysluplné (střecha se zaklání směrem k přednímu skanu/dveřím, ne uprostřed nákladového prostoru).

**Před/po - přesná čísla všech 10 řádků** (výšky sestupně zdola nahoru, N=boxů na patro; fyzický strop/floor viz výš, shodný pro všech 5 variant každého vozidla):

| Řádek | Vozidlo | Varianta | Před (boxy, výšky) | Po (boxy, výšky) |
|---|---|---|---|---|
| 111 | FO31 | A | 4× [270,220] | **6× [270,120]** |
| 153 | FO31 | B | 6× [270,220,120] | **6× [220,170]** |
| 154 | FO31 | C | 6× [220,170,120] | **6× [220,120]** |
| 175 | FO31 | D | 6× [220,170,120] | **6× [170,120]** |
| 176 | FO31 | E | 8× [120×4pater] | **9× [120×3patra]** |
| 118 | VW25 | A | 4× [270,220] | **4× [270,170]** |
| 155 | VW25 | B | 6× [270,220,120] | **4× [270,120]** |
| 156 | VW25 | C | 6× [220,170,120] | **4× [220,170]** |
| 177 | VW25 | D | 6× [220,170,120] | **4× [220,120]** |
| 178 | VW25 | E | 8× [120×4patra] | **6× [120×3patra]** |

FO31 vyšel u většiny variant STEJNĚ nebo VÍC boxů (širší sloupec N=3 kompenzoval nižší strop) - jen VW25 (N=2, méně "šířky na vykompenzování") vyšel u B/C/D/E skutečně méně boxů, jak zadání předjímalo. Rozměry sestavy (skutečný `Box3` ze všech `Object_7` profilů, shodné pro všech 5 variant daného vozidla): FO31 326×1283×1292mm (hloubka×výška×délka), VW25 326×1285×892mm.

**Ověření (mandatory gate, u VŠECH 10 řádků):** (a) 0 kolizí s reálnou karoserií (`collidesWithWalls`, three-mesh-bvh) na KAŽDÉM dílu samostatně - profily, boxy, záslepky i úhelníky; (b) 0 neočekávaných self-kolizí (jen očekávané styky díl↔vlastní záslepka/úhelník do rohu profilu); (c) nezávislý DRUHÝ průchod na FRESH datech přečtených přímo z produkční DB PO commitu (`fresh_after_<id>.json`, samostatná instance kolizního enginu, samostatně napsaná self-kolizní logika, ne sdílený kód z prvního běhu) - 10/10 PASS; (d) dimenzní sanity brána (výška 1000-1400mm, hloubka 280-400mm); (e) explicitní kontrola "celá sestava leží mimo dveřní otvor" (min. Z všech dílů ≥ vzdálenější hrana otvoru) na fresh datech - 10/10 PASS. 2D půdorys+nárys ze skutečné GLB geometrie (mm, barevně podle výšky boxu, dveřní otvor vyznačen) publikován jako artefakt PŘED shrnutím: https://claude.ai/code/artifact/71736625-e0ae-47cd-9630-4894fc6ccaf9

**Nový klíč `car_body_placement_methods.id=1.vylouceni_bocniho_dvernich_otvoru_2026_09_02`** (`version` 9→10, `verified_by` beze změny `'robert'` - existující konvence tohohle řádku, kde numerické doplňky přidávané boty ponechávají verified_by z původního schváleného jádra metody, viz i `mirror_x_pro_stenu_na_zaporne_strane_2026_08_31` výš): obecný popis detekční metody (mezera >150mm mezi Z-seřazenými vertexy v Y∈[200,900] v `_R_D` souboru) a pravidla (nová kotva = vzdálenější hrana otvoru + 30mm) - platí pro VŠECHNY budoucí regály na boční stěně, ne jen FO31/VW25.

**`verified_by` u samotných 10 řádků:** `product_assemblies` nemá vlastní `verified_by` sloupec - číselné ověření (kolize/self-kolize/sanity/fresh-read) je HOTOVÉ a zdokumentované výš, ale Robertovo VIZUÁLNÍ potvrzení ve scéně (`.claude/skills/3d-scena-spoje` bod 8) ještě NEPROBĚHLO - žádný z 10 řádků nelze považovat za finálně schválený, dokud si je Robert neprohlédne přímo v konfigurátoru ("Produktové sestavy" → "Vložit tvar", karoserie FO31/VW25).

**Otevřeno pro navazující práci:** (1) samotný `tmp_2026-08-31_batch_pipeline.js` (a `bc_build.js`/`de_build.js` odvozené skripty) POŘÁD kotví přední nohu jen proti přepážce, bez kontroly dveřního otvoru - kterákoli JINÁ karoserie, kde dveřní otvor začíná hned za přepážkou (ne jen FO31/VW25), může mít STEJNOU chybu, dosud neauditováno napříč zbylými ~113 `is_public=1` regály. Doporučeno: spustit dveřní sken (nový klíč `id=1` výš) jako předběžnou kontrolu na všech vozidlech s postaveným regálem, než se pipeline použije na další nové auto. (2) `planColumn()` oprava (`effLimit=min(TOP_Y,physCeil)` pro všechna patra, ne jen poslední) je taky jen v NOVÉM `tmp_2026-09-02_doorvoid_assemble.js`, ne v původním `tmp_2026-08-31_batch_pipeline.js` - stejné riziko zůstává i pro budoucí vozidla s `physCeil<920mm`.

**Skripty:** `scripts/tmp_2026-09-02_doorvoid_pipeline.js` (STEP1 fixní kotva z dveřního skenu + STEP2-7 převzaté), `scripts/tmp_2026-09-02_doorvoid_assemble.js` (skladba pater s opraveným `effLimit`, id=7 úhelníky, id=8 výška nohy dle dveří), `scripts/tmp_2026-09-02_doorvoid_build_all.js` (postaví a ověří všech 10 řádků), `scripts/tmp_2026-09-02_doorvoid_independent_verify.js` a `_final_fresh_verify.js` (nezávislé druhé průchody), `scripts/tmp_2026-09-02_doorvoid_gen_sql.js` (SQL generování s escapováním).

## Caddy Cargo/Cargo Maxi (PHEV) VW21/22/31/32 — zadní noha protažena přes podběh ke skutečné zadní hraně (bot24, 2026-09-02)

**Shrnutí:** Robert po zhlédnutí Caddy Cargo PHEV regálu: "musí pokraCOVAT PRES PODBĚH DOZADU, i když podběh nekončí" - zadní noha u celé novější generace Caddy (VW21 `id=124`, VW22 `id=125`, VW31 `id=126` + varianty B/C/D/E `id=143/144/165/166`, VW32 `id=127`) se stavěla jako `plain` typ a stavba se zastavovala 745-944mm před skutečnou zadní hranou karoserie, protože kolizní krokování falešně vyhodnotilo první nárůst podlahy (podběh) jako "konec vozidla". Opraveno: zadní noha nyní `vyrez` typu, protažená reálným kolizním krokováním (`shape_geometry_methods.id=6`) přes CELÝ podběh až ke skutečné zadní kolizi karoserie. **Výsledek: 8/8 řádků opraveno, gain 898-1194mm délky, 0 kolizí (before/after i nezávislý fresh druhý průchod), min. 3 odlišné výšky boxů na každém řádku.** 2D ověřovací artefakt (skutečná Box3 geometrie, staré vs. nové díly): https://claude.ai/code/artifact/4f830a3c-00ed-4b44-b2b3-7bbdfd717397

**Kořenová příčina (přesně zjištěná, ne jen odhad):** starší pipeline (`scripts/tmp_2026-09-01_bot16_run_pipeline.js`, STEP2) hledala `REAR_ANCHOR_Z` krokováním CELÉ vyrezové nohy (s pevnou katalogovou `CUTOUT_H_design=330mm`) dozadu - jakmile hloubka podběhu překročila 330mm, spodní díl `sloupek-pred-podbehem` (ten vždy sahá až k podlaze, Y=[0,CUTOUT_H]) zkoliduje s podlahou/podběhem a pipeline to vyhodnotí jako "tady končí vozidlo", i když podběh ve skutečnosti pokračuje o stovky mm dál. U Caddy PHEV/Cargo (nová 5. generace, kratší/strmější podběh než starší VW13/VW14) se tahle chyba spustila hned u obou fyzických variant karoserie (SWB VW21/31 i LWB VW22/32).

**Nezávislé ověření profilu podlahy/podběhu (per karoserie, jak žádalo zadání):** VW21 a VW31 sdílí IDENTICKÝ půdorys (nezávisle přeměřeno, ne převzato - shodné `frontAnchorZ≈-1477`, shodný podběhový profil), stejně VW22/VW32 (LWB, `frontAnchorZ≈-1890`). Jemný sken po 25mm (`Y firstCollideYfromTop` = nejnižší bod, kde tenký plátek koliduje, skenováno odshora) odhalil na OBOU karoseriích **dva samostatné lokální vrcholy podběhu/překážky oddělené úzkou (75-150mm) zcela čistou kapsou** - první vrchol (kolo), krátká čistá mezera, druhý vrchol (pravděpodobně oblast zadního nárazníku/výztuhy), pak prázdný prostor (mimo modelovanou geometrii, `boxL0.max.z≈61mm` SWB / `≈100mm` LWB). Kapsa mezi vrcholy je užší než minimální šířka jednoho boxového slotu (430mm) - nemá praktickou hodnotu pro další sloupec, takže zastavení PŘED prvním vrcholem (ne prostup až za druhý) je správné inženýrské rozhodnutí, ne nedotažené hledání (stejný vzor jako dřívější nález "podběh jako izolovaný ostrov", Ford Custom FO11, `car_body_placement_methods.id=1.max_rozpon_nohou`).

**Oprava (implementace, `scripts/2026-09-02_bot24_caddy_podbeh_fix.js`):**
1. **Adaptivní vyrez na KAŽDÉ kandidátní Z pozici** - `adaptVyrezAt(z)` počítá `Y_new_wall` (kam nejníž smí sáhnout `zadni-svislice-nad-zarezem`, X blízko stěně) FRESH, full-range scan `0..TOP_Y` (ne jen od katalogové `CUTOUT_H_design` dolů - podběh u nové generace potřeboval větší cutout, než katalogový vzor předpokládal), a případně i `sloupek-pred-podbehem` (pokud by i ten kolidoval na svém původním `[0,Y_new_wall]` rozsahu - u VW22/32 skutečně kolidoval, řešeno druhou aplikací stejné id=6 logiky, `sloupekBottom=480mm`). Nová `pricka-uzavreni-vyrezu` (role dle `shape_geometry_methods.id=4`) uzavírá nový šev.
2. **Existence-probe pro rychlé hledání skutečné zadní hranice** - místo volání drahého plného 0..TOP_Y scanu na každém z tisíců 1mm kroků, levný test: tenký pás TĚSNĚ POD STROPEM (`TOP_Y-40..TOP_Y`) na wall-side X pozici + samostatný test kusu `cap` (fixní pozice blízko stropu/střechy). Skutečná zadní stěna/roh karoserie zablokuje TENHLE pás, podběh kola (i hluboký) ho typicky nikdy nezablokuje.
   - **Past nalezená při aplikaci** (zapsáno i do `car_body_placement_methods.id=1`): u VW22/32 byl to `cap` kus, NE podběh podlahy, kdo limitoval skutečnou zadní hranici o dalších ~120mm hloub - existence-probe musí testovat VŠECHNY fixní-pozice kusy nohy, ne jen jeden.
⚠️ **Body 3-4 PŘEKONÁNY 2026-09-17** (Robert: „začíná se stavět nejdříve 3boxový sloupec, pokud nevyjde staví se kratší 2boxový resp 1boxový... čím více nohou tím je dražší“; souvislý postup krok 6): šířky vždy 1232/832/430 v pořadí 3→2→1 bez ohledu na typ nohy, poslední noha se k hranici NEdotahuje na nestandardní šířku.
3. **Dvoufázové greedy plnění sloupců** - fáze A: pouze `plain` nohy, nejširší sloupec první (efektivní využití ROVNÉ podlahy). Fáze B: `vyrez` nohy, NEJUŽŠÍ sloupec první (N=1, ne nejširší) - široký (1232mm) skok by hladově spotřeboval CELOU zbývající hloubku podběhu v jednom kroku a nechal jen 1 patro/box, zatímco užší skoky umožní víc, kratších sloupců s vlastní (vyšší) podlahou blíž realitě na dané Z - přímo naplňuje "využij nově získanou délku".
4. **STEP3b - dotažení poslední nohy k reálné hranici** (`car_body_placement_methods.id=1.max_rozpon_nohou`, 1mm kroky/20mm odskok) - diskrétní šířky sloupců (430/832/1232mm) zřídka trefí přesně na fyzickou hranici, tenhle krok využije zbytek.

**Čísla před/po (8 řádků):**

| id | Vozidlo | Z stará (part) | Z nová (part) | Zisk | Sloupce | Boxy staré→nové | Výšky po |
|---|---|---|---|---|---|---|---|
| 124 | Caddy Cargo VW21 | -1003.0 | -104.0 | **+899mm** | 1→2 | 3→4 | 270,220,170 |
| 125 | Caddy Cargo Maxi VW22 | -1415.0 | -221.0 | **+1194mm** | 1→3 | 3→6 | 270,220,170,120 |
| 126 | Caddy Cargo PHEV VW31 (A) | -1002.0 | -104.0 | **+898mm** | 1→2 | 3→4 | 270,220,170 |
| 127 | Caddy Cargo Maxi PHEV VW32 | -1415.0 | -221.0 | **+1194mm** | 1→3 | 3→6 | 270,220,170,120 |
| 143 | Caddy Cargo PHEV VW31 B | -1002.0 | -104.0 | +898mm | 1→2 | 3→4 | 270,220,170,120 |
| 144 | Caddy Cargo PHEV VW31 C | -1002.0 | -104.0 | +898mm | 1→2 | 3→4 | 220,170,120 |
| 165 | Caddy Cargo PHEV VW31 D | -1002.0 | -104.0 | +898mm | 1→2 | 3→4 | 220,170,120 |
| 166 | Caddy Cargo PHEV VW31 E | -1002.0 | -104.0 | +898mm | 1→2 | 3→4 | 220,170,120 |

Nová geometrie pro VW31 (126) je nová báze: legy `predni-svislice`(front, nezměněno) + PLAIN mezi-noha (nová, u floor=0, 3 patra 270/220/170) + VYREZ zadní noha (nová, floor=564mm, 1 patro 220mm). VW21 identické (jiná karoserie, nezávisle přepočítáno, shodné výsledky). VW22/32 mají 3 sloupce (1 plain + 2 vyrez, floor 0/303/644mm), 4 odlišné výšky. Variant B/C/D/E na VW31 přebírá STEJNOU novou nohovou/rail geometrii (fixní, beze změny) a jen mění, která výška eurobxu sedí na kterém již ověřeném slotu (pravidlo "nová výška ≤ původní výška slotu" - žádný nový kolizní test floor/rail není potřeba, jen fresh eurobox-vs-karoserie test u KAŽDÉ varianty).

**Ověřovací baterie (splněno na všech 8 řádcích):** (a) 0 kolizí profilů/euroboxů/zaslepek s reálnou karoserií - per díl, uvnitř `runVehicle()` při stavbě; (b) 0 neočekávaných self-kolizí (jen očekávané nesting styky díl↔vlastní zaslepka); (c) **nezávislý druhý průchod** - samostatný proces/skript (`scripts/2026-09-02_bot24_verify_final.js`), samostatně napsaná kolizní/self-kolizní logika, čtení FRESH dat přímo z DB PO zápisu (ne z cache) - 8/8 PASS, 0 kolizí, 0 self-kolizí; (d) min. 3 odlišné výšky boxů na regál - splněno na všech 8 (VW21/31/143/144/165/166 mají 3, VW22/32 mají 4); (e) 2D sanity gate (skutečná Box3 geometrie, mm mřížka, staré vs. nové díly) publikováno PŘED zápisem do DB.

**Otevřeno pro navazující práci / Robertovo vizuální potvrzení:**
1. **Robertovo vizuální potvrzení ve scéně NEPROBĚHLO** - `verified_by` zůstává `bot24`, dokud Robert regály nezkontroluje přímo v konfigurátoru (numerické ověření samo nestačí, viz `WORKFLOW.md`/`.claude/skills` konvence).
2. `physCeil` (fyzický strop) u VW31 (SWB) vyšel v FALLBACK větvi (1635mm) místo reálné kolize (na rozdíl od VW21, který dal reálnou hodnotu 850mm na STEJNÉM fyzickém autě) - nekritické (nebyl to limitující faktor v žádné z 8 sestav), ale stojí za doladění (možná souvislost s PHEV offsetem `[0,-1651.5,0]`, scan 2800 kroků nemusí stačit při velkém posunu).
3. Nový sloupec nad podběhem (`col1`/`col2`) má u SWB (VW21/31) jen 1 patro (220mm) kvůli omezenému vertikálnímu prostoru pod stropem designu (`TOP_Y=840mm`) - teoreticky by užší/jiná noha (mimo rozsah tohoto zadání) mohla otevřít víc prostoru, nezkoumáno.
4. Obecné poučení zapsáno do `car_body_placement_methods.id=1` (klíč `podbeh_bez_konce_2026_09_02`, `version` 10→11, `verified_by` beze změny `'robert'`).

**Skripty:** `scripts/2026-09-02_bot24_caddy_podbeh_fix.js` (hlavní build - fáze A/B, existence-probe, STEP3b, adaptivní vyrez), `scripts/2026-09-02_bot24_caddy_vw31_variants.js` (B/C/D/E na fixní nové geometrii), `scripts/2026-09-02_bot24_verify_final.js` (nezávislý druhý průchod, fresh z DB), `scripts/2026-09-02_bot24_gen_2d_data.js` (Box3 data pro 2D artefakt).

## Celokatalogový audit tříd chyb 1-6 (bot26, 2026-09-03)

Robert (přes koordinátora) zadal ucelený audit+opravu přes CELÝ katalog (115 `is_public=1` řádků `product_assemblies` k tomuto datu, ne jen 113 jak zadání odhadovalo) na PĚT dřív popsaných tříd chyb + NOVOU třídu 6 (nevyužitý svislý prostor pod stropem, zadáno dodatečně stejnou prioritou). Systematický skript pro každou třídu, žádná heuristika na jméně - vždy reálná GLB geometrie (`parseGlbMesh`/`glbBoundingBox`, `THREE.Box3` na skutečně transformovaném meshi).

**Výsledek v kostce:** třídy 5 a 6 kompletně auditovány A opraveny s nezávislým druhým průchodem na FRESH datech z DB. Třída 4 má nově zobecněnou/ověřenou detekční metodu a přesný seznam kandidátů, ale NEBYLA automaticky opravena (viz zdůvodnění níže) - zapsáno do `TASKS.md`. Třídy 1-3 nebyly touto session znovu systematicky prohledány přes celý katalog nad rámec už dřív zdokumentovaných otevřených případů (RE28, FO36 pro třídu 1) - kapacita session šla primárně do nově zadané třídy 6 a do dokončení tříd 5/4. Zapsáno jako zbývající otevřený bod v `TASKS.md`, ne mlčky vynecháno.

### Třída 6 - nevyužitý svislý prostor pod stropem (NOVÁ, zadáno 2026-09-03 stejnou prioritou jako 1-5)

**Metoda** (`scripts/2026-09-03_class6_headroom_audit.js`): pro každý sloupec (`eurobox-sloupecN-patroM`/`eurobox-colN-pM`, oba používané naming styly zvlášť detekované) změř SKUTEČNOU `Box3` nejvyššího patra (`topOfStack` = max.y reálné GLB geometrie boxu, ne z `position.y` - ten je jen pivot, u různých výškových variant s různou konvencí počátku, viz dřívější nález o `product_3793`). Spočti `physCeil` stejnou technikou jako `tmp_2026-08-31_batch_pipeline.js` step7 - sonda (`THREE.BoxGeometry` přes celý reálně naměřený X/Z footprint sloupce) posouvaná od `topOfStack` nahoru po 1mm proti REÁLNÉ geometrii karoserie (`makeCollisionModule`), −2mm rezerva. `gap = physCeil − topOfStack`. Prah (Robertovo přesné zadání): `gap ≥ 180mm` (120 min. box + 30 mezera + 30 tloušťka railu).

**2 zvláštní případy narazeny a vyřešeny cestou:**
1. **"Already colliding at topOfStack"** (50 sloupců, hlavně starší rodiny Peugeot Expert PE12-17/e-Expert PE25-27, Mercedes Vito MB17-19/46/47, Ford Connect/Transit Connect FO12/13/36/37/45/46, Berlingo/Partner/Trafic B-varianty) - sonda IHNED koliduje na `topOfStack`. Diagnostikováno jako SPRÁVNÝ výsledek, ne bug: tyhle sloupce byly už dřív (jinými boty, `id=8`/`id=6` práce) protaženy až na skutečný fyzický strop (často kvůli lokální nerovnosti typu výřez kola do stěny) - `gap≈0`, žádná další kapacita. Ověřeno ručně na MB47 (`id=83`): sonda přes celý footprint kolidovala už na Y≈900-960 kvůli lokálnímu zúžení stěny (podběh), i když samotný box sahal do Y=975 - konzervativní full-bbox sonda (STEJNÁ technika jako step7) je citlivější než skutečný (nepravidelný) tvar boxu, ale to je záměrná vlastnost metody (bezpečnostní rezerva), ne chyba.
2. **"Žádná kolize nalezena"** (16 sloupců - Berlingo CI03/04/16/17/22/23, Partner/e-Partner PE02/03/18/19/23/24, Ford Connect FO12/13) - tyhle GLB `_L`/`_R_D`/`_B` soubory NEMAJÍ modelovaný strop/střechu vůbec (jen boční stěny + podlaha), sonda posunutá nahoru nikdy nic nenajde ani po 3000mm. Fallback: `karoserie_model_reference.cargo_height_mm − 30mm` (stejná konvence jako `shape_geometry_methods.id=8`). Všech 16 vyšlo pod prahem 180mm (žádný nebyl třeba opravovat) - u PE02/03 dokonce mírně záporný `gap` (−22mm, tj. postavený box už mírně přesahuje tenhle KONZERVATIVNÍ odhad stropu - nekritické, `cargo_height_mm` je jen hrubý proxy, ne skutečná GLB kolize, a tyhle sloupce byly už dřív ověřené proti reálné geometrii při stavbě).

**Nalezeno 24 sloupců/20 řádků s `gap≥180mm`** - nejvýraznější: Caddy Cargo PHEV VW31 A/B/C/D/E (`id=126/143/144/165/166`, oba sloupce, mezera 799-931mm - vysoká noha s jen 2-3 patry), Proace Long/Medium (16-/Electric) rodina (`id=59/60/63/64/147/148/169/170`, ~200-300mm), Ford Custom FO28/FO29 (`id=109/110`, ~380-400mm), Transit Connect PHEV FO45 (`id=132`, 493mm), Vivaro OP31 C (`id=158`), Trafic RE28 D (`id=163`).

**Oprava** (`scripts/2026-09-03_class6_plan_and_build.js`): pro každý flagovaný sloupec doplň DALŠÍ patra dokud `gap<180`. Nová patra = kopie existujících `nosnik`/`spojnice` dílů posledního patra (stejné X/Z, jen `Y += H_predchozí + 30 + T`), nová `eurobox` pozice dopočtena ZE SKUTEČNÉ GLB geometrie nové výškové varianty (`ty = novy_rail_Y_center + T/2 − probe.box.min.y(pod danym quaternionem) − 12`, stejný vzorec jako `shape_geometry_methods.id=3` krok 4). Výška nového patra: největší dostupná `{270,220,170,120}` splňující SOUČASNĚ (a) nerostoucí pravidlo (≤ výška předchozího nejvyššího patra) a (b) fyzický rozpočet (`H+60 ≤ zbývající gap`). U VW31 rodiny to znamenalo 3-5 nových pater na sloupec (region `[126,143,144,165,166]` dostal dohromady přes 15 nových pater).

**Zvláštní případ `id=59` (Proace Medium 16- / Toyota TO08) - DOSLOVNÝ POKYN NEDODRŽEN, zdůvodněno:** Robert explicitně řekl "dej mu euroboxy 170mm" pro pravý sloupec (col0, `topBoxH=170` v době zadání). Přesné měření ale ukázalo `gap=205mm` u tohohle sloupce → rozpočet na nové patro = `205−60=145mm` < 170mm. Box 170mm by fyzicky NARAZIL do skutečného stropu vozu o ~23mm (po odečtení 2mm rezervy). Vzhledem k projektovému pravidlu "0.01mm přesah je nepřípustný" byla místo 170mm použita bezpečná `120mm` (největší, co se opravdu vejde) - **zapsáno jako otevřený bod do `TASKS.md`, ne provedeno potichu podle doslovného zadání.** Stejný sloupec u sourozeneckých karoserií TO03/TO07/TO22 (`id=60/63/64`, identická geometrie nohy/karoserie) dostal stejné řešení (120mm) pro konzistenci.

**Ověření (na VŠECH 18 opravených řádcích, bez výjimky):** (1) žádný nový sloupec nekoliduje se skutečnou karoserií (`collidesWithWalls` na finálním `topOfStack` PO zápisu) - 0/18 kolizí; (2) bezpečnostní trim-krok (`scripts/2026-09-03_class6_verify_trim.js`) by odstranil libovolné nově přidané patro, které by při přesném měření přeci jen kolidovalo - spustilo se, **0 patro muselo být odstraněno** (plán byl od začátku správný); (3) manuální spot-check mezer mezi patry (`id=143`, 4 nová patra v jednom sloupci) potvrdil PŘESNOU shodu se vzorem už existujícím v týž řádku (42mm mezera box-top→next-rail-bottom, konzistentní na všech 7 patrech); (4) **nezávislý druhý průchod na FRESH datech z DB PO zápisu** (`scripts/2026-09-03_class6_headroom_audit.js` spuštěný znovu, čerstvě stažená `data` z `product_assemblies`) - 0/18 řádků zůstalo flagováno, 0 chyb; (5) **sanity Y-range kontrola na VŠECH 18 upravených řádků** (mimo `car_body_*`): min 16.5-17.0mm, max 1262-2084mm - žádný skok o ~1600mm typu dřívější regrese, všechny hodnoty ve fyzicky rozumném rozsahu pro výšku dodávky.

`verified_by` se u téhle třídy netýká - `product_assemblies` nemá vlastní `verified_by` sloupec (ten je jen u `shape_geometry_methods`/`car_body_placement_methods`, sem nebyla zapsána žádná NOVÁ obecná metoda, jen aplikace už existujícího pravidla `id=3` "vertikální patra"). Robertovo VIZUÁLNÍ potvrzení ve scéně těchto 18 řádků ještě NEPROBĚHLO - číselné ověření (viz výš) je hotové, vizuální ne.

### Třída 5 - jen JEDNA výška boxu v regálu (dokončeno)

Přesný audit (ne jen SQL regex ze zadání, který false-positivoval na jménech typu "boxy43-270x220" u Proace Crew Cab - to je zápis DVOU RŮZNÝCH výšek, ne "výška×počet"): pro každý řádek spočti množinu SKUTEČNÝCH `product_id` euroboxů (`3788`=120/`3793`=170/`3794`=220/`3795`=270/`3796`=320) použitých napříč VŠEMI sloupci. **5 řádků s PŘESNĚ 1 výškou** (přesně odpovídá seznamu z zadání): `id=172` (PE25 E), `174` (MB47 E), `176` (FO31 E), `178` (VW25 E), `180` (OP31 E).

**Rozhodnutí per řádek** (Robertovo pravidlo: "preferuj smazání, pokud D varianta už pokrývá diverzitu, jinak přestav s min 3 výškami, zdokumentuj rozhodnutí"):
- **`id=172` (PE25 E) SMAZÁNO** - sourozenecká `id=171` (PE25 D) má už 3 různé výšky (`220x3-170x3-120x3`), diverzita rodiny pokryta, `E` byla čistě redundantní/chybně postavená varianta (viz zadání - "E = max počet kusů" bylo vymyšlené zdůvodnění, nikdy Robertem neřečené).
- **`id=174` (MB47 E) SMAZÁNO** - sourozenecká `id=173` (MB47 D) má 3 výšky (`220x5-170x5-120x5`).
- **`id=180` (OP31 E) SMAZÁNO** - sourozenecká `id=179` (OP31 D) má 3 výšky (`220x3-170x3-120x3`).
  - U všech 3 ověřeno PŘED smazáním: `shop_products.active=0` (nejde o živý prodávaný produkt), 0 řádků v `shop_order_items`/`shop_cart_items`/`shop_product_images` - bezpečné hard-delete, žádná objednávka/koš/galerie na ně neodkazuje. Smazáno `DELETE FROM product_assemblies WHERE id IN (172,174,180)` + `DELETE FROM shop_products WHERE id IN (3922,3924,3930)` (odpovídající `shop_product_id`).
- **`id=176` (FO31 E) a `id=178` (VW25 E) PONECHÁNY BEZE ZMĚNY** - na rozdíl od výše, sourozenecká `D` varianta u OBOU (`id=175` FO31 D = `170x3-120x3`, `id=177` VW25 D = `220x2-120x2`) má taky jen 2 výšky, ne 3 - "D už pokrývá diverzitu" NEPLATÍ tady. Zkoumáno, jestli lze `E` přestavět na 3 výšky: sloupec má jen 3 patra, `physCeil` dovoluje jen ~478mm (FO31) / ~504mm celkového vertikálního prostoru pro box+mezery na 3 patrech - i NEJMENŠÍ možná trojice DISTINCT výšek (120+170+220=510mm) do tohohle prostoru fyzicky NEVEJDE (chybí ~30-150mm). **3 distinct výšky jsou zde geometricky nedosažitelné kvůli nízké karoserii/krátké noze** (přesně situace, kterou `shape_geometry_methods.id=3` už predikoval: "možné kombinace výšek boxů jsou o to nižší čím kratší je výška nohou"). Zapsáno do `TASKS.md` jako otevřený bod - čeká na Robertovo rozhodnutí (přijmout 2 výšky jako praktické maximum pro tuhle rodinu, nebo smazat `E` bez náhrady).

**Vedlejší zjištění (NENÍ součástí "třídy 5" tak jak byla zadaná, jen zaznamenáno pro info):** dalších ~40 řádků má přesně 2 distinct výšky (ne 1) - technicky taky pod Robertovým obecným pravidlem "min 3", ale mimo doslovný popis týhle třídy chyby ("JEDNA výška") a mimo zadaný SQL vzor. Nebyly touto session měněny - riziko podobného "fyzicky nedosažitelného" scénáře jako u FO31/VW25 je vysoké u mnoha z nich (krátké nohy/nízké karoserie), vyžadovalo by to samostatný per-řádek fyzický rozpočet jako u FO31/VW25 výš. Necháno jako poznámka pro budoucí kolo, ne jako nález k opravě v tomhle auditu.

### Třída 4 - noha v otvoru bočních posuvných dveří (metoda zobecněna, NEOPRAVENO na 48 nalezených kandidátech - zdůvodnění níže)

Navazuje na existující otevřený úkol v `TASKS.md` ("Audit zbylých ~113 eurobox regálů na stejnou třídu chyby..."). Detekční metoda `car_body_placement_methods.id=1` (`vylouceni_bocniho_dvernich_otvoru_2026_09_02`: mezera >150mm mezi Z-seřazenými vertexy v Y∈[200,900] pásmu `_R_D.glb`) byla PŮVODNĚ ověřená a použitá jen na 2 konkrétní vozidla (FO31/VW25), kde skript navíc explicitně ASSERTOVAL přesně 1 nalezenou mezeru (chyba, pokud jich bylo víc/míň).

**Zobecnění na celý katalog** (`scripts/2026-09-03_class4_doorvoid_audit.js`) odhalilo, že SUROVÁ metoda (bez dalšího filtru) najde 2-4 "mezery" u VĚTŠINY vozidel - naprostá většina z nich NEJSOU skutečné dveřní otvory, ale (a) okraj modelované geometrie stěny (nemodelovaná kabina řidiče před přepážkou, otevřený zadní konec) nebo (b) jiné strukturální přerušení. **Filtr přidán:** platná "dveřní" mezera musí mít NEJMÉNĚ 300mm materiálu na OBOU stranách v tomtéž Y-pásmu (tj. musí být SKUTEČNĚ orámovaná stěnou, ne konec modelu) - tenhle filtr snížil falešné nálezy z 97/115 na 48/115 řádků.

**Validace metody na známém stavu:** žádný z 10 už OPRAVENÝCH řádků FO31/VW25 (`id=111/153/154/175/176/118/155/156/177/178`) se v novém seznamu kandidátů needobjevil (správně - noha už tam po opravě NENÍ) - silný pozitivní signál, že metoda po filtru rozlišuje "uvnitř otvoru" od "mimo otvor" správně aspoň na známém referenčním případu.

**Proč NEBYLA provedena automatická oprava na zbylých 48 kandidátech:** i po 300mm filtru metoda zůstává heuristikou bez vizuálního potvrzení PRO KAŽDÉ jednotlivé nově nalezené vozidlo (na rozdíl od FO31/VW25, kde byl nález i vizuálně ověřený ve scéně před opravou). Riziko falešně pozitivních zásahů (např. skutečná mezera může být rozšířený panel/technologický otvor, ne skutečně průchozí dveře - jak se to stalo u RE29 "izolovaná překážka" v `KAROSERIE_UMISTENI.md`) je reálné a oprava vyžaduje STEJNOU důkladnost jako u FO31/VW25 (fresh anchorZ přepočet + kompletní STEP1-7 rebuild + ověřovací baterie + 2D gate) - to je svým rozsahem srovnatelné s PŮVODNÍ noční opravou (10 řádků, celá session), ne něco, co lze bezpečně odbýt mechanicky pro 48 řádků najednou v rámci jednoho auditu. **Zapsáno do `TASKS.md`** jako pokračování existujícího úkolu s přesným seznamem 48 kandidátů (`id` + role + Z-rozsah + šířka mezery) pro navazujícího bota.

## Oprava 6 tříd chyb PŘÍMO VE ZDROJOVÉM KÓDU sdílených stavěcích skriptů (bot27, 2026-09-03)

Robert: "auditujeme to porad dokola a stale jsou tam problemy" + "Já beru automaticky že musíš opravit to co je zdrojem chyby" - dosud se opravovala jen DATA jednotlivých `product_assemblies` řádků, ne SKUTEČNÁ PŘÍČINA ve sdílených skriptech, ze kterých se řádky vyrábí. Tahle session opravila zdroj, ne data (souběžně jiní agenti opravovali data/stavěli nové Jumpy řádky - žádný `product_assemblies` řádek touhle session editován). Regresní ověření: `node scripts/tmp_2026-08-31_batch_run.js` (22 vozidel) po opravě dal stejných **17/22 OK** jako commit `1af103a` PŘED opravou (0 regresí); 6 z 17 i FO31/VW25 A-E porovnáno se souhlasnými uloženými `product_assemblies` řádky - shoda 1:1.

1. **+12mm mezera mezi patry** - vzorec `Y_rail_top(N+1)=Y_rail_top(N)+H_box+30+T` chyběl odečet 12mm "nožky" eurobxu (`H_box-12` misto `H_box`). Opraveno v **6 souborech** (`planColumn`/`computeLevels`/`validateHeights`/`assemble` v každém): `tmp_2026-08-31_batch_pipeline.js`, `tmp_2026-09-01_bc_build.js`, `tmp_2026-09-02_bot16_de_build.js`, `tmp_2026-09-02_doorvoid_assemble.js`, `tmp_2026-09-02_bot25_jumpy_assemble.js` (posledni = AKTIVNÍ Jumpy pipeline, kritický nález). Ověřeno proti `product_assemblies.id=57` (Vivaro OP18): vzorec s `-12` dal přesně 168.0mm/318.001mm mezeru shodnou s uloženými daty.
2. **"Podběh bez konce"** - kandidátní test při hladovém plnění sloupců (`tmp_2026-08-31_batch_pipeline.js` i jeho 2 aktivní kopie `tmp_2026-09-02_doorvoid_pipeline.js`/`tmp_2026-09-02_jumpy_pipeline.js`) testoval rigidní `buildVyrezAtDepth(D)` s pevným `CUTOUT_H` - nahrazeno čerstvým `computeYNewWall(z)` (0..TOP_Y sken wall-side profilu na KAŽDÉ kandidátní Z), sjednoceno z bot24's Caddy-specifické opravy (`git show 0ceb07f`) do sdílených kopií. STEP2 (island-lookahead pro REAR_ANCHOR_Z) beze změny - jiný, už osvědčený mechanismus.
3. **Y-offset regrese (VW31 "regál letí 1650mm")** - kořenová příčina je STRUKTURÁLNÍ (chybí normalizace raw-GLB Y-bbox v `createEngine()`/`makeEnv()`, ne chybná aplikace nějakého DB offsetu - žádný takový sloupec neexistuje), oprava by vyžadovala zásah do toho, jak se zapisuje `car_body_*` díl, riziko pro 17/22 fungujících vozidel bez ověření na celém katalogu - **zapsáno do `TASKS.md` pro Robertovo rozhodnutí**, NEOPRAVENO narychlo (WORKFLOW.md). Bezpečná, explicitně vyžádaná část OPRAVENA: `assertSaneRackYPositions()` (throw při Y mimo `[-500,2500]`mm pro libovolný NE-`car_body_*` díl) přidán do 3 zápisových cest.
4. **Noha v otvoru bočních posuvných dveří** - detekce (`confirmDoorGaps`) existovala jen v `doorvoid_pipeline.js`/`jumpy_pipeline.js`, chyběla v PŮVODNÍM/hlavním `tmp_2026-08-31_batch_pipeline.js` (pořád základ pro ~113 ostatních regálů) - přidán STEP 1b (posun přední nohy) + rozšíření STEP3 candidate-loopu o `overlapsAnyDoorGap`.
5. **Noha zabořená do podlahového hrbu podběhu (MB47)** - `sloupek-pred-podbehem` vždy předpokládal Y=0 na SVÉ VLASTNÍ X pozici (124mm od stěny), i když `computeYNewWall` řeší jen wall-side X. Přidán `computeSloupekBottom()` (fresh sken na sloupkově vlastní X/Z, sjednoceno z bot24's `sloupekPieceAt`) - `buildVyrezAtDepthExtended(D, Y_new, sloupekBottom)` rozšířen o 3. volitelný parametr (default 0, zpětně kompatibilní).
6. **Box neseřazený s příčkami (PE25)** - OVĚŘENO jako už správné, žádná oprava potřeba: kód i živá data (`id=74`) potvrzují, že eurobox Z pozice se počítá ze STEJNÝCH hodnot jako spojnice (`CONNECTOR_POS`), ne nezávisle.

Detail viz `AGENTS_LOG.md`, bot27 2026-09-03. Otevřený bod (bod 3, root-cause normalizace) i pokračování bodu 4 (48 kandidátů) v `TASKS.md`.

## Celá rodina Citroën/e-Jumpy (CI13/14/15/18/19/24/25/26) — regál s úhelníky OD ZAČÁTKU stavby (bot25 stavba, bot28 nezávislé přeověření + dokumentace, 2026-09-01)

**Zadání:** Robert potvrdil, že žádný Jumpy regál v katalogu neexistoval (noční pilotní build z předchozí session nikdy nebyl uložen natrvalo — potvrzeno přímo v DB: `product_assemblies` mělo `MAX(id)=180` a žádný z dřív logovaných Jumpy assembly id (19/27/32-39/43-47/53-55) už neexistoval). Chtěl postavit CELOU rodinu od nuly, s úhelníky (`shape_geometry_methods.id=7`) rovnou při stavbě, ne dodatečně.

**Výsledek: 8/8 karoserií postaveno a uloženo**, profil 30×30mm, D=326mm ("euroboxy podélné", pojmenovaná hloubka ze `shape_geometry_methods.id=2`), noha `custom_shapes.id=526` (plná) / `527` (výřez, H=1180mm nominal). Všechny `is_public=1`, `shop_products.active=0` (draft, standardní konvence pro čerstvě postavený, ještě Robertem vizuálně nepotvrzený regál).

| Karoserie | `product_assemblies.id` | `shop_products.id` | Boxy (výška×počet) | Distinct výšky | Výška nohy | Zdroj výšky dveří |
|---|---|---|---|---|---|---|
| CI13 (Jumpy L1 16-) | 181 | 3931 | 170×3, 120×6 | 2 | 1180mm | `official_door_opening_height_mm` NULL — ponecháno beze změny |
| CI14 (Jumpy L2 16-) | 182 | 3932 | 270×2, 170×3, 120×9 | 3 | ~1188mm | 1220mm |
| CI15 (Jumpy L3 16-) | 183 | 3933 | 270×4, 170×3, 120×9 | 3 | ~1188mm | 1220mm |
| CI18 (Crew Cab L2 16-) | 184 | 3934 | 170×2, 120×4 | 2 | ~1188mm | 1220mm |
| CI19 (Crew Cab L3 16-) | 185 | 3935 | 170×3, 120×6 | 2 | ~1189mm | 1220mm |
| CI24 (ë-Jumpy L1 21-) | 186 | 3936 | 170×3, 120×6 | 2 | 1180mm | NULL — ponecháno beze změny |
| CI25 (ë-Jumpy L2 21-) | 187 | 3937 | 270×2, 170×3, 120×9 | 3 | ~1188mm | 1220mm |
| CI26 (ë-Jumpy L3 21-) | 188 | 3938 | 270×4, 170×3, 120×9 | 3 | ~1188mm | 1220mm |

**Výška nohy (`shape_geometry_methods.id=8`)**: pravidlo je OBOUSMĚRNÉ (`H_cíl = official_door_opening_height_mm − 30`), ne jen zkracovací, jak se dřív provizorně předpokládalo — u 6 karoserií se známou výškou dveří (1220mm) vyšel `H_cíl≈1190mm`, o něco VÍC než nominálních 1180mm, takže přední/nejvyšší zadní profil nohy byl mírně PRODLOUŽEN (na ~1188-1189mm po reálném kolizním doladění ke stropu, ne plochých 1190mm — stejná "kolizní krokování nahoru" záchranná metoda jako u dřívějších 23 řádků zablokovaných plochým vzorcem). CI13/CI24 nemají `official_door_opening_height_mm` v DB — dle výslovného Robertova pravidla ("nikdy neodhadovat") ponechány na nominální 1180mm beze změny.

**Pravidlo 1 (min. 3 distinct výšky) — CI13/18/19/24 mají jen 2, TO07-style fyzický limit, ne porušení**: jednosloupcové, úzké sestavy (vertikální rozpočet 571-577mm) fyzicky nepojmou 3. nejmenší kombinaci výšek (120+170+220=510mm + rámy/mezery přesahuje dostupný prostor) — stejná zdokumentovaná třída výjimky jako Proace TO07 a Vivaro OP31 výše v tomhle souboru. Diverzita napříč rodinou zajištěna jinak (CI14/15/25/26 mají plné 3 výšky).

**Úhelníky (`shop_products.id=3045`, `2.2.001.08.3030.01`)**: aplikovány na všech vnitřních spojích KAŽDÉ nohy od první stavby, ne dodatečně — 19ks na dvounohou sestavu (181/184/185/186), 31ks na třínohou (182/183/187/188), 200ks celkem napříč rodinou.

**Ověřovací baterie (nezávisle přeověřeno bot28, ne jen převzato z bot25's reportu):**
- `node scripts/tmp_2026-09-02_bot25_jumpy_fresh_verify.js` spuštěn ZNOVU, samostatně, po celé investigaci: **8/8 PASS**, 0 kolizí s karoserií, 0 neočekávaných self-kolizí, Y-range sane (`minY≈1-2mm`, žádná ~1500-2000mm regrese třídy E).
- Přímá inspekce `data` JSON (ne jen skript) potvrdila box-breakdown a počty úhelníků v tabulce výše.
- `car_bodies_automation_exclusions` beze změny (2 řádky, žádný neodpovídá Jumpy kódům) — potvrzeno PŘED i PO stavbě.

**Falešný poplach a poučení (třída A, dveřní otvor) — DŮLEŽITÉ pro navazující práci na existující TASKS.md úkolu "48 kandidátů":** Při nezávislém přeověření bot28 nejdřív spustil `scripts/2026-09-03_class4_doorvoid_audit.js` (bot26's celokatalogový vertex-gap audit) na nových 8 řádcích — nahlásil "nohu v otvoru" na 6 z 8 karoserií (vše kromě CI18/CI19). Bot25 (stavitel) tenhle nález odmítl a měl PRAVDU: `scripts/2026-09-03_class4_doorvoid_audit.js` testuje NAPEVNO vždy jen `_R_D.glb`, bez ohledu na to, proti které stěně regál skutečně stojí. Nezávislé ověření (bot28, `scripts/tmp_2026-09-02_verify_raycast_check.js` — hustý rastr raycastů, ne vertex-gap heuristika): rack parts mají X∈[-736,0] (uvnitř `_L.glb` bbox `[-807,0]`, ne `_R_D.glb` bbox `[0,807]`) a `_L.glb` je PLNĚ SOLIDNÍ (hitFraction=1.0000) přesně na Z-rozsahu, kde `_R_D.glb` má SKUTEČNOU díru (hitFraction 0.000-0.036, potvrzeno u CI13/24, CI14/25, CI15/26 samostatně). CI18/CI19's flagged hit byl navíc taky falešný pozitiv opačným směrem (jejich `_R_D` mezera je 100% solidní, jen sparse-mesh artefakt). **Závěr: 0/8 skutečných porušení, celý nález byl testování špatné stěny.** Zapsáno jako nový klíč `car_body_placement_methods.id=1.vylouceni_bocniho_dvernich_otvoru_kterou_stenu_testovat_2026_09_01` (version 11→12) — **existující seznam 48 kandidátů z bot26's auditu (viz sekce "Třída 4" výše) potřebuje přepočet s kontrolou správné stěny (a ideálně raycast ground-truth místo vertex-gap) dřív, než se z něj bude cokoli opravovat** — zapsáno do `TASKS.md`.

**Rozsah nedokončen (vědomě, ne opomenutí):** B/C alternativní výškové varianty pro CI24/25/26 (jako u jiných rodin) NEBYLY postaveny — kapacita šla do primárních 8 karoserií + řešení falešného poplachu výše. Robertovo VIZUÁLNÍ potvrzení ve scéně (skill `3d-scena-spoje` bod 8) u žádné z 8 karoserií ještě NEPROBĚHLO — číselné ověření hotové, vizuální ne. `verified_by` u nové položky `car_body_placement_methods.id=1` zůstává implicitně botem (žádný `verified_by` sloupec na úrovni klíče, jen na úrovni celého záznamu — ten zůstává `'robert'` z předchozí historie záznamu, protože tahle nová položka je jen DOPLŇKOVÁ poznámka k metodice, ne změna jádra už schváleného pravidla).

**Skripty** (necommitnuté dřív, commitnuty touto session): `scripts/tmp_2026-09-02_bot25_final_pipeline.js`, `_jumpy_assemble_v2.js`, `_final_build_all.js`, `_jumpy_update.py`, `_jumpy_fresh_verify.js`, `_jumpy_2d_check.html`/`.js`/`_2d_data.json`, `_confirm_doorgap.js`, `_final_span_check.js`, a starší iterace (`_jumpy_assemble.js`, `_jumpy_build_all.js`, `_jumpy_insert.py`, `_jumpy_span_check.js`, `tmp_2026-09-02_jumpy_pipeline.js`, `_dbg_ci15.js`, `_verify_doorgap.js`) ponechány pro auditní stopu. Bot28 přidal `tmp_2026-09-02_verify_raycast_check.js` (obecný raycast ground-truth nástroj, `<car_body_base> <zLo> <zHi>` argumenty, znovupoužitelný pro budoucí spory o vertex-gap nálezy) a `tmp_2026-09-01_bot28_cbpm1_wallside_note.py` (DB zápis poznámky výše).

## Pravidlo profilů - HORNÍ BLOK PRO DLOUHÉ PŘEDMĚTY (Robert, 2026-09-05/06, VZOROVÁ METODA)

⚠️ **Robert 2026-09-11 (audit bot9 doplnil 2026-09-12): sestavy zmíněné jako vzorové níže (134/135/182/189/209/219/279/289, vč. Jumpy CI25 id=187/189) jsou NEPLATNÉ** - "staré horní bloky neplatí, vzorový horní blok děláme na Doblu C". Nový vzor je K-075 Doblo C (produkt 3942/3943, sestavy 332-337, dnes nástupci 341-347 - viz `shape_geometry_methods.id=9`). Text níže popisuje stav/rozhodnutí PŘED touto změnou vzoru - metoda/algoritmus zůstává platný, konkrétní vzorové sestavy ne.

**Obecná, znovupoužitelná metoda** pro využití prostoru mezi vrchem nejvyššího
eurobox patra a koncem nohy — ukládání dlouhých předmětů (tyče, lišty, profily)
podélně přes celé auto. Plná definice (algoritmus, kritické pasti, rozsah)
je zapsaná strukturovaně v `shape_geometry_methods.id=9`
(`horni-blok-pro-dlouhe-predmety`) — tenhle oddíl je jen ukazatel + shrnutí.

**Vznik:** Robert postupně upřesňoval zadání na regálu Jumpy L2 CI25
(`product_assemblies.id=189`), kterou **výslovně zvolil jako vzorovou
sestavu** pro odvození pravidel použitelných na jakýkoli jiný regál/auto:
*"pojďme na tomto regálu v tomto autě udělat ty možnosti a vzorové patterny,
chování a pravidla, dotáhneme to jako vzorové pro další jiné sestavy v
jiných autech"*.

**✅ POTVRZENO ROBERTEM VE SCÉNĚ 2026-09-10** — *„jednopásmová zóna pro
horní blok je nyní sestavena správně, zapsat do pravidel postupu."*

Potvrzovací sestava: **`Doblo K-075 C` (id=279)**, karoserie
`Fiat_Doblo_FI14_2010-2022`. Zapsaný stav 94 → 103 dílů, 9 nových
(2× `podelnik-celni-spodni`, 2× `podelnik-zadni-spodni`, 3× `pricka-spodni`,
2× `vypln-dno`), světlá výška nad rámem 223,5 mm, **0 kolizí** s díly
i s karoserií. Tím je základní jednopásmové provedení hotové — metoda
`shape_geometry_methods.id=9` je od verze 6 `verified_by='robert'`.

Spuštění: `node scripts/2026-09-05_horni_ram.js <dump.json>
--vozidlo=<karoserie> --jedno-pasmo`

⚠️ **Skript není idempotentní** — nekontroluje, jestli sestava horní blok
už má, a přidal by druhý. Ze šesti Dobel ho k 2026-09-10 už mají **134,
135 a 209**. Před spuštěním se vždy podívej, jestli v `data.parts` nejsou
role `podelnik-*`.

Dvoupásmová varianta (volba „rozdělit na dva") zůstává jako dřív — ověřená
na CI25 (id=189), ale Robertem ve scéně **nepotvrzená**.

**⭐ PRAVIDLO 2026-09-10 (Robert) — příčka u přepážky je DORAZ.** Doslova:
*„první příčka dna nohy u přepážky slouží už jako doraz, tzn. nebude lícovat
horní hranou s deskou dna, ale bude výškově v úrovni podélníku."*

Ostatní příčky pásma s deskou se posouvají dolů, aby jejich horní hrana
lícovala s MDF a nic nečnělo nad rovinu dna. Příčka na noze u přepážky
(`a.zadni[0]`) se **neposouvá** — zůstává vystředěná v pásmu, v úrovni
podélníku, a nad dno záměrně čnívá, aby dlouhé předměty nesjížděly
k přepážce.

Ověřeno na `Doblo K-075 C` (id=279): `pricka-spodni-0` střed Y = 981,5
(pásmo 966,5–996,5), ostatní 970,5 — doraz tedy převyšuje dno o **11 mm**.

**⭐ PRAVIDLO 2026-09-10 (Robert) — vodorovné dno o 1 mm kratší než
podélník.** Doslova: *„dno mdf na oba sloupce které zapadá do podélníků,
musí být vždy kratší o 1 mm než podélník (nosník), proto aby nekolidoval se
svislými profily nohy ani s příčkami."*

Do té doby se dno naopak o `ZASUN` (7 mm) na **každou** stranu prodlužovalo
do příček — bylo tedy o 14 mm **delší** než podélník. Nově je o 1 mm
**kratší** (0,5 mm vůle z každé strany).

Důsledek, který je nutné znát: dno tím leží **výhradně v drážkách obou
podélníků** a má jen **2 zásuny, ne 4**. Požadavek „panel držený po celém
obvodu" tedy platí dál **jen pro svislé výplně**. Kontrola počtu zásunů to
už rozlišuje (`vypln-dno`/`vypln-police` očekávají 2, ostatní 4) — bez toho
by hlásila každé dno jako nedostatečně držené.

Ověřeno na `Doblo K-075 C` (id=279): podélník 430 mm → dno 429 mm,
podélník 834 → dno 833, nula kolizí s díly i s karoserií.

**⭐ OPRAVA 2026-09-10 (Robert) — základ má JEDNO pásmo, ne dvě.** Doslova:
*„Pozor základním provedením je pouze jedno výškové pásmo horního bloku"* →
*„Základní je to spodní, horní pásmo je pouze další volba rozdělení toho
horního bloku na dva."*

Základní provedení = **jen SPODNÍ pásmo** (rám 30 mm nad vrchem posledního
boxu, nese dna), a nad ním světlá výška pro dlouhé předměty až ke koncům
noh. **Horní pásmo** (podélníky u konců noh) je **volba navíc** — jejím
přidáním se blok rozdělí na dvě patra.

Dopad, který se snadno přehlédne: zkracování středových noh o 30 mm a
odebírání horních záslepek je vlastnost **horního** pásma. V základním
jednopásmovém provedení se tedy **neděje** — nohy zůstávají v plné délce.

⚠️ `scripts/2026-09-05_horni_ram.js` staví obě pásma vždy, takže k
2026-09-10 **téhle opravě neodpovídá**; potřebuje doplnit volbu a jako
výchozí nastavit jednopásmový režim. Autoritativní znění:
`shape_geometry_methods.id=9`, verze 3 (verze 2 zazálohovaná v
`backups/2026-09-10_shape_method_9_v2_pred_opravou_pasem.json`).

### ⭐ VARIANTY HORNÍHO BLOKU — jeden postup (2026-09-10)

Robert: *„chci to zpřehlednit jako jeden postup ohledně variant."* Do té
doby žily varianty ve **dvou nesouvisejících seznamech** — původní výčet
pěti variant (Bez / Eko / Plné / Poloviční / Dvířko) a vedle něj přepínače
skriptu přidávané postupně (police, počet pásem), které ve výčtu vůbec
nebyly. Tohle je jediný platný postup; rozhoduje se v tomhle pořadí.

**Krok 1 — Má regál horní blok?**
Ne → varianta „Bez", skript se nespouští, hotovo. Ano → krok 2.

**Krok 2 — Kolik výškových pásem?**

| volba | co to je | přepínač | stav |
|---|---|---|---|
| **Jedno** (základ) | spodní rám 30 mm nad posledním boxem, nese dna; nad ním volná světlá výška až ke koncům noh | `--jedno-pasmo` | ✅ **potvrzeno Robertem ve scéně** |
| Dvě | přidá se druhý rám u konců noh, blok se rozdělí na dvě patra | výchozí | hotovo, ve scéně nepotvrzeno |

⚠️ Tenhle krok **rozhoduje o kroku 4**: při jednom pásmu **nelze stavět
svislé výplně** — panel musí být držený po celém obvodu a bez horního
podélníku nemá horní hrana do čeho zajet. Jedno pásmo umí jen „rám" nebo
„rám + dna".

**Krok 3 — Police v polovině výšky?** (jen u dvou pásem)

| volba | co to je | přepínač |
|---|---|---|
| S policí | další vodorovné pásmo uprostřed kanálu (podélníky + příčky + MDF) | výchozí |
| Bez police | jeden nepřerušený kanál po celé výšce, pro dlouhé předměty | `--bez-police` |

U jednoho pásma police neexistuje (nemá horní hranici) — `--jedno-pasmo`
ji vypíná sám.

**Krok 3b — Horní příčky?** (jen u dvou pásem)

| volba | co to je | přepínač |
|---|---|---|
| S horními příčkami | příčné příčky i v horním pásmu | výchozí |
| **Bez horních příček** | podélníky horního pásma zůstávají (drží rám), příčky se vynechají → **blok je shora otevřený** a dá se vkládat seshora | `--bez-hornich-pricek` |

Robert 2026-09-10: *„verzi 4 odstraň nejvyšší sadu příček"* — navazuje na
jeho dřívější *„na dlouhé předměty si klient vybere variantu bez horních
příček a bude to vkládat i shora"*. Ověřeno na Doblu C: 108 → 105 dílů,
odebrány `pricka-horni-0/1/2`, 0 kolizí. Ve scéně zatím nepotvrzeno.

#### ⭐ Všechny volby jsou OBECNÉ, ne úprava jedné sestavy

Robert 2026-09-10: *„samozřejmě že to budeme opakovat na všechny další auta
i regály."* Každá volba z kroků 2–4 je proto **přepínač skriptu pracující
nad rolemi dílů**, ne zásah do konkrétní sestavy. **Nikdy neřešit variantu
ručním smazáním nebo přidáním dílů v jedné sestavě** — když volba ještě
neexistuje, přidat přepínač.

Pořád ale platí, co se zjistilo na Vivaru OP18: metoda je přenositelná
beze změny kódu, ale **každé vozidlo vyžaduje vlastní kolizní ověření**
před zápisem do DB. Nikdy neaplikovat naslepo jen proto, že to na jiném
autě prošlo.

**Krok 4 — Výplně**

| volba | co to je | přepínač | stav |
|---|---|---|---|
| Bez (dřív „Eko") | jen rám, žádné desky | `--bez-vyplni` | ✅ **potvrzeno** (viz níže) |
| Dna | vodorovné MDF desky (a police, je-li); u jednoho pásma maximum | výchozí u `--jedno-pasmo` | ✅ potvrzeno |
| Plné | dna + svislé stěny (záda, čelo, bok u přepážky) | výchozí u dvou pásem | ✅ |
| Poloviční | stěny do půlky výšky, **ukotvené ke dnu** | — | ❌ **v kódu není** |
| Dvířko | sklopné (dole zavěšené) dvířko na pantech místo pevné výplně | — | ✅ **vlastní tvar hotový** (`custom_shapes.id=552`), vkládání do konkrétní sestavy zatím neověřeno — viz níže |

**Co jde dnes postavit:** jedno pásmo (rám / rám + dna) a dvě pásma
(bez výplní / plné, s policí nebo bez), plus dvířka jako vlastní tvar
(viz níže). Poloviční výplně jsou zatím jen zadání, ne kód.

#### ⭐ Varianty 05 a 06 — rám kotvený k úhelníkům, ne k vrcholu nohy (2026-09-17, POTVRZENO Robertem)

Robert: *„ta původní verze 01-04 funguje dobře jen u některých aut a
některých vzdálenostech mezi nohama, přidejme variantu 05."* Místo
kotvení k vrcholu nohy (`yHornihoHor`/`yHornihoDol`, blízko stropu vozu
— proměnlivá rezerva auto od auta) se rám kotví **5 mm nad nejvyšším
úhelníkem** (`shape_geometry_methods.id=7`, `uhelnik-noha<i>`,
globální `Box3.max.y` přes celou sestavu) — na #127 to je 870,5 mm,
**186 mm pod vrcholem nohy**, tedy bezpečná rezerva nezávislá na tom,
kolik místa zbývá ke stropu.

| | Varianta 05 | Varianta 06 |
|---|---|---|
| Podélníky | 2, PRŮBĚŽNÉ přes celou sestavu | 2×(N−1), segmentované po PŮVODNÍCH sloupcích |
| Příčky | 2, jen na KRAJNÍCH nohách | N, na KAŽDÉ noze |
| Prostřední noha(y) | **zkrátí se** (stejný mechanismus jako u 01-04, cíl = `yDol`) | **nezkracuje se** — proto ji Robert zadal: *„výplně jako 05 ale nechceme zkracovat žádný nohy, tzn budou to sloupce původní"* |
| Kdy použít | méně dílů, když zkrácení prostřední nohy nevadí | když nohy musí zůstat v původní délce |

**Výplně (společné pro obě):** MDF dno; čelní podélník **plast 8mm do
výšky 89mm**; zadní podélník **MDF 8mm do výšky 130mm**; boční příčky
(05: jen krajní 2, 06: všechny) **MDF 8mm do výšky 130mm**. Montáž
stejnou technikou jako existující `panelSvisly()`/`vypln-bok-prepazka`
— zasun 7mm shora do drážky, dál roste nahoru.

**Ověřeno na #127** (0 kolizí se stěnami, 0 skutečných self-kolizí, 4/4
resp. 7/7 nových profilů dosedá celou plochou) a **potvrzeno Robertem**
(„hor blok varianta 05 budiž ok"). Vloženo přímo do scény jako sestavy
**#537** (var. 05) a **#538** (var. 06). Recepty:
`shape_geometry_methods.id=9`, klíče
`varianta_05_ram_nad_uhelniky_2026_09_17` a
`varianta_06_puvodni_sloupce_2026_09_17`. Číselník `horni_blok_varianty`
kód `05`/`06`. Skripty `scripts/2026-09-17_horni_blok_var05.js` a
`_var06.js`.

**Past nalezená a opravená cestou (06):** příčka spočítaná od vnějších
hran krajních noh dala jen 15mm překryv s vlastním podélníkem místo
30mm (částečně kryté čelo) — správně je to od VNITŘNÍ hrany jednoho
podélníku k vnitřní hraně druhého (analogie box-level „spojnice"
D−2T), stejně jako u 05.

#### ⭐ Dvířka horního bloku — ucelený postup (2026-09-18, konsolidováno)

Univerzální komponent (Robert: „dvířka jsou univerzální komponent na
různé regály") — nahrazuje `vypln-celo-*` (čelní výplň) kdekoli v
horním bloku, na libovolném vozidle/sestavě, NE jen na K-020. Tenhle
blok je JEDINÝ zdroj postupu pro **typ 1** (plný rám, výška ČISTÉHO
rámu z profilů BEZ pinu/dorazu **120–300mm** — 2026-09-18 zpřesněno
Robertem, dřív bylo 100mm; viz tabulka stupňů na konci); typy 2/3 jsou
jeden profil bez rámu, ale **od 2026-09-18 MAJÍ pant/šrouby stejně
jako typ 1** (přenesené beze změny z ověřeného typu 1, viz tabulka) —
liší se od typu 1 jen absencí rámu/dorazu, ne absencí pantu.

**Vznik zadání (chronologicky, pro dohledání přesných citací):**
„potřebujeme dvířka do horního bloku" → foto reálné montáže pantu →
„2 profily souběžné a na nich pant" → „my potřebujeme pant:
2.2.003.3030" → „spojovat pantem budeme profil 20x40 a podélníky hor
bloku" → Robert postavil referenční tvar ručně ve scéně → „dvířka
potřebují otočit, pant na čelní stranu a zalícovat profily dvířek s
profily podélníku z venkovní strany" → „dvířka snížit/zmenšit na
výšku zkrácením profilů na boku, aby konec podélného profilu dvířek
20x20 končil 40mm pod koncem nohou" → doraz + šroubové kroužky do
pantu → velikostní stupně a plastová výplň.

##### Krok 1 — Referenční tvar

⚠️ **OPRAVA (2026-09-18): `custom_shapes.id=552` V DB NEEXISTUJE** (ověřeno
přímým SELECT — žádný řádek). Robertem ručně sestavený vzor „dvířka 2040"
se nikdy neuložil pod tímhle číslem (stejný typ incidentu jako u
`product_assemblies#553` níže — INSERT selhal/nikdy neproběhl). **Jediný
skutečný zdroj je lokální soubor `shape552.json`** (scratchpad snapshot z
téhle session) — POUŽÍVEJ TENHLE, nikdy se nepokoušej znovu číst
`custom_shapes` pod číslem 552. 10 dílů, změřeno na reálné GLB
geometrii (ne na uložených scale/position hodnotách natvrdo — ty se v
kroku 3 přepočítávají):

| díl | role v tvaru | rozměr/poznámka |
|---|---|---|
| spodní příčel | `profil_20x40` + 2× záslepka `product_3150` | přes celou šířku dvířek, nese pant |
| 2× svislý sloupek | `profil_20x20`, nativně 160mm | sedí NA spodní příčli |
| horní příčel | `profil_20x20` + 2× záslepka `product_3070` | sedí NA sloupcích |
| 2× pant | `product_3219` („Plastový pant 3030", SKU 2.2.003.3030) | na VNĚJŠÍ straně spodní příčle, zasazené dovnitř od rohů |

Dvířka jsou **zavěšená na SPODNÍ hraně** (pant spojuje spodní příčel
dvířek s podélníkem horního bloku, POD kterým dvířka rostou vzhůru) —
sklápí se dolů/ven jako padací dvířka, ne do strany jako skříňová.

Hardware `product_3219`: `shop_products.visible_in_scene` musí být `1`
(jinak se vůbec neobjeví v `/api/katalog`, viz krok 5). Jeho GLB má
**3 samostatné mesh objekty** (2 listy + čep). `parseGlbMesh` je od
2026-09-18 čte všechny a od 2026-10-02 i všechna primitiva každého meshe
(dřív četl TICHE jen `meshes[0]`); co neumí (transformace uzlů, mód ≠
TRIANGLES, sparse accessor) hlásí `glbRizikaParseru()` / chybou. Pojistka
kolizního sweepu (`zkontrolujPokrytiParseru`, `scripts/2026-09-11_mesh_
kolize_lib.js`) odmítá už jen to — dřív odmítala každý vícemesh GLB a pant
tím od 2026-09-17 do 2026-10-02 shazoval celý přepočet kolizí.

##### Krok 2 — Najdi cílový otvor

Podélníkový segment (`podelnik-celni-06-<i>` nebo obdobná role dle
generátoru), jehož `vypln-celo-*` panel se nahrazuje, a jeho dvě
sousední nohy (typicky role `predni-svislice[-noha<i>]`).

##### Krok 3 — Přepočti cílovou šířku, výšku a pozici

Vše na REÁLNÉ GLB geometrii (`Box3`), ne na uložených číslech:

1. **Šířka**: `cílová_šířka = (podélník.max.z − podélník.min.z) − 2×KRAJ_VULE`.
   `KRAJ_VULE` brání kolizi sloupků/záslepek s nohou — na K-020 stačilo
   **7mm**, na K-019 bylo potřeba **14mm** (5,8mm skutečný přesah při
   7mm). Přesná příčina rozdílu mezi vozidly ZATÍM NEDOHLEDÁNA — před
   nasazením na nové vozidlo vždy přeměřit kolizním skenem, ne slepě
   převzít 7 ani 14.
2. **Dolní kotva** (spodní příčel, SPODEK): `podélník.max.y + 3mm` (GAP).
   Roste vzhůru odtud — **NIKDY dolů/pod podélník** (první pokus to
   spletl, umístil dvířka do noh/podlahy).
3. **Horní mez** (horní příčel, VRCHOL): `konec_noh.max.y − 40mm`
   (Robertovo pevné pravidlo, nezávislé na vozidle).
4. Z toho **délka sloupků** = horní_mez − (tloušťka horní příčle) −
   dolní_kotva − (tloušťka spodní příčle). Vyjde-li ≤ 0 (nebo hodně
   malá), otvor je pod hranicí typu 1 — viz tabulka stupňů, přepnout na
   typ 2/3.

##### Krok 4 — TUHÁ transformace celého tvaru (NE přepočet jednotlivých dílů)

⭐ Klíčové pravidlo, opakovaně porušeno a opraveno v této session: pant
(a obecně cokoli, co Robert ručně umístil v referenčním tvaru) se
**nikdy nepřepočítává vlastní formulí** — i kdyby výsledný směr vyšel
správně, přesné souřadnice už nejsou moje k určení. Postup:

1. Vezmi CELÝ tvar (všech 10 dílů) jako jednu tuhou skupinu.
2. Rotuj o 180° kolem SVISLÉ (Y) osy, kolem vlastního středu tvaru —
   otočí to, která strana je „venkovní/čelní" (pant skončí na správné
   straně), ale **nemění nic** na vzájemné poloze dílů uvnitř tvaru.
   Otáčí se pozice i quaternion KAŽDÉHO dílu stejně.
3. Posuň celou skupinu v X tak, aby VNĚJŠÍ (max-X) plocha rámu byla
   zalícovaná přesně s vnější (max-X) plochou podélníku.
4. Posuň spodní příčel (+ její záslepky) v Y na dolní kotvu z kroku 3.
5. Škáluj DÉLKU (Z) — jen `scale` komponentu odpovídající délkové ose —
   u OBOU dlouhých příčlí (spodní `profil_20x40`, horní `profil_20x20`
   s `scale[1]≈1.0`), faktorem `cílová_šířka/1000`. Sloupky, záslepky a
   panty se NEškálují (fixní/krátké díly), jen se přeposunou podél Z
   proporcionálně vůči středu cílového otvoru.
6. Sloupky: NEjen přeposunout — přeškálovat jejich vlastní délku
   (`scale[1]`) na hodnotu z kroku 3.4 a přepočítat jejich Y-střed
   (`dolní_kotva_top + nová_délka/2`).
7. Horní příčel + její záslepky: Y-přepozicovat na pásmo `[horní_mez −
   tloušťka_příčle, horní_mez]` (ne jen posunout o stejné delta jako
   spodní příčel — post-shortening to posouvá jinak).

##### Krok 5 — Doraz na horní hraně (vyplňuje 40mm mezeru ke koncům noh)

Protože horní příčel záměrně končí 40mm pod koncem noh (krok 3.3),
zůstává tam mezera — přemostěná párem „kvádr + pin" na KAŽDÉ straně
dvířek (2× celkem):

- **Kvádr**: zelený, zaoblený, 60×22×7mm, radius hran 0,6mm. Vlastní
  GLB (`kvadr_zaobleny_0.6mm_1x1x1.glb`) postaven ROVNOU v reálných mm
  se `scale:[1,1,1]` — neuniformní škálování jednotkové krychle by
  radius zdeformovalo elipticky (0,6/0,22/0,07mm po jednotlivých osách
  při škálování 60×22×7).
- Sedí NA horní příčli. Jeho VNĚJŠÍ konec (od středu dvířek směrem k
  noze) je zarovnaný PŘESNĚ na bližší plochu nohy — **nulové zanoření**.
  Nikdy necentrovat na střed nohy (první pokus prošel skrz nohu skrz
  naskrz — reálná chyba, opravená). Z 60mm délky ~53mm leží podepřené
  na příčli, ~7mm přemosťuje vzduchovou mezeru k noze.
- Navíc posunutý 2mm směrem k zadní straně regálu (−X v projektové
  konvenci, stejné jako `zadni-svislice` vs `predni-svislice`/`celní`
  napříč celým projektem).
- Na kvádru černý váleček `pin_valecek_10x20.glb` (10×20mm, vlastní GLB
  ručně sestavený — `THREE.GLTFExporter` v Node.js bez prohlížeče padá
  na `window.FileReader`), svisle, střed na STŘEDU KVÁDRU (ne na středu
  nohy).

##### Krok 5a — Doraz dvířek (červený FBX model, samostatný díl navíc)

⭐ **Doplněno 2026-09-20, doslovně od Roberta** (chybělo tu úplně —
poprvé postaveno jen jako typ2-specifický zápis v `shape_geometry_
methods#12`, 2026-09-19, odtud chybně vypadlo z tohodle návodu; platí
na VŠECHNY velikostní stupně, typ1 i typ2 i typ3):

- „Červený doraz dvířek se dotýká profilů dvířek z čelní strany, tam
  kde je pant" — vnější (čelní, stejná strana jako pant) plocha dorazu
  LÍCUJE s čelní plochou rámu/profilu dvířek (stejná plocha, na které
  sedí pant, ne plocha uprostřed průřezu).
- „Horní hrana dorazu lícuje s horní hranou profilu/rámu dvířek" —
  žádná drážka, žádné vystředění na průřezu, prosté zarovnání horních
  hran (0mm mezera/přesah).
- „Doraz přesahuje rám dvířek vlevo i vpravo o 10mm" — na KAŽDÉ straně
  dvířek (2× celkem) přesahuje svým vnějším koncem 10mm PŘES konec
  rámu/profilu (směrem k noze).
- Díl `doraz_dvirek.glb` (Robertův vlastní FBX export) má EXTRÉMNÍ
  lokální posun vrcholů (lokálně kolem Y≈−1900, Z≈2000 — vlastnost
  exportu, ne chyba) — počítej vždy se skutečným `Box3` po aplikaci
  rotace, nikdy s odhadem ze surové `position`, ta bude vypadat
  nesmyslně velká/vzdálená i při správném výsledku.
- Rotace: quaternion `[0.7071067811865476, 0, 0, 0.7071067811865476]`
  (+90° kolem X) — mění lokální rozměr 4×75×20mm na world 4×20×75mm.

##### Krok 5b — Záslepky: POČÍTAT geometricky, NEPŘEBÍRAT Robertovu ruční katalogovou pozici

⭐ **Změna postupu (2026-09-18, nahrazuje starší verzi tohoto kroku).**
Robert: „testovací tvar dvířka záslepky jsem tam vkládal z katalogu,
možná proto je neumíš nasadit na konce profilu... vlož je jako objekty
znovu sám" + „ve 2 dvířkách bude chybět záslepka ode mě, ty můžeš
odstranit, tam svoje." Na rozdíl od pantu (krok 4 — Robertova ruční
poloha je tam ZÁMĚRNÁ volba a MUSÍ se zachovat tuhou transformací, viz
`VLASTNOSTI_PROFILU.md`) je záslepka MECHANICKÝ, univerzální díl —
stejně sedí na konci JAKÉHOKOLI profilu odpovídajícího průřezu, takže
se nemá přebírat žádná konkrétní ručně tažená pozice ze šablony.
Robertovo vlastní ruční umístění (odkud vzešla i `shape552.json`
šablona) bylo nepřesné právě proto, že šlo o rychlé přetažení z
katalogu, ne o schválenou volbu jako u pantu.

**Správný postup (změřeno přímo na `product_3150`/`product_3070`/
`product_3130`, identity pose, rozlišení 0,01mm po VŠECH distinct Z
hladinách vrcholů — ne jen hrubý bbox):** všechny 3 záslepky stejné
rodiny mají lokální `Z=[0,7]`, ale hranice limec/zobák NENÍ na `Z=0`.
Plná šířka/výška (odpovídá průřezu profilu = LÍMEC) drží PŘESNĚ od
`Z=0` do `Z=3,00mm` (bit shoda na `product_3150` i `product_3070`) —
teprve OD `Z=3,0` DÁL (do `Z=7,0`, tedy 4mm) je užší ZOBÁK. ⭐ **Limec
(Z=0 až 3) musí zůstat VENKU profilu, dovnitř zapadá jen zobák (Z=3 až
7) — první verze tohohle kroku kotvila omylem `Z=0` (vnější, viditelná
plocha límce) na konec profilu, čímž byl CELÝ límec zasunutý dovnitř.
Robert: „ty záslepky tam máš zalícované s koncem profilu zapadlé
vevnitř, tak se nenasazují — vevnitř je zapadlý správně jenom ten
zobák"** (2026-09-18, přímá oprava). Kotvicí bod je tedy `Z=3,0`
(zadní/vnitřní plocha límce = tam, kde limec přechází v zobák), NE
`Z=0`. Obě osy X/Y jsou souměrné kolem 0, žádný další středový posun
není potřeba. Protože rám dvířek je vždy osově zarovnaný (délka příčle
= world Z, průřez = world X/Y):
- na konci profilu s MENŠÍM world Z: `quaternion=[0,0,0,1]` (identita),
  `position=[středX_profilu, středY_profilu, profil.min.z − 3,0]`
- na konci s VĚTŠÍM world Z: `quaternion=[0,1,0,0]` (180° kolem Y),
  `position=[středX_profilu, středY_profilu, profil.max.z + 3,0]`

(odečtení/přičtení `3,0` = COLLAR_DEPTH, kompenzuje že se kotví bod
posunutý o límec dovnitř dílu, ne jeho vnější okraj). Ověřeno přímým
přepočtem lokálního bodu `(0,0,3.0)` přes `quaternion+position` na
#552/#553/#554: světová Z souřadnice zadní plochy límce sedí na konci
profilu na 0,000mm přesnost (bit přesná shoda). Zobák pak zasahuje
přesně 4mm do profilu (`7,0−3,0`) po celém svém (užším) průřezu — to
je OČEKÁVANÝ mesh-kolizní nález mezi zobákem a profilem (profil nemá
modelovanou skutečnou dutinu, stejný obecný jev jako v
`PRAVIDLA_SPOJU.md`, sekce „i skutečný mesh test... může ohlásit
kolizi, která je záměr", 2026-09-11, bot16/bot3/Robert — tam šlo o
jinou konkrétní konstantu `odsun=5,25mm` pro jiný pár GLB, princip je
stejný). Límec (Z=0 až 3, VENKU) naproti tomu s profilem NESMÍ mít
žádný objemový průnik. ⭐ **Kdykoli mesh kolizní test na pár
`<rail-role> + <cap-role>` u TOHOTO pravidla narazí, je to
zobák-do-dutiny (max 4mm zásah, jen v rozměru zobáku), NEOPRAVOVAT jako
nález — pokud by kolize zasahovala i do rozměru límce, TO by naopak
byla skutečná chyba.**

✅ **Robert potvrdil přímo ve scéně (2026-09-18, `custom_shapes#554`
"dvířka - limitní verze"): „potvrzuji správné nasazení záslepek."**
Tímhle je geometrie záslepek uzavřená jako hotová (kanonický postup
učení dílů, finální krok), ne dál otevřená k ověřování.

Aplikuje se na KAŽDÝ profilový konec dvířek, i typ2/typ3 (dřív bez
záslepek vůbec — Robert: „jsou tam profily, vlož do všech záslepky"):
`profil_20x40`→`product_3150`, `profil_20x20`→`product_3070`,
`profil_20x80`→`product_3130`.

##### Krok 6 — Šroubové kroužky v otvorech pantu ⚠️ ODSTRANĚNO, NENÍ SOUČÁSTÍ AKTUÁLNÍ STAVBY

⚠️ **STAV (2026-09-18, ověřeno zpětně přes AGENTS_LOG, ne z paměti):** i
po PŘESNÉM geometrickém měření (viz níže, 0,000mm od skutečných otvorů)
Robert s vizuálním výsledkem nebyl spokojený a řekl doslova: „opakuji
kdyz neumis ty kolecka priblizit k dirkam pantu tak je radeji smazej
vsechny." **Kroužky byly odstraněny ze VŠECH míst** (`custom_shapes#554`,
`product_assemblies#552`, tehdejší #553) a zapsáno „nezkoušet stejný
postup znovu bez nového podnětu od Roberta." Tenhle krok je tedy
**HISTORICKÝ ZÁZNAM ŘEŠENÍ, NE aktuální součást stavby** — nová dvířka
(typ1/2/3) se dnes staví BEZ šroubových kroužků. Zbytek kroku 6 níže
zůstává zapsaný jen jako podklad, kdyby se k tomu Robert sám vrátil s
novým zadáním — nekopírovat do nové stavby bez výslovného pokynu.

Metoda měření (platná, kdyby se krok někdy obnovil):

⭐ **Pozice der (2026-09-18, finální, PŘESNĚ ZMĚŘENO — nahrazuje starší
odhad).** Robert po vizuální kontrole: „ty bílé kruhy jsou jen u pantu
bounding boxu, ale musí se dotnout těch otvorů" — dřívější odhad
X/Z pozic (z fotky + hrubé shlukování vrcholů) byl reálně vedle
otvorů, ne v nich. Nahrazeno přesným měřením přímo na
`product_3219.glb`: pro každý list (`Solid_0`/`Solid_1` v GLB, čteno
přímo z glTF accessors, ne přes `parseGlbMesh` který čte jen
`meshes[0]`) postavena top-down **hloubková mapa** (raycasting po
0,3mm mřížce, `THREE.Raycaster` shora dolů) a na ní `scipy.ndimage.label`
(souvislé oblasti bez zásahu = skutečné průchozí díry, ne jen odhad z
obálky). Výsledek — **4 díry celkem, 2 na každém listu** (potvrzuje
původní počet z fotky, jen pozice byla špatně):
- list A (`Solid_0`, lokální X≈9,5): `X=9,49 Z=−14,99` a `X=9,49 Z=15,01`
- list B (`Solid_1`, lokální X≈40): `X=39,99 Z=−14,99` a `X=39,99 Z=15,01`
- průměr díry ~6,6mm (poloměr z plochy 3,31mm)

Kroužky = nový samostatný díl `sroub_disk_7x1` (Robert: „musí jakoby
zaplnit ty otvory... material kovovost 80%, lesk" — průměr 7mm, mírný
přesah přes 6,6mm otvor, `metallicFactor=0,8 roughnessFactor=0,18`
přímo v GLB materiálu; **NENÍ to zmenšený `pin_valecek_10x20`** jako v
předchozí verzi — ten má vlastní matný černý materiál pro doraz, jiná
role/vzhled). Sedí na VNĚJŠÍ/viditelné ploše pantu (lokální Y≈15,5,
zapuštěno 0,5mm = licuje s plochou, ne montážní plocha Y≈0). ⭐ **Patří
VŽDY, kdykoli je přítomný pant** — nezávisí na dorazu/kroku 5 (ten
potřebuje referenci "konec noh", která u samostatného/vzorového
dvířka bez sestavy neexistuje) — u samostatných dvířek (bez sestavy)
doraz logicky chybí, ale šroubky se přesto doplňují na každý pant.

##### Krok 7 — Plastová výplň

Robert: „do rámu dvířek se vkládá plast síly 6mm, zapadne do drážek
profilů cca 4mm" + „plast se vkládá automaticky pokud mu vyjde větší
výška než 70mm" + „výplň nesahá do drážek profilů, zapuštění 4mm" +
„barva plastu světle šedá".

- **Podmínka vložení**: čistá mezera mezi vnitřními hranami spodní a
  horní příčle (bez jakéhokoli odečtu) musí vyjít **> 70mm**.
- **Výška desky**: `čistá_mezera + 2×4mm` — deska je VĚTŠÍ než čistá
  mezera, ne menší (⚠️ první pokus měl znaménko obráceně — odečítal
  4mm místo přičtení, takže nechal 4mm VZDUCHOVOU mezeru na každé
  straně místo zapuštění do materiálu). Deska se tedy o 4mm zasune DO
  KAŽDÉ příčle (nahoře i dole), přesně jako `vypln-*` desky jinde v
  projektu zapadají do drážky — jen s vlastní hodnotou zásunu 4mm
  (jinde v projektu 7mm).
- **Šířka desky**: `šířka_otvoru − 2×20mm` (mezi sloupky, NE přes ně —
  sloupky jsou 20mm široké na každé straně).
- **Barva**: světle šedá (`#c8c8c8`), ne namodralý odstín.
- **Katalogový díl**: zatím žádný vyhrazený (6mm plast se v projektu
  jinde nepoužívá). Provizorně `product_3950` (nativně 8mm MDF šedá,
  `deska_mdf_seda_8.glb`, 1000×1000×8mm) s přeškálovanou tloušťkou na
  6mm (`scale.z = 6/8` PŘI SPRÁVNÉM pořadí os — GLB má nativně
  X=1000/Y=1000/Z=8, quaternion pro svislou stěnu `[0,0.7071,0,0.7071]`
  otočí lokální Z→world X, lokální X→world Z, lokální Y→world Y; první
  pokus měl osy popletené a vyšla mu skutečná tloušťka 8mm místo 6mm).
  Až bude materiál/produkt v katalogu, nahradit.

##### Ověření (povinné před vložením do scény)

Stejná disciplína jako u zbytku horního bloku: box-based kolizní sken
nových dílů proti VŠEM stávajícím (kromě karoserie), `verifyAssembly()`
(produkční funkce) proti stěnám karoserie, `jeZamernyZasun`-styl filtr
pro rozlišení skutečné kolize od záměrného zásunu (~≤7,5mm na jedné
ose). ⚠️ Produkční mesh-kolizní sweep (`api/kolize_priznak.prepocti`,
render gate pro bota4) na sestavu s pantem SELŽE (vícemesh GLB, viz
krok 1) — `kolize_pocet` zůstává `NULL` (správně, ne falešná nula),
dokud parser nerozšíří podporu.

⚠️ **Past nalezená 2026-09-18 (#552 měla 244 dílů místo ~133):**
opakovaný cyklus "SELECT parts → uprav v paměti → UPDATE" na tutéž
sestavu může TICHOU chybou zdvojit skoro všechna data (přesný okamžik
vzniku nedohledán), bez jakékoli chybové hlášky - transakce proběhne
v pořádku. **Vždy po zápisu zkontrolovat SKUTEČNÝ počet dílů** (SELECT
zpět, porovnat s očekávaným před+nově přidané), ne jen že UPDATE
neshodil chybu.

#### ⭐ Velikostní stupně dvířek (2026-09-18)

Tři konstrukční stupně podle dostupné výšky otvoru (vnější hrana
profilů, tj. výška celého rámu dvířek — krok 3 výše):

| výška rámu | provedení | výplň |
|---|---|---|
| **120–300mm** | **typ 1** — plný rám, krok 1–7 výše, + doraz (krok 5) + pant/šrouby (krok 4/6) | plast 6mm, zasun 4mm — jen když výška výplně > 70mm |
| = 80mm (pevně, `profil_20x80`) | **typ 2** — jen JEDEN profil, ale hraje roli spodní příčle: **MÁ pant + doraz** stejně jako typ 1 (šrouby ODSTRANĚNY, viz krok 6) | nezadáno |
| < 80mm (`profil_20x40` a menší) | **typ 3** — sklopný `profil_20x40` samotný, BEZ `profil_20x20` rámu, ale **MÁ pant + doraz** stejně jako typ 1/2 (šrouby ODSTRANĚNY, viz krok 6) | nezadáno |

⭐ **Mezi 80mm a 120mm ŽÁDNÁ výška dvířek neexistuje** (Robert
2026-09-18, přesná citace: „minimum vysky ciste ramu z profilu (bez
pinu): 120mm, maximum 300mm, tzn. ze neexistuje výška dvirek (pokud
se tyče velikosti ramu) mezi 120 mm a 80mm(typ2)") — není to otevřená
otázka/odhad, je to záměrná mezera ve stupních. Typ 2 je navíc PEVNÁ
hodnota (80mm, daná průřezem `profil_20x80`), ne rozsah.

Panty na typu 2 i 3 (a stejně tak doraz kdekoli, kde chyběl — 2026-09-18
doplněn i na typ 1 v `custom_shapes#554`, dřív omylem chyběl) se NEpočítají
vlastní formulí — **Y/Z offset od rohu profilu (z šablony) se přenáší**,
ale POZOR na dva reálné nálezy z prvního pokusu v živé sestavě
(`product_assemblies#552`, 2026-09-18):

- ⚠️ **OPRAVA v4 (2026-09-18, nahrazuje předchozí — chybné — tvrzení
  o poměrném přepočtu):** dx/dy offset (X kolmo na profil, Y svisle) se
  přenáší BEZE ZMĚNY vždy, nezávisle na šířce. **Z offset ALE NENÍ
  poměrný k šířce dvířek** — je to **PEVNÁ vzdálenost od nejbližšího
  konce profilu, cca 126–130mm**, stejná bez ohledu na celkovou šířku.
  Zjištěno křížovým porovnáním dvou NEZÁVISLÝCH Robertem umístěných
  vzorů: `product_assemblies#552` sloupec 06-0 (818mm šířky, pant
  129,5mm od konce) vs `custom_shapes#554` typ2 vzor (800mm šířky, pant
  126,7mm od konce) — kdyby šlo o poměr k šířce, vyšlo by 84 % vs 16 %
  (naprosto různé číslo), kdežto pevná vzdálenost sedí na 3mm přesně
  mezi oběma nezávislými vzorky. **Nikdy nepočítej `scaleFactor` pro
  tenhle konkrétní offset** — vezmi přesnou hodnotu (~127mm) přímo z
  `custom_shapes#554` (autoritativní recept-vzor, potvrzeno Robertem
  „vzor dvířek je recept na limitní dvířka").
- ⚠️ **Další past, stejný den:** X offset se měří vůči **PIVOTU baru**
  (`bar.position[0]`, střed průřezu), ne vůči jeho změřenému okraji
  (`Box3.min.x`/`max.x`) — musí se tak i APLIKOVAT
  (`novy_pant.x = novy_bar.position[0] + offset`), jinak vznikne posun
  o polovinu tloušťky baru (~10mm u `profil_20x80`).
- **X pozice profilu/rámu se MUSÍ MĚŘIT, ne odhadovat vzorcem s
  konstantou.** Chybný první pokus použil `targetX = podelnik.max.x +
  10` (nepochopená kopie kusu vzorce z jinam kontextu, kde se +10/−10
  jinde rušily) — vzniklo tím 20mm mezera mezi pantem a podélníkem.
  Správně: postavit profil na zkušební pozici, **změřit jeho skutečný
  Box3**, dopočítat přesný posun tak, aby `profil.max.x` skončil
  PŘESNĚ na `podelnik.max.x` (0,000mm rozdíl, žádná odhadovaná
  konstanta).

⭐ **Kontrolní kritérium (Robert 2026-09-18: „panty se musí dotýkat
podélníku horního bloku"): pant musí mít se svým podélníkem PLNÝ
dotyk/přesah na všech 3 osách** (X≈0 flush, Y a Z kladný přesah) —
přesně stejné měřítko jako u spodní příčle typu 1 na kterémkoli už
hotovém sloupci (tam to odjakživa funguje, protože rail.max.x tam
vychází == podelnik.max.x). Po každé stavbě typu 2/3 v reálné sestavě
tohle přímo změřit (`overlap3(podelnik, pant)`), nespoléhat na to, že
kolizní sken „0 neočekávaných" sám o sobě dokazuje dotyk (může to
znamenat i „mezera, žádná kolize" stejně dobře jako „dotyk").

⭐⭐ **Poučení o zpětné kontrole (Robert: „typ1 dvirka maji vysku ramu
85mm... evidentne si to zapomnel nebo nezapracoval"): když se zavede
NOVÉ pravidlo/limit dodatečně (jako 120mm minimum pro typ 1), musí se
zpětně přeměřit VŠECHNY už postavené instance podle NOVÉHO pravidla,
ne jen napříště dodržovat u nových.** Sloupec `06-0` v `#552` (úplně
první instalace dvířek v tomhle projektu, postavená předtím, než 120mm
minimum vůbec existovalo) měl taky jen 85mm a zůstal neopravený, dokud
na to Robert sám neupozornil.

⚠️ **OPRAVA (2026-09-18): `product_assemblies.id=553` V DB NEEXISTUJE**
(ověřeno přímým SELECT + AUTO_INCREMENT stav + prázdný `audit_log` pro
tohle id — INSERT nikdy skutečně neproběhl, viz AGENTS_LOG 2026-09-18
"retrakce"). Předchozí věta o "první reálné aplikaci všech tří stupňů na
K-019 A" popisovala objekt, který nikdy nevznikl — BEROU SE ZPĚT. Reálná
aplikace typu 2 na existující sestavě s doraz+pant+záslepky (dotyk na
podélníku ověřen): `product_assemblies.id=552`, sloupce 06-0 i 06-1 (oba
přestavěny na typ 2, viz AGENTS_LOG 2026-09-18). Druhé vozidlo (Jumpy L3
K-124, `product_assemblies.id=540`): první pokus 2026-09-18 skončil
špatně umístěným hardwarem (pant/doraz roztroušené mimo dveře, viz past
"pivot vs okraj" výše) a byl vrácen na zálohu. Robert: "nepatlej se ve
starych spatnych vytvorech, udelej novou sestavu" — založena nová
`product_assemblies.id=554` (kopie #540), sloupec 1 (06-0) postaven
znovu krok za krokem s opraveným vzorcem, vizuálně ověřen čistý
výsledek (viz AGENTS_LOG). Sloupec 2 čeká na stejný postup.

#### ⭐⭐ Pravidlo výběru a umístění (Robert 2026-09-18, doslovný zápis)

⚠️ **OPRAVENO 2026-09-18 (Robert): „máš to správně podle postupu, ale v
postupu mám chybu já, tak jak jsou dvířka nakreslená musím podmínku
změnit."** Bod o kvádrech níže byl PŮVODNĚ „kvádry se dotýkají nohou"
(zero-gap) — Robert to sám opravil na „záslepky mají mezeru od noh
3mm" po pohledu na aktuální vzor. Aktuální, opravená verze pravidla
(doslovný zápis, ověřeno na `#554`, viz níže):

1. **Najde se čelní podélník**, který buď (a) obsahuje výplň plastem,
   MDF, nebo překližkou (PR10), NEBO (b) má po celé své délce nad sebou
   volný prostor min. **60mm**. Tohle rozšiřuje dosavadní kritérium
   "existuje `vypln-celo-*`" — i podélník BEZ jakékoli výplně, jen s
   dost velkou volnou výškou nad sebou, je kandidát.
2. **Pokud zadání neurčí konkrétní pozici**, dvířka se aplikují na
   VŠECHNY takové podélníky nalezené podle bodu 1 (ne jen na jeden,
   pokud není řečeno který).
3. **Umístění — dvířka jako CELEK** (tuhá skupina, stejný princip jako
   krok 4 výše), posazená NAD podélník:
   - pant se dotýká čela podélníku (stejné jako dosavadní pravidlo
     flush-dotyku výše),
   - ⭐ **2 spodní otvory pantu jsou přesně středem na střed drážky
     čelní strany/stěny podélníku** — NOVÉ, přesnější kritérium než
     dosavadní empirický odstup od kraje. Podélníky v katalogu (viz
     `Object_7` generický profil, měřeno 2026-09-18) mají T-drážku
     symetrickou kolem osy profilu (`X=[±3.15, ±4.19, ±7.1, ±9.11,
     ±10]` v lokálním průřezu) — střed drážky = lokální 0 dané osy,
     přepočtený do world souřadnic přes skutečnou pozici/rotaci
     podélníku. **Před prvním použitím na reálné sestavě přeměřit
     přesně, která osa/rovina je "čelní strana" u KONKRÉTNÍHO profilu
     použitého jako podélník** (u #552/#540/#554 je to generický
     `Object_7`, ne nutně stejný profil jako jinde v katalogu).
   - ⚠️ **OPRAVA: záslepky (NE kvádry) mají mezeru od noh (levá noha /
     pravá noha) 3mm** — nahrazuje dřívější "kvádry se dotýkají noh
     bez mezery". Určuje CELKOVOU ŠÍŘKU/POZICI dveří: záslepka má sama
     o sobě (změřeno přesně) přesah 3,000mm PŘED koncem baru (kotvicí
     Z=3,0 formule, krok 5b) — cílový konec baru je tedy `konec_nohy ∓
     6,0mm` (3mm přesah záslepky + 3mm požadovaná mezera), NE konec
     podélníku a NE dotyk kvádru. Doraz (kvádr+pin) se dál umísťuje,
     ale JEN podle vlastního fixního odstupu od konce baru (30mm,
     půlka jeho 60mm délky, přímý přenos ze vzoru), BEZ vlastní vazby
     na polohu nohy.
   - **na plnou výšku volného prostoru**, pokud zadání neuvádí
     konkrétní výšku,
   - **pin (doraz) má mezeru od jakéhokoli objektu nad svou rovinou min.
     10mm** (bezpečnostní vůle, ne dotyk/zanoření).

✅ **Ověřeno a zapsáno na `product_assemblies#554`, sloupce 06-0 i
06-1 (2026-09-18).** Aktuální vzor pro přesné hodnoty (pant, záslepka,
doraz vůči baru): `custom_shapes.id=558` „dvířka 20 vzory" (nahrazuje
dřívější #554 jako zdroj — Robert aktualizoval geometrii vzoru).
Změřeno bod po bodu: střed 2 spodních otvorů pantu (list se
záslepkovou dvojicí na VĚTŠÍM lokálním X pantu, po rotaci mapuje na
world Y) = střed drážky (Y-střed symetrického profilu podélníku),
rozdíl 0,000mm; pant-podélník dotyk X=0,000mm; záslepka-noha mezera
3,000mm na obou koncích obou sloupců; vůle pinu 21,16mm (≥10mm
požadováno); 0 neočekávaných kolizí.

**Samostatné limitní vzorky (bez sestavy/karoserie)**: `custom_shapes.
id=554` „dvířka - limitní verze", **očíslováno 1–4** (Robert: „očísluj
ty dvířka ať to můžu popsat co s tím ještě chci") — **1**=typ 3,
**2**=typ 2, **3**=typ 1 @ **120mm** (min, přepočteno z dřívějšího
neplatného 100mm — 2026-09-18), **4**=typ 1 @ 300mm (max, s plastem),
šířka 800mm u všech. Rozmístěna VEDLE SEBE
podél osy KOLMÉ na dvířka samotná (osa X, rozestup 250mm) — ne v jedné
řadě podél osy dvířek samotných (Z), jak byla první, špatně pochopená
verze („poskládej v opačném směru" myšleno „v kolmém směru", ne
„v obráceném pořadí podél stejné osy"). Každé dvířko má plovoucí 3D
popisek (`text_labels`) s číslem/typem/výškou/šířkou/stavem plastu.

✅ **Robert potvrdil (2026-09-18): „aktuální stav dvířek v souboru
limitní dvířka je technicky ok."** Celý postup (kroky 1–7 + velikostní
stupně výše) je tímto uzavřený jako hotový a funkční, ne dál otevřený
k ověřování — zapsáno i jako DB recept, viz `reference_dvirka_recept_db.md`
/ `shape_geometry_methods.id=12`.

#### ✅ Eko — potvrzeno Robertem ve scéně 2026-09-10 (náhled `id=332`)

Doslova: *„eko ok, trubky jen na profily, ten poslední první vrstvu zastaví
další ne, nevadí, je to eko."*

Čti takto: ve variantě bez výplní **nejsou žádná dna** — dlouhé předměty
(trubky, tyče, lišty) leží **přímo na profilech** rámu. Dorazová příčka
u přepážky zastaví jen **první, spodní vrstvu**; co leží na ní, už doraz
nepřevyšuje a nezastaví.

⚠️ **Robert o tom ví a přijímá to** — je to ekonomická varianta, ne
nedodělek. Neopravovat: nezvyšovat kvůli tomu doraz a nepřidávat dna. Kdo
chce obsah zajištěný, vezme si jinou variantu z kroku 4.

Spuštění (opraveno 2026-09-10 — dřívější znění uvádělo přepínač
`--nad-boxy`, který v kódu **neexistuje** a tiše se ignoruje):

```bash
node scripts/2026-09-05_horni_ram.js <dump.json> --vozidlo=<karoserie> \
     [--jedno-pasmo] [--bez-police] [--bez-vyplni] [--json]
```

Podrobnosti ke konstrukci: podélníky v HORNÍM pásmu jdou v jednom kuse přes
zkrácené střední nohy (T-styl), ve SPODNÍM pásmu jsou segmentované po
nohách — to platí pro stav po volbě „dvě pásma", viz krok 2. Výplně (MDF 8mm,
`product_3939`/SKU 382223) zajíždí 7mm do drážky, držené na ≥4 hranách.

**Implementace:** `scripts/2026-09-05_horni_ram.js` — obecný nad libovolnou
sestavou se standardními rolemi (`predni-svislice`/`cap`/`eurobox-*`), NE
napsaný natvrdo pro CI25. Zápis do DB: `scripts/2026-09-06_zapis_bom_do_db.py`
jako vzor bezpečného MERGE (mění jen dotčená pole, neexistuje riziko
přepsání `parts`/`join_groups` navíc).

**GENERALIZACE OTESTOVÁNA (2026-09-06) na Vivaro OP18 (`id=57`, jiné auto)
beze změny kódu** — s poučným, ne bezproblémovým výsledkem:
- Metoda (algoritmus, T-styl pravidla, odvození pásem) **je přenositelná** —
  na OP18 vyšlo jiné číslo (250mm světlé místo 200mm na CI25), přesně jak se
  čekává, když se vždy měří z aktuální geometrie.
- **Nalezena a částečně opravena generalizační mezera:** OP18 pojmenovává
  záslepky jinak (`zaslepka-cap`/`zaslepka-predni-svislice` místo prostého
  `zaslepka`) — oprava na tolerantní prefix test, zbytek (přesné dohledání
  Z pozice) není dotažený, ale je to jen kosmetický nedostatek.
- **Důležitější nález: metoda SPRÁVNĚ odhalila skutečnou kolizi** — 7 nových
  dílů na OP18 koliduje se skutečnou karoserií i s existujícím nosníkem
  `spojnice-horni`. **Závěr: metoda je přenositelná, ale KAŽDÉ VOZIDLO
  VYŽADUJE VLASTNÍ KOLIZNÍ OVĚŘENÍ před zápisem do DB** — nikdy neaplikovat
  naslepo jen proto, že to na jiném autě prošlo. OP18 proto **NEBYL zapsán
  do DB**, zůstává jen jako diagnostický test — přesně podle WORKFLOW.md
  ("konflikt, který nelze bezpečně vyřešit narychlo, zapsat pro rozhodnutí,
  ne narychlo obejít").

Tohle přesně odpovídá tomu, co Robert označil jako budoucí práci:
*"budeme dolaďovat technické vlastnosti a rozměry 3D modelů a částí
dodatečně (hlídání pravidla mezery 30mm nad euroboxem, apod.)"* — metoda
sama o sobě je hotová a přenositelná, ale prostorová rezerva na konkrétním
autě je proměnná, kterou je nutné ověřit case-by-case, ne převzít.

### Doplnění 2026-09-06 (bot8): oprava mezery 4mm→30mm + hloubka podle zúžení karoserie

Práce zůstává striktně u vzorové sestavy Jumpy L2 CI25 (`id=189`/`id=187`) —
*"opakuji, řešíme to jedno Jumpy jako vzor"* (Robert, opakováno 2x), žádný
jiný Jumpy sourozenec (CI13/15/18/19/24/26) ani jiné vozidlo se v této fázi
netrhá.

**Oprava mezery nad boxy:** spodní hranice spodního pásma horního bloku
používala omylem `MEZERA=4mm`. Robert opravil: *"V této větvi už máme
konkrétní 1 variantu boxu hotovou ale varianty boxů se mohou měnit tím
pádem se bude měnit výška posledního boxu k tomu mezera 30 milimetrů
povinná a teprve tam může začínat horní blok"* — tedy stejná povinná 30mm
mezera jako mezi patry boxů (`Y_rail_top(N+1) = Y_rail_top(N) + H_box(N) +
30mm + T`). Na CI25 to snížilo světlou výšku horního bloku z (chybných)
200mm na (správných) 174mm — ověřeno bez regrese (0 kolizí).

**Horní regálový blok (oficiální název, ne "horní blok pro dlouhé
předměty") s hloubkou podle zúžení karoserie:** Robert: *"podle karoserie
které jsou většinou nahoře užší musíme mít: horní regálový blok... bude
všude tam kde je členitá noha pod běhu to znamená horní část toho bloku má
menší hloubku než hlavní část regálu"*. Ověřeno měřením (`profil_zuzeni.js`
raycast): karoserie CI25 se v pásmu horního bloku zužuje ~103mm, zatímco
v pásmu hlavních boxů jen ~14mm — horní blok proto potřebuje vlastní,
mělčí zadní linii, ne kopírovat hloubku `cap` nohy.

Implementace (`scripts/2026-09-05_horni_ram.js`, viz `shape_geometry_
methods.id=9` algoritmus 8/9 pro plné znění): raycast na skutečnou stěnu
karoserie v pásmu horního bloku → bezpečná X s rezervou `MIN_MEZERA_KE_
STENE=20mm` → všechny zadní podélníky/příčky/výplně horního bloku (NE
samotné `cap` nohy, ty zůstávají nedotčené) se staví na této posunuté
linii. Konzola/bracket premosťující `cap` a posunutou linii se staví JEN
když `abs(posun) > T` (30mm, půlka šířky profilu) — při menším posunu
(CI25: 14,2mm) se footprinty profilu ještě přirozeně překrývají a žádný
bracket není potřeba; naivní "vždy bracket" implementace při malém posunu
vyrábí zápornou/protnutou přemosťovací délku, kterou kolizní kontrola
správně odhalí jako zanoření do `cap` (na CI25 přesně 15,8mm, `T/2 +
(T/2-posun)`). Bracket-větev (posun > 30mm) zůstává **zatím neověřená na
žádném reálném autě** — CI25 do ní nespadl.

Stav k 2026-09-06: 0 kolizí s díly, 0 kolizí s karoserií, regresní sada
zelená. **Zatím NEZAPSÁNO do `product_assemblies.id=189`** — čeká na
Robertovo schválení výsledku (viz `AGENTS_LOG.md`).

### Aktualizace pravidla 2026-09-07 (Robert) — pozice příček vrchních noh vůči úhelníku

**Pravidlo (Robert, doslovně): "příčky mezi předními a zadními vrchními
nohami posunovat dolu až k pozici vzdálené 5mm od nejbližšího
úhelníku."**

Týká se příček horního regálového bloku (role `pricka-horni-*` ve
`scripts/2026-09-05_horni_ram.js`, spojující přední a zadní svislý
profil KAŽDÉ "vrchní nohy" horního bloku napříč hloubkou) — jejich
vertikální (Y) pozice se má posunout DOLŮ oproti současnému umístění,
až na 5mm vzdálenost od nejbližšího úhelníku (spojovací úhelníkové
spojky na spojích vrchní nohy, `shape_geometry_methods.id=7`
`uhelniky-na-spoje-nohy`).

**Stav: zapsáno jako pravidlo, NEIMPLEMENTOVÁNO.** `scripts/
2026-09-05_horni_ram.js` v současné podobě příčky horního bloku staví,
ale žádné úhelníky na spoje vrchních noh horního bloku ještě nepřidává
(`applyUhelnikyToLeg()` byl dosud aplikován jen na hlavní/dolní nohy,
viz sekce výše "Celá rodina Citroën/e-Jumpy") — implementace týhle
aktualizace tedy nejdřív potřebuje úhelníky na spojích vrchní nohy, a
teprve podle jejich skutečné (změřené, ne odhadnuté) pozice dopočítat
novou Y pozici příčky. Než se to udělá, POUŽÍT tohle pravidlo při
příštím kroku prací na `id=189`/horním bloku, ne teoreticky diskutovat
znovu.

### Doplnění 2026-09-07 (bot8) — verifikační díra (úhelníky) + REÁLNÁ kolize na obou Doblech

Při aplikaci na Doblo K-075 (`id=134`) a Doblo Maxi K-078 (`id=135`,
Robert: "obě dobla") se ukázalo, že `bboxDilu()`/`glbSoubor()` v
`scripts/2026-09-05_horni_ram.js` neuměl `product_3045` (úhelníková
spojka) — soubor `product_3045.glb` neexistuje (skutečný je
`product_2895.glb`, stejná past jako jinde v projektu). `bboxDilu()` na
tenhle part_id TICHE vracel `null`, takže se úhelníky nikdy nedostaly do
`analyzuj().dily` a **kolizní kontrola je celou dobu (i u CI25 vzoru)
vůbec netestovala** — `kolize s dily: žádná` bylo neúplné tvrzení, ne
chyba. Opraveno (`GLB_MAP.product_3045 = "product_2895.glb"`).

**Po opravě CI25 vzor (`id=187`/`189`) zůstává 0 kolizí** — beze změny.

**Po opravě OBĚ Dobla (id=134 i id=135) mají REÁLNOU kolizi:**
`pricka-spodni-prepazka` a `vypln-dno-*` (spodní pásmo horního bloku,
Y=[934.5,964.5]) narážejí do úhelníků na spoji `spojnice-horni`↔`cap`/
`predni-svislice` (na všech 3 nohách, Y=[921.5,950.5] — 16mm překryv).
U CI25 tenhle konflikt není (jiná geometrie/výška boxů dává víc rezervy
u vrcholu). **Přesně odpovídá dřívějšímu nálezu na Vivaru OP18** (jiná
karoserie, jiné místo kolize, stejný princip: "KAŽDÉ VOZIDLO VYŽADUJE
VLASTNÍ KOLIZNÍ OVĚŘENÍ před zápisem do DB").

**Obě Dobla NEBYLA zapsána do DB** — čeká na Robertovo rozhodnutí (viz
`AGENTS_LOG.md`), stejně jako WORKFLOW.md ("konflikt, který nelze
bezpečně vyřešit narychlo, zapsat pro rozhodnutí, ne narychlo obejít").

### Aktualizace pravidla 2026-09-07 (Robert) — příčky/podélníky horního bloku musí lícovat s profily noh, ne jen "bezpečně" viset u nich

**Pravidlo (Robert, doslovně): "příčky mezi horními svislicemi nohou v
horním bloku musí být dotaženy ke stěnám profilů nohou přesně na dotyk,
příčky i spojnice podélné musí všechny lícovat s profily nohou. tzn ve
2D pohledu příčky i podélníky splývají s profily nohou."** — jiné
pravidlo než "aktualizace pravidla 2026-09-07 — pozice příček vrchních
noh vůči úhelníku" výše (to je o SVISLÉ pozici vůči budoucím úhelníkům
na vrchní noze, tohle je o VODOROVNÉM/hloubkovém lícování se
stávajícími `cap`/`predni-svislice`).

**Skutečně chycená chyba** (2026-09-07, při aplikaci na Doblo K-075 a
Doblo Maxi K-078): `pricka-horni-*`/`pricka-spodni-prepazka`/`vypln-bok-
prepazka` počítaly svůj zadní konec (`xOd`) z "bezpečné" (o
`zadniHloubkaPosun` posunuté) zadní linie, ne ze skutečné pozice `cap`
— takže kdykoli byl posun nenulový (na Doblu vyšlo 15,2mm, MENŠÍ než
tehdejší prah pro konzolu 30mm, takže se nepoznalo), příčka zůstala
"viset" přesně `posun` mm PŘED skutečným čelem `cap` — částečně kryté
čelo, přesný opak Pravidla č.1 z `PRAVIDLA_SPOJU.md`. Stejně tak
`podelnik-zadni-horni/spodni` mělo svůj X rozsah jen ČÁSTEČNĚ (ne celý)
uvnitř `cap`ova skutečného footprintu.

**Druhá chycená věc — kolizní kontrola sama nemohla tohle nikdy
odhalit**: kontroluje jen PRŮNIKY (přesah na všech 3 osách), nikdy
"je čelo kryté CELOU plochou" — mezera i částečné kryté čelo jí
projdou beze zmínky. Tohle je stejná třída chyby jako "úhelník GLB
mapování" výše (verifikační díra, ne jen geometrická chyba) — jen
tady jde o CHYBĚJÍCÍ kontrolu, ne o tichý null.

**Oprava** (`scripts/2026-09-05_horni_ram.js`):
1. `xOd`/`xDo` (používané pro `pricka-horni-*`, `pricka-spodni-
   prepazka`, `vypln-bok-prepazka`) teď VŽDY počítají ze skutečné
   `a.zadni`/`a.celni` polohy, nikdy z posunuté linie — příčka totiž
   nepotřebuje vlastní rezervu od stěny navíc, nesahá k ní blíž, než
   už sahá samotný (dávno prověřený) `cap`.
2. Posun zadní linie (`podelnik-zadni-*`, `vypln-zada`, `vypln-dno`,
   konzoly) se teď NEJDŘÍV zkouší s `posun=0` a použije se, pokud
   výsledek NEKOLIDUJE se skutečnou karoserií (`eng.collidesWithWalls`
   na reálné GLB geometrii) — teprve když by `posun=0` kolidoval, sáhne
   se po vypočítaném bezpečném posunu. Dřívější kód posouval VŽDY, jen
   podle fixní 20mm rezervy (`MIN_MEZERA_KE_STENE`), bez ohledu na to,
   že samotné `cap` (nezměněné) nikde s karoserií nekoliduje.
3. Práh pro mostící KONZOLU opraven z "posun > T (30mm)" na "posun !=
   0" — jakýkoli nenulový posun znamená částečně kryté čelo bez
   konzoly, ne jen posun nad 30mm.

**Výsledek po opravě, změřeno na reálné GLB geometrii (ne odhadem):**
- **CI25 vzor (`id=187`/`189`) i OBĚ Dobla (`id=134`, `id=135`)
  vyšly s `posun=0`** — u žádného z těchto tří aut ve skutečnosti
  nebyl potřeba (dřívější "5,8mm mezera u vrcholu, bezpečné ale na
  hraně" u CI25 byla platná, jen zbytečně opatrná - reálná kolizní
  kontrola s `posun=0` vychází čistě, 0 kolizí s karoserií u všech tří).
- Příčka-horní-0 (Doblo K-075): zadní konec teď přesně `-621,50mm` =
  `cap`ova čelní stěna `-621,50mm` (mezera 0,00mm, dřív 15,2mm).
  Přední konec `-402,50mm` = `predni-svislice` stěna `-402,50mm`
  (mezera 0,00mm, tam už byla správně i dřív).
- `podelnik-zadni-horni` X rozsah `[-651.5,-621.5]` = PŘESNĚ stejný
  jako `cap`ův vlastní X rozsah `[-651.5,-621.5]` (dřív jen částečný
  překryv 14,8/30mm).
- `panely s méně než 4 zásuny` zmizelo i u CI25 vzoru (dřív "vypln-
  bok-prepazka 3x", teď 4x) — vedlejší, ale vítaný důsledek opravy
  `xOd`/`xDo`.
- Regresní sada (`node scripts/2026-08-19_regression_scene/run_all.js`)
  zůstává zelená.

Konzola-větev (posun>0, teď spouštěná při JAKÉMKOLI nenulovém posunu)
zůstává na žádném reálném autě dosud NEOVĚŘENÁ — žádné z dosud
zkoušených aut (CI25, Doblo K-075, Doblo Maxi K-078) do ní nespadlo.

### Aktualizace pravidla 2026-09-07 (Robert) — spodní pásmo se musí odsunout od úhelníku, ne jen počítat z výšky boxu

**Pravidlo (Robert, po dotazu proč vznikla dřívější kolize): "při kolizi
se mělo 5mm vrátit."** — spodní hranice spodního pásma horního bloku se
dřív počítala VÝHRADNĚ z výšky nejvyššího boxu (`nejvyssiBox + 30mm`),
bez ohledu na to, jestli tam náhodou nesahá úhelník ze spoje `spojnice-
horni`↔`cap`/`predni-svislice` (`shape_geometry_methods.id=7`). U Doblo
K-075/Maxi K-078 úhelníky sahaly až na Y=950,5mm, zatímco spodní pásmo
mělo začínat na 934,5mm — 16mm skutečný průnik (viz nález výše "REÁLNÁ
kolize na obou Doblech").

**Oprava** (`scripts/2026-09-05_horni_ram.js`): `analyzuj()` teď vrací i
`nejvyssiUhelnik` (nejvyšší Y bod libovolného dílu s rolí začínající
`uhelnik`). Spodní hranice spodního pásma je teď VĚTŠÍ ze dvou hodnot:
`nejvyssiBox + MEZERA_NAD_BOXY(30mm)` NEBO `nejvyssiUhelnik +
MIN_MEZERA_OD_UHELNIKU(5mm)` — podle toho, která vyjde výš. Když
úhelník nesahá tak vysoko jako 30mm nad posledním boxem (běžný případ,
CI25), pravidlo se chová přesně jako dřív. Když sahá výš (Doblo), celé
spodní pásmo (a tedy i horní pásmo a celý horní blok) se odsune nahoru
o přesně tolik, kolik je potřeba + 5mm rezerva.

**Výsledek:** obě Dobla teď `kolize s dily: žádná` (dřív 10 kolizí s
úhelníky) i `kolize s karoserii: žádná` zároveň. CI25 vzor beze změny.
Regresní sada zůstává zelená. Zapsáno znovu do `product_assemblies.
id=134` a `id=135`.

### Vysvětlení 2026-09-07 (bot8, na Robertův dotaz) — proč spodní příčka existuje jen u přepážky

Robert si na živé scéně všiml, že u prostřední a zadní nohy chybí
spodní příčka (`pricka-spodni-prepazka` existuje jen jednou, u
přepážkové nohy, `a.zadni[0]`) a ptal se, jestli je to chyba nebo to
jen není zjevné z pravidla postupu.

**Není to chyba — je to nutný důsledek účelu horního bloku, jen
nikde explicitně nezapsaný.** Horní blok je "zóna pro dlouhé
předměty" — dlouhé kusy se zasouvají od otevřeného (zadního/dveřního)
konce a kloužou po dně (`vypln-dno`, ve stejném spodním pásmu jako by
byla spodní příčka) až k přepážce, kde se zastaví:
- Spodní příčka leží prakticky v rovině dna. Kdyby existovala
  uprostřed nebo u dveří, vytvořila by 30mm příčný práh přímo v cestě
  posouvaného předmětu — funkční překážka, ne jen kosmetický
  nedostatek.
- U přepážky nevadí, protože tam už dál nic neputuje — je to
  přirozený konec dráhy (proto taky název role `pricka-spodni-
  prepazka`, ne obecná `pricka-spodni-N`).
- Horní příčka (`pricka-horni-N`) naproti tomu existuje na VŠECH
  nohách bez problému, protože leží nad celým volným průřezem
  (`svetlaVyskaRamu`) — dlouhý předmět ležící na dně se pod ní vejde,
  nebrání mu.

Žádná úprava kódu — jen zápis důvodu, ať to příště nemusí nikdo znovu
dedukovat z chování skriptu.

### Aktualizace pravidla 2026-09-07 (Robert) — police v polovině výšky horního bloku, s možností dalšího dělení na čtvrtiny

**Pravidlo (Robert, doslovně): "přidat další rám s výplní mdf jako
police v polovině výšky bloku. potom nech existuje možnost výplní do
poloviny těch polovin."**

Rozšiřuje `shape_geometry_methods.id=9`/`scripts/2026-09-05_horni_
ram.js` o binární dělení "zóny pro dlouhé předměty" na výšku:

1. **Základní stav (dosud jediný implementovaný):** 1 volný kanál po
   celé `svetlaVyskaRamu` (mezi spodním a horním pásmem), bez dělení.
2. **Nová možnost — "police v polovině":** další RÁM (podélníky +
   příčky, stejná konstrukce jako spodní/horní pásmo, ne jen samotná
   deska) s výplní MDF, postavený v POLOVINĚ světlé výšky rámu
   (`yStred = (ySpodnihoHor + yHornihoDol) / 2`, samotný rám tloušťky
   `T` kolem tohoto středu jako každé jiné pásmo). Rozdělí 1 kanál na 2
   nižší kanály.
3. **Nová možnost — "výplně do poloviny těch polovin":** KAŽDÝ ze 2
   kanálů z kroku 2 může (nemusí — "možnost", ne povinnost) dostat
   DALŠÍ takový rám v polovině SVÉ vlastní výšky, čímž vznikne až 4
   nejnižších kanálů celkem. Binární dělení, ne pevný počet pater —
   strop je "polovina poloviny", ne konkrétní číslo.

**Platí stejná pravidla jako pro spodní pásmo** (viz sekce výše):
- Nový vnitřní rám (police) je STEJNÝ typ konstrukce jako spodní/horní
  pásmo (podélníky + příčky, lícující přesně na `cap`/`predni-
  svislice`, žádné částečně kryté čelo — "Aktualizace pravidla
  2026-09-07 — příčky/podélníky musí lícovat").
- Příčka NOVÉHO vnitřního rámu smí být na VŠECH nohách (jako horní
  příčka) POUZE pokud daný sub-kanál už neslouží k zasouvání dlouhých
  předmětů "naskrz" - jinou konstrukci uz nema smysl provlekat pod
  hlavni pricku, takze se pravidlo "spodni pricka jen u prepazky" tyka
  jen NEJSPODNEJSIHO kanalu (ten, co sousedi se skutecnym dnem/boxy);
  jakykoli DALSI (vyssi) sub-kanal vznikly delenim uz nema pod sebou
  volnou drahu pro dlouhe predmety, takze jeho spodni pricka (= horni
  pricka kanalu pod nim, sdilena hrana) muze byt na VSECH nohach bez
  omezeni.
- Nejnižší kanál (přiléhající k boxům) si PONECHÁVÁ pravidlo "spodní
  příčka jen u přepážky" (viz vysvětlení výše) — ten jediný slouží
  jako skutečná průchozí zóna pro zasouvání dlouhých předmětů od
  otevřeného konce.

**Stav: zapsáno jako pravidlo, NEIMPLEMENTOVÁNO** — čeká na explicitní
"aplikuj" (stejný vzorec jako u předchozích dvou aktualizací pravidel
v této sekci), a na rozhodnutí, na kterém autě/sestavě se má poprvé
vyzkoušet.

### OPRAVA 2026-09-07 (Robert) — spodní příčka PATŘÍ na všechny nohy, ne jen k přepážce

**Robert opravil předchozí "Vysvětlení... proč spodní příčka existuje
jen u přepážky" (bod výše) i omezení v pravidle "police v polovině":
"to je chytré ano, ale ty profily to zpevní a lze je posunout aby
horní hrana profilu lícovala s horní hranou mdf. na dlouhé předměty si
klient vybere variantu bez horních příček a bude to vkládat i shora,
takže ty příčky tam patří jak jsem upřesnil výše."**

Moje předchozí zdůvodnění (příčka jinde než u přepážky = fyzická
překážka pro dlouhé předměty, proto správně chybí) bylo **nesprávné a
je tímto NAHRAZENO**:

1. **Příčka nemusí být překážka — dá se posunout tak, aby její horní
   hrana lícovala s horní hranou MDF podlahy/police** (ne zůstávat na
   plné výšce pásma s horní hranou nad úrovní MDF). Když profil
   nevyčnívá nad rovinu podlahy, dlouhý předmět po něm hladce přejede,
   žádný 30mm práh nevzniká. Zároveň profil `T=30mm` zpevňuje
   konstrukci (podpírá MDF zespoda/dodává tuhost), takže je to čistý
   přínos, ne kompromis.
2. **Konflikt s "dlouhými předměty" řeší KONFIGUROVATELNOST, ne
   vynechání příčky:** zákazník, který chce ukládat dlouhé předměty,
   si zvolí VARIANTU BEZ HORNÍCH PŘÍČEK (bez dělící police/rámu nad
   daným kanálem) a vkládá je i SHORA (vertikálně), ne jen podélným
   zasunutím od otevřeného konce. Příčky tedy nejsou univerzálně
   škodlivé pro dlouhé předměty — jsou jen součástí JINÉ (dělené)
   varianty, kterou si zákazník s dlouhými předměty prostě nevybere.

**Platné pravidlo (nahrazuje obě předchozí zjednodušení):** příčka na
KAŽDÉ hranici pásma (spodní pásmo základního bloku, i každá "police v
polovině" ze sekce výše) se staví na VŠECH nohách (přepážka, prostřední,
zadní/dveřní) — žádná výjimka jen pro přepážku. Y pozice příčky se
odvozuje od horní hrany přilehlé MDF výplně (podlahy/police), ne od
celé výšky pásma jako dosud (`ySpodnihoDol..ySpodnihoHor`) — přesný
vzorec (kde přesně "horní hrana profilu" leží vůči středu/hraně MDF
desky) zatím NEOVĚŘEN měřením, potřeba dopočítat při implementaci.

**Stav: zapsáno jako pravidlo, NEIMPLEMENTOVÁNO.** Ovlivňuje jak
základní horní blok (`pricka-spodni-*` by mělo existovat na všech
nohách, ne jen `pricka-spodni-prepazka`), tak "police v polovině" výše
(odstraňuje omezení "jen nejspodnější kanál má výjimku" — výjimka
padá úplně, příčky jsou všude, jen správně svisle umístěné).

### APLIKOVÁNO 2026-09-07 (Robert: "aplikuj") — police v polovině + příčky na všech nohách

Implementováno v `scripts/2026-09-05_horni_ram.js` (obě předchozí
NEIMPLEMENTOVANÁ pravidla — "police v polovině" a "příčka patří na
všechny nohy" — najednou, jsou provázaná).

**Vzorec pro Y pozici příčky u pásma s deskou** (dopočítáno měřením,
viz "zatím NEOVĚŘEN" výše): profil (`T=30mm`) má horní hranu = horní
hrana MDF desky (`DESKA_TL=8mm`, vystředěná v pásmu). Protože deska má
z obou stran `(T-DESKA_TL)/2=11mm` rezervu v pásmu, příčka se posune o
těchto 11mm DOLŮ oproti vystředěné poloze — její SPODNÍ hrana tím padá
`11mm` POD nominální spodní hranici pásma (`PRICKA_DESKA_OFFSET`
konstanta). Ověřeno na reálné GLB geometrii: `pricka-police-0` horní
hrana = `vypln-police-0` horní hrana na `0,00mm` přesně.

**3 reálně chycené důsledky tohohle posunu (opraveno postupně, měřením
po každém kroku, ne odhadem):**
1. **`ySpodnihoDol` (30mm nad boxy / 5mm nad úhelníkem) muselo počítat
   s posunutou (nižší) spodní hranou příčky, ne s nominální hranicí
   pásma** — jinak příčka znovu zasahovala do úhelníků/boxů o přesně
   `PRICKA_DESKA_OFFSET` mm. Obě rezervy (`MEZERA_NAD_BOXY`,
   `MIN_MEZERA_OD_UHELNIKU`) teď mají `+ PRICKA_DESKA_OFFSET` navíc.
2. **Svislé výplně (`vypln-zada`/`vypln-celo`/`vypln-bok-prepazka`),
   dřív JEDEN kus přes celou výšku bloku, se musí rozdělit na DVA kusy
   (pod policí / nad policí)** — jinak by uprostřed procházel nový
   vodorovný rám police skrz existující svislý panel (reálná kolize,
   8mm průnik). Segmentace `-a`/`-b` v `panelSvisly()`.
3. **`vypln-bok-prepazka` sedí na STEJNÉ Z jako `pricka-*-0`** (na
   rozdíl od `vypln-zada`/`vypln-celo`, které leží v mezerách MEZI
   nohami) — jeho spodní segment musí končit u SKUTEČNÉ (nižší) spodní
   hrany `pricka-police`, ne u podélníkova zásunu, jinak koliduje s ní
   (18mm průnik, opraveno samostatnou hranicí `panelYUsekyBok`).
4. Regex pro rozpoznání "rámového" dílu (`RAMOVE`, i vylučovací filtr v
   hlavní kolizní smyčce) měl natvrdo vypsané `pricka-horni|pricka-
   spodni`, zapomněl na nově přidané `pricka-police` — zjednodušeno na
   obecný prefix `pricka` (pokryje i budoucí varianty).

**Výsledek na všech 3 testovaných sestavách (CI25 vzor, Doblo K-075,
Doblo Maxi K-078):** `kolize s dily: žádná`, `kolize s karoserii:
žádná`, regresní sada zelená. `--bez-police` CLI přepínač zachovává
původní (nedělený) kanál pro variantu "dlouhé předměty, nakládané i
shora" (Robert). Zapsáno do `product_assemblies.id=134` (127 dílů) a
`id=135` (130 dílů).

### OPRAVA 2026-09-08 (Robert, po screenshotu) — vypln-bok-prepazka počítal hranice podle podélníku, který na jeho Z vůbec neexistuje

**Robert (po screenshotu sestavy "Doblo K-075 A"): "boční horní mdf nezapadá do drážek."**

Skutečná chyba: `vypln-bok-prepazka` (krajní boční panel u přepážky) sedí
na STEJNÉ Z jako `pricka-*-0` — na rozdíl od `vypln-zada`/`vypln-celo`,
které leží v MEZERÁCH MEZI nohami (kde segmentovaný podélník spodní/
police reálně existuje). Na Z přepážkové nohy segmentovaný podélník
(`podelnik-zadni-spodni-0`, `podelnik-zadni-police-0`) NEEXISTUJE —
existuje tam jen příčka. Kód ale pro hranice tohoto panelu dál používal
obecný `panelYUseky` (odvozený z podélníkových zásunů), který na
"police" pásmu neodpovídá skutečné (o `PRICKA_DESKA_OFFSET=11mm` níž
posunuté) příčce — vznikla tak 4mm MEZERA místo dotyku, na OBOU
hranicích sousedících s posunutou příčkou (segment "a" i "b").

**Oprava:** hranice `vypln-bok-prepazka` u pásem S DESKOU (spodní,
police) se teď počítají přímo z polohy SKUTEČNÉ příčky na dané hranici
(`prickaTopY(dol,hor)` — stejná horní hrana jako `stavPricky()` počítá
pro samotnou příčku) — FLUSH (0mm), ne 7mm zásun do neexistujícího
podélníku. Hranice u "horní" pásma (bez desky, příčka-horní tam
splývá s podélník-horní) beze změny.

**Ověřeno na reálné geometrii:** oba konce obou segmentů teď `0,000mm`
(dřív 4mm mezera na dvou ze čtyř hranic). `kolize s dily`/`kolize s
karoserii`: žádná, na všech třech (id=134, 135, 209). Zapsáno znovu.

### OPRAVA 2026-09-08 (Robert, podruhé) — flush (0mm) nestačí, musí to být skutečný zásun min. 5mm

**Robert: "mdf bočních mdf v horním bloku obou Doblo, stále nezapadá
do drážek, musí se zapustit do horní i dolní příčky min 5mm."**

Předchozí oprava (viz sekce výše) odstranila 4mm mezeru, ale nahradila
ji jen FLUSH dotykem (0mm) — správně to má být `ZASUN=7mm` (stejná
konstanta jako všude jinde, splňuje "min 5mm") skutečně zapuštěný DO
příčky, ne jen dotyk na jejím povrchu — stejný princip jako u
`vypln-zada`/`vypln-celo` do podélníku, jen cíl je příčka (na této Z
jediná věc, co tam fyzicky je).

**Oprava:** hranice segmentů u pásem s deskou (spodní, police) teď
`prickaTopY(pásmo) - ZASUN` (zapuštění shora dolů do příčky) /
`prickaBottomY(pásmo) + ZASUN` (zapuštění zdola nahoru) místo
prostého `prickaTopY(pásmo)` (flush).

**Ověřeno na reálné geometrii:** všechny 3 hranice (spodní příčka,
police příčka ×2) teď `7,00mm` zásun přesně. `panely s méně než 4
zásuny` zmizelo úplně (`vypln-bok-prepazka` teď má taky plných 4×,
dřív 2×/3×) — vedlejší, ale vítaný důsledek. 0 kolizí s díly i
karoserií na všech třech (id=134, 135, 209). Zapsáno znovu.
