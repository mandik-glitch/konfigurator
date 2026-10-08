# QA framework - kontrolní mechanismy na celý systém konfigurátoru

Založeno bot14, 2026-09-02 - zadání Roberta (přes bot3): "Udělej
kontrolní mechanismy na celý systém konfigurátoru - hledat chyby,
dělat skripty na hledání chyb, hledat možnosti ke zlepšení." Práce
rozdělena na 5 botů podle oblasti; bot14 vlastní tenhle společný rámec
(adresář, kontrakt, agregátor) - ostatní suity se na něj napojují.

## Kontrakt (pevný, drží ho VŠECHNY suity)

Každý skript `scripts/qa/<suite>.py` (nebo `.sh` wrapper) podporuje
`--json`, který na stdout vypíše **jeden** JSON objekt:

```json
{
  "suite": "health",
  "ran_at": "2026-09-02T20:55:00+02:00",
  "duration_s": 12.3,
  "status": "ok|warn|fail",
  "findings": [
    {
      "severity": "critical|warning|info",
      "code": "HEALTH_SERVICE_DOWN",
      "title": "…",
      "detail": "…",
      "where": "soubor/URL/tabulka/služba",
      "fix_hint": "…"
    }
  ],
  "stats": { "libovolné čítače": "…" }
}
```

Bez `--json` vypíší lidsky čitelný text. Exit kód: `0` ok, `1` warn,
`2` fail, `3` skript sám selhal (crash před prvním printem apod.).

Sdílené jádro je v [`_common.py`](_common.py) - `finding()`,
`overall_status()`, `run_suite()` (hlídá exit kódy a JSON tvar za vás),
`get_conn()` (DB spojení v `SET SESSION TRANSACTION READ ONLY` módu),
`load_env()` (stejná konvence jako `scripts/qa_product_audit.py`).

## Pravidla

- **READ-ONLY vůči datům.** Žádný `INSERT`/`UPDATE`/`DELETE`, žádné
  odesílání formulářů na server, žádné testovací leady/objednávky.
  `_common.get_conn()` to vynucuje na úrovni DB transakce.
  Jediná schválená výjimka je [`send_alert.py`](send_alert.py) - ten
  smí zapsat pending řádek do `system_emails` (schvalovací fronta,
  NIKDY přímé odeslání), když poslední report obsahuje `critical`
  nález.
- **Nalezené chyby suita NEOPRAVUJE**, jen hlásí (Robert, 2026-08-10:
  "jen hledat a hlásit"). Výjimka: chyby ve vlastním novém QA kódu.
- **Nic nemazat/nepřepisovat cizí soubory.** Report úklid (posledních
  30 běhů) dělá výhradně `merge_reports.py` nad `qa-reports/*.json`,
  nic jiného.
- Běh přes `/opt/konfigurator/api/venv/bin/python3` (produkční venv,
  má pymysql atd.). Nástroje třetích stran nad rámec produkčního venv
  (BeautifulSoup, pyflakes, Playwright...) patří do samostatného
  `scripts/qa/.venv/` (gitignored) - `run_all.sh` ho automaticky
  použije jako fallback interpret pro `.py` suity, které nemají vlastní
  `.sh` wrapper (viz `static.sh` pro vzor "wrapper si vybírá interpret
  sám").
- Žádné credentials v kódu/commitech - DB přístup přes `api/.env`
  (stejný parsing jako `scripts/qa_product_audit.py`).
- Běh jedné suity < ~5 min (`run_all.sh` každou zabíjí po 10 min).
- Než napíšeš NOVOU kontrolu, ověř, že už neexistuje v
  `api/qa_checks.py` (`grep '^def check_' api/qa_checks.py`) -
  datové/kódové kontroly typu `fn(cur)->list[(id,name,detail)]` patří
  TAM (sdílené s `/api/admin/qa-audit` na Dashboardu), ne sem. Sem
  patří to, co `qa_checks.py` neumí: běh procesů, síť, prohlížeč, logy,
  bezpečnostní skeny.

## Suity (2026-09-02)

| Suite | Soubor | Vlastník | Co dělá |
|---|---|---|---|
| `data_code` | `../qa_product_audit.py` | bot14 | obal nad `api/qa_checks.py` (52+ existujících kontrol dat/kódu) |
| `health` | `health.py` | bot14 | jednorázový snímek: systemd, HTTP, TLS, disk, DB, fronty, záloha, gunicorn, nginx log |
| `logs` | `logs.py` | bot14 | skener žurnálu/nginx logů za posledních N h, tracebacky, perzistence nových vs. známých signatur |
| `db_integrity` | `db_integrity.py` | bot13 | integrita DB, drift migrací |
| `security` | `security.py` | bot6 | bezpečnostní kontroly |
| `seo` | `seo.py` | bot15 | SEO/a11y crawl |
| `static` | `static.py` / `static.sh` | bot5 | statická analýza kódu (pyflakes atd.) |
| `e2e` | `e2e/run.cjs` | bot5 | Playwright end-to-end |

`run_all.sh` NEČEKÁ na suity ostatních botů - chybějící soubor v dané
iteraci prostě vynechá (žádná chyba), jakmile bot svůj skript přidá,
příští běh ho automaticky zahrne.

## Jak přidat novou suitu

1. `scripts/qa/<jmeno>.py` (nebo `.sh` wrapper, když potřebuješ jiný
   interpret/prostředí než produkční `api/venv`) s `--json` podle
   kontraktu výše - nejjednodušší přes `_common.run_suite()`:

   ```python
   from _common import finding, run_suite

   def collect():
       findings = []
       stats = {}
       # ... vlastní kontroly, findings.append(finding(...)) ...
       return findings, stats

   if __name__ == "__main__":
       run_suite("<jmeno>", collect, "--json" in sys.argv)
   ```
2. Nic dalšího registrovat netřeba - `run_all.sh` novou suitu najde
   sám při příštím běhu (glob `scripts/qa/*.py` / `*.sh`).
3. Otestuj ručně: `api/venv/bin/python3 scripts/qa/<jmeno>.py --json | python3 -m json.tool`.

## Jak spustit

```bash
# jednotlivá suita
api/venv/bin/python3 scripts/qa/health.py           # lidsky čitelně
api/venv/bin/python3 scripts/qa/health.py --json     # JSON kontrakt

# všechny suity + sloučený report
scripts/qa/run_all.sh
cat qa-reports/latest.md      # čitelný souhrn
cat qa-reports/latest.json    # strojově čitelný, i s DIFF proti minulému běhu
```

Report je i v adminu: Dashboard → panel **"QA běhy (systém)"**
(`GET /api/admin/qa-report/latest`, `api/qa_audit.py`) - jiný panel
než existující "Chyby v kódu"/"Návrhy na doplnění" (ty běží ŽIVĚ nad
aktuálním stavem DB při každém otevření Dashboardu, tenhle je SNAPSHOT
z posledního běhu časovače).

Naplánovaný běh: `konfigurator-qa.timer` (denně 04:30, po
`refresh-prices` 02:30) - viz `deploy/konfigurator-qa.service`/`.timer`.

## Výstupy

`qa-reports/` (gitignored, mimo git) - `<YYYY-MM-DD_HHMM>.json`/`.md`
per běh, `latest.json`/`latest.md` symlink na poslední, drží se
posledních 30 běhů. Persistentní stav mezi běhy (`logs_seen.json`,
`last_alert.json`) žije ve stejném adresáři.
