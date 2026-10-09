"""Propis skutečných výsledků do vlastního katalogu, bez DB a sítě."""
from pathlib import Path
import json, shutil

ROOT=Path(__file__).resolve().parent
cat=json.loads((ROOT/'kufriky.json').read_text())
audit=json.loads((ROOT/'overeni-tvar-v5/soucasti.json').read_text())
photos=json.loads((ROOT/'zdroje/doladeni-v5/fotografie.json').read_text())
assert audit['status']=='PASS'
for record in cat['records']:
    if record['id'] not in cat['model_order']:continue
    row=next(x for x in audit['rows'] if x['sku']==record['sku'][0]);n=row['supports']['supports_measured']
    record['review']['support_summary']=f'Ověřeno {n} spodních dílů: všechny vrcholy a středy v obrysu dna, opora na skutečné ploše, žádný nepovolený přesah. Číselná tolerance 0,01 mm.'
    if 'organizer_review' not in record:continue
    sku=record['sku'][0];rec=next(x for x in photos['records'] if x['sku']==sku)
    record['organizer_review']['parts_measured']=len(row['parts'])
    record['organizer_review']['new_photos']=sum('doladeni-v5' in x['file'] for x in rec['photos'])
    record['organizer_review']['angle_summary']={
        '4932471064':'zavřené šikmé, horní, otevřený, přenášení a složené kusy',
        '4932464082':'oba přímé boky, přímý spodek a horní pohled, šikmé víko i spodek, otevřený a složený stav',
        '4932471065':'přímý spodek, otevřený pohled shora, detail přihrádek, zavřený šikmý a složený stav',
        '4932478625':'zavřený šikmý, horní, otevřený s děliči i bez nich, manipulace a složené kusy',
        '4932498323':'přímý čelní, šikmé zavřené i otevřené boxy, boční přepravní poloha a složený stav'
    }[sku]
    limitations=['Přesné rozteče a profily spodních zubů nejsou kótované; jde o vzhledovou rekonstrukci.']
    if sku in ['4932471064','4932478625','4932498323']:
        limitations.append('Přímý spodek této konkrétní varianty nezískán; rodinnou podobnost nevydávám za měření.')
    record['review']['unverified']=list(dict.fromkeys(record['review']['unverified']+limitations))
    if sku in ['4932464082','4932478625'] and 'Červený úchop ve tvaru U' not in record['review']['changed']:
        record['review']['changed']+=' Červený úchop ve tvaru U otevřený nahoře místo uzavřeného obdélníku podle čelních fotografií.'
    record['organizer_review']['corrected']=record['review']['changed']
    record['organizer_review']['findings_v4']=('Čelní desky vyčnívaly o 16 mm; čelní díly o 3–7 mm z původního užšího trupu.' if sku in ['4932471064','4932471065'] else 'Čelní desky vyčnívaly o 15,44 mm; čelní díly o 3–7 mm z původního užšího trupu.' if sku!='4932498323' else 'Nebyl zjištěn přesah půdorysu trupu; doplněné odjištění pod držadlem.')
    if sku=='4932498323':
        record['review']['match']='V obrysu trupu, doplněné čelní odjištění. Tvar průhledných nádob a nekótované detaily zůstávají přibližnou rekonstrukcí.'
(ROOT/'kufriky.json').write_text(json.dumps(cat,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(ROOT/'overeni-tvar-v5/soucasti.csv',ROOT/'nahled-modely-v5/soucasti.csv')
print('V5: výsledky všech 20 typů zapsané do katalogu.')
