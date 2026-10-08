// Spolecne pomucky testu "Priklady realizaci" (bot16, 2026-10-07): ZIVA galerie z e-shopu (read-only GET /api/gallery) a REALNE soubory fotek z disku (webapp/content-files/gallery/...), takze se
// overuje skutecne nacteni obrazku (naturalWidth > 0). Zadne zapisy, zadna DB.
const https = require('https'), fs = require('fs'), path = require('path');
const REPO = path.join(__dirname, '../..');
const ZIVE = 'https://autovestavby.logiman.cz';
const stahni = url => new Promise((res, rej) => https.get(url, r => { let b = ''; r.on('data', c => b += c); r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(e); } }); }).on('error', rej));
const GALERIE_TAG = { vestavby: 'vestavby_dodavek', stoly: 'realizace_stolu' };
async function nactiGalerie() {
  const v = await stahni(ZIVE + '/api/gallery?category=vestavby_dodavek'), s = await stahni(ZIVE + '/api/gallery?category=realizace_stolu');
  return { vestavby: v, stoly: s };
}
// route pro galerii a obrazky: vraci true, kdyz trasu obslouzila
function galerieRoute(route, u, G, opt = {}) {
  const json = (b, st = 200) => route.fulfill({ status: st, contentType: 'application/json', body: JSON.stringify(b) });
  if (u.pathname === '/api/gallery') {
    if (opt.galerieChyba) { json({ error: 'x' }, 500); return true; }
    const tag = u.searchParams.get('category');
    const src = tag === 'vestavby_dodavek' ? G.vestavby : tag === 'realizace_stolu' ? G.stoly : { images: [] };
    json(opt.upravGalerii ? opt.upravGalerii(src, tag) : src); return true;
  }
  if (u.pathname.startsWith('/content-files/gallery/')) {
    const f = path.join(REPO, 'webapp', decodeURIComponent(u.pathname));
    if (fs.existsSync(f)) { const doIt = () => route.fulfill({ status: 200, contentType: 'image/jpeg', body: fs.readFileSync(f) }); if (opt.zpozdeniObrazku) setTimeout(doIt, opt.zpozdeniObrazku); else doIt(); return true; }
  }
  return false;
}
module.exports = { REPO, ZIVE, stahni, nactiGalerie, galerieRoute, GALERIE_TAG };
