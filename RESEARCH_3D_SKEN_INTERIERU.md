# Research: 3D model interiéru vozidla z mobilních fotek

Zadání (Robert, 2026-08-17, přes bot3): jak z několika fotek z mobilu
vytvořit kvalitní 3D model interiéru/prostoru - souběžně s tržním
průzkumem konkurence (bot12), tenhle dokument je **technická stránka**
- jak bychom to MOHLI implementovat sami. Čistě research, žádná
implementace, žádné rozhodnutí zatím padlo.

**Kontext konfigurátoru** (důležité pro doporučení níž): jde o
hliníkový stavebnicový systém pro **užitková vozidla** (dodávky) -
tedy skenovaný "interiér" je typicky nákladní prostor dodávky
(nepravidelný tvar, podběhy kol, boční panely), kde se má následně
šroubovat/nýtovat konfigurovaná police/regálová sestava. To klade
**vyšší nároky na přesnost** než běžné skenování obývacího pokoje pro
vizualizaci - jde o reálné montážní rozměry, ne jen hezký obrázek.

## Shrnutí a doporučení

**Čistá fotogrammetrie z pár fotek NENÍ pro tenhle účel dost přesná.**
Realisticky potřebuješ 30-60+ překrývajících se fotek (ne "pár") na
rozumnou kvalitu, a i tak dává SfM ze samotných fotek jen RELATIVNÍ
měřítko (bez referenčního objektu/pravítka v záběru neznáš skutečné
mm) - typická chyba i za ideálních podmínek řádu jednotek cm, u
amatérského focení klidně víc. Pro montážní přesnost nábytku/regálů
do dodávky to nestačí samo o sobě.

**Nejlibovější reálná cesta: iPhone Pro/Pro Max s LiDARem +
Apple RoomPlan API.** Dává metrické měřítko přímo (ne relativní),
přesnost řádu ~1-3 cm na běžných plochách, skenování trvá ~60-90s,
a hlavně - RoomPlan už rovnou vrací PARAMETRICKÝ model (stěny, otvory,
někdy i nábytek jako obdélníkové objemy), ne jen mrak bodů/mesh, který
by se musel dodatečně ručně vyhodnocovat. To je blízko tomu, co
konfigurátor potřebuje (rozměry prostoru → vstup do sestavy).
Omezení: jen iPhone 12 Pro/Pro Max a novější (a iPad Pro 2020+) mají
LiDAR - běžné iPhony a většina Androidů ho nemají. Přesnost pořád
nemusí stačit na milimetrové šroubovací tolerance - realisticky spíš
"dostatečně přesný podklad pro návrh sestavy", ne "finální výrobní
rozměr bez kontroly na místě".

**Pro širší dostupnost (i telefony bez LiDARu): komerční cloud API
(Luma AI Enterprise, případně RealityScan/RealityCapture) je
realističtější než stavět vlastní SfM/Gaussian Splatting pipeline od
nuly** - výpočet (COLMAP + trénink) potřebuje desítky minut na
výkonném GPU (ideálně cloud pronájem, ne náš současný VPS bez GPU),
což je netriviální infrastrukturní investice. RealityScan (dřív
RealityCapture, teď Epic Games/Unreal) je navíc **zdarma pro firmy
pod 1 mil. USD ročního obratu** - to pravděpodobně platí pro nás, a
má i vlastní mobilní capture appku.

Detaily jednotlivých přístupů níž.

## 1. Structure-from-Motion / fotogrammetrie (čisté foto, bez LiDARu)

Princip: SfM najde společné body napříč fotkami, odhadne polohu
kamery pro každou fotku a zrekonstruuje mrak bodů → mesh.

**Nástroje:**
- **COLMAP** (open-source, výzkumný standard) - přesný, ale
  nejpomalejší a nejméně uživatelsky přívětivý, žádné GUI pro
  běžného uživatele, spíš stavební kámen pro jiné nástroje (i pro
  Gaussian Splatting pipeline - viz níž, COLMAP se často používá jako
  1. krok pro odhad kamerových poz).
- **Meshroom** (open-source, AliceVision) - grafické rozhraní, uzlový
  workflow, zdarma, funguje lokálně na vlastním GPU. Vhodné pro
  experimentování, ne pro nasazení do produkčního webu bez vlastní
  GPU infrastruktury.
- **RealityScan / RealityCapture** (Epic Games/Unreal, dřív
  Capturing Reality) - komerční, ale **zdarma pro firmy pod 1 mil.
  USD ročního obratu** (od dubna 2024, nahradilo dřívější pay-per-
  input model). Nejrychlejší/nejkvalitnější ze zavedených nástrojů,
  má i vlastní mobilní capture appku (RealityScan mobile, iOS/
  Android). Nad limitem obratu 1250 USD/rok/sedadlo.
- **Cloudová API** - Polycam (spotřebitelská appka + web upload,
  min. ~20 fotek, veřejně dostupné vývojářské REST API jsem
  nedohledal - vypadá to na workflow "naskenuj v appce → export",
  ne na server-to-server integraci), Luma AI (má **Enterprise API**
  pro programové generování Gaussian Splattingu - viz níž, tohle je
  ta cesta, pokud bychom chtěli vlastní upload flow bez závislosti
  na cizí appce), KIRI Engine (podobná spotřebitelská appka jako
  Polycam).

**Kolik fotek reálně potřeba:** doporučené překrytí mezi sousedními
fotkami min. 60 % (boční) / 80 % (čelní) - to v praxi znamená
desítky fotek i pro jednu menší místnost/nákladní prostor, ne "5-10
fotek od boku". Polycam sám doporučuje minimum ~20 fotek jako spodní
hranici pro cokoliv použitelného. Pod ~15-20 fotek bývá rekonstrukce
děravá (chybějící plochy tam, kde se snímky nepřekrývaly dost) a
měřítko nespolehlivé.

**Zásadní omezení pro náš účel - měřítko:** čistá fotogrammetrie ze
samotných fotek dá tvar SPRÁVNĚ RELATIVNĚ, ale absolutní velikost
(mm) NEZNÁ, pokud v záběru není něco se známým rozměrem (např.
kalibrační destička, nebo objekt známé velikosti). To je zásadní
rozdíl oproti LiDAR/ARKit skenu, který metrické měřítko má vestavěné
ze senzoru. Bez toho by šlo o "hezký 3D náhled", ne o rozměry použité
k objednání konkrétní délky profilu.

## 2. Neural rendering (NeRF, Gaussian Splatting)

**NeRF (Neural Radiance Fields)** - starší přístup (2020+), trénink
původně hodiny, zrychlené varianty (Instant-NGP od NVIDIA) minuty,
ale pořád pomalejší vykreslování a hůř se z něj extrahuje "tvrdá"
geometrie (mesh s rozměry) - hodí se spíš na fotorealistický náhled/
volný pohled kamerou než na měření.

**3D Gaussian Splatting (3DGS)** - novější (2023+) a dnes de facto
standard komerčních appek (Polycam, Luma AI oba na tom v roce 2026
staví). Trénink řádu 7-45 minut na výkonném GPU (podle složitosti
scény, typicky desítky minut pro místnost/prostor s 20-50+ fotkami),
vykreslování v reálném čase (100-200+ FPS) díky klasické GPU
rasterizaci místo ray-marchingu. **Trénink NEBĚŽÍ na mobilu** - appky
jako Polycam pošlou snímky do cloudu, tam se to spočítá, výsledek se
stáhne zpět. Pro nás by to znamenalo buď pronájem GPU (cloud instance
typu A100 na požádání), nebo použití hotového cizího API (Luma AI
Enterprise).

Pro náš účel (přesné rozměry pro montáž) je Gaussian Splatting
podobně limitovaný jako čistá fotogrammetrie - skvělý na
fotorealistickou vizualizaci "jak to vypadá", ale extrakce přesné
míry (vzdálenost stěna-stěna v mm) z toho není přímočará ani hlavní
účel technologie.

## 3. LiDAR / ARKit (iOS) / ARCore (Android)

**ARKit + LiDAR (iPhone 12 Pro/Pro Max a novější, iPad Pro 2020+):**
Apple **RoomPlan API** (od iOS 16, WWDC22) - specializovaná appka/SDK
přímo pro tenhle účel: nasměruješ telefon po prostoru ~60-90 sekund,
RoomPlan detekuje stěny, otvory (dveře/okna) a rozpozná i typy
nábytku (gauč, stůl, skříň...) jako obdélníkové objemy. Výstup je
**parametrický** (ne surový mesh) - přesně to, co potřebuje systém
jako konfigurátor pro další zpracování (rozměry místnosti/prostoru
jako čísla, ne 3D scan k ručnímu měření). Přesnost ~1-3 cm na
běžných plochách (Apple i nezávislé recenze se shodují). Omezení:
funguje nejlíp na "standardní" pravoúhlé místnosti do cca 9×9 m -
nepravidelný interiér dodávky (zaoblené rohy, podběhy kol) může být
pro detekční model náročnější než navrhovaný use-case (obytné
místnosti), nenašel jsem konkrétní data o přesnosti na vozidlech.

**ARCore Depth API (Android):** obdoba pro Android, ale bez
specializovaného "RoomPlan" ekvivalentu a bez plošně rozšířeného
LiDAR/ToF senzoru napříč Android telefony (na rozdíl od Apple, kde je
LiDAR aspoň na celé "Pro" řadě od 2020) - u Androidu je hloubkové
snímání většinou odvozené ze stereo/software odhadu, ne z vyhrazeného
senzoru, tedy méně přesné a nekonzistentní napříč výrobci/modely.

**Praktický důsledek pro nás:** LiDAR/RoomPlan cesta pokrývá jen
podmnožinu uživatelů (majitelé iPhone Pro) a i tak přesnost (~1-3 cm)
nemusí stačit na milimetrové šroubovací tolerance hliníkového
profilu - realisticky by šlo o "dost přesný podklad pro návrh
sestavy a orientační objednávku", s doporučením přeměřit kritické
rozměry na místě před finální montáží, ne o plně důvěryhodný
výrobní rozměr bez lidské kontroly.

## 4. Reálné limity "pár fotek" - shrnutí čísel

| Metoda | Min. fotek pro použitelný výsledek | Absolutní měřítko (mm)? | Typická přesnost | Kde se počítá |
|---|---|---|---|---|
| SfM/fotogrammetrie (Meshroom/COLMAP/RealityScan) | ~20-30+ (60-80% překryv) | NE (bez referenčního objektu) | řádu cm, zhoršuje se bez dobrého překryvu/světla | lokální GPU nebo cloud |
| Gaussian Splatting (Polycam/Luma) | ~20-50 (podobné jako SfM, používá SfM jako 1. krok) | NE (stejné omezení jako SfM) | vizuálně skvělé, měřicky nepřímé | cloud (desítky minut na GPU) |
| LiDAR + RoomPlan (iPhone Pro) | 0 fotek - jde o video-sken ~60-90s | ANO (senzor dává metrické měřítko) | ~1-3 cm | na zařízení (ARKit), výstup rovnou parametrický |

"Pár fotek" (5-10) realisticky **nestačí na žádnou z metod** pro
kvalitní výsledek - buď je výsledek děravý/nepřesný (fotogrammetrie),
nebo tahle metoda fotky vůbec nepoužívá (LiDAR sken je video, ne
diskrétní fotky).

## 5. Náklady/náročnost - co je realisticky implementovatelné pro nás

**Vlastní SfM/Gaussian Splatting pipeline od nuly:** vysoká náročnost
- potřeba GPU výpočet (náš současný VPS ho nemá, museli bychom
pronajímat cloud GPU instance per-scan, cena řádu jednotek USD/scan
u A100 pronájmu na desítky minut), integrace COLMAP+3DGS kódu,
údržba. Nedoporučuju jako první krok - vysoká investice, výsledek
navíc nedává přímo použitelné rozměry (viz omezení měřítka výš).

**Komerční API (Luma AI Enterprise):** střední náročnost - platili
bychom za scan/API volání, ale odpadá vlastní GPU infrastruktura a
pipeline engineering. Nejasná zatím konkrétní cena/podmínky
Enterprise tieru (nedohledáno v research), potřeboval by se ověřit
přímo u Luma AI, než se počítá jako reálná varianta.

**RealityScan (Epic/Unreal) zdarma tier:** nejnižší náklad ze
seriózních nástrojů (0 Kč pro firmy pod 1 mil. USD obratu), ale
funguje jako desktop/mobilní appka, ne server-to-server API -
znamenalo by to buď ruční workflow (uživatel naskenuje v appce,
exportuje, nahraje nám soubor), nebo by se muselo prozkoumat, jestli
Epic nabízí i nějaké programové rozhraní (nezjišťoval jsem do
hloubky, mimo scope tohohle rychlého researche).

**LiDAR/RoomPlan (jen iPhone Pro):** nejnižší technická náročnost NA
NAŠÍ STRANĚ (Apple odvádí těžkou práci), ale pokrývá jen podmnožinu
uživatelů (iPhone Pro), vyžaduje vlastní nativní iOS kód (RoomPlan
je Swift/ARKit API, ne webová technologie - nešlo by to udělat čistě
v prohlížeči/PWA, potřebovali bychom nativní iOS appku nebo aspoň
"scan" komponentu).

## Doporučení pro další krok (čeká na schválení, sám neimplementuju)

Pokud by měl jít tenhle směr dál, navrhoval bych v tomhle pořadí:
1. Ověřit u Robert/Roberta, jak přesné rozměry reálně potřebujeme
   (je "orientační podklad pro návrh + kontrola na místě" dostačující
   produktový cíl, nebo se čeká na spolehlivá výrobní přesnost bez
   lidské kontroly?) - tohle zásadně mění, která cesta dává smysl.
2. Pokud stačí orientační podklad: vyzkoušet RoomPlan na reálném
   interiéru dodávky (ne obytné místnosti) - ověřit, jestli
   nepravidelný tvar (podběhy, zakulacené rohy) nedělá RoomPlan
   detekci zbytečné problémy, než se investuje do integrace.
3. Souběžně ověřit u Luma AI, jestli jejich Enterprise API skutečně
   nabízí serverové (ne jen appkové) programové rozhraní a za jakou
   cenu - to by rozhodlo, jestli cloudová cesta bez vlastní GPU dává
   ekonomicky smysl.
