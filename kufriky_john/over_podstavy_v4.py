"""Kontrola každé skutečné spodní součásti GLB; bez DB a bez sítě.

Obrys se čte ze spodní styčné roviny skutečného dna, ne z obálky kufru.
Součásti mají ve v4 nulový dovolený přesah. Ověřuje se každý vrchol,
střed, výška, opora a symetrie patek i spojovacích pozic.
"""
from pathlib import Path
import argparse
import json
import re
import sys
import numpy as np
from over_realne_tvary import inspect, ray_hits
from over_doladeni_v3 import contact

ROOT = Path(__file__).resolve().parent
FLOORS = ('telo-dno', 'skrin-dno', 'prepravka-dno', 'pojezdove-telo-dno',
          'vyklopny-organizer-zadni-panel')
SUPPORT = re.compile(r'^(patka-|pojezdova-patka-|PACKOUT-spodni-(patka|zub)-)')


def hull(points):
    points = sorted(set(map(tuple, points)))
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    halves = []
    for seq in (points, points[::-1]):
        side = []
        for p in seq:
            while len(side) > 1 and cross(side[-2], side[-1], p) <= 1e-8:
                side.pop()
            side.append(p)
        halves.append(side[:-1])
    contour = np.array(halves[0]+halves[1], dtype=float)
    if len(contour) < 3:
        raise ValueError('Chybí skutečný obrys styčné plochy dna')
    return contour


def outside_mm(points, contour):
    edge = np.roll(contour, -1, axis=0)-contour
    delta = points[:, None, :]-contour[None, :, :]
    signed = (edge[None, :, 0]*delta[:, :, 1]-edge[None, :, 1]*delta[:, :, 0])/np.linalg.norm(edge, axis=1)
    return np.maximum(0, -signed.min(axis=1))


def audit(file, sku):
    doc, parts, measured = inspect(file)
    floor = next((p for p in parts if p['name'] in FLOORS), None)
    if floor is None:
        raise ValueError(sku+' nemá identifikovatelné dno')
    lo, hi = floor['vertices'].min(0), floor['vertices'].max(0)
    bottom = floor['vertices'][np.abs(floor['vertices'][:, 2]-lo[2]) < .001]
    contour = hull(bottom[:, :2])
    rows, failures, pads, shoes = [], [], [], []
    for part in parts:
        if not SUPPORT.match(part['name']):
            continue
        a, b = part['vertices'].min(0), part['vertices'].max(0)
        center = (a+b)/2
        # ALL projected vertices, not the nominal mesh origin or 4 box corners.
        outside = outside_mm(part['vertices'][:, :2], contour)
        center_out = float(outside_mm(center[None, :2], contour)[0])
        bbox_out = float(max(0, *(lo[:2]-a[:2]), *(b[:2]-hi[:2])))
        is_pad = bool(re.match(r'^(patka-|pojezdova-patka-)', part['name']))
        if is_pad:
            pads.append(center[:2])
        elif part['name'].startswith('PACKOUT-spodni-patka-'):
            shoes.append(center[:2])
        witnesses = []
        # Top cap samples are actual triangle centroids. Every ground foot must
        # meet its own bottom panel, not merely another unrelated component.
        caps = part['faces'][np.all(np.abs(part['faces'][:, :, 2]-b[2]) < .001, axis=1)]
        if len(caps) == 0:
            raise ValueError(sku+' '+part['name']+' nemá horní styčnou plochu')
        gap = max(0., float(lo[2]-b[2]))
        for point in caps.mean(1)[::max(1, len(caps)//8)]:
            start = point.copy()
            start[2] = a[2]-.1
            hits = ray_hits(floor['faces'], start, [0, 0, 1])
            if len(hits):
                z = float(start[2]+hits[0])
                if a[2]-.001 <= z <= b[2]+.001:
                    witnesses.append({'point_xy_mm': point[:2].tolist(), 'floor_surface_z_mm': z})
        # A docking hook joins its matching shoe; it does not itself reach the
        # floor. Verify that exact parent mesh, then verify the shoe separately.
        is_hook = part['name'].startswith('PACKOUT-spodni-zub-')
        support_name = floor['name']
        if is_hook:
            support_name = part['name'].replace('spodni-zub-', 'spodni-patka-')
            parent = next((p for p in parts if p['name'] == support_name), None)
            if parent is None:
                raise ValueError(sku+' '+part['name']+' nemá odpovídající spojovací patku')
            witness = contact(part, parent)
            witnesses = [{'parent': support_name, **witness}] if witness else []
        top_gap = abs(float(b[2]-lo[2])) if is_pad else 0. if is_hook else gap
        row = {'sku': sku, 'part': part['name'], 'kind': 'ground_pad' if is_pad else 'docking',
               'support': support_name, 'floor': floor['name'], 'min_mm': a.tolist(), 'max_mm': b.tolist(),
               'center_mm': center.tolist(), 'vertices_measured': len(part['vertices']),
               'bbox_overhang_mm': bbox_out, 'contour_overhang_mm': float(outside.max()),
               'center_overhang_mm': center_out, 'vertical_gap_mm': top_gap,
               'floor_contact_witnesses': witnesses, 'allowed_overhang_mm': 0}
        rows.append(row)
        if float(outside.max()) > .01 or center_out > .01 or bbox_out > .01:
            failures.append(part['name']+' mimo skutečné dno')
        if top_gap > .01 or not witnesses:
            failures.append(part['name']+' bez ověřené opory na dně')
        if a[2] < measured['min_mm'][2]-.01 or b[2] > hi[2]+.01:
            failures.append(part['name']+' mimo spodní oblast těla')
    if len(rows) < 12:
        raise ValueError(sku+' nebyly změřeny všechny spodní komponenty')
    symmetry = []
    for kind, centers in [('patky', pads), ('spojovací patky', shoes)]:
        if not centers:
            if kind == 'patky' and sku in ('4932471724', '4932498651'):
                reason = ('Otevřená přepravka má přímo spodní spojovací patky; nemá samostatné čtyři nožky.'
                          if sku == '4932471724' else
                          'Pojízdná zásuvka má kola a spodní spojovací patky; nemá samostatné čtyři rohové nožky.')
                symmetry.append({'kind': kind, 'excluded': reason})
                continue
            raise ValueError(sku+' chybí '+kind)
        centers = np.array(centers)
        origin = (lo[:2]+hi[:2])/2
        for axis in (0, 1):
            mirrored = centers.copy()
            mirrored[:, axis] = 2*origin[axis]-mirrored[:, axis]
            errors = np.linalg.norm(mirrored[:, None, :]-centers[None, :, :], axis=2).min(axis=1)
            symmetry.append({'kind': kind, 'axis': 'XY'[axis], 'pairs_measured': len(centers),
                             'max_center_error_mm': float(errors.max())})
            if errors.max() > .01:
                failures.append(kind+' nejsou souměrné vůči skutečnému dnu na ose '+'XY'[axis])
    return {'sku': sku, 'file': file.name, 'actual_model': measured,
            'floor': {'part': floor['name'], 'min_mm': lo.tolist(), 'max_mm': hi.tolist(),
                      'contact_contour_xy_mm': contour.tolist()},
            'supports_measured': len(rows), 'support_vertices_measured': sum(x['vertices_measured'] for x in rows),
            'rows': rows, 'symmetry': symmetry, 'failures': failures}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--sku', default='')
    args = parser.parse_args()
    cat = json.loads((ROOT/'zdroje/doladeni-v4/pred-kufriky.json').read_text())
    order = [next(r for r in cat['records'] if r['id'] == ident) for ident in cat['model_order']]
    rows = []
    for record in order:
        for sku in record['sku']:
            if args.sku and sku not in args.sku.split(','):
                continue
            file = ROOT/('modely-v3' if args.baseline else 'modely')/(sku+'.glb')
            rows.append(audit(file, sku))
    if not rows:
        raise ValueError('Nula změřených modelů')
    failed = [r['sku'] for r in rows if r['failures']]
    result = {'status': 'BASELINE_WITH_FINDINGS' if args.baseline else 'FAIL' if failed else 'PASS',
              'models_measured': len(rows), 'supports_measured': sum(r['supports_measured'] for r in rows),
              'support_vertices_measured': sum(r['support_vertices_measured'] for r in rows),
              'models_with_findings': failed, 'rows': rows,
              'scope': 'Každý spodní díl: všechny vrcholy vůči obrysu skutečné spodní plochy dna, střed, vertikální dosed a zrcadlová symetrie. Dovolený přesah 0 mm; číselná tolerance 0,01 mm.',
              'limitations': 'Neověřuje skutečné rozměry nekótovaných spojovacích profilů ani fyzickou stohovací kompatibilitu.'}
    name = 'podstavy-pred.json' if args.baseline else 'podstavy-prvni-tri.json' if args.sku else 'podstavy.json'
    (ROOT/'overeni-tvar-v4'/name).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(result['status']+f": {len(rows)} modelů, {result['supports_measured']} spodních dílů, {result['support_vertices_measured']} vrcholů; modelů s nálezem: {len(failed)}.")
    if not args.baseline and failed:
        for r in rows:
            if r['failures']:
                print(r['sku'], r['failures'])
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
