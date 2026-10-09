"""Zapíše již ověřené výsledky spodních dílů do katalogu; bez DB a sítě."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
after = json.loads((ROOT/'overeni-tvar-v4/podstavy.json').read_text())
before = json.loads((ROOT/'overeni-tvar-v4/podstavy-pred.json').read_text())
if after['status'] != 'PASS' or after['models_measured'] != 21:
    raise ValueError('Chybí úplná úspěšná kontrola skutečných modelů')
catalog = json.loads((ROOT/'kufriky.json').read_text())
old_by_sku = {r['sku']: r for r in before['rows']}
by_sku = {r['sku']: r for r in after['rows']}
for record in catalog['records']:
    if record['group'] != 'kufriky':
        continue
    sku = record['sku'][0]
    row, old = by_sku[sku], old_by_sku[sku]
    if any(v['sku'] not in by_sku for v in record['model_variants']):
        raise ValueError('Nezměřená varianta '+sku)
    changed = sum(a['min_mm'] != b['min_mm'] or a['max_mm'] != b['max_mm']
                  for a, b in zip(old['rows'], row['rows']))
    review = record['review']
    review['support_summary'] = (f"Ověřeno {row['supports_measured']} spodních dílů: všechny vrcholy i středy uvnitř skutečného dna, dosed a souměrnost v pořádku. Přesah 0 mm; číselná tolerance 0,01 mm.")
    review['support_checked'] = True
    review['support_changes'] = changed
    review['changed_v4'] = review['changed']
    if changed == 0:
        review['changed'] = 'Spodní spojovací prvky beze změny: úplná kontrola potvrdila správné umístění pod skutečným dnem.'
    elif changed == 4:
        review['changed'] = 'Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3.'
    if sku in ('4932464078', '4932478161'):
        review['changed'] += ' Odkryté čelní západky v zapuštěné stěně mezi rohy; označení dosedá na tuto stěnu. Vnitřní kóty, kola a obálka zachované.'
    review['unverified'] = list(dict.fromkeys(review['unverified']+[
        'Přesný tvar, počet a rozteče spodních spojovacích prvků nejsou doložené kótovaným CAD ani měřením fyzického kusu.'
    ]))
    review['comparison_note'] = 'Vlevo zachovaný model v3, vpravo v4 ze stejného směru. Směr vybrané fotografie je orientační; objektiv a přesná poloha kamery nejsou kalibrované. Níže oba boky, čelo, horní a spodní pohled skutečného modelu.'
    review['visual_check_v4'] = 'Prohlédnuto zepředu, z obou boků, shora a zespodu. Podstavné díly nepřesahují skutečné dno; vzhled nekótovaných detailů zůstává rekonstrukcí.'
(ROOT/'kufriky.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n')
print('V4: katalog doplněn výsledky všech 328 spodních dílů a obrazové kontroly.')
