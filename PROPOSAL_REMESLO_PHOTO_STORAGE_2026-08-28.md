# Návrh: škálovatelné úložiště + komprese fotek pro Řemeslo (a obecně gallery_items.py)

Zadání: Robert přes bot3 — modul Řemeslo plánuje škálovat na tisíce
aktivních řemeslníků nahrávajících fotky ze zakázek
(`remeslo_jobs` → `content_gallery_items`, `owner_type='remeslo_job'`).
**Návrh/výzkum, NE implementace** — nic z tohohle nebylo aplikováno.

---

## Zjištěný aktuální stav (ověřeno přímo na serveru/v kódu)

- **Disk VPS**: 157 GB celkem, 53 GB volno (65 % využito).
- **`private-files/`** (kam by fotky zakázek šly — `owner_type=remeslo_job`
  je v `REMESLO_PRIVATE_OWNER_TYPES`, viz `gallery_items.py:65-70`) má
  dnes **51 GB**, ale **skoro celé (51 GB) zabírá `shared-drive/`**
  (nesouvisející funkce — Sdílený disk, `drive.py`) — vlastní
  `gallery-items/` složka má dnes jen **8 KB** (Řemeslo fotky zakázek
  prakticky ještě nezačaly). Veřejná `content-files/gallery-items/`
  (kategorie/produkty) má 4,6 MB.
- **Žádné zpracování obrázků při uploadu neexistuje** — potvrzeno
  (`gallery_items.py:579,832`, `f.save(os.path.join(storage_dir,
  stored_name))` — přímý zápis Werkzeug `FileStorage.save()`, žádný
  Pillow/resize/komprese). Ukládá se přesně to, co telefon vyfotí
  (typicky 4+ MB).
- **3 stránky** volají upload endpoint (`POST /api/gallery-items`):
  `admin.html`, `remeslo.html`, `scene.html` — je to sdílený modul
  napříč appkou, ne jen Řemeslo (potvrzuje zadání).
- **Existující client-side komprese v `capture.html`** (skener
  dokladů): `canvas.toBlob(cb, "image/jpeg", scannerMode ? 0.8 : 0.85)`
  po ořezu/resize na `SCANNER_MAX_DIM=2600px`. Je to ale těsně
  svázané s jeho vlastním flow (detekce rohů dokladu, warp,
  scanner efekt) — nejde 1:1 zkopírovat, ale **technika (canvas
  resize + `toBlob` JPEG kvalita) je přímo přenositelná** na obecný
  upload fotek.

## Revidovaný odhad objemu (Robert: komprimovat na ~1 MB místo
## ukládání originálu)

Podle bot3 s kompresí na ~1 MB/fotka: řádově **2-3 TB/rok** místo
původních 10+ TB/rok při stejném objemu uživatelů/zakázek. I tak
**výrazně nad 53 GB volného místa** — otázka není "jestli", ale "jak
brzy" externí úložiště bude potřeba. Vzhledem k tomu, že `shared-drive/`
už dnes zabírá 51 GB z 98 GB použitých, marže na disku je i bez
Řemesla tenčí, než by se čekalo.

---

## Část A: Komprese/resize obrázků při uploadu

### Doporučení: **client-side (canvas), ne server-side (Pillow)**

| | Client-side (canvas + toBlob) | Server-side (Pillow) |
|---|---|---|
| Šetří přenos dat (mobil na 4G nahrává 1 MB místo 4+ MB) | ✅ ANO | ❌ ne — celý originál musí nejdřív dorazit |
| Zátěž serveru (CPU na resize/re-encode) | ✅ žádná — dělá to prohlížeč | ❌ další zátěž na sdíleném VPS (2 gunicorn workery, viz bot14ho výkonový audit) |
| Konzistence napříč prohlížeči/telefony | ⚠️ Canvas API je standardizované, ale JPEG enkodér se mírně liší mezi Chrome/Safari/Firefox (kvalita `0.8` nemusí dát bit-identický výsledek) | ✅ Pillow = jedna, kontrolovaná implementace |
| Fallback při starém/omezeném prohlížeči | ⚠️ nutný fallback (poslat originál, když canvas/toBlob selže) | ✅ vždy funguje, server má vše pod kontrolou |
| Existující vzor v repu | ✅ `capture.html` — odladěný, testovaný, funkční | ❌ žádný, psalo by se od nuly |
| Nasazení | čistě frontend (JS), žádná nová závislost | nová Python závislost (Pillow), nutno nainstalovat do `venv` |

**Proč client-side vyhrává**: hlavní bolest při tisících řemeslníků
nahrávajících z mobilu je jak DISK, tak PŘENOS DAT (nahrávání 4+ MB
fotek na horší mobilní síti na stavbě je pomalé a nespolehlivé -
větší šance na timeout/selhání uploadu). Server-side komprese tohle
neřeší vůbec (originál musí nejdřív celý dorazit). Navíc `capture.html`
už dokazuje, že tahle technika v appce funguje a je odladěná proti
reálným problémům (viz komentář o 0.8 vs. 0.55 kvalitě - "0.55 přidávalo
viditelné JPEG artefakty").

**Konkrétní návrh**: sdílená JS funkce (např. `compressImageForUpload(file,
{maxDim: 1600, quality: 0.82}) -> Promise<Blob>`) — canvas resize na
max. delší stranu ~1600px (fotka zakázky, ne dokument, nepotřebuje
`capture.html`ho 2600px pro čitelnost textu) + JPEG kvalita ~0.82
(o něco vyšší než capture.html's 0.8, protože zakázkové fotky NEJSOU
černobílý sken s velkými plochami - barevná fotografie nářadí/instalace
komprimuje hůř při stejné kvalitě, artefakty by byly víc vidět).
Odhad výsledné velikosti: 1600×1200px JPEG q0.82 typicky 300-700 KB
podle obsahu fotky - pod cílovým ~1 MB s rezervou. Volat před sestavením
FormData na všech upload cestách (`admin.html`/`remeslo.html`/
`scene.html`, ~5 call sites nalezeno).

**Fallback**: pokud `canvas.toBlob` selže/není podporováno (starý
prohlížeč), poslat originál beze změny — appka nesmí nikdy zablokovat
upload kvůli kompresi, jen o kompresi přijde ten jeden soubor.

**Zachovat originál, nebo jen kompresi?** Doporučuji **JEN
komprimovanou verzi** (ne obojí) — u desítek tisíc fotek ročně by
uchovávání obojího zdvojnásobilo přesně to, co se snažíme vyřešit
(objem dat). Řemeslník/zákazník potřebuje fotku k rozpoznání detailu
zakázky (instalace, poškození, stav před/po) - 1600px na delší straně
při rozumné JPEG kvalitě na tohle bohatě stačí (fotoaparát mobilu má
sice 12+ Mpx, ale k ROZPOZNÁNÍ detailu na obrazovce/tisku netřeba). Pokud
by se v budoucnu ukázalo, že kvůli konkrétnímu sporu/reklamaci je
potřeba víc detailu, jde to řešit výjimkou (např. "fotka dokladu/vady"
kategorie s vyšší kvalitou), ne plošným ukládáním obojího.

---

## Část B: Škálovatelné úložiště

### Srovnání

| | Mount externího disku (např. WEDOS Disk, WebDAV/SFTP) | S3-kompatibilní object storage |
|---|---|---|
| Zásah do kódu | **Minimální** — `PRIVATE_FILES_DIR`/`GALLERY_ITEMS_DIR` ukazuje na mount point, `f.save()` beze změny | **Střední** — upload/download/delete přes S3 SDK (`boto3`) místo přímého file I/O, nutná úprava `gallery_items.py` (upload, serve/download endpoint, delete) |
| Spolehlivost pro časté malé zápisy | ⚠️ síťový mount (WebDAV/SFTP-přes-FUSE) má vyšší latenci a je křehčí při výpadku sítě než lokální disk NEBO přímé S3 volání — appka dnes běží na 2 gunicorn workerech bez threads (viz bot14ho audit), síťové I/O uvnitř requestu by mohlo prodloužit odezvu uploadu citelně | ✅ S3 SDK má vestavěné retry/timeout chování, navržené přímo pro tenhle vzor (upload z aplikace do vzdáleného úložiště) |
| Škálování/cena při růstu | omezené tím, co WEDOS Disk nabízí (typicky pevné tarify po krocích, ne pay-as-you-go) | ✅ přesně pay-per-GB, roste plynule s objemem, konkurenční trh (viz ceny níže) |
| Serve souborů zpět uživateli (zobrazení fotky v appce) | jednoduché — soubor je "lokálně" na mount pointu, nginx/Flask ho servíruje jako dnes | o něco složitější — buď appka streamuje soubor z S3 přes sebe (extra zátěž), nebo generuje dočasné podepsané URL (o něco víc práce navíc, ale standardní vzor) |
| Riziko/nejistota | **vysoké** — nemám ověřenou informaci o skutečné spolehlivosti/limitech WEDOS Disk pro tenhle konkrétní vzor použití (časté malé zápisy z aplikace, ne zálohování). Zdroj (WEDOS knowledge base) přesměroval na podezřelou doménu (`kb.vedos.cz` - "v" místo "w") při pokusu o hlubší ověření, nenásledoval jsem to dál - doporučuji ověřit ceník/limity přímo na `wedos.cz`, ne přes vyhledávač | nízké — S3 protokol je odvětvový standard, chování je dobře zdokumentované a předvídatelné |
| Orientační cena (2026, ověřeno webem) | WEDOS Disk cenu jsem nedohledal spolehlivě (viz výš) | Backblaze B2 ~$0.005/GB/měsíc (nejlevnější), Wasabi ~$0.007/GB/měsíc (ale 90denní minimální retence - u fotek co se občas mažou to zvyšuje efektivní cenu), Cloudflare R2 ~$0.015/GB/měsíc ale **neomezený free egress** (žádný poplatek za stažení dat ven - důležité, protože appka bude fotky často ZOBRAZOVAT zpátky uživatelům, ne jen ukládat) |

### Doporučení: **S3-kompatibilní object storage**, konkrétně zvážit **Cloudflare R2**

Důvody://
1. **Egress zdarma je klíčové pro tenhle use-case** — na rozdíl od
   zálohování (kam se nahraje a málokdy stahuje), appka bude fotky
   zakázek ČASTO zobrazovat zpátky (řemeslník/zákazník otevírá
   detail zakázky opakovaně). Backblaze B2/Wasabi účtují za stahování
   dat ven po překročení limitu - při hodně prohlížených fotkách by
   se to prodražilo. R2 tohle riziko úplně odstraňuje.
2. **Menší, kontrolovanější zásah do kódu než síťový mount** - S3 SDK
   (`boto3`, MIT licence, standardní Python knihovna) je vyzkoušené,
   dobře zdokumentované, appka na něj získá jasné rozhraní
   (upload/get/delete), místo nejistoty "jak se zachová FUSE mount
   při výpadku sítě uprostřed zápisu".
3. **Nezávislé na jednom malém českém poskytovateli** - S3 protokol
   je přenositelný mezi providery (kdyby se cena/podmínky u jednoho
   zhoršily, migrace na jiného S3 providera je mnohem jednodušší než
   migrace ze specifického mount-protokolu).

**Náklad implementace** (odhad, ne závazný): úprava `gallery_items.py`
upload/delete/serve cest (přidat `boto3` klienta, nahradit `f.save()`
za `s3.upload_fileobj()`, řešit serve buď přes presigned URL nebo
proxy), + migrace existujících ~5 MB veřejných galerie fotek (malá,
rychlá) — žádná migrace u Řemesla není potřeba (8 KB, prakticky
nic tam není). Řádově jednotky hodin práce, ne dnů - `gallery_items.py`
má už dnes jasně oddělenou "storage" vrstvu (`_storage_dir_for()`),
takže výměna backendu je lokalizovaná, ne plošná.

**Co zůstává na Robertovi**: založení účtu u zvoleného S3 providera,
API klíče (do `.env`, gitignored jako ostatní tajné klíče), případné
rozhodnutí o data residency (R2/Backblaze/Wasabi jsou všichni mimo
ČR/EU primárně v US - pokud by GDPR/data-residency byl problém, stojí
za zvážení EU-based S3-kompatibilní alternativa, např. OVHcloud
(zmíněný ve výzkumu, sídlí ve Francii, od ledna 2026 taky bez
egress poplatků) - nekontroloval jsem OVHcloud podrobně, jen ho
zaznamenávám jako možnou EU alternativu k dalšímu ověření.

### Doplnění: FORPSI Cloud Object Storage (nalezl bot3, Robert se ptal)

Konkrétní kandidát, který mění doporučení výše - **Forpsi už appka
používá** (DNS/domény pro sesterský Toscanaccio) - jedna faktura
navíc u dodavatele, kterého už Robert má, ne nový vztah s cizí firmou.
Vlastnosti (podle zjištění bot3, needěl jsem to sám nezávisle ověřit -
doporučuji potvrdit přímo na `forpsicloud.cz` před rozhodnutím):

- S3-kompatibilní API (boto3/standardní nástroje beze změny).
- 3 fyzicky oddělené kopie dat, 7 evropských datacenter (**řeší i
  data-residency/GDPR otázku**, kterou jsem výš zmiňoval jako otevřenou
  u R2/Backblaze/Wasabi - Forpsi ji rovnou odstraňuje).
- Škáluje až na 256 TB.
- Cena klesá s objemem: pay-per-use ~1,25 Kč/GB, balíček 4 TB ~60 €/měsíc
  (~375 Kč/TB/měsíc), u největších balíčků až ~0,28 Kč/GB
  (~280 Kč/TB/měsíc).

**Odhad nákladu proti ~2-3 TB/rok** (po kompresi na ~1 MB/foto, KUMULATIVNĚ
- fotky se archivují, neholí se rok od roku): v prvním roce provozu
by šlo o balíček řádu 4 TB (~1 500 Kč/měsíc při kurzu ~25 Kč/€, tj.
~18 000 Kč/rok) - druhý rok už při 4-6 TB kumulativně buď zůstat na
stejném balíčku (pokud má rezervu), nebo navýšit na další úroveň, kde
cena za GB dál klesá. Pro srovnání pay-per-use ~1,25 Kč/GB by při 3 TB
vyšlo na ~3 750 Kč/měsíc - dražší než balíček, takže balíčková varianta
dává větší smysl už od prvního roku.

**Přesnou aktuální cenu/podmínky jsem si sám nedohledal** (čerpám z
bot3ho zjištění, ne z vlastního ověření na `forpsicloud.cz`) -
doporučuji před rozhodnutím potvrdit aktuální ceník přímo tam, čísla
výš berte jako orientační.

**Upravené doporučení**: vzhledem k tomu, že Forpsi řeší data-residency
otázku ROVNOU (na rozdíl od US-based R2/Backblaze/Wasabi) a appka u
něj už má účet, **Forpsi Cloud Object Storage je pravděpodobně lepší
volba než Cloudflare R2** i přes o něco vyšší cenu za GB - praktická
výhoda "jedna faktura navíc u známého dodavatele" + vyřešené GDPR
sídlo dat váží víc než čistě nejnižší cena za GB. Egress (stahování
dat zpátky při zobrazování fotek uživatelům) jsem u Forpsi nedohledal -
stojí za doplnění při definitivním ověření, protože u tohohle use-case
(časté zobrazování, ne jen ukládání) je to důležitý faktor stejně jako
u R2/Backblaze/Wasabi srovnání výš.

---

## Shrnutí doporučení

1. **Komprese**: client-side (canvas + `toBlob`), zobecnit techniku z
   `capture.html` do sdílené JS funkce, volat na všech ~5 upload
   call sites, jen komprimovaná verze (ne originál navíc), cíl
   ~1600px/JPEG q0.82.
2. **Úložiště**: S3-kompatibilní object storage, ne mount externího
   disku. **Upraveno po zjištění bot3**: doporučuji **Forpsi Cloud
   Object Storage** (appka u Forpsi už má účet, GDPR/data-residency
   vyřešené 7 evropskými datacentry) před Cloudflare R2 - i když R2
   má nulový egress a o něco nižší cenu za GB, praktická výhoda
   "žádný nový dodavatel" + vyřešené sídlo dat váží víc. Přesné ceny/
   podmínky obou stojí za potvrzení přímo u zdroje před rozhodnutím.
   WEDOS Disk nedoporučuji bez dalšího ověření - nedohledal jsem
   spolehlivá čísla a oficiální zdroj přesměroval na podezřelou
   doménu.
3. Obojí je obecné pro `gallery_items.py` (sdílený modul), ne
   Řemeslo-specifický hack - platí to i pro category/product galerie
   a scénu.

Nic z tohohle nebylo implementováno, čeká na rozhodnutí.
