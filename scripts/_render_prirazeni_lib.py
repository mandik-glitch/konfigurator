"""Sdilene funkce pro prirazeni materialu/HDRi k testovacim i automatickym
Vandr renderum (Robert 2026-09-28: prirazovaci panel v adminu). Puvodne
zdvojene v 2026-09-24_render_hdri_test_dispatch.py, vycleneno sem, kdyz
pribyl druhy pouzivatel (2026-09-23_vandr_render_auto_dispatch.py, --
zatrzitko "platne i pro automatickou linku renderu").
"""
import glob
import hashlib
import json
import os
import re
import struct
import subprocess
import tempfile
import time

REPO = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + "scripts", 1)[0]
DRIVE_FILES_DIR = os.path.join(REPO, "private-files", "shared-drive")
NASTAVENI_APP_SETTINGS_KLIC = "render_prirazeni_materialu"
VANDR_GLB_GLOB = os.path.join(REPO, "webapp", "katalog", "vandr", "*.glb")
# Rodiny s vlastnim, specialnim radkem v panelu (hlinik = --alu-material,
# celo supliku = --klt-material s rozmerovym filtrem) - v obecne tabulce
# "kazdy material jeden radek" se proto nevypisuji znovu.
RODINY_SE_SPECIALNIM_RADKEM = {"alu", "tyrkys"}


# Typ dilu (Robert 2026-09-28: "jeden materiál je pro boxy KLT i pro
# Multiboxy - pokud to tady bude sloučené, nikdy to nepůjde reálně rozdělit
# v renderu"). Typ = komponenta z Unity/vanDrawee exportu (uzel pod
# colliders/left|right/Nohy..., napr. "PoliceMultibox81357459(Clone)",
# "VysuvKLT41471357459closed"), rozpoznana podle KLICOVEHO SLOVA - prvni
# shoda pri pruchodu retezcem predku OD KORENE dolu (vc. jmena dilu
# samotneho). POZOR na poradi: specifictejsi slova pred obecnejsimi
# ("policemultibox" obsahuje i "police"). STEJNY seznam a pravidlo musi
# drzet api/blender_render_turntable.py (_typ_dilu) i webapp/kontrola.html
# (typDilu) - jinak by tabulka, 3D nahled a render rozdelovaly jinak.
TYPY_DILU = [
    ("multibox", "multibox", "Police s Multiboxy"),
    ("vysuvklt", "vysuvklt", "Výsuv KLT (KLT box)"),
    ("vysuveurobox", "vysuveurobox", "Výsuv Eurobox"),
    ("kufrik", "kufrik", "Kufřík"),
    ("boxpolice", "boxpolice", "Box police"),
    ("suplik", "suplik", "Šuplík"),
    ("drawer", "suplik", "Šuplík"),           # starsi exporty bez komponenty Suplik*
    ("policedoor", "policedoor", "Police s dvířky"),
    ("doorfloor", "doorfloor", "Dvířková podlaha"),
    ("frontfloor", "frontfloor", "Přední podlážka"),
    ("upinaci", "upinaci", "Upínací plocha"),
    ("zavetrovani", "zavetrovani", "Zavětrování"),
    ("pricka", "pricka", "Příčka"),
    ("stul", "stul", "Stůl"),
    ("ramsikmy", "ramsikmy", "Šikmý rám"),
    ("bocniram", "bocniram", "Boční rám"),
    ("noha", "noha", "Noha"),
    ("popruh", "popruh", "Popruh"),
    ("legsbox", "legsbox", "LegsBox"),
    ("police", "police", "Police"),
    ("logo", "logo", "Vodoznak vanDrawee"),
    ("podlaha", "podlaha", "Podlaha"),
]
NAZEV_TYPU = {t: n for _k, t, n in TYPY_DILU}
NAZEV_TYPU[""] = "ostatní díly"


def typ_dilu(retezec_jmen):
    """retezec_jmen = jmena uzlu od korene k dilu (vc. dilu). -> id typu
    nebo "" (nezarazeno)."""
    for jmeno in retezec_jmen:
        t = (jmeno or "").lower()
        for klic, typ, _nazev in TYPY_DILU:
            if klic in t:
                return typ
    return ""


# Role dilu (Robert 2026-09-28: "v různých sestavách mají multiboxy různý
# materiál") = skupina, pod kterou Unity/vanDrawee export dil uklada (uzel
# PRIMO nad meshem: "Multibox_Arc.015", "drawer.002", "dark_grey_bin"...).
# Na rozdil od jmena materialu je napric sestavami KONZISTENTNI: prihradky
# Multibox jsou vzdy pod "Multibox_Arc", i kdyz maji material "blue KLT"
# (190 kusu) nebo "multibox" (Vito). Klic = jen pismena bez "(Clone)" -
# stejny vysledek z puvodniho jmena (Blender: "Multibox_Arc.015"), z verze
# s mezerou ("Multibox Arc") i z three.js (GLTFLoader tecky maze a
# duplicitam pridava "_1"). STEJNE pravidlo: api/blender_render_turntable.py
# _role_dilu, webapp/kontrola.html roleDilu.
NAZEV_ROLE = {
    "multiboxarc": "Multiboxy (přihrádky)",
    "drawer": "Čelo šuplíku",
    "darkgreybin": "Tmavé boxy",
    "plasttyrkys": "Tyrkysový plast",
    "blueklt": "Modré díly (blue_klt)",
    "plastgr": "Šedý plast",
    "black": "Černé díly",
    "alu": "Hliník",
    "preklizkahl": "Překližka",
    "sroub": "Šrouby, trubky (chrom)",
    "default": "Těla šuplíků a ostatní (Default)",
    "red": "Červené díly",
    "zinc": "Zinek",
    "orange": "Oranžové díly",
    "bila": "Bílý plast",
    "layer": "Layer_01",
    "logo": "Vodoznak vanDrawee",
    "podlaha": "Podlaha",
}
# role se specialnim radkem (hlinik = --alu-material, celo = --klt-material)
# nebo v renderu skryte (vynechat_objekty) - v obecne tabulce roli nejsou
ROLE_MIMO_TABULKU = {"alu", "drawer", "logo", "podlaha"}


def role_dilu(jmeno_rodice):
    """Jmeno skupiny primo nad dilem -> klic role (jen mala pismena)."""
    n = re.sub(r"\(clone\)", "", jmeno_rodice or "", flags=re.I).lower()
    return re.sub(r"[^a-z]", "", n)


def rodina_materialu(jmeno):
    """'CUB seda (Instance).003' -> 'CUB seda' (puvodni velikost pismen).
    Stejne pravidlo jako api/blender_render_turntable._rodina_materialu
    (ta porovnava lowercase)."""
    n = (jmeno or "").strip()
    n = re.sub(r"\s*\(instance\).*$", "", n, flags=re.I)
    n = re.sub(r"\.\d{3}$", "", n)
    return n


_rodiny_cache = {"cas": 0.0, "data": None, "po_glb": None, "po_glb_typy": None, "role": None, "po_glb_role": None}


def _nacti_rodiny(max_stari_s):
    """Jeden pruchod vsemi Vandr GLB (jen JSON hlavicka, ne geometrie) ->
    (seznam rodin, {"vandr/<soubor>.glb": set(rodin)},
     {"vandr/<soubor>.glb": set((rodina, typ_dilu))}). Cache 10 min."""
    if _rodiny_cache["data"] is not None and time.time() - _rodiny_cache["cas"] < max_stari_s:
        return _rodiny_cache["data"], _rodiny_cache["po_glb"], _rodiny_cache["po_glb_typy"]
    v_kolika, vyskytu, po_glb, po_glb_typy, typy_rodiny = {}, {}, {}, {}, {}
    role_sestav, role_dilu_n, role_rodiny, role_typy, po_glb_role = {}, {}, {}, {}, {}
    for f in glob.glob(VANDR_GLB_GLOB):
        try:
            with open(f, "rb") as fh:
                fh.read(12)
                delka, _typ = struct.unpack("<I4s", fh.read(8))
                js = json.loads(fh.read(delka))
        except (OSError, ValueError, struct.error):
            continue
        materialy = js.get("materials", [])
        videne = set()
        for m in materialy:
            r = rodina_materialu(m.get("name", ""))
            if not r:
                continue
            vyskytu[r] = vyskytu.get(r, 0) + 1
            videne.add(r)
        for r in videne:
            v_kolika[r] = v_kolika.get(r, 0) + 1
        klic_glb = "vandr/" + os.path.basename(f)
        po_glb[klic_glb] = videne
        # typ dilu kazdeho meshe (retezec predku od korene, viz typ_dilu)
        uzly, meshe = js.get("nodes", []), js.get("meshes", [])
        rodic = {c: i for i, u in enumerate(uzly) for c in u.get("children", [])}
        vt, vr = set(), set()
        for i, u in enumerate(uzly):
            if u.get("mesh") is None or u["mesh"] >= len(meshe):
                continue
            retez, j = [u.get("name") or ""], i
            while j in rodic:
                j = rodic[j]
                retez.append(uzly[j].get("name") or "")
            typ = typ_dilu(retez[::-1])
            role = role_dilu(retez[1]) if len(retez) > 1 else ""
            for p in meshe[u["mesh"]].get("primitives", []):
                mi = p.get("material")
                if mi is None or mi >= len(materialy):
                    continue
                r = rodina_materialu(materialy[mi].get("name", ""))
                if r:
                    vt.add((r, typ))
                if role:
                    vr.add((role, typ))
                    role_dilu_n[role] = role_dilu_n.get(role, 0) + 1
                    role_rodiny.setdefault(role, {})
                    if r:
                        role_rodiny[role][r] = role_rodiny[role].get(r, 0) + 1
        po_glb_typy[klic_glb] = vt
        po_glb_role[klic_glb] = vr
        for role in {x for x, _t in vr}:
            role_sestav[role] = role_sestav.get(role, 0) + 1
        for role, typ in vr:
            role_typy.setdefault(role, {})
            role_typy[role][typ] = role_typy[role].get(typ, 0) + 1
        for r, typ in vt:
            typy_rodiny.setdefault(r, {})
            typy_rodiny[r][typ] = typy_rodiny[r].get(typ, 0) + 1
    data = sorted(({"rodina": r, "sestav": v_kolika[r], "vyskytu": vyskytu[r],
                    "typy": sorted(({"typ": t, "nazev": NAZEV_TYPU.get(t, t), "sestav": n}
                                    for t, n in typy_rodiny.get(r, {}).items()),
                                   key=lambda x: (-x["sestav"], x["nazev"]))}
                   for r in v_kolika),
                  key=lambda x: (-x["sestav"], x["rodina"].lower()))
    role = sorted(({"role": ro, "nazev": NAZEV_ROLE.get(ro, ro), "sestav": role_sestav[ro],
                    "dilu": role_dilu_n.get(ro, 0),
                    "rodiny": [k for k, _v in sorted(role_rodiny.get(ro, {}).items(), key=lambda kv: -kv[1])][:4],
                    "typy": sorted(({"typ": t, "nazev": NAZEV_TYPU.get(t, t), "sestav": n}
                                    for t, n in role_typy.get(ro, {}).items()),
                                   key=lambda x: (-x["sestav"], x["nazev"]))}
                   for ro in role_sestav),
                  key=lambda x: (-x["sestav"], x["role"]))
    _rodiny_cache.update(cas=time.time(), data=data, po_glb=po_glb, po_glb_typy=po_glb_typy,
                         role=role, po_glb_role=po_glb_role)
    return data, po_glb, po_glb_typy


def vandr_glb_rodiny(max_stari_s=600):
    """{"vandr/<soubor>.glb": set(rodin)} pro vsechny Vandr GLB."""
    return _nacti_rodiny(max_stari_s)[1]


def vandr_glb_rodiny_typy(max_stari_s=600):
    """{"vandr/<soubor>.glb": set((rodina, typ_dilu))} pro vsechny Vandr GLB."""
    return _nacti_rodiny(max_stari_s)[2]


def pokryti_roli_sestavami(max_stari_s=600):
    """Jako pokryti_rodin_sestavami, ale podle ROLI dilu z tabulky (bez
    ROLE_MIMO_TABULKU) - vychozi 3D nahled = sestava s nejvic rolemi.
    [(glb_file, set_roli_v_nem, set_nove_pridanych)]."""
    _nacti_rodiny(max_stari_s)
    po = {g: {ro for ro, _t in v if ro not in ROLE_MIMO_TABULKU} for g, v in _rodiny_cache["po_glb_role"].items()}
    zbyva = set().union(*po.values()) if po else set()
    velikost = {g: os.path.getsize(os.path.join(REPO, "webapp", "katalog", g)) for g in po}
    vyber = []
    while zbyva:
        g = max(po, key=lambda k: (len(po[k] & zbyva), -velikost[k]))
        nove = po[g] & zbyva
        if not nove:
            break
        vyber.append((g, po[g], nove))
        zbyva -= nove
    return vyber


def role_dilu_vandr(max_stari_s=600):
    """Role dilu (viz NAZEV_ROLE) vc. typu komponent, serazene podle sestav."""
    _nacti_rodiny(max_stari_s)
    return _rodiny_cache["role"]


def vandr_glb_role(max_stari_s=600):
    """{"vandr/<soubor>.glb": set((role, typ_dilu))} pro vsechny Vandr GLB."""
    _nacti_rodiny(max_stari_s)
    return _rodiny_cache["po_glb_role"]


def rodiny_materialu_vandr(max_stari_s=600):
    """Vsechny rodiny materialu, ktere se v Vandr GLB skutecne vyskytuji,
    serazene podle poctu sestav. [{rodina, sestav, vyskytu}]."""
    return _nacti_rodiny(max_stari_s)[0]


def pokryti_rodin_sestavami(max_stari_s=600):
    """Robert 2026-09-28 ("vykreslit celou sestavu, takovou která obsahuje
    všechny materiály"): zadna JEDINA sestava nema vsechny rodiny, proto
    hladove pokryti - nejdriv GLB s nejvic rodinami, pak vzdy ten, ktery
    prida nejvic dosud chybejicich (pri shode mensi soubor). Vraci
    [(glb_file, set_vsech_rodin_v_nem, set_nove_pridanych)] v tomhle poradi;
    prvni polozka = vychozi 3D nahled v panelu."""
    _, po_glb, _ = _nacti_rodiny(max_stari_s)
    zbyva = set().union(*po_glb.values()) if po_glb else set()
    velikost = {g: os.path.getsize(os.path.join(REPO, "webapp", "katalog", g)) for g in po_glb}
    vyber = []
    while zbyva:
        g = max(po_glb, key=lambda k: (len(po_glb[k] & zbyva), -velikost[k]))
        nove = po_glb[g] & zbyva
        if not nove:
            break
        vyber.append((g, po_glb[g], nove))
        zbyva -= nove
    return vyber


def cesta_k_souboru_podle_jmena(cur, jmeno):
    """Knihovna/HDRi se zada JMENEM souboru (ne id) - hleda se NEJPRVE
    kdekoli na Sdilenem disku (posledni nahrany s tim jmenem vyhrava), pak
    v nasich vlastnich testovacich knihovnach mimo disk."""
    cur.execute("SELECT stored_filename FROM shared_drive_files WHERE filename=%s ORDER BY id DESC LIMIT 1", (jmeno,))
    row = cur.fetchone()
    if row:
        cesta = os.path.realpath(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]))
        if os.path.isfile(cesta):
            return cesta
    for kandidat in (
        os.path.join(REPO, "private-files", "alu_test", jmeno),
        os.path.join(REPO, "scripts", "2026-09-21_vd_materialy", jmeno),
    ):
        if os.path.isfile(kandidat):
            return kandidat
    return None


def cesta_k_souboru_podle_id(cur, file_id):
    """HDRi se v panelu vybira ze <select> (id souboru, ne jmeno - stejny
    princip jako aktivni_hdri_cesta() v api/render_hdri.py, jen tady bez
    zavislosti na tom modulu)."""
    if not file_id:
        return None
    cur.execute("SELECT stored_filename FROM shared_drive_files WHERE id=%s", (file_id,))
    row = cur.fetchone()
    if not row:
        return None
    cesta = os.path.realpath(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]))
    return cesta if os.path.isfile(cesta) else None


SLOUCENE_KNIHOVNY_DIR = os.path.join(REPO, "private-files", "alu_test")
SLOUCENE_KNIHOVNY_STARE_DNY = 7      # slouceny soubor, ktery se tolik dni nepouzil (cache hit mu obnovuje cas), se smaze


def _uklid_stare_knihovny(adresar, dny):
    """Best-effort: smaze STARE docasne slouceniny (tmp*.blend z drivejska, knihovna_*.blend z cache), ktere se `dny` dni
    nepouzily. Nesaha na nic jineho (rucni testovaci soubory vd_materialy_*.blend ve stejne slozce zustavaji)."""
    hranice = time.time() - dny * 86400
    for vzor in ("tmp*.blend", "knihovna_*.blend"):
        for f in glob.glob(os.path.join(adresar, vzor)):
            try:
                if os.path.getmtime(f) < hranice:
                    os.remove(f)
            except OSError:
                pass


def sestav_material_knihovnu(dvojice):
    """dvojice = [(popisek, cesta_souboru), ...] - kdyz je jen JEDEN
    unikatni zdrojovy soubor, vrati ho beze zmeny; kdyz vic ruznych, slouci
    je do jedne knihovny (fake_user, at materialy prezijou ulozeni -
    jinak by je Blender s 0 uzivateli tise zahodil, zjisteno 2026-09-28).

    CACHE (bot4 2026-10-02): slouceny soubor se jmenuje knihovna_<otisk>.blend, otisk = cesty + cas zmeny + velikost
    zdroju, a pri stejnem vstupu se POUZIJE ZNOVU (Blender se nespousti). Drive se pro KAZDE zarazeni vyrobil novy
    tmp*.blend (13-25 MB, ~10 s CPU) a nikdy se nesmazal - za 4 dny 303 souboru / 5,4 GB a disk /opt na 97 %; s renderem
    nabidky (2 zarazeni na nabidku) by to rostlo dal. Zdroje se zmeni -> novy otisk -> nova slouceniny. Stare (viz
    SLOUCENE_KNIHOVNY_STARE_DNY) se uklizi pri vyrobe nove."""
    soubory = sorted({cesta for _, cesta in dvojice if cesta})
    if not soubory:
        return None
    if len(soubory) == 1:
        return soubory[0]
    adresar = SLOUCENE_KNIHOVNY_DIR
    otisk = hashlib.sha1("|".join("%s:%d:%d" % (z, int(os.path.getmtime(z)), os.path.getsize(z)) for z in soubory)
                         .encode("utf-8")).hexdigest()[:16]
    hotovo = os.path.join(adresar, "knihovna_%s.blend" % otisk)
    try:
        if os.path.getsize(hotovo) > 0:
            os.utime(hotovo, None)         # drzi cerstvou, at ji uklid nesmaze, dokud se pouziva
            return hotovo
    except OSError:
        pass
    skript = ("import bpy, sys\n"
              "zdroje = sys.argv[sys.argv.index('--') + 1:-1]\n"
              "vystup = sys.argv[-1]\n"
              "for z in zdroje:\n"
              "    with bpy.data.libraries.load(z, link=False) as (data_from, data_to):\n"
              "        data_to.materials = list(data_from.materials)\n"
              "for m in bpy.data.materials:\n"
              "    m.use_fake_user = True\n"
              "bpy.ops.wm.save_as_mainfile(filepath=vystup)\n")
    fd, skript_cesta = tempfile.mkstemp(suffix=".py")
    os.write(fd, skript.encode("utf-8"))
    os.close(fd)
    docasny = "%s.%d.tmpbuild.blend" % (hotovo[:-len(".blend")], os.getpid())
    try:
        subprocess.run(["/opt/blender-5.2/blender", "--background", "--python", skript_cesta,
                        "--", *soubory, docasny], check=True, capture_output=True, timeout=120)
        os.replace(docasny, hotovo)        # atomicky - soubezne zarazeni nikdy neuvidi pulku
        try:
            os.chmod(hotovo, 0o644)
        except OSError:
            pass
    finally:
        os.remove(skript_cesta)
        for zbytek in (docasny, docasny + "1"):
            try:
                os.remove(zbytek)
            except OSError:
                pass
    _uklid_stare_knihovny(adresar, SLOUCENE_KNIHOVNY_STARE_DNY)
    return hotovo


_MATERIALY_CACHE_SOUBOR = os.path.join(REPO, "private-files", "render_materialy_v_knihovnach.json")


def _cache_nacti():
    try:
        with open(_MATERIALY_CACHE_SOUBOR, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _cache_uloz(cache):
    try:
        tmp = "%s.%d.tmp" % (_MATERIALY_CACHE_SOUBOR, os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp, _MATERIALY_CACHE_SOUBOR)
    except OSError:
        pass   # cache je jen zrychleni, bez ni se knihovna precte znovu


def materialy_v_knihovne(cesta):
    """Nazvy materialu v .blend knihovne (Blender na pozadi, soubor jen cte).
    Vysledek se pamatuje na disku podle cesty + casu zmeny souboru (cteni
    trva ~2 s - ulozeni tabulky kontroluje kazdy radek)."""
    try:
        klic = "%s|%s" % (cesta, os.path.getmtime(cesta))
    except OSError:
        klic = None
    if klic:
        cache = _cache_nacti()
        if klic in cache:
            return list(cache[klic])
    nazvy = _materialy_v_knihovne_blenderem(cesta)
    if klic and nazvy:
        cache = _cache_nacti()
        cache[klic] = nazvy
        _cache_uloz(cache)
    return nazvy


def _materialy_v_knihovne_blenderem(cesta):
    skript = ("import bpy, sys\n"
              "with bpy.data.libraries.load(sys.argv[-1], link=False) as (data_from, data_to):\n"
              "    print('MATERIALY|' + '|'.join(data_from.materials))\n")
    fd, skript_cesta = tempfile.mkstemp(suffix=".py")
    os.write(fd, skript.encode("utf-8"))
    os.close(fd)
    try:
        out = subprocess.run(["/opt/blender-5.2/blender", "--background", "--factory-startup",
                              "--python", skript_cesta, "--", cesta],
                             capture_output=True, text=True, timeout=120).stdout
    finally:
        os.remove(skript_cesta)
    for radek in out.splitlines():
        if radek.startswith("MATERIALY|"):
            return [m for m in radek.split("|")[1:] if m]
    return []


_SVETLA_SKRIPT = os.path.join(REPO, "scripts", "2026-09-09_vps_dilna", "extrahuj_svetla.py")


def svetla_v_souboru(cesta):
    """Svetla z .blend souboru (Robert 2026-09-29: "nastaveni svetel podle
    nejakeho souboru", X1_SCENA.blend) jako dict {"svetla": [...],
    "kamera_azimut_deg": ...}. Blender na pozadi, soubor jen cte; vysledek
    se pamatuje podle cesty + casu zmeny (stejna cache jako materialy).
    None = soubor nejde precist. Prazdny seznam svetel je platny vysledek
    (soubor ma jen svet) - volajici ho ma odmitnout hlasite."""
    try:
        klic = "svetla2|%s|%s" % (cesta, os.path.getmtime(cesta))
    except OSError:
        return None
    cache = _cache_nacti()
    if isinstance(cache.get(klic), dict):
        return cache[klic]
    try:
        out = subprocess.run(["/opt/blender-5.2/blender", "--background", "--factory-startup", cesta,
                              "--python", _SVETLA_SKRIPT],
                             capture_output=True, text=True, timeout=180).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for radek in out.splitlines():
        if radek.startswith("SVETLA_JSON|"):
            try:
                data = json.loads(radek.split("|", 1)[1])
            except ValueError:
                return None
            cache = _cache_nacti()
            cache[klic] = data
            _cache_uloz(cache)
            return data
    return None


def svetla_zapnuta(n):
    """Zatrzitko 'svetla ze souboru' v panelu (Robert 2026-09-30): svetla se
    pouziji jen s vyplnenym souborem A zatrzitkem. Stary ulozeny stav bez
    klice `svetla_aktivni` = zapnuto, je-li soubor vyplneny."""
    return bool(str(n.get("svetla_soubor") or "").strip()) and n.get("svetla_aktivni", True) is not False


SVETLA_VYCHOZI_POCET = 2


def svetla_vychozi_jmena(svetla):
    """Robert 2026-09-30 ("nech jen 2 svetla"): kdyz panel nema ulozeny vyber,
    pouziji se 2 nejsilnejsi svetla souboru (pri shode vykonu to drive v souboru).
    Jmena v poradi, jak jsou v souboru."""
    poradi = sorted(range(len(svetla)), key=lambda i: (-(svetla[i].get("vykon") or 0), i))
    zvolena = set(poradi[:SVETLA_VYCHOZI_POCET])
    return [sv["jmeno"] for i, sv in enumerate(svetla) if i in zvolena]


def svetla_vybrana_jmena(n, svetla, chyby, soubor=""):
    """Jmena svetel, ktera se maji v renderu pouzit: ulozeny vyber panelu
    (`svetla_vybrana`), jinak vychozi 2 nejsilnejsi. Vyber, ktery neodpovida
    souboru (svetlo v nem neni, prazdny seznam), je hlasita chyba - None + text
    v `chyby`, ne tiche pouziti jinych svetel."""
    vyber = n.get("svetla_vybrana")
    if vyber is None:
        return svetla_vychozi_jmena(svetla)
    if not isinstance(vyber, list) or not vyber or not all(isinstance(j, str) for j in vyber):
        chyby.append("vyber svetel v panelu je poskozeny nebo prazdny - zaskrtni aspon jedno svetlo")
        return None
    existujici = [sv["jmeno"] for sv in svetla]
    chybi = [j for j in vyber if j not in existujici]
    if chybi:
        chyby.append("vybrane svetlo '%s' v souboru '%s' neni (jsou tam: %s)"
                     % ("', '".join(chybi), soubor, ", ".join(existujici)))
        return None
    return [j for j in existujici if j in vyber]


def svetla_args(cur, n, chyby):
    """Nastaveni "svetla podle souboru" -> ["--svetla-blend", cesta, ...].
    Prazdne nebo vypnute = [] (vestavene osvetleni beze zmeny). None + text
    v `chyby`, kdyz soubor chybi / nema zadne svetlo - render se pak MA
    preskocit, ne poslat s tise ignorovanym prepinacem."""
    if not svetla_zapnuta(n):
        return []
    jmeno = str(n.get("svetla_soubor") or "").strip()
    cesta = cesta_k_souboru_podle_jmena(cur, jmeno)
    if cesta is None:
        chyby.append("soubor se svetly '%s' nenalezen" % jmeno)
        return None
    data = svetla_v_souboru(cesta)
    if data is None:
        chyby.append("soubor se svetly '%s' nejde precist" % jmeno)
        return None
    if not data.get("svetla"):
        chyby.append("soubor se svetly '%s' neobsahuje zadne svetlo (viditelne v renderu)" % jmeno)
        return None
    vybrana = svetla_vybrana_jmena(n, data["svetla"], chyby, jmeno)
    if vybrana is None:
        return None
    args = ["--svetla-blend", cesta]
    for sv_jmeno in vybrana:
        args.append("--svetla-jen=" + sv_jmeno)
    if n.get("svetla_sila") not in (None, ""):
        args += ["--svetla-sila", str(n["svetla_sila"])]
    return args


def _normalizuj_nazev(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def material_z_knihovny(jmeno_souboru, cesta, chyby):
    """Robert 2026-09-28 vyplnuje jen knihovnu (Multibox.blend, Suplik_celo.blend)
    bez nazvu materialu - material se vezme z ni: stejne pojmenovany jako
    soubor (PM_Blue.blend -> "PM Blue"), jinak jediny krome obecneho
    "Material". None + text v `chyby`, kdyz to nejde jednoznacne urcit."""
    materialy = materialy_v_knihovne(cesta)
    kmen = _normalizuj_nazev(os.path.splitext(jmeno_souboru)[0])
    shoda = [m for m in materialy if _normalizuj_nazev(m) == kmen]
    if len(shoda) == 1:
        return shoda[0]
    vlastni = [m for m in materialy if _normalizuj_nazev(m) != "material"]
    if len(vlastni) == 1:
        return vlastni[0]
    chyby.append("knihovna '%s': nejde poznat, ktery material pouzit (%s) - dopis nazev do sloupce material"
                 % (jmeno_souboru, ", ".join(materialy) or "zadny material"))
    return None


def urci_material_v_knihovne(jmeno_souboru, cesta, zadany, chyby):
    """Transparentni tabulka (Robert 2026-09-29: "proto jsme delali
    priradovaci tabulku aby vsechno fungovalo transparentne"): nazev
    materialu z tabulky se MUSI najit v zadanem souboru, jinak Blender tise
    nechal puvodni material z modelu (cela suplíku/KLT zustala svetle modra,
    protoze v tabulce bylo 'klt1', v souboru 'KLT1', a 'modrecelo' tam
    nebylo vubec). Vraci PRESNY nazev z knihovny (velikost pismen a mezery
    v nazvu nehraji roli), nebo None + text v `chyby`. Prazdny nazev = z
    knihovny (material_z_knihovny)."""
    zadany = (zadany or "").strip()
    if not zadany:
        return material_z_knihovny(jmeno_souboru, cesta, chyby)
    materialy = materialy_v_knihovne(cesta)
    if zadany in materialy:
        return zadany
    shoda = [m for m in materialy if _normalizuj_nazev(m) == _normalizuj_nazev(zadany)]
    if len(shoda) == 1:
        return shoda[0]
    chyby.append("knihovna '%s' nema material '%s' - obsahuje: %s. Vyber nazev z knihovny "
                 "nebo nech pole material prazdne." % (jmeno_souboru, zadany, ", ".join(materialy) or "zadny material"))
    return None


def zkontroluj_kolize_nazvu(dvojice, chyby):
    """Dva ruzne soubory se stejne pojmenovanym materialem (napr. 'Grey' v
    grey.blend i modrecelo.blend) se pri slouceni do jedne knihovny
    prejmenuji ('Grey.001') a render by tise vzal ten druhy. True = v poradku."""
    podle_jmena = {}
    for material, cesta in dvojice:
        if material == "__ostatni__":
            continue
        podle_jmena.setdefault(material, set()).add(cesta)
    kolize = [m for m, cesty in podle_jmena.items() if len(cesty) > 1]
    if kolize:
        chyby.append("material '%s' je ve vice ruznych souborech knihoven - render by nevedel, ktery vzit"
                     % "', '".join(kolize))
        return False
    return True


def material_args_z_nastaveni(cur, n, chyby):
    """n = dict s klici alu_material/alu_knihovna_soubor/klt_material/
    klt_knihovna_soubor/ostatni_knihovna_soubor/cub_seda_tmava_sila/
    alu_ao_sila/hdri_sila/hdri_rotace_deg/svetla_soubor/svetla_sila (chybejici/prazdne = beze zmeny).
    Pripoji textovy popis chyby do `chyby` (list) a vrati None, kdyz neco
    (knihovna) chybi na disku - volajici pak MA cely render preskocit,
    ne ho poslat s tise nefunkcnim prepinacem."""
    args = []
    dvojice_knihoven = []
    # Knihovna staci - prazdny nazev materialu = vezme se z knihovny
    # (material_z_knihovny), Robert 2026-09-28 "ulozit nefunguje".
    for klic_mat, klic_kn, prepinac, popis in (
            ("alu_material", "alu_knihovna_soubor", "--alu-material", "hlinik"),
            ("klt_material", "klt_knihovna_soubor", "--klt-material", "celo supliku")):
        knihovna = (n.get(klic_kn) or "").strip()
        if not knihovna:
            continue
        cesta = cesta_k_souboru_podle_jmena(cur, knihovna)
        if cesta is None:
            chyby.append("knihovna '%s' (%s) nenalezena" % (knihovna, popis))
            return None
        material = urci_material_v_knihovne(knihovna, cesta, n.get(klic_mat), chyby)
        if material is None:
            return None
        dvojice_knihoven.append((material, cesta))
        args += [prepinac, material]
    if n.get("ostatni_knihovna_soubor"):
        cesta = cesta_k_souboru_podle_jmena(cur, n["ostatni_knihovna_soubor"])
        if cesta is None:
            chyby.append("knihovna '%s' (ostatni dily) nenalezena" % n["ostatni_knihovna_soubor"])
            return None
        dvojice_knihoven.append(("__ostatni__", cesta))
    vysledek = nahrady_args(cur, n.get("nahrady"), chyby)
    if vysledek is None:
        return None
    args += vysledek[0]
    dvojice_knihoven += vysledek[1]
    if not zkontroluj_kolize_nazvu(dvojice_knihoven, chyby):
        return None
    if dvojice_knihoven:
        knihovna = sestav_material_knihovnu(dvojice_knihoven)
        args += ["--vd-knihovna", knihovna]
    if n.get("kryci_listy_skryt"):
        args += ["--kryci-listy-pruhledne"]
    # Robert 2026-09-28: nevyplneny radek = material, co si dil nese z modelu
    args += ["--vd-puvodni-nevyplnene"]
    if n.get("hdri_file_id"):
        cesta = cesta_k_souboru_podle_id(cur, n["hdri_file_id"])
        if cesta is None:
            chyby.append("HDRi soubor (id %s) nenalezen" % n["hdri_file_id"])
            return None
        args += ["--hdri", cesta]
    if n.get("cub_seda_tmava_sila") not in (None, ""):
        args += ["--cub-seda-tmava-sila", str(n["cub_seda_tmava_sila"])]
    if n.get("alu_ao_sila") not in (None, ""):
        args += ["--alu-ao-sila", str(n["alu_ao_sila"])]
    if n.get("hdri_sila") not in (None, ""):
        args += ["--hdri-sila", str(n["hdri_sila"])]
    if n.get("hdri_rotace_deg") not in (None, ""):
        args += ["--hdri-rotace-deg", str(n["hdri_rotace_deg"])]
    sv = svetla_args(cur, n, chyby)
    if sv is None:
        return None
    args += sv
    return args


def nahrady_args(cur, nahrady, chyby):
    """"Kazdy material jeden radek" (Robert 2026-09-28): [{rodina, material,
    knihovna_soubor}] -> (["--vd-nahrada", "RODINA=MATERIAL", ...],
    [(material, cesta_knihovny), ...]). Knihovna muze chybet - material se
    pak hleda ve vychozi vd_materialy.blend (napr. "VD_BLACK"). None + text
    v `chyby`, kdyz zadana knihovna na disku neni."""
    args, dvojice = [], []
    for radek in (nahrady or []):
        if not isinstance(radek, dict):
            continue
        rodina = (radek.get("rodina") or "").strip()
        role = (radek.get("role") or "").strip().lower()
        material = (radek.get("material") or "").strip()
        typ = (radek.get("typ") or "").strip().lower()
        knihovna = (radek.get("knihovna_soubor") or "").strip()
        if not (rodina or role) or not (material or knihovna):
            continue
        if knihovna:
            cesta = cesta_k_souboru_podle_jmena(cur, knihovna)
            if cesta is None:
                chyby.append("knihovna '%s' (%s) nenalezena" % (knihovna, role or rodina))
                return None
            material = urci_material_v_knihovne(knihovna, cesta, material, chyby)
            if material is None:
                return None
            dvojice.append((material, cesta))
        if role:
            args += ["--vd-role", "%s%s=%s" % (role, ("@" + typ) if typ else "", material)]
        else:
            args += ["--vd-nahrada", "%s%s=%s" % (rodina, ("@" + typ) if typ else "", material)]
    return args, dvojice


def nacti_ulozene_nastaveni(cur):
    """Ulozeny stav panelu (app_settings) jako dict, {} pri jakekoli chybe -
    nikdy nevyhazuje (vola ho i 10s automat testovacich renderu)."""
    try:
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                    (NASTAVENI_APP_SETTINGS_KLIC,))
        row = cur.fetchone()
        n = json.loads(row["setting_value"]) if row and row.get("setting_value") else {}
        return n if isinstance(n, dict) else {}
    except Exception as e:
        print("PRIRAZENI: ulozene nastaveni nejde precist (%s) - bez radku tabulky" % e)
        return {}


class PrirazeniNeplatne(Exception):
    """Ulozeny stav panelu neodpovida realite (chybi soubor, svetlo, material...).
    Automat kvuli tomu NESMI potichu renderovat bez prepisu panelu - volajici
    ma zarazeni odmitnout a chybu zapsat (pravidlo: neshoda = hlasita chyba)."""


def nacti_nastaveni_pro_automat(cur):
    """Precte trvale ulozene prirazeni z app_settings - vrati PRAZDNY
    seznam (zadne prepisy), kdyz nastaveni chybi, je necitelne, NEBO kdyz
    zatrzitko 'aktivni_pro_automat' neni zaskrtnute. Nastaveni, ktere je
    zapnute, ale NEODPOVIDA realite (soubor/svetlo/material se nenasel),
    vyhodi `PrirazeniNeplatne` - ne tichy navrat bez prepisu, ktery by
    zahodil CELY panel (materialy, HDRI, svetla). Jina vyjimka (vypadek DB)
    ~= 'zadny prepis', produkcni automat na tom nesmi spadnout."""
    try:
        import json
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (NASTAVENI_APP_SETTINGS_KLIC,))
        row = cur.fetchone()
        if not row or not row.get("setting_value"):
            return []
        n = json.loads(row["setting_value"])
        if not isinstance(n, dict) or not n.get("aktivni_pro_automat"):
            return []
        chyby = []
        args = material_args_z_nastaveni(cur, n, chyby)
        if args is None:
            raise PrirazeniNeplatne("; ".join(chyby))
        return args
    except PrirazeniNeplatne:
        raise
    except Exception as e:
        print("PRIRAZENI PRO AUTOMAT: chyba cteni (%s) - render pokracuje bez prepisu" % e)
        return []


# ---------------------------------------------------------------------------------------------------------------
# Ucinna prirazovaci tabulka renderovacich materialu KATALOGU (bot10, 2026-10-01; Robert: "vsechny polozky katalogu
# mimo karoserie -> material z knihovny Vandr materialu"). TABULKY: sql/2026-10-01_render_materialy.sql
# (render_materialy, render_material_casti, sloupec render_material_key na shop_products/cfg_dily/content_categories).
# SPRAVA: admin panel (api/render_materialy.py + webapp/admin/js/render-materialy-katalogu.js).
#
# TENHLE BLOK NIC NEZAPOJUJE: resolve_parts() (scripts/2026-09-09_turntable_job.py) ho zatim NEVOLA, takze se material
# zadne karty nemeni. Zapojeni = az po dohode s bot4 (pred i po spustit test_nabidka_api.py + test_nabidka_cli.py).
# I po zapojeni plati `app_settings.render_materialy_katalogu_aktivni` (vychozi VYPNUTO, jen se CTE - pravidlo 50):
# dokud neni '1', render_material_key() vraci None = chovani jako dnes.
#
# POKUD CHYBI TABULKA/SLOUPEC, DB spadne nebo cokoli jineho: vraci se None (= "beze zmeny"), NIKDY vyjimka - tuhle
# funkci bude volat produkcni render/nabidka a nesmi ji shodit.
RENDER_MATERIALY_FLAG = "render_materialy_katalogu_aktivni"
RENDER_MATERIALY_ZDROJE = ("product", "cfg")
# poradi, v jakem se hleda klic (prvni neprazdny vyhrava); "vychozi" = zadny klic -> None (beze zmeny)
PORADI_ODKUD = ("cast", "karta", "cfg", "kategorie", "mapa", "vychozi")
# Mapa barev/vrstev na klic = posledni zaloha pro polozky bez vlastniho klice (nove karty). Jen jednoznacna pravidla
# z analyzy 2026-10-01: zinek #4d4d4d/#575c62 -> grey, cerna/guma -> black, hlinik (layer=alu) -> alumi2 vzdy.
# Sporne barvy (plotny, MDF #494b50, #63656a...) ZAMERNE chybi - ty rozhodne Robert v adminu.
MAPA_LAYER_NA_KLIC = {"alu": "alumi2"}
MAPA_HEX_NA_KLIC = {
    "#4d4d4d": "grey", "#575c62": "grey",
    "#242424": "black", "#1c1c1e": "black", "#202224": "black", "#1a1a1a": "black",
}
_PRAVDIVE_HODNOTY = ("1", "true", "ano", "on", "yes")
_MAX_HLOUBKA_KATEGORII = 15


def _klic_text(v):
    """Klic materialu z hodnoty ze DB/vstupu: orezany retezec nebo None (None, prazdne, ne-text)."""
    if v is None:
        return None
    try:
        if isinstance(v, bytes):
            v = v.decode("utf-8", "replace")
        v = str(v).strip()
    except Exception:
        return None
    return v or None


def _hex_text(v):
    h = _klic_text(v)
    if not h:
        return None
    h = h.lower()
    return h if re.fullmatch(r"#[0-9a-f]{6}", h) else None


def vyres_klic(cast=None, karta=None, cfg=None, kategorie=None, hex_barva=None, layer=None, navrh_stav=None):
    """CISTE rozhodnuti (bez DB): prvni neprazdny z (cast, karta, cfg, kategorie), pak mapa vrstvy/barvy, jinak
    (None, "vychozi"). Vraci (klic | None, odkud) kde odkud je z PORADI_ODKUD. Nikdy nevyhazuje.
    navrh_stav 'SPORNE' / 'VYNECHANO' (render_material_navrh): polozka, o ktere zatim nerozhodl Robert / ktera se
    nema menit - mapa vrstvy/barvy se pro ni NEPOUZIJE (zustava beze zmeny, dokud nema vlastni klic)."""
    try:
        for odkud, hodnota in (("cast", cast), ("karta", karta), ("cfg", cfg), ("kategorie", kategorie)):
            k = _klic_text(hodnota)
            if k:
                return k, odkud
        if _klic_text(navrh_stav) in ("SPORNE", "VYNECHANO"):
            return None, "vychozi"
        vrstva = (_klic_text(layer) or "").lower()
        if vrstva in MAPA_LAYER_NA_KLIC:
            return MAPA_LAYER_NA_KLIC[vrstva], "mapa"
        h = _hex_text(hex_barva)
        if h and h in MAPA_HEX_NA_KLIC:
            return MAPA_HEX_NA_KLIC[h], "mapa"
    except Exception:
        pass
    return None, "vychozi"


def _radek_hodnota(row, jmeno, index):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(jmeno)
    try:
        return row[index]
    except Exception:
        return None


def _sql_radek(cur, sql, params=()):
    """Jeden radek nebo None; jakakoli chyba (chybejici tabulka/sloupec, vypadek DB) = None."""
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    except Exception:
        return None


def _sql_radky(cur, sql, params=()):
    try:
        cur.execute(sql, params)
        return list(cur.fetchall() or [])
    except Exception:
        return []


def render_materialy_zapnuto(cur):
    """True jen kdyz app_settings.render_materialy_katalogu_aktivni je '1'/'true'/'ano'. Jen CTE. Chybi/chyba = False."""
    row = _sql_radek(cur, "SELECT setting_value FROM app_settings WHERE setting_key=%s", (RENDER_MATERIALY_FLAG,))
    v = _klic_text(_radek_hodnota(row, "setting_value", 0))
    return bool(v) and v.lower() in _PRAVDIVE_HODNOTY


def render_material_knihovna(cur, klic):
    """Radek knihovny materialu {klic, nazev_blender, knihovna_soubor, knihovna_file_id, aktivni} nebo None
    (neexistuje / tabulka chybi). Pro zapojeni do renderu: z klice se tim zjisti material a soubor knihovny."""
    k = _klic_text(klic)
    if not k:
        return None
    row = _sql_radek(cur, "SELECT klic, nazev_blender, knihovna_soubor, knihovna_file_id, aktivni "
                          "FROM render_materialy WHERE klic=%s", (k,))
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(zip(("klic", "nazev_blender", "knihovna_soubor", "knihovna_file_id", "aktivni"), row))
    except Exception:
        return None


def render_material_casti(cur, zdroj, dil_id):
    """{mesh_klic: klic} - material po castech vicetelesoveho dilu ({} kdyz zadny / tabulka chybi)."""
    if zdroj not in RENDER_MATERIALY_ZDROJE or dil_id is None:
        return {}
    out = {}
    for r in _sql_radky(cur, "SELECT mesh_klic, render_material_key FROM render_material_casti "
                             "WHERE zdroj=%s AND dil_id=%s", (zdroj, str(dil_id))):
        m, k = _klic_text(_radek_hodnota(r, "mesh_klic", 0)), _klic_text(_radek_hodnota(r, "render_material_key", 1))
        if m and k:
            out[m] = k
    return out


def _klic_kategorie(cur, category_id):
    """Vlastni klic nejblizsi nadrazene kategorie (NULL u kategorie = dedit od rodice); (klic, nazev) | (None, None)."""
    videno = set()
    cid = category_id
    for _ in range(_MAX_HLOUBKA_KATEGORII):
        if cid is None or cid in videno:
            break
        videno.add(cid)
        row = _sql_radek(cur, "SELECT render_material_key, parent_id, name FROM content_categories WHERE id=%s", (cid,))
        if row is None:
            break
        k = _klic_text(_radek_hodnota(row, "render_material_key", 0))
        if k:
            return k, _radek_hodnota(row, "name", 2)
        cid = _radek_hodnota(row, "parent_id", 1)
    return None, None


def render_material_key(cur, zdroj, dil_id, mesh_klic=None, vyzaduj_flag=True, vysvetli=False):
    """Ucinny klic renderovaciho materialu pro dil katalogu (zdroj 'product' = shop_products.id, 'cfg' = cfg_dily.id).

    Poradi: cast (render_material_casti, jen s mesh_klic) -> karta (shop_products.render_material_key) -> cfg
    (cfg_dily.render_material_key; u karty navazany cfg_dily_id) -> kategorie (nejblizsi nadrazena s klicem) ->
    mapa vrstvy/barvy (MAPA_*) -> None (beze zmeny, material z modelu / dnesni chovani).

    vyzaduj_flag=True (vychozi, pouziva render): kdyz neni zapnuty app_settings.render_materialy_katalogu_aktivni,
    vraci None - zadna zmena materialu. vyzaduj_flag=False = jen pro zobrazeni (admin, kontroly).
    Klic, ktery neni v render_materialy nebo je aktivni=0 (nebo tabulka chybi), se NEPOUZIJE -> None.
    Karta s nativni_material=1 (Vandr sestavy) se nikdy neprepisuje -> None.
    vysvetli=True vraci (klic, odkud) kde odkud je z PORADI_ODKUD, nebo "vypnuto", "nativni", "neplatny:<klic>",
    "chyba". NIKDY nevyhazuje vyjimku (i s None kurzorem / nesmyslnymi vstupy)."""
    def _ven(k, odkud):
        return (k, odkud) if vysvetli else k
    try:
        if cur is None or zdroj not in RENDER_MATERIALY_ZDROJE or dil_id is None:
            return _ven(None, "chyba")
        if vyzaduj_flag and not render_materialy_zapnuto(cur):
            return _ven(None, "vypnuto")
        did = str(dil_id)
        kcast = kkarta = kcfg = kkat = None
        hexb = layer = None
        category_id = None
        if mesh_klic:
            r = _sql_radek(cur, "SELECT render_material_key FROM render_material_casti "
                                "WHERE zdroj=%s AND dil_id=%s AND mesh_klic=%s", (zdroj, did, str(mesh_klic)))
            kcast = _radek_hodnota(r, "render_material_key", 0)
        cfg_id = None
        if zdroj == "product":
            r = _sql_radek(cur, "SELECT render_material_key, cfg_dily_id, category_id, color_hex, nativni_material "
                                "FROM shop_products WHERE id=%s", (did,))
            if r is None:
                return _ven(None, "chyba")
            if _radek_hodnota(r, "nativni_material", 4):
                return _ven(None, "nativni")
            kkarta = _radek_hodnota(r, "render_material_key", 0)
            cfg_id = _klic_text(_radek_hodnota(r, "cfg_dily_id", 1))
            category_id = _radek_hodnota(r, "category_id", 2)
            hexb = _radek_hodnota(r, "color_hex", 3)
        else:
            cfg_id = did
        if cfg_id:
            r = _sql_radek(cur, "SELECT render_material_key, layer, color_hex FROM cfg_dily WHERE id=%s", (cfg_id,))
            if r is not None:
                kcfg = _radek_hodnota(r, "render_material_key", 0)
                layer = _radek_hodnota(r, "layer", 1)
                if not _hex_text(hexb):
                    hexb = _radek_hodnota(r, "color_hex", 2)
        if category_id is not None and not (_klic_text(kcast) or _klic_text(kkarta) or _klic_text(kcfg)):
            kkat, _nazev = _klic_kategorie(cur, category_id)
        r = _sql_radek(cur, "SELECT stav FROM render_material_navrh WHERE zdroj=%s AND dil_id=%s", (zdroj, did))
        navrh_stav = _radek_hodnota(r, "stav", 0)
        klic, odkud = vyres_klic(kcast, kkarta, kcfg, kkat, hexb, layer, navrh_stav)
        if klic is None:
            return _ven(None, odkud)
        mat = render_material_knihovna(cur, klic)
        if mat is None or not mat.get("aktivni"):
            return _ven(None, "neplatny:%s" % klic)
        return _ven(_klic_text(mat.get("klic")) or klic, odkud)
    except Exception:
        return _ven(None, "chyba")


def render_material_pro_dil(cur, zdroj, dil_id, mesh_klic=None):
    """Material katalogu pro render dilu: {"nazev": "<nazev_blender>", "knihovna": "<cesta .blend>"} nebo None.

    Kontrakt s resolve_parts (bot4, 2026-10-02): vraci None = dil zustava po starem (dnesni vypocet z vrstvy/barvy).
    None kdyz: flag render_materialy_katalogu_aktivni je vypnuty (vychozi), dil nema ucinny klic / je SPORNY,
    klic neni v render_materialy nebo je aktivni=0, soubor knihovny chybi na Sdilenem disku (typicky cub_seda.blend
    a bila.blend, dokud je Robert nenahraje) nebo cokoli selze. NIKDY nevyhazuje vyjimku, nic nezapisuje do DB."""
    try:
        klic = render_material_key(cur, zdroj, dil_id, mesh_klic)
        if not klic:
            return None
        mat = render_material_knihovna(cur, klic)
        if not mat or not mat.get("aktivni"):
            return None
        nazev = mat.get("nazev_blender")
        if not nazev:
            return None
        cesta = None
        if mat.get("knihovna_file_id"):
            cesta = cesta_k_souboru_podle_id(cur, mat["knihovna_file_id"])
        if not cesta and mat.get("knihovna_soubor"):
            cesta = cesta_k_souboru_podle_jmena(cur, mat["knihovna_soubor"])
        if not cesta:
            return None
        return {"nazev": nazev, "knihovna": cesta}
    except Exception:
        return None
