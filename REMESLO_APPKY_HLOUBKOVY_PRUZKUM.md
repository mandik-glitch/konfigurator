# Řemeslo — hloubkový průzkum appek (víc metod, ne jen checkbox)

Založeno bot11, 2026-08-18 na zadání Roberta (přes bot3): navazuje na
`REMESLO_APPKY_SROVNANI.md` (checkbox tabulka 14 funkcí) a
`remeslo_workflow_apps` DB tabulku, ale Robert to označil za
"prvotní bezvýznamné" — chce jít do HLOUBKY každé appky víc metodami
(web kompletně, skutečné recenze, veřejný zdrojový kód appky bez
přihlášení, YouTube demo, fóra/diskuze, detailní ceník), ne jen
povrchní přehled funkcí.

**Sdílený soubor — víc botů píše svou appku do stejného souboru**
(bot23/bot12/bot10 dělají zbylé appky souběžně). Každá sekce níže je
napsaná JEDNÍM botem a nepřepisuje sekce ostatních — před editací si
vždy nejdřív přečti aktuální stav souboru a přidej svou sekci na
konec, ne mezi/přes existující.

Tohle je **jen průzkum** — nic neimplementováno, čeká na schválení.

---

## bot11 — EasyZakázky, Kalendo, Ř21

### EasyZakázky (easyzakazky.cz)

**Klíčové zjištění: appka je AKTUÁLNĚ MIMO PROVOZ (živě ověřeno).**
`easyzakazky.cz` (apex doména) nemá vůbec DNS záznam a nejde
rozřešit. `www.easyzakazky.cz` má CNAME na `webapp-49996.eu.
pythonanywhere.com` (bezplatný/hobby tarif PythonAnywhere), ale
skutečný obsah, který server vrací, je PythonAnywhere placeholder
stránka **"Coming Soon"** — appka na tomhle hostingu momentálně
NEBĚŽÍ (ověřeno přímým `curl` na produkční URL i s explicitním
`Host:` hlavičkou přímo na IP, stejný výsledek). Není to dočasný
výpadek jednoho requestu — konfigurace hostingu ukazuje na appku,
která tam v tuhle chvíli není nasazená.

- **Vydavatel**: Jan Galba, Antonína Slavíčka 705, Svitavy (fyzická
  osoba/OSVČ, ne firma s IČO dohledaným v tomhle průzkumu) — kontakt
  `jangalbait@gmail.com`, dohledáno z obchodních podmínek appky
  (které WebSearch index ještě má zachycené, i když appka sama je
  teď nedostupná).
- **Popis appky (z indexovaného obsahu, appka sama teď needostupná
  pro přímé ověření)**: jednoduchý online nástroj pro správu zakázek,
  faktur a klientů, cíl "mít přehled a šetřit čas" — evidence zakázek/
  kontaktů/odpracovaných hodin/nákladů na jednom místě, fakturace
  (zálohové i finální faktury, hlídání číselné řady, legislativa pro
  plátce i neplátce DPH), finanční přehled hned po přihlášení (tržby/
  náklady/zisk), vlastní logo na fakturách, PDF export, notifikace,
  fulltextové vyhledávání v appce.
  - **Ceník**: účet + předplatné platné 30 dní (přesná cena
    NEdohledána, appka sama nedostupná k ověření).
- **Recenze/fórum**: ŽÁDNÉ dohledány — žádná zmínka na Heurece,
  Facebooku, fórech. Appka je zjevně malá/indie (jméno fyzické osoby
  jako vydavatel, ne firma).
- **Archive.org**: ŽÁDNÝ snapshot dostupný (appka nikdy nebyla
  crawlerem archivována, nebo má `robots.txt` blok) — nejde ani
  zpětně ověřit, jak appka vypadala, když fungovala.

**Syntéza**: EasyZakázky je pravděpodobně **mrtvý/opuštěný
jednorázový projekt jednotlivce** — malý rozsah (fyzická osoba,
žádná firma), teď doslova nedostupný (placeholder hosting), nulová
stopa v recenzích/diskuzích. Pro srovnávač: NEDOPORUČUJI zařadit jako
aktivní appku — pokud vůbec, tak s jasným varováním "web momentálně
nefunguje" nebo appku ze srovnávače úplně vyřadit, dokud/pokud se
znovu nezprovozní.

### Kalendo (kalendo.cz)

Na rozdíl od EasyZakázky jde o **aktivně provozovanou, důvěryhodně
vypadající appku** s reálnou firmou v pozadí.

- **Vydavatel**: Kalendo a.s., IČO 23231122 (česká akciová
  společnost, ne jen OSVČ), zakladatel David Mareš. Kontakt: telefon
  +420 735 822 973, e-mail i WhatsApp, "osobní přístup bez call
  centra — odpovídá konkrétní osoba, obvykle stejný den".
- **Funkce**: appka se napojuje na kalendář uživatele (Google
  kalendář) a z něj AUTOMATICKY vede databázi klientů a eviduje
  zakázky — nový klient se založí automaticky ze zápisu v kalendáři,
  žádné ruční přepisování. Faktury s QR kódem jedním klikem (plátce
  i neplátce DPH), ARES integrace (auto-doplnění firemních údajů
  podle IČO), měsíční přehled tržeb, historie zakázek/faktur u
  každého klienta, appka funguje na iOS/Androidu/PC. **Nejsilnější
  odlišující prvek**: "příkazový systém" — přidání hashtagu do
  názvu/popisu události v kalendáři (např. `#faktura`, `#hotovo`)
  spustí automatickou akci v appce — appka se ovládá PŘÍMO z
  kalendáře, ne z vlastního odděleného rozhraní, což je jiný přístup
  než všechny appky v `REMESLO_PRUZKUM_WORKFLOW_APPS.md`.
- **Ceník** (kompletní, žádné skryté poplatky nenalezeny):
  | Tarif | Cena | Limity |
  |---|---|---|
  | Starter | 290 Kč/měs. | max 50 klientů, 100 termínů/měs., 30 faktur/měs. |
  | Pro | 590 Kč/měs. | neomezené klienty/termíny/faktury, pokročilé reporty |
  | Tým | na dotaz | týmová spolupráce, API, webhooks, dedikovaná podpora |

  20% sleva při ročním předplatném. 14denní trial zdarma bez
  kreditní karty, zrušení kdykoliv, přihlášení přes Google jedním
  klikem.
- **Infrastruktura/důvěryhodnost**: appka má samostatnou **veřejnou
  status stránku** (`status.kalendo.cz`) — živě ověřeno, běží na
  reálné Next.js aplikaci za Cloudflare (ne prázdná/mrtvá adresa) —
  silný signál profesionálně provozovaného SaaS (monitoring uptime
  appky je standard u seriózních B2B nástrojů, malé indie appky ho
  typicky nemají). Aktivní Instagram (`@kalendo_cz`, "Automatizační
  software pro živnostníky"), aktivní blog na `kalendo.cz/blog`.
- **Recenze/fórum**: ŽÁDNÉ nezávislé recenze/diskuze dohledány (ani
  Heureka, ani fórum) — appka zjevně nemá dostatečný objem
  uživatelů/stáří na to, aby vznikla organická diskuze, i když
  infrastrukturně působí seriózně.

**Syntéza**: Kalendo je **živá, profesionálně provozovaná appka** s
jasným odlišujícím nápadem (ovládání appky přes hashtagy přímo v
kalendáři) a transparentním ceníkem — nejdůvěryhodnější ze všech 3
appek v mé sekci. Chybí ale nezávislé recenze/sociální důkaz mimo
vlastní kanály firmy. Pro srovnávač: rozhodně zařadit, zdůraznit
kalendářově-first přístup jako unikátní odlišení.

### Ř21 (r21app.cz)

**Odpověď na otázku "žije appka, nebo je mrtvá?": PRAKTICKY JISTĚ
MRTVÁ appka/projekt.** Dva nezávislé signály:

1. **Doména `r21app.cz` aktuálně vůbec neexistuje** — živě ověřeno
   (`dig`/DNS lookup): `NXDOMAIN`, doména není ani registrovaná
   (natožpak že by na ní běžel web). WebSearch nástroj sice appku
   najde a popíše (má starý indexovaný/cachovaný obsah), ale přímý
   pokus o načtení webu dnes selže na úrovni DNS — nejde o dočasný
   výpadek serveru, doména samotná je pryč.
2. **Poslední záznam na Wayback Machine (archive.org) je z 26. 1.
   2022** — přes 4 roky starý, žádný novější snapshot neexistuje,
   což odpovídá tomu, že web přestal existovat/být udržovaný
   nejpozději v tomhle období.

- **Popis appky (z historického/indexovaného obsahu)**: mobilní
  appka (Android, 4.3+, ~19 MB) pro řemeslníky — na místě zakázky
  vytvoření zakázkového listu, výběr zákazníka, přidání materiálu,
  vyfocení práce, podpis zákazníka na místě, generování a odeslání
  faktury 2 kliky. **EET řešení**: hotovostní platby přes přenosnou
  Bluetooth tiskárnu účtenek (řešilo 3./4. vlnu EET, zrušenou 2023 —
  potvrzuje dřívější nález, že appka je vázaná na starý EET režim).
  Webové rozhraní navíc pro nastavení fakturačních údajů, přípravu
  materiálových položek, správu podúčtů zaměstnanců. Zajímavá
  odlišující funkce: appka cílila i na **bytová družstva/správce
  nemovitostí** — mohli napojit řemeslníky a posílat jim zakázky
  přímo do jejich Ř21 appky, se sledováním stavu (viděl/pracuje na
  tom/hotovo) — B2B2C model, který žádná jiná appka ve zkoumaném
  souboru nemá.
- **Ceník**: appka byla PLNĚ ZDARMA, s plánovanou placenou verzí
  "Ř21-Živnostník" za 188 Kč/měsíc, která podle všeho NIKDY plně
  nenaběhla (potvrzuje dřívější `price_note` v DB "plánovaná placená
  verze" — zůstala jen v plánu).
- **Recenze/fórum/Facebook**: žádné dohledány.

**Syntéza**: Ř21 je **mrtvá appka** — doména zanikla, poslední
aktivita nejpozději 2022, appka byla stavěná kolem legislativy (EET
3./4. vlna) zrušené 2023, takže i kdyby ještě existovala, by měla
neaktuální core funkci. Pro srovnávač: NEZAŘAZOVAT jako aktivní
appku, maximálně zmínit jako "historicky existující, dnes mrtvý
projekt" pro úplnost trhu.

**Zdroje**: kalendo.cz, status.kalendo.cz, easyzakazky.cz/
www.easyzakazky.cz (živé `curl`/`dig` ověření), archive.org Wayback
Machine (`r21app.cz`), WebSearch pro historický/indexovaný obsah
appek nedostupných k přímému ověření.

---

## bot12 — BitFaktura, Faktury.co, Timoty, Logeto

### ⚠️ Faktury.co (id 23) — NENÍ česká appka, chybné zařazení

**Klíčové zjištění: appka `faktury.co` (vydavatel Kajetan Dudczak,
Google Play balíček `co.faktury`) je POLSKÝ produkt, ne český.**
Původní mělký průzkum ji zařadil jako "česká appka zdarma" - obojí je
špatně:

- **Ne zdarma**: ceník je v polských zlotých (zł), tarify "Podstawowy/
  Optymalny/Premium" (6/8/12 zł/měsíc), 14denní trial, ŽÁDNÝ trvale
  zdarma tarif.
- **Ne česká**: appka má vestavěnou integraci **KSeF** (polský
  povinný systém e-fakturace) a export **JPK** (polský standardizovaný
  formát pro daňovou kontrolu) - obojí jsou polsky specifické
  legislativní funkce bez české obdoby. Kontakt `+48` (Polsko),
  e-maily `biuro@`/`serwis@faktury.co`. Google Play záznam appku
  řadí do produktové rodiny `kontakty.co`, se stejnými polskými
  daňovými funkcemi.
- Cílené české vyhledávání skutečné české appky "Faktury.co" nic
  nenašlo - jen nesouvisející české konkurenty (Vyfakturuj.cz,
  iDoklad, SuperFaktura, FLOWii, FakturujZdarma.cz).

**Syntéza**: tohle vypadá jako omyl při sestavování `remeslo_
workflow_apps` (možná záměna se skutečně českou appkou podobného
jména, nebo appka byla nalezena přes obecné "faktury" hledání bez
ověření jazyka/země). Vzhledem k tomu, že srovnávač má explicitní
pravidlo "jen appky s českou lokalizací" (viz `webapp/remeslo.html`
implementace bota10), **doporučuji záznam id 23 z DB odstranit nebo
opravit na skutečně českou appku**, ne dopisovat hloubkový průzkum
appky, která nesplňuje základní vstupní kritérium. Zbylých 5 metod
(recenze/demo/YouTube/fóra/ceník) jsem u týhle appky NEDĚLAL - nemá
smysl je dělat na appce, co stejně nepatří do srovnávače.

### BitFaktura (id 20)

**Oprava vydavatele**: DB má "BitFaktura s.r.o.", skutečný vlastník
je **Radgost** (polská firma) - appka je jedna z několika
lokalizovaných značek stejného produktu (BitFaktura v ČR/SK/UA,
"BitFactura" ve Španělsku), 600 000+ uživatelů napříč trhy, ~75
lidí v týmu, na českém trhu od cca 2019, mateřský produkt starý
9-10 let. Nejde o skrytě problematické zjištění (appka funguje
seriózně), jen o nepřesnost v DB.

**Web (kompletně)**: `/cenik`, `/fakturacni-program`, `/skladovy-
program`, `/integrace-a-rozsireni`, samostatný nápovědní portál
(napoveda.bitfaktura.cz), blog, i veřejná hlasovací nástěnka pro
požadavky na nové funkce (navrhy-zmen.bitfaktura.cz). Integrace:
GoPay/PayPal/Stripe/BitPay (platby), **Pohoda je JEDINÝ podporovaný
český účetní systém**, PrestaShop/Selly Shop/CS-Cart + Shoptet
plugin (doplnky.shoptet.cz/bitfaktura).

**Reálné recenze**: Testado.cz (8,1/10, nejvyváženější zdroj) -
chvála: "výhodnější než většina konkurence", sleva až 25 % při
delší předplatbě, víc-uživatelský/víc-firemní model, podpora 10/10.
Kritika: **zdarma tarif = jen 1 vydaná faktura/měsíc** (prakticky
nepoužitelné), UI hodnoceno jen 6/10 - recenzentka doslova "bloudila"
v navigaci, "trošku zastarale", nekonzistentní/nepřeložené texty
("Typ účtu: Max"), nejde upgradovat tarif v půlce období bez
kontaktování podpory. NástrojeProWeb.cz (9,5/10) čte se jako
promo/affiliate recenze (skoro bez kritiky) - nižší důvěryhodnost.
Google Play recenze (`cz.bitfaktura.app`, 30denní trial) se
nepodařilo stránkou vytáhnout jako text (příliš JS-heavy).

**⚠️ Bezpečnostní/důvěryhodnostní nález**: Podnikatel.cz nahlásil, že
platforma BitFaktura byla **zneužita podvodníky k vygenerování
falešných faktur vydávajících se za skutečné firmy** (cíl: Živéfirmy.
cz/DATABOX s.r.o.) - přímá citace z článku: *"Faktury jsou generovány
prostřednictvím platformy BitFaktura.cz. Ta umožňuje vystavení
faktur podepsaných naší společností, i když nejsme klienty těchto
platforem."* Platforma zjevně nedostatečně ověřuje, že vystavitel
faktury skutečně vlastní firmu, jejíž jméno/logo na faktuře používá.
Podnikatel.cz appku samotnou neoznačuje za podvodnou, jen chybu v
ověřování identity - ale je to reálný, zdokumentovaný incident, ne
jen UX drobnost.

**Ceník (živě ověřeno `/cenik`, LIŠÍ SE od DB)**: DB má "Start 99,
Standard 179, Pro 249, Pro Plus 399 Kč". Aktuální web ukazuje:
Micro 0 Kč (1 faktura/měs., 1 uživatel), Standard 129 Kč (sleva ze
161,25, neomezené faktury, 3 uživatelé), Pro 199 Kč (sleva z 248,75,
5 uživatelů, bankovní napojení), Pro Plus 299 Kč (sleva z 373,75, 10
uživatelů, IP omezení). Slevy platí jen při roční předplatbě, ceny
bez DPH. 30denní trial, žádný instalační poplatek.

**YouTube/fóra**: žádný český demo kanál nenalezen (jen `@bitfakturaUA`
ukrajinský, `@BitFactura` zřejmě španělský). Žádná organická
fóra-diskuze mimo výše zmíněný podvodný incident.

**Syntéza**: seriózní, cenově konkurenceschopná appka se širokým
základním feature setem, ale s prakticky nepoužitelným zdarma
tarifem, staromódnějším UI (nezávisle potvrzeno recenzí) a
zdokumentovaným bezpečnostním incidentem s ověřováním identity.
Vhodná pro cenově citlivé OSVČ/malé firmy bez potřeby hlubší
integrace do jiného účetního systému než Pohoda.

### Timoty (id 26)

**Web**: cílí na 30+ řemesel v domácích službách (instalatéři,
elektrikáři, hodinoví manželé, malíři, úklid...) - "full workflow",
ne jen fakturace. Funkce: plánování/kalendář zakázek, GPS lokace
techniků a mapy, elektronické zápisy/protokoly s digitálním
podpisem, foto přílohy, formuláře, evidence materiálu, přehled
ziskovosti zakázek, **automatický překlad rozhraní do ukrajinštiny a
ruštiny** (zjevně cílí i na firmy se zahraničními dělníky -
odlišující funkce). Registrace rovnou do plné zkušební appky.
Vlastní YouTube kanál (@timotycz9294), ale hlavní "demo" cesta je
živá schůzka s obchodníkem ("Rezervujte si ukázku aplikace"), ne
samoobslužný veřejný demo mód - metoda "veřejné JS bez přihlášení"
tady nepřinesla nic.

**Reálné recenze**: App Store 4,3/5, jen 10 hodnocení (malý vzorek).
Jediná viditelná recenze (Werewolf1202, 10/2024) - přímá citace:
*"Aplikace jako taková není špatná, jen je škoda, že nefunguje mimo
dosah sítě, kdy vás automaticky odhlásí a opět přihlásí, jen tam,
kde je opět [signál]."* → **potvrzená reálná stížnost: žádný offline
režim**. Google Play recenze se nepodařilo získat (JS-only stránka).

**⚠️ Nesrovnalosti ve vlastním marketingu appky**: appka/partnerské
weby tvrdí "Google 5,0 hvězdiček, App Store 4,8 hvězdiček" - **realita
na App Store je 4,3/10 hodnocení**, neodpovídá. Referenční stránka
(24 firemních citací napříč obory) má **dvě různé firmy se
IDENTICKOU citací** ("Timoty je skvělou volbou pro organizace, které
hledají efektivní...") - možná známka needitovaných/šablonovitých
referencí. Trial je na webu "7 dní", appka jinde tvrdí "14 dní" -
další drobný rozpor.

**Ceník** (ověřeno `timoty.cz/cena/`, žádné skryté poplatky): roční
platba (2 měsíce zdarma) - Jednotlivec 490 Kč/měs. (1 uživatel), Tým
1 405 Kč/měs. (do 5, ~281 Kč/uživatele), Malá firma 2 490 Kč/měs.
(do 10, ~249 Kč/uživatele), Větší firma 4 150 Kč/měs. (do 20, ~207,50
Kč/uživatele). Měsíční platba o 20-30 % dráž. Všechny tarify mají
STEJNÉ funkce - liší se jen počtem uživatelů a úrovní podpory.

**Fóra**: nic nezávislého nenalezeno (ani Reddit, ani BusinessCenter/
Podnikatel.cz) - buď appka je mimo veřejnou pozornost, nebo se o
appkách tohoto typu řemeslníci veřejně prostě nebaví.

**Syntéza**: široký obor pokrytí, poctivý/přehledný ceník, funkce
šité na míru terénním týmům (vč. jazykové podpory pro zahraniční
pracovníky) - ale chybí offline režim (potvrzeno), extrémně malý a
neověřitelný vzorek recenzí, a několik drobných nesrovnalostí mezi
vlastním marketingem a ověřitelnou realitou. Cena za uživatele klesá
s velikostí týmu - lepší fit pro menší až středně velké servisní
firmy s víc techniky než pro jednotlivého OSVČ (490 Kč/měs. je
citelná fixní položka oproti appkám zdarma).

### Logeto (id 27)

**Vyjasnění vztahu Logeto ↔ vykazprace.cz (byla to priorita
zadání)**: **potvrzeno, je to STEJNÝ produkt, stejná firma** -
Systemart s.r.o. (založena 2003, Hradec Králové) postavila nejdřív
účetní software "Tempo", pak v roce 2007 appku "Výkaz práce"
(docházka + evidence pracovní doby). Od 2018 firma appku
internacionalizuje pod anglickým jménem **Logeto** pro trhy mimo
ČR/SK - v ČR/SK appka běží dál jako "Výkaz práce", jinde jako
"Logeto", OBĚ značky souběžně, ne úplný rebrand. Technicky potvrzeno:
stejné App Store ID (667378257) servíruje jak "Výkaz práce", tak
"Logeto" záznam; Google Play balíček `cz.vykazprace` je teď
pojmenovaný "Logeto – Time tracking". `vykazprace.cz` je živá,
samostatná česká stránka s vlastním CZK ceníkem (ne přesměrování na
logeto.com). **Závěr: sloučení appky v `REMESLO_APPKY_SROVNANI.md`
jako 1 appka bylo správně.**

**Web/funkce**: docházka (GPS ověřená mobilní docházka, otisk prstu/
čipové terminály), evidence času a nákladů na zakázky, digitální
kniha jízd (automaticky doplňovaná), evidence výdajů, podklady pro
mzdy, kontrola rozpočtu, multiplatformní (web, mobil Android/iOS,
desktop, fyzické terminály, **i appka pro Windows na Microsoft
Store**). Veřejná dokumentace (`dokumentace.vykazprace.cz`) je
neobvykle otevřená a popisuje vnitřní logiku appky bez přihlášení
(viz metoda 3 níže).

**Reálné recenze**: App Store 4,0★, 47 hodnocení. Chvála: "super,
přehledná", "Doporučuji všem osvč". Opakující se stížnosti: export
měsíčních výkazů není z appky samotné zjevný (nutnost přes webový
portál); "krizeni casu mezi záznamy" při kombinaci mobilní appky a
fyzického terminálu (nutná oprava adminem); "složité zadávání údajů"
- data jedné zakázky rozházená přes víc samostatných karet
(odrazuje jednotlivce/OSVČ konkrétně). Cenový model prý zaskočil
živnostníky, dokud ho vývojář nevysvětlil (zdarma tarif existuje, ale
není zjevný). Google Play stránka se nepodařilo vytáhnout jako text
(JS-only).

**Veřejné demo bez přihlášení**: žádný samostatný "vyzkoušej bez
registrace" mód (2měsíční trial vyžaduje registraci) - ALE veřejná
dokumentace funguje jako neobvykle transparentní náhrada: explicitně
popisuje výpočet nákladů/výnosů ("dle odvedené práce a nastavitelných
sazeb"), hierarchii vazby čas→zakázka, schvalovací workflow
zadaných záznamů, pravidla evidence absencí (nemoc, přestávky) - vše
veřejně čitelné bez účtu.

**YouTube**: oficiální kanál `@vykazprace71` ("Výkaz práce") +
samostatný slovenský `@vykazpracesk7810` - existence potvrzena, obsah
jednotlivých videí nedohledán (YouTube cookie-wall zablokoval
statické stažení).

**Fóra**: nic nezávislého nenalezeno (ani Reddit, ani Facebook
skupiny řemeslníků, ani BusinessCenter/Podnikatel.cz) - appka má
prakticky nulovou organickou stopu mimo vlastní app-store recenze.

**Ceník** (ověřeno `vykazprace.cz/cena/`, vše bez DPH): Zdarma - 0
Kč/měs., jen 1 pracovník, obsahuje výkazy práce, docházku/plán,
knihu jízd, výdaje, omezené zakázky. Premium - **40 Kč/aktivní
uživatel/měsíc základ** (neomezený počet uživatelů), stejné funkce
jako Zdarma. Doplňkové moduly, každý zvlášť za aktivního uživatele/
měsíc: Zakázky +40 Kč, Sazby +15 Kč, Vlastní pole +15 Kč, Benefity
+5 Kč, Rozpočet +15 Kč. Model "platíte jen za aktivní uživatele" -
neaktivní uživatelé nic nestojí. 2měsíční trial zdarma. Slevy za
předplatbu: 5 000+ Kč → 10 %, 20 000+ Kč → 20 %, 50 000+ Kč → 30 %.
(Mezinárodní logeto.com strana používá stejnou strukturu v EUR/USD -
potvrzuje, že jde o stejný billing engine, jen s lokalizovanou
měnou.)

**Syntéza**: velmi vyzrálý, široký feature set (docházka + čas +
zakázky + kniha jízd + mzdy + rozpočet v jednom systému), granulární
platba jen za skutečně používané moduly/uživatele, multiplatformní
včetně fyzických terminálů, zdarma tarif je skutečně použitelný
produkt pro 1 osobu, ne jen demo. Slabina: šíře funkcí je zároveň
překážkou pro jednotlivce - recenzenti výslovně zmiňují složité
zadávání přes víc karet jako bariéru pro sólo použití; známý bug
synchronizace mobil/terminál; téměř nulová nezávislá komunitní
stopa. Nejlepší fit: malé až středně velké servisní/kontraktorské
firmy s víc terénními pracovníky, kteří potřebují docházku + náklady
na zakázky + knihu jízd pohromadě. Slabší fit: jednotlivý OSVČ, co
chce jen jednoduché sledování zakázek/faktur - složitost UI mu
nesedí, i když cena (často 0 Kč) by mu seděla.

**Zdroje**: bitfaktura.cz (`/cenik`, `/fakturacni-program`,
`/skladovy-program`, `/integrace-a-rozsireni`), napoveda.bitfaktura.cz,
navrhy-zmen.bitfaktura.cz, testado.cz, nastrojeproweb.cz,
podnikatel.cz (podvodný incident), faktury.co (ceník/legislativní
funkce), timoty.cz (`/cena`, `/reference`), App Store (Timoty,
Logeto/Výkaz práce), vykazprace.cz (`/cena`), dokumentace.vykazprace.cz,
logeto.com, Google Play (nepodařilo se vytáhnout text recenzí u
žádné ze 4 appek - JS-only stránky).

---

## bot11 (2) — Buildo, Buildary.Online, iDoklad, SuperFaktura

**Důležité upozornění na kategorii:** na rozdíl od appek v obou
předchozích sekcích (plnohodnotné "evidence zakázek" appky) patří
tahle 4 appky do 2 UŽŠÍCH kategorií, ne do stejné škatulky jako
Kalendo/Timoty/PROFIDAT:
- **Buildo + Buildary.Online = elektronický stavební deník**
  (`construction_diary`) — legislativně řešený produkt (viz níže),
  ne obecná evidence zakázek řemeslníka. Cílovka jsou STAVEBNÍ FIRMY
  se STAVBAMI podléhajícími stavebnímu deníku, ne každý řemeslník.
- **iDoklad + SuperFaktura = čistá fakturace** (`invoicing_only`) —
  řeší jen doklady/fakturaci, ŽÁDNÉ plánování zakázky/foto-dokumentaci/
  timesheets jako appky typu Kalendo/Timoty.
Srovnávač by tohle měl jasně komunikovat jako samostatné kategorie s
jinou otázkou na začátku ("potřebuješ stavební deník?" / "potřebuješ
jen fakturovat?"), ne appky v jedné tabulce vedle sebe se stejnými
sloupci funkcí — vedlo by to k nesmyslnému srovnání jablek s hruškami.

### Buildo (buildoapp.com, Team Buildo)

**Web/ceník** (`buildoapp.com/CZ/`): freemium, 3 tarify —
**Free** (3 aktivní stavby, 1 uživatel, "zkušební verze/drobné
stavby"), **PRO** (9,99 €/měsíc nebo 99,9 €/rok — samostatní
řemeslníci, 2 uživatelé, neomezené stavby, export do Excel, vlastní
logo v exportech), **Organizace** (od 6,99 €/místo/měsíc — týmy
4–21 uživatelů, neomezené stavby). **DB záznam "zdarma" je zavádějící**
— appka MÁ placené tarify, jen vstupní/omezená verze je zdarma
(oprava k zapsání do `remeslo_workflow_apps`).

Funkce: evidence pracovníků/materiálu/strojů, fotodokumentace
průběhu, export PDF/Excel, automatické počasí, týmová spolupráce
(sdílení přes e-mail/Google Drive místo klasického papírového sešitu).

**Recenze**: AppBrain uvádí 4,08★ (220 hodnocení), ~46 tis. stažení
celkem, ~240/měsíc nedávno — malá, ale živá appka s pomalým, stálým
růstem. Dohledané textové recenze (přes agregátory, ne přímo Google
Play — JS-only stránka nešla přečíst) zmiňují appku jako "dokonalou
a pohodlnou", s přáním VÍC nastavení (ceny strojů) a možností, aby
se ZAMĚSTNANCI mohli sami přihlašovat na stavby a sledovat si
odpracované hodiny (chybějící feature, ne bug).

**Syntéza**: malá, aktivní, důvěryhodná niche appka pro drobné až
střední stavební firmy — jasně cílená (ne univerzální evidence
zakázek), reálné, i když řídké recenze. Srovnávač by ji měl uvádět
jako "levnou volbu pro STAVBY s deníkem", ne konkurenta Kalenda.

### Buildary.Online (buildary.online, First information systems s.r.o., Ostrava)

**Web**: mnohem VĚTŠÍ/formálnější produkt, než DB záznam "zdarma"
naznačuje — cloudová platforma splňující zákonné požadavky na
elektronický stavební deník (zák. 283/2021 Sb., příloha 12 vyhl.
131/2024 Sb. — kvalifikovaný elektronický podpis, PDF protokol s
právní závazností). Firma s 20+ lety zkušeností ve stavebnictví.
Zajímavé zjištění: appku používá **ČEZ Distribuce jako white-label**
(samostatná appka "Stavební deník ČEZ Distribuce" na Google Play,
stejný vydavatel `com.firstis.*`) a reference zmiňují HOMOLA a.s.
(velká stavební firma) — jde o B2B produkt pro STŘEDNÍ/VELKÉ firmy a
zakázky, ne pro jednotlivého řemeslníka.

**Cena**: NEZDARMA v praxi — cena podle počtu uživatelů NA STAVBĚ a
počtu modulů, každá stavba fakturována zvlášť, platební výzvy
automaticky čtvrtletně podle aktuálního počtu lidí v týmu projektu;
u větších objemů individuální smlouva na míru. Konkrétní Kč částky
se nepodařilo dohledat (ceník je za přihlášením/na dotaz) — **DB
záznam "zdarma" je nesprávný, potřeba opravit** stejně jako u Buildo.

**Nezávislé srovnání** (`stavei.cz` — POZOR, píše to konkurent Stavei,
takže zaujaté; Buildary dostal v článku nejméně prostoru a ŽÁDNOU
zmínku ceny, což může být záměrná taktika konkurenta, ne fakt o
appce) řadí Buildary vedle appky Stavee do kategorie "formální
deníky s podpisy/časovými razítky", vhodné pro **veřejné zakázky v
nadlimitním režimu** — odlišuje ji to od appky Stavario (širší
provozní systém: docházka, sklady, AI) i od Buildo (levnější,
menší firmy).

**Syntéza**: living, důvěryhodný, ale ENTERPRISE produkt — reálná
reference (ČEZ, HOMOLA), legislativně podložený, ale mimo cílovku
"jednotlivý řemeslník/malá parta", na kterou Řemeslo primárně cílí.
Srovnávač by měl u Buildary jasně napsat "pro větší stavební firmy/
veřejné zakázky", ne ho nabízet jako alternativu k Buildo pro malého
živnostníka.

### iDoklad (Seyfor, a.s.)

**Aktuální ceník** (`idoklad.cz/cenik`, ověřeno živě — **liší se od
DB záznamu**, DB má patrně starší/jinak vypočtenou hodnotu):
Zdarma (max 5 kontaktů), **Základní** 187 Kč/měs. (roční platba,
240 Kč měsíční), **Oblíbený** 358 Kč/měs. (roční, 430 Kč měsíční —
párování plateb, upomínky, API 7 500 req/měs.), **Prémiový**
625 Kč/měs. (roční, 750 Kč měsíční — API 75 000 req/měs., prioritní
telefonická podpora). 60 dní zkušebně, 30denní garance vrácení peněz,
ceny bez DPH. **DB `price_note` (329/579/949 Kč) je třeba opravit**
na aktuální hodnoty výš.

**Recenze — rozpor mezi redakčním a uživatelským hodnocením**:
agregátor `5nej.cz` dává iDokladu 8,3/10 redakčně, ale jen 5,2/10 od
uživatelů — reálný rozdíl mezi marketingem/first-impression a
dlouhodobou zkušeností. Konkrétní citovaná stížnost: chyba při
vystavování DPH v OSS režimu pro zálohy mimo ČR/SR — "program nám
totálně zlikvidoval účetnictví", podpora popsána jako arogantní a
neochotná řešit, časově nenahraditelná škoda při opravách dokladů.
Další zmíněné mezery: chybí párování plateb se všemi bankami,
omezení zdarma verze (5 kontaktů, žádná mobilní appka, žádné
párování/upomínky).

**Pozitiva**: 300 tis.+ uživatelů, integrace s Pohoda/Money S3
(logické u Seyforu — STORMWARE ekosystém), přehledné/profesionálně
vypadající faktury, silné API pro e-shopy.

**Syntéza**: tržní lídr objemem uživatelů, funkčně nejbohatší ze
zkoumaných fakturačních appek, ale s reálným rizikem u OKRAJOVÝCH
případů (OSS DPH) a podporou, která podle recenzí neřeší problémy
vstřícně — srovnávač by měl u iDokladu ukázat OBĚ čísla (redakční i
uživatelské hodnocení), ne jen jedno.

### SuperFaktura (SuperFaktura, s.r.o. — provozuje slovenská agentura 2day, na trhu od 2011)

**Aktuální ceník** (`superfaktura.cz/cenik`, ověřeno živě — **také se
liší od DB záznamu**): Zdarma (5 kontaktů, 14 jazyků faktur, 20
extrakcí dokladů zdarma), **Basic** 129 Kč/měs., **Standard**
279 Kč/měs. (cenové nabídky, objednávky, pokladny, automatické
upomínky, DPH přiznání, opakované faktury, víc uživatelů), **Premium**
469 Kč/měs. (štítky faktur, API, víc číselných řad, neomezený
multi-user přístup). 30 dní zkušebně, 14denní garance vrácení peněz,
ceny bez DPH. Bonus: sledování cest zdarma do 5 000 km ve všech
tarifech. **DB `price_note` (199-239/479/699-769 Kč) je třeba
opravit** na aktuální hodnoty výš.

**Recenze**: 70 tis.+ uživatelů napříč SK/CZ/AT, jen za poslední
měsíc 127 tis. aktivních uživatelů vyfakturovalo 8,5 mld. Kč
(agregátní číslo z marketingu appky, ne nezávislý zdroj). Pozitiva
napříč recenzemi: rychlost, přehlednost, dobrý poměr cena/výkon
oproti iDokladu/Fakturoidu. Zmíněné problémy: pomalé načítání a
občasné výpadky, omezené možnosti úpravy šablon faktur podle
vlastních představ.

**Syntéza**: levnější a jednodušší alternativa k iDokladu se
srovnatelným hodnocením (4,8★ App Store u obou), méně recenzí na
App Store (158 vs. 3300) ale širší reálná uživatelská základna přes
web/desktop verzi (App Store číslo tedy podhodnocuje skutečné
rozšíření appky). Žádné systematické stížnosti srovnatelné
závažnosti s OSS-DPH incidentem u iDokladu.

**Napříč iDoklad/SuperFaktura**: obě appky mají DB ceny neaktuální
(pravděpodobně zaznamenané z jiného tarifového období/měny výpočtu) —
doporučuju při stavbě srovnávače ceny appek pravidelně re-verifikovat
místo spoléhání na jednorázový zápis, ceníky SaaS appek se mění
častěji než u appek s jednorázovou cenou.

**Zdroje**: buildoapp.com/CZ/, appbrain.com (Buildo rating/downloads),
buildary.online (`/cs/cena`, `/cs/podrobnosti`, `/cs/moduly/`),
stavei.cz (srovnávací článek, konkurenční zdroj), Google Play
(Buildary white-label appky pro ČEZ Distribuci), ckait.cz, dek.cz,
idoklad.cz/cenik, 5nej.cz (iDoklad i SuperFaktura recenze),
superfaktura.cz/cenik, svetwp.cz, forexmag.cz, 42media.cz,
flowii.com, webhostingcentrum.cz, businesscenter.podnikatel.cz
(obecná diskuze, appky konkrétně nezmíněny).

---

## bot3 (dříve bot12) — DílnaTech, PROFIDAT, Řemeslník PRO

Dokončuje posledních 7 appek do plného pokrytí 14 českých appek v
srovnávači (`language_cs=1`) - tahle sekce + bot11 "(2)" výše.

### ⚠️ DílnaTech (id 28) — ŠPATNÉ zařazení do kategorie, jiná appka než zbytek "full_workflow_cz"

**Hlavní zjištění: DílnaTech NENÍ obecná appka pro řemeslníky.** Je to
úzce specializovaný systém **výhradně pro autoservisy** (příjem
vozidla, pracovní listy, role poradce/mechanik/skladník, sklad
náhradních dílů) - cílovka autoopravny, ne instalatéři/elektrikáři/
malíři jako zbytek appek v kategorii `full_workflow_cz`. Vydavatel
**ErokoTech, s.r.o.** (Ostřetín, Pardubický kraj) je obecné vývojářské
studio (Flutter) s ~8 velmi různorodými portfolio projekty (appka na
jazyky, laboratorní appka, appka pro bazénové zastřešení, appka pro
domácí mazlíčky...) - DílnaTech je jen jeden z nich, ne jejich
specializace. Firma navíc nabízí i podobně popsaný "Helios
Automotive" (příjem vozidla se skenováním VIN) - nejasný vztah k
DílnaTech, nepodařilo se ověřit.

**Web**: žádný samostatný ceník/FAQ/blog, jen kontaktní formulář na
konzultaci. Funkce: příjem do servisu, řízení zakázek, fotodokumentace
u zakázky, sklad (příjemky/výdejky), plánování/kalendář, SMS/push
notifikace zákazníkům, role-based přístup, iOS/Android/web (PWA),
offline režim s frontou synchronizace.

**Recenze**: ŽÁDNÉ dohledány. Google Play (`cz.dilnatech`) bez
viditelného hodnocení v search snippetech (na rozdíl od appek s
dostatečným objemem instalací) - signál velmi malého počtu uživatelů.

**Demo/JS, YouTube, fóra**: nic nenalezeno - žádné self-service demo,
žádné video, žádná zmínka na fórech.

**Ceník**: veřejně nikde nedostupný, čistě B2B prodej na dotaz.

**Kontext trhu**: existuje etablovaná konkurenční scéna specializovaného
software pro autoservisy v ČR (Carsys, ProCad AutoServis, ADM Win,
Dílna.online, MojeDílna) - DílnaTech je nový/malý hráč do už
obsazeného, jinak zaměřeného trhu.

**Syntéza**: pro srovnávač zaměřený na OBECNÉ řemeslníky je relevance
DílnaTech sporná - doporučuju buď přeřadit do samostatné kategorie
"autoservisy" (mimo `full_workflow_cz`), nebo úplně vyřadit ze
srovnávače, ne prezentovat jako plnohodnotnou konkurenci Timoty/Logeto.

### PROFIDAT (id 29) — doplnění k dřívější analýze

Appka i její veřejně čitelný JS (`js/dashboard.js`, `js/zakazky.js`,
`js/pdf.js`, `js/limits.js` na `profidat.cz/app.html`, bez přihlášení)
byly už dřív podrobně zanalyzované (viz `REMESLO_PRUZKUM_WORKFLOW_
APPS.md` sekce C - přesné vzorce zisku/marže/Kč-hod i klasifikační
prahy dashboardu) - nebylo co znovu odvozovat, jen ověřeno a doplněno:

**Vydavatel** (v DB dosud chyběl): **Roman Hlaváč, IČO 07529325**
(OSVČ), ověřeno křížově v ARES - registrace 8.10.2018, sídlo Zlín,
status aktivní. Appka vzniká zjevně z reálné praxe tvůrce ("z
pracovních problémů, ne z katalogové prezentace"), vedle appky nabízí
i placený Flutter/Firebase konzultační servis.

**Cena**: PLATÍ dřívější zjištění (za přihlášením, `js/limits.js`
potvrzuje existenci tarifů BASIC/STANDARD, ale konkrétní Kč hodnoty
jsou v privátním Firestore dokumentu) - genuinně nedohledatelná
zvenčí, ne mezera v hledání.

**Recenze/fóra/YouTube**: nulová stopa napříč VŠEMI kanály (Google,
Facebook - stránka za přihlašovací zdí, Heureka - nerelevantní
kategorie, Reddit, BusinessCenter.cz, Podnikatel.cz) - jediné video je
registrační tutoriál (`youtu.be/Tlx_5XhNBl8`), ne produktové demo.
POZOR na kolizi jmen - "ProfiDAT" na YouTube vytahuje nesouvisející
mezinárodní firmu (přenos dat pro jeřáby).

**Syntéza**: malý sólo projekt s promyšlenou, prakticky odladěnou
logikou (dashboard klasifikace zisku/marže/Kč-hod, 2 typy PDF
protokolu), ale nulová veřejná stopa důvěryhodnosti a cena skrytá za
loginem - bariéra pro rozhodování bez přímého kontaktu s appkou.
Vhodné pro menší OSVČ, kterým jde hlavně o finanční přehled po
zakázce; nevhodné pro někoho, kdo chce ověřit appku přes reference
před nasazením.

### Řemeslník PRO (id 30)

**Vydavatel**: ELHACOM = **Petr Hájek**, jednotlivec/OSVČ (IČ
01245511, Pelhřimov, neplátce DPH). Firma má JINÝ, zavedenější
vlajkový produkt - **Revizero** (appka pro revizní techniky elektro/
plyn/tlak, vlastní fórum, job portál, 5,0★/8 recenzí na Google) -
Řemeslník PRO je vedlejší/menší produkt solo-vývojáře s prokazatelně
fungující firmou v pozadí (na rozdíl od zcela anonymního EasyZakázky),
ale recenze Revizera se NEDAJÍ použít jako důkaz kvality Řemeslníka
PRO - jiný produkt.

**Web**: appka je nová (landing page publikována cca 8.12.2025, tedy
~8 měsíců stará). Funkce: zakázka (název/popis/stav/odhad ceny/
poznámky/klient), databáze klientů, fotodokumentace u zakázky jako
podklad k fakturaci, faktury PDF/tisk s auto-předvyplněním, evidence
firemních nákladů (materiál/PHM/nářadí) po měsících.

**Recenze/fóra/YouTube**: ŽÁDNÉ nalezeny specificky pro Řemeslník
PRO - stejný vzorec jako Ř21/EasyZakázky z prvního kola (nová/malá
appka, nulová organická stopa).

**Cena**: **365 Kč/rok, jediný tarif** (potvrzeno 3× nezávisle,
konzistentní s DB), 14denní trial zdarma bez závazku, žádné skryté
poplatky/další moduly nalezeny.

**Syntéza**: nová, velmi levná appka od solo-vývojáře s jinak
prokazatelně fungující firmou (ELHACOM/Revizero), ale sama o sobě bez
nezávislé stopy (recenze/YouTube/fóra) - nelze posoudit kvalitu jinak
než podle vlastního popisu appky. Vhodná pro drobného OSVČ hledajícího
nejlevnější řešení evidence zakázek/klientů/nákladů, ochotného přijmout
riziko nového/málo ověřeného produktu.

**Zdroje**: dilnatech.cz, ErokoTech firemní web/portfolio, Google Play
(`cz.dilnatech`), profidat.cz (`/app.html`, `/evidence-zakazek.php`,
`/obchodni-podminky.html`), ares.gov.cz (Roman Hlaváč IČO 07529325),
`js/dashboard.js`/`js/zakazky.js`/`js/pdf.js`/`js/limits.js` (PROFIDAT
veřejný klientský JS), YouTube (`Tlx_5XhNBl8`), elhacom.cz
(Řemeslník PRO landing + firemní kontext), Revizero.cz/.sk (ELHACOM
vlajkový produkt, srovnávací kontext).

---

## Shrnutí celého hloubkového kola (14/14 českých appek pokryto)

| Appka | Stav | Doporučení pro srovnávač |
|---|---|---|
| Kalendo | živá, důvěryhodná | zařadit, zdůraznit kalendářový ovládací prvek |
| Timoty | živá | zařadit, poznamenat chybějící offline režim |
| Logeto | živá (= Výkaz práce) | zařadit, sloučení s vykazprace.cz potvrzeno správné |
| BitFaktura | živá | zařadit, opravit vydavatele (Radgost, ne "BitFaktura s.r.o.") a cenu |
| PROFIDAT | živá, malá | zařadit s poznámkou "cena za loginem, bez recenzí" |
| Řemeslník PRO | živá, nová/malá | zařadit s poznámkou "bez recenzí, ~8 měsíců stará" |
| iDoklad | živá, velká | zařadit, opravit cenu, poznamenat OSS-DPH incident |
| SuperFaktura | živá, velká | zařadit, opravit cenu |
| Buildo | živá | zařadit, opravit "zdarma" na skutečné ceny |
| Buildary.Online | živá, B2B/enterprise | zvážit vyřazení - cílí na firmy/white-label, ne na jednotlivého řemeslníka |
| Kalendo/Timoty/Logeto vs. iDoklad/SuperFaktura | - | **strukturální doporučení (bot11): oddělit `invoicing_only` od `full_workflow_cz` do samostatných sekcí srovnávače, ne míchat** |
| DílnaTech | živá, ale špatná kategorie | přeřadit mimo `full_workflow_cz` (jen autoservisy) nebo vyřadit |
| Faktury.co | **NENÍ česká appka** | opravit/odstranit záznam (polský produkt, `language_cs` chybně 1) |
| Ř21 | mrtvá (doména neexistuje) | vyřadit |
| EasyZakázky | mrtvá (placeholder hosting) | vyřadit nebo označit "web nefunguje" |

Čeká na Robertovo schválení, které konkrétní úpravy DB provést.

---

## bot11 (3) — remeslnik.online

Dodatek mimo původních 14 - appka nebyla v `remeslo_workflow_apps`
(pilotní filtr `language_cs=1` ji buď minul, nebo je appka novější
než pilotní sběr dat). Robert zadal hloubkový průzkum přes bot3,
2026-08-19.

### remeslnik.online (Řemeslník Online)

**Klíčové zjištění: appka je v RANÉ/PŘED-LAUNCHOVÉ fázi vývoje, ne
plně hotový produkt jako zbytek zkoumaných appek.**

- **Homepage** doslovně popisuje stav vývoje jako "Fáze 2" -
  "Implementováno ve Fázi 2" a "Připraveno pro bezpečný růst
  aplikace", s výčtem, co je HOTOVO: bezpečné přihlášení, oddělená
  data firem (multi-tenant), databáze PostgreSQL, jednotné UI.
  Plánovaných je 6 modulů (Zákazníci a zakázky, Cenové nabídky,
  Faktury, Poptávky materiálu, Náklady a ziskovost, Dodavatelé a
  řemeslníci) - homepage textem naznačuje, že produktové moduly
  SAMOTNÉ ještě nejsou dostupné, jen infrastruktura okolo nich.
- **Rozpor s ceníkem** (`/tarify`): na rozdíl od homepage tahle
  stránka uvádí KONKRÉTNÍ, hotově vyhlížející tarify, jako by appka
  už byla plně funkční:
  | Tarif | Cena | Limity |
  |---|---|---|
  | Free | zdarma | 5 faktur/měs., 5 nabídek/měs., 3 aktivní zakázky, 10 zákazníků, 3 "AI vytěžení"/měs. |
  | Standard | 249 Kč/měs. (vč. DPH) | 100 faktur/měs., 100 nabídek/měs., 50 aktivních zakázek, 500 zákazníků, 50 AI vytěžení/měs. |
  | Pro | 499 Kč/měs. (vč. DPH) | neomezené faktury/nabídky/zakázky/zákazníci, 250 AI vytěžení/měs. |

  Tenhle rozpor (homepage "jen infrastruktura hotová" vs. ceník s
  konkrétními produktovými limity) je pro srovnávač důležitý signál -
  buď appka mezitím produktové moduly dodala a homepage text je
  zastaralý, nebo je ceník publikovaný dopředu před dokončením
  produktu. Nedá se to zvenčí rozlišit bez účtu.
- **"AI vytěžení"** (AI extraction/zpracování) je limitovaná
  položka v každém tarifu, ale NENÍ nikde na homepage vysvětlená, co
  přesně dělá - pravděpodobně AI zpracování dokladů/vytěžení dat
  (podobný směr jako Doklado "sken účtenek za 3 s" z
  `REMESLO_APPKY_HLOUBKOVY_PRUZKUM_APP_STORE` sekce), ale tohle je
  odhad, ne ověřené.
- **Přihlášení/registrace**: appka MÁ funkční formulář přihlášení
  (e-mail/heslo, zapomenuté heslo) i registraci ("Vytvořte si ho") -
  není to jen prázdná marketingová stránka, backend na tohle
  minimálně reaguje. Bez vytvoření účtu nejde ověřit, co je za
  přihlášením skutečně funkční.
- **Vydavatel/firma**: ŽÁDNÉ údaje o firmě/IČO/kontaktu nikde na
  webu (jen "Řemeslník Online · 2026" v patičce) - na rozdíl od
  Kalenda (Kalendo a.s., IČO, telefon, e-mail) nebo BitFaktury
  (Radgost) tahle appka nemá žádnou dohledatelnou právnickou/fyzickou
  osobu za sebou. Nejde tedy udělat ARES lookup (chybí IČO i přesný
  název firmy k vyhledání).
- **Recenze/fóra/YouTube**: NULOVÁ stopa - appka není indexovaná ani
  v běžném vyhledávání (`site:remeslnik.online` nevrátilo žádný
  výsledek z domény samotné), žádné recenze, žádná diskuze, žádné
  YouTube demo (5 nejrelevantnějších výsledků na "remeslnik.online"
  byly nesouvisející videa - komediální scénka, výroba svíček,
  pálkařských raket, muzejní záznam). **Žádné použitelné video,
  žádné screenshoty k pořízení** - appka evidentně nemá zatím žádný
  marketingový/demo obsah mimo vlastní web.

**Syntéza**: remeslnik.online je pravděpodobně zcela nový, možná
teprve rozjížděný projekt (2026 copyright, nulová externí stopa,
homepage explicitně přiznává rozestavěnost) - NENÍ to zavedený
konkurent na úrovni Kalenda/PROFIDATu/iDokladu, spíš rané stádium se
solidně znějícím plánem (6 modulů pokrývajících celý cyklus
zakázka→faktura, cenově konkurenceschopné tarify blízké Kalendu).
Pro srovnávač: **zatím NEZAŘAZOVAT jako plnohodnotnou appku** - buď
počkat, až appka reálně spustí produktové moduly (ověřit časem znovu),
nebo zařadit jen s výrazným upozorněním "rané stádium, produktové
moduly možná ještě nejsou funkční, ověřeno zvenčí bez účtu". Řadí se
do kategorie `full_workflow_cz` (moduly pokrývají zakázky→nabídky→
faktury→náklady), NE `invoicing_only`.

### Zdroje (remeslnik.online)

`remeslnik.online` (homepage + `/tarify` + `/prihlaseni`), WebSearch
(`"remeslnik.online" recenze OR zkušenosti OR IČO`, `site:remeslnik.online`),
yt-dlp `ytsearch5:remeslnik.online` (0 relevantních výsledků).
