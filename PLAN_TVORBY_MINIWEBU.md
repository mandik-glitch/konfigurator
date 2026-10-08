# Plán tvorby mini-webů/shopů (domény, jazyky, prolinkování)

Navazuje na `PLAN_TVORBY_SESTAV.md` (Robert, 2026-09-17: "navazuje na plán
tvorby sestav") — tam končí výrobní linka schválenou kartou/rendery, tady
začíná otázka "na jaké doméně/URL to žije a jak se to propojí napříč
značkami/jazyky". Píše/udržuje bot3 (koordinace), stejná disciplína jako
`PLAN_TVORBY_SESTAV.md` — zapisovat stručně výsledek/rozhodnutí, ne průběh
debaty (detail debaty je v `AGENTS_LOG.md`/chatu 2026-09-17, pokud je
někdy potřeba).

## Rozhodnutá architektura (Robert, 2026-09-17)

- **Žádné subdomény podle značky** (`fiat.logiman.cz` zamítnuto). Značka a
  model/velikost = **podadresář** pod hlavní doménou:
  `logiman.cz/<značka>/<model>/<velikost>` (např. `/fiat/ducato/l2h2`).
  Důvod: subdoména se chová jako částečně samostatná jednotka (autorita
  hlavní domény se nepřenáší plně), podadresář autoritu sčítá do jedné
  domény — u nás s nulovou startovní autoritou je to zásadní rozdíl.
- **Jazyk/stát = podadresář** (`/it/...`), **NEBO celá jiná doména**, pokud
  tak Robert rozhodne per stát — obě varianty se propojují přes hreflang
  (funguje i mezi různými doménami, nemusí být stejná doména).
- **Hreflang (návrh bot7, 2026-09-17):** `x-default` → čeština (domácí
  trh, existující autorita). Sebe-odkaz povinný, reciprocita TVRDÁ
  (jednostranný pár Google celý cluster ignoruje) — musí jít z JEDNOHO
  zdroje pravdy (párovací klíč/tabulka), ne ze dvou nezávisle
  udržovaných polí. Vykreslovat JEN když oba páry reálně existují a jsou
  publikované — žádný odkaz na neexistující/404 URL. Cestový prefix se
  překládá taky (`/kategorie/`→`/categoria/`), ne jen slug. Jazykový
  přepínač = jméno jazyka (ne vlajka), vždy na ekvivalentní přeloženou
  stránku nebo zmizí, nikdy na 404.
- **Základ: čeština**, `autovestavby.logiman.cz` (do budoucího cutoveru na
  `logiman.cz` — až nastane, podadresáře se stěhují bezbolestně).
- **2. jazyk/stát: italština → doména `vandrawee.it`** (Robertovo
  rozhodnutí, ne `logiman.cz/it/`). Traktovat jako **italskou větev TÉŽE
  sítě** (hreflang, vzájemné prolinky), ne jako nezávislou značku/entitu.
  **Design/vizuál `vandrawee.it` = STEJNÝ jako Logiman** (HUD, barvy,
  styl, branding) — liší se jen doménové jméno, ne vzhled ani síťová
  identita.
- ⚠️ **`vandrawee.it` NENÍ součástí týhle "mini-web" architektury a NENÍ**
  **to samostatný plán** (Robert, 2026-09-17: "už to nemůžeme nazývat
  miniweby, ani plán, prostě jen překlopíme autovestavby.logiman.cz
  webovou část na vandrawee.it italsky"). Je to prosté 1:1 překlopení
  celého zákaznicky viditelného webu na novou doménu/jazyk/měnu/branding
  (STEJNÝ backend/DB, STEJNÝ vizuál jako Logiman) — technicky velký
  úkol, ale koncepčně žádná nová architektura na rozhodování, jen
  provedení. Sledovat jako běžný úkol v `TASKS.md`, ne rozšiřovat tenhle
  dokument o něj. Klíčové technické body (ať se neztratí): STEJNÝ backend
  jako `autovestavby.logiman.cz`, ne `car_storefronts` vzor; NE oživení
  starého `/opt/vandrawee` Unity systému; EUR/IVA je změna cenové logiky,
  ne jen zobrazení; staff nástroje (`scene.html`) zůstávají staff-only i
  tam. Bot16 fázuje: nejdřív routing/schema skeleton na 1-2 kategoriích,
  pak škálovat překlad na celý katalog (bot7).

## Dnešní Fiat síť (`.top` domény) — co se s ní děje

- **Zůstává BEZE ZMĚNY** jako uzavřená kapitola — žádná migrace,
  žádná přestavba domén ani struktury.
- **Jediná výjimka:** hub (`fiat-autovestavby.top`) dostane **2 prolinky**
  na hlavní web (`autovestavby.logiman.cz`). Je to vědomá, ÚZCE VYMEZENÁ
  výjimka z `TEXT_FILTR.md` pravidel 4–5 ("na Fiat doménách žádná zmínka
  Logimanu") — platí JEN pro hub, zbylých 6 modelových domén
  (`ducato.fiat-autovestavby.top`, `fiat-ducato-vestavby.top`, atd.)
  beze změny, tam pravidlo platí dál beze změny.
- Nové/budoucí značky (ne Fiat) se řídí NOVÝM modelem výše (podadresáře
  pod konsolidovanou doménou), neopakuje se anonymní-satelitní vzor.

## Zjištěné mezery ve schématu — řešit najednou, ne postupně (bot16)

1. `car_storefronts`/`car_storefront_models` nemá sloupec jazyk/locale
   ani měnu — dnes hardcoded čeština v šablonách (`lang="cs"`) a "Kč"/
   "bez DPH" natvrdo ve 2 místech `api/car_storefronts.py` (~ř. 750, 952).
2. Vztah "hub vs. standalone doména stejné značky" dnes žije jen ve tvaru
   URL (subdoména vs. ne), ne jako explicitní sloupec — `_hub_page_response`
   musela dostat opravu (bot16, commit `e06105fe`), protože bez toho
   dvojice se stejným `car_make_id` duplicitně zobrazovala.
3. **Duplicitní obsah mezi hub-subdoménou a standalone doménou stejného
   modelu** (stejné `car_model_id`, žádný `rel=canonical` mezi nimi) —
   reálné riziko nezávislé na jazykové otázce, existuje už dnes v Fiat
   síti. Zvážit aspoň doplnění `canonical`, i když se doménová struktura
   Fiatu jinak nemění.
4. Ověřit, jestli QA kontroly `check_storefront_brand_mention`/
   `check_storefront_identifier_leak` (`api/qa_checks.py:2313`/`:2324`,
   skenují `_storefront_text_fields()` = DB textová pole, ř. 2258) vůbec
   zachytávají hardcoded odkaz v HTML šabloně hubu, nebo je potřeba
   upravit jen dokumentaci (tenhle soubor + `TEXT_FILTR.md`), ne kód
   kontroly.

Doporučení: řešit body 1+2 jedním schema návrhem (locale/měna + vztah k
rodičovskému hubu pohromadě), ne postupným záplatováním — viz bot16 nález
2026-09-17.

## Zdůvodnění architektury (stručně)

- Konsolidace autority pod méně domén > fragmentace: nulová startovní
  autorita, blížící se cutover na `logiman.cz`, GEO/AI odpovědní enginy
  preferují jednu rozpoznatelnou entitu k citování před roj podobných webů.
- Google March 2024 core update cílí přímo na vzorec "mnoho tenkých
  podobných domén od jednoho provozovatele" (scaled content abuse, site
  reputation abuse) — dnešní Fiat síť (hub+standalone dvojčata, stejný
  obsah, bez canonical) tenhle vzorec fakticky naplňuje. Další škálování
  STEJNÝM způsobem na další značky/státy by bylo rizikové — proto nový
  model pro budoucí práci, beze změny existující Fiat sítě.

## vandrawee.it — POZASTAVENO (Robert, 2026-09-17: "italii budeme resit
až budeme mít čestinu"), bot16 průzkum zapsán pro navázání

Práce na vandrawee.it/i18n stojí, dokud bot7 nedokončí kompletní přepis
českého obsahu od nuly (viz `TASKS.md`). Bot16 mezitím dokončil průzkum
- zápis pro navázání, až bude Itálie zase aktuální:

1. **Měna/DPH je systémový problém, ne lokální.** Žádné centrální místo
   pro měnu/DPH v e-shopu neexistuje — `VAT_RATE=21` hardcoded nezávisle
   na 2 místech (`api/documents.py` + `webapp/nabidka-online.html` JS),
   IBAN/SPAYD QR má `"CC:CZK"` natvrdo na 2 místech. Přidání EUR = zásah
   do products.py/orders.py/product_assemblies.py/scene_offers.py/
   documents.py + desítky formátovacích míst ve webapp. **Nezávislé
   doporučení** (dá se udělat kdykoli, bez ohledu na Itálii): sjednotit
   2 hardcoded VAT_RATE kopie do jednoho `app_settings` klíče - malá
   bezpečná oprava existujícího rizika rozjetí.
2. **i18n schema — overlay tabulky potvrzeny, silněji než předtím.**
   Toscanaccio má `name_it`/`name_en` sloupce, ale NIKDY k nim nevznikla
   aplikační vrstva (0 čtení, 0 fallbacku, 0 admin editace) - mrtvé
   schéma. Poučení: schéma samo nestačí, těžká část je resolver+fallback
   na CZ+"vše nebo nic" gate před indexací přeložené SEO stránky (dobrý
   nápad od Toscanaccia, přebrat). `*_i18n` overlay tabulky (FK jako
   strukturální párovací klíč) musí od začátku počítat s CELOU vrstvou.
3. **Domain/tenant routing — žádný hotový vzor mimo `car_storefronts.py`.**
   `PUBLIC_BASE_URL` je 1 pevná env konstanta, `company_info` je
   jednotenantní globální JSON. Návrh: nová tabulka
   `site_tenants(primary_domain, locale, currency_code, branding_json...)`
   + `resolve_tenant(request.host)`, analogicky k `resolve_storefront()`
   - použít VÝHRADNĚ v zákaznickém renderování, nikdy v
   `current_user()`/permission logice.
4. **Staff hranice — potvrzeno 100% bezpečné dnes.** `scene_html_gate`/
   `admin_required`/`require_permission` čtou čistě session, nulová
   závislost na Host. Riziko jen budoucí (omylem propojit) - navrhnout
   QA kontrolu (`qa_checks.py` má `ADMIN_UI_FILES` konstantu připravenou),
   co by hlídala, že `scene.html`/`admin.html` zůstanou Host-nezávislé.
5. **Rozsah obsahu — výrazně větší, než čekáno.** 15 DB tabulek, ~2050-
   2200 řádků, ~229 000 znaků (~38 000 slov) na hlavním webu (mimo Fiat
   storefronty, mimo staff scénu) — včetně `product_assemblies.name`
   (392 veřejných řádků, ~5000 slov, štítky variant na product.html).
   PLUS samostatný problém: hardcoded český text přímo v SSR šablonách
   (product.html, category.html, index.html, nabidka-online.html) - to
   NEJDE opravit přes DB overlay, potřebuje vlastní mechanismus
   (slovník UI stringů nebo duplicitní šablony) - jiná práce než
   překlad katalogových dat.

## Otevřeno / další kroky

- **Kategorie 2 z Robertova zadání** (miniweby cílené na oslovení
  návštěvníka k obchodní spolupráci, ne prodej) — zatím NEŘEŠENO,
  čeká na navazující kolo (obsah/formy nabídky spolupráce je potřeba
  teprve navrhnout).
- `TEXT_FILTR.md` — zapsat přesnou výjimku pro hub-prolinky (bot7).
- Konkrétní schema návrh (jazyk/měna/hub-vztah najednou, + párovací klíč
  pro hreflang) — bot16, v řešení.
- Rozsah/potřeba úpravy QA kontroly viz bod 4 výše — bot16 (odpověď:
  není potřeba, jen dokumentace, kontroly skenují jen DB textová pole).
