// ==================== PREHLEDY > JOHN ====================
// bot16, 2026-10-06 - Robert (pres bot9): "chci Johnovu praci videt primo v adminu v nejakem panelu, tam se bude vse aktualizovat at se mohu
// podivat kdykoli". Panel cte VEREJNY soubor /nahled-john/prace.json (udrzuje ho John sam; format: aktualizovano, ukoly[], historie[]) a kazdych
// 30 s ho nacte znovu BEZ reloadu stranky. Obsah souboru je NEDUVERYHODNY vstup (pise ho externi bot): vsechen text jde pres textContent, odkazy jen
// http(s) na nase domeny. Volitelne zive jednotky john-* z GET /api/admin/john/stav (api/john_stav.py, sekce "prehledy_john"): neni-li endpoint
// (jeste nenasazen) nebo uzivatel nema pravo, panel funguje jen ze souboru.

const JOHN_URL = "/nahled-john/prace.json";
const JOHN_STAV_URL = "/api/admin/john/stav";
const JOHN_INTERVAL_MS = (window.__johnInterval | 0) || 30000;      // testy smi interval zkratit
const JOHN_STARE_H = 3;                                              // soubor starsi nez 3 h = varovani
const JOHN_BEZI_STARE_MIN = 45;                                      // uloha "Bezi", ale soubor se 45 min nezmenil = John mozna skoncil / se zasekl
const JOHN_MAX_UKOLU = 100, JOHN_MAX_HISTORIE = 30;
const JOHN_NASE_DOMENY = ["logiman.cz", "baliace-stoly.top", "packing-tables.top"];

// stav -> text, trida barvy, poradi skupiny, zda je skupina ve vychozim stavu rozbalena
const JOHN_STAVY = {
  bezi: { text: "Běží", tr: "bezi", poradi: 0, otevrena: true },
  ceka_na_schvaleni: { text: "Čeká na schválení", tr: "schval", poradi: 1, otevrena: true },
  rozpracovano: { text: "Rozpracováno", tr: "rozpr", poradi: 2, otevrena: true },
  ceka_na_podklad: { text: "Čeká na podklad", tr: "podklad", poradi: 3, otevrena: true },
  schvaleno: { text: "Schváleno", tr: "ok", poradi: 4, otevrena: false },
  zive: { text: "Živé", tr: "zive", poradi: 5, otevrena: false },
  preruseno: { text: "Přerušeno", tr: "stop", poradi: 6, otevrena: false },
  zastaveno: { text: "Zastaveno", tr: "stop", poradi: 7, otevrena: false },
};

const JOHN = { timer: null, tick: null, seq: 0, data: null, lastOk: null, chyba: null, http: null, lastModified: null, live: null, liveDostupne: false, prev: {}, otevrene: {}, aktivni: false };

function jnEl(tag, tr, text) {
  const e = document.createElement(tag);
  if (tr) e.className = tr;
  if (text != null) e.textContent = String(text);
  return e;
}
function jnCas(v) {
  if (!v || typeof v !== "string") return null;
  const d = new Date(v);
  return isNaN(d.getTime()) ? null : d;
}
function jnHodiny(d, sekundy) {
  return d.toLocaleTimeString("cs-CZ", sekundy ? { hour: "2-digit", minute: "2-digit", second: "2-digit" } : { hour: "2-digit", minute: "2-digit" });
}
function jnAbs(d) { return d.toLocaleString("cs-CZ"); }
function jnRel(d) {
  const s = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
  if (s < 45) return "právě teď";
  const m = Math.round(s / 60);
  if (m < 60) return "před " + m + " min";
  const h = Math.floor(m / 60), zbyt = m % 60;
  if (h < 24) return "před " + h + " h" + (zbyt >= 5 && h < 6 ? " " + zbyt + " min" : "");
  const dny = Math.floor(h / 24);
  return "před " + dny + (dny === 1 ? " dnem" : " dny");
}
// jen http(s) na nase domeny (nebo relativni adresa); jinak null = zobrazi se jen jako text, ne jako odkaz
function jnOdkaz(u) {
  if (!u || typeof u !== "string" || u.length > 600) return null;
  let url;
  try { url = new URL(u, location.origin); } catch (e) { return null; }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  const h = url.hostname.toLowerCase();
  const nase = h === location.hostname.toLowerCase() || JOHN_NASE_DOMENY.some(d => h === d || h.endsWith("." + d));
  return nase ? url.href : null;
}
function jnOdkazEl(u, popisek, hlavni) {
  const href = jnOdkaz(u);
  const text = String(popisek || "").slice(0, 120) || (href ? href.replace(/^https?:\/\//, "").slice(0, 70) : String(u || "").slice(0, 70));
  if (!href) { const s = jnEl("span", "jn-odkaz jn-odkaz-mrtvy", text); s.title = "Odkaz mimo naše domény se neotevírá"; return s; }
  const a = jnEl("a", "jn-odkaz" + (hlavni ? " jn-odkaz-hlavni" : ""), text + " ↗");
  a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
  return a;
}
function jnDalsiOdkaz(o) {                                  // dalsi_odkazy[] muze byt retezec nebo objekt {nazev|text, url|odkaz}
  if (typeof o === "string") return { u: o, t: "" };
  if (o && typeof o === "object") return { u: o.url || o.odkaz || o.href || "", t: o.nazev || o.text || o.popis || "" };
  return null;
}

function jnUkoly(data) {
  const v = data && Array.isArray(data.ukoly) ? data.ukoly.filter(u => u && typeof u === "object") : [];
  return v.slice(0, JOHN_MAX_UKOLU);
}
function jnCasUkolu(u) { return jnCas(u.aktualizovano) || jnCas(u.zahajeno) || jnCas(u.hotovo); }

function jnBannery() {
  const out = [];
  const d = JOHN.data, ted = Date.now();
  if (JOHN.http === 404) out.push({ tr: "chyba", text: "Soubor prace.json na serveru chybí (404) – John ho zatím nevytvořil, nebo byl smazán." });
  else if (JOHN.chyba && !d) out.push({ tr: "chyba", text: "Přehled se nepodařilo načíst: " + JOHN.chyba });
  else if (JOHN.chyba) out.push({ tr: "varovani", text: "Poslední obnovení selhalo (" + JOHN.chyba + "), zobrazuji naposledy načtená data. Zkusím to znovu za 30 s." });
  if (d) {
    const kdy = jnCas(d.aktualizovano) || (JOHN.lastModified ? jnCas(JOHN.lastModified) : null);
    const bezi = jnUkoly(d).filter(u => u.stav === "bezi");
    if (!kdy) out.push({ tr: "varovani", text: "V souboru chybí čas aktualizace, stáří přehledu nejde posoudit." });
    else {
      const min = (ted - kdy.getTime()) / 60000;
      if (min > JOHN_STARE_H * 60) out.push({ tr: "varovani", text: "Přehled se neaktualizoval " + jnRel(kdy).replace("před ", "") + " (naposledy " + jnAbs(kdy) + "). Buď John nic nedělá, nebo přestal soubor aktualizovat." });
      else if (bezi.length && min > JOHN_BEZI_STARE_MIN) out.push({ tr: "varovani", text: "Úkol je označený jako Běží, ale přehled se neměnil " + Math.round(min) + " min – John možná skončil nebo se zasekl." });
    }
    if (JOHN.liveDostupne && JOHN.live) {
      const nBezi = (JOHN.live.bezi || []).length;
      if (bezi.length && !nBezi) out.push({ tr: "varovani", text: "V přehledu je úkol ve stavu Běží, ale žádná jednotka john-* teď neběží (John mohl skončit bez aktualizace přehledu)." });
      if (!bezi.length && nBezi) out.push({ tr: "info", text: "Běží jednotka John (" + JOHN.live.bezi.map(j => j.jednotka).join(", ") + "), ale v přehledu není žádný úkol ve stavu Běží." });
      if ((JOHN.live.selhaly || []).length) out.push({ tr: "chyba", text: "Selhala jednotka: " + JOHN.live.selhaly.map(j => j.jednotka).join(", ") + "." });
    }
  }
  return out;
}

function jnKarta(u) {
  const stav = JOHN_STAVY[u.stav] || { text: String(u.stav || "bez stavu").slice(0, 40), tr: "jiny", poradi: 99, otevrena: true };
  const karta = jnEl("article", "jn-karta jn-st-" + stav.tr);
  karta.dataset.id = String(u.id || "");
  const hlava = jnEl("div", "jn-karta-hlava");
  hlava.appendChild(jnEl("span", "jn-stitek jn-stitek-" + stav.tr, stav.text));
  hlava.appendChild(jnEl("h4", "jn-nazev", u.nazev || u.id || "(bez názvu)"));
  const cas = jnCasUkolu(u);
  if (cas) {
    const t = jnEl("time", "jn-cas", jnRel(cas)); t.dataset.iso = cas.toISOString(); t.title = "Poslední změna: " + jnAbs(cas);
    hlava.appendChild(t);
  }
  karta.appendChild(hlava);
  if (u.popis) karta.appendChild(jnEl("p", "jn-popis", u.popis));
  if (u.zbyva && u.stav !== "zive" && u.stav !== "zastaveno") {
    const z = jnEl("p", "jn-zbyva"); z.appendChild(jnEl("b", "", "Zbývá: ")); z.appendChild(document.createTextNode(String(u.zbyva))); karta.appendChild(z);
  }
  const odkazy = jnEl("div", "jn-odkazy");
  if (u.odkaz) odkazy.appendChild(jnOdkazEl(u.odkaz, "Otevřít náhled", true));
  (Array.isArray(u.dalsi_odkazy) ? u.dalsi_odkazy : []).slice(0, 12).forEach((o, i) => { const x = jnDalsiOdkaz(o); if (x && x.u) odkazy.appendChild(jnOdkazEl(x.u, x.t || ("Další odkaz " + (i + 1)), false)); });
  if (odkazy.childNodes.length) karta.appendChild(odkazy);
  const meta = [];
  const zah = jnCas(u.zahajeno), hot = jnCas(u.hotovo);
  if (zah) meta.push("zahájeno " + jnAbs(zah));
  if (hot) meta.push("hotovo " + jnAbs(hot));
  if (u.id) meta.push("id " + String(u.id).slice(0, 60));
  if (meta.length) karta.appendChild(jnEl("p", "jn-meta", meta.join(" · ")));
  return karta;
}

function jnRender() {
  const host = document.getElementById("johnUkoly");
  if (!host) return;
  // hlavicka
  const stavEl = document.getElementById("johnStav");
  stavEl.textContent = "";
  const d = JOHN.data;
  if (d) {
    const kdy = jnCas(d.aktualizovano) || (JOHN.lastModified ? jnCas(JOHN.lastModified) : null);
    const radek = jnEl("span", "jn-aktualizovano");
    radek.appendChild(document.createTextNode("Aktualizováno "));
    if (kdy) { const b = jnEl("b", "", jnHodiny(kdy, false)); b.title = jnAbs(kdy); radek.appendChild(b); const t = jnEl("time", "jn-cas", " (" + jnRel(kdy) + ")"); t.dataset.iso = kdy.toISOString(); t.dataset.zavorky = "1"; radek.appendChild(t); }
    else radek.appendChild(jnEl("b", "", "neznámo"));
    stavEl.appendChild(radek);
    const poc = {}; jnUkoly(d).forEach(u => { poc[u.stav] = (poc[u.stav] || 0) + 1; });
    const casti = ["bezi", "ceka_na_schvaleni", "rozpracovano", "ceka_na_podklad"].filter(k => poc[k]).map(k => JOHN_STAVY[k].text + " " + poc[k]);
    if (casti.length) stavEl.appendChild(jnEl("span", "jn-shrnuti" + (poc.ceka_na_schvaleni ? " jn-shrnuti-schval" : ""), casti.join(" · ")));
  } else stavEl.appendChild(jnEl("span", "jn-aktualizovano", "Zatím nenačteno"));
  const nacteno = jnEl("span", "jn-nacteno " + (JOHN.chyba ? "jn-nacteno-chyba" : "jn-nacteno-ok"), (JOHN.chyba ? "● nedostupné" : "● živě") + (JOHN.lastOk ? " · načteno " + jnHodiny(JOHN.lastOk, true) : ""));
  nacteno.title = "Panel se obnovuje sám každých " + Math.round(JOHN_INTERVAL_MS / 1000) + " s";
  stavEl.appendChild(nacteno);
  // varovani
  const ban = document.getElementById("johnBanner"); ban.textContent = "";
  jnBannery().forEach(b => ban.appendChild(jnEl("div", "jn-banner jn-banner-" + b.tr, b.text)));
  // zive jednotky
  const live = document.getElementById("johnLive"); live.textContent = "";
  if (JOHN.liveDostupne && JOHN.live) {
    const bezi = JOHN.live.bezi || [];
    const rad = jnEl("div", "jn-live " + (bezi.length ? "jn-live-ano" : "jn-live-ne"));
    rad.appendChild(jnEl("b", "", bezi.length ? "● Právě běží: " : "○ Právě neběží žádná jednotka John"));
    bezi.forEach((j, i) => {
      const od = jnCas(j.od);
      rad.appendChild(document.createTextNode((i ? ", " : "") + String(j.jednotka || "").slice(0, 80) + (od ? " (od " + jnHodiny(od, false) + ", " + jnRel(od).replace("před ", "") + ")" : "")));
    });
    live.appendChild(rad);
  }
  // ukoly po skupinach
  host.textContent = "";
  if (!d) { if (!JOHN.chyba) host.appendChild(jnEl("p", "hint", "Načítám…")); return; }
  const ukoly = jnUkoly(d);
  if (!ukoly.length) host.appendChild(jnEl("p", "hint", "John zatím nemá v přehledu žádný úkol."));
  const skupiny = {};
  ukoly.forEach(u => { const k = JOHN_STAVY[u.stav] ? u.stav : "_jiny"; (skupiny[k] = skupiny[k] || []).push(u); });
  const poradi = Object.keys(skupiny).sort((a, b) => ((JOHN_STAVY[a] || { poradi: 99 }).poradi) - ((JOHN_STAVY[b] || { poradi: 99 }).poradi));
  poradi.forEach(k => {
    const st = JOHN_STAVY[k] || { text: "Ostatní", tr: "jiny", otevrena: true };
    const seznam = skupiny[k].sort((a, b) => ((jnCasUkolu(b) || 0) - (jnCasUkolu(a) || 0)));
    const det = document.createElement("details"); det.className = "jn-skupina jn-sk-" + st.tr; det.dataset.stav = k;
    det.open = k in JOHN.otevrene ? JOHN.otevrene[k] : st.otevrena;
    det.addEventListener("toggle", () => { JOHN.otevrene[k] = det.open; });
    const sum = document.createElement("summary"); sum.className = "jn-skupina-hlava";
    sum.appendChild(jnEl("span", "jn-stitek jn-stitek-" + st.tr, st.text));
    sum.appendChild(jnEl("span", "jn-pocet", seznam.length + (seznam.length === 1 ? " úkol" : seznam.length < 5 ? " úkoly" : " úkolů")));
    det.appendChild(sum);
    seznam.forEach(u => {
      const karta = jnKarta(u);
      const klic = JSON.stringify([u.stav, u.popis, u.zbyva, u.aktualizovano, u.odkaz, u.hotovo, u.nazev]);
      const id = String(u.id || u.nazev || "");
      if (id in JOHN.prev && JOHN.prev[id] !== klic) karta.classList.add("jn-zmena");          // zmena od posledniho nacteni: kratke zvyrazneni
      JOHN.prev[id] = klic;
      det.appendChild(karta);
    });
    host.appendChild(det);
  });
  // historie
  const hist = document.getElementById("johnHistorie"); hist.textContent = "";
  const h = (Array.isArray(d.historie) ? d.historie : []).filter(x => x && typeof x === "object").slice().sort((a, b) => ((jnCas(b.cas) || 0) - (jnCas(a.cas) || 0))).slice(0, JOHN_MAX_HISTORIE);
  if (!h.length) hist.appendChild(jnEl("li", "hint", "Zatím žádné záznamy."));
  h.forEach(z => {
    const li = jnEl("li", "jn-hist-radek"), c = jnCas(z.cas);
    if (c) { const t = jnEl("time", "jn-cas", jnRel(c)); t.dataset.iso = c.toISOString(); t.title = jnAbs(c); li.appendChild(t); }
    li.appendChild(jnEl("span", "jn-hist-text", z.text || ""));
    hist.appendChild(li);
  });
}

// jen prepise relativni casy ("pred 5 min") bez nového stahovani
function johnTik() {
  document.querySelectorAll("#tab-john time[data-iso]").forEach(t => {
    const d = new Date(t.dataset.iso);
    if (!isNaN(d.getTime())) t.textContent = t.dataset.zavorky ? " (" + jnRel(d) + ")" : jnRel(d);
  });
  const ban = document.getElementById("johnBanner");
  if (ban && JOHN.data) { ban.textContent = ""; jnBannery().forEach(b => ban.appendChild(jnEl("div", "jn-banner jn-banner-" + b.tr, b.text))); }
}

async function johnFetch(url, ms) {
  const ac = new AbortController(); const t = setTimeout(() => ac.abort(), ms || 15000);
  try { return await fetch(url + (url.indexOf("?") < 0 ? "?" : "&") + "_=" + Date.now(), { cache: "no-store", signal: ac.signal, credentials: "same-origin" }); }
  finally { clearTimeout(t); }
}

async function johnLoad() {
  const moje = ++JOHN.seq;
  const ref = document.getElementById("johnRefreshBtn"); if (ref) ref.disabled = true;
  let soubor = null, liveOdp = null;
  try {
    const r = await johnFetch(JOHN_URL);
    JOHN.http = r.status;
    if (r.ok) {
      JOHN.lastModified = r.headers.get("Last-Modified");
      try { soubor = await r.json(); } catch (e) { JOHN.chyba = "soubor není platný JSON"; }
    } else JOHN.chyba = r.status === 404 ? "soubor chybí (404)" : "HTTP " + r.status;
  } catch (e) { JOHN.http = 0; JOHN.chyba = e && e.name === "AbortError" ? "vypršel časový limit" : "spojení selhalo"; }
  try {                                                         // zive jednotky: volitelne, selhani (404 pred nasazenim API, 403 bez prava) nic nerozbije
    const r2 = await johnFetch(JOHN_STAV_URL, 8000);
    if (r2.ok) liveOdp = await r2.json();
    else if (r2.status === 404 || r2.status === 403 || r2.status === 401) JOHN.liveDostupne = false;
  } catch (e) { /* bez zivych jednotek */ }
  if (moje !== JOHN.seq) return;                                // novejsi dotaz uz bezi
  if (soubor && typeof soubor === "object" && !Array.isArray(soubor)) { JOHN.data = soubor; JOHN.chyba = null; JOHN.lastOk = new Date(); }
  else if (soubor) JOHN.chyba = "soubor má neočekávaný tvar";
  if (liveOdp && typeof liveOdp === "object") { JOHN.live = liveOdp; JOHN.liveDostupne = true; }
  if (ref) ref.disabled = false;
  jnRender();
}

function johnStart() {
  JOHN.aktivni = true;
  johnLoad();
  clearInterval(JOHN.timer); clearInterval(JOHN.tick);
  JOHN.timer = setInterval(() => { if (!document.hidden) johnLoad(); }, JOHN_INTERVAL_MS);
  JOHN.tick = setInterval(() => { if (!document.hidden) johnTik(); }, Math.min(15000, JOHN_INTERVAL_MS));
}
function johnStop() {
  JOHN.aktivni = false;
  clearInterval(JOHN.timer); clearInterval(JOHN.tick); JOHN.timer = JOHN.tick = null;
}
document.addEventListener("visibilitychange", () => { if (JOHN.aktivni && !document.hidden) johnLoad(); });
(function () { const b = document.getElementById("johnRefreshBtn"); if (b) b.onclick = () => johnLoad(); })();
