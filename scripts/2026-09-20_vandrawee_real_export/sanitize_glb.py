import struct, json, sys, math, array

COMPONENT_TYPES = {
    5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2),
    5125: ('I', 4), 5126: ('f', 4),
}
TYPE_COUNTS = {
    'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4,
    'MAT2': 4, 'MAT3': 9, 'MAT4': 16,
}

def read_glb(path):
    data = open(path, 'rb').read()
    magic, version, length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67
    offset = 12
    json_chunk = None
    bin_chunk = None
    chunks = []
    while offset < length:
        clen, ctype = struct.unpack_from('<II', data, offset)
        offset += 8
        chunk_data = data[offset:offset + clen]
        chunks.append((ctype, clen))
        if ctype == 0x4E4F534A:
            json_chunk = chunk_data
        elif ctype == 0x004E4942:
            bin_chunk = chunk_data
        offset += clen
    return json.loads(json_chunk), bytearray(bin_chunk)

def write_glb(path, gltf, bin_data):
    json_bytes = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    while len(json_bytes) % 4 != 0:
        json_bytes += b' '
    bin_bytes = bytes(bin_data)
    while len(bin_bytes) % 4 != 0:
        bin_bytes += b'\x00'
    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    out = bytearray()
    out += struct.pack('<III', 0x46546C67, 2, total_len)
    out += struct.pack('<II', len(json_bytes), 0x4E4F534A) + json_bytes
    out += struct.pack('<II', len(bin_bytes), 0x004E4942) + bin_bytes
    open(path, 'wb').write(out)

def sanitize(in_path, out_path):
    gltf, bin_data = read_glb(in_path)
    buffer_views = gltf.get("bufferViews", [])
    fixed = 0
    removed_prims = 0

    meshes_to_check = []
    for mi, mesh in enumerate(gltf.get("meshes", [])):
        new_prims = []
        for pi, prim in enumerate(mesh.get("primitives", [])):
            pos_acc_idx = prim.get("attributes", {}).get("POSITION")
            if pos_acc_idx is None:
                new_prims.append(prim)
                continue
            acc = gltf["accessors"][pos_acc_idx]
            bv = buffer_views[acc["bufferView"]]
            fmt, csize = COMPONENT_TYPES[acc["componentType"]]
            ncomp = TYPE_COUNTS[acc["type"]]
            count = acc["count"]
            stride = bv.get("byteStride") or (csize * ncomp)
            start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            has_nan = False
            for j in range(count):
                off = start + j * stride
                vals = struct.unpack_from('<' + fmt * ncomp, bin_data, off)
                if any(isinstance(v, float) and (math.isnan(v) or math.isinf(v)) for v in vals):
                    has_nan = True
                    break
            if has_nan:
                removed_prims += 1
                continue
            new_prims.append(prim)
        if new_prims:
            mesh["primitives"] = new_prims
            meshes_to_check.append(mi)
        else:
            mesh["primitives"] = []

    for i, acc in enumerate(gltf.get("accessors", [])):
        if "bufferView" not in acc:
            continue
        bv = buffer_views[acc["bufferView"]]
        fmt, csize = COMPONENT_TYPES[acc["componentType"]]
        ncomp = TYPE_COUNTS[acc["type"]]
        count = acc["count"]
        stride = bv.get("byteStride") or (csize * ncomp)
        start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)

        needs_fix = False
        for key in ("min", "max"):
            if key in acc:
                v = acc[key]
                if not isinstance(v, list) or len(v) != ncomp or not all(
                    isinstance(x, (int, float)) and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))
                    for x in v
                ):
                    needs_fix = True

        if not needs_fix:
            continue
        if acc["componentType"] != 5126:
            # integer accessor with bad min/max metadata only - just drop min/max (optional except for POSITION)
            acc.pop("min", None)
            acc.pop("max", None)
            fixed += 1
            continue

        mins = [math.inf] * ncomp
        maxs = [-math.inf] * ncomp
        any_valid = False
        for j in range(count):
            off = start + j * stride
            vals = struct.unpack_from('<' + fmt * ncomp, bin_data, off)
            if any(math.isnan(v) or math.isinf(v) for v in vals):
                continue
            any_valid = True
            for k, v in enumerate(vals):
                mins[k] = min(mins[k], v)
                maxs[k] = max(maxs[k], v)

        if any_valid:
            acc["min"] = mins
            acc["max"] = maxs
        else:
            acc.pop("min", None)
            acc.pop("max", None)
        fixed += 1

    print(f"accessors with min/max recomputed or dropped: {fixed}")
    print(f"primitives removed (NaN in POSITION): {removed_prims}")

    def bad_numlist(v, n):
        return (not isinstance(v, list) or len(v) != n or
                not all(isinstance(x, (int, float)) and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) for x in v))

    nodes_fixed = 0
    for node in gltf.get("nodes", []):
        if "matrix" in node and bad_numlist(node["matrix"], 16):
            del node["matrix"]
            node.setdefault("translation", [0.0, 0.0, 0.0])
            nodes_fixed += 1
        if "translation" in node and bad_numlist(node["translation"], 3):
            node["translation"] = [0.0, 0.0, 0.0]
            nodes_fixed += 1
        if "rotation" in node and bad_numlist(node["rotation"], 4):
            node["rotation"] = [0.0, 0.0, 0.0, 1.0]
            nodes_fixed += 1
        if "scale" in node and bad_numlist(node["scale"], 3):
            node["scale"] = [1.0, 1.0, 1.0]
            nodes_fixed += 1
    print(f"node transforms fixed (matrix/translation/rotation/scale): {nodes_fixed}")

    mats_fixed = 0
    for mat in gltf.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        if "baseColorFactor" in pbr and bad_numlist(pbr["baseColorFactor"], 4):
            pbr["baseColorFactor"] = [0.8, 0.8, 0.8, 1.0]
            mats_fixed += 1
        if "emissiveFactor" in mat and bad_numlist(mat["emissiveFactor"], 3):
            mat["emissiveFactor"] = [0.0, 0.0, 0.0]
            mats_fixed += 1
    print(f"materials fixed (baseColorFactor/emissiveFactor): {mats_fixed}")

    # Final comprehensive scan: any leftover NaN/Infinity anywhere in the
    # JSON tree at all (belt-and-suspenders, after the targeted fixes above).
    def scan(obj, path=""):
        issues = []
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            issues.append(path)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                issues += scan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                issues += scan(v, f"{path}[{i}]")
        return issues

    leftover = scan(gltf)
    print(f"leftover NaN/Inf anywhere in JSON tree: {len(leftover)}")
    for p in leftover[:20]:
        print("  ", p)

    write_glb(out_path, gltf, bin_data)

if __name__ == "__main__":
    sanitize(sys.argv[1], sys.argv[2])
