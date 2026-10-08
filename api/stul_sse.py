"""SSE STUL (system 41) - jadro generatoru (bot8, 2026-10-05).

Robert 2026-10-05 (nacrt "#581 Noha SSE"): "postav novy generator, kompatibilni jako ostatni, v podstate jde o system 40, jen nohy pouziva pouze tyto jeklove s vnitrnim profilem 35x35 pro
vyskovou stavitelnost"; "podelniky s pracovni deskou smerem dolu uz nemaji profily 40, ale nohy SSE"; "delku stolu urcuje podelnik tzn deska max 3000 mm, podelnik ma o 10 mm mene aby vesly
zaslepky"; "jeklova spojnice nohy SSE muze mit libovolnou delku, od 400 do 1100 mm coz urcuje hloubku stolu"; "mezera mezi nohama v zakladu: 1570 mm" (u desky 2000 mm). Rozsah prvni verze
(Robertova volba): zaklad + spodni police + supliky; stojky s panely, LED, elektrozlab a drzak PET jsou dalsi krok. Hloubka stolu = jeklova spojnice + 80 mm (Robertova volba).

GEOMETRIE (z vlastniho tvaru #581 "Noha SSE" a stolu #561 "SSE.vzor.01"; osy jako v generatoru stolu: x = hloubka (predni hrana x = 0), y nahoru (podlaha 0), z = sirka zleva doprava)
  * PRACOVNI DESKA (laminodeska 18 mm, karta 4933) sirka W (max 3000) x hloubka D; horni plocha ve vysce H. Spodek desky = T = H - 18 = horni konec jeklu = horni plocha podelniku.
  * PODELNIKY: 2 x profil 40x40 (Object_11), delka W - 10 (5 mm z kazde strany pro zaslepky), predni v x = 46..86, zadni v x = D - 86..D - 46; pod nimi uz neni zadny profil.
  * NOHA SSE (portal; 2 ks, od sirky nad prahem 3. uprostred): 2 svisle jekly 40x40 delky 675 (predni x = 0..40, zadni x = D - 40..D) lezi vnejsim licem v rovine hrany desky; spojuje je jeklova
    SPOJNICE 40x40 delky C = D - 80 (400-1100 mm) 90 mm nad spodkem jeklu; k hornimu konci jeklu je z vnitrni strany privarena sirokova plechova patka 150x40x6, na ni se sroubuje podelnik. Do kazdeho
    jeklu zajizdi zespodu vnitrni profil 35x35 delky 425 (+ 3 mm zaslepka na podlaze): VYSKA STOLU = poloha jeklu na vnitrnim profilu (spodek jeklu y0 = T - 675, 7-307 mm nad podlahou).
    Vnejsi lice noh jsou 175 mm od konce desky (u desky 2000 mm je mezera mezi nohama 1570 mm).
  * SPODNI POLICE (volitelna, 1 ks): laminodeska 18 mm lezi na spojnicich (horni hrana spojnice = spodek police), delka = vnejsi lice krajnich noh + 2 x 7,5 mm, hloubka C - 20 (od predniho jeklu).
  * SUPLIKY: stejny box (karty 4956 / 4930 / 4957) a stejne uchyceni jako v systemu 40 - dve pricky 40x40 mezi podelniky + 4 rohove spojky 3176; polohy se berou ze zmrazene sablony
    systemu 40 (`stul_sablona_system40.json`), takze jsou s nim shodne. Box se da posouvat po celem rozpeti podelniku (nohy mu neprekazi: jekly jsou pred / za podelniky).
  * Stredni noha (W nad prahem pravidla `sirka_stredni_noha` SSE): stejna noha uprostred (nebo kde urci `stredni_noha`), desky se deli v jeji ose (formaty tabuli laminodesky).
  Nic, co SSE nema (stojky, panely, LED, elektrozlab, PET, kolecka, patky, navlek, vzpery, loziska, vyrezy), se nenabizi: vstup se normalizuje na vypnute, EXPLICITNE zapnute = StulChyba.

CENA: jekly, plechy, vnitrni profily a zaslepky jsou PROCEDURALNI dily (bez karty katalogu), cena nohy je PRAVIDLO (stul_api.extra_prace: pravidla `cena_noha_sse_400` / `cena_noha_sse_1100`
v Pravidlech stolu systemu SSE, linearne podle delky spojnice). Cista funkce, zadna DB.
"""
import math

import numpy as np

import stul_konfigurator as S

StulChyba = S.StulChyba
SYSTEM = S.SYSTEM_SSE

_S2 = math.sqrt(0.5)
Q_IDENT = (0.0, 0.0, 0.0, 1.0)
Q_RY90 = (0.0, _S2, 0.0, _S2)                    # lokalni +X -> svetove -Z, lokalni +Z -> svetove +X (plechova patka: sirka podel Z, tloustka podel X)
Q_RY180 = (0.0, 1.0, 0.0, 0.0)                   # lokalni +Z -> svetove -Z (zaslepka praveho konce podelniku: "dovnitr profilu" = -Z)
Q_RZ_M90 = (0.0, 0.0, _S2, -_S2)                 # lokalni +Y -> svetove +X (dlouha osa podel hloubky: spojnice, pricky boxu) - stejny kvaternion jako v sablone
Q_RX_M90 = (-_S2, 0.0, 0.0, _S2)                 # lokalni +Y -> svetove -Z, lokalni +Z -> svetove +Y (deska 1000x1000x18 lezi: tloustka nahoru; osa Y desky = sirka stolu)
Q_PODELNIK = (_S2, 0.0, 0.0, -_S2)               # profil podel osy Z (stejny kvaternion jako podelniky v sablone)

# ---------------------------------------------------------------------------------------------------------------------
# normalizace vstupu
# ---------------------------------------------------------------------------------------------------------------------
NEPODPOROVANE = ("stojky", "kolecka", "panely", "led", "elektrozlab", "drzak_pet", "patky", "navlek", "vzpery", "loz", "hpolice")
# parametry, ktere SSE nepouziva: vzdy vychozi hodnota (jedna kanonicka podoba = jeden hash); explicitni jina hodnota se tise ignoruje u cisel, u prepinacu viz NEPODPOROVANE
IGNOROVANE = ("presah", "led_rameno", "led_svetlo", "stojky_vyska", "panely_pocet", "panely_posun", "panely_z", "panely_delka", "led_delka", "elzlab_y", "elzlab_z", "navlek_delka", "pet_noha", "pet_strana", "pet_posun",
              "loz_rozteca", "loz_okraj", "vzpera_delka", "hpolice_typ", "hpolice_deska", "hpolice_vyska", "hpolice_hloubka", "hpolice_sklon") + tuple(f"police_h{j}" for j in range(1, 11)) + ("led_pocet",) + S.LED_PARAMETRY_Z


def rozsah(klic):
    """(min, max) parametru `klic` (sirka / hloubka / vyska) pro SSE."""
    return S.SYSTEMY[SYSTEM]["rozsah"][klic]


def over_parametry(out, vstup):
    """Dokonci normalizaci parametru pro system SSE (volano z S._norm_parametry po obecne kontrole): zuzene rozsahy, nepodporovane volby vypnute (explicitni zapnuti = StulChyba)."""
    for k in NEPODPOROVANE:
        if k in vstup and bool(vstup[k]):
            raise StulChyba(f"{k}: v systemu SSE zatim neni (zakladni stul, spodni police a supliky)", "nepodporovano")
        out[k] = False
    for n in range(1, S.MAX_VYREZU + 1):
        if vstup.get(f"vyrez{n}") or vstup.get(f"vyrez{n}_police"):
            raise StulChyba(f"vyrez{n}: v systemu SSE zatim vyrezy nejsou", "nepodporovano")
        out[f"vyrez{n}"] = False
        out[f"vyrez{n}_police"] = False
    if "stredni_opora" in vstup and vstup["stredni_opora"] != "auto":
        raise StulChyba(f"stredni_opora: SSE ma jen stredni nohu SSE ('auto'), ne '{vstup['stredni_opora']}'", "nepodporovano")
    out["stredni_opora"] = "auto"
    for k in IGNOROVANE:
        out[k] = S.VYCHOZI[k]
    out["police_deska"] = S.VYCHOZI["police_deska"]                  # SSE nema ram police (deska lezi na spojnicich): volba 'bez desky' se ignoruje (jedna kanonicka podoba = jeden hash)
    for k in ("sirka", "hloubka", "vyska"):
        lo, hi = rozsah(k)
        if not lo <= out[k] <= hi:
            raise StulChyba(f"{k} {out[k]:g} mm je mimo rozsah {lo:g}-{hi:g} mm (stul SSE)", "mimo_rozsah")
    if out["police"] not in (0, 1):
        raise StulChyba(f"police: stul SSE ma nejvyse jednu spodni polici (0 nebo 1), ne {out['police']}", "mimo_rozsah")
    return out


# ---------------------------------------------------------------------------------------------------------------------
# geometrie
# ---------------------------------------------------------------------------------------------------------------------
def spojnice(hloubka):
    """Delka jeklove spojnice nohy (mm) pro hloubku stolu `hloubka`: hloubka - 2 x 40."""
    return float(hloubka) - 2.0 * S.SSE_JEKL


def y_jeklu(vyska):
    """Spodek jeklu nad podlahou (mm) pro vysku horni plochy desky `vyska`: horni konec jeklu = spodek desky."""
    return float(vyska) - S.DESKA_TLOUSTKA - S.SSE_STOJKA


def zeme_nohou(sirka):
    """(z leve nohy, z prave nohy): osy krajnich noh od leve hrany desky."""
    zl = S.SSE_ODSAZENI + S.SSE_JEKL / 2.0
    return zl, float(sirka) - zl


def stredni_meze(sirka):
    """(min, max) osy stredni nohy od leve hrany desky: aspon MIN_ODSTUP_STREDNI_NOHY od krajnich noh a obe casti desky se vejdou do tabule laminodesky; None bez stredni nohy."""
    if float(sirka) <= S.prah_sirky(SYSTEM):
        return None
    zl, zr = zeme_nohou(sirka)
    dl = S.max_delka_desky()
    mo = S.min_odstup_stredni_noha(SYSTEM)                                   # pravidlo systemu SSE (vychozi 150)
    lo = max(zl + mo, float(sirka) - dl)
    hi = min(zr - mo, dl)
    if lo > hi:                                                              # (jen u mensi tabule nez 2 x sirka stolu) poloha se kontroluje jen proti nohám
        lo, hi = zl + mo, zr - mo
    return lo, hi


_BOX_SAB = {}


def _box_sablona():
    """Vztahy suplikoveho boxu k podelnikum a spojkam ZE ZMRAZENE SABLONY SYSTEMU 40 (jedna pravda: SSE a system 40 maji box uchyceny stejne)."""
    if _BOX_SAB:
        return _BOX_SAB
    with S._v_systemu(40):
        sab = S.sablona()
        pred, box = sab[S.ZRAIL_PRAC_PRED], sab[S.BOX]
        b_lo, b_hi = S._aabb(box)
        h = S._H()
        pred_x = float(pred["position"][0])
        pred_y = float(pred["position"][1])
        out = {
            "box_q": tuple(box["quaternion"]),
            "box_x_lo_od_lice": float(b_lo[0]) - (pred_x - h),                 # predni hrana boxu vuci VNEJSIMU licu predniho podelniku (zaporne = pred nim)
            "box_y_hi_od_spodku": float(b_hi[1]) - (pred_y - h),               # horni hrana boxu vuci spodku podelniku
            "box_z_sirka": float(b_hi[2] - b_lo[2]),
            "pricka_q": tuple(sab[S.XRAIL_BOX1]["quaternion"]),
            "pricka_z": [float(sab[i]["position"][2]) - float(b_lo[2]) for i in (S.XRAIL_BOX1, S.XRAIL_BOX2)],
            "pricka_y_od_stredu_podelniku": float(sab[S.XRAIL_BOX1]["position"][1]) - pred_y,
            "spojky": [],
        }
        for i, rail in ((36, S.XRAIL_BOX1), (37, S.XRAIL_BOX1), (38, S.XRAIL_BOX2), (39, S.XRAIL_BOX2)):
            sp = sab[i]
            out["spojky"].append({"part_id": sp["part_id"], "q": tuple(sp["quaternion"]), "rail": 0 if rail == S.XRAIL_BOX1 else 1,
                                  "dx": float(sp["position"][0]) - (pred_x + h),                 # odsazeni od VNITRNIHO lice predniho podelniku
                                  "dy": float(sp["position"][1]) - float(sab[rail]["position"][1]),
                                  "dz": float(sp["position"][2]) - float(sab[rail]["position"][2]),
                                  "color": sp.get("color"), "used_conn": sp.get("used_conn"), "attached_to": dict(sp["attached_to"])})
    _BOX_SAB.update(out)
    return _BOX_SAB


def box_rozmer(pocet):
    """(sirka podel Z, vyska) boxu s `pocet` supliky v mm - z GLB karty."""
    bs = _box_sablona()
    d = {"part_id": S.SUPLIK_PARTY[int(pocet)], "quaternion": bs["box_q"], "scale": (1.0, 1.0, 1.0), "position": (0.0, 0.0, 0.0)}
    lo, hi = S._aabb(d)
    return float(hi[2] - lo[2]), float(hi[1] - lo[1])


def _poloz_stred(part_id, q, scale, stred):
    """Pozice dilu (pocatek GLB), aby stred jeho lokalni obalky lezel v bode `stred` (desky a procedural maji obalku mimo pocatek / ve stredu)."""
    lo, hi = S.glb_bbox(part_id)
    c = (np.array(lo, float) + np.array(hi, float)) / 2.0
    return np.array(stred, float) - S.kvat_na_matici(q) @ (np.array(scale, float) * c)


def _dil(part_id, q, scale, stred, **extra):
    pos = _poloz_stred(part_id, q, scale, stred)
    d = {"part_id": part_id, "position": [round(float(v), 4) for v in pos], "quaternion": [round(float(v), 6) for v in q], "scale": [round(float(v), 6) for v in scale]}
    d.update(extra)
    return d


def _meze_boxu(p, W, box_sirka):
    """Meze posunu supliku (mm, `suplik_posun`): rozpeti podelniku s rezervou SSE_BOX_OKRAJ od jejich konce. Vraci {"vlevo", "z0", "min", "max", "vejde"}: vychozi poloha `z0` je zadni hrana
    boxu (vpravo: z_hi = z0 + posun) nebo predni hrana (vlevo: z_lo = z0 - posun), vzdy 40 mm od vnitrniho lice krajni nohy; `vejde` = box se vubec vejde na rozpeti."""
    zl, zr = zeme_nohou(W)
    z_min, z_max = S.SSE_PODELNIK_PRIREZ / 2.0 + S.SSE_BOX_OKRAJ, W - S.SSE_PODELNIK_PRIREZ / 2.0 - S.SSE_BOX_OKRAJ
    odstup = S.SYSTEMY[SYSTEM]["odstup_od_nohou"]
    if p["suplik_vlevo"]:                                                    # box u leve nohy; kladny posun = k levemu konci
        z_lo0 = zl + S.SSE_JEKL / 2.0 + odstup
        return {"vlevo": True, "z0": z_lo0, "min": (z_lo0 + box_sirka) - z_max, "max": z_lo0 - z_min, "vejde": z_max - z_min >= box_sirka}
    z_hi0 = zr - S.SSE_JEKL / 2.0 - odstup
    return {"vlevo": False, "z0": z_hi0, "min": z_min + box_sirka - z_hi0, "max": z_max - z_hi0, "vejde": z_max - z_min >= box_sirka}


def sestav(p, meze=False):
    """Dily SSE stolu pro normalizovane parametry `p` (system 41) - viz modul. Vraci stejny slovnik jako S._sestav_jadro_systemu (nepouzite polozky None / prazdne)."""
    sd = S.SYSTEMY[SYSTEM]
    W, D, H = float(p["sirka"]), float(p["hloubka"]), float(p["vyska"])
    J, tl = S.SSE_JEKL, S.DESKA_TLOUSTKA
    T = H - tl
    C = spojnice(D)
    y0 = y_jeklu(H)
    zl, zr = zeme_nohou(W)
    zm = None
    mz = stredni_meze(W)
    if mz is not None:
        zm = p["stredni_noha"] + zl if p["stredni_noha"] is not None else (zl + zr) / 2.0
        if p["stredni_noha"] is not None and not mz[0] - 1e-6 <= zm <= mz[1] + 1e-6:
            raise StulChyba(f"stredni_noha {p['stredni_noha']:.0f} mm: musi byt aspon {S.min_odstup_stredni_noha(SYSTEM):.0f} mm od kazde krajni nohy a obe casti desky se musi vejit do tabule "
                            f"{S.max_delka_desky():.0f} mm (pripustno {mz[0] - zl:.0f} az {mz[1] - zl:.0f})", "mimo_rozsah")
    nohy = [zl] + ([zm] if zm is not None else []) + [zr]
    problemy = []
    dily, klice = [], []

    def pridej(klic, d):
        dily.append(d)
        klice.append(list(klic))
        return len(dily) - 1

    # --- pracovni deska (u stredni nohy rozdelena v jeji ose) ---
    hrany = [0.0] + ([zm] if zm is not None else []) + [W]
    for i in range(len(hrany) - 1):
        z0, z1 = hrany[i], hrany[i + 1]
        pridej(("sse", "deska", i), _dil("product_4933", Q_RX_M90, (D / 1000.0, (z1 - z0) / 1000.0, 1.0), (D / 2.0, T + tl / 2.0, (z0 + z1) / 2.0), deska_id=f"prac_{i}"))
    # --- podelniky + zaslepky na koncich ---
    zx = (J + S.SSE_PLECH_TL, D - J - S.SSE_PLECH_TL)                       # vnitrni lice plechu pred / zad
    xr = {"pred": zx[0] + J / 2.0, "zad": zx[1] - J / 2.0}                  # osy podelniku
    delka_p = W - S.SSE_PODELNIK_PRIREZ
    ipod = {}
    for jm in ("pred", "zad"):
        ipod[jm] = pridej(("sse", "podelnik", jm), _dil(sd["profil"], Q_PODELNIK, (1.0, delka_p / 1000.0, 1.0), (xr[jm], T - J / 2.0, W / 2.0)))
    zasl_v = sd["zaslepka_vyska"]
    z_konce = (S.SSE_PODELNIK_PRIREZ / 2.0, W - S.SSE_PODELNIK_PRIREZ / 2.0)
    for jm in ("pred", "zad"):
        pridej(("sse", "konec", jm, "L"), _dil_pos(sd["zaslepka"], Q_IDENT, (xr[jm], T - J / 2.0, z_konce[0] - zasl_v)))
        pridej(("sse", "konec", jm, "P"), _dil_pos(sd["zaslepka"], Q_RY180, (xr[jm], T - J / 2.0, z_konce[1] + zasl_v)))
    # --- nohy SSE ---
    for n, zc in enumerate(nohy):
        for jm, x in (("pred", J / 2.0), ("zad", D - J / 2.0)):
            pridej(("sse", "noha", n, "stojka", jm), _dil(S.SSE_JEKL_PART, Q_IDENT, (1.0, S.SSE_STOJKA / 1000.0, 1.0), (x, y0 + S.SSE_STOJKA / 2.0, zc)))
        pridej(("sse", "noha", n, "spojnice"), _dil(S.SSE_JEKL_PART, Q_RZ_M90, (1.0, C / 1000.0, 1.0), (D / 2.0, y0 + S.SSE_SPOJNICE_ZVEDNUTI + J / 2.0, zc)))
        for jm, x in (("pred", J + S.SSE_PLECH_TL / 2.0), ("zad", D - J - S.SSE_PLECH_TL / 2.0)):
            pridej(("sse", "noha", n, "plech", jm), _dil(S.SSE_PLECH_PART, Q_RY90, (1.0, 1.0, 1.0), (x, T - S.SSE_PLECH_VYSKA / 2.0, zc)))
        for jm, x in (("pred", J / 2.0), ("zad", D - J / 2.0)):
            pridej(("sse", "noha", n, "profil", jm), _dil(S.SSE_PROFIL_PART, Q_IDENT, (1.0, S.SSE_PROFIL_DELKA / 1000.0, 1.0), (x, S.SSE_PATKA_TL + S.SSE_PROFIL_DELKA / 2.0, zc)))
            pridej(("sse", "noha", n, "patka", jm), _dil(S.SSE_PATKA_PART, Q_IDENT, (1.0, 1.0, 1.0), (x, S.SSE_PATKA_TL / 2.0, zc)))
    # --- spodni police na spojnicich ---
    police = None
    if p["police"]:
        y_pol = y0 + S.SSE_SPOJNICE_ZVEDNUTI + J
        d_pol = C - S.SSE_POLICE_ODSTUP
        z_od, z_do = zl - J / 2.0 - S.SSE_POLICE_PRESAH, zr + J / 2.0 + S.SSE_POLICE_PRESAH
        hr = [z_od] + ([zm] if zm is not None else []) + [z_do]
        for i in range(len(hr) - 1):
            pridej(("sse", "polic", i), _dil("product_4933", Q_RX_M90, (d_pol / 1000.0, (hr[i + 1] - hr[i]) / 1000.0, 1.0),
                                             (J + d_pol / 2.0, y_pol + tl / 2.0, (hr[i] + hr[i + 1]) / 2.0), deska_id=f"pol0_{i}"))
        police = {"y_dolni": y_pol, "y_horni": y_pol + tl, "hloubka": d_pol, "z_od": z_od, "z_do": z_do}
    # --- supliky ---
    box = None
    suplik_meze = None
    spojky = []
    if p["suplik"]:
        bs = _box_sablona()
        pocet = int(p["suplik_pocet"])
        box_sirka, box_vyska = box_rozmer(pocet)
        mb = _meze_boxu(p, W, box_sirka)
        d0 = {"part_id": S.SUPLIK_PARTY[pocet], "quaternion": bs["box_q"], "scale": (1.0, 1.0, 1.0), "position": (0.0, 0.0, 0.0)}
        lo0, hi0 = S._aabb(d0)
        x_lo = xr["pred"] - J / 2.0 + bs["box_x_lo_od_lice"]
        x_hi = x_lo + float(hi0[0] - lo0[0])
        zad_vnitrni = zx[1] - J                                              # vnitrni lice zadniho podelniku: box ho nesmi prejit (pod nim uz je zadni jekl)
        vejde = mb["vejde"] and x_hi <= zad_vnitrni + 0.01
        if not vejde:
            problemy.append({"kod": "suplik_nevejde", "dily": [],
                             "text": (f"Šuplíkový box ({box_sirka:.0f} × {x_hi - x_lo:.0f} mm) se nevejde mezi podélníky: stůl musí být hluboký aspoň "
                                      f"{x_hi + (D - zad_vnitrni):.0f} mm a široký aspoň {box_sirka + 2 * (S.SSE_PODELNIK_PRIREZ / 2.0 + S.SSE_BOX_OKRAJ):.0f} mm.")})
        else:
            posun = float(p["suplik_posun"])
            eff = min(max(posun, mb["min"]), mb["max"])
            if mb["vlevo"]:
                z_lo = mb["z0"] - eff
            else:
                z_lo = mb["z0"] + eff - box_sirka
            y_hi = T - J + bs["box_y_hi_od_spodku"]
            pos = np.array([x_lo - float(lo0[0]), y_hi - float(hi0[1]), z_lo - float(lo0[2])], float)
            pridej(("sse", "box"), {"part_id": d0["part_id"], "position": [round(float(v), 4) for v in pos], "quaternion": [round(float(v), 6) for v in bs["box_q"]], "scale": [1.0, 1.0, 1.0]})
            dil_x = D / 2.0                                                     # prostredek mezi vnitrnimi lici podelniku
            delka_pricky = zad_vnitrni - (zx[0] + J)                            # pricka je mezi vnitrnimi lici podelniku (D - 172)
            irl = []
            for k in (0, 1):
                zr_ = z_lo + bs["pricka_z"][k]
                irl.append((pridej(("sse", "box_pricka", k + 1), _dil(sd["profil"], bs["pricka_q"], (1.0, delka_pricky / 1000.0, 1.0),
                                                                          (dil_x, T - J / 2.0 + bs["pricka_y_od_stredu_podelniku"], zr_))), zr_))
            x_spoj = zx[0] + J + bs["spojky"][0]["dx"]
            for sp in bs["spojky"]:
                iz, zr_ = irl[sp["rail"]]
                ic = pridej(("sse", "box_spojka", len(spojky)), {"part_id": sp["part_id"], "position": [round(x_spoj, 4), round(T - J / 2.0 + bs["pricka_y_od_stredu_podelniku"] + sp["dy"], 4), round(zr_ + sp["dz"], 4)],
                                                                 "quaternion": [round(float(v), 6) for v in sp["q"]], "scale": [1.0, 1.0, 1.0]})
                spojky.append({"i": ic, "rail": iz, "def": sp})
            box = {"x_lo": x_lo, "x_hi": x_hi, "z_lo": z_lo, "z_hi": z_lo + box_sirka, "y_dolni": y_hi - box_vyska, "y_horni": y_hi, "pocet": pocet}
            suplik_meze = {"hodnota": round(float(eff), 1), "min": round(float(mb["min"]), 1), "max": round(float(mb["max"]), 1), "vejde": True}
    # --- napojeni: lic_peers (profil-profil z geometrie), spojky, attached_to ---
    for sp in spojky:
        d = dily[sp["i"]]
        d["attached_to"] = {**sp["def"]["attached_to"], "prof": ipod["pred"]}
        if sp["def"].get("color"):
            d["color"] = sp["def"]["color"]
        if sp["def"].get("used_conn") is not None:
            d["used_conn"] = sp["def"]["used_conn"]
    bb = [S._aabb(d) for d in dily]
    profily = [i for i, d in enumerate(dily) if d["part_id"] == sd["profil"]]
    peers = {i: set() for i in profily}
    for ai, i in enumerate(profily):
        for j in profily[ai + 1:]:
            if S._dotyk_cela(bb[i], bb[j]):
                peers[min(i, j)].add(max(i, j))
    for sp in spojky:
        for vl in (sp["rail"], ipod["pred"]):
            peers[vl].add(sp["i"])
    for i in profily:
        if peers[i]:
            dily[i]["lic_peers"] = sorted(peers[i])
    pset = set(profily)
    spoje = sorted((i, j) for i in profily for j in peers[i] if j in pset)
    return {
        "vzpera_meze": None, "navlek_meze": None, "suplik_meze": suplik_meze, "pet_meze": None, "police_meze": None, "panely_info": None, "stojky_meze": None,
        "vyrezy": [], "loz": None, "parametry": p, "dily": dily, "problemy": problemy, "rozmery": S._rozmery(bb), "vodici_scena": None, "max_polic": 1, "info": [],
        "spoje": [list(x) for x in spoje], "pocet_spoju": len(spoje), "klice": klice,
        "sse": {"spojnice": C, "y_jeklu": y0, "T": T, "nohy": nohy, "stredni": zm, "police": police, "box": box, "podelnik_delka": delka_p,
                "preklad_profilu": S.SSE_PATKA_TL + S.SSE_PROFIL_DELKA - y0, "mezera_mezi_nohami": (zr - zl) - J},
    }


def _dil_pos(part_id, q, pos):
    """Dil s pocatkem GLB (ne stredem obalky) v bode `pos` (zaslepky: pocatek = stred vnejsi plochy prirubi)."""
    return {"part_id": part_id, "position": [round(float(v), 4) for v in pos], "quaternion": [round(float(v), 6) for v in q], "scale": [1.0, 1.0, 1.0]}


def co_odebrat(r, p):
    """Prepinace, jejichz prislusenstvi zpusobuje problem v sestave `r`: [(prepinac, text)] (jen supliky)."""
    for pr in r["problemy"]:
        if pr["kod"] == "suplik_nevejde" and p["suplik"]:
            return [("suplik", pr["text"])]
    return []


def dostupnost(vstup):
    """{prepinac: None | text duvodu} jako S.dostupnost: lze zapnout jen supliky (kdyz se vejdou); zbytek SSE zatim nema."""
    p = S.sestav_stul(**vstup)["parametry"]
    out = {}
    for k in S.PREPINACE + ("vzpery",):
        if k != "suplik":
            out[k] = "V systému SSE zatím není."
        elif p["suplik"]:
            out[k] = None
        else:
            r = S.sestav_stul(**{**p, "suplik": True})
            hit = [o["text"] for o in r["odebrano"] if o["volba"] == "suplik"]
            out[k] = None if r["parametry"]["suplik"] else (hit[0] if hit else "Nelze zapnout.")
    return out


def ovladani(r):
    """Popis ovladani ve 3D pro SSE stul (casti k najeti / klikani pravym tlacitkem a tahy = uchopovaci body), stejna struktura jako S._ovladani_3d_systemu (docs/OVLADANI_3D.md): pracovni deska
    (rozmery v panelu), nohy SSE (vyska / hloubka v panelu, pridat polici, stredni noha zpet doprostred), spodni police, supliky; tahy: vyska, sirka, hloubka desky a posun supliku (zive)."""
    dily, klice, p = r["dily"], [tuple(k) for k in r["klice"]], r["parametry"]
    bb = [S._aabb(d) for d in dily]
    sse = r["sse"]
    rz = S.SYSTEMY[SYSTEM]["rozsah"]

    def idx(pred):
        return [i for i, k in enumerate(klice) if pred(k)]

    def aabb(ids, pad=0.0):
        lo = np.min([bb[i][0] for i in ids], axis=0).astype(float)
        hi = np.max([bb[i][1] for i in ids], axis=0).astype(float)
        return [[round(float(v) - pad, 1) for v in lo], [round(float(v) + pad, 1) for v in hi]]

    def pol(text, nastav=None, duvod=None, **extra):
        out = {"text": text, "nastav": nastav, "zakazano": duvod is not None, "duvod": duvod}
        out.update(extra)
        return out
    desky = idx(lambda k: k[:2] == ("sse", "deska"))
    if not desky:
        return {"casti": [], "tahy": []}
    dlo, dhi = aabb(desky)
    X0, y_hore, Z0, X1, Z1 = dlo[0], dhi[1], dlo[2], dhi[0], dhi[2]
    D, W = X1 - X0, Z1 - Z0
    casti, tahy = [], []
    casti.append({"id": "deska", "label": "Pracovní deska", "param": ["sirka", "hloubka"], "aabb": [dlo, dhi], "priorita": 1, "menu": [pol("Rozměry desky nastavit v panelu", None, fokus="sirka")]})
    stredni = sse.get("stredni") is not None
    for n in range(len(sse["nohy"])):
        ids = idx(lambda k, n=n: k[:3] == ("sse", "noha", n))
        je_stredni = stredni and n == 1
        label = "Střední noha SSE" if je_stredni else ("Levá noha SSE" if n == 0 else "Pravá noha SSE")
        menu = [pol("Výšku stolu nastavit v panelu", None, fokus="vyska"), pol("Hloubku stolu (spojnici nohy) nastavit v panelu", None, fokus="hloubka")]
        if not p["police"]:
            menu.append(pol("Přidat spodní polici", {"police": 1}))
        if je_stredni:
            menu.append(pol("Střední nohu vrátit doprostřed", {"stredni_noha": None}, None if p["stredni_noha"] is not None else "Už je uprostřed."))
        casti.append({"id": f"noha_{n}", "label": label, "param": ["vyska", "hloubka"] + (["stredni_noha"] if je_stredni else []), "aabb": aabb(ids, pad=3.0), "priorita": 2, "menu": menu})
    police = idx(lambda k: k[:2] == ("sse", "polic"))
    if police:
        casti.append({"id": "police_1", "label": "Spodní police", "param": ["police"], "aabb": aabb(police), "priorita": 2, "menu": [pol("Odebrat spodní polici", {"police": 0})]})
    box = idx(lambda k: k[:2] in (("sse", "box"), ("sse", "box_pricka"), ("sse", "box_spojka")))
    ibox = idx(lambda k: k[:2] == ("sse", "box"))
    if box:
        casti.append({"id": "suplik", "label": "Šuplíky", "param": ["suplik", "suplik_pocet", "suplik_posun", "suplik_vlevo"], "aabb": aabb(box, pad=3.0), "priorita": 2,
                      "menu": [pol("Odebrat šuplíky", {"suplik": False})]
                      + [pol(f"Box s {c} {'šuplíkem' if c == 1 else 'šuplíky'}", {"suplik_pocet": c}) for c in S.SUPLIK_POCTY if c != int(p["suplik_pocet"])]
                      + [pol("Šuplíky vrátit na výchozí místo", {"suplik_posun": 0.0}, None if p["suplik_posun"] else "Už jsou na výchozím místě."),
                         pol("Přehodit šuplíky na pravou stranu" if p["suplik_vlevo"] else "Přehodit šuplíky na levou stranu", {"suplik_vlevo": not p["suplik_vlevo"]})]})
    # ---- tahy: vyska (horni konec jeklu leve nohy), sirka (prava hrana desky), hloubka (predni hrana desky), posun supliku
    jekl = next(iter(idx(lambda k: k == ("sse", "noha", 0, "stojka", "pred"))), None)
    if jekl is not None:
        lo_, hi_ = bb[jekl]
        tahy.append({"id": "vyska", "label": "Výška desky", "typ": "osa", "ikona": "sipka_y", "bod": [round(float((lo_[0] + hi_[0]) / 2), 1), round(float(hi_[1]), 1), round(float((lo_[2] + hi_[2]) / 2), 1)],
                     "osa": [0.0, 1.0, 0.0], "param": "vyska", "faktor": 1.0, "hodnota": p["vyska"], "min": float(rz["vyska"][0]), "max": float(rz["vyska"][1]), "krok": 10.0, "casti": ["deska"],
                     "mereni": [{"label": "výška desky", "param": "vyska"}]})
    tahy.append({"id": "sirka", "label": "Šířka desky", "typ": "osa", "ikona": "sipka_z", "bod": [round((X0 + X1) / 2, 1), y_hore, Z1], "osa": [0.0, 0.0, 1.0], "param": "sirka", "faktor": 2.0,
                 "hodnota": p["sirka"], "min": float(rz["sirka"][0]), "max": float(rz["sirka"][1]), "krok": 10.0, "casti": ["deska"], "mereni": [{"label": "šířka desky", "param": "sirka"}]})
    tahy.append({"id": "hloubka", "label": "Hloubka desky", "typ": "osa", "ikona": "sipka_x", "bod": [X0, y_hore, round((Z0 + Z1) / 2, 1)], "osa": [-1.0, 0.0, 0.0], "param": "hloubka", "faktor": 2.0,
                 "hodnota": p["hloubka"], "min": float(rz["hloubka"][0]), "max": float(rz["hloubka"][1]), "krok": 10.0, "casti": ["deska"], "mereni": [{"label": "hloubka desky", "param": "hloubka"}]})
    if ibox:
        blo, bhi = aabb(ibox)
        sm = r.get("suplik_meze") or {}
        t = {"id": "suplik_posun", "label": "Posun šuplíků", "typ": "osa", "ikona": "sipka_z", "bod": [blo[0], round((blo[1] + bhi[1]) / 2, 1), round((blo[2] + bhi[2]) / 2, 1)],
             "osa": [0.0, 0.0, -1.0 if p["suplik_vlevo"] else 1.0], "param": "suplik_posun", "faktor": 1.0, "hodnota": sm.get("hodnota", p["suplik_posun"]),
             "min": sm.get("min", 0.0), "max": sm.get("max", 0.0), "krok": 10.0, "casti": ["suplik"], "mereni": [{"label": "posun šuplíků", "param": "suplik_posun"}]}
        t["zive"] = [{"op": "posun", "ix": sorted(int(i) for i in box), "k": 1.0}]                     # zive tazeni: box, pricky a spojky se hybou spolu (presne - viz test)
        tahy.append(t)
    return {"jednotky": "mm; GLB: X hloubka (dozadu), Y nahoru, Z šířka (doprava)", "deska": {"pocatek": [X0, y_hore, Z0], "hloubka": round(D, 1), "sirka": round(W, 1)}, "casti": casti, "tahy": tahy}


# ---------------------------------------------------------------------------------------------------------------------
# vyrobni vypis (role dilu, montazni postup, oddil nohou)
# ---------------------------------------------------------------------------------------------------------------------
_NOHA_POPIS = {"stojka": "svislý jekl", "plech": "plechová patka", "profil": "vnitřní profil 35×35", "patka": "záslepka vnitřního profilu"}
_JM = {"pred": "přední", "zad": "zadní"}


def role(klic):
    """(kategorie, citelny popis) dilu SSE stolu podle klice generatoru (r["klice"][i]); viz S.role_dilu."""
    t = klic[1]
    if t == "deska":
        return "deska", "pracovní deska"
    if t == "polic":
        return "deska", "spodní police"
    if t == "podelnik":
        return "pricka", f"{_JM[klic[2]]} podélník (nese pracovní desku)"
    if t == "konec":
        return "konec", f"záslepka podélníku ({_JM[klic[2]]}, {'levý' if klic[3] == 'L' else 'pravý'} konec)"
    if t == "noha":
        n = klic[2]
        return "noha", f"noha SSE č. {n + 1} – " + (f"{_NOHA_POPIS[klic[3]]} ({_JM[klic[4]]})" if len(klic) > 4 else "jeklová spojnice")
    if t == "box":
        return "prislusenstvi", "šuplíkový box"
    if t == "box_pricka":
        return "pricka", f"příčka pod deskou držící šuplíky ({klic[2]})"
    if t == "box_spojka":
        return "spojka", "rohová spojka příčky šuplíků"
    return "dil", str(klic)


MONTAZNI_KROKY = {
    1: "Nařezat profily 40×40 podle řezného plánu (podélníky jsou o 10 mm kratší než deska – záslepky; řezy kolmé, odjehlit), jekly 40×40 a vnitřní profily 35×35 podle plánu nohou SSE; připravit desky a spojovací "
       "materiál. Nasunout hlavy šroubů do T-drážek podélníků PŘED montáží.",
    2: "Sestavit nohy SSE (2 ks, u širšího stolu 3 ks): svislé jekly spojit jeklovou spojnicí (její délka je hloubka stolu − 80 mm, 90 mm nad spodkem jeklu), k hornímu konci každého jeklu zevnitř přivařená plechová patka; "
       "do každého jeklu zespodu zasunout vnitřní profil 35×35 se záslepkou na podlaze (výšku nastavit v kroku 8).",
    3: "Přišroubovat podélníky k plechovým patkám nohou (vnější líc nohy 175 mm od konce desky, horní plocha podélníku v rovině horního konce jeklu) a nasadit záslepky na oba konce podélníků.",
    4: "Osadit rohové spojky na spoje příček šuplíkového boxu s předním podélníkem (jsou-li šuplíky).",
    5: "Položit pracovní desku na podélníky a přišroubovat (u stolu se střední nohou obě části desky, dělicí spára v ose střední nohy); zkontrolovat doléhání.",
    6: "Spodní police (je-li zvolena): položit desku (u střední nohy obě části) na jeklové spojnice nohou; police je o 20 mm užší než světlá hloubka mezi jekly.",
    7: "Šuplíkový box (je-li zvolen): dvě příčky mezi podélníky (přední konec se dvěma rohovými spojkami, zadní na čelo podélníku), na ně zavěsit box.",
    8: "Výška stolu: posunout jekly nohou po vnitřních profilech na zvolenou výšku horní plochy desky (vnitřní profil zůstává v jeklu aspoň 100 mm) a zajistit; stůl postavit a vyrovnat.",
}


def krok_montaze(klic):
    """Cislo kroku montazniho postupu (MONTAZNI_KROKY) pro dil SSE stolu."""
    return {"deska": 5, "podelnik": 3, "konec": 3, "noha": 2, "polic": 6, "box": 7, "box_pricka": 7, "box_spojka": 4}.get(klic[1], 2)


def vypis_noh(r):
    """Oddil vyrobniho vypisu: nohy SSE (rezny plan jeklu a vnitrnich profilu, plechy, zaslepky, vyska) - dily nohou nejsou karty katalogu."""
    dily, klice, sse = r["dily"], [tuple(k) for k in r["klice"]], r["sse"]
    n = len(sse["nohy"])
    jekly = [i for i, k in enumerate(klice) if k[:2] == ("sse", "noha") and dily[i]["part_id"] == S.SSE_JEKL_PART]
    profily = [i for i, k in enumerate(klice) if k[:2] == ("sse", "noha") and dily[i]["part_id"] == S.SSE_PROFIL_PART]
    plechy = [i for i, k in enumerate(klice) if k[:2] == ("sse", "noha") and dily[i]["part_id"] == S.SSE_PLECH_PART]
    zasl = [i for i, k in enumerate(klice) if k[:2] == ("sse", "noha") and dily[i]["part_id"] == S.SSE_PATKA_PART]
    rezny = []
    for nazev, ids in (("svislý jekl 40×40 (noha)", [i for i in jekly if len(klice[i]) > 4]), ("jeklová spojnice 40×40", [i for i in jekly if len(klice[i]) == 4]), ("vnitřní profil 35×35", profily)):
        for L in sorted({round(1000.0 * dily[i]["scale"][1], 1) for i in ids}, reverse=True):
            q = [i for i in ids if round(1000.0 * dily[i]["scale"][1], 1) == L]
            rezny.append({"nazev": nazev, "delka_mm": L, "pocet": len(q), "id_dilu": q})
    return {"nazev": "nohy SSE – jeklové nohy s vnitřním profilem 35×35 (výška stolu 700–1000 mm)", "pocet_noh": n, "spojnice_mm": round(sse["spojnice"], 1), "rezny_plan": rezny,
            "plechove_patky": {"rozmer": "150×40×6", "pocet": len(plechy), "id_dilu": plechy}, "zaslepky_vnitrnich_profilu": {"pocet": len(zasl), "id_dilu": zasl},
            "barva": S.NAVLEK_BARVA, "povrch": S.NAVLEK_POVRCH, "spodek_jeklu_od_podlahy_mm": round(sse["y_jeklu"], 1), "zasun_profilu_v_jeklu_mm": round(sse["preklad_profilu"], 1),
            "mezera_mezi_nohami_mm": round(sse["mezera_mezi_nohami"], 1),
            "pozn": f"Každá noha = 2 svislé jekly 40×40×{S.SSE_STOJKA:g} mm (stěna 2 mm, {S.NAVLEK_POVRCH}), jeklová spojnice {sse['spojnice']:.0f} mm, 2 plechové patky 150×40×6 a 2 vnitřní profily 35×35×{S.SSE_PROFIL_DELKA:g} mm "
                    f"se záslepkou; vnitřní profil zasahuje do jeklu {sse['preklad_profilu']:.0f} mm (nejméně {S.SSE_PREKRYTI_MIN:g} mm). Cena nohy je pravidlo stolu (cena_noha_sse_400 / 1100)."}
