"""Prehled postupu vyroby sestav (bot10, zadani bot3 koordinace 2026-09-11,
puvodne Robertovo: "ten plán je potreba prepracovat na tu přehledovou
tabulku kde se bude moci odškrtávat hotové a uvidi se stav práce na vsech
sestavach"). Viz PLAN_TVORBY_SESTAV.md pro cely kontext retezce Recept ->
Scena -> Schvaleni -> Karta -> Rendery -> Web.

Radek obrazovky = KARTA (vozidlo x typologie), rozbalitelna na jednotlive
sestavy. Rozliseni dvou druhu "stavu" (bot3, 2026-09-11):

  1. DOPOCITANE, needitovatelne - fadze 1-5 + "profil vyplnen" + sloupec R.
     Ctou se ZIVE z product_assemblies/product_turntable_frames/
     shop_products, nikde se neuklada priznak "hotovo/nehotovo" - presne
     proto se to nemuze rozejit se skutecnosti (viz PLAN_TVORBY_SESTAV.md,
     nalez "40 sad snimku na disku, 0 radku v DB, mesic si nikdo nevsiml").
  2. RUCNI kroky, ktere DB poznat neumi (production_step_defs/_checks) -
     DVOUSTAVOVE: "hlaseno" a "overeno" (JEDINE bot4). CELA obrazovka je
     JEN KE CTENI, bez vyjimky (bot3 2026-09-11, po incidentu: Robert v
     adminu omylem odkliknul krok, ktery byl navrzen jako klikatelny pro
     staff - "zaškrtávátko, které jde kliknout omylem, je ve výkazu
     stavu vada"). Zapis obou stavu jde VYHRADNE pres API se servisnim
     tokenem, nikdy klikanim v UI ani staff session:
       - "hlaseno": BOT_STEP_TOKEN (kterykoli bot, viz vyroba_sestav_hlasit)
       - "overeno": KONTROLOR_TOKEN (jedine bot4, viz vyroba_sestav_overit)
     Zadny z nich NENI app_users role - bot3 2026-09-11: "Nezakládej
     účet... zakládat admin účty pro boty je přesně to, co dnes
     vyplavalo jako kritický nález" (živý případ bot8-test-scene@test.local
     v produkci). Puvodni navrh mel jeste jeden krok
     ("robert_confirmed_placement", klikatelny jen Robertem) - zrusen,
     protoze je to duplicita s uz dopocitanou fazi "2 Schvaleno"
     (technicky_ok) - viz sql/2026-09-11g_production_step_defs_oprava.sql.
     Reset: znovu-nahlaseni stejneho kroku smaze existujici overeni
     (product_assemblies nema updated_at, takze automaticke poznani
     "sahlo se do veci znovu" neni mozne - zapsano jako samostatny nalez,
     viz NOTE nize).

NOTE (nalez, poslano bot3 2026-09-11, needit se v tomhle ukolu):
product_assemblies nema `updated_at` sloupec, takze zadna cast systemu
(vcetne tohohle) neumi automaticky poznat "geometrie sestavy se zmenila
od posledniho overeni" - jedina cesta zpet na "hlaseno" je rucni
znovu-nahlaseni krokem po cloveku/botovi.
"""
import json
import os
import re
import sys
import time
from datetime import datetime

from flask import jsonify, request

from app import app, get_conn, current_user, require_permission

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import razitkovac  # noqa: E402 - sdileny s scripts/razitkovac.py (spoustec pri zarazeni do slozky), stejne rozhodnuti na obou mistech (bot8, 2026-09-11)
import production_work_claims  # noqa: E402 - bot9 2026-09-11, fronta prace pro automat (sql/2026-09-11j_production_work_claims.sql). Puvodne jen CTE abandoned() pro badge (claim/release delal vyhradne watchdog) - od komentaru/vyhrad (kolo 2, sql/2026-09-11l_*.sql) tenhle modul NAVIC sam vola claim()/release() pro target_type='sestava_komentar' (clovek/bot vyrizuje rucne nahlasenou vyhradu, ne automatizovany krok watchdogu - jiny puvodce zabrani, stejna tabulka/mechanismus).

KONTROLOR_TOKEN = os.environ.get("KONTROLOR_TOKEN", "")

# bot10, 2026-09-11 (nalez "1 321 650 Kc napric katalogem" - stare ceny
# pocitaly spoje jinym pravidlem nez dnes, nikdo je od zmeny pravidla
# neprepocital): otisk VERZE CENOVEHO VZORCE (od v3 kryje i marzi
# konfiguratoru a balne, ne jen pocet spoju), ne geometrie - musi jit
# soucasne s JOINT_RULE_VERSION ve webapp/scene.html (viz komentar tam
# pro historii verzi). Chybejici `price_summary.joint_rule_version`
# (stara sestava, ulozena pred zavedenim tohohle pole) se CTE jako
# zastarala, nikdy jako aktualni - stejna zasada jako u kolize_pocet
# (bot16: "nezmereno nesmi vypadat jako zelena").
CURRENT_JOINT_RULE_VERSION = 3

# Stav bezicich/frontovych renderovacich uloh (bot3 2026-09-11, po
# Robertove hlaseni "proc nerenderujeme, v prehledu je nula" - renderovalo
# se, 40/81 snimku, ale sloupec Rendery pocita jen RADKY V DB a ty se
# zapisou az po dokonceni CELE davky, takze 80 z 81 minut vypadaly stejne
# jako "nic se nedeje"). Presne obracena varianta pravidla u kolizi
# (bot16: "nezmereno nesmi vypadat jako zelena") - tady "prave se to dela"
# nesmi vypadat jako necinnost.
BLENDER_RENDERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "private-files", "blender-renders")
# Po tehle dobe bez aktualizace uz "bezi"/"ve fronte" neni duveryhodne -
# nejspis osiretly/spadly zaznam, ne skutecna aktivni prace (bot3: "stary
# dokonceny stav at nesviti jako bezici"). Plna davka trva ~3h, 6h je
# bezpecna rezerva nad tim.
RENDER_JOB_STALE_S = 6 * 3600


def _load_render_jobs_by_assembly():
    """Cte VSECHNY *.status.json v BLENDER_RENDERS_DIR, vraci
    {assembly_id: nejnovejsi_status_dict}. KAZDA chyba (chybejici adresar,
    rozbity/neplatny JSON, chybejici klic u JEDNOHO souboru) se pro TEN
    JEDEN soubor jen preskoci - nikdy nesmi shodit zbytek prehledu (bot3
    2026-09-11: "jeden radek s null shodil cely panel pro vsechny", jiny
    incident, ale stejna trida chyby)."""
    result = {}
    try:
        names = os.listdir(BLENDER_RENDERS_DIR)
    except OSError:
        return result
    for fname in names:
        if not fname.endswith(".status.json"):
            continue
        try:
            with open(os.path.join(BLENDER_RENDERS_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            aid = data.get("assembly_id")
            if aid is None:
                continue
            ts = data.get("progress_ts") or data.get("updated") or 0
            existing = result.get(aid)
            if existing is None or (existing.get("_ts") or 0) <= ts:
                data["_ts"] = ts
                result[aid] = data
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return result


def _render_job_status(job, now_ts):
    """Prevede syrovy status.json na {kind, note} pro UI, nebo None kdyz
    tenhle job neni pro sloupec Rendery relevantni (state=done - to uz
    resi pocet radku v product_turntable_frames beze zmeny)."""
    if not job:
        return None
    state = job.get("state")
    ts = job.get("_ts") or 0
    stale = bool(ts) and (now_ts - ts) > RENDER_JOB_STALE_S
    note = job.get("progress_note")
    if state == "error":
        return {"kind": "error", "note": job.get("error") or note}
    if state == "cancelled":
        return {"kind": "cancelled", "note": note}
    if state == "running":
        return {"kind": "stale", "note": note} if stale else {"kind": "running", "note": note}
    if state in ("queued", "waiting_worker"):
        return {"kind": "stale", "note": note} if stale else {"kind": "queued", "note": note}
    return None

# Vsechny fazove sloupce jsou POCITANE, ne ukladane - viz jednotlive
# _compute_* funkce nize. Odpovida presne bot3 zadani 2026-09-11.

_KOD_SUFFIX_RE = re.compile(r"\s*\[K-[^\]]*\]\s*—.*$")
# K-kod vozidla (bot16, 2026-09-15, zadani bot3/Robert - "kartě chybí
# sloupec čísla"): zivi jen v car_models.name jako "[K-075]"/"[K-246e]"
# (car_bodies.name NEMA K-kod - je to nazev casti GLB karoserie jako
# "leva"/"prava"/"koncova", overeno primo v datech pred implementaci,
# bot3ovo puvodni zadani melo zdrojovy sloupec obracene). "e" suffix
# (napr. K-123e) je SOUCAST kodu, ne oddelitelny priznak - [K-122] a
# [K-123e] jsou DVE RUZNA vozidla (viz car_models_kcode_electric_suffix
# pamet), proto se bere cely obsah zavorky beze zmeny.
_K_KOD_RE = re.compile(r"\[K-([^\]]+)\]")


def _extract_k_kod(name):
    """car_models.name -> "K-075"/"K-246e"/None. Viz komentar u _K_KOD_RE."""
    if not name:
        return None
    m = _K_KOD_RE.search(name)
    return f"K-{m.group(1)}" if m else None


def _iso(dt):
    """`datetime` -> ISO 8601 string, ne Flask default JSON encoder
    (RFC 822 s natvrdo prilepenym "GMT", i kdyz je hodnota naivni
    MISTNI cas z MySQL DATETIME sloupce - vysledek pak vypadal jako UTC
    a byl 2 hodiny mimo, bot4 review 2026-09-11). Zbytek projektu uz
    `.isoformat()` pouziva (viz napr. api/approvals.py) - navazuju na
    stavajici konvenci, nevymyslim novou."""
    return dt.isoformat() if dt else None


def _clean_vehicle_name(name):
    """car_models.name nese vzadu "[K-168] — 4609mm (L)...", ktere na
    tabuli nepatri (Robertuv priklad: "Fiat Doblo L1H1 (do 2022)")."""
    if not name:
        return name
    return _KOD_SUFFIX_RE.sub("", name).strip()


def _has_horni_blok(parts):
    """Spolehlivy test je role zacinajici na 'podelnik' - podelnik se
    mimo horni blok nevyskytuje (PLAN_TVORBY_SESTAV.md, overeno 2x
    nezavisle nad vsemi 269 sestavami: 13 s blokem, 256 bez - NE 14,
    puvodni cislo pocitalo omylem celou osmicku "ceka na smazani" misto
    sedmi z ni, co blok skutecne maji)."""
    return any(str(p.get("role") or "").lower().startswith("podelnik") for p in parts)


def _r_sloupec(typologie_kod, has_outdated_horni_blok):
    if typologie_kod != "EB":
        return "-"
    if has_outdated_horni_blok:
        return "!"
    return "+"


def _load_assemblies(cur):
    # bot3/Robert 2026-09-23: 2 radky "(vozidlo nerozpoznano)" v tomhle
    # panelu byly bot4uv testovaci vanDrawee EXPORT stub (671/672,
    # zalozeny jen jako nosic geometrie/razitek pro render pipeline,
    # zadne vozidlo/typologie zamerne nemaji) - "2. vetev se vepisuje
    # do tabulky pro 1. vetev, to nelze". Docasny filtr podle role
    # markeru 'vandrawee-export' (stejny marker pouziva cely Vandr
    # import), dokud stub mechanismus nedostane vlastni tabulku (bot5
    # stavi paralelni Vandr prehled).
    cur.execute(
        "SELECT pa.id, pa.name, pa.data, pa.karoserie_kod, pa.typologie_id, "
        "pa.profil_mm, pa.verze, pa.horni_blok_varianta_id, pa.technicky_ok, "
        "pa.shop_product_id, pa.category_id, "
        "pa.kolize_pocet, pa.kolize_detail, pa.kolize_checked_at, "
        "pa.prepazka_rezerva_mm, pa.podbeh_rezerva_mm, "
        "rt.kod AS typologie_kod "
        "FROM product_assemblies pa "
        "LEFT JOIN regal_typologie rt ON rt.id = pa.typologie_id "
        "WHERE JSON_SEARCH(pa.data, 'one', 'vandrawee-export', NULL, '$.parts[*].role') IS NULL"
    )
    return cur.fetchall()


def _resolve_vehicle(cur, data_parts):
    """car_body_<id> part_id -> car_bodies.model_id -> car_models.name.
    Jediny kompletni zdroj identity vozidla (car_model_id na sestave je
    NULL u vsech 269, karoserie_kod jen u 243/269) - viz rozbor poslany
    bot3 2026-09-11. K-kod (viz _extract_k_kod) se bere ze STEJNE,
    uz jednoznacne dohledane car_models radky - zadna dalsi viceznacnost
    (jeden car_model_id muze mit vic car_bodies radku, ale ty nesou jen
    geometrii GLB karoserie, ne vlastni K-kod - ten je 1:1 na car_models)."""
    for p in data_parts:
        pid = str(p.get("part_id") or "")
        if pid.startswith("car_body_"):
            try:
                car_body_id = int(pid[len("car_body_"):])
            except ValueError:
                continue
            cur.execute(
                "SELECT cm.id AS car_model_id, cm.name AS car_model_name "
                "FROM car_bodies cb JOIN car_models cm ON cm.id = cb.model_id "
                "WHERE cb.id=%s", (car_body_id,))
            row = cur.fetchone()
            if row:
                return (row["car_model_id"], _clean_vehicle_name(row["car_model_name"]),
                        _extract_k_kod(row["car_model_name"]))
    return None, None, None


def _turntable_counts(cur, assembly_ids):
    if not assembly_ids:
        return {}
    ph = ",".join(["%s"] * len(assembly_ids))
    cur.execute(
        f"SELECT assembly_id, COUNT(*) n FROM product_turntable_frames "
        f"WHERE assembly_id IN ({ph}) AND is_active=1 GROUP BY assembly_id",
        assembly_ids)
    return {r["assembly_id"]: r["n"] for r in cur.fetchall()}


def _shop_active_map(cur, shop_product_ids):
    if not shop_product_ids:
        return {}
    ph = ",".join(["%s"] * len(shop_product_ids))
    cur.execute(
        f"SELECT id, active, category_id FROM shop_products WHERE id IN ({ph})",
        shop_product_ids)
    return {r["id"]: r for r in cur.fetchall()}


def _step_defs(cur):
    cur.execute(
        "SELECT step_key, label, phase, scope, sort_order FROM production_step_defs "
        "WHERE active=1 ORDER BY sort_order")
    return cur.fetchall()


def _step_checks(cur):
    cur.execute(
        "SELECT id, step_key, assembly_id, car_model_id, typologie_id, "
        "reported_by, reported_at, verified_by, verified_at, verify_verdict, verify_note "
        "FROM production_step_checks")
    return cur.fetchall()


def _open_blockers(cur):
    cur.execute(
        "SELECT id, car_model_id, typologie_id, text, author, created_at "
        "FROM production_card_blockers WHERE resolved_at IS NULL "
        "ORDER BY created_at DESC")
    rows = cur.fetchall()
    out = {}
    for r in rows:
        key = (r["car_model_id"], r["typologie_id"])
        if key not in out:  # jen nejnovejsi na kartu
            out[key] = r
    return out


def _comments_by_assembly(cur, assembly_ids):
    """Vsechny komentare (vyhrady) - OTEVRENE i VYRESENE, Robert chce u
    schvaleni videt odpoved, ne zmizely radek (bot3 2026-09-11). Na
    rozdil od _open_blockers() se nefiltruje na "jen nejnovejsi" -
    komentare jsou HISTORIE (sql/2026-09-11l_production_comments.sql),
    kazdy zapis vlastni radek."""
    if not assembly_ids:
        return {}
    placeholders = ",".join(["%s"] * len(assembly_ids))
    cur.execute(
        f"SELECT id, assembly_id, body, author, created_at, resolved_at, resolved_by, resolution_note "
        f"FROM production_comments WHERE assembly_id IN ({placeholders}) ORDER BY created_at DESC",
        tuple(assembly_ids))
    out = {}
    for r in cur.fetchall():
        out.setdefault(r["assembly_id"], []).append(r)
    return out


# bot16, 2026-09-29 (Robert pres bot3, "kazdy panel adminu do tabulky
# roli a prav"): prehled+blokace patri VYHRADNE dashboard panelu
# vyrobaSestavPanel (DASHBOARD_PANEL_SECTION v admin.html) - proto
# vlastni "dash_vyroba_sestav", NE puvodni sdilene "vyroba_sestav".
# komentare NIZE zustavaji na "vyroba_sestav" schvalne - ty pouziva
# JEN scene.html (frontovy panel pri konfiguraci sestavy), ne dashboard.
@app.get("/api/admin/vyroba-sestav/prehled")
@require_permission("dash_vyroba_sestav", "zobrazit")
def vyroba_sestav_prehled():
    import json as _json
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            assemblies = _load_assemblies(cur)
            parsed = []
            for a in assemblies:
                try:
                    data = _json.loads(a["data"]) if a["data"] else {}
                except (ValueError, TypeError):
                    data = {}
                parts = data.get("parts") or []
                car_model_id, car_model_name, car_model_k_kod = _resolve_vehicle(cur, parts)
                parsed.append({
                    "row": a,
                    "data": data,
                    "parts": parts,
                    "bom": data.get("bom") or [],
                    "price_summary": data.get("price_summary") or {},
                    "car_model_id": car_model_id,
                    "car_model_name": car_model_name,
                    "car_model_k_kod": car_model_k_kod,
                    "razitka_stav": razitkovac.stav_razitek(data),
                })

            assembly_ids = [p["row"]["id"] for p in parsed]
            tt_counts = _turntable_counts(cur, assembly_ids)
            shop_ids = list({p["row"]["shop_product_id"] for p in parsed if p["row"]["shop_product_id"]})
            shop_map = _shop_active_map(cur, shop_ids)
            step_defs = _step_defs(cur)
            step_checks = _step_checks(cur)
            blockers = _open_blockers(cur)
            # Opustene zabrani automatu (bot9, production_work_claims -
            # sql/2026-09-11j_*.sql). Jen CTENI pro badge, nikdy nezapisuje
            # (claim/release dela vyhradne watchdog skript). Chyba (chybejici
            # tabulka, ktera jeste nemusi byt na vsech prostredich nasazena)
            # se stejne jako u render_jobs jen preskoci - nesmi shodit zbytek
            # prehledu.
            try:
                abandoned_claims = production_work_claims.abandoned(cur)
            except Exception:
                abandoned_claims = []
            try:
                comments_by_assembly = _comments_by_assembly(cur, assembly_ids)
            except Exception:
                comments_by_assembly = {}
    finally:
        conn.close()

    abandoned_by_assembly = {}
    for c in abandoned_claims:
        if c.get("target_type") == "assembly":
            abandoned_by_assembly.setdefault(c["target_id"], []).append(c)

    render_jobs = _load_render_jobs_by_assembly()
    now_ts = time.time()

    # -- KARTA = (car_model_id, typologie_id); bez rozpoznaneho vozidla
    #    (26 sestav bez karoserie_kod I bez car_body_* dilu - viz nalez
    #    poslany bot3) jde do zvlastni "neurcena" skupiny, at nezmizi ze
    #    statistiky.
    kartas = {}
    for p in parsed:
        row = p["row"]
        typologie_id = row["typologie_id"]
        car_model_id = p["car_model_id"]
        key = (car_model_id, typologie_id)
        k = kartas.setdefault(key, {
            "car_model_id": car_model_id,
            "car_model_name": p["car_model_name"] or "(vozidlo nerozpoznáno)",
            "car_model_k_kod": p["car_model_k_kod"],
            "typologie_id": typologie_id,
            "typologie_kod": row["typologie_kod"],
            "sestavy": [],
        })
        k["sestavy"].append(p)

    # step_checks indexovane pro rychle hledani
    checks_by_assembly = {}
    checks_by_karta = {}
    for c in step_checks:
        if c["assembly_id"] is not None:
            checks_by_assembly.setdefault(c["assembly_id"], {})[c["step_key"]] = c
        elif c["car_model_id"] is not None:
            checks_by_karta.setdefault((c["car_model_id"], c["typologie_id"]), {})[c["step_key"]] = c

    def check_state(c):
        if not c:
            return {"reported": False, "verified": False}
        return {
            "reported": bool(c["reported_at"]),
            "reported_by": c["reported_by"], "reported_at": _iso(c["reported_at"]),
            "verified": bool(c["verified_at"]),
            "verified_by": c["verified_by"], "verified_at": _iso(c["verified_at"]),
            "verify_verdict": c["verify_verdict"], "verify_note": c["verify_note"],
        }

    result_kartas = []
    for (car_model_id, typologie_id), k in kartas.items():
        n = len(k["sestavy"])
        n_scena = sum(1 for p in k["sestavy"] if p["bom"] and p["price_summary"].get("material_czk") is not None)
        n_schvaleno = sum(1 for p in k["sestavy"] if p["row"]["technicky_ok"])
        has_karta = any(p["row"]["shop_product_id"] for p in k["sestavy"])
        n_rendery = sum(1 for p in k["sestavy"] if tt_counts.get(p["row"]["id"], 0) > 0)
        has_web = False
        for p in k["sestavy"]:
            spid = p["row"]["shop_product_id"]
            if spid and shop_map.get(spid, {}).get("active") and shop_map.get(spid, {}).get("category_id"):
                has_web = True
                break
        profil_vyplnen = sum(1 for p in k["sestavy"] if p["row"]["profil_mm"] is not None)
        n_razitka = sum(1 for p in k["sestavy"] if p["razitka_stav"] == "aktualni")
        n_razitka_zastarala = sum(1 for p in k["sestavy"] if p["razitka_stav"] == "zastarala")
        has_outdated = any(_has_horni_blok(p["parts"]) for p in k["sestavy"])
        r_val = _r_sloupec(k["typologie_kod"], has_outdated)

        sestavy_out = []
        for p in k["sestavy"]:
            row = p["row"]
            assembly_steps = {}
            for sd in step_defs:
                if sd["scope"] != "sestava":
                    continue
                assembly_steps[sd["step_key"]] = check_state(checks_by_assembly.get(row["id"], {}).get(sd["step_key"]))
            kolize_detail = row["kolize_detail"]
            if isinstance(kolize_detail, str):
                try:
                    kolize_detail = _json.loads(kolize_detail)
                except (ValueError, TypeError):
                    kolize_detail = None
            sestavy_out.append({
                "id": row["id"], "name": row["name"],
                "scena": bool(p["bom"] and p["price_summary"].get("material_czk") is not None),
                "schvaleno": bool(row["technicky_ok"]),
                "karta": bool(row["shop_product_id"]),
                "rendery": tt_counts.get(row["id"], 0),
                "web": bool(row["shop_product_id"] and shop_map.get(row["shop_product_id"], {}).get("active")
                            and shop_map.get(row["shop_product_id"], {}).get("category_id")),
                "profil_mm": row["profil_mm"],
                "verze": row["verze"],
                "horni_blok_varianta_id": row["horni_blok_varianta_id"],
                # Serie (Robert 2026-09-12, pres bot3: paralelni serie
                # regalu se stejnym receptem, jinou kolizni rezervou -
                # "10-30mm od kolize" vedle dosavadnich "2-20mm"). ZADNY
                # samostatny textovy sloupec (bot3: riziko rozjeti
                # cisla/textu) - stitek se sklada az na frontendu ze
                # dvou cisel. Existujicich 269 ma OBE cisla vyplnena
                # (2/20, zpetne dopocteno bot8 2026-09-12) - NULL tu tedy
                # neznamena "puvodni serie", ale "jeste nezpracovano".
                "prepazka_rezerva_mm": row["prepazka_rezerva_mm"],
                "podbeh_rezerva_mm": row["podbeh_rezerva_mm"],
                # kolize_pocet: NULL = nikdy nezmereno, 0 = cisto, >0 = pocet
                # nalezu - NEZAMENOVAT (bot16, 2026-09-11: "0 nalezeno" uz
                # 3x znamenalo "nic jsem neporovnal", ne "cisto").
                "kolize_pocet": row["kolize_pocet"],
                "kolize_detail": kolize_detail,
                "kolize_checked_at": row["kolize_checked_at"],
                "razitka_stav": p["razitka_stav"],
                # Aktualni render job (bot3 2026-09-11, po Robertove hlaseni
                # "proc nerenderujeme, v prehledu je nula" - renderovalo se,
                # jen radek v DB se zapise az PO cele davce). None = zadny
                # aktivni/relevantni job (bud se nikdy nerenderovalo, nebo
                # uz je "done" a to uz resi cislo vys).
                "render_job": _render_job_status(render_jobs.get(row["id"]), now_ts),
                # Automat/bot spadl uprostred prace na tomhle kroku (zabral,
                # nedokoncil, ani neuvolnil) - production_work_claims,
                # abandoned() (bot9 2026-09-11). Prazdny seznam = nic
                # takoveho, needitovatelne, jen ke cteni.
                "stuck_claims": [
                    {"step_key": c["step_key"], "held_by": c["held_by"], "expires_at": _iso(c["expires_at"])}
                    for c in abandoned_by_assembly.get(row["id"], [])
                ],
                # Vyhrady (production_comments, bot3/Robert 2026-09-11 -
                # "dej moznost napsat komentar"). HISTORIE - otevrene i
                # vyresene se posilaji obe (Robert chce u schvaleni videt
                # odpoved, ne zmizely radek), rozliseni dela frontend
                # podle resolved_at. open_comments_count je tu navic
                # separatne, at ho staci scitat pro kartu bez znovu-
                # filtrovani seznamu.
                "comments": [
                    {
                        "id": c["id"], "body": c["body"], "author": c["author"],
                        "created_at": _iso(c["created_at"]),
                        "resolved_at": _iso(c["resolved_at"]) if c["resolved_at"] else None,
                        "resolved_by": c["resolved_by"], "resolution_note": c["resolution_note"],
                    } for c in comments_by_assembly.get(row["id"], [])
                ],
                "open_comments_count": sum(1 for c in comments_by_assembly.get(row["id"], []) if not c["resolved_at"]),
                # Cena podle stare verze pravidla poctu spoju - viz
                # CURRENT_JOINT_RULE_VERSION vyse. Chybejici pole = stale.
                "joint_rule_stale": p["price_summary"].get("joint_rule_version") != CURRENT_JOINT_RULE_VERSION,
                "steps": assembly_steps,
            })

        karta_steps = {}
        for sd in step_defs:
            if sd["scope"] != "karta":
                continue
            karta_steps[sd["step_key"]] = check_state(checks_by_karta.get((car_model_id, typologie_id), {}).get(sd["step_key"]))

        blocker = blockers.get((car_model_id, typologie_id))

        kolize_koliduje = sum(1 for p in k["sestavy"] if (p["row"]["kolize_pocet"] or 0) > 0)
        kolize_zmereno = sum(1 for p in k["sestavy"] if p["row"]["kolize_pocet"] is not None)

        # Nejvyznamnejsi aktivni render job na karte - "chyba" ma prednost
        # pred "bezi" pred "ve fronte" pred "nejasny/stary", at se nejhorsi
        # stav neztrati mezi devitkou jinak klidnych sestav.
        _RENDER_KIND_PRIORITY = {"error": 0, "running": 1, "queued": 2, "stale": 3, "cancelled": 4}
        karta_render_job = None
        for p in k["sestavy"]:
            rj = _render_job_status(render_jobs.get(p["row"]["id"]), now_ts)
            if not rj:
                continue
            if karta_render_job is None or _RENDER_KIND_PRIORITY.get(rj["kind"], 9) < _RENDER_KIND_PRIORITY.get(karta_render_job["kind"], 9):
                karta_render_job = rj

        stuck_claims_count = sum(len(abandoned_by_assembly.get(p["row"]["id"], [])) for p in k["sestavy"])
        open_comments_count = sum(
            1 for p in k["sestavy"] for c in comments_by_assembly.get(p["row"]["id"], []) if not c["resolved_at"])
        joint_rule_stale_count = sum(
            1 for p in k["sestavy"] if p["price_summary"].get("joint_rule_version") != CURRENT_JOINT_RULE_VERSION)

        result_kartas.append({
            "car_model_id": car_model_id,
            "typologie_id": typologie_id,
            "typologie_kod": k["typologie_kod"],
            "nazev": k["car_model_name"],
            "k_kod": k["car_model_k_kod"],
            "pocet_sestav": n,
            "r": r_val,
            "scena": {"hotovo": n_scena, "celkem": n},
            "schvaleno": {"hotovo": n_schvaleno, "celkem": n},
            "karta": has_karta,
            # Brana pred renderem (Robert pres bot3, 2026-09-11: "aby se
            # mohlo renderovat") - proto v poradi MEZI schvalenim a
            # rendery, ne az za nimi. 3 stavy (razitkovac.stav_razitek,
            # sdileno se spoustecem pri zarazeni do slozky, bot8): "zadna"
            # se pocita jako nehotovo stejne jako "zastarala" (obe musi
            # jeste projit razitkovacem), ale zastarala se ukazuje zvlast
            # - "ma, ale spatne" neni totez jako "nema vubec".
            "razitka": {"hotovo": n_razitka, "celkem": n, "zastarala": n_razitka_zastarala},
            "rendery": {"hotovo": n_rendery, "celkem": n, "aktivni_job": karta_render_job},
            "web": has_web,
            "profil_vyplnen": {"hotovo": profil_vyplnen, "celkem": n},
            # Kolizni uhelniky (bot16, scripts/2026-09-11_sweep_kolizni_uhelniky.cjs,
            # pravidlo v3) - JEN uhelniky proti ostatnim dilum, ne vsechny
            # dvojice (all-pairs zmereno jako neunosne, >13 min na 40
            # sestav). "zmereno" < "celkem" znamena "NULL, ne cisto".
            "kolize": {"koliduje": kolize_koliduje, "zmereno": kolize_zmereno, "celkem": n},
            "next_step": _next_step(r_val, n_scena, n_schvaleno, has_karta, n_razitka, n_rendery, has_web, n),
            "stuck_claims_count": stuck_claims_count,
            "open_comments_count": open_comments_count,
            "joint_rule_stale_count": joint_rule_stale_count,
            "sestavy": sestavy_out,
            "karta_steps": karta_steps,
            "blokace": {
                "text": blocker["text"], "author": blocker["author"], "created_at": _iso(blocker["created_at"]),
            } if blocker else None,
        })

    result_kartas.sort(key=lambda k: (k["nazev"] or ""))

    # Souhrn podle serie (Robert 2026-09-12: "aby se nova davka nemichala
    # do statistik jako nerozlisena") - napric VSEMI kartami, ne per-karta,
    # protoze obe serie vznikaji ze stejnych receptu/karoserii. Razeno
    # sestupne podle poctu, at nejpocetnejsi (dnes 2-20mm, 269 kusu) je
    # prvni.
    serie_counts = {}
    for p in parsed:
        key = (p["row"]["prepazka_rezerva_mm"], p["row"]["podbeh_rezerva_mm"])
        serie_counts[key] = serie_counts.get(key, 0) + 1
    serie_summary = [
        {"prepazka_rezerva_mm": k[0], "podbeh_rezerva_mm": k[1], "pocet": v}
        for k, v in sorted(serie_counts.items(), key=lambda kv: -kv[1])
    ]

    return jsonify({
        "step_defs": [{"step_key": sd["step_key"], "label": sd["label"], "phase": sd["phase"], "scope": sd["scope"]} for sd in step_defs],
        "kartas": result_kartas,
        "serie_summary": serie_summary,
    })


def _next_step(r_val, n_scena, n_schvaleno, has_karta, n_razitka, n_rendery, has_web, n):
    if r_val == "-":
        return "recepty chybí"
    if n_scena < n:
        return "doplnit kusovník"
    if n_schvaleno < n:
        return "čeká na schválení"
    if not has_karta:
        return "založit skladovou kartu"
    if n_razitka < n:
        return "chybí razítka"
    if n_rendery < n:
        return "pustit rendery"
    if not has_web:
        return "publikovat"
    return "hotovo"


def _target_from_body(body):
    """Vrati bud ('assembly', assembly_id) nebo ('karta', (car_model_id,
    typologie_id)) podle toho, co telo requestu poslalo."""
    if body.get("assembly_id") is not None:
        return "assembly", int(body["assembly_id"])
    if body.get("car_model_id") is not None and body.get("typologie_id") is not None:
        return "karta", (int(body["car_model_id"]), int(body["typologie_id"]))
    return None, None


BOT_STEP_TOKEN = os.environ.get("BOT_STEP_TOKEN", "")


def _require_bot_step_token():
    """Rucni kroky se v UI JEN CTOU, nikdy neklikaji (bot3 2026-09-11, po
    incidentu: Robert v adminu omylem odkliknul zaskrtavatko, ktere melo
    byt jen zobrazeni stavu). Zapis "hlaseno" proto smi jedine bot s
    timhle tokenem, stejny vzor jako KONTROLOR_TOKEN pro "overeno"."""
    if not BOT_STEP_TOKEN:
        return jsonify({"error": "BOT_STEP_TOKEN není na serveru nakonfigurovaný."}), 503
    import hmac
    if not hmac.compare_digest(request.headers.get("X-Bot-Token") or "", BOT_STEP_TOKEN):
        return jsonify({"error": "Neplatný bot token."}), 401
    return None


@app.post("/api/admin/vyroba-sestav/steps/hlasit")
def vyroba_sestav_hlasit():
    err = _require_bot_step_token()
    if err:
        return err
    # bot3 2026-09-11 ("kdokoli se muze podepsat jako kdokoli, cela stopa
    # je bezcenna"): identita se NEBERE z tela pozadavku, ale z toho,
    # KTERY token pozadavek pouzil - BOT_STEP_TOKEN je sdileny mezi
    # vsemi boty, takze jemnejsi rozliseni neni mozne bez sady tokenu
    # per-bot (dnes nezavedeno), proto pevny obecny "bot".
    reported_by = "bot"
    body = request.get_json(silent=True) or {}
    step_key = body.get("step_key")
    if not step_key:
        return jsonify({"error": "Chybí step_key."}), 400
    scope, target = _target_from_body(body)
    if scope is None:
        return jsonify({"error": "Chybí assembly_id nebo (car_model_id + typologie_id)."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT scope FROM production_step_defs WHERE step_key=%s AND active=1", (step_key,))
            sd = cur.fetchone()
            if not sd:
                return jsonify({"error": "Neznámý nebo neaktivní krok."}), 400
            if (sd["scope"] == "sestava") != (scope == "assembly"):
                return jsonify({"error": f"Krok '{step_key}' má rozsah '{sd['scope']}', nesedí s odesílaným cílem."}), 400

            now = datetime.now()
            if scope == "assembly":
                cur.execute(
                    "INSERT INTO production_step_checks (step_key, assembly_id, reported_by, reported_at) "
                    "VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
                    "reported_by=VALUES(reported_by), reported_at=VALUES(reported_at), "
                    "verified_by=NULL, verified_at=NULL, verify_verdict=NULL, verify_note=NULL",
                    (step_key, target, reported_by, now))
            else:
                car_model_id, typologie_id = target
                cur.execute(
                    "INSERT INTO production_step_checks (step_key, car_model_id, typologie_id, reported_by, reported_at) "
                    "VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
                    "reported_by=VALUES(reported_by), reported_at=VALUES(reported_at), "
                    "verified_by=NULL, verified_at=NULL, verify_verdict=NULL, verify_note=NULL",
                    (step_key, car_model_id, typologie_id, reported_by, now))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


def _require_kontrolor_token():
    if not KONTROLOR_TOKEN:
        return jsonify({"error": "KONTROLOR_TOKEN není na serveru nakonfigurovaný."}), 503
    import hmac
    if not hmac.compare_digest(request.headers.get("X-Kontrolor-Token") or "", KONTROLOR_TOKEN):
        return jsonify({"error": "Neplatný kontrolní token."}), 401
    return None


def _find_step_check_row(cur, scope, target, step_key):
    if scope == "assembly":
        cur.execute("SELECT id, reported_at FROM production_step_checks WHERE assembly_id=%s AND step_key=%s",
                    (target, step_key))
    else:
        car_model_id, typologie_id = target
        cur.execute("SELECT id, reported_at FROM production_step_checks WHERE car_model_id=%s AND typologie_id=%s AND step_key=%s",
                    (car_model_id, typologie_id, step_key))
    return cur.fetchone()


@app.post("/api/admin/vyroba-sestav/steps/overit")
def vyroba_sestav_overit():
    """Jedine bot4 (kontrolor) - gatovano servisnim tokenem, NE
    app_users rolí (bot3 2026-09-11: zakladani admin uctu pro boty uz
    jednou zpusobilo tichy bezpecnostni nalez, viz bot8-test-scene@test.local).

    verified_by NENI z tela requestu (bot3 2026-09-11: "kdokoli se muze
    podepsat jako kdokoli") - kontrolorsky token ma jedine bot4, takze
    identita je pevne "bot4".

    verify_verdict ma TRI hodnoty, ne dve - SPLNENO/CASTECNE/NESPLNENO.
    Bez NESPLNENO nemel kontrolor jak zapsat "zkontroloval jsem a NEPLATI
    to" - krok by dal svitil jen "ceka na overeni", ac uz byl proveren a
    neuspel (bot3 2026-09-11: "kdyz kontrola propadne, nezustane po ni
    stopa")."""
    err = _require_kontrolor_token()
    if err:
        return err
    verified_by = "bot4"
    body = request.get_json(silent=True) or {}
    step_key = body.get("step_key")
    verdict = body.get("verify_verdict")
    if not step_key:
        return jsonify({"error": "Chybí step_key."}), 400
    if verdict not in ("SPLNENO", "CASTECNE", "NESPLNENO"):
        return jsonify({"error": "verify_verdict musí být SPLNENO, CASTECNE nebo NESPLNENO."}), 400
    scope, target = _target_from_body(body)
    if scope is None:
        return jsonify({"error": "Chybí assembly_id nebo (car_model_id + typologie_id)."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            row = _find_step_check_row(cur, scope, target, step_key)
            if not row or not row["reported_at"]:
                return jsonify({"error": "Krok zatím nikdo nenahlásil jako hotový - není co ověřovat."}), 400
            cur.execute(
                "UPDATE production_step_checks SET verified_by=%s, verified_at=%s, verify_verdict=%s, verify_note=%s "
                "WHERE id=%s",
                (verified_by, datetime.now(), verdict, body.get("verify_note"), row["id"]))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/admin/vyroba-sestav/steps/zneplatnit-overeni")
def vyroba_sestav_zneplatnit_overeni():
    """Zrusi drivejsi overeni (verified_* -> NULL), krok se vrati do
    stavu "hlaseno, ceka na overeni" - reported_* zustava netknute, na
    tvrzeni "je hotovo" se nic nemeni, jen se rusi TVRZENI O OVERENI
    (bot3 2026-09-11: "udelene overeni nejde odebrat" - napr. kdyz se
    ukaze, ze byl kontrolor sam na omylu, nebo se podklad zmenil).
    Jedine bot4, stejny token jako overit."""
    err = _require_kontrolor_token()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    step_key = body.get("step_key")
    if not step_key:
        return jsonify({"error": "Chybí step_key."}), 400
    scope, target = _target_from_body(body)
    if scope is None:
        return jsonify({"error": "Chybí assembly_id nebo (car_model_id + typologie_id)."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            row = _find_step_check_row(cur, scope, target, step_key)
            if not row:
                return jsonify({"error": "Krok nemá žádný záznam k zneplatnění."}), 400
            cur.execute(
                "UPDATE production_step_checks SET verified_by=NULL, verified_at=NULL, "
                "verify_verdict=NULL, verify_note=NULL WHERE id=%s",
                (row["id"],))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/admin/vyroba-sestav/blokace")
@require_permission("dash_vyroba_sestav", "upravit")
def vyroba_sestav_blokace():
    """Zapise novou blokaci (uzavre pripadnou drivejsi otevrenou) - nebo
    jen uzavre, kdyz text prijde prazdny ("vyreseno, bez nove poznamky").

    Kdyz se text NEZMENIL oproti aktualni oteviene blokaci, nedela se
    nic (bot4 review 2026-09-11: opakovane "Ulozit" se stejnym textem
    by jinak zavrelo starou a zalozilo identickou novou - zanaseni
    historie beze zmeny)."""
    user = current_user()
    body = request.get_json(silent=True) or {}
    car_model_id = body.get("car_model_id")
    typologie_id = body.get("typologie_id")
    text = (body.get("text") or "").strip()
    if car_model_id is None or typologie_id is None:
        return jsonify({"error": "Chybí car_model_id nebo typologie_id."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT text FROM production_card_blockers "
                "WHERE car_model_id=%s AND typologie_id=%s AND resolved_at IS NULL",
                (car_model_id, typologie_id))
            existing = cur.fetchone()
            if existing and existing["text"] == text:
                return jsonify({"status": "ok", "unchanged": True})
            cur.execute(
                "UPDATE production_card_blockers SET resolved_at=%s "
                "WHERE car_model_id=%s AND typologie_id=%s AND resolved_at IS NULL",
                (datetime.now(), car_model_id, typologie_id))
            if text:
                author = user.get("name") or user.get("email") or str(user.get("id"))
                cur.execute(
                    "INSERT INTO production_card_blockers (car_model_id, typologie_id, text, author, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (car_model_id, typologie_id, text, author, datetime.now()))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


# --- Komentare (vyhrady) k sestave ve fronte ke schvaleni ---------------
# bot10, zadani bot3 koordinace 2026-09-11 (puvodne Robert: "dej moznost
# napsat komentar, ulozi se to k tomu do prehledu stavu sestav"). Kolo 1
# (Robert cekal ZIVE ve fronte): jen zapis + historie k jedne sestave, viz
# sql/2026-09-11l_production_comments.sql. NEZAVISLE na schvaleni/zamitnuti
# (bot3: "komentar nesmi byt podminovany schvalenim ani zamitnutim") a
# NESAHA na product_assemblies.data/technicky_ok - samostatna tabulka.
# Napojeni na production_work_claims (bot9) a rozsireni velkeho /prehled
# o souhrn za kartu jsou dalsi kolo, zamerne odlozene (bot3: "at uz to
# prvni kolo uklada historii, ne jedno prepisovane pole - dodelavat to
# zpetne by znamenalo migraci dat").
@app.post("/api/admin/vyroba-sestav/komentare")
@require_permission("vyroba_sestav", "upravit")
def vyroba_sestav_komentar_zapsat():
    user = current_user()
    body = request.get_json(silent=True) or {}
    assembly_id = body.get("assembly_id")
    text = (body.get("text") or "").strip()
    if not assembly_id:
        return jsonify({"error": "Chybí assembly_id."}), 400
    if not text:
        return jsonify({"error": "Prázdná poznámka."}), 400
    text = text[:2000]
    author = user.get("name") or user.get("email") or str(user.get("id"))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO production_comments (assembly_id, body, author, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (assembly_id, text, author, datetime.now()))
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": new_id})


@app.get("/api/admin/vyroba-sestav/komentare")
@require_permission("vyroba_sestav", "zobrazit")
def vyroba_sestav_komentare_list():
    """Historie komentaru k JEDNE sestave (query assembly_id) - pouziva
    frontovy panel ve scene.html pri kazde navigaci na jinou sestavu.
    Velky /prehled endpoint od kola 2 taky posila komentare (na urovni
    kazde sestavy), tenhle zustava kvuli scene.html - ta netahá cely
    prehled, jen jednu sestavu."""
    assembly_id = request.args.get("assembly_id", type=int)
    if not assembly_id:
        return jsonify({"error": "Chybí assembly_id."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, body, author, created_at, resolved_at, resolved_by, resolution_note "
                "FROM production_comments WHERE assembly_id=%s ORDER BY created_at DESC",
                (assembly_id,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"komentare": [
        {
            "id": r["id"], "body": r["body"], "author": r["author"],
            "created_at": _iso(r["created_at"]),
            "resolved_at": _iso(r["resolved_at"]) if r["resolved_at"] else None,
            "resolved_by": r["resolved_by"], "resolution_note": r["resolution_note"],
        } for r in rows
    ]})


@app.post("/api/admin/vyroba-sestav/komentare/<int:comment_id>/claim")
def vyroba_sestav_komentar_claim(comment_id):
    """Bot si vyhradu 'bere' jako ukol - VOLITELNY krok (nikdo ho nemusi
    volat), jen anti-kolizni zabrani pres jiz existujici
    production_work_claims (bot9, sql/2026-09-11j_*.sql), stejny
    mechanismus jako automatizovane kroky (bom_backfill...), jiny
    puvodce - target_type='sestava_komentar', target_id=comment_id
    (KAZDY komentar vlastni klic, ne assembly_id - dva soucasne otevrene
    komentare na tez sestave se navzajem neblokuji)."""
    err = _require_bot_step_token()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    held_by = (body.get("held_by") or "").strip()
    if not held_by:
        return jsonify({"error": "Chybí held_by."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT resolved_at FROM production_comments WHERE id=%s", (comment_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Komentář nenalezen."}), 404
            if row["resolved_at"]:
                return jsonify({"error": "Komentář je už vyřešený."}), 400
            claimed = production_work_claims.claim(cur, "sestava_komentar", comment_id, "vyrizeni", held_by)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "claimed": claimed})


@app.post("/api/admin/vyroba-sestav/komentare/<int:comment_id>/vyresit")
def vyroba_sestav_komentar_vyresit(comment_id):
    """Uzavre vyhradu - VZDY s poznamkou co se udelalo (Robert pres
    bot3: "at ma u schvaleni videt odpoved, ne zmizely radek"). Zavira
    ji ten, kdo ji opravil (`held_by`, sebe-hlaseny - stejny model
    duvery jako production_work_claims.held_by, viz modul-level
    komentar). NIKDY nesaha na product_assemblies/technicky_ok - 28
    sestav ma nafouknuty joint_count, znovu-ulozeni ze sceny by
    prepsalo ceny, o kterych Robert jeste nerozhodl (stejne pravidlo
    jako u zapisu komentare vyse). Predchozi claim() NENI podminka -
    release() nize je bezny no-op, kdyz nic nebylo zabrane."""
    err = _require_bot_step_token()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    held_by = (body.get("held_by") or "").strip()
    note = (body.get("note") or "").strip()
    if not held_by:
        return jsonify({"error": "Chybí held_by (kdo výhradu vyřešil)."}), 400
    if not note:
        return jsonify({"error": "Chybí note (co se udělalo)."}), 400
    note = note[:1000]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT resolved_at FROM production_comments WHERE id=%s", (comment_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Komentář nenalezen."}), 404
            if row["resolved_at"]:
                return jsonify({"error": "Komentář je už vyřešený."}), 400
            cur.execute(
                "UPDATE production_comments SET resolved_at=%s, resolved_by=%s, resolution_note=%s WHERE id=%s",
                (datetime.now(), held_by, note, comment_id))
            production_work_claims.release(cur, "sestava_komentar", comment_id, "vyrizeni", held_by, "hotovo", note[:290])
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})
