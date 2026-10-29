// Prohlídka více 3D modelů v jednom samostatném HTML (three.js + GLB jako base64, bez sítě).
// node nastroje/zabal_prohlidku.mjs <vystup.html> --titulek "Text" <složka-s-GLB>[,<složka>...] [--jmena <csv>[,<csv>...]] [--nejdriv 4932..,...]
// Názvy modelů se berou z CSV (první sloupec = SKU/číslo, sloupec 'název'/'nazev'), jinak z asset.extras.nazev, jinak z názvu souboru.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const out = args[0];
const opt = (n) => { const i = args.indexOf(n); return i > 0 ? args[i + 1] : null; };
const titulek = opt('--titulek') || '3D prohlídka modelů';
const slozky = (args.find((a, i) => i > 0 && !a.startsWith('--') && args[i - 1] !== '--titulek' && args[i - 1] !== '--jmena' && args[i - 1] !== '--nejdriv') || '').split(',').filter(Boolean);
const jmenaCsv = (opt('--jmena') || '').split(',').filter(Boolean);
const klic = (s) => String(s).toUpperCase().replace(/[^A-Z0-9]/g, '');
const nazvy = new Map();
for (const f of jmenaCsv) {
  const t = fs.readFileSync(f, 'utf8').replace(/^﻿/, '').split(/\r?\n/).filter(Boolean);
  const sep = t[0].includes(';') ? ';' : ',';
  const h = t[0].split(sep).map(x => x.trim());
  const iN = h.findIndex(x => /^(nazev|název|typ)$/i.test(x)); const iT = h.findIndex(x => /^typ$/i.test(x));
  const iNaz = h.findIndex(x => /^(nazev|název)$/i.test(x));
  for (const r of t.slice(1)) {
    const c = r.split(sep); const k = klic(c[0]);
    const typ = iT >= 0 ? (c[iT] || '').trim() : ''; const naz = (iNaz >= 0 ? c[iNaz] : c[iN] || '').trim();
    nazvy.set(k, [typ && typ !== naz ? typ : '', naz].filter(Boolean).join(' – '));
  }
}
const nazevPro = (id) => { const k = klic(id); if (nazvy.has(k)) return nazvy.get(k); for (const [kk, v] of nazvy) { if (kk.startsWith(k) || k.startsWith(kk)) return v; } return ''; };
const polozky = [];
for (const s of slozky) {
  const dir = path.isAbsolute(s) ? s : path.resolve(ROOT, '..', s);
  for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.glb')).sort()) {
    const id = f.replace(/\.glb$/, '');
    const varianta = id.includes('_') ? ' (varianta: ' + id.split('_').slice(1).join(' ') + ')' : '';
    const zakl = id.split('_')[0];
    const nazev = (nazevPro(zakl) || '').slice(0, 80);
    polozky.push({ id, nazev: `${zakl}${nazev ? ' · ' + nazev : ''}${varianta}`, soubor: path.join(dir, f) });
  }
}
polozky.sort((a, b) => a.id.localeCompare(b.id));
let t = fs.readFileSync(path.join(ROOT, 'prohlizec/prohlidka.html'), 'utf8');
const js = f => fs.readFileSync(path.join(ROOT, 'vendor', f), 'utf8').replace(/<\/script/gi, '<\\/script');
t = t.replace('<!--THREE_SCRIPTS-->', `<script>${js('three.min.js')}</script><script>${js('OrbitControls.js')}</script>`);
t = t.replaceAll('__TITULEK__', titulek.replace(/[<>&]/g, ''));
const data = polozky.map(p => ({ id: p.id, nazev: p.nazev, b64: fs.readFileSync(p.soubor).toString('base64') }));
t = t.replace('__MODELY__', () => JSON.stringify(data));
fs.writeFileSync(out, t);
console.log(out, (t.length / 1e6).toFixed(1) + ' MB,', polozky.length, 'modelů');
