#!/bin/bash
# Mini-shop: pravni dokumenty (podminky, soukromi, vraceni: import, schvaleni, vydani u formulare), kontakt z nastaveni spolecnosti a poptavka JEN FIRMAM (firma, ICO, DIC / IC DPH mimo CR, potvrzeni podnikatele).
# Patche api/miniweb.py, api/miniweb_admin.py a webapp/miniweb-schvaleni.html, nove testy (+ test skriptu miniweb_shop.py), pusti vsechny testy mini-shopu nad ZIVYMI soubory a commitne.
# NEPOUSTET bez PRIMEHO povoleni Roberta v session, ktera skript spousti (commit guarded api/*.py a webapp/* je nasazeni; api/*.py jde na ostro pri planovanem nasazeni 3:30/12:30, webapp ihned).
# Tabulka miniweb_documents uz v DB je (sql/2026-10-02_miniweb_documents.sql), zadne DDL tady.
set -u
trap '' HUP        # odpojeni terminalu (zavreny telefon, spadle spojeni) nesmi nasazeni useknout v pulce
cd /opt/konfigurator || exit 1
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
K=scripts/2026-10-02_miniweb_pravni_testy
D=$K/nasazeni
OLD=scripts/2026-10-02_miniweb_testy
RUN_ALL=scripts/2026-09-30_karta_produktu_testy/run_all.sh
G="api/miniweb.py api/miniweb_admin.py webapp/miniweb-schvaleni.html"
TESTY="test_miniweb.py test_miniweb_admin.py test_miniweb_poptavka.py test_miniweb_schvaleni.js test_miniweb_shop.py"
TESTY_ZIVE="test_miniweb.py test_miniweb_poptavka.py test_miniweb_admin.py test_qa_miniweb.py test_miniweb_shop.py"
scripts/lock.sh acquire bot5 "api/miniweb.py + api/miniweb_admin.py + webapp/miniweb-schvaleni.html: pravni dokumenty, kontakt ze spolecnosti, poptavka jen firmam" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git reset -q -- $K $OLD 2>/dev/null; git checkout -- $G $RUN_ALL $OLD/test_miniweb.py $OLD/test_miniweb_admin.py $OLD/test_miniweb_poptavka.py $OLD/test_miniweb_schvaleni.js 2>/dev/null; rm -f $OLD/test_miniweb_shop.py; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
trap 'rollback "preruseno signalem (Ctrl-C nebo ukonceni)"' INT TERM
for f in $G $RUN_ALL $OLD/test_miniweb.py $OLD/test_miniweb_admin.py $OLD/test_miniweb_poptavka.py $OLD/test_miniweb_schvaleni.js; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
[ ! -e $OLD/test_miniweb_shop.py ] || abort "$OLD/test_miniweb_shop.py uz existuje (uz nasazeno?)"
git ls-files --error-unmatch sql/2026-10-02_miniweb_documents.sql > /dev/null 2>&1 || abort "migrace miniweb_documents neni v gitu"
timeout 60 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY -c "
import os, pymysql
c = pymysql.connect(host=os.environ['DB_HOST'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], database=os.environ['DB_NAME'], port=int(os.environ.get('DB_PORT', 3306)))
cur = c.cursor(); cur.execute(\"SHOW TABLES LIKE 'miniweb_documents'\"); assert cur.fetchone(), 'tabulka miniweb_documents v DB chybi'" || abort "tabulka miniweb_documents v DB chybi (sql/2026-10-02_miniweb_documents.sql)"
for f in miniweb.py miniweb_admin.py miniweb-schvaleni.html; do patch -p1 --dry-run -s -i $D/$f.patch > /dev/null || abort "patch $f nesedi na zive soubory (nekdo je mezitim zmenil)"; done
for f in miniweb.py miniweb_admin.py miniweb-schvaleni.html; do patch -p1 -s -i $D/$f.patch || rollback "patch $f"; done
for t in $TESTY; do cp $K/$t $OLD/$t; done
$PY -m py_compile api/miniweb.py api/miniweb_admin.py scripts/miniweb_shop.py scripts/miniweb_import.py || rollback "py_compile"
python3 - <<'PY' || rollback "run_all.sh"
p = "scripts/2026-09-30_karta_produktu_testy/run_all.sh"
t = open(p, encoding="utf-8").read()
if "test_miniweb_shop.py" not in t:
    a = '[ $rc -eq 0 ] && echo "VSE OK" || echo "NEKTERY TEST SELHAL"\n'
    assert t.count(a) == 1
    t = t.replace(a, ("systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\\n"
                      "  ${MINIWEB_PY:+--setenv=MINIWEB_PY=$MINIWEB_PY} \\\n"
                      "  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_miniweb_testy/test_miniweb_shop.py || rc=1\n") + a)
    open(p, "w", encoding="utf-8").write(t)
PY
bash -n $RUN_ALL || rollback "syntaxe run_all.sh"
for t in $TESTY_ZIVE; do
  timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY $OLD/$t > /tmp/claude-0/pr_$t.out 2>&1 || { grep -E "^FAIL|Traceback" /tmp/claude-0/pr_$t.out | head -8 | cut -c1-300; rollback "$t"; }
  echo "$t (zive soubory): $(grep VYSLEDEK /tmp/claude-0/pr_$t.out | tail -1 | cut -c1-120)"
done
SNIMKY_DIR=/tmp/claude-0/pr_snimky timeout 600 node $OLD/test_miniweb_schvaleni.js > /tmp/claude-0/pr_schvaleni.out 2>&1 || { grep -E "^FAIL|CHYBA" /tmp/claude-0/pr_schvaleni.out | head -8 | cut -c1-300; rollback "test_miniweb_schvaleni.js"; }
echo "test_miniweb_schvaleni.js (zive soubory): $(grep VYSLEDEK /tmp/claude-0/pr_schvaleni.out | tail -1 | cut -c1-120)"
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "
import app, miniweb, miniweb_admin
assert hasattr(miniweb, '_documents') and hasattr(miniweb_admin, 'doc_rev')
pravidla = sorted(r.rule for r in app.app.url_map.iter_rules() if r.rule.startswith('/api/miniweb') or r.rule.startswith('/api/admin/miniweb'))
assert '/api/miniweb/legal' in pravidla and '/api/miniweb/inquiry' in pravidla, pravidla
print('import app OK, dokumenty a B2B nacteny, trasy mini-shopu:', len(pravidla))" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app / moduly"
git rm -q --ignore-unmatch $K/test_miniweb.py $K/test_miniweb_admin.py $K/test_miniweb_poptavka.py $K/test_miniweb_schvaleni.js $K/test_miniweb_shop.py      # testy se presunuly do $OLD
git add $K scripts/miniweb_shop.py scripts/miniweb_import.py $OLD/test_miniweb_shop.py
BOT_ID=bot5 git commit -q -F - -- $G $RUN_ALL $K $OLD/test_miniweb.py $OLD/test_miniweb_admin.py $OLD/test_miniweb_poptavka.py $OLD/test_miniweb_schvaleni.js $OLD/test_miniweb_shop.py scripts/miniweb_shop.py scripts/miniweb_import.py <<'MSG' || rollback "git commit"
feat(miniweb): pravni dokumenty, kontakt ze spolecnosti a poptavka JEN FIRMAM, skript pro zalozeni a spusteni shopu (bot5)

Robert pres bot3 2026-10-02: slovensky mini-shop se spousti zive, kontakt = Robertovy udaje z nastaveni spolecnosti (bez e-mailu), prodej jen podnikatelum ("vzdy jen firmam").
- pravni dokumenty (terms, privacy, returns, shipping, cookies): tabulka miniweb_documents (migrace uz v DB), import jako draft (klic documents v JSON), schvaleni Robertem na teze strance s rozbalenim
  dlouheho textu, verejne GET /api/miniweb/legal -> documents[{kind,title,body,updated}] jen schvalene, v jazyce shopu; zadna znacka krome zakonneho nazvu prodejce, zastupne znacky [DOPLNIT]/[OVERIT]
  a oznaceni navrhu blokuji schvaleni i vydani
- kontakt shopu: contact_json use_company true = jmeno, adresa a telefon z nastaveni spolecnosti (company_info, jeden zdroj), nikdy e-mail ani web
- poptavka: firma, ICO (CZ a SK 6 az 8 cislic, doplni se na 8), DIC / IC DPH mimo CR (syntaxe SK, CZ a EU, kontrola VIES zatim otevreny bod), zeme (u shopu s jedinou zemi vychozi), potvrzeni podnikatele
  (b2b_confirm); udaje do zpravy v CRM ve tvaru, ktery CRM umi vycist; zadny automaticky e-mail
- scripts/miniweb_shop.py: zalozeni storefrontu (jen draft) a radku shopu, --go-live s podminkami (certifikat, zeme, poptavky, schvaleny katalog, schvalene dokumenty), --take-offline
Testy: cteni 63, import a schvalovani 59, poptavka 62, QA 10, stranka schvalovani 30 (Chromium), skript shopu 28.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-140
