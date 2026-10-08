# Nová kategorie „Robustní balicí stůl system 40“ – texty (bot7, 2026-10-04, NÁVRH, čeká na id kategorie od bot10)

Kostru (název, adresa, pod 182, viditelná) zakládá bot10; generátor stolu systém 40 (karta #4954) připojuje v `category.html`. Texty píšu já, z ověřených zdrojů (pravidlo 16) a jinak formulované než kategorie 206 (pravidlo 6).

Ověřené zdroje: profil 40×40 = SuperLight S10 s drážkou 10 mm (`VLASTNOSTI_PROFILU.md`); generátor „system 30|40“ má stejné rozsahy a stejné příslušenství jako system 30, vnější rozměry stolu stejné, nohy dovnitř o 5 mm (`api/stul_konfigurator.py`); montáž volitelná a cena dopravy po objednávce (Robert 2026-10-04). Neznámé a proto nepsané: nosnost, tloušťka a materiál desky, doba dodání pro system 40 (karta má `availability_text` „3 - 5 týdnů“, ale v textu ji neuvádím, ukazuje ji karta).

**intro_html**
```html
<div><span style="font-size: 10pt;">Robustní balicí stůl pro balení, příjem a expedici, jehož rám je z hliníkového profilu 40×40 (u stolu system 30 je to profil 30×30). Rozměry, počet polic i příslušenství si nastavíte níže ve 3D a orientační cenu vidíte hned. Co v nabídce nenajdete, poptejte. Montáž je volitelná služba a podle ní se mění cena dopravy: tu určíme po objednávce a před vystavením zálohové faktury ji potvrdíte.</span></div>
```
**body_html**
```html
<div><span style="font-size: 10pt;">Příslušenství výše je základní nabídka. Jiný doplněk nebo úpravu poptejte.</span></div>
```
**meta_title** (54 znaků): `Robustní balicí stůl system 40 – generátor stolu ve 3D`
**meta_description** (142 znaků): `Balicí stůl s rámem z profilu 40×40: nastavte rozměry, police a příslušenství ve 3D a zjistěte orientační cenu. Pro balení, příjem a expedici.`
**focus_keyword**: `robustní balicí stůl`

## ZAPSÁNO 2026-10-04 (kategorie id 311 založil bot10)
Vložen `content_pages` řádek (podmíněný INSERT, rowcount 1) a nastaveny meta_title, meta_description a focus_keyword (podmíněný UPDATE, jen když byly prázdné, rowcount 1). Záloha: `backups/2026-10-04_kat311_pred_textem_2026-10-04_213013.json`. Ověřeno na živém API `/api/categories/311/content` i `<meta name="description">` stránky. Texty jsou editovatelné v adminu.
