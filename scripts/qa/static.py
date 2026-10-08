#!/usr/bin/env python3
"""
QA suita (C) - staticka analyza kodu (bot5, 2026-09-02, "kontrolni
mechanismy na cely system konfiguratoru", zadani od Roberta pres bot3,
rozdeleno na 5 botu - tohle je bot5uv FRONTEND dil C+E+J, tenhle soubor
je C).

Kontroluje (bez zapisu, bez zmeny dat - jen cte soubory + jednu READ ONLY
DB kontrolu pres api/qa_checks.py):
  1) py_compile vsech api/*.py (syntax)
  2) pyflakes nad api/*.py (samostatny venv scripts/qa/.venv, NE
     produkcni api/venv - viz WORKFLOW.md/bot3 zadani), filtrovano proti
     scripts/qa/static_ignore.txt (znama zamerna "unused import" kvuli
     vedlejsimu efektu registrace routes, viz hlavicka tam)
  3) `node --check` vsech webapp/js/*.js
  4) `node --check` vsech INLINE <script> bloku ve webapp/*.html (module
     vs. classic podle type=, chyba se hlasi jako soubor:radek v puvodni
     HTML, ne v docasnem souboru)
  5) validita vsech *.json v repu (mimo node_modules)
  6) check_broken_static_asset_ref z api/qa_checks.py (script src/link
     href/CSS url() na neexistujici soubor - broken_static_image_src uz
     resi jen <img src>, tohle je totozna trida chyby na jinych znackach)
  7) hygiena repa: git status guardovanych souboru (necommitovane zmeny),
     zapomenute .bak/.orig/.old soubory, soubory >5 MB v gitu,
     TODO/FIXME/XXX pocty (jen stats, ne jednotlive nalezy)

Pouziti:
  cd /opt/konfigurator && scripts/qa/static.sh [--json]
  (nebo primo: api/venv/bin/python3 scripts/qa/static.py --json)

Zadny zapis, zadne INSERT/UPDATE/DELETE - viz _common.get_conn()
(READ ONLY transakce) a WORKFLOW.md "read-only vuci datum".
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import REPO_ROOT, QA_REPORTS_DIR, finding, run_suite, get_conn  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "api"))
import qa_checks  # noqa: E402

WEBAPP_DIR = os.path.join(REPO_ROOT, "webapp")
API_DIR = os.path.join(REPO_ROOT, "api")
QA_DIR = os.path.dirname(os.path.abspath(__file__))
QA_VENV_PYFLAKES = os.path.join(QA_DIR, ".venv", "bin", "pyflakes")
IGNORE_FILE = os.path.join(QA_DIR, "static_ignore.txt")
GUARDED_RE_FILES = ("webapp/", "api/app.py")  # stejny vzor jako .git/hooks/pre-commit GUARDED_PATTERN


def _py_compile_check():
    import py_compile
    findings = []
    files = sorted(glob.glob(os.path.join(API_DIR, "*.py")))
    for path in files:
        rel = os.path.relpath(path, REPO_ROOT)
        try:
            py_compile.compile(path, doraise=True, quiet=2)
        except py_compile.PyCompileError as e:
            findings.append(finding(
                "critical", "STATIC_PY_SYNTAX_ERROR",
                f"Syntax error v {rel}", str(e.msg), where=rel,
                fix_hint="Oprav syntaxi - soubor se nenacte (ImportError pri startu gunicornu).",
            ))
    return findings, len(files)


def _load_ignore_list():
    ignore = set()
    if os.path.isfile(IGNORE_FILE):
        with open(IGNORE_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.lstrip().startswith("#") or "\t" not in line:
                    continue
                file_part, msg_part = line.split("\t", 1)
                ignore.add((file_part.strip(), msg_part.strip()))
    return ignore


def _pyflakes_check():
    findings = []
    stats = {}
    if not os.path.isfile(QA_VENV_PYFLAKES):
        findings.append(finding(
            "warning", "STATIC_PYFLAKES_MISSING",
            "pyflakes není nainstalován v scripts/qa/.venv",
            f"Očekávám {QA_VENV_PYFLAKES} - spusť: python3 -m venv scripts/qa/.venv && "
            f"scripts/qa/.venv/bin/pip install pyflakes",
            fix_hint="Vytvoř samostatný venv pro QA nástroje třetích stran (ne produkční api/venv).",
        ))
        return findings, stats
    files = sorted(glob.glob(os.path.join(API_DIR, "*.py")))
    proc = subprocess.run([QA_VENV_PYFLAKES, *files], capture_output=True, text=True, timeout=60)
    ignore = _load_ignore_list()
    by_file = {}
    total_raw = 0
    total_ignored = 0
    for line in proc.stdout.splitlines():
        # format: <path>:<line>:<col>: <message>
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        path, lineno, col, msg = parts
        msg = msg.strip()
        rel = os.path.relpath(path, REPO_ROOT)
        total_raw += 1
        if (rel, msg) in ignore:
            total_ignored += 1
            continue
        by_file.setdefault(rel, []).append(f"{lineno}:{col}: {msg}")
    for rel, items in sorted(by_file.items()):
        severity = "warning"
        findings.append(finding(
            severity, "STATIC_PYFLAKES",
            f"pyflakes: {len(items)} nález(ů) v {rel}",
            "\n".join(items[:25]) + (f"\n… a dalších {len(items) - 25}" if len(items) > 25 else ""),
            where=rel,
            fix_hint="Nepoužité importy/proměnné odstranit; u f-stringu bez placeholderu zkontrolovat, jestli nechybí {proměnná}.",
        ))
    stats["pyflakes_raw_findings"] = total_raw
    stats["pyflakes_whitelisted"] = total_ignored
    stats["pyflakes_reported"] = total_raw - total_ignored
    stats["pyflakes_files_with_findings"] = len(by_file)
    return findings, stats


def _node_check_file(path):
    proc = subprocess.run(["node", "--check", path], capture_output=True, text=True, timeout=20)
    return proc.returncode, proc.stderr.strip()


def _node_check_js_files():
    findings = []
    files = sorted(glob.glob(os.path.join(WEBAPP_DIR, "js", "*.js")))
    for path in files:
        rel = os.path.relpath(path, REPO_ROOT)
        rc, err = _node_check_file(path)
        if rc != 0:
            findings.append(finding(
                "critical", "STATIC_JS_SYNTAX_ERROR",
                f"JS syntax error v {rel}", err or "node --check selhal", where=rel,
                fix_hint="Oprav syntaxi - prohlížeč soubor vůbec nenačte / spadne na parse chybě.",
            ))
    return findings, len(files)


class _ScriptBlockCollector:
    """Rucni radkovy parser <script> bloku (ne html.parser) - potrebujeme
    PRESNE cislo radku prvniho radku OBSAHU (ne tagu), aby chyba z
    `node --check` sla namapovat zpet na spravny radek v puvodnim HTML.
    html.parser.getpos() by fungovalo taky, ale rucni pruchod po radcich
    je tu jednodussi na spravne osetreni <script type="application/json">
    (json-ld, sablony) a vicerádkových atributů tagu."""

    _TYPES_TO_CHECK = ("", "text/javascript", "application/javascript", "module")

    def __init__(self, html_text):
        self.html_text = html_text
        self.blocks = []  # (start_line 1-based, kind, content)

    def run(self):
        import re
        tag_re = re.compile(r'<script\b([^>]*)>', re.IGNORECASE)
        end_re = re.compile(r'</script\s*>', re.IGNORECASE)
        pos = 0
        # HTML komentare (<!-- ... -->) mohou obsahovat "<script>" jako
        # BEZNY TEXT (dokumentacni komentar, ne skutecny tag) - realny
        # nalez ve webapp/scene.html ~radek 2623 ("...prohlizec odmita
        # spustit jako <script>)," uvnitr komentare o BVH). Vybledit na
        # mezery (zachovat delku/radky, aby cisla radku sedela) PRED
        # hledanim tagu, ne po nem.
        text = re.sub(r'<!--.*?-->', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), self.html_text, flags=re.DOTALL)
        while True:
            m = tag_re.search(text, pos)
            if not m:
                break
            attrs_str = m.group(1)
            if re.search(r'\bsrc\s*=', attrs_str, re.IGNORECASE):
                pos = m.end()
                continue
            type_m = re.search(r'\btype\s*=\s*["\']?([^"\'\s>]+)', attrs_str, re.IGNORECASE)
            typ = (type_m.group(1) if type_m else "").lower()
            end_m = end_re.search(text, m.end())
            if not end_m:
                break
            content = text[m.end():end_m.start()]
            if typ in self._TYPES_TO_CHECK:
                kind = "module" if typ == "module" else "classic"
                start_line = text.count("\n", 0, m.end()) + 1
                if content.strip():
                    self.blocks.append((start_line, kind, content))
            pos = end_m.end()
        return self.blocks


def _node_check_inline_scripts():
    findings = []
    checked = 0
    html_files = sorted(glob.glob(os.path.join(WEBAPP_DIR, "*.html")))
    with tempfile.TemporaryDirectory(prefix="qa-static-inline-") as tmpdir:
        for path in html_files:
            rel = os.path.relpath(path, REPO_ROOT)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            blocks = _ScriptBlockCollector(content).run()
            for start_line, kind, block_content in blocks:
                checked += 1
                padded = ("\n" * (start_line - 1)) + block_content
                ext = ".mjs" if kind == "module" else ".js"
                tmp_path = os.path.join(tmpdir, f"block_{checked}{ext}")
                with open(tmp_path, "w", encoding="utf-8") as tf:
                    tf.write(padded)
                rc, err = _node_check_file(tmp_path)
                if rc != 0:
                    findings.append(finding(
                        "critical", "STATIC_INLINE_JS_SYNTAX_ERROR",
                        f"Syntax error v inline <script> ({kind}) v {rel}",
                        err.replace(tmp_path, f"{rel} (inline script od řádku {start_line})"),
                        where=f"{rel}:{start_line}",
                        fix_hint="Oprav syntaxi inline scriptu - prohlížeč blok vůbec nenačte.",
                    ))
    return findings, checked


def _json_validity_check():
    findings = []
    checked = 0
    for path in glob.glob(os.path.join(REPO_ROOT, "**", "*.json"), recursive=True):
        if "/node_modules/" in path or "/.git/" in path or "/qa-reports/" in path:
            continue
        if "/scripts/qa/.venv/" in path:
            continue
        rel = os.path.relpath(path, REPO_ROOT)
        checked += 1
        try:
            with open(path, encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            findings.append(finding(
                "critical", "STATIC_JSON_INVALID",
                f"Neplatný JSON: {rel}", f"{e}", where=rel,
                fix_hint="Oprav syntaxi JSON - cokoli, co soubor čte přes json.load()/JSON.parse(), na něm spadne.",
            ))
        except OSError as e:
            findings.append(finding("warning", "STATIC_JSON_UNREADABLE", f"Nelze přečíst {rel}", str(e), where=rel))
    return findings, checked


def _asset_ref_check():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            rows = qa_checks.check_broken_static_asset_ref(cur)
    finally:
        conn.close()
    findings = []
    for _id, _label, detail in rows:
        findings.append(finding(
            "warning", "STATIC_BROKEN_ASSET_REF", "Odkaz na neexistující statický soubor", detail,
            fix_hint="Oprav cestu nebo přidej chybějící soubor (viz api/qa_checks.py::check_broken_static_asset_ref).",
        ))
    return findings, len(rows)


def _repo_hygiene_check():
    findings = []
    stats = {}

    # git status guardovanych ZDROJOVYCH souboru (webapp/*.html,
    # webapp/js/*.js, api/app.py) - ZAMERNE ne cely strom webapp/, protoze
    # tam lezi stovky netrackovanych binarnich assetu (webapp/katalog/*.glb,
    # HDRI...) - to neni "rozdelana kodova zmena", jen chybejici/rozumne
    # nedoplnene .gitignore (viz stat untracked_non_source_under_webapp
    # nize, at se cislo neztrati, ale nehlasi se to jako 20 nalezu).
    import re as _re
    guarded_src_re = _re.compile(r'^webapp/[^/]+\.(?:html|js|css)$|^webapp/js/[^/]+\.js$|^api/app\.py$')
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
    guarded_dirty = []
    untracked_non_source = 0
    for line in proc.stdout.splitlines():
        status, path = line[:2], line[3:].strip()
        if guarded_src_re.match(path):
            guarded_dirty.append(line.strip())
        elif status.strip() == "??" and path.startswith("webapp/"):
            untracked_non_source += 1
    if guarded_dirty:
        findings.append(finding(
            "warning", "STATIC_GUARDED_UNCOMMITTED",
            f"{len(guarded_dirty)} guardovaný zdrojový soubor(ů) s necommitovanou změnou",
            "\n".join(guarded_dirty[:20]),
            fix_hint="Guardované soubory (webapp/*.html, webapp/js/*.js, api/app.py) by měly být commitnuté hned po zápisu (viz WORKFLOW.md zámek) - zkontroluj, jestli někdo nedrží rozdělanou práci moc dlouho.",
        ))
    stats["guarded_source_files_uncommitted"] = len(guarded_dirty)
    stats["untracked_non_source_under_webapp"] = untracked_non_source

    # zapomenute .bak/.orig/.old soubory - NA DISKU (obvykle rucni
    # `cp file file.bak.$(date)` mimo git, viz WORKFLOW.md "rollback pres
    # git checkout, NIKDY .bak.* kopie") - proto se hleda primo na
    # souborovem systemu, ne jen mezi git-trackovanymi soubory (`git
    # ls-files` by je typicky vubec nenasel, jsou netrackovane).
    proc = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
    tracked = proc.stdout.splitlines()
    def _is_vendor_dir(name):
        return name in (".git", "node_modules", "qa-reports", "site-packages") or name == "venv" or name.endswith("_venv") or name.endswith(".venv")

    bak_files = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if not _is_vendor_dir(d)]
        for fn in filenames:
            low = fn.lower()
            if low.endswith((".bak", ".orig", ".old")) or ".bak." in low or ".bak-" in low:
                bak_files.append(os.path.relpath(os.path.join(dirpath, fn), REPO_ROOT))
    if bak_files:
        env_baks = [p for p in bak_files if ".env" in os.path.basename(p).lower()]
        findings.append(finding(
            "warning" if env_baks else "info", "STATIC_STALE_BACKUP_FILES",
            f"{len(bak_files)} zapomenutých .bak/.orig/.old souborů na disku",
            "\n".join(sorted(bak_files)) + (
                f"\n\nPOZOR: {len(env_baks)} z nich vypadá jako záloha .env (obsahuje hesla/tokeny) - "
                f"riziko úniku při případném budoucím `git add -A`: {', '.join(env_baks)}" if env_baks else ""
            ),
            fix_hint="Zkontrolovat, jestli jsou tyhle záložní kopie ještě k něčemu (staré rollback body dle WORKFLOW.md měly vznikat přes git checkout, ne .bak.* kopie) - pokud ne, smazat (NE automaticky, jen návrh).",
        ))
    stats["stale_backup_files"] = len(bak_files)

    # soubory > 5 MB v gitu
    big_files = []
    for p in tracked:
        full = os.path.join(REPO_ROOT, p)
        try:
            size = os.path.getsize(full)
        except OSError:
            continue
        if size > 5 * 1024 * 1024:
            big_files.append((p, size))
    if big_files:
        detail = "\n".join(f"{p} ({size / 1024 / 1024:.1f} MB)" for p, size in sorted(big_files, key=lambda x: -x[1]))
        findings.append(finding(
            "info", "STATIC_LARGE_FILE_IN_GIT",
            f"{len(big_files)} souborů > 5 MB v gitu", detail,
            fix_hint="Zvážit .gitignore / Git LFS / přesun mimo repo, pokud jde o binární data (git repo pak zbytečně roste).",
        ))
    stats["large_files_in_git"] = len(big_files)

    # TODO/FIXME/XXX pocty (jen stats)
    todo_re_files = list(glob.glob(os.path.join(API_DIR, "*.py"))) + list(glob.glob(os.path.join(WEBAPP_DIR, "*.html"))) + \
        list(glob.glob(os.path.join(WEBAPP_DIR, "js", "*.js")))
    counts = {"TODO": 0, "FIXME": 0, "XXX": 0}
    for path in todo_re_files:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        for key in counts:
            counts[key] += text.count(key)
    stats["todo_fixme_xxx_counts"] = counts

    return findings, stats


def collect():
    findings = []
    stats = {}

    f, n = _py_compile_check()
    findings += f
    stats["api_py_files_compiled"] = n

    f, s = _pyflakes_check()
    findings += f
    stats.update(s)

    f, n = _node_check_js_files()
    findings += f
    stats["webapp_js_files_checked"] = n

    f, n = _node_check_inline_scripts()
    findings += f
    stats["inline_script_blocks_checked"] = n

    f, n = _json_validity_check()
    findings += f
    stats["json_files_checked"] = n

    f, n = _asset_ref_check()
    findings += f
    stats["broken_asset_refs"] = n

    f, s = _repo_hygiene_check()
    findings += f
    stats.update(s)

    return findings, stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="výstup jako jeden JSON objekt na stdout")
    args = ap.parse_args()
    run_suite("static", collect, args.json)
