// Genericky, parametrizovany leg-builder pro ProAce rodinu (19 karoserii) -
// port z tmp_2026-08-30_build_depth_variants_both.js (D uz byl parametr tam),
// navic parametrizovano H a CUTOUT_H (ruzne velikosti karoserie v teto
// rodine - City/mid-size/Max - potrebuji ruzne H, viz rule 2 v zadani).
// D=349, T=30 jsou nativni rozmery noh ProAce (custom_shapes.id=506/507,
// "Noha.1.ProAce.H1.1180.349") - overeno 2026-08-31 primym rozborem ulozenych
// dat (506/507): vsech 5+6 dilu presne odpovida temto vzorcum pri T=40
// (puvodni 40x40 profil pred prevodem na 30x30 dle shape_geometry_methods.id=1
// "prevod-profilu-zachovanim-rozmeru" - prevod je matematicky totozny s
// pouhym dosazenim T=30 do stejnych vzorcu, protoze metoda cely navrh
// zachova a meni jen T).
const CAP_H_DEFAULT = 260;
const CAP_OFFSET_FROM_WALL_DEFAULT = 70;
const WALL_CLEARANCE_ARCH_DEFAULT = 349 - 225; // 124mm, fyzicka vule pred podbehem (nezavisla na D)

function part(xCenter, yCenter, lengthY, vertical, zCenter, role) {
  return {
    position: [xCenter, yCenter, zCenter],
    quaternion: vertical ? [0, 0, 0, 1] : [0, 0, -0.707107, 0.707107],
    scale: [1, lengthY / 1000, 1],
    role,
  };
}

function buildPlainAtDepth(D, H, opts = {}) {
  const T = opts.T ?? 30;
  const CAP_H = opts.CAP_H ?? CAP_H_DEFAULT;
  const CAP_OFFSET_FROM_WALL = opts.CAP_OFFSET_FROM_WALL ?? CAP_OFFSET_FROM_WALL_DEFAULT;
  const zCenter = T / 2;
  const rungLo = T, rungHi = D - T;
  const capRight = D - CAP_OFFSET_FROM_WALL, capLeft = capRight - T;
  const skipCap = D <= CAP_OFFSET_FROM_WALL + 2 * T;
  const parts = [];
  parts.push(part(T / 2, H / 2, H, true, zCenter, "predni-svislice"));
  if (!skipCap) {
    const rungLen = rungHi - rungLo;
    parts.push(part((rungLo + rungHi) / 2, T / 2, rungLen, false, zCenter, "spojnice-dolni"));
    parts.push(part((rungLo + rungHi) / 2, H - CAP_H - T / 2, rungLen, false, zCenter, "spojnice-horni"));
    parts.push(part(D - T / 2, (H - CAP_H) / 2, H - CAP_H, true, zCenter, "zadni-svislice-dolni"));
    parts.push(part((capLeft + capRight) / 2, H - CAP_H / 2, CAP_H, true, zCenter, "cap"));
  } else {
    const rungLen2 = (D - T) - T;
    if (rungLen2 > 0.01) parts.push(part((T + (D - T)) / 2, T / 2, rungLen2, false, zCenter, "spojnice-dolni"));
    parts.push(part(D - T / 2, (H - CAP_H) / 2, H - CAP_H, true, zCenter, "zadni-svislice-dolni"));
  }
  return parts;
}

function buildVyrezAtDepth(D, H, CUTOUT_H, opts = {}) {
  const T = opts.T ?? 30;
  const CAP_H = opts.CAP_H ?? CAP_H_DEFAULT;
  const CAP_OFFSET_FROM_WALL = opts.CAP_OFFSET_FROM_WALL ?? CAP_OFFSET_FROM_WALL_DEFAULT;
  const WALL_CLEARANCE_ARCH = opts.WALL_CLEARANCE_ARCH ?? WALL_CLEARANCE_ARCH_DEFAULT;
  const zCenter = T / 2;
  const skipColumn = D <= WALL_CLEARANCE_ARCH + 2 * T;
  const skipCap = D <= CAP_OFFSET_FROM_WALL + 2 * T;
  const parts = [];
  parts.push(part(T / 2, H / 2, H, true, zCenter, "predni-svislice"));

  if (!skipColumn) {
    const colRight = D - WALL_CLEARANCE_ARCH, colLeft = colRight - T;
    parts.push(part((colLeft + colRight) / 2, CUTOUT_H / 2, CUTOUT_H, true, zCenter, "sloupek-pred-podbehem"));
    const rungLen0 = colLeft - T;
    if (rungLen0 > 0.01) parts.push(part((T + colLeft) / 2, T / 2, rungLen0, false, zCenter, "spojnice-dolni"));
    if (!skipCap) {
      const closeLeft = T, closeRight = D - T, closeLen = closeRight - closeLeft;
      if (closeLen > 0.01) {
        parts.push(part((closeLeft + closeRight) / 2, CUTOUT_H + T / 2, closeLen, false, zCenter, "pricka-uzavreni-vyrezu"));
      }
    }
  }
  if (!skipCap) {
    const rungLo = T, rungHi = D - T;
    const rungLen = rungHi - rungLo;
    const capRight = D - CAP_OFFSET_FROM_WALL, capLeft = capRight - T;
    const upperH = (H - CAP_H) - CUTOUT_H;
    parts.push(part(D - T / 2, CUTOUT_H + upperH / 2, upperH, true, zCenter, "zadni-svislice-nad-zarezem"));
    parts.push(part((rungLo + rungHi) / 2, H - CAP_H - T / 2, rungLen, false, zCenter, "spojnice-horni"));
    parts.push(part((capLeft + capRight) / 2, H - CAP_H / 2, CAP_H, true, zCenter, "cap"));
  }
  return parts;
}

// Rule 4 extension: nahradi "sloupek-pred-podbehem" + navazujici dily
// realnym Y_new (odvozeny fresh kolizni krokovani proti KONKRETNI karoserii,
// viz proace_pipeline_run.js), stejny vzor jako Vivaro
// buildVyrezAtDepthExtended.
function buildVyrezAtDepthExtended(D, H, CUTOUT_H, Y_new, opts = {}) {
  const T = opts.T ?? 30;
  const CAP_H = opts.CAP_H ?? CAP_H_DEFAULT;
  const TOP_Y = H - CAP_H;
  const base = buildVyrezAtDepth(D, H, CUTOUT_H, opts);
  const zCenter = T / 2;
  const parts = base.filter(p => !["sloupek-pred-podbehem", "pricka-uzavreni-vyrezu", "zadni-svislice-nad-zarezem", "spojnice-dolni"].includes(p.role));
  const orig = base.find(p => p.role === "sloupek-pred-podbehem");
  const colX = orig.position[0];
  // Nalez (bot16, 2026-08-31, Proace Max rodina - tesny podbeh blizko
  // podlahy): pokud realny Y_new (fresh kolizni krokovani proti KONKRETNI
  // karoserii) vyjde MALY (blizko/pod T), puvodni "spojnice-dolni" (fixni
  // pozice odvozena z nominalniho CUTOUT_H, NEZAVISLA na Y_new) a
  // repozicovana "pricka-uzavreni-vyrezu" (na Y_new+T/2) se vertikalne
  // srazi - overeno primo (7 Proace Max variant, self-kolize "spojnice-
  // dolni"<->"pricka-uzavreni-vyrezu"). Fyzikálně spravne reseni: kdyz je
  // sloupek pred podbehem tak nizky, ze by "uzavirajici" pricka zasahovala
  // do stejne vysky jako spodni spojnice, cely nizky sloupek/spojnice/
  // pricka trojice ztraci smysl (temer zadny uzitecny prostor pod
  // podbehem) - zjednodusit na SAMOTNY protazeny "zadni-svislice-nad-
  // zarezem" (uz sam o sobe sahá od Y_new skoro k podlaze), bez
  // spojnice-dolni a bez pricka.
  const degenerate = Y_new <= T + 1e-6;
  if (!degenerate) {
    parts.push({ position: [colX, Y_new / 2, zCenter], quaternion: [0, 0, 0, 1], scale: [1, Y_new / 1000, 1], role: "sloupek-pred-podbehem" });
    const origPricka = base.find(p => p.role === "pricka-uzavreni-vyrezu");
    if (origPricka) {
      parts.push({ position: [origPricka.position[0], Y_new + T / 2, zCenter], quaternion: origPricka.quaternion, scale: origPricka.scale, role: "pricka-uzavreni-vyrezu" });
    }
    const origSpojniceDolni = base.find(p => p.role === "spojnice-dolni");
    if (origSpojniceDolni) parts.push(origSpojniceDolni);
  }
  const upperLen = TOP_Y - Y_new;
  parts.push({ position: [D - T / 2, (Y_new + TOP_Y) / 2, zCenter], quaternion: [0, 0, 0, 1], scale: [1, upperLen / 1000, 1], role: "zadni-svislice-nad-zarezem" });
  return parts;
}

function legEndcapRoles(type) { return type === "vyrez" ? ["predni-svislice", "zadni-svislice-nad-zarezem", "cap"] : ["predni-svislice", "zadni-svislice-dolni", "cap"]; }
function topEndcapsFor(legParts, roles, CAP_FLANGE_THICKNESS) {
  return legParts.filter(p => roles.includes(p.role)).map(p => {
    const lenMm = p.scale[1] * 1000;
    const topY = p.position[1] + lenMm / 2 + CAP_FLANGE_THICKNESS;
    return { part_id: "product_3071", position: [p.position[0], topY, p.position[2]], quaternion: [0.7071067811865475, 0, 0, 0.7071067811865475], scale: [1, 1, 1], role: "zaslepka-" + p.role };
  });
}

module.exports = {
  buildPlainAtDepth, buildVyrezAtDepth, buildVyrezAtDepthExtended,
  legEndcapRoles, topEndcapsFor,
  CAP_H_DEFAULT, CAP_OFFSET_FROM_WALL_DEFAULT, WALL_CLEARANCE_ARCH_DEFAULT,
};
