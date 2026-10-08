#!/usr/bin/env python3
"""Mutace UI RUCNICH POLOZEK (bot8, 2026-10-06): kazda umyslna chyba v webapp/admin/js/crm-nabidky.js (editor v adminu) nebo webapp/nabidka-online.html (verejna stranka) MUSI shodit
prislusny prohlizecovy test (CHYCENA = dobre). Kandidat = kopie souboru s jednou zmenou (CRM_NABIDKY_JS / NABIDKA_HTML), zivy soubor se nemeni. Po 4 paralelne.
  python3 mutace_rucni_polozky_ui.py [nazev_mutace ...]"""
import concurrent.futures
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ADMIN_JS = open(os.path.join(REPO, "webapp/admin/js/crm-nabidky.js"), encoding="utf-8").read()
STRANKA = open(os.path.join(REPO, "webapp/nabidka-online.html"), encoding="utf-8").read()

# (nazev, "admin"|"stranka", puvodni text (prave 1x), nahrada)
MUTACE = [
    ("a01_bez_priznaku", "admin", 'offerEditManualCfg = data.rucni_polozky && typeof data.rucni_polozky === "object" ? data.rucni_polozky : null;', "offerEditManualCfg = { max: 20, obrazky_max: 2 };"),
    ("a02_rucni_v_tabulce", "admin", 'offerEditItems.map((it, idx) => it.manual ? "" : `', 'offerEditItems.map((it, idx) => false ? "" : `'),
    ("a03_total_cena", "admin", "x.it.total = Math.round(x.it.qty * x.it.unit_price);", "x.it.total = x.it.unit_price;"),
    ("a04_ulozeni_pri_nahravani", "admin", "if (offerEditUploads > 0) {", "if (false) {"),
    ("a05_bez_zmenseni", "admin", "if (file.size <= 1500 * 1024) return resolve(fr.result);", "if (true) return resolve(fr.result);"),
    ("a06_bez_kontroly_typu", "admin", "if (!/^image\\/(png|jpeg)$/.test(file.type)) return reject(", "if (false) return reject("),
    ("a07_html_v_popisu", "admin", 'if (!html) return "";\n  const doc', 'return String(html || "");\n  const doc'),
    ("a08_dlouhy_nazev", "admin", 'name: String(p.name || "").slice(0, 200), dim: "", qty: 1,', 'name: String(p.name || ""), dim: "", qty: 1,'),
    ("a09_strop_hledani", "admin", 'document.getElementById("offerEditManualSearch").disabled = nTotal >= max;', 'document.getElementById("offerEditManualSearch").disabled = false;'),
    ("a10_strop_text", "admin", 'document.getElementById("btnOfferEditManualText").disabled = nTotal >= max;', 'document.getElementById("btnOfferEditManualText").disabled = false;'),
    ("a11_sipka_nahoru", "admin", "else if (c.contains(\"oe-mi-up\")) offerEditManualSwap(idx, -1);", "else if (c.contains(\"oe-mi-up\")) offerEditManualSwap(idx, 1);"),
    ("a12_mazani_bez_souctu", "admin", "offerEditItems.splice(idx, 1); renderOfferEditManual(); offerEditUpdateGrandTotal(); }", "offerEditItems.splice(idx, 1); renderOfferEditManual(); }"),
    ("a13_odebrani_obrazku", "admin", "x.it.manual.obrazky = (x.it.manual.obrazky || []).filter(k => k !== key);", "x.it.manual.obrazky = x.it.manual.obrazky;"),
    ("a14_model_bez_modelu", "admin", "cb.checked = false; cb.disabled = true; it.manual.model = false;", "cb.checked = false; it.manual.model = false;"),
    ("a15_min_delka_hledani", "admin", "if (q.length < 2) {", "if (q.length < 1) {"),
    ("a16_mnozstvi_text", "admin", 'value="${parseInt(it.qty, 10) || 1}"', 'value="${Number(it.qty) || 1}"'),
    ("a17_pridat_na_zacatek", "admin", 'offerEditItems.push({ name: "", dim: "", qty: 1, unit_price: 0, total: 0, manual: { typ: "text"', 'offerEditItems.unshift({ name: "", dim: "", qty: 1, unit_price: 0, total: 0, manual: { typ: "text"'),
    ("a18_cena_z_katalogu", "admin", "? Number(p.price_czk_placeholder) : 0;", "? 0 : 0;"),
    ("a19_model_vychozi", "admin", "model: !!p.glb_file },", "model: false },"),
    ("a20_chyba_uploadu", "admin", 'if (!r.ok) throw new Error(d.error || "Obrázek se nepodařilo nahrát.");', "if (!r.ok) { /* ignorovano */ }"),
    ("a21_klic_obrazku", "admin", "it.manual.obrazky.push(d.key);", "it.manual.obrazky.push(d.url);"),
    ("a22_debounce", "admin", "offerEditSearchTimer = setTimeout(offerEditCatalogSearch, 250);", "offerEditCatalogSearch();"),
    ("a23_mnozstvi_pole_text", "admin", 'value="${Number.isFinite(parseFloat(it.qty)) ? parseFloat(it.qty) : ""}">`', 'value="${it.qty}">`'),
    ("a24_mnozstvi_bez_ks", "admin", "it.qty = (typeof it.qty === \"string\" && /ks\\s*$/i.test(it.qty)) ? `${n} ks` : n;", "it.qty = n;"),
    ("a26_atribut_bez_uvozovek", "admin", 'const offerEditAttr = s => escapeHtmlAdmin(s).replace(/"/g, "&quot;").replace(/\'/g, "&#39;");', "const offerEditAttr = s => escapeHtmlAdmin(s);"),
    ("p01_3d_hned", "stranka", 'if (typeof IntersectionObserver === "function") {', "if (false) {"),
    ("p02_karta_vzdy", "stranka", "return !!(m && typeof m === \"object\" && ((m.popis", "return !!(m && typeof m === \"object\" || ((m.popis"),
    ("p03_bez_hud_dock", "stranka", 'hudKoty: false, hudDock: "top", dims: 0,', "hudKoty: false, dims: 0,"),
    ("p04_html_v_popisu", "stranka", "escapeHtml(String(m.popis).trim())", "String(m.popis).trim()"),
    ("p05_html_v_nazvu", "stranka", '<span>${escapeHtml(it.name)}</span></figcaption>', "<span>${it.name}</span></figcaption>"),
    ("p06_vic_obrazku", "stranka", ".slice(0, 2).map(k =>\n        `<img", ".slice(0, 9).map(k =>\n        `<img"),
    ("p07_esc_zavira", "stranka", 'document.addEventListener("keydown", e => { if (e.key === "Escape") box.classList.remove("show"); });', ""),
    ("p08_zadny_odkaz", "stranka", 'const nameHtml = escapeHtml(it.name) + (mi ? ', 'const nameHtml = escapeHtml(it.name) + (false ? '),
    ("p09_model_url", "stranka", '/item-model/${encodeURIComponent(it.product_id)}', '/item-model/0'),
    ("p10_obrazek_url", "stranka", '/item-image/${encodeURIComponent(k)}" alt=', '/item-obrazek/${encodeURIComponent(k)}" alt='),
    ("p12_lightbox_klik", "stranka", 'box.addEventListener("click", () => box.classList.remove("show"));', ""),
    ("p13_karty_mimo_tabulku", "stranka", "${manualCardsHtml(offer, manualRows)}\n        <div class=\"total-banner\"", "<div class=\"total-banner\""),
]


def spust(m):
    nazev, cil, puvodni, nahrada = m
    zdroj = ADMIN_JS if cil == "admin" else STRANKA
    if zdroj.count(puvodni) != 1:
        return nazev, None, f"puvodni text se nenasel prave jednou ({zdroj.count(puvodni)}x)"
    d = tempfile.mkdtemp(prefix="mut_ui_rp_")
    cesta = os.path.join(d, "kandidat" + (".js" if cil == "admin" else ".html"))
    open(cesta, "w", encoding="utf-8").write(zdroj.replace(puvodni, nahrada))
    env = dict(os.environ)
    if cil == "admin":
        env["CRM_NABIDKY_JS"] = cesta
        test = "test_rucni_polozky_admin.js"
    else:
        env["NABIDKA_HTML"] = cesta
        test = "test_rucni_polozky_stranka.js"
    p = subprocess.run(["node", test], cwd=HERE, env=env, capture_output=True, text=True, timeout=900)
    return nazev, p.returncode, p.stdout.count("FAIL")


if __name__ == "__main__":
    vyber = set(sys.argv[1:])
    seznam = [m for m in MUTACE if not vyber or m[0] in vyber]
    necytene = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for nazev, rc, info in ex.map(spust, seznam):
            if rc is None:
                print(f"mutace {nazev}: CHYBA MUTACE - {info}")
                necytene.append(nazev)
                continue
            chycena = rc != 0
            print(f"mutace {nazev}: rc={rc} ({'CHYCENA' if chycena else 'NECHYCENA'})  {info} FAIL")
            if not chycena:
                necytene.append(nazev)
    print(f"\n==> {len(seznam) - len(necytene)}/{len(seznam)} mutaci chyceno" + (f"; NECHYCENE / VADNE: {', '.join(necytene)}" if necytene else " - VSECHNY CHYCENY"))
    sys.exit(1 if necytene else 0)
