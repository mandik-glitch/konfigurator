# Mini-shop DE a HU: právní dokumenty (bot7, 2026-10-07) – NÁVRH PRO PRÁVNÍKA, ne finál

Soubory: `docs/miniweb_packstations_de_pravne_navrh.json` („Impressum und Bestellung“, „Datenschutz“) a `docs/miniweb_packstations_hu_pravne_navrh.json` („Szolgáltató és megrendelés“, „Adatvédelem“). Odvozeno ze SK/EN dokumentů a Robertových pokynů (jen zákonné minimum, žádný e-mail na webu, uchování bez omezení do změny, poskytovatelé obecně, montáž volitelná, cena dopravy po objednávce, platba předem proformou, ceny netto, uložení konfigurace se souhlasem). Prošly parserem bota5 bez chyb.

## Co právník / Robert musí posoudit před zveřejněním
1. **Kontaktní e-mail.** Německé Anbieterkennzeichnung (§ 5 DDG, dříve TMG) i maďarský zákon o elektronickém obchodu (Ekertv. 4. §) vyžadují mj. e-mailovou adresu poskytovatele. Robertovo pravidlo „žádný živý e-mail na webu“ s tím může být v rozporu (hrozí upomínky/pokuty, v DE zejména Abmahnung). Texty proto e-mail neobsahují, uvádějí formulář a telefon. Rozhodnutí Roberta.
2. **Zástupce společnosti.** Německé Impressum vyžaduje jméno oprávněného zástupce (jednatele). Neznám ho, do textu jsem ho nepsal.
3. **Jen firmám.** Návrh nemá spotřebitelskou část (odstoupení, reklamace, řešení sporů). Pokud mini-shop nebude technicky omezen na podnikatele (např. povinné pole firma + ověřené ID), je v DE a HU nutná spotřebitelská část (v DE navíc Widerrufsbelehrung, informační povinnosti dle VSBG).
4. **Ověření firem.** Pole IČO se ověřuje v ARES/RPO jen pro CZ/SK. Pro DE firmy je potřeba USt-IdNr. (VIES) nebo Handelsregisternummer, pro HU adószám/cégjegyzékszám (bot5 a bot16 řeší).
5. **DPH.** Texty říkají „Nettopreise / nettó árak“ a že DPH není v cenách. Pravidla pro dodání do DE/HU z CZ (osvobozená dodávka při platném ID vs. DPH země dodání / OSS) neřeší.
6. **Uchování bez časového omezení** (Robertův pokyn): GDPR čl. 5/1/e vyžaduje stanovit dobu podle účelu.
7. **AGB.** Dokument neobsahuje obchodní podmínky v plném rozsahu (uzavření smlouvy, dodací lhůty, odpovědnost za vady, rozhodné právo, příslušnost soudů). Právník posoudí, zda je to pro B2B v DE/HU dostačující.
8. **Překlad.** Němčina a maďarština jsou psané nerodilým mluvčím; před spuštěním doporučuji kontrolu rodilým mluvčím.
