#!/bin/bash
# Spusti GUI Blender dilny. Ulozenou dilnu predava Blenderu na PRIKAZOVE
# RADCE - otevirat ji az uvnitr gui_setup.py pres open_mainfile NELZE,
# protoze to ukonci zbytek skriptu a autosave se nezaregistruje
# (Robert 2026-09-09: "proc se nerendovalo to co mam ve scene v dilne?").
DILNA=/opt/konfigurator/private-files/blender-renders/vps_dilna.blend
SETUP="${1:-/opt/konfigurator/scripts/2026-09-09_vps_dilna/gui_setup.py}"
# Nejnovejsi /opt/blender-<verze> (stejna logika jako _najdi_blender v api/blender_render.py).
BLENDER=$(ls -d /opt/blender-[0-9]*/blender 2>/dev/null | sort -V | tail -1)
if [ -f "$DILNA" ]; then
  exec "$BLENDER" "$DILNA" --python "$SETUP"
else
  exec "$BLENDER" --python "$SETUP"
fi
