/*
 * ImageMarkup - celoobrazovkovy kreslici modul pro "zakreslenou
 * pripominku" zakaznika na fotce produktu (Robert 2026-09-02, pres
 * bot3): zakaznik si prohlizi obrazek produktu na e-shopu a chce do
 * nej myší/prstem zakrouzkovat, dokreslit nebo skrtnout co chce jinak
 * + doprovodny text, a odeslat to jako dotaz.
 *
 * Vektorovy engine (datovy model, souradnice jako ZLOMKY 0..1 vuci
 * obrazku, canvas jako "pohled" prekreslovany z dat pri kazde zmene,
 * DPR-aware sizing, Pointer Events + min. krok mezi body) prevzat a
 * rozsireny z webapp/nabidka-online.html (~r.2021-2410 pen+number
 * engine, CSS ~r.315-329 a ~r.410-424 pointer-events vzor) - viz
 * komentare tam pro puvodni kontext. `nabidka-online.html` NENI touto
 * zmenou nijak dotcena (zadny refactor, zadna regrese nabidek) -
 * sjednoceni na sdileny modul je pripadny samostatny pozdejsi ukol.
 *
 * Tenhle modul NEVI nic o produktech/API - jen obrazek -> znacky/
 * composite -> callback. Napojeni na product.html a backend
 * (endpoint pro odeslani dotazu) dela soubezne bot14/bot16 podle
 * kontraktu (viz AGENTS_LOG.md 2026-09-02) - zadne zavislosti, zadny
 * framework, zadny externi CDN.
 *
 * **v2 (Robert 2026-09-02, upresneni): "To zakreslovani musi byt v
 * souladu s uhlem pohledu... Zajemce muze zakreslit to, co zamysli,
 * ve vice pohledech a pokazde to bude jinak."** Jedna pripominka = 1..N
 * POHLEDU (kazdy = obrazek konkretniho natoceni/fotky + znacky),
 * spolecny text + kontakt, odeslane najednou. Proto se v2 rozdelilo
 * puvodni jedno `open()` (kresleni + kontaktni formular v jednom) na
 * DVA nezavisle overlaye:
 *   - `open()` - JEN kresleni jednoho pohledu, zadny kontaktni
 *     formular. "Hotovo" preda hotovy pohled volajicimu (onDone),
 *     ktery si drzi seznam vsech pohledu v pameti (a mezitim necha
 *     zakaznika otocit otocny nahled, bot16 - modul se o otaceni
 *     NESTARA).
 *   - `openSubmitForm()` - az kdyz ma zakaznik hotovo se VSEMI
 *     pohledy, samostatny formular (nahledy pohledu + text + kontakt),
 *     ktery vse odesle najednou.
 *
 * Pouziti:
 *   const view = await new Promise((resolve) => {
 *     ImageMarkup.open({ imageUrl, title, viewLabel, initialMarks,
 *       onDone: resolve, onClose: () => resolve(null) });
 *   });
 *   // ... zopakovat pro dalsi pohledy, sbirat `view` do vlastniho pole ...
 *   ImageMarkup.openSubmitForm({
 *     views: myViews.map(v => ({ thumbUrl: URL.createObjectURL(v.composite), label: v.label })),
 *     onRemove: (i) => { myViews.splice(i, 1); },
 *     onSubmit: (contact) => fetch(...).then(...),
 *     onClose: () => {},
 *   });
 */
(function () {
  "use strict";

  const COLORS = ["#ff3a3a", "#f5c518", "#2b6cff"]; // cervena (vychozi), zluta, modra
  const COLOR_NAMES = { "#ff3a3a": "červená", "#f5c518": "žlutá", "#2b6cff": "modrá" }; // pro aria-label/title tlacitek barev
  const TOOLS = [
    { key: "pen", label: "Tužka", icon: "✏️" },
    { key: "ellipse", label: "Kroužek", icon: "⭕" },
    { key: "cross", label: "Škrtnout", icon: "✖️" },
    { key: "arrow", label: "Šipka", icon: "➡️" },
    { key: "text", label: "Text", icon: "🔤" },
  ];
  const LINE_WIDTH_FRACTION = 0.006; // zlomek SIRKY OBRAZKU - skaluje stejne na mobilu i desktopu
  const MIN_STEP_PX = 8; // min. krok mezi sbiranymi body pera (viz nabidka-online, "nejmensi radius 2mm")
  const MAX_COMPOSITE_SIDE = 1920;
  const COMPOSITE_JPEG_QUALITY = 0.9;
  const NOTE_MAX_LEN = 2000;

  let drawInst = null; // aktivni open() instance - dalsi open() pri jeste otevrene predchozi ji nejdriv uklidi
  let submitInst = null; // aktivni openSubmitForm() instance - nezavisly zivotni cyklus od drawInst

  // ---- CSS vlozene modulem samotnym (zadne zavislosti na hostitelske
  // strance) - jen jednou, i kdyz se open()/openSubmitForm() zavola
  // vickrat. Sjednocene pismo dle WORKFLOW.md bod 6: systemovy font
  // stack, 16px pro formularova pole (note/email/telefon), 13-14px
  // pripustne pro funkcni UI drobnosti (nastrojova lista - stejna
  // vyjimka jako .markup-btn/.cn-btn-* jinde v projektu). ----
  function ensureStyles() {
    if (document.getElementById("im-styles")) return;
    const style = document.createElement("style");
    style.id = "im-styles";
    style.textContent = `
/* HUD styl (Robert 2026-09-14: "styl okna HUD") - stejny jazyk jako
   zbytek webapp/product.html: useknute rohy (clip-path), --accent
   obrys s vyplnovaci animaci u primarnich tlacitek, monospace pro
   funkcni/technicke popisky, --panel-bg-2/--border-soft misto
   napevno zapsanych hex barev (tenhle soubor je pouzity jen v
   product.html, viz overeni pred restylem - zadne jine misto v
   projektu ho nesdili, takze CSS promenne stranky jsou vzdy dostupne).
   Modul zustava self-contained (vlastni <style>), jen barvy/tvary
   teď přebírají tokeny hostitelske stranky misto vlastnich. */
.im-overlay {
  position: fixed; inset: 0; z-index: 999999;
  display: flex; flex-direction: column;
  background: var(--panel-bg-2, #14181d); color: var(--text-soft, #fff);
  font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
}
.im-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; background: var(--panel-bg, #1c2128); color: var(--text-soft, #fff);
  flex-shrink: 0; gap: 10px; border-bottom: 1px solid var(--border-soft, #3a4250);
}
.im-title-wrap { min-width: 0; overflow: hidden; }
.im-title { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.im-viewlabel {
  font-family: "SF Mono","Cascadia Code","Consolas",monospace; font-size: 11px; letter-spacing: .05em;
  color: var(--text-muted, #9aa4b2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.im-stage { position: relative; flex: 1; overflow: hidden; background: var(--panel-bg-2, #14181d); touch-action: none; }
.im-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; pointer-events: none; }
.im-canvas { position: absolute; touch-action: none; cursor: crosshair; }
.im-toolbar {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  padding: 8px; background: var(--panel-bg, #1c2128); flex-shrink: 0;
  border-top: 1px solid var(--border-soft, #3a4250);
}
.im-btn {
  appearance: none; border: 1px solid var(--border-soft, #3a4250); background: var(--panel-bg-2, #262c35);
  color: var(--text-soft, #fff); border-radius: 0; padding: 10px 12px; font-size: 12.5px; font-weight: 700;
  letter-spacing: .02em; font-family: inherit; cursor: pointer; min-height: 44px;
  clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px));
}
.im-btn.im-active { background: var(--accent, #3b6ef5); border-color: var(--accent, #3b6ef5); color: #06140c; }
.im-btn:disabled { opacity: .6; cursor: default; }
.im-close-btn { background: transparent; border: none; min-height: 44px; flex-shrink: 0; clip-path: none; }
.im-close-btn-bottom { background: transparent; color: var(--error, #ff6b6b); border-color: var(--error, #ff6b6b); }
.im-close-btn-bottom:hover { background: var(--error, #ff6b6b); color: #06140c; }
.im-done-btn { background: transparent; color: var(--success, #2b9a5c); border-color: var(--success, #2b9a5c); }
.im-done-btn:hover { background: var(--success, #2b9a5c); color: #06140c; }
.im-submit-btn { background: transparent; color: var(--success, #2b9a5c); border-color: var(--success, #2b9a5c); width: 100%; transition: background-color .18s ease, color .18s ease; }
.im-submit-btn:hover { background: var(--success, #2b9a5c); color: #06140c; }
.im-colors { display: flex; gap: 8px; align-items: center; padding: 0 4px; }
.im-color-btn {
  width: 32px; height: 32px; border-radius: 50%; border: 2px solid transparent;
  cursor: pointer; padding: 0;
}
.im-color-btn.im-active { border-color: var(--text-soft, #fff); box-shadow: 0 0 0 2px var(--accent, #3b6ef5); }
.im-submit-body { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 16px; }
.im-views-row { display: flex; flex-wrap: wrap; gap: 10px; }
/* Nahledy zakreslenych pohledu v kontaktnim formulari - stejne
   zvetseni jako .pd-markup-view-thumb v product.html (Robert
   2026-09-14: "nech je to vetsi... nemui si vsimnout"). */
.im-view-thumb { position: relative; width: 140px; }
.im-view-thumb img {
  width: 140px; height: 140px; object-fit: cover; display: block; background: var(--panel-bg-2, #262c35);
  border: 1px solid var(--border-soft, #3a4250);
  clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px));
}
.im-view-label {
  font-size: 12px; color: var(--text-muted, #9aa4b2); margin-top: 5px; text-align: center;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.im-view-remove {
  position: absolute; top: -6px; right: -6px; width: 24px; height: 24px; border-radius: 0;
  border: 1px solid var(--error, #ff3a3a); background: var(--panel-bg, #1c2128); color: var(--error, #ff3a3a);
  font-size: 13px; line-height: 22px; padding: 0; cursor: pointer;
  clip-path: polygon(0 0, calc(100% - 5px) 0, 100% 5px, 100% 100%, 5px 100%, 0 calc(100% - 5px));
}
.im-panel { display: flex; flex-direction: column; gap: 6px; }
.im-input {
  width: 100%; box-sizing: border-box; padding: 10px 12px; font-size: 16px;
  font-family: inherit; border-radius: 0; border: 1px solid var(--border-soft, #3a4250);
  background: var(--panel-bg-2, #262c35); color: var(--text-soft, #fff); resize: vertical; margin-top: 10px;
}
.im-panel .im-input:first-child { margin-top: 0; }
.im-input:focus-visible { outline: 2px solid var(--accent, #3b6ef5); outline-offset: 1px; }
.im-field-error { font-size: 12.5px; color: var(--error, #ff6b6b); min-height: 15px; }
.im-status { font-size: 13px; min-height: 18px; margin-top: 4px; }
.im-status-error { color: var(--error, #ff6b6b); }
.im-status-ok { color: var(--success, #4ade80); }
.im-text-popover {
  position: fixed; z-index: 1000000; background: var(--panel-bg, #fff); border: 1px solid var(--border-soft, #3a4250);
  box-shadow: 0 6px 18px rgba(0,0,0,.35); padding: 8px; display: flex; gap: 6px;
  width: 220px; box-sizing: border-box;
}
.im-text-popover input {
  flex: 1; min-width: 0; padding: 7px 9px; font-size: 16px; font-family: inherit;
  border: 1px solid var(--border-soft, #cbd5e1); border-radius: 0;
  background: var(--panel-bg-2, #fff); color: var(--text-soft, #000);
}
.im-text-popover button {
  appearance: none; border: 1px solid var(--accent, #3b6ef5); background: transparent; color: var(--accent, #3b6ef5);
  font-weight: 700; border-radius: 0; padding: 7px 12px; cursor: pointer; font-family: inherit;
}
.im-text-popover button:hover { background: var(--accent, #3b6ef5); color: #06140c; }
@media (min-width: 720px) {
  .im-toolbar { justify-content: center; }
  .im-submit-body { max-width: 480px; margin: 0 auto; width: 100%; }
}
`;
    document.head.appendChild(style);
  }

  // ---- a11y: Escape zavira overlay, Tab je uvnitr uzamcen (focus trap) ----
  // Zivy nalez (bot3 2026-09-02): overlay nemel zadnou klavesovou cestu
  // ven krome kliknuti na "Zavřít" (Escape fungoval jen uvnitr textoveho
  // popoveru), Tab mohl utect na prvky pod overlay. Sdileno mezi
  // createDrawInstance i createSubmitInstance - vraci cleanup funkci pro
  // volani z destroy().
  function wireOverlayA11y(overlay, closeBtn) {
    function focusables() {
      return Array.from(overlay.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      ));
    }
    function onKeydown(ev) {
      if (ev.key === "Escape") {
        ev.preventDefault();
        closeBtn.click();
        return;
      }
      if (ev.key !== "Tab") return;
      const els = focusables();
      if (!els.length) return;
      const first = els[0], last = els[els.length - 1];
      if (ev.shiftKey && document.activeElement === first) {
        ev.preventDefault(); last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault(); first.focus();
      }
    }
    overlay.addEventListener("keydown", onKeydown);
    closeBtn.focus();
    return () => overlay.removeEventListener("keydown", onKeydown);
  }

  // ---- pomocne funkce souradnic (fractions <-> viewport px) ----

  function computeContainRect(container, naturalW, naturalH) {
    // Rucni "object-fit: contain" vypocet - potrebujeme SKUTECNY
    // vykresleny obdelnik obrazku (s letterboxem), ne box <img>
    // elementu samotneho (ten muze byt vetsi/mensi nez obrazek).
    const cw = container.clientWidth, ch = container.clientHeight;
    if (!naturalW || !naturalH || !cw || !ch) return null;
    const scale = Math.min(cw / naturalW, ch / naturalH);
    const w = naturalW * scale, h = naturalH * scale;
    const containerRect = container.getBoundingClientRect();
    return {
      left: containerRect.left + (cw - w) / 2,
      top: containerRect.top + (ch - h) / 2,
      width: w, height: h,
    };
  }

  function fracFromClient(refRect, clientX, clientY) {
    return {
      x: Math.min(1, Math.max(0, (clientX - refRect.left) / refRect.width)),
      y: Math.min(1, Math.max(0, (clientY - refRect.top) / refRect.height)),
    };
  }

  // Zamek scrollu pozadi behem overlaye (bot5, 2026-09-15, Robert na
  // iPhonu: "Zakreslovani tuzkou... se mi na mobilu zatuhne"). Samotne
  // `overflow:hidden` na body/html (puvodni kod) NESTACI na iOS Safari -
  // znamy WebKit problem, kdy stranka pod overlayem porad reaguje na
  // dotykove gesto (rubber-band scroll), i kdyz ma overflow:hidden - na
  // desktopu/Chromium (i mobilni emulaci) se to neprojevi, proto to
  // neodhalila zadna z mych zivych zkousek pres Playwright (jen chromium
  // je tu nainstalovany, realny WebKit engine k dispozici nemam). Standardni
  // oprava: navic `position:fixed` s ulozenou/obnovenou pozici scrollu -
  // tim stranka pod overlayem fyzicky NEJDE posunout vubec, misto
  // spolehnuti na overflow, ktere iOS obchazi.
  function lockBodyScroll(self) {
    self.prevBodyOverflow = document.body.style.overflow;
    self.prevHtmlOverflow = document.documentElement.style.overflow;
    self.prevBodyPosition = document.body.style.position;
    self.prevBodyTop = document.body.style.top;
    self.prevBodyWidth = document.body.style.width;
    self.prevScrollY = window.scrollY || window.pageYOffset || 0;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.body.style.position = "fixed";
    document.body.style.top = `-${self.prevScrollY}px`;
    document.body.style.width = "100%";
  }

  function unlockBodyScroll(self) {
    document.body.style.overflow = self.prevBodyOverflow;
    document.documentElement.style.overflow = self.prevHtmlOverflow;
    document.body.style.position = self.prevBodyPosition;
    document.body.style.top = self.prevBodyTop;
    document.body.style.width = self.prevBodyWidth;
    window.scrollTo(0, self.prevScrollY);
  }

  // ---- vykresleni jedne znacky do libovolneho 2D kontextu, kde
  // (0,0)-(w,h) odpovida CELE ploše obrazku (CSS px nebo natural px -
  // volajici uz nastavil transform/scale podle potreby). ----

  function drawMark(ctx, w, h, mark) {
    const color = mark.color || COLORS[0];
    const lineWidth = Math.max(1, (mark.width || LINE_WIDTH_FRACTION) * w);
    const toPx = (p) => ({ x: p.x * w, y: p.y * h });

    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    if (mark.kind === "pen") {
      const pts = mark.points.map(toPx);
      if (!pts.length) return;
      ctx.beginPath();
      if (pts.length < 3) {
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
      } else {
        // Vyhlazena stopa - retez kvadratickych krivek pres stredy
        // usecek, body slouzi jako ridici (viz nabidka-online.html).
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length - 1; i++) {
          const midX = (pts[i].x + pts[i + 1].x) / 2;
          const midY = (pts[i].y + pts[i + 1].y) / 2;
          ctx.quadraticCurveTo(pts[i].x, pts[i].y, midX, midY);
        }
        ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
      }
      ctx.stroke();
    } else if (mark.kind === "ellipse") {
      if (mark.points.length < 2) return;
      const a = toPx(mark.points[0]), b = toPx(mark.points[1]);
      const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const rx = Math.abs(b.x - a.x) / 2, ry = Math.abs(b.y - a.y) / 2;
      ctx.beginPath();
      ctx.ellipse(cx, cy, Math.max(rx, 1), Math.max(ry, 1), 0, 0, Math.PI * 2);
      ctx.stroke();
    } else if (mark.kind === "cross") {
      if (mark.points.length < 2) return;
      const a = toPx(mark.points[0]), b = toPx(mark.points[1]);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      ctx.moveTo(b.x, a.y); ctx.lineTo(a.x, b.y);
      ctx.stroke();
    } else if (mark.kind === "arrow") {
      if (mark.points.length < 2) return;
      const a = toPx(mark.points[0]), b = toPx(mark.points[1]);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      ctx.stroke();
      const angle = Math.atan2(b.y - a.y, b.x - a.x);
      const headLen = Math.max(12, lineWidth * 4);
      const headAngle = Math.PI / 7;
      ctx.beginPath();
      ctx.moveTo(b.x, b.y);
      ctx.lineTo(b.x - headLen * Math.cos(angle - headAngle), b.y - headLen * Math.sin(angle - headAngle));
      ctx.lineTo(b.x - headLen * Math.cos(angle + headAngle), b.y - headLen * Math.sin(angle + headAngle));
      ctx.closePath();
      ctx.fill();
    } else if (mark.kind === "text" && mark.text) {
      const p = toPx(mark.points[0]);
      const fontPx = Math.max(14, w * 0.022);
      ctx.font = `700 ${fontPx}px -apple-system, "Segoe UI", Roboto, Arial, sans-serif`;
      ctx.textBaseline = "top";
      const lines = String(mark.text).split("\n");
      const lineH = fontPx * 1.25;
      const wMax = Math.max(...lines.map((l) => ctx.measureText(l).width));
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.fillRect(p.x - 4, p.y - 3, wMax + 8, lines.length * lineH + 6);
      ctx.fillStyle = color;
      lines.forEach((l, i) => ctx.fillText(l, p.x, p.y + i * lineH));
    }
  }

  // ---- kreslici overlay (open) ----

  function createDrawInstance(opts) {
    const self = {
      opts,
      marks: Array.isArray(opts.initialMarks) ? opts.initialMarks.map((m) => Object.assign({}, m)) : [],
      tool: "pen",
      color: COLORS[0],
      naturalW: 0, naturalH: 0,
      stroke: null, // rozpracovana pen-cara (fractions)
      dragStart: null, // rozpracovany ellipse/cross/arrow (fraction bod)
      dragCurrent: null,
      prevBodyOverflow: "", prevHtmlOverflow: "",
      prevBodyPosition: "", prevBodyTop: "", prevBodyWidth: "", prevScrollY: 0,
    };

    // ---- DOM ----
    const overlay = document.createElement("div");
    overlay.className = "im-overlay";
    overlay.id = "imgMarkupOverlay";

    const topbar = document.createElement("div");
    topbar.className = "im-topbar";
    const titleWrap = document.createElement("div");
    titleWrap.className = "im-title-wrap";
    const titleEl = document.createElement("div");
    titleEl.className = "im-title";
    titleEl.textContent = opts.title || "";
    titleWrap.appendChild(titleEl);
    if (opts.viewLabel) {
      const viewLabelEl = document.createElement("div");
      viewLabelEl.className = "im-viewlabel";
      viewLabelEl.textContent = opts.viewLabel;
      titleWrap.appendChild(viewLabelEl);
    }
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "im-btn im-close-btn";
    closeBtn.textContent = "✕ Zavřít";
    topbar.appendChild(titleWrap);
    topbar.appendChild(closeBtn);

    const stage = document.createElement("div");
    stage.className = "im-stage";
    const img = document.createElement("img");
    img.className = "im-img";
    img.alt = "";
    const canvas = document.createElement("canvas");
    canvas.className = "im-canvas";
    stage.appendChild(img);
    stage.appendChild(canvas);

    const toolbar = document.createElement("div");
    toolbar.className = "im-toolbar";
    // Zavřít i tady dole, ne jen v horní liště (Robert 2026-09-15, po
    // vlastnim vyzkouseni: "zavrit ma prilis bokem" - na sirsich
    // obrazovkach je horni "✕ Zavřít" maly a osamoceny v rohu, daleko
    // od pozornosti/palce uzivatele, ktera je celou dobu dole u
    // nastroju). Stejny handler jako horni tlacitko (viz onCloseClick nize).
    const closeBtnBottom = document.createElement("button");
    closeBtnBottom.type = "button";
    closeBtnBottom.className = "im-btn im-close-btn-bottom";
    closeBtnBottom.textContent = "✕ Zavřít";
    toolbar.appendChild(closeBtnBottom);
    const toolBtns = {};
    TOOLS.forEach((t) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "im-btn im-tool-btn";
      b.textContent = `${t.icon} ${t.label}`;
      b.dataset.tool = t.key;
      toolBtns[t.key] = b;
      toolbar.appendChild(b);
    });
    const colorWrap = document.createElement("div");
    colorWrap.className = "im-colors";
    const colorBtns = COLORS.map((c) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "im-color-btn";
      b.style.background = c;
      b.dataset.color = c;
      // a11y (bot3 2026-09-02): jen barevny ctverecek bez textu nemel
      // pristupny nazev vubec - ctecka obrazovky by ohlasila jen "button".
      b.setAttribute("aria-label", `Barva: ${COLOR_NAMES[c] || c}`);
      b.title = COLOR_NAMES[c] || c;
      colorWrap.appendChild(b);
      return b;
    });
    toolbar.appendChild(colorWrap);
    const undoBtn = document.createElement("button");
    undoBtn.type = "button";
    undoBtn.className = "im-btn im-undo-btn";
    undoBtn.textContent = "↩️ Zpět";
    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "im-btn im-clear-btn";
    clearBtn.textContent = "🗑️ Vymazat";
    const doneBtn = document.createElement("button");
    doneBtn.type = "button";
    doneBtn.className = "im-btn im-done-btn";
    doneBtn.textContent = "✔️ Hotovo";
    toolbar.appendChild(undoBtn);
    toolbar.appendChild(clearBtn);
    toolbar.appendChild(doneBtn);

    overlay.appendChild(topbar);
    overlay.appendChild(stage);
    overlay.appendChild(toolbar);
    document.body.appendChild(overlay);
    const cleanupA11y = wireOverlayA11y(overlay, closeBtn);

    Object.assign(self, { overlay, stage, img, canvas, toolbar, toolBtns, colorBtns, undoBtn, clearBtn, doneBtn });

    // ---- canvas sizing (letterbox rect + DPR) ----
    function resizeCanvas() {
      const rect = computeContainRect(stage, self.naturalW, self.naturalH);
      if (!rect) return;
      const stageRect = stage.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.style.left = (rect.left - stageRect.left) + "px";
      canvas.style.top = (rect.top - stageRect.top) + "px";
      canvas.style.width = rect.width + "px";
      canvas.style.height = rect.height + "px";
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      self._refRect = rect;
      self._cssW = rect.width;
      self._cssH = rect.height;
      redraw();
    }

    function redraw() {
      if (!self._cssW || !self._cssH) return;
      const ctx = canvas.getContext("2d");
      const dpr = window.devicePixelRatio || 1;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, self._cssW, self._cssH);
      self.marks.forEach((m) => drawMark(ctx, self._cssW, self._cssH, m));
      if (self.tool !== "pen" && self.dragStart && self.dragCurrent) {
        drawMark(ctx, self._cssW, self._cssH, {
          kind: self.tool, color: self.color, width: LINE_WIDTH_FRACTION,
          points: [self.dragStart, self.dragCurrent],
        });
      }
      if (self.tool === "pen" && self.stroke && self.stroke.length > 1) {
        drawMark(ctx, self._cssW, self._cssH, {
          kind: "pen", color: self.color, width: LINE_WIDTH_FRACTION, points: self.stroke,
        });
      }
    }

    function updateToolbarUi() {
      TOOLS.forEach((t) => toolBtns[t.key].classList.toggle("im-active", self.tool === t.key));
      colorBtns.forEach((b) => b.classList.toggle("im-active", b.dataset.color === self.color));
    }

    // ---- pointer handlery ----
    canvas.addEventListener("pointerdown", (e) => {
      if (!e.isPrimary) return; // druhy prst/pero nesmi kreslit soubezne
      e.preventDefault();
      const f = fracFromClient(self._refRect, e.clientX, e.clientY);
      if (self.tool === "text") {
        openTextInput(e.clientX, e.clientY, f);
        return;
      }
      try { canvas.setPointerCapture(e.pointerId); } catch (err) {}
      if (self.tool === "pen") {
        self.stroke = [f];
      } else {
        self.dragStart = f;
        self.dragCurrent = f;
      }
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!e.isPrimary) return;
      if (self.tool === "pen" && self.stroke) {
        const last = self.stroke[self.stroke.length - 1];
        const dxPx = (e.clientX - self._refRect.left) - last.x * self._refRect.width;
        const dyPx = (e.clientY - self._refRect.top) - last.y * self._refRect.height;
        if (Math.hypot(dxPx, dyPx) < MIN_STEP_PX) return;
        self.stroke.push(fracFromClient(self._refRect, e.clientX, e.clientY));
        if (self.stroke.length > 800) self.stroke.splice(0, self.stroke.length - 800);
        redraw();
      } else if (self.dragStart) {
        self.dragCurrent = fracFromClient(self._refRect, e.clientX, e.clientY);
        redraw();
      }
    });
    function finishDraw() {
      if (self.tool === "pen" && self.stroke) {
        if (self.stroke.length > 1) {
          self.marks.push({ kind: "pen", color: self.color, width: LINE_WIDTH_FRACTION, points: self.stroke });
        }
        self.stroke = null;
        redraw();
      } else if (self.dragStart && self.dragCurrent) {
        self.marks.push({
          kind: self.tool, color: self.color, width: LINE_WIDTH_FRACTION,
          points: [self.dragStart, self.dragCurrent],
        });
        self.dragStart = null; self.dragCurrent = null;
        redraw();
      }
    }
    canvas.addEventListener("pointerup", (e) => { if (e.isPrimary) finishDraw(); });
    canvas.addEventListener("pointercancel", (e) => {
      if (!e.isPrimary) return;
      self.stroke = null; self.dragStart = null; self.dragCurrent = null;
      redraw();
    });

    // Kratky inline vstup textu u ťuknuti (Robert: "Text (ťuknutí ->
    // kratky inline input)").
    function openTextInput(clientX, clientY, f) {
      const old = overlay.querySelector(".im-text-popover");
      if (old) old.remove();
      const pop = document.createElement("div");
      pop.className = "im-text-popover";
      const left = Math.max(8, Math.min(clientX, window.innerWidth - 8 - 220));
      const top = Math.max(8, Math.min(clientY, window.innerHeight - 8 - 90));
      pop.style.left = left + "px";
      pop.style.top = top + "px";
      const input = document.createElement("input");
      input.type = "text";
      input.maxLength = 120;
      input.placeholder = "Text…";
      const ok = document.createElement("button");
      ok.type = "button";
      ok.textContent = "OK";
      pop.appendChild(input);
      pop.appendChild(ok);
      overlay.appendChild(pop);
      // `closed` je nutny strazny flag - bez nej mohl Enter zavrit popover
      // driv, nez stihl doběhnout 50ms setTimeout nize, a pozdeji
      // pridany "klik mimo = zavrit" posluchac pak reagoval na UPLNE
      // JINY, nesouvisejici klik kdekoli na strance (napr. na tlacitko
      // Zpet) - `pop` uz byl odpojeny z DOM, takze `pop.contains(cíl)`
      // vzdy vratilo false, coz vypadalo jako "klik mimo" a `done(true)`
      // se zavolalo DRUHY KRAT, pridalo duplicitni znacku (nalezeno
      // Playwright testem, ne teoreticky).
      let closed = false;
      let outsideCloser = null;
      const done = (save) => {
        if (closed) return;
        closed = true;
        const v = input.value.trim();
        if (save && v) {
          self.marks.push({ kind: "text", color: self.color, width: LINE_WIDTH_FRACTION, points: [f], text: v.slice(0, 120) });
          redraw();
        }
        pop.remove();
        if (outsideCloser) document.removeEventListener("pointerdown", outsideCloser, true);
      };
      ok.addEventListener("click", () => done(true));
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") done(true);
        if (ev.key === "Escape") done(false);
      });
      setTimeout(() => {
        if (closed) return; // uz zavreno (Enter/Escape) drive, nez timeout dobehl
        outsideCloser = (ev) => { if (!pop.contains(ev.target)) done(true); };
        document.addEventListener("pointerdown", outsideCloser, true);
      }, 50);
      input.focus();
    }

    // ---- ovladaci prvky ----
    TOOLS.forEach((t) => {
      toolBtns[t.key].addEventListener("click", () => {
        self.tool = t.key;
        self.stroke = null; self.dragStart = null; self.dragCurrent = null;
        updateToolbarUi();
      });
    });
    colorBtns.forEach((b) => {
      b.addEventListener("click", () => { self.color = b.dataset.color; updateToolbarUi(); });
    });
    undoBtn.addEventListener("click", () => {
      self.marks.pop();
      redraw();
    });
    clearBtn.addEventListener("click", () => {
      if (self.marks.length && !window.confirm("Vymazat všechny značky?")) return;
      self.marks = [];
      redraw();
    });
    // Zavirani BEZ ulozeni (v2: kontaktni formular uz neni soucasti
    // teto obrazovky, viz hlavicka souboru) - kdyz uz neco nakreslil,
    // potvrdit, at prijde o rozdelanou znacku jen zamerne. Sdileno mezi
    // hornim (closeBtn) i spodnim (closeBtnBottom) tlacitkem - viz
    // komentar u closeBtnBottom vys.
    function onCloseClick() {
      if (self.marks.length && !window.confirm("Zahodit zákres?")) return;
      destroy(false);
    }
    closeBtn.addEventListener("click", onCloseClick);
    closeBtnBottom.addEventListener("click", onCloseClick);
    doneBtn.addEventListener("click", async () => {
      doneBtn.disabled = true;
      try {
        const { blob, w, h } = await buildComposite();
        destroy(true, { marks: self.marks, image_w: w, image_h: h, composite: blob });
      } finally {
        doneBtn.disabled = false;
      }
    });

    window.addEventListener("resize", resizeCanvas);

    async function buildComposite() {
      const scale = Math.min(1, MAX_COMPOSITE_SIDE / Math.max(self.naturalW, self.naturalH));
      const w = Math.max(1, Math.round(self.naturalW * scale));
      const h = Math.max(1, Math.round(self.naturalH * scale));
      const off = document.createElement("canvas");
      off.width = w; off.height = h;
      const ctx = off.getContext("2d");
      ctx.drawImage(img, 0, 0, w, h);
      self.marks.forEach((m) => drawMark(ctx, w, h, m));
      const blob = await new Promise((resolve) => off.toBlob(resolve, "image/jpeg", COMPOSITE_JPEG_QUALITY));
      return { blob, w, h };
    }

    // ---- scroll lock ----
    lockBodyScroll(self);

    function destroy(viaDone, viewPayload) {
      window.removeEventListener("resize", resizeCanvas);
      cleanupA11y();
      unlockBodyScroll(self);
      overlay.remove();
      if (drawInst === self) drawInst = null;
      if (viaDone) {
        if (typeof opts.onDone === "function") opts.onDone(viewPayload);
      } else if (typeof opts.onClose === "function") {
        opts.onClose();
      }
    }
    self.destroy = () => destroy(false);

    // ---- nacteni obrazku ----
    img.addEventListener("load", () => {
      self.naturalW = img.naturalWidth;
      self.naturalH = img.naturalHeight;
      resizeCanvas();
    });
    img.src = opts.imageUrl;

    updateToolbarUi();
    return self;
  }

  // ---- formular "Odeslat pripominku" (openSubmitForm) ----

  function validateEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
  }
  function validatePhone(v) {
    const cleaned = v.replace(/[\s+-]/g, "");
    return /^\d{9,}$/.test(cleaned);
  }

  function createSubmitInstance(opts) {
    const self = {
      opts,
      views: Array.isArray(opts.views) ? opts.views.slice() : [],
      prevBodyOverflow: "", prevHtmlOverflow: "",
      prevBodyPosition: "", prevBodyTop: "", prevBodyWidth: "", prevScrollY: 0,
    };

    const overlay = document.createElement("div");
    overlay.className = "im-overlay";
    overlay.id = "imgMarkupSubmit";

    const topbar = document.createElement("div");
    topbar.className = "im-topbar";
    const titleEl = document.createElement("div");
    titleEl.className = "im-title";
    titleEl.textContent = "Odeslat připomínku";
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "im-btn im-close-btn";
    closeBtn.textContent = "✕ Zavřít";
    topbar.appendChild(titleEl);
    topbar.appendChild(closeBtn);

    const body = document.createElement("div");
    body.className = "im-submit-body";

    const viewsRow = document.createElement("div");
    viewsRow.className = "im-views-row";

    const panel = document.createElement("div");
    panel.className = "im-panel";

    const noteEl = document.createElement("textarea");
    noteEl.id = "imNote";
    noteEl.className = "im-input im-note";
    noteEl.rows = 3;
    noteEl.maxLength = NOTE_MAX_LEN;
    noteEl.placeholder = "Co byste chtěli jinak?";
    const noteErr = document.createElement("div");
    noteErr.className = "im-field-error";

    const emailEl = document.createElement("input");
    emailEl.type = "email";
    emailEl.id = "imEmail";
    emailEl.className = "im-input";
    emailEl.placeholder = "E-mail";
    emailEl.required = true;
    const emailErr = document.createElement("div");
    emailErr.className = "im-field-error";

    const phoneEl = document.createElement("input");
    phoneEl.type = "tel";
    phoneEl.id = "imPhone";
    phoneEl.className = "im-input";
    phoneEl.placeholder = "Telefon";
    phoneEl.required = true;
    const phoneErr = document.createElement("div");
    phoneErr.className = "im-field-error";

    const submitBtn = document.createElement("button");
    submitBtn.type = "button";
    submitBtn.className = "im-btn im-submit-btn";
    submitBtn.textContent = "Odeslat";
    const statusEl = document.createElement("div");
    statusEl.className = "im-status";

    panel.appendChild(noteEl);
    panel.appendChild(noteErr);
    panel.appendChild(emailEl);
    panel.appendChild(emailErr);
    panel.appendChild(phoneEl);
    panel.appendChild(phoneErr);
    panel.appendChild(submitBtn);
    panel.appendChild(statusEl);

    body.appendChild(viewsRow);
    body.appendChild(panel);
    overlay.appendChild(topbar);
    overlay.appendChild(body);
    document.body.appendChild(overlay);
    const cleanupA11y = wireOverlayA11y(overlay, closeBtn);

    Object.assign(self, { overlay, viewsRow, noteEl, emailEl, phoneEl, submitBtn, statusEl });

    function renderViews() {
      viewsRow.innerHTML = "";
      self.views.forEach((v, i) => {
        const thumb = document.createElement("div");
        thumb.className = "im-view-thumb";
        const img = document.createElement("img");
        img.src = v.thumbUrl;
        img.alt = v.label || "";
        const label = document.createElement("div");
        label.className = "im-view-label";
        label.textContent = v.label || "";
        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "im-view-remove";
        removeBtn.textContent = "✕";
        removeBtn.setAttribute("aria-label", `Odebrat pohled: ${v.label || i + 1}`);
        removeBtn.addEventListener("click", () => {
          self.views.splice(i, 1);
          renderViews();
          if (typeof opts.onRemove === "function") opts.onRemove(i);
        });
        thumb.appendChild(img);
        thumb.appendChild(label);
        thumb.appendChild(removeBtn);
        viewsRow.appendChild(thumb);
      });
      submitBtn.disabled = self.views.length === 0;
    }
    renderViews();

    function clearFieldErrors() {
      noteErr.textContent = "";
      emailErr.textContent = "";
      phoneErr.textContent = "";
    }
    [noteEl, emailEl, phoneEl].forEach((el) => el.addEventListener("input", clearFieldErrors));

    // Robert 2026-09-02 (upresneni): "poznamka zustava POVINNA jako ve
    // v1 (min. 3 znaky, max 2000) - samotny kruzek bez slova admin
    // nevylozi." Povinne: pohledy >=1 (viz renderViews), poznamka,
    // e-mail, telefon.
    function validate() {
      clearFieldErrors();
      let ok = true;
      if (noteEl.value.trim().length < 3) {
        noteErr.textContent = "Popiš prosím krátce, co bys chtěl/a jinak (aspoň pár slov).";
        ok = false;
      }
      if (!validateEmail(emailEl.value)) {
        emailErr.textContent = "Zadej prosím platný e-mail.";
        ok = false;
      }
      if (!validatePhone(phoneEl.value)) {
        phoneErr.textContent = "Zadej prosím platné telefonní číslo (aspoň 9 číslic).";
        ok = false;
      }
      return ok;
    }

    closeBtn.addEventListener("click", () => destroy());
    submitBtn.addEventListener("click", onSubmitClick);

    async function onSubmitClick() {
      if (self.views.length === 0 || !validate()) return;
      statusEl.textContent = "";
      statusEl.className = "im-status";
      submitBtn.disabled = true;
      submitBtn.textContent = "Odesílám…";
      try {
        await opts.onSubmit({
          note: noteEl.value.trim(),
          email: emailEl.value.trim(),
          phone: phoneEl.value.trim(),
        });
        statusEl.textContent = "Děkujeme, ozveme se.";
        statusEl.className = "im-status im-status-ok";
        setTimeout(() => destroy(), 900);
      } catch (e) {
        statusEl.textContent = (e && e.message) || "Odeslání se nepovedlo, zkus to prosím znovu.";
        statusEl.className = "im-status im-status-error";
        submitBtn.disabled = self.views.length === 0;
        submitBtn.textContent = "Odeslat";
      }
    }

    lockBodyScroll(self);

    function destroy() {
      cleanupA11y();
      unlockBodyScroll(self);
      overlay.remove();
      if (submitInst === self) submitInst = null;
      if (typeof opts.onClose === "function") opts.onClose();
    }
    self.destroy = destroy;

    return self;
  }

  window.ImageMarkup = {
    open(opts) {
      ensureStyles();
      if (drawInst) drawInst.destroy();
      drawInst = createDrawInstance(opts || {});
      return drawInst;
    },
    openSubmitForm(opts) {
      ensureStyles();
      if (submitInst) submitInst.destroy();
      submitInst = createSubmitInstance(opts || {});
      return submitInst;
    },
  };
})();
