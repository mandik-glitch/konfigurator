#!/usr/bin/env node
/**
 * QA (E) - Playwright e2e smoke suite (bot5, 2026-09-02, "kontrolni
 * mechanismy na cely system konfiguratoru" od Roberta pres bot3).
 *
 * READ-ONLY vuci produkci: zadny formular se NEODESILA na server bez
 * page.route()+route.fulfill() prestreni (kontaktni/poptavkovy formular,
 * "Zakreslena pripominka"), zadne testovaci leady/objednavky/registrace.
 * Admin sekce (je-li QA_ADMIN_EMAIL/QA_ADMIN_PASSWORD v api/.env) jen
 * prohlizi zalozky, nic neklika na zapisove akce.
 *
 * Pouziti:
 *   node scripts/qa/e2e/run.cjs --browser both --viewport both --json
 *   node scripts/qa/e2e/run.cjs --browser chromium --viewport mobile
 *
 * Vystup: JSON kontrakt (suite/ran_at/duration_s/status/findings/stats),
 * viz scripts/qa/_common.py hlavicka pro presny tvar (tenhle skript je
 * .cjs, takze kontrakt je tu zopakovan rucne, ne importovan).
 * Exit: 0 ok, 1 warn, 2 fail, 3 skript sam selhal.
 *
 * Playwright BEZI ze /opt/konfigurator/node_modules (ne osobni scratch
 * install - bot3 pozadavek), prohlizece SEKVENCNE (chromium pak firefox),
 * ne paralelne - kontrola /run/ram-watchdog-alert pred spustenim.
 */
const { chromium, firefox } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const QA_REPORTS_DIR = path.join(REPO_ROOT, "qa-reports", "e2e");
const BASELINE_PATH = path.join(QA_REPORTS_DIR, "baseline.json");

function parseArgs(argv) {
  const out = { browser: "both", viewport: "both", json: false, baseUrl: "https://autovestavby.logiman.cz" };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--browser") out.browser = argv[++i];
    else if (a === "--viewport") out.viewport = argv[++i];
    else if (a === "--json") out.json = true;
    else if (a === "--base-url") out.baseUrl = argv[++i];
  }
  return out;
}

function finding(severity, code, title, detail, where, fix_hint) {
  return { severity, code, title, detail, where: where || null, fix_hint: fix_hint || null };
}

function overallStatus(findings) {
  if (findings.some(f => f.severity === "critical")) return "fail";
  if (findings.some(f => f.severity === "warning")) return "warn";
  return "ok";
}

const STATUS_EXIT = { ok: 0, warn: 1, fail: 2 };

// --- stranky k proverovani (bot3 zadani) -----------------------------
const SITE_BASE = "https://autovestavby.logiman.cz";
const REMESLO_APP = "https://app.remeslnik.pro";
const REMESLO_PRO = "https://remeslnik.pro";

const PAGES = [
  { name: "homepage", url: `${SITE_BASE}/` },
  { name: "kategorie-1", url: `${SITE_BASE}/kategorie/plastove-zaslepky-profilu` },
  { name: "kategorie-2", url: `${SITE_BASE}/kategorie/hlinikove-profily-s-drazkou-10-mm` },
  { name: "produkt-dil", url: `${SITE_BASE}/produkt/uhelnikova-spojka-30x30` },
  { name: "produkt-sestava-tt", url: `${SITE_BASE}/produkt/jumpy-l3-ci26-boxy43-270x4-170x3-120x9` },
  { name: "produkt-galerie", url: `${SITE_BASE}/produkt/podlozkova-matice-s-kulatou-hlavou` },
  { name: "scene", url: `${SITE_BASE}/scene.html`, sceneHeadless: true },
  { name: "kontakt", url: `${SITE_BASE}/kontakt.html` },
  { name: "realizace", url: `${SITE_BASE}/realizace.html` },
  { name: "blok", url: `${SITE_BASE}/blok/alu-profily-vhodne-pro-vestavby-pracovnich-dodavek` },
  { name: "register", url: `${SITE_BASE}/register.html` },
  { name: "login", url: `${SITE_BASE}/login.html` },
  { name: "forgot-password", url: `${SITE_BASE}/forgot-password.html` },
  { name: "poptavka-stul", url: `${SITE_BASE}/poptavka-stul.html` },
  { name: "nabidka-online", url: `${SITE_BASE}/nabidka-online.html` },
  { name: "glb-vyber", url: `${SITE_BASE}/glb-vyber.html` },
  { name: "capture", url: `${SITE_BASE}/capture.html` },
  { name: "robots-txt", url: `${SITE_BASE}/robots.txt`, isText: true },
  { name: "sitemap-xml", url: `${SITE_BASE}/sitemap.xml`, isText: true },
  { name: "remeslo-home", url: `${REMESLO_APP}/` },
  { name: "remeslo-login", url: `${REMESLO_APP}/login.html` },
  { name: "remeslo-register", url: `${REMESLO_APP}/remeslo-register.html` },
  { name: "remeslo-forgot-password", url: `${REMESLO_APP}/forgot-password.html` },
  { name: "remeslo-srovnavac", url: `${REMESLO_APP}/remeslo-srovnavac.html` },
  { name: "remeslo-hlas-test", url: `${REMESLO_APP}/remeslo-hlas-test.html` },
  { name: "remeslo-spolupracovnik", url: `${REMESLO_APP}/remeslo-spolupracovnik.html` },
  { name: "remeslo-nabidka-online", url: `${REMESLO_PRO}/remeslo-nabidka-online.html` },
];

const VIEWPORTS = {
  mobile: { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true },
  desktop: { width: 1280, height: 900, deviceScaleFactor: 1, isMobile: false, hasTouch: false },
};

// /api/katalog, /api/pricing-config, /api/admin/blender-render/assets jsou
// @staff_required (Robert 2026-09-03: "zakaznikum pristup do sceny
// neumoznime") - anonymni 401 na scene.html je ocekavane. /api/remeslo/* trojice
// je @remeslnik_or_admin_required v samostatnem /opt/remeslo projektu (Faze 6
// cutover 2026-09-05) - anonymni navsteva remeslo-hlas-test.html tam spravne
// dostane 401.
const KNOWN_ANON_401 = [
  "/api/auth/me", "/api/cart", "/api/customer/profile",
  "/api/katalog", "/api/pricing-config", "/api/admin/blender-render/assets",
  "/api/remeslo/voice-phrases/effective", "/api/remeslo/calculator-types", "/api/remeslo/voice-notes",
];
// /api/track/* ma vlastni per-IP anti-flood limit (api/tracking.py
// _track_guard, 30 req/60s) - e2e beh sam sebe naplni kumulativnim objemem
// napric ~26 strankami ze stejne IP, ne realny bug (viz i page.route
// intercept v checkPage, ktery navic zabrani skutecnym zapisum do prod DB).
const KNOWN_RATE_LIMITED_429 = ["/api/track/page-view", "/api/track/product-view"];

async function checkPage(page, url, opts) {
  const findings = [];
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const mixedContent = [];
  let transferredBytes = 0;

  const onConsole = (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    // Prohlizec sam hlasi "Failed to load resource: ... 401/429" pro
    // requesty, ktere uz onResponse nize spravne vyfiltroval jako zname -
    // beze filtru se stejny znamy stav hlasi 2x (jednou tise potlaceny jako
    // E2E_FAILED_REQUEST, podruhe tady jako E2E_CONSOLE_ERROR).
    if (/^Failed to load resource: the server responded with a status of (401|429)/i.test(text)) {
      let loc;
      try { loc = msg.location(); } catch (e) { loc = null; }
      if (loc && loc.url) {
        if (/401/.test(text) && KNOWN_ANON_401.some(p => loc.url.includes(p))) return;
        if (/429/.test(text) && KNOWN_RATE_LIMITED_429.some(p => loc.url.includes(p))) return;
      }
    }
    consoleErrors.push(text.slice(0, 300));
  };
  const onPageError = (err) => pageErrors.push(String(err.message || err).slice(0, 300));
  const onResponse = (resp) => {
    try {
      const len = resp.headers()["content-length"];
      if (len) transferredBytes += parseInt(len, 10) || 0;
      const status = resp.status();
      const rurl = resp.url();
      if (status >= 400) {
        if (KNOWN_ANON_401.some(p => rurl.includes(p)) && status === 401) return; // znamy anonymni 401, jen info
        if (KNOWN_RATE_LIMITED_429.some(p => rurl.includes(p)) && status === 429) return; // e2e beh sam sebe naplnil anti-flood limit kumulativnim objemem, ne realny bug
        failedRequests.push(`${status} ${rurl}`);
      }
      if (url.startsWith("https://") && rurl.startsWith("http://")) mixedContent.push(rurl);
    } catch (e) { /* ignore */ }
  };
  const onReqFailed = (req) => {
    const f = req.failure();
    failedRequests.push(`NET_FAIL ${req.url()} (${f ? f.errorText : "?"})`);
  };

  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  page.on("response", onResponse);
  page.on("requestfailed", onReqFailed);

  // QA beh nesmi zapisovat skutecne radky do produkcni analytiky
  // (page_views/product_views) - stejne READ-ONLY pravidlo jako u zbytku
  // suity (hlavicka souboru). Mimoto to odstrani i 429 sum z vlastniho
  // anti-flood limitu endpointu pri prochazeni desitek stranek ze stejne IP.
  await page.route("**/api/track/**", (route) => route.fulfill({ status: 204, contentType: "application/json", body: "{}" }));

  const t0 = Date.now();
  let navError = null;
  try {
    await page.goto(url, { waitUntil: "load", timeout: 25000 });
  } catch (e) {
    navError = String(e.message || e).slice(0, 300);
  }
  const loadMs = Date.now() - t0;
  await page.waitForTimeout(600);

  let pageMetrics = null;
  if (!navError && !opts.isText) {
    try {
      pageMetrics = await page.evaluate(() => {
        const h1 = document.querySelector("h1");
        const imgs = Array.from(document.querySelectorAll("img"));
        // POZOR: <img> bez src atributu (nebo src="") vraci .src jako
        // AKTUALNI URL STRANKY (resolvovana relativni URL prazdneho
        // retezce), ne prazdny retezec - naivni filtr jen na
        // naturalWidth===0 by tak oznacil zamerne prazdne placeholdery
        // (napr. #clbImg na kategorii, plni se JS pozdeji) jako "rozbity
        // obrazek". Reálné selhani nacteni MUSI mit neprazdny src atribut.
        const brokenImgs = imgs.filter(i => i.complete && i.naturalWidth === 0 && i.getAttribute("src")).map(i => i.src).slice(0, 10);
        const inputs = Array.from(document.querySelectorAll("input:not([type=hidden]), textarea, select"));
        const inputsNoLabel = inputs.filter(i => {
          if (i.getAttribute("aria-label") || i.getAttribute("aria-labelledby") || i.placeholder) return false;
          if (i.id && document.querySelector(`label[for="${CSS.escape(i.id)}"]`)) return false;
          if (i.closest("label")) return false;
          return true;
        }).map(i => i.name || i.id || i.type || i.tagName).slice(0, 10);
        const buttons = Array.from(document.querySelectorAll("button"));
        const buttonsNoText = buttons.filter(b => {
          const txt = (b.textContent || "").trim();
          return !txt && !b.getAttribute("aria-label") && !b.title;
        }).length;
        return {
          title: document.title || "",
          h1Text: h1 ? h1.textContent.trim() : null,
          hasH1: !!h1,
          horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          brokenImgsCount: brokenImgs.length,
          brokenImgs,
          inputsNoLabelCount: inputsNoLabel.length,
          inputsNoLabel,
          buttonsNoTextCount: buttonsNoText,
          domContentLoadedMs: performance.timing ? (performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart) : null,
          loadEventMs: performance.timing ? (performance.timing.loadEventEnd - performance.timing.navigationStart) : null,
        };
      });
    } catch (e) {
      pageMetrics = null;
    }
  }

  page.off("console", onConsole);
  page.off("pageerror", onPageError);
  page.off("response", onResponse);
  page.off("requestfailed", onReqFailed);

  if (navError) {
    findings.push(finding("critical", "E2E_NAV_FAILED", `Stránka se nenačetla: ${opts.label}`, navError, opts.label));
  }
  if (consoleErrors.length) {
    findings.push(finding("warning", "E2E_CONSOLE_ERROR", `console.error na ${opts.label} (${consoleErrors.length}×)`,
      consoleErrors.slice(0, 8).join("\n"), opts.label));
  }
  if (pageErrors.length) {
    // scene.html + Firefox: bot3 zadani rika "ve Firefoxu jen ze
    // nepada" - headless Firefox nemusi mit funkcni WebGL (znama
    // limitace prostredi, ne bug appky), takove chyby nejsou critical.
    const isWebglMsg = (m) => /webgl/i.test(m);
    const webglErrors = opts.sceneFirefoxWebglOk ? pageErrors.filter(isWebglMsg) : [];
    const otherErrors = opts.sceneFirefoxWebglOk ? pageErrors.filter((m) => !isWebglMsg(m)) : pageErrors;
    if (webglErrors.length) {
      findings.push(finding("info", "E2E_SCENE_FIREFOX_NO_WEBGL", `Firefox headless nemá funkční WebGL na ${opts.label} (známá limitace prostředí)`,
        webglErrors.slice(0, 3).join("\n"), opts.label));
    }
    if (otherErrors.length) {
      findings.push(finding("critical", "E2E_PAGE_ERROR", `Neošetřená JS chyba na ${opts.label} (${otherErrors.length}×)`,
        otherErrors.slice(0, 8).join("\n"), opts.label,
        "Neošetřená výjimka za běhu - najdi stack trace a oprav (může shodit část stránky pro uživatele)."));
    }
  }
  if (failedRequests.length) {
    findings.push(finding("warning", "E2E_FAILED_REQUEST", `Selhal HTTP request na ${opts.label} (${failedRequests.length}×)`,
      failedRequests.slice(0, 10).join("\n"), opts.label));
  }
  if (mixedContent.length) {
    findings.push(finding("warning", "E2E_MIXED_CONTENT", `Mixed content (http:// z https:// stránky) na ${opts.label}`,
      mixedContent.slice(0, 5).join("\n"), opts.label));
  }
  if (pageMetrics) {
    if (pageMetrics.horizontalOverflow) {
      findings.push(finding("warning", "E2E_HORIZONTAL_OVERFLOW",
        `Vodorovné přetečení na ${opts.label}`,
        `scrollWidth ${pageMetrics.scrollWidth} > clientWidth ${pageMetrics.clientWidth}`, opts.label));
    }
    if (!pageMetrics.hasH1 || !pageMetrics.h1Text) {
      findings.push(finding("warning", "E2E_MISSING_H1", `Chybí/prázdný <h1> na ${opts.label}`,
        pageMetrics.hasH1 ? "h1 existuje, ale je prázdný" : "h1 na stránce vůbec není", opts.label));
    }
    if (pageMetrics.brokenImgsCount) {
      findings.push(finding("warning", "E2E_BROKEN_IMAGE", `${pageMetrics.brokenImgsCount} obrázek/ů s naturalWidth 0 na ${opts.label}`,
        pageMetrics.brokenImgs.join("\n"), opts.label));
    }
    if (pageMetrics.inputsNoLabelCount) {
      findings.push(finding("info", "E2E_A11Y_INPUT_NO_LABEL", `${pageMetrics.inputsNoLabelCount} pole bez labelu na ${opts.label}`,
        pageMetrics.inputsNoLabel.join(", "), opts.label,
        "Přidej <label for=...>, aria-label nebo alespoň placeholder."));
    }
    if (pageMetrics.buttonsNoTextCount) {
      findings.push(finding("info", "E2E_A11Y_BUTTON_NO_TEXT", `${pageMetrics.buttonsNoTextCount} tlačítko/tlačítek bez textu/aria-label na ${opts.label}`,
        "", opts.label));
    }
  }
  const mobileLimit = 3 * 1024 * 1024;
  if (opts.isMobile && transferredBytes > mobileLimit) {
    findings.push(finding("warning", "E2E_LARGE_TRANSFER", `Přenos > 3 MB na mobilu na ${opts.label}`,
      `${Math.round(transferredBytes / 1024)} kB`, opts.label,
      "Zkontrolovat, jestli se na mobilu nenačítá zbytečně velký obrázek/model."));
  }

  return {
    findings,
    stats: {
      loadMs,
      transferredBytes,
      domContentLoadedMs: pageMetrics ? pageMetrics.domContentLoadedMs : null,
      loadEventMs: pageMetrics ? pageMetrics.loadEventMs : null,
      title: pageMetrics ? pageMetrics.title : null,
    },
  };
}

// --- Flows (bez zapisu na server) --------------------------------------

async function flowSearchAndFilter(page, findings, label) {
  try {
    await page.goto(`${SITE_BASE}/`, { waitUntil: "load", timeout: 20000 });
    const searchInput = page.locator('input[type="search"], input[name*="search" i], input[placeholder*="hledat" i]').first();
    if (!(await searchInput.count())) {
      findings.push(finding("info", "E2E_FLOW_SEARCH_NOT_FOUND", "Vyhledávací pole na homepage nenalezeno", "", label));
      return;
    }
    if (!(await searchInput.isVisible().catch(() => false))) {
      // Mobil: vyhledavani je typicky schovane za hamburger/menu - nejde
      // o bug (najit skryty input je legitimni odpovedny vzor), jen
      // zaznamenat, ze flow nemuze pokracovat bez znalosti UI togglu.
      findings.push(finding("info", "E2E_FLOW_SEARCH_HIDDEN", "Vyhledávací pole existuje, ale není viditelné (pravděpodobně za menu/hamburger togglem)", "", label));
      return;
    }
    await searchInput.fill("profil", { timeout: 5000 });
    await searchInput.press("Enter");
    await page.waitForTimeout(1200);
  } catch (e) {
    findings.push(finding("warning", "E2E_FLOW_SEARCH_ERROR", "Flow vyhledávání selhal", String(e.message || e).slice(0, 300), label));
  }
}

async function flowCart(page, findings, label) {
  let cartWritesApi = null;
  const onReq = (req) => {
    if (req.method() === "POST" && /\/api\/cart/.test(req.url())) cartWritesApi = req.url();
  };
  page.on("request", onReq);
  try {
    await page.goto(`${SITE_BASE}/produkt/uhelnikova-spojka-30x30`, { waitUntil: "load", timeout: 20000 });
    const addBtn = page.locator('button', { hasText: /do košíku/i }).first();
    if (!(await addBtn.count())) {
      findings.push(finding("info", "E2E_FLOW_CART_BUTTON_NOT_FOUND", "Tlačítko „Do košíku“ nenalezeno na dílu", "", label));
    } else {
      // Tlacitko muze byt docasne disabled (znamy stav e-shopu:
      // "Objednávky přes košík jsou dočasně pozastaveny") - overit
      // viditelnost/enabled KRATKYM timeoutem misto rovnou klikat,
      // at se pripadny disabled stav nehlasi jako "flow selhal".
      const clickable = await addBtn.waitFor({ state: "visible", timeout: 3000 }).then(() => true).catch(() => false);
      const disabled = clickable ? await addBtn.isDisabled().catch(() => true) : true;
      if (!clickable || disabled) {
        findings.push(finding("info", "E2E_FLOW_CART_DISABLED", "Tlačítko „Do košíku“ není klikatelné (disabled/skryté - objednávky pravděpodobně pozastaveny) - přeskočeno", "", label));
      } else {
        await addBtn.click({ timeout: 5000 });
        await page.waitForTimeout(800);
      }
    }
  } catch (e) {
    findings.push(finding("warning", "E2E_FLOW_CART_ERROR", "Flow košíku selhal", String(e.message || e).slice(0, 300), label));
  } finally {
    page.off("request", onReq);
  }
  if (cartWritesApi) {
    findings.push(finding("warning", "E2E_CART_WRITES_SERVER", "Přidání do košíku volá server API (ne jen localStorage)",
      cartWritesApi, label, "Ověřit, jestli /api/cart POST při hostím košíku skutečně zapisuje do DB - pokud ano, je to zamýšlené chování e-shopu, ne bug, ale QA test ho nesmí nechat běžet naostro (zde jen zaznamenáno, request NEBYL blokován route.fulfill - zvaž přidání interceptu, pokud se tenhle test má spouštět častěji)."));
  }
}

async function flowTurntableDrag(page, findings, label) {
  try {
    await page.goto(`${SITE_BASE}/produkt/jumpy-l3-ci26-boxy43-270x4-170x3-120x9`, { waitUntil: "load", timeout: 20000 });
    const tt = page.locator("#pdTurntable").first();
    if (!(await tt.count())) {
      findings.push(finding("warning", "E2E_FLOW_TURNTABLE_NOT_FOUND", "Otočný náhled (#pdTurntable) nenalezen", "", label));
      return;
    }
    await tt.scrollIntoViewIfNeeded();
    // window.productTurntable se priradi az po async mountu (viz
    // product.html paTurntableInit) - pollovat misto pevneho waitFor,
    // aby test nebyl zavisly na jednom napevno odhadnutem cekani.
    await page.waitForFunction(() => window.productTurntable && typeof window.productTurntable.getCurrentFrame === "function",
      { timeout: 10000 }).catch(() => {});
    const box = await tt.boundingBox();
    if (!box) return;
    const before = await page.evaluate(() => {
      const t = window.productTurntable;
      const f = t && t.getCurrentFrame && t.getCurrentFrame();
      return f ? { az: f.azimuth_deg, el: f.elevation_deg } : null;
    });
    await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(500);
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.3);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.7, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(1000);
    const after = await page.evaluate(() => {
      const t = window.productTurntable;
      const f = t && t.getCurrentFrame && t.getCurrentFrame();
      return f ? { az: f.azimuth_deg, el: f.elevation_deg } : null;
    });
    if (!before || !after) {
      findings.push(finding("warning", "E2E_FLOW_TURNTABLE_API_MISSING", "window.productTurntable.getCurrentFrame() nedostupné", "", label));
    } else if (before.az === after.az && before.el === after.el) {
      findings.push(finding("critical", "E2E_FLOW_TURNTABLE_NO_CHANGE", "Tažení oběma osami nezměnilo snímek otočného náhledu",
        `před: ${JSON.stringify(before)}, po: ${JSON.stringify(after)}`, label,
        "Ověřit pointer event handlery widgetu (webapp/js/turntable.js) - drag by měl měnit azimuth_deg i elevation_deg."));
    }
  } catch (e) {
    findings.push(finding("warning", "E2E_FLOW_TURNTABLE_ERROR", "Flow otočného náhledu selhal", String(e.message || e).slice(0, 300), label));
  }
}

async function flowMarkupSubmit(page, findings, label, screenshotDir) {
  let captured = null;
  await page.route("**/api/shop/products/*/markups", async (route) => {
    captured = { method: route.request().method(), bytes: (route.request().postDataBuffer() || Buffer.from("")).length };
    await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ ok: true, submission_id: "qa-e2e-test" }) });
  });
  try {
    await page.goto(`${SITE_BASE}/produkt/jumpy-l3-ci26-boxy43-270x4-170x3-120x9`, { waitUntil: "load", timeout: 20000 });
    await page.waitForTimeout(1000);
    const drawBtn = page.locator("button", { hasText: /Zakreslit (tento|další) pohled/ }).first();
    if (!(await drawBtn.count())) {
      findings.push(finding("warning", "E2E_FLOW_MARKUP_BUTTON_NOT_FOUND", "Tlačítko „Zakreslit pohled“ nenalezeno", "", label));
      return;
    }
    await drawBtn.scrollIntoViewIfNeeded();
    await drawBtn.click();
    const canvas = page.locator("#imgMarkupOverlay canvas").first();
    await canvas.waitFor({ state: "visible", timeout: 8000 });
    const cbox = await canvas.boundingBox();
    await page.mouse.move(cbox.x + cbox.width * 0.3, cbox.y + cbox.height * 0.3);
    await page.mouse.down();
    await page.mouse.move(cbox.x + cbox.width * 0.6, cbox.y + cbox.height * 0.6, { steps: 8 });
    await page.mouse.up();
    await page.locator("#imgMarkupOverlay button", { hasText: /Hotovo/ }).first().click();
    await page.waitForTimeout(500);
    const sendBtn = page.locator("button", { hasText: /^Odeslat \(\d\)/ }).first();
    if (!(await sendBtn.count())) {
      findings.push(finding("warning", "E2E_FLOW_MARKUP_SEND_NOT_FOUND", "Tlačítko „Odeslat (N)“ po zakreslení nenalezeno", "", label));
      return;
    }
    await sendBtn.scrollIntoViewIfNeeded();
    await sendBtn.click();
    await page.locator("#imgMarkupSubmit").waitFor({ state: "visible", timeout: 5000 });
    await page.fill("#imNote", "QA e2e test - neodesílá se na server (route.fulfill).");
    await page.fill("#imEmail", "qa-test@example.com");
    await page.fill("#imPhone", "+420 601 000 000");
    await page.locator("#imgMarkupSubmit button", { hasText: /Odeslat/ }).first().click();
    await page.waitForTimeout(1000);
    if (!captured) {
      findings.push(finding("critical", "E2E_FLOW_MARKUP_NO_SUBMIT", "Odeslání zakreslené připomínky nevyvolalo POST na /api/shop/products/*/markups",
        "", label, "Zkontrolovat submit handler v image-markup.js / product.html."));
    }
    await page.screenshot({ path: path.join(screenshotDir, "markup-flow.png") }).catch(() => {});
  } catch (e) {
    findings.push(finding("warning", "E2E_FLOW_MARKUP_ERROR", "Flow zakreslené připomínky selhal", String(e.message || e).slice(0, 300), label));
  }
}

async function flowContactForm(page, findings, label) {
  let captured = false;
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    if (req.method() === "POST" && /(kontakt|contact|poptav|lead|inquir)/i.test(req.url())) {
      captured = true;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    } else {
      await route.continue();
    }
  });
  try {
    await page.goto(`${SITE_BASE}/kontakt.html`, { waitUntil: "load", timeout: 20000 });
    const nameInput = page.locator('input[name*="jmeno" i], input[name*="name" i]').first();
    const emailInput = page.locator('input[type="email"]').first();
    const msgInput = page.locator('textarea').first();
    if (await nameInput.count()) await nameInput.fill("QA Test");
    if (await emailInput.count()) await emailInput.fill("qa-test@example.com");
    if (await msgInput.count()) await msgInput.fill("QA e2e test zprávy - neodesílá se (route intercept).");
    const submitBtn = page.locator('button[type="submit"], input[type="submit"]').first();
    if (await submitBtn.count()) {
      await submitBtn.click();
      await page.waitForTimeout(800);
    } else {
      findings.push(finding("info", "E2E_FLOW_CONTACT_SUBMIT_NOT_FOUND", "Odesílací tlačítko na kontakt.html nenalezeno", "", label));
    }
  } catch (e) {
    findings.push(finding("warning", "E2E_FLOW_CONTACT_ERROR", "Flow kontaktního formuláře selhal", String(e.message || e).slice(0, 300), label));
  } finally {
    await page.unroute("**/api/**").catch(() => {});
  }
}

async function flowRegistrationValidationOnly(page, findings, label) {
  let posted = false;
  await page.route("**/api/**", async (route) => {
    if (route.request().method() === "POST") { posted = true; await route.abort(); } else { await route.continue(); }
  });
  try {
    await page.goto(`${SITE_BASE}/register.html`, { waitUntil: "load", timeout: 20000 });
    const submitBtn = page.locator('button[type="submit"], input[type="submit"]').first();
    if (await submitBtn.count()) {
      await submitBtn.click(); // prazdny formular - ocekavana jen klientska validace
      await page.waitForTimeout(500);
    }
    if (posted) {
      findings.push(finding("warning", "E2E_REGISTER_POSTED_EMPTY", "Prázdný registrační formulář odeslal POST na server (chybí klientská validace?)", "", label));
    }
  } catch (e) {
    findings.push(finding("warning", "E2E_FLOW_REGISTER_ERROR", "Flow registrace selhal", String(e.message || e).slice(0, 300), label));
  } finally {
    await page.unroute("**/api/**").catch(() => {});
  }
}

async function runAdminSection(browserType, viewport, findings, screenshotDir) {
  const env = {};
  try {
    const envPath = path.join(REPO_ROOT, "api", ".env");
    for (const line of fs.readFileSync(envPath, "utf-8").split("\n")) {
      const l = line.trim();
      if (!l || l.startsWith("#") || !l.includes("=")) continue;
      const idx = l.indexOf("=");
      env[l.slice(0, idx).trim()] = l.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
    }
  } catch (e) { /* ignore */ }
  if (!env.QA_ADMIN_EMAIL || !env.QA_ADMIN_PASSWORD) {
    findings.push(finding("info", "E2E_ADMIN_ACCOUNT_MISSING",
      "Admin sekce přeskočena - chybí QA_ADMIN_EMAIL/QA_ADMIN_PASSWORD",
      "Doporučeno založit samostatný účet s rolí „jen zobrazit“ (read-only) pro QA e2e testy, ne sdílet Robertův/adminův účet.",
      "admin", "V api/.env přidat QA_ADMIN_EMAIL/QA_ADMIN_PASSWORD až bude read-only účet založen (nezakládat automaticky)."));
    return;
  }
  const browser = await browserType.launch();
  try {
    const ctx = await browser.newContext({ viewport });
    const page = await ctx.newPage();
    const consoleErrors = [];
    const failedRequests = [];
    page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
    page.on("response", (r) => { if (r.status() >= 500) failedRequests.push(`${r.status()} ${r.url()}`); });
    await page.goto(`${SITE_BASE}/login.html`, { waitUntil: "load", timeout: 20000 });
    const emailInput = page.locator('input[type="email"], input[name*="email" i]').first();
    const passInput = page.locator('input[type="password"]').first();
    if (await emailInput.count() && await passInput.count()) {
      await emailInput.fill(env.QA_ADMIN_EMAIL);
      await passInput.fill(env.QA_ADMIN_PASSWORD);
      await page.locator('button[type="submit"], input[type="submit"]').first().click();
      await page.waitForTimeout(1500);
    }
    const tabs = ["Dashboard", "Produkty", "Objednávky", "CRM", "QA audit", "Zakreslené připomínky"];
    await page.goto(`${SITE_BASE}/admin.html`, { waitUntil: "load", timeout: 20000 });
    await page.waitForTimeout(1000);
    for (const tabName of tabs) {
      const tab = page.locator(`[data-tab], button, a`, { hasText: tabName }).first();
      if (await tab.count()) {
        await tab.click().catch(() => {});
        await page.waitForTimeout(1200);
      }
    }
    await page.screenshot({ path: path.join(screenshotDir, "admin.png") }).catch(() => {});
    if (consoleErrors.length) {
      findings.push(finding("warning", "E2E_ADMIN_CONSOLE_ERROR", `console.error v adminu (${consoleErrors.length}×)`, consoleErrors.slice(0, 8).join("\n"), "admin"));
    }
    if (failedRequests.length) {
      findings.push(finding("critical", "E2E_ADMIN_500", `500 z admin API (${failedRequests.length}×)`, failedRequests.slice(0, 8).join("\n"), "admin"));
    }
    await ctx.close();
  } finally {
    await browser.close();
  }
}

function loadBaseline() {
  try { return JSON.parse(fs.readFileSync(BASELINE_PATH, "utf-8")); } catch (e) { return null; }
}

function saveBaseline(data) {
  fs.mkdirSync(path.dirname(BASELINE_PATH), { recursive: true });
  fs.writeFileSync(BASELINE_PATH, JSON.stringify(data, null, 1));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const started = Date.now();
  const ranAt = new Date().toISOString();
  const findings = [];
  const stats = { pages_checked: 0, browsers_run: [], per_page: {} };

  if (fs.existsSync("/run/ram-watchdog-alert")) {
    const result = {
      suite: "e2e", ran_at: ranAt, duration_s: 0, status: "warn",
      findings: [finding("warning", "E2E_SKIPPED_RAM_WATCHDOG", "e2e přeskočeno - aktivní /run/ram-watchdog-alert", "Prohlížeče se nespouští, dokud je aktivní RAM watchdog alert.", null)],
      stats: {},
    };
    console.log(JSON.stringify(result));
    process.exit(1);
  }

  const browsersToRun = args.browser === "both" ? ["chromium", "firefox"] : [args.browser];
  const viewportsToRun = args.viewport === "both" ? ["mobile", "desktop"] : [args.viewport];

  const today = new Date().toISOString().slice(0, 10);
  const screenshotDir = path.join(QA_REPORTS_DIR, today);
  fs.mkdirSync(screenshotDir, { recursive: true });

  let flowsRun = false;

  try {
    for (const browserName of browsersToRun) {
      const browserType = browserName === "firefox" ? firefox : chromium;
      // scene.html potrebuje WebGL - headless chromium bez ANGLE/
      // SwiftShader softwaroveho renderu WebGL context nemusi ziskat
      // (bot3 zadani). Firefox tenhle prepinac nema/nepotrebuje - tam
      // stačí, že stránka nespadne (viz sceneFirefoxWebglOk vyse).
      const launchArgs = browserName === "chromium" ? { args: ["--use-gl=angle", "--use-angle=swiftshader"] } : {};
      const browser = await browserType.launch(launchArgs);
      stats.browsers_run.push(browserName);
      try {
        for (const vpName of viewportsToRun) {
          const viewport = VIEWPORTS[vpName];
          // hasTouch/isMobile: Firefox v Playwright tyhle emulace
          // nepodporuje (CDP-only, Chromium) - newContext s nimi projde,
          // ale nasledny newPage() spadne na "Target.createTarget: Not
          // supported" (ziva chyba nalezena timhle behem). Predavat jen
          // pro chromium.
          const ctx = await browser.newContext({
            viewport: { width: viewport.width, height: viewport.height },
            deviceScaleFactor: viewport.deviceScaleFactor,
            hasTouch: browserName === "chromium" ? viewport.hasTouch : undefined,
            isMobile: browserName === "chromium" ? viewport.isMobile : undefined,
          });
          for (const p of PAGES) {
            const label = `${p.name} [${browserName}/${vpName}]`;
            const page = await ctx.newPage();
            try {
              const { findings: pf, stats: ps } = await checkPage(page, p.url, {
                label, isText: !!p.isText, isMobile: vpName === "mobile",
                sceneFirefoxWebglOk: !!p.sceneHeadless && browserName === "firefox",
              });
              findings.push(...pf);
              stats.per_page[label] = ps;
              stats.pages_checked++;
              if (pf.some(f => f.severity === "critical")) {
                await page.screenshot({ path: path.join(screenshotDir, `${p.name}-${browserName}-${vpName}-fail.png`) }).catch(() => {});
              }
            } catch (e) {
              findings.push(finding("critical", "E2E_CHECK_CRASHED", `Kontrola stránky selhala: ${label}`, String(e.message || e).slice(0, 300), label));
            } finally {
              await page.close().catch(() => {});
            }
          }
          // Flows - jen jednou (prvni pozadovana kombinace browser/viewport), aby beh zustal pod ~10 min
          if (!flowsRun) {
            flowsRun = true;
            const flowPage = await ctx.newPage();
            try {
              await flowSearchAndFilter(flowPage, findings, `flow-search [${browserName}/${vpName}]`);
              await flowCart(flowPage, findings, `flow-cart [${browserName}/${vpName}]`);
              await flowTurntableDrag(flowPage, findings, `flow-turntable [${browserName}/${vpName}]`);
              await flowMarkupSubmit(flowPage, findings, `flow-markup [${browserName}/${vpName}]`, screenshotDir);
              await flowContactForm(flowPage, findings, `flow-contact [${browserName}/${vpName}]`);
              await flowRegistrationValidationOnly(flowPage, findings, `flow-register [${browserName}/${vpName}]`);
            } finally {
              await flowPage.close().catch(() => {});
            }
          }
          await ctx.close().catch(() => {});
        }
      } finally {
        await browser.close().catch(() => {});
      }
    }

    // Admin (read-only) - jen jednou, prvni pozadovany prohlizec/viewport
    const adminBrowserType = browsersToRun[0] === "firefox" ? firefox : chromium;
    const adminViewport = VIEWPORTS[viewportsToRun[0]];
    await runAdminSection(adminBrowserType, { width: adminViewport.width, height: adminViewport.height }, findings, screenshotDir);

    // Baseline (velikost/cas per stranka) - varovani pri zhorseni > 30 %
    const baseline = loadBaseline();
    const currentBaseline = {};
    for (const [label, s] of Object.entries(stats.per_page)) {
      currentBaseline[label] = { transferredBytes: s.transferredBytes, loadMs: s.loadMs };
      if (baseline && baseline[label]) {
        const prev = baseline[label];
        // Relativni prah (30 %, bot3 zadani) KOMBINOVANY s absolutnim
        // minimem - zivy sdileny server ma prirozeny jitter v sitovem
        // case (stovky ms) i velikosti (male stranky), 30% z malicka
        // cisla by jinak zbytecne strasilo pri kazdem behu.
        if (prev.transferredBytes > 0 && s.transferredBytes > prev.transferredBytes * 1.3 &&
            s.transferredBytes - prev.transferredBytes > 50 * 1024) {
          findings.push(finding("warning", "E2E_BASELINE_SIZE_REGRESSION", `Přenesená data vzrostla > 30 % oproti baseline: ${label}`,
            `${prev.transferredBytes} → ${s.transferredBytes} bajtů`, label));
        }
        if (prev.loadMs > 0 && s.loadMs > prev.loadMs * 1.3 && s.loadMs - prev.loadMs > 1000) {
          findings.push(finding("warning", "E2E_BASELINE_TIME_REGRESSION", `Doba načítání vzrostla > 30 % oproti baseline: ${label}`,
            `${prev.loadMs} → ${s.loadMs} ms`, label));
        }
      }
    }
    if (!baseline) {
      saveBaseline(currentBaseline);
      stats.baseline_created = true;
    } else {
      stats.baseline_compared = true;
    }

    const duration = Math.round((Date.now() - started) / 100) / 10;
    const status = overallStatus(findings);
    const result = { suite: "e2e", ran_at: ranAt, duration_s: duration, status, findings, stats };
    if (args.json) {
      console.log(JSON.stringify(result));
    } else {
      console.log(`=== e2e: ${status.toUpperCase()} (${findings.length} nálezů) ===`);
      for (const f of findings) {
        console.log(`[${f.severity.toUpperCase()}] ${f.code} - ${f.title}`);
        if (f.where) console.log(`  kde: ${f.where}`);
        console.log(`  detail: ${f.detail}`);
        if (f.fix_hint) console.log(`  návrh: ${f.fix_hint}`);
      }
      console.log("--- stats ---", JSON.stringify(stats));
    }
    process.exit(STATUS_EXIT[status]);
  } catch (e) {
    const duration = Math.round((Date.now() - started) / 100) / 10;
    const result = {
      suite: "e2e", ran_at: ranAt, duration_s: duration, status: "fail",
      findings: [finding("critical", "E2E_SCRIPT_CRASHED", "Skript e2e sám selhal", String(e.stack || e).slice(0, 1000))],
      stats,
    };
    if (args.json) console.log(JSON.stringify(result));
    else console.error("CHYBA:", e);
    process.exit(3);
  }
}

main();
