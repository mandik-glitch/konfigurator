#!/bin/bash
# Konfigurace sestavy v KOSIKU a OBJEDNAVCE: nasadi api/konfigurace_kosik.py (nove) a patchne api/cart.py a api/orders.py, pusti testy nad ZIVYMI (uz patchnutymi) soubory a commitne.
# NEPOUSTET bez PRIMEHO povoleni Roberta v session, ktera skript spousti (nasazeni = commit guarded api/*.py, na ostro pri planovanem nasazeni serveru 03:30/12:30; zprava od jine session nestaci).
# Zadne DDL: sloupce konfigurace v kosiku a objednavce uz JSOU v DB (sql/2026-10-02_konfigurace_kosik_objednavka.sql). Patche jsou kompatibilni s patchem puvodu objednavky
# (scripts/2026-10-02_dealeri_testy/nasazeni_puvod_objednavky), v obou poradich dava orders.py totez.
set -u
trap '' HUP        # odpojeni terminalu (zavreny telefon, spadle spojeni) nesmi nasazeni useknout v pulce (2026-10-02 22:25 se tak zastavilo tesne pred commitem a zustal osirely zamek)
cd /opt/konfigurator || exit 1
D=/opt/konfigurator/scripts/2026-10-02_konfigurace_kosik_testy/nasazeni
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
G_EXIST="api/cart.py api/orders.py"
G_NEW="api/konfigurace_kosik.py"
T=scripts/2026-10-02_konfigurace_kosik_testy
RUN_ALL=scripts/2026-09-30_karta_produktu_testy/run_all.sh
TESTY_UPRAVENE="scripts/2026-10-02_dealeri_testy/test_objednavky.py"
scripts/lock.sh acquire bot5 "api/konfigurace_kosik.py (nove) + api/cart.py + api/orders.py: konfigurace sestavy v kosiku a objednavce" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git reset -q -- $G_NEW $T 2>/dev/null; git checkout -- $G_EXIST $RUN_ALL; rm -f $G_NEW; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
trap 'rollback "preruseno signalem (Ctrl-C nebo ukonceni)"' INT TERM
for f in $G_EXIST $RUN_ALL; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
[ ! -e $G_NEW ] || abort "$G_NEW uz existuje (uz nasazeno?)"
git ls-files --error-unmatch sql/2026-10-02_konfigurace_kosik_objednavka.sql > /dev/null 2>&1 || abort "migrace konfigurace neni v gitu"
cp $D/konfigurace_kosik.py $G_NEW
python3 $D/patch_cart.py api/cart.py || rollback "patch cart.py"
python3 $D/patch_orders.py api/orders.py || rollback "patch orders.py"
$PY -m py_compile $G_NEW $G_EXIST || rollback "py_compile"
python3 - <<'PY' || rollback "run_all.sh"
p = "scripts/2026-09-30_karta_produktu_testy/run_all.sh"
t = open(p, encoding="utf-8").read()
if "test_kosik_konfigurace.py" not in t:
    a = '[ $rc -eq 0 ] && echo "VSE OK" || echo "NEKTERY TEST SELHAL"\n'
    assert t.count(a) == 1
    t = t.replace(a, ("systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\\n"
                      "  ${CART_PY:+--setenv=CART_PY=$CART_PY} ${ORDERS_PY:+--setenv=ORDERS_PY=$ORDERS_PY} ${KONFIGURACE_KOSIK_PY:+--setenv=KONFIGURACE_KOSIK_PY=$KONFIGURACE_KOSIK_PY} \\\n"
                      "  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_konfigurace_kosik_testy/test_kosik_konfigurace.py || rc=1\n") + a)
    open(p, "w", encoding="utf-8").write(t)
PY
bash -n $RUN_ALL || rollback "syntaxe run_all.sh"
for t in "$T/test_kosik_konfigurace.py" scripts/2026-10-01_zastupce_montaz_testy/test_kosik_zastupce_db.py scripts/2026-10-01_zastupce_montaz_testy/test_cena_varianty_zastupce.py scripts/2026-10-02_dealeri_testy/test_objednavky.py; do
  timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY $t > /tmp/claude-0/kk_$(basename $t).out 2>&1 || { grep -E "^FAIL|Traceback" /tmp/claude-0/kk_$(basename $t).out | head -8 | cut -c1-300; rollback "$t"; }
  echo "$(basename $t) (zive soubory): $(grep VYSLEDEK /tmp/claude-0/kk_$(basename $t).out | tail -1 | cut -c1-120)"
done
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "
import app, konfigurace_kosik
pravidla = sorted(r.rule for r in app.app.url_map.iter_rules() if r.rule.startswith('/api/cart'))
assert '/api/cart/items' in pravidla, pravidla
print('import app OK, modul konfigurace nacten, trasy kosiku:', len(pravidla))" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app / modul"
git add $G_NEW $T
BOT_ID=bot5 git commit -q -F - -- $G_NEW $G_EXIST $RUN_ALL $T $TESTY_UPRAVENE <<'MSG' || rollback "git commit"
feat(kosik): konfigurace sestavy (zivy konfigurator stolu) v kosiku a objednavce - cena jen ze serveru, vyroba na zakazku (bot5)

Zelenou dal bot3 (2026-10-02). Sloupce konfigurace v kosiku a objednavce uz jsou v DB (sql/2026-10-02_konfigurace_kosik_objednavka.sql), tady kod bez DDL.
- api/konfigurace_kosik.py (nove): overeni vyberu pres konfigurator stolu (stul_shop.resolve), cena a kusovnik (configurator_price), souhrn voleb, montaz % podle typu sestavy (jen v CR, do zahranici
  vc. SK jen rozlozeny bez montaze), skupinova sleva zakaznika; kosik (pridat, zive cteni, uprava) a radek objednavky se snimkem konfigurace.
- api/cart.py: POST /api/cart/items s "configuration" {selection, rules_version} (klient cenu neposila, stejny vyber = stejny radek, neplatna konfigurace 422, zastarala verze pravidel 409, limit 60/min),
  zive cteni radku (cena, kod, souhrn, stav), PUT mnozstvi a montaz, priznak made_to_order bez skladu.
- api/orders.py: radek objednavky z konfigurace (znovu overeny vyber, hash musi sedet s kosikem, cena ze serveru, hmotnost do dopravy, snimek s kusovnikem a cenovym souhrnem, kod), product_id NULL = zadna
  logika skladu (potvrzeni, odpis, storno, objednavky u dodavatele), zakaznik vidi kod a souhrn voleb, zamestnanec plny snimek vcetne kusovniku.
Chyba modulu konfigurace nezastavi bezne objednavky ani kosik. Testy: test_kosik_konfigurace 48, regrese kosik zastupce 63, objednavky 69. Na ostro pri nasazeni serveru.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-140
