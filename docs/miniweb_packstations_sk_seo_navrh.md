# Mini-shop SK – SEO návrh názvu a meta popisov (bot7, 2026-10-02, aktualizované pre B2B, NÁVRH, nič sa nenahráva)

Doména: `baliace-stoly.top`. Podklad: našepkávač Googlu pre SK (hl=sk, gl=sk), relatívna popularita bez absolútnych čísel. Slovenský dopyt je **tenký**: väčšina
výrazov má len presnú zhodu bez rozšírení, ide o úzky B2B segment s nízkou konkurenciou. Ceny sú uvedené bez DPH (`price.excl_vat`); texty nič nevysvetľujú o tom, komu sa predáva (Robert).

## Čo ľudia na SK hľadajú
- **„pracovný stôl"** je najsilnejší všeobecný výraz (do dielne, skladací, do kancelárie, na mieru).
- **„baliaci stôl", „baliace stoly", „baliace pracovisko", „baliaca stanica", „stôl na balenie balíkov"** existujú, ale bez rozšírení, teda málo hľadané. Ľudia často píšu bez diakritiky.
- **„packstation"** na SK znamená len DHL boxy v Nemecku: nepoužívať. **„dielenský stôl"** je spotrebiteľský (Güde, so zásuvkami): hodí sa do textov, nie do názvu.
- **„konfigurátor"** nehľadá nikto a je to zakázané slovo vo verejnom texte: nahrádza ho „zostavenie", „konfigurácia", „nastaviť stôl".

## Názov obchodu (`brand.name`, do titulkov „stránka – názov")
1. **Baliace a pracovné stoly** (odporúčam) – zhoduje sa s doménou `baliace-stoly.top`, pokrýva dva hlavné výrazy, krátky (24 znakov).
2. Pracovné a baliace stoly – rovnaké slová v inom poradí.
3. Baliace pracoviská a pracovné stoly – blízko B2B výrazu „pracovisko", dlhší (35 znakov).

Kategória: **Pracovné a baliace stoly**. Produkt: **Konfigurovateľný baliaci a pracovný stôl**. Poznámka o cenách „bez DPH" je v `b2b.notice`.

## Titulky a meta popisy (dĺžky v zátvorke, cieľ titulok <= 60, popis <= 155 znakov)
| Stránka | Titulok | Meta popis |
|---|---|---|
| Úvodná stránka | Baliace a pracovné stoly – Navrhnite si vlastný baliaci stôl (60) | Konfigurovateľné baliace a pracovné stoly z hliníkových profilov. Nastavte rozmery a príslušenstvo, pozrite si 3D a objednajte. Ceny bez DPH. (146) |
| Kategória | Pracovné a baliace stoly – Baliace a pracovné stoly (57) | Pracovné a baliace stoly z hliníkových profilov: vlastná šírka, hĺbka a výška, police a príslušenstvo. Dodanie 3–5 týždňov. (150) |
| Produkt | Konfigurovateľný baliaci a pracovný stôl – Baliace a pracovné stoly (72) | Baliaci a pracovný stôl s rámom z hliníkových profilov, vyrobený na mieru. Zvoľte rozmery, police a príslušenstvo a pozrite si 3D. (146) |
| Kontakt | Kontakt – Baliace a pracovné stoly (34) | Máte otázku k baliacemu alebo pracovnému stolu? Napíšte nám cez formulár a odpovieme vám. (126) |

Poznámky:
- **Titulok produktu je dlhší ako 60 znakov** (názov + názov obchodu). Odporúčam pri produkte vynechať príponu „– názov obchodu" alebo ju skrátiť (rovnako EN).
- **Košík, dopyt a náhľady: `noindex`**, ostatné stránky po spustení indexovať. Dnes majú všetky HTML šablóny `noindex` a prázdny `<title>` (titulky len v JS), chýba meta popis,
  canonical, hreflang (`config.alternates`) a štruktúrované dáta. Pred spustením treba server-side meta z `name` + `summary` (rovnako ako pri EN).
- **Slugy sú spoločné pre všetky jazyky** (katalóg je jazykovo neutrálny), takže SK adresy majú anglický slug. Slovenské slugy by pomohli SEO, ale vyžadujú podporu per-jazykových slugov (bot5), nízka priorita.
- **hreflang** medzi `baliace-stoly.top` (sk) a `packing-tables.top` (en) cez `config.alternates`.

## Úplné SEO a úvodné texty (bot7, 2026-10-03)
- Úvodné texty (H1, úvod, 4 výhody, kroky pre dopyt, výzva, FAQ 8 otázok, alt texty): `miniweb_packstations_sk_home_navrh.json` (kľúče pre `i18n/sk.json`; nový kľúč `home.h1`).
- Šablóny: `miniweb_seo_sablony_navrh.json` (titulky a popisy všetkých typov stránok vrátane noindex, og/twitter, JSON-LD, klíčové slová, robots.txt, sitemap, pokyny pre server-side).
- Dôležité: stránky sa dnes kreslia v JS (shell má `noindex`, `lang=en`, prázdny title) a adresy sú `/miniweb/product.html?id=1`. Pre indexáciu musí server vložiť meta, JSON-LD a ideálne aj H1 a FAQ do HTML; `robots.txt` je dnes `Disallow: /`; `/miniweb/` ani `/api/miniweb/` sa nesmú blokovať.

**Zmena 2026-10-03 (Robert):** shop má košík (hosť bez účtu, platba vopred zálohovou faktúrou), preto sú kroky „Nastavte stôl / Pozrite si cenu / Pridajte do košíka a odošlite objednávku“; `og:image` sa vynecháva, kým bot4 neoverí rendery bez loga; indexácia sa zapne hneď po dodaní server-side meta.
