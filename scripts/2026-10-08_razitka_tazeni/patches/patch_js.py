#!/usr/bin/env python3
"""Zaplata webapp/js/v3d-ovladani.js (bot8, 2026-10-08; Robert: „razitka na generatoru pri tazeni zustavaji na miste“): pri ZIVEM tazeni se razitka (logo = uzel n<i>, vypln drazky = vrcholy v uzlu hlinik; popis
`desc.razitka` = [{dil, uzel, vypln: [uzel, od, pocet]}] z vodici.ovladani) hybou s dilem, na kterem sedi: posun = stejne jako dil; natahni / roztahni = podle POLOHY STREDU razitka vuci STREDU dilu podel osy (stejne pravidlo
jako pro vrcholy dilu: strana natazeni +d, druha 0; roztahni +d / -d), razitko se pritom nedeformuje (tuhe teleso). Konec tazeni se zrusenim vrati vse na puvodni misto; pusteni nechava nahled (server model zpresni).
Test: `ov.liveRazitka()` = aktualni poloha stredu razitek v nactenem modelu.
Pouziti: patch_js.py <koren repa>   (soubor se prepisuje na miste; kazda kotva musi byt v souboru prave jednou)"""
import io
import os
import sys

koren = sys.argv[1] if len(sys.argv) > 1 else "/opt/konfigurator"
p = os.path.join(koren, "webapp/js/v3d-ovladani.js")
s = io.open(p, encoding="utf-8").read()
if "function rigReset(L)" in s:
    print("JS: zaplata uz je aplikovana (commit e45888a3), nic se nemeni")
    sys.exit(0)


def sub(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:90])
    s = s.replace(a, b)


sub('  var VERSION = "1.1.5";', '  var VERSION = "1.2.0";')

# 1) liveBegin: sber razitek na hybanych dilech
sub("      if (!ok || !Object.keys(dily).length) return null;\n      Object.keys(nodes).forEach(function (k) { nodes[k].mesh.frustumCulled = false; });\n",
    "      if (!ok || !Object.keys(dily).length) return null;\n"
    "      var rig = {};                                                // razitka (logo = uzel n<i>, vypln drazky = vrcholy v uzlu hlinik) na dilech, ktere se hybou, se hybou s nimi (Robert 2026-10-08: \"razitka pri tazeni zustavaji na miste\")\n"
    "      ((desc && desc.razitka) || []).forEach(function (z) {\n"
    "        if (!z || !dily[z.dil]) return;\n"
    "        var obj = live.ctx.model && live.ctx.model.getObjectByName ? live.ctx.model.getObjectByName(\"n\" + z.uzel) : null, v = null, nd2 = z.vypln && liveNode(z.vypln[0]);\n"
    "        if (nd2 && z.vypln[1] + z.vypln[2] <= nd2.attr.count) { v = { nd: nd2, from: z.vypln[1] * 3, to: (z.vypln[1] + z.vypln[2]) * 3 }; v.orig = nd2.attr.array.slice(v.from, v.to); nodes[z.vypln[0]] = nd2; }\n"
    "        if (!obj && !v) return;\n"
    "        var r = { obj: obj, v: v, p0: obj ? [obj.position.x, obj.position.y, obj.position.z] : null, c: null };\n"
    "        if (obj) r.c = r.p0.slice();\n"
    "        else { var sx = 0, sy = 0, sz = 0, nn = (v.to - v.from) / 3, jj, aa = v.nd.attr.array; for (jj = v.from; jj < v.to; jj += 3) { sx += aa[jj]; sy += aa[jj + 1]; sz += aa[jj + 2]; } r.c = [sx / nn, sy / nn, sz / nn]; }\n"
    "        r.c0 = r.c.slice();\n"
    "        (rig[z.dil] = rig[z.dil] || []).push(r);\n"
    "      });\n"
    "      Object.keys(nodes).forEach(function (k) { nodes[k].mesh.frustumCulled = false; });\n")
sub("      return { ctx: live.ctx, ops: ops, dily: dily, nodes: nodes, osa: norm(vec(d.osa)), s: 0 };\n",
    "      return { ctx: live.ctx, ops: ops, dily: dily, nodes: nodes, osa: norm(vec(d.osa)), s: 0, rig: rig };\n")

# 2) pomocne funkce + liveApply
sub("    function liveApply(L, s) {\n",
    "    function rigReset(L) {                                        // razitka zpet na vychozi misto (kazdy liveApply pocita od puvodnich poloh)\n"
    "      var k, i, r, rs;\n"
    "      for (k in L.rig) { rs = L.rig[k]; for (i = 0; i < rs.length; i++) { r = rs[i]; if (r.obj) r.obj.position.set(r.p0[0], r.p0[1], r.p0[2]); if (r.v) r.v.nd.attr.array.set(r.v.orig, r.v.from); r.c = r.c0.slice(); } }\n"
    "    }\n"
    "    function rigMove(r, f, dx, dy, dz) {                          // razitko se posune jako tuhe teleso o f * (dx, dy, dz)\n"
    "      if (!f) return;\n"
    "      var a, j;\n"
    "      if (r.obj) r.obj.position.set(r.obj.position.x + f * dx, r.obj.position.y + f * dy, r.obj.position.z + f * dz);\n"
    "      if (r.v) { a = r.v.nd.attr.array; for (j = r.v.from; j < r.v.to; j += 3) { a[j] += f * dx; a[j + 1] += f * dy; a[j + 2] += f * dz; } }\n"
    "      r.c[0] += f * dx; r.c[1] += f * dy; r.c[2] += f * dz;\n"
    "    }\n"
    "    function liveApply(L, s) {\n")
sub("      for (ix in L.dily) { var q = L.dily[ix]; q.nd.attr.array.set(q.orig, q.from); }\n      L.ops.forEach(function (op) {\n",
    "      for (ix in L.dily) { var q = L.dily[ix]; q.nd.attr.array.set(q.orig, q.from); }\n      rigReset(L);\n      L.ops.forEach(function (op) {\n")
sub('          if (op.op === "posun") { for (j = q.from; j < n; j += 3) { a[j] += dx; a[j + 1] += dy; a[j + 2] += dz; } return; }\n',
    '          if (op.op === "posun") { for (j = q.from; j < n; j += 3) { a[j] += dx; a[j + 1] += dy; a[j + 2] += dz; } (L.rig[i] || []).forEach(function (r) { rigMove(r, 1, dx, dy, dz); }); return; }\n')
sub("          var st = (mn + mx) / 2, side, f;\n",
    "          var st = (mn + mx) / 2, side, f;\n"
    "          (L.rig[i] || []).forEach(function (r) {                  // razitka na tomto dile: stejne pravidlo jako pro vrcholy, rozhoduje poloha STREDU razitka vuci stredu dilu podel osy\n"
    "            var us = r.c[0] * ax + r.c[1] * ay + r.c[2] * az, sd = us > st + 0.05 ? 1 : (us < st - 0.05 ? -1 : 0), ff = op.op === \"natahni\" ? (sd === 0 ? 0.5 : (sd === (op.strana > 0 ? 1 : -1) ? 1 : 0)) : sd;\n"
    "            rigMove(r, ff, dx, dy, dz);\n"
    "          });\n")

# 3) liveEnd: zruseni vraci i razitka
sub("      if (restore) {\n        for (var ix in L.dily) { var q = L.dily[ix]; q.nd.attr.array.set(q.orig, q.from); }\n        Object.keys(L.nodes).forEach(function (k) { L.nodes[k].attr.needsUpdate = true; });\n      }\n",
    "      if (restore) {\n        for (var ix in L.dily) { var q = L.dily[ix]; q.nd.attr.array.set(q.orig, q.from); }\n        rigReset(L);\n        Object.keys(L.nodes).forEach(function (k) { L.nodes[k].attr.needsUpdate = true; });\n      }\n")

# 4) zkousky: poloha razitek
sub("    // zkousky: obalka a stred vrcholu dilu cteny primo z atributu v nactenem modelu\n",
    "    // zkousky: aktualni poloha stredu kazdeho razitka v nactenem modelu (logo = poloha uzlu, vypln = teziste vrcholu)\n"
    "    function liveRazitka() {\n"
    "      var out = [];\n"
    "      ((desc && desc.razitka) || []).forEach(function (z) {\n"
    "        var obj = live.ctx && live.ctx.model && live.ctx.model.getObjectByName ? live.ctx.model.getObjectByName(\"n\" + z.uzel) : null, nd = z.vypln && live.ctx ? liveNode(z.vypln[0]) : null, c = null, a, n, sx = 0, sy = 0, sz = 0, j;\n"
    "        if (nd) { a = nd.attr.array; n = z.vypln[2]; for (j = z.vypln[1] * 3; j < (z.vypln[1] + n) * 3; j += 3) { sx += a[j]; sy += a[j + 1]; sz += a[j + 2]; } c = [sx / n, sy / n, sz / n]; }\n"
    "        out.push({ dil: z.dil, uzel: z.uzel, logo: obj ? [obj.position.x, obj.position.y, obj.position.z] : null, vypln: c });\n"
    "      });\n"
    "      return out;\n"
    "    }\n"
    "    // zkousky: obalka a stred vrcholu dilu cteny primo z atributu v nactenem modelu\n")
sub("plugin: plugin, liveBox: liveBox, version: VERSION };", "plugin: plugin, liveBox: liveBox, liveRazitka: liveRazitka, version: VERSION };")
io.open(p, "w", encoding="utf-8").write(s)
print("OK webapp/js/v3d-ovladani.js")
