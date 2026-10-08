# Plán rozdělení backendu (api/app.py + api/remeslo.py) do modulů

bot16, 2026-09-02, na zadání Roberta přes bot3 ("optimalizaci procesů aplikujme hned").
Podklad: `grep -n "^@app\.\|^# ==="` + `wc -l` — soubory nebyly čteny celé, řádky jsou orientační
(app.py 9757 ř. / 161 rout, remeslo.py 11461 ř. / 134 rout k datu psaní).

## Vzor, který už funguje (držet se ho, žádné Blueprinty)

Existující moduly (`orders.py`, `products.py`, `turntable.py`, …) jsou obyčejné soubory, které
udělají `from app import app, get_conn, current_user, login_required, log_audit, …` a registrují
routy přímo na sdílenou `app` přes `@app.get/@app.post`. `app.py` je importuje **až na konci**
(blok `import xxx  # noqa: F401`, ř. ~9720–9757). Nový modul = stejný vzor:
1. vyříznout blok (helpery + routy) do `api/<modul>.py`, nahoře `from app import (...)` jen to, co
   blok opravdu používá (zjistit `pyflakes`, viz Ověření bod 1);
2. do `app.py` na konec přidat `import <modul>  # noqa: F401` (pořadí: pokud modul importuje
   jiný modul, musí být za ním — viz komentáře u stávajících importů);
3. pokud blok definuje helper, který používá **zbytek app.py** (např. `_slugify`, cenové funkce),
   helper v app.py zůstává a modul si ho importuje — nikdy obráceně (cyklický import).

## app.py — skupiny rout (řádky od–do, počet rout → cílový modul)

| # | Skupina | Řádky | Rout | Cílový modul |
|---|---------|-------|------|--------------|
| 1 | Social posts (plánované příspěvky) | 5728–5900 | 5 | `social_posts.py` |
| 2 | Announcement items + homepage blocks + sidebar blocks + theme presets | 6078–7345 | 21 | `cms_blocks.py` |
| 3 | Accessories admin | 6134–6244 | 6 | `accessories.py` |
| 4 | Team chat (`/api/admin/internal-chat`) | 8472–8534 | 2 | `internal_chat.py` |
| 5 | Audit log routy (`/api/admin/audit-log`) | 8767–8828 | 2 | `audit_log.py` (helpery ř. 416 zůstávají v app.py) |
| 6 | Price scraping logiman.cz + product price check | 8829–9047 | 3 | `price_scraping.py` |
| 7 | User management admin (`/api/admin/users`) | 8223–8416 | 6 | `admin_users.py` |
| 8 | Custom shapes + kategorie custom shapes | 2113–2793 | 8 | `custom_shapes.py` |
| 9 | Product assemblies + jejich kategorie (`/api/product-assemblies*`) | 2794–3209 | 10 | `product_assemblies.py` |
| 10 | Cars tree: make → model → car body + karoserie-model-reference | 3552–3990 | 11 | `cars.py` |
| 11 | Admin profily (cena/hmotnost tabulka, step-quality-preview) | 3210–3551 | 11 | `admin_profily.py` |
| 12 | Nastavení: field-labels/options, settings, theme-colors, og-settings, pricing-config | 4300–4830 | 11 | `admin_settings.py` |
| 13 | E-shop stránky + SEO (`/`, `product.html`, `kategorie`, `blok`, `robots.txt`, `sitemap.xml`, `panel`) | 4952–5727, 7377 | 10 | `storefront_pages.py` |
| 14 | Kategorie (scene + eshop) + price-coefficients + logiman-price-check | 6265–8222 (mimo bloky 2) | 19 | `categories.py` |
| 15 | Shop API (`/api/shop/*`) | 4004–4299, 8946 | 11 | `shop_api.py` |
| 16 | Katalog + thumbnail + products + join-rules + export-fbx | 1329–2112 | 10 | zůstává (jádro scény, těsně provázané s `products.py`) |
| 17 | Auth + role-permissions + health + deploy-status + client-error + AI | 565–1273, 1361, 1426, 2095, 9170 | 19 | **zůstává v app.py** (jádro) |

Po extrakci 1–15 zbývá v app.py ~2 000 ř.: konfigurace, e-mail/SMTP (103), AI vrstva (223),
pagination/audit/bulk/CSV helpery (365–527), rate limit, auth, role, katalog, importy modulů.

## remeslo.py — skupiny rout (všechno pod `/api/remeslo/*` + pár public)

| # | Skupina (sekce v souboru) | Řádky | Rout | Cílový modul |
|---|---------------------------|-------|------|--------------|
| A | Počasí (modul „počasí navázané na kalkulačky") | 6306–6415 | 1 | `remeslo_weather.py` |
| B | Modul 5 foto analýzy + hlasové zadání (async fronta) | 300–424, 2990–3120 | 7 | `remeslo_media.py` |
| C | Dodavatelé + profese | 2761–2989 | 6 | `remeslo_suppliers.py` |
| D | Materiál položkově + pracovní deník | 2505–2760 | 6 | `remeslo_worklog.py` |
| E | Denní zásobník + app comparator | 3121–3443 | 6 | `remeslo_daily.py` |
| F | Modul 7A veřejný profil + katalog řemeslníků + vizitky (`/r/…`, `/vizitky`, `/profese`) | 3444–4014 | 3+3 | `remeslo_public_profile.py` |
| G | Modul 7B spolupracovníci | 4015–4300 | 6 | `remeslo_collaborators.py` |
| H | Modul 4 ověření + modul 9 ceník + kalkulačky | 6063–6305, 6909–7288 | 9 | `remeslo_pricelist.py` |
| I | Modul 8 nabídky + nastavení, 8d online nabídka + QR | 4301–5418, 10838–11112 | 21 | `remeslo_offers.py` |
| J | Modul 10a faktury + 10b finance | 5419–6062, 6416–6908 | 20 | `remeslo_finance.py` |
| K | Moderátor: hlasové vyhledávání + editovatelné fráze; zákazníci per řemeslník | 11113–11461 | 8 | `remeslo_moderator.py` |
| L | Odvození/zdroj + individualizace (bot9) | 7289–10837 | 16 | `remeslo_derivation.py` (největší blok, 3,5k ř.) |
| M | Infrastruktura (vlastní DB `get_remeslo_conn`, `current_craftsman`), modul 2 zakázky, modul 11 self-service účty | 152–299, 425–2504 | 30 | **zůstává v remeslo.py** (jádro, ostatní z něj importují) |

Moduly A–L dělají `from remeslo import get_remeslo_conn, current_craftsman, …` (a `from app import
app, …`) a v app.py se importují **za** `import remeslo`.

## Pořadí extrakce (nejméně provázané první)

1. app.py: 1 social_posts → 4 internal_chat → 5 audit_log → 6 price_scraping → 3 accessories →
   7 admin_users → 8 custom_shapes → 9 product_assemblies → 10 cars → 11 admin_profily →
   12 admin_settings → 2 cms_blocks → 13 storefront_pages → 14 categories → 15 shop_api.
   (13–15 až nakonec: sdílejí cenové/SEO helpery, nejdřív se musí ukázat, co z nich zůstává v jádru.)
2. remeslo.py: A weather → C suppliers → D worklog → E daily → B media → G collaborators →
   F public_profile → H pricelist → K moderator → J finance → I offers → L derivation.
3. Kdo si blok vezme, nejdřív `grep -n "<název_helperu>" api/*.py` — pokud helper používá i jiný
   soubor, zůstává v jádru (viz bod 3 vzoru).

## Ověření po KAŽDÉM modulu (než se pustí zámek)

1. `api/venv/bin/python -m py_compile api/<modul>.py api/app.py` (nebo remeslo.py) — bez chyby;
   nepoužité/chybějící importy odhalí `api/venv/bin/pip install pyflakes` + `pyflakes api/<modul>.py` (dnes v venv není).
2. `sudo systemctl restart konfigurator && curl -fsS http://127.0.0.1:8090/api/health`.
3. `scripts/qa/run_all.sh` — stejný výsledek jako před extrakcí (žádný nový FAIL).
4. Smoke: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8090/api/<jedna routa z bloku>`
   pro každou GET routu modulu (očekává se stejný kód jako před přesunem, typicky 200/401),
   plus `journalctl -u konfigurator -n 30 --no-pager` bez tracebacku.
5. Počet rout se nesmí změnit: `grep -c "^@app\." api/*.py | awk -F: '{s+=$2} END{print s}'`
   před = po (dnes 161 + 134 + moduly).

## Pravidla

- **Jeden modul = jeden commit se zámkem ≤ 10 min.** `scripts/lock.sh acquire <bot> "split: <modul>" --wait`
  těsně před vyříznutím, commit `BOT_ID=<bot> git commit -m "refactor: <modul>.py vyčleněn z app.py" -- api/app.py api/<modul>.py`,
  `release` hned po commitu. Když se do 10 min nestihne ověření, `git checkout -- api/app.py`, smazat modul, pustit zámek.
- Čistý přesun, **žádné změny chování/URL** v tomtéž commitu (opravy zvlášť, až po přesunu).
- Nikdy dva boti současně dva bloky téhož souboru — každý přesun mění app.py/remeslo.py, konflikt je jistý.
- Po dokončení každého bloku zapsat řádek do `AGENTS_LOG.md` a odškrtnout v `TASKS.md`; tuhle tabulku
  aktualizovat (čísla řádků se posouvají s každým přesunem — před prací vždy znovu `grep -n`).
