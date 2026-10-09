"""Diagnostika skutečných součástí GLB: nulové plochy a tenké detaily.

Prahy jsou pouze číselné filtry pro kontrolu, nejsou údaji výrobce.
Nenulový objem neprokazuje fyzickou správnost nekótovaného detailu.
"""
from pathlib import Path
import json
import sys
import numpy as np
from over_realne_tvary import inspect

ROOT = Path(__file__).resolve().parent
catalog = json.loads((ROOT/'kufriky.json').read_text())
rows, failures, models = [], [], 0
for record in catalog['records']:
    if record['group'] != 'kufriky':
        continue
    for variant in record['model_variants']:
        _, parts, measured = inspect(ROOT/variant['file'])
        models += 1
        for part in parts:
            faces = part['faces']
            # Signed tetrahedra of the actual triangles; no box surrogate.
            volume = abs(float(np.einsum('ij,ij->i', faces[:, 0],
                                         np.cross(faces[:, 1], faces[:, 2])).sum()/6))
            size = np.ptp(part['vertices'], axis=0)
            row = {'sku': variant['sku'], 'part': part['name'], 'size_xyz_mm': size.tolist(),
                   'signed_volume_abs_mm3': volume, 'vertices_measured': len(part['vertices']),
                   'thin_diagnostic': bool(size.min() < 3),
                   'physical_detail_dimensions_verified': False}
            if row['thin_diagnostic']:
                row['interpretation'] = ('Vzhledové písmo; jeho tloušťka není technický údaj výrobce.'
                                         if part['name'].startswith('oznaceni-') else
                                         'Tenký objemový detail. Tloušťka zůstává rekonstrukční; porovnání proběhlo v kontrolních pohledech.')
            rows.append(row)
            if volume < .01 or size.min() < .05:
                failures.append(variant['sku']+' '+part['name'])
if models != 21 or not rows:
    raise ValueError('Neúplný rozsah měření')
result = {'status': 'FAIL' if failures else 'PASS', 'models_measured': models,
          'parts_measured': len(rows), 'vertices_measured': sum(r['vertices_measured'] for r in rows),
          'thin_details_listed': sum(r['thin_diagnostic'] for r in rows), 'failures': failures, 'rows': rows,
          'limitations': 'Číselná kontrola hledá nulové a téměř nulové plochy. Nenahrazuje fyzické měření tlouštěk, uzavřenosti sítí ani úplnou kontrolu všech kolizí.'}
(ROOT/'overeni-tvar-v5/tenke-plochy.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(f"{result['status']}: {models} modelů, {len(rows)} součástí; {result['thin_details_listed']} tenkých detailů zaznamenáno; {len(failures)} nulových nebo téměř nulových ploch.")
sys.exit(bool(failures))
