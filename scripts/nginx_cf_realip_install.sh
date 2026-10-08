#!/usr/bin/env bash
# ROOT krok (bot16, 2026-10-03): skutecna IP navstevnika za Cloudflare u AUTOVYCH mini-webu (storefront-* vhosty z gen_storefront_vhosts.py).
#   cd /opt/konfigurator && bash scripts/nginx_cf_realip_install.sh
# Nalez: bez set_real_ip_from + CF-Connecting-IP vidi aplikace misto navstevnika IP Cloudflare uzlu (X-Real-IP = $remote_addr) a vsechna omezeni
# podle IP (login, poptavky, kosik, rate limity) se sdili mezi nesouvisejicimi navstevniky. Skript: 1) snippet s rozsahy Cloudflare
# 2) znovu vygeneruje storefront-* vhosty (gen_storefront_vhosts.py, ktery ted snippet vklada) 3) nginx -t, pri chybe VRATI puvodni soubory 4) reload.
set -euo pipefail
cd "$(dirname "$0")/.."
NGX="${NGINX_ROOT:-/etc/nginx}"; SNIP=$NGX/snippets/cloudflare-realip.conf; AV=$NGX/sites-available
TEST_CMD="${TEST_CMD:-nginx -t}"; RELOAD_CMD="${RELOAD_CMD:-systemctl reload nginx}"; GEN_CMD="${GEN_CMD:-api/venv/bin/python3 scripts/gen_storefront_vhosts.py --write}"
BK=$(mktemp -d); mkdir -p "$BK/av"; cp -a "$AV"/storefront-* "$BK/av/" 2>/dev/null || true; [ -e "$SNIP" ] && cp -a "$SNIP" "$BK/" || true
rollback() { echo "CHYBA - vracim puvodni stav"; rm -f "$AV"/storefront-*; cp -a "$BK/av/." "$AV/" 2>/dev/null || true; if [ -e "$BK/cloudflare-realip.conf" ]; then cp -a "$BK/cloudflare-realip.conf" "$SNIP"; else rm -f "$SNIP"; fi; exit 1; }
trap rollback ERR
install -d -m 755 "$NGX/snippets"
cf_ips() { if [ -n "${CF_IPS_CMD:-}" ]; then $CF_IPS_CMD; else for u in ips-v4 ips-v6; do curl -fsS --max-time 20 "https://www.cloudflare.com/$u"; echo; done; fi; }
{ echo "# generovano nginx_cf_realip_install.sh $(date -u +%F) - rozsahy Cloudflare"; cf_ips | sed '/^$/d; s/^/set_real_ip_from /; s/$/;/'; echo "real_ip_header CF-Connecting-IP;"; echo "real_ip_recursive off;"; } > "$SNIP.new"
[ "$(grep -c '^set_real_ip_from' "$SNIP.new")" -ge 10 ] || { echo "seznam IP Cloudflare se nenacetl"; rm -f "$SNIP.new"; false; }
mv "$SNIP.new" "$SNIP"
$GEN_CMD
$TEST_CMD
trap - ERR
$RELOAD_CMD
echo "== hotovo: autove storefront vhosty ted vidi skutecnou IP navstevnika (nginx nacten)."
