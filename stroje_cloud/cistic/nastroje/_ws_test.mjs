import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('/opt/node22/lib/node_modules/playwright');
const server = await chromium.launchServer({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
process.env.CISTIC_WS = server.wsEndpoint(); process.env.CISTIC_DIMS='/tmp/d0.json';
const { execFileSync } = await import('node:child_process');
const t=Date.now();
try { console.log(execFileSync('node',['nastroje/eval_rozmery.mjs','r8','300'],{env:process.env,encoding:'utf8',timeout:60000}), Date.now()-t); } catch(e){ console.log('ERR', e.stderr?.toString().slice(0,800)); }
await server.close();
