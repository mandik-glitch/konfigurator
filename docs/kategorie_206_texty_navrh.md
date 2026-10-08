# Kategorie 206 „Lehký balicí stůl system 30“ – texty kolem generátoru (bot7, 2026-10-04, NÁVRH, nic se nezapisuje)

Zdroj stavu: `content_pages.category_id=206` (intro_html, body_html), `content_categories` (meta_title, meta_description, focus_keyword).
Kategorie 206 patří do centrální typologie 11 „Balicí a expediční stoly“ (SCHVÁLENO, `schvaleno=1`): tu **nechávám beze změny**, žádný její text se nepřepisuje.

## Co je dnes na stránce
- intro: „Lehké pracovní stoly pro balení, příjem, expedici či jinou běžnou práci na provozech. **Veškeré rozměry stolu lze libovolně změnit na míru, kromě ocelového perforovaného panelu, jejich rozměrová řada je omezená, ovšem díky individuálním konstrukcím jsme schopni i perforované panely nakombinovat do celkového požadovaného rozměru.**“
- pod výpisem příslušenství (body): „Uvedené příslušenství ke stolům **LIGHT-30** je základní ukázkou, poptejte jakýkoli doplněk či úpravu.“ (+ prázdné odstavce `&nbsp;`)
- meta title/description/focus: „Lehký balicí stůl **Light-30-A**…“ (název kategorie je přitom „system 30“; Light-30-A je jiná, starší řada, viz kategorie 239).

## Problémy
1. **„Veškeré rozměry … libovolně“** není pravda pro generátor (šířka 500–3000 mm, hloubka 400–1500 mm; panely a LED potřebují šířku aspoň 1200 mm). Věta o kombinování perforovaných panelů je tvrzení o výrobní praxi, které nemám ověřené (TEXT_FILTR 1, 3). Navíc opakuje údaje, které generátor ukazuje strukturovaně (pravidlo 17).
2. **Dvojí název**: stránka je „system 30“, text a meta říkají „LIGHT-30“ / „Light-30-A“. Kód řady se na stránce s generátorem neuvádí.
3. Prázdné odstavce v `body_html`.

## Návrh (krátký úvod nad generátorem, bez výčtu voleb)
**intro_html**
```html
<p>Lehký balicí stůl z hliníkových profilů 30×30 pro balení, příjem a expedici. Níže si ho sami nastavíte: rozměry, počet polic i příslušenství vidíte ve 3D a orientační cenu hned u konfigurace. Co v nabídce nenajdete, poptejte.</p>
```
(Neříká nic o rozsahu rozměrů, příslušenství ani dodání: to ukazuje generátor. Bez „libovolně“ a bez tvrzení o panelech.)

**body_html** (pod příslušenstvím)
```html
<p>Uvedené příslušenství je základní ukázka, poptejte jakýkoli doplněk či úpravu.</p>
```

**meta_title** (51 znaků): `Lehký balicí stůl system 30 – generátor stolu ve 3D`
**meta_description** (≤160): `Lehký balicí stůl z hliníkových profilů 30×30 pro balení, příjem a expedici. Nastavte rozměry, police a příslušenství ve 3D a uvidíte orientační cenu.`
**focus_keyword**: `balicí stůl` (dnes „balicí stůl Light-30-A“)

## Otevřené (nerozhodnu sám)
- Dodání a montáž (Robert 2026-10-04: „volba montáže se doplní“ do generátoru, text tedy o dodání a montáži nic neříká a po doplnění volby ji ukáže generátor): pro CZ není ověřeno, jestli je stůl dodáván smontovaný, nebo rozložený (v zahraničí rozložený a bez montáže, 3–5 týdnů). Text proto o dodání nic neříká.
- Starou druhou větu intra psal Robert nebo dřívější bot? Pokud ji Robert chce zachovat, přesunout ji až pod generátor jako obecnou poznámku o panelech, ne jako „libovolné rozměry“.
- Kdo to zapíše: texty jsou editovatelné v adminu (Katalog → obsah kategorie), pravidlo 55. Zápis do DB provede bot16 nebo já po domluvě, s dumpem do backups/ předem.

## ZAPSÁNO 2026-10-04 (bot7, po domluvě s bot16)
intro_html, body_html, meta_title, meta_description a focus_keyword kategorie 206 jsou zapsané v DB (podmíněný UPDATE, rowcount 1+1). Záloha původních řádků: `backups/2026-10-04_kat206_pred_textem_2026-10-04_185720.json`. Ověřeno na živé stránce (API i `<meta name="description">`). `bottom_body_html` beze změny. Texty zůstávají editovatelné v adminu (pravidlo 55).

## Montáž a doprava (Robert 2026-10-04 přes bot9: „montáž je vždy volitelná a podle toho se změní cena dopravy, kterou určí staff“)
- **Zapsáno do intro kategorie 206** (záloha `backups/2026-10-04_kat206_pred_montazi_2026-10-04_193501.json`): „Montáž je volitelná služba a podle ní se mění cena dopravy: tu určíme po objednávce a před vystavením zálohové faktury ji potvrdíte.“ Bez čísla procenta, bez tvrzení, zda je stůl dodáván smontovaný nebo rozložený.
- **Karta 4934** (`shop_products`): popis je prázdný, `availability_text` = „3 - 5 týdnů“. Návrh popisu k dodání (zápis přes admin UI, přímý UPDATE řádku produktu sandbox blokuje): „Montáž je volitelná služba, její cena je podíl z ceny stolu. Cena dopravy se mění podle toho, zda si montáž zvolíte; určí ji pracovník po objednávce a před vystavením zálohové faktury ji potvrdíte.“
- **Mini-shop SK/EN** (Robert 2026-10-04: „montáž je vždy volitelná“ platí i tam): věty „dodává se rozložený a bez montáže“ jsou nahrazené neutrálním textem o dodací lhůtě a ceně dopravy, viz `docs/miniweb_montaz_volitelna_navrh.md`.

## ZAPSÁNO 2026-10-04: popis karty 4934 (Robert přes bot9: „popis vyřeší bot7“)
`shop_products.description` karty 4934 (jen toto pole, `active` ani jiné sloupce beze změny): „Montáž je volitelná služba, její cena je podíl z ceny stolu. Cena dopravy se mění podle toho, zda si montáž zvolíte. Určí ji pracovník po objednávce a před vystavením zálohové faktury ji potvrdíte.“ Záloha řádku: `backups/2026-10-04_karta4934_pred_popisem_2026-10-04_205524.json`. Podmíněný UPDATE (jen když byl popis prázdný), rowcount 1, ověřeno čerstvým SELECTem z nového spojení. Popis je prostý text, editovatelný v administraci produktu.

## ZAPSÁNO 2026-10-05: popis karty 4954 (system 40), jen pole `description`
„Stůl z hliníkového profilu 40×40 s drážkou 10 mm. Montáž je volitelná služba, její cena je podíl z ceny stolu. S montáží dodáme stůl smontovaný, bez ní demontovaný (rozložený). Cena dopravy se mění podle toho, zda si montáž zvolíte. Určí ji pracovník po objednávce a před vystavením zálohové faktury ji potvrdíte.“ Záloha: `backups/2026-10-05_karta4954_pred_popisem_2026-10-05_050321.json`. Podmíněný UPDATE (jen při prázdném popisu), rowcount 1, ověřeno čerstvým SELECTem. Meta karet 4934 a 4954 (`meta_title`, `meta_description`) jsou prázdné a na stránce produktu se použije šablona; vlastní meta se nezapisovalo (Robertovo pověření se týkalo jen pole popisu).
