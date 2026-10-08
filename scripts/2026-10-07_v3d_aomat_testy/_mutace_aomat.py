#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mutacni kontrola AO po komponentech + automatickeho ukladani (viewer 1.16.0, kontrola.html, nabidka-online.html; bot10, 2026-10-07).
Rozbije jednu vec v kopii viewer3d.js / kontrola.html / nabidka-online.html (docasny soubor, podstrceny testu pres WEB_OVERRIDE) a overi, ze test selze. "!!!" = mutaci test nechytil (exit 1).
Nic se nezapisuje do repa. Nejdriv bezi ZAKLAD bez mutace (musi projit, jinak by "chyceno" nic neznamenalo).
  VIEWER_JS=<viewer3d.js> KONTROLA_HTML=<kontrola.html> NABIDKA_HTML=<nabidka-online.html> WEB_DIR=<prekryv webapp> python3 _mutace_aomat.py [cast]
Vychozi: soubory z ziveho repa. [cast] = jen mutace, jejichz nazev obsahuje retezec (napr. 'alu')."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = {
    "viewer": (os.environ.get("VIEWER_JS") or os.path.join(REPO, "webapp/js/v3d/viewer3d.js"), "/js/v3d/viewer3d.js"),
    "kontrola": (os.environ.get("KONTROLA_HTML") or os.path.join(REPO, "webapp/kontrola.html"), "/kontrola.html"),
    "nabidka": (os.environ.get("NABIDKA_HTML") or os.path.join(REPO, "webapp/nabidka-online.html"), "/nabidka-online.html"),
}
TEXT = {k: open(v[0], encoding="utf-8").read() for k, v in SRC.items()}
FILTR = sys.argv[1] if len(sys.argv) > 1 else ""

# (nazev, soubor, kotva, nahrada, oddily testu)
MUTACE = [
    # ---- viewer: vahovy pruchod, slozeni, vahy materialu
    ("viewer: vahovy pruchod se nekresli", "viewer", "var useW = aoWeightPass(res, meshesVis, skip);", "var useW = false;", "A"),
    ("viewer: slozeni ignoruje vahu (uK bez w)", "viewer", "uK * w * (1.0 - v)", "uK * (1.0 - v)", "A"),
    ("viewer: slozeni vahu nepouzije (uUseW = 0)", "viewer", "C.uUseW.value = useW ? 1 : 0;", "C.uUseW.value = 0;", "A"),
    ("viewer: materialy meshu se po vahovem pruchodu nevrati", "viewer", "for (var k = 0; k < list.length; k++) list[k][0].material = orig[k];", "", "A"),
    ("viewer: vaha hliniku se nenastavi", "viewer", "mat.userData.__v3dAoW = st.aluCfg ? st.aluCfg.ao : 1;", "", "A"),
    ("viewer: vaha barvy se bere z lesku misto z ao", "viewer", "var aw = cfg ? cfg.ao[srgbHexOfBase(b)] : undefined;", "var aw = cfg ? cfg.gloss[srgbHexOfBase(b)] : undefined;", "A"),
    ("viewer: strop vahy 20 misto 2", "viewer", "var AO_MAT_MAX = 2;", "var AO_MAT_MAX = 20;", "A"),
    ("viewer: vaha 1 se v konfiguraci neodstrani", "viewer", "if (g !== 1) { ao[s] = g; an++; }", "{ ao[s] = g; an++; }", "A"),
    ("viewer: kodovani vahy bez 0,5 (vaha 1 = 2)", "viewer", "gl_FragColor = vec4(vec3(uW * 0.5), 1.0);", "gl_FragColor = vec4(vec3(uW), 1.0);", "A"),
    ("viewer: materialPalette bez ao", "viewer", "ao: (st.matCfg && st.matCfg.ao[hex] !== undefined) ? st.matCfg.ao[hex] : 1, rough:", "rough:", "A"),
    ("viewer: aluConfig.ao se ignoruje", "viewer", "ao = clampNum(c.ao, 1, 0, AO_MAT_MAX);", "ao = 1;", "A"),
    ("viewer: getMatConfig bez ao", "viewer", ", ao: JSON.parse(JSON.stringify(st.matCfg.ao)) }", " }", "AB"),
    ("viewer: pocitadlo vahovych pruchodu se nezvysuje", "viewer", "aoStat.wPasses++;", "", "A"),
    ("viewer: pruchod kresli i kdyz jsou vsechny vahy 1", "viewer", "if (!any) return false;", "if (false) return false;", "A"),
    ("viewer: vaha hliniku se pocita i mimo AO (aluInfo.aoW vzdy 1)", "viewer", "aoW: typeof m.userData.__v3dAoW === 'number' ? m.userData.__v3dAoW : 1 }; }); },\n      aoValues", "aoW: 1 }; }); },\n      aoValues", "A"),
    # ---- kontrola.html: posuvniky, automaticke ukladani, seznam mimo scenu
    ("kontrola: zmeny barev / lesku / AO se samy neukladaji", "kontrola", "api.setMatConfig(c);\n      vzhledObnovInfo();\n      vzhledAutoPlan();", "api.setMatConfig(c);\n      vzhledObnovInfo();", "C"),
    ("kontrola: ukladani bez cekani (debounce 0)", "kontrola", "const VZHLED_AUTO_MS = 900;", "const VZHLED_AUTO_MS = 0;", "C"),
    ("kontrola: ukladani na pozadi uklada i HDRI a volby z rohu 3D", "kontrola", "vzhledUloz(vzhledTelo(v, false), { keepalive: !!naKonci })", "vzhledUloz(vzhledTelo(v, true, null), { keepalive: !!naKonci })", "C"),
    ("kontrola: ukladani nejde po jednom (dve PUT naraz)", "kontrola", "const p = vzhledAutoChain.then(fn);\n      vzhledAutoChain = p.catch(() => {});\n      return p;", "return Promise.resolve().then(fn);", "C"),
    ("kontrola: chyba ukladani se nehlasi", "kontrola", 'vzhledAutoHlaska("Neuloženo: " + ((e && e.message) || e), "err");', 'vzhledAutoHlaska("", "");', "C"),
    ("kontrola: PUT vzdy nese ao_mat (i pro server bez nej)", "kontrola", "if (vzhledApiAoMat) telo.ao_mat =", "telo.ao_mat =", "D"),
    ("kontrola: PUT nese alu_cfg.ao i pro server bez nej", "kontrola", "(vzhledApiAoMat ? ac : { refl: ac.refl, rough: ac.rough })", "ac", "D"),
    ("kontrola: pri zavreni stranky se cekajici zmena neposle", "kontrola", 'window.addEventListener("pagehide", () => { if (vzhledAutoDirty && api) vzhledAutoUloz(true); });', "", "C"),
    ("kontrola: seznam mimo scenu ukazuje i barvy ze sceny", "kontrola", ".filter((h) => !vScene.has(h)).sort();", ".sort();", "E"),
    ("kontrola: Vratit vychozi neruší cekajici ukladani", "kontrola", 'clearTimeout(vzhledAutoTimer); vzhledAutoDirty = false; vzhledAutoHlaska("");\n      vzhledVRade(() => vzhledUloz(null))', "vzhledVRade(() => vzhledUloz(null))", "C"),
    ("kontrola: posuvnik Hlinik - AO zustava aktivni pri vypnutem AO", "kontrola", "vzhledAluAo.disabled = vyp;", "", "B"),
    ("kontrola: ulozene ao_mat se pri otevreni nepredava prohlizeci", "kontrola", "ao: vzhledUlozeny.ao_mat || {} }", "ao: {} }", "F"),
    ("kontrola: ao_mat ze serveru se zahodi", "kontrola", "ao_mat: obj(j && j.ao_mat),", "ao_mat: null,", "F"),
    ("kontrola: posuvnik Hlinik - AO neposila ao do prohlizece", "kontrola", ", ao: (+vzhledAluAo.value) / 100 });", " });", "B"),
    ("kontrola: posuvnik AO u barvy zapisuje do lesku", "kontrola", "cfg.ao = cfg.ao || {}; if (v === 1) delete cfg.ao[p.hex]; else cfg.ao[p.hex] = v;", "cfg.gloss = cfg.gloss || {}; if (v === 1) delete cfg.gloss[p.hex]; else cfg.gloss[p.hex] = v;", "B"),
    ("kontrola: posuvniky AO u barev se pri vypnutem AO nevypnou", "kontrola", 'vzhledPal.querySelectorAll("[data-ao]").forEach((x) => { x.disabled = vyp;', 'vzhledPal.querySelectorAll("[data-ao]").forEach((x) => { x.disabled = false;', "B"),
    ("kontrola: tlacitko Ulozit neruší cekajici ukladani", "kontrola", "          clearTimeout(vzhledAutoTimer);\n          return vzhledVRade(() => vzhledUloz(vzhledTelo(v, true, cfg)))", "          return vzhledVRade(() => vzhledUloz(vzhledTelo(v, true, cfg)))", "C"),
    ("kontrola: ukladani se spusti i bez zmeny (pri otevreni okna)", "kontrola", "      vzhledObnovInfo();\n      vzhledTimer = setInterval(vzhledObnovInfo, 600);", "      vzhledObnovInfo(); vzhledAutoPlan();\n      vzhledTimer = setInterval(vzhledObnovInfo, 600);", "C"),
    ("kontrola: ?vzhled=1 okno neotevre", "kontrola", "if (vzhledOtevritSamo && !vzhledBtn.hidden) { vzhledOtevritSamo = false; if (vzhledPanel.hidden) vzhledOtevri(true); }", "", "G"),
    ("kontrola: okno se otevira vzdy (i bez ?vzhled=1)", "kontrola", "let vzhledOtevritSamo = /[?&]vzhled=1(?:&|$)/.test(location.search);", "let vzhledOtevritSamo = true;", "G"),
    # ---- stranka nabidky
    ("nabidka: ao_mat se viewer nepredava", "nabidka", 'if (j && j.ao_mat && typeof j.ao_mat === "object") mc.ao = j.ao_mat;', "", "H"),
]


def spust(oddily, soubor_key=None, text=None):
    """Bezi test; vraci (rc, vystup). oddily 'H' = harness_page.js scenar 9 (stranka nabidky)."""
    env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="mutace_aomat_") as d:
        ov = {}
        if soubor_key:
            cesta = os.path.join(d, "mutovany")
            open(cesta, "w", encoding="utf-8").write(text)
            ov[SRC[soubor_key][1]] = cesta
        if oddily == "H":
            env.update(H_ONLY="9", H_NO_TIMING="1", V3D_TEST_OUT=os.environ.get("V3D_TEST_OUT", "/tmp/v3d_testy"), VIEWER_JS=SRC["viewer"][0])
            env["V3D_PAGE_HTML"] = ov.get("/nabidka-online.html") or SRC["nabidka"][0]
            cmd = ["node", os.path.join(REPO, "scripts/2026-10-02_v3d_testy/harness_page.js")]
        else:
            env.update(ONLY=oddily, WEB_OVERRIDE=json.dumps(ov))
            cmd = ["node", os.path.join(HERE, "test_ao_mat.js")]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=1500)
        return r.returncode, r.stdout + r.stderr


vysl = []
print("== ZAKLAD (bez mutace, musi projit)")
for oddily in ("ABCDEF", "H"):
    rc, out = spust(oddily)
    print("   zaklad %-7s rc=%s" % (oddily, rc))
    if rc != 0:
        print(out[-2500:])
        print("ZAKLAD SELHAL - mutace nema smysl")
        sys.exit(2)
for nazev, soubor, kotva, nahrada, oddily in MUTACE:
    if FILTR and FILTR not in nazev:
        continue
    if TEXT[soubor].count(kotva) != 1:
        print("CHYBA PRIPRAVY '%s': kotva nalezena %d x" % (nazev, TEXT[soubor].count(kotva)))
        vysl.append((nazev, None))
        continue
    rc, out = spust(oddily, soubor, TEXT[soubor].replace(kotva, nahrada))
    vysl.append((nazev, rc))
    print(("chyceno " if rc != 0 else "!!! NECHYCENO ") + "| " + nazev + ("  [%s]" % oddily))
    sys.stdout.flush()
spatne = [n for n, rc in vysl if rc in (0, None)]
print("\n%d mutaci, chyceno %d, nechyceno/chyba pripravy %d" % (len(vysl), len(vysl) - len(spatne), len(spatne)))
sys.exit(1 if spatne else 0)
