import bpy
import mathutils

def world_bbox_ranges(obj):
    """Vraci [(min,max), (min,max), (min,max)] pro X,Y,Z v SVETOVEM prostoru
    (respektuje existujici scale/rotaci objektu - realna orientace tak,
    jak ji vidi kazdy standardni glTF prohlizec, ne surova mesh data)."""
    bpy.context.view_layer.update()
    corners = [obj.matrix_world @ v.co for v in obj.data.vertices]
    ranges = []
    for axis in range(3):
        vals = [c[axis] for c in corners]
        ranges.append((min(vals), max(vals)))
    return ranges

def overlap_amount(r1, r2):
    """Kladne cislo = prekryv (o kolik), zaporne = mezera (o kolik)."""
    return min(r1[1], r2[1]) - max(r1[0], r2[0])

def detect_axis_mapping(l_obj, rd_obj, b_obj):
    """Zjisti, ktera SOUCASNA (native, pred korekci) osa objektu odpovida
    sirce/vysce/delce vozidla - NEZALEZI na tom, jakou startovni orientaci
    ma zdrojovy soubor (na rozdil od pevneho "-90 X vzdy").

    Sirka (width): osa, na ktere se L a R_D DOTYKAJI (nejmensi/zaporny
    prekryv - jsou to 2 protilehle poloviny karoserie podel teto osy).
    Delka (length): ze zbylych 2 os ta, na ktere ma B (koncova stena)
    NEJUZSI rozsah (B uzavira JEDEN konec podel delky, takze na delkove
    ose je tenka; na sirkove ose je naopak siroka - presne obracene
    chovani nez u L/R_D).
    Vyska (height): zbyva.

    Vraci dict {"width": axis_idx, "length": axis_idx, "height": axis_idx}.
    """
    l_r = world_bbox_ranges(l_obj)
    rd_r = world_bbox_ranges(rd_obj)
    b_r = world_bbox_ranges(b_obj)

    overlaps = [overlap_amount(l_r[i], rd_r[i]) for i in range(3)]
    width_axis = min(range(3), key=lambda i: overlaps[i])

    remaining = [i for i in range(3) if i != width_axis]
    b_sizes = [b_r[i][1] - b_r[i][0] for i in remaining]
    length_axis = remaining[min(range(len(remaining)), key=lambda i: b_sizes[i])]
    height_axis = [i for i in remaining if i != length_axis][0]

    return {"width": width_axis, "length": length_axis, "height": height_axis}, l_r, rd_r, b_r


def build_correction_matrix(mapping):
    """Sestavi 3x3 rotacni matici (determinant +1, zadne zrcadleni) v
    Blenderove SOURADNEM RAMCI (matrix_world pred exportem).

    DULEZITE: Blenderuv gltf EXPORTER dela svou vlastni pevnou Z-up
    (Blender) -> Y-up (glTF/THREE.js) konverzi PRI KAZDEM exportu,
    nezavisle na cemkoli, co udelame my (final_X=blender_X,
    final_Y=blender_Z, final_Z=-blender_Y). Cili vysledna "vyska" v
    prohlizeci (final_Y) odpovida BLENDEROVE ose Z, ne Y - a vysledna
    "delka" (final_Z) odpovida BLENDEROVE ose Y. Bez tohohle zohledneni
    vyjde v Blenderu "spravna" orientace, ktera je po exportu otocena
    o 90st (empiricky zachyceno na FO30 2026-08-21: puvodni verze
    cilila blender_Y=vyska/blender_Z=delka, coz po exportu davalo
    postavenou "budku" mist podlouhle karoserie).

    Cili v BLENDEROVE ramci: X=sirka, Y=delka, Z=vyska.
    """
    w, l, h = mapping["width"], mapping["length"], mapping["height"]
    M = mathutils.Matrix(((0,0,0),(0,0,0),(0,0,0)))
    M[0][w] = 1.0  # blender X <- puvodni osa sirky
    M[1][l] = 1.0  # blender Y <- puvodni osa delky (bude finalni Z po exportu)
    M[2][h] = 1.0  # blender Z <- puvodni osa vysky (bude finalni Y po exportu)
    if M.determinant() < 0:
        M[1][l] = -1.0
    return M
