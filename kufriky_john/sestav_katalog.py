"""Čisté sestavení katalogu z uložených podkladů, bez databáze a sítě."""
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import csv
import html
import json
import re

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'nahled'
DATE = '2026-10-05'

# SKU -> český název, zařazení, typ. Anglický přesný název se bere ze zdroje.
TYPES = {
 '4932464080': ('Box na nářadí', 'kufriky', 'Box'),
 '4932464079': ('Velký box na nářadí', 'kufriky', 'Box'),
 '4932478162': ('Box na nářadí XL', 'kufriky', 'Box'),
 '4932471723': ('Kompaktní box na nářadí', 'kufriky', 'Box'),
 '4932493189': ('Box se 4 zásuvkami', 'kufriky', 'Zásuvky'),
 '4932472129': ('Box se 2 zásuvkami', 'kufriky', 'Zásuvky'),
 '4932472130': ('Box se 3 zásuvkami', 'kufriky', 'Zásuvky'),
 '4932493190': ('Box se zásuvkami 2 + 1', 'kufriky', 'Zásuvky'),
 '4932480623': ('Skříň s předními dvířky', 'kufriky', 'Skříň'),
 '4932471724': ('Otevřená přepravka', 'kufriky', 'Přepravka'),
 '4932464082': ('Organizér', 'kufriky', 'Organizér'),
 '4932478625': ('Hluboký organizér', 'kufriky', 'Organizér'),
 '4932471064': ('Nízký organizér', 'kufriky', 'Organizér'),
 '4932471065': ('Kompaktní nízký organizér', 'kufriky', 'Organizér'),
 '4932498323': ('Organizér s výklopnými boxy', 'kufriky', 'Organizér'),
 '4932478161': ('Pojízdná bedna na nářadí', 'kufriky', 'Pojízdný box'),
 '4932464078': ('Pojízdný box s výsuvným držadlem', 'kufriky', 'Pojízdný box'),
 '4932498651': ('Pojízdný box s čelní zásuvkou', 'kufriky', 'Pojízdný box'),
 '4932499703': ('Box pro elektrikáře', 'kufriky', 'Profesní kufr'),
 '4932499704': ('Box pro instalatéry', 'kufriky', 'Profesní kufr'),
 '4932480625': ('Vložka na nářadí s držadlem', 'ostatni', 'Otevřená vložka'),
 '4932471068': ('Plochý vozík', 'ostatni', 'Vozík'),
 '4932472131': ('Dvoukolový vozík', 'ostatni', 'Vozík'),
 '4932472128': ('Pracovní deska', 'ostatni', 'Deska'),
 '4932478648': ('Termobox XL', 'ostatni', 'Termobox'),
 '4932471722': ('Termobox 15 l', 'ostatni', 'Termobox'),
 '4932492962': ('Lékárnička XL s náplní', 'ostatni', 'Lékárnička'),
 '4932464085': ('Otevřená brašna 40 cm', 'ostatni', 'Brašna'),
 '4932464086': ('Otevřená brašna 50 cm', 'ostatni', 'Brašna'),
 '4932471067': ('Pracovní taška 50 cm', 'ostatni', 'Brašna'),
 '4932471130': ('Taška pro řemeslníky / Tech Bag', 'ostatni', 'Brašna'),
 '4932498634': ('Profesionální brašna 38 cm', 'ostatni', 'Brašna'),
 '4932493623': ('Uzavřená brašna 38 cm', 'ostatni', 'Brašna'),
 '4932498633': ('Strukturovaný batoh', 'ostatni', 'Batoh'),
}

HARDWARE = {
 'packout-boxes': 'Kovem vyztužený uzamykací bod; IP65. Horní vyztužené držadlo výrobce výslovně připisuje velkému boxu.',
 'packout-drawer-tool-boxes': 'Zajišťovací lišta zásuvek s možností visacího zámku; kuličkové výsuvy.',
 'packout-cabinet': 'Západka dole a vzadu pro stohování či zavěšení; zasouvací přední dvířka.',
 'packout-crate': 'Možnost stohování v obou směrech; otevřená přepravka.',
 'packout-organisers': 'Vyjímatelné přihrádky a těsnění IP65; rozměry západek a držadla neuvedeny.',
 'packout-tip-bin-organiser': 'Vyjímatelné výklopné boxy, rukojeť a uchycení na nástěnnou desku.',
 'packout-rolling-tool-chest': 'Výsuvné držadlo; terénní kola 230 mm; dvě stohovací pozice nahoře.',
 'packout-trolley-box': 'Výsuvné držadlo; kola 228 mm; vyztužený uzamykací bod.',
 'packout-rolling-drawer': 'Čelní zásuvka; kola 228 mm; boční uchycení příslušenství na tyčích.',
 'packout-electrician-box': 'Vložky a přepážky fixují nářadí; rozměry držadla a zámků neuvedeny.',
 'packout-plumbing-box': 'Vložky a přepážky fixují nářadí; rozměry držadla a zámků neuvedeny.',
 'packout-tool-tray': 'Horní držadlo; nastavitelné přepážky; lze vložit do větších boxů.',
 'packout-flat-trolley': 'Otočná kola s brzdami a blokovací brzdou pro připojování modulů.',
 'packout-2-wheeled-cart': 'Dvě montážní plochy; skládací základna; kola 250 mm.',
 'packout-customisable-work-surface': 'Povrch pro montáž na horní část stohu PACKOUT.',
 'packout-xl-cooler': 'Vyjímatelná přihrádka a otvírák; vložka IP65.',
 'packout-hard-cooler': 'Vyjímatelná přihrádka a otvírák; vložka IP65.',
 'packout-first-aid-kit-xl': 'Červený organizér s náplní; vyjímatelné přihrádky a těsnění IP65.',
 'packout-tote-toolbag': 'Tvarované držadlo; kovové spony, zipy a patentky.',
 'packout-duffel-bag': 'Ramenní popruh, horní a boční držadla.',
 'packout-tech-bag': 'Pevná základna PACKOUT; ochranné kapsy pro elektroniku.',
 'packout-pro-tote-toolbag': 'Ramenní popruh, rukojeť a kovová poutka.',
 'packout-closed-tote-tool-bag': 'Ramenní popruh, rukojeť a kovová poutka.',
 'packout-structured-backpack': 'Polstrované ramenní popruhy a rukojeť; pevná základna PACKOUT.',
}

def load(name):
    return json.loads((ROOT/'zdroje'/name).read_text())

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def numbers(text):
    return [float(x.replace(',', '.')) for x in re.findall(r'\d+(?:[.,]\d+)?', html.unescape(text))]

def normalize_hwd(h, w, d):
    return {'length': max(w, d), 'width': min(w, d), 'height': h}

def dim(text, url, order='H × W × D', basis='vyrobce', axes_url=None):
    nums = numbers(text)
    if len(nums) != 3:
        return None
    a, b, c = nums
    normalized = normalize_hwd(a, b, c) if order == 'H × W × D' else {'length':a,'width':b,'height':c}
    formula = (f'L = max({b:g}, {c:g}) = {normalized["length"]:g}; '
               f'Š = min({b:g}, {c:g}) = {normalized["width"]:g}; V = {a:g} mm') if order == 'H × W × D' else f'L = {a:g}; Š = {b:g}; V = {c:g} mm'
    return {'mm': normalized, 'source_url': url, 'axes_source_url': axes_url or url,
            'raw':html.unescape(text), 'raw_order':order, 'basis':basis, 'formula':formula}

def price_from_text(text):
    m = re.search(r'(\d[\d\s\xa0]*(?:[.,]\d+)?)\s*(Kč|CZK|€)\s*bez DPH', text)
    return (float(re.sub(r'\s','',m[1]).replace(',','.')), 'CZK' if m[2] in ('Kč','CZK') else 'EUR') if m else (None, None)

def market(skus, details):
    result = []
    for sku in skus:
        for country in ('CZ','SK'):
            options = []
            for x in details:
                url = x['url']
                host = urlparse(url).hostname or ''
                if x.get('error') or x.get('sku_requested') != sku: continue
                if not host.endswith('.cz' if country == 'CZ' else '.sk'): continue
                # Detail musí doložit správné SKU, ne pouze podobný název nebo přesměrování.
                props = x.get('properties',{})
                if sku not in props.get('sku',[]) and sku not in url and sku not in (x.get('card_evidence') or ''): continue
                texts = x.get('specifications',[])
                candidates = [price_from_text(t) for t in texts if 'bez DPH' in t]
                val, cur = next((p for p in candidates if p[0] is not None),(None,None))
                stock = next((t for t in texts if re.search(r'Sklad|Odesíl|objedn|týd', t, re.I)),None)
                if stock is None:
                    availability=props.get('availability',[])
                    if any(x.endswith('/OutOfStock') for x in availability):stock='Mimo sklad (údaj stránky); termín viz prodejce'
                    elif any(x.endswith('/InStock') for x in availability):stock='Skladem (údaj stránky)'
                seller = ('V-V nářadí' if 'v-vnaradi' in host else 'OK nářadí' if 'oknaradie' in host
                          else 'Elglobal' if 'elglobal' in host else 'ELVIN' if 'elvin' in host else 'ELKOV' if 'elkov' in host else host)
                priority = (0 if 'v-vnaradi' in host or 'oknaradie' in host else 1 if 'elglobal' in host else 2)
                options.append((val is None, priority, {'country':country,'sku':sku,'seller':seller,'url':url,
                       'price_net':val,'currency':cur,'vat':'bez DPH','availability_raw':stock,'checked_on':DATE}))
            if options: result.append(sorted(options,key=lambda x:x[:2])[0][2])
    return result

def mass_value(skus, props, source, details):
    if 'Weight' in props:
        return {'kg':numbers(props['Weight']['value'])[0], 'source_url':source,
                'basis':'vyrobce', 'note':'Hmotnost uvedená výrobcem.'}
    for sku in skus:
        for x in details:
            if x.get('sku_requested') != sku or x.get('error'):continue
            for t in x.get('specifications',[]):
                m = re.search(r'Hmotnost\s*:?\s*([\d.,]+)\s*kg',t,re.I)
                if m:
                    return {'kg':float(m[1].replace(',','.')), 'source_url':x['url'],
                            'basis':'prodejce', 'sku':sku, 'note':'Prodejce neurčuje, zda jde o hmotnost bez obalu.'}
    return None

def image_for(data, sku):
    for x in data['images']:
        url = x.get('src') or x.get('data-src')
        if url and f'/{sku}--' in url:
            parts = urlparse(url)
            query = dict(parse_qsl(parts.query));query['width']='240'
            return {'file':f'obrazky/{sku}.jpg', 'source_url':urlunparse(parts._replace(query=urlencode(query))),
                    'page_url':data['source_url'], 'caption':x.get('alt') or f'PACKOUT {sku}', 'credit':'Fotografie výrobce Milwaukee'}
    raise ValueError(f'Chybí fotografie SKU {sku}')

def build():
    OUT.mkdir(exist_ok=True)
    details = load('prodejci-detail.json')
    records, excluded, accounted = [], [], []
    for summary in load('prehled-vyrobce.json'):
        slug = summary['slug']
        path = ROOT/'zdroje'/f'{slug}.json'
        if not path.exists():continue
        data = load(path.name)
        source = data['source_url']
        local = load(f'{slug}-cz.json')
        official = [{'market':'EU','url':source}]+[
            {'market':country,'url':load(f'{slug}-{country.lower()}.json')['source_url']} for country in ('CZ','SK')]
        for g in data['groups']:
            for v in g.get('hasVariant',[g]):
                sku = v['sku']; accounted.append(sku)
                props = {x['name']:x for x in v.get('additionalProperty',[])}
                outer = dim(props['Dimensions (Outer)']['value'],source) if 'Dimensions (Outer)' in props else None
                if sku not in TYPES:
                    reason = 'Sada existujících boxů; nejde o další samostatný tvar.' if 'Contents' in props else 'Vnější vodorovná délka nepřesahuje 400 mm.'
                    raw = props.get('Size',{}).get('value') if outer is None else None
                    excluded.append({'sku':sku,'name':v['name'],'reason':reason,'outer':outer,'raw_dimensions':raw,'source_url':source})
                    continue
                name, group, category = TYPES[sku]
                skus = ['4932501784','4932478162'] if sku == '4932478162' else [sku]
                eans = [{'sku':skus[0],'ean':props.get('EAN',{}).get('value'),'source_url':source}]
                if len(skus)>1:
                    eans.append({'sku':'4932478162','ean':'4058546340957','source_url':'https://eshop.elkov.cz/products/milwaukee-box-packout-xl-4932478162'})
                notes = []
                observations = []
                if sku in ('4932499703','4932499704'):
                    supplement = load(f'rozmery-doplnkove-{sku}.json')
                    outer = dim('560 × 410 × 165', supplement['url'], 'L × Š × V', 'prodejce')
                    if sku == '4932499703':
                        outer['original_units'] = 'cm'; outer['formula'] = 'L = 56 × 10 = 560; Š = 41 × 10 = 410; V = 16,5 × 10 = 165 mm'
                    notes.append('Výrobce rozměry neuvádí. Rozměry prodejce nejsou potvrzené výrobcem; před 3D změřit skutečný kus.')
                    if sku == '4932499704':
                        notes.append('Zdroj s označenými osami byl čitelný ve veřejném indexu; přímý přístup odmítl. Jiný prodejce uvádí délku 561 mm.')
                        observations.append({'text':'Klium: délka 561 mm, výška 165 mm; rozpor v délce 1 mm.','source_url':'https://www.klium.be/fr/milwaukee-packout-c103611?page=6'})
                if sku == '4932492962':
                    supplement = load(f'rozmery-doplnkove-{sku}.json')
                    outer = dim(props['Size']['value'],source,'L × Š × V','vyrobce',supplement['url'])
                    notes.append('Výrobce uvádí 500 × 380 × 120 bez názvů os. Pořadí L × Š × V doloženo prodejcem Klium.')
                if sku in ('4932471723','4932471065'):
                    notes.append('Hraniční případ: delší vodorovná strana je podle výrobce 411 mm, ačkoli jde o kompaktní půlmodul. Zařazeno podle doložených rozměrů; fyzickou obálku před 3D ověřit.')
                if sku == '4932471723':
                    observations.append({'text':'ELKOV uvádí hmotnost 3,07 kg, výrobce 2,50 kg; obal ani způsob vážení nejsou upřesněny.','source_url':'https://eshop.elkov.cz/products/milwaukee-kufr-kompaktni-na-naradi-packout-4932471723'})
                if sku == '4932471065':
                    observations.append({'text':'Starší katalog výrobce 2020/21 uvádí 250 × 380 × 65 mm. Současná stránka uvádí H × W × D = 64 × 249 × 411 mm. Starý údaj nesplňuje hranici 400 mm; před 3D rozměry potvrdit.','source_url':'https://www.esco.ae/assets/pdf/products/TED/Milwaukee/MILWAUKEE%20POWERTOOLS%20CATALOGUE%202020.pdf'})
                if sku == '4932498651':
                    observations.append({'text':'Katalog výrobce 2025 uvádí H × W × D = 665 × 570 × 480 mm. Současná EU/CZ/SK stránka uvádí 550 × 610 × 480 mm. V tabulce je současná stránka; rozdíl není vyřešen, před 3D nutné potvrzení výrobce nebo měření.','source_url':'https://s3.eu-west-2.amazonaws.com/milwaukee-finland/Milw_HT-STORAGE_Catalogue_2025-FINLAND_SCREEN.pdf'})
                if sku == '4932464080':
                    observations.append({'text':'ELKOV v popisu uvádí 560 × 410 × 170 mm; výrobce H × W × D = 165 × 561 × 411 mm.','source_url':'https://eshop.elkov.cz/products/milwaukee-box-packout-4932464080'})
                if sku == '4932464079':
                    observations.append({'text':'ELKOV v popisu uvádí 560 × 410 × 290 mm; výrobce H × W × D = 282 × 561 × 411 mm.','source_url':'https://eshop.elkov.cz/products/milwaukee-box-packout-velky-4932464079'})
                if len(skus)>1:
                    notes.append('Současné CZ/SK číslo 4932501784 a starší 4932478162 mají v této stránce výrobce společnou rozměrovou specifikaci XL. Úplnou konstrukční shodu obou verzí netvrdím. EAN a prodejní nabídky jsou oddělené.')
                if outer and outer['mm']['length'] <= 400:raise ValueError(f'Zařazení pod hranicí: {sku}')
                inner = []
                if 'Dimensions (Inner)' in props:
                    raw = props['Dimensions (Inner)']['value']
                    if sku == '4932493190':
                        for text, label in [('61 x 416 x 322','Malá zásuvka'),('130 x 416 x 322','Velká zásuvka')]:
                            inner.append({'context':label,**dim(text,source)})
                    else:
                        inner.append({'context':'Jedna zásuvka' if category=='Zásuvky' else 'Úložný prostor',**dim(raw,source)})
                capacity = []
                if 'Loading capacity' in props:
                    capacity.append({'kg':numbers(props['Loading capacity']['value'])[0], 'context':'Celý box' if category=='Zásuvky' else 'Uvedená nosnost', 'source_url':source,'basis':'vyrobce'})
                feature_load = {
                  '4932498651':[(68,'Uvnitř'),(113,'Na horní straně')],
                  '4932471068':[(113,'Celý vozík')], '4932472131':[(180,'Celý vozík')],
                  '4932480623':[(22,'Úložný prostor')], '4932480625':[(11,'Celá vložka')],
                  '4932472128':[(22,'Pracovní deska')], '4932498633':[(22.7,'Celý batoh')],
                  '4932498634':[(22.7,'Brašna; společná stránka řady')],
                }
                if sku in feature_load:
                    capacity.extend({'kg':kg,'context':ctx,'source_url':local['source_url'],'basis':'vyrobce'} for kg,ctx in feature_load[sku])
                if category=='Zásuvky':
                    capacity.append({'kg':11,'context':'Jedna zásuvka; celkem maximálně 22 kg','source_url':local['source_url'],'basis':'vyrobce'})
                if sku == '4932471723':
                    capacity.append({'kg':34,'context':'Dle prodejce; výrobce v tabulce neuvedl','source_url':'https://eshop.elkov.cz/products/milwaukee-kufr-kompaktni-na-naradi-packout-4932471723','basis':'prodejce'})
                weight = mass_value(skus,props,source,details)
                if sku == '4932478162':
                    weight = {'kg':7.5,'sku':'4932501784','source_url':'https://www.elvin.cz/p/milwaukee-box-na-naradi-xl-packouttm-4932501784','basis':'prodejce','note':'Nové SKU; prodejce neurčuje, zda jde o hmotnost bez obalu.'}
                    observations.append({'text':'Starší SKU 4932478162: ELKOV uvádí 7,56 kg; nový SKU ELVIN 7,5 kg.','source_url':'https://eshop.elkov.cz/products/milwaukee-box-packout-xl-4932478162'})
                # Další rozměry prodejců uchováváme jako rozpor, nepřepisujeme výrobce.
                for x in details:
                    if x.get('sku_requested')!=sku or x.get('error'):continue
                    for t in x.get('specifications',[]):
                        if re.search(r'ozměr|ozmer',t) and len(numbers(t))==3:
                            vals=numbers(t)
                            if re.search(r'vnitř|vnút|inner',t,re.I) or any(sorted(vals)==sorted(item['mm'].values()) for item in inner):
                                continue
                            if outer and sorted(vals)!=sorted(outer['mm'].values()):
                                observations.append({'text':f'Prodejce uvádí: {t}. Pořadí os nemusí být vyznačené.','source_url':x['url']})
                sales=market(skus,details)
                if not sales:raise ValueError(f'Chybí CZ/SK prodej: {sku}')
                hardware=HARDWARE.get(slug,'Popis úchytů neuveden.')
                if slug == 'packout-boxes' and sku!='4932464079':hardware='Kovem vyztužený uzamykací bod; rodina boxů má těsnění IP65. Přesné rozměry držadla neuvedeny.'
                missing=[]
                if not weight:missing.append('Hmotnost: údaj nedohledán.')
                if not capacity:missing.append('Nosnost: údaj nedohledán; neodvozovat z hmotnosti nebo objemu.')
                if not inner:missing.append('Vnitřní rozměry: údaj nedohledán nebo se na otevřený díl nevztahuje.')
                if {x['country'] for x in sales}!={'CZ','SK'}:missing.append('Prodej doložen pouze v '+', '.join(sorted({x['country'] for x in sales}))+'.')
                status='pozor' if notes or observations or outer['basis']=='prodejce' else 'zdroje'
                records.append({'id':f'milwaukee-packout-{skus[0]}','manufacturer':'Milwaukee','series':'PACKOUT™',
                  'name':name,'official_name':v['name'],'sku':skus,'eans':eans,'group':group,'category':category,
                  'outer':outer,'inner':inner,'mass':weight,'capacity':capacity,
                  'hardware':{'text':hardware,'source_url':local['source_url'],'scope':'Popis typu nebo společné rodiny; rozměry jednotlivých zámků a drážek nejsou doložené.'},
                  'sales':sales,'official_sources':official,'image':image_for(data,sku),
                  'notes':notes,'observations':observations,'missing':missing,'review_status':status,
                  'model_file':None,'model_status':'Etapa 2 čeká na Robertovo schválení tabulky.',
                  'measuring_needed':'Před 3D ověřit fyzickou obálku s držadly/zámky a konstrukční detaily; chybějící údaje vyžádat nebo změřit.',
                  'checked_on':DATE})
    records.sort(key=lambda r:(r['outer']['mm']['length'],r['name']))
    catalogue={'schema_version':'1.0','stage':1,'checked_on':DATE,
      'scope':'Milwaukee PACKOUT: L > 400 mm; veřejně doložený prodej v CZ a/nebo SK. Pevné úložné díly oddělené od brašen a ostatních modulů.',
      'dimensions_convention':'L = delší vodorovná strana; Š = kratší vodorovná strana; V = výška. Převod z označeného H × W × D: L=max(W,D), Š=min(W,D), V=H. Výška se do podmínky L > 400 nezapočítává.',
      'price_note':'Veřejné ceny bez DPH v měně zdroje, zachycené při průzkumu; aktuální cenu a dostupnost potvrzuje prodejce. Bez přepočtu měn.',
      'facts_vs_assumptions':'Vidím ve zdroji: citované specifikace a nabídky. Rozhodnutí Johna: rozdělení kategorií a definice L. Chybějící rozměry ani nosnosti nejsou odhadované.',
      'photo_note':'Lokální miniatury z veřejných stránek výrobce pro interní přehled; autorská práva výrobce. Volnou licenci ani právo dalšího publikování netvrdím.',
      'records':records,'excluded':excluded,
      'other_exclusions':[
        {'name':'Sady a naplněné sestavy','reason':'Odlišný obsah nebo kombinace již zapsaných boxů není další tvar kufru. Sada 4932464244 je výslovně zachycena výše. Další obchodní sestavy se nesčítají jako nové typy.','source_url':'https://www.milwaukeetool.eu/en-eu/storage/packout/packout-kits/'},
        {'name':'Montážní desky, háky, držáky, pěny a náhradní přihrádky','reason':'Samostatné příslušenství pro uchycení nebo vybavení; ne přepravní kufr. Vozíky, vložka s držadlem a pracovní deska jsou pro srovnání uvedeny v ostatních dílech.','source_url':'https://www.milwaukeetool.eu/en-eu/storage/packout/packout-mounting/'},
        {'name':'Nabíječky, rádia, světla a nádoby na nápoje','reason':'Funkční spotřebiče či nádoby, nikoli kufříky na nářadí.','source_url':'https://www.milwaukeetool.eu/range/packout/'},
      ],
      'outside_cz_sk':[
        {'sku':'48-22-8450','name':'PACKOUT Tool Case with Customizable Insert','reason':'Doložena stránka výrobce pro USA; veřejnou nabídku tohoto SKU v CZ/SK jsem nedohledal. Netvrdím, že dovoz není možný.','source_url':'https://www.milwaukeetool.com/products/details/packout-tool-case-w-customizable-insert/48-22-8450'},
        {'sku':'48-22-8441','name':'PACKOUT Single Drawer Tool Box','reason':'Doložena stránka výrobce pro USA; veřejnou nabídku tohoto SKU v CZ/SK jsem nedohledal.','source_url':'https://www.milwaukeetool.com/48-22-8441'},
      ],
      'coverage':{'manufacturer_variants':accounted,'category_sources':[
        {'url':f'https://www.milwaukeetool.eu/en-eu/storage/packout/{s}/'} for s in (
         'packout-tool-boxes','packout-organisers','packout-rolling-storage','packout-totes-and-bags','packout-tumblers-and-coolers')],
        'limitation':'Pokryty varianty příslušných veřejných EU produktových rodin a doložené nabídky CZ/SK. Úplnost není záruka zachycení neindexované novinky nebo soukromého dovozu.'}}
    write_json(ROOT/'kufriky.json',catalogue);write_json(OUT/'kufriky.json',catalogue)
    fields=['id','vyrobce','rada','nazev','presny_nazev_vyrobce','skupina','typ','sku','ean','L_mm','S_mm','V_mm','rozmery_zdroj','poradi_ve_zdroji','rozmery_podklad','hmotnost_kg','hmotnost_zdroj','hmotnost_podklad','nosnost_kg_a_kontext','nosnost_zdroje','vnitrni_rozmery','prodej_CZ_SK','ceny_bez_DPH','fotografie','fotografie_zdroj','vyrobce_zdroje','model_soubor','model_stav','poznamky']
    with (ROOT/'kufriky.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,delimiter=';');writer.writeheader()
        for r in records:
            d=r['outer']['mm'];w=r['mass'] or {}
            values = [r['id'],r['manufacturer'],r['series'],r['name'],r['official_name'],r['group'],r['category'],
              ' | '.join(r['sku']), ' | '.join(x['sku']+': '+str(x['ean']) for x in r['eans']),
              d['length'],d['width'],d['height'],r['outer']['source_url'],r['outer']['raw_order'],r['outer']['basis'],
              w.get('kg',''),w.get('source_url',''),w.get('basis',''),
              ' | '.join(f"{c['kg']} kg ({c['context']})" for c in r['capacity']),
              ' | '.join(c['source_url'] for c in r['capacity']),
              ' | '.join(f"{x['context']}: {x['mm']}" for x in r['inner']),
              ' | '.join(f"{s['country']} {s['sku']} {s['url']}" for s in r['sales']),
              ' | '.join(f"{s['country']} {s['sku']}: {s['price_net']} {s['currency']} bez DPH" for s in r['sales'] if s['price_net'] is not None),
              r['image']['file'],r['image']['source_url'],' | '.join(x['url'] for x in r['official_sources']),
              '',r['model_status'],' | '.join(r['notes']+r['missing']+[x['text'] for x in r['observations']])]
            assert len(values) == len(fields)
            writer.writerow(dict(zip(fields,values)))
    (OUT/'kufriky.csv').write_bytes((ROOT/'kufriky.csv').read_bytes())
    # Data jako lokální JS: stránka nepotřebuje fetch ani síťové API a funguje z file://.
    (OUT/'data.js').write_text('"use strict";\nwindow.KUFRIKY = '+json.dumps(catalogue,ensure_ascii=False).replace('</','<\\/')+';\n')
    print('Typy:',len(records),'kufříky:',sum(r['group']=='kufriky' for r in records),'ostatní:',sum(r['group']=='ostatni' for r in records),'vyřazené varianty:',len(excluded))

if __name__=='__main__':build()
