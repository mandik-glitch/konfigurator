# Pravidla UI — navigační šipky (galerie/carousel/lightbox)

Autor: bot4 (Claude / Cowork), 2026-08-09.
Stav: PLATNÉ PRAVIDLO — závazný standard pro jakoukoli budoucí práci na
navigačních šipkách (listování obrázky, galerie, lightbox, carousel)
kdekoli na webu.

## Zadání

Robert: "ty šipky napříč listováním obrázků či galeriemi potrebujeme
vetsi a ve stylu HUD navrhni nejake koncepty vzhledu" — následně vybral
**Koncept 2 ("Cut Corner")** ze 3 navržených konceptů (mockup viz
`galerie-sipky-koncepty.html` v tomto adresáři) a nechal ho aplikovat:
"aplikuj vzhled 2, zapis to di pravidel pro dalsi praci".

## Standard: "Cut Corner"

Vizuální jazyk odvozený ze stávajícího `#pdAddCartBtn` ("DO KOŠÍKU" na
detailu produktu) — stejný fill-sweep hover efekt, jen aplikovaný na
kruhové/čtvercové navigační prvky.

**Tvar** — `clip-path` seříznuté rohy (ne `border-radius`):
```css
clip-path: polygon(
  0 Npx, Npx 0,
  100% 0, 100% calc(100% - Npx),
  calc(100% - Npx) 100%, 0 100%
);
```

**Barva** — pevná (theme-independent) zelená `#2fe07a`, NE `var(--accent)`
ani jiná theme-reaktivní proměnná. Border `1px solid #2fe07a`.

**Hover fill-sweep**:
```css
background-image: linear-gradient(#2fe07a, #2fe07a);
background-size: 0% 100%;
background-repeat: no-repeat;
/* na hover: background-size: 100% 100%; */
```
Ikona při hoveru změní barvu na tmavou (`#06140c`), jakmile ji fill
"přejede" — kontrast na zelené ploše.

**Ikony** — SVG chevrony, ne HTML entity (`&#8249;`/`&#8250;` apod.):
```html
<svg viewBox="0 0 24 24" fill="none" stroke-width="2.5"
     stroke-linecap="round" stroke-linejoin="round">
  <polyline points="15 18 9 12 15 6"></polyline>
</svg>
```
(`points="9 18 15 12 9 6"` pro opačný směr). Malý `transform:translateX(±Npx)`
posun ikony na hover ve směru pohybu (směrová zpětná vazba).

**Rozměry podle kontextu** (poměry z první implementace, škáluj podle
prostoru):
| Kontext | Velikost | Clip-path cut | Ikona |
|---|---|---|---|
| Lightbox (fullscreen) | 84px | 14px | 30px |
| Lightbox — mobil (`max-width:640px`) | 56px | 10px | 22px |
| Carousel v těle textu | 44px | 9px | 20px |
| Carousel — úzký kontejner (`@container carousel (max-width:260px)`) | 32px | 6px | 15px |

**Přístupnost**: `@media (prefers-reduced-motion:reduce)` vypíná
transitions. Disabled stav: `opacity:.25`, hover efekt se nespouští.

**CSS specificita — past, na kterou narazíš**: pokud šipky žijí uvnitř
kontejneru, který má obecné pravidlo typu `#idKontejneru button {...}`
(ID+typ selektor, specificita (1,0,1)), NESTAČÍ přebít ho holým
`#prevBtn, #nextBtn {...}` (jen ID, (1,0,0)) — prohraje. Musíš scopovat
přes rodiče: `#idKontejneru #prevBtn, #idKontejneru #nextBtn {...}`
((2,0,0)).

## Kde je to použité (reference implementace)

`webapp/category.html`:
- `#clbPrev`/`#clbNext` (fullscreen lightbox nad galeriemi v těle textu
  kategorie) — plné rozměry z tabulky výše.
- `.carousel-arrow` (vestavěný carousel obrázků v těle textu) — zmenšená
  varianta.

Commit: viz `git log --oneline -- webapp/category.html | grep -i "cut corner"`.

## Pravidlo do budoucna

Jakákoli NOVÁ navigační šipka pro listování obrázky/galeriemi/carousely
(produktová galerie, homepage mozaika, kdekoli jinde) se stylizuje podle
tohoto standardu — ne znovu vymýšlet vlastní vzhled. Pokud si nejsi jistý
rozměry pro nový kontext, drž se poměru cut/velikost/ikona z tabulky výše
(cut ≈ velikost/6, ikona ≈ velikost/2.8).
