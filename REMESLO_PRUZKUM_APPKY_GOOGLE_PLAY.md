# Řemeslo — systematický průzkum appek na Google Play (podklad pro srovnávač)

Založeno bot10, 2026-08-18 na zadání Roberta (přes bot3): strategický
posun - Řemeslo NEBUDE stavět další appku pro řízení práce
řemeslníka do konkurence (trh je přehlcený, viz
`REMESLO_PRUZKUM_WORKFLOW_APPS.md`). Místo toho PRVNÍ služba bude
**srovnávač existujících appek** - meta-služba, co pomůže řemeslníkovi
zorientovat se v nabídce. Tenhle dokument je podklad dat pro ten
srovnávač.

**Metoda**: systematické hledání přes Google Play přímo (ne jen
odvozeně z webu appky) - u kandidátů nalezených přes web/marketing
stránky jsem ověřoval SKUTEČNÝ Play Store záznam (`play.google.com/
store/apps/details?id=...`), stahoval jeho HTML a četl vestavěná
strukturovaná data (JSON-LD `aggregateRating`, `name`, `description`,
`applicationCategory`) - žádné dohadování balíčkových ID, jen ověřené
zdroje z vyhledávání. **Zjištění o metodě**: stránka s `hl=cs`
parametrem u řady appek NEobsahuje strukturovaná data o hodnocení
(zobrazí se jen karusel "podobných appek" s JEJICH hodnocením, což by
při nepozorném čtení vedlo k mylnému přiřazení cizího hodnocení) -
spolehlivě fungovalo `hl=en_US&gl=US`. Kde se hodnocení nepodařilo
dohledat ani tak, uvedeno poctivě jako "nedostupné" (typicky appky s
málo recenzemi, Google Play pod určitým prahem hodnocení nezobrazuje).

Tohle je **jen research** - žádná implementace, čeká na schválení.

---

## Nalezené appky (18 s ověřenými daty přímo z Google Play)

### A. Mezinárodní field service / job management

| Appka | Package ID | Vydavatel | Hodnocení | Cena (appka zdarma ke stažení, jde o předplatné) | Cílovka |
|---|---|---|---|---|---|
| **Jobber: Field Service Software** | `com.getjobber.jobber` | Jobber Software | 4,44★ (6 632 recenzí) | od $25/měsíc (dle dřívějšího průzkumu) | malé firmy 1-15 vozidel |
| **Housecall Pro: Field Service** | `housecall.pros` | Codefied Inc. | 4,49★ (6 625) | $59-329/měsíc + povinné doplatky $40-149/měsíc | 5-50 techniků |
| **Tradify - Easy Job Management** | `com.tradifyhq.tradifyapp` | Tradify Limited | 4,37★ (3 080) | $48-62/měsíc | malé-střední řemeslné firmy (NZ/AU) |
| **Fergus Go** | `com.fergus.app` | Fergus Software Ltd. | nedostupné (málo recenzí) | podobný řád jako Tradify | o trochu větší firmy než Tradify |
| **mHelpDesk** | `com.mhelpdesk.endeavor` | mHelpDesk | **1,95★ (521)** ⚠ | $169-299/měsíc | 1-20 techniků |
| **ServiceTitan Mobile** | `com.servicetitan.mobile` | ServiceTitan Mobile | **2,39★ (1 022)** ⚠ | enterprise, cena na dotaz | střední-velké firmy |
| **Contractor+ Invoice & Estimate** | `contractorplus.app` | Contractor Plus, Inc. | 4,39★ (666) | freemium, AI odhady | handyman kontraktoři |
| **CompanyCam** | `com.agilx.companycam` | Company Cam | 4,69★ (7 603) | freemium | foto-dokumentace zakázky (NENÍ plný workflow - úzce zaměřená appka) |
| **ServiceTrade** | `com.servicenet.mobile` | ServiceTrade Inc | 4,11★ (270) | enterprise | komerční servisní kontraktoři (HVAC/mechanical/fire) |
| **Fieldwire - Construction App** | `net.fieldwire.app` | Fieldwire | 4,35★ (4 862) | freemium | stavební TÝMY (plány, punch listy) - větší projekty, ne solo řemeslník |

**Pozoruhodné zjištění - dvě appky s výrazně nízkým hodnocením
navzdory tisícům recenzí**: mHelpDesk (1,95★/521) a ServiceTitan
Mobile (2,39★/1022). Obě jsou etablované, placené produkty s
dlouhou historií (viz `REMESLO_PRUZKUM_WORKFLOW_APPS.md`), ale
mobilní appka samotná je zjevně slabým článkem - přesně typ
informace, kterou samotný marketing appky nikdy neřekne a kterou
srovnávač Řemesla může nabídnout jako přidanou hodnotu.

### B. Stavební deník (příbuzná, ale odlišná kategorie - zákonná
evidence na stavbě, ne obecná evidence zakázek řemeslníka)

| Appka | Package ID | Vydavatel | Hodnocení | Poznámka |
|---|---|---|---|---|
| **Buildo - Construction diary** | `net.spacive.buildo` | Team Buildo | 4,0★ (257) | CZ, denní záznamy + management stavby |
| **Buildary.Online** | `com.firstis.buildary` | First information systems | nedostupné | CZ, elektronický stavební deník |
| **SiteLogs: Construction Diary** | `com.construction.diary` | apptech_Infotech | nedostupné | nahrazuje papírové deníky |

### C. České fakturační/servisní appky

| Appka | Package ID | Vydavatel | Hodnocení | Poznámka |
|---|---|---|---|---|
| **Logeto** (CZ značka "Výkaz práce") | `cz.vykazprace` | Systemart s.r.o. | 4,25★ (352, CS verze) | docházka + práce + kniha jízd - přesah do "kniha jízd" jako `api/fleet.py` |
| **DílnaTech** | `cz.dilnatech` | ErokoTech, s.r.o. | nedostupné | servisní DÍLNA (kategorie Auto/vozidla - spíš autoservis než univerzální řemeslník) |
| **Faktury** (Faktury.co) | `co.faktury` | Kajetan Dudczak | nedostupné | čistě fakturace, ne evidence zakázek |
| **Faktura** (Weiswise) | `com.weiswise.faktura` | Weis & Wise A/S | nedostupné | čistě fakturace |
| **KROS Fakturácia** | `sk.kros.fakturacia.twa` | KROS a.s. | nedostupné | SK, čistě fakturace |

## Kandidáti NEnalezeni na Google Play (přiznáno poctivě, ne fabrikováno)

Tyhle appky/appky-kandidáti se objevily v research podkladech
(vlastní web, `REMESLO_PRUZKUM_WORKFLOW_APPS.md`), ale SYSTEMATICKÉ
hledání jejich Play Store záznamu nebylo úspěšné:

- **PROFIDAT** - marketingový web tvrdí "mobilní aplikace Android",
  ale konkrétní Play Store záznam se nepodařilo dohledat žádnou
  kombinací hledání. Buď má neintuitivní/neveřejně inzerovaný
  package ID, nebo appka zatím není publikovaná (jen v přípravě/
  testování) - nejisté, nedomýšleno.
- **Kalendo.cz** - web prezentuje appku, mobilní appka na Google Play
  nedohledána (možná jen webová appka bez nativní mobilní verze).
- **Ř21** - jediná dohledaná zmínka je ze staršího článku
  odkazujícího na povinnou EET (elektronická evidence tržeb) - EET
  byla v ČR **zrušena v roce 2023**, takže tenhle zdroj je
  pravděpodobně zastaralý a appka může být dnes nedostupná/
  neudržovaná. Nepotvrzeno ani vyvráceno - nutno ověřit, pokud bude
  relevantní.
- **Řemeslník PRO** (elhacom.cz) - vlastní popis appky ji označuje
  jako "webovou aplikaci", nativní appka na Google Play
  pravděpodobně neexistuje.
- **Timoty.cz, EasyZakázky** - z `REMESLO_PRUZKUM_WORKFLOW_APPS.md`,
  appka na Google Play nedohledána (pravděpodobně jen webové appky).

## Shrnutí čísel

**18 appek s ověřenými daty přímo z Google Play** (10 mezinárodních
field service, 3 stavební deník, 5 českých fakturačních/servisních).
**5 dalších kandidátů zaznamenáno jako nepotvrzené** (buď nemají
appku, nebo se nepodařilo dohledat záznam).

Datový bod, který se u VĚTŠINY appek nepodařilo zjistit ze samotného
Play Store záznamu: přesná cena/model předplatného (Play Store ukazuje
jen cenu STAŽENÍ appky, což je u freemium modelu vždy 0 Kč/zdarma -
skutečná cena je v appce/na webu vydavatele za přihlášením). U appek
zkoumaných už dřív (`REMESLO_PRUZKUM_WORKFLOW_APPS.md`) cenu mám,
u nově nalezených (Fergus, ServiceTrade, ContractorPlus, CompanyCam,
Fieldwire, všechny české) by bylo potřeba dohledat zvlášť - mimo
scope tohohle kola (čistě Google Play data), pokud bude potřeba pro
srovnávač samotný.

## Návrh struktury dat (čeká na schválení, neimplementováno)

Podobně jako `remeslo_competitor_platforms` z `REMESLO_PRUZKUM.md`:

```sql
CREATE TABLE remeslo_workflow_apps (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    publisher           VARCHAR(255) NULL,
    play_store_package  VARCHAR(255) NULL UNIQUE,   -- NULL = appka na Google Play nenalezena
    category            VARCHAR(30) NOT NULL,        -- 'field_service' | 'construction_diary' | 'invoicing_only'
    rating_value         DECIMAL(3,2) NULL,
    rating_count         INT NULL,
    price_note           TEXT NULL,                  -- prosa, ne strukturovane (ruzne modely napric appkami)
    features_note         TEXT NULL,
    target_audience_note  TEXT NULL,
    language_cs           TINYINT(1) NOT NULL DEFAULT 0,
    researched_at          DATE NOT NULL,
    source_url              VARCHAR(500) NULL
);
```

**Zůstává jen návrh** - dokud Robert/bot3 neschválí, data zůstávají v
tomhle Markdown dokumentu (stejný vzor jako `REMESLO_PRUZKUM.md`).

## Zdroje

Google Play záznamy (přímo staženo a čteno, `hl=en_US&gl=US`):
play.google.com/store/apps/details?id=com.getjobber.jobber,
housecall.pros, com.tradifyhq.tradifyapp, com.fergus.app,
com.mhelpdesk.endeavor, com.servicetitan.mobile, contractorplus.app,
com.agilx.companycam, com.servicenet.mobile, net.fieldwire.app,
net.spacive.buildo, com.firstis.buildary, com.construction.diary,
cz.vykazprace, cz.dilnatech, co.faktury, com.weiswise.faktura,
sk.kros.fakturacia.twa. Doplňkově WebSearch pro dohledání správných
package ID a kandidátů (Google Play `dev`/`developer` stránky
vydavatelů, marketingové weby appek).
