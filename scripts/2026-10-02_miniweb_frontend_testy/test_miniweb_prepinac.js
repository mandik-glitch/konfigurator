// Prepinac systemu stolu 30 / 35 / 40 na karte produktu mini-shopu (Robert 2026-10-05: "prepinac dame klientovi") - SKUTECNY front-end nad skutecnym API a daty (bridge_miniweb.py).
// APPROVE=1 (vychozi): vsechny tri produkty verejne -> prepinac je videt a tentyz vyber (sirka) se prenese na dalsi produkt a zpet. APPROVE=0: druhy produkt je jen draft (verejne neni) -> prepinac se NEUKAZE.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs"), path = require("path");
const BASE = process.env.BASE, DRUHY_VEREJNY = process.env.APPROVE !== "0";
const DICT = JSON.parse(fs.readFileSync(path.join(process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp", "miniweb/i18n/sk.json"), "utf8"));         // stitky systemu (pdc.sys30/35/40) pise bot7
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } });
  await ctx.route(/pripni-cokoli/, r => r.abort());                    // druhy 3D prvek se tu netestuje
  const errs = [], page = await ctx.newPage(); page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text().slice(0, 200)); });
  const ready = async () => { await page.locator(W).waitFor({ timeout: 90000 }); await page.waitForFunction(() => document.querySelector("#mwPdPrice") && /\d/.test(document.querySelector("#mwPdPrice").textContent), null, { timeout: 90000 }); };

  await page.goto(`${BASE}/miniweb/product.html?id=1`); await ready();
  if (!DRUHY_VEREJNY) {
    ok(await page.locator(".pdc-sys").count() === 0, "N1 druhý produkt není veřejný (draft) → přepínač se NEUKAZUJE (nenabízí se odkaz do prázdna)");
    ok(!errs.length, "N2 bez JS chyb"); await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
  }
  ok(await page.locator(".pdc-sys").count() === 1 && await page.locator(".mw-pd-title .pdc-sys").count() === 1, "P1 přepínač je pod názvem produktu");
  const popisky = await page.$$eval(".pdc-sys-b", b => b.map(x => x.textContent)), stitek = await page.locator(".pdc-sys-l").innerText();
  const L = [DICT["pdc.sys30"], DICT["pdc.sys35"] || DICT["pdc.sysOpt"].replace("{n}", "35"), DICT["pdc.sys40"]];
  ok(popisky.join("|") === L.join("|") && stitek === DICT["pdc.sysLabel"] && L[0] === "Ľahký 30×30" && L[2] === "Robustný 40×40", "P2 popisky slovensky (tři veřejné produkty): " + stitek + " | " + popisky.join(" | "));
  ok((await page.locator(".pdc-sys-b[data-system='30']").getAttribute("aria-pressed")) === "true", "P3 na produktu 1 je zvolený systém 30");
  await page.locator(W).fill("1800"); await page.locator(W).blur(); await page.waitForTimeout(2200);
  const n = (t) => Number(t.replace(/\s| /g, "").replace(",", ".").replace(/[^\d.]/g, ""));
  const cena30 = n(await page.locator("#mwPdPrice").innerText());
  await Promise.all([page.waitForURL(/product\.html\?id=2/, { timeout: 30000 }), page.locator(".pdc-sys-b[data-system='40']").click()]);
  await ready();
  ok((await page.locator("h1").first().innerText()) === "Konfigurovateľný robustný baliaci stôl", "P4 přepnuto na produkt systému 40: " + await page.locator("h1").first().innerText());
  ok((await page.locator(W).inputValue()) === "1800", "P5 stejný výběr: šířka 1800 se přenesla: " + await page.locator(W).inputValue());
  ok((await page.locator(".pdc-sys-b[data-system='40']").getAttribute("aria-pressed")) === "true" && (await page.evaluate(() => location.hash)) === "", "P6 zvolený systém 40, hash #v=… uklizen z adresy");
  const cena40 = n(await page.locator("#mwPdPrice").innerText());
  ok(cena40 > cena30, "P7 cena u systému 40 je při stejném výběru vyšší: " + cena30 + " → " + cena40 + " €");
  await Promise.all([page.waitForURL(/product\.html\?id=1/, { timeout: 30000 }), page.locator(".pdc-sys-b[data-system='30']").click()]);
  await ready();
  ok((await page.locator(W).inputValue()) === "1800" && (await page.locator("h1").first().innerText()) === "Konfigurovateľný baliaci a pracovný stôl", "P8 zpět na produkt 1: šířka 1800 zůstala");
  // treti produkt = system 35 (karta 4955): stejny vyber, rovnou na 40 a zpet
  await Promise.all([page.waitForURL(/product\.html\?id=3/, { timeout: 30000 }), page.locator(".pdc-sys-b[data-system='35']").click()]); await ready();
  ok((await page.locator(W).inputValue()) === "1800" && (await page.locator(".pdc-sys-b[data-system='35']").getAttribute("aria-pressed")) === "true" && (await page.evaluate(() => location.hash)) === "", "P8b přepnuto na produkt systému 35: šířka 1800 se přenesla, zvolený je systém 35, hash uklizen");
  await Promise.all([page.waitForURL(/product\.html\?id=2/, { timeout: 30000 }), page.locator(".pdc-sys-b[data-system='40']").click()]); await ready();
  ok((await page.locator(W).inputValue()) === "1800", "P8c ze systému 35 rovnou na 40: šířka 1800 zůstala");
  await Promise.all([page.waitForURL(/product\.html\?id=1/, { timeout: 30000 }), page.locator(".pdc-sys-b[data-system='30']").click()]); await ready();
  const px = (n2) => page.evaluate(() => { const s = document.querySelector(".pdc-sys").getBoundingClientRect(); return { w: Math.round(s.width), h: Math.round(s.height) }; });
  const r = await px();
  ok(r.h > 30 && r.h < 80, "P9 přepínač má rozumnou výšku (" + r.h + " px)");
  // mobil: prepinac se vejde na sirku (bez vodorovneho posunu)
  const mob = await browser.newContext({ viewport: { width: 360, height: 800 } }); await mob.route(/pripni-cokoli/, rr => rr.abort());
  const mp = await mob.newPage(); await mp.goto(`${BASE}/miniweb/product.html?id=1`); await mp.locator(".pdc-sys").waitFor({ timeout: 90000 });
  const fit = await mp.evaluate(() => { const s = document.querySelector(".pdc-sys-seg").getBoundingClientRect(); return { n: document.querySelectorAll(".pdc-sys-b").length, right: Math.round(s.right), vw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth }; });
  ok(fit.n === 3 && fit.right <= fit.vw && fit.sw <= fit.vw + 1, "P10 mobil 360 px: tři tlačítka přepínače se vejdou, stránka nemá vodorovný posun (" + JSON.stringify(fit) + ")");
  ok(!errs.length, "X bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(rr => setTimeout(rr, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
