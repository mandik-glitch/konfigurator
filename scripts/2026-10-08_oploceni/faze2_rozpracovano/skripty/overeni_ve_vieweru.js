// OVERENI GLB VE SKUTECNEM VIEWERU PROJEKTU (bot8, 2026-10-08, faze 1 generatoru oploceni): nacte GLB do webapp/js/v3d/viewer3d.js (three r128 + zavislosti z jsdelivr, CSS webapp/css/v3d.css) v headless
// Chromiu pres V3D.mount({arrayBuffer}), vypise v.state() (legacy / mode / warnings) a ulozi <out>.png (screenshot stranky) a <out>_snap.png (v.snapshot()). Jen cte, nic nenasazuje.
// Pouziti: node scripts/2026-10-08_oploceni/overeni_ve_vieweru.js <soubor.glb> <out.png> [real|wire]
// Nacte GLB do SKUTECNEHO vieweru projektu (webapp/js/v3d/viewer3d.js, three r128) v Chromiu a ulozi screenshot. Pouziti: node viewer_test.js <glb> <out.png> [mode: real|wire]
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const CDN = "https://cdn.jsdelivr.net/npm/three@0.128.0/";
const DEPS = ["build/three.min.js", "examples/js/controls/OrbitControls.js", "examples/js/loaders/GLTFLoader.js", "examples/js/environments/RoomEnvironment.js", "examples/js/renderers/CSS2DRenderer.js",
  "examples/js/shaders/HorizontalBlurShader.js", "examples/js/shaders/VerticalBlurShader.js"];
(async () => {
  const [glbPath, out, mode] = process.argv.slice(2);
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 900, height: 700 } })).newPage();
  const logs = [];
  page.on("console", m => logs.push(m.type() + ": " + m.text().slice(0, 220)));
  page.on("pageerror", e => logs.push("pageerror: " + e.message.slice(0, 220)));
  await page.setContent('<!doctype html><html><body style="margin:0;background:#fff"><style>#v{position:fixed;inset:0;z-index:1}#v canvas{display:block;width:100%;height:100%}</style><div id="v"></div></body></html>');
  await page.addStyleTag({ path: "/opt/konfigurator/webapp/css/v3d.css" });
  for (const d of DEPS) await page.addScriptTag({ url: CDN + d });
  await page.addScriptTag({ path: "/opt/konfigurator/webapp/js/v3d/viewer3d.js" });
  const b64 = fs.readFileSync(glbPath).toString("base64");
  const res = await page.evaluate(async ([b64, mode]) => {
    const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer;
    return await new Promise((ok) => {
      let v;
      const opts = { arrayBuffer: bin, hudKoty: false, onReady: () => { window.__v = v; ok({ ready: true, state: JSON.stringify(v.state()).slice(0, 700) }); }, onError: (e) => ok({ error: String((e && e.message) || e) }) };
      if (mode) opts.mode = mode;
      v = V3D.mount(document.getElementById("v"), opts);
      setTimeout(() => ok({ timeout: true }), 60000);
    });
  }, [b64, mode || ""]);
  console.log(JSON.stringify(res));
  console.log(logs.slice(0, 15).join("\n"));
  await page.waitForTimeout(2500);
  await page.screenshot({ path: out, timeout: 170000 });
  console.log("screenshot OK");
  const snap = await page.evaluate(async () => { try { return await window.__v.snapshot({ width: 900, type: "png", background: "#e8ecf1" }); } catch (e) { return "ERR " + e.message; } });
  if (snap && snap.startsWith("data:image")) { fs.writeFileSync(out.replace(".png", "_snap.png"), Buffer.from(snap.split(",")[1], "base64")); console.log("snapshot OK"); } else console.log("snapshot:", String(snap).slice(0, 200));
  await browser.close();
})();
