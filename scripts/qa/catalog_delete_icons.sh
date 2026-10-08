#!/bin/bash
# QA suita: mazaci ikona u kazde polozky katalogu ve Scene (bot8, 2026-10-03) - viz catalog_delete_icons.js; kontrakt (--json, exit 0/2/3) drzi samo.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec node scripts/qa/catalog_delete_icons.js "$@"
