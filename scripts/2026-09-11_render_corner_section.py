#!/usr/bin/env python3
"""Vykresli 2D technicke rezy rohu (zaslepka na sestave id=58) - vstup
je segmenty z 2026-09-11_corner_zaslepka_section.js (rezy ze ZIVEHO
stavu, zadny vlastni rig). mm mrizka + koty (Robertovo zavazne pravidlo
pro schvalovani umisteni dilu)."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

DATA = json.load(open("/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/corner58_sections.json"))

COLORS = {
    "vodorovny_profil": "#2f6690",
    "svisla_noha": "#2f9e5c",
    "uhelnikova_spojka": "#b8721f",
    "zaslepka": "#c23b3b",
}
LABELS = {
    "vodorovny_profil": "vodorovný profil (Object_7)",
    "svisla_noha": "svislá noha (Object_7)",
    "uhelnikova_spojka": "úhelníková spojka (product_3045)",
    "zaslepka": "záslepka (product_3071)",
}


def draw_view(view_key, title, out_path, dim_lines, xlim=None, ylim=None):
    v = DATA[view_key]
    fig, ax = plt.subplots(figsize=(9, 8.8))
    for label, segs in v["segs"].items():
        color = COLORS[label]
        for (x1, y1, x2, y2) in segs:
            ax.add_line(Line2D([x1, x2], [y1, y2], color=color, linewidth=1.1))
    # mm mrizka po 10mm
    if xlim and ylim:
        xmin, xmax = xlim
        ymin, ymax = ylim
    else:
        all_x = [x for segs in v["segs"].values() for (x1, y1, x2, y2) in segs for x in (x1, x2)]
        all_y = [y for segs in v["segs"].values() for (x1, y1, x2, y2) in segs for y in (y1, y2)]
        xmin, xmax = min(all_x) - 20, max(all_x) + 20
        ymin, ymax = min(all_y) - 20, max(all_y) + 20
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    if True:
        import numpy as np
        for gx in np.arange(round(xmin / 10) * 10, xmax, 10):
            ax.axvline(gx, color="#dddddd", linewidth=0.4, zorder=0)
        for gy in np.arange(round(ymin / 10) * 10, ymax, 10):
            ax.axhline(gy, color="#dddddd", linewidth=0.4, zorder=0)
    ax.set_aspect("equal")
    ax.set_xlabel(v["xLabel"])
    ax.set_ylabel(v["yLabel"])
    ax.set_title(title, fontsize=11)
    legend_handles = [Line2D([0], [0], color=COLORS[k], lw=2, label=LABELS[k]) for k in COLORS]
    ax.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8, framealpha=0.9)

    for (x1, y1, x2, y2, text, offset) in dim_lines:
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="<->", color="black", lw=0.9),
        )
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.annotate(text, xy=(mx, my), xytext=(mx + offset[0], my + offset[1]),
                     fontsize=8.5, ha="center", color="black",
                     bbox=dict(boxstyle="round,pad=0.2", fc="#fff8dc", ec="#999", lw=0.5))

    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    print("uloženo:", out_path)


# VIEW A (celni, rez rovinou Z=const): X = podel vodorovneho profilu, Y = vyska (podel nohy)
# kóty: konec vodorovneho profilu (x=-720.5) vs. vrchol nohy (y=922) vs. rozsah zaslepky
draw_view(
    "viewA",
    "POHLED A – čelní řez (Z = %.1f mm)\nsestava id=58 „Proace Compact 16-“, roh záslepky product_3071" % DATA["viewA"]["cutValue"],
    "/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/corner58_viewA.png",
    dim_lines=[
        (-720.5, 800, -720.5, 892, "konec vodorovného\nprofilu X=-720.5\n(dosedá na spojku)", (55, -10)),
        (-800, 922, -800, 925.0, "+3 mm\npřesah", (-18, 0)),
        (-691.5, 863, -691.5, 892, "úhelníková\nspojka", (35, 0)),
    ],
    xlim=(-820, -600), ylim=(830, 950),
)

# VIEW B (pudorys, rez rovinou Y=918): X x Z
draw_view(
    "viewB",
    "POHLED B – půdorys (Y = %.0f mm, těsně pod vrcholem nohy)\nsestava id=58, roh záslepky product_3071" % DATA["viewB"]["cutValue"],
    "/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/corner58_viewB.png",
    dim_lines=[],
)

# VIEW C (uvnitr nohy, 0.3mm za spolecnou hranici s profilem): Z x Y
draw_view(
    "viewC",
    "POHLED C – příčný řez UVNITŘ NOHY (X = %.1f mm, 0,3 mm za hranicí s profilem)\nsestava id=58 – skutečná stěna nohy + záslepka v tomto místě" % DATA["viewC"]["cutValue"],
    "/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/corner58_viewC.png",
    dim_lines=[],
    xlim=(-1690, -1630), ylim=(850, 950),
)

# VIEW D (uvnitr profilu, 0.3mm pred jeho koncem): Z x Y
draw_view(
    "viewD",
    "POHLED D – příčný řez UVNITŘ PROFILU (X = %.1f mm, 0,3 mm před jeho koncem)\nsestava id=58 – skutečný dutý průřez konce vodorovného profilu" % DATA["viewD"]["cutValue"],
    "/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/corner58_viewD.png",
    dim_lines=[],
    xlim=(-1690, -1630), ylim=(850, 950),
)
