# CZ obchodní podmínky a ochrana údajů pro objednávku hosta (bot7, 2026-10-04) – NÁVRH PRO PRÁVNÍKA, ne finál

## Co už existuje (ověřeno)
- `autovestavby.logiman.cz/obchodni-podminky`, `/ochrana-osobnich-udaju`: neexistují (404 „Kategorie nenalezena“); v `content_pages`, `content_categories` ani `app_settings` žádný takový text není.
- Starý e-shop `www.logiman.cz` (Shoptet) má jen `https://www.logiman.cz/podminky-ochrany-osobnich-udaju/`. Nelze na ni odkázat: uvádí uchování 3 roky od ukončení smlouvy, jmenuje Shoptet a Toptrans, e-mail a pověřence (v rozporu s Robertovým „uchování bez omezení do změny“ a „příjemci obecně, bez jmen“). Obchodní podmínky (VOP) tam žádné nejsou (`/obchodni-podminky/` = 404).

## Návrh
Soubor `docs/cz_pravni_navrh_objednavka_hosta.json` (formát jako SK/EN dokumenty, `lang: cs`, prošel parserem bota5 bez chyb): `terms` „Obchodní podmínky“ a `privacy` „Ochrana osobních údajů“. Je odvozený ze SK dokumentů („Prevádzkovateľ a objednávka“, „Ochrana osobných údajov“) a z Robertových pokynů: jen zákonné prvky, žádný e-mail, uchování zpráv, objednávek a dokladů bez omezení do změny, poskytovatelé obecně, montáž volitelná, cena dopravy po objednávce potvrzená před zálohovou fakturou, platba předem zálohovou fakturou, ceny bez DPH.

## Doporučené zatržítko (jedno, povinné)
`Souhlasím s <a>obchodními podmínkami</a> a beru na vědomí <a>zásady ochrany osobních údajů</a>.`
Bez „souhlasu se zpracováním“: právní základ je smlouva (čl. 6/1/b GDPR), ne souhlas. `consent` v API = potvrzení obchodních podmínek + seznámení se zásadami.
Odkazy: `https://autovestavby.logiman.cz/obchodni-podminky` a `https://autovestavby.logiman.cz/ochrana-osobnich-udaju`.

## Kde stránky provozovat (rozhodne bot16/bot5)
Doporučuji editovatelné stránky v adminu (pravidlo 55): buď stávající dokumenty `miniweb_documents` (kind terms/privacy, schvalování Robertem), nebo kategorie obsahu se slugy výše. Texty se nemají psát natvrdo do kódu.

## Rozhodnutí Roberta 2026-10-04: objednávka je pro firmy i spotřebitele stejná
Robert: „to si spotřebitel neobjedná, ale může, pro nás v tom není rozdíl“. Proto návrh obsahuje spotřebitelskou část: odstoupení od smlouvy, reklamace, mimosoudní řešení sporů. Dokument je pořád jen návrh pro právníka.

## Zatržítko (jedno, povinné) – sedí na obě skupiny
`Souhlasím s <a>obchodními podmínkami</a> a beru na vědomí <a>zásady ochrany osobních údajů</a>.` Pro spotřebitele je to potvrzení, že se s podmínkami (včetně informace o výjimce z odstoupení) seznámil před objednávkou; pro podnikatele přijetí podmínek. Nejde o souhlas se zpracováním (právní základ je smlouva).

## Co z toho plyne pro zobrazení a formulář (nutné posoudit, než půjde na živý web)
1. **Tlačítko objednávky.** Spotřebitel musí při objednání výslovně potvrdit povinnost platby (§ 1827 odst. 2 OZ; směrnice 2011/83/EU čl. 8 odst. 2): tlačítko má být označeno např. „Objednávka zavazující k platbě“, ne „Objednat“.
2. **Ceny včetně DPH.** Spotřebiteli se cena uvádí včetně DPH. Generátor dnes ukazuje cenu bez DPH. Protože formulář nerozlišuje firmu a spotřebitele, je řešením ukazovat u ceny vždy obojí (bez DPH i s DPH). Návrh podmínek říká: „Podnikatelům uvádíme ceny bez DPH, spotřebitelům včetně DPH.“ Dokud to generátor neumí, ta věta není pravdivá.
3. **Firma a IČO nejsou povinné** (spotřebitel je nemá). Text o ochraně údajů je upravený („u podnikatele též firmy a IČO“). Formulář objednávky a backend (bot5, bot16) musí povolit objednávku bez firmy a IČO; potvrzení „objednávám jménem podnikatele“ u spotřebitele nesmí být povinné.
4. **Odstoupení.** Výjimka u zboží upraveného podle přání spotřebitele je v § 1837 písm. d) OZ; stůl se vyrábí podle zvolené konfigurace. Informaci musí spotřebitel dostat před uzavřením smlouvy (§ 1820 odst. 1 písm. f)); je v podmínkách a v zatržítku. Volitelná služba montáže je služba: u ní právník posoudí, zda a jak se na ni výjimka vztahuje (§ 1837 písm. a), plnění až po souhlasu spotřebitele).
5. **Reklamace.** Lhůta 30 dnů a potvrzení pro spotřebitele (zákon č. 634/1992 Sb., § 19 odst. 3); délka záruční doby (24 měsíců od převzetí) v textu záměrně není, nechat na právníkovi (novela od 2023, rozdíl pro podnikatele).
6. **Mimosoudní řešení sporů:** ČOI jako subjekt ADR (§ 20d zákona 634/1992). Platforma ODR EU byla zrušena (2025), proto se neuvádí. Adresu ČOI ověřit.

## Předpoklady k potvrzení (právník / Robert)
1. „Adresa je sídlo, nikoli prodejna ani dílna“: převzato ze SK dokumentu; ověřit, že platí i pro CZ.
2. Žádné ustanovení o uzavření smlouvy (okamžik akceptace), dodací lhůtě, odpovědnosti ani rozhodném právu (Robert chce jen zákonné minimum). Právník posoudí, zda to pro spotřebitele stačí (§ 1811, § 1820 OZ: informační povinnosti, uložení smlouvy, jazyk, technické kroky uzavření).
3. Uchování bez časového omezení: GDPR (čl. 5/1/e) vyžaduje určit dobu podle účelu; právník posoudí formulaci.
4. Sekce Cookies je záměrně omezená na objednávku přes generátor stolu. Tvrzení „na webu nejsou žádné sledovací cookies“ jsem nedal, protože hlavní web měří návštěvnost (`page_views`).
