#!/usr/bin/env python3
"""Pomocny LOKALNI server pro prohlizecovy test stranky konfiguratoru stolu (bez Flasku a bez prihlaseni - jen na 127.0.0.1).
Servíruje webapp/ jako staticke soubory a odpovida na /api/stul/konfigurace + /api/stul/model.glb skutecnym Pythonem
(api/stul_konfigurator.py + api/stul_glb.py). Cena = None (bez DB). NIKDY nespoustet na verejne adrese."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qsl

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_glb as G  # noqa: E402
import stul_konfigurator as S  # noqa: E402

box_lo, box_hi = S.glb_bbox("product_4930")
if box_hi[1] - box_lo[1] > 1000:
    S.BBOX_PREPIS["product_4930"] = ([-2279.2, -950.4, 627.4], [-1714.2, -367.3, 907.5])
WEB = os.path.abspath(os.environ.get("STUL_WEB") or os.path.join(REPO, "webapp"))      # STUL_WEB = jiny koren statiky (vyvoj mimo zivy web)
TYPY = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".json": "application/json"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/stul/konfigurace":
                par = S.parametry_z_dotazu(dict(parse_qsl(u.query)))
                out = S.odpoved(par)
                out["cena"] = {"bez_dph": 1000, "s_dph": 1210, "sazba_dph": 21, "mena": "CZK", "kusovnik": {   # ukazkova data pro test vykresleni (cena z DB tu neni)
                    "radky": [{"nazev": "Profil 30x30mm (alu)", "rozmer": "1340 mm", "mnozstvi": 5, "cena_ks": 100, "celkem": 500},
                              {"nazev": "Laminovaná dřevotříska 18mm [Laminodeska.SEDA.18] (produkt)", "rozmer": "800 × 1400 mm", "mnozstvi": 1, "cena_ks": 400, "celkem": 400}],
                    "prace": [{"nazev": "Spoje profilů", "rozmer": None, "mnozstvi": 2, "cena_ks": 50, "celkem": 100}],
                    "celkem": {"bez_dph": 1000, "dph": 210, "s_dph": 1210, "sazba_dph": 21},
                    "montaz": {"pct": 20.0, "czk": 200, "poznamka": "volitelná služba, není v ceně"}, "hmotnost_kg": 12.5, "varovani": []}}
                out["vodici"] = G.vodici(par, out)
                out["hash"] = G.kanonicky_hash(par)
                out["kod"] = "STL-" + out["hash"][:6].upper()
                out["model_url"] = "/api/stul/model.glb" + ("?" + u.query if u.query else "")
                return self._send(200, json.dumps(out).encode(), "application/json")
            if u.path == "/api/stul/model.glb":
                h, data = G.model_pro_parametry(S.parametry_z_dotazu(dict(parse_qsl(u.query))))
                return self._send(200, data, "model/gltf-binary")
        except S.StulChyba as e:
            return self._send(400, json.dumps({"error": str(e), "kod": e.kod}).encode(), "application/json")
        path = os.path.normpath(os.path.join(WEB, u.path.lstrip("/")))
        if path.startswith(WEB) and os.path.isfile(path):
            with open(path, "rb") as f:
                return self._send(200, f.read(), TYPY.get(os.path.splitext(path)[1], "application/octet-stream"))
        return self._send(404, b"not found", "text/plain")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
