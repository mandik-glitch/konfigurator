"""ZASTUPNY dopravnik_konfigurator (bot5, 2026-10-07): spustitelna specifikace kontraktu pro api/dopravnik_konfigurator.py (bot8) a nahrada v testech dopravnik_shop.
Implementuje pravidla receptu docs/dopravniky_recept.json (v1, opraveno): valecku len // pitch, 2 bocni profily, nohy 4 do 3 m / 6 do 6 m (nejmene podle rozpeti 3 m), patka na nohu, H-ram (pricky na dvojici
noh + podelna len - 0,2 m + 4 uchyty na dvojici). Skutecny modul ma davat u parametru odvozenych ze SKU hotove karty STEJNE dily (stejnou cenu). Do api/ nepatri."""
import math

ROZSAH = {"len": (1000, 6000, 100), "pitch": (75, 300, 25), "h": (570, 870, 10)}
TYPY = ("alu", "knurl", "steel")
SIRKY_PODLE_TYPU = {"alu": (290, 440, 590, 790), "knurl": (290, 440, 590, 790), "steel": (290, 440, 590, 790, 990)}
NOHY = ("auto", 4, 6, 8)
RAMY = ("full", "cross", "none")
VALECEK = {"alu": ("3.009.01.50.", "Hliníkový váleček Ø50"), "knurl": ("3.009.03.50.", "Vroubkovaný hliníkový váleček Ø50"), "steel": ("3.009.02.51.", "Ocelový váleček Ø51")}
PROFIL = {"alu": ("1.2.00.023075.00", "Dopravníkový profil 23x75", "3.004.03.01", "Kovová noha 23x75 (teleskopická)"),
          "knurl": ("1.2.00.023075.00", "Dopravníkový profil 23x75", "3.004.03.01", "Kovová noha 23x75 (teleskopická)"),
          "steel": ("1.2.00.023127.00", "Dopravníkový profil 23x127", "3.004.02.01", "Kovová noha, malá stupňovaná (teleskopická)")}
PATKA = ("2.3.002.1050", "Vyrovnávací patka M10")
RAM = ("1.1.10.040040.02", "Hliníkový profil 40x40 Light S10", "3.006.240.021.180", "Spodní spojovací úchyt rámu")


class DopravnikChyba(Exception):
    pass


def _krok(v, mn, mx, st):
    v = min(max(v, mn), mx)
    return int(mn + round((v - mn) / st) * st)


def min_nohou(delka_mm):
    return 4 if delka_mm <= 3000 else 6


def sestav_dopravnik(rtype="alu", width=590, len=2000, pitch=150, h=800, legs="auto", frame="full", guide="none", guidetype="40"):      # noqa: A002 - jmena jako klice vyberu
    if rtype not in TYPY or frame not in RAMY or legs not in NOHY:
        raise DopravnikChyba("neplatna volba")
    upoz = []
    L = _krok(int(len), *ROZSAH["len"])
    if L != len:
        upoz.append({"id": "len_upravena", "slot": "len", "hodnota": L})
    pt = _krok(int(pitch), *ROZSAH["pitch"])
    if pt != pitch:
        upoz.append({"id": "pitch_upraven", "slot": "pitch", "hodnota": pt})
    hh = _krok(int(h), *ROZSAH["h"])
    if hh != h:
        upoz.append({"id": "h_upravena", "slot": "h", "hodnota": hh})
    sirky = SIRKY_PODLE_TYPU[rtype]
    W = int(width) if int(width) in sirky else min(sirky, key=lambda s: (abs(s - int(width)), s))
    if W != width:
        upoz.append({"id": "sirka_upravena", "slot": "width", "hodnota": W})
    nmin = min_nohou(L)
    nohy = nmin if legs == "auto" else int(legs)
    if nohy < nmin:
        nohy = nmin
        upoz.append({"id": "nohy_zvyseny", "slot": "legs", "hodnota": nmin})
    pary = nohy // 2
    prefix, nazev_v = VALECEK[rtype]
    sku_p, nazev_p, sku_n, nazev_n = PROFIL[rtype]
    dily = [{"sku": f"{prefix}{W}", "nazev": f"{nazev_v} délky {W} mm", "mnozstvi": float(L // pt), "jednotka": "ks"},
            {"sku": sku_p, "nazev": f"{nazev_p} (2 boční profily)", "mnozstvi": 2 * L / 1000.0, "jednotka": "m", "kusy": 2, "delka_mm": L},
            {"sku": sku_n, "nazev": nazev_n, "mnozstvi": float(nohy), "jednotka": "ks"},
            {"sku": PATKA[0], "nazev": PATKA[1], "mnozstvi": float(nohy), "jednotka": "ks"}]
    if frame != "none":
        dily.append({"sku": RAM[0], "nazev": f"{RAM[1]} – příčky H-rámu (šířka {W} mm)", "mnozstvi": pary * W / 1000.0, "jednotka": "m", "kusy": pary, "delka_mm": W})
        if frame == "full":
            dily.append({"sku": RAM[0], "nazev": f"{RAM[1]} – podélná příčka", "mnozstvi": max(L / 1000.0 - 0.2, 0.0), "jednotka": "m", "kusy": 1, "delka_mm": max(L - 200, 0)})
        dily.append({"sku": RAM[2], "nazev": RAM[3], "mnozstvi": float(pary * 4), "jednotka": "ks"})
    return {"parametry": {"rtype": rtype, "width": W, "len": L, "pitch": pt, "h": hh, "legs": nohy, "frame": frame, "guide": "none", "guidetype": "40"}, "dily": dily, "upozorneni": upoz}
