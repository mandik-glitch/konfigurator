#!/usr/bin/env python3
"""Zaplata api/stul_konfigurator.py: spodni police BEZ DESKY (parametr `police_deska`, vychozi True; Robert 2026-10-07: "spodni police nech ma volbu byt bez desky, jen profily / ram").
Kotvene nahrady (assert count == 1) proti ZIVEMU souboru. Pouziti: patch_konfigurator.py <vstup stul_konfigurator.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


# 1) vychozi hodnota parametru
s = nahrad(s, '''    "police": 1,                  # POCET spodnich polic (0 = zadna; vice ks rovnomerne po vysce, min. 100 mm volne mezi nimi)
''', '''    "police": 1,                  # POCET spodnich polic (0 = zadna; vice ks rovnomerne po vysce, min. 100 mm volne mezi nimi)
    "police_deska": True,         # Robert 2026-10-07: spodni police MAJI DESKU (laminodeska na rame); False = police BEZ DESKY, jen ram z profilu (odpadne deska, jeji deleni u opory a podpery pod ni);
                                  # plati pro vsechny spodni police (police pod vyrezem ma vlastni prepinac), bez spodnich polic a v systemu SSE nic nedela
''', "VYCHOZI")

# 2) normalizace: pravdivostni hodnota jako u ostatnich prepinacu
s = nahrad(s, '''    out["police"] = int(pol)
    sp = out["suplik_pocet"]
''', '''    out["police"] = int(pol)
    out["police_deska"] = bool(out["police_deska"])
    sp = out["suplik_pocet"]
''', "norm_police_deska")

# 3) ucinne parametry: bez spodnich polic je 'bez desky' bezpredmetne (jedna podoba parametru = jeden hash)
s = nahrad(s, '''    n_pol = min(p["police"], n_max)
    p["police"] = n_pol
''', '''    n_pol = min(p["police"], n_max)
    p["police"] = n_pol
    if not n_pol:
        p["police_deska"] = True                   # bez spodnich polic volba 'bez desky' nic nedela: ucinne parametry maji jednu podobu
''', "n_pol")

# 4) deska police v aktivnich dilech sablony
s = nahrad(s, '''    if not p["kolecka"]:
        a -= set(KOLECKA)
    a -= {PANEL_D, PANEL_H, ZRAIL_PANEL}''', '''    if not p.get("police_deska", True):
        a -= {DESKA_POLICE}                                           # Robert 2026-10-07: spodni police BEZ DESKY (jen ram z profilu): deska police, jeji deleni u opory a podpery pod ni odpadaji; spojky se vynechavaji
                                                                      # podle skutecnych dilu, takze se vrati rohove spojky, ktere dosud vynechala deska
    if not p["kolecka"]:
        a -= set(KOLECKA)
    a -= {PANEL_D, PANEL_H, ZRAIL_PANEL}''', "aktivni")

# 5) dotaz na staff API
s = nahrad(s, '''        elif k in PREPINACE or k in VYREZY_PREP or k in ("loz", "vzpery", "suplik_vlevo", "led_svetlo"):''',
           '''        elif k in PREPINACE or k in VYREZY_PREP or k in ("loz", "vzpery", "suplik_vlevo", "led_svetlo", "police_deska"):''', "dotaz")

# 6) pomocna funkce: patro ramu spodni police podle klice boční příčky police
s = nahrad(s, '''def ovladani_3d(r):
    """Popis ovladani ve 3D v systemu vysledku''', '''def _patro_ramu_police(klic):
    """Patro (0 = nejnizsi) ramu spodni police podle klice jeho BOCNI PRICKY police ((t, XRAIL_POL_L / P) = patro 0, (polic, k, ...) = patro k), jinak None. Slouzi police BEZ DESKY
    (Robert 2026-10-07; parametr police_deska): patro nema desku, takze ho ve 3D ovladani a v kotach zastupuje jeho ram (obe bocni pricky police)."""
    if not isinstance(klic, tuple):
        return None
    if klic in (("t", XRAIL_POL_L), ("t", XRAIL_POL_P)):
        return 0
    if len(klic) == 3 and klic[0] == "polic" and tuple(klic[2]) in (("t", XRAIL_POL_L), ("t", XRAIL_POL_P)):
        return int(klic[1])
    return None


def ovladani_3d(r):
    """Popis ovladani ve 3D v systemu vysledku''', "helper_patro")

# 7) 3D ovladani: patro police bez desky = jeho ram; polozka nabidky 'odebrat / vratit desku'
s = nahrad(s, '''    police_skup = [patra_p[k_] for k_ in sorted(patra_p)]                   # police od nejnizsi: seznam indexu dilu (1 nebo 2 desky) na patro
    for j, ids_p in enumerate(police_skup):
''', '''    if not p.get("police_deska", True) and p["police"] >= 1:                # police BEZ DESKY (Robert 2026-10-07): patro = jeho ramove profily (obe bocni pricky police), deska uz neni
        patra_p = {}
        for i in idx(lambda k, rl, d: _patro_ramu_police(k) is not None):
            patra_p.setdefault(_patro_ramu_police(klice_t[i]), []).append(i)
    police_skup = [patra_p[k_] for k_ in sorted(patra_p)]                   # police od nejnizsi: seznam indexu dilu (1 nebo 2 desky; bez desky 2 bocni pricky ramu) na patro
    for j, ids_p in enumerate(police_skup):
''', "police_skup")
s = nahrad(s, '''                pol("Odebrat spodní polici", {"police": p["police"] - 1}, None if p["police"] > 0 else "Žádná police není.")]
        casti.append({"id": f"police_{j + 1}", "label": "Spodní police" if len(police_skup) == 1 else f"Spodní police {j + 1}", "param": ["police"], "aabb": aabb(ids_p), "priorita": 2, "menu": menu})
''', '''                pol("Odebrat spodní polici", {"police": p["police"] - 1}, None if p["police"] > 0 else "Žádná police není.")]
        menu.append(pol(("Odebrat desku police" if p["police"] == 1 else "Odebrat desky všech polic") if p.get("police_deska", True)
                        else ("Vrátit desku police" if p["police"] == 1 else "Vrátit desky všech polic"), {"police_deska": not p.get("police_deska", True)}))          # Robert 2026-10-07: police bez desky (jen ram z profilu), plati pro vsechny spodni police
        casti.append({"id": f"police_{j + 1}", "label": "Spodní police" if len(police_skup) == 1 else f"Spodní police {j + 1}", "param": ["police", "police_deska"], "aabb": aabb(ids_p), "priorita": 2, "menu": menu})
''', "menu_police")

# 8) vyrobni vypis: montazni postup bez desek polic
s = nahrad(s, '''}


def vyrobni_vypis(r, nazvy_karet=None):''', '''}
# kroky montaze, ktere se u stolu se spodnimi policemi BEZ DESKY (parametr police_deska = False) lisi: police tvori jen ram z profilu, bez desky a bez podper pod ni (Robert 2026-10-07)
MONTAZNI_KROKY_BEZ_DESEK_POLIC = {
    2: "Sestavit levý a pravý boční rám: nohy, boční příčky rámu desky a police, svislé profily bočnic; střední nohy a střední příčky u širokého stolu (nebo vestavěný rám: dvě příčky v ose X a dva svislé profily "
       "mezi podélníky – podélníky zůstanou celé).",
    3: "Spojit boční rámy předními a zadními příčkami (rám pracovní desky a rám police); u stolu hlubšího než {prah} mm pod pracovní desku vložit podpěrné profily "
       "mezi čelní a zadní podélník (přední konec se dvěma rohovými spojkami, zadní konec na čelo podélníku); spodní police jsou BEZ DESEK – tvoří je jen rám z profilů "
       "(do rámu police se podpěrné profily nevkládají); dotáhnout imbusem přes otvory.",
}


def vyrobni_vypis(r, nazvy_karet=None):''', "montaz_texty")
s = nahrad(s, '''for n, t in (_sse().MONTAZNI_KROKY if sse_stul else MONTAZNI_KROKY).items()}''',
           '''for n, t in (_sse().MONTAZNI_KROKY if sse_stul else ({**MONTAZNI_KROKY, **MONTAZNI_KROKY_BEZ_DESEK_POLIC} if (p["police"] and not p.get("police_deska", True)) else MONTAZNI_KROKY)).items()}''', "montaz_kroky")

open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
