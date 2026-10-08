# Audit systému — konkrétní doporučená zlepšení

Založeno bot11, 2026-08-18 na zadání Roberta (přes bot3): projít celý
systém konfigurátoru (`api/*.py`, `webapp/*.html` mimo `scene.html`,
DB schéma) a navrhnout konkrétní, akceschopná zlepšení — výkon,
bezpečnost, UX, chybějící validace, zastaralý/mrtvý kód.

**Rozsah a metoda**: rozděleno na 10 paralelních forků podle modulů
(`app.py` jádro, orders/cart/quotes, products/gallery, customers/crm/
fleet, purchase_orders/support, documents/emails/drive, menší moduly +
DB schéma, `admin.html`, `nabidka-online.html`/`product.html`, zbylé
frontend stránky). **`webapp/scene.html` a vše kolem 3D scény/renderu/
cuttingu/FBX (bot8's teritorium) vědomě NEDOTČENO** — vyloučeno ze
zadání.

**Tohle je ČISTĚ ANALÝZA — nic z toho není opraveno.** Čeká na
schválení bot3/Robertem, souběžně na opravách pracuje jiný bot.

---

## Jak číst tenhle dokument

Nálezy jsou seřazené podle **kategorie**, uvnitř podle **závažnosti**
(vysoká → nízká). U každého: přesné umístění (`soubor:řádek`), co je
problém, a proč na tom záleží. Doporučené pořadí řešení je na konci
dokumentu.

---

## 1. Bezpečnost — VYSOKÁ závažnost

### 1.1 `api/app.py:44-48` — hardcoded DB heslo jako fallback
`DB_PASSWORD = os.environ.get("DB_PASSWORD", "<staré heslo, rotováno>")`
(a podobně HOST/USER/NAME) — skutečné produkční heslo bylo natvrdo v
kódu, trvale v git historii. Pokud env proměnná chyběla, appka se tiše
připojila produkčním heslem bez varování. (Doslovná hodnota tady
odstraněna 2026-09-03, bot14, na žádost bot3 - heslo je od té doby
rotováno, viz `daef6da`; historie samotná se z opatrnosti nepřepisuje,
viz `[[git-history-live-credential-2026-09-03]]`.)

### 1.2 `api/app.py:193` — nebezpečný fallback `FLASK_SECRET_KEY`
`"dev-only-insecure-key-change-me"` jako fallback. Pokud env
proměnná chybí v produkci, session cookies se podepisují VEŘEJNĚ
ZNÁMÝM klíčem → útočník si může padělat libovolnou session (včetně
`role=admin`). Fallback je aspoň zjevně označený jako nebezpečný.

### 1.3 `api/app.py:670-696` (`/api/auth/login`) — žádné rate-limiting
Neomezený počet pokusů o heslo na libovolný e-mail. V kombinaci s
veřejnou registrací bez ověření e-mailu snadno umožňuje brute-force
zjišťování platných hesel.

### 1.4 `api/gallery_items.py:307-313` (`gallery_items_import_url`) — SSRF + čtení lokálních souborů
`urllib.request.urlopen(safe_url)` nemá allowlist schématu. Python's
`urllib` má ve výchozím stavu zaregistrovaný `FileHandler` →
`url: "file:///opt/konfigurator/api/.env"` se STÁHNE a ULOŽÍ jako
gallery item, který je následně **veřejně stažitelný**. Dostupné
běžné roli s právem "upravit" na cílové sekci, ne jen adminovi.
**Nejzávažnější jednotlivý nález celého auditu.**

### 1.5 `api/support.py:168-244` (`support_customer_send`) — neomezené AI/e-mail náklady od anonymního uživatele
Endpoint bez rate-limitu/CAPTCHA spustí synchronně reálné volání
Anthropic API + vždy odešle SMTP notifikaci Robertovi. Kdokoli bez
přihlášení může skriptem generovat neomezené API náklady a zahltit
schránku.

### 1.6 `api/import_customers_xml.py:35-38` — hardcoded DB přihlašovací údaje
Na rozdíl od sesterského `import_logiman_gallery.py` (načítá `.env`)
má tenhle skript DB_HOST/USER/PASSWORD/NAME přímo v kódu, trvale v
git historii.

### 1.7 `api/cart.py:343` (`cart_add_item`) — reálný bug, ne bezpečnost, ale kritický dopad
`clean_cuts` je definována jen uvnitř `if cut_pieces_raw is not
None:`. Pro běžný produkt (nejčastější případ) zůstává nedefinovaná
→ přidání STEJNÉHO produktu do košíku podruhé spadne na
`NameError` → 500. **Zasahuje nejběžnější e-shop akci** — doporučeno
opravit přednostně před ostatními nálezy.

### 1.8 `webapp/product.html:1895` — neescapovaný popis produktu
`pdDesc.innerHTML = p.description || ...` bez `escapeHtml()`, zatímco
zbytek souboru ho důsledně používá. `description` může pocházet z
dodavatelských importů (Dogus a další feedy) — stored-XSS vektor.

### 1.9 `webapp/admin.html` (`buildCatBlock`, ř. 9654-9659, 9700-9703) — neescapovaný název kategorie
`${cat.name}` do `innerHTML` bez `escapeHtmlAdmin()` — 2 konkrétní
výjimky z jinak důsledně dodržovaného vzoru (234 správně
escapovaných míst v souboru). Stored-XSS mezi adminy.

## 2. Bezpečnost — STŘEDNÍ závažnost

- **`api/app.py:1377-1416`** (`/api/catalog-thumbnail`) — chybí
  `@require_permission`, jen `@login_required`. Kterýkoli zaregistrovaný
  zákazník může přepsat náhledový obrázek libovolného produktu.
- **`api/gallery.py:301-309`** — stejný SSRF/`file://` problém jako
  1.4, admin-only (nižší závažnost), řešit společně.
- **`api/gallery.py`/`gallery_items.py`** — upload obrázků kontroluje
  jen příponu z klientského filename, ne skutečný obsah (magic
  bytes)/velikost — libovolný binární obsah pod `.jpg` příponou.
- **`api/documents.py`** (PDF endpointy) — `Content-Disposition:
  inline` bez ověření, nekonzistentní s vlastním bezpečnostním vzorem
  projektu (`drive.py`/`quotes.py` mají "attachment vždy + magic-bytes
  kontrola u inline" jako explicitní pojistku proti stored XSS).
- **`api/documents.py:191-199`** (`_next_part_number`) — chybí
  `FOR UPDATE`, na rozdíl od sesterské `_next_document_number()` o pár
  řádků výš. Souběžné kliky mohou vygenerovat DUPLICITNÍ číslo VDD.
- **`api/inquiries.py:150-156`** — veřejný neautentizovaný formulář
  přijímá přílohu bez kontroly typu (jen velikost 15 MB), `content_type`
  je nedůvěryhodná klientská hlavička.
- **`webapp/register.html`** — heslo bez `minlength`/kontroly síly,
  na rozdíl od `reset-password.html` (má `minlength="8"`).

## 3. Bezpečnost — NÍZKÁ závažnost

- `api/app.py:202` — `SESSION_COOKIE_SECURE=False` (zdokumentovaný
  known-gap, ne nový nález).
- `api/fleet.py:481` — GPS auth token jako GET query parametr, riziko
  úniku přes access logy (vynuceno protokolem OsmAnd/Traccar).
- `api/support_email_sync.py:92-93` — IMAP heslo = SMTP heslo,
  zvyšuje dopad úniku jednoho hesla na oba kanály.
- `api/incoming_documents.py` — přílohy z libovolného e-mailu bez
  antivirového skenu před schválením/stažením adminem.
- `api/documents.py:1282-1294` — neescapované XML entity v ReportLab
  `Paragraph()` markupu, může spadnout na parse chybě s určitým
  vstupem (`&`, `<` v adrese/jménu).
- `api/incoming_documents.py:213-263` — race condition mezi kontrolním
  SELECT a UPDATE při schvalování, dvojklik/2 admini = dvojí zpracování.
- `api/emails.py:318-321` — chybějící `None` kontrola po
  `_fetch_order`, neošetřený 500 při smazané objednávce.
- `webapp/category.html:1359-1362` — `image_url` v `src="${...}"` bez
  escapování (dnes pravděpodobně neexploitovatelné, nekonzistentní vzor).
- `api/products.py:830-843` — SKU uniqueness check-then-insert race.

## 4. Výkon

| Závažnost | Umístění | Problém | Dopad |
|---|---|---|---|
| Vysoká | `api/support.py:242` | AI odpověď generovaná SYNCHRONNĚ v request handleru (`_maybe_generate_ai_reply`) | zákazník čeká na celé Anthropic API volání, výpadek AI = zaseknutý chat |
| Střední | `api/products.py:204-205` | Korelovaný subquery na obrázek PER ŘÁDEK v `shop_products_list()` | lineární škálování na celém katalogu (1000+ produktů) bez stránkování |
| Střední | `api/cart.py:171` | `_effective_unit_price()` volá dotaz na slevovou skupinu zákazníka PRO KAŽDOU položku košíku | 10 položek = 10× stejný redundantní dotaz |
| Střední | `api/support_ai.py:51-120` | Celý katalog + 140KB+ dokument posílán jako system prompt při KAŽDÉM AI volání, žádné prompt caching | zbytečně vysoké API náklady a latence |
| Střední | `api/support_email_sync.py:337` | IMAP `UID search ALL` každé 2 min místo rozsahového dotazu | rostoucí zátěž IMAP serveru s velikostí schránky |
| Střední | `api/approvals.py:52` | DB zápis/sync při KAŽDÉM pollu `GET /api/admin/approvals`, ne jen při skutečné změně | zbytečná zátěž při otevřených admin tabech |
| Střední | `api/crm.py:534-553` | Hromadná změna stavu leadů = N samostatných transakcí místo 1 dávkového UPDATE | znatelné zpomalení při výběru desítek+ leadů |
| Střední | `webapp/admin.html` | 950 KB / 18 389 řádků v jednom souboru, žádné code-splitting | pomalejší první načtení adminu bez ohledu na použitou sekci |
| Nízká | `api/app.py:436-562` | `current_user()` + `has_permission()` = 2 DB dotazy na každý chráněný request, šlo by sloučit JOINem | malý, ale na každém requestu |
| Nízká | `webapp/category.html:2063,2066` | Vyhledávání volá API při KAŽDÉM stisku klávesy, žádný debounce | zbytečná zátěž serveru při rychlém psaní |

## 5. Chybějící validace

| Závažnost | Umístění | Problém |
|---|---|---|
| Střední | `api/products.py:851-950` | Žádná server-side kontrola rozsahu u cen/skladu/slevy (záporná cena, sleva >100 %) |
| Střední | `api/purchase_orders.py:970-977` | Příjem zboží navyšuje sklad smazaného produktu tiše (rowcount nekontrolován) |
| Střední | `api/customers.py:523-529` / `api/crm.py:210-232` | Duplicitní e-mail/lead — check-then-insert race, ne atomické |
| Nízká-střední | `api/customers.py:179-180` | IČO/DIČ bez kontroly formátu |
| Nízká | `api/crm.py:1052-1058` | Pravidlo klasifikace odesílatele bez kontroly, že vypadá jako e-mail/doména |
| Nízká | `api/gallery_items.py:387-391` | Reorder smyčka nekontroluje `rowcount` u neplatných ID |

## 6. GDPR / auditovatelnost

- **`api/customers.py:668-759`** — tvrdé smazání zákazníka nechává PII
  snapshot v `shop_orders.billing_*`. Pokud je motivace částečně GDPR,
  osobní údaje ve skutečnosti dál existují v historii objednávek —
  stojí za vědomé rozhodnutí (anonymizovat billing_* při smazání, nebo
  explicitně zdokumentovat záměr ponechat historii).
- **`api/customers.py:664`, `api/crm.py:530`** — `log_audit` ukládá
  syrové tělo requestu, ne skutečný diff (co se změnilo z čeho na co)
  — ztěžuje zpětnou rekonstrukci u citlivých dat.

## 7. Zastaralý / mrtvý kód

- **`api/documents.py:850-852`** — `SELECT` jehož výsledek se nikde
  nepoužívá, zbytečný DB round-trip při každém volání.
- **`api/import_logiman_gallery.py`** — jednorázový import skript
  (2026-07-25), kandidát na smazání, pokud se import nebude opakovat.
- **`webapp/admin.html`** — 3 samostatné, prakticky identické
  escapovací funkce (`escapeHtmlFleet`, `escapeHtmlAdmin`,
  `escapeInternalChat`) — riziko, že nová sekce omylem použije
  žádnou/špatnou variantu (přesně takhle vznikl nález 1.9).
- **`webapp/admin.html`** — 71 nezávislých `load*()` funkcí, žádná
  sdílená generická list/detail komponenta. Funguje to, ale každá nová
  sekce = ruční kopie stejné CRUD logiky — architektonická příčina
  nálezu 1.9, ne jen kosmetika.

## 8. Co je v pořádku (ověřeno, ne nález)

Pro úplnost — tyhle věci prošly kontrolou a jsou v pořádku, ať se
příští audit nezdržuje jejich opakovaným ověřováním:
- `api/orders.py`/`api/cart.py`/`api/quotes.py` — žádné IDOR, dynamické
  `UPDATE {table}` vzory staví jméno tabulky/sloupců výhradně z
  pevných whitelistů, ne z uživatelského vstupu (bezpečné).
- `api/app.py` bulk-update/delete vzory — stejně bezpečné, ne SQL
  injection riziko, i když to na první pohled tak vypadá.
- `drive.py`/`quotes.py` — promyšlený bezpečnostní vzor (attachment
  vždy, magic-bytes kontrola u inline PDF, náhodný stored filename) —
  vzor, který by měl `documents.py` (nález ve 2. sekci) následovat.
- `login.html`/`register.html`/`reset-password.html` — správně
  nastavené `autocomplete="username"/"current-password"/"new-password"`.
- `capture.html` — nepoužívá `<input type="file">`, fotí přímo přes
  `getUserMedia()`, takže riziko libovolného uploadu z disku se netýká.
- `api/remeslo.py` — `@admin_required` misto plné RBAC je vědomý
  interim stav (zdokumentováno), ne opomenutí.

---

## Doporučené pořadí řešení

**Ihned (dopad na běžný provoz, ne jen bezpečnost):**
1. `api/cart.py:343` — NameError bug, kazí nejběžnější e-shop akci
   (přidání druhého kusu produktu do košíku). Triviální oprava.

**Vysoká priorita (bezpečnost s reálným dopadem):**
2. `api/gallery_items.py`/`gallery.py` — SSRF/`file://` (nálezy 1.4 + 2.
   druhý bod) — allowlist `http`/`https` schématu.
3. `api/app.py:193` — `FLASK_SECRET_KEY` fallback — ověřit, že env
   proměnná je v produkci VŽDY nastavená (fail-fast, ne tichý fallback).
4. `api/app.py:44-48` + `api/import_customers_xml.py:35-38` —
   hardcoded DB credentials — přesunout do `.env`, zvážit rotaci hesla
   (bylo v gitu).
5. `webapp/product.html:1895` + `webapp/admin.html` (`buildCatBlock`)
   — 2 konkrétní XSS mezery — doplnit `escapeHtml()`/`escapeHtmlAdmin()`.
6. `api/support.py:168-244` — rate-limit na veřejném support endpointu
   (finanční expozice přes AI náklady).
7. `api/app.py:670-696` — rate-limit/lockout na loginu.

**Střední priorita (výkon a robustnost):**
8. `api/support.py:242` — přesunout AI generování na pozadí (async).
9. `api/documents.py:191-199` — `FOR UPDATE` u `_next_part_number`.
10. Zbytek výkonových nálezů (sekce 4) — postupně, žádný není urgentní.

**Nízká priorita / architektonické (delší dech):**
11. `webapp/admin.html` — sjednotit 3 escapovací funkce do jedné,
    zvážit sdílenou list/detail komponentu místo 71 kopií — snižuje
    riziko budoucích XSS mezer stejného typu jako nález 1.9.
12. GDPR/audit-diff nálezy (sekce 6) — vyžadují Robertovo rozhodnutí
    o záměru (anonymizace vs. ponechání historie), ne čistě technická
    volba.

---

## Zdroje / metoda ověření

Nálezy pocházejí z 10 paralelních analytických forků (bot11,
2026-08-18), každý čtoucí konkrétní podmnožinu souborů přímo (Read
tool, u `admin.html` kombinace `grep` + cílené čtení kvůli velikosti).
Žádný nález není z pouhého vzoru/heuristiky bez ověření konkrétního
řádku kódu. Rozsah auditu explicitně VYNECHÁVÁ `webapp/scene.html` a
vše kolem 3D scény/renderu/cuttingu/FBX (`blender_render*.py`,
`cutting*.py`, `dimension_match_fbx.py`, `step_convert*.py`,
`obj_to_fbx_blender.py`, `fbx_convert.py`, `leg_fbx_import.py`,
`hdri.py`, `scene_offers.py`) — to je mimo zadání (bot8's teritorium).
