#!/bin/bash
# Admin API Mini-shopy: api/miniweb_shops_admin.py (shops, inquiries, orders) + RBAC sekce `miniweb` a `miniweb_schvalovani` (api/app.py PERMISSION_SECTIONS + import) a approve/unapprove/overview v api/miniweb_admin.py
# misto jen role admin na require_permission. Pro zalozku "Mini-shopy" (bot16). Pusti testy nad zivymi soubory a commitne. PORADI: po sade "objednavky". NEPOUSTET bez PRIMEHO povoleni Roberta v session, ktera skript spousti.
# Po nasazeni: bot16 doplni RP_SECTION_LABELS/RP_SECTION_DESC (webapp/admin/js/uzivatele-role.js) a TAB_SECTION v admin.html pro sekce miniweb a miniweb_schvalovani (pravidlo 11, 3 vrstvy RBAC).
set -u
trap '' HUP
cd /opt/konfigurator || exit 1
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
K=scripts/2026-10-03_miniweb_objednavky_testy
D=$K/nasazeni
G="api/app.py api/miniweb_admin.py"
scripts/lock.sh acquire bot5 "api/app.py + api/miniweb_admin.py + miniweb_shops_admin.py: admin API Mini-shopy s RBAC" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git checkout -- $G 2>/dev/null; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
trap 'rollback "preruseno signalem"' INT TERM
for f in $G api/miniweb_shops_admin.py; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
grep -q "miniweb_objednavky_admin" api/app.py || abort "sada objednavky neni nasazena"
grep -q "miniweb_shops_admin" api/app.py && abort "uz nasazeno"
patch -p1 --dry-run -s -i $D/adm_app.py.patch > /dev/null || abort "patch app nesedi"
patch -p1 --dry-run -s -i $D/adm_miniweb_admin.py.patch > /dev/null || abort "patch miniweb_admin nesedi"
patch -p1 -s -i $D/adm_app.py.patch || rollback "patch app"
patch -p1 -s -i $D/adm_miniweb_admin.py.patch || rollback "patch miniweb_admin"
$PY -m py_compile api/app.py api/miniweb_admin.py api/miniweb_shops_admin.py || rollback "py_compile"
run() { timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY "$@" > /tmp/claude-0/am_out.txt 2>&1 || { grep -E "^FAIL|CHYBA" /tmp/claude-0/am_out.txt | head -8 | cut -c1-300; rollback "test $1"; }; echo "$1: $(grep -E 'VYSLEDEK|OK [0-9]' /tmp/claude-0/am_out.txt | tail -1 | cut -c1-110)"; }
run $K/test_miniweb_shops_admin.py
run scripts/2026-10-02_miniweb_testy/test_miniweb_admin.py
run scripts/2026-10-02_miniweb_testy/test_miniweb.py
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "
import app
assert 'miniweb' in app.PERMISSION_SECTIONS and 'miniweb_schvalovani' in app.PERMISSION_SECTIONS
r = sorted(x.rule for x in app.app.url_map.iter_rules() if x.rule.startswith('/api/admin/miniweb'))
assert '/api/admin/miniweb/shops' in r and '/api/admin/miniweb/orders' in r and '/api/admin/miniweb/inquiries' in r, r
print('import app OK, sekce RBAC a trasy Mini-shopy:', len(r))" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app / moduly"
git add $K
BOT_ID=bot5 git commit -q -F - -- $G api/miniweb_shops_admin.py $K <<'MSG'
feat(miniweb): admin API Mini-shopy (shops, inquiries, orders) + RBAC sekce miniweb a miniweb_schvalovani (bot5)

bot16 + Robert pres bot3 2026-10-03: zalozka "Mini-shopy" v administraci se stejnymi ucty a pravy. GET/PUT /api/admin/miniweb/shops (cena, marze, kurz, zeme, poptavky, objednavky, kontakt; stav live jen skriptem),
GET /api/admin/miniweb/inquiries|orders?shop=, approve/unapprove/overview pres RBAC miniweb_schvalovani misto jen role admin; objednavky lze zapnout jen s kompletni cenou (shown, EUR, marze).

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-120
