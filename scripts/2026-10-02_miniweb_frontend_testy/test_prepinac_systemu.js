// Zakaznicky PREPINAC SYSTEMU stolu 30 / 35 / 40 ve vlozenem generatoru (Robert 2026-10-05: "Ano prepinac dame klientovi"). Nad skutecnym schematem a generatorem (bridge.py: PID = system 30,
// PID35 = system 35, PID40 = system 40, vsechny tri karty aktivni). Overuje: prepinac je videt jen pri 2+ aktivnich systemech, tentyz vyber (sirka) se prenese na druhy system a zpet, hash #v=... se po nacteni
// uklidi, v nasi strance kategorie (stejny origin) generator posle rodici zpravu a kdyz rodic nereaguje, prepne se sam; modul balí/rozbali vyber bezpecne (neznamy slot, __proto__).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID, PID40 = process.env.PID40, PID35 = process.env.PID35;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } }); const errs = [];
  const ready = async (p) => { await p.locator(W).waitFor({ timeout: 60000 }); await p.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 60000 }); };
  const settle = (p, ms) => p.waitForTimeout(ms || 1800);
  const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message));
  await pg.addInitScript(() => { window.__pdcDebug = true; });

  // --- 1) prepinac je videt, 30 je zvoleny
  await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg);
  ok(await pg.locator(".pdc-sys").count() === 1 && await pg.locator(".pdc-sys-b").count() === 3, "S1 prepínač systému je vidět (tři tlačítka: 30, 35, 40) u systému 30");
  ok((await pg.locator(".pdc-sys-b[data-system='30']").getAttribute("aria-pressed")) === "true" && (await pg.locator(".pdc-sys-b[data-system='35']").getAttribute("aria-pressed")) === "false" && (await pg.locator(".pdc-sys-b[data-system='40']").getAttribute("aria-pressed")) === "false", "S2 zvolený je systém 30");
  const popisky = await pg.$$eval(".pdc-sys-b", b => b.map(x => x.textContent)), stitek = await pg.locator(".pdc-sys-l").innerText();
  const L35 = await pg.evaluate(async () => { const d = await (await fetch("/miniweb/i18n/cs.json")).json(); return d["pdc.sys35"] || (d["pdc.sysOpt"] || "Systém {n}").replace("{n}", "35"); });          // štítek systému 35 napíše bot7 (pdc.sys35); do té doby "Systém 35"
  ok(popisky.join("|") === "Lehký 30×30|" + L35 + "|Robustní 40×40" && stitek === "Systém profilu", "S3 popisky česky: " + stitek + " | " + popisky.join(" | "));
  const nad = await pg.evaluate(() => { const s = document.querySelector(".pdc-sys").getBoundingClientRect(), g = document.querySelector(".mw-grid, .pdc-grid, .emb-grid, #app > div:not(.pdc-sys)"); return g ? s.bottom <= g.getBoundingClientRect().top + 2 : null; });
  ok(nad !== false, "S4 prepínač je nad mřížkou oken (ne uvnitř ní)");

  // --- 2) tentyz vyber na druhem systemu a zpet
  await pg.locator(W).fill("1800"); await pg.locator(W).blur(); await settle(pg);
  const cena30 = await pg.locator(".emb-price .big").innerText();
  await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID40}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='40']").click()]);
  await ready(pg);
  ok((await pg.locator(W).inputValue()) === "1800", "S5 po přepnutí na systém 40 zůstala šířka 1800 (stejný výběr): " + await pg.locator(W).inputValue());
  ok((await pg.title()) === "Generátor stolu – systém 40" && (await pg.locator(".pdc-sys-b[data-system='40']").getAttribute("aria-pressed")) === "true", "S6 jsme na systému 40 (titulek i zvolené tlačítko): " + await pg.title());
  ok((await pg.evaluate(() => location.hash)) === "", "S7 hash #v=… se po načtení uklidil z adresy");
  const cena40 = await pg.locator(".emb-price .big").innerText();
  const n = (t) => Number(t.replace(/[^\d]/g, ""));
  ok(n(cena40) > n(cena30), "S8 cena systému 40 je vyšší než systému 30 při stejném výběru: " + cena30 + " → " + cena40);
  await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='30']").click()]);
  await ready(pg);
  ok((await pg.locator(W).inputValue()) === "1800" && (await pg.title()) === "Generátor stolu – systém 30", "S9 zpět na systém 30: šířka 1800 se zachovala");
  // --- 2b) treti system 35 (karta #4955): stejny vyber, titulek, rovnou na 40 a zpet
  await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID35}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='35']").click()]); await ready(pg);
  ok((await pg.locator(W).inputValue()) === "1800" && (await pg.title()) === "Generátor stolu – systém 35" && (await pg.locator(".pdc-sys-b[data-system='35']").getAttribute("aria-pressed")) === "true", "S9b přepnutí na systém 35: šířka 1800 se zachovala, titulek i zvolené tlačítko: " + await pg.title());
  await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID40}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='40']").click()]); await ready(pg);
  ok((await pg.locator(W).inputValue()) === "1800" && (await pg.title()) === "Generátor stolu – systém 40", "S9c ze systému 35 rovnou na 40: šířka 1800 se zachovala");
  await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='30']").click()]); await ready(pg);

  // --- 3) co druhy system nema (sikme vzpery), se odebere s oznamenim; ostatni zustane
  await pg.evaluate(() => window.__pdcApplyPatch({ arm: true, braces: true })); await settle(pg, 3500);
  const sel30 = await pg.evaluate(() => ({ arm: window.__pdcState.sel.arm, braces: window.__pdcState.sel.braces }));
  if (sel30.braces) {
    await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID40}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='40']").click()]);
    await ready(pg); await settle(pg, 2500);
    const st40 = await pg.evaluate(() => ({ braces: window.__pdcState.sel.braces, w: window.__pdcState.sel.w, notices: [...document.querySelectorAll(".pdc-notice-item")].map(x => x.textContent) }));
    ok(!st40.braces && st40.w === 1800 && st40.notices.some(t => /vzpěry/i.test(t)), "S10 šikmé vzpěry se v systému 40 odebraly s oznámením, šířka zůstala: " + JSON.stringify(st40.notices));
    await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='30']").click()]); await ready(pg);
  } else ok(true, "S10 (přeskočeno: vzpěry v testovacím stole nejdou zapnout) " + JSON.stringify(sel30));

  // --- 4) v nasi strance (stejny origin): generator posle rodici zpravu; kdyz rodic nereaguje, prepne se jen generator
  const host = await ctx.newPage(); const hostErrs = []; host.on("pageerror", e => hostErrs.push(e.message));
  await host.route("**/__host.html", r => r.fulfill({ contentType: "text/html", body: `<!doctype html><meta charset=utf-8><body style="margin:0"><iframe id=f src="/embed/stul.html?p=${PID}" style="width:1200px;height:2400px;border:0"></iframe><script>window.__msgs=[];addEventListener("message",function(e){if(e.data&&e.data.type==="stul-embed-switch-system")window.__msgs.push(e.data)})</script>` }));
  await host.goto(`${BASE}/__host.html`);
  const fr = host.frames().find(f => /embed\/stul\.html/.test(f.url())) || (await (await host.waitForSelector("#f")).contentFrame());
  await fr.locator(W).waitFor({ timeout: 60000 }); await fr.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 60000 });
  await fr.locator(W).fill("1500"); await fr.locator(W).blur(); await host.waitForTimeout(1800);
  await fr.locator(".pdc-sys-b[data-system='40']").click();
  await host.waitForFunction(() => window.__msgs.length === 1, null, { timeout: 10000 });
  const msg = await host.evaluate(() => window.__msgs[0]);
  const dec = await fr.evaluate((v) => window.PdConfigurator.unpackSelection("#" + v), msg.v);
  ok(msg.type === "stul-embed-switch-system" && msg.card_id === Number(PID40) && msg.system === 40 && dec && dec.w === 1500, "S11 v naší stránce generátor pošle rodiči zprávu (karta " + msg.card_id + ", systém " + msg.system + ", šířka " + (dec && dec.w) + ")");
  await host.waitForFunction((pid) => { const f = document.getElementById("f"); try { return f.contentWindow.location.search.indexOf("p=" + pid) >= 0; } catch (e) { return false; } }, PID40, { timeout: 15000 }).catch(() => {});
  const fr2 = host.frames().find(f => /embed\/stul\.html\?.*p=/.test(f.url()) && f.url().indexOf("p=" + PID40) >= 0);
  ok(!!fr2, "S12 rodič nereagoval → po chvíli se přepnul jen generátor na kartu druhého systému");
  if (fr2) { await fr2.locator(W).waitFor({ timeout: 60000 }); ok((await fr2.locator(W).inputValue()) === "1500", "S13 i přepnutí uvnitř rámu přeneslo šířku 1500"); }

  // --- 5) pomocne funkce vyberu: kolecko, neznamy slot, nebezpecne klice
  const t = await pg.evaluate(() => {
    const P = window.PdConfigurator, sel = { w: 1800, cut1: true, nazev: "á ü & #", x: 0.5 };
    const back = P.unpackSelection("#" + P.packSelection(sel));
    const evil = P.unpackSelection("#v=" + btoa(JSON.stringify({ __proto__: { polluted: 1 }, w: 5, a: [1], b: { c: 1 } })).replace(/=+$/, ""));
    return { ok: JSON.stringify(back) === JSON.stringify(sel), evil: evil, polluted: ({}).polluted, garbage: [P.unpackSelection("#v=@@@"), P.unpackSelection("#nic"), P.unpackSelection(""), P.unpackSelection("#v=" + btoa("[1,2]"))] };
  });
  ok(t.ok && t.polluted === undefined && t.evil && t.evil.w === 5 && !("a" in t.evil) && !("b" in t.evil) && t.garbage.every(x => x === null), "S14 balení výběru: kolečko sedí, pole/objekty a __proto__ se zahodí, nesmysly = null: " + JSON.stringify(t.evil));
  // --- 6) uzky telefon: tri tlacitka prepinace se vejdou do radku bez vodorovneho posuvu (360 a 320 px)
  for (const vw of [360, 320]) {
    const mob = await browser.newContext({ viewport: { width: vw, height: 800 }, isMobile: true, hasTouch: true }); const mp = await mob.newPage(); mp.on("pageerror", e => errs.push(e.message));
    await mp.goto(`${BASE}/embed/stul.html?p=${PID}`); await mp.locator(".pdc-sys-b").first().waitFor({ timeout: 60000 }); await mp.waitForTimeout(1500);
    const fit = await mp.evaluate(() => { const bs = [...document.querySelectorAll(".pdc-sys-b")].map(b => b.getBoundingClientRect()); return { n: bs.length, right: Math.round(Math.max(...bs.map(b => b.right))), left: Math.round(Math.min(...bs.map(b => b.left))), minH: Math.round(Math.min(...bs.map(b => b.height))), scrollW: document.documentElement.scrollWidth, vw: window.innerWidth }; });
    ok(fit.n === 3 && fit.right <= fit.vw && fit.left >= 0 && fit.scrollW <= fit.vw && fit.minH >= 36, "S16 " + vw + " px: tři tlačítka přepínače se vejdou (okraje " + fit.left + "–" + fit.right + " z " + fit.vw + ", bez vodorovného posuvu, nejnižší tlačítko " + fit.minH + " px)");
    await mob.close();
  }
  ok(!errs.length && !hostErrs.length, "S15 bez JS chyb" + ((errs[0] || hostErrs[0]) ? " | " + (errs[0] || hostErrs[0]) : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
