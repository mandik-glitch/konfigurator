# -*- coding: utf-8 -*-
"""Spolecne cesty testu 3D nabidky (scripts/2026-10-02_v3d_testy/).

REPO    koren repa (scripts/2026-10-02_v3d_testy -> koren; na serveru /opt/konfigurator; $V3D_TEST_REPO = kandidatni strom)
FIX     fixtures/ vedle testu (nativni export nabidky 103, synteticky GLB, ctx 7 Vandr karet)
OUT     vystupy testu (build 7 karet, docasne GLB) - MIMO repo: $V3D_TEST_OUT nebo <tmp>/v3d_testy
KATALOG webapp/katalog (jen CTENI: katalogove GLB Vandr karet); $V3D_TEST_KATALOG prepise
Testy nikdy nepisou do repa ani do DB (DB je vzdy atrapa, viz _fakes.py).
"""
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("V3D_TEST_REPO") or os.path.dirname(os.path.dirname(HERE))      # V3D_TEST_REPO = kandidatni strom (mutacni kontroly, _mutace_kontrola_route.py)
FIX = os.path.join(HERE, "fixtures")
OUT = os.environ.get("V3D_TEST_OUT") or os.path.join(tempfile.gettempdir(), "v3d_testy")
KATALOG = os.environ.get("V3D_TEST_KATALOG") or os.path.join(REPO, "webapp", "katalog")
CONTENT_FILES = os.environ.get("V3D_TEST_CONTENT_FILES") or os.path.join(REPO, "webapp", "content-files")
NODE_MODULES = os.environ.get("V3D_NODE_MODULES") or "/opt/konfigurator/node_modules"
BLENDER = "/opt/blender-5.2/blender"
KARTY = ("4453", "4474", "4594", "4910", "4917", "4918", "4921")
os.makedirs(OUT, exist_ok=True)
# knihovna materialu (scripts/_render_prirazeni_lib.py): v repu je vedle scripts/v3d; ve stavebnim stromu bez ni
# se vezme z provozniho repa (jen cteni)
if not os.path.isfile(os.path.join(REPO, "scripts", "_render_prirazeni_lib.py")):
    os.environ.setdefault("V3D_LIB_DIR", "/opt/konfigurator/scripts")
