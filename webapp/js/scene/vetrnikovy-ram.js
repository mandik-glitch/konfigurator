// "Vetrnikovy" ram/ctverec (Robert 2026-08-16) - vyclenene z app-script
// (bot14, 2026-09-03, PLAN_ROZDELENI_FRONTENDU.md). 1:1 presun, beze
// zmeny chovani. Klasicky script (ne modul), sdili globalni scope s
// app-script - musi se nacist PRED nim (viz <script src> v scene.html).
//
// refitFrameEntriesByKind/currentFrameDimsByKind (spolecny rozcestnik
// rect vs. pinwheel ram) ZUSTAVAJI v app-script - volaji i
// refitRectFrameEntries/currentRectFrameDims (jina, nesouvisejici
// sekce), takze patri do jadra, ne sem. Volaji funkce z tohohle
// souboru jen za behu (runtime call, ne top-level pri parsovani), coz
// v klasickem sdilenem globalnim scope funguje bez ohledu na poradi
// souboru - vetrnikovy-ram.js se navic nacita DRIV nez app-script.
// ==== "Vetrnikovy" ram (Ctverec/ram (plne profily), Robert 2026-08-16) ====
// Jina struktura nez zkracena varianta vyse, proto vlastni refit/dims:
// vsechny 4 dily jsou v plne delce, dvojice A/B lezi podel jedne osy,
// dvojice C/D podel druhe, a kazdy dil dosedne celem na bok nasledujiciho
// (rotacne soumerne). Pri vnejsim rozmeru Lx x Ly a sirce prurezu w plati
// jednoduchy vztah: delka dilu A/B = Ly - w, delka dilu C/D = Lx - w, a
// jejich vnejsi hrany lezi (pri kotve vnejsiho rohu na pocatku) takto:
// (v = smer sirky dilu A, u = smer jeho delky; hodnoty jsou [vMin,vMax] x
// [uMin,uMax] vuci vnejsimu rohu sestavy):
//   A: [0, w]      x [w, Ly]      C: [w, Lx]     x [Ly-w, Ly]
//   B: [Lx-w, Lx]  x [0, Ly-w]    D: [0, Lx-w]   x [0, w]
// Vsimni si, ze kazdy dil zacina o w posunuty proti jednomu sousedovi -
// prave tim vznika "vetrnik" (rotacne soumerny, zadny dil neprekryva jiny).
// (v osach u = smer delky A/B, v = smer delky C/D). Pozice se proto po
// zmene delek nastavuji primo z bounding-boxu na tyhle cilove hrany -
// spolehlivejsi nez rekonstrukce z konektoru, ktera musi resit i scale
// (stejne pouceni jako u refitRectFrameEntries krok 2).
function pinwheelFrameAxes(frameMeta) {
  const { entryA, entryC } = frameMeta;
  const uDir = profileLengthAxisWorld(entryA);
  const vDir = profileLengthAxisWorld(entryC);
  if (!uDir || !vDir) return null;
  // pracujeme v osach zarovnanych se svetem (ram lezi v rovine) - vybereme
  // dominantni svetovou osu kazdeho smeru
  const dom = d => {
    const a = [Math.abs(d.x), Math.abs(d.y), Math.abs(d.z)];
    return ["x", "y", "z"][a.indexOf(Math.max(...a))];
  };
  const uAxis = dom(uDir), vAxis = dom(vDir);
  if (uAxis === vAxis) return null;
  return { uAxis, vAxis };
}

function currentPinwheelFrameDims(frameMeta) {
  const ax = pinwheelFrameAxes(frameMeta);
  if (!ax) return { Ly: 0, Lx: 0 };
  const box = new THREE.Box3();
  [frameMeta.entryA, frameMeta.entryB, frameMeta.entryC, frameMeta.entryD]
    .forEach(e => box.union(new THREE.Box3().setFromObject(e.object3d)));
  return {
    Ly: box.max[ax.uAxis] - box.min[ax.uAxis],
    Lx: box.max[ax.vAxis] - box.min[ax.vAxis],
  };
}

function refitPinwheelFrameEntries(frameMeta, newLy, newLx) {
  const { entryA, entryB, entryC, entryD } = frameMeta;
  const ax = pinwheelFrameAxes(frameMeta);
  if (!ax) return;
  const all = [entryA, entryB, entryC, entryD];
  const boxOf = e => new THREE.Box3().setFromObject(e.object3d);

  const outer = new THREE.Box3();
  all.forEach(e => outer.union(boxOf(e)));
  const cur = currentPinwheelFrameDims(frameMeta);
  const Ly = newLy != null ? newLy : cur.Ly;
  const Lx = newLx != null ? newLx : cur.Lx;
  // sirka prurezu (tloustka ramu v rovine) - z libovolneho dilu, mereno v
  // ose KOLME na jeho vlastni delku
  const bA = boxOf(entryA);
  const w = bA.max[ax.vAxis] - bA.min[ax.vAxis];
  if (!(w > 0) || !(Ly > w) || !(Lx > w)) return; // degenerovany cil - radeji nedelat nic

  const u0 = outer.min[ax.uAxis], v0 = outer.min[ax.vAxis];

  // 1) delky: A/B podel u = Ly - w, C/D podel v = Lx - w
  const setLen = (entry, targetLen) => {
    const localLen = entry.connectorsLocal[0].point.distanceTo(entry.connectorsLocal[1].point);
    if (localLen > 0 && targetLen > 0) applyLengthScale(entry, targetLen / localLen, 0);
    entry.object3d.updateMatrixWorld(true);
  };
  setLen(entryA, Ly - w);
  setLen(entryB, Ly - w);
  setLen(entryC, Lx - w);
  setLen(entryD, Lx - w);

  // 2) pozice: posunout kazdy dil tak, aby jeho bbox zacinal na cilove hrane
  const place = (entry, uMin, vMin) => {
    entry.object3d.updateMatrixWorld(true);
    const b = boxOf(entry);
    const d = new THREE.Vector3();
    d[ax.uAxis] = (u0 + uMin) - b.min[ax.uAxis];
    d[ax.vAxis] = (v0 + vMin) - b.min[ax.vAxis];
    entry.object3d.position.add(d);
    entry.object3d.updateMatrixWorld(true);
  };
  place(entryA, w, 0);
  place(entryC, Ly - w, w);
  place(entryB, 0, Lx - w);
  place(entryD, 0, 0);

  all.forEach(e => { e.object3d.userData.basePos = e.object3d.position.clone(); });
}
