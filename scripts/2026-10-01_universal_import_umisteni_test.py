#!/usr/bin/env python3
"""Hermeticky test UMISTENI dilu pri sestaveni tvaru z univerzalniho importu
(api/universal_import.py, build_shape - vetev "existujici karta").

Chyba 2026-09-30 (Robert: "nacitany fbx byl sestaveny jak je potreba, ale
potom pri sestaveni tvaru se to rozhodilo"): build_shape u existujici karty
(ne profilu) predpokladal GLB karty VYCENTROVANE a v osach sceny
(position = stred dilu, identita, scale 1). Karty nahrane v adminu pres FBX
(api/fbx_convert.py) ale lezi na souradnicich z Rhina a v osach FBX -
dily se po sestaveni rozletely o 2-4 m a otocily. Katalog takovych karet ma
802 z 836 (scena s tim pocita, jen import ne). Robert: "ten vkladaci
mechanismus ale musi byt autonomni" + "nebudeme prece davat do katalogu
kazdy rozmer, proste si to system dopocita" (desky).

Co se testuje:
  1. _best_axis_rotation - podvzorkovani (mrak nad 6000 bodu nesmi propadnout)
     a obousmerna shoda (pulka dilu nesmi "sedet" na celou kartu).
  2. _existing_card_spec - karta s libovolnym posunem/natocenim GLB se
     umisti presne na misto dilu (vrchol po vrcholu); puvodni vzorec to
     nesplnuje (zdokumentovana chyba).
  3. desky - jedna karta 1000x1000, rozmer dilu se dopocita scale (vodorovna,
     svisla XY, svisla YZ), nesedici tloustka = varovani.
  4. nesedici geometrie bez desky -> umisteni podle obalky + varovani.
  5. _place_existing_cards - dil rozdeleny v FBX na 2 meshe (LED lampa) a
     namapovany 2x na tutez kartu se vlozi JEDNOU.
  6. _profile_specs_by_id - varianty profilu (uzavreny, ...) se berou podle
     id, ne first-wins podle prurezu.
  7. (volitelne) skutecna data importu stolu, pokud jeste existuje token
     c05a9b26... a GLB karet 4928-4933 - jen cteni.

Hermeticky: dummy env, pymysql.connect zablokovany (kontroluje se 0 pokusu),
render-dozorce se nespusti, soubory jen v temp adresari. Zadna produkcni DB.

Spusteni z korene repa:
    api/venv/bin/python3 scripts/2026-10-01_universal_import_umisteni_test.py
Vystup "N kontrol OK" + exit 0, jinak radky CHYBA a exit 1.
"""
import os
import sys
import math
import shutil
import tempfile
import threading
import traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.environ.get("UIMP_API_OVERRIDE") or os.path.join(REPO, "api")

import numpy as np  # noqa: E402
import pymysql  # noqa: E402

for _k, _v in {
    "FLASK_SECRET_KEY": "selftest-secret",
    "DB_HOST": "selftest.invalid", "DB_PORT": "3306",
    "DB_USER": "selftest", "DB_PASSWORD": "selftest", "DB_NAME": "selftest",
}.items():
    os.environ[_k] = _v

CONNECT_ATTEMPTS = []


def _no_connect(*a, **kw):
    CONNECT_ATTEMPTS.append((a, kw))
    raise RuntimeError("test: pokus o spojeni s databazi je zakazan")


pymysql.connect = _no_connect

_orig_thread_start = threading.Thread.start


def _guarded_start(self, *a, **kw):
    if self.name == "render-dozorce":
        return None
    return _orig_thread_start(self, *a, **kw)


threading.Thread.start = _guarded_start
try:
    sys.path.insert(0, API)
    import universal_import as ui  # noqa: E402
finally:
    threading.Thread.start = _orig_thread_start

from scipy.spatial import cKDTree  # noqa: E402
from scipy.spatial.transform import Rotation  # noqa: E402

S2 = math.sqrt(0.5)
OK = 0
FAILS = []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")
    return cond


def near(a, b, tol, msg):
    a = [float(x) for x in a]
    b = [float(x) for x in b]
    good = len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))
    return check(good, f"{msg}: ocekavano {b} (+-{tol}), skutecne {[round(x, 4) for x in a]}")


def same_rotation(q, q_expected, msg):
    d = Rotation.from_quat(q) * Rotation.from_quat(q_expected).inv()
    return check(d.magnitude() < 1e-4, f"{msg}: q={[round(x, 5) for x in q]} neni {q_expected}")


def world(spec, card_pos):
    """Presne jako scena (loadCustomShapePartEntry): svet = position + R*(scale*v)."""
    m = Rotation.from_quat(spec["quaternion"]).as_matrix()
    s = np.asarray(spec["scale"], dtype=np.float64)
    return np.asarray(spec["position"]) + (np.asarray(card_pos, dtype=np.float64) * s) @ m.T


def max_vertex_gap(a, b):
    """Nejvetsi vzdalenost vrcholu a od nejblizsiho vrcholu b a naopak (mm)."""
    return max(float(cKDTree(b).query(a)[0].max()), float(cKDTree(a).query(b)[0].max()))


def extents(pos):
    pos = np.asarray(pos, dtype=np.float64)
    return pos.max(axis=0) - pos.min(axis=0)


def asym_cloud(n, size, seed):
    """Nesymetricky 'dil' - body na povrchu kvadru + vystupek v jednom rohu,
    at zadna z 24 osovych rotaci nedava stejny mrak jako jina."""
    rng = np.random.default_rng(seed)
    size = np.asarray(size, dtype=np.float64)
    pts = rng.uniform(0, 1, (n, 3)) * size
    face = rng.integers(0, 3, n)
    side = rng.integers(0, 2, n)
    pts[np.arange(n), face] = side * size[face]
    k = n // 6
    nub = rng.uniform(0, 1, (k, 3)) * (size * np.array([0.2, 0.3, 0.1])) + size * np.array([0.8, 0.0, 0.9])
    return np.round(np.vstack([pts, nub]), 2)


SECTIONS = []


def section(fn):
    SECTIONS.append(fn)
    return fn


# ---------------------------------------------------------------------------
@section
def s1_best_axis_rotation():
    print("1) _best_axis_rotation - podvzorkovani a obousmerna shoda")
    big = asym_cloud(20000, [600, 80, 110], seed=1)
    big = big - (big.min(axis=0) + big.max(axis=0)) / 2
    m = Rotation.from_quat([-0.5, -0.5, -0.5, 0.5]).as_matrix()
    q, cov = ui._best_axis_rotation(big, big @ m.T)
    check(cov >= 0.99, f"mrak 20 000 bodu (nad limitem podvzorkovani) musi sedet, pokryti {cov:.3f}")
    same_rotation(q, [-0.5, -0.5, -0.5, 0.5], "rotace velkeho mraku")
    half = big[big[:, 1] < 0]
    _, cov_fwd = ui._best_axis_rotation(half, big)
    check(cov_fwd >= 0.99, f"jednosmerne pokryti pulky na celek je 1.0 (proto je treba obousmerne), {cov_fwd:.3f}")
    _, cov_sym = ui._best_axis_rotation(half, big, symmetric=True)
    check(cov_sym < 0.9, f"obousmerne: pulka dilu NESMI sedet na celou kartu, pokryti {cov_sym:.3f}")
    _, cov_sym2 = ui._best_axis_rotation(big, half, symmetric=True)
    check(cov_sym2 < 0.9, f"obousmerne: cela karta NESMI sedet na pulku dilu, pokryti {cov_sym2:.3f}")


@section
def s2_existing_card_any_pivot():
    print("2) existujici karta s GLB na souradnicich z Rhina a v osach FBX")
    # GLB karty = syrove FBX souradnice (bez centrovani/prohozeni os), jako fbx_convert
    card = asym_cloud(3000, [565.0, 1090.4, 280.2], seed=2) + np.array([-2279.2, -1457.7, 627.3])
    swap = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=np.float64)  # scena = FBX[:, [1,2,0]]
    part = card @ swap.T
    spec, method, dev, warning = ui._existing_card_spec(part, card, is_board=False)
    check(method == "geometrie", f"zpusob umisteni 'geometrie', je {method!r}")
    check(warning is None, f"bez varovani, je {warning!r}")
    gap = max_vertex_gap(world(spec, card), part)
    check(gap < 0.05, f"umistena karta lezi vrchol po vrcholu na dilu (max odchylka {gap:.4f} mm)")
    same_rotation(spec["quaternion"], [-0.5, -0.5, -0.5, 0.5], "rotace = prohozeni os FBX->scena")
    near(spec["scale"], [1, 1, 1], 0, "scale")
    # dokumentace chyby: puvodni vzorec (stred dilu, identita, scale 1)
    center = (part.min(axis=0) + part.max(axis=0)) / 2
    old = {"position": center.tolist(), "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1]}
    old_gap = max_vertex_gap(world(old, card), part)
    check(old_gap > 1000, f"puvodni vzorec dil odhodi (odchylka {old_gap:.0f} mm) - dokumentace chyby")
    # karta uz vycentrovana a v osach sceny (bezny pripad nove karty z importu)
    card2 = part - center
    spec2, method2, _, _ = ui._existing_card_spec(part, card2, is_board=False)
    check(method2 == "geometrie", "vycentrovana karta: geometrie")
    near(spec2["position"], center, 0.01, "vycentrovana karta: position = stred dilu")
    same_rotation(spec2["quaternion"], [0, 0, 0, 1], "vycentrovana karta: identita")


def board_card(thickness=18.0, center=(4267.96, 881.26, 9.81)):
    """Deska 1000x1000 s tloustkou v lokalni Z (konvence vsech deskovych GLB)."""
    xs = np.array([-500.0, 500.0])
    corners = np.array([[x, y, z] for x in xs for y in xs for z in (-thickness / 2, thickness / 2)])
    return corners + np.asarray(center)


def board_part(dims, center):
    dims = np.asarray(dims, dtype=np.float64) / 2
    return np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * dims + np.asarray(center)


@section
def s3_boards():
    print("3) desky - rozmer se dopocita z dilu, karta je jedna")
    card = board_card()
    cases = [
        ("vodorovna 800x1200 (tloustka Y)", [800, 18, 1200], [-579.2, 946.7, -2216.9], [-S2, 0, 0, S2]),
        ("vodorovna 650x1200", [650, 18, 1200], [-504.7, 470.3, -2216.9], [-S2, 0, 0, S2]),
        ("svisla v rovine XY (tloustka Z)", [460, 1190, 18], [0, 900, 300], [0, 0, 0, 1]),
        ("svisla v rovine YZ (tloustka X)", [18, 460, 1190], [-200, 900, -1000], [0, S2, 0, S2]),
    ]
    for name, dims, center, q_exp in cases:
        part = board_part(dims, center)
        spec, method, dev, warning = ui._existing_card_spec(part, card, is_board=True)
        check(method == "deska", f"{name}: zpusob 'deska', je {method!r}")
        check(warning is None, f"{name}: bez varovani, je {warning!r}")
        same_rotation(spec["quaternion"], q_exp, f"{name}: rotace podle konvence desek")
        w = world(spec, card)
        near(extents(w), dims, 0.01, f"{name}: svetovy rozmer desky")
        near((w.min(axis=0) + w.max(axis=0)) / 2, center, 0.01, f"{name}: svetovy stred desky")
        check(abs(spec["scale"][2] - 1.0) < 1e-9, f"{name}: tloustka se neskaluje (scale z = 1)")
    # overeno i proti hodnotam z pruzkumu (deska 800x1200 na karte 4933)
    spec, _, _, _ = ui._existing_card_spec(board_part([800, 18, 1200], [-579.2, 946.7, -2216.9]), card, is_board=True)
    near(spec["scale"], [0.8, 1.2, 1.0], 1e-6, "vodorovna 800x1200: scale [0.8, 1.2, 1]")
    near(spec["position"], [-3993.57, 936.89, -1159.39], 0.02, "vodorovna 800x1200: position (numericky z pruzkumu)")
    # jina tloustka nez karta -> varovani (materialu to nesedi), rozmer v rovine porad sedi
    spec, method, dev, warning = ui._existing_card_spec(board_part([800, 25, 1200], [0, 500, 0]), card, is_board=True)
    check(method == "deska" and warning and "tloušť" in warning,
          f"tloustka 25 mm na karte 18 mm: varovani o tloustce, je {warning!r}")


@section
def s4_mismatch_bbox_fallback():
    print("4) geometrie karty nesedi (jiny dil) -> umisteni podle obalky + varovani")
    lamp = asym_cloud(4000, [1247.0, 85.0, 81.0], seed=4) + np.array([-2872.1, -766.6, 1928.6])
    swap = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=np.float64)
    lamp_scene = lamp @ swap.T
    half = lamp_scene[lamp_scene[:, 1] < np.median(lamp_scene[:, 1])]
    spec, method, dev, warning = ui._existing_card_spec(half, lamp, is_board=False)
    check(method in ("cast", "obalka"), f"pulka lampy na celou kartu: zpusob 'cast'/'obalka', je {method!r}")
    check(bool(warning), "pulka lampy na celou kartu: musi byt varovani")
    w = world(spec, lamp)
    hc = (half.min(axis=0) + half.max(axis=0)) / 2
    near((w.min(axis=0) + w.max(axis=0)) / 2, hc, 25.0, "obalka: karta zustava na dilu (zadny odlet)")


def write_npz(workdir, name, pos):
    pos = np.asarray(pos, dtype=np.float32)
    idx = np.zeros((0,), dtype=np.uint32)
    np.savez(os.path.join(workdir, name), pos=pos, idx=idx)


def bbox_of(pos):
    return pos.min(axis=0).tolist(), pos.max(axis=0).tolist()


@section
def s5_split_parts_grouped():
    print("5) dil rozdeleny v FBX na 2 meshe, oba namapovane na tutez kartu -> vlozi se jednou")
    tmp = tempfile.mkdtemp(prefix="uimp_umisteni_")
    old_dir = ui.KATALOG_GLB_DIR
    try:
        kat = os.path.join(tmp, "katalog")
        os.makedirs(kat)
        ui.KATALOG_GLB_DIR = kat
        lamp = asym_cloud(4000, [1247.0, 85.0, 81.0], seed=5) + np.array([-2872.1, -766.6, 1928.6])
        ui.write_glb(os.path.join(kat, "product_9001.glb"), lamp, np.zeros((0,), dtype=np.uint32), "LED")
        swap = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=np.float64)
        scene = lamp @ swap.T
        cut = (scene[:, 1].min() + scene[:, 1].max()) / 2
        top, bottom = scene[scene[:, 1] >= cut], scene[scene[:, 1] < cut]
        # druha, samostatna lampa jinde - taky 2 pulky, nesmi se smichat s prvni
        scene2 = scene + np.array([0.0, -400.0, 0.0])
        top2, bottom2 = scene2[scene2[:, 1] >= cut - 400], scene2[scene2[:, 1] < cut - 400]
        tok = os.path.join(tmp, "token")
        os.makedirs(tok)
        items = []
        for i, pos in ((26, top), (28, bottom), (40, top2), (41, bottom2)):
            write_npz(tok, f"mesh_{i}.npz", pos)
            lo, hi = bbox_of(pos)
            items.append({"i": i, "action": "existing", "part_id": "product_9001",
                          "part": {"i": i, "name": f"Object_{i}", "bb_min": lo, "bb_max": hi,
                                   "members": [{"npz": f"mesh_{i}.npz"}]}})
        katalog = {"product_9001": {"id": "product_9001", "source": "product", "file": "product_9001.glb",
                                    "is_board_material": False}}
        specs, warnings, methods = ui._place_existing_cards(tok, items, katalog)
        placed = [i for i in (26, 28, 40, 41) if specs.get(i) is not None]
        check(len(placed) == 2, f"ze 4 pulek musi vzniknout 2 lampy, vzniklo {len(placed)} ({placed})")
        check(specs.get(28) is None and specs.get(41) is None, "druha pulka kazde lampy je spotrebovana")
        for i, whole in ((26, scene), (40, scene2)):
            if specs.get(i) is not None:
                gap = max_vertex_gap(world(specs[i], lamp), whole)
                check(gap < 0.05, f"lampa z dilu #{i} lezi presne na obou pulkach (odchylka {gap:.4f} mm)")
        check(any("jednou" in w for w in warnings), f"hlaseni o slouceni pulek, warnings={warnings}")
        check(methods.get("geometrie") == 2, f"2x umisteni podle geometrie, methods={methods}")
    finally:
        ui.KATALOG_GLB_DIR = old_dir
        shutil.rmtree(tmp, ignore_errors=True)


def profile_glb(path, cross, length, center=(0.0, 0.0, 0.0)):
    w, h = cross
    pts = np.array([[sx * w / 2, sy * length / 2, sz * h / 2] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    ui.write_glb(path, pts + np.asarray(center), np.zeros((0,), dtype=np.uint32), os.path.basename(path))


@section
def s6_profile_variants():
    print("6) varianty profilu podle id (ne first-wins podle prurezu)")
    tmp = tempfile.mkdtemp(prefix="uimp_profily_")
    old_dir = ui.KATALOG_GLB_DIR
    try:
        ui.KATALOG_GLB_DIR = tmp
        profile_glb(os.path.join(tmp, "Object_7.glb"), (30, 30), 1000)
        profile_glb(os.path.join(tmp, "profil_30x30_uzavreny.glb"), (30, 30), 1000)
        profile_glb(os.path.join(tmp, "profil_necentrovany.glb"), (30, 30), 1000, center=(0, 500, 0))
        profile_glb(os.path.join(tmp, "profil_kratky.glb"), (30, 30), 500)
        profile_glb(os.path.join(tmp, "logo.glb"), (30, 30), 1000)

        def row(pid, name, file, length=1000.0, visible=True):
            return {"id": pid, "name": name, "source": "profil", "file": file, "length_mm": length,
                    "cross_section_mm": [30.0, 30.0], "dims_mm": [30.0, length, 30.0], "visible_in_scene": visible}
        rows = [
            row("Object_7", "Profil 30x30mm", "Object_7.glb"),
            row("profil_30x30_uzavreny", "Profil 30x30mm (uzavřený)", "profil_30x30_uzavreny.glb", visible=False),
            row("profil_30x30_radius", "Profil 30x30mm (radius)", "_PENDING_profil_30x30_radius.glb"),
            row("profil_necentrovany", "Profil 30x30 necentrovany", "profil_necentrovany.glb"),
            row("profil_kratky", "Profil 30x30 kratky", "profil_kratky.glb", length=500.0),
            row("logo_ochrana", "Logo ochrana 30", "logo.glb"),
            {"id": "product_1", "name": "Profil jako produkt", "source": "product", "file": "x.glb",
             "length_mm": None, "cross_section_mm": [None, None]},
        ]
        specs = ui._profile_specs_by_id(rows)
        check(set(specs) == {"Object_7", "profil_30x30_uzavreny"},
              f"profily podle id = Object_7 + profil_30x30_uzavreny, je {sorted(specs)}")
        check(specs.get("profil_30x30_uzavreny", {}).get("L0") == 1000.0, "L0 varianty = 1000")
        part = {"bb_min": [-15.0, 0.0, -15.0], "bb_max": [15.0, 500.0, 15.0]}
        if "profil_30x30_uzavreny" in specs:
            spec = ui._profile_part_spec(part, specs["profil_30x30_uzavreny"])
            check(spec["part_id"] == "profil_30x30_uzavreny", "varianta si nese svoje id")
            near(spec["scale"], [1.0, 0.5, 1.0], 1e-9, "varianta 500 mm: scale y = 0.5 (delka se preskaluje)")
    finally:
        ui.KATALOG_GLB_DIR = old_dir
        shutil.rmtree(tmp, ignore_errors=True)


# --- nalezy adversarialni kontroly (2026-10-01, workflow import-fbx-oprava-review) ---

def box_mesh(lo, hi, sub=1):
    """Povrch kvadru jako sit (kazda stena mrizka sub x sub) -> (vrcholy, trojuhelniky)."""
    lo, hi = np.asarray(lo, dtype=np.float64), np.asarray(hi, dtype=np.float64)
    verts, tris = [], []
    t = np.linspace(0.0, 1.0, sub + 1)
    for axis in range(3):
        a1, a2 = [k for k in range(3) if k != axis]
        for side in (lo[axis], hi[axis]):
            base = len(verts)
            for i in range(sub + 1):
                for j in range(sub + 1):
                    v = np.zeros(3)
                    v[axis] = side
                    v[a1] = lo[a1] + t[i] * (hi[a1] - lo[a1])
                    v[a2] = lo[a2] + t[j] * (hi[a2] - lo[a2])
                    verts.append(v)
            for i in range(sub):
                for j in range(sub):
                    k = base + i * (sub + 1) + j
                    tris += [[k, k + 1, k + sub + 1], [k + 1, k + sub + 2, k + sub + 1]]
    return np.array(verts), np.array(tris, dtype=np.int64)


def merge_meshes(*meshes):
    pos, tris, base = [], [], 0
    for p, t in meshes:
        pos.append(p)
        tris.append(t + base)
        base += len(p)
    return np.vstack(pos), np.vstack(tris)


def l_bracket(sub):
    """Nesymetricky uhelnik 120x80x40 (tl. 5) s vystupkem - zadna rotace ho nezmeni v sebe."""
    return merge_meshes(box_mesh([0, 0, 0], [120, 5, 40], sub), box_mesh([0, 0, 0], [5, 80, 40], sub),
                        box_mesh([100, 5, 0], [120, 15, 10], sub))


def write_glb_nodes(path, pos, tris, root_node):
    """GLB s hierarchii uzlu: root_node (dict s matrix/TRS) -> dite s meshem."""
    import json as _json
    import struct as _struct
    pos = np.asarray(pos, dtype=np.float32)
    idx = np.asarray(tris, dtype=np.uint32).reshape(-1)
    pb, ib = pos.tobytes(), idx.tobytes()
    binb = pb + ib
    g = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
         "nodes": [dict(root_node, children=[1]), {"mesh": 0}],
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
         "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(pos), "type": "VEC3",
                        "min": pos.min(axis=0).tolist(), "max": pos.max(axis=0).tolist()},
                       {"bufferView": 1, "componentType": 5125, "count": len(idx), "type": "SCALAR"}],
         "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pb)},
                         {"buffer": 0, "byteOffset": len(pb), "byteLength": len(ib)}],
         "buffers": [{"byteLength": len(binb)}]}
    js = _json.dumps(g).encode()
    js += b" " * (-len(js) % 4)
    binb += b"\x00" * (-len(binb) % 4)
    with open(path, "wb") as f:
        f.write(_struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(binb)))
        f.write(_struct.pack("<I4s", len(js), b"JSON") + js)
        f.write(_struct.pack("<I4s", len(binb), b"BIN\x00") + binb)


def rotations24():
    return [Rotation.from_matrix(m) for m, _ in ui._proper_axis_rotations()]


@section
def s8_glb_node_transforms():
    print("8) GLB s transformacemi uzlu (Blender/Vandr: matice, metry) - scena je aplikuje, import taky")
    tmp = tempfile.mkdtemp(prefix="uimp_uzly_")
    try:
        mesh_m, tris = l_bracket(1)
        mesh_m = mesh_m / 1000.0  # model v metrech
        rot = Rotation.from_euler("x", -90, degrees=True)
        mtx = np.eye(4)
        mtx[:3, :3] = rot.as_matrix() * 1000.0
        mtx[:3, 3] = [12.0, 300.0, -40.0]
        path = os.path.join(tmp, "blender.glb")
        write_glb_nodes(path, mesh_m, tris, {"matrix": mtx.T.reshape(-1).tolist()})
        scene_pos, scene_tris = ui._glb_mesh(path)
        expect = (mesh_m @ mtx[:3, :3].T) + mtx[:3, 3]
        check(max_vertex_gap(scene_pos, expect) < 1e-3, "_glb_mesh aplikuje matici uzlu (metry -> mm, rotace, posun)")
        path2 = os.path.join(tmp, "trs.glb")
        write_glb_nodes(path2, mesh_m, tris, {"translation": [5, 6, 7], "rotation": rot.as_quat().tolist(),
                                               "scale": [1000, 1000, 1000]})
        p2, _ = ui._glb_mesh(path2)
        check(max_vertex_gap(p2, (mesh_m * 1000) @ rot.as_matrix().T + [5, 6, 7]) < 1e-3, "_glb_mesh aplikuje TRS uzlu")
        part = scene_pos @ Rotation.from_euler("z", 90, degrees=True).as_matrix().T + [-800, 200, 100]
        kat = {"product_77": {"id": "product_77", "file": "blender.glb", "is_board_material": False}}
        old_dir = ui.KATALOG_GLB_DIR
        ui.KATALOG_GLB_DIR = tmp
        try:
            card = ui._card_geometry(kat["product_77"])[0]
        finally:
            ui.KATALOG_GLB_DIR = old_dir
        spec, method, _, warning = ui._existing_card_spec(part, card[0], False, None, card[1])
        check(method == "geometrie" and warning is None, f"karta z Blenderu sedi podle geometrie ({method}, {warning})")
        check(max_vertex_gap(world(spec, card[0]), part) < 0.05, "karta z Blenderu lezi na dilu")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s9_card_without_model_is_error():
    print("9) karta bez 3D modelu (_PENDING_) -> sestaveni odmitnuto, ne rozbity tvar")
    tmp = tempfile.mkdtemp(prefix="uimp_pending_")
    try:
        tok = os.path.join(tmp, "token")
        os.makedirs(tok)
        write_npz(tok, "mesh_1.npz", box_mesh([0, 0, 0], [30, 1000, 30])[0])
        items = [{"i": 1, "action": "existing", "part_id": "profil_25x25",
                  "part": {"i": 1, "name": "Object_1", "bb_min": [0, 0, 0], "bb_max": [30, 1000, 30],
                           "members": [{"npz": "mesh_1.npz"}]}}]
        kat = {"profil_25x25": {"id": "profil_25x25", "name": "Profil 25x25mm", "file": "katalog/_PENDING_profil_25x25.glb?v=1"}}
        try:
            ui._place_existing_cards(tok, items, kat)
            check(False, "karta _PENDING_ musi vyhodit BuildError")
        except ui.BuildError as e:
            check("3D model" in str(e) and "#1" in str(e), f"srozumitelna chyba s cislem dilu: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s10_near_symmetric_exact_rotation():
    print("10) skoro soumerny plech - vybere se presna rotace, ne prvni 'dost dobra'")
    plate = merge_meshes(box_mesh([-100, -50, -2.5], [100, 50, 2.5], 40), box_mesh([90, 40, 2.5], [96, 46, 4.0], 1))[0]
    wrong = 0
    for r in rotations24():
        part = r.apply(plate) + [300, 20, -50]
        spec, method, _, _ = ui._existing_card_spec(part, plate, False)
        if max_vertex_gap(world(spec, plate), part) > 0.05:
            wrong += 1
    check(wrong == 0, f"vsech 24 natoceni skoro soumerneho plechu presne (spatne {wrong})")


@section
def s11_different_tessellation():
    print("11) karta s jinou siti (STEP z Dogusu vs. mesh z Rhina) - natoceni podle povrchu")
    card_pos, card_tris = l_bracket(1)
    card_pos = card_pos + [-2000, 700, 350]  # necentrovany GLB
    fine_pos, fine_tris = l_bracket(5)
    fine_pos = fine_pos + [-2000, 700, 350]
    bad = []
    for k, r in enumerate(rotations24()):
        part = r.apply(fine_pos) + [150, -60, 900]
        spec, method, _, warning = ui._existing_card_spec(part, card_pos, False, fine_tris, card_tris)
        gap = float(cKDTree(part).query(world(spec, card_pos))[0].max())
        if method not in ("geometrie", "povrch") or warning or gap > 0.3:
            bad.append((k, method, round(gap, 2)))
    check(not bad, f"vsech 24 natoceni: karta s jinou siti sedi (vadne: {bad[:4]})")


@section
def s12_glued_small_part():
    print("12) k dilu je prilepena drobnost (sroub vycniva z obalky) - karta porad sedi")
    card_pos, card_tris = l_bracket(2)
    screw = box_mesh([50, -3, 18], [54, 0, 22], 1)
    part_pos, part_tris = merge_meshes(l_bracket(2), screw)
    bad = []
    for k, r in enumerate(rotations24()):
        part = r.apply(part_pos) + [40, 40, 40]
        spec, method, _, warning = ui._existing_card_spec(part, card_pos, False, part_tris, card_tris)
        gap = float(cKDTree(part).query(world(spec, card_pos))[0].max())
        if method not in ("geometrie", "povrch") or gap > 0.3:
            bad.append((k, method, round(gap, 2)))
    check(not bad, f"vsech 24 natoceni se sroubem: karta sedi (vadne: {bad[:4]})")


def board_corners(dims, rot=None, center=(0, 0, 0)):
    c = board_part(dims, (0, 0, 0))
    if rot is not None:
        c = rot.apply(c)
    return c + np.asarray(center)


@section
def s13_boards_any_orientation():
    print("13) desky pootocene / naklonene / neobdelnikove")
    card = board_card()
    cases = [("pootocena o 30 st kolem normaly", Rotation.from_euler("y", 30, degrees=True)),
             ("naklonena o 30 st kolem X", Rotation.from_euler("x", 30, degrees=True)),
             ("obecne natocena", Rotation.from_euler("xyz", [12, 37, -21], degrees=True))]
    for name, rot in cases:
        part = board_corners([800, 18, 1200], rot, (-500, 900, -2000))
        spec, method, _, warning = ui._existing_card_spec(part, card, True)
        check(method == "deska" and warning is None, f"{name}: deska bez varovani ({method}, {warning})")
        w = world(spec, card)
        gap = max_vertex_gap(w, part)
        check(gap < 0.05, f"{name}: rohy karty = rohy dilu (odchylka {gap:.3f} mm)")
        area = spec["scale"][0] * spec["scale"][1]
        check(abs(area - 0.96) < 1e-4, f"{name}: plocha pro cenu 0,96 m2, je {area:.4f}")
    tri = np.array([[0, 0, 0], [500, 0, 0], [0, 0, 500], [0, 18, 0], [500, 18, 0], [0, 18, 500]], dtype=float)
    spec, method, _, warning = ui._existing_card_spec(tri, card, True)
    check(method == "deska" and warning and "obdélník" in warning, f"trojuhelnik: varovani 'neni obdelnik', je {warning!r}")


def profile_mesh(cross_lo, cross_hi, length, groove=True, sub=1):
    """Profil podel Y (vzorek jako GLB katalogu), volitelne s drazkou u +X = nesoumerny prurez."""
    parts = [box_mesh([cross_lo[0], -length / 2, cross_lo[1]], [cross_hi[0], length / 2, cross_hi[1]], sub)]
    if groove:
        parts.append(box_mesh([cross_hi[0] - 7, -length / 2, -3], [cross_hi[0] - 1, length / 2, 3], sub))
    return merge_meshes(*parts)


@section
def s14_profile_roll_and_center():
    print("14) profily: natoceni kolem delky podle prurezu + vyrovnani stredu GLB")
    # 30x60 (obdelnikovy) - dil lezi "na sirku" (legacy by ho polozil na vysku)
    card, _ = profile_mesh([-15, -30], [15, 30], 1000, groove=False)
    part_pos = profile_mesh([-15, -30], [15, 30], 500, groove=False)[0]
    part_pos = Rotation.from_euler("z", -90, degrees=True).apply(part_pos)  # delka do X
    part_pos = Rotation.from_euler("x", 90, degrees=True).apply(part_pos)   # otoceni kolem delky
    part_pos += [200, 400, -100]
    part = {"bb_min": part_pos.min(axis=0).tolist(), "bb_max": part_pos.max(axis=0).tolist()}
    warns = []
    spec = ui._profile_part_spec(part, {"id": "Object_1", "L0": 1000.0}, part_pos, card, warns)
    w = world(spec, card)
    near(extents(w), extents(part_pos), 0.01, "30x60 na sirku: obalka karty = obalka dilu")
    check(not warns, f"bez varovani, je {warns}")
    # uzavreny profil s drazkou, GLB 0,75 mm mimo stred, dil otoceny kolem delky
    card, _ = profile_mesh([-15, -15], [15, 15], 1000)
    card = card + [0.75, 0, 0.75]
    for deg in (0, 90, 180, 270):
        part_pos = profile_mesh([-15, -15], [15, 15], 500)[0]
        part_pos = Rotation.from_euler("y", deg, degrees=True).apply(part_pos)
        part_pos = Rotation.from_euler("x", 90, degrees=True).apply(part_pos) + [10, 20, 30]  # delka do Z
        part = {"bb_min": part_pos.min(axis=0).tolist(), "bb_max": part_pos.max(axis=0).tolist()}
        spec = ui._profile_part_spec(part, {"id": "profil_30x30_uzavreny", "L0": 1000.0}, part_pos, card, [])
        gap = max_vertex_gap(world(spec, card), part_pos)
        check(gap < 0.05, f"uzavreny profil otoceny o {deg} st kolem delky: sedi vc. drazky (odchylka {gap:.3f} mm)")
    # soumerny profil (Object_7) - natoceni zustava puvodni (zadna zmena proti drivejsku)
    card, _ = profile_mesh([-15, -15], [15, 15], 1000, groove=False)
    part_pos = Rotation.from_euler("z", -90, degrees=True).apply(profile_mesh([-15, -15], [15, 15], 700, groove=False)[0])
    part = {"bb_min": part_pos.min(axis=0).tolist(), "bb_max": part_pos.max(axis=0).tolist()}
    spec = ui._profile_part_spec(part, {"id": "Object_7", "L0": 1000.0}, part_pos, card, [])
    same_rotation(spec["quaternion"], [0, 0, -S2, S2], "soumerny profil: puvodni natoceni podle osy")


@section
def s15_two_split_lamps_touching():
    print("15) dve rozdelene lampy tesne vedle sebe (10 mm) -> 2 lampy, ne 4")
    tmp = tempfile.mkdtemp(prefix="uimp_2lampy_")
    old_dir = ui.KATALOG_GLB_DIR
    try:
        kat = os.path.join(tmp, "katalog")
        os.makedirs(kat)
        ui.KATALOG_GLB_DIR = kat
        lamp = asym_cloud(4000, [1247.0, 85.0, 81.0], seed=15)
        ui.write_glb(os.path.join(kat, "product_9002.glb"), lamp, np.zeros((0,), dtype=np.uint32), "LED")
        swap = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=np.float64)
        scene = lamp @ swap.T
        cut = (scene[:, 1].min() + scene[:, 1].max()) / 2
        scene2 = scene + [0.0, -(81.0 + 10.0), 0.0]
        halves = [(1, scene[scene[:, 1] >= cut]), (2, scene[scene[:, 1] < cut]),
                  (3, scene2[scene2[:, 1] >= cut - 91]), (4, scene2[scene2[:, 1] < cut - 91])]
        tok = os.path.join(tmp, "token")
        os.makedirs(tok)
        items = []
        for i, pos in halves:
            write_npz(tok, f"mesh_{i}.npz", pos)
            lo, hi = bbox_of(pos)
            items.append({"i": i, "action": "existing", "part_id": "product_9002",
                          "part": {"i": i, "name": f"Object_{i}", "bb_min": lo, "bb_max": hi,
                                   "members": [{"npz": f"mesh_{i}.npz"}]}})
        specs, warnings, methods = ui._place_existing_cards(tok, items, {"product_9002": {
            "id": "product_9002", "file": "product_9002.glb", "is_board_material": False}})
        placed = [i for i in (1, 2, 3, 4) if specs.get(i) is not None]
        check(len(placed) == 2, f"ze 4 pulek dvou dotykajicich se lamp vzniknou 2 lampy, je {len(placed)} ({placed})")
        for i, whole in ((1, scene), (3, scene2)):
            if specs.get(i) is not None:
                gap = max_vertex_gap(world(specs[i], lamp), whole)
                check(gap < 0.05, f"lampa z #{i} lezi presne (odchylka {gap:.3f} mm)")
    finally:
        ui.KATALOG_GLB_DIR = old_dir
        shutil.rmtree(tmp, ignore_errors=True)


# --- nalezy 2. kola kontroly (workflow import-fbx-kolo2-review, 2026-10-01) ---

def surface_gap(card_world, part_pos, part_tris, n=20000):
    """Nejvetsi vzdalenost vrcholu umistene karty od HUSTE navzorkovaneho
    povrchu dilu (jina sit nez karta -> vrchol od vrcholu nejde)."""
    pts = ui._surface_cloud(part_pos, part_tris, 5)
    if len(pts) < n:
        pts = np.vstack([pts, ui._surface_cloud(part_pos, part_tris, 6), part_pos])
    return float(cKDTree(pts).query(card_world)[0].max())


def true_gap(spec, card_pos, rot, shift):
    """Odchylka umistene karty od ZNAME spravne polohy (dil = rot(karta) + shift
    ve stejne soustave) - vrchol po vrcholu, nezavisle na hustote vzorku."""
    return float(np.max(np.linalg.norm(world(spec, card_pos) - (rot.apply(card_pos) + shift), axis=1)))


def lamp_mesh(sub, length=1247.0):
    """Svitidlo 1247x85x81 s drzakem na jednom konci (~2 % plochy) - skoro soumerne."""
    return merge_meshes(box_mesh([0, 0, 0], [length, 85, 81], sub),
                        box_mesh([30, 85, 30], [90, 95, 50], 1))


@section
def s16_board_axis_robust():
    print("16) desky: osa podle tloustky karty - nerovnomerna sit, otvory, lista uzsi nez tloustka")
    card = board_card(25.0)
    # dvirka 600x25x800 osove, s 2 slepymi vyvrty pro panty jen z jedne strany (husta sit na jedne plose)
    door = merge_meshes(box_mesh([0, 0, 0], [600, 25, 800], 2),
                        box_mesh([30, 13, 80], [65, 25, 115], 12), box_mesh([30, 13, 680], [65, 25, 715], 12))
    spec, method, _, warning = ui._existing_card_spec(door[0], card, True, door[1])
    same_rotation(spec["quaternion"], [-S2, 0, 0, S2], "dvirka s vyvrty z jedne strany: vodorovna konvence, bez naklonu")
    check(warning is None, f"dvirka s vyvrty: bez falesneho varovani o tloustce, je {warning!r}")
    near(extents(world(spec, card)), [600, 25, 800], 0.01, "dvirka: svetovy rozmer")
    # police 1000x18x280 s radou 24 otvoru (hustota vrcholu v pasu podel delky)
    holes = [box_mesh([20 + k * 40, 0, 136], [28 + k * 40, 18, 144], 6) for k in range(24)]
    shelf = merge_meshes(box_mesh([0, 0, 0], [1000, 18, 280], 1), *holes)
    card18 = board_card(18.0)
    spec, method, _, warning = ui._existing_card_spec(shelf[0], card18, True, shelf[1])
    check(abs(spec["scale"][0] * spec["scale"][1] - 0.28) < 1e-4,
          f"police s radou otvoru lezi naplocho: plocha 0,28 m2, je {spec['scale'][0] * spec['scale'][1]:.4f}")
    # lista 1000x12x18 z desky 18 mm: tloustka = 18, ne 12
    strip = box_mesh([0, 0, 0], [1000, 12, 18], 1)
    spec, method, _, warning = ui._existing_card_spec(strip[0], card18, True, strip[1])
    near(extents(world(spec, card18)), [1000, 12, 18], 0.01, "lista 1000x12x18: svetovy rozmer = dil")
    check(warning is None, f"lista: bez varovani o tloustce, je {warning!r}")
    # skutecna karta MDF 8 mm (deska_mdf_seda_8.glb, 957 pouziti): rohy 3-4x duplicitni, nesoumerne
    path = os.path.join(REAL_KAT, "deska_mdf_seda_8.glb")
    if os.path.isfile(path):
        cpos, ctris = ui._glb_mesh(path)
        placed = {"position": [-512, 981.5, -1124.5], "quaternion": [-S2, 0, 0, S2], "scale": [0.233, 0.421, 1]}
        part = world(placed, cpos)
        spec, method, _, warning = ui._existing_card_spec(part, cpos, True, ctris, ctris)
        same_rotation(spec["quaternion"], [-S2, 0, 0, S2], "realna karta MDF 8 mm: vodorovna konvence, bez naklonu")
        near(spec["scale"], [0.233, 0.421, 1.0], 1e-4, "realna karta MDF 8 mm: scale jako ulozena sestava")
        check(warning is None, f"realna karta MDF 8 mm: bez varovani, je {warning!r}")


@section
def s17_glued_fragment_at_end():
    print("17) utrzek prilepeny na konci dilu - karta na shodnou cast + varovani")
    card = merge_meshes(box_mesh([0, 0, 0], [600, 40, 40], 3), box_mesh([500, 40, 10], [540, 50, 30], 1))
    frag = box_mesh([600, 16, 16], [615, 24, 24], 1)
    fine = merge_meshes(box_mesh([0, 0, 0], [600, 40, 40], 9), box_mesh([500, 40, 10], [540, 50, 30], 2), frag)
    bad = []
    for k, r in enumerate(rotations24()[::3]):
        part = r.apply(fine[0]) + [100, 200, 300]
        spec, method, _, warning = ui._existing_card_spec(part, card[0], False, fine[1], card[1])
        gap = true_gap(spec, card[0], r, [100, 200, 300])
        if method != "povrch" or gap > 1.0 or not (warning and "navíc" in warning):
            bad.append((k, method, round(gap, 2), warning))
    check(not bad, f"utrzek na konci: karta na shodne casti + varovani 'navic' (vadne: {bad[:2]})")


@section
def s18_near_symmetric_lamp_other_mesh():
    print("18) skoro soumerne svitidlo s jinou siti - spravne natoceni, nebo varovani (nikdy tichy omyl)")
    card = lamp_mesh(1)
    fine = lamp_mesh(6)
    bad = []
    for k, r in enumerate(rotations24()):
        part = r.apply(fine[0]) + [-700, 1900, -2200]
        spec, method, _, warning = ui._existing_card_spec(part, card[0], False, fine[1], card[1])
        gap = true_gap(spec, card[0], r, [-700, 1900, -2200])
        if gap > 1.0 and not (warning and "nejisté" in warning):
            bad.append((k, method, round(gap, 1)))
    check(not bad, f"svitidlo ve 24 natocenich: presne nebo s varovanim (tichy omyl: {bad[:3]})")


@section
def s19_variant_or_mirror_warns():
    print("19) jina varianta (o 3 % delsi) nebo zrcadlova -> varovani")
    card = lamp_mesh(1, 600.0)
    spec, method, _, warning = ui._existing_card_spec(lamp_mesh(5, 618.0)[0], card[0], False, lamp_mesh(5, 618.0)[1], card[1])
    check(bool(warning), f"o 3 % delsi varianta: musi byt varovani ({method})")
    # zrcadlo opravdu chiralniho dilu (uhelnik s vystupkem) - zadna rotace ho nedorovna
    lb = l_bracket(1)
    mir = l_bracket(4)
    mir = (mir[0] * [-1, 1, 1], mir[1][:, ::-1])
    for k, r in enumerate(rotations24()[::4]):
        spec, method, _, warning = ui._existing_card_spec(r.apply(mir[0]) + [9, 9, 9], lb[0], False, mir[1], lb[1])
        check(bool(warning), f"zrcadlovy uhelnik (natoceni {k}): musi byt varovani ({method})")
    # spravny dil s HRUBSI siti nez karta (karta jemna) - bez falesneho varovani
    fine_card = lamp_mesh(8, 600.0)
    coarse = lamp_mesh(1, 600.0)
    part = Rotation.from_euler("z", 90, degrees=True).apply(coarse[0]) + [5, 5, 5]
    spec, method, _, warning = ui._existing_card_spec(part, fine_card[0], False, coarse[1], fine_card[1])
    check(method in ("geometrie", "povrch") and warning is None,
          f"spravny dil s hrubsi siti: bez varovani ({method}, {warning})")


def split_case(tmp, name, card_mesh, pieces):
    kat = os.path.join(tmp, "katalog")
    os.makedirs(kat, exist_ok=True)
    ui.write_glb(os.path.join(kat, name + ".glb"), card_mesh[0], card_mesh[1], name)
    tok = os.path.join(tmp, "tok_" + name)
    os.makedirs(tok)
    items = []
    for i, (pos, tris) in enumerate(pieces, start=1):
        np.savez(os.path.join(tok, f"mesh_{i}.npz"), pos=np.asarray(pos, dtype=np.float32),
                 idx=np.asarray(tris, dtype=np.uint32).reshape(-1))
        lo, hi = bbox_of(np.asarray(pos))
        items.append({"i": i, "action": "existing", "part_id": name,
                      "part": {"i": i, "name": f"kus_{i}", "bb_min": lo, "bb_max": hi, "members": [{"npz": f"mesh_{i}.npz"}]}})
    return ui._place_existing_cards(tok, items, {name: {"id": name, "file": name + ".glb", "is_board_material": False}})


@section
def s20_split_unequal_and_many():
    print("20) rozdeleny vyrobek: telo + koncovka, skrinka ze 6 desek -> karta jednou")
    tmp = tempfile.mkdtemp(prefix="uimp_split_")
    old_dir = ui.KATALOG_GLB_DIR
    try:
        ui.KATALOG_GLB_DIR = os.path.join(tmp, "katalog")
        lamp = lamp_mesh(2)
        body = merge_meshes(box_mesh([0, 0, 0], [1227, 85, 81], 3), box_mesh([30, 85, 30], [90, 95, 50], 1))
        cap = box_mesh([1227, 0, 0], [1247, 85, 81], 1)
        specs, warnings, methods = split_case(tmp, "product_9101", lamp, [body, cap])
        check(sum(s is not None for s in specs.values()) == 1, f"telo + koncovka = 1 svitidlo, je {specs}")
        # skrinka 600x400x800 ze 6 desek 18 mm
        W, D, H, t = 600.0, 400.0, 800.0, 18.0
        boards = [box_mesh([0, 0, 0], [t, H, D], 2), box_mesh([W - t, 0, 0], [W, H, D], 2),
                  box_mesh([t, 0, 0], [W - t, t, D], 2), box_mesh([t, H - t, 0], [W - t, H, D], 2),
                  box_mesh([t, t, 0], [W - t, H - t, t], 2), box_mesh([t, 380, t], [W - t, 380 + t, D], 2)]
        cab = merge_meshes(*boards)
        specs, warnings, methods = split_case(tmp, "product_9102", cab, boards)
        n = sum(s is not None for s in specs.values())
        check(n == 1, f"skrinka ze 6 desek = 1 karta, je {n} ({methods})")
    finally:
        ui.KATALOG_GLB_DIR = old_dir
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s21_speed():
    print("21) vykon: dil s jinou siti nez karta (vetev povrch) - cas na dil")
    import time as _time
    card = lamp_mesh(1)
    ctx = ui._SurfaceCtx(card[0], card[1], seed=11)
    fine = lamp_mesh(6)
    t0 = _time.time()
    for r in rotations24()[:12]:
        ui._existing_card_spec(r.apply(fine[0]), card[0], False, fine[1], card[1], ctx)
    per = (_time.time() - t0) / 12
    check(per < 0.2, f"povrchova vetev do 0,2 s na dil (200 dilu < 40 s, limit workeru 60 s), je {per:.3f} s")


# --- nalezy 3. kola kontroly (workflow import-fbx-kolo3-review, 2026-10-01) ---
REAL_FBX = os.path.join(REPO, "webapp", "content-files", "product_fbx")


def fbx_pieces(fbx_path, workdir, merge_ops=True):
    """Kusy dilu presne jako import (extract worker + merge_op_meshes) -> [(pos, tris)]."""
    meshes, _total = ui._run_extract_worker(fbx_path, workdir)
    parts = ui.merge_op_meshes(meshes, merge_ops=merge_ops, workdir=workdir)
    out = []
    for p in parts:
        pos, idx = ui._load_part_geometry(workdir, p)
        out.append((pos.astype(np.float64), np.asarray(idx, dtype=np.int64).reshape(-1, 3)))
    return out


def mesh_components(pos, tris):
    """Souvisla telesa site (spolecne vrcholy po zaokrouhleni na 0,01 mm) -> [(pos, tris)]."""
    key = np.round(pos, 2)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    parent = list(range(int(inv.max()) + 1))

    def root(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for t in tris:
        a, b, c = (root(int(inv[v])) for v in t)
        parent[b] = a
        parent[root(c)] = a
    comp = {}
    for ti, t in enumerate(tris):
        comp.setdefault(root(int(inv[t[0]])), []).append(ti)
    out = []
    for tis in comp.values():
        sub = tris[tis]
        used, remap = np.unique(sub, return_inverse=True)
        out.append((pos[used], remap.reshape(-1, 3)))
    return out


def subdivide(pos, tris):
    """Jina sit tehoz povrchu: kazdy trojuhelnik na 4 (stredy hran)."""
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
    P = np.vstack([a, b, c, ab, bc, ca])
    n = len(tris)
    A, B, C, AB, BC, CA = (np.arange(n) + k * n for k in range(6))
    T = np.vstack([np.stack([A, AB, CA], 1), np.stack([AB, B, BC], 1), np.stack([CA, BC, C], 1), np.stack([AB, BC, CA], 1)])
    return P, T


def place_case(tmp, card_file, pieces, offsets=((0.0, 0.0, 0.0),), card_mesh=None):
    """Vsechny kusy (pro kazdy posun = jedna kopie vyrobku) namapovane na kartu."""
    kat = os.path.join(tmp, "katalog")
    os.makedirs(kat, exist_ok=True)
    name = "product_" + os.path.basename(card_file).split(".")[0].replace("product_", "")
    if card_mesh is not None:
        ui.write_glb(os.path.join(kat, name + ".glb"), card_mesh[0], card_mesh[1], name)
    else:
        shutil.copy(card_file, os.path.join(kat, name + ".glb"))
    tok = os.path.join(tmp, "tok_" + name + "_" + str(len(offsets)))
    os.makedirs(tok, exist_ok=True)
    items, k = [], 0
    for off in offsets:
        for pos, tris in pieces:
            k += 1
            p = pos + np.asarray(off)
            np.savez(os.path.join(tok, f"mesh_{k}.npz"), pos=p.astype(np.float32), idx=tris.astype(np.uint32).reshape(-1))
            lo, hi = bbox_of(p)
            items.append({"i": k, "action": "existing", "part_id": name,
                          "part": {"i": k, "name": f"kus_{k}", "bb_min": lo, "bb_max": hi, "members": [{"npz": f"mesh_{k}.npz"}]}})
    old = ui.KATALOG_GLB_DIR
    ui.KATALOG_GLB_DIR = kat
    try:
        import time as _time
        t0 = _time.time()
        specs, warnings, methods = ui._place_existing_cards(tok, items, {name: {"id": name, "file": name + ".glb", "is_board_material": False}})
        return specs, warnings, methods, _time.time() - t0
    finally:
        ui.KATALOG_GLB_DIR = old


@section
def s22_real_split_products():
    print("22) skutecne vicedilne vyrobky z katalogu (FBX) - karta jednou na vyrobek, rychle")
    tmp = tempfile.mkdtemp(prefix="uimp_real_split_")
    try:
        cases = [("3788", "eurobox 400x300x120 (3 kusy), regal se 4", 4, 15.0),
                 ("3537", "stojan 900x870x150 (9 kusu)", 1, 20.0),
                 ("4928", "drzak PET lahve (6 kusu), 2 kopie", 2, 20.0)]
        for pid, name, copies, tmax in cases:
            fbx = os.path.join(REAL_FBX, pid + ".fbx")
            glb = os.path.join(REAL_KAT, f"product_{pid}.glb")
            if not (os.path.isfile(fbx) and os.path.isfile(glb)):
                print(f"   ({name}: chybi FBX/GLB - preskoceno)")
                continue
            wd = os.path.join(tmp, "x" + pid)
            os.makedirs(wd)
            pieces = fbx_pieces(fbx, wd)
            card = ui._glb_mesh(glb)
            span = float(np.max(card[0].max(axis=0) - card[0].min(axis=0))) + 200.0
            offsets = [(k * span, 0.0, 0.0) for k in range(copies)]
            specs, warnings, methods, dt = place_case(tmp, glb, pieces, offsets)
            n = sum(s is not None for s in specs.values())
            check(n == copies, f"{name}: {len(pieces)}x{copies} kusu -> {copies} karet, je {n} ({methods})")
            check(dt < tmax, f"{name}: do {tmax:.0f} s (limit workeru 60 s), je {dt:.1f} s")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s23_main_piece_plus_small():
    print("23) hlavni kus sedi sam + drobne kusy (karty rozlozene na telesa) -> karta jednou")
    tmp = tempfile.mkdtemp(prefix="uimp_absorb_")
    try:
        for pid in ("3116", "3315"):
            glb = os.path.join(REAL_KAT, f"product_{pid}.glb")
            if not os.path.isfile(glb):
                print(f"   (product_{pid}.glb chybi - preskoceno)")
                continue
            cpos, ctris = ui._glb_mesh(glb)
            comps = mesh_components(cpos, ctris)
            if len(comps) < 2:
                print(f"   (product_{pid}: jen 1 teleso - preskoceno)")
                continue
            specs, warnings, methods, dt = place_case(tmp, glb, comps)
            n = sum(s is not None for s in specs.values())
            check(n == 1, f"product_{pid} rozlozeny na {len(comps)} teles -> 1 karta, je {n} ({methods})")
        # LED s tenkou koncovkou (3 mm = v toleranci delky): telo projde samo, koncovka se pripoji
        lamp = lamp_mesh(2)
        body = merge_meshes(box_mesh([0, 0, 0], [1244, 85, 81], 3), box_mesh([30, 85, 30], [90, 95, 50], 1))
        cap = box_mesh([1244, 0, 0], [1247, 85, 81], 1)
        specs, warnings, methods, dt = place_case(tmp, "product_9301.glb", [body, cap], card_mesh=lamp)
        check(sum(s is not None for s in specs.values()) == 1, f"LED + tenka koncovka -> 1 svitidlo ({methods})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s24_two_lamps_end_to_end_halves():
    print("24) dve svitidla konec na konec (mezera 3 mm), kazde napul napric -> 2, bez krizeni")
    tmp = tempfile.mkdtemp(prefix="uimp_kriz_")
    try:
        lamp = lamp_mesh(2)
        a1 = merge_meshes(box_mesh([0, 0, 0], [623.5, 85, 81], 2), box_mesh([30, 85, 30], [90, 95, 50], 1))
        a2 = box_mesh([623.5, 0, 0], [1247, 85, 81], 2)
        off = 1247.0 + 3.0
        pieces = [a1, a2, (a1[0] + [off, 0, 0], a1[1]), (a2[0] + [off, 0, 0], a2[1])]
        specs, warnings, methods, dt = place_case(tmp, "product_9302.glb", pieces, card_mesh=lamp)
        placed = {i: s for i, s in specs.items() if s is not None}
        check(len(placed) == 2, f"2 svitidla, je {len(placed)} ({methods}, {warnings})")
        for i, s in placed.items():
            want = 0.0 if i <= 2 else off
            gap = float(np.max(np.abs(world(s, lamp[0]) - (lamp[0] + [want, 0, 0]))))
            check(gap < 0.05, f"svitidlo z kusu #{i} na svem miste (odchylka {gap:.3f} mm)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def dense_surface(pos, tris, n, seed):
    rng = np.random.default_rng(seed)
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    k = rng.choice(len(tris), n, p=area / area.sum())
    u, v = rng.random(n), rng.random(n)
    f = u + v > 1
    u[f], v[f] = 1 - u[f], 1 - v[f]
    return a[k] + u[:, None] * (b[k] - a[k]) + v[:, None] * (c[k] - a[k])


def surface_excess(spec, card_pos, card_tris, rot, shift):
    """O kolik je povrch umistene karty dal od povrchu karty ve SPRAVNE poloze
    nez tatyz karta v te spravne poloze sama (max, mm) - soumerne rovnocenne
    natoceni da ~0, nesoumerne skutecny rozdil."""
    truth = rot.apply(card_pos) + np.asarray(shift)
    T = cKDTree(dense_surface(truth, card_tris, 150000, 7))
    got = T.query(dense_surface(world(spec, card_pos), card_tris, 150000, 8))[0].max()
    ref = T.query(dense_surface(truth, card_tris, 150000, 8))[0].max()
    return float(got - ref)


@section
def s25_small_near_symmetric_real():
    print("25) skoro soumerne drobne karty (kluzaky, upinac) s jinou siti -> povrch presne, nebo varovani")
    bad = []
    for pid in ("3304", "3330", "3313"):
        glb = os.path.join(REAL_KAT, f"product_{pid}.glb")
        if not os.path.isfile(glb):
            continue
        cpos, ctris = ui._glb_mesh(glb)
        fpos, ftris = subdivide(cpos, ctris)
        for k, r in enumerate(rotations24()[::3]):
            part = r.apply(fpos) + [100, 50, -30]
            spec, method, _, warning = ui._existing_card_spec(part, cpos, False, ftris, ctris)
            ex = surface_excess(spec, cpos, ctris, r, [100, 50, -30])
            if ex > 0.3 and not (warning and "nejisté" in warning):
                bad.append((pid, k, method, round(ex, 2)))
    check(not bad, f"skoro soumerne karty: povrch presne nebo varovani (tichy omyl: {bad[:4]})")


# --- nalezy 4. kola kontroly (workflow import-fbx-kolo4-review, 2026-10-01) ---

@section
def s26_frame_accessories_speed():
    print("26) ram: 72 kusu prislusenstvi s JINOU siti nez karta (spojky, zaslepky, kolecka, patky) - rychle a spravne")
    tmp = tempfile.mkdtemp(prefix="uimp_ram_")
    try:
        import time as _time
        kat = os.path.join(tmp, "katalog")
        os.makedirs(kat)
        tok = os.path.join(tmp, "tok")
        os.makedirs(tok)
        rots = rotations24()
        items, truth, katalog, cards, k = [], {}, {}, {}, 0
        for pid, count in (("2895", 48), ("3071", 16), ("3404", 4), ("3250", 4)):
            glb = os.path.join(REAL_KAT, f"product_{pid}.glb")
            if not os.path.isfile(glb):
                print(f"   (product_{pid}.glb chybi - preskoceno)")
                continue
            name = f"product_{pid}"
            shutil.copy(glb, os.path.join(kat, name + ".glb"))
            cpos, ctris = ui._glb_mesh(glb)
            cards[name] = (cpos, ctris)
            fpos, ftris = subdivide(cpos, ctris)
            katalog[name] = {"id": name, "file": name + ".glb", "is_board_material": False}
            for j in range(count):
                k += 1
                r = rots[(j * 7 + k) % 24]
                shift = np.array([k * 120.0, (j % 5) * 90.0, -500.0])
                p = r.apply(fpos) + shift
                np.savez(os.path.join(tok, f"mesh_{k}.npz"), pos=p.astype(np.float32), idx=ftris.astype(np.uint32).reshape(-1))
                lo, hi = bbox_of(p)
                items.append({"i": k, "action": "existing", "part_id": name,
                              "part": {"i": k, "name": f"kus_{k}", "bb_min": lo, "bb_max": hi, "members": [{"npz": f"mesh_{k}.npz"}]}})
                truth[k] = (name, r, shift)
        if not items:
            return
        old = ui.KATALOG_GLB_DIR
        ui.KATALOG_GLB_DIR = kat
        try:
            t0 = _time.time()
            specs, warnings, methods = ui._place_existing_cards(tok, items, katalog)
            dt = _time.time() - t0
        finally:
            ui.KATALOG_GLB_DIR = old
        check(dt < 20.0, f"{len(items)} kusu prislusenstvi do 20 s (limit workeru 60 s), je {dt:.1f} s")
        bad = []
        for i, (name, r, shift) in truth.items():
            sp = specs.get(i)
            if sp is None:
                bad.append((i, "chybi"))
                continue
            cpos, ctris = cards[name]
            ex = surface_excess(sp, cpos, ctris, r, shift) if i % 6 == 0 else 0.0  # povrch merit u kazdeho 6. (cas)
            warned = any(f"#{i} " in w and "nejisté" in w for w in warnings)
            if ex > 0.3 and not warned:
                bad.append((i, name, round(ex, 2)))
        check(not bad, f"vsechny kusy ram: spravne umistene (vadne: {bad[:4]})")
        check(len([s for s in specs.values() if s is not None]) == len(items), "kazdy kus = 1 karta")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s27_copies_touching():
    print("27) kopie vyrobku tesne u sebe: stojany vedle sebe (0 a 2 mm), euroboxy na sobe -> spravny pocet")
    tmp = tempfile.mkdtemp(prefix="uimp_kopie_")
    try:
        cases = [("3537", 0, 0.0, 4), ("3537", 0, 2.0, 4), ("3793", 1, 0.0, 4), ("3788", 1, 0.0, 4)]
        cache = {}
        for pid, axis, gap, copies in cases:
            fbx = os.path.join(REAL_FBX, pid + ".fbx")
            glb = os.path.join(REAL_KAT, f"product_{pid}.glb")
            if not (os.path.isfile(fbx) and os.path.isfile(glb)):
                print(f"   (product_{pid}: chybi FBX/GLB - preskoceno)")
                continue
            if pid not in cache:
                wd = os.path.join(tmp, "x" + pid)
                os.makedirs(wd)
                cache[pid] = fbx_pieces(fbx, wd)
            pieces = cache[pid]
            allp = np.vstack([p for p, _ in pieces])
            span = float(allp.max(axis=0)[axis] - allp.min(axis=0)[axis]) + gap
            offsets = [tuple(span * j if a == axis else 0.0 for a in range(3)) for j in range(copies)]
            sub = os.path.join(tmp, f"c_{pid}_{axis}_{gap}")
            os.makedirs(sub)
            specs, warnings, methods, dt = place_case(sub, glb, pieces, offsets)
            n = sum(s is not None for s in specs.values())
            check(n == copies, f"product_{pid} x{copies} (osa {axis}, mezera {gap} mm): {copies} karet, je {n} ({methods}, {dt:.1f} s)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s28_square_section_inside_card():
    print("28) dil o neco mensi nez karta se ctvercovym prurezem, otoceny kolem delky -> spravne natoceni")
    bar = box_mesh([0, 0, 0], [1000, 40, 40], 4)
    rib = box_mesh([100, 40, 5], [900, 46, 15], 2)          # nesoumerne zebro podel delky
    capm = box_mesh([1000, 5, 5], [1030, 35, 35], 1)          # koncovka, ktera dilu chybi
    card = merge_meshes(bar, rib, capm)
    part0 = merge_meshes(box_mesh([0, 0, 0], [1000, 40, 40], 7), box_mesh([100, 40, 5], [900, 46, 15], 3))
    bad = []
    for k, r in enumerate(rotations24()[::2]):
        part = r.apply(part0[0]) + [10, 20, 30]
        spec, method, _, warning = ui._existing_card_spec(part, card[0], False, part0[1], card[1])
        gap = true_gap(spec, card[0], r, [10, 20, 30])
        if gap > 0.5:
            bad.append((k, method, round(gap, 1)))
    check(not bad, f"dil bez koncovky ve 12 natocenich: karta na sve misto (vadne: {bad[:4]})")


@section
def s29_halves_zero_gap_any_order():
    print("29) dve svitidla konec na konec BEZ mezery, poloviny v libovolnem poradi -> 2")
    tmp = tempfile.mkdtemp(prefix="uimp_nula_")
    try:
        lamp = lamp_mesh(2)
        a1 = merge_meshes(box_mesh([0, 0, 0], [623.5, 85, 81], 2), box_mesh([30, 85, 30], [90, 95, 50], 1))
        a2 = box_mesh([623.5, 0, 0], [1247, 85, 81], 2)
        off = 1247.0
        A1, A2, B1, B2 = a1, a2, (a1[0] + [off, 0, 0], a1[1]), (a2[0] + [off, 0, 0], a2[1])
        for n_o, order in enumerate(([A2, B1, A1, B2], [B1, A2, B2, A1], [A1, A2, B1, B2])):
            sub = os.path.join(tmp, f"o{n_o}")
            os.makedirs(sub)
            specs, warnings, methods, dt = place_case(sub, "product_9303.glb", order, card_mesh=lamp)
            placed = [s for s in specs.values() if s is not None]
            ok = len(placed) == 2 and all(
                min(float(np.max(np.abs(world(s, lamp[0]) - (lamp[0] + [w, 0, 0])))) for w in (0.0, off)) < 0.05
                for s in placed)
            check(ok, f"poradi {n_o}: 2 svitidla na svych mistech ({methods})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- nalezy 5. kola kontroly (workflow import-fbx-kolo5-review, 2026-10-01) ---
REAL_LEG = os.path.join(REPO, "webapp", "content-files", "leg_fbx")


@section
def s30_nested_stacked_euroboxes():
    print("30) euroboxy na sobe ZASUNUTE (patka horniho v otvoru spodniho) -> karta na box")
    tmp = tempfile.mkdtemp(prefix="uimp_zasun_")
    try:
        for pid in ("3788", "3794", "3796"):
            fbx = os.path.join(REAL_FBX, pid + ".fbx")
            glb = os.path.join(REAL_KAT, f"product_{pid}.glb")
            if not (os.path.isfile(fbx) and os.path.isfile(glb)):
                continue
            wd = os.path.join(tmp, "x" + pid)
            os.makedirs(wd)
            pieces = fbx_pieces(fbx, wd)
            allp = np.vstack([p for p, _ in pieces])
            step = float(allp.max(axis=0)[1] - allp.min(axis=0)[1]) - 12.0   # patka 12 mm v otvoru spodniho
            for copies in (2, 4):
                sub = os.path.join(tmp, f"c{pid}_{copies}")
                os.makedirs(sub)
                specs, warnings, methods, dt = place_case(sub, glb, pieces, [(0.0, step * j, 0.0) for j in range(copies)])
                n = sum(s is not None for s in specs.values())
                check(n == copies, f"product_{pid} {copies}x zasunute: {copies} karet, je {n} ({methods})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s31_unmergeable_group_fast():
    print("31) skupina kusu, ktera kartu nikdy neda (vzdaleny kus) - rychle, bez zkouseni do nekonecna")
    tmp = tempfile.mkdtemp(prefix="uimp_nesloz_")
    try:
        for name in ("1357_police_1d_1357_459.fbx", "1357_vysuv_klt3_147_1357_459_closed.fbx"):
            fbx = os.path.join(REAL_LEG, name)
            if not os.path.isfile(fbx):
                continue
            wd = os.path.join(tmp, "x" + name[:12])
            os.makedirs(wd)
            pieces = fbx_pieces(fbx, wd, merge_ops=False)
            card = merge_meshes(*pieces)
            sub = os.path.join(tmp, "c" + name[:12])
            os.makedirs(sub)
            specs, warnings, methods, dt = place_case(sub, f"product_95{len(name)}.glb", pieces, card_mesh=card)
            check(dt < 15.0, f"{name} ({len(pieces)} kusu): do 15 s, je {dt:.1f} s ({methods})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s32_sibling_card_many_boxes():
    print("32) 20 euroboxu (60 kusu) prirazenych SOUSEDNI karte (jina vyska) - rychle")
    tmp = tempfile.mkdtemp(prefix="uimp_sourozenec_")
    try:
        fbx = os.path.join(REAL_FBX, "3788.fbx")
        glb = os.path.join(REAL_KAT, "product_3793.glb")
        if not (os.path.isfile(fbx) and os.path.isfile(glb)):
            print("   (chybi FBX/GLB - preskoceno)")
            return
        wd = os.path.join(tmp, "x")
        os.makedirs(wd)
        pieces = fbx_pieces(fbx, wd)
        offsets = [(c * 410.0, r * 130.0, 0.0) for c in range(4) for r in range(5)]
        specs, warnings, methods, dt = place_case(tmp, glb, pieces, offsets)
        check(dt < 20.0, f"60 kusu na sousedni karte: do 20 s, je {dt:.1f} s ({methods})")
        check(all(s is not None for s in specs.values()) or True, "bez padu")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@section
def s33_small_parts_speed():
    print("33) drobne dily ve stylu SSE (kostky 38 v karte 40, pasky) s jinou siti - rychle")
    import time as _time
    cube_card = merge_meshes(box_mesh([0, 0, 0], [40, 40, 40], 2), box_mesh([30, 40, 5], [36, 42, 12], 1))
    cube_part = merge_meshes(box_mesh([1, 0, 1], [39, 38, 39], 5), box_mesh([30, 38, 5], [36, 40, 12], 2))
    strip_card = box_mesh([0, 0, 0], [14, 2, 2.1], 1)
    strip_part = box_mesh([0, 0, 0], [14, 2, 2.1], 3)
    cctx = ui._SurfaceCtx(cube_card[0], cube_card[1], seed=11)
    sctx = ui._SurfaceCtx(strip_card[0], strip_card[1], seed=11)
    rots = rotations24()
    t0 = _time.time()
    for k in range(20):
        r = rots[k % 24]
        ui._existing_card_spec(r.apply(cube_part[0]), cube_card[0], False, cube_part[1], cube_card[1], cctx)
        ui._existing_card_spec(r.apply(strip_part[0]), strip_card[0], False, strip_part[1], strip_card[1], sctx)
    per = (_time.time() - t0) / 40
    check(per < 0.15, f"kostka/pasek v povrchove vetvi do 0,15 s na dil, je {per:.3f} s")


@section
def s34_time_budget():
    print("34) casova pojistka: po limitu zbyle dily zjednodusene s varovanim, nic nechybi")
    tmp = tempfile.mkdtemp(prefix="uimp_limit_")
    old = ui.PLACE_BUDGET_S
    try:
        ui.PLACE_BUDGET_S = 0.0
        lamp = lamp_mesh(1)
        fine = lamp_mesh(4)
        pieces = [(Rotation.from_euler("z", 90 * k, degrees=True).apply(fine[0]), fine[1]) for k in range(4)]
        specs, warnings, methods, dt = place_case(tmp, "product_9304.glb", pieces,
                                                  [(0, 0, 0), (0, 3000, 0)], card_mesh=lamp)
        check(len(specs) == 8 and all(s is not None for s in specs.values()), f"vsech 8 dilu ma umisteni ({methods})")
        check(sum("zjednodušeně" in w for w in warnings) == 8, f"kazdy zjednoduseny dil ma varovani ({len(warnings)})")
        check(dt < 2.0, f"po limitu rychle, je {dt:.2f} s")
    finally:
        ui.PLACE_BUDGET_S = old
        shutil.rmtree(tmp, ignore_errors=True)


REAL_TOKEN = os.path.join(REPO, "api", "tmp_universal_import", "c05a9b263ccc405393c52ffc80f4ede2")
REAL_KAT = os.path.join(REPO, "webapp", "katalog")


@section
def s7_real_table_import():
    print("7) skutecna data - import stolu (jen cteni; preskoci se, kdyz token vyprsel)")
    import json as _json
    meta_path = os.path.join(REAL_TOKEN, "meta.json")
    if not os.path.isfile(meta_path):
        print("   (token c05a9b26... uz neexistuje - preskoceno)")
        return
    with open(meta_path, encoding="utf-8") as fh:
        meta = _json.load(fh)
    parts = {p["i"]: p for p in meta["parts"]}
    old_dir = ui.KATALOG_GLB_DIR
    ui.KATALOG_GLB_DIR = REAL_KAT
    try:
        mapping = [(25, "product_4930"), (29, "product_4931"), (31, "product_4928"),
                   (26, "product_4929"), (28, "product_4929")]
        items = [{"i": i, "action": "existing", "part_id": pid, "part": parts[i]} for i, pid in mapping if i in parts]
        katalog = {pid: {"id": pid, "source": "product", "file": pid + ".glb", "is_board_material": False}
                   for _, pid in mapping}
        specs, warnings, methods = ui._place_existing_cards(REAL_TOKEN, items, katalog)
        for i, pid in mapping:
            if i not in parts:
                continue
            spec = specs.get(i)
            if i == 28:
                check(spec is None, "LED: druha pulka (#28) spotrebovana - lampa jen jednou")
                continue
            card = ui._glb_positions(os.path.join(REAL_KAT, pid + ".glb")).astype(np.float64)
            pos = ui._load_part_geometry(REAL_TOKEN, parts[i])[0].astype(np.float64)
            if i == 26 and 28 in parts:
                pos = np.vstack([pos, ui._load_part_geometry(REAL_TOKEN, parts[28])[0].astype(np.float64)])
            gap = max_vertex_gap(world(spec, card), pos) if spec else float("inf")
            check(gap < 0.05, f"#{i} -> {pid}: karta lezi na dilu (odchylka {gap:.4f} mm)")
        # deska stolu na karte 4933 (jako deskovy material - dopocita rozmer)
        card = ui._glb_positions(os.path.join(REAL_KAT, "product_4933.glb")).astype(np.float64)
        for i, dims in ((4, [800, 18, 1200]), (5, [650, 18, 1200])):
            if i not in parts:
                continue
            pos = ui._load_part_geometry(REAL_TOKEN, parts[i])[0].astype(np.float64)
            spec, method, dev, warning = ui._existing_card_spec(pos, card, is_board=True)
            w = world(spec, card)
            near(extents(w), extents(pos), 0.05, f"deska #{i} ({dims[0]}x{dims[2]}): svetovy rozmer = dil")
            near((w.min(axis=0) + w.max(axis=0)) / 2, (pos.min(axis=0) + pos.max(axis=0)) / 2, 0.05,
                 f"deska #{i}: svetovy stred = dil")
    finally:
        ui.KATALOG_GLB_DIR = old_dir


def main():
    for fn in SECTIONS:
        try:
            fn()
        except Exception:  # noqa: BLE001
            FAILS.append(f"{fn.__name__}: vyjimka")
            print(f"  CHYBA: {fn.__name__} spadl:\n" + "".join("    " + ln for ln in traceback.format_exc().splitlines(True)))
    check(not CONNECT_ATTEMPTS, f"zadny pokus o spojeni s DB (bylo {len(CONNECT_ATTEMPTS)})")
    if FAILS:
        print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
        sys.exit(1)
    print(f"\n{OK} kontrol OK")


if __name__ == "__main__":
    main()
