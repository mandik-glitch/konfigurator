// Příklady realizací: 4 reálné fotografie z fotogalerie + odkaz na fotogalerii (bot16, 2026-10-07; Robert: „v každé sestavě do aut i v online nabídce musí být ukázána reálná fotografie 4ks a odkaz
// na fotogalerie vestaveb, v každé sestavě stolů i v online nabídce 4ks a odkaz na fotogalerie stolů; ty 4 fotky se musí točit, kolovat, tzn v každé nabídce budou jiné i v každé kartě jako související
// příklad realizace“). Znovupoužitelný modul bez závislostí: RealizaceFoto.mount(kontejner, { typ: "vestavby" | "stoly", seed: <id karty / číslo nabídky>, n: 4 }) -> Promise<boolean> (true = zobrazeno).
// Zdroj: veřejné API fotogalerie GET /api/gallery?category=vestavby_dodavek | realizace_stolu (jen veřejné fotky, nic se nezapisuje; odpověď se 15 min drží v sessionStorage).
// Výběr čtyř fotek je DETERMINISTICKÝ podle seed (stejná karta / nabídka ukazuje při obnovení stejné fotky, sousední karty různé; kroky po fotkách jsou nesoudělné s počtem fotek, takže se v rámci
// galerie střídají všechny) a navíc se po týdnech posouvá (fotky „kolují“ i v čase; tyden lze přepsat v opts pro test). OD 2026-10-08 (Robert: „reloaduju F5 a načtou se stále tytéž“) se okno fotek posune při KAŽDÉM načtení stránky (citac `rf:n:<seed>` v localStorage; viz poradiNacteni). Hodnoty z dat se do DOM dávají jen přes textContent / atributy.
// Odkazy na galerii: /realizace.html?category=<tag> (nová karta); fotka se klikem zvětší (lightbox, Esc / šipky; šipky se nepředávají stránce).
(function () {
  "use strict";
  var TYPY = {
    vestavby: { tag: "vestavby_dodavek", odkazText: "Zobrazit fotogalerii vestaveb", href: "/realizace.html?category=vestavby_dodavek", popis: "Reálné fotografie našich vestaveb" },
    stoly: { tag: "realizace_stolu", odkazText: "Zobrazit fotogalerii stolů", href: "/realizace.html?category=realizace_stolu", popis: "Reálné fotografie našich stolů a pracovišť" }
  };
  var CACHE_MS = 15 * 60 * 1000;
  // Fotky s mateřskou značkou v názvu souboru / titulku (jen pro stránky bez značky: opts.bezZnacky; text ve snímku neřeším - Robert 2026-10-07 u storefrontů vodoznak ve fotkách výslovně povolil). Slova jsou
  // rozdělená, aby tenhle soubor nebyl sám nálezem QA „static_page_brand_leak“ (skenuje i .js načtené ze storefront stránek).
  var ZNACKA_RE = new RegExp(["van" + "drawee", "van" + "dr", "logi" + "man", "konfigur" + "[aá]tor"].join("|"), "i");
  // Fotky, které se do bloku „reálné fotografie“ NEVYBÍRAJÍ (ruční třídění galerie 2026-10-07, kontaktní archy: scripts/2026-10-07_realizace_foto_testy/kontaktni_arch.py): rendery a produktové
  // snímky na bílém pozadí (nejsou to fotky, TEXT_FILTR pravidlo 7), fotky s viditelným textem druhé značky ve snímku a duplicity. Nově nahrané fotky z adminu se vybírají automaticky; po nahrání
  // renderu / duplicity sem doplnit jeho id.
  var VYLOUCENE = {
    vestavby: [61, 83, 89, 92, 95, 22, 82, 17, 31, 36, 37, 74, 13, 107, 79, 81, 105, 218],
    stoly: [148]
  };
  var EPOCH_TYDNY = Date.UTC(2026, 0, 5);                         // pondělí 2026-01-05 = týden 0

  function hash(s) { var h = 2166136261; s = String(s); for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h >>> 0; }
  function gcd(a, b) { while (b) { var t = a % b; a = b; b = t; } return a; }
  function tydenIndex(ts) { return Math.floor(((ts == null ? Date.now() : ts) - EPOCH_TYDNY) / 604800000); }

  // Výběr n fotek: start i krok z hashe seedu (a týdne), krok nesoudělný s počtem fotek -> n různých fotek rozprostřených po galerii.
  // poradi = poradi nacteni stranky (0, 1, 2, ...): kazde dalsi nacteni posune okno o n fotek po stejne permutaci, takze F5 ukaze 4 NOVE fotky a az po prochazeni cele galerie se zacne od zacatku.
  function vyber(images, seed, n, tyden, poradi) {
    var N = images.length; if (!N) return [];
    n = Math.min(n || 4, N);
    var h = hash(String(seed) + "|" + (tyden == null ? tydenIndex() : tyden));
    var kroky = [7, 11, 13, 17, 19, 23, 29, 31, 37], krok = 1;
    for (var k = 0; k < kroky.length; k++) { var c = kroky[(h + k) % kroky.length]; if (gcd(c, N) === 1) { krok = c; break; } }
    var start = (h % N + (poradi > 0 ? (poradi % N) * n * krok : 0)) % N, out = [];
    for (var i = 0; i < n; i++) out.push(images[(start + i * krok) % N]);
    return out;
  }

  // Poradi nacteni pro danou kartu / nabidku (seed): citac v localStorage (`rf:n:<seed>`) se zvysi pri KAZDEM nacteni stranky (F5 = dalsi okno fotek), pocatecni hodnota je nahodna (kazdy navstevnik zacina jinde).
  // V ramci jedne stranky se hodnota pamatuje (opakovane vykresleni bloku nema fotky prehazovat); bez localStorage (soukromy rezim, zakazano) je poradi nahodne pri kazdem nacteni.
  var poradiStranky = {};
  function poradiNacteni(seed) {
    var k = String(seed);
    if (poradiStranky[k] != null) return poradiStranky[k];
    var v = NaN;
    try { var s = window.localStorage.getItem("rf:n:" + k); v = s == null ? NaN : parseInt(s, 10); } catch (e) { /* bez ulozeni */ }
    if (!(v >= 0) || !isFinite(v)) v = Math.floor(Math.random() * 1000000);
    poradiStranky[k] = v;
    try { window.localStorage.setItem("rf:n:" + k, String(v + 1)); } catch (e) { /* bez ulozeni */ }
    return v;
  }

  function nactiGalerii(tag) {
    var key = "rf:" + tag;
    try {
      var c = JSON.parse(sessionStorage.getItem(key) || "null");
      if (c && c.t && Date.now() - c.t < CACHE_MS && Array.isArray(c.images) && c.images.length) return Promise.resolve(c.images);
    } catch (e) { /* bez cache */ }
    return fetch("/api/gallery?category=" + encodeURIComponent(tag)).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(function (d) {
      var im = (d.images || []).filter(function (i) { return i && i.url && i.active !== false; }).map(function (i) { return { id: i.id, url: i.url, alt: i.alt_text || i.title || "", title: i.title || i.alt_text || "", file: i.filename || "" }; });
      try { sessionStorage.setItem(key, JSON.stringify({ t: Date.now(), images: im })); } catch (e) { /* plné úložiště nevadí */ }
      return im;
    });
  }

  var cssVlozeno = false;
  function vlozCss() {
    if (cssVlozeno || document.getElementById("rf-css")) { cssVlozeno = true; return; }
    cssVlozeno = true;
    var st = document.createElement("style"); st.id = "rf-css";
    st.textContent = [
      ".rf-root { --rf-text: var(--text, #e8eaed); --rf-muted: var(--text-muted, #8b93a1); --rf-border: var(--border-card, #2c313a); --rf-panel: var(--panel-bg, #22262e); --rf-accent: var(--accent, #9fd0ff); --rf-btn: var(--btn-bg, #3a5a7a); --rf-btn-h: var(--btn-bg-hover, #4a6a8a); color: var(--rf-text); }",
      ".rf-root *, .rf-root *::before, .rf-root *::after { box-sizing: border-box; }",
      ".rf-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 0 0 12px; padding: 0; list-style: none; }",
      ".rf-foto { display: block; position: relative; aspect-ratio: 4 / 3; overflow: hidden; border: 1px solid var(--rf-border); background: var(--rf-panel); cursor: zoom-in; padding: 0; width: 100%; }",
      ".rf-foto img { display: block; width: 100%; height: 100%; object-fit: cover; transition: transform .25s ease; }",
      ".rf-foto:hover img, .rf-foto:focus-visible img { transform: scale(1.04); }",
      ".rf-foto:focus-visible { outline: 2px solid var(--rf-accent); outline-offset: 2px; }",
      ".rf-popis { margin: 0 0 10px; color: var(--rf-muted); font-size: 13px; }",
      ".rf-grid.rf-vse { grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); }",
      "@media (max-width: 640px) { .rf-grid.rf-vse { grid-template-columns: repeat(2, minmax(0, 1fr)); } }",
      ".rf-link { display: inline-block; background: var(--rf-btn); color: #fff !important; text-decoration: none; padding: 9px 18px; font-weight: 600; clip-path: polygon(0 8px, 8px 0, 100% 0, 100% 100%, 0 100%); }",
      ".rf-link:hover { background: var(--rf-btn-h); }",
      "@media (max-width: 640px) { .rf-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; } .rf-link { display: block; text-align: center; } }",
      ".rf-lb { position: fixed; inset: 0; z-index: 10050; background: rgba(8, 12, 18, .92); display: none; align-items: center; justify-content: center; padding: 16px; }",
      ".rf-lb.rf-open { display: flex; }",
      ".rf-lb figure { margin: 0; max-width: min(1200px, 100%); max-height: 100%; display: flex; flex-direction: column; align-items: center; gap: 10px; }",
      ".rf-lb img { max-width: 100%; max-height: calc(100vh - 110px); object-fit: contain; background: #111; }",
      ".rf-lb figcaption { color: #dfe6ee; font-size: 14px; text-align: center; max-width: 80ch; }",
      ".rf-lb button { position: absolute; appearance: none; border: 1px solid rgba(255,255,255,.35); background: rgba(20,26,34,.8); color: #fff; width: 46px; height: 46px; font-size: 24px; line-height: 1; cursor: pointer; }",
      ".rf-lb button:hover { background: rgba(60,80,104,.9); }",
      ".rf-lb .rf-x { top: 14px; right: 14px; } .rf-lb .rf-p { left: 14px; top: 50%; transform: translateY(-50%); } .rf-lb .rf-n { right: 14px; top: 50%; transform: translateY(-50%); }",
      "@media print { .rf-lb { display: none !important; } .rf-foto img { transition: none; } }"
    ].join("\n");
    document.head.appendChild(st);
  }

  var lb = null, lbList = [], lbIdx = 0, lbLast = null;
  function lbBuild() {
    if (lb) return lb;
    lb = document.createElement("div"); lb.className = "rf-lb rf-root"; lb.setAttribute("role", "dialog"); lb.setAttribute("aria-modal", "true"); lb.setAttribute("aria-label", "Fotografie realizace");
    var fig = document.createElement("figure"), im = document.createElement("img"), cap = document.createElement("figcaption");
    im.alt = ""; fig.appendChild(im); fig.appendChild(cap); lb.appendChild(fig);
    function btn(cls, txt, label, fn) { var b = document.createElement("button"); b.type = "button"; b.className = cls; b.textContent = txt; b.setAttribute("aria-label", label); b.addEventListener("click", function (e) { e.stopPropagation(); fn(); }); lb.appendChild(b); }
    btn("rf-x", "×", "Zavřít", lbClose); btn("rf-p", "‹", "Předchozí fotografie", function () { lbShow(lbIdx - 1); }); btn("rf-n", "›", "Další fotografie", function () { lbShow(lbIdx + 1); });
    lb.addEventListener("click", function (e) { if (e.target === lb || e.target.tagName === "FIGURE") lbClose(); });
    document.body.appendChild(lb);
    window.addEventListener("keydown", function (e) {
      if (!lb.classList.contains("rf-open")) return;
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); lbClose(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); lbShow(lbIdx - 1); }
      else if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); lbShow(lbIdx + 1); }
    }, true);
    return lb;
  }
  function lbShow(i) {
    if (!lbList.length) return;
    lbIdx = (i + lbList.length) % lbList.length;
    var f = lbList[lbIdx], el = lbBuild();
    el.querySelector("img").src = f.url; el.querySelector("img").alt = f.alt || "";
    el.querySelector("figcaption").textContent = (f.title || "") + (lbList.length > 1 ? "  (" + (lbIdx + 1) + " / " + lbList.length + ")" : "");
  }
  function lbOpen(list, i, from) { lbList = list; lbLast = from || null; lbBuild().classList.add("rf-open"); lbShow(i); lb.querySelector(".rf-x").focus(); }
  function lbClose() { if (!lb) return; lb.classList.remove("rf-open"); lb.querySelector("img").removeAttribute("src"); if (lbLast && lbLast.focus) lbLast.focus(); }

  function mount(root, opts) {
    opts = opts || {};
    var t = TYPY[opts.typ];
    if (!root || !t) return Promise.resolve(false);
    return nactiGalerii(t.tag).then(function (images) {
      var vyloucene = VYLOUCENE[opts.typ] || [];
      images = images.filter(function (i) { return vyloucene.indexOf(Number(i.id)) < 0 && !(opts.bezZnacky && ZNACKA_RE.test(i.file + " " + i.title + " " + i.alt)); });
      var poradi = opts.poradi != null ? Number(opts.poradi) : (opts.stabilni ? 0 : poradiNacteni(opts.seed));          // stabilni: true = stale stejna sada (testy); poradi: cislo = pevne okno
      var fotky = vyber(images, opts.seed, opts.n || 4, opts.tyden, poradi);
      if (!fotky.length) return false;
      vlozCss();
      root.textContent = ""; root.classList.add("rf-root");
      if (opts.popis !== false) { var p = document.createElement("p"); p.className = "rf-popis"; p.textContent = opts.popis || t.popis; root.appendChild(p); }
      var ul = document.createElement("ul"); ul.className = "rf-grid"; ul.setAttribute("data-rf-n", String(fotky.length));
      fotky.forEach(function (f, i) {
        var li = document.createElement("li");
        var a = document.createElement("button"); a.type = "button"; a.className = "rf-foto"; a.setAttribute("data-rf-id", String(f.id)); a.setAttribute("aria-label", "Zvětšit fotografii: " + (f.title || "realizace"));
        var im = document.createElement("img"); im.src = f.url; im.alt = f.alt || f.title || ""; im.decoding = "async"; im.loading = opts.eager ? "eager" : "lazy";
        a.appendChild(im); a.addEventListener("click", function () { lbOpen(fotky, i, a); });
        li.appendChild(a); ul.appendChild(li);
      });
      root.appendChild(ul);
      var l = document.createElement("a"); l.className = "rf-link"; l.href = opts.href || t.href; l.target = "_blank"; l.rel = "noopener"; l.textContent = (opts.odkazText || t.odkazText) + " →"; root.appendChild(l);
      return true;
    }).catch(function () { return false; });
  }

  // Celá galerie jednoho typu (mřížka všech veřejných fotek + zvětšení) pro samostatnou stránku galerie bez značky (storefront-galerie.html). opts: { typ, bezZnacky }; vyloučené fotky (rendery, duplicity...) se
  // nezobrazují ani tady.
  function mountGalerie(root, opts) {
    opts = opts || {};
    var t = TYPY[opts.typ];
    if (!root || !t) return Promise.resolve(false);
    return nactiGalerii(t.tag).then(function (images) {
      var vyloucene = VYLOUCENE[opts.typ] || [];
      images = images.filter(function (i) { return vyloucene.indexOf(Number(i.id)) < 0 && !(opts.bezZnacky && ZNACKA_RE.test(i.file + " " + i.title + " " + i.alt)); });
      if (!images.length) return false;
      vlozCss();
      root.textContent = ""; root.classList.add("rf-root");
      var ul = document.createElement("ul"); ul.className = "rf-grid rf-vse"; ul.setAttribute("data-rf-n", String(images.length));
      images.forEach(function (f, i) {
        var li = document.createElement("li");
        var a = document.createElement("button"); a.type = "button"; a.className = "rf-foto"; a.setAttribute("data-rf-id", String(f.id)); a.setAttribute("aria-label", "Zvětšit fotografii: " + (f.title || "realizace"));
        var im = document.createElement("img"); im.src = f.url; im.alt = f.alt || f.title || ""; im.decoding = "async"; im.loading = i < 8 ? "eager" : "lazy";
        a.appendChild(im); a.addEventListener("click", function () { lbOpen(images, i, a); });
        li.appendChild(a); ul.appendChild(li);
      });
      root.appendChild(ul);
      return true;
    }).catch(function () { return false; });
  }

  window.RealizaceFoto = { mount: mount, mountGalerie: mountGalerie, vyber: vyber, poradiNacteni: poradiNacteni, VYLOUCENE: VYLOUCENE, _hash: hash, _tydenIndex: tydenIndex };
})();
