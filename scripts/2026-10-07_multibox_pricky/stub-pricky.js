// ATRAPA pluginu 3D priccek pro test_page.js (bot8, 2026-10-07): stejne API jako webapp/js/v3d/pricky-multibox.js (docs/KONTRAKT_NABIDKA_PRICKY.md, oddil Plugin; vyber po BOXECH {boxId: n},
// setGroup(gid, setId) bere pocty z g.sety[setId].po_boxech), ale nic nekresli - zaznamenava volani do window.__pr.calls, drzi aktualni vyber (window.__pr.api.get()) a pocita stav / souhrn z payloadu.
// Nacita ji harness_pricky.js misto skutecneho pluginu (nespousti se samostatne).
//   window.__prNeready = [id skupin nebo boxu]  oznaci je jako "nenalezene ve 3D" (ready:false)
//   api.motionIds(gid): id pohybu boxu skupiny = "m_<id boxu>" (skutecny plugin dava id pohybu vieweru); window.__prMotionIds = pole | 'throw' | cokoli jineho = pevna odpoved / vyjimka / nesmysl;
//   window.__prBezMotionIds = true: plugin motionIds nema (starsi verze); window.__prHlChyba = true: highlightGroup vyhodi vyjimku
(function () {
  var calls = [];
  window.__pr = { calls: calls, created: 0, payload: null, api: null };
  window.V3DPricky = {
    create: function (cfg) {
      var P = (cfg && cfg.payload) || { skupiny: [], boxy: [], typy: {}, dily: [], sety: [] };
      window.__pr.created++; window.__pr.payload = P;
      var sel = {};                                              // id boxu -> n (jen n > 0)
      var boxById = {};
      P.boxy.forEach(function (b) { boxById[b.id] = b; });
      var skup = function (id) { for (var i = 0; i < P.skupiny.length; i++) if (P.skupiny[i].id === id) return P.skupiny[i]; return null; };
      var neready = function () { return window.__prNeready || []; };
      var boxReady = function (b) { return neready().indexOf(b.id) < 0 && neready().indexOf(b.s) < 0; };
      var typ = function (b) { return P.typy[b.k]; };
      var jedn = function (b) { var t = typ(b), d = P.dily.filter(function (x) { return x.klic === t.dil; })[0]; return d ? d.cena : 0; };
      var cisloId = function (id) { return parseInt(String(id).replace(/\D/g, ''), 10) || 0; };
      var setBoxN = function (b, n) { if (n > 0) sel[b.id] = n; else delete sel[b.id]; };
      // [{b, i}] boxy skupiny s indexem do po_boxech
      var boxyGrp = function (gid) { var g = skup(gid); return g ? g.boxy.map(function (id, i) { return { b: boxById[id], i: i }; }).filter(function (x) { return x.b; }) : []; };
      function rozpoznej(gid) {
        var g = skup(gid), bs = boxyGrp(gid).filter(function (x) { return boxReady(x.b); });
        for (var i = 0; i < P.sety.length; i++) {
          var s = g.sety[P.sety[i].id];
          if (s && bs.every(function (x) { return (sel[x.b.id] || 0) === s.po_boxech[x.i]; })) return P.sety[i].id;
        }
        return 'vlastni';
      }
      function info(gid) {
        var g = skup(gid); if (!g) return null;
        var bs = boxyGrp(gid).filter(function (x) { return boxReady(x.b); }), pr = 0, cena = 0, bsp = 0;
        bs.forEach(function (x) { var n = sel[x.b.id] || 0; pr += n; cena += n * jedn(x.b); if (n > 0) bsp++; });
        return { set: rozpoznej(gid), priccek: pr, cena: Math.round(cena * 100) / 100, boxu_s_pricky: bsp };
      }
      var api = {
        skupiny: function () {
          return P.skupiny.map(function (g) {
            var rd = boxyGrp(g.id).filter(function (x) { return boxReady(x.b); }).length, i = info(g.id);
            return { id: g.id, k: g.k, n: g.n, g: g.g, popis: g.popis, boxu: g.boxu, ready: rd > 0, pocet_ready: rd, set: i.set, priccek: i.priccek, cena: i.cena };
          });
        },
        boxes: function () { return P.boxy.map(function (b) { return { id: b.id, k: b.k, n: sel[b.id] || 0, max: typ(b).max, s: b.s, g: b.g, ready: boxReady(b) }; }); },
        get: function () { var o = {}; Object.keys(sel).sort(function (a, b) { return cisloId(a) - cisloId(b); }).forEach(function (k) { o[k] = sel[k]; }); return o; },
        setBox: function (id, n) {
          calls.push(['setBox', id, n]);
          var b = boxById[id];
          if (!b || typeof n !== 'number' || n % 1 !== 0 || n < 0 || n > typ(b).max) return false;
          setBoxN(b, n); return true;
        },
        setGroup: function (gid, sid) {
          calls.push(['setGroup', gid, sid]);
          var g = skup(gid), s = g && g.sety[sid]; if (!s) return false;
          boxyGrp(gid).forEach(function (x) { setBoxN(x.b, s.po_boxech[x.i]); }); return true;
        },
        setAll: function (sid) {
          calls.push(['setAll', sid]);
          var pocet = 0;
          P.skupiny.forEach(function (g) { var s = g.sety[sid]; if (s) { boxyGrp(g.id).forEach(function (x) { setBoxN(x.b, s.po_boxech[x.i]); }); pocet++; } });
          return pocet;
        },
        setMany: function (o) {
          calls.push(['setMany', Object.keys(o || {}).sort(function (a, b) { return cisloId(a) - cisloId(b); }).map(function (k) { return k + '=' + o[k]; }).join(',')]);
          sel = {}; var pouzito = 0;
          Object.keys(o || {}).forEach(function (id) { var b = boxById[id], n = o[id]; if (b && typeof n === 'number' && n % 1 === 0 && n > 0 && n <= typ(b).max) { sel[id] = n; pouzito++; } });
          return pouzito;
        },
        clear: function () { calls.push(['clear']); sel = {}; },
        groupInfo: function (gid) { return info(gid); },
        highlightBox: function (id) { calls.push(['highlightBox', id]); return !!(id === null || (boxById[id] && boxReady(boxById[id]))); },
        highlightGroup: function (gid) { calls.push(['highlightGroup', gid]); if (window.__prHlChyba) throw new Error('test highlight'); return true; },
        motionIds: function (gid) {
          calls.push(['motionIds', gid]);
          var o = window.__prMotionIds;
          if (o === 'throw') throw new Error('test motionIds');
          if (o !== undefined) return Array.isArray(o) ? o.slice() : o;
          var out = [], seen = {};
          ((gid === undefined || gid === null) ? P.skupiny.map(function (g) { return g.id; }) : [gid]).forEach(function (id) {
            if (!skup(id)) return;
            boxyGrp(id).filter(function (x) { return boxReady(x.b); }).forEach(function (x) { var m = 'm_' + x.b.id; if (!seen[m]) { seen[m] = true; out.push(m); } });
          });
          return out;
        },
        souhrn: function () {
          var pocty = {}, kusy = 0, boxu = 0;
          Object.keys(sel).forEach(function (id) { var b = boxById[id], t = typ(b); pocty[t.dil] = (pocty[t.dil] || 0) + sel[id]; boxu++; });
          var radky = P.dily.filter(function (d) { return pocty[d.klic] > 0; }).map(function (d) { kusy += pocty[d.klic]; return { klic: d.klic, nazev: d.nazev, qty: pocty[d.klic], unit_price: d.cena, total: Math.round(d.cena * pocty[d.klic] * 100) / 100 }; });
          var skupiny = P.skupiny.map(function (g) { var i = info(g.id); return { id: g.id, set: i.set, cena: i.cena, priccek: i.priccek, boxu_s_pricky: i.boxu_s_pricky }; }).filter(function (x) { return x.priccek > 0; });
          return { boxu: boxu, kusy: kusy, cena_net: Math.round(radky.reduce(function (s, r) { return s + r.total; }, 0) * 100) / 100, radky: radky, skupiny: skupiny };
        },
        ready: function () { return true; }
      };
      if (window.__prBezMotionIds) delete api.motionIds;
      window.__pr.api = api;
      return { plugin: function (ctx) { calls.push(['plugin']); return function dispose() { calls.push(['dispose']); }; }, api: api };
    }
  };
})();
