/* ucetni-emaily.js - admin zalozka Prodej > E-maily ucetni (bot16, 2026-10-06).
   Robert: "chceme schvalene doklady automaticky posilat na emaily ucetni, budou to ruzne emaily podle typu dokladu, postav nato tabulku v adminu".
   Tabulka: 1 radek = 1 typ dokladu (stabilni kod z API: vydane doklady + prijaty_doklad), sloupce adresy ucetni / aktivni / poznamka; kazdy radek se uklada zvlast
   (PUT /api/admin/ucetni-emaily/<kod>, api/ucetni_emaily.py, app_settings bez DDL). NIC SE NEODESILA - tabulka jen uklada adresy (pravidlo 16: e-maily jen pres frontu se schvalenim).
   Vse z API se vklada pres textContent. Kdyz je nejaky radek rozeditovany, opetovne otevreni zalozky ho nepreplachuje (tlacitko "Nacist znovu" se pta). */
const UE_URL = "/api/admin/ucetni-emaily";
const UE_ADRESA = /^[^\s@<>(),;:\\"\[\]]{1,64}@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,24}$/;   // stejny tvar jako api/ucetni_emaily.py
const UE = { data: null, radky: [], nacitam: false };

function ueEl(tag, attrs, kids) {
  const e = document.createElement(tag);
  Object.keys(attrs || {}).forEach(k => {
    const v = attrs[k];
    if (v == null || v === false) return;
    if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v === true ? "" : v);
  });
  (kids == null ? [] : (Array.isArray(kids) ? kids : [kids])).forEach(c => { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
  return e;
}

function ueCas(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d.toLocaleString("cs-CZ", { day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

// text -> { adresy (male pismeno, bez duplicit), chyba }; stejna pravidla jako server (ten je ale rozhodujici)
function ueParsuj(text, max) {
  const adresy = [], spatne = [];
  String(text || "").split(/[,;\s]+/).map(s => s.trim().toLowerCase()).filter(Boolean).forEach(p => {
    if (p.length > 254 || !UE_ADRESA.test(p)) spatne.push(p.slice(0, 80));
    else if (adresy.indexOf(p) < 0) adresy.push(p);
  });
  let chyba = "";
  if (spatne.length) chyba = "Neplatná adresa: " + spatne.slice(0, 5).join(", ") + ".";
  else if (adresy.length > max) chyba = "Nejvýš " + max + " adres na jeden typ dokladu.";
  return { adresy, chyba };
}

function ueStav(text, trida) {
  const e = document.getElementById("ueStav");
  if (!e) return;
  e.textContent = text || "";
  e.className = "ue-stav" + (trida ? " " + trida : "");
}

function ueMaZmeny() { return UE.radky.some(r => ueZmeneno(r)); }

function ueAktualni(r) {
  const p = ueParsuj(r.el.adresy.value, UE.data ? UE.data.max_adres : 5);
  return { adresy: p.adresy, chyba: p.chyba, aktivni: r.el.aktivni.checked, poznamka: r.el.pozn.value.trim() };
}

function ueZmeneno(r) {
  const a = ueAktualni(r);
  return JSON.stringify(a.adresy) !== JSON.stringify(r.ulozeno.adresy) || a.aktivni !== r.ulozeno.aktivni || a.poznamka !== r.ulozeno.poznamka;
}

// po kazde zmene: zvyrazneni neulozeneho radku, chyba pod radkem, dostupnost tlacitka Ulozit
function ueObnovRadek(r) {
  const a = ueAktualni(r);
  let chyba = a.chyba;
  if (!chyba && a.aktivni && !a.adresy.length) chyba = "Aktivní řádek musí mít aspoň jednu adresu.";
  const zmena = ueZmeneno(r);
  r.el.tr.classList.toggle("dirty", zmena);
  r.el.chyba.textContent = chyba || "";
  r.el.chyba.hidden = !chyba;
  r.el.uloz.disabled = r.busy || !zmena || !!chyba;
  r.el.adresy.setAttribute("aria-invalid", chyba && a.chyba ? "true" : "false");
  if (zmena && !r.busy) r.el.stav.textContent = "Neuloženo";
  else if (!zmena && r.el.stav.textContent === "Neuloženo") r.el.stav.textContent = "";
}

function ueNastavMeta(r) {
  const cas = ueCas(r.upraveno);
  r.el.meta.textContent = cas ? "Naposledy upraveno: " + cas + (r.upravil ? " (" + r.upravil + ")" : "") : "Zatím nenastaveno.";
}

function ueNaplnRadek(r, t) {
  r.ulozeno = { adresy: (t.adresy || []).slice(), aktivni: t.aktivni === true, poznamka: t.poznamka || "" };
  r.upraveno = t.upraveno || null;
  r.upravil = t.upravil || null;
  r.el.adresy.value = r.ulozeno.adresy.join(", ");
  r.el.aktivni.checked = r.ulozeno.aktivni;
  r.el.pozn.value = r.ulozeno.poznamka;
  ueNastavMeta(r);
}

function ueChybaServeru(status, j) {
  if (status === 400 && j && j.message) return String(j.message).slice(0, 300);
  if (status === 401) return "Nejsi přihlášený – přihlas se znovu.";
  if (status === 403) return "Na úpravu nemáš oprávnění (právo „E-maily účetní“ – upravit).";
  if (status === 404) return j && j.error === "typ_neznamy" ? "Neznámý typ dokladu – načti tabulku znovu." : "API pro tuhle tabulku ještě není nasazené (nasazuje se v 0:00 a 12:30).";
  return "Server selhal, nic se neuložilo.";
}

async function ueUloz(r) {
  const a = ueAktualni(r);
  if (r.busy || a.chyba || (a.aktivni && !a.adresy.length) || !ueZmeneno(r)) return;
  r.busy = true;
  [r.el.adresy, r.el.aktivni, r.el.pozn].forEach(x => { x.disabled = true; });
  r.el.stav.textContent = "Ukládám…";
  r.el.chyba.hidden = true;
  ueObnovRadek(r);
  try {
    const res = await fetch(UE_URL + "/" + encodeURIComponent(r.kod), {
      method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ adresy: a.adresy, aktivni: a.aktivni, poznamka: a.poznamka }),
    });
    let j = null;
    try { j = await res.json(); } catch (e) { j = null; }
    if (res.ok && j && j.ok && j.radek) {
      ueNaplnRadek(r, j.radek);
      r.el.stav.textContent = "Uloženo ✓";
      ueStav("Uloženo: " + r.nazev, "ue-ok");
      setTimeout(() => { if (r.el.stav.textContent === "Uloženo ✓") r.el.stav.textContent = ""; }, 4000);
    } else {
      r.el.stav.textContent = "";
      r.el.chyba.textContent = ueChybaServeru(res.status, j);
      r.el.chyba.hidden = false;
    }
  } catch (e) {
    r.el.stav.textContent = "";
    r.el.chyba.textContent = "Spojení selhalo, nic se neuložilo.";
    r.el.chyba.hidden = false;
  } finally {
    r.busy = false;
    [r.el.adresy, r.el.aktivni, r.el.pozn].forEach(x => { x.disabled = false; });
    const k = r.el.chyba.hidden ? "" : r.el.chyba.textContent;
    ueObnovRadek(r);
    if (k) { r.el.chyba.textContent = k; r.el.chyba.hidden = false; }          // chyba serveru zustane vedle pripadne chyby validace
  }
}

function ueVytvorRadek(t) {
  const r = { kod: t.kod, nazev: t.nazev, smer: t.smer, busy: false, el: {} };
  const pop = " – " + t.nazev;
  r.el.adresy = ueEl("input", { type: "text", class: "ue-adresy-pole", autocomplete: "off", spellcheck: "false", placeholder: "adresa@ucetni.cz, druha@ucetni.cz", "aria-label": "E-mailové adresy účetní" + pop });
  r.el.aktivni = ueEl("input", { type: "checkbox", "aria-label": "Aktivní" + pop });
  r.el.pozn = ueEl("input", { type: "text", class: "ue-pozn-pole", maxlength: "200", autocomplete: "off", placeholder: "nepovinná poznámka", "aria-label": "Poznámka" + pop });
  r.el.uloz = ueEl("button", { type: "button", class: "ue-uloz", text: "Uložit", "aria-label": "Uložit řádek" + pop });
  r.el.stav = ueEl("span", { class: "ue-radek-stav", role: "status", "aria-live": "polite" });
  r.el.chyba = ueEl("div", { class: "ue-radek-chyba", role: "alert", hidden: true });
  r.el.meta = ueEl("div", { class: "ue-meta" });
  r.el.tr = ueEl("tr", { "data-typ": t.kod }, [
    ueEl("td", { class: "ue-typ", "data-label": "Typ dokladu" }, [ueEl("span", { text: t.nazev }), ueEl("span", { class: "ue-smer", text: t.smer === "prijaty" ? "Přijatý doklad" : "Vydaný doklad" })]),
    ueEl("td", { class: "ue-td-adresy", "data-label": "E-mailové adresy účetní" }, [r.el.adresy, r.el.chyba, r.el.meta]),
    ueEl("td", { class: "ue-aktivni", "data-label": "Aktivní" }, [ueEl("label", null, [r.el.aktivni, "aktivní"])]),
    ueEl("td", { class: "ue-td-pozn", "data-label": "Poznámka" }, [r.el.pozn]),
    ueEl("td", { class: "ue-td-uloz", "data-label": "" }, [r.el.uloz, r.el.stav]),
  ]);
  ueNaplnRadek(r, t);
  ["input", "change"].forEach(ev => { [r.el.adresy, r.el.aktivni, r.el.pozn].forEach(x => x.addEventListener(ev, () => ueObnovRadek(r))); });
  [r.el.adresy, r.el.pozn].forEach(x => x.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); ueUloz(r); } }));
  r.el.uloz.addEventListener("click", () => ueUloz(r));
  ueObnovRadek(r);
  return r;
}

function ueVykresli() {
  const telo = document.getElementById("ueTelo");
  if (!telo || !UE.data) return;
  telo.textContent = "";
  UE.radky = (UE.data.typy || []).map(ueVytvorRadek);
  UE.radky.forEach(r => telo.appendChild(r.el.tr));
  const banner = document.getElementById("ueBanner");
  if (banner) banner.hidden = UE.data.odesilani_zapojeno === true;
}

function ueChybaNacteni(status) {
  if (status === 401) return "Nejsi přihlášený – přihlas se znovu.";
  if (status === 403) return "Na tuhle záložku nemáš oprávnění.";
  if (status === 404) return "Tabulka bude fungovat až po nasazení API (plánovaně v 0:00 nebo 12:30).";
  return "Načtení se nepovedlo (" + (status || "spojení") + "). Zkus „Načíst znovu“.";
}

async function loadUcetniEmaily(force) {
  if (!force && UE.data && ueMaZmeny()) return;            // rozeditovane radky se pri prepnuti zalozky nepreplachuji
  if (UE.nacitam) return;
  UE.nacitam = true;
  ueStav("Načítám…", "");
  try {
    const res = await fetch(UE_URL, { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
    if (!res.ok) { ueStav(ueChybaNacteni(res.status), "ue-chyba"); return; }
    const j = await res.json();
    if (!j || !Array.isArray(j.typy)) { ueStav(ueChybaNacteni(0), "ue-chyba"); return; }
    UE.data = j;
    ueVykresli();
    ueStav("Načteno " + new Date().toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" }), "");
  } catch (e) {
    ueStav(ueChybaNacteni(0), "ue-chyba");
  } finally {
    UE.nacitam = false;
  }
}

(function () {
  const b = document.getElementById("ueNacistZnovu");
  if (b) b.addEventListener("click", () => {
    if (ueMaZmeny() && !window.confirm("Zahodit neuložené změny a načíst tabulku znovu?")) return;
    loadUcetniEmaily(true);
  });
})();
