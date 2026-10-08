"""Vyrobni list stolu (bot8, 2026-10-03): citelna HTML stranka z vyrobni sestavy (stul_shop.vyrobni_sestava) - rezny plan profilu, desky s vyrezy
a polohami loziskovych jednotek (SVG vykres shora), prislusenstvi, spojovaci material, montazni postup a katalogovy kusovnik. Jen pro zamestnance
(routa /api/stul/vyrobni-list v stul_shop.py). Cista funkce, bez DB a Flasku (testovatelna).

Souradnice na vykresu: pracovni deska shora, PREDNI okraj dole; x = od predniho okraje, z = od leveho okraje (mm)."""
from html import escape as _e

_CSS = """
:root{color-scheme:light dark}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;margin:0 auto;max-width:980px;padding:16px;background:#fff;color:#1b1f24}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:26px 0 8px;border-bottom:1px solid #c9d1d9;padding-bottom:4px}
.sub{color:#57606a;font-size:12.5px;margin-bottom:10px}
table{border-collapse:collapse;width:100%;margin:6px 0}th,td{border:1px solid #d0d7de;padding:4px 8px;text-align:left;vertical-align:top;font-size:13px}
th{background:#f3f5f7}td.n,th.n{text-align:right;white-space:nowrap}
.note{background:#fff8e1;border:1px solid #f0d58a;padding:6px 10px;border-radius:6px;font-size:12.5px;margin:6px 0}
ol li{margin:5px 0}.ids{color:#6e7781;font-size:11.5px}
svg{max-width:100%;height:auto;border:1px solid #d0d7de;background:#fafbfc}
@media print{body{max-width:none;padding:0}h2{break-after:avoid}table,svg{break-inside:avoid}}
@media (prefers-color-scheme:dark){body{background:#13171c;color:#e6e8eb}th{background:#222831}th,td,svg,h2{border-color:#3a4150}svg{background:#1a1f26}.note{background:#3a3217;border-color:#6b5a1f}}
"""


def _cislo(v, nd=0):
    if v is None:
        return "–"
    return f"{v:,.{nd}f}".replace(",", " ")


def _svg_desky(d, jednotky=None, mrizka=None):
    """SVG pohled shora na desku (sirka_mm podel osy z doprava, hloubka_mm od predniho okraje nahoru) s vyrezy a polohami jednotek. Polohy jednotek jsou vuci CELE pracovni plose; u desky
    deleneho stolu (leva / prava cast) se prepocitaji na roh teto desky (`pocatek_mm`) a nakresli se jen ty, ktere v ni lezi."""
    sk, hl = float(d["sirka_mm"]), float(d["hloubka_mm"])
    px, pz = (d.get("pocatek_mm") or [0.0, 0.0])
    jednotky = [(x - px, z - pz) for x, z in (jednotky or []) if -1.0 <= x - px <= hl + 1.0 and -1.0 <= z - pz <= sk + 1.0]
    sc = min(860.0 / sk, 520.0 / hl)
    okraj = 46
    W, H = sk * sc + 2 * okraj, hl * sc + 2 * okraj
    out = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{_e(d["role"])}">',
           '<defs><pattern id="sr" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#ffffff"/>'
           '<line x1="0" y1="0" x2="0" y2="6" stroke="#9aa4ae" stroke-width="1.4"/></pattern></defs>']

    def X(z):
        return okraj + z * sc

    def Y(x):
        return okraj + (hl - x) * sc          # predni okraj dole
    out.append(f'<rect x="{X(0):.1f}" y="{Y(hl):.1f}" width="{sk * sc:.1f}" height="{hl * sc:.1f}" fill="#d9d2c2" stroke="#555" stroke-width="1.5"/>')
    for v in d.get("vyrezy") or []:
        z0, x0, w, h = v["od_leveho_okraje_mm"], v["od_predniho_okraje_mm"], v["sirka_mm"], v["hloubka_mm"]
        out.append(f'<rect x="{X(z0):.1f}" y="{Y(x0 + h):.1f}" width="{w * sc:.1f}" height="{h * sc:.1f}" fill="url(#sr)" stroke="#c0392b" stroke-width="1.6"/>')
        out.append(f'<text x="{X(z0 + w / 2):.1f}" y="{Y(x0 + h / 2):.1f}" text-anchor="middle" font-size="12" fill="#c0392b">výřez {v["n"]}: {w:.0f} × {h:.0f}</text>')
        out.append(f'<text x="{X(z0 + w / 2):.1f}" y="{Y(x0 + h / 2) + 14:.1f}" text-anchor="middle" font-size="10.5" fill="#6e7781">od předu {x0:.0f}, zleva {z0:.0f}</text>')
    r_j = max(1.6, 17.0 * sc)
    for x, z in jednotky or []:
        out.append(f'<circle cx="{X(z):.1f}" cy="{Y(x):.1f}" r="{r_j:.1f}" fill="#7f8c9a" stroke="#34495e" stroke-width="0.8"/>')
    out.append(f'<text x="{X(sk / 2):.1f}" y="{okraj - 18:.1f}" text-anchor="middle" font-size="12.5" fill="#444">šířka {sk:.0f} mm</text>')
    out.append(f'<text x="14" y="{Y(hl / 2):.1f}" text-anchor="middle" font-size="12.5" fill="#444" transform="rotate(-90 14 {Y(hl / 2):.1f})">hloubka {hl:.0f} mm</text>')
    out.append(f'<text x="{X(sk / 2):.1f}" y="{H - 12:.1f}" text-anchor="middle" font-size="11" fill="#6e7781">▼ přední okraj</text>')
    out.append("</svg>")
    return "".join(out)


_CISLO_GENERATORU = {30: "01", 40: "02", 35: "03", 41: "04", 45: "05"}          # cislo generatoru stolu podle systemu profilu (poradi vzniku)
_JMENO_SYSTEMU = {41: "– ergonomický stůl SSE"}                                  # SSE se viditelne nejmenuje „system 41“ (Robert 2026-10-08); 41 je jen vnitrni klic


def html_list(s):
    """Vyrobni list (HTML retezec) ze sestavy ze stul_shop.vyrobni_sestava / stul_shop._sestava_z_gen."""
    v, par = s["vypis"], s["parametry"]
    system = int(v.get("system") or par.get("system") or 30)                              # system profilu (30 | 35 | 40): generator stolu 01 = system 30, 02 = system 40, 03 = system 35
    pn = str(v.get("profil_nazev") or "profil 30×30").replace("profil ", "")              # "30×30" / "40×40"
    rozmer = " × ".join(f"{par[k]:.0f}" for k in ("sirka", "hloubka", "vyska"))
    h = [f'<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">'
         f'<title>Výrobní list {_e(s["kod"])}</title><style>{_CSS}</style></head><body>',
         f'<h1>Výrobní list – Generátor stolu {_CISLO_GENERATORU.get(system, "01")} {_JMENO_SYSTEMU.get(system, f"systém {system}")} · {_e(s["kod"])}</h1>',
         f'<div class="sub">Šířka × hloubka × výška desky: <b>{rozmer} mm</b> · verze pravidel {_e(s["rules_version"])} · hash {_e(s["hash"])} · počet dílů {len(s["dily"])}'
         + (f' · hmotnost (neúplná) {_cislo(s.get("hmotnost_kg"), 1)} kg' if s.get("hmotnost_kg") is not None else "") + '</div>']
    # --- rezny plan
    h.append(f'<h2>1. Řezný plán profilů {pn} (řezy kolmé)</h2><table><tr><th class="n">Délka (mm)</th><th class="n">Počet</th><th>Použití (díly)</th></tr>')
    role = {i: r[1] for i, r in enumerate(v["role_dilu"])}
    for q in v["rezny_plan"]:
        pouziti = sorted({role[i] for i in q["id_dilu"]})
        h.append(f'<tr><td class="n">{_cislo(q["delka_mm"], 1)}</td><td class="n">{q["pocet"]}</td><td>{_e(", ".join(pouziti))}</td></tr>')
    celkem = sum(q["delka_mm"] * q["pocet"] for q in v["rezny_plan"])
    h.append(f'<tr><th>Celkem</th><th class="n">{sum(q["pocet"] for q in v["rezny_plan"])} ks</th><th>{celkem / 1000.0:.2f} m profilu</th></tr></table>')
    # --- navleky nohou (jekl 40x40x2, system 35): rezny plan jeklu
    nv = v.get("navlek")
    if nv:
        h.append('<h2>1b. Návleky nohou – jekl 40×40, stěna 2 mm (se záslepkou jeklu 40×40)</h2><table><tr><th class="n">Délka jeklu (mm)</th><th class="n">Počet</th><th>Poznámka</th></tr>')
        for q in nv["rezny_plan"]:
            h.append(f'<tr><td class="n">{_cislo(q["delka_mm"], 1)}</td><td class="n">{q["pocet"]}</td><td>na spodek nohy, záslepka jeklu dole (záslepek celkem {nv["zaslepky_jeklu"]} ks); {_e(nv.get("povrch", ""))}</td></tr>')
        h.append(f'</table><div class="note">{_e(nv["pozn"])}.</div>')
    # --- nohy SSE (system 41): rezny plan jeklu a vnitrnich profilu, plechy, zaslepky
    ns = v.get("nohy_sse")
    if ns:
        h.append(f'<h2>1b. Nohy SSE ({ns["pocet_noh"]} ks) – jekly 40×40, plechové patky, vnitřní profily 35×35</h2><table><tr><th>Díl</th><th class="n">Délka (mm)</th><th class="n">Počet</th></tr>')
        for q in ns["rezny_plan"]:
            h.append(f'<tr><td>{_e(q["nazev"])}</td><td class="n">{_cislo(q["delka_mm"], 1)}</td><td class="n">{q["pocet"]}</td></tr>')
        h.append(f'<tr><td>plechová patka {ns["plechove_patky"]["rozmer"]}</td><td class="n">–</td><td class="n">{ns["plechove_patky"]["pocet"]}</td></tr>'
                 f'<tr><td>záslepka vnitřního profilu 35×35</td><td class="n">–</td><td class="n">{ns["zaslepky_vnitrnich_profilu"]["pocet"]}</td></tr></table>'
                 f'<div class="note">{_e(ns["pozn"])} Mezera mezi nohami {ns["mezera_mezi_nohami_mm"]:.0f} mm, spodek jeklu {ns["spodek_jeklu_od_podlahy_mm"]:.0f} mm nad podlahou.</div>')
    # --- desky
    h.append('<h2>2. Desky (laminovaná dřevotříska 18 mm) – formáty, výřezy, otvory</h2>')
    jednotky = next((q for q in v["prislusenstvi"] if q["karta_id"] == 3025), None)
    h.append('<table><tr><th>Deska</th><th class="n">Šířka × hloubka (mm)</th><th class="n">Tloušťka</th><th>Výřezy (šířka × hloubka; od předního a levého okraje)</th></tr>')
    for d in v["desky"]:
        vyr = "; ".join(f'{x["n"]}: {x["sirka_mm"]:.0f} × {x["hloubka_mm"]:.0f}; {x["od_predniho_okraje_mm"]:.0f} / {x["od_leveho_okraje_mm"]:.0f}' + (" (přesahuje do druhé desky)" if x.get("pozn") else "") for x in d["vyrezy"]) or "–"
        h.append(f'<tr><td>{_e(d["role"])}</td><td class="n">{d["sirka_mm"]:.0f} × {d["hloubka_mm"]:.0f}</td><td class="n">{d["tloustka_mm"]:.0f} mm</td><td>{_e(vyr)}</td></tr>')
    deleny = any(str(d.get("deska_id") or "").endswith("_1") for d in v["desky"])
    h.append('</table><div class="note">Deska s výřezy je JEDEN kus (ve 3D modelu se kreslí po částech, ale vyřezává se z jednoho formátu). Okraje výřezů min. 30 mm od hrany desky a mezi výřezy.'
             + (((' Pracovní deska je u střední nohy / vestavěného rámu <b>dělená na dvě desky</b> (levá a pravá část při pohledu zepředu); každá se vejde do tabule laminodesky. '
                  'Pracovní deska u střední nohy navazuje bez mezery.') if (par.get("police") and not par.get("police_deska", True)) else
                 (' Pracovní deska a police jsou u střední nohy / vestavěného rámu <b>dělené na dvě desky</b> (levá a pravá část při pohledu zepředu); každá se vejde do tabule laminodesky. '
                  'Pracovní deska a police u střední nohy na sebe navazují bez mezery, spodní police u vestavěného rámu jsou kratší o mezeru pro svislý profil rámu.')) if deleny else '') + '</div>')
    for d in v["desky"]:
        if str(d.get("deska_id") or "").startswith("prac_") and (d["vyrezy"] or jednotky):
            h.append(f'<h3 style="font-size:14px;margin:14px 0 4px">{_e(d["role"][0].upper() + d["role"][1:])} shora (přední okraj dole)</h3>')
            h.append(_svg_desky(d, jednotky["polohy_stredu_mm"] if jednotky else None))
            if jednotky and not str(d.get("deska_id")).endswith("_1"):
                h.append(f'<div class="sub">Ložiskové jednotky: {jednotky["pocet"]} ks, rozteč {jednotky["rozteca_mm"]:.0f} mm, od okraje {jednotky["od_okraje_mm"]:.0f} mm '
                         f'({jednotky.get("radku")} × {jednotky.get("sloupcu")} v mřížce, vynecháno u výřezů, dělicí spáry nebo kolizí: {jednotky.get("vynechano")}). Vyvrtat otvory podle poloh níže.</div>')
    if jednotky:
        h.append('<details><summary>Polohy středů ložiskových jednotek (mm od předního okraje x, od levého okraje z celé pracovní plochy)</summary><div class="ids">'
                 + _e("; ".join(f"{x:.0f}/{z:.0f}" for x, z in jednotky["polohy_stredu_mm"])) + '</div></details>')
    # --- prislusenstvi
    h.append('<h2>3. Příslušenství a ostatní díly</h2><table><tr><th>Karta</th><th>Díl</th><th class="n">Počet</th></tr>')
    for q in v["prislusenstvi"]:
        h.append(f'<tr><td>{q["karta_id"]}</td><td>{_e(q["nazev"])}</td><td class="n">{q["pocet"]}</td></tr>')
    h.append(f'<tr><td>{v.get("spojka_karta") or 3158}</td><td>rohová spojka {pn}</td><td class="n">{v["rohove_spojky"]["pocet"]}</td></tr></table>')
    # --- spojovaci material
    sm = v["spojovaci_material"]
    h.append('<h2>4. Spoje a spojovací materiál</h2>')
    h.append(f'<p>Spojů profil–profil: <b>{sm["spoje_profil_profil"]}</b>, rohových spojek: <b>{sm["pocet_rohovych_spojek"]}</b>. {_e(sm["popis_spoje"])}.</p>')
    if sm.get("ke_spojkam"):
        h.append('<table><tr><th>Spojovací materiál ke spojkám (názvy z karet)</th><th>SKU</th><th class="n">Počet</th></tr>')
        for m in sm["ke_spojkam"]:
            h.append(f'<tr><td>{_e(m["nazev"])}</td><td>{_e(m["sku"] or "zatím neurčeno")}</td><td class="n">{m["mnozstvi"]}</td></tr>')
        h.append('</table>')
    if sm.get("typ_sroubu_a_matic") is None:
        h.append(f'<div class="note"><b>Doplnit:</b> {_e(sm["poznamka"])}.</div>')
    # --- montazni postup
    h.append(f'<h2>5. Montážní postup</h2><div class="note">{_e(v["montazni_postup_stav"])}.</div><ol>')
    for k in v["montazni_postup"]:
        h.append(f'<li>{_e(k["text"])} <span class="ids">({len(k["dily"])} dílů)</span></li>')
    h.append('</ol>')
    # --- katalogovy kusovnik
    kb = s.get("kusovnik_katalog")
    if kb:
        h.append('<h2>6. Kusovník z katalogu (SKU, ceny bez DPH)</h2><table><tr><th>Položka</th><th>Rozměr</th><th class="n">Počet</th><th class="n">Cena/ks</th><th class="n">Celkem</th></tr>')
        for b in kb:
            h.append(f'<tr><td>{_e(b["nazev"])}</td><td>{_e(b["rozmer"] or "–")}</td><td class="n">{b["mnozstvi"]}</td><td class="n">{_cislo(b["cena_ks_czk"])}</td><td class="n">{_cislo(b["celkem_czk"])}</td></tr>')
        pr = s.get("kusovnik_prace") or []
        if pr:                                          # rezy, pausal za profil, spoje, balne, zaokrouhleni: patri do celkove ceny, proto jsou videt (soucet radku = celkem)
            h.append('<tr><th colspan="5">Práce, spoje a balné</th></tr>')
            for b in pr:
                h.append(f'<tr><td>{_e(b["nazev"])}</td><td>–</td><td class="n">{b["mnozstvi"] if b["mnozstvi"] is not None else ""}</td><td class="n">{_cislo(b["cena_ks_czk"]) if b["cena_ks_czk"] is not None else ""}</td><td class="n">{_cislo(b["celkem_czk"])}</td></tr>')
        cs = s.get("cenovy_souhrn") or {}
        if cs:
            h.append(f'<tr><th colspan="4">Celkem bez DPH (včetně spojů, řezů a balného)</th><th class="n">{_cislo(s.get("cena_celkem_czk"))} Kč</th></tr>')
        h.append('</table>')
    h.append('</body></html>')
    return "".join(h)
