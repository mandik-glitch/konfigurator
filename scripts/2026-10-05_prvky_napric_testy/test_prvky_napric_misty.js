// PRVKY GENERATORU NAPRIC MISTY (Robert 2026-10-05: "laskave zarid at jsou prvky napric generatory na vsech mistech: interni ve scene, minishopy, iframe na Logiman.cz"; bot16).
// Mista: vlozeny generator (/embed/stul.html?p=<karta> = iframe na logiman.cz), interni stranky Generator stolu 01-03 (stul-konfigurator*.html), mini-shop (demo produkt 9001 = system 30).
// Prvky: KOTY (prepinac v HUD + koty z modelu), okno HLAVNI PROFIL (schema pruzezu), okno PRIPNI COKOLI (ukazka). Pravidlo: co ma jedno misto, maji vsechna; zamerne KONTEXTOVE veci (cena a kosik,
// kusovnik, pravidla stolu, HDRI, popis, doprava, odznaky) se nesrovnavaji. Ocekavani se berou z registru /pripni-cokoli/texty.json (profil bez schvalene animace = okno nikde neni),
// ne z napevno zapsanych systemu: az pribude animace pro dalsi profil, test ji pozaduje na vsech mistech.
// SKUTECNA statika + skutecny modul voleb + skutecny viewer nad skutecnym kodem stolu (api/stul_shop.py) pres bridge.py (BRIDGE_CARDS=real: karty 4934 / 4955 / 4954, falesny zamestnanec).
// Spusteni (DB pres systemd-run), PID = fiktivni produkt mini-shopu:
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=BRIDGE_CARDS=real --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge.py scripts/2026-10-05_prvky_napric_testy/test_prvky_napric_misty.js 9001
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const KARTY = { 30: 4934, 35: 4955, 40: 4954 };
const STAFF = { 30: "/stul-konfigurator.html", 35: "/stul-konfigurator-35.html", 40: "/stul-konfigurator-40.html" };

// stejne rozpoznani profilu jako PdcLayout.profileKey / prvek Pripni cokoli (aliasy v registru): vrati { mm, drazka } nebo null (profil bez schvalene animace)
function ocekavej(reg, profile) {
  const n = String(profile || "").toLowerCase().replace(/\s+/g, ""), profs = (reg && reg._profily) || {};
  const k = Object.keys(profs).find(x => x === n || (profs[x].aliasy || []).includes(n));
  if (!k || profs[k].zive === false) return null;
  const m = /^(\d{1,2})x\d{1,2}-d(\d{1,2})$/.exec(k);
  return m ? { mm: m[1], drazka: String(profs[k].drazka_mm != null ? profs[k].drazka_mm : m[2]) } : null;
}

async function otevri(browser, m) {                                       // m: { nazev, url, w, mini }
  const ctx = await browser.newContext({ viewport: { width: m.w, height: 900 }, locale: "cs-CZ" });
  const page = await ctx.newPage(), errs = [];
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", x => { if (x.type() === "error" && !/Failed to load resource/.test(x.text())) errs.push("console: " + x.text().slice(0, 160)); });
  await page.addInitScript(() => { window.__pdcDebug = true; });
  if (m.mini) await page.route("**/miniweb/config.cs.json", async (route) => { const r = await route.fetch(); const j = await r.json(); j.configurator_product_id = Number(PID); await route.fulfill({ response: r, json: j }); });
  await page.goto(BASE + m.url, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".v3d-root canvas", { timeout: 150000 });
  await page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading; }, null, { polling: 400, timeout: 150000 });
  await page.waitForTimeout(2500);
  const att = await page.$(".mw-win-attach");                                // ukazka se nacita az po modelu a az je okno na obrazovce: posunout k ni a pockat na dlazdici (nebo na schovani okna)
  if (att) { await att.scrollIntoViewIfNeeded().catch(() => {}); await page.waitForSelector(".mw-win-attach .pct, .mw-win-attach[hidden]", { timeout: 120000 }).catch(() => {}); await page.waitForTimeout(2000); }
  return { ctx, page, errs };
}
const mereni = (page) => page.evaluate(() => {
  const vis = (e) => !!e && !e.hidden && e.offsetParent !== null;
  const st = window.__pdcState.viewer.state(), seg = [...document.querySelectorAll('.v3d-hud button[data-grp="dims"]')];
  const popisky = [...document.querySelectorAll(".v3d-dim")].filter(e => getComputedStyle(e).display !== "none" && e.offsetParent !== null).map(e => e.textContent.trim());
  const prof = document.querySelector(".mw-win-profile"), att = document.querySelector(".mw-win-attach"), img = prof && prof.querySelector("img");
  return {
    koty: { hudKoty: st.hudKoty, dims: st.dims, popisky: popisky, prepinac: seg.filter(vis).length, caption: seg.length ? (seg[0].closest(".v3d-seg").getAttribute("aria-label") || "") : "" },
    profil: { viditelne: vis(prof), text: vis(prof) ? (prof.querySelector("p") || {}).textContent : null, obr: img ? img.naturalWidth : 0 },
    attach: { viditelne: vis(att), dlazdice: !!(att && att.querySelector(".pct")), platno: !!(att && att.querySelector("canvas")) },
    docW: document.documentElement.scrollWidth, innerW: window.innerWidth
  };
});
const cisla = a => a.map(x => Number(String(x).replace(/[^\d]/g, ""))).sort((x, y) => x - y);

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const reg = await (await fetch(BASE + "/pripni-cokoli/texty.json")).json();
  const schema = {};
  for (const s of Object.keys(KARTY)) schema[s] = await (await fetch(`${BASE}/api/shop/products/${KARTY[s]}/configurator?lang=cs`)).json();
  const profil = {}; for (const s of Object.keys(KARTY)) profil[s] = schema[s].profile;
  t("S1 schema nese profil u kazdeho systemu (z nej se paruje okno Hlavni profil a ukazka): " + JSON.stringify(profil), Object.values(profil).every(p => /^\d{2}x\d{2}$/.test(p || "")), profil);
  const ocek = {}; for (const s of Object.keys(KARTY)) ocek[s] = ocekavej(reg, profil[s]);
  t("S2 aspon jeden system ma schvalenou animaci a schema profilu (jinak by test nic neoveroval): " + JSON.stringify(ocek), Object.values(ocek).some(Boolean), ocek);

  const out = {};                                                           // out[system][misto] = mereni
  const mista = [];
  for (const s of Object.keys(KARTY)) {
    mista.push({ s, nazev: "embed", url: `/embed/stul.html?p=${KARTY[s]}`, w: 1100 }, { s, nazev: "interni", url: STAFF[s], w: 1400 });
  }
  mista.push({ s: "30", nazev: "minishop", url: "/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=9001", w: 1300, mini: true });
  async function meriDvojice(pole) {
    return Promise.all(pole.map(async (m) => {
      const o = await otevri(browser, m); const r = await mereni(o.page);
      r.errs = o.errs; (out[m.s] = out[m.s] || {})[m.nazev] = r; await o.ctx.close();
    }));
  }
  for (let i = 0; i < mista.length; i += 2) await meriDvojice(mista.slice(i, i + 2));

  for (const s of Object.keys(KARTY)) {
    const o = ocek[s], M = out[s];
    for (const nazev of Object.keys(M)) {
      const r = M[nazev], pfx = `[${nazev} ${s}]`;
      t(`${pfx} KOTY: prepinac v HUD (hudKoty) a koty z modelu zapnute (uroven Rozmery, aspon 3 popisky)`, r.koty.hudKoty === true && r.koty.dims === 1 && r.koty.prepinac >= 2 && r.koty.popisky.length >= 3, r.koty);
      if (o) {
        t(`${pfx} HLAVNI PROFIL: okno je videt, ma schema (obrazek se nacetl) a vetu "Profil ${o.mm}×${o.mm} mm, drazka ${o.drazka} mm."`, r.profil.viditelne && r.profil.obr > 0 && r.profil.text === `Profil ${o.mm}×${o.mm} mm, drážka ${o.drazka} mm.`, r.profil);
        t(`${pfx} PRIPNI COKOLI: okno je videt a ukazka se nacetla (dlazdice + 3D platno)`, r.attach.viditelne && r.attach.dlazdice && r.attach.platno, r.attach);
      } else {
        t(`${pfx} profil ${profil[s]} nema schvalenou animaci: okna Hlavni profil a Pripni cokoli se NEUKAZUJI (zadna prazdna okna)`, !r.profil.viditelne && !r.attach.viditelne, { profil: r.profil, attach: r.attach });
      }
      t(`${pfx} bez chyb JS`, r.errs.length === 0, r.errs.slice(0, 3));
    }
    // SROVNANI MIST pro system: tytez prvky, tytez koty, tyz profil
    const jmena = Object.keys(M), ref = M[jmena[0]];
    t(`[system ${s}] mista se shoduji v sade prvku (koty / profil / pripni cokoli): ${jmena.join(" = ")}`, jmena.every(n => M[n].koty.prepinac >= 2 === ref.koty.prepinac >= 2 && M[n].profil.viditelne === ref.profil.viditelne && M[n].attach.viditelne === ref.attach.viditelne), jmena.map(n => ({ n, k: M[n].koty.prepinac, p: M[n].profil.viditelne, a: M[n].attach.viditelne })));
    t(`[system ${s}] koty jsou na vsech mistech STEJNE (tatez cisla): ${jmena.map(n => M[n].koty.popisky.length).join(" / ")} popisku`, jmena.every(n => JSON.stringify(cisla(M[n].koty.popisky)) === JSON.stringify(cisla(ref.koty.popisky))), jmena.map(n => ({ n, c: cisla(M[n].koty.popisky) })));
    t(`[system ${s}] okno Hlavni profil ma na vsech mistech stejny text`, jmena.every(n => M[n].profil.text === ref.profil.text), jmena.map(n => ({ n, t: M[n].profil.text })));
  }

  // ---- uzke okno (telefon, 360 px): prepinac Koty je, koty jsou po nacteni vypnute (maly nahled by zahltily); Hlavni profil a Pripni cokoli jsou v toku stranky; zadny vodorovny posun (zakaznicka mista)
  const uzke = [{ s: "30", nazev: "embed", url: `/embed/stul.html?p=${KARTY[30]}`, w: 360 }, { s: "30", nazev: "interni", url: STAFF[30], w: 360 }, { s: "30", nazev: "minishop", url: "/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=9001", w: 360, mini: true }];
  const U = {};
  for (let i = 0; i < uzke.length; i += 2) await Promise.all(uzke.slice(i, i + 2).map(async (m) => { const o = await otevri(browser, m); const r = await mereni(o.page); r.errs = o.errs; U[m.nazev] = r; await o.ctx.close(); }));
  for (const nazev of Object.keys(U)) {
    const r = U[nazev], pfx = `[${nazev} 30 telefon 360 px]`;
    t(`${pfx} KOTY: prepinac je v HUD a koty jsou po nacteni vypnute (dims 0, 0 popisku)`, r.koty.hudKoty === true && r.koty.dims === 0 && r.koty.prepinac >= 1 && r.koty.popisky.length === 0, r.koty);
    if (ocek[30]) {
      t(`${pfx} HLAVNI PROFIL a PRIPNI COKOLI: okna jsou ve strance`, r.profil.viditelne && r.attach.viditelne && r.attach.dlazdice, { p: r.profil, a: r.attach });
    }
    if (nazev !== "interni") t(`${pfx} bez vodorovneho posunu (sirka stranky ${r.docW} px)`, r.docW <= r.innerW + 1, { docW: r.docW, innerW: r.innerW });
    t(`${pfx} bez chyb JS`, r.errs.length === 0, r.errs.slice(0, 3));
  }
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 20000))]);
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("SPADLO", e); process.exit(1); });
