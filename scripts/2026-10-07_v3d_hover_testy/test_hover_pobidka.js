// 3D prohlizec online nabidky / kontrolni sceny: VYZVA KE KLIKNUTI pri najeti mysi na pohyblivy dil (viewer 1.13.0, opts.hoverHint; bot10, 2026-10-07;
// Robert: "nech se nabidne pri najeti mysi na dynamicky komponent pobidka kliknout intuitivne").
// SKUTECNA stranka kontrola.html (rezim=nabidka) + SKUTECNY viewer3d.js v prohlizeci proti falesnemu serveru (nic se nezapisuje); testovaci GLB = vyrob_glb.py
// (dvoustrane / trojstrane / bez_g z hotovych Vandr modelu). Druhe instance vieweru (jazyk, bez hoverHint, setModel, snimek, dispose) se mountuji do stranky pres V3D.mount.
// Kandidat pred nasazenim: WEB_DIR=<prekryv webapp> node test_hover_pobidka.js        (SHOTS=<slozka> uklada snimky vyzvy)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), cp = require("child_process");
const REPO = path.resolve(__dirname, "..", ".."), WEB = process.env.WEB_DIR || path.join(REPO, "webapp");
const SHOTS = process.env.SHOTS || fs.mkdtempSync(path.join(os.tmpdir(), "hover_shots_"));
fs.mkdirSync(SHOTS, { recursive: true });
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "hover_glb_"));
cp.execFileSync(path.join(REPO, "api/venv/bin/python3"), ["-B", path.join(REPO, "scripts/2026-10-06_v3d_rady_testy/vyrob_glb.py"), TMP], { stdio: ["ignore", "pipe", "inherit"] });
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream", ".svg": "image/svg+xml" };
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const J = (st, o) => { res.writeHead(st, { "Content-Type": "application/json" }); res.end(typeof o === "string" ? o : JSON.stringify(o)); };
  let m = /^\/api\/kontrola-scena\/vd\/(\d+)$/.exec(p);
  if (m) return J(200, { product: { id: +m[1], name: "Atrapa karta " + m[1] } });
  if (/^\/api\/kontrola-scena\/v3d\/[\d+]+\.glb$/.test(p)) { res.writeHead(200, { "Content-Type": "model/gltf-binary" }); return res.end(fs.readFileSync(path.join(TMP, "dvoustrane.glb"))); }
  m = /^\/glb\/(\w+)\.glb$/.exec(p);
  if (m && fs.existsSync(path.join(TMP, m[1] + ".glb"))) { res.writeHead(200, { "Content-Type": "model/gltf-binary" }); return res.end(fs.readFileSync(path.join(TMP, m[1] + ".glb"))); }
  if (p === "/api/public/v3d-vzhled") return J(200, { env: null, alu: null, ao: null, sat: null, barvy: null });
  if (p.startsWith("/api/")) return J(404, {});
  const f = path.join(WEB, p);
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nf"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 700) : ""}`); };
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  async function otevri(o) {
    o = o || {};
    const ctx = await browser.newContext(Object.assign({ viewport: { width: 1280, height: 900 }, locale: "cs-CZ" }, o));
    const page = await ctx.newPage(); const errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
    await page.goto(`${base}/kontrola.html?items=vd:4965+4964&rezim=nabidka`, { waitUntil: "load" });
    await page.waitForFunction(() => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText), null, { timeout: 120000 });
    await page.waitForFunction(() => window.__v3d && window.__v3d.state().ready, null, { timeout: 60000 });
    await page.waitForTimeout(1200);
    return { ctx, page, errs };
  }
  const chips = (page, root) => page.evaluate((root) => [...document.querySelectorAll((root || "") + " [data-motion]")].map((b) => {
    const row = b.closest(".v3d-chiprow"), mm = row ? /v3d-chiprow--(\w+)/.exec(row.className) : null;
    return { id: b.getAttribute("data-motion"), txt: b.textContent.trim(), side: mm ? mm[1] : null };
  }), root);
  const hov = (page) => page.evaluate(() => window.__v3d.hoverInfo());
  const pt = (page, id) => page.evaluate((id) => window.__v3d.pickPoint(id), id);
  const settle = (page) => page.waitForFunction(() => window.__v3d.idle(), null, { timeout: 30000 }).catch(() => {});
  const moveTo = async (page, x, y) => { await page.mouse.move(x, y, { steps: 4 }); await page.waitForTimeout(300); };     // 4 kroky: prvni se vyhodnoti, posledni musi dovyhodnotit casovac
  const otevrenych = (page, root) => page.evaluate((root) => document.querySelectorAll((root || "") + " [data-motion].is-open").length, root);
  const meanRGB = (page, x, y) => page.evaluate(([x, y]) => {         // prumerna barva 16x16 px kolem bodu (platno hned po vykresleni, ve stejnem ukolu)
    window.__v3d.renderNow();
    const cv = document.querySelector(".v3d-canvas"), r = cv.getBoundingClientRect(), k = cv.width / r.width;
    const c2 = document.createElement("canvas"); c2.width = cv.width; c2.height = cv.height;
    const g = c2.getContext("2d"); g.drawImage(cv, 0, 0);
    const px = Math.round((x - r.left) * k), py = Math.round((y - r.top) * k), R = Math.round(8 * k);
    const d = g.getImageData(Math.max(0, px - R), Math.max(0, py - R), 2 * R, 2 * R).data;
    let sr = 0, sg = 0, sb = 0, n = 0;
    for (let i = 0; i < d.length; i += 4) { sr += d[i]; sg += d[i + 1]; sb += d[i + 2]; n++; }
    return { r: sr / n, g: sg / n, b: sb / n };
  }, [x, y]);
  const najdiBod = (page, jeMotion) => page.evaluate((jeMotion) => {     // bod na platne: zasah do dilu BEZ pohybu (jeMotion=false) nebo mimo model (null)
    const r = document.querySelector(".v3d-canvas").getBoundingClientRect();
    const cv = document.querySelector(".v3d-canvas");
    for (let y = r.top + 24; y < r.bottom - 24; y += 14) for (let x = r.left + 24; x < r.right - 24; x += 14) {
      if (document.elementFromPoint(x, y) !== cv) continue;                  // pod prvkem HUD (tlacitka, cipy): mys by opustila platno
      const h = window.__v3d.pickInfo(x, y);
      if (jeMotion === false ? (h && !h.motion) : !h) return { x, y };
    }
    return null;
  }, jeMotion);
  const prvniZasazitelny = async (page, list) => { for (const x of list) { const p = await pt(page, x.id); if (p) return Object.assign({ p }, x); } return null; };
  const ONLY = process.env.H_ONLY || "ABCD";                 // podmnozina oddilu (A = A+B, C, D), napr. H_ONLY=D
  let c;

  if (ONLY.includes("A")) {
  console.log("\n## A) kontrolni scena, dvoustranna scena, mys (1280x900)");
  c = await otevri();
  const ch = await chips(c.page);
  t("A0 model ma pohyblive dily obou stran (cipy Leva / Prava)", ch.some((x) => x.side === "left") && ch.some((x) => x.side === "right"), ch.slice(0, 4));
  const L = await prvniZasazitelny(c.page, ch.filter((x) => x.side === "left"));
  const R = await prvniZasazitelny(c.page, ch.filter((x) => x.side === "right"));
  t("A0b pro levou i pravou stranu jde najit bod na obrazovce, kde klik zasahne pohyb", !!(L && R), { L, R });
  const h0 = await hov(c.page);
  t("A1 bez najeti: zadna vyzva ani podsviceni", !h0.on && h0.overlays === 0 && h0.id === null, h0);
  const vsechny = [];
  for (const x of ch) { const p = await pt(c.page, x.id); if (p) vsechny.push(Object.assign({ p }, x)); }
  const F = vsechny.filter((x) => x.id !== L.id).sort((a, b) => Math.hypot(b.p.x - L.p.x, b.p.y - L.p.y) - Math.hypot(a.p.x - L.p.x, a.p.y - L.p.y))[0];       // nejvzdalenejsi jiny pohyblivy dil na obrazovce
  t("A1b existuje jiny pohyblivy dil daleko od testovaneho (>= 150 px) pro kontrolu, ze se nepodsviti i on", !!F && Math.hypot(F.p.x - L.p.x, F.p.y - L.p.y) >= 150, { L: L.p, F: F && F.p });
  const base0 = await meanRGB(c.page, L.p.x, L.p.y), baseF = await meanRGB(c.page, F.p.x, F.p.y);
  await moveTo(c.page, L.p.x, L.p.y);
  let h = await hov(c.page);
  t("A2 najeti na dil leve strany: vyzva \"" + L.txt + " · Levá strana / Kliknutím otevřete\", dil podsvicen, kurzor ruka", h.on && h.id === L.id && h.name === L.txt + " · Levá strana" && h.act === "Kliknutím otevřete" && h.overlays >= 1 && h.cursor === "pointer", h);
  const inTip = h.tip && L.p.x >= h.tip.x && L.p.x <= h.tip.x + h.tip.width && L.p.y >= h.tip.y && L.p.y <= h.tip.y + h.tip.height;
  t("A3 popisek je u kurzoru (do 90 px), neprekryva kurzor a je cely v okne", h.tip && !inTip && Math.hypot(h.tip.x - L.p.x, h.tip.y - L.p.y) < 90 && h.tip.x >= 0 && h.tip.y >= 0 && h.tip.x + h.tip.width <= 1280 && h.tip.y + h.tip.height <= 900, { tip: h.tip, p: L.p });
  const css = await c.page.evaluate(() => { const e = document.querySelector(".v3d-tip"), s = getComputedStyle(e); return { pe: s.pointerEvents, pos: s.position, role: e.getAttribute("role"), aria: e.getAttribute("aria-hidden"), ico: !!e.querySelector("svg") }; });
  t("A3b popisek nezachytava mys (pointer-events: none), role tooltip, ikona kurzoru", css.pe === "none" && css.pos === "absolute" && css.role === "tooltip" && css.aria === "true" && css.ico, css);
  const after0 = await meanRGB(c.page, L.p.x, L.p.y);
  t("A4 podsviceni je videt na platne: barva dilu se posunula k oranzove (R-B vzrostlo o > 15)", (after0.r - after0.b) - (base0.r - base0.b) > 15, { base0, after0 });
  const afterF = await meanRGB(c.page, F.p.x, F.p.y);
  t("A4b podsviti se JEN najety dil: vzdaleny jiny pohyblivy dil (" + F.txt + " · " + F.side + ") ma barvu beze zmeny", Math.abs((afterF.r - afterF.b) - (baseF.r - baseF.b)) < 6, { baseF, afterF });
  await c.page.screenshot({ path: path.join(SHOTS, "hover_levy.png"), clip: { x: Math.max(0, L.p.x - 300), y: Math.max(0, L.p.y - 200), width: 700, height: 420 } });
  const pi = await c.page.evaluate(([x, y]) => window.__v3d.pickInfo(x, y), [L.p.x, L.p.y]);
  t("A5 podsvicovaci vrstva neodpovida na klik ani najeti (zasah porad vraci puvodni pohyb)", pi && pi.motion === L.id, pi);
  const stat = await najdiBod(c.page, false), mimo = await najdiBod(c.page, null);
  await moveTo(c.page, stat.x, stat.y);
  h = await hov(c.page);
  const piStat = await c.page.evaluate(([x, y]) => window.__v3d.pickInfo(x, y), [stat.x, stat.y]), onPickOn = await c.page.evaluate(() => window.__v3d.state().onPick);
  t("A6 najeti na dil BEZ pohybu (korpus): zadna vyzva ani podsviceni; kurzor jen podle dosavadni logiky (ruka jen kdyz klik jde do onPick stranky)", !h.on && h.overlays === 0 && h.id === null && h.cursor === ((onPickOn && piStat && piStat.slot != null) ? "pointer" : ""), { h, stat, piStat, onPickOn });
  await moveTo(c.page, L.p.x, L.p.y);
  await moveTo(c.page, mimo ? mimo.x : 300, mimo ? mimo.y : 120);
  h = await hov(c.page);
  t("A7 odjeti z dilu (na pozadi / mimo model): vyzva i podsviceni zmizi", !h.on && h.overlays === 0 && h.id === null, { h, mimo });
  const back = await meanRGB(c.page, L.p.x, L.p.y);
  t("A7b po odjeti je barva dilu zase puvodni (podsviceni odstraneno z platna)", Math.abs((back.r - back.b) - (base0.r - base0.b)) < 6, { base0, back });
  await moveTo(c.page, L.p.x, L.p.y);
  await c.page.mouse.move(400, 12);
  await c.page.waitForTimeout(300);
  h = await hov(c.page);
  t("A8 opusteni platna (nahoru na horni listu) vyzvu schova", !h.on && h.overlays === 0, h);
  await moveTo(c.page, L.p.x, L.p.y);
  await c.page.mouse.down(); await c.page.mouse.move(L.p.x + 50, L.p.y + 14, { steps: 6 }); await c.page.waitForTimeout(250);
  h = await hov(c.page);
  t("A9 tazeni mysi (otaceni modelu) vyzvu schova", !h.on && h.overlays === 0, h);
  await c.page.mouse.up(); await c.page.waitForTimeout(300);
  t("A9b tah NENI klik: dil se neotevrel", (await otevrenych(c.page)) === 0, await c.page.evaluate(() => window.__v3d.tapLog()));
  const Lp2 = await pt(c.page, L.id);
  await moveTo(c.page, Lp2.x, Lp2.y);
  await c.page.mouse.down(); await c.page.mouse.up();
  await c.page.waitForTimeout(450);
  const sel = await c.page.evaluate(() => window.__v3d.selectedMotion());
  h = await hov(c.page);
  t("A10 klik dil otevre a vybere (klik se vyzvou nezmenil), a vyzva po kliknuti nikdy neukazuje stary text \"otevrete\" pro otevreny dil", sel === L.id && (!h.on || h.id !== L.id || h.act === "Kliknutím zavřete"), { sel, h });
  await settle(c.page);
  t("A10b dil je po animaci otevreny (cip is-open)", (await otevrenych(c.page)) === 1);
  const Lp3 = await pt(c.page, L.id);
  await moveTo(c.page, Lp3.x, Lp3.y);
  h = await hov(c.page);
  t("A11 najeti na OTEVRENY dil: vyzva \"Kliknutím zavřete\"", h.on && h.id === L.id && h.act === "Kliknutím zavřete" && h.name === L.txt + " · Levá strana", h);
  await c.page.mouse.down(); await c.page.mouse.up();
  await settle(c.page); await c.page.waitForTimeout(400);
  const Lp4 = await pt(c.page, L.id);
  await moveTo(c.page, Lp4.x, Lp4.y);
  h = await hov(c.page);
  t("A12 druhy klik dil zavre a vyzva je zase \"Kliknutím otevřete\"", (await otevrenych(c.page)) === 0 && h.on && h.act === "Kliknutím otevřete", { open: await otevrenych(c.page), h });
  const Rp = await pt(c.page, R.id);
  await moveTo(c.page, Rp.x, Rp.y);
  h = await hov(c.page);
  t("A13 dil prave strany: popisek konci \"· Pravá strana\"", h.on && h.id === R.id && h.name === R.txt + " · Pravá strana", h);
  // box na zavrenem vysuvu: prvni klik vysune vysuv -> vyzva rika, co se otevre
  const stv = await c.page.evaluate(() => window.__v3d.state());
  const boxy = stv.motions.filter((m) => m.deps.length && stv.t[m.id] < 0.5 && stv.t[m.deps[0]] < 1);
  let boxInfo = "model nema box na vysuvu";
  if (boxy.length) {
    const hodnoty = [];
    for (const b of boxy.slice(0, 4)) {
      const p = await pt(c.page, b.id); if (!p) continue;
      await moveTo(c.page, p.x, p.y);
      const hh = await hov(c.page);
      const mh = stv.motions.find((m) => m.id === hh.id), dh = mh && mh.deps.length ? stv.motions.find((m) => m.id === mh.deps[0]) : null;
      const cekano = (mh && dh && stv.t[mh.id] < 0.5 && stv.t[dh.id] < 1) ? "Kliknutím otevřete: " + dh.label : "Kliknutím otevřete";       // box na zavrenem vysuvu: prvni klik vysune vysuv
      hodnoty.push({ box: b.label, ok: hh.on && !!mh && hh.act === cekano, hov: hh.id, name: hh.name, act: hh.act, cekano });
    }
    boxInfo = hodnoty;
    t("A14 box na zavrenem vysuvu: vyzva rika \"Kliknutím otevřete: <vysuv>\" (prvni klik vysune vysuv); text vzdy odpovida dilu pod mysi", hodnoty.length >= 2 && hodnoty.every((x) => x.ok) && hodnoty.filter((x) => /: Výsuv/.test(x.act)).length >= 2, hodnoty);
  } else console.log("  INFO A14 preskoceno: " + boxInfo);
  t("A15 stranka bez chyb v konzoli", c.errs.length === 0, c.errs);

  console.log("\n## B) drateny vzhled: jen popisek a kurzor (podsviceni se nestavi)");
  await c.page.click('[data-grp="mode"][data-v="wire"]'); await c.page.waitForTimeout(900);
  const Wp = await pt(c.page, L.id);
  await moveTo(c.page, Wp.x, Wp.y);
  h = await hov(c.page);
  t("B1 v dratenem vzhledu: popisek je, podsviceni (vrstva na meshich) ne", h.on && h.id === L.id && h.overlays === 0, { h, mode: (await c.page.evaluate(() => window.__v3d.state().mode)) });
  await c.page.click('[data-grp="mode"][data-v="real"]'); await c.page.waitForTimeout(900);
  h = await hov(c.page);
  t("B2 prepnuti vzhledu vyzvu uklidi (zadna zbytkova vrstva)", h.overlays === 0, h);
  await c.ctx.close();

  }
  if (ONLY.includes("C")) {
  console.log("\n## C) dotyk (390x844): bez najeti, bez vyzvy, klepnuti dil porad otevre");
  c = await otevri({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  const cht = await chips(c.page);
  const T = await prvniZasazitelny(c.page, cht);
  await c.page.touchscreen.tap(T.p.x, T.p.y); await c.page.waitForTimeout(500);
  h = await hov(c.page);
  t("C1 klepnuti na dil: pohyb se spusti (vybrany komponent) a zadna vyzva ani podsviceni", (await c.page.evaluate(() => window.__v3d.selectedMotion())) === T.id && !h.on && h.overlays === 0, h);
  t("C2 zadny prvek popisku se v dotykovem rezimu ani nevytvoril", (await c.page.evaluate(() => document.querySelectorAll(".v3d-tip.is-on").length)) === 0);
  t("C3 stranka bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  }
  if (ONLY.includes("D")) {
  console.log("\n## D) druhe instance vieweru ve strance: bez hoverHint, jazyk, strany, setModel, snimek, dispose");
  c = await otevri();
  const mountExtra = (glb, o) => c.page.evaluate(async ([url, o]) => {
    const old = document.getElementById("extra"); if (old) { if (window.__extra) { try { window.__extra.dispose(); } catch (e) { /* */ } } old.remove(); }
    const d = document.createElement("div"); d.id = "extra"; d.style.cssText = "position:fixed;left:0;top:0;width:1000px;height:700px;z-index:99999;background:#fff";
    document.body.appendChild(d);
    window.__extra = V3D.mount(d, Object.assign({ modelUrl: url, mode: "real", allowReal: true, hudKoty: false, dims: 0 }, o));
    await window.__extra.ready;
    await new Promise((r) => setTimeout(r, 1200));
    return true;
  }, [base + "/glb/" + glb + ".glb", o]);
  await mountExtra("dvoustrane", {});
  let ce = await prvniZasazitelny(c.page, (await chips(c.page, "#extra")).filter((x) => x.side === "left"));
  await moveTo(c.page, ce.p.x, ce.p.y);
  h = await hov(c.page);
  t("D1 BEZ hoverHint (vychozi): zadna vyzva ani podsviceni, ale kurzor ruka zustava jako driv", !h.on && h.overlays === 0 && h.cursor === "pointer", h);
  const en = { hover_open: "Click to open", hover_close: "Click to close", side_left: "Left side", side_right: "Right side", side_bulkhead: "Bulkhead" };
  await mountExtra("trojstrane", { hoverHint: true, labels: en });
  const c3 = await chips(c.page, "#extra");
  t("D2 trojstranna scena ma cipy leve, prave i prepazky", ["left", "right", "bulkhead"].every((s) => c3.some((x) => x.side === s)), c3.map((x) => x.side + ":" + x.txt));
  for (const [side, txt] of [["left", "Left side"], ["right", "Right side"], ["bulkhead", "Bulkhead"]]) {
    const q = await prvniZasazitelny(c.page, c3.filter((x) => x.side === side));
    if (!q) { t("D3 " + side + ": bod na dilu nalezen", false); continue; }
    await moveTo(c.page, q.p.x, q.p.y);
    h = await hov(c.page);
    t("D3 hostitelske texty (labels): " + side + " -> \"" + q.txt + " · " + txt + " / Click to open\"", h.on && h.name === q.txt + " · " + txt && h.act === "Click to open", h);
  }
  const q0 = await prvniZasazitelny(c.page, c3.filter((x) => x.side === "left"));
  await moveTo(c.page, q0.p.x, q0.p.y);
  const snapOk = await c.page.evaluate(async () => { const s = await window.__extra.snapshot({ width: 300 }); return /^data:image\//.test(s); });
  h = await hov(c.page);
  t("D4 snimek (snapshot) uklidi podsviceni z platna, vyzva se vrati az dalsim pohybem mysi", snapOk && h.overlays === 0 && h.id === null && !h.on, h);
  await moveTo(c.page, q0.p.x + 1, q0.p.y + 1); await moveTo(c.page, q0.p.x, q0.p.y);
  h = await hov(c.page);
  t("D4b po snimku se vyzva s dalsim pohybem mysi zase ukaze", h.on && h.overlays >= 1, h);
  await c.page.evaluate(() => window.__extra.setMode("wire"));
  h = await hov(c.page);
  t("D4c programove prepnuti vzhledu (setMode) behem najeti hned uklidi podsviceni z platna", h.overlays === 0 && h.id === null && !h.on, h);
  await c.page.evaluate(() => window.__extra.setMode("real"));
  await moveTo(c.page, q0.p.x + 1, q0.p.y + 1); await moveTo(c.page, q0.p.x, q0.p.y);
  h = await hov(c.page);
  t("D4d po navratu do skutecneho vzhledu a pohybu mysi se vyzva i podsviceni vrati", h.on && h.overlays >= 1, h);
  h = await c.page.evaluate(async (u) => { await window.__extra.setModel(u); return window.__v3d.hoverInfo(); }, base + "/glb/bez_g.glb");
  t("D5 vymena modelu (setModel) hned uklidi podsviceni a vyzvu (patrily starému modelu)", h.overlays === 0 && h.id === null && !h.on, h);
  await c.page.waitForTimeout(1500);
  const cb = await prvniZasazitelny(c.page, await chips(c.page, "#extra"));
  await moveTo(c.page, cb.p.x, cb.p.y);
  h = await hov(c.page);
  t("D6 model bez strany (g): popisek je jen nazev dilu, bez \" · \"", h.on && h.name === cb.txt && !/ · /.test(h.name) && h.act === "Click to open", h);
  await c.page.evaluate(() => window.__extra.dispose());
  const zbytek = await c.page.evaluate(() => ({ tip: document.querySelectorAll("#extra .v3d-tip").length, hook: window.__v3d }));
  t("D7 dispose odstrani popisek z DOM a ladici hook", zbytek.tip === 0 && zbytek.hook === null, zbytek);
  t("D8 stranka bez chyb v konzoli (vc. dispose a vymeny modelu)", c.errs.length === 0, c.errs);
  await c.ctx.close();

  }

  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : "") + "   snimky: " + SHOTS);
  await browser.close(); server.close(); fs.rmSync(TMP, { recursive: true, force: true });
  process.exit(bad ? 1 : 0);
})();
