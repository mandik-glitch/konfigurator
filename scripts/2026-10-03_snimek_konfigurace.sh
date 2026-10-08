#!/bin/bash
# Obrazek VYCHOZI konfigurace konfigurovatelneho produktu (napr. stul, karta 4934) pro prehled mini-shopu / nabidku (bot10, 2026-10-03).
# Cte jen VEREJNE API (schema -> resolve -> GLB, nic nezapisuje do DB), pak headless snimek stejnym prohlizecem jako web.
#
#   scripts/2026-10-03_snimek_konfigurace.sh <product_id> <vystup.jpg|png> [parametry pro 2026-10-03_snimek_modelu.js]
#   priklad: scripts/2026-10-03_snimek_konfigurace.sh 4934 webapp/miniweb/img/produkt-4934.jpg --w 1200 --h 900 --pozadi '#0f1722'
#
# Vychozi: 3/4 pohled shora (iso), tmava barva pozadi, AO stredni, bez kot a bez HUD, hlinik "puvodni", HDRI tlumene.
# Stav webu se muze zmenit (nova pravidla/recept): obrazek je pak treba VYROBIT ZNOVU timhle skriptem.
# Promenne: SNIMEK_HOST (vychozi autovestavby.logiman.cz; spojeni jde pres 127.0.0.1:443, ne ven).
set -euo pipefail
[ $# -ge 2 ] || { echo "pouziti: $0 <product_id> <vystup.jpg|png> [parametry snimek_modelu.js]" >&2; exit 2; }
PID="$1"; OUT="$2"; shift 2
case "$PID" in ''|*[!0-9]*) echo "product_id musi byt cislo" >&2; exit 2;; esac
HOST="${SNIMEK_HOST:-autovestavby.logiman.cz}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -f "$TMP/schema.json" "$TMP/body.json" "$TMP/res.json" "$TMP/model.glb" "$TMP/poll.json"; rmdir "$TMP" 2>/dev/null || true' EXIT
api() { curl -sk --resolve "$HOST:443:127.0.0.1" -m 90 -f "$@"; }

api "https://$HOST/api/shop/products/$PID/configurator" -o "$TMP/schema.json" || { echo "CHYBA: schema produktu $PID nedostupne (neni konfigurovatelny?)" >&2; exit 3; }
python3 - "$TMP" "$PID" <<'EOF'
import json, sys
tmp, pid = sys.argv[1], int(sys.argv[2])
d = json.load(open(tmp + '/schema.json'))
json.dump({"product_id": pid, "selection": d["default_selection"], "rules_version": d["rules_version"], "price": "hidden"}, open(tmp + '/body.json', 'w'))
EOF
api -H 'Content-Type: application/json' -X POST "https://$HOST/api/shop/configurator/resolve" --data @"$TMP/body.json" -o "$TMP/res.json" || { echo "CHYBA: resolve selhal" >&2; exit 3; }
read -r STAV URL HASH < <(python3 - "$TMP/res.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1])); m = d.get("model") or {}
print(m.get("stav", ""), m.get("url") or "-", d.get("hash") or "-")
EOF
)
# model se muze stavet na pozadi: pockat max 90 s
for i in $(seq 1 45); do
  [ "$STAV" = "hotovo" ] && break
  [ "$STAV" = "chyba" ] && { echo "CHYBA: server nepostavil model (stav=chyba)" >&2; exit 3; }
  sleep 2
  api "https://$HOST/api/shop/configurator/model/$HASH" -o "$TMP/poll.json" || continue
  read -r STAV URL < <(python3 - "$TMP/poll.json" <<'EOF'
import json, sys
m = (json.load(open(sys.argv[1])).get("model") or {})
print(m.get("stav", ""), m.get("url") or "-")
EOF
)
done
[ "$STAV" = "hotovo" ] && [ "$URL" != "-" ] || { echo "CHYBA: model neni hotovy (stav=$STAV)" >&2; exit 3; }
api "https://$HOST$URL" -o "$TMP/model.glb" || { echo "CHYBA: GLB se nepodarilo stahnout" >&2; exit 3; }
node "$HERE/2026-10-03_snimek_modelu.js" --glb "$TMP/model.glb" --out "$OUT" "$@"
