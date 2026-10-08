#!/bin/bash
# Objednavka stolu HOSTEM (hlavni e-shop), montaz stolu (volitelna, sazba v app_settings stul_montaz_pct, vychozi 12 %), doprava ke schvaleni i pro objednavky hlavniho e-shopu (viz README.md).
# Patchuje api/app.py (import), api/konfigurace_kosik.py (sazba montaze, samostatny radek montaze), api/orders.py (radek montaze, doprava ke schvaleni u konfigurace s neuplnou hmotnosti),
# api/miniweb_objednavky_admin.py (schvaleni dopravy i bez order_host); pridava api/stul_montaz.py a api/stul_objednavka_host.py; pusti testy nad ZIVYMI soubory a commitne.
# PORADI: po nasazeni sady objednavky/doklady (miniweb_objednavky_admin existuje). Potrebuje CISTE soubory (rozpracovana zmena bot8 v konfigurace_kosik.py/stul_shop.py musi byt commitnuta).
# NEPOUSTET bez PRIMEHO povoleni Roberta v session, ktera skript spousti (commit guarded api/*.py = nasazeni, na ostro pri nasazeni API 3:30/12:30).
set -u
trap '' HUP
cd /opt/konfigurator || exit 1
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
K=scripts/2026-10-04_stul_host_testy
D=scripts/2026-10-03_miniweb_objednavky_testy/nasazeni
G="api/app.py api/konfigurace_kosik.py api/orders.py api/miniweb_objednavky_admin.py"
NOVE="api/stul_montaz.py api/stul_objednavka_host.py"
scripts/lock.sh acquire bot5 "api/app.py + konfigurace_kosik.py + orders.py + miniweb_objednavky_admin.py + stul_montaz.py + stul_objednavka_host.py: objednavka stolu hostem, montaz" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git checkout -- $G 2>/dev/null; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
trap 'rollback "preruseno signalem"' INT TERM
for f in $G; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny (cizi rozpracovana zmena?)"; done
for f in $NOVE; do [ -f $f ] || abort "chybi $f"; done
grep -q "stul_objednavka_host" api/app.py && abort "uz nasazeno"
grep -q "miniweb_objednavky_admin" api/app.py || abort "sada objednavky neni nasazena"
patch -p1 --dry-run -s -i $D/stul_app.py.patch > /dev/null || abort "patch app nesedi"
for f in konfigurace_kosik orders miniweb_objednavky_admin; do patch -p1 --dry-run -s -i $D/stul_$f.py.patch > /dev/null || abort "patch $f nesedi"; done
patch -p1 -s -i $D/stul_app.py.patch || rollback "patch app"
for f in konfigurace_kosik orders miniweb_objednavky_admin; do patch -p1 -s -i $D/stul_$f.py.patch || rollback "patch $f"; done
$PY -m py_compile api/app.py api/konfigurace_kosik.py api/orders.py api/miniweb_objednavky_admin.py api/stul_montaz.py api/stul_objednavka_host.py || rollback "py_compile"
run() { timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY "$@" > /tmp/claude-0/sh_out.txt 2>&1 || { grep -E "^FAIL|CHYBA|Error" /tmp/claude-0/sh_out.txt | head -8 | cut -c1-300; rollback "test $1"; }; echo "$1: $(grep -E 'VYSLEDEK|OK [0-9]' /tmp/claude-0/sh_out.txt | tail -1 | cut -c1-110)"; }
run $K/test_stul_objednavka_host.py
run scripts/2026-10-02_konfigurace_kosik_testy/test_kosik_konfigurace.py
run scripts/2026-10-03_miniweb_objednavky_testy/test_miniweb_objednavky.py
run scripts/2026-10-02_dealeri_testy/test_objednavky.py
run scripts/2026-10-01_zastupce_montaz_testy/test_kosik_zastupce_db.py
run scripts/2026-10-01_zastupce_montaz_testy/test_cena_varianty_zastupce.py
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "
import app
r = sorted(x.rule for x in app.app.url_map.iter_rules() if x.rule.startswith('/api/shop/stul') or x.rule == '/api/stul/montaz')
assert '/api/shop/stul/quote' in r and '/api/shop/stul/order' in r and '/api/stul/montaz' in r, r
print('import app OK, trasy objednavky hosta a montaze:', r)" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app / moduly"
git add $K $NOVE $G
git diff --cached --quiet -- $G && abort "nic ke commitu (patche nic nezmenily?)"
BOT_ID=bot5 git commit -q -F - -- $G $NOVE $K scripts/2026-10-02_konfigurace_kosik_testy scripts/2026-10-03_miniweb_objednavky_testy <<'MSG'
feat(stul): objednavka stolu HOSTEM bez registrace, montaz (volitelna, % z ceny, vychozi 12), doprava ke schvaleni v hlavnim e-shopu (bot5)

Robert pres bot9 2026-10-04: objednavka hosta ANO; montaz je vzdy volitelna, cena = nastavitelne % z ceny stolu (vychozi 12, nastavuje se v Generatoru stolu, zakaznik % nevidi), samostatny radek Montaz, DPH 21 %;
doprava u hlavniho e-shopu ke schvaleni zamestnancem (objednavka vznikne s dopravou 0 a priznakem shipping_review, zalohova faktura az po schvaleni, e-mail do schvalovaci fronty).
- api/stul_objednavka_host.py: POST /api/shop/stul/quote a /order (bez uctu, cena ze serveru, jen aktivni konfigurovatelny produkt, otisk obsahu + zamek proti dvojitemu odeslani, rate limity, honeypot)
- api/stul_montaz.py: sazba app_settings stul_montaz_pct (GET/PUT /api/stul/montaz, RBAC nastaveni/upravit, audit); konfigurace_kosik.montaz_pct_pro_typ ji cte pro STUL_SKLAD
- konfigurace_kosik/orders: montaz jako samostatny radek objednavky; konfigurace s neuplnou hmotnosti + Toptrans nevraci 409, vznikne ke schvaleni; schvaleni dopravy (POST /api/admin/orders/<id>/shipping) bez order_host

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-120
