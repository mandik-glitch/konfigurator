# Řemeslo — průzkum appek pro řízení denní práce řemeslníka

Založeno bot10, 2026-08-18 na zadání Roberta (přes bot3): navazuje na
`REMESLO_PRUZKUM.md` (bot11, lead-gen/poptávkové platformy), ale řeší
**jinou kategorii** — appky na řízení DENNÍ PRÁCE řemeslníka (ne
získávání zákazníků): plánování zakázek, evidence zákazníků/historie,
fakturace, sledování času, foto-dokumentace zakázky, komunikace se
zákazníkem. Cíl: podklad pro `REMESLO_KONCEPT.md` moduly 2 (Evidence
zakázek) a 3 (Jednoduché CRM).

Stejná metoda jako u `REMESLO_PRUZKUM.md`: u každé appky konkrétní
workflow kroky + cenový model + nejsilnější funkce, ne obecný přehled.
Prioritně hledáno, jestli existuje česká obdoba (menší je OK).

Tohle je **jen průzkum** — nic neimplementováno, čeká na schválení.

---

## A. Velké mezinárodní appky (field service management)

| Appka | Odhad podílu/velikost trhu | Cílovka (velikost firmy) | Cena |
|---|---|---|---|
| **ServiceTitan** | ~31 % podíl mezi digitalizovanými HVAC firmami (USA) | Střední až velké firmy (desítky+ techniků) | Enterprise, cena na dotaz, nejdražší ze zkoumaných |
| **Housecall Pro** | ~16 % podíl | 5–50 techniků | $59–329/měsíc + povinné doplatky $40–149/měsíc (ceník bez add-onů je zavádějící) |
| **Jobber** | Nejrychleji rostoucí mezi malými firmami (1–15 vozidel) | 1–15 vozidel/živnostník+pár lidí | od $25/měsíc (roční platba) |
| **Tradify** | Menší, NZ/AU trh | Malé-střední řemeslné firmy | $48–62/měsíc |
| **Fergus** | Menší, NZ/AU trh | O trochu větší firmy než Tradify (opakované zakázky, více lidí) | Podobný řád jako Tradify |
| **mHelpDesk** | Menší, US trh | 1–20 techniků | $169–299/měsíc (nebo $55–95/uživatel/měsíc ročně) |

**Workflow kroky, které řeší (společný jmenovatel napříč všemi):**
poptávka/lead → **nabídka/odhad ceny** → (po schválení) **automatický
převod na zakázku** → **plánování/rozvrh** (drag-and-drop kalendář,
přiřazení technika) → **práce na místě** (mobilní appka, fotky před/
po, podpis zákazníka) → **fakturace** (často automatický převod
zakázky na fakturu, případně dílčí/milníkové faktury u větších
zakázek) → **platba online** → **historie zákazníka** (CRM - další
zakázky u stejného klienta, kontaktní údaje, poznámky).

**Nejsilnější/nejpoužívanější funkce podle appky (co odlišuje, ne
obecný seznam):**
- **Jobber**: nejjednodušší onboarding ("nastavíš za víkend bez IT
  znalostí") — nabídka se PO SCHVÁLENÍ zákazníkem automaticky
  přemění na zakázku, žádné ruční přepisování. Milníkové faktury
  (progress invoicing) u větších zakázek.
- **Housecall Pro**: "on my way" SMS/e-mail se fotkou technika před
  příjezdem (důvěryhodnostní/transparentní prvek pro zákazníka) +
  foto-dokumentace stavu PŘED/PO zásahu jako důkaz odvedené práce.
  GPS sledování vozidel (aktualizace po pár minutách, ne real-time).
- **ServiceTitan**: nejpokročilejší reporting/dashboardy — cílí na
  firmy, které už řídí víc techniků a potřebují datový přehled
  napříč firmou, ne jen jednotlivé zakázky.
- **Tradify/Fergus**: obě staví přímo pro řemeslné obory (elektrikáři,
  instalatéři, tesaři) — Fergus navíc silný v **job costing/material
  tracking** (sledování nákladů na materiál per zakázka → přímá
  souvislost s naším modulem 1, srovnávačem cen materiálu).
- **mHelpDesk**: nejdostupnější vstupní cena z mezinárodních appek,
  integrace QuickBooks/Google Calendar - cílí čistě na nejmenší firmy.

---

## B. České appky (prioritní zjištění)

Na rozdíl od lead-gen kategorie (`REMESLO_PRUZKUM.md`, kde je český
trh hodně obsazený), tahle kategorie má **méně známých, ale reálně
existujících** českých hráčů:

| Appka | Cena | Klíčová funkce/odlišnost |
|---|---|---|
| **PROFIDAT** (profidat.cz) | nedohledána konkrétní cena, zdarma vyzkoušení | JEDINÁ ze zkoumaných (česká i zahraniční) explicitně zdůrazňuje **ziskovost/marži zakázky** (výdělek v Kč/hodinu, měsíční statistiky výkonu firmy) — jde nad rámec prosté evidence, řeší "kolik na tom fakt vydělávám" |
| **Řemeslník PRO** (elhacom.cz) | 365 Kč/ROK (~1 Kč/den), 14 dní zkušebně | Nejlevnější ze všech zkoumaných appek (mezinárodní i české) o řád — zakázky+klienti+faktury+fotodokumentace v jednom, appka je prý na zakázku upravitelná vývojářem |
| **Timoty.cz** | od 440 Kč/měsíc | Cílí na "servisní firmy a pracovníky v terénu", výkaz práce/čas na zakázce + přehled služeb/produktů k fakturaci |
| **EasyZakázky** (easyzakazky.cz) | nedohledána | Jednoduchá správa zakázek/faktur/klientů, cílovka "malé firmy a živnostníci" — název i pozicionování nejblíž tomu, co plánujeme v modulu 2 |
| **Výkaz práce** (vykazprace.cz) | nedohledána | Kombinuje docházku + rozpis práce + KNIHU JÍZD + výdaje + zakázky + fakturaci v jedné appce — nejširší záběr ze zkoumaných českých appek (přesah i do "kniha jízd", což konfigurátor už MÁ vlastní implementaci, `api/fleet.py` — zajímavá shoda vzoru) |

**Klíčové zjištění o českém trhu:** existuje víc funkčních, aktivních
appek, než by se čekalo — žádná z nich ale nevypadá jako jasný tržní
lídr s velkým podílem (na rozdíl od Jobber/Housecall Pro/ServiceTitan
v US), spíš roztříštěný trh malých hráčů s podobnou nabídkou. Ceny
jsou řádově nižší než mezinárodní appky (365 Kč/rok až ~5 300 Kč/rok
u Timoty, oproti ~7 000–90 000+ Kč/rok u Jobber/Housecall Pro/
ServiceTitan) — čeští řemeslníci evidentně nejsou zvyklí/ochotní
platit mezinárodní ceny za tuhle kategorii nástrojů. **Přímo relevantní
pro cenování budoucí "evidence zakázek" v Řemeslu, pokud by se někdy
zpoplatňovalo** (mimo současný scope, Řemeslo je zatím zdarma - cíl
1. etapy).

---

## C. Detailní rozbor: PROFIDAT (na žádost Roberta, 2026-08-18)

Robert prošel appku sám (2 screenshoty demo dashboardu s reálnými
čísly), poslal doplňující zadání na hloubkový rozbor. Metoda:
`profidat.cz` je statický marketing web + samostatná Firebase/
Firestore SPA appka (`profidat.cz/app.html`) - její JS soubory
(`js/dashboard.js`, `js/zakazky.js`, `js/pdf.js`, `js/limits.js`...)
jsou veřejně stažitelné bez přihlášení (žádné obcházení autentizace,
jen čtení statických zdrojových souborů, které appka posílá
prohlížeči). Skutečná DATA firem (zakázky, ceny, tarify) jsou v
Firestore za přihlášením - nedostupná, ale VÝPOČETNÍ LOGIKA (vzorce,
prahy klasifikace) je v client-side JS kódu čitelná napřímo.

### 1. Kompletní seznam funkcí

- **Evidence zákazníků** - každý zákazník má "vlastní kartu"
  (kontaktní údaje, historie zakázek).
- **Evidence zakázek** - vlastní detail per zakázka (zákazník, popis,
  fotky, přílohy, PDF protokol).
- **"Work log" - průběžné záznamy práce** (klíčový prvek, který
  žádná appka z části A/B nemá takhle explicitně): BĚHEM práce na
  zakázce (ne až na konci) se přidávají dílčí záznamy s odpracovanými
  hodinami a náklady (`workLogHours`, `workLogCosts`) - dají se
  upravovat/mazat jednotlivě, systém je průběžně sčítá.
- **Dokončení zakázky** (`completeZakazka`) - zadá se finální cena
  (`finalPrice`) + případné DODATEČNÉ náklady/hodiny nad rámec
  work-logu, systém spočítá finální zisk/marži/Kč-hod a zapíše (přes
  Firebase Cloud Function na serveru, klient jen zobrazuje živý
  náhled stejným vzorcem - viz bod 4).
- **Foto-dokumentace + přílohy** u každé zakázky (mobilní appka -
  "vyfotíš závadu, průběh nebo hotový výsledek").
- **2 typy PDF protokolu** (viz bod 5) + **historie PDF exportů**
  (seznam dřívějších generování, ne jen poslední).
- **Finanční dashboard** (viz screenshoty od Roberta) - banner "Stav
  firmy" (celkový zisk za období, průměrná marže, počet zakázek "k
  prověření"), 4 KPI karty, graf výkonu, žebříček nejvýnosnějších
  zakázek s tagem rizika/kvality (viz bod 3), přepínání
  měsíc/všechna období (`dashboardPeriod`).
- **Textový "insight" řádek** - appka generuje VĚTU shrnující stav
  ("V období … je celkový zisk X Kč, průměrná marže Y %. Z zakázek
  potřebuje prověřit.") - jednoduchý template, ne AI, ale efektivní
  UX prvek.
- **Web + mobilní appka** (Android teď, iOS "později"), jedno
  společné přihlášení.
- **Cloud storage/zálohy** (Firebase/Google Cloud, HTTPS přenos,
  automatické zálohy databáze i souborů, fotky NEJSOU veřejné trvalé
  odkazy - řízený přístup appkou).
- **Plánované rozšíření ekosystému** (zatím NEexistuje, jen
  ohlášeno): PROFIDAT Dokumenty (GDPR/BOZP šablony bez registrace),
  ToolPouch (servisní protokoly, QR kódy/štítky pro techniky),
  PROFIDAT Agent (AI marketingové texty/reference generované z fotek
  hotové zakázky).

### 2. Cenový model - NEDOHLEDATELNÝ zvenčí, transparentně přiznáno

Marketingový web (`profidat.cz`, `evidence-zakazek.php`) **neobsahuje
žádnou cenu** - jen "Vyzkoušet zdarma". Appka sama (`js/limits.js`)
potvrzuje, že existují tarify (`"basic"` je defaultní/fallback klíč),
ale konkrétní limity a ceny NEJSOU v kódu - načítají se za běhu z
privátního Firestore dokumentu (`config/plans`), který appka čte, až
když je uživatel přihlášený. **Nejde to zjistit bez přihlášení do
appky** - žádné fabrikování čísel, tarify BASIC/STANDARD, které
Robert viděl na screenshotech, jsou reálné, ale jejich přesnou cenu/
limity zná jen ten, kdo appku má otevřenou (Robert), ne tenhle
zvenčí prováděný rozbor.

### 3. Přesná definice "riziková vs výborná zakázka" (nalezeno v kódu)

`js/dashboard.js`, funkce `getDashboardFinanceStatus(job)` - přesné
prahy (na `job.profit`, `job.marginPercent`, `job.profitPerHour`):

| Podmínka | Stav | Popisek v UI |
|---|---|---|
| zakázka nedokončená nebo `profit` není číslo | `empty` | "Bez finančních údajů" |
| `profit < 0` | `loss` | "Ztrátová zakázka" |
| marže `< 5 %` | `danger` | "Riziková zakázka" |
| marže `< 15 %` | `warning` | "Slabší marže" |
| marže `>= 30 %` A ZÁROVEŇ `profitPerHour > 0` | `great` | "Výborná zakázka" |
| jinak (marže 15-30 %) | `healthy` | "Zdravá zakázka" |

Navíc samostatný "risk reason" text (`getDashboardRiskReason`) -
i mimo výše uvedené stavy platí: pokud je `profitPerHour > 0` ale
`< 300 Kč/hod` u dokončené zakázky → "Nízký zisk za hodinu" (i když
marže sama o sobě není v pásmu riziko/varování - odděleně sleduje
"vydělává na hodinu", ne jen marži z ceny).

### 4. Přesný vzorec výpočtu Kč/hod a marže (nalezeno v kódu)

`js/zakazky.js`, funkce `updateCompletePreview()` (živý náhled při
dokončování zakázky, stejná logika jako finální server-side výpočet):

```
totalCosts = baseCosts (souhrn z work-logu) + extraCosts (zadané při dokončení)
totalHours = baseHours (souhrn z work-logu) + extraHours (zadané při dokončení)
profit      = finalPrice - totalCosts
margin (%)  = finalPrice > 0 ? (profit / finalPrice) * 100 : 0
hourly      = totalHours > 0 ? profit / totalHours : 0
```

Tedy: **marže se počítá z CENY zakázky** (ne z nákladů - `profit/
finalPrice`, ne `profit/costs`), **Kč/hod se počítá ze VŠECH
odpracovaných hodin dohromady** (průběžné z work-logu + dodatečné při
dokončení), náklady zahrnují cokoliv, co uživatel zadá jako "costs"
(appka nerozlišuje materiál/dopravu/jiné - jedno číslo "náklady").

### 5. PDF protokol - 2 typy, obsah generován server-side

`js/pdf.js` rozlišuje:
- **Průběžný protokol** - jde vytvořit KDYKOLIV, i před dokončením
  zakázky (dokumentační účel v průběhu práce).
- **Závěrečný protokol** - tlačítko aktivní až po `completedAt`
  (dokončení) - logicky finální/předávací výstup.
- Historie PDF exportů se ukládá a zobrazuje (ne jen poslední
  vygenerovaný soubor).
- Samotný LAYOUT/obsah PDF se generuje server-side (Cloud Function) -
  z veřejného klientského kódu není vidět, co přesně PDF obsahuje
  (žádné šablony v `js/pdf.js`, jen volání API + správa historie/
  stavu tlačítek). Podle marketingové kopie ("Výstup ze zakázky bez
  přepisování") jde pravděpodobně o zákaznicky-orientovaný dokument
  (popis práce, fotky, případně cena) - přesná struktura nejistá.

### 6. Další zjištění

- PROFIDAT je malý/indie projekt (kontakt `kontakt.profidat@gmail.com`,
  vlastní text "vzniká z reálných pracovních problémů, ne z
  katalogové prezentace") - ne etablovaná firma jako zahraniční appky
  z části A. Relevantní pro důvěryhodnost/stabilitu zdroje inspirace,
  ne pro kvalitu nápadu samotného.
- Technologie: Flutter (mobil) + Firebase/Firestore/Cloud Functions
  (backend) - stejná kombinace jako `api/remeslo.py`'s "Vývoj
  aplikací" produkt PROFIDATu nabízí jako SLUŽBU jiným (mimoděk
  zajímavé - PROFIDAT dělá i placenou technickou pomoc s Flutter/
  Firebase projekty, "audit a opravy po AI/vibecodingu").

---

## Syntéza — co by mělo obsahovat "Evidence zakázek" (modul 2)

Současný návrh v `REMESLO_KONCEPT.md` (`remeslo_jobs`: customer_name,
description, status, start_date, due_date, price_czk, note) je
**funkční minimální základ**, ale průzkum ukazuje 3 konkrétní mezery
oproti tomu, co má PRAKTICKY KAŽDÁ zkoumaná appka (mezinárodní i
česká) a co řemeslníci evidentně reálně používají:

1. **Foto-dokumentace zakázky** (před/po) — Housecall Pro i Řemeslník
   PRO ji mají jako jednu z hlavních funkcí, ne doplněk. U nás by šlo
   o přímé znovupoužití vzoru `api/gallery_items.py` (obecný
   "připojitelný" fotogalerie modul, `owner_type='remeslo_job'`
   analogicky k existujícím `'category'|'product'|'document'`) — ŽÁDNÁ
   nová tabulka, jen nová hodnota `owner_type`. Nejlevnější/
   nejrychlejší rozšíření z celého seznamu níž.
2. **Sledování odpracovaného času na zakázce** — Timoty.cz i Výkaz
   práce to mají jako klíčovou funkci (ne PROFIDAT/Řemeslník PRO,
   které ne). Užitečné pro řemeslníka, co fakturuje hodinovku, ale
   NENÍ univerzální (řemeslník fakturující paušálem/položkově to
   nepotřebuje) — kandidát na VOLITELNÉ pole, ne povinnou součást.
3. **Odkaz na fakturu/doklad** — všechny zkoumané appky spojují
   zakázku→fakturu (u Jobber dokonce automaticky). `remeslo_jobs`
   dnes má jen `status='fakturovano'` (booleovský příznak), ne odkaz
   na samotný doklad. Vzhledem k tomu, že Řemeslo cílí na INTERNÍ
   databázi (GDPR, viz koncept) a NENÍ účetní/fakturační systém
   konfigurátoru — navrhuju u tohohle NEROZŠIŘOVAT teď (mimo scope,
   riziko duplicity s `api/documents.py`), jen zaznamenat jako
   otevřenou otázku pro budoucí fázi, pokud řemeslník dostane vlastní
   přístup (zmíněno v konceptu jako "mimo rozsah tohohle konceptu").

**Update 2026-08-18 (bot10):** body 1-2 výš jsou od té doby
IMPLEMENTOVÁNY (`remeslo_jobs.hours_worked` volitelný sloupec,
foto-dokumentace přes `api/gallery_items.py` s `owner_type=
'remeslo_job'`) - viz `REMESLO_KONCEPT.md` modul 2, hotovo a živě
otestováno. Bod 3 zůstává otevřenou otázkou beze změny.

4. **[NOVĚ, po detailním rozboru PROFIDAT — část C výš] Finanční
   dashboard (náklady → zisk → marže → Kč/hod → klasifikace
   zakázky)** — tohle je PŘESNĚ to, co PROFIDAT dělá jinak než
   všechny ostatní appky v tomhle průzkumu, a co `remeslo_jobs` dnes
   vůbec neumí (má jen `price_czk`, žádné `costs`). Konkrétní návrh
   rozšíření (čeká na schválení, mimo scope už hotového modulu 2):
   - Nový sloupec `remeslo_jobs.costs_czk DECIMAL(10,2) NULL`
     (náklady na zakázku - materiál apod., jedno číslo jako u
     PROFIDATu, ne rozpad po kategoriích).
   - Odvozené hodnoty (`profit`, `margin_percent`, `profit_per_hour`)
     POČÍTAT ZA BĚHU v SQL dotazu (ne ukládat jako sloupce) - jde o
     čistou funkci `price_czk`/`costs_czk`/`hours_worked`, žádný
     důvod duplikovat stav; PROFIDAT je ukládá jen kvůli
     Cloud-Function architektuře (jinde by přepočet byl drahý), tady
     stačí `SELECT ..., (price_czk - costs_czk) AS profit, ...`.
   - Klasifikace (Ztrátová/Riziková/Slabší marže/Zdravá/Výborná) —
     PŘEVZÍT přesné prahy z PROFIDATu jako výchozí hodnotu (marže
     <0/<5/<15/<30/≥30 %, Kč/hod <300 pro "nízký výdělek" varování) -
     reálně otestovaný/používaný práh, ne vymyšlené číslo, ale
     označit jako snadno upravitelné (jiné obory mohou mít jiné
     realistické marže).
   - Minimální dashboard sekce v `remeslo.html` (souhrn zisk/marže za
     období, žebříček nejvýnosnějších zakázek) - PROFIDATův
     "insight" text (jedna generovaná věta shrnující stav) je
     levný a efektivní UX nápad, vhodný ke zkopírování.
   - PDF protokol (2 typy jako PROFIDAT) — MIMO SCOPE teď, ale
     poznamenáno: konfigurátor už MÁ PDF pipeline (`reportlab`,
     `api/documents.py`) - žádná nová závislost, jen nová šablona,
     až přijde na řadu.

**Co naopak NEpřebírat** (i když to konkurence má): GPS sledování
vozidel (Housecall Pro) a pokročilý reporting (ServiceTitan) — obojí
cílí na firmy s víc zaměstnanci/vozidly, ne na jednotlivého
řemeslníka/malou partu, což je náš cílový segment (stejný jako
Jobber/Tradify/Řemeslník PRO, ne ServiceTitan/Housecall Pro).

## Syntéza — Jednoduché CRM (modul 3)

Návrh v konceptu (`crm_leads.craftsman_id` sloupec navíc, žádná nová
tabulka) přesně odpovídá tomu, jak fungují ČESKÉ appky v tomhle
průzkumu (PROFIDAT/Řemeslník PRO/EasyZakázky všechny spojují
klienta↔zakázky↔fakturu v jednom jednoduchém modelu, ne odděleným
"CRM produktem") — potvrzuje, že "nejmenší možný zásah" není jen
programátorská zkratka, ale odpovídá tomu, jak tenhle typ appky
reálně funguje i u konkurence. Žádná změna návrhu, jen potvrzení.

---

## Zdroje

Mezinárodní appky: housecallpro.com/compare, servicetitan.com/
comparison, getjobber.com/academy, softwareadvice.com,
fieldservicesoftware.io, contractorplus.app, selecthub.com,
memberjungle.com, fergus.com, itqlick.com. České appky: profidat.cz,
elhacom.cz, timoty.cz, easyzakazky.cz, vykazprace.cz — ověřeno přímo
na vlastních webech, kde dostupné.
