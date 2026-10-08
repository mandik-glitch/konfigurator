#!/usr/bin/env python3
"""Tydenni sken strukturalne prazdnych bloku (Robert pres bot3, 2026-09-27:
"udelat script, ktery projede jednou tydne vsechny kategorie webu a smaze
prazdne bloky jako je tento" - priloha byl screenshot cistě seddeho oreznuteho
obdelniku, uplne bez textu/nadpisu/obsahu, nejspis pozustatek editace v
adminu). Puvodni konkretni screenshot se na homepage/v 73 kategoriich
nepodarilo zivě zopakovat (bot3 usoudil, ze slo o prechodny stav pri editaci).
Skutecny, PRAVE PROBIHAJICI stejny bug se ale nasel az timhle skriptem primo v
DB: kategorie 182 (balici-stoly-a-pracoviste-na-miru) ma opusteny Fillout
formularovy embed (`<div style="width:100%;height:500px" data-fillout-id=...>
&nbsp;</div>`) - stranka NIKDY nenacita Fillout embed skript, takze se
tenhle div nikdy nevyplni a zustava cistym prazdnym boxem presne 718x500px,
zivě potvrzeno screenshotem 2026-09-27. Tenhle skript proto resi CELOU TRIDU
problemu (opustene/prazdne wrapper-divy - embed, galerie, cokoli podobneho),
ne jen jeden konkretni pripad.

DULEZITY NALEZ BEHEM LADENI (2026-09-27): prvni verze skriptu zahrnovala i
<p> mezi hledane tagy - na zivych datech to vytahlo 33 "nalezu", ale VETSINA
byla `<p><br></p>`/`<p>&nbsp;</p>`/`<p>\\n</p>` - BEZNY, NESKODNY zpusob, jak
RTE editory (Quill apod.) zapisuji prazdny radek pro odsazeni, ne bug. <p> je
proto ZAMERNE VYNECHANO z BLOCK_TAGS - viz komentar tam.

ROZSAH:
  - homepage_blocks / sidebar_blocks (CELE RADKY): title + meta_description +
    body_html vsechny prazdne PO odstraneni znacek A ZAROVEN zadny obrazek/
    video/gallery_preview -> mazani celeho radku. Nic tam neni k zachovani,
    title je NOT NULL sloupec, ale muze byt prazdny retezec.
  - content_pages (intro_html/body_html/bottom_body_html): JEDNOTLIVE prazdne
    blokove elementy UVNITR vetsiho textoveho pole (napr. osamocene
    <div></div>/<p></p> bez textu i obrazku, zbyle po smazani textu v editoru
    ale ne obalu) - stripuje se JEN ten konkretni prazdny tag, zbytek pole
    zustava beze zmeny.

KRITICKY ROZDIL od WORKFLOW.md pravidla 55 (editovatelnost textu kategorii se
nesmi ztratit, Robert 2026-09-26): pravidlo 55 chrani strukturu, ktera NESE
INFORMACI pro budouci obsah (priklad: prazdny FAQ blok, <h3>Caste dotazy</h3>
bez paru, se SCHOVAL na urovni vykresleni, NESMAZAL - viz
api/app.py::_strip_empty_faq_block). Tenhle sken cili VYHRADNE na bloky, kde
neni VUBEC NIC (zadny text vcetne nadpisu, zadny obrazek) - takovy blok pri
psani noveho obsahu Robert stejne napise do noveho odstavce, nezalezi mu na
zachovani puvodni prazdne znacky. Kriterium "prazdny" je proto STRIKTNI: text
bez HTML tagu a bez whitespace musi byt "" A ZAROVEN zadny funkcni obrazek/
video/galerie - viz _je_radek_prazdny()/_najdi_prazdne_bloky_v_html(). Protoze
kazdy heading (h1-h6) ma vzdy neprazdny text, blok se skutecnou strukturou
(jako FAQ wrapper) timhle kriteriem NIKDY neprojde jako "prazdny" - zadna
specialni vyjimka neni potreba.

BEZPECNOSTNI SIT (Robert/bot3 2026-09-27, "je to RECURRING destruktivni
automat, bezici bez lidskeho dohledu kazdy tyden"):
  - PRED kazdym --apply zapisem zaloha VSECH dotcenych radku/poli do
    backups/<datum>_empty_block_scan_pred_zmenou.json
  - PO uspesnem --apply zapisu (jen kdyz NECO nasel a smazal) zapis do
    AGENTS_LOG.md + `scripts/handover.py add --bot bot7`
  - PRI NULOVEM nalezu ticho - zadny zapis do logu/handoveru, jen jeden radek
    na stdout (pro journalctl, kdyby nekdo dohledaval spravny beh timeru)
  - Bez --apply je VZDY jen cteni (read-only dry-run), zadny UPDATE/DELETE
    v DB se nestane.

Spousti se jako systemd timer (konfigurator-empty-block-scan.{service,timer}),
tydne (nedele 03:40, mimo spicku a mimo dogus prepocet cen v 03:20), stejny
vzor jako konfigurator-refresh-dogus-profile-prices.timer.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

from bs4 import BeautifulSoup

REPO_ROOT = "/opt/konfigurator"
BACKUP_DIR = os.path.join(REPO_ROOT, "backups")

# Wrapper-elementy, ktere davaji smysl jako "samostatny box" v CMS textu.
# ZAMERNE BEZ <p> - zivy dry-run 2026-09-27 ukazal, ze prazdne <p> (`<p><br></p>`,
# `<p>&nbsp;</p>`, `<p>\n</p>`) je BEZNY a NESKODNY artefakt editoru (Quill i
# jine RTE takhle zapisuji "prazdny radek pro odsazeni") - 50+ instanci napric
# TEMER VSEMI kategoriemi, casto zamerna mezera mezi odstavci, ne bug. Mazani
# vsech by bylo agresivni a nezadouci zasahnuti do rozestupu v textu, ktere
# Robert nikdy nereklamoval. Skutecny nahlaseny bug (kategorie 182,
# "balici-stoly-a-pracoviste-na-miru", ziva screenshotem potvrzeno 2026-09-27)
# byl `<div>` - opusteny Fillout formularovy embed (`data-fillout-id`,
# `style="width:100%;height:500px"`) BEZ nactenho Fillout embed skriptu na
# strance -> zustane cisty prazdny 718x500px box. Wrapper tagy (div a
# pribuzne) takhle NIKDY nevznikaji z bezneho psani textu v editoru - kdyz
# jsou uplne prazdne, je to skutecny pozustatek (smazany embed/galerie/
# widget), ne typograficka mezera.
BLOCK_TAGS = ("div", "section", "article", "blockquote", "figure")

# (tabulka, [textove sloupce], [obrazek/video/galerie sloupce])
ROW_TABLES = [
    ("homepage_blocks", ["title", "meta_description", "body_html"], ["image_filename", "gallery_preview"]),
    ("sidebar_blocks", ["title", "meta_description", "body_html"], ["image_filename", "video_filename"]),
]
CONTENT_PAGES_COLS = ["intro_html", "body_html", "bottom_body_html"]


def _pripoj_db():
    import pymysql
    env = {}
    for line in open(os.path.join(REPO_ROOT, "api", ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                            password=env["DB_PASSWORD"], database=env["DB_NAME"],
                            cursorclass=pymysql.cursors.DictCursor)


def _strip_text(html_fragment):
    """Text bez znacek a bez whitespace - stejna definice "prazdno", jakou uz
    pouziva api/app.py::_extract_faq_pairs pro Q/A pary."""
    if not html_fragment:
        return ""
    text = re.sub(r"<[^>]+>", "", html_fragment)
    return re.sub(r"\s+", "", text)


def _je_radek_prazdny(radek, text_sloupce, media_sloupce):
    text_all = "".join(_strip_text(radek.get(c) or "") for c in text_sloupce)
    if text_all != "":
        return False
    for col in media_sloupce:
        if radek.get(col):
            return False
    return True


def _najdi_prazdne_bloky_v_html(html_text):
    """Vrati (zmeneno:bool, novy_html:str, pocet:int). Hleda blokove elementy
    BEZ textu A BEZ <img> potomka, od nejhlubsich k nejvyssim (aby se prazdny
    vnitrni <p> smazal SAMOSTATNE, ne strhl s sebou rodice, ktery muze mit
    JINY obsah vedle nej)."""
    if not html_text or not html_text.strip():
        return False, html_text, 0
    soup = BeautifulSoup(html_text, "html.parser")
    odstraneno = 0
    for tag in reversed(soup.find_all(BLOCK_TAGS)):
        if tag.decomposed:
            continue
        if tag.find("img"):
            continue
        if tag.get_text(strip=True) != "":
            continue
        tag.decompose()
        odstraneno += 1
    if odstraneno == 0:
        return False, html_text, 0
    return True, str(soup), odstraneno


def _zapsat_agents_log(zprava):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (f"\n## empty-block-scan (automaticky, "
             f"scripts/2026-09-27_empty_block_scan.py) — {ts}\n\n{zprava}\n")
    try:
        with open(os.path.join(REPO_ROOT, "AGENTS_LOG.md"), "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as e:
        print(f"[empty-block-scan] zapis do AGENTS_LOG.md selhal: {e}", file=sys.stderr)


def _zapsat_handover(zprava):
    try:
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "scripts", "handover.py"), "add",
             "--bot", "bot7", "--project", "konfigurator", "--topic", "empty-block-scan: nalez a smazano",
             "--status", "info", "--body", zprava],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        print(f"[empty-block-scan] handover.py add selhal: {e}", file=sys.stderr)


def sken(cur):
    """Read-only pruzkum - vrati seznam nalezu (dict), NIC nezapisuje."""
    nalezy = []

    for tabulka, text_sloupce, media_sloupce in ROW_TABLES:
        sloupce_sql = ", ".join(["id"] + text_sloupce + media_sloupce)
        cur.execute(f"SELECT {sloupce_sql} FROM {tabulka} WHERE is_visible=1")
        for radek in cur.fetchall():
            if _je_radek_prazdny(radek, text_sloupce, media_sloupce):
                nalezy.append({"typ": "radek", "tabulka": tabulka, "id": radek["id"], "puvodni": radek})

    cur.execute("SELECT category_id, intro_html, body_html, bottom_body_html FROM content_pages")
    for radek in cur.fetchall():
        for col in CONTENT_PAGES_COLS:
            zmeneno, novy_html, pocet = _najdi_prazdne_bloky_v_html(radek.get(col))
            if zmeneno:
                nalezy.append({
                    "typ": "fragment", "tabulka": "content_pages", "category_id": radek["category_id"],
                    "sloupec": col, "puvodni_html": radek[col], "novy_html": novy_html,
                    "pocet_odstranenych_tagu": pocet,
                })
    return nalezy


def _zaloha(nalezy, cesta):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(cesta, "w", encoding="utf-8") as f:
        json.dump(nalezy, f, ensure_ascii=False, indent=2, default=str)


def aplikuj(conn, nalezy):
    with conn.cursor() as cur:
        for n in nalezy:
            if n["typ"] == "radek":
                cur.execute(f"DELETE FROM {n['tabulka']} WHERE id=%s", (n["id"],))
                if cur.rowcount != 1:
                    raise RuntimeError(f"DELETE {n['tabulka']} id={n['id']} ovlivnil {cur.rowcount} radku, cekal jsem 1")
            else:
                cur.execute(
                    f"UPDATE content_pages SET {n['sloupec']}=%s WHERE category_id=%s",
                    (n["novy_html"], n["category_id"]),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"UPDATE content_pages.{n['sloupec']} category_id={n['category_id']} "
                        f"ovlivnil {cur.rowcount} radku, cekal jsem 1"
                    )
    conn.commit()


def _popis_nalezu(nalezy):
    radky = [n for n in nalezy if n["typ"] == "radek"]
    fragmenty = [n for n in nalezy if n["typ"] == "fragment"]
    radky_zprava = "\n".join(
        f"  - {n['tabulka']} id={n['id']} (title={n['puvodni'].get('title')!r})" for n in radky
    )
    fragmenty_zprava = "\n".join(
        f"  - content_pages category_id={n['category_id']}.{n['sloupec']}: "
        f"smazano {n['pocet_odstranenych_tagu']} prazdnych tagu"
        for n in fragmenty
    )
    casti = [f"Nalezeno {len(radky)} prazdnych radku (homepage_blocks/sidebar_blocks) "
             f"a {len(fragmenty)} poli content_pages s prazdnymi vlozenymi bloky."]
    if radky_zprava:
        casti.append(radky_zprava)
    if fragmenty_zprava:
        casti.append(fragmenty_zprava)
    return "\n".join(casti)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Skutecne smazat/upravit v DB. Bez teto volby jen dry-run.")
    ap.add_argument("--backup", default=None, help="Cesta pro JSON zalohu nalezu (jen s --apply).")
    args = ap.parse_args()

    conn = _pripoj_db()
    try:
        with conn.cursor() as cur:
            nalezy = sken(cur)

        ts = datetime.datetime.now().strftime("%Y-%m-%d")
        print(f"OK: nalezeno {len(nalezy)} prazdnych bloku ({ts})")

        if not nalezy:
            return  # ticho pri nulovem nalezu - viz bezpecnostni sit v hlavicce

        for n in nalezy:
            if n["typ"] == "radek":
                print(f"  RADEK {n['tabulka']} id={n['id']} title={n['puvodni'].get('title')!r} -> SMAZAT")
            else:
                print(f"  FRAGMENT content_pages category_id={n['category_id']}.{n['sloupec']} "
                      f"-> odstranit {n['pocet_odstranenych_tagu']} prazdnych tagu")

        if not args.apply:
            print("(dry-run - nic nezapsáno, spusť s --apply pro skutečný zápis)", file=sys.stderr)
            return

        backup_path = args.backup or os.path.join(BACKUP_DIR, f"{ts}_empty_block_scan_pred_zmenou.json")
        _zaloha(nalezy, backup_path)
        print(f"Záloha zapsána do {backup_path}", file=sys.stderr)

        aplikuj(conn, nalezy)
        zprava = _popis_nalezu(nalezy) + f"\n\nZaloha: {backup_path}"
        print(f"Zapsáno/smazáno {len(nalezy)} nálezů.", file=sys.stderr)
        _zapsat_agents_log(zprava)
        _zapsat_handover(zprava)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
