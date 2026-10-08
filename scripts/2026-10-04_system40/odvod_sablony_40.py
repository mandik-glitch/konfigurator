#!/opt/konfigurator/api/venv/bin/python
"""Odvozeni sablony stolu pro SYSTEM 40 (profil SuperLight 40x40, scenovy dil Object_11) ze zmrazene sablony #577 (system 30, profil 30x30 Object_7).
bot10, 2026-10-04. Zadani Roberta: druhy generator stolu s profily 40x40, VNEJSI rozmery stolu stejne (nohy se posunou dovnitr o 5 mm), konce/okraje/rohy se
prepocitaji z 30 na 40; prepinani mezi systemy 30 a 40 jen pro zakladni konstrukci z profilu (dalsi prvky nebudou vzdy kompatibilni).

Pravidla odvozeni (kazde cislo se bere z NAMERENYCH souradnic sablony 30, nic se nepise "od oka"):
  * VNEJSI plochy noh (X predni/zadni, Z leva/prava) zustavaji -> osy noh a pricek v rovinach noh se posunou dovnitr o D = (40 - 30) / 2 = 5 mm;
  * NOSNE plochy zustavaji: horni plocha horniho ramu (pod deskou), horni plocha rámu police (pod policovou deskou), horni konce zadnich noh (na nich lezi ramena LED);
    cili osy ramu horni a police se snizi o D, osy ramen LED se zvysi o D (lezi na koncich noh);
  * konce profilu dosedaji na LICE sousednich profilu (puvodne +-15, nove +-20): pricky 30 -> 40: delka = rozteč os noh - 40;
  * prislusenstvi se drzi sveho dotykoveho lice (panely k zadnim nohám, kolecka k nohám, PET k noze, LED k ramenu LED, box pod rámy), pracovni deska a police
    se zkrati o D*2 (zadni hrana lezi na lici zadnich noh);
  * rohove spojky 3158 -> 3176: vnejsi plochy ramen spojky lezi na plochach profilu (rohova hrana spojky = pruseciky dvou licovych roviny, sirka spojky je vystredena na osy);
    poloha spojky se pocita z uzlu spoje (pruseciky os) a z mistnich souradnic rohu a stredu sirky obou spojek.
Vystup: scripts/2026-10-04_system40/vystup/stul_sablona_system40.json (stejny format jako api/stul_sablona_577.json), tabulka zmen a zprava o overeni.
"""
import json, os, sys, copy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _spolecne import load_glb, quat, world, tmpl, KAT

P0, P1 = 30.0, 40.0
DD = (P1 - P0) / 2.0
CON30, CON40 = 'product_3158', 'product_3176'
PROF30, PROF40 = 'Object_7', 'Object_11'
# mistni souradnice rohu a stredu sirky spojek (z rozboru GLB: vnejsi plocha desky A = rovina x=0, vnejsi plocha desky B = rovina y=ycorner, sirka po z)
Q30 = np.array([0.0, 0.86, 13.5])      # product_3158: rovina x=0 a y=0.86, sirka 27 (z 0..27)
Q40 = np.array([0.0, -37.0, 18.5])     # product_3176: rovina x=0 a y=-37, sirka 37 (z 0..37)


def close(a, b, tol=0.6):
    return abs(a - b) <= tol


def main():
    d = tmpl()
    parts = d['parts']
    new = copy.deepcopy(parts)
    prof = [i for i, p in enumerate(parts) if p['part_id'] == PROF30]
    con = [i for i, p in enumerate(parts) if p['part_id'] == CON30]
    V7 = load_glb(KAT + PROF30 + '.glb')[0]; V158 = load_glb(KAT + CON30 + '.glb')[0]

    def info(i):
        p = parts[i]; R = quat(p['quaternion']); ax = R @ np.array([0, 1, 0.]); k = int(np.argmax(np.abs(ax)))
        L = p['scale'][1] * 1000.0; c = np.array(p['position'], float)
        return {'k': k, 'c': c, 'L': L, 'lo': c[k] - L / 2, 'hi': c[k] + L / 2}
    M = {i: info(i) for i in prof}
    legs = [i for i in prof if M[i]['k'] == 1 and M[i]['lo'] < 150]           # vsechny svisle profily od podlahy
    xs = sorted({round(M[i]['c'][0], 2) for i in legs}); zs = sorted({round(M[i]['c'][2], 2) for i in legs})
    x_front, x_rear, z_left, z_right = xs[0], xs[-1], zs[0], zs[-1]
    nx = lambda x: x_front + DD if close(x, x_front) else (x_rear - DD if close(x, x_rear) else x)
    nz = lambda z: z_left + DD if close(z, z_left) else (z_right - DD if close(z, z_right) else z)
    y_top = {round(M[i]['c'][1], 1) for i in prof if M[i]['k'] != 1 and M[i]['c'][1] < 900 and M[i]['c'][1] > 700}       # osa horniho ramu
    y_shelf = {round(M[i]['c'][1], 1) for i in prof if M[i]['k'] != 1 and M[i]['c'][1] < 400}
    y_led = {round(M[i]['c'][1], 1) for i in prof if M[i]['k'] != 1 and M[i]['c'][1] > 1800}
    assert len(y_top) == 1 and len(y_shelf) == 1 and len(y_led) == 1, (y_top, y_shelf, y_led)
    y_top, y_shelf, y_led = y_top.pop(), y_shelf.pop(), y_led.pop()
    print('osy: nohy x %.2f / %.2f, z %.2f / %.2f; horni ram y %.1f, police %.1f, LED %.1f' % (x_front, x_rear, z_left, z_right, y_top, y_shelf, y_led))

    # ---- profily: nove osy a delky
    ny = lambda y: y - DD if (close(y, y_top, 1.0) or close(y, y_shelf, 1.0)) else (y + DD if close(y, y_led, 1.0) else y)
    front_lic = x_front + DD + P1 / 2.0          # zadni plocha predni nohy (nove)
    rear_lic = x_rear - DD - P1 / 2.0            # predni plocha zadni nohy (nove)
    left_in = z_left + DD + P1 / 2.0             # vnitrni plocha leve nohy
    right_in = z_right - DD - P1 / 2.0
    # rameno LED: predni konec zustava (delka ramene = parametr), pricka LED se posune dopredu
    led_arms = [i for i in prof if M[i]['k'] == 0 and close(M[i]['c'][1], y_led, 1.0)]
    led_cross = [i for i in prof if M[i]['k'] == 2 and close(M[i]['c'][1], y_led, 1.0)]
    assert len(led_arms) == 2 and len(led_cross) == 1
    arm_front = min(M[i]['lo'] for i in led_arms)                       # predni konec ramen (zustava)
    x_cross_new = arm_front - P1 / 2.0                                  # osa priceky LED
    outer_rear = x_rear + P0 / 2.0                                      # zadni vnejsi plocha zadnich noh (zustava)
    delta = {}
    for i in prof:
        m = M[i]; p = new[i]; c = m['c'].copy(); k = m['k']
        if k == 1:                                  # svisly profil: osa x,z; delka (spodek a horni konec) zustava
            c[0], c[2] = nx(c[0]), nz(c[2]); L = m['L']
        elif k == 0:                                # profil po hloubce (X)
            c[1] = ny(c[1]); c[2] = nz(c[2])
            if i in led_arms:
                lo, hi = arm_front, outer_rear
            else:
                lo, hi = front_lic, rear_lic
            c[0] = (lo + hi) / 2.0; L = hi - lo
        else:                                       # profil po sirce (Z)
            c[1] = ny(c[1])
            if i in led_cross:
                c[0] = x_cross_new; lo, hi = z_left - P0 / 2.0, z_right + P0 / 2.0     # zustava mezi vnejsimi plochami noh
            else:
                c[0] = nx(c[0]); lo, hi = left_in, right_in
            c[2] = (lo + hi) / 2.0; L = hi - lo
        p['part_id'] = PROF40; p['position'] = [float(v) for v in c]; p['scale'] = [1.0, L / 1000.0, 1.0]
        delta[i] = {'osa': 'XYZ'[k], 'stred_30': [round(float(v), 2) for v in m['c']], 'stred_40': [round(float(v), 2) for v in c], 'delka_30': round(m['L'], 2), 'delka_40': round(L, 2)}
    Mn = {}
    for i in prof:
        p = new[i]; R = quat(p['quaternion']); ax = R @ np.array([0, 1, 0.]); k = int(np.argmax(np.abs(ax))); c = np.array(p['position']); L = p['scale'][1] * 1000
        Mn[i] = {'k': k, 'c': c, 'L': L, 'lo': c[k] - L / 2, 'hi': c[k] + L / 2}

    # ---- rohove spojky
    def owners(c):
        return [i for i in prof if c in (parts[i].get('lic_peers') or [])]

    def node(Mx, a, b):
        ka, kb = Mx[a]['k'], Mx[b]['k']
        n = np.array(Mx[a]['c'], float); n[ka] = Mx[b]['c'][ka]; n[kb] = Mx[a]['c'][kb]
        return n
    conn_report = []
    for c in con:
        a, b = owners(c)
        p = parts[c]; R = quat(p['quaternion'])
        n30 = node(M, a, b); n40 = node(Mn, a, b)
        W30 = R @ Q30 + np.array(p['position'])                       # rohova hrana spojky ve stredu sirky (svet)
        off = W30 - n30
        # offset ma byt +-15 po dvou osach (licove plochy) a 0 po treti (sirka vystredena)
        sg = np.sign(off) * (np.abs(off) > 1.0)
        mag = np.abs(off)
        W40 = n40 + sg * np.where(mag > 1.0, P1 / 2.0, 0.0)
        pos40 = W40 - R @ Q40
        q = new[c]; q['part_id'] = CON40; q['position'] = [float(v) for v in pos40]
        conn_report.append({'spojka': c, 'vlastnici': [a, b], 'offset_rohu_od_uzlu_30': [round(float(v), 2) for v in off],
                            'pos_30': [round(float(v), 2) for v in p['position']], 'pos_40': [round(float(v), 2) for v in pos40],
                            'offset_pivotu_od_uzlu_30': [round(float(v), 2) for v in (np.array(p['position']) - n30)],
                            'offset_pivotu_od_uzlu_40': [round(float(v), 2) for v in (pos40 - n40)]})

    # ---- prislusenstvi
    def aabb(p, V):
        W = world(p, V); return W.min(0), W.max(0)
    cache = {}
    def geom(pid):
        if pid not in cache: cache[pid] = load_glb(KAT + pid + '.glb')[0]
        return cache[pid]
    acc = [i for i, p in enumerate(parts) if p['part_id'] not in (PROF30, CON30)]
    byid = {}
    for i in acc: byid.setdefault(parts[i]['part_id'], []).append(i)
    shifts = {}
    def shift(i, dx=0.0, dy=0.0, dz=0.0, why=''):
        q = new[i]; q['position'] = [q['position'][0] + dx, q['position'][1] + dy, q['position'][2] + dz]; shifts[i] = {'dx': dx, 'dy': dy, 'dz': dz, 'duvod': why}
    def retarget(i, lo_t, hi_t, why):
        p = parts[i]; V = geom(p['part_id']); R = quat(p['quaternion']); s = np.array(p['scale'], float)
        lo0, hi0 = aabb(p, V); lo_t = np.array(lo_t, float); hi_t = np.array(hi_t, float)
        nat_c = (V.min(0) + V.max(0)) / 2; nat_e = V.max(0) - V.min(0)
        s2 = s.copy()
        for kloc in range(3):
            col = R[:, kloc]; w = int(np.argmax(np.abs(col))); assert abs(abs(col[w]) - 1) < 1e-3, 'osa neni zarovnana'
            ext_t = hi_t[w] - lo_t[w]
            if abs(ext_t - (hi0[w] - lo0[w])) < 0.01:                # rozmer se nemeni: meritko zustane PRESNE (jinak sum 1,00004 u tloustky desky)
                s2[kloc] = s[kloc]
            else:
                s2[kloc] = ext_t / nat_e[kloc] if abs(ext_t) > 1e-9 else s[kloc]
        pos2 = (lo_t + hi_t) / 2.0 - R @ (s2 * nat_c)
        new[i]['scale'] = [float(v) for v in s2]; new[i]['position'] = [float(v) for v in pos2]
        shifts[i] = {'retarget': True, 'lo_30': [round(float(v), 2) for v in lo0], 'hi_30': [round(float(v), 2) for v in hi0], 'lo_40': [round(float(v), 2) for v in lo_t], 'hi_40': [round(float(v), 2) for v in hi_t], 'duvod': why}
    for pid, idxs in byid.items():
        for i in idxs:
            p = parts[i]; lo, hi = aabb(p, geom(pid))
            if pid == 'product_4933':                                # laminodeska: pracovni deska (nahore) a police
                hi2 = hi.copy(); lo2 = lo.copy()
                gap_rear = (x_rear - P0 / 2.0) - hi[0]                   # mezera zadni hrany k lici zadnich noh (0 u desky, 0,5 u police)
                hi2[0] = rear_lic - gap_rear
                if lo[1] > 700:  # pracovni deska: vnejsi rozmer zustava, zadni hrana na lici zadnich noh
                    pass
                lo2[2] = lo[2]; hi2[2] = hi[2]
                retarget(i, lo2, hi2, 'zadni hrana zustava na lici zadnich noh (delka -%.0f mm), predni hrana a sirka stejne' % (2 * DD))
            elif pid == 'product_4930':                                # supliky pod horni ram: drzi se spodku ramu (horni plocha ramu zustava, spodek -D*2)
                shift(i, 0, -2 * DD, 0, 'drzi se spodku ramu (osa ramu o %.0f niz, ram o %.0f silnejsi)' % (DD, 2 * DD))
            elif pid == 'product_4931':                                # perfopanely: lici zadnich noh
                shift(i, -2 * DD, 0, 0, 'lezi na lici zadnich noh (lico se posunulo o %.0f mm dopredu)' % (2 * DD))
            elif pid == 'product_4932':                                # elektrozlab: pripojen k panelu
                shift(i, -2 * DD, 0, 0, 'pripojeno k panelu')
            elif pid == 'product_4929':                                # LED: pod priceku LED
                shift(i, x_cross_new - 83.5 if False else (x_cross_new - parts[led_cross[0]]['position'][0]), 0, 0, 'drzi se pod pricku LED (jeji osa x se posunula)')
            elif pid == 'product_4928':                                # PET: lice a osa nohy
                shift(i, nx(x_front) - x_front, 0, 2 * DD, 'klip na vnitrni plose predni leve nohy (osa x +%.0f, vnitrni lico z +%.0f)' % (DD, 2 * DD))
            elif pid == 'product_4916':                                # kolecka: osa nohy
                c = np.array(p['position']); xc = (lo[0] + hi[0]) / 2; zc_leg = None
                # koleso nalezi k noze s nejblizsi osou
                best = min(legs, key=lambda L_: (M[L_]['c'][0] - xc) ** 2 + (M[L_]['c'][2] - (lo[2] + hi[2]) / 2) ** 2)
                shift(i, Mn[best]['c'][0] - M[best]['c'][0], 0, Mn[best]['c'][2] - M[best]['c'][2], 'kolecko drzi osu nohy %d' % best)
            else:
                shifts[i] = {'duvod': 'bez zmeny (neznamy dil)'}

    d40 = {'_popis': "ODVOZENA sablona stolu SYSTEM 40 (profil SuperLight 40x40, scenovy dil Object_11, rohova spojka 3176) ze zmrazene sablony #577 (system 30) skriptem scripts/2026-10-04_system40/odvod_sablony_40.py (bot10, 2026-10-04): vnejsi rozmery stejne (nohy dovnitr o 5 mm), konce/okraje/rohy prepocitane. NEMENIT rucne.",
           '_zdroj': 'odvozeno z custom_shapes#577 (api/stul_sablona_577.json)', '_vychozi': d.get('_vychozi'), 'parts': new}
    os.makedirs(os.path.join(HERE, 'vystup'), exist_ok=True)
    json.dump(d40, open(os.path.join(HERE, 'vystup', 'stul_sablona_system40.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    rep = {'D': DD, 'osy': {'x_front': x_front, 'x_rear': x_rear, 'z_left': z_left, 'z_right': z_right, 'y_top': y_top, 'y_shelf': y_shelf, 'y_led': y_led},
           'profily': delta, 'spojky': conn_report, 'prislusenstvi': shifts}
    json.dump(rep, open(os.path.join(HERE, 'vystup', 'zmeny_30_na_40.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    offs = sorted({tuple(abs(round(v, 1)) for v in r['offset_rohu_od_uzlu_30']) for r in conn_report})
    print('offsety rohu spojky od uzlu (30), abs:', offs)
    print('zapsano vystup/stul_sablona_system40.json a vystup/zmeny_30_na_40.json')


if __name__ == '__main__':
    main()
