"""Čisté kontroly podkladů a výstupů; bez DB, internetu a hesel."""
from pathlib import Path
from html.parser import HTMLParser
import csv
import html
import json
import re
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parent
CAT=json.loads((ROOT/'kufriky.json').read_text())
RECORDS=CAT['records']
BY_SKU={sku:r for r in RECORDS for sku in r['sku']}
RETAIL=json.loads((ROOT/'zdroje/prodejci-detail.json').read_text())

def ean_valid(value):
    digits=[int(c) for c in value]
    return len(digits)==13 and (sum(digits[::2])+3*sum(digits[1::2]))%10==0

class CatalogueChecks(unittest.TestCase):
    def test_coverage_every_manufacturer_variant_decided(self):
        source_skus=set(CAT['coverage']['manufacturer_variants'])
        decided={sku for sku in BY_SKU if sku in source_skus}|{r['sku'] for r in CAT['excluded']}
        self.assertEqual(source_skus,decided)
        self.assertEqual(len({r['id'] for r in RECORDS}),len(RECORDS))
        self.assertEqual(len(RECORDS),34)
        self.assertEqual(sum(r['group']=='kufriky' for r in RECORDS),20)

    def test_axes_against_source_not_sorted_height(self):
        for r in RECORDS:
            d=r['outer'];v=d['mm']
            self.assertGreater(v['length'],400,r['id'])
            self.assertGreaterEqual(v['length'],v['width'])
            if d['raw_order']=='H × W × D':
                nums=list(map(float,re.findall(r'\d+(?:\.\d+)?',d['raw'])))
                self.assertEqual(v['height'],nums[0],r['id'])
                self.assertEqual(v['length'],max(nums[1:]),r['id'])
                self.assertEqual(v['width'],min(nums[1:]),r['id'])
            for inside in r['inner']:
                self.assertTrue(all(inside['mm'][axis]<=v[axis] for axis in v),r['id'])
        # Výška 1200 mm nesmí být zapsaná jako délka; kompaktní hloubka 411 se neztratí.
        self.assertEqual(BY_SKU['4932472131']['outer']['mm'],dict(length=660,width=510,height=1200))
        self.assertEqual(BY_SKU['4932471723']['outer']['mm'],dict(length=411,width=249,height=330))
        self.assertEqual(BY_SKU['4932471065']['outer']['mm'],dict(length=411,width=249,height=64))
        excluded={r['sku']:r for r in CAT['excluded']}
        self.assertEqual(excluded['4932471131']['outer']['mm']['length'],381)
        self.assertEqual(excluded['4932471131']['outer']['mm']['height'],508)
        self.assertEqual(excluded['4932471132']['outer']['mm']['length'],394)

    def test_dimensions_from_actual_primary_variant(self):
        variants={}
        for p in (ROOT/'zdroje').glob('packout-*.json'):
            if p.stem.endswith(('-cz','-sk')):continue
            d=json.loads(p.read_text())
            for group in d['groups']:
                for v in group.get('hasVariant',[group]):variants[v['sku']]=v
        for r in RECORDS:
            if r['outer']['basis']!='vyrobce':
                self.assertIn('Výrobce rozměry neuvádí.',r['notes'][0]);continue
            sku='4932478162' if '4932478162' in r['sku'] else r['sku'][0]
            props={p['name']:p['value'] for p in variants[sku]['additionalProperty']}
            raw=props.get('Dimensions (Outer)') or props.get('Size')
            self.assertEqual(re.findall(r'\d+(?:\.\d+)?',html.unescape(raw)),re.findall(r'\d+(?:\.\d+)?',r['outer']['raw']))
        self.assertEqual(BY_SKU['4932498651']['outer']['mm'],dict(length=610,width=480,height=550))
        self.assertTrue(any('665 × 570 × 480' in o['text'] for o in BY_SKU['4932498651']['observations']))

    def test_real_country_and_net_price_evidence(self):
        for r in RECORDS:
            self.assertEqual({s['country'] for s in r['sales']},{'CZ','SK'},r['id'])
            for sale in r['sales']:
                matches=[x for x in RETAIL if x.get('sku_requested')==sale['sku'] and x['url']==sale['url'] and not x.get('error')]
                self.assertTrue(matches,sale)
                self.assertIn(sale['sku'],r['sku'])
                self.assertIsNotNone(sale['price_net'],sale)
                self.assertGreater(sale['price_net'],0)
                self.assertEqual(sale['currency'],'CZK' if sale['country']=='CZ' else 'EUR')
                self.assertTrue(any('bez DPH' in t for x in matches for t in x['specifications']),sale)
                gross=matches[0].get('properties',{}).get('price',[])
                if len(gross)==1:
                    ratio=1.21 if sale['country']=='CZ' else 1.23
                    self.assertLess(abs(float(gross[0])/ratio-sale['price_net']),.6,sale)
        # Brání záměně nižší ceny doporučeného příslušenství za cenu brašny.
        self.assertEqual(next(s['price_net'] for s in BY_SKU['4932464085']['sales'] if s['country']=='CZ'),2757)
        self.assertEqual(next(s['price_net'] for s in BY_SKU['4932498634']['sales'] if s['country']=='CZ'),4636)

    def test_xl_skus_and_eans_not_merged(self):
        xl=BY_SKU['4932501784']
        self.assertIs(xl,BY_SKU['4932478162'])
        self.assertEqual({e['sku']:e['ean'] for e in xl['eans']},{'4932501784':'4058546645007','4932478162':'4058546340957'})
        self.assertEqual(len(xl['sales']),4)
        for r in RECORDS:
            for e in r['eans']:
                self.assertTrue(ean_valid(e['ean']),e)

    def test_load_contexts_and_missing_values(self):
        rolling=BY_SKU['4932498651']
        self.assertEqual({c['context']:c['kg'] for c in rolling['capacity']},{'Uvnitř':68,'Na horní straně':113})
        for sku in ['4932472129','4932472130','4932493189','4932493190']:
            caps=BY_SKU[sku]['capacity']
            self.assertEqual(caps[0]['kg'],22)
            self.assertEqual(caps[1]['kg'],11)
        self.assertEqual(BY_SKU['4932471723']['mass']['kg'],2.5)
        self.assertEqual(BY_SKU['4932471723']['mass']['basis'],'vyrobce')
        for sku in ['4932464082','4932471064','4932471065','4932499703','4932499704']:
            self.assertEqual(BY_SKU[sku]['capacity'],[])
            self.assertTrue(any('Nosnost' in s for s in BY_SKU[sku]['missing']))
        self.assertTrue(all(r['model_file'] is None for r in RECORDS))
        self.assertIn(CAT['stage'],(1,2))
        if CAT['stage']==2:
            self.assertTrue(all(r['model_status']=='chybi_presny_model' for r in RECORDS if r['group']=='kufriky'))

    def test_fact_sources_and_local_photos(self):
        for r in RECORDS:
            for item in [r['outer'],r['mass'],r['hardware']]+r['inner']+r['capacity']+r['eans']+r['observations']:
                if item is not None:self.assertRegex(item['source_url'],r'^https://')
            photo=r['image'];path=ROOT/'nahled'/photo['file']
            self.assertTrue(path.is_file(),r['id'])
            self.assertRegex(photo['source_url'],r'^https://static\.milwaukeetool\.eu/')
            with Image.open(path) as im:
                self.assertEqual(im.width,240)
                self.assertGreater(im.height,0)
                im.verify()

    def test_csv_and_public_data_match(self):
        with (ROOT/'kufriky.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f,delimiter=';'))
        self.assertEqual([x['id'] for x in rows],[x['id'] for x in RECORDS])
        for csvrow,r in zip(rows,RECORDS):
            self.assertEqual(float(csvrow['L_mm']),r['outer']['mm']['length'])
            self.assertEqual(float(csvrow['V_mm']),r['outer']['mm']['height'])
        # Schválený veřejný náhled etapy 1 zůstává historickou kopií.
        prior=ROOT/'zdroje' if CAT['stage']==2 else ROOT
        prefix='etapa1-' if CAT['stage']==2 else ''
        self.assertEqual((prior/(prefix+'kufriky.json')).read_bytes(),(ROOT/'nahled/kufriky.json').read_bytes())
        self.assertEqual((prior/(prefix+'kufriky.csv')).read_bytes(),(ROOT/'nahled/kufriky.csv').read_bytes())
        script=(ROOT/'nahled/data.js').read_text()
        parsed=json.loads(script.split('window.KUFRIKY = ',1)[1].strip().removesuffix(';').replace('<\\/','</'))
        self.assertEqual(parsed,json.loads((prior/(prefix+'kufriky.json')).read_text()))

    def test_static_page_rules(self):
        public=ROOT/'nahled'
        for p in public.rglob('*'):
            if not p.is_file():continue
            self.assertIn(p.suffix,{'.html','.js','.css','.json','.csv','.jpg'})
            if p.suffix=='.jpg':continue
            text=p.read_text(encoding='utf-8-sig')
            for forbidden in ['/home/openai1','/opt/','ukoly/']:
                self.assertNotIn(forbidden,text,p.name)
        index=(public/'index.html').read_text()
        self.assertIn('<meta name="robots" content="noindex, nofollow">',index)
        self.assertIn("connect-src 'none'",index)
        self.assertNotRegex(index,r'(?:src|href)="https?://')
        runtime=(public/'app.js').read_text()+(public/'style.css').read_text()
        self.assertNotRegex(runtime,r'\b(?:fetch|XMLHttpRequest|WebSocket|sendBeacon)\s*\(|@import')

if __name__=='__main__':
    unittest.main(verbosity=2)
