#!/usr/bin/env python3
"""Naplni content_obor/content_typologie navrhem textu pro obory 1-4
(Robert pres bot3, 2026-09-27). VSECHNY radky se zapisuji jako NESCHVALENE
navrhy (schvaleno=0) - Robert je musi projit v adminu (nova zalozka
"Centrální texty") a schvalit, az POTOM uz na ne bot7 nesmi sahnout (viz
memory feedback_approved_central_text_hands_off.md).

Zdroje: [1] backups/otisk_logiman_cz_2026-08-10.md + navrh_texty (osvedceny
text ze stareho logiman.cz), [2] SEO_KONKURENCE_NASTENKA.md (klicove
fraze), [3] Robertovy soubory ze slozky "SEO GEO" na Sdilenem disku,
2026-09-27: "Ergonomie pracovišť ok cz.doc" (odborny ergonomicky text),
"klíčová slova pro obor 2,3,4.csv" (terminologie podle oboru), "LOGiMAN
ergonomic workstations... .odt" (anglicky produktovy popis, technicke
specifikace prevzaty, ne cizi jmena/branding).

Idempotentni na urovni "jiz existuje kod/klic" - lze spustit vicekrat.

Pouziti:
    python3 scripts/2026-09-27_content_obor_seed.py            # dry-run
    python3 scripts/2026-09-27_content_obor_seed.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv

# ============================================================
# OBOR 1: Vestavby do dodávek (užitková auta) - 1. priorita
# ============================================================
OBOR1_POPIS = """
<p>Logiman dodává pracovní vestavby a přestavby do užitkových vozidel na klíč od roku 2009. Od roku 2019 používáme vlastní systém výsuvných rámů s pružinovou aretací – u poškození se mění jen konkrétní díl police, ne celá police. Po montáži se provádí zápis vestavby do technického průkazu vozidla, v souladu s požadavky na homologaci. Montáž probíhá v Praze, ve Slavičíně na Zlínsku nebo přímo u zákazníka; konstrukci lze smontovat i svépomocí.</p>
<p>Pracovní vestavby a stavebnice navrhujeme pro nejběžnější dodávky na českém trhu: Mercedes Sprinter, Mercedes Vito, Ford Transit, Ford Transit Custom, Fiat Ducato, Fiat Doblo, Citroën Jumper, Citroën Jumpy, Renault Master, Renault Trafic, Opel Movano, Opel Vivaro, VW Crafter, VW Transporter, VW Caddy, MAN, Iveco Daily a Toyota ProAce.</p>
<h3>Jak probíhá vestavba na klíč</h3>
<ol>
<li>Pošlete nám náčrt od ruky (nebo fotografii nákladového prostoru) s popisem, jak si vestavbu představujete.</li>
<li>Navrhneme reálný 3D model.</li>
<li>Návrh si prohlédnete a okomentujete – 3D model upravujeme, dokud není přesně podle vašich představ.</li>
<li>Montáž proběhne na klíč v Praze, ve Slavičíně (Zlínský kraj) nebo přímo u vás; případně si vestavbu smontujete svépomocí.</li>
<li>Po montáži provedeme zápis vestavby do technického průkazu vozidla, v souladu s požadavky na homologaci.</li>
</ol>
<h3>Vestavba na míru, nebo univerzální stavebnice</h3>
<p>Vestavba do dodávky je řešení šité na míru konkrétnímu modelu vozidla nebo profesi zákazníka – rozměry na milimetr podle nákladového prostoru (např. Ford Transit Custom, Toyota ProAce, nebo šuplíkové vestavby TECNO podle značky a modelu). Stavebnice do aut je naproti tomu univerzální komponentní systém organizovaný podle výšky vozidla (Systém 30, Systém 40, Systém 45), který si zákazník poskládá sám nebo s naší pomocí.</p>
<p>Fiat Ducato, Citroën Jumper a Peugeot Boxer sdílejí stejnou platformu, takže pro ně nabízíme shodný regálový systém rozpadající se podle strany a verze karoserie: levá strana auta (L1H1, L1H2, L2H2, L3H2, L4H2), pravá strana auta (stejná řada) a regál k přepážce za kabinou (výška H1, H2). Jejich menší sourozenci, Fiat Doblo a Citroën Jumpy, mají vlastní rozměrovou řadu a řešení pro ně vychází spíš ze Systému 30.</p>
<h3>Systém 30, 40 a 45</h3>
<p>Šuplíkový systém 30 je lehké provedení s nosností 20–25 kg na jeden výsuv. Regál obsahuje pružinovou aretaci proti vysunutí, která automaticky zajistí šuplík při jeho zasunutí – výsuvy upravíme pro přepravky (euroboxy), systainery nebo jiné libovolné kufry. Nohy regálu tvoří profily 60×30 mm (přední noha) a 30×30 mm (zadní noha); sestava jako celek může obsahovat více sloupců výsuvů a každý sloupec může mít jiný počet i jinou výšku vysouvaných boxů.</p>
<p>Systém 40 je určený pro dodávky výšky H1, Systém 45 pro vyšší dodávky H2 a H3 a náročnější zatížení. K základní konstrukci všech tří systémů doplníte plastové boxy a přepravky, dřevěné nebo plastové výplně polic (dno, boky, záda, čela) a kotevní sety; předpřipravené balíčky (Balíčky systém 40, Balíčky systém 45) sdružují nejčastěji používané komponenty do jedné sady.</p>
<h3>Kotvení konstrukce ke karoserii</h3>
<p>Každý hliníkový profil má po celé délce upínací drážku, díky které lze kotvit regály, šuplíky, madla i vlastní doplňky kdekoli na konstrukci bez nutnosti vrtat znovu do profilu při každé úpravě. Ukotvení celé konstrukce ke karoserii vozidla ale obvykle vyžaduje vrtání do jejích zpevněných částí – originálních kotevních bodů bývá u dodávek jen málo – v souladu s požadavky na homologaci. Kotevní prvky a sety využívají upínací drážku profilu; příklady konkrétního kotvení najdete přímo u vestaveb v katalogu.</p>
<h3>Jak zákazníci hledají – terminologie</h3>
<p>Stejný produkt zákazníci hledají pod řadou různých názvů, které je užitečné mít přirozeně rozeseté v textu: regály do dodávky, regály do auta, police do dodávky, dílenská vestavba do dodávky, pracovní vestavba do dodávky, regály se zásuvkami, pojízdná dílna, vestavba regálů, regálový systém do dodávky, regály a police do užitkového vozu, policový úložný systém v dodávce, šuplíky do dodávky, úložný box do dodávky, ponk do auta, pracovní deska do dodávky, vestavba na nářadí do dodávky, homologovaná vestavba do dodávky, modulární organizér dodávky.</p>
<h3>Časté otázky</h3>
<p><strong>Musím si vybrat z hotových sestav, nebo lze regál udělat na míru?</strong> Obojí: v e-shopu najdete příkladové sestavy k okamžité objednávce, zároveň ale vyrábíme zcela individuální rozměry podle vašich potřeb.</p>
<p><strong>Je nutná homologace po montáži vestavby?</strong> Ano, po montáži se provádí zápis do technického průkazu vozidla v souladu s požadavky na homologaci.</p>
<p><strong>Jaký je rozdíl mezi vestavbou a stavebnicí do auta?</strong> Vestavba je řešení na míru konkrétnímu modelu vozidla nebo profesi. Stavebnice do aut je univerzální komponentní systém organizovaný podle výšky vozidla, který si skládáte sami.</p>
<p><strong>Musí se kvůli kotvení vrtat do karoserie auta?</strong> Do samotného hliníkového profilu ne (využívá se jeho upínací drážka po celé délce), ale ukotvení celé konstrukce ke karoserii obvykle vyžaduje vrtání do jejích zpevněných částí – to je běžné a homologačně v pořádku.</p>
""".strip()

OBOR1_TYPOLOGIE = [
    ("regal-ke-stene", "Regál ke stěně (levá, pravá, za kabinou)", "247",
     "<p>Regál ke stěně (levý nebo pravý) vede podél boční stěny nákladového prostoru; regál za kabinou stojí hned za přepážkou oddělující kabinu od nákladového prostoru – na rozdíl od bočních regálů nemá u některých vozidel horní blok, místo něj přichází v úvahu spodní blok.</p>"),
    ("podlaha", "Dvojitá podlaha, úložný prostor v podlaze, výsuvná podlaha", "249,254",
     "<p>V podlaze užitkového vozidla vzniká využitelný úložný prostor tam, kde potřebujete zachovat maximální velikost ložné plochy nad ním – typicky u vozidel s nízkým podvozkem, jako je Ford Transit nebo Mercedes Sprinter. Praktické jsou především euroboxy na výsuvech, jejichž skladbu zvolíte libovolně podle typu a množství materiálu; skladbu šuplíků v podlaze navrhneme podle 3D modelu na základě vaší specifikace – stačí poslat skicu od ruky nebo jednoduchý popis, jak chcete mít úložný prostor rozdělený. Výsuvnou podlahu vyrobíme přesně podle zadání – lze ji zkombinovat i se stávající vestavbou, například jako doplňkový výsuv na kolo.</p>"),
    ("vysuvne-bloky", "Výsuvné bloky a přídavná ložná plocha", "246,292",
     "<p>Když je dodávka zaskládaná natolik, že se stává problémem vozit i palety s materiálem, řeší to vyjímatelná přídavná ložná plocha umístěná do zadního prostoru, mezi zadní a boční dveře, nad podběhy kol. Systém lze přizpůsobit každé dodávce: zvolit libovolnou nosnost, rozdělit plochu přepážkami, zvolit výšku bočních stojin napevno na milimetr nebo s možností nastavitelnosti. U menších dodávek řeší nepohodlný přístup individuální výsuvy z podlahy nebo z bočních dveří: výsuvné rámy na míru pro těžké elektrocentrály, jumbo šuplíky z bočních dveří na kufry, nebo výsuvné plato z podlahy plné euroboxů libovolných velikostí.</p>"),
    ("vysuvy-na-kola", "Individuální výsuvy na kola", "",
     "<p>Pro cyklisty, kteří chtějí mít kolo bezpečně uložené přímo v dodávce, navrhujeme individuální výsuvné plato na míru – stačí poslat e-mailem fotografii nákladové části vozidla a stručně popsat představu, jak má výsuv vypadat, ideálně s náčrtem od ruky a kótami. Konstrukci tvoří hliníkové profily s drážkami pro kotvení čehokoli kamkoli, v provedení elox přírodní nebo černý; spojovací kostky lze nastříkat do libovolného barevného odstínu. Plocha výsuvných plat nemusí být souvislá – standardním materiálem je foliovaná topolová překližka. Rozměry se navrhují vždy individuálně na milimetr pro libovolný podporovaný model dodávky.</p>"),
    ("euroboxy", "Regál na euroboxy", "274,248",
     "<p>Regál na euroboxy má výsuvné hliníkové rámy (platy), které se přizpůsobí libovolné přepravce a jistí ji automatickou pružinovou aretací. Regál lze sestavit z více sekcí vedle sebe, takže lze v jednom vozidle kombinovat euroboxy různých velikostí podle potřeby.</p>"),
    ("univerzalni-regal", "Univerzální regál", "277,220",
     "<p>Univerzální regál zahrnuje upínací police, police s organizéry, police s vanami a police se sklopnými dvířky. Samostatnou kapitolou je ukládání kufrů a batohů – řešení, které zabrání jejich sklouznutí nebo přesunu při jízdě.</p>"),
    ("ocelove-suplíky", "Ocelové šuplíky (univerzální i TECNO na míru)", "210,295",
     "<p>Ocelové šuplíky s aretací jsou univerzální komponenta stavebnice – na rozdíl od šuplíkových vestaveb TECNO je lze zakomponovat do libovolné sestavy Systému 30 nebo 45 bez ohledu na konkrétní model vozidla. Nabídka zahrnuje přes 10 velikostí, například šuplík 420×360×100 mm. Šuplíkové vestavby TECNO naproti tomu nabízí ocelové šuplíkové vestavby s aretací navržené přesně pro konkrétní modely užitkových vozidel podle značky (Renault, Mercedes-Benz, Fiat, Ford, Peugeot, Volkswagen, Opel, Citroën, Iveco, Nissan, Toyota, MAN, Dacia a další) – šuplíky jsou přizpůsobené skutečným rozměrům nákladového prostoru daného vozidla, ne univerzální šabloně.</p>"),
    ("privesny-vozik", "Přívěsný vozík s úložným systémem", "244",
     "<p>Přívěsné vozíky s úložným systémem zásuvek nabízíme v různých velikostech a zatíženích – příkladem realizace je vozík s vnějšími rozměry ložné plochy 1850×1750 mm, osazený stejným zásuvkovým systémem jako hliníková stavebnice do vozidel.</p>"),
    ("podle-vozidla", "Podle vozidla / platformy", "233,267,272,273,283,284,280,293,282,294,285,286,287,288",
     "<p>Vyrábíme individuální pracovní vestavby na milimetr podle vybavení řemeslníka pro nejběžnější dodávky na trhu. U vozidel sdílejících stejnou platformu (Fiat Ducato, Citroën Jumper, Peugeot Boxer) nabízíme shodný regálový systém rozpadající se podle strany a verze karoserie. U Ford Transit Custom a Toyota ProAce vyrábíme individuální pracovní vestavbu přizpůsobenou na milimetr rozměrům nákladového prostoru.</p>"),
    ("podle-profese", "Podle profese (elektrikář, instalatér)", "296,297",
     "<p>Elektrikář má v autě obvykle kombinaci nářadí, měřicích přístrojů, instalačního materiálu, kabeláže a ochranných pomůcek. Vhodný je především odlehčený Systém 30 s lehkou konstrukcí a výsuvnými rámy na libovolné euroboxy; nářadí, které chcete mít stále na očích, lze zavěsit na děrovaný plechový panel.</p><p>Instalatér vozí kombinaci ručního a aku nářadí, lisovací a řezací techniky, potrubních systémů a instalačního materiálu – PVC a HT trubky, PPR trubky a tvarovky, mosazné fitinky, armatury, ventily a těsnicí materiál. Vhodný je jak lehký Systém 30 pro menší dodávky, tak robustnější řada 40 nebo 45 pro náročnější vybavení.</p>"),
]

# ============================================================
# OBOR 2: Pracovní ergonomické stoly na míru - 2. priorita
# ============================================================
OBOR2_POPIS = """
<p>Ergonomické navrhování pracovních stolů v montážních a výrobních provozech má za primární cíl minimalizovat riziko muskuloskeletálních poruch (MSD), které patří k nejčastějším pracovním onemocněním v Evropě i v Česku. Dlouhodobé setrvávání v nepřirozených statických polohách, předklon trupu a hlavy, vysoká repetitivita pohybů vedou k bolestem zad, krku a ramen, zánětům šlach i syndromu karpálního tunelu. Správně navržené pracoviště tato rizika výrazně snižuje a přispívá k vyšší dlouhodobé produktivitě – v optimalizovaných provozech až o 20–30 %.</p>
<h3>Hlavní ergonomické požadavky na pracovní stůl</h3>
<p><strong>Výškové nastavení.</strong> Pracovní rovina musí umožňovat dynamickou změnu polohy během směny (sezení – polosed – stání). Optimální rozsah nastavení je 650–1250 mm. Doporučené výšky pracovní roviny jsou 630–760 mm pro práci vsedě a 900–1200 mm pro práci vestoje – udržují se tak neutrální úhly loktů (90–110°) a páteř v přirozeném postavení.</p>
<p><strong>Rozměry a uspořádání desky.</strong> Ideální hloubka desky je 600–800 mm (nejčastěji 700 mm), aby bylo možné opřít předloktí bez natahování. Šířka desky se volí podle charakteru operace (1200–3000 mm), s dostatečným prostorem pro dolní končetiny (minimálně 600 mm) a zaoblenými hranami.</p>
<p><strong>Nosnost a stabilita.</strong> Pracovní stůl musí vykazovat vysokou nosnost (150–600 kg podle typu provozu) a absolutní stabilitu – jakákoliv nestabilita vyvolává kompenzační svalové napětí a zvyšuje riziko chyb i chronického přetížení.</p>
<p>Správně navržené pracoviště splňuje požadavky ČSN EN ISO 6385 a respektuje antropometrická data podle ISO 14738.</p>
<h3>Specifické požadavky podle oborů</h3>
<p>V automobilovém průmyslu a na montážních linkách lehkého průmyslu se upřednostňují jednoúčelová ergonomická pracoviště s vysokou nosností a přesným přizpůsobením konkrétní operaci – montážní stanice, kontrolní stoly, předmontážní stoly, otočné montážní stoly. V e-shopech a distribučních centrech je klíčové rychlé výškové nastavení pro balicí a expediční činnosti (balicí stůl, expediční stůl, kompletovací stůl). V potravinářství a hygienických provozech se ergonomie kombinuje s požadavky na omyvatelnost materiálů (nerezový pracovní stůl). Na koncích dopravníkových linek se využívají odběrové a výstupní stoly, často doplněné kuličkovými nebo válečkovými jednotkami pro snadný ruční posun těžších výrobků.</p>
<h3>Materiál pracovní desky</h3>
<p>Podle provozu volíme laminovanou dřevotřísku (běžný dílenský provoz), březovou nebo bukovou překližku, případně nerezovou ocel pro hygienické provozy. Povrch desky bývá záměrně matný, aby neoslňoval.</p>
<h3>Jak stůl objednáváte a jak probíhá montáž</h3>
<p>Stůl navrhneme podle vašeho zadání – typ, rozměry, materiál desky i příslušenství vyberete v poptávkovém formuláři nebo nám pošlete náčrt od ruky. Hotové stoly připravujeme a dodáváme třemi způsoby: kompletně smontované (na paletách nebo bez), napůl smontované z komponent, které si snadno sestavíte sami, nebo zcela nesmontované (nejlevnější varianta, díly rozbalíte z fólie a sestavíte kompletně sami). Přepravní náklady se počítají vždy individuálně podle vzdálenosti a objemu.</p>
<h3>Časté otázky</h3>
<p><strong>Jaký je rozdíl mezi ergonomickým a běžným pracovním stolem?</strong> Ergonomický stůl umožňuje dynamickou změnu pracovní polohy (sezení – polosed – stání) v doporučeném výškovém rozsahu a respektuje zóny komfortního dosahu – snižuje tím riziko muskuloskeletálních poruch a zvyšuje produktivitu.</p>
<p><strong>Lze stůl doplnit dodatečně o další příslušenství?</strong> Ano, díky upínacím drážkám v profilech lze kdykoli doplnit osvětlení, perforovaný panel, odkládací polici nebo držák monitoru, aniž byste museli měnit celý stůl.</p>
<p><strong>Jakým způsobem se stoly dodávají?</strong> Kompletně smontované, napůl smontované k domontování, nebo zcela nesmontované – podle toho, co se vám nejvíc vyplatí z hlediska ceny a přepravy.</p>
""".strip()

OBOR2_TYPOLOGIE = [
    ("balici-expedicni-stoly", "Balicí a expediční stoly", "182,183,206,226,289",
     "<p>Ať už hledáte malé nebo komplexní řešení pro novou halu, přizpůsobíme konstrukci balicího a expedičního pracoviště vašim požadavkům. Nastavitelnost a flexibilita stolů, pracovních stanic i packstations je možná díky všudypřítomným upínacím drážkám na profilech, ze kterých se konstrukce sestavuje – systém posuvných odkládacích polic se přizpůsobí vaší práci, police jsou posuvné nahoru a dolů, vpřed i vzad a plynule úhlově polohovací. Lehký balicí stůl Light-30-A je určený pro balení, příjem a expedici; rozměry lze libovolně upravit na míru, kromě ocelového perforovaného panelu (jeho rozměrová řada je omezená, i tak jde perforované panely nakombinovat do celkového požadovaného rozměru). Balicí pracoviště lze doplnit výsuvnými boxy, ocelovými šuplíky, řezačkami balicího materiálu, odkládacími policemi nad i pod stůl, sklopnými prodlužovacími deskami, LED osvětlením, držáky rolí i háčky. Řezací stojany slouží jako pevná opora při řezání profilů, desek nebo jiného materiálu na míru – lze je doplnit o dorazy pro opakované řezání na stejnou délku nebo o digitální délkový doraz pro přesné odměřování.</p>"),
    ("ergonomicke-stoly", "Ergonomické pracovní stoly", "193,290",
     "<p>Ergonomické pracovní stoly navrhujeme s důrazem na zdraví zaměstnanců podle výše uvedených zásad (výškové nastavení, rozměry desky, nosnost). Kontrolní a kompletační stoly navrhujeme pro pracoviště výstupní kontroly a kompletace výrobků, kde je potřeba mít vše po ruce – nářadí, díly i dokumentaci; konstrukci lze kdykoli doplnit o osvětlení, držák monitoru nebo přihrádky na drobný materiál, aniž byste museli měnit celý stůl.</p>"),
    ("elektricky-nastavitelne", "Elektricky výškově nastavitelné stoly ESSE", "194,201,238",
     "<p>Elektricky ovládané stoly ESSE jsou řešením pro maximální ergonomii – výšková stavitelnost je zcela plynulá a tichá, se zcela zakázkovým provedením podle potřeby. Zvedací sloupky (elektrický pohon) umožňují plynulé nastavení pracovní výšky; vlastní elektrický zvedací systém polic lze využít i pro zvedání těžších přístrojů do velké výšky nad pracovním stolem, s nosností, velikostí i rychlostí přesně podle individuálních potřeb. Technicky jde o nízkou hladinu hluku, přesný posuv, rychlost zdvihu kolem 38 mm/s, provoz v teplotním rozsahu +10 °C až +40 °C a shodu s EN 60335-1 a UL 962.</p>"),
    ("montazni-stoly", "Montážní stoly a pracoviště", "212,239,241,242,222",
     "<p>Montážní pracoviště navrhujeme individuálně s důrazem na ergonomii – připravíme 3D vizualizaci a podle zájmu vyrobíme pracoviště přesně podle vašich nároků: elektrické polohovací stoly s osvětlením, montážní stoly s policemi a spádovými dráhami, pracovní stoly s lamino deskou, multiplexem nebo bukovou spárovkou, pojízdné i výškově nastavitelné stoly. Robustní pracovní stůl 45 je stavěný na profilech Sigma, s vysokou stabilitou a tuhostí i přes montovanou konstrukci – lze ho doplnit polohovacími panely pro boxy, zásuvkovými kontejnery pod stůl, výškově stavitelnou rampou s LED osvětlením, polohovacími nebo úhlově nastavitelnými policemi, perforovanými panely na nářadí, magnetickými popisovacími tabulemi či upínacími hliníkovými deskami s drážkou 10 mm pro T-matice. Specializované pracovní stoly zahrnují upínací stoly a podstavce pro roboty i nerezová provedení, vždy na míru konkrétní operaci.</p>"),
    ("pojizdne-stoly", "Pojízdné pracovní stoly", "240",
     "<p>Libovolný stůl nebo konstrukci lze opatřit pojezdovými koly, aniž by ztratily na výškové stavitelnosti – řešení pro snadné přemístění po provozu.</p>"),
    ("kulickove-stoly", "Kuličkové ložiskové stoly", "291",
     "<p>Kuličkové ložiskové stoly mají v pracovní desce zapuštěné kuličkové jednotky, díky kterým se i těžké výrobky nebo palety po ploše posouvají prakticky bez námahy – hodí se pro balicí a expediční pracoviště i konce dopravníkových linek, kde se manipuluje s objemnějším nebo těžším materiálem. Konstrukce je postavená na stejném hliníkovém profilovém systému jako ostatní pracovní stoly.</p>"),
    ("vozíky-a-stojany", "Vozíky a stojany", "219",
     "<p>Manipulační, zásobovací a skladové vozíky a stojany navrhujeme na míru podle požadavků provozu. Ergonomické zásobovací vozíky mají plně a plynule polohovací police (výškově, úhlově, před/vzad), nosnost 120 nebo 200 kg, otočná kolečka s aretací a rozměry upravitelné na vaše stávající přepravky a boxy.</p>"),
    ("komponenty-desky", "Komponenty, polotovary a materiály desek", "200,207",
     "<p>Pro vlastní sestavení nebo náhradní díly nabízíme komponenty a polotovary pracovních stolů – zvedací sloupky, desky i doplňky. Pracovní desky dodáváme v laminované dřevotřísce (běžný dílenský provoz), březové nebo bukové překližce, případně dalších materiálech podle nároků provozu.</p>"),
]

# ============================================================
# OBOR 3: Prodej hliníkových profilů a příslušenství - 3. priorita
# ============================================================
OBOR3_POPIS = """
<p>Hliníkové stavebnicové profily jsou univerzální modulární systém pro rychlou stavbu rámů, pracovních stolů, ochranných krytů strojů, montážních linek, regálů i nábytku na míru. Díky drážkám po celé délce profilu (nejčastěji 6, 8 nebo 10 mm) lze konstrukci kdykoli rozšířit, upravit nebo rozebrat – bez svařování, jen šrouby a spojovacím příslušenstvím.</p>
<p>V nabídce najdete profily s drážkou 6, 8 a 10 mm (podle velikosti a nosnosti konstrukce), dále speciální profily – vodicí (pro lineární vedení a hřídele), kulaté, deskové a systému Dynamic pro dopravníkové tratě – a kompletní sortiment spojovacího materiálu a příslušenství.</p>
<h3>Jak vybrat správnou velikost profilu</h3>
<p>Menší profily (drážka 6 mm, typicky 20×20 až 30×60 mm) se hodí na lehké konstrukce – stojany, kryty přístrojů, výstavní stojany, drobný nábytek, nízká hmotnost usnadňuje i přenosné konstrukce. Střední řada (drážka 8 mm) je běžný standard pro pracovní stoly, rámy strojů, montážní pracoviště a dopravníkové konstrukce – nejuniverzálnější volba, pokud si nejste jistí velikostí. Nejsilnější profily (drážka 10 mm) volte pro těžké, namáhané konstrukce – velké rámy strojů, montážní linky, jeřábové a manipulační konstrukce, dlouhé rozpony.</p>
<h3>Časté otázky</h3>
<p><strong>Jaký je rozdíl mezi drážkou 6, 8 a 10 mm?</strong> Velikost drážky určuje nosnost i hmotnost profilu – 6 mm je nejlehčí, 10 mm nejsilnější a nejdražší. Příslušenství (T-matice, šrouby, záslepky) není mezi velikostmi zaměnitelné.</p>
<p><strong>Jde konstrukci z profilů později upravit nebo rozšířit?</strong> Ano, to je hlavní výhoda stavebnicového systému – žádné svařování, jen šrouby a spojovací příslušenství, takže konstrukci kdykoli rozšíříte, upravíte nebo rozeberete.</p>
<p><strong>Nejste si jistí, který profil je pro váš projekt vhodný?</strong> Napište nám, poradíme podle zamýšleného použití a zátěže konstrukce.</p>
""".strip()

OBOR3_TYPOLOGIE = [
    ("drazka-6mm", "Hliníkové profily s drážkou 6 mm", "198",
     "<p>Nejlehčí řada stavebnicových profilů (typicky rozměry 20×20 až 30×60 mm), s drážkou 6 mm. Vhodná pro lehké konstrukce, kde není potřeba vysoká nosnost – drobné stojany, kryty přístrojů, výstavní stojany, ochranné rámy a menší nábytkové konstrukce. Nízká hmotnost usnadňuje manipulaci i přenosné konstrukce. Drážku 6 mm volte u lehkých konstrukcí, kde hlavní výhodou je nízká hmotnost a snadná manipulace; pro cokoliv namáhanějšího nebo s větším rozponem přejděte na drážku 8 nebo 10 mm.</p>"),
    ("drazka-8mm", "Hliníkové profily s drážkou 8 mm", "169",
     "<p>Středně silná, univerzální řada profilů – běžný standard pro pracovní stoly, rámy strojů, montážní pracoviště a dopravníkové konstrukce. Dobrý poměr nosnosti a hmotnosti pro většinu průmyslových i dílenských aplikací. Drážka 8 mm je nejuniverzálnější volba pro běžné pracovní stoly, rámy strojů a montážní pracoviště – pokud si nejste jistí velikostí, tahle řada je bezpečný výchozí bod.</p>"),
    ("drazka-10mm", "Hliníkové profily s drážkou 10 mm", "154",
     "<p>Nejsilnější řada stavebnicových profilů, určená pro těžké a namáhané konstrukce – velké rámy strojů, montážní linky, jeřábové a manipulační konstrukce, velké rozpony. Vyšší nosnost a tuhost za cenu vyšší hmotnosti profilu. Drážku 10 mm volte u konstrukcí s velkým rozponem, vyšším zatížením nebo tam, kde bude rám vystaven rázům a vibracím.</p>"),
    ("deskove-profily", "Deskové hliníkové profily", "168",
     "<p>Ploché, deskové profily pro konstrukce, kde je potřeba širší nosná nebo krycí plocha než u standardního hranatého profilu – pracovní desky, boční stěny krytů, montážní panely. Zachovávají drážkový systém po obvodu pro snadné spojení s ostatními profily a příslušenstvím.</p>"),
    ("kulate-profily", "Kulaté hliníkové profily", "181",
     "<p>Profily s kruhovým průřezem, vhodné tam, kde je potřeba konstrukce bez ostrých hran (madla, zábradlí, stojany v provozech s pohybem osob) nebo kde se má díl v uložení otáčet kolem své osy. Kombinují nosnost stavebnicového systému s hladkým, bezpečným povrchem; spojovací příslušenství zůstává kompatibilní s drážkovým systémem stavebnice.</p>"),
    ("vodici-profily", "Vodící hliníkové profily", "215",
     "<p>Speciální profily s integrovaným kruhovým vedením pro uložení hřídelí a lineárních ložiskových jednotek. Používají se tam, kde konstrukce potřebuje kombinovat nosný rám stavebnicového systému s přesným lineárním pohybem – posuvné dveře, vozíky, dopravníky, polohovací zařízení.</p>"),
    ("sigma-profily", "Sigma profily", "262",
     "<p>Profily řady Sigma tvoří základ našich nejrobustnějších dílenských stolů a pracovišť – vykazují vysokou stabilitu a tuhost přestože jde o montovanou (nesvařovanou) konstrukci, díky drážkovanému systému nabízejí vysokou flexibilitu dovybavení.</p>"),
    ("system-dynamic", "Systém Dynamic (profily, příslušenství, spojovací prvky, válečkové dráhy)", "156,192,191,157,225",
     "<p>Konstrukční řada Dynamic je určená pro montážní linky, dopravníkové tratě a válečkové dráhy – zahrnuje profily, vlastní příslušenství, spojovací prvky i válečkové dráhy jako celek.</p>"),
    ("dopravnikove-profily", "Dopravníkové profily", "264",
     "<p>Profily pro konstrukci dopravníkových tratí a válečkových drah – součást stejné rodiny jako systém Dynamic, pro pohyb výrobků na montážních linkách.</p>"),
    ("prislusenstvi-profilu", "Příslušenství profilů", "150",
     "<p>Doplňkové díly, které dělají ze stavebnicových profilů kompletní konstrukci: plastové záslepky profilů a rožků, krycí lišty drážek, stavitelné a pojezdové patky, kolečka, panty, madla, držáky kabelů a plexiskla, plynové vzpěry, zámky, magnety a další drobný spojovací a montážní materiál. Nejdřív zkontrolujte velikost drážky vašeho profilu (6, 8 nebo 10 mm) – většina příslušenství je vyráběná přesně na konkrétní velikost drážky a nejde kombinovat mezi řadami. Záslepky a krytky se jen nasadí na konec profilu bez nářadí; stavitelné patky a kolečka se zašroubují do čela profilu přes vnitřní závit a délku nohy doladíte otáčením i po sestavení konstrukce.</p>"),
    ("spojovaci-prvky", "Spojovací prvky", "152",
     "<p>Kompletní sortiment pro pevné i rozebíratelné spoje mezi profily: rohové úhelníky a rožky (standardní, úzké, velké, trojcestné), spojovací kostky a klouby, plotny pro T-spoje a křížové spoje, úhlové spojky a konzole. Doplňují je T-matice (otočné, pružinové, s kloubem, dlouhé), T-šrouby, čtvercové a obdélníkové matice. Pro rychlou montáž bez předvrtání použijte úhelníky s T-maticemi zasunutými do drážky; pro maximální pevnost a minimální viditelnost spoje volte spojovací kostky nebo vnitřní spoje. Trojcestné rožky se hodí tam, kde se v jednom bodě potkávají tři profily (rohy rámů, nohy stolů).</p>"),
]

# ============================================================
# OBOR 4: Vše ostatní - max. 10-20 % objemu textu
# ============================================================
OBOR4_POPIS = """
<p>Menší, doplňkové téma vedle hlavních tří oborů (vestavby do dodávek, pracovní stoly, hliníkové profily) - text se drží záměrně stručnější.</p>
""".strip()

OBOR4_TYPOLOGIE = [
    ("montazni-linky", "Montážní linky na míru", "213",
     "<p>Navrhujeme a realizujeme montážní linky s pohybem produktů po válečkových drahách posunem rukou, případně se spádovou (gravitační) dráhou. K dispozici je řada velikostí hliníkových profilů podle požadované nosnosti a rozpětí – od lehkých ergonomických montážních linek přes robustní sofistikované polohování produktů až po elektricky výškově stavitelná montážní místa. Výrobky mohou ležet na otočné montážní plotně, která se po dokončení operace vrací zpět na začátek dráhy vespod linky.</p>"),
    ("bezpecnostni-oplaceni", "Bezpečnostní ochranné oplocení", "243",
     "<p>Ochranné oplocení strojů a montážních linek stavíme ze stejného hliníkového profilového systému jako ostatní konstrukce – lze ho tedy kdykoli rozšířit nebo upravit podle změny provozu, doplnit o dveře, průhledné výplně nebo bezpečnostní senzory.</p>"),
    ("konstrukce-stroju", "Konstrukce strojů", "",
     "<p>[Obor zatím bez jednoznačné shody s existujícím katalogem - podle shrnutí z 2026-09-27 jde o téma, které Robert zmínil jako součást oboru 4, ale nespecifikoval, jde-li o novou produktovou linku, nebo o stávající sortiment vedený pod jiným názvem. Text doplnit, až bude upřesnění.]</p>"),
    ("navody-a-postupy", "Návody a postupy", "5,7,9,10,12",
     "<p>Návody a postupy k práci s konfigurátorem, montáži konstrukce a přehled instruktážních videí a katalogu profilů (PDF) - dokumentace k webu a montáži, ne prodejní kategorie. Kategorie 7 (Montáž konstrukce) má už dnes dobrý, schválený text - při redistribuci se nepřepisuje.</p>"),
]


def _insert_obor(cur, kod, nazev, popis_html, sort_order):
    cur.execute("SELECT id FROM content_obor WHERE kod=%s", (kod,))
    row = cur.fetchone()
    if row:
        print(f"  obor {kod} ({nazev}) už existuje (id={row['id']}), přeskočeno")
        return row["id"]
    if not APPLY:
        print(f"  (dry-run) obor {kod} ({nazev}) by se vytvořil")
        return None
    cur.execute(
        "INSERT INTO content_obor (kod, nazev, popis_html, sort_order, schvaleno) VALUES (%s,%s,%s,%s,0)",
        (kod, nazev, popis_html, sort_order),
    )
    obor_id = cur.lastrowid
    print(f"  obor {kod} ({nazev}) -> vytvořen, id={obor_id}")
    return obor_id


def _insert_typologie(cur, obor_id, items):
    if obor_id is None and APPLY:
        return
    for i, (klic, nazev, kategorie_ids, popis_html) in enumerate(items):
        sort_order = (i + 1) * 10
        if APPLY:
            cur.execute("SELECT id FROM content_typologie WHERE obor_id=%s AND klic=%s", (obor_id, klic))
            if cur.fetchone():
                print(f"    typologie {klic} už existuje, přeskočeno")
                continue
            cur.execute(
                "INSERT INTO content_typologie (obor_id, klic, nazev, popis_html, kategorie_ids, sort_order, schvaleno) "
                "VALUES (%s,%s,%s,%s,%s,%s,0)",
                (obor_id, klic, nazev, popis_html, kategorie_ids or None, sort_order),
            )
            print(f"    typologie {klic} ({nazev}) -> vytvořena")
        else:
            print(f"    (dry-run) typologie {klic} ({nazev}) by se vytvořila, kategorie_ids={kategorie_ids!r}")


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=== OBOR 1: Vestavby do dodávek ===")
    obor1_id = _insert_obor(cur, "1", "Vestavby do dodávek", OBOR1_POPIS, 10)
    _insert_typologie(cur, obor1_id, OBOR1_TYPOLOGIE)

    print("=== OBOR 2: Pracovní ergonomické stoly na míru ===")
    obor2_id = _insert_obor(cur, "2", "Pracovní ergonomické stoly na míru", OBOR2_POPIS, 20)
    _insert_typologie(cur, obor2_id, OBOR2_TYPOLOGIE)

    print("=== OBOR 3: Prodej hliníkových profilů a příslušenství ===")
    obor3_id = _insert_obor(cur, "3", "Prodej hliníkových profilů a příslušenství", OBOR3_POPIS, 30)
    _insert_typologie(cur, obor3_id, OBOR3_TYPOLOGIE)

    print("=== OBOR 4: Vše ostatní ===")
    obor4_id = _insert_obor(cur, "4", "Vše ostatní", OBOR4_POPIS, 40)
    _insert_typologie(cur, obor4_id, OBOR4_TYPOLOGIE)

    if APPLY:
        conn.commit()
        print("\nZapsáno a commitnuto.")
    else:
        print("\n(dry-run - nic nezapsáno, spusť s --apply pro skutečný zápis)")


if __name__ == "__main__":
    main()
