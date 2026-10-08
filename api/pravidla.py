"""Přehledy > Pravidla/Postupy (bot9, 2026-09-12, zadání Robert přes bot3,
upřesněno Robertem přímo v chatu týž den).

Cíl: administrace má ukazovat pravidla/postupy, které Robert osobně
považuje za nejdůležitější, ale NESMÍ vzniknout druhá, nezávislá kopie
OBSAHU vedle `.md` souborů v rootu repa - přesně tahle třída chyby (dva
zdroje pravdy pro totéž, co se tiše rozejdou) způsobila ranní bug s
`is_public` na kategoriích. Robert výslovně: "nechci dva zdroje pravdy
pro totéž".

Robert (chat, 2026-09-12) k původnímu návrhu "ukázat všech ~16 souborů
najednou" upřesnil:
  * "nechceme tisíce řádků v adminu"
  * "souhlasím s živým čtením z md souborů ale jen důležité věci"
  * "navrhuji aby jsi mi předkládal jednotlivé postupy jestli se mají
    zobrazovat v přehledech pro admina, vyberu si např. odkliknutím"

Řešení = DVĚ vrstvy, obě bez duplikace OBSAHU:
  1. Kandidáti (`_sestav_kandidaty()`) - živě naparsovaní z `.md` souborů
     při každém requestu, stejně jako v prvním návrhu. Zrnitost SMÍŠENÁ
     (Robertova volba): u dvou velkých "živých seznamů pravidel"
     (WORKFLOW.md sekce "AKTIVNÍ POKYNY OD ROBERTA" a
     VLASTNOSTI_PROFILU.md sekce "⭐ Nadřazená pravidla") se kandidát
     dělá PER JEDNOTLIVÝ BOD (rozdělení na odstavce podle prázdného
     řádku - funguje bez ohledu na to, jestli bod začíná `**tučně**`
     nebo číslem, viz `_rozparcuj_na_bloky()`), u ostatních souborů je
     kandidát CELÝ SOUBOR (s krátkým popisem z rozcestníku, ne s celým
     obsahem - viz bod 2).
  2. Výběr (`pravidla_vyber`, sql/2026-09-12_pravidla_vyber.sql) - JEDINÁ
     věc, která se ukládá do DB, je Robertovo zaškrtnutí "zobrazit ano/
     ne" pro daný `klic` kandidáta. Text pravidla/postupu se do DB
     NEKOPÍRUJE nikdy - i u vybraných položek se při zobrazení čte znovu
     živě ze souboru.

`klic` u "pravidlo" kandidátů je POZIČNÍ (`SOUBOR#index` v rámci dané
sekce) - stabilní vůči editaci textu existujícího bodu, ALE posune se,
když někdo NOVÝ bod vloží doprostřed už procházené sekce (ne na konec).
Vědomý kompromis - jednodušší než pokoušet se o obsahový fingerprint,
který by se zase rozjel při běžné opravě překlepu. Robert dělá výběr
mnohem prakticky - ojedinělé posunutí pozná podle textu vedle checkboxu.

Vyloučeno z kandidátů úplně (schváleno bot3/Robert 2026-09-12):
`TASKS.md`, `STAV.md`, `AGENTS_LOG.md` - živé STAVOVÉ přehledy/log, ne
pravidla/postupy. Neparsuje se transitivně (viz `pravidla.py` historie
v gitu pro dřívější širší návrh) - jen CLAUDE.md rozcestník +
VLASTNOSTI_PROFILU.md "Kde co najdeš" + jeho "⭐ Nadřazená pravidla" +
WORKFLOW.md "AKTIVNÍ POKYNY OD ROBERTA" + PRAVIDLA_SPOJU.md (celý po
sekcích, viz `_pravidlove_kandidaty`), nic víc.

Doplněno 2026-09-15 (Robert přes bot3 - "kompletní tabulka stávajících
pravidel napříč projektem", po dvou případech, kdy se na existující
pravidlo zapomnělo): `TEXT_FILTR.md` (číslované 1-15, stejný rozpad na
odstavce jako u WORKFLOW.md) a `PLAN_TVORBY_SESTAV.md` (klíčová "⭐"
rozhodnutí rozeseta napříč celým dokumentem, ne pod jedním nadpisem -
viz `_hvezdickove_kandidaty`). `VANDR_*`/`PRODUKTOVE_RENDERY.md`
zůstávají kandidát "celý soubor" (menší, tematicky ucelené, nemají
číslovaný seznam jako tyhle dva).

Třetí zdroj kandidátů (Robert, chat, 2026-09-12 - "určitě tam chci mít
shape_geometry_methods a související"): `_db_recept_kandidaty()` čte
ŽIVĚ tabulky `shape_geometry_methods`/`car_body_placement_methods` -
STEJNÝ princip jako u `.md` souborů (žádná kopie `definition` JSON do
`pravidla_vyber`, jen klíč `tabulka#id` a checkbox). Přesně tyhle dvě
tabulky jsou podle `VLASTNOSTI_PROFILU.md` už dnes "DB jako zdroj
pravdy pro čísla" - tenhle modul k nim jen přidává admin pohled, ne
druhou cestu, jak se k nim dostat.
"""
import os
import re
import subprocess

from flask import jsonify, request

from app import app, get_conn, require_permission, current_user, log_audit

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VYNECHAT = {"TASKS.md", "STAV.md", "AGENTS_LOG.md"}

# Tyhle soubory se NEUKAZUJÍ jako kandidát "celý soubor" - jsou to buď
# čistý rozcestník (VLASTNOSTI_PROFILU.md) nebo příliš velké/pestré na
# jeden checkbox (WORKFLOW.md, TEXT_FILTR.md, PLAN_TVORBY_SESTAV.md) -
# místo toho se rozpadají na "pravidlo" kandidáty, viz
# _pravidlove_kandidaty() a _hvezdickove_kandidaty().
BEZ_CELEHO_SOUBORU = {
    "WORKFLOW.md", "VLASTNOSTI_PROFILU.md", "PRAVIDLA_SPOJU.md",
    "TEXT_FILTR.md", "PLAN_TVORBY_SESTAV.md",
}

# Tabulky se strukturovanymi recepty (JSON `definition`) - "DB jako
# zdroj pravdy pro cisla", viz VLASTNOSTI_PROFILU.md posledni radek.
DB_REPTABULKY = ("shape_geometry_methods", "car_body_placement_methods")

_MD_ODKAZ_RE = re.compile(r"`([A-Za-z0-9_-]+\.md)`")
_POLOZKA_RE = re.compile(r"^\d+\.\s", re.MULTILINE)


def _precti(nazev):
    cesta = os.path.join(REPO_ROOT, nazev)
    if not os.path.isfile(cesta):
        return None
    with open(cesta, "r", encoding="utf-8") as f:
        return f.read()


def _posledni_commit(nazev):
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", nazev],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def _rozpadni_tesny_seznam(blok):
    """Pomocník pro `_rozparcuj_na_bloky`: pokud blok obsahuje NĚKOLIK
    řádků začínajících "- " na sloupci 0 (těsný odrážkový seznam BEZ
    prázdných řádků mezi položkami, viz VLASTNOSTI_PROFILU.md "⭐
    Nadřazená pravidla"), rozdělí ho na jednotlivé odrážky. Jinak (proza
    bez odrážek, nebo jen jedna) vrátí blok beze změny."""
    radky = blok.split("\n")
    if sum(1 for r in radky if r.startswith("- ")) < 2:
        return [blok]
    casti, aktualni = [], []
    for radek in radky:
        if radek.startswith("- ") and aktualni:
            casti.append("\n".join(aktualni).strip())
            aktualni = []
        aktualni.append(radek)
    if aktualni:
        casti.append("\n".join(aktualni).strip())
    return [c for c in casti if c]


def _rozparcuj_na_bloky(text):
    """Odstavce oddělené prázdným řádkem - funguje bez ohledu na to, jestli
    blok začíná `**tučně**`, číslem, nebo obyčejnou větou (viz docstring
    modulu - AKTIVNÍ POKYNY nejsou formátované jednotně). Každý výsledný
    odstavec se navíc zkusí rozpadnout na těsný seznam, viz
    `_rozpadni_tesny_seznam` (jinak by "⭐ Nadřazená pravidla" v
    VLASTNOSTI_PROFILU.md vyšla jako JEDEN blok - žádné prázdné řádky
    mezi jejími odrážkami)."""
    odstavce = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    vysledek = []
    for odstavec in odstavce:
        vysledek.extend(_rozpadni_tesny_seznam(odstavec))
    return vysledek


def _rozcestnik_claude_md():
    """[(popis_md, [soubory...]), ...] pro každou číslovanou položku
    sekce "Než začneš pracovat" v CLAUDE.md, v původním pořadí."""
    obsah = _precti("CLAUDE.md")
    if not obsah:
        return []
    m = re.search(r"## Než začneš pracovat.*?\n(.*?)\n## ", obsah, re.DOTALL)
    if not m:
        return []
    sekce = m.group(1)
    zacatky = [m2.start() for m2 in _POLOZKA_RE.finditer(sekce)] + [len(sekce)]
    polozky = []
    for i in range(len(zacatky) - 1):
        blok = sekce[zacatky[i]:zacatky[i + 1]].strip()
        soubory = [s for s in _MD_ODKAZ_RE.findall(blok) if s not in VYNECHAT]
        if soubory:
            polozky.append((blok, soubory))
    return polozky


def _vlastnosti_profilu_podsoubory():
    """[(popis_md, soubor), ...] ze sekce "Kde co najdeš" v
    VLASTNOSTI_PROFILU.md - jeden řádek seznamu na tematický soubor."""
    obsah = _precti("VLASTNOSTI_PROFILU.md")
    if not obsah:
        return []
    m = re.search(r"## Kde co najdeš\n(.*?)\n\n", obsah, re.DOTALL)
    if not m:
        return []
    vysledek = []
    for radek in m.group(1).splitlines():
        radek = radek.strip()
        if not radek.startswith("-"):
            continue
        soubory = _MD_ODKAZ_RE.findall(radek)
        if soubory:
            vysledek.append((radek.lstrip("- ").strip(), soubory[0]))
    return vysledek


def _souborove_kandidaty():
    """Kandidáti typu "soubor" - CELÝ soubor je jedna položka k výběru,
    popis je krátký (z rozcestníku), ne celý obsah (viz modul docstring
    bod 2 - obsah se posílá zvlášť, na vyžádání, přes soubor_obsah())."""
    kandidati = []
    videne = set()
    for popis_md, soubory in _rozcestnik_claude_md():
        for soubor in soubory:
            if soubor in videne or soubor in BEZ_CELEHO_SOUBORU:
                continue
            videne.add(soubor)
            if _precti(soubor) is None:
                continue
            kandidati.append({
                "klic": soubor, "typ": "soubor", "soubor": soubor,
                "skupina": None, "text_md": popis_md,
                "posledni_commit": _posledni_commit(soubor),
            })
    for pod_popis, pod_soubor in _vlastnosti_profilu_podsoubory():
        if pod_soubor in videne or pod_soubor in BEZ_CELEHO_SOUBORU:
            continue
        videne.add(pod_soubor)
        if _precti(pod_soubor) is None:
            continue
        kandidati.append({
            "klic": pod_soubor, "typ": "soubor", "soubor": pod_soubor,
            "skupina": "VLASTNOSTI_PROFILU.md", "text_md": pod_popis,
            "posledni_commit": _posledni_commit(pod_soubor),
        })
    return kandidati


def _md_sekce(soubor):
    """[(nadpis, text), ...] pro každou '## ' sekci (ne '###' a hlubší) v
    souboru, v původním pořadí - obecný rozpad na nadpisy nejvyšší úrovně
    pod titulkem (`# Nadpis`)."""
    obsah = _precti(soubor)
    if not obsah:
        return []
    casti = re.split(r"\n(?=## [^#])", "\n" + obsah)
    vysledek = []
    for cast in casti:
        cast = cast.strip("\n")
        if not cast.startswith("## "):
            continue
        prvni_radek, _, zbytek = cast.partition("\n")
        vysledek.append((prvni_radek[3:].strip(), zbytek.strip()))
    return vysledek


def _pravidlove_kandidaty(soubor, rozpadnout_nadpisy, preskocit_nadpisy=()):
    """Kandidáti typu "pravidlo" ze všech '## ' sekcí daného souboru.
    Sekce, jejichž nadpis JE v `rozpadnout_nadpisy`, se navíc rozpadnou
    na jednotlivé odstavce (`_rozparcuj_na_bloky`) - použito pro velké/
    pestré "živé seznamy pravidel" (WORKFLOW.md AKTIVNÍ POKYNY,
    VLASTNOSTI_PROFILU.md ⭐ Nadřazená pravidla). Ostatní sekce (menší,
    tematicky ucelené - např. "Git/zámek disciplína") jsou kandidát CELÉ,
    jedna položka na sekci. `preskocit_nadpisy` = sekce, které nejsou
    pravidlo ale rozcestník (VLASTNOSTI_PROFILU.md "Kde co najdeš" -
    tu už zpracovává `_vlastnosti_profilu_podsoubory()` zvlášť)."""
    kandidati = []
    for nadpis, text in _md_sekce(soubor):
        if not text or nadpis in preskocit_nadpisy:
            continue
        if nadpis in rozpadnout_nadpisy:
            for i, blok in enumerate(_rozparcuj_na_bloky(text)):
                kandidati.append({
                    "klic": f"{soubor}#{nadpis}#{i}", "typ": "pravidlo", "soubor": soubor,
                    "skupina": f"{soubor} — {nadpis}", "text_md": blok,
                    "posledni_commit": _posledni_commit(soubor),
                })
        else:
            kandidati.append({
                "klic": f"{soubor}#{nadpis}", "typ": "pravidlo", "soubor": soubor,
                "skupina": soubor, "text_md": f"**{nadpis}**\n\n{text}",
                "posledni_commit": _posledni_commit(soubor),
            })
    return kandidati


def _hvezdickove_kandidaty(soubor):
    """Kandidáti typu "pravidlo" z klíčových rozhodnutí značených "⭐" v
    CELÉM souboru, napříč všemi sekcemi - na rozdíl od
    `_pravidlove_kandidaty()` (ta rozpadá JEDNU pojmenovanou sekci).
    Použito pro `PLAN_TVORBY_SESTAV.md`: klíčová rozhodnutí jsou
    rozeseta po celém dokumentu (Fáze 1/1b/2/3/4...), ne soustředěná
    pod jedním nadpisem jako u WORKFLOW.md/VLASTNOSTI_PROFILU.md.
    Blok = odstavec oddělený prázdným řádkem (`_rozparcuj_na_bloky`,
    funguje na libovolném textu, ne jen na sekci), který obsahuje "⭐"."""
    obsah = _precti(soubor)
    if not obsah:
        return []
    kandidati = []
    i = 0
    for blok in _rozparcuj_na_bloky(obsah):
        if "⭐" not in blok:
            continue
        kandidati.append({
            "klic": f"{soubor}#hvezda#{i}", "typ": "pravidlo", "soubor": soubor,
            "skupina": f"{soubor} — ⭐ klíčová rozhodnutí", "text_md": blok,
            "posledni_commit": _posledni_commit(soubor),
        })
        i += 1
    return kandidati


def _db_recept_kandidaty():
    """Kandidáti typu "recept" - jeden řádek `shape_geometry_methods`/
    `car_body_placement_methods` je jedna položka. Popis v seznamu je
    krátký (`popis`/`stav` z JSON, ne celá `definition`) - celý recept
    na vyžádání přes `db_recept_obsah()`, stejný princip jako u "soubor"
    kandidátů."""
    import json
    kandidati = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for tabulka in DB_REPTABULKY:
                # `definition` se ctou i tady (ne jen v _nacti_recept) -
                # bez `popis` by nahled v seznamu ukazoval jen nazev/verzi,
                # zadny popis CO recept dela (Robertova zpetna vazba na
                # screenshotu, 2026-09-12: "proc nekde chybi text?").
                cur.execute(
                    f"SELECT id, name, version, verified_by, created_by, created_at, definition "
                    f"FROM {tabulka} ORDER BY id"
                )
                for r in cur.fetchall():
                    try:
                        definice = json.loads(r["definition"]) if r["definition"] else {}
                    except (TypeError, ValueError):
                        definice = {}
                    popis = ""
                    if isinstance(definice, dict):
                        popis = str(definice.get("popis") or definice.get("stav") or "").strip()
                    if len(popis) > 220:
                        popis = popis[:220].rstrip() + "…"
                    hlavicka = (
                        f"verze {r['version']}"
                        + (f", ověřil {r['verified_by']}" if r["verified_by"] else ", zatím neověřeno")
                        + f", zapsal {r['created_by']} {r['created_at'].date().isoformat()}"
                    )
                    kandidati.append({
                        "klic": f"{tabulka}#{r['id']}", "typ": "recept",
                        "soubor": None, "tabulka": tabulka, "recept_id": r["id"],
                        "nazev": r["name"], "skupina": f"DB: {tabulka}",
                        "text_md": f"*{hlavicka}*" + ("\n\n" + popis if popis else ""),
                        "posledni_commit": None,
                    })
    finally:
        conn.close()
    return kandidati


def _nacti_recept(tabulka, recept_id):
    if tabulka not in DB_REPTABULKY:
        return None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {tabulka} WHERE id=%s", (recept_id,))
            return cur.fetchone()
    finally:
        conn.close()


def _sestav_kandidaty():
    kandidati = (
        _pravidlove_kandidaty("WORKFLOW.md", {"AKTIVNÍ POKYNY OD ROBERTA (přečti si PRVNÍ, než cokoliv děláš)"})
        + _pravidlove_kandidaty(
            "VLASTNOSTI_PROFILU.md",
            {"⭐ Nadřazená pravidla (číst PRVNÍ, platí univerzálně pro každý spoj/tvar/profil)"},
            preskocit_nadpisy={"Kde co najdeš"},
        )
        + _pravidlove_kandidaty("PRAVIDLA_SPOJU.md", rozpadnout_nadpisy=set())
        + _pravidlove_kandidaty("TEXT_FILTR.md", {"Rozsah (na co se filtr vztahuje)"})
        + _pravidlove_kandidaty(
            "PLAN_TVORBY_SESTAV.md",
            {"⭐ Pravidla tohoto dokumentu (Robert 2026-09-11)"},
        )
        + _hvezdickove_kandidaty("PLAN_TVORBY_SESTAV.md")
        + _souborove_kandidaty()
        + _db_recept_kandidaty()
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT klic, zobrazit FROM pravidla_vyber")
            vyber = {r["klic"]: bool(r["zobrazit"]) for r in cur.fetchall()}
    finally:
        conn.close()
    for k in kandidati:
        k["zobrazit"] = vyber.get(k["klic"], False)
    return kandidati


@app.get("/api/admin/pravidla-postupy")
@require_permission("nastaveni", "zobrazit")
def admin_pravidla_postupy():
    return jsonify({"items": _sestav_kandidaty()})


@app.get("/api/admin/pravidla-postupy/soubor/<path:nazev>")
@require_permission("nastaveni", "zobrazit")
def admin_pravidla_postupy_soubor(nazev):
    # Whitelist = přesně ty soubory, které _souborove_kandidaty() nabízí -
    # nejde o obecné "přečti mi libovolný soubor z disku" (path traversal).
    povolene = {k["soubor"] for k in _souborove_kandidaty()}
    if nazev not in povolene:
        return jsonify({"error": "Tenhle soubor není v seznamu kandidátů."}), 404
    obsah = _precti(nazev)
    if obsah is None:
        return jsonify({"error": "Soubor nenalezen na disku."}), 404
    return jsonify({"obsah_md": obsah, "posledni_commit": _posledni_commit(nazev)})


def _definice_na_md(definice, uroven=0):
    """Rekurzivní, obecný převod JSON `definition` na čitelný markdown -
    nezávislé na tom, jaké klíče/tvar zrovna který recept používá (v
    DB se to mezi recepty i verzemi liší, viz `_db_recept_kandidaty`
    docstring)."""
    odsazeni = "  " * uroven
    if isinstance(definice, dict):
        radky = []
        for klic, hodnota in definice.items():
            if isinstance(hodnota, (dict, list)):
                radky.append(f"{odsazeni}- **{klic}:**")
                radky.append(_definice_na_md(hodnota, uroven + 1))
            else:
                radky.append(f"{odsazeni}- **{klic}:** {hodnota}")
        return "\n".join(radky)
    if isinstance(definice, list):
        radky = []
        for polozka in definice:
            if isinstance(polozka, (dict, list)):
                radky.append(_definice_na_md(polozka, uroven))
            else:
                radky.append(f"{odsazeni}- {polozka}")
        return "\n".join(radky)
    return f"{odsazeni}{definice}"


@app.get("/api/admin/pravidla-postupy/recept/<tabulka>/<int:recept_id>")
@require_permission("nastaveni", "zobrazit")
def admin_pravidla_postupy_recept(tabulka, recept_id):
    import json
    r = _nacti_recept(tabulka, recept_id)
    if r is None:
        return jsonify({"error": "Recept nenalezen (nebo neplatná tabulka)."}), 404
    try:
        definice = json.loads(r["definition"]) if r["definition"] else {}
    except (TypeError, ValueError):
        definice = {"__chyba__": "definition není platný JSON"}
    obsah_md = (
        f"**{r['name']}** — verze {r['version']}, vytvořil {r['created_by']} "
        f"({r['created_at'].isoformat()}), ověřil: {r['verified_by'] or 'zatím nikdo'}\n\n"
        + _definice_na_md(definice)
    )
    return jsonify({"obsah_md": obsah_md, "posledni_commit": None})


@app.put("/api/admin/pravidla-postupy/vyber")
@require_permission("nastaveni", "upravit")
def admin_pravidla_postupy_vyber():
    body = request.get_json(silent=True) or {}
    klic = (body.get("klic") or "").strip()
    if not klic:
        return jsonify({"error": "Chybí klíč položky."}), 400
    zobrazit = 1 if body.get("zobrazit") else 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pravidla_vyber (klic, zobrazit) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE zobrazit=VALUES(zobrazit)",
                (klic, zobrazit),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "pravidla_vyber", None, "%s -> %s" % (klic, zobrazit))
    return jsonify({"status": "ok"})


# --- Editace receptu primo z adminu (Robert 2026-09-21: "pravidla postupy
# pro geometrii chci mit na nejake tabuli v adminu v prehledu" + "tak abych
# to mohl kdykoli editovat") ------------------------------------------------
#
# Proc se edituje PO CASTECH (jeden klic JSON `definition`), ne cely recept
# jako jeden text: recepty byly 2026-09-21 na Robertuv pokyn rozdeleny "na
# mensi samostatne casti dle vyznamu" prave proto, ze jeden rostouci blob si
# zacal odporovat sam se sebou. Editor te zrnitosti musi odpovidat - jinak by
# se cely recept zase prepisoval najednou.
#
# Kazda zmena: zapise PREDCHOZI zneni do `recept_historie` (rucni editace
# nenechava stopu v gitu, na rozdil od dosavadnich zmen skriptem), povysi
# `version` a zaloguje se do `audit_log`.

_CESTA_ODDELOVAC = "."


def _rozlozit_definici(definice, prefix=""):
    """Rozlozi JSON `definition` na seznam editovatelnych casti. Retezcove
    listy jsou 'text', vse ostatni (dict/list/cislo/bool) se edituje jako
    JSON - aby slo upravit i strukturovany klic, ne jen prozu."""
    casti = []
    if not isinstance(definice, dict):
        return casti
    for klic, hodnota in definice.items():
        cesta = f"{prefix}{klic}"
        if isinstance(hodnota, str):
            casti.append({"cesta": cesta, "typ": "text", "hodnota": hodnota})
        elif isinstance(hodnota, dict):
            casti.append({
                "cesta": cesta, "typ": "skupina",
                "hodnota": "", "podcasti": len(hodnota),
            })
            casti.extend(_rozlozit_definici(hodnota, cesta + _CESTA_ODDELOVAC))
        else:
            import json as _json
            casti.append({
                "cesta": cesta, "typ": "json",
                "hodnota": _json.dumps(hodnota, ensure_ascii=False, indent=1),
            })
    return casti


def _projdi_cestu(definice, cesta, vytvorit=False):
    """Vrati (rodic_dict, posledni_klic) pro danou teckovou cestu."""
    casti = cesta.split(_CESTA_ODDELOVAC)
    uzel = definice
    for klic in casti[:-1]:
        if not isinstance(uzel, dict) or klic not in uzel:
            if not vytvorit:
                return None, None
            uzel[klic] = {}
        uzel = uzel[klic]
        if not isinstance(uzel, dict):
            return None, None
    return uzel, casti[-1]


@app.get("/api/admin/pravidla-postupy/recept/<tabulka>/<int:recept_id>/casti")
@require_permission("nastaveni", "zobrazit")
def admin_recept_casti(tabulka, recept_id):
    import json
    r = _nacti_recept(tabulka, recept_id)
    if r is None:
        return jsonify({"error": "Recept nenalezen (nebo neplatna tabulka)."}), 404
    try:
        definice = json.loads(r["definition"]) if r["definition"] else {}
    except (TypeError, ValueError):
        return jsonify({"error": "definition neni platny JSON - neda se editovat po castech."}), 409
    return jsonify({
        "nazev": r["name"], "verze": r["version"],
        "overil": r["verified_by"], "zapsal": r["created_by"],
        "casti": _rozlozit_definici(definice),
    })


@app.put("/api/admin/pravidla-postupy/recept/<tabulka>/<int:recept_id>/cast")
@require_permission("nastaveni", "upravit")
def admin_recept_upravit_cast(tabulka, recept_id):
    import json
    if tabulka not in DB_REPTABULKY:
        return jsonify({"error": "Neplatna tabulka."}), 400
    body = request.get_json(silent=True) or {}
    cesta = (body.get("cesta") or "").strip()
    akce = (body.get("akce") or "upravit").strip()
    if not cesta:
        return jsonify({"error": "Chybi cesta ke klici."}), 400
    if akce not in ("upravit", "pridat", "smazat"):
        return jsonify({"error": "Neplatna akce."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, name, version, definition FROM {tabulka} WHERE id=%s", (recept_id,))
            r = cur.fetchone()
            if r is None:
                return jsonify({"error": "Recept nenalezen."}), 404
            try:
                definice = json.loads(r["definition"]) if r["definition"] else {}
            except (TypeError, ValueError):
                return jsonify({"error": "definition neni platny JSON."}), 409
            if not isinstance(definice, dict):
                return jsonify({"error": "definition neni objekt."}), 409

            rodic, klic = _projdi_cestu(definice, cesta, vytvorit=(akce == "pridat"))
            if rodic is None:
                return jsonify({"error": f"Cesta '{cesta}' v receptu neexistuje."}), 404

            stara = rodic.get(klic)
            stara_txt = stara if isinstance(stara, str) else (
                json.dumps(stara, ensure_ascii=False) if stara is not None else None)

            if akce == "smazat":
                if klic not in rodic:
                    return jsonify({"error": f"Klic '{cesta}' neexistuje."}), 404
                del rodic[klic]
                nova_txt = None
            else:
                if akce == "pridat" and klic in rodic:
                    return jsonify({"error": f"Klic '{cesta}' uz existuje - pouzij 'upravit'."}), 409
                if akce == "upravit" and klic not in rodic:
                    return jsonify({"error": f"Klic '{cesta}' neexistuje - pouzij 'pridat'."}), 404
                hodnota = body.get("hodnota")
                if hodnota is None:
                    return jsonify({"error": "Chybi hodnota."}), 400
                if body.get("jako_json"):
                    try:
                        hodnota = json.loads(hodnota)
                    except (TypeError, ValueError) as e:
                        return jsonify({"error": f"Hodnota neni platny JSON: {e}"}), 400
                elif not isinstance(hodnota, str):
                    return jsonify({"error": "Hodnota musi byt text."}), 400
                elif not hodnota.strip():
                    return jsonify({"error": "Prazdne pravidlo se neuklada - pouzij smazani."}), 400
                rodic[klic] = hodnota
                nova_txt = hodnota if isinstance(hodnota, str) else json.dumps(hodnota, ensure_ascii=False)

            nova_verze = (r["version"] or 0) + 1
            cur.execute(
                f"UPDATE {tabulka} SET definition=%s, version=%s WHERE id=%s AND version=%s",
                (json.dumps(definice, ensure_ascii=False), nova_verze, recept_id, r["version"]),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return jsonify({"error": "Recept mezitim zmenil nekdo jiny - nacti znovu."}), 409

            u = current_user()
            cur.execute(
                "INSERT INTO recept_historie (tabulka, recept_id, cesta, akce, hodnota_pred, "
                "hodnota_po, verze_pred, verze_po, kdo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (tabulka, recept_id, cesta, akce, stara_txt, nova_txt,
                 r["version"], nova_verze, (u or {}).get("email") or "?"),
            )
        conn.commit()
    finally:
        conn.close()

    log_audit((current_user() or {}).get("id"), f"recept_{akce}", tabulka, recept_id,
              f"{r['name']}: {cesta} (v{r['version']} -> v{nova_verze})")
    return jsonify({"ok": True, "verze": nova_verze})


@app.get("/api/admin/pravidla-postupy/recept/<tabulka>/<int:recept_id>/historie")
@require_permission("nastaveni", "zobrazit")
def admin_recept_historie(tabulka, recept_id):
    if tabulka not in DB_REPTABULKY:
        return jsonify({"error": "Neplatna tabulka."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, cesta, akce, hodnota_pred, hodnota_po, verze_pred, verze_po, kdo, kdy "
                "FROM recept_historie WHERE tabulka=%s AND recept_id=%s ORDER BY id DESC LIMIT 100",
                (tabulka, recept_id),
            )
            radky = cur.fetchall()
    finally:
        conn.close()
    for r in radky:
        if r.get("kdy"):
            r["kdy"] = r["kdy"].isoformat()
    return jsonify({"historie": radky})


@app.post("/api/admin/pravidla-postupy/recept/<tabulka>/<int:recept_id>/vratit/<int:historie_id>")
@require_permission("nastaveni", "upravit")
def admin_recept_vratit(tabulka, recept_id, historie_id):
    """Vrati JEDNU zmenu zpet - zapise puvodni hodnotu z historie. Samo to
    je zase zmena (dalsi radek historie), takze nic nemizi."""
    import json
    if tabulka not in DB_REPTABULKY:
        return jsonify({"error": "Neplatna tabulka."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM recept_historie WHERE id=%s AND tabulka=%s AND recept_id=%s",
                        (historie_id, tabulka, recept_id))
            h = cur.fetchone()
            if h is None:
                return jsonify({"error": "Zaznam historie nenalezen."}), 404
            cur.execute(f"SELECT id, name, version, definition FROM {tabulka} WHERE id=%s", (recept_id,))
            r = cur.fetchone()
            definice = json.loads(r["definition"]) if r["definition"] else {}
            rodic, klic = _projdi_cestu(definice, h["cesta"], vytvorit=True)
            if rodic is None:
                return jsonify({"error": "Cesta uz v receptu neexistuje."}), 409
            stara = rodic.get(klic)
            stara_txt = stara if isinstance(stara, str) else (
                json.dumps(stara, ensure_ascii=False) if stara is not None else None)
            if h["hodnota_pred"] is None:
                rodic.pop(klic, None)
            else:
                rodic[klic] = h["hodnota_pred"]
            nova_verze = (r["version"] or 0) + 1
            cur.execute(f"UPDATE {tabulka} SET definition=%s, version=%s WHERE id=%s AND version=%s",
                        (json.dumps(definice, ensure_ascii=False), nova_verze, recept_id, r["version"]))
            if cur.rowcount != 1:
                conn.rollback()
                return jsonify({"error": "Recept mezitim zmenil nekdo jiny - nacti znovu."}), 409
            u = current_user()
            cur.execute(
                "INSERT INTO recept_historie (tabulka, recept_id, cesta, akce, hodnota_pred, "
                "hodnota_po, verze_pred, verze_po, kdo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (tabulka, recept_id, h["cesta"], "upravit", stara_txt, h["hodnota_pred"],
                 r["version"], nova_verze, ((u or {}).get("email") or "?") + " (vraceni)"),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "verze": nova_verze})


# --- Strom pravidel podle vyznamu (Robert 2026-09-21: "udelej to jako strom,
# podle vyznamu ty pravidla" + "at se stejne shlukuji do jedne vetve") -------
#
# Zarazeni je DATA (sloupec `kategorie`, cesta s lomitkem), ne struktura
# zadratovana v kodu - strom jde prerovnat ze stejne obrazovky jako zneni
# pravidel, bez zasahu do kodu. Prazdna kategorie spadne do "Nezarazene",
# takze se recept nikdy neztrati tim, ze ho nikdo nezaradil.

NEZARAZENE = "Nezařazené"


@app.get("/api/admin/pravidla-postupy/strom")
@require_permission("nastaveni", "zobrazit")
def admin_pravidla_strom():
    import json
    vetve = {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for tabulka in DB_REPTABULKY:
                cur.execute(
                    f"SELECT id, name, version, verified_by, kategorie, poradi, definition "
                    f"FROM {tabulka} ORDER BY poradi, name"
                )
                for r in cur.fetchall():
                    try:
                        definice = json.loads(r["definition"]) if r["definition"] else {}
                    except (TypeError, ValueError):
                        definice = {}
                    popis = ""
                    if isinstance(definice, dict):
                        popis = str(definice.get("popis") or "").strip()
                    if len(popis) > 190:
                        popis = popis[:190].rstrip() + "…"
                    cesta = (r["kategorie"] or "").strip() or NEZARAZENE
                    casti = [c.strip() for c in cesta.split("/") if c.strip()]
                    vetev = casti[0] if casti else NEZARAZENE
                    podvetev = casti[1] if len(casti) > 1 else ""
                    polozka = {
                        "tabulka": tabulka, "id": r["id"], "nazev": r["name"],
                        "verze": r["version"], "overil": r["verified_by"],
                        "kategorie": r["kategorie"] or "", "poradi": r["poradi"],
                        "popis": popis, "klicu": len(definice) if isinstance(definice, dict) else 0,
                    }
                    vetve.setdefault(vetev, {}).setdefault(podvetev, []).append(polozka)
    finally:
        conn.close()

    # Nezarazene vzdy na konec, zbytek abecedne - poradi VETVI zamerne neni
    # dalsi editovatelne pole (jedna os razeni staci, `poradi` uvnitr vetve).
    nazvy = sorted(k for k in vetve if k != NEZARAZENE)
    if NEZARAZENE in vetve:
        nazvy.append(NEZARAZENE)
    strom = [{
        "nazev": v,
        "podvetve": [{"nazev": pv, "recepty": vetve[v][pv]}
                     for pv in sorted(vetve[v], key=lambda x: (x == "", x))],
        "pocet": sum(len(x) for x in vetve[v].values()),
    } for v in nazvy]
    return jsonify({"strom": strom})


@app.put("/api/admin/pravidla-postupy/recept/<tabulka>/<int:recept_id>/kategorie")
@require_permission("nastaveni", "upravit")
def admin_recept_kategorie(tabulka, recept_id):
    if tabulka not in DB_REPTABULKY:
        return jsonify({"error": "Neplatna tabulka."}), 400
    body = request.get_json(silent=True) or {}
    kategorie = (body.get("kategorie") or "").strip()
    if kategorie.count("/") > 1:
        return jsonify({"error": "Strom ma nejvys dve urovne - pouzij jedno lomitko."}), 400
    if len(kategorie) > 120:
        return jsonify({"error": "Zarazeni je moc dlouhe (max 120 znaku)."}), 400
    poradi = body.get("poradi")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT name, kategorie FROM {tabulka} WHERE id=%s", (recept_id,))
            r = cur.fetchone()
            if r is None:
                return jsonify({"error": "Recept nenalezen."}), 404
            if poradi is None:
                cur.execute(f"UPDATE {tabulka} SET kategorie=%s WHERE id=%s",
                            (kategorie or None, recept_id))
            else:
                cur.execute(f"UPDATE {tabulka} SET kategorie=%s, poradi=%s WHERE id=%s",
                            (kategorie or None, int(poradi), recept_id))
            if cur.rowcount != 1:
                conn.rollback()
                return jsonify({"error": "Zarazeni se neulozilo."}), 500
            u = current_user()
            cur.execute(
                "INSERT INTO recept_historie (tabulka, recept_id, cesta, akce, hodnota_pred, "
                "hodnota_po, verze_pred, verze_po, kdo) VALUES (%s,%s,%s,%s,%s,%s,NULL,NULL,%s)",
                (tabulka, recept_id, "__kategorie__", "upravit", r["kategorie"], kategorie or None,
                 (u or {}).get("email") or "?"),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit((current_user() or {}).get("id"), "recept_kategorie", tabulka, recept_id,
              f"{r['name']}: {r['kategorie'] or '-'} -> {kategorie or '-'}")
    return jsonify({"ok": True})
