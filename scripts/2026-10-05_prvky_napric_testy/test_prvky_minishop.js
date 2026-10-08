// PRVKY GENERATORU V MINI-SHOPU nad SKUTECNYMI daty (Robert 2026-10-05: "prvky napric generatory na vsech mistech ... minishopy"; bot16): produkty 1 / 2 / 3 = stul system 30 / 40 / 35 (SK obchod,
// bridge_miniweb.py: skutecny front-end + API + data, docasne kopie tabulek miniweb_*, ostre tabulky se nemeni). Overuje KOTY (prepinac v HUD v jazyce obchodu, koty z modelu), okno HLAVNI PROFIL
// a ukazku PRIPNI COKOLI podle dat produktu (profil_mm, groove_family) a registru /pripni-cokoli/texty.json: profil bez schvalene animace = okna nejsou. Doplnuje test_prvky_napric_misty.js (embed,
// interni stranky, mini-shop demo). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge_miniweb.py scripts/2026-10-05_prvky_napric_testy/test_prvky_minishop.js
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs"), path = require("path");
const BASE = process.env.BASE;
const DICT = JSON.parse(fs.readFileSync(path.join(process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp", "miniweb/i18n/sk.json"), "utf8"));
let bad = 0, total = 0; const ok = (c, tt, d) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${tt}${!c && d !== undefined ? " | " + (typeof d === "string" ? d : JSON.stringify(d)) : ""}`); };

function ocekavej(reg, profile) {                                         // stejne rozpoznani profilu jako PdcLayout.profileKey (aliasy v registru)
  const n = String(profile || "").toLowerCase().replace(/\s+/g, ""), profs = (reg && reg._profily) || {};
  const k = Object.keys(profs).find(x => x === n || (profs[x].aliasy || []).includes(n));
  if (!k || profs[k].zive === false) return null;
  const m = /^(\d{1,2})x\d{1,2}-d(\d{1,2})$/.exec(k);
  return m ? { drazka: String(profs[k].drazka_mm != null ? profs[k].drazka_mm : m[2]) } : null;
}

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const reg = await (await fetch(BASE + "/pripni-cokoli/texty.json")).json();
  await fetch(`${BASE}/__bridge/approve?products=1,2,3`);
  for (const id of [1, 2, 3]) {
    const pr = (await (await fetch(`${BASE}/api/miniweb/products/${id}`)).json()).product || {};
    const mm = pr.profil_mm, g1 = String(pr.groove_family || "").split(",")[0].trim(), o = mm ? ocekavej(reg, `${mm}x${mm}`) : null;
    const pfx = `[produkt ${id}, profil ${mm || "?"}]`;
    const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } }); const page = await ctx.newPage(), errs = [];
    page.on("pageerror", e => errs.push(e.message));
    page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text().slice(0, 160)); });
    await page.addInitScript(() => { window.__pdcDebug = true; });
    await page.goto(`${BASE}/miniweb/product.html?id=${id}`);
    await page.waitForSelector(".pdc-slot[data-slot=w] .pdc-num", { timeout: 120000 });
    await page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading; }, null, { polling: 400, timeout: 150000 });
    await page.waitForTimeout(2500);
    const att = await page.$(".mw-win-attach"); if (att) { await att.scrollIntoViewIfNeeded().catch(() => {}); await page.waitForSelector(".mw-win-attach .pct, .mw-win-attach[hidden]", { timeout: 120000 }).catch(() => {}); await page.waitForTimeout(2000); }
    const r = await page.evaluate(() => {
      const vis = (e) => !!e && !e.hidden && e.offsetParent !== null;
      const st = window.__pdcState.viewer.state(), seg = [...document.querySelectorAll('.v3d-hud button[data-grp="dims"]')];
      const prof = document.querySelector(".mw-win-profile"), at = document.querySelector(".mw-win-attach"), img = prof && prof.querySelector("img");
      return { hudKoty: st.hudKoty, dims: st.dims, popisky: [...document.querySelectorAll(".v3d-dim")].filter(e => e.offsetParent !== null).length, prepinac: seg.filter(vis).length,
        caption: seg.length ? (seg[0].closest(".v3d-seg").getAttribute("aria-label") || "") : "", profil: vis(prof), profilText: vis(prof) ? (prof.querySelector("p") || {}).textContent : null, obr: img ? img.naturalWidth : 0,
        attach: vis(at), dlazdice: !!(at && at.querySelector(".pct")) };
    });
    ok(r.hudKoty === true && r.dims === 1 && r.prepinac >= 2 && r.popisky >= 3, `${pfx} KOTY: prepinac v HUD a koty z modelu zapnute (${r.popisky} popisku)`, r);
    ok(r.caption === DICT["v3d.dims_cap"] && r.caption !== "Kóty", `${pfx} KOTY: popisek prepinace je v jazyce obchodu (SK): "${r.caption}"`, { caption: r.caption, slovnik: DICT["v3d.dims_cap"] });
    if (o) {
      const g = /^\d{1,2}$/.test(g1) ? g1 : o.drazka;
      ok(r.profil && r.obr > 0 && r.profilText === `Profil ${mm}×${mm} mm, drážka ${g} mm.`, `${pfx} HLAVNI PROFIL: okno se schematem a vetou "Profil ${mm}×${mm} mm, drážka ${g} mm."`, { p: r.profil, obr: r.obr, text: r.profilText });
      ok(r.attach && r.dlazdice, `${pfx} PRIPNI COKOLI: okno a nactena ukazka`, { a: r.attach, d: r.dlazdice });
    } else {
      ok(!r.profil && !r.attach, `${pfx} profil bez schvalene animace: okna Hlavni profil a Pripni cokoli se NEUKAZUJI`, { profil: r.profil, attach: r.attach, text: r.profilText });
    }
    ok(errs.length === 0, `${pfx} bez chyb JS`, errs.slice(0, 3));
    await ctx.close();
  }
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 20000))]);
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("SPADLO", e); process.exit(1); });
