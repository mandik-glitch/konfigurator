"""Offline evidence inventory and explicitly labelled image-plane measurements."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'zdroje/doladeni-v6'
photos=json.loads((ROOT/'zdroje/doladeni-v5/fotografie.json').read_text())['records']
cat=json.loads((OUT/'pred-kufriky.json').read_text())
SKUS=['4932471064','4932464082','4932471065','4932478625','4932498323']

def photo(sku,pattern):
    matches=[p for r in photos if r['sku']==sku for p in r['photos'] if pattern in p['file']]
    assert matches,(sku,pattern)
    return matches[0]

# Integer annotations refer to the saved, unmodified source pixels. They are
# projected extents, never a claim of physical dimensions to +/- 2 mm.
# Each SKU has its OWN photo and annotations; no inherited family dimensions.
annotations={
 '4932471064':dict(top='Hero_4',bounds=[72,200,1128,1000],rows=[[312,506],[530,716],[744,932]],banks=[[130,534],[666,1070]],gap=[534,666],front_handle_fraction=[.32,.68],lid_height_fraction=.29,body_corner_fraction=.055,bottom=None),
 '4932464082':dict(top='TIM-Photo001',bounds=[0,0,1,1],rows=None,banks=None,front_handle_fraction=[.32,.68],lid_height_fraction=.22,body_corner_fraction=.055,bottom='Photo007'),
 '4932471065':dict(top='DE_4932471065_0',bounds=[0,0,1,1],rows=None,banks=None,front_handle_fraction=[.17,.83],lid_height_fraction=.29,body_corner_fraction=.085,bottom='DE_4932471065_3'),
 '4932478625':dict(top='Hero_4',bounds=[0,0,1,1],rows=None,banks=None,front_handle_fraction=[.32,.68],lid_height_fraction=.15,body_corner_fraction=.055,bottom=None),
 '4932498323':dict(top='Hero_1',bounds=[72,148,1128,1052],rows=[[316,513],[544,728],[763,933]],banks=[[178,563],[641,1035]],gap=[563,641],front_handle_fraction=[.315,.685],lid_height_fraction=0,body_corner_fraction=.055,bottom=None),
}
findings={
 '4932471064':('Přihrádky splývaly do červené desky; chyběly děliče, střední pruh víka, výrazné rohy a čelní úchop. Víko bylo příliš nízké.', '10 samostatných zaoblených nádob (8 malých + 2 velké), děliče v každé nádobě, oddělené těsnicí okénko nad každou nádobou, střední pruh, čelní úchop a spony.'),
 '4932464082':('Tenké červené U nenahrazovalo skutečnou sklopnou rukojeť s černým vroubkovaným úchopem. Chyběly kapsy a sloupky čela. Víko téměř nemělo výšku.', 'Samostatné nádoby, výrazné zaoblené rohy, kapsy čela, červená výklopná rukojeť s černým úchopem, kovové spony a plné průhledné víko. Vlastní doložený spodek 3 × 4.'),
 '4932471065':('Nádoby byly téměř bez mezer a děličů; čelní úchop a spony neodpovídaly fotografii kompaktního SKU.', 'Pět samostatných nádob (4 malé + 1 velká), dva děliče velké a jeden každé malé, výraznější čelní úchop, spony u obou čelních rohů. Vlastní doložený spodek 3 × 2.'),
 '4932478625':('V5 měla jen dva červené děliče a čtyři oddíly. Hero_2 ukazuje tři dlouhé a tři krátké děliče po obou stranách pevného středu. Chyběly drážky pro děliče.', 'Šest červených vyjímatelných děličů (3 dlouhé + 3 krátké), pevný příčný střed a osm oddílů, kotvení děličů, vlastní profil čelní rukojeti a spon.'),
 '4932498323':('Souvislá vysoká stěna zakrývala vyklápěcí boxy, chyběl střední sloupek, tři kovové tyče a sklopné držadlo. Nádoby neměly správné čelo.', 'Otevřený nosný rám, 8 malých + 2 velké samostatné duté průhledné boxy, dělič v každém velkém, střední západka T, tři kovové přídržné tyče, přední rukojeť a její horní výklopná poloha.'),
}
rows=[]
for sku in SKUS:
    r=next(r for r in cat['records'] if sku in r.get('sku',[]))
    a=annotations[sku];top=photo(sku,a['top'])
    from PIL import Image
    w,h=Image.open(ROOT/top['file']).size
    # Annotate these independent top photos at their own resolution.
    if sku=='4932464082':
        a.update(bounds=[335,276,2432,1860],rows=[[487,878],[918,1320],[1358,1747]],banks=[[429,1275],[1503,2352]],gap=[1275,1503])
    if sku=='4932471065':
        a.update(bounds=[160,6,640,793],rows=[[154,339],[353,538],[548,744]],banks=[[203,595]],gap=None)
    if sku=='4932478625':
        a.update(bounds=[73,196,1129,1000],rows=[[310,506],[530,716],[744,932]],banks=[[129,534],[666,1070]],gap=[534,666])
    # Fractions for bin/lid topology, computed ONLY from that SKU's photo.
    x0,y0,x1,y1=a['bounds']
    a['row_fractions']=[[1-(v-y0)/(y1-y0) for v in row[::-1]] for row in a['rows']]
    a['bank_fractions']=[[(v-x0)/(x1-x0)-.5 for v in bank] for bank in a['banks']]
    a['top_photo']=dict(url=top['url'],page_url=top['page_url'],file=top['file'],size_px=[w,h])
    a['physical_tolerance_mm']=None
    a['measurement_note']='Ruční odečet projekce fotografie; nekalibrovaný objektiv. Hloubky, tloušťky a poloměry nejsou fyzicky ověřené. Poměry výšek a rukojetí jsou vizuální anotace vlastní fotografie SKU.'
    a['known_outer_mm']=r['outer']['mm'];a['known_inner_mm']=r['inner'][0]['mm'] if r['inner'] else None
    a['findings_v5'],a['changed']=findings[sku]
    a['unverified']=['Nekótované poloměry, tloušťky stěn, úkosy, přesné polohy, hloubky a vůle nejsou doměřené.','Shoda jednotlivých detailů do 2 mm není prokázaná; model není výrobní CAD.']
    if not a['bottom']:
        a['unverified'].append('Přímá fotografie spodku tohoto SKU nezískána; přesné spodní spojovací pozice nejsou v6 přebírané z jiného SKU ani potvrzené.')
    if sku=='4932478625':
        a['unverified'].append('Rozpor zdrojů: některé jazykové produktové listy uvádějí 10 nádob; fotografie tohoto SKU a katalog 2023 ukazují 6 děličů a 8 oddílů. Model odpovídá zobrazené sestavě.')
    rows.append(dict(sku=sku,**a))
(OUT/'anotace.json').write_text(json.dumps({'note':'Vnější a publikované vnitřní kóty jsou ověřené. Obrazové poměry nejsou fyzicky změřené milimetry.','records':rows},ensure_ascii=False,indent=2)+'\n')
print('Připravené nezávislé podklady pěti SKU, žádné převzetí roztečí mezi SKU.')
