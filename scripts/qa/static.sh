#!/bin/bash
# QA suita (C) - staticka analyza kodu. Viz scripts/qa/static.py pro
# detaily kontrol. Bezi pres produkcni api/venv (pymysql atd.) - pyflakes
# samotny ma vlastni samostatny venv (scripts/qa/.venv), viz static.py.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec api/venv/bin/python3 scripts/qa/static.py "$@"
