# Řemeslo — průzkum konkurenčních/inspirativních platforem

Založeno bot11, 2026-08-17 na zadání Roberta (přes bot3): průzkum
existujících aplikací na podporu řemeslníkům — české i zahraniční —
jako podklad před stavbou podprojektu **Řemeslo** (viz
`REMESLO_KONCEPT.md`, zatím jen plán, nic neimplementováno).

**Účel a metoda (Robertovo upřesnění, 2026-08-17):** Cílem NENÍ jen
katalogizovat trh. U každé platformy je zaznamenaná konkrétní
**služba + hodnota, kterou to řemeslníkovi přináší** (ne obecná fráze
typu "má poptávkový systém"), a z toho je na konci odvozený **konkrétní
seznam doporučených služeb pro Řemeslo, seřazený podle priority**.
To je hlavní výstup dokumentu, ne přehled trhu sám o sobě.

Tohle je **jen průzkum/analýza** — nic z něj není naprogramováno.
Čeká na schválení bot3/Robertem (standing proces: bot analyzuje a
navrhne, bot3 schvaluje před dalším krokem), teprve pak přechod k
implementaci podle `REMESLO_KONCEPT.md`.

---

## Přehled nalezených platforem podle kategorie

### A. České/slovenské poptávkové portály

| Platforma | Model | Konkrétní hodnota pro řemeslníka |
|---|---|---|
| **NejŘemeslníci.cz** | Kredit vázaný na hodnotu zakázky (~1,5 % z ceny), max. 4 konkurenti/poptávka | Platí prakticky jen za reálnou šanci na zakázku, ne za "výstřel do tmy"; startovní kredit zdarma (bezriziková zkouška) |
| **Poptávej.cz** | Kredit 60 Kč/ks nebo Premium bez limitu | Transparentní strop nákladů předem, 100 000+ registrovaných řemeslníků |
| **ePoptávka.cz** | Nízký roční paušál, bez provize z realizace | Nejnižší administrativní tření, nejvyšší dosah (275 000+ dodavatelů, 11 000+ poptávek/měsíc) |
| **Remsygo.cz** | Bez provizí, prémiový tier "BOOST" | Jediná platforma se školním/učňovským přesahem (nábor budoucí pracovní síly) |
| **SeznamRemeslniku.cz** | — | Vynucuje **doklad** (faktura/předávací protokol) jako důkaz reference — silnější důvěryhodnostní signál než nepodložené hvězdičky |
| **Firmyzarohem.cz** | — | 130 000+ firem v databázi (detaily modelu nedohledány) |
| **Lokálni remeselníci** (SK) | — | Obdobný ověřovací adresářový model pro Slovensko |

*Pozn.: přesně pojmenované "Prozeman" a "ČeskéŘemeslo" nebyly
dohledány jako aktivní platformy — funkčně stejný prostor pokrývají
platformy výše.*

**Klíčové zjištění o českém trhu:** všechny nalezené platformy jsou
**lead-generation tržiště** (zákazník zadá poptávku → řemeslníci platí
za kontakt). **Žádná nedělá AI foto-analýzu ani srovnávač cen
materiálu napříč dodavateli.** Fáze 2 a 3 z `REMESLO_KONCEPT.md`
nejsou "dohnat konkurenci" — jsou skutečná bílá plocha na trhu. Řemeslo
tak není přímý konkurent těmhle portálům (jiná kategorie produktu —
nástroje šetřící čas vs. získávání zákazníků), spíš doplňková pozice.

### B. Velké mezinárodní lead-gen platformy

| Platforma | Trh | Model | Konkrétní hodnota pro řemeslníka |
|---|---|---|---|
| **Thumbtack** | USA | Pay-per-lead, aukčně ($8–150) | Real-time notifikace — 78 % zákazníků vybere prvního, kdo odpoví |
| **TaskRabbit** | USA/mezinár. | Provize 15–35 % + vstupní $25 | Kompletní tok nabídka→domluva→platba v jedné appce, materiál proplacen 100 % bez provize |
| **Airtasker** | Austrálie/UK | Tiered provize 12,5–20 %, u opakovaného zákazníka klesá na 1,9 % | Zadání pro zákazníka zdarma (víc poptávek), vestavěné pojištění škody/úrazu |
| **Angi/HomeAdvisor** | USA | Hybrid: roční paušál (~$288–300) **+** pay-per-lead ($15–120+) | Verified review systém zvyšuje konverzi — ALE nejhůř hodnocená ze všech zkoumaných (Trustpilot 2,1/5, BBB rating F, FTC žaloba 2023) |

**Silná shoda napříč zdroji — anti-patterny, kterým se vyhnout:**
1. Prodej **jednoho leadu více konkurentům bez limitu** — hlavní zdroj
   frustrace řemeslníků na všech zkoumaných platformách.
2. **Netransparentní/aukční cena** za lead, která roste s poptávkou.
3. **Auto-renewal smlouvy** + refundace za špatný lead jen jako
   "kredit", ne reálné peníze (přímý zdroj Angi's FTC žaloby).
4. **Kombinace paušál + pay-per-lead zároveň** (Angi) — vnímáno jako
   nejdražší/nejhorší model ze všech čtyř zkoumaných.

### C. "Ověřené"/prémiové platformy a provozní SaaS nástroje

| Platforma | Trh | Klíčová diferenciace | Konkrétní hodnota pro řemeslníka |
|---|---|---|---|
| **MyBuilder** | UK | Pay-per-shortlist (£2–35) | Platí jen když ho zákazník SÁM vybere ze seznamu — ale jen vstupní vetting, žádná průběžná kontrola (BBC odhalila falešné profily) |
| **Checkatrade** | UK | Až 12 kontrol na řemeslníka (doklady, finance, reference, trestní rejstřík) + **průběžná revalidace** | Značka "Checkatrade" nese důvěryhodnost za řemeslníka — členské plány £0–399+/měsíc podle viditelnosti |
| **Houzz Pro** | USA/mezinár. | NENÍ lead-gen — je to CRM/SaaS pro řemeslníka | Plánování zakázek, fakturace+platby+QuickBooks, marketing, AI insighty, od $49/měsíc — jiná kategorie: provozní nástroje, ne adresář |
| **Bark.com** | UK/mezinár. | Kreditový systém ($2,20/kredit) | "Horké" live leady ihned — ale 1 lead sdílený s až 5 řemeslníky, nízká konverze vůči ceně (varovný příklad) |

**Nejsilnější přenositelný prvek: Checkatrade model ověřování.**
`REMESLO_KONCEPT.md` fáze 1 zatím řeší jen `status` pole
(candidate→active) — ŽÁDNÝ systém průběžného ověřování kvality/
reference. To je přesně to, co u konkurence dělá rozdíl mezi levnou a
důvěryhodnou platformou, a přímo souvisí s otevřenou otázkou "veřejná
vs. interní databáze" v konceptu.

### D. Nástroje na srovnávání cen materiálu (fáze 3 vize)

Nenalezeno nic, co by dělalo přesně to, co plánuje fáze 3 (živý
scraping N dodavatelů + geografická vzdálenost) pro JEDNOTLIVÉ
řemeslníky:

- **BuildZoom** — cenové odhady jsou jen orientační interní kalkulačka
  (typ projektu), NE agregace reálných cen dodavatelů.
- **Field Materials AI** — nejblíž konceptu, ale klíčový rozdíl:
  ceny NEscrapuje z webů, ale **čte z nabídek/faktur/příjemek**, které
  firma sama nahraje (AI čtení dokumentů). Cílovka: větší stavební
  firmy, ne jednotlivý řemeslník.
- **Joist** — pošle materiálový seznam ručně max. 3 dodavatelům,
  dotaz na vyžádání, ne živá databáze.
- **Contractor+** — srovnává ceny jen u velkých řetězců se
  strukturovaným e-shopem/API (Lowe's, Home Depot) — nefunguje u
  malých lokálních stavebnin, o které by u řemeslníků šlo hlavně.

**Proč to nikdo nedělá dobře (potvrzuje riziko z `REMESLO_KONCEPT.md`
fáze 3):** dodavatelé jsou finančně motivovaní NEbýt cenově
transparentní (ceny se liší podle vyjednávací síly konkrétního
zákazníka), ceny jsou volatilní — obecný scraper pro libovolného
dodavatele je proto strukturálně křehký a drahý na údržbu, ne jen
"hodně práce navíc".

---

## Doporučené služby pro Řemeslo (podle priority)

Odvozeno z průzkumu výše — konkrétní, akceschopná doporučení, ne
obecný přehled trhu.

### 1. [VYSOKÁ PRIORITA] Doplnit fázi 1 o strukturovaný ověřovací mechanismus

`REMESLO_KONCEPT.md` má zatím jen `remeslo_craftsmen.status`
(candidate/contacted/.../active). Checkatrade ukazuje, že **průběžné**
ověřování (ne jednorázový vstupní check) je hlavní důvěryhodnostní
diferenciace na trhu. SeznamRemeslniku.cz navíc ukazuje konkrétní,
levný mechanismus: vyžadovat doklad (faktura/předávací protokol) jako
důkaz reference, ne nepodložené hvězdičky.

**Konkrétní návrh:** rozšířit fázi 1 o `remeslo_verification_checks`
(doklady o oprávnění k řemeslu, reference s nahraným dokladem,
kontrola vůči insolvenčnímu rejstříku — veřejně dostupné API/výpis),
s `checked_at`/`valid_until`, aby šlo vynutit **revalidaci**, ne jen
jednorázové schválení. Přímo řeší otevřenou otázku "veřejná vs.
interní databáze" — ověřovací vrstva dělá veřejnou variantu bezpečnější
a důvěryhodnější.

### 2. [VYSOKÁ PRIORITA] Fáze 2 (foto-analýzy) — potvrzeno jako bílá plocha, stavět jak plánováno

Žádná zkoumaná platforma (ČR ani zahraničí) foto-AI analýzu
(počítání předmětů, čtení výkresů/textu) nenabízí. `REMESLO_KONCEPT.md`
plán fáze 2 zůstává beze změny — jen připomínka existujícího blokátoru
(neplatný `ANTHROPIC_API_KEY`), který je třeba vyřešit dřív, než se
k fázi dojde, ne až v jejím průběhu.

**Doplněk k plánu:** rozšířit `analysis_type` o čtvrtou hodnotu
(`ctenifaktury_nabidky`) — přímo navazuje na doporučení č. 3 níž.

### 3. [STŘEDNÍ PRIORITA] Přehodnotit fázi 3 — crowdsourcing z faktur místo scrapingu

`REMESLO_KONCEPT.md` sám označuje scraping N dodavatelů za
nejrizikovější část konceptu. Průzkum to potvrzuje (žádná zkoumaná
platforma to nedělá spolehlivě) a nabízí konkrétní alternativu
inspirovanou Field Materials AI: **místo scrapingu cizích webů nechat
řemeslníky samotné nahrávat faktury/nabídky, které dostávají od
dodavatelů** (přes AI-vision infrastrukturu z fáze 2 — stejný
mechanismus, jiné `analysis_type`). Systém extrahuje
dodavatele/materiál/cenu/datum a agreguje do sdílené databáze.

**Proč je to lepší než plán v konceptu:**
- Nulové riziko rozbití při redesignu cizího webu (žádný scraper).
- Řeší geografii ZDARMA — faktura je doklad o reálném nákupu v
  konkrétním regionu, žádné geokódování navíc potřeba.
- Network efekt: čím víc řemeslníků přispívá, tím užitečnější databáze
  pro všechny — přímo motivuje používání fáze 2 (foto-analýzy).
- Nevylučuje pilotní scraping 2–3 vybraných dodavatelů jako DOPLNĚK
  (souhlas s "pilotním" přístupem z konceptu zůstává v platnosti),
  jen to přestává být JEDINÝ zdroj dat.

### 4. [STŘEDNÍ PRIORITA] Pokud se v budoucnu přidá poptávkový systém — konkrétní mantinely

`REMESLO_KONCEPT.md` fáze 1 zatím poptávkový/lead systém neplánuje
(jen adresář). Pokud by se v budoucnu přidal (přirozené rozšíření
databáze řemeslníků), průzkum dává jasné mantinely, které NEkopírovat:
- Nikdy neprodávat jeden kontakt neomezenému počtu řemeslníků
  (max. 4, jako NejŘemeslníci, nebo pay-per-shortlist jako MyBuilder).
- Transparentní/predikovatelná cena předem, ne aukční model rostoucí
  s poptávkou (Thumbtack).
- Žádné auto-renewal smlouvy, reálná refundace (peníze, ne "kredit")
  za prokazatelně špatný kontakt.
- Zvážit klesající poplatek pro opakované zákazníky (Airtasker tiered
  fee) jako retenční mechanismus, pokud dojde na transakční poplatky.

### 5. [NÍZKÁ PRIORITA / mimo současný scope] Provozní nástroje jako budoucí fáze 5

Houzz Pro ukazuje, že "provozní nástroje pro řemeslníka" (CRM,
plánování, fakturace) jsou samostatná, životaschopná kategorie —
odlišná od adresáře/lead-gen, přesně v duchu vize Řemesla ("co
řemeslníkovi ušetří čas"). TaskRabbit navíc ukazuje konkrétní žádanou
funkci: jeden tok nabídka→platba→fakturace bez ručního dohánění.
Nejde o žádnou ze 4 plánovaných fází — zaznamenáno jako **možná
budoucí fáze 5**, ne k okamžité stavbě.

### 6. [NÍZKÁ PRIORITA] Inspirace pro fázi 4 (akvizice) — školní/učňovský přesah

Remsygo.cz je jediná zkoumaná platforma s náborovým/vzdělávacím
přesahem (propojuje řemeslníky se školami/studenty na praxi) —
originální, nikde jinde nenalezený nápad. Vhodné jako dlouhodobá
akviziční myšlenka pro fázi 4 (budování vztahu s budoucí generací
řemeslníků), ne jako okamžitá stavba — fáze 4 je i podle konceptu
primárně průběžná analytická práce, ne systém k naprogramování.

---

## Navrhované DB schéma (JEN NÁVRH — čeká na schválení, neimplementováno)

Podobně jako u Toscanaccia (`supplier_leads` tabulka +
`toscanaccio_vyrobci_pruzkum.md` jako orientační doprovodný dokument)
by dávalo smysl mít i tenhle průzkum zpracovatelný strukturovaně,
zvlášť pokud bude potřeba dál sledovat vývoj konkurence v čase (nové
platformy, změny cenových modelů):

```sql
CREATE TABLE remeslo_competitor_platforms (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    country             VARCHAR(100) NULL,
    website             VARCHAR(255) NULL,
    category            VARCHAR(30) NOT NULL,   -- 'lead_gen' | 'verified_directory' | 'saas_tools' | 'price_comparison'
    business_model      TEXT NULL,               -- jak platforma vydelava
    key_services_note   TEXT NULL,               -- konkretni sluzby + hodnota pro remeslnika (prosa, ne strukturovane)
    verification_note   TEXT NULL,               -- jak (pokud vubec) overuji kvalitu/reference
    strengths_note      TEXT NULL,
    weaknesses_note      TEXT NULL,
    relevance_to_remeslo VARCHAR(20) NULL,        -- 'primy_vzor' | 'anti_vzor' | 'informativni'
    researched_at        DATE NOT NULL,
    source_urls           TEXT NULL
);
```

**Zůstává jen návrh** — dokud Robert/bot3 neschválí, data zůstávají v
tomhle Markdown dokumentu (stejně jako u Toscanaccia před založením
`supplier_leads`).

---

## Zdroje

Plný seznam citovaných URL je u jednotlivých dílčích průzkumů
(archivováno v transcriptu session bot11, 2026-08-17) — hlavní zdroje
u mezinárodních platforem (Thumbtack/TaskRabbit/Airtasker/Angi):
housecallpro.com, procured.us, ideausher.com, taskrabbit.com/blog,
airtasker.com, leadtruffle.co, en.wikipedia.org/wiki/Angi,
consumeraffairs.com. České platformy ověřeny přímo na vlastních webech
(nejremeslnici.cz, poptavej.cz, epoptavka.cz, remsygo.cz,
seznamremeslniku.cz).
