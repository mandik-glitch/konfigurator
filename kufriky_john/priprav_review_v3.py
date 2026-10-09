"""Soukromý zápis vizuální kontroly všech variant; bez DB a sítě."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'zdroje/doladeni-v3'
cat = json.loads((OUT/'pred-kufriky.json').read_text())
manifest = json.loads((OUT/'fotografie.json').read_text())
# All observations refer to the inspected contact sheets in the same folder.
# Confidence concerns visible topology, never a physical dimensional tolerance.
changes = {
 '4932471064': ('Hero_1', 'Nízké tělo, dvě západky, 10 vložek, šest obdélníkových polí spodního spojení.', 'Uchycení spon a držadla, okraj víka, spodní prvky uvnitř obálky.'),
 '4932464082': ('Hero_1', '10 vyjímatelných vložek; červená pevná rukojeť mezi dvěma sponami.', 'Červený úchop s kotvením, propojení víka a prolisů.'),
 '4932471065': ('Hero_1', 'Dvě západky po stranách úzkého čela, 5 vložek; čelo na kratší straně.', 'Dvě spony místo jedné, otočení čela na krátkou stranu, uchycení držadla.'),
 '4932471723': ('Hero_1', 'Jedna široká spona na krátkém čele, horní výklopné držadlo, vnitřní dělič.', 'Šířka spony, správná orientace, horní držadlo s čepy a vnitřní dělič.'),
 '4932471724': ('Hero_1', 'Otevřená přepravka; boční otvory tvoří samotné stěny; vodorovná žebra.', 'Odstraněna nadbytečná přidaná držadla; žebra a spodní červený odjišťovací prvek.'),
 '4932498323': ('Hero_5', '8 menších + 2 větší výklopné nádoby, čelní rukojeť; v přepravě nádoby směrem vzhůru.', 'Rukojeť přesunuta na krátkou stěnu; nádoby, skutečná dutina, víčka a samostatné panty.'),
 '4932478625': ('Hero_1', 'Tři úložné sloupce s červenými děliči a zadní dlouhá přihrádka; nejde o 10 červených vložek.', 'Odstraněno chybné uspořádání 10 vložek; nové přepážky podle otevřených snímků.'),
 '4932480623': ('Hero_1', 'Dvířka mají pant nahoře a vyklápějí se vzhůru.', 'Horní vodorovný pant a směr otevření; dveřní výztuhy, dolní uzávěr a kotvení.'),
 '4932501784': ('Hero_1', 'XL má dvě přední spony, boční rukojeti a kovové rohové tyče.', 'Odstraněn obecný přední úchop; doplněny boční rukojeti a uložení tyčí.'),
 '4932499703': ('Hero_1', 'Výrobce ukazuje otevřený kufr s červenými rámy vnitřních panelů a kapsami.', 'Upraveny rámy a skutečně duté kapsy; vložka přestala být řadou plných kvádrů.'),
 '4932499704': ('Hero_1', 'Výrobce ukazuje otevřený kufr s červenými rámy vnitřních panelů a kapsami.', 'Upraveny rámy a duté kapsy; rozdíl oproti elektrikářské variantě není doložen fotografiemi.'),
 '4932464078': ('Hero_1', 'Dvě kola vzadu, teleskopické tyče na zadní straně, dvě čelní spony a boční držadla.', 'Kruhová kola 228 mm, skutečná osa a upevnění, zadní vedení madla, boční rukojeti.'),
 '4932464079': ('Hero_1', 'Výklopné držadlo nahoře, pevný čelní úchop a dvě spony; horní vložka.', 'Kotvení sklopeného držadla a výztuhy víka; držadlo se otevírá společně s víkem.'),
 '4932464080': ('Hero_1', 'Dvě čelní spony, pevný červený úchop a vnitřní vyjímatelné vložky.', 'Čelní úchop s kotvením, propojené vrstvy víka a spony.'),
 '4932472129': ('Hero_1', 'Dvě zásuvky, červené přepážky, zajišťovací rám uchycený dole.', 'Kotvení rámu nahoře i dole; úchopy připojené k čelům, výška dutin zachována.'),
 '4932472130': ('Hero_1', 'Tři zásuvky; červené přepážky a dolní kloub zajišťovacího rámu.', 'Kotvení rámu a úchopů; dutiny a mezery mezi čely bez škálování.'),
 '4932493189': ('Hero_1', 'Čtyři čela, červené úchopy, dolní kloub a horní uzávěr rámu.', 'Kotvení čtyř úchopů, rámu a přepážek; zachované zdrojové dutiny.'),
 '4932493190': ('Hero_1', 'Dvě nízké zásuvky nahoře, jedna vysoká dole.', 'Výšky dutin 61 / 61 / 130 mm, přepážky a kotvení zajišťovacího rámu.'),
 '4932498651': ('Hero_1', 'Jediná vysoká čelní zásuvka, horní uzávěr, kola vzadu a teleskopické madlo.', 'Dutina vysoká 400 mm, kruhová kola 228 mm, upevněné madlo a úchop; odstraněn rám víc zásuvek.'),
 '4932478161': ('Hero_1', 'Obě kola na jednom konci dlouhé bedny; osy podél kratší strany. Dvě horní stohovací pozice.', 'Opravená strana a osa kol; kruhový průměr 230 mm, uchycené boční madlo, dvě pole horních spojů.'),
}
rows = []
for record in manifest['records']:
    sku = record['sku'][0]
    photo_tag, seen, changed = changes[sku]
    photos = record['photos']
    primary = next((p for p in photos if photo_tag in p['file']), photos[0])
    unverified = ['Poloměry, úkosy a tloušťky nejsou kótované.',
                  'Přesné vůle a profil PACKOUT nelze potvrdit fotografiemi.',
                  'Proporce nekótovaných detailů jsou vizuální rekonstrukce; fyzická přesnost není potvrzena.']
    if sku in ('4932499703','4932499704'):
        unverified += ['Dohledané CZ/SK nabídky opakují stejný snímek výrobce; nezávislý boční a spodní pohled konkrétní vložky chybí.']
    if sku == '4932501784':
        unverified += ['Galerie zobrazuje starší SKU 4932478162; konstrukční identita nové revize 4932501784 není potvrzená.']
    if sku == '4932498651':
        unverified += ['Zdroje se rozcházejí ve vnějších rozměrech; zachován původní rozpor v katalogu.']
    if sku in ('4932464078','4932498651','4932464079','4932471723','4932478161'):
        unverified += ['Model je v přepravní poloze; fotografie může mít vysunuté nebo zdvižené držadlo. Jeho zdvih není kótovaný.']
    match = ('Slabé místo: chybí odlišné pohledy a doložení vložky.' if sku in ('4932499703','4932499704')
             else 'Slabé místo: galerie nedokládá novou revizi SKU.' if sku == '4932501784'
             else 'Slabé místo: rozpor vnějších rozměrů ve zdrojích.' if sku == '4932498651'
             else 'Shoduje se hlavní uspořádání; rozdíly zůstávají v nekótovaných detailech.')
    public = {'seen': seen, 'changed': changed, 'match': match,
              'unverified': unverified, 'source_photo_url': primary['url'],
              'source_page_url': primary['page_url'], 'photo_count': len(photos),
              'comparison_note': 'Render ve směru vybraného snímku. Perspektiva je přiblížená; fotografie není rozměrový výkres.',
              'render_file': 'porovnani/'+sku+'.png', 'render_before_file': 'porovnani/'+sku+'-v2.png'}
    rows.append({'id': record['id'], 'sku': record['sku'], 'public': public,
                 'private_reference_file': primary['file'],
                 'inspected_contact_sheet': 'zdroje/doladeni-v3/'+sku+'/prehled.jpg'})
(OUT/'review.json').write_text(json.dumps({'method':'John vizuálně prohlédl soukromé galerie všech 20 typů; žádná fyzická tolerance nebyla odvozena.', 'records': rows}, ensure_ascii=False, indent=2)+'\n')
print('Zápis kontroly všech 20 typů připraven.')
