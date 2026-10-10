// Ovladač renderu (Playwright + three.js, software WebGL). Čte GLB ze souboru, nikoli z paměti generátoru.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
let chromium;
for (const p of ['playwright', '/opt/node22/lib/node_modules/playwright']) { try { ({ chromium } = require(p)); break; } catch { /* další */ } }
const HERE = path.dirname(fileURLToPath(import.meta.url));

export class Renderer {
  async open(w = 1024, h = 1024) {
    this.w = w; this.h = h;
    this.browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
    this.page = await this.browser.newPage({ viewport: { width: w, height: h } });
    this.page.on('pageerror', e => console.error('PAGEERROR', e.message));
    this.page.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()); });
    await this.page.goto('file://' + path.join(HERE, 'stranka.html'));
    await this.page.evaluate(([w, h]) => window.init(w, h), [w, h]);
    return this;
  }
  async resize(w, h) { this.w = w; this.h = h; await this.page.setViewportSize({ width: w, height: h }); await this.page.evaluate(([w, h]) => window.size(w, h), [w, h]); }
  async load(glbFile, silhouette = false) {
    const b64 = fs.readFileSync(glbFile).toString('base64');
    return this.page.evaluate(([b, s]) => window.load(b, s), [b64, silhouette]);
  }
  async pose(p) { await this.page.evaluate(p => window.pose(p), p); }
  async bg(hex) { await this.page.evaluate(h => window.setBg(h), hex); }
  async hide(names) { await this.page.evaluate(n => window.hide(n), names); }
  async png(cam, out) {
    await this.page.evaluate(c => window.shot(c), cam);
    const buf = await this.page.locator('canvas').screenshot({ type: 'png' });
    fs.mkdirSync(path.dirname(out), { recursive: true }); fs.writeFileSync(out, buf); return out;
  }
  async mask(cam) {
    await this.page.evaluate(c => window.shot(c), cam);
    const b64 = await this.page.evaluate(() => window.pixels());
    return Buffer.from(b64, 'base64');
  }
  async close() { await this.browser.close(); }
}

// kamera z úhlů: azim (° kolem Z, 0 = pohled z +X na střed), elev (° nad horizontem), vzdálenost, ohnisko (fov svisle °)
export function kamera({ azim, elev, dist, fov = 30, target = [0, 0, 0], roll = 0, shiftX = 0, shiftY = 0 }) {
  const a = azim * Math.PI / 180, e = elev * Math.PI / 180;
  const pos = [target[0] + dist * Math.cos(e) * Math.cos(a), target[1] + dist * Math.cos(e) * Math.sin(a), target[2] + dist * Math.sin(e)];
  return { pos, target, fov, up: [0, 0, 1], roll, shiftX, shiftY };
}
