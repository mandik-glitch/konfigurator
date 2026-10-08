#!/usr/bin/env python3
"""Mutacni kontrola testu stranky priccek (bot8, 2026-10-07): do KOPIE nabidka-online.html se vlozi zamerna chyba v logice sekce priccek (vyber setu, ceny, rozpoznani setu, miniatura, texty podle druhu,
skryto, zvyrazneni skupiny, vysunuti boxu, selhani pluginu / modelu, ulozeni, QR, prijeti ...) a test_page.js musi selhat. Kazda mutace bezi v ZKRACENE kopii testu jen s sekcemi, ktere ji maji chytit
(pole `sekce` u mutace; test se zkrati mechanicky podle hlavicek "// ==== X) ..." a bezi s FAILFAST = skonci pri prvni selhane kontrole), takze vsech ~60 mutaci trva radove desitky minut, ne hodiny.
Nejdriv se overi NEMUTOVANE zaklady: cely test_page.js a kazda pouzita zkracena sada sekci (musi projit - jinak by se mutace vyhodnotily spatne), potom mutace; vse paralelne po MAX.
Spusteni (z teto slozky; potreba hotova GLB: python3 /opt/konfigurator/scripts/2026-10-02_v3d_testy/build_karty.py 4921 4453, viz test_page.js):
    python3 mutace_page.py                          vsechny mutace (+ zaklady)
    python3 mutace_page.py qr_bez_pr hover_nezvyrazni   jen vybrane (+ zaklady jejich sekci)
    python3 mutace_page.py --suchy                  jen overi, ze kazda kotva v strance existuje prave 1x (nic nespusti)
    python3 mutace_page.py --bez-zakladu ...        bez overeni nemutovanych zakladu (rychlejsi, mene spolehlive)
Prostredi: NABIDKA_HTML (stranka k mutaci, vychozi <repo>/webapp/nabidka-online.html), PRICKY_REPO (koren repa, vychozi ../..), MAX (paralelne, vychozi 3), dale vse, co cte test_page.js (PRICKY_API,
V3D_TEST_OUT, PLUGIN_JS ...). Mutovane kopie a logy: docasna slozka (pri neuspechu se jeji cesta vypise, jinak se smaze). Konci kodem 0 jen kdyz zaklady prosly a jsou chyceny VSECHNY mutace."""
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("PRICKY_REPO") or os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.environ.get("NABIDKA_HTML") or os.path.join(REPO, "webapp", "nabidka-online.html")
TEST = os.path.join(HERE, "test_page.js")
OUT = tempfile.mkdtemp(prefix="pricky_page_mut_")
MAX = int(os.environ.get("MAX", "3"))
s0 = open(SRC, encoding="utf-8").read()

# (id, popis, old, new, sekce testu, ktere ji maji chytit): P pin, A bez priccek, B jadro, M sety / vlastni kombinace, C poradi, D qty / montaz / zaloha, E prijeti, F localStorage, G chyby / boxy bez 3D,
# H admin / XSS, I rozlozeni / navigace / tisk, J vzorec, L 1 skupina, U suplíky (v5), Z zvyrazneni, O vysunuti boxu, K bez chyb JS
M = [
    # ---- ceny, QR, prijeti, montaz
    ("qr_bez_pr", "QR platba bez ?pr=", '(prQ ? `&pr=${encodeURIComponent(prQ)}` : "")', '""', "B"),
    ("pricky_mimo_soucet", "pricky se nepricitaji k cene", 'const prickyNet = (typeof PRICKY !== "undefined" ? PRICKY.perKus() : 0) * qty;', "const prickyNet = 0;", "B"),
    ("pricky_bez_nasobeni_qty", "pricky se nenasobi poctem kusu", 'const prickyNet = (typeof PRICKY !== "undefined" ? PRICKY.perKus() : 0) * qty;', 'const prickyNet = (typeof PRICKY !== "undefined" ? PRICKY.perKus() : 0);', "D"),
    ("montaz_jen_ze_zbozi", "montaz % jen ze zbozi (bez priccek)", "const montazNet = montazNetFor(offer, itemsNet, p);", "const montazNet = montazNetFor(offer, goodsNet, p);", "D"),
    ("montaz_info_bez_priccek", "informace o montazi bez priccek", '(goodsNetAfterDiscount(offer, effectiveQty(p)) + (typeof PRICKY !== "undefined" ? PRICKY.perKus() : 0) * effectiveQty(p)) * pct / 100',
     "(goodsNetAfterDiscount(offer, effectiveQty(p))) * pct / 100", "D"),
    ("montaz_stitek_bez_priccek", "stitek tlacitka montaze bez priccek", 'const itemsNet = goodsNetAfterDiscount(offer, effectiveQty(orderPrefsState)) + (typeof PRICKY !== "undefined" ? PRICKY.perKus() : 0) * effectiveQty(orderPrefsState);',
     "const itemsNet = goodsNetAfterDiscount(offer, effectiveQty(orderPrefsState));", "D"),
    ("banner_bez_radku_priccek", "banner bez radku priccek", "      if (parts.prickyNet > 0) detailParts.push(`příčky bez DPH ${fmtCzk(parts.prickyNet)}`);\n", "", "B"),
    ("accept_bez_pricky", "prijeti bez pole pricky", '}, typeof PRICKY !== "undefined" && PRICKY.retezec() ? { pricky: PRICKY.retezec() } : null)),', "}, null)),", "E"),
    ("poradi_abecedne", "retezec razeny abecedne misto podle cisla boxu", ".sort((a, b) => cisloId(a) - cisloId(b) || (a < b ? -1 : 1))", ".sort()", "C"),
    ("zmena_neprekresli_qr", "zmena vyberu neprekresli QR", "if (currentOffer) { refreshTotalBanner(currentOffer); refreshPayQr(currentOffer); }", "if (currentOffer) { refreshTotalBanner(currentOffer); }", "B"),
    ("zmena_neprekresli_zalohu_a_montaz", "zmena vyberu neprekresli zalohu a stitek montaze", "      if (obnoveniVoleb) obnoveniVoleb();\n", "", "D"),
    ("tabulka_bez_radku", "cenova tabulka bez radku priccek", '      tb.textContent = "";\n      radky().forEach((r, i) => {', '      tb.textContent = "";\n      [].forEach((r, i) => {', "B"),
    ("paticka_bez_nasobku", "paticka bez nasobku pri vice kusech", 'if (qty > 1) ui.paticka.appendChild(el("div", "pr-note", "Při " + qty', 'if (false) ui.paticka.appendChild(el("div", "pr-note", "Při " + qty', "D"),
    ("odznak_prazdny", "odznak v zahlavi je prazdny", 'ui.odznak.textContent = ks > 0 ? ks + " ks · " + cenaTxt(net) : "";', 'ui.odznak.textContent = "";', "B"),
    # ---- vyber setu, rozpoznani, ulozeni
    ("aria_pressed_vzdy_false", "aktivni cip se neoznaci", 'b.setAttribute("aria-pressed", akt ? "true" : "false");', 'b.setAttribute("aria-pressed", "false");', "B"),
    ("rozpoznej_nepresna_shoda", "set se pozna i pri nepresne shode", "if (bs.every(({ b, i: ix }) => nBoxu(b) === pb[ix])) return sety[i].id;", "if (bs.every(({ b, i: ix }) => nBoxu(b) >= pb[ix])) return sety[i].id;", "B"),
    ("pouzij_set_uklada_nuly", "set uklada i nulove pocty", "if (n > 0) vyber[b.id] = n; else delete vyber[b.id];", "vyber[b.id] = n;", "F"),
    ("cena_setu_bez_poctu", "cena setu bez poctu pricek", "c += k * jednB(b); }); return { priccek: n, cena: zaokr(c) }; }", "c += jednB(b); }); return { priccek: n, cena: zaokr(c) }; }", "B"),
    ("souhrn_bez_stitku_vlastni", "souhrn bez stitku Vlastni kombinace", '(set === "vlastni" ? "Vlastní kombinace · " : "")', '""', "M"),
    ("cip_bez_poctu_pricek", "cip bez textu N pricek", 'if (priccek > 0) b.appendChild(el("span", "pr-pocet", priccek', 'if (false) b.appendChild(el("span", "pr-pocet", priccek', "B"),
    ("sety_bez_kontroly_po_boxech", "nabizi se i set s neplatnym po_boxech", 'return Array.isArray(pb) && pb.length === g.boxy.length && pb.every(n => Number.isInteger(n) && n >= 0) && bs.every(({ b, i }) => pb[i] <= maxB(b));', "return Array.isArray(pb);", "G"),
    ("localstorage_bez_validace", "ulozeny vyber se nevaliduje", "Object.assign(vyber, ocisti(j.boxy));", "Object.assign(vyber, j.boxy);", "F"),
    ("localstorage_n_nad_max", "ulozeny pocet nad max se bere", "n < 1 || n > maxB(b)) return;", "n < 1) return;", "F"),
    # ---- selhani, boxy a skupiny bez 3D, zamek, mount
    ("selhani_nezahodi_vyber", "pri selhani se vyber nezahodi", "      Object.keys(vyber).forEach(id => delete vyber[id]);\n      pr = null;", "      pr = null;", "G"),
    ("po_modelu_ignoruje_ready", "skupiny, ktere plugin ve 3D nenasel, se nabizeji", "skupinyUi = skupinyVse.filter(g => (boxyVse.get(g.id) || []).some(({ b }) => hotove.has(b.id)));", "skupinyUi = skupinyVse.slice();", "G"),
    ("po_modelu_boxy_bez_filtru", "boxy, ktere plugin ve 3D nenasel, se pocitaji", "skupinyUi.forEach(g => boxySk.set(g.id, (boxyVse.get(g.id) || []).filter(({ b }) => hotove.has(b.id))));", "skupinyUi.forEach(g => boxySk.set(g.id, boxyVse.get(g.id) || []));", "G"),
    ("zamknout_nic_nedela", "po prijeti se vyber nezamkne", "function zamknout() { zamceno = true; osvez(); }", "function zamknout() { }", "E"),
    ("cip_neni_disabled_pri_zamku", "po prijeti cipy zustanou aktivni", "b.disabled = zamceno;", "b.disabled = false;", "E"),
    ("bez_3d_modelu_bere_pricky", "sekce i pro nabidku bez 3D modelu", 'blok = (offer && offer.has_3d_model && offer.source !== "configurator" && platnyBlok(offer.pricky)) ? offer.pricky : null;', 'blok = (offer && offer.source !== "configurator" && platnyBlok(offer.pricky)) ? offer.pricky : null;', "G"),
    ("plugin_se_nepredava_mountu", "plugin se nepredava V3D.mount", "}, pluginyPricky.length ? { plugins: pluginyPricky } : null));", "}, null));", "B"),
    ("panel_i_bez_priccek", "panel v DOM i bez offer.pricky", 'function panelHtml() { return blok ? `<aside', 'function panelHtml() { return true ? `<aside', "A"),
    ("pin_neodpovida", "pin pluginu neodpovida souboru", "pricky-multibox.js?v=", "pricky-multibox.js?v=0000000000&x=", "P"),
    # ---- XSS, navigace, tisk
    ("xss_innerhtml_tabulka", "text v tabulce jako HTML", 'if (cls) c.className = cls; c.textContent = txt; return c; };', 'if (cls) c.className = cls; c.innerHTML = txt; return c; };', "H"),
    ("xss_innerhtml_panel", "texty panelu jako HTML", "if (text != null) e.textContent = text; return e; };\n    const svgEl", "if (text != null) e.innerHTML = text; return e; };\n    const svgEl", "H"),
    ("kolecko_v_panelu_listuje", "kolecko v panelu listuje stranky", 'if (e.target.closest("#viewer3dContainer") || e.target.closest("#prickyPanel")) return;', 'if (e.target.closest("#viewer3dContainer")) return;', "I"),
    ("sipky_v_panelu_listuji", "sipky v panelu listuji stranky", '    if (e.target && e.target.closest && e.target.closest("#prickyPanel")) return;', "", "I"),
    ("tah_prstem_v_panelu_listuje", "tah prstem v panelu listuje stranky", 'if (markupTool || (e.target && e.target.closest && e.target.closest("#prickyPanel"))) {', "if (markupTool) {", "I"),
    ("tisk_panel_zustane", "panel se tiskne", ".xsec-panel, #viewer3dContainer, #viewer3dHint, #bomList, #prickyPanel,", ".xsec-panel, #viewer3dContainer, #viewer3dHint, #bomList,", "I"),
    # ---- miniatura, nadpis sekce, slova, skryto (v5)
    ("miniatura_bez_lemu", "miniatura nikdy nekresli tmavy lem", "if (d.lem > 0) svg.appendChild(", "if (false) svg.appendChild(", "U"),
    ("miniatura_lem_vzdy", "miniatura kresli lem i u supliku (lem 0)", "if (d.lem > 0) svg.appendChild(", "if (true) svg.appendChild(", "U"),
    ("miniatura_pomer_pevny", "pomer stran miniatury nezavisi na L:W", "Math.max(0.3, Math.min(0.8, d.W / d.L))", "0.47", "U"),
    ("miniatura_cary_pevne_L", "pozice car pocita z pevne delky 395", "pozice.push(num(dk.s[0]) / d.L)", "pozice.push(num(dk.s[0]) / 395)", "U"),
    ("miniatura_spatny_pocet_car", "miniatura kresli o pricku vic", "t.pocty.find(p => p && p.n === bx.n)", "t.pocty.find(p => p && p.n === Math.min(bx.n + 1, t.max))", "B"),
    ("titulek_vzdy_multibox", "nadpis sekce je vzdy Pricky do multiboxu", 'return d.has("suplik") ? (d.has("box") ? "Příčky do multiboxů a šuplíků" : "Příčky do šuplíků") : "Příčky do multiboxů";', 'return "Příčky do multiboxů";', "U"),
    ("titulek_oboji_jen_supliky", "u smisene nabidky nadpis jen suplíky", 'd.has("box") ? "Příčky do multiboxů a šuplíků" : "Příčky do šuplíků"', '"Příčky do šuplíků"', "U"),
    ("aria_label_neaktualizovan", "aria-label panelu se po filtraci skupin neaktualizuje", '      panel.setAttribute("aria-label", titulek());', "", "U"),
    ("slovo_suplik_chybi", "u supliku se pise box / boxu", 'const slovoBoxu = (g, n) => (druhSk(g) === "suplik" ? plural(n, "šuplík", "šuplíky", "šuplíků") : plural(n, "box", "boxy", "boxů"));', 'const slovoBoxu = (g, n) => plural(n, "box", "boxy", "boxů");', "U"),
    ("druh_ignoruje_typ", "druh skupiny se nepozna", 'const d = (t && typeof t.druh === "string") ? t.druh : (g.k === "suplik" ? "suplik" : "box");', 'const d = "box";', "U"),
    ("skryto_stitek_chybi", "skryta skupina nema stitek", "if (g.skryto === true) {", "if (false) {", "U"),
    ("skryto_stitek_vzdy", "stitek skryto u vsech skupin", "if (g.skryto === true) {", "if (true) {", "U"),
    # ---- v4.1: zadny radek Vsechny, zvyrazneni skupiny ve 3D
    ("vse_radek_zpet", "radek Vsechny se znovu objevi", 'ui.paticka = el("div", "pr-foot");', 'body.appendChild(el("section", "pr-card pr-all")); ui.paticka = el("div", "pr-foot");', "B"),
    ("bez_zvyrazneni_po_kliku", "po kliknuti na set se skupina nezvyrazni", "      hlDrzet(gid);                              // skupina zustane ve 3D zvyraznena ~3 s (dotyk nema hover)\n", "", "Z"),
    ("zvyrazneni_navzdy", "zvyrazneni po kliknuti nikdy nevyprsi", "hl.timer = setTimeout(() => { hl.drz = null; hlAkt(); }, HL_DRZENI_MS);", "hl.timer = null;", "Z"),
    ("zvyrazneni_kratke", "zvyrazneni po kliknuti vyprsi za 0,3 s", "HL_DRZENI_MS = 3000", "HL_DRZENI_MS = 300", "Z"),
    ("hover_nezvyrazni", "najeti mysi na kartu skupinu nezvyrazni", '        card.addEventListener("pointerenter", () => hlNad(g.id));\n', "", "BZ"),
    ("hover_neodzvyrazni", "odjeti mysi zvyrazneni nezrusi", '        card.addEventListener("pointerleave", () => hlNad(null));\n', "", "BZ"),
    ("dotyk_nezvyrazni", "po pusteni prstu se zvyrazneni nedrzi", '        card.addEventListener("pointerup", prstPusten);\n        card.addEventListener("pointercancel", prstPusten);\n', "", "Z"),
    ("fokus_nezvyrazni", "zaostreni klavesnici skupinu nezvyrazni", "          if (viditelne) hlFokus(g.id);\n", "", "Z"),
    ("mysi_fokus_drzi_zvyrazneni", "zaostreny cip po kliknuti mysi drzi zvyrazneni navzdy", 'try { viditelne = !!(e.target && e.target.matches && e.target.matches(":focus-visible")); } catch (x) { viditelne = true; }', "viditelne = true;", "Z"),
    ("jina_karta_neprebije_drzeni", "najeti na jinou kartu neprebije drzeni po kliknuti", "function hlNad(gid) { hl.mys = gid; if (gid) { hl.drz = null; clearTimeout(hl.timer); } hlAkt(); }", "function hlNad(gid) { hl.mys = gid; hlAkt(); }", "Z"),
    # ---- v4.1: vysunuti boxu skupiny po vyberu setu
    ("otevreni_dir0", "viewer.play(id, 0) misto (id, 1)", "try { v.play(id, 1); }", "try { v.play(id, 0); }", "O"),
    ("otevreni_pri_bez", "vysunuti i pri Bez pricek", 'if (sid !== "bez") otevriSkupinu(gid);', "otevriSkupinu(gid);", "O"),
    ("otevreni_bez_odstupu", "boxy se vysunou naraz bez odstupu 150 ms", "if (i === 0) jdi(); else casovace.push(setTimeout(jdi, i * OTEVRENI_MS));", "jdi();", "O"),
    ("otevreni_jen_prvni", "vysune se jen prvni box", 'Array.from(new Set(ids.filter(id => typeof id === "string" && id))).forEach((id, i) => {', 'Array.from(new Set(ids.filter(id => typeof id === "string" && id))).slice(0, 1).forEach((id, i) => {', "O"),
    ("otevreni_pri_obnove", "vysunuti i pri obnove vyberu z ulozeni", "        pluginVolej(a => { a.clear(); if (Object.keys(vyber).length) predejVyber(a); });\n",
     "        pluginVolej(a => { a.clear(); if (Object.keys(vyber).length) predejVyber(a); });\n        skupinyUi.forEach(g => { if (rozpoznej(g) !== \"bez\") otevriSkupinu(g.id); });\n", "O"),
    ("otevreni_nerusi_casovace", "dalsi klik nezrusi rozdelana vysouvani", "      (otevTimery.get(gid) || []).forEach(clearTimeout);\n", "", "O"),
    ("otevreni_id_bez_filtru", "neplatna id pohybu se posilaji viewer", 'Array.from(new Set(ids.filter(id => typeof id === "string" && id))).forEach(', "Array.from(new Set(ids)).forEach(", "O"),
    ("otevreni_bez_dedup", "duplicitni id pohybu se vysunou vickrat", 'Array.from(new Set(ids.filter(id => typeof id === "string" && id))).forEach(', 'ids.filter(id => typeof id === "string" && id).forEach(', "O"),
    ("otevreni_play_bez_try", "vyjimka viewer.play shodi stranku", "const jdi = () => { try { v.play(id, 1); } catch (e) { /* vizualizace nesmi shodit stranku */ } };", "const jdi = () => { v.play(id, 1); };", "O"),
    ("otevreni_motionids_bez_try", "vyjimka api.motionIds shodi stranku", "try { ids = pr.api.motionIds(gid); } catch (e) { return; }", "ids = pr.api.motionIds(gid);", "O"),
    ("otevreni_bez_kontroly_pole", "api.motionIds vrati nesmysl a stranka spadne", "      if (!Array.isArray(ids)) return;\n", "", "O"),
    ("otevreni_nenapojen_viewer", "stranka nepredava viewer sekci priccek", "      PRICKY.nastavViewer(api);", "      ", "O"),
]


def sekce_testu(text):
    """rozdeli test_page.js na predehru, sekce (pismeno -> text) a doznivani"""
    radky = text.split("\n")
    hl = [(i, re.match(r"^  // ={10,} ([A-Z])\) ", l).group(1)) for i, l in enumerate(radky) if re.match(r"^  // ={10,} ([A-Z])\) ", l)]
    konec = next(i for i, l in enumerate(radky) if l.startswith("  const ok = vysl.filter(Boolean).length;"))
    predehra = "\n".join(radky[:hl[0][0]])
    sekce = {}
    for j, (i, pismeno) in enumerate(hl):
        sekce[pismeno] = "\n".join(radky[i:(hl[j + 1][0] if j + 1 < len(hl) else konec)])
    return predehra, sekce, "\n".join(radky[konec:])


T0 = open(TEST, encoding="utf-8").read()
PREDEHRA, SEKCE, DOZNIVANI = sekce_testu(T0)


def zkraceny_test(sekce):
    """cesta k testu jen s danymi sekcemi (spolu s harness_pricky.js a stub-pricky.js v jedne docasne slozce); "" = cely test_page.js"""
    if not sekce:
        return TEST
    d = os.path.join(OUT, "test_" + sekce)
    if not os.path.isdir(d):
        os.makedirs(d)
        for f in ("harness_pricky.js", "stub-pricky.js"):
            shutil.copy(os.path.join(HERE, f), os.path.join(d, f))
        chybi = [p for p in sekce if p not in SEKCE]
        assert not chybi, ("neznama sekce testu", chybi)
        open(os.path.join(d, "test_page.js"), "w", encoding="utf-8").write(PREDEHRA + "\n" + "\n".join(SEKCE[p] for p in sekce) + "\n" + DOZNIVANI)
    return os.path.join(d, "test_page.js")


def spust(nazev, html, sekce="", failfast=True):
    env = dict(os.environ, NABIDKA_HTML=html, PRICKY_REPO=REPO)
    env.pop("NABIDKA_BASE_HTML", None)                                                           # mutace bezi bez porovnani s puvodni verzi
    if failfast:
        env["FAILFAST"] = "1"
    else:
        env.pop("FAILFAST", None)
    test = zkraceny_test(sekce)
    log = os.path.join(OUT, nazev + ".log")
    with open(log, "w", encoding="utf-8") as f:
        rc = subprocess.run(["node", test], cwd=os.path.dirname(test), env=env, stdout=f, stderr=subprocess.STDOUT, timeout=1800).returncode
    radky = open(log, encoding="utf-8").read().split("\n")
    return nazev, rc, [l for l in radky if l.startswith("FAIL")], [l for l in radky if l.startswith("TEST SPADL")] + [l for l in radky if "Error" in l][:1]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    suchy, bez_zakladu = "--suchy" in sys.argv, "--bez-zakladu" in sys.argv
    seznam = [m for m in M if not args or m[0] in args]
    assert len({m[0] for m in M}) == len(M), "duplicitni id mutace"
    prace = []
    for nazev, popis, old, new, sekce in seznam:
        assert s0.count(old) == 1, ("kotva mutace musi byt ve strance prave jednou", nazev, s0.count(old))
        assert old != new
        p = os.path.join(OUT, nazev + ".html")
        open(p, "w", encoding="utf-8").write(s0.replace(old, new))
        prace.append((nazev, popis, p, sekce))
    print("mutaci: %d (kotvy v poradku)" % len(prace))
    if suchy:
        shutil.rmtree(OUT, ignore_errors=True)
        return
    zaklady = [("_zaklad_cely", "")] + [("_zaklad_" + s, s) for s in sorted({m[3] for m in prace})]
    nesrovnalosti = 0
    if not bez_zakladu:
        with concurrent.futures.ThreadPoolExecutor(MAX) as ex:
            for nazev, rc, selhalo, spadl in ex.map(lambda z: spust(z[0], SRC, z[1], failfast=False), zaklady):
                ok = rc == 0
                print("ZAKLAD %-22s %s" % (nazev, "projde" if ok else "SELHAL rc=%d %s %s" % (rc, [x[:90] for x in selhalo[:3]], spadl[:1])))
                nesrovnalosti += 0 if ok else 1
        if nesrovnalosti:
            sys.exit("nemutovany zaklad musi projit - mutace nelze vyhodnotit (logy: %s)" % OUT)
    nechyceno, padem = [], []

    def beh(a):
        """mutace bez selhane kontroly (jen pad / timeout testu) se pusti znovu: pad pri zatizeni neni chyceni; opakovany pad se hlasi zvlast (chyceno padem)"""
        nazev, rc, selhalo, spadl = spust(a[0], a[2], a[3])
        if rc != 0 and not selhalo:
            nazev, rc, selhalo, spadl = spust(a[0] + "_znovu", a[2], a[3])
        return nazev, rc, selhalo, spadl

    with concurrent.futures.ThreadPoolExecutor(MAX) as ex:
        for (nazev, popis, p, sekce), (n2, rc, selhalo, spadl) in zip(prace, ex.map(beh, prace)):
            chyceno = rc != 0
            kdo = (selhalo[0][5:75] if selhalo else ("PAD TESTU: " + (spadl[0][:70] if spadl else "rc=%d" % rc)))
            print("%-34s %-8s %s" % (nazev, "CHYCENO" if chyceno else "NECHYCENO", kdo if chyceno else popis))
            if not chyceno:
                nechyceno.append(nazev)
            elif not selhalo:
                padem.append(nazev)
    print("\nchyceno %d z %d mutaci" % (len(prace) - len(nechyceno), len(prace)))
    if padem:
        print("z toho jen padem testu (zadna kontrola nevypsala FAIL - zkontrolovat v lozich): ", ", ".join(padem))
    if nechyceno:
        print("NECHYCENO:", ", ".join(nechyceno), "(logy a mutovane kopie: %s)" % OUT)
        sys.exit(1)
    shutil.rmtree(OUT, ignore_errors=True)


main()
