#!/usr/bin/env python3
"""
step_convert_worker.py - bot1, 2026-07-27, rozsireno 2026-07-28 a 2026-08-04.

Bezi VYHRADNE uvnitr izolovaneho `api/step_venv` (ma tezke zavislosti
cadquery-ocp/OpenCascade - ~1.1GB, proto NENI soucasti hlavniho app venv).
Hlavni Flask appka (viz api/step_convert.py) tenhle skript spousti jako
samostatny SUBPROCESS pres step_venv/bin/python3 - takze i kdyby prevod
spadl, zabral moc pameti nebo trval prilis dlouho (timeout v rodicovskem
procesu), hlavni gunicorn worker appky tim neni ohrozeny.

Robert: "co kdybychom chteli vkladat stp? umime to nejak tu strukturu
zjednodusit a dat do glb?" -> "potrebujeme tu mesh maximalne zjednodusit"
-> "osekat radiusy" -> (2026-07-28, po srovnani STEP vs FBX na realnem
"Uhelniku 30x30"/product 2895) "muzeme ten step jeste vice osekat? a
zrusit tam vzdy logo DogusKalip". Reseno TREMI kroky zjednoduseni:

  1) FILTR MALYCH PLOCH (2026-07-28) - pred samotnou tesselaci se
     spocita plocha (mm^2) KAZDE B-rep plochy dilu. Vyrobni razitka/loga
     (napr. "DogusKalip") a jina jemna rytina/embossing byvaji na STEP
     dilech reprezentovany jako spousta DROBNYCH ploch (na testovacim
     produktu 2895 - "Uhelnikova spojka 30x30" - bylo z celkem 144 ploch
     az 107 mensich nez 1 mm^2, zatimco funkcni tvar dilu tvorilo jen ~37
     ploch vetsich nez 70 mm^2 - jasna a velka mezera mezi "detailem" a
     "tvarem"). Plochy mensi nez `min_face_area_frac` (relativne k
     nejvetsi plose na dilu) se VUBEC netesseluji, takze logo/rytina do
     vysledneho meshe nikdy nedorazi - misto aby se pak muselo slozite
     hledat a mazat AZ v trojuhelnikove siti.
  2) HRUBA tesselace (BRepMesh_IncrementalMesh s relativne velkou
     linearni odchylkou) - ploche steny maji vzdy jen minimum trojuhelniku
     bez ohledu na tuhle hodnotu, zaobleni/radiusy uz se ale pri hrubsi
     odchylce rozlozi na mnohem min facet.
  3) Quadric decimation (fast-simplification pres trimesh) jako treti,
     nezavisly prusak - dotahne pripadne zbyle detaily (male radiusy,
     srazeni hran) na jeste nizsi pocet trojuhelniku bez ohledu na to,
     jak byla puvodni tesselace hruba. Pozor: parametr `percent` u
     simplify_quadric_decimation je podil OCEKAVANY K ODSTRANENI (ne k
     zachovani) - percent=0.6 znamena "zahod 60 %, nechej 40 %". Vychozi
     hodnota zvysena z 0.6 na 0.75 (2026-07-28, Robert: "muzeme to jeste
     vice osekat? myslim ze urcite").

  0) AUTOMATICKA DETEKCE LOGA + ADAPTIVNI JEMNOST TESSELACE (NOVE,
     2026-08-04). Robert: "toto nastaveni plati, pokud ma model logo jako
     soucast prvku, pravidlo, a dale pokud model logo nema potrebujeme
     tesselaci o 50 % jemnejsi" -> "system nech to rozlisuje automaticky
     pri nacteni stepu" (tzn. ZADNY rucni prepinac v adminu) -> "pokud
     model logo nema potrebujeme jeste o 30 % tesselaci jemnejsi" ->
     upresneno jako SECTENO celkem, tedy 50 % + 30 % = 80 % jemnejsi
     celkem, pokud model logo NEMA.

     Detekce loga vyuziva PRESNE tu samou statistiku, kterou uz krok (1)
     stejne pocita (plocha kazde B-rep plochy vs. nejvetsi plocha na
     dilu) - zadny novy vypocet navic. Pokud aspon jedna plocha spadne
     pod `min_face_area_frac` prah (tzn. filtr v kroku 1 bude mit vubec
     co zahodit), povazujeme model za "ma logo/rytinu" a pouzije se
     PUVODNI (adaptivni, dle velikosti dilu) tesselacni odchylka beze
     zmeny. Pokud NEspadne pod prah zadna plocha (filtr by beztak nemel
     co zahodit), povazujeme model za "bez loga" a tesselacni odchylka
     (linear_deflection_mm) se dale VYNASOBI 0.2 (= 80 % jemnejsi/mensi
     odchylka = jemnejsi sit), protoze u hladkych dilu bez rytiny uz
     neni potreba nic filtrovat a jemnejsi sit vic sedi na realny tvar.
     Tohle automaticke prizpusobeni se uplatni jen pokud volajici
     NEPOSLAL explicitni --linear-deflection (stejne jako u puvodni
     adaptivni logiky dle velikosti dilu) - explicitni hodnota od
     volajiciho ma vzdy prednost.

  00) VOLBA KVALITY (NOVE, 2026-08-04, druhy pozadavek tyz den). Robert:
      "potrebujeme pridat do skladovych karet, zatrzitkovac hned vedle
      nacteni 3D modelu, ma to byt vyber kvality 3D modelu, nejnizsi ta
      puvodni kdyz je v modelu logo, stredni (tu jsme dnes pridali jako
      o 80% jemnejsi) a dejme 3 stupen plne zaobleni, zaroven tam
      uvadejme velikost kB". Rozsiruje automatickou detekci z bloku "0"
      o RUCNI PREPSANI - pokud volajici posle `quality`, pouzije se
      pevny preset MISTO automaticke detekce (viz QUALITY_PRESETS nize):
        - "low"    - puvodni chovani (jako drive vzdy, resp. jako auto
          detekce s logem): filtr malych ploch aktivni (1 %), odchylka
          beze zmeny, decimace 75 %.
        - "medium" - dnesni "bez loga" chovani: filtr aktivni (1 %),
          odchylka o 80 % jemnejsi, decimace 75 %.
        - "high"   - NOVY 3. stupen "plne zaobleni": filtr VYPNUTY (0 %,
          zadna plocha se nezahazuje, ani pripadne logo), odchylka o
          90 % jemnejsi (jeste jemnejsi nez medium), BEZ decimace
          (simplify_percent=0) - maximalni zachovani zaobleni/radiusu.
      Bez `quality` (None) se chova stejne jako pred timto rozsirenim -
      automaticka detekce z bloku "0".

Pouziti (CLI):
    step_venv/bin/python3 step_convert_worker.py vstup.stp vystup.glb \\
        [--linear-deflection 0.5] [--simplify-percent 0.75] \\
        [--min-face-area-frac 0.01] [--quality low|medium|high]

Vystup: jeden radek JSON na stdout, {"ok": true/false, ...}. Exit kod 0
pri uspechu, 1 pri jakemkoli selhani (chyba je v JSON i na stderr).
"""

QUALITY_PRESETS = {
    "low":    {"min_face_area_frac": 0.01, "deflection_mult": 1.0, "simplify_percent": 0.75},
    "medium": {"min_face_area_frac": 0.01, "deflection_mult": 0.2, "simplify_percent": 0.75},
    "high":   {"min_face_area_frac": 0.0,  "deflection_mult": 0.1, "simplify_percent": 0.0},
}
import sys
import json
import argparse


def convert(step_path, glb_path, linear_deflection_mm=None, simplify_percent=0.75, min_face_area_frac=0.01, quality=None):
    import numpy as np
    import trimesh
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    reader = STEPControl_Reader()
    status = reader.ReadFile(step_path)
    if status != IFSelect_RetDone:
        return {"ok": False, "error": f"Nepodařilo se přečíst STEP soubor (status={status}) - poškozený nebo nepodporovaný formát."}
    num_roots = reader.TransferRoots()
    if num_roots < 1:
        return {"ok": False, "error": "STEP soubor neobsahuje žádnou přenositelnou geometrii (0 transferred roots)."}
    shape = reader.OneShape()

    # Odhad celkove velikosti dilu (bounding box) - pouziva se k odvozeni
    # rozumne HRUBE tesselacni odchylky, pokud nebyla explicitne zadana
    # (--linear-deflection). Male dily (male desitky mm) by s pevnou
    # odchylkou 0.5mm mohly vypadat hranate, velke dily (metry) by naopak
    # zbytecne narostly v poctu trojuhelniku - odchylka cca 0.3-1 % z
    # nejvetsiho rozmeru je rozumny kompromis.
    bbox = Bnd_Box()
    BRepBndLib.Add_s(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    dims_mm = [xmax - xmin, ymax - ymin, zmax - zmin]
    max_dim = max(dims_mm) if dims_mm else 0

    # bot6, 2026-08-09 (Robert: "šlo by tu patku přebarvit jen částečně?"
    # - "Kovová patka M8x50" ma ve zdrojovem STEP 2 samostatna telesa
    # /kovovy sroub + gumova/plastova patka/, ale drivejsi verze tenhle
    # rozdil zahazovala - VSECHNY plochy skoncily v jednom spolecnem
    # meshi bez ohledu na to, ke kteremu telesu (TopAbs_SOLID) patrily.
    # Diky tomu nešlo v scene.html cilit barvu jen na cast dilu (viz
    # applyPartMaterial - traverse() prochazi VSECHNY meshe stejne).
    # Reseni: samostatne tesely (TopAbs_SOLID) se ted tesseluji KAZDE
    # ZVLAST (viz face_solid_idx nize) a vysledny GLB pak ma pro kazde
    # samostatny pojmenovany mesh ("Solid_0", "Solid_1", ...) mist
    # jednoho slouceneho - beze zmeny vizualniho vysledku u (drtive
    # vetsiny) dilu s jen JEDNIM telesem, ktere se exportuji uplne
    # stejne jako drive (jeden Trimesh, ne Scene).
    solid_exp = TopExp_Explorer(shape, TopAbs_SOLID)
    solids = []
    while solid_exp.More():
        solids.append(TopoDS.Solid_s(solid_exp.Current()))
        solid_exp.Next()
    if not solids:
        # Fallback - STEP bez explicitniho Solidu (napr. holy Shell) -
        # puvodni chovani, cely shape jako "jedno teleso".
        solids = [shape]

    # KROK 1: projdi vsechny B-rep plochy (po jednotlivych telesech, aby
    # slo pozdeji tesselaci rozdelit zvlast pro kazde), spocitej jejich
    # plochu (mm^2) a rozhodni prah pro "detail/logo" - relativne k
    # NEJVETSI plose na CELEM dilu (nezmeneno, stale globalni - logo muze
    # byt na kterekoli casti). Teprve plochy NAD prahem se posilaji do
    # tesselace - logo/rytina se tak nikdy neobjevi ani v hrube siti,
    # natoz ve finalnim GLB. Tahle statistika se navic pouzije i pro
    # KROK 0 (automaticka detekce loga) nize.
    all_brep_faces = []
    face_areas = []
    face_solid_idx = []
    for solid_i, solid in enumerate(solids):
        exp_area = TopExp_Explorer(solid, TopAbs_FACE)
        while exp_area.More():
            f = TopoDS.Face_s(exp_area.Current())
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(f, props)
            all_brep_faces.append(f)
            face_areas.append(props.Mass())
            face_solid_idx.append(solid_i)
            exp_area.Next()

    faces_step_total = len(all_brep_faces)
    max_face_area = max(face_areas) if face_areas else 0.0

    # KROK 00: rucni preset kvality ma prednost pred automatikou - pokud
    # je zadan, prepise min_face_area_frac/simplify_percent PRED vypoctem
    # prahu, aby detekce loga (KROK 0 nize) i filtr uz pracovaly se
    # spravnym prahem pro zvoleny stupen kvality (viz docstring, blok "00").
    quality_preset = QUALITY_PRESETS.get(quality) if quality else None
    if quality_preset:
        min_face_area_frac = quality_preset["min_face_area_frac"]
        simplify_percent = quality_preset["simplify_percent"]

    area_threshold = (max_face_area * min_face_area_frac) if (min_face_area_frac and max_face_area > 0) else 0.0

    # KROK 0: automaticka detekce loga/rytiny - "ma logo", pokud aspon
    # jedna plocha spadne pod prah z kroku 1 (tzn. filtr by mel vubec co
    # zahodit). Bez explicitni --linear-deflection OD volajiciho A bez
    # rucniho presetu kvality se podle tohohle dale upravi jemnost
    # tesselace (viz docstring, blok "0").
    logo_detected = area_threshold > 0 and any(a < area_threshold for a in face_areas)

    base_deflection = max(0.1, min(2.0, max_dim * 0.004)) if max_dim > 0 else 0.5
    if quality_preset:
        linear_deflection_mode = f"quality_{quality}"
        linear_deflection_mm = base_deflection * quality_preset["deflection_mult"]
    elif linear_deflection_mm is None:
        linear_deflection_mode = "auto_logo" if logo_detected else "auto_no_logo_finer"
        linear_deflection_mm = base_deflection if logo_detected else base_deflection * 0.2
    else:
        linear_deflection_mode = "explicit"

    mesh = BRepMesh_IncrementalMesh(shape, linear_deflection_mm, False, 0.5, True)
    mesh.Perform()
    if not mesh.IsDone():
        return {"ok": False, "error": "Tesselace (BRepMesh_IncrementalMesh) selhala."}

    # Trojuhelniky se sbiraji ZVLAST pro kazde teleso (solid_verts[i]/
    # solid_tris[i]), ne do jednoho spolecneho pole jako drive - vert_offset
    # se tak resetuje na 0 pro kazde teleso zvlast (indexy trojuhelniku
    # musi byt lokalni v ramci SVEHO pole vrcholu).
    solid_verts = [[] for _ in solids]
    solid_tris = [[] for _ in solids]
    solid_vert_offset = [0] * len(solids)
    faces_kept = 0
    faces_dropped_as_detail = 0
    for face, area, si in zip(all_brep_faces, face_areas, face_solid_idx):
        if area_threshold > 0 and area < area_threshold:
            faces_dropped_as_detail += 1
            continue
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            n_nodes = tri.NbNodes()
            for i in range(1, n_nodes + 1):
                p = tri.Node(i)
                p_transformed = p.Transformed(trsf)
                solid_verts[si].append([p_transformed.X(), p_transformed.Y(), p_transformed.Z()])
            n_tris = tri.NbTriangles()
            face_reversed = face.Orientation_s() if hasattr(face, "Orientation_s") else face.Orientation()
            vert_offset = solid_vert_offset[si]
            for i in range(1, n_tris + 1):
                t = tri.Triangle(i)
                i1, i2, i3 = t.Get()
                # OCCT indexy jsou 1-based; FORWARD orientace = normalni
                # poradi, REVERSED = prohodit 2 vrcholy (jinak by normala
                # ukazovala dovnitr dilu misto ven).
                if str(face_reversed) == "TopAbs_Orientation.TopAbs_REVERSED" or face_reversed == 1:
                    solid_tris[si].append([vert_offset + i1 - 1, vert_offset + i3 - 1, vert_offset + i2 - 1])
                else:
                    solid_tris[si].append([vert_offset + i1 - 1, vert_offset + i2 - 1, vert_offset + i3 - 1])
            solid_vert_offset[si] += n_nodes
            faces_kept += 1

    meshes = []
    for si in range(len(solids)):
        if not solid_tris[si]:
            continue
        verts_np = np.array(solid_verts[si], dtype=np.float64)
        faces_np = np.array(solid_tris[si], dtype=np.int64)
        meshes.append(trimesh.Trimesh(vertices=verts_np, faces=faces_np, process=True))

    if not meshes:
        return {"ok": False, "error": "Ve STEP souboru nebyla po tesselaci nalezena žádná použitelná geometrie (0 trojúhelníků) - zkontrolujte, zda min_face_area_frac není nastaven příliš agresivně."}

    tris_before = sum(len(m.faces) for m in meshes)
    tris_after = tris_before
    if simplify_percent and 0 < simplify_percent < 1:
        simplified = []
        for m in meshes:
            if len(m.faces) > 20:
                try:
                    m = m.simplify_quadric_decimation(percent=simplify_percent)
                except Exception:
                    # Zjednoduseni je "bonus" krok (osekani radiusu) - selhani
                    # (napr. degenerovana topologie) nesmi shodit cely prevod,
                    # jen se pouzije nezjednodusena (ale porad hrube tesselovana)
                    # geometrie tohohle jednoho telesa.
                    pass
            simplified.append(m)
        meshes = simplified
        tris_after = sum(len(m.faces) for m in meshes)

    for m in meshes:
        _ = m.vertex_normals  # zajisti NORMAL atribut v exportu (viz fbx_convert.py - stejny duvod)

    if len(meshes) == 1:
        # Drtiva vetsina dilu ma jen 1 teleso - export beze zmeny oproti
        # puvodnimu chovani (jeden Trimesh, ne Scene).
        combined = meshes[0]
        combined.export(glb_path)
        vertices_count = int(len(combined.vertices))
        watertight = bool(combined.is_watertight)
    else:
        # Vice telesech (napr. sroub + gumova patka) - kazde jako vlastni
        # pojmenovany mesh v GLB, aby je slo v scene.html cilit samostatne
        # (napr. castecne obarveni - viz applyPartMaterial).
        scene_out = trimesh.Scene()
        for i, m in enumerate(meshes):
            scene_out.add_geometry(m, node_name=f"Solid_{i}", geom_name=f"Solid_{i}")
        scene_out.export(glb_path)
        vertices_count = sum(int(len(m.vertices)) for m in meshes)
        watertight = all(bool(m.is_watertight) for m in meshes)

    return {
        "ok": True,
        "dims_mm": [round(d, 2) for d in dims_mm],
        "faces_step": faces_kept,
        "faces_step_total": faces_step_total,
        "faces_dropped_as_detail": faces_dropped_as_detail,
        "min_face_area_frac_used": min_face_area_frac,
        "triangles_before_simplify": tris_before,
        "triangles_after_simplify": tris_after,
        "logo_detected": logo_detected,
        "quality": quality if quality_preset else None,
        "linear_deflection_mode": linear_deflection_mode,
        "linear_deflection_used_mm": round(linear_deflection_mm, 4),
        "simplify_percent_used": simplify_percent,
        "vertices": vertices_count,
        "watertight": watertight,
        "solid_count": len(meshes),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step_path")
    parser.add_argument("glb_path")
    parser.add_argument("--linear-deflection", type=float, default=None)
    parser.add_argument("--simplify-percent", type=float, default=0.75)
    parser.add_argument("--min-face-area-frac", type=float, default=0.01)
    parser.add_argument("--quality", choices=["low", "medium", "high"], default=None)
    args = parser.parse_args()

    try:
        result = convert(args.step_path, args.glb_path, args.linear_deflection, args.simplify_percent, args.min_face_area_frac, args.quality)
    except Exception as e:
        result = {"ok": False, "error": f"Neočekávaná chyba převodu: {type(e).__name__}: {e}"}

    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
