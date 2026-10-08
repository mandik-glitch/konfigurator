#!/bin/bash
# Mini-shop: kosik a objednavka konfigurovatelneho stolu (faze 3 pro SK): quote, orders, vat-check, VIES, adresy, Toptrans odhad, DPH, vyrovnani v Kc, puvod v admin prehledu objednavek.
# Patchuje api/app.py (import), api/miniweb.py (checkout_mode) a api/orders.py (puvod, filtry, origins), pridava api/miniweb_objednavky.py a api/miniweb_vies.py, pusti testy nad ZIVYMI soubory a commitne.
# PORADI: az PO sadach konfigurace, pravni a ceny, a po DDL sql/2026-10-03_miniweb_orders_enabled.py (sloupce orders_enabled, shipping_review, vat_mode, vat_check; DDL pousti bot3/Robert).
# NEPOUSTET bez PRIMEHO povoleni Roberta v session, ktera skript spousti (commit guarded api/*.py = nasazeni, na ostro pri planovanem nasazeni 3:30/12:30). Objednavky jsou za prepinacem (orders_enabled = 0), takze
# nasazeni samo mini-shop nemeni: zapina se `scripts/miniweb_shop.py --slug packstations-sk --orders on --apply`.
set -u
trap '' HUP
cd /opt/konfigurator || exit 1
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
K=scripts/2026-10-03_miniweb_objednavky_testy
D=$K/nasazeni
G="api/app.py api/miniweb.py api/orders.py"
NOVE="api/miniweb_objednavky.py api/miniweb_objednavky_admin.py api/miniweb_vies.py"
scripts/lock.sh acquire bot5 "api/app.py + api/miniweb.py + api/orders.py + miniweb_objednavky.py: kosik a objednavka mini-shopu" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git checkout -- $G 2>/dev/null; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
trap 'rollback "preruseno signalem"' INT TERM
for f in $G; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
grep -q "miniweb_cena" api/miniweb.py || abort "sada ceny neni nasazena"
grep -q "miniweb_objednavky" api/app.py && abort "uz nasazeno"
for f in $NOVE; do [ -f $f ] || abort "chybi $f"; done
timeout 60 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY -c "
import os, pymysql
c = pymysql.connect(host=os.environ['DB_HOST'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], database=os.environ['DB_NAME'], port=int(os.environ.get('DB_PORT', 3306)))
cur = c.cursor()
for t, col in (('miniweb_shops', 'orders_enabled'), ('shop_orders', 'shipping_review'), ('shop_orders', 'vat_mode'), ('shop_orders', 'vat_check')):
    cur.execute('SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s', (t, col))
    assert cur.fetchone()[0], f'{t}.{col} v DB chybi'" || abort "sloupce v DB chybi (sql/2026-10-03_miniweb_orders_enabled.py)"
for f in app miniweb orders; do patch -p1 --dry-run -s -i $D/$f.py.patch > /dev/null || abort "patch $f nesedi"; done
for f in app miniweb orders; do patch -p1 -s -i $D/$f.py.patch || rollback "patch $f"; done
$PY -m py_compile api/app.py api/miniweb.py api/orders.py api/miniweb_objednavky.py api/miniweb_objednavky_admin.py api/miniweb_vies.py || rollback "py_compile"
run() { timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY "$@" > /tmp/claude-0/ob_out.txt 2>&1 || { grep -E "^FAIL|CHYBA" /tmp/claude-0/ob_out.txt | head -8 | cut -c1-300; rollback "test $1"; }; echo "$1: $(grep -E 'VYSLEDEK|OK [0-9]' /tmp/claude-0/ob_out.txt | tail -1 | cut -c1-110)"; }
run $K/test_miniweb_vies.py
run $K/test_miniweb_objednavky.py
run $K/test_admin_puvod.py
run scripts/2026-10-03_miniweb_ceny_eur/test_resolve_eur.py
run scripts/2026-10-02_miniweb_testy/test_miniweb.py
run scripts/2026-10-02_miniweb_testy/test_miniweb_poptavka.py
run scripts/2026-10-02_miniweb_testy/test_miniweb_admin.py
run scripts/2026-10-02_konfigurace_kosik_testy/test_kosik_konfigurace.py
run scripts/2026-10-02_dealeri_testy/test_objednavky.py
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "
import app
pravidla = sorted(r.rule for r in app.app.url_map.iter_rules() if r.rule.startswith('/api/miniweb'))
assert '/api/miniweb/quote' in pravidla and '/api/miniweb/orders' in pravidla and '/api/miniweb/vat-check' in pravidla, pravidla
assert any(r.rule == '/api/admin/orders/<int:order_id>/shipping' for r in app.app.url_map.iter_rules()), 'chybi trasa schvaleni dopravy'
print('import app OK, trasy objednavek mini-shopu nactene:', len(pravidla))" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app / moduly"
git add $K $NOVE
BOT_ID=bot5 git commit -q -F - -- $G $NOVE $K <<'MSG'
feat(miniweb): kosik a objednavka konfigurovatelneho stolu (quote, orders, vat-check, VIES), puvod objednavky v admin prehledu (bot5)

Robert pres bot3 2026-10-03: mini-shop ma funkcni kosik, pokladnu a objednavku jako hlavni e-shop; objednavka vznika v shop_orders s puvodem (host + jazyk).
- api/miniweb_objednavky.py: POST /api/miniweb/quote, /orders, /vat-check; objednavka hosta (firma, ICO povinne), fakturacni i dodaci adresa, cena v EUR bez DPH ze serveru (kurz + marze),
  k uhrade v Kc = EUR x kurz, doprava Toptrans (odhad podle PSC a uplne hmotnosti, jinak ke schvaleni), DPH 0 % pro platne IC DPH (VIES) mimo CR, jinak CZ sazba, VIES nedostupne = ruzna kontrola;
  bez automaticke proformy a bez e-mailu (pravidlo 16), za prepinacem miniweb_shops.orders_enabled
- api/miniweb_objednavky_admin.py: POST /api/admin/orders/<id>/shipping (uprava a schvaleni dopravy zamestnancem, pri schvaleni zalohova faktura a e-mail do schvalovaci fronty)
- api/miniweb_vies.py: overeni IC DPH (VIES, cache, bez hadani); api/miniweb.py: config.checkout_mode; api/orders.py: order_host/order_lang/origin_label, filtry origin a shipping_review, origins
- sql/2026-10-03_miniweb_orders_enabled.py: sloupce orders_enabled, shipping_review, vat_mode, vat_check

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-120
