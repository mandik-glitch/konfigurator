#!/bin/bash
# Mini-shop (Packstations) faze 1 + 2 + 1b: nasadi api/miniweb.py (cteci API + poptavka), api/miniweb_admin.py (import a schvalovani textu), webapp/miniweb-schvaleni.html (stranka pro schvalovani z mobilu),
# importy v api/app.py a QA kontrolu miniweb_text_brand_leak v api/qa_checks.py, pusti testy nad ZIVYMI (uz patchnutymi) soubory a commitne.
# NEPOUSTET bez PRIMEHO povoleni Roberta v teto session (bot3 2026-10-02: "nasazeni nech lezet, otazku polozim ja"; prvni pokus o spusteni zablokoval system oprávneni jako Production Deploy).
# Migrace JIZ JSOU v DB (sql/2026-10-02_miniweb.sql, _miniweb_inquiries.sql, _miniweb_family.sql). api/*.py a webapp/* jdou na ostro pri plánovanem nasazeni serveru (03:30/12:30), po nasazeni overit
# nemutujicimi sondami: /api/miniweb/config na cizim hostu = 404 shop_not_found, /api/admin/miniweb/overview bez prihlaseni = 401, /miniweb-schvaleni.html = 200, hlavni routy a bezna objednavka beze zmeny.
set -u
cd /opt/konfigurator || exit 1
D=/opt/konfigurator/scripts/2026-10-02_miniweb_testy/nasazeni
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
G_EXIST="api/app.py api/qa_checks.py"
G_NEW="api/miniweb.py api/miniweb_admin.py webapp/miniweb-schvaleni.html"
T=scripts/2026-10-02_miniweb_testy
RUN_ALL=scripts/2026-09-30_karta_produktu_testy/run_all.sh
scripts/lock.sh acquire bot5 "api/miniweb.py + api/miniweb_admin.py + webapp/miniweb-schvaleni.html (nove) + api/app.py importy + api/qa_checks.py: mini-shop API, schvalovani textu a QA kontrola znacky" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git reset -q -- $G_NEW $T 2>/dev/null; git checkout -- $G_EXIST $RUN_ALL; rm -f $G_NEW; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
for f in $G_EXIST $RUN_ALL; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
for f in $G_NEW; do [ ! -e $f ] || abort "$f uz existuje (uz nasazeno?)"; done
for t in sql/2026-10-02_miniweb.sql sql/2026-10-02_miniweb_inquiries.sql sql/2026-10-02_miniweb_family.sql; do git ls-files --error-unmatch $t > /dev/null 2>&1 || abort "$t neni v gitu"; done
cp $D/miniweb.py api/miniweb.py
cp $D/miniweb_admin.py api/miniweb_admin.py
cp $D/miniweb-schvaleni.html webapp/miniweb-schvaleni.html
python3 $D/patch_app_import.py api/app.py || rollback "patch app.py"
python3 $D/patch_qa_checks.py api/qa_checks.py || rollback "patch qa_checks.py"
$PY -m py_compile api/miniweb.py api/miniweb_admin.py $G_EXIST || rollback "py_compile"
python3 - <<'PY' || rollback "run_all.sh"
p = "scripts/2026-09-30_karta_produktu_testy/run_all.sh"
t = open(p, encoding="utf-8").read()
if "test_miniweb.py" not in t:
    a = '[ $rc -eq 0 ] && echo "VSE OK" || echo "NEKTERY TEST SELHAL"\n'
    assert t.count(a) == 1
    novy = "node ../2026-10-02_miniweb_testy/test_miniweb_schvaleni.js || rc=1\n"
    for test in ("test_miniweb.py", "test_miniweb_poptavka.py", "test_miniweb_admin.py", "test_qa_miniweb.py"):
        novy += ("systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\\n"
                 "  ${MINIWEB_PY:+--setenv=MINIWEB_PY=$MINIWEB_PY} ${MINIWEB_ADMIN_PY:+--setenv=MINIWEB_ADMIN_PY=$MINIWEB_ADMIN_PY} ${QA_CHECKS_PY:+--setenv=QA_CHECKS_PY=$QA_CHECKS_PY} \\\n"
                 f"  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_miniweb_testy/{test} || rc=1\n")
    t = t.replace(a, novy + a)
    open(p, "w", encoding="utf-8").write(t)
PY
bash -n $RUN_ALL || rollback "syntaxe run_all.sh"
for t in test_miniweb.py test_miniweb_poptavka.py test_miniweb_admin.py test_qa_miniweb.py; do
  timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY $T/$t > /tmp/claude-0/mw_$t.out 2>&1 || { grep -E "^FAIL|Traceback" /tmp/claude-0/mw_$t.out | head -8 | cut -c1-300; rollback "$t"; }
  echo "$t (zive soubory): $(grep VYSLEDEK /tmp/claude-0/mw_$t.out | tail -1 | cut -c1-120)"
done
timeout 600 node $T/test_miniweb_schvaleni.js > /tmp/claude-0/mw_schvaleni.out 2>&1 || { grep -E "^FAIL|CHYBA" /tmp/claude-0/mw_schvaleni.out | head -6 | cut -c1-300; rollback "test_miniweb_schvaleni.js"; }
echo "test_miniweb_schvaleni.js (zive soubory): $(grep VYSLEDEK /tmp/claude-0/mw_schvaleni.out | tail -1 | cut -c1-120)"
for t in test_duplikace_db.py test_qa_kontrola.py; do
  timeout 600 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY scripts/2026-09-30_duplikace_produktu_testy/$t > /tmp/claude-0/mw_$t.out 2>&1 || { grep -E "^FAIL|Traceback" /tmp/claude-0/mw_$t.out | head -6 | cut -c1-300; rollback "$t"; }
  echo "$t: $(grep VYSLEDEK /tmp/claude-0/mw_$t.out | tail -1 | cut -c1-100)"
done
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "
import app
verejne = sorted(r.rule for r in app.app.url_map.iter_rules() if r.rule.startswith('/api/miniweb/'))
admin = sorted(r.rule for r in app.app.url_map.iter_rules() if r.rule.startswith('/api/admin/miniweb/'))
assert len(verejne) == 6, verejne
assert len(admin) == 3, admin
print('import app OK, trasy: verejne', len(verejne), 'admin', len(admin))" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app / trasy"
git add $G_NEW $T scripts/miniweb_import.py
BOT_ID=bot5 git commit -q -F - -- $G_NEW $G_EXIST $RUN_ALL $T scripts/miniweb_import.py <<'MSG' || rollback "git commit"
feat(miniweb): mini-shop Packstations - serverove API /api/miniweb/* (cteni, poptavka), import a schvalovani textu, QA kontrola znacky (bot5)

Navrh a faze 1 + 2 + 1b schvalil bot3 (2026-10-02), kostru shopu a tvary odpovedi dodal bot16 (webapp/miniweb, docs/KONTRAKT_MINISHOP.md). Faze 3 (objednavky: mena, DPH, doprava) zustava zavrena.
Migrace uz jsou v DB (sql/2026-10-02_miniweb.sql, _miniweb_inquiries.sql, _miniweb_family.sql).
- api/miniweb.py: GET config, categories, products, products/<id>, legal a POST inquiry. Shop = storefront (host a jazyk podle domeny, aliasy) + miniweb_shops, katalog patri rodine shopu, texty po jazycich
  se stavem draft/approved, shop ve stavu draft jen pro staff (brana na serveru), BEZ ZNACKY (fail closed, vyjimka jen legal.seller), zadny zivy e-mail, ceny se nevydavaji ani neprijimaji, poptavka zaklada
  CRM poptavku (osobni udaje jen tam), potvrzeni zakaznikovi e-mailem je zatim vypnute, nahled pro staff nic neuklada, limity a ochrany vstupu.
- api/miniweb_admin.py + webapp/miniweb-schvaleni.html + scripts/miniweb_import.py: import textu jako DRAFT (nahled, vse nebo nic, schvaleny text se neprepise, zaloha pred zapisem) a klikaci schvaleni
  Robertem z mobilu (otisk obsahu: zmeneny text se neschvali; znacka a prazdny nazev blokuji), jen admin, audit.
- api/qa_checks.py: kontrola miniweb_text_brand_leak. api/app.py: importy miniweb a miniweb_admin.
Testy: test_miniweb 50, test_miniweb_poptavka 51, test_miniweb_admin 44, test_qa_miniweb 10, test_miniweb_schvaleni.js 23 (vse do run_all.sh). Na ostro pri nasazeni serveru.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-140
