#!/bin/bash
# Mini-shop: URL slugy po jazycich (SEO adresy): klic url_slug v importu (kategorie, produkt), sloupec url_slug v *_texts, API vraci slug v jazyce shopu + slug_alt, ?category= prijme oba, unikatnost v jazyce.
# Patchuje api/miniweb.py a api/miniweb_admin.py, pusti testy nad ZIVYMI soubory a commitne. PORADI: po DDL sql/2026-10-03_miniweb_url_slug.py (pousti bot3/Robert).
# NEPOUSTET bez PRIMEHO povoleni Roberta v session, ktera skript spousti (commit guarded api/*.py = nasazeni, na ostro pri nasazeni API / HUP).
set -u
trap '' HUP
cd /opt/konfigurator || exit 1
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
K=scripts/2026-10-03_miniweb_objednavky_testy
D=$K/nasazeni
G="api/miniweb.py api/miniweb_admin.py"
scripts/lock.sh acquire bot5 "api/miniweb.py + api/miniweb_admin.py: URL slugy po jazycich" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git checkout -- $G 2>/dev/null; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
trap 'rollback "preruseno signalem"' INT TERM
for f in $G; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
grep -q "_check_url_slugs" api/miniweb_admin.py && abort "uz nasazeno"
timeout 60 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY -c "
import os, pymysql
c = pymysql.connect(host=os.environ['DB_HOST'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], database=os.environ['DB_NAME'], port=int(os.environ.get('DB_PORT', 3306)))
cur = c.cursor()
for t in ('miniweb_category_texts', 'miniweb_product_texts'):
    cur.execute('SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=\"url_slug\"', (t,))
    assert cur.fetchone()[0], f'{t}.url_slug v DB chybi'" || abort "sloupce url_slug v DB chybi (sql/2026-10-03_miniweb_url_slug.py)"
for f in miniweb miniweb_admin; do patch -p1 --dry-run -s -i $D/slug_$f.py.patch > /dev/null || abort "patch $f nesedi"; done
for f in miniweb miniweb_admin; do patch -p1 -s -i $D/slug_$f.py.patch || rollback "patch $f"; done
$PY -m py_compile api/miniweb.py api/miniweb_admin.py || rollback "py_compile"
run() { timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY "$@" > /tmp/claude-0/sl_out.txt 2>&1 || { grep -E "^FAIL|CHYBA" /tmp/claude-0/sl_out.txt | head -8 | cut -c1-300; rollback "test $1"; }; echo "$1: $(grep -E 'VYSLEDEK|OK [0-9]' /tmp/claude-0/sl_out.txt | tail -1 | cut -c1-110)"; }
run $K/test_miniweb_slugy.py
run scripts/2026-10-02_miniweb_testy/test_miniweb.py
run scripts/2026-10-02_miniweb_testy/test_miniweb_poptavka.py
run scripts/2026-10-02_miniweb_testy/test_miniweb_admin.py
run $K/test_miniweb_objednavky.py
run $K/test_miniweb_shops_admin.py
SCHVALENI_HTML=/opt/konfigurator/webapp/miniweb-schvaleni.html timeout 600 node scripts/2026-10-02_miniweb_testy/test_miniweb_schvaleni.js > /tmp/claude-0/sl_js.txt 2>&1 || { grep -E "FAIL" /tmp/claude-0/sl_js.txt | head -5; rollback "test schvaleni.js"; }
echo "test_miniweb_schvaleni.js: $(grep VYSLEDEK /tmp/claude-0/sl_js.txt | tail -1 | cut -c1-110)"
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "
import app, miniweb, miniweb_admin
assert hasattr(miniweb, '_url_slug') and hasattr(miniweb_admin, '_check_url_slugs')
print('import app OK, url_slug nacten')" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app / moduly"
git add $K
BOT_ID=bot5 git commit -q -F - -- $G $K scripts/2026-10-02_miniweb_testy <<'MSG'
feat(miniweb): URL slugy po jazycich (url_slug v importu, sloupec v *_texts, slug a slug_alt v API, ?category= oba, unikatnost v jazyce) (bot5)

bot3/bot16/bot7 2026-10-03: SEO adresy v jazyce shopu (SK: baliace-a-pracovne-stoly, konfigurovatelny-baliaci-stol), zakladni slug zustava identitou a jako slug_alt (301 na strane webu).
- import: volitelny klic url_slug u kategorie a produktu (tvar a filtr znacky jako slug, unikatni v jazyce vc. proti polozkam mimo soubor), uklada se do miniweb_*_texts.url_slug, je soucasti otisku schvalovaneho
  obsahu (text bez slugu ma otisk beze zmeny); API: slug = url_slug nebo zakladni, slug_alt = [zakladni], jinak []; poskozeny/znackovy url_slug v DB se verejne nevyda
- sql/2026-10-03_miniweb_url_slug.py: sloupec url_slug + UNIQUE (lang, url_slug) v obou tabulkach textu

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-120
