# Průzkum — 3D modelování interiéru z fotek mobilu (český trh)

Založeno bot12, 2026-08-17 na zadání Roberta (přes bot3): průzkum toho,
kdo v ČR nabízí tvorbu 3D modelu interiéru na základě fotek/skenu
mobilem (obdoba zahraničních Matterport/Polycam apod.), jaká
technologie/postup, cena, cílovka. Kontext zadání: možná souvislost
s tím, jak by si zákazník konfigurátoru (vandrawee.cz — 3D nábytek/
skříně na míru) mohl sám zaměřit prostor pro objednávku.

**Tohle je jen průzkum/analýza — nic naprogramováno.** Čeká na
schválení bot3/Robertem (standing proces), teprve pak případný další
krok.

---

## Klíčové zjištění hned na začátek

Trh se rozpadá na dvě zřetelně oddělené vrstvy a **v jedné z nich žádný
český hráč neexistuje**:

1. **Profesionální služba se skenovacím zařízením** (technik přijede,
   naskenuje, dodá hotový výstup) — tady je český trh docela hustý,
   ale skoro výhradně přes technologii **Matterport** (dedikovaná
   360° kamera, ne běžný mobil) a cílí na **reality/B2B prezentaci
   prostoru**, ne na zaměření pro výrobu nábytku na míru.
2. **Self-service aplikace, kde si zákazník naskenuje prostor sám
   vlastním mobilem** (bez technika) — tady jsem **nenašel jediného
   českého hráče**. Všechny reálně používané appky (Polycam,
   CamToPlan, RealityScan, samotná Matterport appka pro telefon) jsou
   **zahraniční**.
3. **Nábytkářský/kuchyňský segment** (nejbližší přímé konkurenci
   vandrawee) **stále funguje na tradičním zaměření technikem
   osobně** — u žádné z prověřených českých firem na míru vyráběného
   nábytku/kuchyní jsem nenašel nabídku "naskenujte si to sami
   mobilem".

Jinými slovy: **"self-serve 3D scan mobilem před objednávkou nábytku"
je v ČR bílé místo na trhu** — nejde o dohánění konkurence, ale o
skutečnou příležitost k odlišení (podobný závěr jako u Modulu 2/3
`REMESLO_KONCEPT.md`, jen v jiné oblasti).

---

## A. Realitní 3D skenování — dominantní český segment (B2B, profesionální zařízení)

Všechny nalezené firmy fungují stejně: objednáte si termín, **technik
přijede s profesionální kamerou** (typicky Matterport Pro2/Pro3 —
NENÍ to běžný mobil, i když Pro3 umí kombinovat s LiDARem/dronem),
naskenuje prostor na místě, výstup dodá do 24–48 hodin.

| Firma | Zařízení | Čas skenování | Výstup | Cena | Cílovka |
|---|---|---|---|---|---|
| **Matterpro.cz** (Děčín, action pro Praha/Střč./Ústecký/Liberecký kraj) | Matterport Pro3 | — | 3D prohlídka, HDR fotky, technický půdorys s kótami, formát pro Sreality.cz | **Byt 4 500 Kč, dům 6 000 Kč** (jediná firma s veřejným ceníkem) | Realitní makléři, prodejci nemovitostí |
| **Scan360.cz** | Matterport Pro2 (interiér) / Pro3 (interiér+exteriér, LiDAR) | byt do 100 m² 45–60 min, dům 1–2 h | 3D prohlídka s "Mattertags" (foto/video/text/PDF/mapy), 4K foto, půdorysy, panoramata | Individuální nabídka, hosting 6 měsíců v ceně | Realitní profesionálové, soukromí prodejci, firmy (hotely, školy, obchody) |
| **PanoPro** | "nejmodernější kamery a drony" | — | 3D prohlídka do 48 h | Čistě individuální dohoda (žádný ceník) | Realitky, developeři |
| **3Dvire.cz** | Matterport + dron | — | 3D prohlídka, letecké práce | — | Realitky, hotely, restaurace |
| **iVirtual.cz** | Matterport | — | 3D prohlídky napříč typy objektů | — | Realitní kanceláře i další |
| **VirtualView.cz** | Matterport (optika + hloubková/LiDAR data) | 1–3 hodiny skenování | Digitální model prostoru | — | Nemovitosti obecně |

**Shrnutí segmentu:** silná nabídka, ale je to **služba s technikem
a drahým zařízením** (Matterport Pro kamera stojí řádově statisíce
Kč) — ne nástroj, který by si zákazník mohl použít sám doma mobilem
před objednávkou nábytku. Relevance pro konfigurátor: nízká přímo,
ale ukazuje zavedený formát výstupu (půdorys + kóty + 3D prohlídka),
který by bylo možné použít jako inspiraci pro to, co konfigurátor
zákazníkovi vrátí.

## B. Stavební/geodetická dokumentace mobilem (B2B, video-based)

| Firma | Zařízení/postup | Výstup | Cena | Cílovka |
|---|---|---|---|---|
| **MawisPhoto** (HRDIČKA spol. s r.o., Praha) | **Vlastní mobil** (Android/iOS) — natočíte video prostoru přímo appkou, systém dopočítá 3D model | Geodeticky přesný 3D model (3. třída přesnosti), měřitelné vzdálenosti/plochy/kubatury, web+mobilní přístup | Neveřejná, na dotaz (B2B smluvní vztah) | Stavební firmy, dodavatelé, geodeti — postup výstavby, bezpečnostní dokumentace |

**Jediný nalezený český příklad, kde zákazník skutečně používá VLASTNÍ
mobil bez dalšího hardwaru** — ale cílí na stavební průběh (rozestavěná
stavba), ne na hotový interiér pro nábytek. Technologicky nejbližší
vzor tomu, co by konfigurátor mohl potřebovat (mobil → video/fotky →
3D model s kótami), i když cílovka je jinde.

## C. Nábytkářský/kuchyňský segment — relevance k vandrawee.cz

Prověřeno několik českých výrobců nábytku/kuchyní na míru
(Nábytek Sprint, Glanc kuchyně, Nábytek Panda, JN interier,
kuchyňská studia Gorenje) — **žádný nenabízí "naskenujte si prostor
mobilem"**. Standardní vzorec u všech: zákazník buď zadá rozměry sám
do online 3D konfigurátoru (2D/3D nábytkový plánovač), nebo si
objedná **osobní zaměření technikem přímo u zákazníka doma** (většinou
zdarma v rámci objednávky s montáží).

Samotný **vandrawee.cz** (ověřeno přímo) — jeho 3D konfigurátor slouží
k SESTAVENÍ produktu ("poskládejte si tu svou přímo v prohlížeči"), ne
k zaměření prostoru fotkami. Žádná scan-to-order funkce zatím
neexistuje.

**Toto je přímo tržní mezera relevantní zadání.**

## D. Self-service aplikace (spotřebitel skenuje sám vlastním telefonem)

| Aplikace | Původ | Technologie | Poznámka |
|---|---|---|---|
| Polycam | USA | Foto nebo LiDAR (novější iPhone/iPad) | Nejrozšířenější, export do AR/webu, i textury |
| CamToPlan | zahraniční | AR půdorys v reálném čase, pár sekund/místnost | Rychlé, ale spíš půdorys než plný 3D mesh |
| RealityScan | Epic Games (USA) | Foto→3D mesh (fotogrammetrie) | Určeno spíš pro objekty než celé místnosti |
| Matterport (mobilní appka) | USA | Foto nebo LiDAR přímo v telefonu, bez Pro kamery | Levnější varianta jejich vlastní profi služby |
| Homestyler, Magic Plan, Floorplanner, Home Design 3D | zahraniční | Foto pozadí / ruční 2D půdorys + 3D nábytek | Spíš vizualizace/plánování než přesné zaměření |

**Žádná z těchto aplikací není český produkt.** Český zákazník, který
dnes chce sám naskenovat byt mobilem, sáhne po zahraniční appce — v ČR
neexistuje lokální konkurence ani v podobě menší appky, ani jako
funkce v rámci nábytkářského e-shopu.

---

## Doporučení pro konfigurátor (Robert/vandrawee), seřazeno podle priority

1. **Nejreálnější první krok — NE vlastní fotogrammetrie, ale
   integrace/inspirace existujícím řešením.** Stavět vlastní
   foto→3D mesh technologii od nuly je velký, rizikový projekt
   (přesně proto to nikdo v ČR nedělá — bariéra vstupu je vysoká).
   Realističtější cesta: (a) nechat zákazníka nahrát pár fotek/video
   pokoje jako **kontext pro konfigurátor** (ne přesný mesh, jen
   vizuální reference + AI odhad přibližných rozměrů), nebo (b)
   integrovat existující SDK/API (Polycam má vývojářské API,
   Matterport taky) místo budování vlastního skeneru.
2. **Přesné rozměry pořád nejspolehlivěji zadá zákazník ručně** (jak
   dělá dnes vandrawee i celý zbytek nábytkářského trhu) — fotky/scan
   by měly sloužit jako **doplněk pro kontrolu/vizualizaci**
   ("umístěte navrženou skříň do fotky vašeho pokoje"), ne jako
   náhrada přesného měření. To by bylo unikátní i v porovnání s
   Matterport-založenými firmami výš, které taky nedávají
   výrobní přesnost pro nábytek na míru (jejich přesnost cílí na
   realitní prezentaci, ne na milimetrové osazení skříně).
3. **Nejbližší technický vzor** je MawisPhoto (mobil → video → 3D
   model s kótami) — je to jediný český příklad "mobil bez
   dalšího hardwaru", i když jiná cílovka (stavba). Stálo by za to
   se podívat, jestli nepoužívají nějaký veřejně dostupný
   photogrammetry engine, který by šel znovupoužít.
4. **Nízká priorita, ale zmínka:** formát výstupu realitních
   Matterport firem (půdorys s kótami + 3D prohlídka) je dobrý
   referenční vzor PRO UI/UX výstupu, i když samotnou skenovací
   technologii přebírat nedává smysl (drahé profi zařízení, ne mobil).
