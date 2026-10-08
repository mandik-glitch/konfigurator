#!/usr/bin/env python3
"""
scripts/qa/merge_reports.py - slouci vysledky jednotlivych QA suit
(kazdy jeden JSON objekt podle kontraktu v _common.py) do jednoho
souhrnneho reportu (bot14, 2026-09-02, bod H "kontrolni mechanismy na
cely system"). Vola scripts/qa/run_all.sh, negeneruje se rucne.

Vstup: cesty k .json souboru per suite (kazdy jeden radek/objekt, jak
ho vyplivne <suite>.py --json), nebo "MISSING:<suite>" pokud suita
selhala tak, ze nevygenerovala zadny JSON (crash pred prvnim
print(), spatny exit kod bez vystupu...).

Vystup: qa-reports/<YYYY-MM-DD_HHMM>.json + .md, symlink latest.json/
latest.md, DIFF proti predchozimu nejnovejsimu reportu (nove/zmizele
nalezy podle code+where), drzi poslednich 30 reportu.
"""
import argparse
import datetime
import glob
import json
import os
import sys

QA_REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "qa-reports")
MAX_KEPT = 30


def _finding_key(f):
    return (f.get("code"), f.get("where"))


def load_suite_result(path, suite_name):
    if path.startswith("MISSING:"):
        return {
            "suite": suite_name, "ran_at": None, "duration_s": None, "status": "fail",
            "findings": [{"severity": "critical", "code": "QA_SUITE_MISSING",
                          "title": f"Suita {suite_name} nevygenerovala žádný výstup",
                          "detail": path[len('MISSING:'):], "where": suite_name, "fix_hint": None}],
            "stats": {},
        }
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        # posledni radek s validnim JSON (nekdy skript vypise warning na
        # stdout pred samotnym JSON radkem - defenzivně vezmeme posledni
        # neprazdny radek, ne cely soubor).
        for line in reversed(content.splitlines()):
            line = line.strip()
            if not line:
                continue
            return json.loads(line)
        raise ValueError("prazdny vystup")
    except (OSError, ValueError, json.JSONDecodeError) as e:
        return {
            "suite": suite_name, "ran_at": None, "duration_s": None, "status": "fail",
            "findings": [{"severity": "critical", "code": "QA_SUITE_OUTPUT_INVALID",
                          "title": f"Suita {suite_name} vrátila nevalidní JSON",
                          "detail": str(e), "where": suite_name, "fix_hint": None}],
            "stats": {},
        }


def build_report(suite_results):
    all_findings = []
    for r in suite_results:
        for f in r.get("findings", []):
            f = dict(f)
            f["suite"] = r["suite"]
            all_findings.append(f)
    sev_order = {"critical": 0, "warning": 1, "info": 2}
    all_findings.sort(key=lambda f: sev_order.get(f.get("severity"), 9))

    overall = "ok"
    if any(r["status"] == "fail" for r in suite_results):
        overall = "fail"
    elif any(r["status"] == "warn" for r in suite_results):
        overall = "warn"

    return {
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "overall_status": overall,
        "suites": [
            {"suite": r["suite"], "status": r["status"], "ran_at": r.get("ran_at"),
             "duration_s": r.get("duration_s"), "finding_count": len(r.get("findings", [])),
             "stats": r.get("stats", {})}
            for r in suite_results
        ],
        "findings": all_findings,
    }


def diff_against_previous(report, previous):
    if not previous:
        return {"new": [], "resolved": []}
    prev_keys = {_finding_key(f) for f in previous.get("findings", [])}
    cur_keys = {_finding_key(f) for f in report.get("findings", [])}
    new = [f for f in report["findings"] if _finding_key(f) not in prev_keys]
    resolved_keys = prev_keys - cur_keys
    resolved = [f for f in previous["findings"] if _finding_key(f) in resolved_keys]
    return {"new": new, "resolved": resolved}


def render_md(report, diff):
    lines = [f"# QA report {report['generated_at']}", "", f"**Celkový stav: {report['overall_status'].upper()}**", ""]
    lines.append("## Suity")
    lines.append("| Suita | Stav | Nálezů | Trvání |")
    lines.append("|---|---|---|---|")
    for s in report["suites"]:
        lines.append(f"| {s['suite']} | {s['status']} | {s['finding_count']} | {s.get('duration_s') or '-'} s |")
    lines.append("")

    if diff["new"]:
        lines.append(f"## Nové nálezy oproti minulému běhu ({len(diff['new'])})")
        for f in diff["new"][:30]:
            lines.append(f"- [{f['severity']}] `{f['code']}` ({f['suite']}) {f['title']} — {f.get('where') or ''}")
        lines.append("")
    if diff["resolved"]:
        lines.append(f"## Zmizelé nálezy (vyřešeno nebo už neplatí) ({len(diff['resolved'])})")
        for f in diff["resolved"][:30]:
            lines.append(f"- [{f['severity']}] `{f['code']}` ({f['suite']}) {f['title']} — {f.get('where') or ''}")
        lines.append("")

    lines.append(f"## TOP 20 nálezů podle závažnosti (z {len(report['findings'])} celkem)")
    for f in report["findings"][:20]:
        lines.append(f"- **[{f['severity']}]** `{f['code']}` ({f['suite']}) — {f['title']}")
        lines.append(f"  - kde: {f.get('where') or '-'}")
        lines.append(f"  - detail: {(f.get('detail') or '')[:300]}")
        if f.get("fix_hint"):
            lines.append(f"  - návrh: {f['fix_hint']}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", action="append", nargs=2, metavar=("SUITE", "PATH"), required=True,
                     help="jméno suity + cesta k jejímu JSON výstupu (nebo MISSING:<duvod>), lze opakovat")
    args = ap.parse_args()

    os.makedirs(QA_REPORTS_DIR, exist_ok=True)
    suite_results = [load_suite_result(path, suite) for suite, path in args.input]
    report = build_report(suite_results)

    latest_json = os.path.join(QA_REPORTS_DIR, "latest.json")
    previous = None
    if os.path.islink(latest_json) or os.path.isfile(latest_json):
        try:
            with open(latest_json, encoding="utf-8") as f:
                previous = json.load(f)
        except (OSError, ValueError):
            previous = None
    diff = diff_against_previous(report, previous)
    report["diff"] = {
        "new_count": len(diff["new"]), "resolved_count": len(diff["resolved"]),
        "new": diff["new"][:50], "resolved": diff["resolved"][:50],
    }

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    json_path = os.path.join(QA_REPORTS_DIR, f"{stamp}.json")
    md_path = os.path.join(QA_REPORTS_DIR, f"{stamp}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_md(report, diff))

    for name, target in (("latest.json", json_path), ("latest.md", md_path)):
        link = os.path.join(QA_REPORTS_DIR, name)
        if os.path.islink(link) or os.path.exists(link):
            os.remove(link)
        os.symlink(os.path.basename(target), link)

    # drzet poslednich MAX_KEPT (podle jmena = chronologicky, YYYY-MM-DD_HHMM razeni funguje lexikograficky)
    all_json = sorted(glob.glob(os.path.join(QA_REPORTS_DIR, "20*.json")))
    for old in all_json[:-MAX_KEPT]:
        try:
            os.remove(old)
            md_sibling = old[:-5] + ".md"
            if os.path.isfile(md_sibling):
                os.remove(md_sibling)
        except OSError:
            pass

    print(json.dumps({"overall_status": report["overall_status"], "json_path": json_path, "md_path": md_path,
                       "new_findings": len(diff["new"]), "resolved_findings": len(diff["resolved"])}, ensure_ascii=False))
    sys.exit({"ok": 0, "warn": 1, "fail": 2}[report["overall_status"]])


if __name__ == "__main__":
    main()
