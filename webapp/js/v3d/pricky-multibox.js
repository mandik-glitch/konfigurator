/*
 * Plugin pro viewer3d.js: PRICKY V MULTIBOXECH v online nabidce - hotove MIXY pro celou policii / suplik, pod nimi vyber po boxech (bot8, 2026-10-07; Robert: "multiboxy maji moznost delicich pricek, ... v online
 * nabidce pro multiboxy nejaky system pro priobjednani pricek jako prislusenstvi, v nejakych par variantach i vizualne primo v multiboxech, at jsou videt ceny aby si uzivatel vybral";
 * "jde o to nabidnout vzdy nejake varianty SETU, vzdy pro celou policii / suplik s multiboxy"; "chci moznost v jedne polici kombinovat ruzne pocty pricek, 3D vyobrazeni primo v multiboxech";
 * "nechci kazdy box zvlast, ale hotove varianty mix, v jedne polici napr. 4 moznosti ruznych kombinaci").
 *
 *   var pr = V3DPricky.create({ payload: offer.pricky, onChange: function (vyber, souhrn) { ... } });
 *   V3D.mount(container, { modelUrl: ..., mode: 'real', plugins: [pr.plugin] });
 *
 *   VYBER = {boxId: n}, n = pocet pricek v boxu 0..typy[k].max (288 mm 4, 395 mm 6, 500 mm 8). Zakaznik vybira SETY (bez / mix1 .. mix4 / pln): set = hotovy mix poctu pricek pro VSECHNY boxy skupiny, pocty po boxech
 *   bere z payload.skupiny[].sety[setId].po_boxech (v poradi boxu skupiny). Set, ktery by ve skupine dal STEJNE pocty jako jiny, se skupine nenabizi (u 2 boxu chybi mix3, u 1 boxu jen bez + pln). Pocty po boxech
 *   (setBox) zustavaji v API pro budouci pouziti; stav, ktery neodpovida zadnemu nabizenemu setu, je 'vlastni'.
 *   pr.api.get()                    {boxId: n}  jen n > 0, KOPIE, razene podle cisla boxu
 *   pr.api.setGroup(gid, setId)     nastavi pocty ve vsech boxech skupiny z po_boxech setu ('bez' = vsude 0); true / false (neznama skupina, set, ktery skupina nenabizi, spatne typy)
 *   pr.api.setAll(setId)            totez pro vsechny skupiny, ktere set nabizeji; vraci jejich pocet (0 = nikdo set nenabizi / neznamy set)
 *   pr.api.setBox(boxId, n)         true = platna dvojice (i kdyz uz tak byla); neznamy box, n neni cele cislo 0..max typu boxu = false a nic se nezmeni
 *   pr.api.setMany({boxId: n})      nahradi CELY vyber (obnova z localStorage, i PRED mountem); neplatne polozky preskoci; vraci pocet pouzitych polozek s n > 0
 *   pr.api.clear()                  zrusi vsechny pricky; vraci pocet boxu, kterym se zmenil stav
 *   pr.api.groupInfo(gid)           {set: 'bez'|'mix1'..'mix4'|'pln'|'vlastni', priccek, cena, boxu_s_pricky, boxu, po_boxech: [n po boxech skupiny v poradi skupiny]} | null (neznama skupina)
 *                                   set = vysledek rozpoznani: 'bez' (zadne pricky), jinak nabizeny set, jehoz po_boxech presne odpovida stavu, jinak 'vlastni'
 *   pr.api.skupiny()                [{id, k, n, g, popis, boxu, ready, pocet_ready, set, priccek, cena, boxu_s_pricky, sety: [id nabizenych setu]}]  skupina = police / suplik s multiboxy; ready = aspon jeden jeji box je v modelu
 *   pr.api.boxes()                  [{id, k, n (AKTUALNI pocet pricek), poradi (poradi boxu z payloadu), g, s, max, dil, cena (cena pricek boxu), ready}]
 *   pr.api.souhrn()                 {boxu (boxu s pricky), kusy, cena_net, radky: [{klic, nazev, qty, unit_price, total}], skupiny: [{id, set, cena, priccek, boxu_s_pricky}]}  skupiny jen s pricky;
 *                                   cena = Sum n x cena dilu (payload.dily[typy[box.k].dil]); jen pro zobrazeni, server pocita znovu z karet
 *   pr.api.highlightBox(boxId|null) oranzovy obrys JEDNOHO boxu (nasleduje pohyb boxu); false = box neni v modelu (nic se nezmeni); null obrys zrusi; novy obrys nahradi predchozi
 *   pr.api.highlightGroup(gid|null) totez pro VSECHNY boxy skupiny
 *   pr.api.motionIds(gid)           id pohybu vieweru (spec.motions[].id), ktere otevrou (zvednou) boxy skupiny gid; bez gid boxy vsech skupin. UNIKATNI, v poradi boxu skupiny (u vsech skupin po skupinach);
 *                                   box -> pohyb, jehoz steps[].p je pivot boxu (mbx[].p); pohyb k 'box' ma prednost, jinak prvni pohyb s timto pivotem; box bez pivotu (p null), bez pohybu nebo mimo model se preskoci.
 *                                   spec.motions se cte ze stejneho mista jako mbx (gltf.scenes[0].userData.v3d). Nikdy nevyhodi vyjimku: neznama / neplatna skupina, po dispose, bez modelu = []
 *   pr.api.setOf(gid)               id rozpoznaneho setu ('bez' / set / 'vlastni'), neznama skupina = null;  pr.api.ready()  true = plugin ma postaveny model (do dispose)
 *
 * Vstupy (viz KONTRAKT_PRICKY.md + ZMENA_V3.md + ZMENA_V4): payload = offer.pricky: skupiny[] (id, k, n, g, popis, boxy = poradi boxu skupiny, sety {set: {po_boxech}}), boxy[] (id, k = typ boxu, n = poradi, g,
 * s = skupina), typy[k] {max, dil, pocty [{n, desky}] pro n = 0..max} a dily[] (klic, nazev, cena), sety[] (id, popis, pozn; poradi = priorita rozpoznani). typy[k].pocty[n].desky = pricky JEDNOHO boxu typu k pro n pricek
 * v MISTNIM systemu boxu (X delka od konce s vykrojem, Y vyska od spodku, Z sirka; geometrii a sloty pocita SERVER, tady se jen preklada do sveta); scenes[0].extras.v3d.mbx = poloha boxu v zavrenem stavu (AABB, osa
 * delky = delsi vodorovny rozmer, e = +1 / -1 strana konce s vykrojem (suplik: strana cela na kratsi ose), p = pivot boxu nebo null). Prevod multiboxu: a = osa delky, b = 2 - a;
 *   svet[a] = e > 0 ? min[a] + x : max[a] - x;  svet[b] = min[b] + z;  svet[1] = min[1] + y.
 * v5 (Robert: "potom i pricky v supliku, sloty po 100 mm, smer jen zepredu dozadu"; jen ocelove supliky s modrym celem): "box" muze byt i PODNOS ocelového SUPLIKU, jeho typ ma klic S<delka>x<sirka>x<vyska>
 * ("S950x384x101"; delka = sirka podnosu = delsi vodorovna strana, sirka = hloubka zepredu dozadu = kratsi, vyska). Typ nese typy[k] {druh 'box' | 'suplik', os 'a' | 'b', L, W, H, lem}; rozmery typu bere plugin
 * z L / W / H, kdyz jsou (jinak z klice, vyska multiboxu z geom.vyska_boxu jako driv) a kontroluje podle nich rozmer boxu v modelu (vcetne VYSKY H). os = osa, kterou PREVRACI e:
 *   os 'a' (multibox, jako driv): svet[a] = e > 0 ? min[a] + x : max[a] - x;  svet[b] = min[b] + z;  svet[1] = min[1] + y.
 *   os 'b' (suplik): svet[a] = min[a] + x (BEZ prevraceni, sloty jsou soumerne kolem stredu);  svet[b] = e > 0 ? min[b] + z : max[b] - z (z je od cela, e = strana cela na kratsi ose b);  svet[1] = min[1] + y.
 *   Rozmer desky (obe osy): podel a r[0] (tloustka), podel 1 r[1] (vyska), podel b r[2] (delka zepredu dozadu u supliku, sirka boxu u multiboxu). Chybi-li os, je 'a' (u klice S... 'b').
 * Pricky jednoho boxu = JEDEN spojeny mesh (kvadry 2 mm) + jedny hrany jako potomek pivotu boxu (jede s vysuvem a zvednutim boxu), staticky box = potomek modelu. Typ bez pocty / dil / dily z payloadu se zahodi
 * (jeho boxy plugin ignoruje); set se spatnym po_boxech (jina delka nez pocet boxu skupiny, pocet mimo 0..max typu boxu) se skupine nenabizi. Vyber (sel) zije v create() a prezije setModel: viewer plugin po kazdem
 * postaveni modelu zavola znovu a vyber i obrys se obnovi. Dratovy vzhled viewer (root.v3d-mode-wire): jen hrany (plocha pricek se prestane kreslit, ale dal zakryva). Plugin nikdy nevyhodi vyjimku do smycky
 * vieweru a bez WebGL/mbx/payloadu je no-op.
 */
(function (global) {
  'use strict';

  var PLATE_HEX = 0xdbe6ff;                 // svetla modra (pricky)
  var EDGE_HEX = 0x1b2a55;                  // tmave hrany pricek
  var HL_HEX = 0xff7a3d;                    // oranzova viewer (HIGHLIGHT) - obrys boxu
  var HL_PAD = 2;                           // obrys boxu je o 2 mm vetsi na kazdou stranu
  var TOL_L = 12, TOL_W = 5, TOL_H = 3;     // tolerance rozmeru boxu v modelu proti typu z payloadu (mm; skutecne 395,5 / 288, 186 / 91-92, 81)
  var MAX_N = 99;                           // horni mez poctu pricek v boxu (jen pojistka proti nesmyslnemu payloadu)
  var PIVOT_RE = /^p\d{1,4}$/;
  var BID_RE = /^b\d{1,4}$/;
  var GID_RE = /^s\d{1,4}$/;
  var SET_RE = /^[a-z0-9]{1,8}$/;
  var TYP_RE = /^(?:S(\d{2,4})x(\d{2,4})x(\d{2,4})|(\d{2,4})x(\d{2,4}))$/;        // klic typu: suplik "S950x384x101" (m[1..3]) | multibox "395x186" (m[4..5])

  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function isInt(x) { return isNum(x) && Math.floor(x) === x; }
  function posNum(x) { return isNum(x) && x > 0; }
  function isVec3(a) { return Array.isArray(a) && a.length === 3 && isNum(a[0]) && isNum(a[1]) && isNum(a[2]); }
  function round2(x) { return Math.round(x * 100) / 100; }
  function idNum(id) { return parseInt(id.slice(1), 10); }

  // ------------------------------------------------------------------ payload (offer.pricky) -> vnitrni tvar; cokoli neplatneho se tise zahodi
  function normPayload(p) {
    var out = { sety: [], setIds: [], skupiny: [], skById: Object.create(null), boxy: [], boxById: Object.create(null), typy: Object.create(null), dily: [], dilById: Object.create(null), vyska: 81 };
    if (!p || typeof p !== 'object' || !Array.isArray(p.skupiny) || !Array.isArray(p.boxy) || !p.typy || typeof p.typy !== 'object') return out;
    (Array.isArray(p.dily) ? p.dily : []).forEach(function (d) {
      if (!d || typeof d.klic !== 'string' || !isNum(d.cena) || out.dilById[d.klic]) return;
      var rec = { klic: d.klic, nazev: typeof d.nazev === 'string' ? d.nazev : d.klic, cena: d.cena };
      out.dilById[d.klic] = rec;
      out.dily.push(rec);
    });
    Object.keys(p.typy).forEach(function (k) {
      var m = TYP_RE.exec(k), t = p.typy[k];
      if (!m || !t || typeof t !== 'object' || !Array.isArray(t.pocty) || typeof t.dil !== 'string' || !out.dilById[t.dil]) return;
      var pocty = [];
      for (var n = 0; n < t.pocty.length && n <= MAX_N; n++) {          // pocty[n] = {n, desky}: musi jit v poradi 0, 1, 2 ... bez mezer (jinak se rada na prvni vadne polozce zkrati)
        var pr = t.pocty[n], desky = [];
        if (!pr || typeof pr !== 'object' || pr.n !== n) break;
        (Array.isArray(pr.desky) ? pr.desky : []).forEach(function (d) {
          if (d && isVec3(d.s) && isVec3(d.r) && d.r[0] > 0 && d.r[1] > 0 && d.r[2] > 0) desky.push({ s: d.s.slice(), r: d.r.slice() });
        });
        pocty.push({ desky: desky });
      }
      var max = pocty.length - 1;
      if (isInt(t.max) && t.max >= 1) max = Math.min(max, t.max);
      if (max < 1) return;
      var drawer = m[1] !== undefined;                                    // klic S<L>x<W>x<H> = podnos supliku
      out.typy[k] = { L: posNum(t.L) ? t.L : (drawer ? +m[1] : +m[4]), W: posNum(t.W) ? t.W : (drawer ? +m[2] : +m[5]), H: posNum(t.H) ? t.H : (drawer ? +m[3] : null),      // H null = vyska multiboxu z geom.vyska_boxu (doplni se nize)
        popis: typeof t.popis === 'string' ? t.popis : k, max: max, dil: t.dil, pocty: pocty, os: (t.os === 'a' || t.os === 'b') ? t.os : (drawer ? 'b' : 'a') };
    });
    (Array.isArray(p.sety) ? p.sety : []).forEach(function (s) {
      if (s && typeof s.id === 'string' && SET_RE.test(s.id)) {
        out.sety.push({ id: s.id, popis: typeof s.popis === 'string' ? s.popis : s.id, pozn: typeof s.pozn === 'string' ? s.pozn : '' });
        if (s.id !== 'bez' && out.setIds.indexOf(s.id) < 0) out.setIds.push(s.id);
      }
    });
    p.boxy.forEach(function (b) {
      if (!b || typeof b.id !== 'string' || !BID_RE.test(b.id) || out.boxById[b.id] || typeof b.k !== 'string' || !out.typy[b.k] || typeof b.s !== 'string' || !GID_RE.test(b.s)) return;
      var rec = { id: b.id, k: b.k, n: isNum(b.n) ? b.n : null, g: typeof b.g === 'string' ? b.g : null, s: b.s };
      out.boxById[b.id] = rec;
      out.boxy.push(rec);
    });
    p.skupiny.forEach(function (g) {
      if (!g || typeof g.id !== 'string' || !GID_RE.test(g.id) || out.skById[g.id]) return;
      var boxIds = [], seen = Object.create(null);
      if (Array.isArray(g.boxy)) {
        g.boxy.forEach(function (id) { if (typeof id === 'string' && out.boxById[id] && out.boxById[id].s === g.id && !seen[id]) { seen[id] = true; boxIds.push(id); } });
      } else {
        out.boxy.forEach(function (b) { if (b.s === g.id) boxIds.push(b.id); });
      }
      var sety = Object.create(null), order = [];
      if (g.sety && typeof g.sety === 'object') {
        Object.keys(g.sety).forEach(function (sid) {
          var st = g.sety[sid], po = st && typeof st === 'object' && Array.isArray(st.po_boxech) ? st.po_boxech : null, ok = !!po && SET_RE.test(sid) && po.length === boxIds.length;
          for (var i = 0; ok && i < po.length; i++) if (!isInt(po[i]) || po[i] < 0 || po[i] > out.typy[out.boxById[boxIds[i]].k].max) ok = false;
          if (ok) { sety[sid] = { po: po.slice() }; order.push(sid); }
        });
      }
      var rec = { id: g.id, k: typeof g.k === 'string' ? g.k : 'box', n: isNum(g.n) ? g.n : null, g: typeof g.g === 'string' ? g.g : null,
        popis: typeof g.popis === 'string' ? g.popis : g.id, boxu: boxIds.length, boxIds: boxIds, sety: sety, setOrder: order };
      out.skById[g.id] = rec;
      out.skupiny.push(rec);
    });
    var allIds = out.sety.map(function (x) { return x.id; });
    out.skupiny.forEach(function (g) {                                        // poradi nabizenych setu skupiny = poradi z payload.sety (bez, mixy, pln; = priorita rozpoznani), nezname na konec
      g.setOrder.sort(function (a, b) { var ia = allIds.indexOf(a), ib = allIds.indexOf(b); return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib); });
    });
    if (p.geom && isNum(p.geom.vyska_boxu) && p.geom.vyska_boxu > 0) out.vyska = p.geom.vyska_boxu;
    Object.keys(out.typy).forEach(function (k) { if (out.typy[k].H === null) out.typy[k].H = out.vyska; });
    return out;
  }

  // ------------------------------------------------------------------ geometrie: kvadry (svet, osy rovnobezne se svetem) -> geometrie v lokalnim systemu rodice
  // plocha: 6 sten x 4 rohy (znamenka sx, sy, sz), po obvodu proti smeru hodin ze strany ven; hrany: 12 usecek mezi rohy krychle
  var FACES = [
    [[1, 0, 0], [[1, -1, -1], [1, 1, -1], [1, 1, 1], [1, -1, 1]]],
    [[-1, 0, 0], [[-1, -1, 1], [-1, 1, 1], [-1, 1, -1], [-1, -1, -1]]],
    [[0, 1, 0], [[-1, 1, -1], [-1, 1, 1], [1, 1, 1], [1, 1, -1]]],
    [[0, -1, 0], [[-1, -1, 1], [-1, -1, -1], [1, -1, -1], [1, -1, 1]]],
    [[0, 0, 1], [[1, -1, 1], [1, 1, 1], [-1, 1, 1], [-1, -1, 1]]],
    [[0, 0, -1], [[-1, -1, -1], [-1, 1, -1], [1, 1, -1], [1, -1, -1]]]
  ];
  var EDGES = (function () {
    var e = [];
    for (var i = 0; i < 8; i++) [1, 2, 4].forEach(function (bit) { if (!(i & bit)) e.push([i, i | bit]); });
    return e;
  })();

  // quads: [{c: [x,y,z] stred ve svete, sz: [dx,dy,dz]}], inv = Matrix4 svet(zavreny stav) -> rodic; vraci {tri: BufferGeometry, lines: BufferGeometry}
  function buildGeometry(THREE, quads, inv) {
    var nm = new THREE.Matrix3().getNormalMatrix(inv), v = new THREE.Vector3(), nv = new THREE.Vector3();
    var n = quads.length, pos = new Float32Array(n * 24 * 3), nor = new Float32Array(n * 24 * 3), lin = new Float32Array(n * 24 * 3);
    var big = n * 24 > 65535, idx = big ? new Uint32Array(n * 36) : new Uint16Array(n * 36);
    quads.forEach(function (q, i) {
      var h = [q.sz[0] / 2, q.sz[1] / 2, q.sz[2] / 2], vo = i * 24, io = i * 36;
      FACES.forEach(function (f, fi) {
        nv.set(f[0][0], f[0][1], f[0][2]).applyMatrix3(nm).normalize();
        for (var c = 0; c < 4; c++) {
          var s = f[1][c];
          v.set(q.c[0] + s[0] * h[0], q.c[1] + s[1] * h[1], q.c[2] + s[2] * h[2]).applyMatrix4(inv);
          var o = (vo + fi * 4 + c) * 3;
          pos[o] = v.x; pos[o + 1] = v.y; pos[o + 2] = v.z;
          nor[o] = nv.x; nor[o + 1] = nv.y; nor[o + 2] = nv.z;
        }
        var b = vo + fi * 4, k = io + fi * 6;
        idx[k] = b; idx[k + 1] = b + 1; idx[k + 2] = b + 2; idx[k + 3] = b; idx[k + 4] = b + 2; idx[k + 5] = b + 3;
      });
      EDGES.forEach(function (ed, ei) {
        for (var e = 0; e < 2; e++) {
          var c8 = ed[e];
          v.set(q.c[0] + ((c8 & 4) ? 1 : -1) * h[0], q.c[1] + ((c8 & 2) ? 1 : -1) * h[1], q.c[2] + ((c8 & 1) ? 1 : -1) * h[2]).applyMatrix4(inv);
          var o2 = (vo + ei * 2 + e) * 3;
          lin[o2] = v.x; lin[o2 + 1] = v.y; lin[o2 + 2] = v.z;
        }
      });
    });
    var tri = new THREE.BufferGeometry();
    tri.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    tri.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
    tri.setIndex(new THREE.BufferAttribute(idx, 1));
    tri.computeBoundingSphere();
    tri.userData.__pricky = true;
    var lines = new THREE.BufferGeometry();
    lines.setAttribute('position', new THREE.BufferAttribute(lin, 3));
    lines.computeBoundingSphere();
    lines.userData.__pricky = true;
    return { tri: tri, lines: lines };
  }

  function colorOf(THREE, ctx, hex) {
    var c = new THREE.Color(hex);
    try { if (ctx.renderer && THREE.sRGBEncoding !== undefined && ctx.renderer.outputEncoding === THREE.sRGBEncoding) c.convertSRGBToLinear(); } catch (e) { /* bez prevodu */ }
    return c;
  }

  function isWire(ctx) {
    try { if (ctx.root && ctx.root.classList) return ctx.root.classList.contains('v3d-mode-wire'); } catch (e) { /* dal */ }
    try { return !!(ctx.state && ctx.state().mode === 'wire'); } catch (e2) { return false; }
  }

  var V3DPricky = global.V3DPricky = {};
  V3DPricky.version = '5.0.0';

  V3DPricky.create = function (opts) {
    opts = opts || {};
    var P = normPayload(opts.payload);
    var onChange = typeof opts.onChange === 'function' ? opts.onChange : null;
    var sel = Object.create(null);          // {boxId: n}, jen boxy s n > 0
    var run = null;                         // beh pluginu pro aktualne postaveny model (null = zadny model / po dispose)
    var hl = null;                          // {kind: 'box' | 'group', id}: oranzovy obrys (znovu se ukaze po setModel, je-li box / aspon jeden box skupiny v novem modelu)

    // ---------------------------------------------------------------- vyber a ceny
    function maxOf(id) { return P.typy[P.boxById[id].k].max; }
    function unitOf(id) { return P.dilById[P.typy[P.boxById[id].k].dil].cena; }
    function validN(id, n) { return typeof id === 'string' && !!P.boxById[id] && isInt(n) && n >= 0 && n <= maxOf(id); }
    function copySel() {
      var o = {};
      Object.keys(sel).sort(function (a, b) { return idNum(a) - idNum(b); }).forEach(function (id) { o[id] = sel[id]; });
      return o;
    }
    // pocty pricek boxu skupiny podle setu (v poradi boxu skupiny; po_boxech z payloadu) nebo null, kdyz skupina set nenabizi ('bez' je vzdy dostupny = vsude 0)
    function planSet(g, sid) {
      if (sid === 'bez') return g.boxIds.map(function () { return 0; });
      var s = g.sety[sid];
      return s && sid !== 'bez' ? s.po.slice() : null;
    }
    // 'bez' (v boxech skupiny nejsou zadne pricky) | id nabizeneho setu, jehoz po_boxech presne odpovida stavu (v poradi priority z payload.sety) | 'vlastni'
    function recognize(g) {
      var any = false, i;
      for (i = 0; i < g.boxIds.length; i++) if (sel[g.boxIds[i]]) any = true;
      if (!any) return 'bez';
      for (var si = 0; si < g.setOrder.length; si++) {
        var sid = g.setOrder[si], po = g.sety[sid].po, ok = sid !== 'bez';
        for (i = 0; ok && i < g.boxIds.length; i++) if ((sel[g.boxIds[i]] || 0) !== po[i]) ok = false;
        if (ok) return sid;
      }
      return 'vlastni';
    }
    function groupInfoOf(g) {
      var counts = Object.create(null), kusy = 0, bs = 0, cena = 0, po = [];
      g.boxIds.forEach(function (id) {
        var n = sel[id] || 0;
        po.push(n);
        if (!n) return;
        var kd = P.typy[P.boxById[id].k].dil;
        counts[kd] = (counts[kd] || 0) + n;
        kusy += n;
        bs++;
      });
      Object.keys(counts).forEach(function (kd) { cena += P.dilById[kd].cena * counts[kd]; });
      return { set: recognize(g), priccek: kusy, cena: round2(cena), boxu_s_pricky: bs, boxu: g.boxIds.length, po_boxech: po };
    }
    function souhrn() {
      var counts = Object.create(null), boxu = 0, kusy = 0, net = 0, radky = [], skup = [];
      P.boxy.forEach(function (b) {
        var n = sel[b.id] || 0;
        if (!n) return;
        var kd = P.typy[b.k].dil;
        counts[kd] = (counts[kd] || 0) + n;
        boxu++;
      });
      P.dily.forEach(function (d) {
        var n = counts[d.klic];
        if (!n) return;
        var tot = round2(d.cena * n);
        radky.push({ klic: d.klic, nazev: d.nazev, qty: n, unit_price: round2(d.cena), total: tot });
        kusy += n;
        net += tot;
      });
      P.skupiny.forEach(function (g) {
        var gi = groupInfoOf(g);
        if (gi.priccek) skup.push({ id: g.id, set: gi.set, cena: gi.cena, priccek: gi.priccek, boxu_s_pricky: gi.boxu_s_pricky });
      });
      return { boxu: boxu, kusy: kusy, cena_net: round2(net), radky: radky, skupiny: skup };
    }
    function notify() { if (onChange) { try { onChange(copySel(), souhrn()); } catch (e) { /* stranka */ } } }
    // zapise pocet pricek boxu do vyberu, true = zmenilo se
    function setN(id, n) {
      var cur = sel[id] || 0;
      if (cur === n) return false;
      if (n === 0) delete sel[id]; else sel[id] = n;
      return true;
    }

    // ---------------------------------------------------------------- vykresleni
    function disposeGroup(g) {
      if (!g) return;
      try { if (g.parent) g.parent.remove(g); } catch (e) { /* uz odpojeno */ }
      g.children.slice().forEach(function (ch) { try { if (ch.geometry) ch.geometry.dispose(); } catch (e) { /* uz uvolneno */ } });
    }
    function clearBox(rec) {
      if (!rec || !rec.grp) return;
      var g = rec.grp;
      rec.grp = null;
      disposeGroup(g);
    }
    function clearHl(r) {
      var list = r.hl;
      r.hl = [];
      list.forEach(disposeGroup);
    }
    function worldPlate(rec, d) {
      var m = rec.mbx, a = rec.a, b = 2 - a, e = rec.e, c = [0, 0, 0], sz = [0, 0, 0];
      if (rec.os === 'b') {                                              // suplik: x podel delsi osy a BEZ prevraceni (sloty jsou soumerne), z od cela po kratsi ose b; e = strana cela na ose b
        c[a] = m.min[a] + d.s[0];
        c[b] = e > 0 ? m.min[b] + d.s[2] : m.max[b] - d.s[2];
      } else {                                                           // multibox: e prevraci delsi osu a (konec s vykrojem), z od min kratsi osy
        c[a] = e > 0 ? m.min[a] + d.s[0] : m.max[a] - d.s[0];
        c[b] = m.min[b] + d.s[2];
      }
      c[1] = m.min[1] + d.s[1];
      sz[a] = d.r[0];
      sz[b] = d.r[2];
      sz[1] = d.r[1];
      return { c: c, sz: sz };
    }
    function applyBox(r, rec) {
      var n = sel[rec.id] || 0, desky = n ? P.typy[rec.k].pocty[n].desky : [], want = desky.length ? n : 0;
      if (rec.applied === want) return;
      clearBox(rec);
      rec.applied = want;
      if (!want) return;
      var THREE = r.THREE, geo = buildGeometry(THREE, desky.map(function (d) { return worldPlate(rec, d); }), rec.inv);
      var mesh = new THREE.Mesh(geo.tri, r.matPlate), lines = new THREE.LineSegments(geo.lines, r.matEdge), grp = new THREE.Group();
      mesh.userData.__pricky = rec.id;
      lines.userData.__pricky = rec.id;
      grp.userData.__pricky = rec.id;
      grp.userData.__v3dHelper = true;
      grp.add(mesh);
      grp.add(lines);
      rec.parent.add(grp);
      rec.grp = grp;
    }
    // obrysy boxu z ids (jen ty, ktere jsou v modelu); key = klic obrysu (id boxu nebo skupiny); vraci pocet nakreslenych
    function showHl(r, ids, key) {
      clearHl(r);
      var THREE = r.THREE, n = 0;
      ids.forEach(function (id) {
        var rec = r.boxes[id];
        if (!rec) return;
        var m = rec.mbx, c = [], sz = [];
        for (var i = 0; i < 3; i++) { c.push((m.min[i] + m.max[i]) / 2); sz.push(m.max[i] - m.min[i] + 2 * HL_PAD); }
        var geo = buildGeometry(THREE, [{ c: c, sz: sz }], rec.inv);
        var fill = new THREE.Mesh(geo.tri, r.matHlFill), lines = new THREE.LineSegments(geo.lines, r.matHlLine), grp = new THREE.Group();
        fill.renderOrder = 997;
        lines.renderOrder = 998;
        fill.userData.__prickyHl = key;
        lines.userData.__prickyHl = key;
        grp.userData.__prickyHl = key;
        grp.userData.__prickyBox = id;
        grp.userData.__v3dHelper = true;
        grp.add(fill);
        grp.add(lines);
        rec.parent.add(grp);
        r.hl.push(grp);
        n++;
      });
      return n;
    }
    function render(r) { try { if (r && !r.disposed && r.ctx.requestRender) r.ctx.requestRender(); } catch (e) { /* viewer uvolnen */ } }
    function refreshBox(id) {
      if (!run || run.disposed) return;
      var rec = run.boxes[id];
      if (rec) applyBox(run, rec);
    }
    function readyCount(gid) {
      var g = P.skById[gid], n = 0;
      if (!g || !run || run.disposed) return 0;
      g.boxIds.forEach(function (id) { if (run.boxes[id]) n++; });
      return n;
    }
    function showCurrentHl(r) {
      if (!hl) return;
      if (hl.kind === 'box' && r.boxes[hl.id]) showHl(r, [hl.id], hl.id);
      else if (hl.kind === 'group' && P.skById[hl.id] && readyCount(hl.id)) showHl(r, P.skById[hl.id].boxIds, hl.id);
    }

    // ---------------------------------------------------------------- beh pluginu (jeden model)
    function newRun(ctx) {
      var THREE = ctx.THREE;
      var r = { ctx: ctx, THREE: THREE, boxes: Object.create(null), byPiv: Object.create(null), disposed: false, wire: false, off: null, hl: [] };
      r.matPlate = new THREE.MeshStandardMaterial({ color: colorOf(THREE, ctx, PLATE_HEX), roughness: 0.55, metalness: 0.0, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
      r.matPlate.envMapIntensity = 0.9;
      r.matEdge = new THREE.LineBasicMaterial({ color: colorOf(THREE, ctx, EDGE_HEX), transparent: true, opacity: 0.7, toneMapped: false });
      r.matHlLine = new THREE.LineBasicMaterial({ color: colorOf(THREE, ctx, HL_HEX), transparent: true, opacity: 0.95, depthTest: false, toneMapped: false });
      r.matHlFill = new THREE.MeshBasicMaterial({ color: colorOf(THREE, ctx, HL_HEX), transparent: true, opacity: 0.2, depthWrite: false, toneMapped: false,
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      [r.matPlate, r.matEdge, r.matHlLine, r.matHlFill].forEach(function (mt) { mt.userData.__pricky = true; });
      return r;
    }
    function modeMat(r) { r.matPlate.colorWrite = !r.wire; r.matPlate.needsUpdate = true; }
    function populate(r) {
      var ctx = r.ctx, model = ctx.model, s0 = ctx.gltf && ctx.gltf.scenes && ctx.gltf.scenes[0];
      var raw = (s0 && s0.userData && s0.userData.v3d) || (model && model.userData && model.userData.v3d) || null;
      var mbx = raw && Array.isArray(raw.mbx) ? raw.mbx : [];
      var motions = raw && Array.isArray(raw.motions) ? raw.motions : [];          // pohyby vieweru ze stejneho mista jako mbx (pro motionIds)
      if (!model || !mbx.length || !P.boxy.length) return;
      model.updateMatrixWorld(true);
      motions.forEach(function (mo) {                                              // pivot -> {box: id prvniho pohybu k 'box' s timto pivotem ve steps, any: id prvniho pohybu s timto pivotem}
        if (!mo || typeof mo.id !== 'string' || !Array.isArray(mo.steps)) return;
        mo.steps.forEach(function (st) {
          if (!st || typeof st.p !== 'string') return;
          var e = r.byPiv[st.p] || (r.byPiv[st.p] = { box: null, any: null });
          if (e.any === null) e.any = mo.id;
          if (mo.k === 'box' && e.box === null) e.box = mo.id;
        });
      });
      var byName = Object.create(null);
      model.traverse(function (n) {
        var nm = (n.userData && typeof n.userData.name === 'string') ? n.userData.name : n.name;
        if (typeof nm === 'string' && PIVOT_RE.test(nm) && !byName[nm]) byName[nm] = n;
      });
      mbx.forEach(function (m) {
        if (!m || typeof m.id !== 'string' || r.boxes[m.id] || !isVec3(m.min) || !isVec3(m.max)) return;
        var b = P.boxById[m.id];
        if (!b) return;
        var dx = m.max[0] - m.min[0], dy = m.max[1] - m.min[1], dz = m.max[2] - m.min[2];
        if (dx < 0 || dy < 0 || dz < 0) return;
        var t = P.typy[b.k], L = Math.max(dx, dz), W = Math.min(dx, dz);
        if (Math.abs(L - t.L) > TOL_L || Math.abs(W - t.W) > TOL_W || Math.abs(dy - t.H) > TOL_H) return;                 // box v modelu neni typu z payloadu (delka, sirka i vyska)
        if (m.e !== 1 && m.e !== -1) return;
        var parent = model;
        if (m.p !== null && m.p !== undefined) {
          if (typeof m.p !== 'string' || !byName[m.p]) return;                                                            // pivot v modelu neni: box se preskoci
          parent = byName[m.p];
        }
        r.boxes[m.id] = { id: m.id, k: b.k, gid: b.s, mbx: { min: m.min.slice(), max: m.max.slice() }, a: dx >= dz ? 0 : 2, e: m.e, os: t.os, p: (typeof m.p === 'string') ? m.p : null, parent: parent, inv: parent.matrixWorld.clone().invert(), grp: null, applied: 0 };
      });
      r.wire = isWire(ctx);
      modeMat(r);
      if (typeof ctx.onFrame === 'function') {
        r.off = ctx.onFrame(function () {
          var w = isWire(ctx);
          if (w !== r.wire) { r.wire = w; modeMat(r); }
        });
      }
    }
    function disposeRun(r) {
      if (!r || r.disposed) return;
      r.disposed = true;
      try { if (r.off) r.off(); } catch (e) { /* viewer uz odhlasil */ }
      Object.keys(r.boxes).forEach(function (id) { clearBox(r.boxes[id]); });
      clearHl(r);
      [r.matPlate, r.matEdge, r.matHlLine, r.matHlFill].forEach(function (mt) { try { mt.dispose(); } catch (e) { /* uz uvolneno */ } });
      if (run === r) run = null;
    }
    function plugin(ctx) {
      if (run) disposeRun(run);                                  // pojistka: viewer stary plugin ukoncuje sam pred novym volanim
      var r = null;
      try {
        r = newRun(ctx);
        run = r;
        populate(r);
        Object.keys(r.boxes).forEach(function (id) { applyBox(r, r.boxes[id]); });
        showCurrentHl(r);
        render(r);
      } catch (e) {
        if (r) disposeRun(r);
        run = null;
        return function () { /* nic nezustalo */ };
      }
      return function () { disposeRun(r); };
    }

    // ---------------------------------------------------------------- verejne API
    function setHl(kind, id) {
      try {
        if (id === null || id === undefined) {
          hl = null;
          if (run && !run.disposed) { clearHl(run); render(run); }
          return true;
        }
        if (typeof id !== 'string' || !run || run.disposed) return false;
        var ids;
        if (kind === 'box') { if (!P.boxById[id] || !run.boxes[id]) return false; ids = [id]; }
        else { if (!P.skById[id] || !readyCount(id)) return false; ids = P.skById[id].boxIds; }
        hl = { kind: kind, id: id };
        showHl(run, ids, id);
        render(run);
        return true;
      } catch (e) { return false; }
    }
    var api = {
      skupiny: function () {
        return P.skupiny.map(function (g) {
          var n = readyCount(g.id), gi = groupInfoOf(g);
          return { id: g.id, k: g.k, n: g.n, g: g.g, popis: g.popis, boxu: g.boxu, ready: n > 0, pocet_ready: n, set: gi.set, priccek: gi.priccek, cena: gi.cena, boxu_s_pricky: gi.boxu_s_pricky, sety: g.setOrder.slice() };
        });
      },
      boxes: function () {
        return P.boxy.map(function (b) {
          var n = sel[b.id] || 0, ty = P.typy[b.k];
          return { id: b.id, k: b.k, n: n, poradi: b.n, g: b.g, s: b.s, max: ty.max, dil: ty.dil, cena: round2(n * P.dilById[ty.dil].cena), ready: !!(run && !run.disposed && run.boxes[b.id]) };
        });
      },
      get: function () { return copySel(); },
      setOf: function (gid) { return (typeof gid === 'string' && P.skById[gid]) ? recognize(P.skById[gid]) : null; },
      groupInfo: function (gid) {
        try { return (typeof gid === 'string' && P.skById[gid]) ? groupInfoOf(P.skById[gid]) : null; } catch (e) { return null; }
      },
      setBox: function (id, n) {
        try {
          if (!validN(id, n)) return false;
          if (setN(id, n)) { refreshBox(id); render(run); notify(); }
          return true;
        } catch (e) { return false; }
      },
      setGroup: function (gid, sid) {
        try {
          if (typeof gid !== 'string' || typeof sid !== 'string' || !P.skById[gid]) return false;
          var g = P.skById[gid], plan = planSet(g, sid), changed = false;
          if (!plan) return false;
          g.boxIds.forEach(function (id, i) { if (setN(id, plan[i])) { changed = true; refreshBox(id); } });
          if (changed) { render(run); notify(); }
          return true;
        } catch (e) { return false; }
      },
      setAll: function (sid) {
        try {
          if (typeof sid !== 'string') return 0;
          var n = 0, changed = false;
          P.skupiny.forEach(function (g) {
            var plan = planSet(g, sid);
            if (!plan) return;
            n++;
            g.boxIds.forEach(function (id, i) { if (setN(id, plan[i])) { changed = true; refreshBox(id); } });
          });
          if (changed) { render(run); notify(); }
          return n;
        } catch (e) { return 0; }
      },
      setMany: function (map) {
        try {
          if (!map || typeof map !== 'object') return 0;
          var clean = Object.create(null), n = 0, changed = false, ids = Object.create(null);
          Object.keys(map).forEach(function (id) {
            var v = map[id];
            if (!validN(id, v)) return;
            clean[id] = v;
            if (v > 0) n++;
          });
          Object.keys(sel).forEach(function (id) { ids[id] = true; });
          Object.keys(clean).forEach(function (id) { ids[id] = true; });
          Object.keys(ids).forEach(function (id) { if (setN(id, clean[id] || 0)) { changed = true; refreshBox(id); } });
          if (changed) { render(run); notify(); }
          return n;
        } catch (e) { return 0; }
      },
      clear: function () {
        try {
          var ids = Object.keys(sel);
          ids.forEach(function (id) { delete sel[id]; refreshBox(id); });
          if (ids.length) { render(run); notify(); }
          return ids.length;
        } catch (e) { return 0; }
      },
      highlightBox: function (id) { return setHl('box', id); },
      highlightGroup: function (gid) { return setHl('group', gid); },
      motionIds: function (gid) {
        try {
          if (!run || run.disposed) return [];
          var groups;
          if (gid === undefined || gid === null) groups = P.skupiny;
          else if (typeof gid === 'string' && P.skById[gid]) groups = [P.skById[gid]];
          else return [];
          var out = [], seen = Object.create(null);
          groups.forEach(function (g) {
            g.boxIds.forEach(function (id) {
              var rec = run.boxes[id], e = rec && rec.p ? run.byPiv[rec.p] : null, mid = e ? (e.box !== null ? e.box : e.any) : null;
              if (mid !== null && !seen[mid]) { seen[mid] = true; out.push(mid); }
            });
          });
          return out;
        } catch (e) { return []; }
      },
      souhrn: souhrn,
      ready: function () { return !!(run && !run.disposed); }
    };
    return { plugin: plugin, api: api };
  };
})(typeof window !== 'undefined' ? window : this);
