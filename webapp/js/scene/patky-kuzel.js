/* patky-kuzel.js - STAVITELNA PATKA ve Scene = DVA kusy: sroub s maticí (barva dilu) + plastovy kuzel v CERNE (bot10, 2026-10-08).
   Robert 2026-10-08: "stavitelne patky se skladaji ze dvou casti: sroub s maticí a plastovy kuzel - dat do cerne barvy, je potreba to v 3D modelech tak upravit" a "kdyz udelam nabidku
   z generatoru, 3D scena neni ta nova ale stara" (3D pohledy a vykresy nabidky z generatoru dela SCENA ze svych dilu z katalogu, nikoli GLB generatoru).
   Katalogove GLB patek (product_3251 = M8, product_3283 = M10) je JEDEN svarovany mesh bez materialu, proto se kuzel pozna GEOMETRICKY - stejna pravidla a rovina jako api/stul_glb.py
   (KUZEL_PATKY; test scripts/2026-10-08_patky_kuzel/test_patky_kuzel.py porovnava obe tabulky): trojuhelnik patri kuzeli, kdyz jeho tezisko je v lokalnim y <= rovina + 0,001
   (rovina = horni plocha kuzele; patka roste od horniho stredu zavitu do -y; 3251: -50, 3283: -48).
   Tri veci, vsechny bez uprav katalogu a bez uprav puvodniho kodu Sceny:
     1) sdileny `loader` (THREE.GLTFLoader z hdri-panels-ui.js) se obali: po nacteni GLB patky se jediny mesh rozdeli na dva (`sroub_matice`, `plast_cerny`) - tim projdou VSECHNY cesty, ktere dil
        nacitaji (vkladani stolu z generatoru, rucni vlozeni, ulozene sestavy, AI stavitel...);
     2) `applyPartMaterial` se obali: kuzel dostane vychozi barvu `#242424` (cerny plast jako zaslepky) pres `obj.userData.meshColors` - existujici mechanismus castecneho obarveni dilu
        (paintEntry), ktery ostatni kod (panely materialu, HDRI) uz respektuje. Sroub s maticí se NEMENI: drzi barvu dilu jako dosud (katalogova barva dilu, kterou ve Scene nastavuje i
        "Obarvit dil" - ta se uklada jako vychozi barva katalogoveho dilu - nebo barva vrstvy). Kuzel se obarvuje jen samostatne (klik na cast = meshColors); "Obarvit dil" ho nechava cerny -
        je to plast, a ulozena barva dilu tak dal patri sroubu s maticí;
     3) `serializeEntryForSave` se obali: VYCHOZI cerna kuzele se do ulozene sestavy (`mesh_colors`) NEZAPISUJE, uklada se jen to, co uzivatel obarvil. Jinak by obnova sestavy provedla u dilu
        s `mesh_colors` druhe `applyPartMaterial(obj, layer, entry.customColor)` a sroub s maticí by prisel o katalogovou barvu dilu (puvodni vlastnost loadCustomShapePartEntry u vsech dilu
        s castecnym obarvenim); ulozene sestavy s patkami tak vypadaji po nacteni stejne jako po vlozeni.
   Nacita se v scene.html AZ PO #app-script (serializeEntryForSave je v nem) a pred stul-konfigurator.js (ten patky vklada); bez pinu ?v= jako ostatni skripty sceny (nginx `location /` = no-cache). */
(function () {
  "use strict";
  if (typeof THREE === "undefined" || typeof loader === "undefined" || typeof applyPartMaterial === "undefined" || typeof serializeEntryForSave === "undefined") {
    console.warn("patky-kuzel: chybi THREE / loader / applyPartMaterial / serializeEntryForSave - patky zustavaji jednobarevne"); return;
  }

  const ROVINA = { product_3251: -50.0, product_3283: -48.0 };          // lokalni y horni plochy plastoveho kuzele (stejne jako stul_glb.KUZEL_PATKY)
  const NAZEV_SROUBU = "sroub_matice", NAZEV_KUZELE = "plast_cerny", BARVA_KUZELE = "#242424";
  const TOLERANCE = 1e-3;

  // rozdeli JEDINY mesh sceny gltf podle roviny na sroub s maticí a kuzel; neplati-li predpoklad (vice meshu, bez indexu, jedna cast prazdna) nedela nic. Vraci true, kdyz rozdelilo.
  function rozdel(gltf, rovina) {
    const meshe = [];
    gltf.scene.traverse(n => { if (n.isMesh) meshe.push(n); });
    if (meshe.length !== 1) return false;
    const m = meshe[0], g = m.geometry, pos = g && g.attributes && g.attributes.position, idx = g && g.index;
    if (!pos || !idx) return false;
    const ia = idx.array, tris = ia.length / 3, jeKuzel = new Uint8Array(tris);
    let nk = 0;
    for (let t = 0; t < tris; t++) {
      const y = (pos.getY(ia[3 * t]) + pos.getY(ia[3 * t + 1]) + pos.getY(ia[3 * t + 2])) / 3;
      if (y <= rovina + TOLERANCE) { jeKuzel[t] = 1; nk++; }
    }
    if (nk === 0 || nk === tris) return false;
    const nrm = g.attributes.normal;
    function cast(chciKuzel) {                                              // geometrie jen s pouzitymi vrcholy (v puvodnim poradi), indexy prepocitane
      const mapa = new Map(), P = [], N = [], I = [];
      for (let t = 0; t < tris; t++) {
        if ((jeKuzel[t] === 1) !== chciKuzel) continue;
        for (let k = 0; k < 3; k++) {
          const v = ia[3 * t + k];
          let nv = mapa.get(v);
          if (nv === undefined) {
            nv = P.length / 3; mapa.set(v, nv);
            P.push(pos.getX(v), pos.getY(v), pos.getZ(v));
            if (nrm) N.push(nrm.getX(v), nrm.getY(v), nrm.getZ(v));
          }
          I.push(nv);
        }
      }
      const ng = new THREE.BufferGeometry();
      ng.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
      if (nrm) ng.setAttribute("normal", new THREE.Float32BufferAttribute(N, 3));
      ng.setIndex(I);
      ng.computeBoundingBox(); ng.computeBoundingSphere();
      return ng;
    }
    function novy(nazev, chciKuzel) {
      const x = new THREE.Mesh(cast(chciKuzel), m.material && m.material.clone ? m.material.clone() : m.material);
      x.name = nazev;
      x.position.copy(m.position); x.quaternion.copy(m.quaternion); x.scale.copy(m.scale);
      x.castShadow = m.castShadow; x.receiveShadow = m.receiveShadow; x.visible = m.visible;
      return x;
    }
    const sroub = novy(NAZEV_SROUBU, false), kuzel = novy(NAZEV_KUZELE, true), rodic = m.parent;
    if (!rodic) return false;
    rodic.add(sroub, kuzel);
    rodic.remove(m);
    g.dispose();
    return true;
  }

  // 1) sdileny loader: po nacteni GLB patky rozdelit mesh (chyba rozdeleni nikdy nesmi zabranit nacteni dilu)
  const puvodniLoad = loader.load.bind(loader);
  loader.load = function (url, onLoad, onProgress, onError) {
    const m = /(?:^|\/)(product_\d+)\.glb(?:[?#]|$)/.exec(String(url));
    const rovina = m ? ROVINA[m[1]] : undefined;
    if (rovina === undefined || typeof onLoad !== "function") return puvodniLoad(url, onLoad, onProgress, onError);
    return puvodniLoad(url, function (gltf) {
      try {
        if (rozdel(gltf, rovina)) {
          gltf.scene.userData = gltf.scene.userData || {};
          gltf.scene.userData.patkaKuzel = true;                              // znacka pro obalene funkce nize (Object3D.clone() ji zkopiruje)
        }
      } catch (e) { console.warn("patky-kuzel: rozdeleni patky selhalo (patka zustava jednobarevna):", e); }
      onLoad(gltf);
    }, onProgress, onError);
  };

  // 2) vychozi barva kuzele (cerny plast), dokud ho uzivatel neobarvil samostatne; sroub s maticí se nemeni
  const puvodniApply = window.applyPartMaterial;
  window.applyPartMaterial = function (obj, layer, overrideColor) {
    try {
      const ud = obj && obj.userData;
      if (ud && ud.patkaKuzel) {
        const mc = ud.meshColors || (ud.meshColors = {});
        if (!mc[NAZEV_KUZELE]) mc[NAZEV_KUZELE] = BARVA_KUZELE;
      }
    } catch (e) { /* barva kuzele je jen vylepseni - nikdy neshodit vkladani ani prekresleni dilu */ }
    return puvodniApply.apply(this, arguments);
  };

  // 3) vychozi barva kuzele se neuklada do sestavy (jen to, co uzivatel obarvil)
  const puvodniUloz = window.serializeEntryForSave;
  window.serializeEntryForSave = function (entry) {
    const out = puvodniUloz.apply(this, arguments);
    try {
      const ud = entry && entry.object3d && entry.object3d.userData;
      if (out && ud && ud.patkaKuzel && out.mesh_colors && out.mesh_colors[NAZEV_KUZELE] === BARVA_KUZELE) {
        const mc = Object.assign({}, out.mesh_colors);                        // zivy objekt userData.meshColors se nikdy nemeni
        delete mc[NAZEV_KUZELE];
        if (Object.keys(mc).length) out.mesh_colors = mc; else delete out.mesh_colors;
      }
    } catch (e) { /* ukladani nesmi nikdy spadnout kvuli barve kuzele */ }
    return out;
  };

  window.PATKY_KUZEL = { ROVINA: ROVINA, NAZEV_SROUBU: NAZEV_SROUBU, NAZEV_KUZELE: NAZEV_KUZELE, BARVA_KUZELE: BARVA_KUZELE, rozdel: rozdel };      // pro testy
})();
