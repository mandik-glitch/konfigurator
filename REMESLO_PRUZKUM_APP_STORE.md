# Řemeslo — průzkum appek pro řemeslníky na Apple App Store

Založeno bot11, 2026-08-18 na zadání Roberta (přes bot3): navazuje na
`REMESLO_PRUZKUM.md` (lead-gen platformy) a `REMESLO_PRUZKUM_WORKFLOW_APPS.md`
(bot10, web-first průzkum appek pro řízení denní práce), ale řeší
konkrétně **App-Store-first úhel pohledu** — co si řemeslník reálně
najde a nainstaluje na iPhone, s hodnocením/recenzemi/cenou přímo
z App Store listingu.

**Strategický posun (Robert, přes bot3, 2026-08-18):** appek pro
řemeslníky je na trhu mnohem víc, než se původně čekalo — nemá smysl
stavět vlastní appku do konkurence hned teď. Místo toho PRVNÍ služba
Řemesla bude **srovnávač existujících appek** — meta-služba, co
pomůže řemeslníkovi zorientovat se v nabídce a vybrat si, ne další
appka do stejné konkurence. Tenhle dokument je přímý podklad pro
obsah srovnávače (data o appkách, ne návrh srovnávače samotného).

Appky už detailně rozebrané v `REMESLO_PRUZKUM_WORKFLOW_APPS.md`
(PROFIDAT, Řemeslník PRO, EasyZakázky, Výkaz práce/vykazprace.cz,
ServiceTitan, Fergus, Housecall Pro, Jobber, Tradify, mHelpDesk) se
tu NEOPAKUJÍ celé — jen doplněno App-Store-specifické info (je appka
vůbec na App Store? hodnocení? přesná cena z listingu?), pokud
chybělo.

Tohle je **jen průzkum** — nic neimplementováno, čeká na schválení.

---

## A. České a slovenské appky

| Appka | Vydavatel | Hodnocení | Cena | Klíčové funkce | Cílovka | Čeština |
|---|---|---|---|---|---|---|
| **iDoklad** | Seyfor, a.s. (Brno) | 4,8★ (3 300 recenzí) | Freemium — Basic 329 Kč, Favorites 579 Kč, Premium 949 Kč (jednorázově/balíček) | Fakturace do minuty, přehled podnikání, správa všech typů dokladů, automatizace upomínek/pravidelných faktur, notifikace o platbě, sync mobil↔PC | Podnikatelé a malé firmy (300 tis. uživatelů) | **Ano** |
| **SuperFaktura** | SuperFaktura, s.r.o. (Bratislava) | 4,8★ (158 recenzí) | Freemium — Basic 199–239 Kč/měs., Standard 479 Kč/měs., Premium 699–769 Kč/měs. | Faktury/zálohové/pravidelné faktury, cenové nabídky, objednávky, dodací listy, náklady, dobropisy, cashflow přehledy, QR skenování | Živnostníci a malé firmy | Ano (popis appky v AJ, ale cílí na CZ/SK legislativu) |
| **BitFaktura** | BitFaktura s.r.o. (Zlín) | 4,8★ (24 recenzí) | Freemium, 30 dní zdarma — Start 99 Kč, Standard 179 Kč, Pro 249 Kč, Pro Plus 399 Kč | Fakturace <30 s, e-mail přímo z appky, "turbofaktury", foto nákladových dokladů, statistiky tržeb, vícejazyčné faktury s ČNB kurzem, víc účtů | Živnostníci, začínající podnikatelé, malé firmy | **Ano** (1 z 12 jazyků) |
| **Doklado** | SmartLab s.r.o. | Nedostatek recenzí pro zobrazení | Zdarma + předplatné PLUS | Sken účtenek/faktur za 3 s, fakturace z mobilu, párování s bankovními pohyby, hromadná úhrada, víc firem v 1 účtu | Malí/střední podnikatelé, účetní, živnostníci (SK/CZ trh) | **Ne** (jen AJ, přestože cílí na SK/CZ) |
| **Faktúry online — Fintoro** | Fintoro s.r.o. (Trenčín, SK) | 5,0★ (15 recenzí) | Freemium — free do 15 faktur, Mini 6,49 €, Standard 13,49 €, Pro (cena neuvedena) | Rychlá fakturace, sledování zaplaceno/nezaplaceno, export PDF, auto-párování bankovních plateb, filtrování/hledání | Živnostníci, freelanceři, malé firmy | **Ne** (jen slovenština) |
| **Timoty** | Timoty s.r.o. (Praha) — viz i web-verze v `REMESLO_PRUZKUM_WORKFLOW_APPS.md` | 4,3★ (10 recenzí) | Zdarma ke stažení, appka samotná bez in-app nákupů (ceny řešeny přes web timoty.cz) | Správa/přiřazování úkolů, sledování postupu v reálném čase, docházka, inventarizace materiálu, týmová komunikace | Manažeři terénních operací, stavební firmy, servisní firmy | **Ano** |
| **Logeto** (Systemart s.r.o.) | Systemart s.r.o. (ČR) | 4,0★ (47 recenzí) | Zdarma pro jednotlivce, placeně pro firmy dle rozsahu | Evidence pracovní doby/docházky, správa projektů/zakázek, auto-zápis jízd vozidel, plánování pracovníků, výpočet mezd, export PDF/Excel | Malé firmy, podnikatelé, OSVČ, jednotlivci | **Ano** — pozn.: nejde jistě o stejný produkt jako `vykazprace.cz` z `REMESLO_PRUZKUM_WORKFLOW_APPS.md` (jiný vydavatel), spíš samostatný konkurenční nález ve stejné kategorii |

**Nedohledáno na App Store** (buď jen web appka / jen Android /
nenalezeno): **PROFIDAT** (potvrzuje zjištění z
`REMESLO_PRUZKUM_WORKFLOW_APPS.md` — "Android teď, iOS později"),
**Řemeslník PRO** (elhacom.cz — popsáno jako webová appka, žádný
App Store listing nenalezen), **EasyZakázky**, **Výkaz práce**
(vykazprace.cz jako takový, na rozdíl od výše zmíněného Logeta).

**Mimo scope** (nalezeno při hledání, ale jiná kategorie): **Dobrý
Řemeslník** (PEPIAPP s.r.o.) — adresář/vyhledávač řemeslníků pro
ZÁKAZNÍKY, ne nástroj PRO řemeslníka; **Mileage Tracker by
Driversnote** — čistě kniha jízd bez vazby na zakázky, tangenciální.

---

## B. Mezinárodní appky (field service management) — bez české lokalizace

Všechny appky v téhle sekci navazují na appky už zmapované v
`REMESLO_PRUZKUM_WORKFLOW_APPS.md` části A — tady jen App Store
hodnocení/cena/jazyky, které tam chyběly.

| Appka | Vydavatel | Hodnocení | Cena (z App Store) | Klíčové funkce | Cílovka | Čeština |
|---|---|---|---|---|---|---|
| **Jobber** | Jobber (Octopusapp Inc) | 4,8★ (20 000 recenzí) | Freemium — Lite $29,99/měs., Core $69,99, Connect $139,99–199,99, Grow $199,99–399,99 | Nabídky/odhady, chytré plánování+dispatch s GPS trasováním, fakturace+platby (QuickBooks), komunikace s klientem, timesheets | HVAC, úklid, zahradníci, elektrikáři, instalatéři, hendymani — sólo i týmy | Ne (jen AJ) |
| **Housecall Pro** | Codefied Inc. | 4,6★ (29 000+ recenzí) | Freemium, od $59/měs. (více tarifů $39,99–169) | Plánování+dispatch (drag-and-drop), komunikace se zákazníkem, online booking, nabídky/faktury, platby, GPS, QuickBooks, marketing | Domácí služby (HVAC, instalatéři, elektrikáři) — malé až středně velké rodinné firmy | Ne (AJ, ES) |
| **Tradify** | Tradify Limited | 4,8★ (175 recenzí) | Zdarma (ceník mimo appku) | Sledování zakázek/plánování, nabídky/fakturace, timesheets, subdodavatelé, foto/video k zakázce, job costing, QuickBooks/Xero | Řemeslníci 1–20 lidí (elektrikáři, instalatéři, stavaři, HVAC, malíři) | Ne (AJ, FR) |
| **ServiceM8** | Eroldawn Pty Ltd | 4,6★ (809 recenzí) | Freemium — Lite $8,99, Starter $28,99, Growing $78,99, Premium $149,99/měs. | Digitální job karty, GPS poloha týmu, komunikace, nabídky/faktury, timesheets, Tap to Pay, vlastní formuláře, Xero/QuickBooks | Sólo řemeslníci až 20 zaměstnanců (instalatéři, elektrikáři, HVAC, zámečníci, úklid) | Ne (jen AJ) |
| **Workiz** | Send A Job Inc | 4,6★ (2 100+ recenzí) | Zdarma + prémiové tarify (přesná cena mimo appku) | Plánování zakázek, fakturace+platby, týmová komunikace, mobilní správa v terénu, booking, nabídky | Terénní služby, malé-střední firmy (110 000+ uživatelů) | Ne (AJ, ES) |
| **mHelpDesk** | mHelpdesk, LLC | 3,5★ (197 recenzí) — nejhůř hodnocená appka ze zkoumaných | Zdarma (ceník mimo appku) | Offline/online sync, plánování, nabídky/faktury, správa zákazníků/leadů, e-mail/SMS automatizace, sklad, QuickBooks | HVAC, elektrikáři, instalatéři, hendymani, pokrývači | Ne (9 jazyků vč. polštiny/italštiny, ČEŠTINA CHYBÍ) |
| **Joist** | Joist Software Inc. | Nedostatek recenzí | Freemium — Basics €8,99/měs., Pro €13,49, Elite €30,99, Run €99,99/měs. | Odhady/faktury, platby (karta/PayPal), správa klientů, foto, podpis, branding, export do účetnictví | Generální dodavatelé, hendymani, elektrikáři, instalatéři, tesaři a další řemesla | Ne (jen AJ) |
| **QuoteIQ** | QuoteIQ LLC | 4,7★ (3 300 recenzí) | Freemium, od $29,99/měs. (14denní trial) | CRM, nabídky/faktury+platby, drag-and-drop plánování, self-service quoting/booking pro zákazníka, AI Estimator, měření nemovitosti na dálku, website builder | Tlakové mytí, HVAC, instalatéři, elektrikáři, zahradnictví, střechy, úklid, hubení škůdců, stavebnictví | Ne (jen AJ) |

---

## Syntéza — co z App Store dat říká o stavbě srovnávače

1. **Žádná mezinárodní appka (8 z 8 zkoumaných) nemá češtinu** — to
   je tvrdý, okamžitě viditelný rozlišovací filtr pro srovnávač
   (přesně jako u YouTube kanálů/rádia — jazyk je bariéra vstupu, ne
   detail). České appky tuhle mezeru evidentně zaplňují, ale žádná
   z nich (kromě iDokladu, 3 300 recenzí) nemá srovnatelný počet
   recenzí/tržní ověření jako mezinárodní hráči — **signalizuje
   mezeru důvěryhodnosti**, kterou by srovnávač mohl řešit (agregace
   "co o appce reálně říkají recenze", ne jen marketing appky).
2. **Trh je jasně rozdělený na 2 kategorie appek**, ne kontinuum:
   (a) **čistě fakturační appky** (iDoklad, SuperFaktura, BitFaktura,
   Doklado, Fintoro — silné v dokladech, slabé/chybí v evidenci
   zakázky-jako-projektu) vs. (b) **appky pro řízení zakázky od A do
   Z** (Timoty, Logeto, PROFIDAT, mezinárodní field-service appky —
   plánování, foto, tým, a teprve pak fakturace jako poslední krok).
   Tenhle rozdíl by měl být PRVNÍ otázka srovnávače ("chceš jen
   fakturovat, nebo řídit celou zakázku?"), ne skrytý v seznamu
   funkcí — řemeslník neznalý kategorie appek si to sám neodvodí.
3. **Hodnocení/počet recenzí jsou přímo z App Store srovnatelná
   napříč appkami** (na rozdíl od webových marketingových textů,
   které si každá appka píše sama) — tohle je konkrétní, objektivní
   datový sloupec, který web-first průzkum (`REMESLO_PRUZKUM_
   WORKFLOW_APPS.md`) neměl a srovnávač by ho měl ukazovat jako
   primární důvěryhodnostní signál vedle ceny.

---

## Zdroje

App Store listingy appek uvedených v tabulkách výš (apps.apple.com,
CZ/SK/US regiony), WebSearch pro dohledání App Store ID jednotlivých
appek. Křížové odkazy na `REMESLO_PRUZKUM_WORKFLOW_APPS.md` (bot10)
a `REMESLO_PRUZKUM.md` (bot11) pro appky/kontext popsané tam
detailněji.
