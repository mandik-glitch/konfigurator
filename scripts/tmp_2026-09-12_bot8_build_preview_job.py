"""Postavi job.json pro jednosnimkovy preview nove serie AA (K-075),
BEZ zapisu do product_assemblies - pouziva stejne resolve_parts()/
compute_front_azimuth_deg()/TT konstanty jako 2026-09-09_turntable_job.py,
jen misto cteni DB assembly dostane raw parts primo z pipeline vystupu.
"""
import importlib.util
import json
import math
import os
import uuid

REPO = "/opt/konfigurator"
spec = importlib.util.spec_from_file_location("tj", os.path.join(REPO, "scripts", "2026-09-09_turntable_job.py"))
tj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tj)

with open(os.path.join(REPO, "scripts", "tmp_2026-09-12_serie_AA_K075_parts.json")) as f:
    raw_parts = json.load(f)

job_id = uuid.uuid4().hex
out_dir = os.path.join(tj.REPO if hasattr(tj, "REPO") else REPO, "..", "render_out_preview_" + job_id)
out_dir = os.path.abspath(out_dir)
os.makedirs(out_dir, exist_ok=True)

conn = tj._connect()
try:
    with conn.cursor() as cur:
        parts, missing = tj.resolve_parts(cur, raw_parts)
finally:
    conn.close()

if missing:
    raise SystemExit("Chybejici dily v katalogu: %s" % missing)

front = tj.compute_front_azimuth_deg(raw_parts)
if front is None:
    front = tj.TT["FRONT_AZIMUTH_DEG"]

azimuths = tj.azimuths_for_front(front)
elev = list(tj.TT["ELEVATIONS"])
el0 = 0 if 0 in elev else elev[len(elev) // 2]
front_mod = front % 360


def _odchylka(az):
    d = abs((az % 360) - front_mod) % 360
    return min(d, 360 - d)


az0 = min(azimuths, key=_odchylka)

job = {
    "assembly_id": 0,
    "assembly_name": "PREVIEW serie AA K-075 (neuloz eno, jen nahled)",
    "shop_product_id": None,
    "front_azimuth_deg": front,
    "front_source": "role-tagy" if front is not None else "fallback",
    "parts": parts,
    "missing_parts": [],
    "elevations": [el0],
    "azimuths": [az0],
    "tiers": {str(k): list(v) for k, v in tj.TT["TIERS"].items()},
    "stills": [],
    "fov_deg": tj.TT_FOV,
    "margin": tj.TT_MARGIN,
    "still_margin": tj.TT_STILL_MARGIN,
    "shadow_pad": tj.TT_SHADOW_PAD,
    "shadow_fade": tj.TT_SHADOW_FADE,
    "key_dir": tj.TT_KEY_DIR,
    "bg_color": tj.TT_BG_COLOR,
    "bg_color_bottom": tj.TT_BG_COLOR_BOTTOM,
    "jpeg_quality": tj.TT_JPEG_Q,
    "samples": tj._vzorky_z_nastaveni(),
    "out_dir": out_dir,
    "expected_frames": len(tj.TT["TIERS"]),
    "karoserie_odraz": {"ok": False, "reason": "preview bez karoserie"},
    "podlaha_obrys": {"ok": False, "reason": "preview bez karoserie"},
}

job_path = os.path.join(REPO, "scripts", "tmp_2026-09-12_serie_AA_preview_job.json")
with open(job_path, "w", encoding="utf-8") as f:
    json.dump(job, f, ensure_ascii=False)

print("job JSON:", job_path)
print("out_dir :", out_dir)
print("dilu    :", len(parts))
print("front_azimuth_deg:", front, "el0:", el0, "az0:", az0)
print("\nSpusteni (CPU, lokalne):")
print("  /opt/blender-5.2/blender -b -noaudio -P %s/api/blender_render_turntable.py -- %s"
      % (REPO, job_path))
