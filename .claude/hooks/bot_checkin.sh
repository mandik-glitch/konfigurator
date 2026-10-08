#!/bin/bash
# bot3, 2026-09-12 (Robert: "potrebujeme aby se tam aktualizovalo vice...
# poslal zpravu apd" - checkin jen pri git commitu/render byl moc hrubozrny,
# mezi commity klidne uplynou desitky minut skutecne prace). PostToolUse
# hook s matcher "*" - fires na KAZDE pouziti nastroje (Bash/Edit/Read/
# SendMessage/...), ne jen na commit. Cte JSON na stdin (Claude Code hook
# konvence), vytahne tool_name, posle checkin s BOT_ID z prostredi.
#
# Async (nastaveno v .claude/settings.json "async": true) - nesmi
# zpomalit/zablokovat bota jen kvuli tomuhle vedlejsimu mechanismu.
# Tichy fail vsude - chybejici BOT_ID/network chyba/cokoli nema shodit
# tool call, ktery hook spustil.

BOT_ID="${BOT_ID:-}"
[ -z "$BOT_ID" ] && exit 0

INPUT=$(cat)
# Robert 2026-09-12 ("pridej sloupec jmeno souboru"): file_path je jen u
# nastroju, co se souborem primo pracuji (Edit/Write/Read/NotebookEdit) -
# u Bash/SendMessage/atd. zustane prazdne, nehadat ho z command retezce.
TOOL_A_SOUBOR=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    tool = data.get('tool_name', '')
    ti = data.get('tool_input') or {}
    soubor = ti.get('file_path') or ti.get('path') or ''
    print(tool)
    print(soubor)
except Exception:
    pass
" "$INPUT" 2>/dev/null)
TOOL=$(echo "$TOOL_A_SOUBOR" | sed -n '1p')
SOUBOR=$(echo "$TOOL_A_SOUBOR" | sed -n '2p')
[ -z "$TOOL" ] && exit 0

ENC_CINNOST=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "pouziva: $TOOL" 2>/dev/null)
ENC_SOUBOR=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$SOUBOR" 2>/dev/null)
curl -s --max-time 2 -o /dev/null \
  "http://127.0.0.1:8090/api/bots/checkin?bot_id=${BOT_ID}&cinnost=${ENC_CINNOST}&soubor=${ENC_SOUBOR}" \
  >/dev/null 2>&1
exit 0
