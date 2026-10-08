"""Vzhled online nabidek (sdileny 3D prohlizec V3D): HDRI prostredi, povrch hliniku, AO, sytost barev a barvy materialu - JEDNA ulozena konfigurace pro VSECHNY online nabidky
(bot10, 2026-10-06; Robert: "potrebuju upravovat materialy v online nabidce a hdri, tzn v kontrolni scene").

Nastavuje se v kontrolni scene (webapp/kontrola.html, rezim=nabidka: okno "Vzhled nabidek" s V3D.envPicker + volba Hliniku / AO v HUD prohlizece a tlacitko
"Ulozit vzhled pro nabidky"). Cte ho stranka online nabidky pri zobrazeni (webapp/nabidka-online.html) a preda prohlizeci V3D.mount({envConfig, aluVariant, aoVariant}).
Vzhled se NEPEKE do modelu nabidky (je to volba prohlizece), proto se projevi i u uz vytvorenych nabidek. Materialy dilu podle role (barva boxu, desek) zustavaji v panelu
Rendering -> HDRi (app_settings render_prirazeni_materialu) a plati pro nove stavene modely nabidek.

app_settings `v3d_nabidka_vzhled` = JSON {"env": {hdri, strength, rot_deg, hemi} | null, "alu": klic | null, "ao": klic | null, "sat": 0-2 | null, "barvy": {"#puvodni": "#nova"} | null,
"lesk": {"#puvodni": 0-2} | null, "ao_mat": {"#puvodni": 0-2} | null, "alu_cfg": {"refl": 0-1.5, "rough": 0.5-2, "ao": 0-2} | null, "ao_cfg": {"k": 0-2, "r": 0.25-3} | null};
null = vychozi vzhled prohlizece. lesk = lesk NE-hlinikoveho materialu podle jeho puvodni barvy (nasobek 0-2, 1 = beze zmeny / dvojice se zahodi; drsnost = puvodni^lesk), alu_cfg = sila odrazu (refl) a matnost (rough)
hliniku jako nasobky zvolene varianty hliniku, ao_cfg = sila (k) a dosah (r) AO jako nasobky zvolene varianty AO (Robert 2026-10-07: "reseni odlesku materialu, jejich AO"; viewer3d.js 1.14.0). sat = nasobek sytosti barev NE-hlinikovych materialu (1 = beze zmeny, ulozi se jako null), barvy = nahrada puvodni barvy materialu (sRGB hex male pismo, max 40 dvojic)
(Robert 2026-10-06: "chci upravit barvy a sytost materialu v 3D pohledu kontrolni sceny / v nabidce"; uplatni prohlizec podle puvodni barvy materialu, viewer3d.js 1.11.0 setMatConfig).
ao_mat = sila AO na dilech teto PUVODNI barvy (nasobek 0-2 sily AO, 1 = beze zmeny / dvojice se zahodi) a alu_cfg.ao = totez pro hlinikove profily (Robert 2026-10-07: "nenasel jsem AO pro jednotlive komponenty, jen pro hlinikove profily";
viewer3d.js 1.16.0, matConfig.ao / aluConfig.ao). Zapisuje JEN kod PUT nize (admin, opravneni nastaveni/upravit) - nikdy primo bot ani skript (stejne pravidlo jako u prostredi generatoru a renderu).
  GET /api/public/v3d-vzhled     verejne, bez prihlaseni (nese jen vyber vzhledu, zadna data nabidky ani zakaznika)
  PUT /api/admin/v3d-vzhled      telo {env?, alu?, ao?, sat?, barvy?, lesk?, ao_mat?, alu_cfg?, ao_cfg?} nebo `null` = smazat (vychozi); nezname klice, hodnoty mimo meze nebo spatny typ = 400, nic se neorezava potichu
Klice a meze jsou shodne s webapp/js/v3d/viewer3d.js (V3D.envLibrary, aluVariants, aoVariants, normalizeEnvConfig); shodu hlida scripts/2026-10-06_v3d_vzhled_testy/test_vzhled_api.py.
Doplnena HDRI ze Sdileneho disku: api/v3d_env_import.py (env.hdri smi byt i jejich klic; GET vraci navic hdri_extra). Docs: docs/KONTRAKT_NABIDKA_3D.md (5f, 5j, 5k)."""
import json
import re
import time

from flask import jsonify, request

from app import app, get_conn, require_permission, current_user, log_audit
import v3d_env_import  # noqa: E402 - registruje trasy /api/admin/v3d-env/* a /api/public/v3d-env/* (HDRI ze Sdileneho disku) a dodava klice doplnenych HDRI

KLIC = "v3d_nabidka_vzhled"
ENV_HDRI = ("crossfit", "tv_studio", "berg_inner", "teufelsberg", "mistnost")
ENV_MEZE = {"strength": (0.1, 3.0), "rot_deg": (-180.0, 180.0), "hemi": (0.0, 1.2)}
ALU = ("puvodni", "satin", "matny", "eloxovany", "bez")
AO = ("vyp", "jemne", "stredni", "silne")
SAT_MEZE = (0.0, 2.0)                # nasobek sytosti barev materialu (viewer3d.js MAT_SAT_MAX)
BARVY_MAX = 40                       # nejvyse tolik dvojic puvodni -> nova barva (viewer3d.js MAT_COLORS_MAX); stejny strop plati pro lesk
LESK_MEZE = (0.0, 2.0)               # lesk materialu (viewer3d.js GLOSS_MAX)
ALU_CFG_MEZE = {"refl": (0.0, 1.5), "rough": (0.5, 2.0), "ao": (0.0, 2.0)}        # hlinik: sila odrazu, matnost, vaha AO (viewer3d.js ALU_REFL_MAX, ALU_ROUGH_MIN / MAX, AO_MAT_MAX)
AO_MAT_MEZE = (0.0, 2.0)             # AO po komponentech: vaha AO materialu podle puvodni barvy (viewer3d.js AO_MAT_MAX)
AO_CFG_MEZE = {"k": (0.0, 2.0), "r": (0.25, 3.0)}               # AO: sila, dosah (viewer3d.js AO_K_MAX, AO_R_MIN / MAX)
_HEX6 = re.compile(r"#[0-9a-fA-F]{6}")
TTL_S = 5.0
_cache = {"t": 0.0, "v": None}


def prazdny():
    return {"env": None, "alu": None, "ao": None, "sat": None, "barvy": None, "lesk": None, "ao_mat": None, "alu_cfg": None, "ao_cfg": None}


def _cislo(v):
    return not isinstance(v, bool) and isinstance(v, (int, float)) and v == v and v not in (float("inf"), float("-inf"))


def over_env(cfg):
    """Prostredi {hdri, strength, rot_deg, hemi} (vsechny 4 klice povinne, cisla zaokrouhlena na 2 mista) nebo ValueError."""
    if not isinstance(cfg, dict):
        raise ValueError("env musi byt objekt {hdri, strength, rot_deg, hemi} nebo null")
    cizi = set(cfg) - {"hdri", "strength", "rot_deg", "hemi"}
    if cizi:
        raise ValueError("env: neznamy klic " + ", ".join(sorted(map(str, cizi))))
    klice = ENV_HDRI + v3d_env_import.extra_klice()
    if cfg.get("hdri") not in klice:
        klice = ENV_HDRI + v3d_env_import.extra_klice(force=True)        # prave doplnene HDRI jeste nemusi byt v cache tohoto workeru
    if cfg.get("hdri") not in klice:
        raise ValueError("env.hdri musi byt jedno z: " + ", ".join(klice))
    out = {"hdri": cfg["hdri"]}
    for k, (lo, hi) in ENV_MEZE.items():
        v = cfg.get(k)
        if not _cislo(v):
            raise ValueError("env.%s musi byt cislo" % k)
        if not lo <= v <= hi:
            raise ValueError("env.%s %s je mimo rozsah %g az %g" % (k, v, lo, hi))
        out[k] = round(float(v), 2)
    return out


def over_barvy(b):
    """{"#puvodni": "#nova"} (sRGB hex, vstup libovolna velikost pismen, ulozi se male; dvojice se stejnou barvou se zahodi; max BARVY_MAX) -> dict | None (prazdne) nebo ValueError."""
    if not isinstance(b, dict):
        raise ValueError("barvy musi byt objekt {\"#puvodni\": \"#nova\"} nebo null")
    if len(b) > BARVY_MAX:
        raise ValueError("barvy: nejvyse %d dvojic" % BARVY_MAX)
    out = {}
    for k, v in b.items():
        if not (isinstance(k, str) and isinstance(v, str) and _HEX6.fullmatch(k) and _HEX6.fullmatch(v)):
            raise ValueError("barvy: klic i hodnota musi mit tvar #rrggbb")
        if k.lower() != v.lower():
            out[k.lower()] = v.lower()
    return out or None


def _over_hex_nasobky(b, jmeno, meze):
    """{"#puvodni": nasobek v mezich} (sRGB hex, ulozi se male; 1 = beze zmeny se zahodi; max BARVY_MAX; cisla na 2 mista) -> dict | None (prazdne) nebo ValueError."""
    if not isinstance(b, dict):
        raise ValueError("%s musi byt objekt {\"#puvodni\": cislo} nebo null" % jmeno)
    if len(b) > BARVY_MAX:
        raise ValueError("%s: nejvyse %d materialu" % (jmeno, BARVY_MAX))
    out = {}
    for k, v in b.items():
        if not (isinstance(k, str) and _HEX6.fullmatch(k)):
            raise ValueError("%s: klic musi mit tvar #rrggbb" % jmeno)
        if not _cislo(v) or not meze[0] <= v <= meze[1]:
            raise ValueError("%s: hodnota musi byt cislo %g az %g (1 = beze zmeny)" % ((jmeno,) + tuple(meze)))
        v = round(float(v), 2)
        if v != 1.0:
            out[k.lower()] = v
    return out or None


def over_lesk(b):
    """Lesk materialu {"#puvodni": nasobek 0-2} -> dict | None nebo ValueError (viz _over_hex_nasobky)."""
    return _over_hex_nasobky(b, "lesk", LESK_MEZE)


def over_ao_mat(b):
    """AO po komponentech {"#puvodni": vaha AO 0-2} -> dict | None nebo ValueError (viz _over_hex_nasobky)."""
    return _over_hex_nasobky(b, "ao_mat", AO_MAT_MEZE)


def over_nasobky(cfg, meze, jmeno):
    """{klic: cislo} s klici z `meze` (kazdy nepovinny, chybejici = 1), cisla v mezich, na 2 mista; vsechno 1 = None (vychozi) nebo ValueError."""
    if not isinstance(cfg, dict):
        raise ValueError("%s musi byt objekt {%s} nebo null" % (jmeno, ", ".join(meze)))
    cizi = set(cfg) - set(meze)
    if cizi:
        raise ValueError("%s: neznamy klic %s" % (jmeno, ", ".join(sorted(map(str, cizi)))))
    out = {}
    for k, (lo, hi) in meze.items():
        v = cfg.get(k, 1.0)
        if not _cislo(v) or not lo <= v <= hi:
            raise ValueError("%s.%s musi byt cislo %g az %g (1 = beze zmeny)" % (jmeno, k, lo, hi))
        out[k] = round(float(v), 2)
    return None if all(v == 1.0 for v in out.values()) else out


def over_vzhled(body):
    """Cele telo PUT -> normalizovany {env, alu, ao, sat, barvy, lesk, ao_mat, alu_cfg, ao_cfg} (chybejici klic = null = vychozi) nebo ValueError. `None` = vsechno vychozi."""
    if body is None:
        return prazdny()
    if not isinstance(body, dict):
        raise ValueError("telo musi byt JSON objekt {env, alu, ao, sat, barvy, lesk, ao_mat, alu_cfg, ao_cfg} nebo null")
    cizi = set(body) - {"env", "alu", "ao", "sat", "barvy", "lesk", "ao_mat", "alu_cfg", "ao_cfg"}
    if cizi:
        raise ValueError("neznamy klic " + ", ".join(sorted(map(str, cizi))))
    out = prazdny()
    if body.get("env") is not None:
        out["env"] = over_env(body["env"])
    for k, povolene in (("alu", ALU), ("ao", AO)):
        v = body.get(k)
        if v is not None:
            if not isinstance(v, str) or v not in povolene:
                raise ValueError("%s musi byt jedno z: %s" % (k, ", ".join(povolene)))
            out[k] = v
    if body.get("sat") is not None:
        v = body["sat"]
        if not _cislo(v) or not SAT_MEZE[0] <= v <= SAT_MEZE[1]:
            raise ValueError("sat musi byt cislo %g az %g (1 = beze zmeny)" % SAT_MEZE)
        v = round(float(v), 2)
        out["sat"] = None if v == 1.0 else v
    if body.get("barvy") is not None:
        out["barvy"] = over_barvy(body["barvy"])
    if body.get("lesk") is not None:
        out["lesk"] = over_lesk(body["lesk"])
    if body.get("ao_mat") is not None:
        out["ao_mat"] = over_ao_mat(body["ao_mat"])
    if body.get("alu_cfg") is not None:
        out["alu_cfg"] = over_nasobky(body["alu_cfg"], ALU_CFG_MEZE, "alu_cfg")
    if body.get("ao_cfg") is not None:
        out["ao_cfg"] = over_nasobky(body["ao_cfg"], AO_CFG_MEZE, "ao_cfg")
    return out


def nacti_vzhled(force=False):
    """Ulozeny vzhled nabidek (dict {env, alu, ao, sat, barvy, lesk, ao_mat, alu_cfg, ao_cfg}); nikdy nevyhodi: chybna / chybejici hodnota = vychozi (verejna stranka nabidky nesmi spadnout)."""
    ted = time.time()
    if not force and _cache["v"] is not None and ted - _cache["t"] < TTL_S:
        return dict(_cache["v"])
    v = prazdny()
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC,))
                r = cur.fetchone()
        finally:
            conn.close()
        if r and r.get("setting_value"):
            v = over_vzhled(json.loads(r["setting_value"]))
    except Exception as e:                                      # noqa: BLE001
        app.logger.warning("v3d vzhled nabidek: ulozenou hodnotu nejde nacist, plati vychozi: %s", e)
        v = prazdny()
    _cache["t"], _cache["v"] = ted, v
    return dict(v)


def uloz_vzhled(v):
    """Ulozi (v po over_vzhled) nebo SMAZE (vsechno null) ulozeny vzhled. Vraci ulozenou hodnotu."""
    if v == prazdny():
        sql, args = "DELETE FROM app_settings WHERE setting_key=%s", (KLIC,)
    else:
        val = json.dumps(v, sort_keys=True)
        sql, args = "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s", (KLIC, val, val)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        conn.commit()
    finally:
        conn.close()
    _cache["t"], _cache["v"] = time.time(), dict(v)
    return dict(v)


@app.get("/api/public/v3d-vzhled")
def v3d_vzhled_get():
    """Verejne: ulozeny vzhled online nabidek {env, alu, ao, sat, barvy, lesk, ao_mat, alu_cfg, ao_cfg} (null = vychozi) + hdri_extra (doplnena HDRI). Zadna data nabidky ani zakaznika."""
    d = nacti_vzhled()
    d["hdri_extra"] = v3d_env_import.public_extra()               # HDRI doplnena ze Sdileneho disku [{key, label, mul0, rot0_deg, url, lo}] (viewer: V3D.addEnvLibrary)
    resp = jsonify(d)
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.put("/api/admin/v3d-vzhled")
@require_permission("nastaveni", "upravit")
def v3d_vzhled_put():
    """Admin-only: ulozi vzhled online nabidek (HDRI, povrch hliniku, AO, sytost, barvy a lesk materialu, AO po komponentech, odlesky hliniku, sila a dosah AO) pro VSECHNY nabidky; telo `null` = vratit vychozi. Mimo meze / neznamy klic = 400."""
    raw = request.get_data(as_text=True).strip()
    if raw == "null":
        body = None
    else:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "telo musi byt JSON objekt {env, alu, ao, sat, barvy, lesk, ao_mat, alu_cfg, ao_cfg} nebo null"}), 400
    try:
        v = over_vzhled(body)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    ulozeno = uloz_vzhled(v)
    u = current_user()
    log_audit(u["id"] if u else None, "update", "v3d_vzhled", None, {"vzhled": ulozeno})
    return jsonify(ulozeno)
