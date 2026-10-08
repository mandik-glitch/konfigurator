// Parametric local-frame leg part builder (T=30 fixed, Object_7), generalized
// from shape_geometry_methods.id=1/2/6 formulas, verified against
// scripts/2026-09-01_verify_leg_touchreport.js on Expert (H=1180) and Vito (H=1200).
const T = 30, half = 15, W = 349;

function buildPlain(H, CAP_H, capOffsetFromW) {
  return [
    { position: [W - half, (H - CAP_H) / 2, half], quaternion: [0, 0, 0, 1], scale: [1, (H - CAP_H) / 1000, 1], role: "zadni-svislice-dolni" },
    { position: [W / 2, half, half], quaternion: [0, 0, -0.707107, 0.707107], scale: [1, (W - 2 * T) / 1000, 1], role: "spojnice-dolni" },
    { position: [half, H / 2, half], quaternion: [0, 0, 0, 1], scale: [1, H / 1000, 1], role: "predni-svislice" },
    { position: [W - capOffsetFromW - half, H - CAP_H / 2, half], quaternion: [0, 0, 0, 1], scale: [1, CAP_H / 1000, 1], role: "cap" },
    { position: [W / 2, H - CAP_H - half, half], quaternion: [0, 0, -0.707107, 0.707107], scale: [1, (W - 2 * T) / 1000, 1], role: "spojnice-horni" },
  ];
}

// vyrez leg, using a given CUTOUT_H (bottom of zadni-svislice-nad-zarezem / top of sloupek)
// - matches Expert/Vito original 5/6-part designs; Y_new may differ from the
// design's base CUTOUT_H when scripts/2026-09-01 rule-4 extension has been applied.
function buildVyrez(H, CAP_H, CUTOUT_H, uskok, capOffsetFromW, includeShortBottomCross) {
  const parts = [
    { position: [W / 2, H - CAP_H - half, half], quaternion: [0, 0, -0.707107, 0.707107], scale: [1, (W - 2 * T) / 1000, 1], role: "spojnice-horni" },
    { position: [W - half, (CUTOUT_H + (H - CAP_H)) / 2, half], quaternion: [0, 0, 0, 1], scale: [1, (H - CAP_H - CUTOUT_H) / 1000, 1], role: "zadni-svislice-nad-zarezem" },
    { position: [W - capOffsetFromW - half, H - CAP_H / 2, half], quaternion: [0, 0, 0, 1], scale: [1, CAP_H / 1000, 1], role: "cap" },
    { position: [half, H / 2, half], quaternion: [0, 0, 0, 1], scale: [1, H / 1000, 1], role: "predni-svislice" },
    { position: [uskok - half, CUTOUT_H / 2, half], quaternion: [0, 0, 0, 1], scale: [1, CUTOUT_H / 1000, 1], role: "sloupek-pred-podbehem" },
  ];
  if (includeShortBottomCross) {
    const len = uskok - 2 * T;
    if (len > 0) parts.push({ position: [uskok / 2, half, half], quaternion: [0, 0, -0.707107, 0.707107], scale: [1, len / 1000, 1], role: "spojnice-dolni-kratka" });
  }
  return parts;
}

const FAMILY = {
  expert: { H: 1180, CAP_H: 260, CUTOUT_H: 395, uskok: 225, capOffsetFromW: 70, hasBottomCrossVyrez: true },
  vito: { H: 1200, CAP_H: 300, CUTOUT_H: 350, uskok: 175, capOffsetFromW: 79, hasBottomCrossVyrez: false },
};

module.exports = { T, half, W, buildPlain, buildVyrez, FAMILY };
