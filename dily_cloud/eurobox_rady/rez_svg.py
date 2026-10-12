"""Boční řez uchycením dolního a horního konce dráhy (v rámu sklonu, bez náklonu) -> obr_ukotveni.svg.
Je to HYPOTÉZA z rozměrů (GLB dílů nejsou k dispozici), ne měření. Spuštění: python3 -I rez_svg.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eurobox_rady as E  # noqa: E402


def panel(x0, y0, dolni, dr="5276"):
    sc = 2.3
    d = E.DILY[int(dr)]
    Lp, kapsa, zas = 86.29, 54.5, 54.5
    hp = (Lp - kapsa) / 2
    pod = 27.75
    out = []

    def X(s):
        return x0 + s * sc

    def Y(h):
        return y0 - h * sc

    def rect(s0, s1, h0, h1, fill, st="#333", extra=""):
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="%s" stroke-width="1" %s/>'
                   % (X(s0), Y(h1), (s1 - s0) * sc, (h1 - h0) * sc, fill, st, extra))

    def txt(s, h, t, anchor="start", size=11, fill="#222"):
        out.append('<text x="%.1f" y="%.1f" font-size="%d" text-anchor="%s" fill="%s">%s</text>' % (X(s), Y(h), size, anchor, fill, t))

    def line(s0, h0, s1, h1, col="#c00", w=1, dash=""):
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%s" %s/>' % (X(s0), Y(h0), X(s1), Y(h1), col, w, dash))

    if dolni:
        sp0, sin_ = -Lp, 0.0           # plech [-86.29, 0], otvor kapsy v 0, hák vlevo
        rect(0, 150, -d["pod"], 0, "#cfd6e0")     # dráha (náhrada)
        rect(sp0, sin_, -pod, 0, "#f3b7a6", "#a33")
        rect(-1.5, 0, 0, 28, "#d9482b", "#a33")  # zarážka
        rect(-zas, 0, -d["pod"], 0, "#b9c3d1", "#335", 'stroke-dasharray="4 2"')
        rect(17, 150, 0, 12, "#9ec5ff", "#25c", 'opacity=".8"')   # nožka boxu (odsazená 17 mm od čela)
        rect(0, 150, 12, 45, "#cfe1ff", "#25c", 'opacity=".6"')
        tcx = sp0 + hp
        txt(sp0, 62, "dolní konec: plech 5282", size=12)
        txt(-Lp, -52, "otvor kapsy = s 0 = čelo boxu, zarážka 28 mm", size=11)
        txt(sp0, -42, "hák", size=11)
    else:
        sin_ = 0.0
        sp1 = Lp
        rect(-150, 0, -d["pod"], 0, "#cfd6e0")
        rect(sin_, sp1, -pod, 0, "#a9d9b9", "#2a6")
        rect(-zas, 0, -d["pod"], 0, "#b9c3d1", "#335", 'stroke-dasharray="4 2"')
        rect(-150, -17, 0, 12, "#9ec5ff", "#25c", 'opacity=".8"')
        rect(-150, 0, 12, 45, "#cfe1ff", "#25c", 'opacity=".6"')
        tcx = sp1 - hp
        txt(-150, 62, "horní konec: plech 5281 (hák vpravo)", size=12)
        txt(-150, -52, "otvor kapsy (s 0 = plech začíná)", size=11)
        txt(sp1 - 5, -42, "hák", size=11, anchor="end")
    # trubka Ø28
    out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#6b7280" fill-opacity=".45" stroke="#222" stroke-width="1.5"/>' % (X(tcx), Y(-hp), 14 * sc))
    line(tcx - 22, -hp, tcx + 22, -hp, "#c00", 0.8, 'stroke-dasharray="3 2"')
    line(tcx, -hp - 22, tcx, -hp + 22, "#c00", 0.8, 'stroke-dasharray="3 2"')
    # kóty
    if dolni:
        out.append('<text x="%.1f" y="%.1f" font-size="10" fill="#c00">osa trubky: %.1f od vnějšího konce, %.1f pod horní plochou plechu</text>' % (X(-Lp), Y(-72), hp, hp))
        out.append('<text x="%.1f" y="%.1f" font-size="10" fill="#555">dráha zasunuta %.1f mm (čárkovaně), kapsa %.1f, hák %.2f</text>' % (X(-Lp), Y(-84), zas, kapsa, Lp - kapsa))
    else:
        out.append('<text x="%.1f" y="%.1f" font-size="10" fill="#c00">osa trubky: %.1f od vnějšího konce, %.1f pod horní plochou plechu</text>' % (X(-150), Y(-72), hp, hp))
    line(0, 0, 150 if dolni else -150, 0, "#25c", 0.8, 'stroke-dasharray="2 2"')
    return "\n".join(out)


def main():
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="440" viewBox="0 0 1180 440" font-family="system-ui,sans-serif">',
             '<rect width="1180" height="440" fill="#fff"/>',
             '<text x="14" y="22" font-size="14" font-weight="bold">Uchycení konců dráhy na trubku Ø28 (HYPOTÉZA z rozměrů, neověřeno na GLB)</text>',
             '<text x="14" y="40" font-size="11" fill="#555">boční řez v rovině sklonu; modrá = box (nožka 12 mm), šedá = dráha, plná čára horní plochy dráhy = rovina h=0</text>',
             panel(240, 225, True), panel(960, 225, False), '</svg>']
    open(os.path.join(HERE, "obr_ukotveni.svg"), "w", encoding="utf8").write("\n".join(parts))
    print("obr_ukotveni.svg")


if __name__ == "__main__":
    main()
