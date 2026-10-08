"""
Doplneni meta_title/meta_description/focus_keyword pro 96 viditelnych
kategorii, ktere je meli prazdne (QA audit: category_missing_meta_description).

Texty psany rucne podle SEO_STANDARD_TEXTY_KATEGORII.md (formule pro
meta_title/meta_description, priorita: vlastni vyrobni program > stavajici
texty v DB (content_pages.intro_html) > vzor konkurence na forme, ne obsahu).

Idempotentni: aktualizuje jen radky, kde je meta_description dnes prazdne/NULL
(stejna podminka jako QA kontrola v api/qa_checks.py), takze opakovane spusteni
uz nic nezmeni. Pred zapisem ulozi zalohu puvodniho stavu do backups/.
"""
import json
import sys
import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

# id -> (meta_title, meta_description, focus_keyword)
DATA = {
    5: ("Návody a postupy – práce s konfigurátorem a montáž profilů",
        "Praktické návody, jak navrhnout konstrukci v 3D konfigurátoru Logiman a jak smontovat hliníkové profily po doručení, krok za krokem s ukázkami a videi.",
        "návody konfigurátor hliníkové profily"),
    8: ("Videa – ukázky 3D konfigurátoru a instruktážní návody",
        "Videa ukazují práci s 3D konfigurátorem hliníkových profilů Logiman i instruktáže montáže konstrukce – rychlý přehled možností stavebnicového systému.",
        "videa konfigurátor hliníkové profily"),
    11: ("Technické podklady – katalog profilů a nosnosti ke stažení",
         "Technická dokumentace k hliníkovým stavebnicovým profilům Logiman: katalog profilů ke stažení v PDF a přehled rozměrů a nosností jednotlivých řad.",
         "technické podklady hliníkové profily"),
    14: ("Poptávky a servis – formulář, reklamace a servis",
         "Poptejte konstrukci, pracoviště nebo produkt na míru přes poptávkový formulář, nebo řešte reklamaci a servis u hliníkových profilů a doplňků Logiman.",
         "poptávka servis reklamace"),
    149: ("Hliníkové stavebnicové profily – modulární systém pro konstrukce",
          "Hliníkové stavebnicové profily Logiman pro rámy, pracovní stoly, kryty strojů i regály – drážkový systém pro pevné spoje bez svařování, drážky 6–10 mm.",
          "hliníkové stavebnicové profily"),
    182: ("Balicí stoly a pracoviště na míru",
          "Balicí stoly a pracoviště na míru od Logiman – navrhneme a sestavíme řešení pro balení a expedici podle vašich prostorových i výkonových požadavků.",
          "balicí stoly na míru"),
    193: ("Ergonomické pracovní stoly – zdravé pracoviště na míru",
          "Ergonomické pracovní stoly Logiman pro montážní a výrobní provozy – výškově stavitelná řešení snižující riziko muskuloskeletálních potíží zaměstnanců.",
          "ergonomické pracovní stoly"),
    212: ("Montážní stoly a pracoviště na míru",
          "Montážní pracoviště a stoly Logiman navržená s důrazem na ergonomii – 3D vizualizace i realizace montážní linky nebo pracoviště podle vašeho provozu.",
          "montážní stoly a pracoviště"),
    237: ("Digitální délkové dorazy na míru",
          "Digitální délkový doraz Logiman pro přesné a bezchybné řezání hliníkových profilů na míru – ověřeno v provozu vlastní dílny po několik měsíců.",
          "digitální délkový doraz"),
    6: ("Práce s 3D konfigurátorem hliníkových profilů online",
        "Návod, jak si v prohlížeči postavit vlastní konstrukci z hliníkových stavebnicových profilů a příslušenství ve 3D konfigurátoru Logiman s cenou na místě.",
        "práce s 3D konfigurátorem"),
    7: ("Montáž konstrukce z hliníkových profilů – návod",
        "Jak fyzicky smontovat konstrukci navrženou v konfigurátoru, jakmile dorazí hliníkové profily a spojovací materiál Logiman – postup krok za krokem.",
        "montáž konstrukce z profilů"),
    9: ("Ukázky 3D konfigurátoru hliníkových profilů – video",
        "Videoukázky práce s 3D konfigurátorem Logiman – jak se navrhuje konstrukce z hliníkových stavebnicových profilů přímo v prohlížeči, krok za krokem.",
        "ukázky konfigurátoru"),
    10: ("Instruktážní videa – montáž hliníkových profilů",
         "Instruktážní videa k montáži konstrukcí z hliníkových stavebnicových profilů a spojovacích prvků Logiman – praktické postupy pro sestavení na místě.",
         "instruktážní videa montáž profilů"),
    12: ("Katalog hliníkových profilů Logiman ke stažení (PDF)",
         "Kompletní katalog hliníkových stavebnicových profilů Logiman ke stažení v PDF – průřezy, rozměry a technické parametry jednotlivých řad profilů.",
         "katalog profilů PDF"),
    13: ("Rozměry a nosnosti hliníkových profilů",
         "Přehled rozměrů, průřezů a nosností hliníkových stavebnicových profilů Logiman – podklad pro návrh rámů, pracovních stolů a strojních konstrukcí.",
         "rozměry a nosnosti profilů"),
    15: ("Poptávkový formulář – poptejte konstrukci na míru",
         "Poptejte u Logiman konstrukci, pracoviště nebo produkt z hliníkových profilů na míru – vyberte typ poptávky a vyplňte krátký formulář.",
         "poptávkový formulář"),
    16: ("Reklamace a servis – hliníkové profily a doplňky",
         "Řešení reklamace a servisu k hliníkovým stavebnicovým profilům, konstrukcím a doplňkům Logiman – jak postupovat a co k reklamaci potřebujete.",
         "reklamace a servis"),
    150: ("Příslušenství profilů – záslepky, patky, panty a doplňky",
          "Doplňkové díly pro hliníkové stavebnicové profily Logiman – plastové záslepky, krycí lišty drážek, stavitelné patky, kolečka, panty, madla a další.",
          "příslušenství hliníkových profilů"),
    152: ("Spojovací prvky – úhelníky, kostky, matice a šrouby",
          "Sortiment spojovacích prvků pro hliníkové stavebnicové profily Logiman – rohové úhelníky, spojovací kostky, T-matice a šrouby pro pevné i rozebíratelné spoje.",
          "spojovací prvky profilů"),
    154: ("Hliníkové profily s drážkou 10 mm – nejsilnější řada",
          "Nejsilnější řada hliníkových stavebnicových profilů s drážkou 10 mm Logiman – pro těžké rámy strojů, montážní linky a konstrukce s vysokou nosností.",
          "hliníkové profily drážka 10 mm"),
    156: ("Hliníkové profily Dynamic – systém pro dopravníky a linky",
          "Systém hliníkových profilů Dynamic Logiman pro dopravníkové tratě, montážní linky a válečkové dráhy – vlastní řada spojovacích prvků a příslušenství.",
          "profily Dynamic"),
    168: ("Deskové hliníkové profily – ploché profily s drážkou",
          "Ploché deskové hliníkové profily Logiman pro širší nosné a krycí plochy – pracovní desky, boční stěny krytů a montážní panely se drážkovým systémem.",
          "deskové hliníkové profily"),
    169: ("Hliníkové profily s drážkou 8 mm – univerzální řada",
          "Univerzální řada hliníkových stavebnicových profilů s drážkou 8 mm Logiman – standard pro pracovní stoly, rámy strojů a montážní pracoviště.",
          "hliníkové profily drážka 8 mm"),
    181: ("Kulaté hliníkové profily – madla, zábradlí, stojany",
          "Hliníkové profily s kruhovým průřezem Logiman bez ostrých hran – vhodné pro madla, zábradlí, stojany i konstrukce s rotačním pohybem kolem osy.",
          "kulaté hliníkové profily"),
    198: ("Hliníkové profily s drážkou 6 mm – nejlehčí řada",
          "Nejlehčí řada hliníkových stavebnicových profilů s drážkou 6 mm Logiman – pro lehké konstrukce, kryty přístrojů, stojany a přenosné konstrukce.",
          "hliníkové profily drážka 6 mm"),
    215: ("Vodící hliníkové profily – lineární vedení hřídelí",
          "Hliníkové profily s integrovaným kruhovým vedením Logiman pro uložení hřídelí a lineárních ložisek – posuvné dveře, vozíky, dopravníky, polohování.",
          "vodící hliníkové profily"),
    262: ("Sigma profily – speciální řada hliníkových profilů",
          "Sigma profily Logiman – speciální série hliníkových stavebnicových profilů s vlastním profilovým průřezem pro specifické konstrukční požadavky.",
          "sigma profily"),
    151: ("Konektory pro patky hliníkových profilů",
          "Konektory pro uchycení stavitelných a pojezdových patek k hliníkovým stavebnicovým profilům Logiman – varianty skladem pro spodní zakončení konstrukce.",
          "konektory pro patky"),
    158: ("Plastové záslepky rožků hliníkových profilů",
          "Plastové záslepky rohových spojů (rožků) hliníkových profilů Logiman – bezpečné zakrytí ostrých hran a estetické dokončení konstrukce.",
          "plastové záslepky rožků"),
    160: ("Vrtací přípravky pro hliníkové profily",
          "Vrtací přípravky a šablony pro přesné vrtání hliníkových stavebnicových profilů Logiman – rychlá a opakovatelná příprava otvorů pro spoje.",
          "vrtací přípravky"),
    164: ("Závěsné karabiny na profil",
          "Závěsné karabiny pro zavěšení nářadí, kabelů a doplňků na drážku hliníkových stavebnicových profilů Logiman.",
          "závěsné karabiny"),
    165: ("Zámky pro hliníkové profilové konstrukce",
          "Zámky a uzamykací prvky pro dvířka a kryty z hliníkových stavebnicových profilů Logiman – zabezpečení skříní, krytů strojů a pracovišť.",
          "zámky pro profilové konstrukce"),
    170: ("Plastové záslepky profilů",
          "Plastové záslepky čel hliníkových stavebnicových profilů Logiman – zakrytí drážek a hran, dostupné pro všechny běžné rozměry profilů skladem.",
          "plastové záslepky profilů"),
    171: ("Plastové panty pro hliníkové profily",
          "Plastové panty pro dvířka a kryty z hliníkových stavebnicových profilů Logiman – lehké řešení otočných spojů bez nutnosti vrtání.",
          "plastové panty"),
    172: ("Kovové panty pro hliníkové profily",
          "Kovové panty pro dvířka, kryty a poklopy z hliníkových stavebnicových profilů Logiman – vyšší nosnost a životnost než plastové varianty.",
          "kovové panty"),
    177: ("Vodící kolečka na profil",
          "Vodící kolečka pro pojezd po hliníkových stavebnicových profilech Logiman – posuvné dveře, kryty a vozíky s hladkým vedením.",
          "vodící kolečka"),
    179: ("Panty s aretací pro hliníkové profily",
          "Panty s aretací (samodržné) pro dvířka z hliníkových stavebnicových profilů Logiman – bezpečně udrží otevřenou polohu bez dalšího zajištění.",
          "panty s aretací"),
    180: ("Madla pro hliníkové profilové konstrukce",
          "Madla a úchyty pro dvířka, kryty a konstrukce z hliníkových stavebnicových profilů Logiman – hliníkové provedení kompatibilní s drážkovým systémem.",
          "madla pro profilové konstrukce"),
    185: ("Držáky kabelů na profil",
          "Držáky kabelů pro uspořádané vedení elektroinstalace a vzduchových hadic po hliníkových stavebnicových profilech Logiman.",
          "držáky kabelů"),
    186: ("Drážkové čepy pro hliníkové profily",
          "Drážkové čepy pro rychlé a pevné spojení hliníkových stavebnicových profilů Logiman bez nutnosti vrtání otvorů.",
          "drážkové čepy"),
    187: ("Plynové vzpěry pro profilové konstrukce",
          "Plynové vzpěry pro odklopná víka, dvířka a kryty z hliníkových stavebnicových profilů Logiman – plynulé a bezpečné otevírání.",
          "plynové vzpěry"),
    195: ("Páčky pro hliníkové profilové konstrukce",
          "Ovládací a upínací páčky pro dvířka, uzávěry a upínací mechanismy hliníkových stavebnicových profilů Logiman.",
          "páčky pro profilové konstrukce"),
    196: ("Krycí lišty drážek profilů",
          "Krycí lišty pro zakrytí nevyužitých drážek hliníkových stavebnicových profilů Logiman – estetické dokončení a ochrana povrchu konstrukce.",
          "krycí lišty drážek"),
    202: ("Stavitelné patky pro hliníkové profily",
          "Stavitelné patky pro vyrovnání a výškové nastavení konstrukcí z hliníkových stavebnicových profilů Logiman – stabilní ukotvení na nerovném povrchu.",
          "stavitelné patky"),
    203: ("Plastové kluzáky pro hliníkové profily",
          "Plastové kluzáky (patky) pro hliníkové stavebnicové profily Logiman – ochrana podlahy a snadný posun lehčích konstrukcí.",
          "plastové kluzáky"),
    209: ("Magnety pro hliníkové profilové konstrukce",
          "Magnetické prvky pro uchycení na hliníkové stavebnicové profily Logiman – rychlé a nedestruktivní upevnění dvířek, štítků a doplňků.",
          "magnety pro profilové konstrukce"),
    214: ("Pojezdová kola pro hliníkové konstrukce",
          "Pojezdová kola pro mobilní konstrukce a vozíky z hliníkových stavebnicových profilů Logiman – snadná manipulace po dílně či hale.",
          "pojezdová kola"),
    217: ("Držáky plexiskla pro hliníkové profily",
          "Držáky plexiskla a průhledných výplní pro hliníkové stavebnicové profily Logiman – ochranné kryty strojů a přepážky pracovišť.",
          "držáky plexiskla"),
    236: ("Zavěšovací vidlice pro hliníkové profily",
          "Zavěšovací vidlice pro manipulaci a zavěšení konstrukcí z hliníkových stavebnicových profilů Logiman jeřábem či zvedacím zařízením.",
          "zavěšovací vidlice"),
    153: ("Plotny pro rohové spoje profilů",
          "Spojovací plotny pro rohové spoje hliníkových stavebnicových profilů Logiman – pevné a přesné spojení rámů v pravém úhlu.",
          "plotny pro rohové spoje"),
    155: ("Plotny pro T spoje profilů",
          "Spojovací plotny pro T-spoje hliníkových stavebnicových profilů Logiman – napojení příčného profilu na hlavní rám konstrukce.",
          "plotny pro T spoje"),
    159: ("Ploché úhlové spojky profilů",
          "Ploché úhlové spojky pro spoje hliníkových stavebnicových profilů Logiman pod úhlem 90° – nízkoprofilové řešení bez vyčnívajících prvků.",
          "ploché úhlové spojky"),
    161: ("Trojcestné oblé rožky profilů",
          "Trojcestné oblé rožky pro spojení tří hliníkových stavebnicových profilů Logiman v jednom bodě – zaoblený design bez ostrých hran.",
          "trojcestné oblé rožky"),
    162: ("Spojovací kostky pro profily",
          "Spojovací kostky pro pevné rohové spoje hliníkových stavebnicových profilů Logiman – jednoduchá montáž bez obrábění profilu.",
          "spojovací kostky"),
    163: ("Plotny pro křížové spoje profilů",
          "Spojovací plotny pro křížové spoje hliníkových stavebnicových profilů Logiman – spojení čtyř profilů v jednom rovinném uzlu.",
          "plotny pro křížové spoje"),
    166: ("Standardní rožky hliníkových profilů",
          "Standardní rohové rožky pro spojení hliníkových stavebnicových profilů Logiman v pravém úhlu – nejpoužívanější spojovací prvek konstrukce.",
          "standardní rožky"),
    167: ("Velké rožky hliníkových profilů",
          "Velké rohové rožky pro spojení silnějších hliníkových stavebnicových profilů Logiman – vyšší pevnost spoje pro náročnější konstrukce.",
          "velké rožky"),
    173: ("Úzké rožky hliníkových profilů",
          "Úzké rohové rožky pro hliníkové stavebnicové profily Logiman – kompaktní spoj tam, kde standardní rožek nemá dostatek místa.",
          "úzké rožky"),
    174: ("Úhelníky pro hliníkové profily",
          "Úhelníky pro pevné šroubované spoje hliníkových stavebnicových profilů Logiman – univerzální rohové i T spojení konstrukce.",
          "úhelníky pro profily"),
    175: ("Vnitřní spoje hliníkových profilů",
          "Vnitřní spojovací prvky hliníkových stavebnicových profilů Logiman – spoj skrytý uvnitř profilu pro čistý vzhled konstrukce.",
          "vnitřní spoje profilů"),
    176: ("Spojovací klouby s páčkou",
          "Spojovací klouby s aretační páčkou pro nastavitelné a rychle rozebíratelné spoje hliníkových stavebnicových profilů Logiman.",
          "spojovací klouby s páčkou"),
    178: ("Trojcestné ukosené rožky profilů",
          "Trojcestné rožky s ukoseným tvarem pro spojení tří hliníkových stavebnicových profilů Logiman v omezeném prostoru konstrukce.",
          "trojcestné ukosené rožky"),
    199: ("Matice s kloubem pro profily",
          "Kloubové matice pro pohyblivé a nastavitelné spoje hliníkových stavebnicových profilů Logiman – kompenzace odchylky úhlu spoje.",
          "matice s kloubem"),
    204: ("T matice otočné pro profily",
          "Otočné T-matice do drážky hliníkových stavebnicových profilů Logiman – rychlé zasunutí i uprostřed profilu bez navlékání od konce.",
          "T matice otočné"),
    205: ("T šrouby pro hliníkové profily",
          "T šrouby do drážky hliníkových stavebnicových profilů Logiman – spolehlivé šroubové spoje kompatibilní s T-maticemi a úhelníky.",
          "T šrouby"),
    218: ("Obdélníkové spojovací plotny profilů",
          "Obdélníkové spojovací plotny pro plošné spoje hliníkových stavebnicových profilů Logiman – vyšší tuhost spoje na větší ploše.",
          "obdélníkové plotny"),
    224: ("Obdélníkové matice pro profily",
          "Obdélníkové matice do drážky hliníkových stavebnicových profilů Logiman – stabilní uložení proti pootočení při utahování šroubu.",
          "matice obdélníkové"),
    227: ("Spojka s úhlem 45° pro profily",
          "Spojka s úhlem 45° pro šikmé spoje hliníkových stavebnicových profilů Logiman – konstrukce vzpěr, výztuh a šikmých rámů.",
          "spojka s úhlem 45"),
    228: ("Čtvercové matice pro profily",
          "Čtvercové matice do drážky hliníkových stavebnicových profilů Logiman – základní spojovací prvek pro šroubové spoje po délce drážky.",
          "matice čtvercové"),
    229: ("T matice kameny pro profily",
          "T-matice (kameny) do drážky hliníkových stavebnicových profilů Logiman – nejpoužívanější způsob zasunutí matice do drážky od konce profilu.",
          "T matice kameny"),
    230: ("T matice kameny dlouhé",
          "Dlouhé T-matice (kameny) do drážky hliníkových stavebnicových profilů Logiman – větší plocha pro spoje s vyšším namáháním.",
          "T matice kameny dlouhé"),
    231: ("Pružinové matice pro profily",
          "Pružinové matice do drážky hliníkových stavebnicových profilů Logiman – zasunutí a upevnění kdekoli podél drážky bez navlékání od konce.",
          "matice pružinové"),
    232: ("Stavitelné úhlové konzole profilů",
          "Plynule stavitelné úhlové konzole pro spoje hliníkových stavebnicových profilů Logiman pod libovolným úhlem – flexibilní konstrukční řešení.",
          "stavitelné úhlové konzole"),
    234: ("Vnitřní spojky úhel 90° profilů",
          "Vnitřní spojky pod úhlem 90° pro hliníkové stavebnicové profily Logiman – skrytý pravoúhlý spoj bez vyčnívajících dílů na povrchu.",
          "vnitřní spojky úhel 90"),
    263: ("Šrouby pro hliníkové profilové konstrukce",
          "Šrouby pro spojovací prvky hliníkových stavebnicových profilů Logiman – kompletní sortiment k úhelníkům, maticím a rožkům skladem.",
          "šrouby pro profilové konstrukce"),
    157: ("Spojovací prvky systému Dynamic",
          "Spojovací prvky pro hliníkové profily systému Dynamic Logiman – díly pro montážní linky, dopravníky a válečkové dráhy.",
          "spojovací prvky Dynamic"),
    191: ("Příslušenství systému Dynamic",
          "Příslušenství k hliníkovým profilům systému Dynamic Logiman – doplňkové díly pro dopravníkové a montážní linky.",
          "příslušenství Dynamic"),
    192: ("Profily systému Dynamic pro linky a dopravníky",
          "Hliníkové profily systému Dynamic Logiman – konstrukční řada určená pro montážní linky, dopravníkové tratě a válečkové dráhy.",
          "profily Dynamic linky"),
    225: ("Válečkové dráhy systému Dynamic",
          "Válečkové dráhy ze systému Dynamic Logiman pro pohyb materiálu a výrobků na montážních linkách a dopravnících.",
          "válečkové dráhy"),
    183: ("Ergonomické balicí stoly SSE",
          "Balicí stoly SSE z hliníkových profilů s drážkou pro snadnou montáž vlastního příslušenství – flexibilní ergonomické pracoviště pro balení a expedici.",
          "balicí stoly SSE"),
    206: ("Lehký balicí stůl Light-30-A",
          "Lehký balicí stůl Light-30-A Logiman pro balení, příjem a expedici – rozměry stolu lze upravit na míru provozu.",
          "balicí stůl Light-30-A"),
    226: ("Příslušenství balicích stolů",
          "Příslušenství k balicím stolům a pracovištím Logiman – doplňkové díly pro dovybavení balicího pracoviště podle potřeby.",
          "příslušenství balicích stolů"),
    261: ("Deskové materiály pro stavebnici do auta",
          "Deskové materiály pro stavbu vestaveb a regálů do užitkových vozidel ze stavebnice Logiman – podlahy, přepážky a police na míru.",
          "deskové materiály stavebnice do auta"),
    194: ("Elektrické ergonomické stoly ESSE",
          "Elektricky výškově stavitelné stoly ESSE Logiman – ergonomické pracoviště s motorickým nastavením výšky pro maximální komfort obsluhy.",
          "elektrické ergonomické stoly ESSE"),
    200: ("Komponenty a polotovary pracovních stolů",
          "Komponenty, polotovary a náhradní díly pro ergonomické pracovní stoly Logiman – zvedací sloupky, desky a doplňky pro vlastní sestavení.",
          "komponenty pracovních stolů"),
    201: ("Zvedací sloupky pro pracovní stoly",
          "Zvedací sloupky pro výškově stavitelné pracovní stoly Logiman – elektrický pohon pro plynulé nastavení pracovní výšky.",
          "zvedací sloupky"),
    207: ("Laminovaná dřevotříska pro pracovní desky",
          "Laminovaná dřevotříska pro pracovní desky stolů a pracovišť Logiman – odolný povrch pro běžný dílenský provoz.",
          "laminovaná dřevotříska"),
    238: ("Zvedací elektrické police na míru",
          "Vlastní elektrický zvedací systém polic Logiman na míru – zvedání těžších přístrojů do výšky nad pracovním stolem podle potřeb zákazníka.",
          "zvedací elektrické police"),
    213: ("Montážní linky na míru",
          "Montážní linky na míru od Logiman – válečkové nebo spádové dráhy pro pohyb výrobků, řešení podle rozměru profilu a provozu zákazníka.",
          "montážní linky na míru"),
    219: ("Vozíky a stojany na míru",
          "Manipulační vozíky a stojany z hliníkových profilů Logiman pro sklady a výrobu – konstrukce na míru podle požadavků provozu.",
          "vozíky a stojany"),
    222: ("Specializované pracovní stoly na míru",
          "Specializované pracovní stoly Logiman – upínací stoly a podstavce pro roboty, nerezová provedení a řešení na míru výrobní linky.",
          "specializované pracovní stoly"),
    239: ("Montážní stůl Light-30-A",
          "Lehký montážní stůl Light-30-A Logiman pro montáž, kompletaci a kontrolu výrobků – rozměry lze upravit na míru pracoviště.",
          "montážní stůl Light-30-A"),
    240: ("Pojízdné pracovní stoly na míru",
          "Pojízdné pracovní stoly Logiman s pojezdovými koly a zachovanou výškovou stavitelností – snadné přemístění po provozu.",
          "pojízdné pracovní stoly"),
    241: ("Pracovní stoly na míru pro výrobu",
          "Pracovní stoly na míru od Logiman navržené s ohledem na zdraví zaměstnanců – od jednoho pracoviště po kompletní projekt nové výroby.",
          "pracovní stoly na míru"),
    242: ("Robustní pracovní stůl 45",
          "Robustní pracovní stůl 45 Logiman pro náročné provozy – individuální řešení pracoviště podle konkrétních požadavků zákazníka.",
          "robustní pracovní stůl 45"),
    243: ("Bezpečnostní ochranné oplocení strojů",
          "Bezpečnostní ochranné oplocení z hliníkových profilů Logiman pro ohrazení strojů a montážních linek podle bezpečnostních požadavků provozu.",
          "bezpečnostní ochranné oplocení"),
}


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, meta_title, meta_description, focus_keyword FROM content_categories "
        "WHERE is_visible=1 AND (meta_description IS NULL OR TRIM(meta_description)='')"
    )
    missing = {r["id"]: r for r in cur.fetchall()}

    not_covered = [i for i in missing if i not in DATA]
    stale = [i for i in DATA if i not in missing]
    if not_covered:
        print("CHYBI DATA pro id:", not_covered)
        sys.exit(1)
    if stale:
        print("Uz maji popis (asi zmenilo mezitim jiny bot), preskakuji:", stale)

    backup = {str(i): missing[i] for i in missing if i in DATA}
    backup_path = "backups/category_meta_description_backfill_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zaloha {len(backup)} radku -> {backup_path}")

    n = 0
    for cid, (title, desc, kw) in DATA.items():
        if cid not in missing:
            continue
        if dry_run:
            print(f"#{cid} {missing[cid]['name']!r}")
            print(f"  title: {title} ({len(title)} znaku)")
            print(f"  desc:  {desc} ({len(desc)} znaku)")
            continue
        cur.execute(
            "UPDATE content_categories SET meta_title=%s, meta_description=%s, "
            "focus_keyword=COALESCE(NULLIF(TRIM(focus_keyword),''), %s) WHERE id=%s",
            (title, desc, kw, cid),
        )
        n += 1

    if dry_run:
        print(f"\nDRY RUN - {len(DATA)} kategorii pripraveno, 0 zapsano. Spust s --apply pro skutecny zapis.")
    else:
        conn.commit()
        print(f"Zapsano {n} kategorii.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
