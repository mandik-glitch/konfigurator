# Prvek „Připni cokoli“ do mřížky na kartě (např. karta stolu v mini-shopu)

Autor bot10, 2026-10-03. Samopohyblivá živá 3D ukázka (WebGL v prohlížeči, žádné video, žádné rendery na serveru): do T-drážky profilu se zasune matice, šroub přitáhne díl, otočná matice se při dotahování otočí o 90°. Popisky v 3D mají jazyky cs/en/sk (de/pl jsou v souboru, ale vypnuté do ověření). Bez značky: v prvku, pluginu, textech ani v modelu není jméno firmy ani dodavatele (hlídá `test_tile.js`).

## Vložení (jedno volání)
```html
<div id="policko"></div>
<script src="/js/pripni-cokoli-tile.js"></script>
<script>
  PripniCokoliTile.mount(document.getElementById('policko'), { lang: 'en', accent: '#14b8a6', version: '20261003' })
    .then(function (ctl) { /* ctl.pause(), ctl.play(), ctl.destroy() */ });
</script>
```
Prvek si sám doloží three (CDN jsdelivr, jako konfigurátor), `/js/v3d/viewer3d.js` a `/js/v3d/demo-stavebnice.js` (pokud už stránka V3D má, nic nenačítá). CSS prohlížeče `/css/v3d.css` stránka musí mít (kartový konfigurátor ho má).

Možnosti: `lang` (cs/en/sk), `accent` (barva popisků/spojnic; mini-shop tyrkys), `bg`, `autoplay` (true), `steps` (false; true = tlačítka kroků), `caption` (false; text nese popisek v 3D), `speed`, `version` (?v= k modelu a textům), `assetBase` (`/pripni-cokoli/`), `texts` (přepis textů z i18n obchodu). Podrobně v hlavičce `webapp/js/pripni-cokoli-tile.js`.

Chování: poměr 4:3, přizpůsobí se šířce políčka (do 640 px popisky nahoře, nad 640 px vlevo), animace se zastaví mimo obrazovku a na kartě na pozadí, „omezit animace“ startuje pozastaveně, klepnutí ani tažení za model animaci nezastaví. Doporučená šířka políčka ≥ 320 px.

## Automatické párování podle profilu generátoru (Robert 2026-10-04)
Animace se k prvku páruje sama podle profilu, se kterým generátor pracuje. Do `mount` stačí předat identifikátor profilu:
```js
PripniCokoliTile.mount(el, { profile: 'systém 30' /* nebo '30x30', 'Object_7', '1.1.08.030030.03', 3457 */, lang: 'en' }).then(function (ctl) { if (!ctl) { /* profil bez animace: políčko je prázdné, hostitel ho může skrýt */ } });
PripniCokoliTile.supports('30x30').then(function (ano) { /* zjistit předem, zda se políčko vůbec ukáže */ });
```
Registr je v `webapp/pripni-cokoli/texty.json` (`_profily`: klíč varianty, `aliasy`, soubor modelu; `_varianty`: věty, které se pro profil liší; `_vychozi_profil`). Dnes: **40×40 / drážka 10** (`stavebnice-demo.glb`) a **30×30 / drážka 8** (`stavebnice-demo-30x30.glb`, model od externího bota Johna, **verze v5 schválená Robertem 2026-10-04, živá** (`zive:true`), starší v2–v4 jsou v `nahled/`). Rozpoznání je tolerantní: `30`, `30x30`, `30 × 30`, cfg_dily `Object_7`/`Object_11`, SKU profilu, číslo produktu profilu 3457/3468 i libovolný text s „systém 30“ (např. název receptu „Stůl systém 30 SP002“). Profil mimo registr (45×45 a další) = `mount` vrátí `null`, nikdy se neukáže animace jiného profilu. Samostatná stránka má totéž v parametru `?profil=` (neznámý nebo chybějící = 40×40). Nový profil = nový záznam v `_profily` a `_varianty` + model v `webapp/pripni-cokoli/`.
**Odkud se bere profil:** generátor stolu (bot8) nově nese ve veřejné odpovědi konfigurátoru `GET /api/shop/products/4934/configurator` pole `profile: "30x30"` a `profile_mm: 30` (`api/stul_shop.py`, kontrakt `docs/KONTRAKT_KONFIGURATOR_UI.md`; do ostrého API s dalším nasazením api). Mini-shop bere profil z `profil_mm` produktu (`api/miniweb.py::_profil_info`) a předává `profile: '30x30'` (bot16). Jiný hostitel předá `profile` z pole konfigurátoru; rozpoznání z názvu receptu („Stůl systém 30 SP002“) je jen záloha. Pilotní stůl „systém 30“ pracuje s profilem 30×30, takže se mu přiřadí animace 30×30.

## Co musí povolit whitelist vhostu mini-shopu (`scripts/gen_miniweb_vhost.py`, nutná regenerace vhostu a reload nginx = krok pro Roberta)
Dnes je povoleno `/js/v3d/*` a `/css/v3d.css` (stačí pro viewer a plugin), chybí jen čtyři soubory (do `locations()` ve skriptu; je to f-string, proto dvojité závorky):
```
    location = /js/pripni-cokoli-tile.js {{ root {WEBAPP}; expires 1h; }}
    location = /pripni-cokoli/texty.json {{ root {WEBAPP}; expires 1h; }}
    location = /pripni-cokoli/stavebnice-demo.glb {{ root {WEBAPP}; expires 1h; }}
    location = /pripni-cokoli/stavebnice-demo-30x30.glb {{ root {WEBAPP}; expires 1h; }}
```
(po každé úpravě souborů znovu vystavit verzi pro Cloudflare, jako u ostatních JS mini-shopu: `scripts/miniweb_verze.py`, a změnit `version` v `mount`). Prvek nepotřebuje `schema-*.svg` ani `pripni-cokoli.html`; ty na mini-shopu povolené nejsou.

## Soubory
`webapp/js/pripni-cokoli-tile.js` (prvek), `webapp/js/v3d/demo-stavebnice.js` (plugin), `webapp/pripni-cokoli/stavebnice-demo.glb` + `texty.json` (data), samostatná stránka `webapp/pripni-cokoli.html` (pro weby a online nabídku, návrh s noindex). Model se generuje v `scripts/stavebnice/` (README: jak přidat další díl). Testy: `scripts/2026-10-03_pripni_cokoli_testy/run_all.sh` (stránka, plugin) a `test_tile.js` (prvek, cesty jako whitelist).

## Náhled návrhů externího bota Johna (pravidlo 60 ve WORKFLOW.md)
Práci Johna musí nejdřív vidět a schválit Robert, nasazuje se jen do náhledu: `https://autovestavby.logiman.cz/pripni-cokoli.html?profil=30&nahled=<id>` (např. `nahled=v3`) načte model z `webapp/pripni-cokoli/nahled/<id>/stavebnice-demo-30x30.glb` místo živého, ukáže oranžové upozornění „NÁHLED … čeká na schválení Robertem“ a nemění živou stránku ani prvek do mřížky (ten náhled nezná). Id je `[a-z0-9_-]` do 24 znaků, neplatné se ignoruje. Po schválení se soubor zkopíruje na živou cestu a registr/`PC_V` se zvýší. Stav 2026-10-04: živé 30×30 je Johnova **v5** (schválil Robert 2026-10-04; registr `_profily['30x30-d8'].zive = true`, model `stavebnice-demo-30x30.glb`, `PC_V` zvýšen, nová verze prvku pro mini-shop). Variantu jde kdykoli stáhnout jedním krokem `zive: false` (živá stránka s `?profil=30` pak ukáže jen „Animace pro tento profil se připravuje“, prvek do mřížky vrátí `null`, `supports('30x30')` = false). Náhledy dál fungují: `nahled/v2`–`v5` (starší verze) a `nahled/spoj-sroubem-v1` (nová verze Johna s dalším krokem „Spoj šroubem“, 10,6 MB; živá v5 beze změny).

**Texty náhledu:** volitelný soubor `nahled/<id>/texty.json` (tvar jako `texty.json`, jazyky cs/en/sk/de/pl) přidá nebo přepíše texty JEN v náhledu, typicky popisky a název nových kroků návrhu. Přebírají se jen řetězce (a o úroveň hloub `cues` a `viewer`), cokoli jiného se ignoruje; živý registr se nemění a bez `?nahled=` se soubor ani nestahuje (`js/pripni-cokoli-page.js`: `mergeNahledTexty`; test `scripts/2026-10-03_pripni_cokoli_testy/test_nahled_texty.js`).
