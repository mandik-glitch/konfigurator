#!/bin/bash
# Mini-shop: cena v EUR bez DPH (kurz Fio nebo rucni + marze, vse z DB a nikdy natvrdo). Patchuje api/miniweb.py (price_from) a api/stul_shop.py (resolve v EUR),
# pusti testy nad ZIVYMI soubory a commitne. PORADI: az PO sade "pravni" (patch miniweb.py je nad jeho vysledkem) a po migraci sql/2026-10-03_miniweb_ceny_eur.py (uz provedena).
# NEPOUSTET bez PRIMEHO povoleni Roberta v session, ktera skript spousti (commit guarded api/*.py = nasazeni, na ostro pri planovanem nasazeni 3:30/12:30).
set -u
trap '' HUP
cd /opt/konfigurator || exit 1
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
K=scripts/2026-10-03_miniweb_ceny_eur
D=$K/nasazeni
G="api/miniweb.py api/stul_shop.py"
scripts/lock.sh acquire bot5 "api/miniweb.py + api/stul_shop.py: cena v EUR pro mini-shop" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git checkout -- $G 2>/dev/null; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
trap 'rollback "preruseno signalem"' INT TERM
for f in $G; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
grep -q "_documents" api/miniweb.py || abort "sada pravni neni nasazena (api/miniweb.py nema dokumenty)"
grep -q "miniweb_cena" api/stul_shop.py && abort "uz nasazeno"
timeout 60 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY -c "
import os, pymysql
c = pymysql.connect(host=os.environ['DB_HOST'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], database=os.environ['DB_NAME'], port=int(os.environ.get('DB_PORT', 3306)))
cur = c.cursor(); cur.execute(\"SHOW COLUMNS FROM miniweb_shops\"); n = {r[0] for r in cur.fetchall()}; assert {'eur_rate','margin_pct'} <= n, n" || abort "sloupce eur_rate/margin_pct v DB chybi (sql/2026-10-03_miniweb_ceny_eur.py)"
for f in miniweb stul_shop; do patch -p1 --dry-run -s -i $D/$f.py.patch > /dev/null || abort "patch $f nesedi"; done
for f in miniweb stul_shop; do patch -p1 -s -i $D/$f.py.patch || rollback "patch $f"; done
$PY -m py_compile api/miniweb.py api/stul_shop.py api/miniweb_cena.py || rollback "py_compile"
run() { timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY "$@" > /tmp/claude-0/ce_out.txt 2>&1 || { tail -8 /tmp/claude-0/ce_out.txt | cut -c1-200; rollback "test $1"; }; echo "$1: $(tail -1 /tmp/claude-0/ce_out.txt | cut -c1-100)"; }
run $K/test_miniweb_cena.py
run $K/test_resolve_eur.py
run scripts/2026-10-02_stul_testy/test_stul_shop.py
run scripts/2026-10-02_miniweb_testy/test_miniweb.py
run scripts/2026-10-02_miniweb_testy/test_miniweb_poptavka.py
git add $K
BOT_ID=bot5 git commit -q -F - -- $G $K <<'MSG'
feat(miniweb): cena v EUR bez DPH (kurz Fio nebo rucni + marze z DB), price_from a resolve v EUR (bot5)

Robert 2026-10-03: zadna cena se neskryva, SK mini-shop ukazuje EUR bez DPH (B2B), kurz a marze nastavitelne, nic natvrdo (pravidlo 9).
- api/miniweb_cena.py: Kc / kurz * (1 + marze), cele EUR; kurz = miniweb_shops.eur_rate, jinak zivy Fio (EUR, prodej), bez fallbacku; bez marze nebo kurzu cena neni
- api/miniweb.py: product.price_from v EUR; api/stul_shop.py: resolve.price a options.*.price_delta v EUR pro host mini-shopu s price_mode 'shown'
- scripts/miniweb_shop.py --price-mode shown --margin-pct --eur-rate

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-120
