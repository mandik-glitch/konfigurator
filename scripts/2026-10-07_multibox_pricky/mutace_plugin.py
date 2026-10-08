#!/usr/bin/env python3
"""Mutacni kontrola testu pluginu pricek v5 (bot8, 2026-10-07): zamerne pokazi kopii webapp/js/v3d/pricky-multibox.js a test_plugin.js MUSI selhat ([CHYBA]).
Nejdriv se overi NEMUTOVANY zaklad (cely test, sam, musi projit, jinak konci s kodem 2), pak kazda mutace zvlast. Mutace jsou rozdelene podle toho, co hlidaji:
  - hotove MIXY (setGroup / setAll z po_boxech, nenabizeny set = false, deduplikace setu, rozpoznani setu bez / mixN / pln / vlastni, 3D: ruzne pocty pricek v boxech jedne police),
  - vyber po boxech (setBox, mez 0..max, onChange, get() po boxech, souhrn a ceny), obrys boxu a skupiny (highlightBox / highlightGroup),
  - geometrie (e, osa, pivot, rozmery), pohyb s vysuvem, dratovy vzhled, setModel, dispose, normalizace payloadu,
  - motionIds (v4.1): id pohybu vieweru, ktere otevrou boxy skupiny (box -> pohyb podle steps[].p, prednost k 'box', unikatnost, poradi, neplatne vstupy),
  - supliky (v5): podnos = box typu S<sirka>x<hloubka>x<vyska> s osou 'b' (x od min[a] bez prevraceni, z od cela podle e), rozmery typu z payloadu (L / W / H) nebo z klice,
    kontrola rozmeru boxu v modelu vcetne vysky, klic typu (S-tvar, anchory), vychozi os, vyska multiboxu z geom.vyska_boxu.
Kazda mutace se nejdriv zkusi proti CILENYM sekcim testu (SEKCE=A,K ... = rychle); chyceni v jine sekci se pocita taky, ale vypise se "mapovani" (cilena sekce ji nechytila),
beh, ktery selhal jen v casove citlivych kontrolach (G1, G4, K11, E7 = limity v ms), se pro jistotu zopakuje celym testem.
Spusteni (z teto slozky; potrebuje stejne GLB a prostredi jako test_plugin.js - viz jeho hlavicka):
    python3 mutace_plugin.py              vsechny mutace (93; -j 2: dve najednou, ~35-40 min; -j 1: postupne, ~70 min)
    python3 mutace_plugin.py -j 2 3 7 25  jen vybrane mutace (cisla z vypisu), dve najednou
Prostredi: PLUGIN_JS (zdroj pluginu, vychozi <repo>/webapp/js/v3d/pricky-multibox.js; kandidat pred nasazenim), PRICKY_REPO (vychozi ../..), MUTACE_J (pocet soubeznych behu, vychozi 1);
dale se predava testu beze zmeny: PRICKY_API, V3D_TEST_OUT, PRICKY_FIX, WEB_DIR, VIEWER_JS, V3D_CSS, THREE_DIR, PY.
Vystup: radek na mutaci (CHYCENO / NECHYCENO) a na konci "chyceno N z N"; exit 0 jen kdyz jsou chycene VSECHNY (mutace je chycena, kdyz test skonci s chybou a vypise aspon jedno [CHYBA])."""
import concurrent.futures
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("PRICKY_REPO") or os.path.abspath(os.path.join(HERE, "..", ".."))
PLUGIN = os.environ.get("PLUGIN_JS") or os.path.join(REPO, "webapp", "js", "v3d", "pricky-multibox.js")
TEST = os.path.join(HERE, "test_plugin.js")
LIMIT_S = 1200
CASOVANI = {"G1", "G4", "K11", "E7"}          # kontroly s limitem v ms: selhani jen v nich nestaci jako dukaz chyceni (zatizeny stroj)
SRC = open(PLUGIN, encoding="utf-8").read()

# (nazev, [(kotva, nahrada), ...], cilene sekce testu) - kazda kotva musi v zdroji byt PRAVE JEDNOU
M = [
    # ---- geometrie a pohyb
    ("m01 prohozene e (konec s vykrojem na druhe strane)", [("c[a] = e > 0 ? m.min[a] + d.s[0] : m.max[a] - d.s[0];", "c[a] = e < 0 ? m.min[a] + d.s[0] : m.max[a] - d.s[0];")], "A"),
    ("m02 spatna osa delky (X <-> Z)", [("a: dx >= dz ? 0 : 2,", "a: dx >= dz ? 2 : 0,")], "A"),
    ("m03 pricky vzdy pod modelem (jsou mimo pivot, nejedou s boxem)", [("parent = byName[m.p];", "parent = model;")], "B"),
    ("m04 pricky posunute po sirce boxu o 5 mm", [("c[b] = m.min[b] + d.s[2];", "c[b] = m.min[b] + d.s[2] + 5;")], "A"),
    ("m05 prohozena tloustka a delka pricky", [("sz[a] = d.r[0];\n      sz[b] = d.r[2];", "sz[a] = d.r[2];\n      sz[b] = d.r[0];")], "A"),
    ("m06 pivot hledan spatne (userData.name ignorovano, vzdy rodic uzlu)", [("if (typeof nm === 'string' && PIVOT_RE.test(nm) && !byName[nm]) byName[nm] = n;", "if (typeof nm === 'string' && PIVOT_RE.test(nm)) byName[nm] = n.parent || n;")], "B"),
    ("m07 box jineho typu nez v payloadu se neodmitne", [("if (Math.abs(L - t.L) > TOL_L || Math.abs(W - t.W) > TOL_W || Math.abs(dy - t.H) > TOL_H) return;", "")], "E"),
    # ---- mixy: set = hotove pocty po boxech z po_boxech skupiny
    ("m08 setGroup: stejny pocet ve vsech boxech (pocet prvniho boxu) misto mixu z po_boxech", [("return s && sid !== 'bez' ? s.po.slice() : null;", "return s && sid !== 'bez' ? s.po.map(function () { return s.po[0]; }) : null;")], "A"),
    ("m09 setGroup: pocty z po_boxech v obracenem poradi boxu", [("return s && sid !== 'bez' ? s.po.slice() : null;", "return s && sid !== 'bez' ? s.po.slice().reverse() : null;")], "A"),
    ("m10 nenabizeny set vycisti skupinu misto false", [("return s && sid !== 'bez' ? s.po.slice() : null;", "return s && sid !== 'bez' ? s.po.slice() : g.boxIds.map(function () { return 0; });")], "A"),
    ("m11 nenabizeny set se tise zmeni na Plny set", [("return s && sid !== 'bez' ? s.po.slice() : null;", "return s && sid !== 'bez' ? s.po.slice() : (g.sety.pln ? g.sety.pln.po.slice() : null);")], "A"),
    ("m12 setAll u skupiny, ktera set nenabizi, nepreskoci (spadne a vrati 0)", [("var plan = planSet(g, sid);\n            if (!plan) return;\n            n++;", "var plan = planSet(g, sid);\n            n++;")], "H"),
    ("m13 setGroup(.., 'bez') nic neudela", [("if (sid === 'bez') return g.boxIds.map(function () { return 0; });", "if (sid === 'bez') return null;")], "A"),
    ("m14 setAll ignorovano", [("setAll: function (sid) {\n        try {", "setAll: function (sid) {\n        try {\n          return 0;")], "A"),
    ("m15 set se ukaze jen v prvnim boxu skupiny", [("var g = P.skById[gid], plan = planSet(g, sid), changed = false;\n          if (!plan) return false;\n          g.boxIds.forEach(function (id, i) {", "var g = P.skById[gid], plan = planSet(g, sid), changed = false;\n          if (!plan) return false;\n          g.boxIds.slice(0, 1).forEach(function (id, i) {")], "A"),
    ("m16 setGroup zmeni vyber, ale neprekresli pricky ve 3D", [("if (!plan) return false;\n          g.boxIds.forEach(function (id, i) { if (setN(id, plan[i])) { changed = true; refreshBox(id); } });", "if (!plan) return false;\n          g.boxIds.forEach(function (id, i) { if (setN(id, plan[i])) { changed = true; } });")], "A"),
    ("m17 setGroup nevola onChange", [("if (changed) { render(run); notify(); }\n          return true;\n        } catch (e) { return false; }\n      },\n      setAll:", "if (changed) { render(run); }\n          return true;\n        } catch (e) { return false; }\n      },\n      setAll:")], "A"),
    ("m18 skupiny() nenabizi zadne sety", [("boxu_s_pricky: gi.boxu_s_pricky, sety: g.setOrder.slice() };", "boxu_s_pricky: gi.boxu_s_pricky, sety: [] };")], "A"),
    # ---- rozpoznani setu a ceny
    ("m19 rozpoznani: shoda s setem se hlasi jako 'vlastni'", [("if (ok) return sid;", "if (ok) return 'vlastni';")], "A"),
    ("m20 rozpoznani: posledni box skupiny se ignoruje", [("for (i = 0; ok && i < g.boxIds.length; i++) if ((sel[g.boxIds[i]] || 0) !== po[i]) ok = false;", "for (i = 0; ok && i < g.boxIds.length - 1; i++) if ((sel[g.boxIds[i]] || 0) !== po[i]) ok = false;")], "H"),
    ("m21 rozpoznani: prazdny stav skupiny neni 'bez'", [("if (!any) return 'bez';", "")], "A"),
    ("m22 groupInfo: priccek = pocet boxu s pricky misto poctu pricek", [("return { set: recognize(g), priccek: kusy, cena: round2(cena),", "return { set: recognize(g), priccek: bs, cena: round2(cena),")], "A"),
    ("m23 souhrn ignoruje pocet kusu v cene radku", [("var tot = round2(d.cena * n);", "var tot = round2(d.cena);")], "A"),
    ("m24 souhrn: cena skupiny je vzdy 0", [("if (gi.priccek) skup.push({ id: g.id, set: gi.set, cena: gi.cena, priccek: gi.priccek, boxu_s_pricky: gi.boxu_s_pricky });", "if (gi.priccek) skup.push({ id: g.id, set: gi.set, cena: 0, priccek: gi.priccek, boxu_s_pricky: gi.boxu_s_pricky });")], "A"),
    ("m25 boxes()[].cena se pocita z jednoho kusu misto n kusu", [("cena: round2(n * P.dilById[ty.dil].cena), ready:", "cena: round2(n * 1), ready:")], "K"),
    # ---- mixy ve 3D: pocty pricek v boxech
    ("m26 3D: v boxu se kresli nejvyse 1 pricka (mixy nejsou videt)", [("var n = sel[rec.id] || 0, desky = n ? P.typy[rec.k].pocty[n].desky : [], want = desky.length ? n : 0;", "var n = sel[rec.id] || 0, desky = n ? P.typy[rec.k].pocty[Math.min(n, 1)].desky : [], want = desky.length ? n : 0;")], "A"),
    ("m27 3D: kazdy box dostane plny pocet pricek bez ohledu na vyber", [("var n = sel[rec.id] || 0, desky = n ? P.typy[rec.k].pocty[n].desky : [], want = desky.length ? n : 0;", "var n = sel[rec.id] || 0, desky = n ? P.typy[rec.k].pocty[P.typy[rec.k].max].desky : [], want = desky.length ? n : 0;")], "A"),
    # ---- vyber po boxech: setBox, mez, onChange, get()
    ("m28 setBox bez horni meze (pocet nad max typu boxu)", [("function validN(id, n) { return typeof id === 'string' && !!P.boxById[id] && isInt(n) && n >= 0 && n <= maxOf(id); }", "function validN(id, n) { return typeof id === 'string' && !!P.boxById[id] && isInt(n) && n >= 0; }")], "K"),
    ("m29 setBox prijme desetinny pocet", [("function validN(id, n) { return typeof id === 'string' && !!P.boxById[id] && isInt(n) && n >= 0 && n <= maxOf(id); }", "function validN(id, n) { return typeof id === 'string' && !!P.boxById[id] && isNum(n) && n >= 0 && n <= maxOf(id); }")], "K"),
    ("m30 setBox prijme zaporny pocet", [("function validN(id, n) { return typeof id === 'string' && !!P.boxById[id] && isInt(n) && n >= 0 && n <= maxOf(id); }", "function validN(id, n) { return typeof id === 'string' && !!P.boxById[id] && isInt(n) && n >= -1 && n <= maxOf(id); }")], "K"),
    ("m31 stejny pocet znovu se hlasi jako zmena (onChange bez zmeny)", [("if (cur === n) return false;\n      if (n === 0) delete sel[id]; else sel[id] = n;", "if (n === 0) delete sel[id]; else sel[id] = n;")], "A"),
    ("m32 get() neradi boxy podle cisla", [("Object.keys(sel).sort(function (a, b) { return idNum(a) - idNum(b); }).forEach(function (id) { o[id] = sel[id]; });", "Object.keys(sel).forEach(function (id) { o[id] = sel[id]; });")], "K"),
    ("m33 get() vraci zivy objekt misto kopie", [("function copySel() {\n      var o = {};", "function copySel() {\n      return sel;\n      var o = {};")], "A"),
    ("m34 onChange se nevola", [("function notify() { if (onChange) {", "function notify() { if (false) {")], "A"),
    ("m35 setMany nezrusi puvodni vyber", [("Object.keys(sel).forEach(function (id) { ids[id] = true; });", "/* mutace */")], "A"),
    ("m36 setMany pocita i nulove pocty", [("if (v > 0) n++;", "n++;")], "A"),
    ("m37 clear() nezrusi pricky ve scene", [("ids.forEach(function (id) { delete sel[id]; refreshBox(id); });", "ids.forEach(function (id) { delete sel[id]; });")], "A"),
    ("m38 zmeny nevolaji requestRender (viewer neprekresli)", [("if (r && !r.disposed && r.ctx.requestRender) r.ctx.requestRender();", "")], "H"),
    # ---- obrys boxu a skupiny
    ("m39 highlightBox zvyrazni celou skupinu", [("highlightBox: function (id) { return setHl('box', id); },", "highlightBox: function (id) { return setHl('group', (typeof id === 'string' && P.boxById[id]) ? P.boxById[id].s : id); },")], "K"),
    ("m40 novy obrys nenahradi predchozi (obrysy se hromadi)", [("      clearHl(r);\n      var THREE = r.THREE, n = 0;", "      var THREE = r.THREE, n = 0;")], "K"),
    ("m41 obrys skupiny jen u prvniho boxu", [("ids.forEach(function (id) {\n        var rec = r.boxes[id];", "ids.slice(0, 1).forEach(function (id) {\n        var rec = r.boxes[id];")], "D"),
    ("m42 obrys se vklada pod model, ne pod pivot boxu", [("rec.parent.add(grp);\n        r.hl.push(grp);", "r.ctx.model.add(grp);\n        r.hl.push(grp);")], "D"),
    ("m43 obrys skupiny se po setModel neobnovi", [("        showCurrentHl(r);\n        render(r);", "        render(r);")], "E"),
    ("m44 obrys boxu se po setModel neobnovi", [("if (hl.kind === 'box' && r.boxes[hl.id]) showHl(r, [hl.id], hl.id);", "")], "K"),
    ("m45 highlightGroup prijme skupinu, jejiz zadny box neni v modelu", [("else { if (!P.skById[id] || !readyCount(id)) return false; ids = P.skById[id].boxIds; }", "else { if (!P.skById[id]) return false; ids = P.skById[id].boxIds; }")], "H"),
    # ---- normalizace payloadu
    ("m46 set s jinou delkou po_boxech nez pocet boxu skupiny se nabizi", [("ok = !!po && SET_RE.test(sid) && po.length === boxIds.length;", "ok = !!po && SET_RE.test(sid);")], "H"),
    ("m47 set s poctem pricek nad max typu boxu se nabizi", [("if (!isInt(po[i]) || po[i] < 0 || po[i] > out.typy[out.boxById[boxIds[i]].k].max) ok = false;", "if (!isInt(po[i]) || po[i] < 0) ok = false;")], "H"),
    ("m48 typ boxu bez dilu v payloadu se prijme", [("if (!m || !t || typeof t !== 'object' || !Array.isArray(t.pocty) || typeof t.dil !== 'string' || !out.dilById[t.dil]) return;", "if (!m || !t || typeof t !== 'object' || !Array.isArray(t.pocty)) return;")], "H"),
    # ---- drat, setModel, dispose
    ("m49 dratovy vzhled ignorovan", [("function modeMat(r) { r.matPlate.colorWrite = !r.wire;", "function modeMat(r) { r.matPlate.colorWrite = true;")], "C"),
    ("m50 frame hook (prepinani dratoveho vzhledu) se neregistruje", [("if (typeof ctx.onFrame === 'function') {", "if (false) {")], "C"),
    ("m51 vyber se po setModel neobnovi", [("Object.keys(r.boxes).forEach(function (id) { applyBox(r, r.boxes[id]); });", "/* mutace */")], "E"),
    ("m52 dispose neuklidi skupiny pricek", [("Object.keys(r.boxes).forEach(function (id) { clearBox(r.boxes[id]); });", "/* mutace */")], "H"),
    ("m53 dispose neuvolni geometrie", [("g.children.slice().forEach(function (ch) { try { if (ch.geometry) ch.geometry.dispose(); } catch (e) { /* uz uvolneno */ } });", "/* mutace */")], "H"),
    ("m54 dispose neuvolni materialy", [("[r.matPlate, r.matEdge, r.matHlLine, r.matHlFill].forEach(function (mt) { try { mt.dispose(); } catch (e) { /* uz uvolneno */ } });", "/* mutace */")], "H"),
    # ---- motionIds (v4.1): id pohybu vieweru, ktere otevrou boxy skupiny (automaticke vysunuti po vyberu setu)
    ("m55 motionIds: pohyb k 'box' nema prednost (bere se prvni pohyb s pivotem boxu)", [("if (mo.k === 'box' && e.box === null) e.box = mo.id;", "")], "N"),
    ("m56 motionIds: u pivotu s vice pohyby k 'box' se bere posledni misto prvniho", [("if (mo.k === 'box' && e.box === null) e.box = mo.id;", "if (mo.k === 'box') e.box = mo.id;")], "N"),
    ("m57 motionIds: bez pohybu k 'box' se bere posledni pohyb s pivotem misto prvniho", [("if (e.any === null) e.any = mo.id;", "e.any = mo.id;")], "N"),
    ("m58 motionIds: bez pohybu k 'box' se box preskoci (zadny nahradni pohyb)", [("mid = e ? (e.box !== null ? e.box : e.any) : null;", "mid = e ? e.box : null;")], "N"),
    ("m59 motionIds: vraci i duplicitni id (sdileny pivot)", [("if (mid !== null && !seen[mid]) { seen[mid] = true; out.push(mid); }", "if (mid !== null) { out.push(mid); }")], "N"),
    ("m60 motionIds: box bez pohybu / pivotu se vlozi jako null", [("if (mid !== null && !seen[mid]) {", "if (!seen[mid]) {")], "N"),
    ("m61 motionIds: poradi razene podle id pohybu misto podle boxu skupiny", [("          return out;\n        } catch (e) { return []; }", "          return out.slice().sort();\n        } catch (e) { return []; }")], "N"),
    ("m62 motionIds: gid se ignoruje (vzdy vsechny skupiny)", [("else if (typeof gid === 'string' && P.skById[gid]) groups = [P.skById[gid]];", "else if (typeof gid === 'string' && P.skById[gid]) groups = P.skupiny;")], "N"),
    ("m63 motionIds: bez gid vraci []", [("if (gid === undefined || gid === null) groups = P.skupiny;", "if (gid === undefined || gid === null) groups = [];")], "N"),
    ("m64 motionIds: neplatne gid se bere jako vsechny skupiny", [("          else return [];\n          var out = [], seen = Object.create(null);", "          else groups = P.skupiny;\n          var out = [], seen = Object.create(null);")], "N"),
    ("m65 motionIds: spec.motions se cte z jineho klice", [("var motions = raw && Array.isArray(raw.motions) ? raw.motions : [];", "var motions = raw && Array.isArray(raw.motion) ? raw.motion : [];")], "N"),
    ("m66 motionIds: pivot boxu se hleda podle id boxu misto mbx[].p", [("e = rec && rec.p ? run.byPiv[rec.p] : null", "e = rec && rec.p ? run.byPiv[rec.id] : null")], "N"),
    ("m67 motionIds: z pohybu se bere jen prvni krok", [("mo.steps.forEach(function (st) {\n          if (!st || typeof st.p !== 'string') return;", "mo.steps.slice(0, 1).forEach(function (st) {\n          if (!st || typeof st.p !== 'string') return;")], "N"),
    ("m68 motionIds: vadna polozka motions (null) shodi cteni spec", [("if (!mo || typeof mo.id !== 'string' || !Array.isArray(mo.steps)) return;", "if (typeof mo.id !== 'string' || !Array.isArray(mo.steps)) return;")], "N"),
    ("m69 motionIds: pivot boxu se do zaznamu boxu neulozi (rec.p = null)", [("e: m.e, os: t.os, p: (typeof m.p === 'string') ? m.p : null, parent: parent, inv:", "e: m.e, os: t.os, p: null, parent: parent, inv:")], "N"),
    # ---- v5: supliky (podnos = box typu S<L>x<W>x<H>, os 'b')
    ("m70 suplik: x se u e = -1 prevraci jako u multiboxu (sloty maji byt soumerne, x BEZ prevraceni)", [("c[a] = m.min[a] + d.s[0];", "c[a] = e > 0 ? m.min[a] + d.s[0] : m.max[a] - d.s[0];")], "S"),
    ("m71 suplik: z se u e = -1 nepocita od MAX strany (cela na druhe strane osy b)", [("c[b] = e > 0 ? m.min[b] + d.s[2] : m.max[b] - d.s[2];", "c[b] = m.min[b] + d.s[2];")], "S"),
    ("m72 suplik: prohozene e (celo na opacne strane osy b)", [("c[b] = e > 0 ? m.min[b] + d.s[2] : m.max[b] - d.s[2];", "c[b] = e < 0 ? m.min[b] + d.s[2] : m.max[b] - d.s[2];")], "S"),
    ("m73 suplik: x se vzdy pocita od MAX strany", [("c[a] = m.min[a] + d.s[0];", "c[a] = m.max[a] - d.s[0];")], "S"),
    ("m74 prohozena vetev os 'a' / 'b' ve svetove poloze (multiboxy podle supliku a naopak)", [("if (rec.os === 'b') {", "if (rec.os !== 'b') {")], "A,S"),
    ("m75 zaznam boxu ma vzdy os 'a' (typ os 'b' se ignoruje pri vypoctu polohy)", [("e: m.e, os: t.os, p:", "e: m.e, os: 'a', p:")], "S"),
    ("m76 vychozi os pro klic S... je 'a' (typ bez pole os)", [(": (drawer ? 'b' : 'a') };", ": 'a' };")], "S"),
    ("m77 os z payloadu se ignoruje (vzdy vychozi podle klice)", [("os: (t.os === 'a' || t.os === 'b') ? t.os : (drawer ? 'b' : 'a') };", "os: (drawer ? 'b' : 'a') };")], "S"),
    ("m78 delka typu L z payloadu se ignoruje (vzdy z klice)", [("L: posNum(t.L) ? t.L : (drawer ? +m[1] : +m[4]),", "L: (drawer ? +m[1] : +m[4]),")], "S"),
    ("m79 sirka typu W z payloadu se ignoruje (vzdy z klice)", [("W: posNum(t.W) ? t.W : (drawer ? +m[2] : +m[5]),", "W: (drawer ? +m[2] : +m[5]),")], "S"),
    ("m80 vyska typu H z payloadu se ignoruje (vzdy z klice / geom)", [("H: posNum(t.H) ? t.H : (drawer ? +m[3] : null),", "H: (drawer ? +m[3] : null),")], "S"),
    ("m81 vyska supliku se z klice nebere (H = vyska multiboxu z geom.vyska_boxu)", [("H: posNum(t.H) ? t.H : (drawer ? +m[3] : null),", "H: posNum(t.H) ? t.H : null,")], "S"),
    ("m82 kontrola VYSKY boxu v modelu proti typu chybi (kontroluje se jen delka a sirka)", [("|| Math.abs(dy - t.H) > TOL_H) return;", ") return;")], "S"),
    ("m83 tolerance vysky boxu 40 mm misto 3 (vyska 100 / 90 proti 81 projde)", [("TOL_H = 3;", "TOL_H = 40;")], "S"),
    ("m84 klic typu S<L>x<W>x<H> se nerozpozna (supliky se zahodi)", [("/^(?:S(", "/^(?:Z(")], "S"),
    ("m85 klic typu: sirka muze mit 1 cislici (S9x384x101 projde)", [("S(\\d{2,4})x", "S(\\d{1,4})x")], "S"),
    ("m86 klic typu bez koncove kotvy (S950x384x101x5 projde)", [("))$/;", "))/;")], "S"),
    ("m87 klic typu bez pocatecni kotvy (950x384x101 projde jako 384x101)", [("/^(?:S(", "/(?:S(")], "S"),
    ("m88 sirka (hloubka) supliku z klice se bere z cisla vysky", [("W: posNum(t.W) ? t.W : (drawer ? +m[2] : +m[5]),", "W: posNum(t.W) ? t.W : (drawer ? +m[3] : +m[5]),")], "S"),
    ("m89 H typu bez pole se nedoplni z geom.vyska_boxu (multiboxy z payloadu v4 nejsou ready)", [("Object.keys(out.typy).forEach(function (k) { if (out.typy[k].H === null) out.typy[k].H = out.vyska; });", "")], "S"),
    ("m90 H typu bez pole je pevne 81 (geom.vyska_boxu se ignoruje)", [("out.typy[k].H = out.vyska; });", "out.typy[k].H = 81; });")], "S"),
    ("m91 klic S... se nepovazuje za suplik (rozmery a os se z klice nebeou)", [("var drawer = m[1] !== undefined;", "var drawer = false;")], "S"),
    ("m92 druh skupiny (k = 'suplik') se ignoruje (vzdy 'box')", [("var rec = { id: g.id, k: typeof g.k === 'string' ? g.k : 'box',", "var rec = { id: g.id, k: 'box',")], "S"),
    ("m93 vyska pricky = tloustka pricky (r[0] misto r[1])", [("sz[1] = d.r[1];", "sz[1] = d.r[0];")], "A,S"),
]


def vyrob(zmeny):
    s = SRC
    for a, b in zmeny:
        assert s.count(a) == 1, "kotva %d x: %r" % (s.count(a), a[:70])
        s = s.replace(a, b)
    return s


def spust(plugin_js, sekce=None):
    """Jeden beh test_plugin.js nad danym pluginem (STOP_ON_FAIL, volitelne jen cilene sekce): {rc, chyby: [radky [CHYBA]], ids: [id kontroly], soucet, konec}."""
    env = dict(os.environ, PLUGIN_JS=plugin_js, STOP_ON_FAIL="1")
    env.pop("SEKCE", None)
    if sekce:
        env["SEKCE"] = sekce
    try:
        r = subprocess.run(["node", TEST], cwd=HERE, env=env, capture_output=True, text=True, timeout=LIMIT_S)
    except subprocess.TimeoutExpired:
        return {"rc": 124, "chyby": [], "ids": [], "soucet": [], "konec": "casovy limit %d s" % LIMIT_S}
    lines = r.stdout.splitlines()
    chyby = [l for l in lines if l.startswith("[CHYBA]")]
    return {"rc": r.returncode, "chyby": chyby, "ids": [(l[8:].split() or ["?"])[0] for l in chyby],
            "soucet": [l for l in lines if re.match(r"\d+/\d+ OK", l)], "konec": (r.stdout[-300:] + r.stderr[-300:]).strip()}


def chyceno(r):
    return r["rc"] != 0 and bool(r["chyby"])


def jen_casovani(r):
    return bool(r["chyby"]) and all(i in CASOVANI for i in r["ids"])


def zpracuj(i, f):
    """Jedna mutace: cilene sekce -> (kdyz nechytily nebo selhaly jen casove) cely test -> (jen casove) jeste jednou cely. Vraci (stav, text)."""
    nazev, zmeny, sekce = M[i - 1]
    r = spust(f, sekce)
    if chyceno(r) and not jen_casovani(r):
        return "CHYCENO", "%s | %s: %s" % (nazev, sekce, r["chyby"][0][:150])
    poznamka = "cilene sekce %s nechytily" % sekce if not chyceno(r) else "cilene sekce selhaly jen v casovych kontrolach"
    for pokus in range(2):
        r = spust(f)
        if chyceno(r) and not jen_casovani(r):
            return "CHYCENO", "%s | MAPOVANI (%s, chyceno celym testem): %s" % (nazev, poznamka, r["chyby"][0][:130])
    return "NECHYCENO", "%s | rc=%d %s" % (nazev, r["rc"], ((r["chyby"][0][:150]) if r["chyby"] else r["konec"][-160:].replace("\n", " ")))


def main():
    args = sys.argv[1:]
    j = int(os.environ.get("MUTACE_J") or 1)
    if args and args[0] == "-j":
        j = int(args[1])
        args = args[2:]
    vyb = [int(x) for x in args] or list(range(1, len(M) + 1))
    for i in vyb:
        if not 1 <= i <= len(M):
            print("neplatne cislo mutace %d (1..%d)" % (i, len(M)))
            return 2
    for nazev, zmeny, sekce in M:
        vyrob(zmeny)                                          # kazda kotva musi sedet PRAVE JEDNOU (jinak AssertionError = zdroj pluginu se zmenil, mutace upravit)
    z = spust(PLUGIN)
    print("ZAKLAD (nemutovany, cely test, %s): rc=%d %s" % (PLUGIN, z["rc"], z["soucet"]))
    sys.stdout.flush()
    if z["rc"] != 0:
        print("nemutovany zaklad NEPROSEL - mutace nemaji smysl:\n" + z["konec"] + "\n" + "\n".join(z["chyby"][:5]))
        return 2
    tmp = tempfile.mkdtemp(prefix="pricky_mut_")
    zive, mapovani, hotovo = [], [], 0
    try:
        soubory = {}
        for i in vyb:
            f = os.path.join(tmp, "m%02d.js" % i)
            open(f, "w", encoding="utf-8").write(vyrob(M[i - 1][1]))
            soubory[i] = f
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, j)) as ex:
            futs = {ex.submit(zpracuj, i, soubory[i]): i for i in vyb}
            for fu in concurrent.futures.as_completed(futs):
                i = futs[fu]
                try:
                    stav, text = fu.result()
                except Exception as e:  # noqa: BLE001 - chyba behu mutace = nechycena
                    stav, text = "NECHYCENO", "%s | vyjimka behu: %s" % (M[i - 1][0], e)
                hotovo += 1
                print("[%2d/%d] %s: %s" % (hotovo, len(vyb), "CHYCENO" if stav == "CHYCENO" else "NECHYCENO !!!", text))
                sys.stdout.flush()
                if stav != "CHYCENO":
                    zive.append(M[i - 1][0])
                elif "MAPOVANI" in text:
                    mapovani.append(M[i - 1][0])
    finally:
        for fn in os.listdir(tmp):
            os.unlink(os.path.join(tmp, fn))
        os.rmdir(tmp)
    print("\nchyceno %d z %d" % (len(vyb) - len(zive), len(vyb)))
    for n in sorted(zive):
        print("  NECHYCENO: " + n)
    for n in sorted(mapovani):
        print("  (mapovani na sekci testu neplati, chyceno az celym testem: %s)" % n)
    return 1 if zive else 0


if __name__ == "__main__":
    sys.exit(main())
