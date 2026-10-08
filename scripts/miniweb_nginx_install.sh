#!/usr/bin/env bash
# ROOT krok pripojeni verejneho mini-shopu (bot16, 2026-10-03): zapis do /etc/nginx + reload (sandbox to botum blokuje, spousti Robert).
#   cd /opt/konfigurator && bash scripts/miniweb_nginx_install.sh baliace-stoly.top            # noindex (vychozi)
#   cd /opt/konfigurator && bash scripts/miniweb_nginx_install.sh baliace-stoly.top --index sk   # SEO rezim: hezke adresy, meta/sitemap/robots z Flasku (api/miniweb_seo.py MUSI byt nasazene), indexuje se jen live shop
# Co dela: 1) Origin CA cert + klic -> /etc/nginx/ssl/miniweb-origin-ca.{pem,key}  2) snippet se skutecnou IP navstevniku za Cloudflare
# (rozsahy z cloudflare.com/ips-*)  3) vhost z scripts/gen_miniweb_vhost.py -> sites-available/miniweb-<domena> + symlink
# 4) nginx -t; pri chybe se vsechno VRATI (puvodni soubory) a nginx se nereloaduje  5) reload  6) kontrola na localhostu.
set -euo pipefail
DOMAIN="${1:?pouziti: miniweb_nginx_install.sh <domena> [--index]}"
INDEX_ARG=""; [ "${2:-}" = "--index" ] && INDEX_ARG="--index --lang ${3:?pouziti: miniweb_nginx_install.sh <domena> --index <jazyk, napr. sk, en, de, hu>}"
cd "$(dirname "$0")/.."
# cesty jdou prepsat jen pro test (NGINX_ROOT, CA_DIR, TEST_CMD, RELOAD_CMD, CF_IPS_CMD); ostry beh pouziva vychozi hodnoty
NGX="${NGINX_ROOT:-/etc/nginx}"; CA="${CA_DIR:-private-files/cloudflare-origin-ca}"
SSL=$NGX/ssl; AV=$NGX/sites-available/miniweb-$DOMAIN; EN=$NGX/sites-enabled/miniweb-$DOMAIN; SNIP=$NGX/snippets/cloudflare-realip.conf
TEST_CMD="${TEST_CMD:-nginx -t}"; RELOAD_CMD="${RELOAD_CMD:-systemctl reload nginx}"
for f in "$CA/miniweb-origin-ca.pem" "$CA/miniweb-origin-ca.key"; do [ -s "$f" ] || { echo "CHYBI $f - nejdriv: scripts/miniweb_domena.py cert $DOMAIN --apply"; exit 2; }; done
BK=$(mktemp -d); for f in "$SSL/miniweb-origin-ca.pem" "$SSL/miniweb-origin-ca.key" "$AV" "$SNIP"; do [ -e "$f" ] && cp -a "$f" "$BK/" || true; done
rollback() { echo "CHYBA - vracim puvodni stav"; for f in "$SSL/miniweb-origin-ca.pem" "$SSL/miniweb-origin-ca.key" "$AV" "$SNIP"; do b="$BK/$(basename "$f")"; if [ -e "$b" ]; then cp -a "$b" "$f"; else rm -f "$f"; fi; done; rm -f "$EN"; exit 1; }
trap rollback ERR
if [ -n "$INDEX_ARG" ] && [ -z "${NGINX_ROOT:-}" ]; then   # SEO rezim posila stranky do Flasku - bez nasazeneho api/miniweb_seo.py by web prestal fungovat
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 --unix-socket api/konfigurator.sock -H "Host: $DOMAIN" http://localhost/api/miniweb/seo/robots.txt || true)
  [ "$code" = "200" ] || { echo "STOP: Flask zatim nema SEO vrstvu (/api/miniweb/seo/robots.txt -> $code). Nejdriv planovane nasazeni api (12:30 / 3:30), pak znovu."; exit 3; }
fi
install -d -m 755 "$SSL" "$NGX/snippets" "$NGX/sites-available" "$NGX/sites-enabled"
install -m 644 "$CA/miniweb-origin-ca.pem" "$SSL/miniweb-origin-ca.pem"
install -m 600 "$CA/miniweb-origin-ca.key" "$SSL/miniweb-origin-ca.key"
# skutecna IP za Cloudflare (BEZ toho by se limity aplikace pocitaly na IP Cloudflare uzlu)
cf_ips() { if [ -n "${CF_IPS_CMD:-}" ]; then $CF_IPS_CMD; else for u in ips-v4 ips-v6; do curl -fsS --max-time 20 "https://www.cloudflare.com/$u"; echo; done; fi; }
{ echo "# generovano miniweb_nginx_install.sh $(date -u +%F) - rozsahy Cloudflare"; cf_ips | sed '/^$/d; s/^/set_real_ip_from /; s/$/;/'; echo "real_ip_header CF-Connecting-IP;"; echo "real_ip_recursive off;"; } > "$SNIP.new"
[ "$(grep -c '^set_real_ip_from' "$SNIP.new")" -ge 10 ] || { echo "seznam IP Cloudflare se nenacetl"; rm -f "$SNIP.new"; false; }
mv "$SNIP.new" "$SNIP"
api/venv/bin/python3 scripts/gen_miniweb_vhost.py "$DOMAIN" $INDEX_ARG --out "$AV"
if [ -n "${NGINX_ROOT:-}" ]; then sed -i "s#/etc/nginx/#$NGX/#g" "$AV"; fi   # jen test
ln -sf "$AV" "$EN"
$TEST_CMD
trap - ERR
$RELOAD_CMD
echo "== nginx nacten. Kontrola na localhostu (mimo DNS):"
if [ -z "${NGINX_ROOT:-}" ]; then for p in / /miniweb/miniweb.js /robots.txt /product.html /miniweb/demo-api.js; do printf '%-28s ' "$p"; curl -sk --resolve "$DOMAIN:443:127.0.0.1" -o /dev/null -w '%{http_code}\n' "https://$DOMAIN$p"; done; fi
echo "(ocekavano: 200 200 200(noindex) 404 404)"
echo "Dalsi krok: api/venv/bin/python3 scripts/miniweb_domena.py overit $DOMAIN --origin"
