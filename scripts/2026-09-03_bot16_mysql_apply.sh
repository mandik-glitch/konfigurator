#!/bin/bash
# Bezpecny wrapper pro aplikaci SQL souboru do DB konfiguratoru (bot16, 2026-09-03).
# Robert: "pokud klasifikator zamitne velky zasah do DB, automaticky jej musime
# rozdelit na mensi casti a aplikovat postupne" - pouzij tenhle wrapper na
# kazdou cast/soubor zvlast, misto jednoho velkeho `mysql ... < big.sql`.
#
# Pouziti: scripts/2026-09-03_bot16_mysql_apply.sh <soubor.sql>
# Credentials se ctou z api/.env (DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME),
# heslo se predava pres MYSQL_PWD (nezobrazi se v `ps`/historii), nikdy se
# nevypisuje na stdout/stderr.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/api/.env"
SQL_FILE="$1"

if [ -z "$SQL_FILE" ] || [ ! -f "$SQL_FILE" ]; then
  echo "usage: $0 <soubor.sql>" >&2
  exit 1
fi

while IFS='=' read -r k v; do
  case "$k" in
    ''|'#'*) continue ;;
  esac
  v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
  case "$k" in
    DB_HOST) DB_HOST="$v" ;;
    DB_PORT) DB_PORT="$v" ;;
    DB_USER) DB_USER="$v" ;;
    DB_PASSWORD) DB_PASSWORD="$v" ;;
    DB_NAME) DB_NAME="$v" ;;
  esac
done < "$ENV_FILE"

export MYSQL_PWD="$DB_PASSWORD"
mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" "$DB_NAME" < "$SQL_FILE"
echo "OK: aplikovano $SQL_FILE"
