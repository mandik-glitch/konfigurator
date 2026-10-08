#!/usr/bin/env python3
"""Vykresli rez ze ziveho stavu (2026-08-20_live_section_cut.js vystup) pro
sestavu 337 (produkt 3942), 2 dvojice s 8mm nalezem. mm mrizka + koty."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

SP = "/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/rez_zaslepka_8mm"

PAIRS = [
    ("par1", "pricka-spodni-0", "vypln-bok-prepazka-a", "Nalez 1"),
    ("par2", "pricka-police-0", "vypln-bok-prepazka-b", "Nalez 2"),
]

for key, prof_role, dil_role, label in PAIRS:
    d = json.load(open(f"{SP}/{key}_sections.json"))
    fig, ax = plt.subplots(figsize=(9, 7.5))
    for seg in d["profil"]:
        ax.add_line(Line2D([seg[0], seg[2]], [seg[1], seg[3]], color="#2f6690", linewidth=1.3))
    for seg in d["dil"]:
        ax.add_line(Line2D([seg[0], seg[2]], [seg[1], seg[3]], color="#c23b3b", linewidth=1.3))

    all_x = [v for seg in d["profil"] + d["dil"] for v in (seg[0], seg[2])]
    all_y = [v for seg in d["profil"] + d["dil"] for v in (seg[1], seg[3])]
    xmin, xmax = min(all_x) - 10, max(all_x) + 10
    ymin, ymax = min(all_y) - 10, max(all_y) + 10
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    for gx in np.arange(round(xmin / 5) * 5, xmax, 5):
        ax.axvline(gx, color="#dddddd", linewidth=0.4, zorder=0)
    for gy in np.arange(round(ymin / 5) * 5, ymax, 5):
        ax.axhline(gy, color="#dddddd", linewidth=0.4, zorder=0)
    ax.set_aspect("equal")
    ax.set_xlabel("u [mm] (napříč, ⟂ na osu příčky)")
    ax.set_ylabel("v [mm] (hloubka drážky)")
    ax.set_title(
        f"{label}: {prof_role} (modrá) × {dil_role} (červená)\n"
        f"Produkt 3942 „Regál na euroboxy – Fiat Doblò L1H1 (do 2022)“, sestava id=337 (K-075-EB-30-C-0063-6-0)\n"
        f"Řez ze ŽIVÉHO stavu scény (2026-08-20_live_section_cut.js)", fontsize=10
    )
    legend_handles = [
        Line2D([0], [0], color="#2f6690", lw=2, label=prof_role + " (profil 30×30)"),
        Line2D([0], [0], color="#c23b3b", lw=2, label=dil_role + " (MDF deska 8mm)"),
    ]
    ax.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=8.5)

    # kota: presah desky do drazky v "v" smeru (hloubka) - navrh 7mm, tady 8mm
    dil_v = [v for seg in d["dil"] for v in (seg[1], seg[3])]
    prof_v = [v for seg in d["profil"] for v in (seg[1], seg[3])]
    v_presah_hi = min(max(dil_v), max(prof_v))
    v_presah_lo = max(min(dil_v), min(prof_v))
    xc = sum(xmin_i for xmin_i in [xmin]) + 5
    ax.annotate("", xy=(xmax - 8, v_presah_hi), xytext=(xmax - 8, v_presah_lo),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1.1))
    ax.annotate(f"8 mm\n(návrh: 7 mm)", xy=(xmax - 8, (v_presah_hi + v_presah_lo) / 2),
                xytext=(xmax - 60, (v_presah_hi + v_presah_lo) / 2),
                fontsize=9, ha="center", color="black",
                bbox=dict(boxstyle="round,pad=0.25", fc="#fff2cc", ec="#c9a227", lw=0.8))

    fig.tight_layout()
    out = f"{SP}/{key}_rez.png"
    fig.savefig(out, dpi=160)
    print("uloženo:", out)
