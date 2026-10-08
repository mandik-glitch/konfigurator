import struct, json, sys, math

COMPONENT_TYPES = {
    5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2),
    5125: ('I', 4), 5126: ('f', 4),
}
TYPE_COUNTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}

def read_glb(path):
    data = open(path, 'rb').read()
    magic, version, length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67
    offset = 12
    json_chunk = None
    bin_chunk = None
    while offset < length:
        clen, ctype = struct.unpack_from('<II', data, offset)
        offset += 8
        chunk_data = data[offset:offset + clen]
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

def scale_positions(in_path, out_path, factor=1000.0):
    gltf, bin_data = read_glb(in_path)
    buffer_views = gltf.get("bufferViews", [])

    position_accessors = set()
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            idx = prim.get("attributes", {}).get("POSITION")
            if idx is not None:
                position_accessors.add(idx)

    scaled = 0
    for i in position_accessors:
        acc = gltf["accessors"][i]
        bv = buffer_views[acc["bufferView"]]
        fmt, csize = COMPONENT_TYPES[acc["componentType"]]
        ncomp = TYPE_COUNTS[acc["type"]]
        count = acc["count"]
        stride = bv.get("byteStride") or (csize * ncomp)
        start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)

        mins = [math.inf] * ncomp
        maxs = [-math.inf] * ncomp
        for j in range(count):
            off = start + j * stride
            vals = list(struct.unpack_from('<' + fmt * ncomp, bin_data, off))
            vals = [v * factor for v in vals]
            struct.pack_into('<' + fmt * ncomp, bin_data, off, *vals)
            for k, v in enumerate(vals):
                mins[k] = min(mins[k], v)
                maxs[k] = max(maxs[k], v)
        acc["min"] = mins
        acc["max"] = maxs
        scaled += 1
    print(f"POSITION accessors scaled x{factor}: {scaled}")

    nodes_scaled = 0
    for node in gltf.get("nodes", []):
        if "translation" in node:
            node["translation"] = [v * factor for v in node["translation"]]
            nodes_scaled += 1
        if "matrix" in node:
            m = node["matrix"]
            m[12] *= factor
            m[13] *= factor
            m[14] *= factor
            node["matrix"] = m
            nodes_scaled += 1
    print(f"node translations/matrices scaled: {nodes_scaled}")

    write_glb(out_path, gltf, bin_data)

if __name__ == "__main__":
    scale_positions(sys.argv[1], sys.argv[2])
