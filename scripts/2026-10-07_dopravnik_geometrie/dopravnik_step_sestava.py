#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP sestava valeckoveho dopravniku z ORIGINALNICH STEP dilu dodavatele na polohach z generatoru (bot8, 2026-10-07; Robert: "pro kontrolu potrebuji vzorovy dopravnik ve stepu ke stazeni").

Kazdy dil sestavy (valecky, bocnice, nohy, patky, spodni ram) = originalni STEP dodavatele (`podklady/<SKU>/<SKU>.step`), prevedeny do mistni soustavy dilu (rotace zdroje a pivot z geometrie.json, stejne jako ve GLB),
posunuty o teleskop a vysunuti cepu (to jsou NAVRHOVE kontrolni polohy generatoru, ne hotova montaz) a umisteny podle `polohy_dilu` konfiguratoru. Prizmaticke profily (bocnice 23x75 / 23x127, profil 40x40) se dela PRESNE
v dane delce vytazenim koncove plochy (zadne natazeni sitě). Spodni uchyty ramu (kruhove sedlo O48,3 neodpovida profilu 40x40) NEMAJI polohu a ve STEP nejsou.
Vystup: STEP AP214 s pojmenovanymi soucastmi (XCAF; nazvy = uzly generatoru roll_001, rail_left, leg_01_L ..., s priponou _solid_<n>), jednotky mm, osa X = delka, Y = vyska (podlaha 0), Z = sirka.

Spusteni (potrebuje OCP = api/step_venv):
  api/step_venv/bin/python scripts/2026-10-07_dopravnik_geometrie/dopravnik_step_sestava.py --podklady <slozka s podklady/<SKU>/<SKU>.step> [--vyber '{"rtype":"alu","width":590,"len":2000,...}'] -o dopravnik.step
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_Plane
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
from OCP.gp import gp_Trsf, gp_Vec

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "api_kandidat"))                  # kandidat (po prevzeti do repa: api/dopravnik_konfigurator.py a odsud smazat)
sys.path.insert(1, os.path.join(HERE, "..", "..", "api"))
import dopravnik_konfigurator as K  # noqa: E402

PROFILY_PRIZMA = ("1.2.00.023075.00", "1.2.00.023127.00", "1.1.10.040040.02")        # prizmaticke profily: presna delka vytazenim koncove plochy
BARVY = {"valecek": (0.63, 0.66, 0.70), "profil": (0.70, 0.72, 0.75), "noha": (0.45, 0.48, 0.53), "patka": (0.10, 0.10, 0.11), "ram": (0.90, 0.55, 0.15)}


def cti_step(cesta):
    r = STEPControl_Reader()
    if r.ReadFile(cesta) != IFSelect_RetDone or r.TransferRoots() < 1:
        raise SystemExit("STEP se nepodarilo precist: " + cesta)
    return r.OneShape()


def solidy(shape):
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    out = []
    while ex.More():
        out.append(TopoDS.Solid_s(ex.Current()))
        ex.Next()
    return out or [shape]


def trsf_z_matice(M):
    """gp_Trsf z 4x4 matice (rotace + posun; bez zkoseni)."""
    t = gp_Trsf()
    t.SetValues(M[0][0], M[0][1], M[0][2], M[0][3], M[1][0], M[1][1], M[1][2], M[1][3], M[2][0], M[2][1], M[2][2], M[2][3])
    return t


def matice(R=None, posun=(0.0, 0.0, 0.0)):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = np.array(R, dtype=float)
    M[:3, 3] = posun
    return M


def quaternion_na_matici(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def transformuj(shape, M):
    return BRepBuilderAPI_Transform(shape, trsf_z_matice(M), True).Shape()


def prizma_v_delce(solid_lokalne, delka_vzoru, delka):
    """Prizmaticky profil v mistni soustave (osa X = delka, vzor ma stred v X = 0) -> solid dlouhy `delka` mm se stredem v X = 0 (vytazeni koncove plochy v X = +vzor/2)."""
    nejlepsi, plocha = None, -1.0
    ex = TopExp_Explorer(solid_lokalne, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        a = BRepAdaptor_Surface(f)
        if a.GetType() == GeomAbs_Plane:
            pl = a.Plane()
            n = pl.Axis().Direction()
            o = pl.Location()
            if abs(abs(n.X()) - 1.0) < 1e-6 and abs(o.X() - delka_vzoru / 2.0) < 1e-3:
                g = GProp_GProps()
                BRepGProp.SurfaceProperties_s(f, g)
                if g.Mass() > plocha:
                    nejlepsi, plocha = f, g.Mass()
        ex.Next()
    if nejlepsi is None:
        raise SystemExit("Profil nema planarni koncovou plochu v X = +%.1f (nelze vytahnout presnou delku)" % (delka_vzoru / 2.0))
    prisma = BRepPrimAPI_MakePrism(nejlepsi, gp_Vec(-delka, 0.0, 0.0)).Shape()
    return transformuj(prisma, matice(None, (delka / 2.0 - delka_vzoru / 2.0, 0.0, 0.0)))


def barva(sku):
    if sku.startswith("3.009."):
        return BARVY["valecek"]
    if sku.startswith("3.004."):
        return BARVY["noha"]
    if sku == K.PATKA:
        return BARVY["patka"]
    return BARVY["profil"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--podklady", required=True, help="slozka s podklady/<SKU>/<SKU>.step")
    ap.add_argument("--vyber", default="{}", help="JSON vyber (rtype, width, len, pitch, h, legs, frame)")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    geo = K.nacti_geometrii()
    r = K.sestav_dopravnik(**json.loads(a.vyber))
    cache = {}

    def zdroj(sku):
        if sku not in cache:
            cache[sku] = cti_step(os.path.join(a.podklady, sku, sku + ".step"))
        return cache[sku]

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    koren = st.NewShape()
    TDataStd_Name.Set_s(koren, TCollection_ExtendedString("Dopravnik %s %d x %d, rozteč %d, výška %d" % (r["parametry"]["rtype"], r["parametry"]["width"], r["parametry"]["len"], r["parametry"]["pitch"], r["parametry"]["h"])))
    pocet = 0
    for d in r["polohy_dilu"]:
        if d["poloha_mm"] is None:
            continue
        g = geo[d["sku"]]
        R = np.array(g["rotace_zdroje"], dtype=float)
        pivot = np.array(g["pivot_zdroje_mm"], dtype=float)
        lokalni = matice(R, -R @ pivot)                                        # STEP -> mistni soustava dilu (mm)
        svet = matice(quaternion_na_matici(d["quaternion"]), d["poloha_mm"])   # mistni -> svet
        S = np.diag(d["scale"] + [1.0])
        for m in g["meshes"]:
            i = m["teleso"]
            solid = solidy(zdroj(d["sku"]))[i]
            posun = (0.0, d.get("posun_teleskopu_mm", 0.0) if i in g.get("posuvna_telesa", []) else 0.0, d.get("vysunuti_cepu_mm", 0.0) if i in d.get("vysunuta_telesa", []) else 0.0)
            if d["sku"] in PROFILY_PRIZMA:
                delka_vzoru = g["delka_vzoru_mm"]
                delka = delka_vzoru * d["scale"][0]
                tvar = transformuj(solid, lokalni)
                tvar = prizma_v_delce(tvar, delka_vzoru, delka)
                tvar = transformuj(tvar, svet)                                  # (mnozina meritek: jen v ose X, uz zohledneno delkou)
            else:
                tvar = transformuj(solid, svet @ matice(None, posun) @ S @ lokalni)
            lab = st.AddShape(tvar, False)
            TDataStd_Name.Set_s(lab, TCollection_ExtendedString("%s_solid_%02d" % (d["id"], i)))
            c = barva(d["sku"]) if not d.get("navrh") else BARVY["ram"]
            ct.SetColor(lab, Quantity_Color(c[0], c[1], c[2], Quantity_TOC_RGB), XCAFDoc_ColorSurf)
            st.AddComponent(koren, lab, TopLoc_Location())
            pocet += 1
    st.UpdateAssemblies()
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.SetColorMode(True)
    if not w.Transfer(doc, STEPControl_AsIs):
        raise SystemExit("Prevod sestavy do STEP selhal")
    if not w.Write(a.out):
        raise SystemExit("Zapis STEP selhal")
    print("STEP: %s | %d teles z %d dilu | %.1f MB" % (a.out, pocet, sum(1 for d in r["polohy_dilu"] if d["poloha_mm"] is not None), os.path.getsize(a.out) / 1e6))


if __name__ == "__main__":
    main()
