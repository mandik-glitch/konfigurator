# Řemeslo — sloučený přehled appek pro srovnávač (podklad pro DB)

Založeno bot10, 2026-08-18. Sloučení a deduplikace 3 průzkumů:
`REMESLO_PRUZKUM_WORKFLOW_APPS.md` (bot10, web-first), `REMESLO_PRUZKUM_
APPKY_GOOGLE_PLAY.md` (bot10, Google Play ověřená data),
`REMESLO_PRUZKUM_APP_STORE.md` (bot11, App Store ověřená data).

**Metoda deduplikace:** appka se počítá jako JEDNA, pokud se shoduje
vydavatel/publisher napříč zdroji (např. Jobber z Google Play i App
Store průzkumu = 1 appka se 2 sadami hodnocení). Jeden nejistý případ:
**Logeto** (Google Play, `cz.vykazprace`, vydavatel Systemart s.r.o.)
a **Logeto** z App Store průzkumu (bot11, stejný vydavatel Systemart
s.r.o.) - sloučeno jako STEJNÁ appka na základě shody vydavatele,
i když bot11 poznamenal nejistotu, jestli jde o stejný produkt jako
`vykazprace.cz`. Zbytek (`Výkaz práce` jako takový, `PROFIDAT`,
`Řemeslník PRO`, `EasyZakázky`) zůstal NEnalezen na žádném store
napříč všemi 3 průzkumy - potvrzeno nezávisle 2× (bot10 i bot11), což
zvyšuje jistotu, že jde skutečně o appky bez veřejného store záznamu
(pravděpodobně jen web), ne o chybu hledání.

Toto je **jen podklad dat, čeká na schválení** - žádný zápis do DB
zatím neproběhl.

---

## Navrhované DB schéma

```sql
CREATE TABLE remeslo_workflow_apps (
    id                     INT AUTO_INCREMENT PRIMARY KEY,
    name                   VARCHAR(255) NOT NULL,
    publisher              VARCHAR(255) NULL,
    category               VARCHAR(30) NOT NULL,   -- 'field_service' | 'construction_diary' | 'invoicing_only' | 'full_workflow_cz'
    play_store_package     VARCHAR(255) NULL UNIQUE,
    app_store_id           VARCHAR(50) NULL UNIQUE,
    rating_play            DECIMAL(3,2) NULL,
    rating_count_play      INT NULL,
    rating_appstore        DECIMAL(3,2) NULL,
    rating_count_appstore  INT NULL,
    price_note             TEXT NULL,               -- prosa, ruzne modely napric appkami
    target_audience_note   TEXT NULL,
    language_cs            TINYINT(1) NOT NULL DEFAULT 0,
    not_found_on_stores    TINYINT(1) NOT NULL DEFAULT 0,  -- appky jako PROFIDAT/Řemeslník PRO - zaznamenané, ale bez store zaznamu
    source_doc             VARCHAR(255) NULL,        -- ktery pruzkumny .md dokument je zdroj
    researched_at          DATE NOT NULL
);

CREATE TABLE remeslo_workflow_features (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    slug       VARCHAR(50) NOT NULL UNIQUE,
    name       VARCHAR(255) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0
);

-- M:N vazba appka<->funkce, stejny vzor jako remeslo_material_category_professions.
-- ZJEDNODUŠENÍ (vědomé, uvedeno ke schválení): existence řádku = funkce
-- POTVRZENA výzkumem. Chybějící řádek = "appka funkci nemá" NEBO
-- "nebylo ověřeno" - netříští se to na 3 stavy (má/nemá/neověřeno),
-- což by pro první verzi srovnávače bylo přeinženýrství dat, která
-- beztak vznikla z omezeného průzkumu popisků appky, ne z vlastního
-- vyzkoušení každé appky.
CREATE TABLE remeslo_workflow_app_features (
    app_id     INT NOT NULL,
    feature_id INT NOT NULL,
    PRIMARY KEY (app_id, feature_id),
    CONSTRAINT fk_rwaf_app FOREIGN KEY (app_id) REFERENCES remeslo_workflow_apps(id) ON DELETE CASCADE,
    CONSTRAINT fk_rwaf_feature FOREIGN KEY (feature_id) REFERENCES remeslo_workflow_features(id) ON DELETE CASCADE
);
```

## Navrhovaný seznam funkcí (14, sestaveno ze všech 3 průzkumů)

| slug | Funkce |
|---|---|
| `fakturace` | Fakturace |
| `zakazky` | Evidence zakázek/projektu (ne jen faktura) |
| `planovani` | Plánování/kalendář/dispatch |
| `foto` | Foto-dokumentace |
| `cas` | Sledování odpracovaného času |
| `gps` | GPS sledování / kniha jízd |
| `crm` | CRM / historie zákazníka |
| `platby` | Online platby v appce |
| `offline` | Offline režim |
| `cestina` | Čeština |
| `ucetnictvi` | Integrace účetnictví (QuickBooks/Xero/export) |
| `tym` | Tým / subdodavatelé (víc uživatelů) |
| `ziskovost` | Ziskovost/marže zakázky (job costing) |
| `sklad` | Materiál / sklad |

---

## Náhled matice appka × funkce (celá v příloze níž)

Ukázka prvních 6 appek (celá tabulka 28 appek × 14 funkcí je v sekci
"Kompletní matice" níže - moc široká pro krátký náhled):

| Appka | Fakt | Zak | Plán | Foto | Čas | GPS | CRM | Platby | Off | CZ | Účto | Tým | Zisk | Sklad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Jobber | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | | | ✓ | ✓ | | |
| Housecall Pro | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | | | ✓ | ✓ | | |
| Tradify | ✓ | ✓ | ✓ | ✓ | ✓ | | | | | | ✓ | ✓ | ✓ | |
| mHelpDesk | ✓ | ✓ | ✓ | | | | ✓ | | ✓ | | ✓ | | | ✓ |
| iDoklad | ✓ | | | | | | | | | ✓ | ✓ | | | |
| Logeto (Systemart) | | ✓ | ✓ | | ✓ | ✓ | | | | ✓ | ✓ | ✓ | | |

(✓ = funkce potvrzena průzkumem; prázdné = nepotvrzeno, NE nutně
"nemá" - viz poznámka ke zjednodušení schématu výš)

## Kompletní matice (28 appek × 14 funkcí)

### Mezinárodní field service (14 appek)

| Appka | Fakt | Zak | Plán | Foto | Čas | GPS | CRM | Platby | Off | CZ | Účto | Tým | Zisk | Sklad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Jobber | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | | | ✓ | ✓ | | |
| Housecall Pro | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | | | ✓ | ✓ | | |
| Tradify | ✓ | ✓ | ✓ | ✓ | ✓ | | | | | | ✓ | ✓ | ✓ | |
| Fergus | ✓ | ✓ | ✓ | | | | | | | | | | ✓ | ✓ |
| mHelpDesk | ✓ | ✓ | ✓ | | | | ✓ | | ✓ | | ✓ | | | ✓ |
| ServiceTitan Mobile | ✓ | ✓ | ✓ | ✓ | | | | ✓ | | | | | | |
| Contractor+ | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | | | | | | ✓ |
| CompanyCam | | | | ✓ | | ✓ | | | | | | ✓ | | |
| ServiceTrade | | ✓ | ✓ | ✓ | ✓ | | ✓ | | | | | | | |
| Fieldwire | | ✓ | ✓ | | | | | | | | | ✓ | | |
| ServiceM8 | ✓ | ✓ | | | ✓ | ✓ | ✓ | ✓ | | | ✓ | ✓ | | |
| Workiz | ✓ | ✓ | ✓ | | | | ✓ | ✓ | | | | ✓ | | |
| Joist | ✓ | ✓ | | ✓ | | | ✓ | ✓ | | | ✓ | | | |
| QuoteIQ | ✓ | ✓ | ✓ | | | | ✓ | ✓ | | | | | | |

### Stavební deník (3 appky, jiná kategorie)

| Appka | Fakt | Zak | Plán | Foto | Čas | GPS | CRM | Platby | Off | CZ | Účto | Tým | Zisk | Sklad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Buildo | | ✓ | | | | | | | | ✓ | | | | ✓ |
| Buildary.Online | | ✓ | | | | | | | | ✓ | | | | |
| SiteLogs | | ✓ | | | | | | | | | | | | |

### Čistě fakturační appky CZ/SK (8 appek)

| Appka | Fakt | Zak | Plán | Foto | Čas | GPS | CRM | Platby | Off | CZ | Účto | Tým | Zisk | Sklad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| iDoklad | ✓ | | | | | | | | | ✓ | ✓ | | | |
| SuperFaktura | ✓ | | | | | | | | | ✓ | | | | ✓ |
| BitFaktura | ✓ | | | ✓ | | | | | | ✓ | | ✓ | | |
| Doklado | ✓ | | | ✓ | | | | | | | ✓ | ✓ | | |
| Fintoro | ✓ | | | | | | | | | | ✓ | | | |
| Faktury.co | ✓ | | | | | | | | | ✓ | | | | |
| Faktura (Weiswise) | ✓ | | | | | | | | | | | | | |
| KROS Fakturácia | ✓ | | | | | | | | | | | | | |

### Plný workflow CZ (3 appky)

| Appka | Fakt | Zak | Plán | Foto | Čas | GPS | CRM | Platby | Off | CZ | Účto | Tým | Zisk | Sklad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Timoty | (✓) | ✓ | ✓ | | ✓ | | | | | ✓ | | ✓ | | ✓ |
| Logeto (Systemart) | | ✓ | ✓ | | ✓ | ✓ | | | | ✓ | ✓ | ✓ | | |
| DílnaTech | | ✓ | | | | | ✓ | | | ✓ | | ✓ | | ✓ |

---

## Appky BEZ store záznamu (potvrzeno nezávisle 2× - bot10 i bot11)

Tyhle appky se zapíšou do `remeslo_workflow_apps` s `not_found_on_stores=1`,
`play_store_package`/`app_store_id` NULL - existují (mají web), ale
nepodařilo se dohledat mobilní store listing:

- **PROFIDAT** - web tvrdí "Android appka", nedohledáno na Google Play ani App Store.
- **Řemeslník PRO** (elhacom.cz) - vlastní popis appky ji označuje jako "webovou aplikaci".
- **EasyZakázky** - nedohledáno na žádném store.
- **Kalendo.cz** - pravděpodobně jen webová appka (jen bot10 hledal).
- **Ř21** - jediný zdroj zmiňuje zrušenou EET (2023), možná zastaralá appka (jen bot10 hledal).

---

## Zdroje

`REMESLO_PRUZKUM_WORKFLOW_APPS.md`, `REMESLO_PRUZKUM_APPKY_GOOGLE_PLAY.md`,
`REMESLO_PRUZKUM_APP_STORE.md` - plné detaily/citace/URL u každé appky
tam, tenhle dokument je jen sloučený/deduplikovaný podklad pro DB.
