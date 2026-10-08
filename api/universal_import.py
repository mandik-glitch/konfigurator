"""
universal_import.py - univerzalni import objektu (FBX -> rozpojena skladba
dilu -> Vlastni tvar) - bot8, 2026-09-29.

Robert (2026-09-29): "nechci jednorazovy script, postav univerzalni funkci
ktera importuje libovolny objekt: 1) rozpojene dily, aniz se od sebe
vzdalily, 2) rucne oznacim a mapuju dily na existujici profily a dily
(prislusenstvi) v katalogu, 3) nove dily zalozime jako nove produkty/karty
s novym SKU, 4) musi to splnit podminky, aby se zobrazovala v zivem pravem
panelu celkova cena, spoje atd. a sla vytvorit online nabidka." + "ad 1)
totez co vzniklo po importu SSE".

Generalizuje OVERENY postup bot10 z 18.9. (commit 726104f9, "SSE.vzor.01 -
ROZPOJENO", custom_shapes #561, shop_products 4606-4898): kazdy dil ma
vlastni GLB s puvodnimi vrcholy v souradnicich sestavy, v tvaru
position=[0,0,0]/identita - dily se "nevzdali" a zadna extrakce rotaci
neni potreba. Drobne CAD operace (zaobleni, diry, "Odebrat vysunutim"),
ktere SolidWorks exportuje jako samostatne meshe, se slouci do nejblizsiho
skutecneho dilu (mezera bboxu <= 15 mm), presne jako u SSE (461 -> 287).

Co je navic proti SSE: (a) vstup je FBX (SSE cetl uz hotovy multi-mesh
GLB; dnesni fbx_convert.convert_single_fbx sleva vsechny meshe do jedne
geometrie, nelze pouzit) -> fbx_mesh_extract_worker.py; (b) mapovani na
EXISTUJICI katalogove dily - profily (GLB vycentrovane, referencni delka
po Y) stejnou logikou jako dimension_match_fbx.build_parts; ostatni karty
NEMAJI zadnou zarucenou konvenci GLB (802 z 836 neni vycentrovanych, FBX
upload = souradnice z Rhina a osy FBX), proto se natoceni i posun
dopocitaji z geometrie GLB karty proti dilu, desky se dopocitaji do
rozmeru dilu a vyrobek rozdeleny v FBX na vic meshu se vlozi jednou
(_place_existing_cards, 2026-10-01); (c) nove karty maji GLB VYCENTROVANE na stred bboxu a
position=stred (vizualne totez jako SSE, ale karta je zaroven pouzitelna
jako bezny katalogovy dil - SSE dily "nejsou urceny k rucnimu tazeni").

Tok (UI = plovouci panel "Import objektu" primo ve scene, viz
webapp/js/scene/universal-import.js):
  POST /api/admin/universal-import/analyze   FBX -> token + seznam dilu +
        nahledove GLB (privatni adresar, jen pro scenu pres GET nize)
  GET  /api/admin/universal-import/<token>/part/<i>.glb   nahled dilu
  POST /api/admin/universal-import/build     rozhodnuti per dil ->
        nove shop_products + GLB do katalogu + 1x custom_shapes

Bod 4 zadani nevyzaduje novou cenovou logiku: computeAssemblyBomAndPrice()
a insertCustomShape() (scene.html) pracuji nad libovolnymi entries s
platnym part_id; lic_peers (spoje profil-profil) se predpocitaji stejne
jako v dimension_match_fbx (compute_lic_peers). Online nabidka = stavajici
Produktove sestavy (Ctrl+Shift+S).

BEZPECNOST: nahrany FBX ani nahledove GLB NEJDOU do webapp/content-files
(nginx ho servíruje verejne - viz oprava bot16 v dimension_match_fbx.py),
ale do privatniho api/tmp_universal_import/<token>/ (www-data, mimo
webroot); po buildu se adresar smaze, stare tokeny (>24 h) se uklidi pri
kazdem analyze.
"""
import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import uuid
from collections import Counter

import numpy as np
from flask import jsonify, request, send_file
from werkzeug.utils import secure_filename

from app import (
    app, get_conn, current_user, require_permission, staff_required, log_audit,
    CUSTOM_SHAPE_MAX_PARTS, KATALOG_GLB_DIR, fetch_katalog_parts,
    _validate_custom_shape_parts, _validate_custom_shape_relations, _product_slug_for_name,
)
from leg_fbx_import import _catalog_profiles_by_cross_section, _S2
from dimension_match_fbx import compute_lic_peers, count_lic_peer_pairs, MIN_LENGTH_MM

TMP_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_universal_import")
EXTRACT_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fbx_mesh_extract_worker.py")
FBX_READ_TIMEOUT_SEC = 180  # stul ma stovky meshu, kazdy se uklada do .npz
TOKEN_TTL_SEC = 24 * 3600
MERGE_GAP_MM = 15.0  # stejny prah jako bot10 (DROP_THRESHOLD_MM)
TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")

# Rodiny nazvu meshu, ktere SolidWorks/CAD exportuje jako samostatna
# telesa, ale fyzicky jsou to jen OPERACE na rodicovskem dilu (zaobleni,
# odebrani materialu, dira, zkoseni). Prevzato z bot10 (Zaoblit,
# Odebrat_vysunutm, Solid, M10_Tapped_Hole) + anglicke ekvivalenty.
# "Pidat_vysunutm" (Pridat vysunutim = Boss-Extrude) je naopak SKUTECNY
# dil - bot10 ho mel mezi BIG_FAMS, tady tedy zamerne chybi.
OP_FAMILY_PREFIXES = (
    "Zaoblit", "Odebrat_vysunut", "Odebrat vysunut", "Solid", "M10_Tapped_Hole", "Tapped_Hole",
    "Fillet", "Cut-Extrude", "Cut_Extrude", "Chamfer", "Zkosit", "Dira", "Díra", "Hole",
)


def _family(name):
    """Zakladni rodina nazvu meshe: bez assimp pripony '.NNN' a bez
    ciselneho sufixu '_N' / '-N'."""
    n = re.sub(r"\.\d+$", "", name or "")
    n = re.sub(r"[_\-]\d+$", "", n)
    return n


def _is_op_mesh(name):
    fam = _family(name)
    return any(fam.startswith(p) for p in OP_FAMILY_PREFIXES)


# Robert 2026-09-30 ("jsou tam spousty malych dilu to je co? nejaky sum?"):
# Rhino exportuje nespojene plochy telesa jako samostatne meshe - ploche
# utrzky bez objemu (58x2x0 mm) nebo drobne kousky (4x2x0). Nejsou to dily,
# patri k sousednimu telesu -> zachazi se s nimi jako s CAD operacemi
# (prilepit k nejblizsimu skutecnemu dilu do MERGE_GAP_MM), co zbyde
# osamocene, dostane priznak fragment ("sum") a jde smazat jednim tlacitkem.
FRAGMENT_FLAT_MM = 0.5   # nejmensi rozmer pod timhle = plocha bez tloustky
FRAGMENT_TINY_MM = 10.0  # nejvetsi rozmer pod timhle = drobek


def _is_fragment_bbox(bb_min, bb_max):
    size = sorted(float(b - a) for a, b in zip(bb_min, bb_max))
    return size[0] < FRAGMENT_FLAT_MM or size[2] < FRAGMENT_TINY_MM


def _bbox_gap(a_min, a_max, b_min, b_max):
    total = 0.0
    for k in range(3):
        gap = max(0.0, a_min[k] - b_max[k], b_min[k] - a_max[k])
        total += gap * gap
    return total ** 0.5


def _run_extract_worker(fbx_path, workdir):
    cmd = [sys.executable, EXTRACT_WORKER, fbx_path, workdir]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=FBX_READ_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        raise ValueError(f"Čtení FBX trvalo déle než {FBX_READ_TIMEOUT_SEC} s a bylo zastaveno.")
    except OSError as e:
        raise ValueError(f"Nepodařilo se spustit čtení FBX: {e}")
    try:
        result = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ValueError(f"Čtení FBX selhalo (exit={proc.returncode}). {(proc.stderr or '')[-300:]}")
    if not result.get("ok"):
        raise ValueError(result.get("error") or "Neznámá chyba čtení FBX.")
    return result.get("meshes") or [], int(result.get("total") or 0)


SHARED_VERTEX_ROUND = 2      # zaokrouhleni souradnic (0.01 mm) pro shodu vrcholu
SHARED_VERTEX_MIN = 2        # aspon 2 spolecne vrcholy = spolecna hrana


def _cluster_by_shared_vertices(workdir, meshes):
    """Union-find nad meshi: hrana mezi dvema, kdyz sdileji >= SHARED_VERTEX_MIN
    shodnych vrcholu (zaokrouhlene souradnice). Vraci seznam clusteru
    (seznamy mesh dictu) v puvodnim poradi."""
    vert_sets = []
    for m in meshes:
        z = np.load(os.path.join(workdir, m["npz"]))
        pts = np.round(z["pos"].astype(np.float64), SHARED_VERTEX_ROUND)
        vert_sets.append(set(map(tuple, pts.tolist())))
    n = len(meshes)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    # index vrchol -> meshe (misto O(n^2) porovnavani mnozin)
    owner = {}
    for k, vs in enumerate(vert_sets):
        for v in vs:
            owner.setdefault(v, []).append(k)
    pair_count = {}
    for v, ks in owner.items():
        if len(ks) < 2:
            continue
        for x in range(len(ks)):
            for y in range(x + 1, len(ks)):
                key = (ks[x], ks[y])
                pair_count[key] = pair_count.get(key, 0) + 1
    for (x, y), c in pair_count.items():
        if c >= SHARED_VERTEX_MIN:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx
    clusters = {}
    for k in range(n):
        clusters.setdefault(find(k), []).append(meshes[k])
    return [clusters[r] for r in sorted(clusters, key=lambda r: min(meshes[i]["i"] for i in range(n) if find(i) == r))]


PROFILE_NAME_RE = re.compile(r"(\d{2,3})\s*[xX×]\s*(\d{2,3})")


def merge_op_meshes(meshes, merge_ops=True, workdir=None):
    """Vrati seznam DILU: {members:[mesh,...], name, bb_min, bb_max,
    n_merged_ops}. S merge_ops=True se kazdy OP mesh prilepi k nejblizsimu
    skutecnemu dilu, pokud je mezera bboxu <= MERGE_GAP_MM; jinak zustane
    samostatnym dilem (NEzahazuje se - Robert chce vsechno videt)."""
    def is_op(m):
        return merge_ops and (_is_op_mesh(m["name"]) or _is_fragment_bbox(m["bb_min"], m["bb_max"]))

    big = [m for m in meshes if not is_op(m)]
    ops = [m for m in meshes if is_op(m)]
    groups = {m["i"]: {"members": [m], "n_merged_ops": 0} for m in big}
    orphans = []
    for op in ops:
        if not big:
            orphans.append(op)
            continue
        best = min(big, key=lambda b: _bbox_gap(op["bb_min"], op["bb_max"], b["bb_min"], b["bb_max"]))
        gap = _bbox_gap(op["bb_min"], op["bb_max"], best["bb_min"], best["bb_max"])
        if gap <= MERGE_GAP_MM:
            groups[best["i"]]["members"].append(op)
            groups[best["i"]]["n_merged_ops"] += 1
        else:
            orphans.append(op)
    # Robert 2026-09-30 ("mechanismus musi detekovat profily"): profil z
    # Rhina prichazi jako SADA PLOCHYCH STEN bez jedineho "velkeho" telesa
    # (kazda plocha = mesh), takze zadny utrzek nema k cemu se prilepit a
    # prurez neni z ceho poznat. Osamocene utrzky se proto slepi mezi
    # sebou podle SDILENYCH VRCHOLU (steny jednoho telesa sdileji hranove
    # vrcholy s presnosti exportu; dve ruzna telesa i kdyz se dotykaji
    # maji jinou tesselaci) - vznikne dil 30x30xL a prurez se rozpozna.
    # Bbox-blizkost by tady byla spatne: dotykajici se profily ramu by
    # slila do jedne hroudy.
    if workdir and len(orphans) >= 2:
        clusters = _cluster_by_shared_vertices(workdir, orphans)
        orphans = []
        for cl in clusters:
            if len(cl) == 1:
                orphans.append(cl[0])
            else:
                groups[cl[0]["i"]] = {"members": cl, "n_merged_ops": len(cl) - 1}
    for op in orphans:
        groups[op["i"]] = {"members": [op], "n_merged_ops": 0}
    parts = []
    for seed_i in sorted(groups):
        g = groups[seed_i]
        mins = np.min([m["bb_min"] for m in g["members"]], axis=0)
        maxs = np.max([m["bb_max"] for m in g["members"]], axis=0)
        seed = g["members"][0]
        parts.append({
            "members": g["members"],
            "name": seed["name"],
            "node": seed.get("node") or "",
            "bb_min": mins.tolist(), "bb_max": maxs.tolist(),
            "n_merged_ops": g["n_merged_ops"],
            "fragment": _is_fragment_bbox(mins, maxs),
        })
    return parts


def _pad4(buf):
    while len(buf) % 4 != 0:
        buf += b"\x00"
    return buf


def write_glb(out_path, pos, idx, name):
    """Minimalni GLB (jen POSITION + indices, bez normal/materialu) -
    stejny writer, jaky pouzil bot10 pro sse_part_NNN.glb; Three.js
    GLTFLoader si normaly dopocita, scene.html pak aplikuje vlastni
    material (applyPartMaterial)."""
    pos = np.asarray(pos, dtype=np.float32)
    idx = np.asarray(idx, dtype=np.uint32)
    use_uint = len(pos) > 65535
    idx_bytes = idx.astype(np.uint32 if use_uint else np.uint16).tobytes()
    pos_bytes = pos.tobytes()
    buffer = bytearray()
    pos_off = len(buffer); buffer.extend(pos_bytes); buffer = bytearray(_pad4(bytes(buffer)))
    idx_off = len(buffer); buffer.extend(idx_bytes); buffer = bytearray(_pad4(bytes(buffer)))
    gltf = {
        "asset": {"version": "2.0", "generator": "konfigurator-universal-import"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": int(len(pos)), "type": "VEC3",
             "min": pos.min(axis=0).astype(float).tolist(), "max": pos.max(axis=0).astype(float).tolist()},
            {"bufferView": 1, "componentType": (5125 if use_uint else 5123), "count": int(len(idx)), "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": pos_off, "byteLength": len(pos_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": idx_off, "byteLength": len(idx_bytes), "target": 34963},
        ],
        "buffers": [{"byteLength": len(buffer)}],
    }
    json_bytes = json.dumps(gltf).encode("utf-8")
    while len(json_bytes) % 4 != 0:
        json_bytes += b" "
    bin_bytes = bytes(buffer)
    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    with open(out_path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total_len))
        f.write(struct.pack("<I4s", len(json_bytes), b"JSON"))
        f.write(json_bytes)
        f.write(struct.pack("<I4s", len(bin_bytes), b"BIN\x00"))
        f.write(bin_bytes)


def _load_part_geometry(workdir, part):
    """Sloucene vrcholy/indexy vsech members dilu (puvodni souradnice)."""
    all_pos, all_idx, vbase = [], [], 0
    for m in part["members"]:
        z = np.load(os.path.join(workdir, m["npz"]))
        pos, idx = z["pos"], z["idx"]
        all_pos.append(pos)
        all_idx.append(idx.astype(np.uint32) + vbase)
        vbase += len(pos)
    return np.concatenate(all_pos), np.concatenate(all_idx)


def _cleanup_old_tokens():
    if not os.path.isdir(TMP_ROOT):
        return
    now = time.time()
    for d in glob.glob(os.path.join(TMP_ROOT, "*")):
        try:
            if not os.path.isdir(d):
                continue
            has_draft = False
            mp = os.path.join(d, "meta.json")
            if os.path.isfile(mp):
                try:
                    with open(mp, encoding="utf-8") as fh:
                        has_draft = bool((json.load(fh) or {}).get("draft"))
                except (OSError, ValueError):
                    has_draft = False
            ttl = DRAFT_TTL_SEC if has_draft else TOKEN_TTL_SEC
            if now - os.path.getmtime(d) > ttl:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def _token_dir(token):
    if not TOKEN_RE.match(token or ""):
        return None
    d = os.path.join(TMP_ROOT, token)
    return d if os.path.isdir(d) else None


def _glb_geometry_signature(path):
    """(dims_sorted, n_verts, n_tris) z hlavicky GLB (JSON chunk: accessor
    POSITION min/max + count, indices count) - bez cteni BIN chunku, takze
    rychle i pro stovky katalogovych souboru. None = nejde precist."""
    try:
        with open(path, "rb") as f:
            head = f.read(20)
            if len(head) < 20 or head[:4] != b"glTF":
                return None
            json_len = struct.unpack("<I", head[12:16])[0]
            g = json.loads(f.read(json_len).decode("utf-8", "replace"))
        accessors = g.get("accessors") or []
        n_verts = 0
        n_idx = 0
        mins = [float("inf")] * 3
        maxs = [float("-inf")] * 3
        for mesh in g.get("meshes") or []:
            for prim in mesh.get("primitives") or []:
                pa = prim.get("attributes", {}).get("POSITION")
                if pa is None:
                    continue
                acc = accessors[pa]
                n_verts += int(acc.get("count") or 0)
                if acc.get("min") and acc.get("max"):
                    mins = [min(mins[k], float(acc["min"][k])) for k in range(3)]
                    maxs = [max(maxs[k], float(acc["max"][k])) for k in range(3)]
                if prim.get("indices") is not None:
                    n_idx += int(accessors[prim["indices"]].get("count") or 0)
                else:
                    n_idx += int(acc.get("count") or 0)
        if n_verts == 0 or mins[0] == float("inf"):
            return None
        dims = sorted(maxs[k] - mins[k] for k in range(3))
        return dims, n_verts, n_idx // 3
    except (OSError, ValueError, KeyError, IndexError, struct.error):
        return None


def _catalog_geometry_index():
    """Vsechny katalogove dily s GLB (profily i produkty) -> seznam
    {id, name, dims (sorted), n_verts, n_tris, is_profile}. Cte se pri
    kazdem rozpoznavani znovu (stejne jako _catalog_profiles_by_cross_
    section) - nove zalozene karty se tak rozpoznaji hned."""
    out = []
    for p in fetch_katalog_parts():
        fname = (p.get("file") or "").split("?")[0]
        if fname.startswith("katalog/"):
            fname = fname[len("katalog/"):]
        if not fname or fname == "_PENDING_":
            continue
        sig = _glb_geometry_signature(os.path.join(KATALOG_GLB_DIR, fname))
        if not sig:
            continue
        dims, nv, nt = sig
        cs = p.get("cross_section_mm") or [None, None]
        out.append({"id": p["id"], "name": p["name"], "dims": dims, "n_verts": nv, "n_tris": nt,
                    "is_profile": bool(p.get("length_mm") and cs[0] is not None)})
    return out


EXACT_TOL_MM = 0.6   # stejna geometrie (stejny export) - rozmery se lisi jen zaokrouhlenim
SIMILAR_TOL_MM = 2.0  # jen stejne rozmery (jiny export/tesselace) - navrh k potvrzeni


def recognize_part(dims_mm, n_verts, n_tris, profiles, geo_index, tolerance=2.0, name=""):
    """Vrati (suggested_part_id, kind): kind 'exact' (rozmery i pocet
    vrcholu/trojuhelniku sedi = tentyz dil, napr. kolo zalozene minulym
    importem), 'profil' (prurez katalogoveho profilu, delka libovolna),
    'rozmer' (jen rozmery sedi - podobny dil, potvrdit rucne), nebo
    (None, None). Robert 2026-09-30: "dej tam funkci rozpoznat stavajici
    tvary"."""
    a, b, c = sorted(dims_mm)
    # 1) katalogovy PROFIL podle prurezu ma prednost - i kdyz by stejna
    #    geometrie sedela presne na nejakou drive zalozenou kartu (napr.
    #    SSE.vzor.01 dil 098 = kus profilu 40x40x1569): cena/natahovani
    #    profilu funguje jen pres katalogovy profil s referencni delkou.
    if c >= MIN_LENGTH_MM:
        for cross, cat in profiles.items():
            if abs(a - cross[0]) <= tolerance and abs(b - cross[1]) <= tolerance:
                return cat["id"], "profil"
    # 1b) profil podle NAZVU ("30x30", "profil 45x45x1200") - kdyz bbox
    #     nesedi na prurez (napr. profil s prilepenym prislusenstvim nebo
    #     zkoseny konec), ale nazev z Rhina prurez rika
    m = PROFILE_NAME_RE.search(name or "")
    if m and c >= MIN_LENGTH_MM:
        w, h = sorted((int(m.group(1)), int(m.group(2))))
        for cross, cat in profiles.items():
            if abs(w - cross[0]) <= 0.5 and abs(h - cross[1]) <= 0.5:
                return cat["id"], "profil"
    # 2) tentyz dil (rozmery + pocet vrcholu/trojuhelniku) - typicky karta
    #    zalozena minulym importem tehoz objektu (kolo, patka...)
    # 3) jen rozmery - podobny dil, k rucnimu potvrzeni
    similar = None
    for g in geo_index:
        if g["is_profile"]:
            continue
        d = g["dims"]
        if all(abs(x - y) <= EXACT_TOL_MM for x, y in zip((a, b, c), d)) and g["n_verts"] == n_verts and g["n_tris"] == n_tris:
            return g["id"], "exact"
        if similar is None and all(abs(x - y) <= SIMILAR_TOL_MM for x, y in zip((a, b, c), d)):
            similar = g["id"]
    if similar:
        return similar, "rozmer"
    return None, None


# --- rozpoznani podle TVARU PRUREZU (Robert 2026-09-30: "tytez prurezy a
#     tvary maji profily, se kterymi pracujeme, pochazi z tehoz
#     geometrickeho tvaru") - porovnava se skutecny 2D prurez (vrcholy
#     dilu promitnute kolmo k delce) s prurezem katalogoveho GLB, nezavisle
#     na delce, natoceni (8 symetrii ctverce) a tesselaci (pokryti bodu do
#     SECTION_TOL_MM, ne shoda vrcholu). Odlisi i varianty se stejnym
#     obrysem (30x30 vs. 30x30 radius/uzavreny), ktere bbox nerozezna. ---
SECTION_TOL_MM = 0.6
SECTION_COVER_MIN = 0.85
SECTION_MAX_CROSS_MM = 120.0  # vetsi "prurez" uz neni profil (deska, panel)
SECTION_MAX_POINTS = 6000

_ACC_DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}


def _glb_positions(path):
    """Vsechny POSITION vrcholy GLB (Nx3 float32), bez transformaci uzlu
    (katalogove GLB jsou jednoduche, stejny predpoklad jako bot10 loader)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        return None
    length = struct.unpack("<I", data[8:12])[0]
    off = 12
    g = None
    binc = None
    while off < length:
        clen, ctype = struct.unpack("<I4s", data[off:off + 8])
        chunk = data[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            g = json.loads(chunk.decode("utf-8", "replace"))
        elif ctype == b"BIN\x00":
            binc = chunk
        off += 8 + clen
    if not g or binc is None:
        return None
    out = []
    for mesh in g.get("meshes") or []:
        for prim in mesh.get("primitives") or []:
            pa = prim.get("attributes", {}).get("POSITION")
            if pa is None:
                continue
            acc = g["accessors"][pa]
            bv = g["bufferViews"][acc["bufferView"]]
            dt = _ACC_DTYPE.get(acc["componentType"], np.float32)
            n = int(acc["count"])
            base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            stride = bv.get("byteStride") or (3 * np.dtype(dt).itemsize)
            if stride == 3 * np.dtype(dt).itemsize:
                arr = np.frombuffer(binc, dtype=dt, count=3 * n, offset=base).reshape(n, 3)
            else:
                arr = np.stack([np.frombuffer(binc, dtype=dt, count=3, offset=base + k * stride) for k in range(n)])
            out.append(arr.astype(np.float32))
    return np.concatenate(out) if out else None


def _section_points(pos):
    """(body Nx2 vycentrovane, (w, h) serazene) - projekce vrcholu kolmo k
    nejdelsi ose bboxu, dedup na 0.1 mm."""
    pos = np.asarray(pos, dtype=np.float64)
    size = pos.max(axis=0) - pos.min(axis=0)
    ax = int(np.argmax(size))
    others = [k for k in range(3) if k != ax]
    pts = pos[:, others]
    pts = pts - (pts.min(axis=0) + pts.max(axis=0)) / 2.0
    pts = np.unique(np.round(pts, 1), axis=0)
    if len(pts) > SECTION_MAX_POINTS:
        pts = pts[np.random.default_rng(0).choice(len(pts), SECTION_MAX_POINTS, replace=False)]
    ext = sorted((size[others[0]], size[others[1]]))
    return pts, (float(ext[0]), float(ext[1]))


def _section_coverage(a, b):
    """Nejlepsi symetricke pokryti (min z obou smeru) pres 8 symetrii
    ctverce aplikovanych na b."""
    from scipy.spatial import cKDTree
    ta = cKDTree(a)
    best = 0.0
    for sx, sy, swap in ((1, 1, 0), (1, -1, 0), (-1, 1, 0), (-1, -1, 0), (1, 1, 1), (1, -1, 1), (-1, 1, 1), (-1, -1, 1)):
        bb = b[:, ::-1] if swap else b
        bb = bb * np.array([sx, sy], dtype=np.float64)
        d_ab, _ = ta.query(bb, distance_upper_bound=SECTION_TOL_MM)
        cov_b = float(np.mean(np.isfinite(d_ab)))
        if cov_b < best:
            continue
        d_ba, _ = cKDTree(bb).query(a, distance_upper_bound=SECTION_TOL_MM)
        cov_a = float(np.mean(np.isfinite(d_ba)))
        best = max(best, min(cov_a, cov_b))
    return best


def _catalog_profile_sections():
    """Prurezy vsech katalogovych profilu s realnym GLB (vc. variant
    radius/uzavreny/light, ktere nejsou v pickeru sceny, ale jsou platne
    dily tvaru). Cte GLB pri kazdem rozpoznani (~11 malych souboru)."""
    out = []
    for p in fetch_katalog_parts():
        if p.get("source") != "profil" or not p.get("length_mm") or not p.get("cross_section_mm") or p["cross_section_mm"][0] is None:
            continue
        # jen skutecne profily (katalogovy vzorek 1000 mm, nazev "Profil ...") -
        # cfg_dily ma i pomocne dily se stejnymi poli (logo, vypln drazky,
        # pin, doraz...), ktere by chytaly drobne utrzky jako "profil"
        if float(p["length_mm"]) < 900 or not str(p.get("name") or "").lower().startswith("profil"):
            continue
        fname = (p.get("file") or "").split("?")[0]
        if fname.startswith("katalog/"):
            fname = fname[len("katalog/"):]
        if not fname or fname.startswith("_PENDING_"):
            continue
        path = os.path.join(KATALOG_GLB_DIR, fname)
        if not os.path.isfile(path):
            continue
        try:
            pos = _glb_positions(path)
        except (OSError, ValueError, KeyError, struct.error):
            pos = None
        if pos is None or len(pos) < 8:
            continue
        pts, ext = _section_points(pos)
        out.append({"id": p["id"], "name": p["name"], "visible": bool(p.get("visible_in_scene")), "pts": pts, "ext": ext})
    return out


def recognize_section(pos, catalog_sections):
    """Vrati (part_id, coverage) nejlepsiho profilu podle tvaru prurezu,
    nebo (None, 0)."""
    pts, ext = _section_points(pos)
    if ext[1] > SECTION_MAX_CROSS_MM or len(pts) < 8:
        return None, 0.0
    best_id, best_cov, best_vis = None, 0.0, False
    for c in catalog_sections:
        if abs(c["ext"][0] - ext[0]) > 1.0 or abs(c["ext"][1] - ext[1]) > 1.0:
            continue
        cov = _section_coverage(pts, c["pts"])
        if cov > best_cov + 0.02 or (abs(cov - best_cov) <= 0.02 and c["visible"] and not best_vis):
            best_id, best_cov, best_vis = c["id"], cov, c["visible"]
    if best_id and best_cov >= SECTION_COVER_MIN:
        return best_id, best_cov
    return None, best_cov


def recognize_all(meta_parts, tolerance=2.0, workdir=None):
    profiles = _catalog_profiles_by_cross_section()
    geo_index = _catalog_geometry_index()
    sections = _catalog_profile_sections() if workdir else []
    for p in meta_parts:
        pid, kind = None, None
        p["section_cov"] = None
        dims_sorted = sorted(p["dims_mm"])
        if sections and dims_sorted[2] >= MIN_LENGTH_MM and dims_sorted[1] <= SECTION_MAX_CROSS_MM and p.get("members"):
            try:
                pos, _ = _load_part_geometry(workdir, p)
                pid, cov = recognize_section(pos, sections)
                p["section_cov"] = round(cov, 3)
                if pid:
                    kind = "profil"
            except (OSError, ValueError):
                pid = None
        if not pid:
            pid, kind = recognize_part(p["dims_mm"], p["n_verts"], p["n_tris"], profiles, geo_index, tolerance,
                                       name=f"{p.get('name', '')} {p.get('node', '')}")
        p["suggested_part_id"] = pid
        p["suggest_kind"] = kind
    return meta_parts


def analyze_fbx(fbx_path, workdir, merge_ops=True, tolerance=2.0):
    """Jadro analyze (bez Flasku) - vrati (parts_meta, total_meshes).
    parts_meta[i] uz obsahuje 'preview_file' (part_<i>.glb ve workdir)
    a rozpoznani 'suggested_part_id'/'suggest_kind' (viz recognize_part)."""
    meshes, total = _run_extract_worker(fbx_path, workdir)
    if not total:
        raise ValueError("FBX neobsahuje žádnou geometrii.")
    parts = merge_op_meshes(meshes, merge_ops=merge_ops, workdir=workdir)
    meta = []
    for i, p in enumerate(parts):
        pos, idx = _load_part_geometry(workdir, p)
        fname = f"part_{i}.glb"
        write_glb(os.path.join(workdir, fname), pos, idx, p["name"])
        size = np.array(p["bb_max"]) - np.array(p["bb_min"])
        meta.append({
            "i": i, "name": p["name"], "node": p["node"],
            "dims_mm": [round(float(v), 1) for v in size.tolist()],
            "bb_min": [round(float(v), 3) for v in p["bb_min"]],
            "bb_max": [round(float(v), 3) for v in p["bb_max"]],
            "n_members": len(p["members"]), "n_merged_ops": p["n_merged_ops"],
            "n_verts": int(len(pos)), "n_tris": int(len(idx) // 3),
            "suggested_part_id": None, "suggest_kind": None,
            "fragment": bool(p.get("fragment")),
            "preview_file": fname,
            "members": [{"npz": m["npz"], "name": m["name"]} for m in p["members"]],
        })
    recognize_all(meta, tolerance, workdir=workdir)
    return meta, total


@app.post("/api/admin/universal-import/analyze")
@require_permission("rozklad_fbx", "upravit")
def universal_import_analyze():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    stem, ext = os.path.splitext(safe_name)
    if ext.lower() != ".fbx":
        return jsonify({"error": "Očekávám soubor .fbx (SolidWorks nativní .SLDPRT/.SLDASM otevřít neumíme - exportuj FBX)."}), 400
    merge_ops = (request.form.get("merge_ops") or "1") not in ("0", "false", "no")
    try:
        tolerance = float(request.form.get("tolerance") or 2.0)
    except (TypeError, ValueError):
        tolerance = 2.0

    _cleanup_old_tokens()
    token = uuid.uuid4().hex
    workdir = os.path.join(TMP_ROOT, token)
    os.makedirs(workdir, exist_ok=True)
    fbx_path = os.path.join(workdir, "source.fbx")
    f.save(fbx_path)
    try:
        meta, total = analyze_fbx(fbx_path, workdir, merge_ops=merge_ops, tolerance=tolerance)
    except Exception as e:  # noqa: BLE001 - chybu hlasit uzivateli, ne 500
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify({"error": f"Rozbor FBX selhal: {e}"}), 400
    if len(meta) > CUSTOM_SHAPE_MAX_PARTS:
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify({"error": f"Rozpoznáno {len(meta)} dílů, limit vlastního tvaru je {CUSTOM_SHAPE_MAX_PARTS}."}), 400
    _write_meta(workdir, {"source_name": safe_name, "parts": meta, "total_meshes": total,
                          "merge_ops": merge_ops, "tolerance": tolerance})
    return jsonify({
        "token": token, "source_name": safe_name, "shape_code_suggestion": re.sub(r"[^A-Za-z0-9]+", ".", stem).strip(".")[:40],
        "total_meshes": total, **_public_parts_payload(token, meta),
    })


def _write_meta(workdir, meta):
    with open(os.path.join(workdir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)


def _read_meta(workdir):
    with open(os.path.join(workdir, "meta.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _public_parts_payload(token, meta_parts):
    """Radky dilu pro frontend (bez interniho seznamu .npz). `v` = verze
    nahledu - po spojeni/rozpojeni se stejna URL part_<i>.glb prepise,
    frontend ji pripoji jako ?v=, aby prohlizec nepouzil stary soubor."""
    public = []
    for p in meta_parts:
        q = {k: v for k, v in p.items() if k not in ("members", "preview_file", "joined_from")}
        q["joined"] = bool(p.get("joined_from"))
        q["preview_url"] = f"/api/admin/universal-import/{token}/part/{p['i']}.glb?v={p.get('v', 0)}"
        public.append(q)
    return {
        "parts": public, "n_parts": len(meta_parts),
        "n_merged_ops": sum(p["n_merged_ops"] for p in meta_parts),
        "n_suggested_profiles": sum(1 for p in meta_parts if p.get("suggested_part_id")),
        "n_exact": sum(1 for p in meta_parts if p.get("suggest_kind") == "exact"),
    }


# --- rozpracovane importy (Robert 2026-09-30: "u vetsiho tvaru to
#     sestavovani celkem trva, chce to ukladat v prubehu") -------------------
DRAFT_TTL_SEC = 14 * 24 * 3600  # import s ulozenym rozpracovanim drzime dele nez holy token


@app.post("/api/admin/universal-import/<token>/draft")
@require_permission("rozklad_fbx", "upravit")
def universal_import_draft_save(token):
    d = _token_dir(token)
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import."}), 404
    body = request.get_json(silent=True) or {}
    meta = _read_meta(d)
    meta["draft"] = {
        "shape_name": (body.get("shape_name") or "")[:200],
        "shape_code": (body.get("shape_code") or "")[:60],
        "category_id": body.get("category_id"),
        "decisions": body.get("decisions") if isinstance(body.get("decisions"), dict) else {},
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_meta(d, meta)
    os.utime(d, None)
    return jsonify({"status": "ok", "saved_at": meta["draft"]["saved_at"]})


@app.get("/api/admin/universal-import/drafts")
@require_permission("rozklad_fbx", "zobrazit")
def universal_import_drafts():
    out = []
    if os.path.isdir(TMP_ROOT):
        for dpath in sorted(glob.glob(os.path.join(TMP_ROOT, "*")), key=os.path.getmtime, reverse=True):
            token = os.path.basename(dpath)
            if not TOKEN_RE.match(token) or not os.path.isfile(os.path.join(dpath, "meta.json")):
                continue
            try:
                meta = _read_meta(dpath)
            except (OSError, ValueError):
                continue
            draft = meta.get("draft") or {}
            decided = sum(1 for v in (draft.get("decisions") or {}).values() if isinstance(v, dict) and v.get("action") in ("existing", "new"))
            out.append({
                "token": token, "source_name": meta.get("source_name"), "n_parts": len(meta.get("parts") or []),
                "shape_name": draft.get("shape_name") or "", "saved_at": draft.get("saved_at"),
                "n_decided": decided, "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(dpath))),
            })
    return jsonify({"drafts": out})


@app.get("/api/admin/universal-import/<token>")
@require_permission("rozklad_fbx", "zobrazit")
def universal_import_get(token):
    d = _token_dir(token)
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import."}), 404
    meta = _read_meta(d)
    return jsonify({"token": token, "source_name": meta.get("source_name"), "total_meshes": meta.get("total_meshes"),
                    "draft": meta.get("draft") or None, **_public_parts_payload(token, meta["parts"])})


@app.post("/api/admin/universal-import/<token>/recognize")
@require_permission("rozklad_fbx", "upravit")
def universal_import_recognize(token):
    """Znovu rozpoznat vsechny dily proti aktualnimu katalogu (po spojeni
    dilu, nebo kdyz mezitim pribyly nove karty)."""
    d = _token_dir(token)
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import."}), 404
    meta = _read_meta(d)
    recognize_all(meta["parts"], float(meta.get("tolerance") or 2.0), workdir=d)
    _write_meta(d, meta)
    return jsonify(_public_parts_payload(token, meta["parts"]))


def _part_from_members(workdir, i, members, name, n_merged_ops, v):
    """Postavi zaznam dilu z members (npz) - bbox z geometrie, nahledove
    GLB part_<i>.glb prepsano. Pouziva join i split."""
    pos, idx = _load_part_geometry(workdir, {"members": members})
    fname = f"part_{i}.glb"
    write_glb(os.path.join(workdir, fname), pos, idx, name)
    lo, hi = pos.min(axis=0), pos.max(axis=0)
    size = hi - lo
    return {
        "i": i, "name": name, "node": "",
        "dims_mm": [round(float(x), 1) for x in size.tolist()],
        "bb_min": [round(float(x), 3) for x in lo.tolist()],
        "bb_max": [round(float(x), 3) for x in hi.tolist()],
        "n_members": len(members), "n_merged_ops": n_merged_ops,
        "n_verts": int(len(pos)), "n_tris": int(len(idx) // 3),
        "suggested_part_id": None, "preview_file": fname, "members": members, "v": v,
    }


@app.post("/api/admin/universal-import/<token>/join")
@require_permission("rozklad_fbx", "upravit")
def universal_import_join(token):
    """Robert 2026-09-30: "nektery dil se nahraje jako rozpojeny, i kdyz jej
    chci mit spojeny... zakomponuj funkci J, aby oznacene dily povazoval za
    1 objekt" - rucni slouceni vybranych dilu do jednoho (jedna geometrie,
    jedno mapovani). Vratne pres /split (puvodni dily se uchovaji v
    joined_from)."""
    d = _token_dir(token)
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import."}), 404
    body = request.get_json(silent=True) or {}
    try:
        ids = sorted({int(x) for x in (body.get("parts") or [])})
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné indexy dílů."}), 400
    if len(ids) < 2:
        return jsonify({"error": "Označ aspoň 2 díly ke spojení."}), 400
    meta = _read_meta(d)
    by_i = {p["i"]: p for p in meta["parts"]}
    missing = [i for i in ids if i not in by_i]
    if missing:
        return jsonify({"error": f"Díl(y) {missing} v tomto importu nejsou."}), 400
    chosen = [by_i[i] for i in ids]
    members = [m for p in chosen for m in p["members"]]
    name = (body.get("name") or "").strip() or f"{chosen[0]['name']} (+{len(chosen) - 1})"
    seed_i = ids[0]
    new_part = _part_from_members(d, seed_i, members, name, sum(p["n_merged_ops"] for p in chosen),
                                  int(time.time() * 1000))
    # uchovat puvodni dily pro pripadne rozpojeni (vc. jejich joined_from)
    new_part["joined_from"] = chosen
    new_part["fragment"] = _is_fragment_bbox(new_part["bb_min"], new_part["bb_max"])
    # spojeny dil hned rozpoznat (typicky: steny profilu slepene rucne pres J)
    recognize_all([new_part], float(meta.get("tolerance") or 2.0), workdir=d)
    meta["parts"] = [new_part if p["i"] == seed_i else p for p in meta["parts"] if p["i"] == seed_i or p["i"] not in ids]
    _write_meta(d, meta)
    return jsonify({"joined_i": seed_i, **_public_parts_payload(token, meta["parts"])})


@app.post("/api/admin/universal-import/<token>/merge-small")
@require_permission("rozklad_fbx", "upravit")
def universal_import_merge_small(token):
    """Robert 2026-09-30 ("u SSE importu jsem neresil mikrodily"): drobne
    nerozpoznane dily (frontend posle ids, typicky max rozmer <= 60 mm)
    prilepit k nejblizsimu VETSIMU dilu (mezera bboxu <= MERGE_GAP_MM),
    stejne jako CAD operace pri rozboru. Co nema souseda, zustane."""
    d = _token_dir(token)
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import."}), 404
    body = request.get_json(silent=True) or {}
    try:
        ids = {int(x) for x in (body.get("ids") or [])}
        exclude_hosts = {int(x) for x in (body.get("exclude_hosts") or [])}
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné indexy dílů."}), 400
    return jsonify(merge_small_parts(d, token, ids, exclude_hosts))


def merge_small_parts(d, token, ids, exclude_hosts=frozenset()):
    """Jadro merge-small (bez Flasku, testovatelne): viz endpoint vyse.
    exclude_hosts = dily, ke kterym se NESMI nic prilepit: vsechno, co se
    mapuje na EXISTUJICI katalogovy dil (profily, stejne dily, rucni
    prirazeni) - ve tvaru je nahradi katalogove GLB, takze prilepena
    geometrie by zmizela a posunuty bbox by profil spatne umistil."""
    meta = _read_meta(d)
    parts = meta["parts"]
    small = [p for p in parts if p["i"] in ids]
    hosts = [p for p in parts if p["i"] not in ids and p["i"] not in exclude_hosts]
    if not small or not hosts:
        return {"n_merged": 0, "n_left": len(small), **_public_parts_payload(token, parts)}
    attach = {}
    left = []
    for s in small:
        best = min(hosts, key=lambda h: _bbox_gap(s["bb_min"], s["bb_max"], h["bb_min"], h["bb_max"]))
        gap = _bbox_gap(s["bb_min"], s["bb_max"], best["bb_min"], best["bb_max"])
        if gap <= MERGE_GAP_MM:
            attach.setdefault(best["i"], []).append(s)
        else:
            left.append(s)
    v = int(time.time() * 1000)
    new_parts = [p for p in parts if p["i"] in exclude_hosts and p["i"] not in ids]
    for h in hosts:
        if h["i"] in attach:
            members = h["members"] + [m for s in attach[h["i"]] for m in s["members"]]
            np_ = _part_from_members(d, h["i"], members, h["name"], h["n_merged_ops"] + len(attach[h["i"]]), v)
            np_["node"] = h.get("node", "")
            np_["suggested_part_id"] = h.get("suggested_part_id")
            np_["suggest_kind"] = h.get("suggest_kind")
            np_["fragment"] = False
            if h.get("joined_from"):
                np_["joined_from"] = h["joined_from"]
            new_parts.append(np_)
        else:
            new_parts.append(h)
    new_parts.extend(left)
    meta["parts"] = sorted(new_parts, key=lambda p: p["i"])
    _write_meta(d, meta)
    n_merged = sum(len(v_) for v_ in attach.values())
    return {"n_merged": n_merged, "n_left": len(left), **_public_parts_payload(token, meta["parts"])}


@app.post("/api/admin/universal-import/<token>/remove")
@require_permission("rozklad_fbx", "upravit")
def universal_import_remove(token):
    """Robert 2026-09-30 ("nejake delete tlacitko se hodi"): dil z importu
    uplne odstranit (na rozdil od 'preskocit', ktere ho necha v tabulce)."""
    d = _token_dir(token)
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import."}), 404
    body = request.get_json(silent=True) or {}
    try:
        ids = {int(x) for x in (body.get("parts") or [])}
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné indexy dílů."}), 400
    if not ids:
        return jsonify({"error": "Označ díly ke smazání."}), 400
    meta = _read_meta(d)
    meta["parts"] = [p for p in meta["parts"] if p["i"] not in ids]
    _write_meta(d, meta)
    return jsonify({"removed": sorted(ids), **_public_parts_payload(token, meta["parts"])})


@app.delete("/api/admin/universal-import/<token>")
@require_permission("rozklad_fbx", "upravit")
def universal_import_cancel(token):
    d = _token_dir(token)
    if d:
        shutil.rmtree(d, ignore_errors=True)
    return jsonify({"status": "ok"})


@app.post("/api/admin/universal-import/<token>/split")
@require_permission("rozklad_fbx", "upravit")
def universal_import_split(token):
    d = _token_dir(token)
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import."}), 404
    body = request.get_json(silent=True) or {}
    try:
        i = int(body.get("i"))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatný index dílu."}), 400
    meta = _read_meta(d)
    by_i = {p["i"]: p for p in meta["parts"]}
    part = by_i.get(i)
    if not part or not part.get("joined_from"):
        return jsonify({"error": "Tenhle díl nevznikl spojením - není co rozpojit."}), 400
    restored = []
    v = int(time.time() * 1000)
    for orig in part["joined_from"]:
        r = _part_from_members(d, orig["i"], orig["members"], orig["name"], orig["n_merged_ops"], v)
        r["node"] = orig.get("node", "")
        r["suggested_part_id"] = orig.get("suggested_part_id")
        if orig.get("joined_from"):
            r["joined_from"] = orig["joined_from"]
        restored.append(r)
    others = [p for p in meta["parts"] if p["i"] != i]
    meta["parts"] = sorted(others + restored, key=lambda p: p["i"])
    _write_meta(d, meta)
    return jsonify({"split_i": i, **_public_parts_payload(token, meta["parts"])})


@app.get("/api/admin/universal-import/<token>/part/<int:i>.glb")
@staff_required
def universal_import_preview_glb(token, i):
    d = _token_dir(token)
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import."}), 404
    path = os.path.join(d, f"part_{i}.glb")
    if not os.path.isfile(path):
        return jsonify({"error": "Díl nenalezen."}), 404
    return send_file(path, mimetype="model/gltf-binary", max_age=0)


def _profile_part_spec(part, cat_entry, part_pos=None, card_pos=None, warnings=None):
    """Profil: stred bboxu, delka = nejdelsi osa dilu, scale y = delka / L0
    (stejne jako dimension_match_fbx.build_parts). S geometrii (part_pos =
    vrcholy dilu, card_pos = vrcholy GLB profilu) navic (bot8, 2026-10-01):
    natoceni KOLEM DELKY podle tvaru prurezu (uzavreny profil, drazky, 30x60
    na vysku/na sirku - driv pevne podle osy) a vyrovnani stredu GLB
    (profil_30x30_uzavreny ma prurez 0,75 mm mimo pocatek). Pri shode vice
    natoceni (soumerny prurez) zustava puvodni natoceni podle osy."""
    global _ROTATIONS
    lo = np.array(part["bb_min"], dtype=np.float64)
    hi = np.array(part["bb_max"], dtype=np.float64)
    size = hi - lo
    axis = int(np.argmax(size))
    actual_len = float(size[axis])
    legacy = {1: [0.0, 0.0, 0.0, 1.0], 0: [0.0, 0.0, -_S2, _S2], 2: [_S2, 0.0, 0.0, _S2]}[axis]
    center = (lo + hi) / 2.0
    scale = np.array([1.0, actual_len / cat_entry["L0"], 1.0])
    q, card_center = legacy, np.zeros(3)
    if card_pos is not None:
        from scipy.spatial import cKDTree
        if _ROTATIONS is None:
            _ROTATIONS = _proper_axis_rotations()
        card_pos = np.asarray(card_pos, dtype=np.float64)
        c_lo, c_hi = card_pos.min(axis=0), card_pos.max(axis=0)
        card_center, card_ext = (c_lo + c_hi) / 2.0, c_hi - c_lo
        others = [k for k in range(3) if k != axis]
        m_legacy = _quat_matrix(legacy)
        cands = [(m, qq) for m, qq in _ROTATIONS if abs(m[axis, 1]) > 0.5
                 and np.max(np.abs((np.abs(m) @ (scale * card_ext))[others] - size[others])) <= 1.0]
        if not cands:
            if warnings is not None:
                warnings.append(f"průřez karty {card_ext[0]:.0f}×{card_ext[2]:.0f} mm nesedí na díl "
                                f"{size[others[0]]:.0f}×{size[others[1]]:.0f} mm - vložen s natočením podle osy")
        else:
            rng = np.random.default_rng(0)

            def section(pts):
                s = np.unique(np.round(pts, 1), axis=0)
                return s[rng.choice(len(s), SECTION_MAX_POINTS, replace=False)] if len(s) > SECTION_MAX_POINTS else s
            best = None
            if part_pos is not None:
                psec = section((np.asarray(part_pos, dtype=np.float64) - center)[:, others])
                tp = cKDTree(psec)
                local = card_pos - card_center
                local[:, 1] = 0.0
                for m, qq in cands:
                    csec = section((local @ m.T)[:, others])
                    d1, _ = tp.query(csec, distance_upper_bound=SECTION_TOL_MM)
                    d2, _ = cKDTree(csec).query(psec, distance_upper_bound=SECTION_TOL_MM)
                    cov = min(float(np.mean(np.isfinite(d1))), float(np.mean(np.isfinite(d2))))
                    is_legacy = bool(np.allclose(m, m_legacy, atol=1e-6))
                    if best is None or cov > best[0] + 0.02 or (abs(cov - best[0]) <= 0.02 and is_legacy and not best[2]):
                        best = (cov, qq, is_legacy)
            if best is not None:
                q = best[1]
            else:
                q = legacy if any(np.allclose(m, m_legacy, atol=1e-6) for m, _ in cands) else cands[0][1]
    m = _quat_matrix(q)
    position = center - m @ (scale * card_center)
    return {
        "part_id": cat_entry["id"],
        "position": [round(float(v), 2) for v in position],
        "quaternion": [round(float(v), 6) for v in q],
        "scale": [1.0, round(float(scale[1]), 6), 1.0],
    }


_AXIS_PERMS = [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]


def _proper_axis_rotations():
    """24 vlastnich rotaci krychle (matice + kvaternion [x,y,z,w])."""
    from scipy.spatial.transform import Rotation as R
    out = []
    for perm in _AXIS_PERMS:
        for signs in ((1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)):
            m = np.zeros((3, 3))
            for row in range(3):
                m[row, perm[row]] = signs[row]
            if abs(np.linalg.det(m) - 1.0) < 1e-9:
                q = R.from_matrix(m).as_quat()  # x, y, z, w
                out.append((m, [float(v) for v in q]))
    return out


_ROTATIONS = None


def _best_axis_rotation(pos_ref_centered, pos_member_centered, tol_mm=0.8, symmetric=False, rotations=None,
                        ranked=False):
    """Najde z 24 osove zarovnanych rotaci tu, pri ktere rotovany REFERENCNI
    mrak nejlip pokryje mrak dalsiho kusu (stejny dil jinak natoceny - napr.
    4 kolecka). Vraci (kvaternion, pokryti 0..1).

    Podvzorkuje se jen mrak, ktery se dotazuje (a), strom se stavi nad CELYM
    druhym mrakem - driv se podvzorkovaly oba nezavisle a u dilu nad ~6500
    bodu spravna rotace propadla pod 0,9 (nahodne podmnoziny si neodpovidaly;
    test 2026-10-01: 20 000 bodu -> pokryti 0,32).

    symmetric=True: pokryti se bere v obou smerech (min) - jinak by pulka dilu
    "sedela" na celou kartu (vsechny jeji body lezi na celku).
    rotations: jen tyto [(matice, kvaternion)] (predvyber podle obalky).
    ranked=True: vraci vsechny [(kvaternion, pokryti, matice)] od nejlepsiho."""
    global _ROTATIONS
    from scipy.spatial import cKDTree
    if _ROTATIONS is None:
        _ROTATIONS = _proper_axis_rotations()
    a_full = np.unique(np.round(np.asarray(pos_ref_centered, dtype=np.float64), 1), axis=0)
    b_full = np.unique(np.round(np.asarray(pos_member_centered, dtype=np.float64), 1), axis=0)
    a, b = a_full, b_full
    if len(a) > SECTION_MAX_POINTS:
        a = a[np.random.default_rng(0).choice(len(a), SECTION_MAX_POINTS, replace=False)]
    if len(b) > SECTION_MAX_POINTS:
        b = b[np.random.default_rng(0).choice(len(b), SECTION_MAX_POINTS, replace=False)]
    tb = cKDTree(b_full)
    ta = cKDTree(a_full) if symmetric else None
    best_q, best_cov = [0.0, 0.0, 0.0, 1.0], 0.0
    allr = []
    for m, q in (rotations if rotations is not None else _ROTATIONS):
        dist, _ = tb.query(a @ m.T, distance_upper_bound=tol_mm)
        cov = float(np.mean(np.isfinite(dist)))
        if symmetric and (cov > best_cov or ranked):
            # b zpet do soustavy a (m je ortogonalni: inverze = transpozice) - strom jen jednou
            dist_b, _ = ta.query(b @ m, distance_upper_bound=tol_mm)
            cov = min(cov, float(np.mean(np.isfinite(dist_b))))
        allr.append((q, cov, m))
        if cov > best_cov:  # vsech 24 (driv konec pri >= 0.995 = u skoro soumerneho dilu spatna z rovnocennych)
            best_q, best_cov = q, cov
    if ranked:
        return sorted(allr, key=lambda x: -x[1])
    return best_q, best_cov


# --- Umisteni EXISTUJICI katalogove karty na misto dilu z FBX (bot8, 2026-10-01)
# Robert 2026-09-30: "nacitany fbx byl sestaveny jak je potreba, ale potom pri
# sestaveni tvaru se to rozhodilo" + "ten vkladaci mechanismus ale musi byt
# autonomni" + (desky) "nebudeme prece davat do katalogu kazdy rozmer, proste
# si to system dopocita". Puvodne se u karty predpokladal GLB vycentrovany a
# v osach sceny (position = stred dilu, identita) - to plati jen u novych
# karet z importu. 802 z 836 GLB katalogu vycentrovanych neni (Dogus STEP,
# admin upload FBX pres fbx_convert = souradnice z Rhina a osy FBX, Blender/
# Vandr exporty s transformacemi uzlu) a scena i 530 ulozenych sestav s tim
# pocitaji (placeAtOrigin pri vlozeni z katalogu), takze GLB se NEPREPISUJI -
# import si umisteni dopocita sam z geometrie. Scena kresli dil jako
# svet = position + R*(scale*v_glb) (loadCustomShapePartEntry, v_glb vc.
# transformaci uzlu), odtud position = stred_dilu - R*(scale*stred_GLB).
EXISTING_MATCH_MIN = 0.9        # obousmerne pokryti vrcholu karty a dilu (presna shoda)
EXACT_TOL_MM = 0.2              # presna shoda: vrchol do 0,2 mm (tentyz export; zaokrouhleni na 0,1 mm)
EXISTING_EXTENT_TOL_MM = 1.0    # tloustka desky: dil vs. karta
EXTENT_TOL_MM = 1.5             # obalka karty vs. dil: "stejny rozmer" (absolutne ...)
EXTENT_TOL_REL = 0.005          # ... nebo 0,5 % rozmeru, co je vic
EXTRA_WARN_MM = 5.0             # dil presahuje kartu o vic -> varovani "dil ma navic"
SURFACE_TREE_MAX = 30000        # husty vzorek povrchu (strom): ~1 bod na SURFACE_SPACING_MM^2 ...
SURFACE_TREE_MIN = 2000         # ... v mezich (drobne pasky ne 30 000 bodu na 29 mm2 - kontrola 5. kola)
SURFACE_SPACING_MM = 0.5        # jemne i u drobnych dilu (kluzak 17x24x80 = strop); sum se meri
SURFACE_QUERY_N = 4000          # kolik bodu se dotazuje pri odhadu prumerne vzdalenosti
FIT_FACTOR, FIT_ABS_MM = 1.3, 0.3   # "lezi na povrchu": prumer <= 1,3 * sum vzorkovani + 0,3 mm
FIT99_FACTOR, FIT99_ABS_MM = 3.0, 1.0  # ... a 99. percentil <= 3 * sum + 1 mm (mistni rozdil: zrcadlo, drzak)
AMBIG_ABS, AMBIG_REL = 0.03, 0.02    # dve natoceni s timto rozdilem (normovaneho) skore = nejiste
SMALL_PIECE_VOL = 0.5           # dil s obalkou pod 50 % objemu obalky karty = kus vyrobku, poloha se nehleda
COARSE_N = 150                  # hruby odhad: tolik bodu na smer ...
COARSE_ROT_TOP = 4              # ... 1) natoceni na stredu, 2) kotvy (po osach) jen u tolika nejlepsich ...
FINE_TOP = 3                    # ... 3) jemne (SURFACE_QUERY_N bodu) jen tolik nejlepsich kombinaci
PLACE_BUDGET_S = 35.0           # umistovani existujicich karet: po teto dobe zbytek zjednodusene (gunicorn 60 s)
MERGE_MAX_EVAL = 6              # rozdeleny vyrobek: nejvys tolik overeni tvaru na jedno seminko
EXACT_PERFECT = 0.995           # presna shoda s timto pokrytim je jista (bez kontroly skoro soumerneho natoceni)
BOARD_RECT_FILL_MIN = 0.95      # plocha obrysu desky / obdelnik prirezu; mene = tvar/vyrez
BOARD_AXIS_PREF_MM = 0.2        # deska: svetova osa ma prednost pred sikmou normalou do tohoto rozdilu
# desky: GLB 1000x1000 s tloustkou v lokalni ose; natoceni podle toho, kam ve
# svete miri tloustka dilu - stejne 3 konvence jako 1648 ulozenych desek
# (vodorovna = LENGTH_TILT, svisla XY = identita, svisla YZ = 90 st. kolem Y)
_BOARD_QUAT_FOR_LOCAL_Z = {1: [-_S2, 0.0, 0.0, _S2], 2: [0.0, 0.0, 0.0, 1.0], 0: [0.0, _S2, 0.0, _S2]}
_GLTF_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _quat_matrix(q):
    from scipy.spatial.transform import Rotation as R
    return R.from_quat(q).as_matrix()


def _matrix_quat(m):
    from scipy.spatial.transform import Rotation as R
    return [float(v) for v in R.from_matrix(m).as_quat()]


def _gltf_node_matrix(n):
    if n.get("matrix"):
        return np.array(n["matrix"], dtype=np.float64).reshape(4, 4).T  # glTF = sloupcove
    m = np.eye(4)
    m[:3, :3] = _quat_matrix(n.get("rotation") or [0, 0, 0, 1]) * np.asarray(n.get("scale") or [1, 1, 1], dtype=np.float64)
    m[:3, 3] = n.get("translation") or [0, 0, 0]
    return m


def _glb_mesh(path):
    """(vrcholy Nx3 float64, trojuhelniky Mx3) GLB presne tak, jak ho kresli
    scena (gltf.scene): vsechny meshe vsech uzlu vychozi sceny VCETNE
    transformaci uzlu (Blender/Vandr exporty maji matice, metry, prohozene
    osy). Trojuhelniky jen z primitiv mode 4; bez indexu = po trojicich.
    None, kdyz soubor neni GLB nebo nema geometrii."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        return None
    length = struct.unpack("<I", data[8:12])[0]
    off, g, binc = 12, None, None
    while off < length:
        clen, ctype = struct.unpack("<I4s", data[off:off + 8])
        chunk = data[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            g = json.loads(chunk.decode("utf-8", "replace"))
        elif ctype == b"BIN\x00":
            binc = chunk
        off += 8 + clen
    if not g or binc is None:
        return None

    def accessor(ai):
        acc = g["accessors"][ai]
        dt = np.dtype(_ACC_DTYPE.get(acc["componentType"], np.float32))
        nc = _GLTF_NCOMP.get(acc.get("type"), 1)
        n = int(acc["count"])
        if n == 0 or "bufferView" not in acc:
            return np.zeros((n, nc), dtype=dt)
        bv = g["bufferViews"][acc["bufferView"]]
        base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = bv.get("byteStride") or nc * dt.itemsize
        if stride == nc * dt.itemsize:
            return np.frombuffer(binc, dtype=dt, count=n * nc, offset=base).reshape(n, nc)
        return np.stack([np.frombuffer(binc, dtype=dt, count=nc, offset=base + k * stride) for k in range(n)])

    nodes = g.get("nodes") or []
    scenes = g.get("scenes") or []
    if scenes:
        roots = list(scenes[g.get("scene", 0) or 0].get("nodes") or [])
    else:
        children = {c for n in nodes for c in (n.get("children") or [])}
        roots = [k for k in range(len(nodes)) if k not in children]
    all_pos, all_tri, vbase = [], [], 0
    stack = [(r, np.eye(4)) for r in roots]
    guard = 0
    while stack and guard < 100000:
        guard += 1
        k, parent = stack.pop()
        node = nodes[k]
        mtx = parent @ _gltf_node_matrix(node)
        if node.get("mesh") is not None:
            for prim in g["meshes"][node["mesh"]].get("primitives") or []:
                pa = prim.get("attributes", {}).get("POSITION")
                if pa is None:
                    continue
                pos = accessor(pa).astype(np.float64)[:, :3]
                pos = pos @ mtx[:3, :3].T + mtx[:3, 3]
                if prim.get("mode", 4) == 4:
                    idx = accessor(prim["indices"]).reshape(-1) if prim.get("indices") is not None else np.arange(len(pos))
                    tri = idx[: len(idx) // 3 * 3].astype(np.int64).reshape(-1, 3)
                    tri = tri[(tri < len(pos)).all(axis=1)] + vbase
                    all_tri.append(tri)
                all_pos.append(pos)
                vbase += len(pos)
        stack.extend((c, mtx) for c in (node.get("children") or []))
    if not all_pos:
        return None
    tris = np.concatenate(all_tri) if all_tri else np.zeros((0, 3), dtype=np.int64)
    return np.concatenate(all_pos), tris


def _card_glb_path(kp):
    fname = (kp.get("file") or "").split("?")[0]
    if fname.startswith("katalog/"):
        fname = fname[len("katalog/"):]
    if not fname or "_PENDING_" in fname:
        return None
    path = os.path.join(KATALOG_GLB_DIR, fname)
    return path if os.path.isfile(path) else None


def _card_geometry(kp):
    """((vrcholy, trojuhelniky), None), nebo (None, duvod)."""
    path = _card_glb_path(kp)
    if not path:
        return None, "karta nemá 3D model (chybí soubor nebo čeká na převod)"
    try:
        mesh = _glb_mesh(path)
    except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error):
        return None, "3D model karty nejde přečíst"
    if mesh is None or len(mesh[0]) < 4:
        return None, "3D model karty je prázdný"
    return mesh, None


def _surface_cloud(pos, tris, seed):
    """Husty vzorek povrchu (body rovnomerne po plose, ~1 na SURFACE_SPACING_MM^2
    v mezich SURFACE_TREE_MIN..MAX) - srovnani dvou siti TEHOZ tvaru s ruznou
    teselaci. Bez trojuhelniku = unikatni vrcholy. Jemne i u drobnych dilu
    (kluzak 17x24x80 - jinak 2mm nesoumernost zanikne v sumu, kontrola 3. kola),
    ale ne 30 000 bodu na pasek 29 mm2 (pomale hledani, kontrola 5. kola)."""
    pos = np.asarray(pos, dtype=np.float64)
    if tris is None or len(tris) == 0:
        return np.unique(np.round(pos, 1), axis=0)
    tris = np.asarray(tris, dtype=np.int64)
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    total = float(area.sum())
    if total <= 0:
        return np.unique(np.round(pos, 1), axis=0)
    n = int(min(SURFACE_TREE_MAX, max(SURFACE_TREE_MIN, total / SURFACE_SPACING_MM ** 2)))
    rng = np.random.default_rng(seed)
    k = rng.choice(len(tris), n, p=area / total)
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    return a[k] + u[:, None] * (b[k] - a[k]) + v[:, None] * (c[k] - a[k])


class _SurfaceCtx:
    """Povrch jednoho telesa pro porovnani: obalka, husty vzorek (vycentrovany na
    stred obalky) se stromem, mensi dotazovaci vzorek a SUM VZORKOVANI (prumerna
    vzdalenost nezavisleho druheho vzorku teho povrchu k prvnimu - tolik vychazi
    i u dokonale shodnych povrchu; prah "lezi na povrchu" se k nemu vztahuje).
    Karta se pocita jednou pro vsechny dily (_place_existing_cards)."""

    def __init__(self, pos, tris, seed=11):
        from scipy.spatial import cKDTree
        pos = np.asarray(pos, dtype=np.float64)
        tris = None if tris is None or len(tris) == 0 else np.asarray(tris, dtype=np.int64).reshape(-1, 3)
        lo, hi = pos.min(axis=0), pos.max(axis=0)
        self.pos, self.tris = pos, tris
        self.lo, self.hi, self.center, self.ext = lo, hi, (lo + hi) / 2.0, hi - lo
        cloud = _surface_cloud(pos, tris, seed) - self.center
        rng = np.random.default_rng(seed + 1)
        if tris is not None:
            self.cloud = cloud
            other = _surface_cloud(pos, tris, seed + 2) - self.center
        else:  # jen vrcholy: sum = vzdalenost dvou disjunktnich polovin
            perm = rng.permutation(len(cloud))
            half = max(1, len(cloud) // 2)
            self.cloud, other = cloud[perm[:half]], cloud[perm[half:]] if len(cloud) > 1 else cloud
        self.tree = cKDTree(self.cloud)
        self.query = self.cloud if len(self.cloud) <= SURFACE_QUERY_N else \
            self.cloud[rng.choice(len(self.cloud), SURFACE_QUERY_N, replace=False)]
        self.coarse = self.query if len(self.query) <= COARSE_N else \
            self.query[rng.choice(len(self.query), COARSE_N, replace=False)]
        oq = other if len(other) <= SURFACE_QUERY_N else other[rng.choice(len(other), SURFACE_QUERY_N, replace=False)]
        self.base = float(self.tree.query(oq)[0].mean()) if len(oq) else 0.0

    def fit_mm(self):
        return FIT_FACTOR * self.base + FIT_ABS_MM

    def fit99_mm(self):
        return FIT99_FACTOR * self.base + FIT99_ABS_MM


def _extent_tol(ext):
    return np.maximum(EXTENT_TOL_MM, EXTENT_TOL_REL * np.asarray(ext, dtype=np.float64))


def _rotation_candidates(card_ext, part_ext):
    """[(m, q, rozdil_obalky)] z 24 osovych rotaci. rozdil = |m|*karta - dil."""
    global _ROTATIONS
    if _ROTATIONS is None:
        _ROTATIONS = _proper_axis_rotations()
    return [(m, q, np.abs(m) @ card_ext - part_ext) for m, q in _ROTATIONS]


def _pair_score(part, card, m, T, cap, coarse=False):
    """Vzdalenosti vzorku pro kartu natocenou m se stredem v T (svet):
    (dil->karta prumer, 99. percentil, karta->dil prumer, 99. percentil).
    Body dilu se prevadeji do soustavy karty (m^T), oba stromy jen jednou.
    cap: vzdalenejsi body se nedohledavaji (u spatne polohy je hledani daleko
    od stromu pomale - kontrola 3. kola: 70 ms/volani, eurobox 17 s) a
    pocitaji se hodnotou cap."""
    pq, cq = (part.coarse, card.coarse) if coarse else (part.query, card.query)
    d1 = np.minimum(card.tree.query((pq + part.center - T) @ m, distance_upper_bound=cap)[0], cap)
    d2 = np.minimum(part.tree.query(cq @ m.T + T - part.center, distance_upper_bound=cap)[0], cap)
    if coarse:  # hruby odhad potrebuje jen prumery (percentil = trideni navic)
        return float(d1.mean()), 0.0, float(d2.mean()), 0.0
    return float(d1.mean()), float(np.percentile(d1, 99)), float(d2.mean()), float(np.percentile(d2, 99))


def _surface_match(part, card):
    """Natoceni + posun karty podle POVRCHU (jina sit, drobnost navic, dil jen
    cast karty). Zkousi rotace, jejichz obalka sedi, je uvnitr dilu, nebo dil
    uvnitr ni; na osach s rozdilem obalky kotvi kartu k jednomu i druhemu konci
    i na stred (dil s utrzkem na konci -> karta na shodny konec). Vraci dict
    m, q, T, p2c, c2p, diff, ambiguous (jine natoceni skoro stejne dobre a
    karta neni vuci nemu soumerna)."""
    tol = _extent_tol(part.ext)
    cands = _rotation_candidates(card.ext, part.ext)
    ext_err = lambda c: float(np.sum(np.abs(c[2])))  # noqa: E731
    pool = [c for c in cands if np.all(c[2] <= tol) or np.all(c[2] >= -tol)]
    if not pool:
        pool = sorted(cands, key=ext_err)[:4]
    cf, pf = card.fit_mm(), part.fit_mm()
    cap = max(5.0, 4.0 * max(card.fit99_mm(), part.fit99_mm()))
    # dil vsude mensi nez karta = kus vyrobku rozdeleneho v FBX (nebo jiny dil):
    # jeho vlastni poloha uvnitr karty se nehleda (az 24 natoceni x 27 kotev),
    # rozhodne sjednoceni kusu (_merge_split_parts) / usazena karta (_absorb_pieces)
    inside_only = all(not np.all(c[2] <= tol) for c in pool) and all(np.all(c[2] >= -tol) for c in pool)
    if inside_only and float(np.prod(part.ext + 1.0) / np.prod(card.ext + 1.0)) < SMALL_PIECE_VOL:
        m, q, diff = min(pool, key=ext_err)
        return {"m": m, "q": q, "T": part.center.copy(), "p2c": np.inf, "p2c99": np.inf, "c2p": np.inf,
                "c2p99": np.inf, "diff": diff, "score": np.inf, "ambiguous": False, "small_piece": True}

    def score_of(p2c, c2p, card_in_part, part_in_card):
        # skore normovane prahy "lezi na povrchu"; rozhoduje smer, ktery ma
        # pri dane obalce platit: karta uvnitr dilu (dil ma navic) -> karta
        # musi lezet na dilu; dil uvnitr karty (cast vyrobku) -> dil na karte
        if card_in_part and not part_in_card:
            return c2p / pf
        if part_in_card and not card_in_part:
            return p2c / cf
        return (p2c / cf + c2p / pf) / 2.0 + (0.0 if card_in_part else 10.0)

    def coarse_score(c):
        p2c, _, c2p, _ = _pair_score(part, card, c[0], c[3], cap, coarse=True)
        return score_of(p2c, c2p, c[4], c[5])

    # 1) kazde natoceni hrube na stredu dilu, 2) kotvy ke koncum jen u COARSE_ROT_TOP
    # nejlepsich, 3) jemne jen FINE_TOP kombinaci (kontrola 4./5. kola: krychle uvnitr
    # karty 24 natoceni x 27 kotev = 648 hodnoceni = 4 s/dil, SSE stul 100 s)
    rots = []
    for m, q, diff in pool:
        cin, pin = bool(np.all(diff <= tol)), bool(np.all(diff >= -tol))
        rots.append((m, q, diff, part.center.copy(), cin, pin))
    if len(rots) > COARSE_ROT_TOP:
        rots = [c for _, _, c in sorted(((coarse_score(c), k, c) for k, c in enumerate(rots)),
                                        key=lambda x: (x[0], x[1]))[:COARSE_ROT_TOP]]
    combos = []
    for m, q, diff, _c, cin, pin in rots:
        wext = np.abs(m) @ card.ext
        T = part.center.copy()
        combos.append((m, q, diff, T.copy(), cin, pin))
        # kotvy po osach nezavisle (3 + 3 + 3 misto 3 x 3 x 3 kombinaci): na kazde
        # ose s rozdilem obalky stred / jeden konec / druhy konec, ostatni osy na stredu
        moved = False
        for k in range(3):
            if abs(diff[k]) <= tol[k]:
                continue
            best_k = None
            for v in (part.center[k], part.lo[k] + wext[k] / 2.0, part.hi[k] - wext[k] / 2.0):
                Tk = part.center.copy()
                Tk[k] = v
                sc = coarse_score((m, q, diff, Tk, cin, pin))
                if best_k is None or sc < best_k[0] - 1e-12:
                    best_k = (sc, v)
            if best_k[1] != part.center[k]:
                T[k] = best_k[1]
                moved = True
        if moved:
            combos.append((m, q, diff, T, cin, pin))
    if len(combos) > FINE_TOP:
        combos = [c for _, _, c in sorted(((coarse_score(c), k, c) for k, c in enumerate(combos)),
                                          key=lambda x: (x[0], x[1]))[:FINE_TOP]]
    results = []
    for m, q, diff, T, card_in_part, part_in_card in combos:
        p2c, p2c99, c2p, c2p99 = _pair_score(part, card, m, T, cap)
        results.append({"m": m, "q": q, "T": T, "p2c": p2c, "p2c99": p2c99, "c2p": c2p, "c2p99": c2p99,
                        "diff": diff, "score": score_of(p2c, c2p, card_in_part, part_in_card)})
    results.sort(key=lambda r: r["score"])
    best = results[0]
    best["ambiguous"] = False
    best["small_piece"] = False
    margin = AMBIG_ABS + AMBIG_REL * best["score"]
    for r in results[1:]:
        if r["score"] > best["score"] + margin:
            break
        rel = best["m"].T @ r["m"]
        if np.allclose(rel, np.eye(3), atol=1e-6):
            continue
        # karta soumerna vuci relativni rotaci -> obe natoceni daji tentyz tvar, neni co hlasit;
        # soumernost i podle 99. percentilu (drobny nesoumerny prvek = NEsoumerna)
        d = np.minimum(card.tree.query(card.query @ rel.T, distance_upper_bound=cap)[0], cap)
        if float(d.mean()) > card.fit_mm() or float(np.percentile(d, 99)) > card.fit99_mm():
            best["ambiguous"] = True
            break
    return best


def _min_area_rect(pts2):
    """(uhel osy obdelniku, rozmery [a, b], stred 2D, zaplneni obrysem) -
    nejmensi opsany obdelnik (rotating calipers nad konvexnim obalem)."""
    from scipy.spatial import ConvexHull
    try:
        hull = ConvexHull(pts2)
    except Exception:  # noqa: BLE001 - degenerovany (prilis malo bodu / primka)
        lo, hi = pts2.min(axis=0), pts2.max(axis=0)
        return 0.0, hi - lo, (lo + hi) / 2.0, 1.0
    hp = pts2[hull.vertices]
    best = None
    for k in range(len(hp)):
        e = hp[(k + 1) % len(hp)] - hp[k]
        if float(np.hypot(e[0], e[1])) < 1e-9:
            continue
        ang = float(np.arctan2(e[1], e[0])) % (np.pi / 2)
        c, s = np.cos(ang), np.sin(ang)
        rot = hp @ np.array([[c, s], [-s, c]]).T  # souradnice v osach (u, v) otocenych o ang
        lo, hi = rot.min(axis=0), rot.max(axis=0)
        area = float(np.prod(hi - lo))
        if best is None or area < best[0] - 1e-6:
            best = (area, ang, lo, hi)
    area, ang, lo, hi = best
    c, s = np.cos(ang), np.sin(ang)
    mid = (lo + hi) / 2.0
    center = np.array([c * mid[0] - s * mid[1], s * mid[0] + c * mid[1]])
    return ang, hi - lo, center, (float(hull.volume) / area) if area > 0 else 1.0


def _board_normal(part_pos, part_tris, card_thick):
    """Normala desky = smer, ve kterem ma dil TLOUSTKU KARTY. Kandidati:
    3 svetove osy (prednost - osove ulozena deska se nesmi naklopit kvuli
    nesoumerne siti, otvorum nebo duplicitnim vrcholum) a hlavni smery normal
    trojuhelniku vazenych plochou (bez trojuhelniku smery rozptylu vrcholu) -
    pro sikmo ulozenou desku. Lista uzsi nez tloustka karty (1000x12x18 z
    desky 18) tak dostane tloustku 18, ne 12."""
    part_pos = np.asarray(part_pos, dtype=np.float64)
    cands = [(np.eye(3)[k], True) for k in range(3)]
    if part_tris is not None and len(part_tris):
        t = np.asarray(part_tris, dtype=np.int64)
        nrm = np.cross(part_pos[t[:, 1]] - part_pos[t[:, 0]], part_pos[t[:, 2]] - part_pos[t[:, 0]])
        # |n| = 2*plocha: tenzor sum(n n^T)/|n| = sum(plocha * jednotkova normala^2)
        ln = np.linalg.norm(nrm, axis=1)
        ok = ln > 1e-12
        tensor = (nrm[ok].T * (1.0 / ln[ok])) @ nrm[ok]
        evecs = np.linalg.eigh(tensor)[1]
    else:
        evecs = np.linalg.eigh(np.cov((part_pos - part_pos.mean(axis=0)).T))[1]
    cands += [(evecs[:, k] / np.linalg.norm(evecs[:, k]), False) for k in range(3)]
    scored = []
    for n, is_axis in cands:
        along = part_pos @ n
        scored.append((abs(float(along.max() - along.min()) - card_thick), is_axis, n))
    best_err = min(s[0] for s in scored)
    axis_best = min((s for s in scored if s[1]), key=lambda s: s[0])
    if axis_best[0] <= best_err + BOARD_AXIS_PREF_MM:
        return axis_best[2], True
    return min(scored, key=lambda s: s[0])[2], False


def _board_placement(part_pos, part_tris, card_center, card_ext):
    """Deska (is_board_material): rovina podle tloustky karty (_board_normal),
    v rovine nejmensi opsany obdelnik, rozmer v rovine pres scale (tloustka 1).
    Osove ulozena deska dostane jednu ze 3 zavedenych konvenci
    (_BOARD_QUAT_FOR_LOCAL_Z). Vraci (m, q, scale, position, varovani[])."""
    part_pos = np.asarray(part_pos, dtype=np.float64)
    warns = []
    t_local = int(np.argmin(card_ext))
    plane_local = [k for k in range(3) if k != t_local]
    n, n_is_axis = _board_normal(part_pos, part_tris, float(card_ext[t_local]))
    if n_is_axis:
        axis_hit = int(np.argmax(np.abs(n)))
        n = np.eye(3)[axis_hit]
        u0, v0 = [np.eye(3)[k] for k in range(3) if k != axis_hit]
    else:
        axis_hit = None
        u0 = np.cross(n, np.eye(3)[int(np.argmin(np.abs(n)))])
        u0 /= np.linalg.norm(u0)
        v0 = np.cross(n, u0)
    pts2 = np.stack([part_pos @ u0, part_pos @ v0], axis=1)
    ang, dims2, center2, fill = _min_area_rect(pts2)
    along_n = part_pos @ n
    thick = float(along_n.max() - along_n.min())
    center = center2[0] * u0 + center2[1] * v0 + (along_n.max() + along_n.min()) / 2.0 * n
    aligned = n_is_axis and min(ang, np.pi / 2 - ang) < np.radians(0.05)
    scale = np.ones(3)
    if aligned and t_local == 2:
        q = _BOARD_QUAT_FOR_LOCAL_Z[axis_hit]
        m = _quat_matrix(q)
        lo, hi = part_pos.min(axis=0), part_pos.max(axis=0)
        want_local = np.abs(m).T @ (hi - lo)
        for k in plane_local:
            scale[k] = want_local[k] / card_ext[k]
        center = (lo + hi) / 2.0
    else:
        c, s = np.cos(ang), np.sin(ang)
        e1 = c * u0 + s * v0
        e2 = np.cross(n, e1)
        m = np.zeros((3, 3))
        m[:, plane_local[0]] = e1
        m[:, plane_local[1]] = e2
        m[:, t_local] = n
        if np.linalg.det(m) < 0:
            m[:, plane_local[1]] = -e2
        q = _matrix_quat(m)
        scale[plane_local[0]] = dims2[0] / card_ext[plane_local[0]]
        scale[plane_local[1]] = dims2[1] / card_ext[plane_local[1]]
    fmt = lambda e: "×".join(f"{v:.0f}" for v in e)  # noqa: E731
    if abs(thick - card_ext[t_local]) > EXISTING_EXTENT_TOL_MM:
        warns.append(f"jiná tloušťka desky než karta (karta {card_ext[t_local]:.1f} mm, díl {thick:.1f} mm) - "
                     f"rozměr v rovině dopočítán, tloušťka ne")
    if fill < BOARD_RECT_FILL_MIN:
        warns.append(f"deska není obdélník (šikmá hrana / výřez, obrys zaplní {fill * 100:.0f} % přířezu) - "
                     f"vložena jako obdélníkový přířez {fmt(sorted(dims2))} mm, cena podle přířezu")
    position = center - m @ (scale * card_center)
    return m, q, scale, position, warns


def _existing_card_spec(part_pos, card_pos, is_board=False, part_tris=None, card_tris=None, card_ctx=None):
    """Umisteni katalogove karty (GLB s libovolnym pocatkem a natocenim) na
    misto dilu z FBX. part_pos = vrcholy dilu v osach sceny, card_pos =
    vrcholy GLB karty tak, jak je scena nacte (vc. transformaci uzlu);
    card_ctx = predpocitany _SurfaceCtx karty (sdileny pro vic dilu).
    Vraci (spec, zpusob, odchylka_mm, varovani|None); zpusob:
      "geometrie" - vrcholy karty sedi na dil (24 osovych rotaci, obalka sedi),
      "povrch"    - povrch karty lezi na dilu (jina sit; dil muze mit navic
                    drobnost - nad EXTRA_WARN_MM varovani),
      "deska"     - deskovy material: rovina a obdelnik dilu, rozmer pres scale,
      "cast"      - dil je jen cast karty (rozdeleny vyrobek -> slucuje se),
      "obalka"    - tvar nesedi (jiny dil, jina varianta, zrcadlo).
    Nejiste natoceni (skoro soumerny dil, drobny rozdil) = varovani."""
    part_pos = np.asarray(part_pos, dtype=np.float64)
    card_pos = np.asarray(card_pos, dtype=np.float64)
    p_lo, p_hi = part_pos.min(axis=0), part_pos.max(axis=0)
    c_lo, c_hi = card_pos.min(axis=0), card_pos.max(axis=0)
    part_center, part_ext = (p_lo + p_hi) / 2.0, p_hi - p_lo
    card_center, card_ext = (c_lo + c_hi) / 2.0, c_hi - c_lo
    scale = np.ones(3)
    warns = []
    fmt = lambda e: "×".join(f"{v:.0f}" for v in e)  # noqa: E731
    tol = _extent_tol(part_ext)
    same_rot = [(m, q) for m, q, diff in _rotation_candidates(card_ext, part_ext) if np.all(np.abs(diff) <= tol)]
    q, cov = ([0.0, 0.0, 0.0, 1.0], 0.0)
    if same_rot:
        # presna shoda = tentyz export (vrcholy se kryji na setiny mm) -> tolerance 0,2 mm;
        # 0,8 mm u drobneho huste siteneho dilu "sedelo" i na jine siti v jinem natoceni
        ranked = _best_axis_rotation(card_pos - card_center, part_pos - part_center, tol_mm=EXACT_TOL_MM,
                                     symmetric=True, rotations=same_rot, ranked=True)
        q, cov, m0 = ranked[0]
        # jine natoceni skoro stejne dobre a karta vuci nemu NENI soumerna (skoro
        # soumerny dil s drobnym rozdilem - upinac 3313: 1,5 mm) -> presna shoda
        # vrcholu (10% tolerance) nerozhodne, rozhodne jemnejsi povrch
        if EXISTING_MATCH_MIN <= cov < EXACT_PERFECT:
            from scipy.spatial import cKDTree
            cc = card_pos - card_center
            tcc = cKDTree(np.unique(np.round(cc, 1), axis=0))
            for q2, cov2, m2 in ranked[1:]:
                if cov2 < cov - 0.02:
                    break
                rel = m0.T @ m2
                if float(np.mean(np.isfinite(tcc.query(cc @ rel.T, distance_upper_bound=EXACT_TOL_MM)[0]))) < 0.98:
                    cov = 0.0  # -> povrch
                    break
    if cov >= EXISTING_MATCH_MIN:
        method, m = "geometrie", _quat_matrix(q)
        position = part_center - m @ card_center
    elif is_board:
        method = "deska"
        m, q, scale, position, warns = _board_placement(part_pos, part_tris, card_center, card_ext)
    else:
        card = card_ctx or _SurfaceCtx(card_pos, card_tris, seed=11)
        part = _SurfaceCtx(part_pos, part_tris, seed=21)
        r = _surface_match(part, card)
        m, q, diff = r["m"], r["q"], r["diff"]
        position = r["T"] - m @ card.center
        p2c_ok = r["p2c"] <= card.fit_mm() and r["p2c99"] <= card.fit99_mm()
        c2p_ok = r["c2p"] <= part.fit_mm() and r["c2p99"] <= part.fit99_mm()
        world_ext = np.abs(m) @ card_ext
        card_in_part = bool(np.all(diff <= tol))
        part_in_card = bool(np.all(diff >= -tol))
        if r["small_piece"]:
            method = "cast"
            warns.append(f"díl je výrazně menší než karta (karta {fmt(world_ext)} mm, díl {fmt(part_ext)} mm) - "
                         f"kus výrobku rozděleného v FBX? Přiřaď kartu všem jeho kusům, sloučí se; jinak zkontroluj "
                         f"přiřazení")
        elif card_in_part and c2p_ok:
            method = "povrch"
            extra = float(np.max(-diff))
            if not p2c_ok or extra > EXTRA_WARN_MM:
                warns.append(f"díl má navíc proti kartě (o {extra:.0f} mm větší, přilepený útržek / jiná "
                             f"varianta?) - karta usazena na shodnou část (karta {fmt(world_ext)} mm, díl "
                             f"{fmt(part_ext)} mm)")
        elif part_in_card and p2c_ok and not card_in_part:
            method = "cast"
            warns.append(f"díl je jen část karty (karta {fmt(world_ext)} mm, díl {fmt(part_ext)} mm) - "
                         f"výrobek rozdělený v FBX? Přiřaď kartu všem jeho kusům, sloučí se")
        else:
            method = "obalka"
            ps, cs = np.sort(part_ext), np.sort(card_ext)
            if ps[0] < 0.1 * ps[1] and cs[0] < 0.1 * cs[1] and abs(ps[0] - cs[0]) <= 2.0:
                warns.append(f"díl je deska {fmt(part_ext)} mm, ale karta není označená jako deskový materiál - "
                             f"rozměr se nedopočítal (vložena karta {fmt(world_ext)} mm). Kartě zapni "
                             f"„deskový materiál“ s cenou za m² a sestav znovu")
            else:
                warns.append(f"tvar karty se liší od dílu (povrch místy vedle o {max(r['p2c99'], r['c2p99']):.1f} mm: jiný "
                             f"díl, jiná varianta nebo zrcadlová) - vložena v nejlepším natočení "
                             f"(karta {fmt(world_ext)} mm, díl {fmt(part_ext)} mm)")
        if r["ambiguous"] and method in ("povrch", "cast"):
            warns.append("natočení nejisté (skoro souměrný díl s drobným rozdílem) - zkontroluj natočení ve scéně")
    world_ext = np.abs(m) @ (scale * card_ext)
    dev = float(np.max(np.abs(world_ext - part_ext)))
    spec = {
        "position": [round(float(v), 2) for v in position],
        "quaternion": [round(float(v), 6) for v in q],
        "scale": [round(float(v), 6) for v in scale],
    }
    return spec, method, dev, ("; ".join(warns) if warns else None)


def _touching_groups(items):
    """Souvisle skupiny dilu, jejichz obalky se dotykaji (mezera <= MERGE_GAP_MM)."""
    n = len(items)
    parent = list(range(n))

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for a in range(n):
        for b in range(a + 1, n):
            pa, pb = items[a]["part"], items[b]["part"]
            if _bbox_gap(pa["bb_min"], pa["bb_max"], pb["bb_min"], pb["bb_max"]) <= MERGE_GAP_MM:
                parent[root(a)] = root(b)
    groups = {}
    for k in range(n):
        groups.setdefault(root(k), []).append(items[k])
    return list(groups.values())


def _union_geometry(geo, subset):
    pos, tris, vbase = [], [], 0
    for it in subset:
        p, t = geo[it["i"]]
        pos.append(p)
        tris.append(np.asarray(t, dtype=np.int64).reshape(-1, 3) + vbase)
        vbase += len(p)
    return np.vstack(pos), np.vstack(tris)


def _merge_split_parts(group, geo, card_pos, card_tris, card_ctx, is_board, deadline=None):
    """Rozdeleny vyrobek: z dotykajicich se kusu teze karty, ktere samy nesedi
    ("cast"/"obalka"), sklada vyrobky. Seminka od KRAJE rady (osa nejvetsiho
    rozptylu stredu kusu) - kopie vedle sebe / na sobe se berou postupne.
    Ke shluku se pribira sousedni kus, ktery obalku nejvic priblizi karte,
    pri shode NEJBLIZSI; obalka nesmi kartu presahnout o vic nez toleranci.
    Shluk se overi tvarem AZ kdyz obalkou dosahne karty - a kdyz sedi, nic
    dalsiho se nepribira (zasunute stohovane euroboxy: patka horniho boxu v
    otvoru spodniho patri hornimu - kontrola 5. kola). Kdyz nesedi, pribiraji
    se kusy uvnitr obalky (police skrinky) a overuje se znovu (nejvys
    MERGE_MAX_EVAL). Shluk, ktery karty nedosahne, se neoveruje vubec
    (nesložitelne skupiny driv 53-177 s). Sousedstvi se pocita jednou.
    Vraci [(kusy, vysledek _existing_card_spec)]."""
    card_sorted = np.sort(card_ctx.ext)
    tol = _extent_tol(card_sorted)
    n = len(group)
    lo_all = np.array([it["part"]["bb_min"] for it in group], dtype=np.float64)
    hi_all = np.array([it["part"]["bb_max"] for it in group], dtype=np.float64)
    gap = np.sqrt(np.sum(np.maximum(0.0, np.maximum(lo_all[:, None, :] - hi_all[None, :, :],
                                                      lo_all[None, :, :] - hi_all[:, None, :])) ** 2, axis=2))
    nbrs = [set(np.nonzero(gap[k] <= MERGE_GAP_MM)[0].tolist()) - {k} for k in range(n)]
    cs = (lo_all + hi_all) / 2.0
    ax = int(np.argmax(np.ptp(cs, axis=0))) if n > 1 else 0
    order = [ax, (ax + 1) % 3, (ax + 2) % 3]
    seeds = sorted(range(n), key=lambda k: tuple(float(lo_all[k, a]) for a in order))
    alive = set(range(n))
    merged = []
    for seed in seeds:
        if seed not in alive or len(alive) < 2:
            continue
        if deadline is not None and time.monotonic() > deadline:
            break
        cluster, clo, chi = [seed], lo_all[seed].copy(), hi_all[seed].copy()
        evals = 0
        accepted = None
        while True:
            cur = np.sort(chi - clo)
            full = bool(np.all(np.abs(cur - card_sorted) <= tol))
            if full and evals < MERGE_MAX_EVAL and len(cluster) >= 2:
                evals += 1
                pos, tris = _union_geometry(geo, [group[k] for k in cluster])
                r = _existing_card_spec(pos, card_pos, is_board, tris, card_tris, card_ctx)
                if r[1] in ("geometrie", "povrch"):
                    accepted = r
                    break
            frontier = set().union(*(nbrs[k] for k in cluster)) & alive - set(cluster)
            cur_err = float(np.sum(np.abs(cur - card_sorted)))
            cc = (clo + chi) / 2.0
            best = None
            for k in frontier:
                ulo, uhi = np.minimum(clo, lo_all[k]), np.maximum(chi, hi_all[k])
                u = np.sort(uhi - ulo)
                if np.any(u > card_sorted + tol):
                    continue  # sjednoceni by bylo vetsi nez karta (kus sousedni kopie)
                err = float(np.sum(np.abs(u - card_sorted)))
                if full and err > cur_err + 0.5:
                    continue  # obalka vyrobku je cela - kus souseda by ji vzdalil
                key = (round(err, 3), float(np.linalg.norm(cs[k] - cc)), k)
                if best is None or key < best:
                    best = key
            if best is None or (full and evals >= MERGE_MAX_EVAL):
                break
            k = best[2]
            cluster.append(k)
            clo, chi = np.minimum(clo, lo_all[k]), np.maximum(chi, hi_all[k])
        if accepted is not None:
            merged.append(([group[k] for k in cluster], accepted))
            alive -= set(cluster)
    return merged


def _absorb_pieces(pieces, instances, geo, card_pos, card_tris, card_ctx, is_board, deadline=None):
    """Kusy, ktere samy nesedi ("cast"/"obalka"), ale patri k UZ VLOZENE karte
    (hlavni kus prosel sam, nebo sjednoceni): kus se pribere, kdyz se dotyka
    instance, sjednoceni nepresahne kartu, jeho obalka se od karty nevzdali
    a sjednoceni sedi ("geometrie"/"povrch"). Karta se pak usadi podle celku
    (LED: telo o 3 mm kratsi + koncovka -> presne). Kontrola 3. kola: drzak
    plexiskla 3116 / LED s tenkou koncovkou vlozily kartu za kazdy kus znovu.
    instances = {i zastupce: [kusy]} (meni se na miste); vraci
    ({i kusu: i zastupce}, {i zastupce: novy vysledek})."""
    card_sorted = np.sort(card_ctx.ext)
    tol = _extent_tol(card_sorted)

    def bbox(items):
        return (np.min([x["part"]["bb_min"] for x in items], axis=0),
                np.max([x["part"]["bb_max"] for x in items], axis=0))
    absorbed, updated = {}, {}
    progress = True
    while progress:
        progress = False
        if deadline is not None and time.monotonic() > deadline:
            break
        for rep_i, members in instances.items():
            lo, hi = bbox(members)
            cur_err = float(np.sum(np.abs(np.sort(hi - lo) - card_sorted)))
            for it in pieces:
                if it["i"] in absorbed:
                    continue
                p = it["part"]
                if _bbox_gap(p["bb_min"], p["bb_max"], lo, hi) > MERGE_GAP_MM:
                    continue
                ulo, uhi = bbox(members + [it])
                u = np.sort(uhi - ulo)
                if np.any(u > card_sorted + tol) or float(np.sum(np.abs(u - card_sorted))) > cur_err + 0.5:
                    continue
                pos, tris = _union_geometry(geo, members + [it])
                r = _existing_card_spec(pos, card_pos, is_board, tris, card_tris, card_ctx)
                if r[1] not in ("geometrie", "povrch"):
                    continue
                members.append(it)
                absorbed[it["i"]] = rep_i
                updated[rep_i] = r
                progress = True
                break
            if progress:
                break
    return absorbed, updated


def _fast_spec(part_pos, card_pos):
    """Zjednodusene umisteni (casovy limit sestaveni): stred na stred, natoceni
    podle obalky - vzdy s varovanim."""
    part_pos = np.asarray(part_pos, dtype=np.float64)
    card_pos = np.asarray(card_pos, dtype=np.float64)
    p_lo, p_hi = part_pos.min(axis=0), part_pos.max(axis=0)
    c_lo, c_hi = card_pos.min(axis=0), card_pos.max(axis=0)
    m, q, _ = min(_rotation_candidates(c_hi - c_lo, p_hi - p_lo), key=lambda c: float(np.sum(np.abs(c[2]))))
    position = (p_lo + p_hi) / 2.0 - m @ ((c_lo + c_hi) / 2.0)
    spec = {"position": [round(float(v), 2) for v in position], "quaternion": [round(float(v), 6) for v in q],
            "scale": [1.0, 1.0, 1.0]}
    return spec, "obalka", 0.0, "umístěno zjednodušeně (časový limit sestavení) - zkontroluj natočení a polohu ve scéně"


def _place_repeated(card_items, geo, cpos, ctris, ctx, is_board, deadline=None):
    """_existing_card_spec pro vsechny dily jedne karty; dil, ktery je PRESNOU
    kopii uz spocteneho dilu (tentyz mesh v jine poloze/natoceni - 48 stejnych
    spojek v ramu), prevezme jeho vysledek prepocitany o vzajemne natoceni
    (kontrola 4. kola: 72 kusu prislusenstvi s jinou siti nez karta = 64 s)."""
    res, protos = {}, []
    for it in card_items:
        pos, tris = geo[it["i"]]
        lo, hi = pos.min(axis=0), pos.max(axis=0)
        c, ext = (lo + hi) / 2.0, np.sort(hi - lo)
        hit = None
        for pr in protos:
            if pr["n"] != len(pos) or np.max(np.abs(pr["ext"] - ext)) > EXACT_TOL_MM:
                continue
            qrel, cov = _best_axis_rotation(pr["centered"], pos - c, tol_mm=EXACT_TOL_MM, symmetric=True)
            if cov >= EXACT_PERFECT:
                hit = (pr, _quat_matrix(qrel))
                break
        if hit is None:
            if deadline is not None and time.monotonic() > deadline:
                res[it["i"]] = _fast_spec(pos, cpos)
                continue
            r = _existing_card_spec(pos, cpos, is_board, tris, ctris, ctx)
            protos.append({"n": len(pos), "ext": ext, "centered": pos - c, "c": c, "r": r})
            res[it["i"]] = r
            continue
        pr, rel = hit
        spec, method, dev, warning = pr["r"]
        m = rel @ _quat_matrix(spec["quaternion"])
        position = c + rel @ (np.asarray(spec["position"]) - pr["c"])
        res[it["i"]] = ({"position": [round(float(v), 2) for v in position],
                         "quaternion": [round(float(v), 6) for v in _matrix_quat(m)],
                         "scale": list(spec["scale"])}, method, dev, warning)
    return res


def _place_existing_cards(d, items, katalog):
    """Umisteni vsech dilu namapovanych na existujici NEprofilove karty.
    Vraci ({i: spec | None}, varovani[], {zpusob: pocet}); None = dil je
    soucasti jineho (rozdeleny dil - vlozen jednou u prvniho kusu).
    Karta bez pouzitelneho 3D modelu = BuildError: scena by ulozeny tvar
    nenacetla (loader spadne na chybejicim souboru a nevlozi nic).

    Rozdeleny dil: CAD/FBX casto ulozi jeden vyrobek jako vic meshu (LED
    lampa = 2 pulky, telo + koncovka, skrinka z 6 desek). Kusy namapovane na
    TUTEZ kartu, ktere samy nesedi ("cast"/"obalka"), se skladaji do vyrobku
    (_merge_split_parts) - sedi-li sjednoceni na kartu, vlozi se jednou (jinak
    by vznikly dve cele lampy pres sebe a dvoji cena). Povrch karty se pocita
    jednou pro vsechny jeji dily (_SurfaceCtx)."""
    by_card = {}
    for it in items:
        by_card.setdefault(it["part_id"], []).append(it)
    cards = {}
    for pid, card_items in by_card.items():
        mesh, why = _card_geometry(katalog[pid])
        if mesh is None:
            names = ", ".join(f"#{it['i']}" for it in card_items)
            raise BuildError(f"Karta {pid} ({katalog[pid].get('name') or ''}): {why} - nejde vložit do tvaru "
                             f"(díly {names}). Přiřaď jinou kartu, nebo kartě nahraj 3D model.")
        cards[pid] = mesh
    geo = {}
    for it in items:
        pos, idx = _load_part_geometry(d, it["part"])
        geo[it["i"]] = (pos.astype(np.float64), np.asarray(idx, dtype=np.int64).reshape(-1, 3))
    specs, warnings, methods = {}, [], Counter()
    deadline = time.monotonic() + PLACE_BUDGET_S
    for pid, card_items in by_card.items():
        kp, (cpos, ctris) = katalog[pid], cards[pid]
        is_board = bool(kp.get("is_board_material"))
        ctx = None if is_board else _SurfaceCtx(cpos, ctris, seed=11)
        if time.monotonic() > deadline:
            ctx = None  # casovy limit: zbyle karty zjednodusene (bez vzorku povrchu)
            res = {it["i"]: _fast_spec(geo[it["i"]][0], cpos) for it in card_items}
        else:
            res = _place_repeated(card_items, geo, cpos, ctris, ctx, is_board, deadline)
        failing = [it for it in card_items if res[it["i"]][1] in ("cast", "obalka")]
        members = {}  # i zastupce -> kusy sloucene do jednoho vyrobku
        if len(failing) >= 2 and ctx is not None:
            for group in _touching_groups(failing):
                if len(group) < 2:
                    continue
                for subset, r in _merge_split_parts(group, geo, cpos, ctris, ctx, is_board, deadline):
                    subset = sorted(subset, key=card_items.index)  # zastupce = prvni kus v poradi dilu
                    members[subset[0]["i"]] = subset
                    res[subset[0]["i"]] = r
                    for it in subset[1:]:
                        res[it["i"]] = None
                    ids = " + ".join(f"#{it['i']}" for it in subset)
                    warnings.append(f"díly {ids} jsou jeden výrobek rozdělený v FBX - karta {pid} vložena jednou")
        if ctx is not None:
            left = [it for it in card_items if res[it["i"]] is not None and res[it["i"]][1] in ("cast", "obalka")]
            instances = {it["i"]: list(members.get(it["i"], [it])) for it in card_items
                         if res[it["i"]] is not None and res[it["i"]][1] in ("geometrie", "povrch")}
            if left and instances:
                absorbed, updated = _absorb_pieces(left, instances, geo, cpos, ctris, ctx, is_board, deadline)
                for piece_i, inst_i in absorbed.items():
                    res[piece_i] = None
                    warnings.append(f"díl #{piece_i} je součástí výrobku z dílu #{inst_i} (rozdělený v FBX) - "
                                    f"karta {pid} vložena jednou")
                res.update(updated)
        for it in card_items:
            r = res[it["i"]]
            if r is None:
                specs[it["i"]] = None
                continue
            spec, method, _dev, warning = r
            specs[it["i"]] = spec
            methods[method] += 1
            if warning:
                warnings.append(f"díl #{it['i']} ({it['part']['name']}) → {pid}: {warning}")
    return specs, warnings, dict(methods)


def _is_catalog_profile_row(p):
    """Skutecny katalogovy profil (vzorek 1000 mm, nazev "Profil ...") -
    stejny predikat jako _catalog_profile_sections (rozpoznani)."""
    if p.get("source") != "profil" or not p.get("length_mm") or not p.get("cross_section_mm") \
            or p["cross_section_mm"][0] is None:
        return False
    return float(p["length_mm"]) >= 900 and str(p.get("name") or "").lower().startswith("profil")


def _profile_specs_by_id(katalog_rows):
    """{id: {"id", "L0"}} pro VSECHNY profily s pouzitelnym GLB (vycentrovany,
    delka po ose Y = L0 +-2 mm, jak predpoklada _profile_part_spec) - vcetne
    variant, ktere nejsou v pickeru sceny (uzavreny/radius/light).
    Nahrazuje first-wins slovnik podle prurezu (_catalog_profiles_by_cross_
    section vraci pro 30x30 jen Object_7), se kterym dil namapovany na
    variantu padl do vetve prislusenstvi: bez preskalovani delky a bez spoju."""
    from leg_fbx_import import _glb_axis_spans
    out = {}
    for p in katalog_rows:
        if not _is_catalog_profile_row(p):
            continue
        fname = (p.get("file") or "").split("?")[0]
        if fname.startswith("katalog/"):
            fname = fname[len("katalog/"):]
        if not fname or fname.startswith("_PENDING_"):
            continue
        path = os.path.join(KATALOG_GLB_DIR, fname)
        if not os.path.isfile(path):
            continue
        try:
            spans = _glb_axis_spans(path)
        except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error):
            continue
        L0 = float(p["length_mm"])
        if not all(abs(lo + hi) < 2.0 for lo, hi in spans) or abs((spans[1][1] - spans[1][0]) - L0) > 2.0:
            continue
        out[p["id"]] = {"id": p["id"], "L0": L0}
    return out


class BuildError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@app.post("/api/admin/universal-import/build")
@require_permission("rozklad_fbx", "upravit")
def universal_import_build():
    body = request.get_json(silent=True) or {}
    d = _token_dir(body.get("token") or "")
    if not d:
        return jsonify({"error": "Neznámý nebo expirovaný import - nahraj FBX znovu."}), 404
    try:
        return jsonify(build_shape(d, body, current_user()))
    except BuildError as e:
        return jsonify({"error": str(e)}), e.status


def build_shape(d, body, admin):
    """Jadro build (bez Flasku, testovatelne primo): d = adresar tokenu,
    body = {shape_name, category_id?, product_category_id?, decisions[]},
    admin = current_user() dict. Vraci payload odpovedi, pri chybe
    BuildError (nic nezapsano - jedna transakce + uklid GLB)."""
    shape_name = (body.get("shape_name") or "").strip()
    if not shape_name:
        raise BuildError("Vyplň název tvaru.")
    shape_category_id = body.get("category_id")
    product_category_id = body.get("product_category_id")
    decisions = body.get("decisions") or []
    if not isinstance(decisions, list) or not decisions:
        raise BuildError("Chybí rozhodnutí o dílech.")

    with open(os.path.join(d, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    parts_by_i = {p["i"]: p for p in meta["parts"]}

    # 1) validace rozhodnuti (nic se jeste nezapisuje)
    katalog = {p["id"]: p for p in fetch_katalog_parts()}
    profile_by_id = _profile_specs_by_id(katalog.values())
    plan = []
    new_skus = []
    for dec in decisions:
        try:
            i = int(dec.get("i"))
        except (TypeError, ValueError):
            raise BuildError("Neplatný index dílu.")
        part = parts_by_i.get(i)
        if not part:
            raise BuildError(f"Díl #{i} v tomto importu neexistuje.")
        action = dec.get("action")
        if action == "skip":
            continue
        if action == "existing":
            pid = dec.get("part_id")
            if pid not in katalog:
                raise BuildError(f"Díl #{i} ({part['name']}): neznámý katalogový díl '{pid}'.")
            plan.append({"i": i, "part": part, "action": "existing", "part_id": pid})
        elif action == "new":
            sku = (dec.get("sku") or "").strip()
            name = (dec.get("name") or "").strip() or f"{shape_name} - {part['name']}"
            if not sku:
                raise BuildError(f"Díl #{i} ({part['name']}): chybí SKU nového dílu.")
            # Stejne SKU u vice dilu v jednom importu = JEDNA karta pouzita
            # vickrat (4 kolecka = 1 produkt, 4 pozice) - Robert 2026-09-30
            # ("tady je milion dilu"): stejne dily se ve UI seskupuji.
            if sku not in new_skus:
                new_skus.append(sku)
            plan.append({"i": i, "part": part, "action": "new", "sku": sku, "name": name})
        else:
            raise BuildError(f"Díl #{i}: neznámá akce '{action}'.")
    if not plan:
        raise BuildError("Všechny díly jsou přeskočené - není co sestavit.")

    conn = get_conn()
    written_glbs = []
    try:
        with conn.cursor() as cur:
            if new_skus:
                fmt = ",".join(["%s"] * len(new_skus))
                cur.execute(f"SELECT sku FROM shop_products WHERE sku IN ({fmt})", new_skus)
                kolize = [r["sku"] for r in cur.fetchall()]
                if kolize:
                    raise BuildError("SKU už existuje: " + ", ".join(kolize) + " - nic nezaloženo.")

            # 2) sestaveni parts + zalozeni novych karet (stejna transakce)
            part_specs = []
            new_products = []
            new_by_sku = {}
            warnings = []
            profile_boxes = []  # (index v part_specs, bb_min, bb_max) pro lic_peers
            # existujici NEprofilove karty: umisteni z geometrie GLB karty (libovolny
            # pocatek/osy), desky dopocitany do rozmeru dilu, rozdelene dily jednou
            existing_items = [it for it in plan if it["action"] == "existing" and it["part_id"] not in profile_by_id]
            for it in existing_items:
                if _is_catalog_profile_row(katalog[it["part_id"]]):
                    warnings.append(f"díl #{it['i']} ({it['part']['name']}): profil {it['part_id']} nemá použitelný "
                                    f"3D model (chybí / nevycentrovaný / délka ≠ vzorek) - délka se nepřepočítá a "
                                    f"nevzniknou spoje")
            existing_specs, existing_warnings, placement_methods = _place_existing_cards(d, existing_items, katalog)
            profile_geo = {}
            warnings.extend(existing_warnings)
            for item in plan:
                part = item["part"]
                lo = np.array(part["bb_min"]); hi = np.array(part["bb_max"])
                if item["action"] == "existing":
                    pid = item["part_id"]
                    if pid in profile_by_id:
                        if pid not in profile_geo:
                            mesh, _why = _card_geometry(katalog[pid])
                            profile_geo[pid] = mesh[0] if mesh else None
                        pw = []
                        spec = _profile_part_spec(part, profile_by_id[pid], _load_part_geometry(d, part)[0],
                                                  profile_geo[pid], pw)
                        warnings.extend(f"díl #{item['i']} ({part['name']}) → {pid}: {w}" for w in pw)
                        profile_boxes.append((len(part_specs), lo, hi))
                    else:
                        if existing_specs[item["i"]] is None:
                            continue  # soucast rozdeleneho dilu, vlozen u prvniho kusu
                        spec = {"part_id": pid, **existing_specs[item["i"]]}
                    part_specs.append(spec)
                else:
                    pos, idx = _load_part_geometry(d, part)
                    center = (pos.min(axis=0) + pos.max(axis=0)) / 2.0
                    ref = new_by_sku.get(item["sku"])
                    if ref is None:
                        cur.execute(
                            "INSERT INTO shop_products (category_id, sku, name, slug, unit, visible_in_scene, active, glb_file) "
                            "VALUES (%s,%s,%s,%s,'ks',1,0,%s)",
                            (product_category_id, item["sku"], item["name"], _product_slug_for_name(cur, item["name"]), "_PENDING_"),
                        )
                        new_id = cur.lastrowid
                        glb_name = f"product_{new_id}.glb"
                        glb_path = os.path.join(KATALOG_GLB_DIR, glb_name)
                        write_glb(glb_path, pos - center, idx, item["name"])
                        written_glbs.append(glb_path)
                        cur.execute("UPDATE shop_products SET glb_file=%s WHERE id=%s", (glb_name, new_id))
                        new_products.append({"id": new_id, "sku": item["sku"], "name": item["name"]})
                        new_by_sku[item["sku"]] = {"id": new_id, "pos_centered": pos - center}
                        quat = [0.0, 0.0, 0.0, 1.0]
                    else:
                        # dalsi vyskyt tehoz dilu: stejna karta, vlastni pozice,
                        # natoceni dopocitane porovnanim geometrie s prvnim kusem
                        new_id = ref["id"]
                        quat, cov = _best_axis_rotation(ref["pos_centered"], pos - center)
                        if cov < 0.9:
                            # geometrie nesedi zadnou rotaci (typicky ZRCADLOVA
                            # dvojice - leva/prava bocnice se stejnym bboxem):
                            # radsi vlastni karta s pripona, nez spatne natoceny
                            # kus ze spolecne karty
                            ref["variants"] = ref.get("variants", 1) + 1
                            sku_v = f"{item['sku']}-{ref['variants']}"
                            name_v = f"{item['name']} ({ref['variants']})"
                            cur.execute(
                                "INSERT INTO shop_products (category_id, sku, name, slug, unit, visible_in_scene, active, glb_file) "
                                "VALUES (%s,%s,%s,%s,'ks',1,0,%s)",
                                (product_category_id, sku_v, name_v, _product_slug_for_name(cur, name_v), "_PENDING_"),
                            )
                            new_id = cur.lastrowid
                            glb_name = f"product_{new_id}.glb"
                            glb_path = os.path.join(KATALOG_GLB_DIR, glb_name)
                            write_glb(glb_path, pos - center, idx, name_v)
                            written_glbs.append(glb_path)
                            cur.execute("UPDATE shop_products SET glb_file=%s WHERE id=%s", (glb_name, new_id))
                            new_products.append({"id": new_id, "sku": sku_v, "name": name_v})
                            warnings.append(f"díl #{item['i']} ({part['name']}): geometrie nesedí na první kus '{item['sku']}' "
                                            f"žádnou rotací (shoda {cov:.2f}, nejspíš zrcadlová varianta) - založena vlastní karta {sku_v}")
                            quat = [0.0, 0.0, 0.0, 1.0]
                    part_specs.append({
                        "part_id": f"product_{new_id}",
                        "position": [round(float(v), 2) for v in center.tolist()],
                        "quaternion": [round(float(v), 6) for v in quat],
                        "scale": [1.0, 1.0, 1.0],
                    })

            # 3) spoje profil-profil (stejny princip jako dimension_match_fbx)
            if len(profile_boxes) >= 2:
                boxes = [{"bb_min": lo, "bb_max": hi} for _, lo, hi in profile_boxes]
                peers = compute_lic_peers(boxes)
                for k, (spec_idx, _, _) in enumerate(profile_boxes):
                    if peers[k]:
                        part_specs[spec_idx]["lic_peers"] = [profile_boxes[j][0] for j in peers[k]]

            # 4) validace presne jako Ctrl+S / ostatni importy - katalog znovu
            #    (nove karty uz jsou v teto transakci videt pres stejne spojeni)
            valid_ids = set(katalog.keys())
            valid_ids.update(f"product_{np_['id']}" for np_ in new_products)
            clean_parts, err = _validate_custom_shape_parts(part_specs, valid_ids)
            if err:
                raise ValueError(err)
            clean_jg, clean_fg, err = _validate_custom_shape_relations(None, None, len(clean_parts), clean_parts)
            if err:
                raise ValueError(f"Interní chyba sestavení: {err}")

            data = {"parts": clean_parts, "join_groups": clean_jg, "frame_groups": clean_fg, "text_labels": []}
            cur.execute(
                "INSERT INTO custom_shapes (name, category_id, data, created_by, is_public) VALUES (%s,%s,%s,%s,1)",
                (shape_name, shape_category_id, json.dumps(data, ensure_ascii=False), admin["id"] if admin else None),
            )
            shape_id = cur.lastrowid
        conn.commit()
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        for g in written_glbs:
            try:
                os.remove(g)
            except OSError:
                pass
        if isinstance(e, BuildError):
            raise
        raise BuildError(f"Sestavení selhalo, nic nezapsáno: {e}")
    finally:
        conn.close()

    # 5) katalogove radky novych dilu ve formatu /api/katalog (scena si je
    #    pripoji do CATALOG bez reloadu) - z cerstveho fetch_katalog_parts
    new_ids = {f"product_{np_['id']}" for np_ in new_products}
    katalog_rows = [p for p in fetch_katalog_parts() if p["id"] in new_ids] if new_ids else []

    log_audit(admin["id"] if admin else None, "create", "custom_shape_universal_import", shape_id,
              f"{shape_name}: {len(clean_parts)} dílů, {len(new_products)} nových karet, zdroj {meta.get('source_name')}")
    shutil.rmtree(d, ignore_errors=True)
    breakdown = Counter("nový díl" if s["part_id"] in new_ids else s["part_id"] for s in clean_parts)
    return {
        "custom_shape_id": shape_id, "name": shape_name,
        "n_parts": len(clean_parts), "new_products": new_products, "warnings": warnings,
        "placement_methods": placement_methods,
        "katalog_rows": katalog_rows,
        "joints_found": count_lic_peer_pairs(clean_parts),
        "breakdown": [{"part_id": k, "count": v} for k, v in breakdown.most_common()],
    }
