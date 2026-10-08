#!/bin/bash
# Testy typu sestavy (AUTO / STUL_SKLAD) - bot8 2026-10-02. Zadny zapis do ostrych dat.
#   1) backend: skutecny handler nad DOCASNYMI tabulkami (DB prihlaseni pres systemd-run)
#   2) scena: vyber typu v panelu Produktove sestavy (Node vm nad textem z scene.html; kandidat: SCENE_HTML=...)
set -u
cd "$(dirname "$0")/../.." || exit 1
rc=0
echo "== 1) backend ukladani typu"
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  --working-directory=/opt/konfigurator ${PA_API_OVERRIDE:+--setenv=PA_API_OVERRIDE=$PA_API_OVERRIDE} \
  api/venv/bin/python3 scripts/2026-10-02_sestava_typ_testy/test_ulozeni_typu.py 2>&1 | grep -E "CHYBA: [^n]|kontrol OK|CHYB," ; [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
echo "== 2) scena - vyber typu"
node scripts/2026-10-02_sestava_typ_testy/test_scena_vyber_typu.js | tail -1 ; [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
exit $rc
