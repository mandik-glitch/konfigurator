#!/opt/konfigurator/api/venv/bin/python
"""PREJIMKA systemu 35 v generatoru stolu (bot10, 2026-10-05): `sestav_stul(system=35, sirka=1200, panely=False)` musi dat tytez dily jako moje odvozena sablona
(scripts/2026-10-05_system35/vystup/stul_sablona_system35.json, odvod_sablony_35.py) BEZ panelovych dilu; system 30 (sirka 1200, bez panelu) musi dat zmrazenou sablonu #577 bez nich (kontrola,
ze test dobre paruje dily); vychozi stul 35 (sirka 1280, 1 vsazeny panel) je bez problemu a ma 1 panel (min. sirka 1262 = 1190 + 2 + 2 x 35).
Parovani dilu: podle part_id a nejblizsi polohy. Meze: poloha 0,05 mm, mereni 1e-4, otoceni 0,05 st.
  api/venv/bin/python -B scripts/2026-10-05_system35/test_prejimka_system35.py [--jen35]"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'api')); sys.path.insert(0, os.path.join(REPO, 'scripts', '2026-10-04_system40')); sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import stul_konfigurator as S
from _spolecne import tmpl

TOL_POS, TOL_SC, TOL_ANG = 0.05, 1e-4, 0.05
# bot8 2026-10-05: panely jsou od ted VSAZENE do profilu mezi zadni stojky (vychozi stul = sirka 1280, 1 panel), takze vychozi stul uz neni sablona. Sablona ZUSTAVA zlatym vzorem pro stul BEZ panelu
# o sirce sablony (1200): srovnava se se sablonou bez panelovych dilu (profil pod panely #14, panely #23/#24, elektrozlab #22, jejich dve spojky #42/#45; indexy shodne ve 30 i v odvozene 40).
PANELOVE = {14, 22, 23, 24, 42, 45}
def bez_panelu(parts): return [p for i, p in enumerate(parts) if i not in PANELOVE]

def pos_of(d): return np.array(d.get('position', d.get('pos')), float)
def ang(q1, q2):
    a = np.array(q1, float); b = np.array(q2, float); a /= np.linalg.norm(a); b /= np.linalg.norm(b)
    return float(np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(a, b)))))))

def porovnej(dily, sab, nazev):
    out = {'ok': True, 'zprava': []}
    ids = sorted({p['part_id'] for p in sab})
    gen_ids = sorted({d['part_id'] for d in dily})
    if ids != gen_ids:
        out['ok'] = False; out['zprava'].append('jine druhy dilu: sablona %s, generator %s' % (ids, gen_ids)); return out
    if len(dily) != len(sab):
        out['ok'] = False; out['zprava'].append('pocet dilu: sablona %d, generator %d' % (len(sab), len(dily)))
    worst = {'pos': 0.0, 'sc': 0.0, 'ang': 0.0}; used = set(); bad = []
    for pid in ids:
        S_idx = [i for i, p in enumerate(sab) if p['part_id'] == pid]; G_idx = [i for i, d in enumerate(dily) if d['part_id'] == pid]
        if len(S_idx) != len(G_idx):
            out['ok'] = False; out['zprava'].append('%s: sablona %d ks, generator %d ks' % (pid, len(S_idx), len(G_idx))); continue
        free = list(G_idx)
        for i in S_idx:
            ps = np.array(sab[i]['position'], float)
            j = min(free, key=lambda g: np.linalg.norm(pos_of(dily[g]) - ps)); free.remove(j)
            dp = float(np.linalg.norm(pos_of(dily[j]) - ps)); dsc = float(np.max(np.abs(np.array(dily[j]['scale'], float) - np.array(sab[i]['scale'], float)))); da = ang(dily[j]['quaternion'], sab[i]['quaternion'])
            worst['pos'] = max(worst['pos'], dp); worst['sc'] = max(worst['sc'], dsc); worst['ang'] = max(worst['ang'], da)
            if dp > TOL_POS or dsc > TOL_SC or da > TOL_ANG: bad.append((pid, i, round(dp, 3), round(dsc, 6), round(da, 3)))
    out['worst'] = worst
    if bad: out['ok'] = False; out['zprava'].append('mimo toleranci (part_id, index sablony, dpos mm, dscale, dangle st.): %s' % bad[:8] + (' ...' if len(bad) > 8 else ''))
    return out

def main():
    ok = True
    def chk(nazev, cond, det=''):
        nonlocal ok; print(('OK   ' if cond else 'FAIL ') + nazev + ('  ' + str(det) if det != '' else '')); ok &= bool(cond)
    if '--jen35' not in sys.argv:
        r30 = S.sestav_stul(sirka=1200, panely=False)
        c = porovnej(r30['dily'], bez_panelu(tmpl()['parts']), '30')
        chk('system 30 (sirka 1200, bez panelu) = zmrazena sablona #577 bez panelovych dilu (zlaty test, kontrola parovani dilu)', c['ok'], c.get('zprava') or c.get('worst'))
        chk('system 30: vychozi stul (1280, 1 vsazeny panel) bez problemu', not S.sestav_stul().get('problemy'), S.sestav_stul().get('problemy'))
    try:
        r35 = S.sestav_stul(system=35, sirka=1200, panely=False)
    except (TypeError, S.StulChyba) as e:
        print('FAIL parametr system 35 neni implementovan:', e); return 3
    d35 = json.load(open(os.path.join(HERE, 'vystup', 'stul_sablona_system35.json'), encoding='utf-8'))['parts']
    c = porovnej(r35['dily'], bez_panelu(d35), '35')
    chk('system 35 (sirka 1200, bez panelu) = moje odvozena sablona bez panelovych dilu (poloha <= 0,05 mm, mereni, otoceni)', c['ok'], c.get('zprava') or c.get('worst'))
    chk('system 35: zadne problemy napojeni (r["problemy"] prazdne)', not r35.get('problemy'), r35.get('problemy'))
    r35v = S.sestav_stul(system=35)
    chk('system 35: vychozi stul (1280, 1 vsazeny panel) bez problemu', not r35v.get('problemy'), r35v.get('problemy'))
    chk('system 35: vychozi stul ma 1 panel (min. sirka 1262 = 1190 + 2 + 2 x 35) a 2 profily nad/pod nim', sum(1 for d in r35v['dily'] if d['part_id'] == S.PANEL_PART) == 1 and r35v['panely_info']['min_sirka'] == 1262, r35v['panely_info'])
    print('VSE OK' if ok else 'NEKTERA KONTROLA SELHALA')
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
