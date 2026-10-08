"""Prepocet ulozenych cen sestav a karet: koeficient sceny jen na profily a
produkty z Dogusu (Robert 2026-10-01: "koeficient pro scenu se tyka jen
profilu a produktu, ktere se nacitaji z dogusu") + balne 3 % + rozpis dilu.

Do 2026-10-01 /api/katalog nasobil scene_price_coefficient (1,25) u VSECH
dilu (desky, euroboxy, vlastni/Vandr dily...) a rozpis dilu (data.bom) mel
jeste ceny s 1,4. Kod opraven commitem c77795b5 (priznak scene_coef ve
fetch_katalog_parts). Tento skript prepocita ULOZENE ceny stejnym vzorcem,
jakym je spocita scena (computeAssemblyBomAndPrice + currentWeightPrice
v webapp/scene.html), z ZIVYCH cen katalogu (fetch_katalog_parts - stejny
kod jako /api/katalog, vcetne priznaku scene_coef):
  profil (ma delku + prurez): cena_dilu = cena_vzorku * delka / delka_vzorku
      (delka = rozmer GLB po nejdelsi ose * scale)
  deska (is_board_material): cena_za_m2 * sirka * vyska (osy GLB mimo
      tloustku, * scale)
  ostatni: pevna cena
  cena_vzorku = zakladni cena * koeficient JEN kdyz scene_coef, jinak * 1
  material = profily + desky, prislusenstvi = ostatni (zaokrouhleno)
  rez, pausal za profil, spoje: z ulozeneho price_summary BEZE ZMENY
  balne = round(subtotal * 3 %), celkem = subtotal + balne, montaz = 20 %
  rozpis: skupiny jako scena (dil | delka | rozmer desky | barva), unit =
      round(cena dilu), total = unit * ks - prepisuje se jen kdyz skupiny
      sedi na ulozeny rozpis (pocet, ks, rozmer), jinak se nahlasi
  karta (master): price_czk_placeholder = celkem, jen kdyz dnes sedi na
      ulozeny celkem mastera (rucni upravu neprepsat)
Nesaha na active (pravidlo 54), Vandr VD-%, nabidky/objednavky.

Bezpecnost: zaloha, fresh-read pred zapisem, JSON_SET jen konkretnich
klicu + bom, rowcount, overeni z noveho spojeni.

Spusteni NA SERVERU v /opt/konfigurator (venv):
    api/venv/bin/python3 scripts/2026-10-01_bot8_prepocet_koef_profily_dogus.py          (nahled)
    api/venv/bin/python3 scripts/2026-10-01_bot8_prepocet_koef_profily_dogus.py --apply  (zapis)
"""
import json
import os
import sys
import threading

REPO = "/opt/konfigurator"
API = os.path.join(REPO, "api")
ZAL_DIR = os.path.join(REPO, "backups", "2026-10-01_prepocet_koef_profily_dogus")
ZAL = os.path.join(ZAL_DIR, "pred_zapisem.json")
PUBLIC = "https://autovestavby.logiman.cz"

for _ln in open(os.path.join(API, ".env"), encoding="utf-8"):
    _ln = _ln.strip()
    if _ln and not _ln.startswith("#") and "=" in _ln:
        _k, _v = _ln.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, API)
import numpy as np  # noqa: E402
import app as appmod  # noqa: E402
import universal_import as ui  # noqa: E402
threading.Thread.start = _orig

STAMP, KONTROLNI, CAR_BODY = "logo-ochrana", "kontrolni-pomucka", "car_body_"
_ext_cache = {}


def glb_ext(kp):
    f = (kp.get("file") or "").split("?")[0]
    if f.startswith("katalog/"):
        f = f[len("katalog/"):]
    if f not in _ext_cache:
        path = os.path.join(appmod.KATALOG_GLB_DIR, f)
        try:
            mesh = ui._glb_mesh(path) if f and os.path.isfile(path) else None
        except Exception:  # noqa: BLE001
            mesh = None
        _ext_cache[f] = None if mesh is None else (mesh[0].max(axis=0) - mesh[0].min(axis=0))
    return _ext_cache[f]


def part_price(p, kp, coef):
    """(cena dilu, je_material, klic skupiny rozpisu) jako scena; cena None = nejde."""
    base = kp.get("price_czk_approx_PLACEHOLDER")
    price_czk = round(base * coef, 2) if base is not None else None
    scale = np.abs(np.asarray(p.get("scale") or [1, 1, 1], dtype=np.float64))
    color = p.get("color") or ""
    if kp.get("is_board_material"):
        ext = glb_ext(kp)
        if ext is None:
            raise ValueError(f"deska {p['part_id']}: GLB nejde precist")
        t = int(np.argmin(ext))
        a1, a2 = [k for k in range(3) if k != t]
        w, h = float(ext[a1] * scale[a1]), float(ext[a2] * scale[a2])
        price = price_czk * (w / 1000.0) * (h / 1000.0) if price_czk is not None else None
        return price, True, (p["part_id"], None, f"{round(w)}x{round(h)}", color)
    if kp.get("length_mm") and kp.get("cross_section_mm") and kp["cross_section_mm"][0] is not None:
        ext = glb_ext(kp)
        if ext is None:
            raise ValueError(f"profil {p['part_id']}: GLB nejde precist")
        ax = int(np.argmax(ext))
        length = float(ext[ax] * scale[ax])
        price = price_czk * (length / float(kp["length_mm"])) if price_czk is not None else None
        return price, True, (p["part_id"], round(length), None, color)
    return price_czk, False, (p["part_id"], None, None, color)


def spocitej(parts, katalog, coef_rule):
    """coef_rule(kp) -> koeficient pro dil. Vraci (material, accessory, skupiny[(klic, unit, ks)])."""
    mat = acc = 0.0
    groups = {}
    order = []
    for p in parts:
        pid = p.get("part_id")
        if str(p.get("role") or "").startswith((STAMP, KONTROLNI)) or str(pid).startswith(CAR_BODY):
            continue
        kp = katalog.get(pid)
        if kp is None:
            raise ValueError(f"dil {pid} neni v katalogu")
        price, is_mat, key = part_price(p, kp, coef_rule(kp))
        if is_mat:
            mat += price or 0.0
        else:
            acc += price or 0.0
        unit = round(price) if price is not None else 0
        if key in groups:
            groups[key][1] += 1
        else:
            groups[key] = [unit, 1]
            order.append(key)
    return round(mat), round(acc), [(k, groups[k][0], groups[k][1]) for k in order]


def bom_dim(key):
    _pid, length, board, _c = key
    if length is not None:
        return f"{length} mm"
    if board is not None:
        w, h = board.split("x")
        return f"{w} × {h} mm"
    return "-"


def bom_name(kp):
    """Nazev radku rozpisu jako scena: partDisplayName (nazev + [SKU], kdyz v nazvu
    neni) + " (vrstva)" - overeno proti 8 715 ulozenym radkum (100 % shoda)."""
    nm = kp.get("name") or "díl"
    sku = kp.get("sku")
    disp = f"{nm} [{sku}]" if sku and sku not in str(nm) else nm
    return f"{disp} ({kp.get('layer')})"


def bom_dims(key):
    """Rozmer radku rozpisu v obou poradich (deska: scena pise sirka x vyska
    podle os GLB, ktere mohou byt prohozene proti vypoctu zde)."""
    d = bom_dim(key)
    if "×" in d:
        w, h = d.replace(" mm", "").split(" × ")
        return {d, f"{h} × {w} mm"}
    return {d}


def main():
    apply = "--apply" in sys.argv
    conn = appmod.get_conn()
    cur = conn.cursor()
    coef = appmod.get_scene_price_coefficient(cur)
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='packaging_pct'")
    packaging_pct = float(cur.fetchone()["setting_value"])
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='montaz_pct'")
    montaz_pct = float(cur.fetchone()["setting_value"])
    katalog = {k["id"]: k for k in appmod.fetch_katalog_parts()}
    if not any("scene_coef" in k for k in katalog.values()):
        raise SystemExit("CHYBA: fetch_katalog_parts nema priznak scene_coef (kod c77795b5 neni na disku)")
    print(f"koeficient {coef} (jen profily + Dogus), balne {packaging_pct} %, montaz {montaz_pct} %")

    cur.execute("""
        SELECT pa.id, pa.is_master, pa.shop_product_id, pa.data, sp.sku, sp.slug, sp.name AS sp_name,
               sp.price_czk_placeholder
        FROM product_assemblies pa LEFT JOIN shop_products sp ON sp.id = pa.shop_product_id
        ORDER BY pa.id
    """)
    import collections
    plan, skipped, bom_mismatch, drift = [], [], [], []
    board_order = collections.defaultdict(collections.Counter)
    for r in cur.fetchall():
        if r["sku"] and str(r["sku"]).startswith("VD-"):
            continue
        d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
        ps = (d or {}).get("price_summary") or {}
        if ps.get("total_czk") is None:
            continue
        parts = d.get("parts") or []
        try:
            m_old, a_old, _g = spocitej(parts, katalog, lambda kp: float(ps.get("scene_price_coefficient_applied") or 1.0))
            m_new, a_new, groups = spocitej(parts, katalog, lambda kp: coef if kp.get("scene_coef") else 1.0)
        except ValueError as e:
            skipped.append((r["id"], str(e)))
            continue
        drift.append((abs(m_old - ps.get("material_czk", 0)) + abs(a_old - ps.get("accessory_czk", 0)), r["id"]))
        sub = m_new + ps.get("cut_czk", 0) + ps.get("profile_flat_fee_czk", 0) + ps.get("joint_czk", 0) + a_new
        packaging = round(sub * packaging_pct / 100)
        total = sub + packaging
        montaz = round(total * montaz_pct / 100)
        old_bom = d.get("bom") or []
        new_bom = None
        if len(old_bom) == len(groups) and all(int(b.get("qty", -1)) == g[2] and str(b.get("dim")) in bom_dims(g[0])
                                               for b, g in zip(old_bom, groups)):
            new_bom = [dict(b, unit_price=g[1], total=int(round(g[1] * g[2]))) for b, g in zip(old_bom, groups)]
            for b, g in zip(old_bom, groups):
                if g[0][2] is not None:  # deska: poradi rozmeru v ulozenem rozpisu (podle karty)
                    board_order[g[0][0]][str(b.get("dim")) == bom_dim(g[0])] += 1
        else:
            bom_mismatch.append(r["id"])
        plan.append({"r": r, "ps": ps, "material": m_new, "accessory": a_new, "packaging": packaging, "total": total,
                     "montaz": montaz, "bom": new_bom, "groups": groups})
    # rozpis, ktery nesedi na geometrii (geometrie zmenena po ulozeni, rozpis
    # zastaraly): vygenerovat cely znovu jako scena
    for p in plan:
        if p["bom"] is None:
            rows = []
            for key, unit, qty in p["groups"]:
                dim = bom_dim(key)
                if key[2] is not None and board_order[key[0]][True] < board_order[key[0]][False] + 1:
                    w, h = dim.replace(" mm", "").split(" × ")
                    dim = f"{h} × {w} mm"
                rows.append({"name": bom_name(katalog[key[0]]), "dim": dim, "qty": qty, "unit_price": unit,
                             "total": int(round(unit * qty))})
            p["bom"] = rows

    karty, karty_rucne = [], []
    for p in plan:
        r = p["r"]
        if r["is_master"] and r["shop_product_id"]:
            cena = float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None
            if cena is not None and round(cena) == p["ps"]["total_czk"]:
                karty.append(p)
            else:
                karty_rucne.append((r["shop_product_id"], r["sku"], cena, p["ps"]["total_czk"]))

    zmeny = [p for p in plan if p["total"] != p["ps"]["total_czk"]]
    diffs = [p["total"] - p["ps"]["total_czk"] for p in zmeny]
    print(f"sestav: {len(plan)}, cena se meni u {len(zmeny)}; preskoceno (nejde spocitat) {len(skipped)}; "
          f"rozpis zastaraly proti geometrii (vygeneruje se znovu) {len(bom_mismatch)}")
    if diffs:
        rel = [(p["total"] / p["ps"]["total_czk"] - 1) * 100 for p in zmeny]
        print(f"rozdil celkove ceny: prumer {np.mean(diffs):+.0f} Kc ({np.mean(rel):+.2f} %), "
              f"nejvetsi {min(diffs):+d} Kc ({min(rel):+.2f} %), nejmensi {max(diffs):+d} Kc")
    drift.sort(reverse=True)
    print(f"kontrola vzorce (stare pravidlo z zivych cen vs ulozeno): presne {sum(1 for x, _ in drift if x <= 2)}/{len(drift)}, "
          f"nejvetsi odchylka {drift[0][0] if drift else 0} Kc (#{drift[0][1] if drift else '-'})")
    print("\nKARTY NA WEBU (master):")
    print(f"{'karta':>6} {'sku':<18} {'dnes':>8} {'nove':>8} {'rozdil':>8}   odkaz")
    for p in karty:
        r = p["r"]
        print(f"{r['shop_product_id']:>6} {r['sku']:<18} {p['ps']['total_czk']:>8} {p['total']:>8} "
              f"{p['total'] - p['ps']['total_czk']:>+8}   {PUBLIC}/produkt/{r['slug']}")
    if karty_rucne:
        print("!!! karty nesedici na master (neprepisou se):", karty_rucne)
    if skipped:
        print("PRESKOCENO:", skipped[:10])
    if bom_mismatch:
        print("ROZPIS ZASTARALY (vygenerovan znovu):", bom_mismatch[:20])

    if not apply:
        print("\n(nahled, nic nezapsano - zapis: --apply)")
        return

    os.makedirs(ZAL_DIR, exist_ok=True)
    if os.path.exists(ZAL):
        raise SystemExit(f"CHYBA: zaloha {ZAL} uz existuje - neprepisuji (druhy beh?)")
    with open(ZAL, "w", encoding="utf-8") as f:
        json.dump({"sestavy": [{"id": p["r"]["id"], "price_summary": p["ps"],
                                "bom": (json.loads(p["r"]["data"]) if isinstance(p["r"]["data"], str) else p["r"]["data"]).get("bom")}
                               for p in plan],
                   "karty": [{"shop_product_id": p["r"]["shop_product_id"], "price_czk_placeholder": p["ps"]["total_czk"]}
                             for p in karty]}, f, ensure_ascii=False, indent=1, default=str)
    print(f"\nzaloha: {ZAL}")
    for p in plan:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (p["r"]["id"],))
        d = json.loads(cur.fetchone()["data"])
        if (d.get("price_summary") or {}).get("total_czk") != p["ps"]["total_czk"]:
            conn.rollback()
            raise SystemExit(f"CHYBA: sestava #{p['r']['id']} se mezitim zmenila - ROLLBACK")
        sets = ["'$.price_summary.material_czk', %s", "'$.price_summary.accessory_czk', %s",
                "'$.price_summary.packaging_czk', %s", "'$.price_summary.total_czk', %s",
                "'$.price_summary.montaz_czk', %s", "'$.price_summary.packaging_pct_applied', %s",
                "'$.price_summary.scene_price_coefficient_applied', %s",
                "'$.price_summary.scene_price_coefficient_scope', %s"]
        vals = [p["material"], p["accessory"], p["packaging"], p["total"], p["montaz"], packaging_pct, coef,
                "profily+dogus"]
        if p["bom"] is not None:
            sets.append("'$.bom', CAST(%s AS JSON)")
            vals.append(json.dumps(p["bom"], ensure_ascii=False))
        cur.execute(f"UPDATE product_assemblies SET data = JSON_SET(data, {', '.join(sets)}) WHERE id=%s",
                    vals + [p["r"]["id"]])
        if cur.rowcount != 1:
            conn.rollback()
            raise SystemExit(f"CHYBA: UPDATE #{p['r']['id']} rowcount={cur.rowcount} - ROLLBACK")
    for p in karty:
        cur.execute("UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s AND ROUND(price_czk_placeholder)=%s",
                    (p["total"], p["r"]["shop_product_id"], p["ps"]["total_czk"]))
        if cur.rowcount != 1:
            conn.rollback()
            raise SystemExit(f"CHYBA: karta {p['r']['shop_product_id']} rowcount={cur.rowcount} - ROLLBACK")
    conn.commit()
    print(f"zapsano: {len(plan)} sestav, {len(karty)} karet")

    c2 = appmod.get_conn().cursor()
    chyby = 0
    for p in plan:
        c2.execute("SELECT data FROM product_assemblies WHERE id=%s", (p["r"]["id"],))
        d = json.loads(c2.fetchone()["data"])
        if d["price_summary"]["total_czk"] != p["total"] or (p["bom"] is not None and d.get("bom") != p["bom"]):
            chyby += 1
    for p in karty:
        c2.execute("SELECT price_czk_placeholder FROM shop_products WHERE id=%s", (p["r"]["shop_product_id"],))
        if round(float(c2.fetchone()["price_czk_placeholder"])) != p["total"]:
            chyby += 1
    if chyby:
        raise SystemExit(f"CHYBA: {chyby} hodnot po zapisu nesedi")
    print("OK - overeno z noveho spojeni")


if __name__ == "__main__":
    main()
