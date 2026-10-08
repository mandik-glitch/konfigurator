import sys, json, math, importlib.util, time
sys.path.insert(0, '/opt/konfigurator/scripts')
from _env import get_conn
import razitkovac as NEW
spec = importlib.util.spec_from_file_location("razitkovac_head", "" + (sys.argv[1] if len(sys.argv) > 1 else "/tmp/razitkovac_puvodni.py") + "")
OLD = importlib.util.module_from_spec(spec); spec.loader.exec_module(OLD)
KAT = "/opt/konfigurator/webapp/katalog"
c = get_conn(); cur = c.cursor()
rozmery = NEW.rozmery_z_katalogu(cur, KAT)
cur.execute("SELECT id, data FROM product_assemblies WHERE data LIKE '%%logo-ochrana-logo-%%' ORDER BY id")
rows = cur.fetchall()
PROF = {"Object_7", "Object_8", "Object_9"}
def rot(q, v): return NEW._rotuj(q, v)
def porusi(ciste, razitka):
    prof = [p for p in ciste if p.get("part_id") in PROF]
    skup = {}
    nezarazeno = 0
    for lg in razitka:
        if lg.get("part_id") != NEW.LOGO_PART_ID: continue
        P = lg["position"]; host = None
        for i, p in enumerate(prof):
            a = NEW._norm(rot(p.get("quaternion") or [0,0,0,1], (0.0,1.0,0.0)))
            cc = p.get("position") or [0,0,0]
            d = [P[k]-cc[k] for k in range(3)]
            al = sum(d[k]*a[k] for k in range(3))
            perp = math.sqrt(max(0.0, sum(x*x for x in d) - al*al))
            if abs(perp - (NEW.PROFIL_POLOMER_MM + NEW.LOGO_ODSAZENI_PIVOTU_MM)) < 0.5 and abs(al) <= NEW._delka_profilu(p)/2 + 1:
                host = i; break
        if host is None: nezarazeno += 1; continue
        skup.setdefault(host, []).append(al)
    v = 0; minmez = None
    for ts in skup.values():
        ts.sort()
        for i in range(len(ts)):
            for j in range(i+1, len(ts)):
                mez = abs(ts[j]-ts[i]) - NEW.LOGO_DELKA_MM
                minmez = mez if minmez is None else min(minmez, mez)
                if mez < NEW.MIN_ROZESTUP_LOG_MM - 1e-6: v += 1
    return v, sum(1 for r in razitka if r.get("part_id")==NEW.LOGO_PART_ID), nezarazeno, minmez
t0 = time.time(); tot = {"old_v":0,"new_v":0,"old_n":0,"new_n":0,"sestav":0,"old_s_por":0,"nez":0,"chyby":0}
new_minmez = None; ukazky = []
for r in rows:
    d = json.loads(r["data"]); parts = d.get("parts") or []
    ciste = [p for p in parts if not NEW.je_razitko(p.get("role"))]
    o, eo = OLD.orazitkuj_data_sestavy(ciste, r["id"], KAT, rozmery=rozmery)
    n, en = NEW.orazitkuj_data_sestavy(ciste, r["id"], KAT, rozmery=rozmery)
    if eo or en: tot["chyby"] += 1; continue
    ov, on, onz, _ = porusi(ciste, o); nv, nn, nnz, nm = porusi(ciste, n)
    tot["sestav"] += 1; tot["old_v"] += ov; tot["new_v"] += nv; tot["old_n"] += on; tot["new_n"] += nn; tot["nez"] += onz + nnz
    if ov: tot["old_s_por"] += 1
    if nm is not None: new_minmez = nm if new_minmez is None else min(new_minmez, nm)
    if ov and len(ukazky) < 5: ukazky.append((r["id"], ov, on, nn))
    if any("_t" in x for x in n): tot["chyby"] += 1
print("sestav s razitky:", len(rows), "| zpracovano:", tot["sestav"], "| chyby orientace/_t:", tot["chyby"])
print("STARY kod: log", tot["old_n"], "| paru log < 500 mm na tem.profilu:", tot["old_v"], "| sestav s porusenim:", tot["old_s_por"])
print("NOVY kod:  log", tot["new_n"], "| paru log < 500 mm na tem.profilu:", tot["new_v"], "| nejmensi mezera mezi logy na temz profilu:", new_minmez)
print("loga, u kterych se nenasel hostitelsky profil (kontrola mereni):", tot["nez"])
print("ukazky (id, poruseni_stare, loga_stare, loga_nove):", ukazky)
print("sekund", round(time.time()-t0,1))
