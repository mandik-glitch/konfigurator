#!/opt/konfigurator/api/venv/bin/python
"""PDF doklady: text z objednavky se do reportlab Paragraph vkladal BEZ escapovani (bot5, 2026-10-02, nalez pri dealerskych objednavkach, zadani bot3).

Paragraph PARSUJE ZNACKY: `<img src='/cesta/obrazek.png'/>` v jmene/adrese/nazvu polozky vlozilo do PDF libovolny cteny obrazek ze serveru (lokalni cesty
reportlab neomezuje; http(s) se vychozim nastavenim nestahuje, zkouska s lokalnim listenerem: 0 pripojeni), neplatna znacka shodila generovani PDF
a `R&D` se tisklo jako `R&D;`. Oprava: documents._esc (escape pred vlozenim) + documents._P (pojistka: jen znacky b/i/u/br).

Test NEPOTREBUJE DB (doklady se skladaji z ruznych snapshotu, tady syntetickych). Pred opravou PADA (spusteni nad puvodnim documents.py), po oprave projde.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_pdf_escape_testy/test_pdf_escape.py            (kandidat: --setenv=DOCUMENTS_PY=/cesta/documents.py)
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.environ.get("DOCUMENTS_PY"):
    tmp = tempfile.mkdtemp(prefix="kand_documents_")
    shutil.copy(os.environ["DOCUMENTS_PY"], os.path.join(tmp, "documents.py"))
    sys.path.insert(0, tmp)
sys.path.insert(1 if os.environ.get("DOCUMENTS_PY") else 0, os.path.join(REPO, "api"))

import app as appmod  # noqa: E402,F401
import documents  # noqa: E402
from reportlab.platypus import Paragraph, Table  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:300]))


IMG = os.path.join(REPO, "webapp", "capture-icon-192.png")          # verejna ikona v repu - cteny obrazek, ktery by se pri zneuziti vlozil do PDF
assert os.path.exists(IMG), IMG
CAPTURED = []


def texty(flow):
    """Plne texty vsech Paragraphu (i v bunkach tabulek) a retezcovych bunek, jak je reportlab SKUTECNE vykresli."""
    out = []
    for f in flow:
        if isinstance(f, Paragraph):
            out.append(f.getPlainText())
        elif isinstance(f, Table):
            for row in f._cellvalues:
                for cell in row:
                    out.append(cell.getPlainText() if isinstance(cell, Paragraph) else str(cell))
    return out


class Zaznam(documents.SimpleDocTemplate):
    def build(self, flowables, *a, **k):
        CAPTURED.append(texty(flowables))        # texty PRED stavbou - reportlab pri build() tabulky deli a meni
        return super().build(flowables, *a, **k)


documents.SimpleDocTemplate = Zaznam


def doklad(typ, jmeno, adresa, ico, email, telefon, dod_adresa, nazvy, poznamka, platba, vystavil):
    items = [{"name": n, "qty": 2, "unit_price_net": 100.0, "line_total_net": 200.0, "is_profile_unit": False, "unit": "ks",
              "vat_rate": 21, "vat_amount": 42.0, "line_total_gross": 242.0} for n in nazvy]
    return {
        "id": 1, "order_id": 1, "document_type": typ, "document_number": "DOC00001", "variable_symbol": "DOC00001",
        "payment_method_label": platba, "issue_date": datetime.datetime(2026, 10, 2, 12, 0), "due_date": datetime.date(2026, 10, 9),
        "taxable_supply_date": datetime.date(2026, 10, 2), "note": poznamka,
        "items_snapshot": json.dumps(items), "vat_breakdown": json.dumps([{"rate": 21, "base_czk": 200.0, "vat_czk": 42.0, "total_czk": 242.0}]),
        "recipient_snapshot": json.dumps({"name": jmeno, "address": adresa, "ico": ico, "dic": None, "email": email, "phone": telefon}),
        "delivery_snapshot": json.dumps({"address": dod_adresa}) if dod_adresa else None,
        "total_without_vat_czk": 200.0, "total_vat_czk": 42.0, "total_with_vat_czk": 242.0, "rounding_czk": 0, "advance_deduction_czk": 0,
        "advance_document_number": None, "amount_due_czk": 242.0, "issued_by": vystavil,
    }


TYPY = ("proforma_invoice", "invoice", "payment_tax_document", "delivery_note")
IMG_TAG = f"<img src='{IMG}' width='30' height='30'/>"
HOSTILE = dict(
    jmeno=f"Jan <Novák> & syn {IMG_TAG}", adresa=f"{IMG_TAG}, Ulice 5, R&D <font color='red'>centrum</font>", ico="<font size='30'>1</font>",
    email="<a href='http://x.test'>m@x.cz</a>", telefon=IMG_TAG, dod_adresa=f"Sklad {IMG_TAG}, <link rel='x'/>, Brno",
    nazvy=[f"Profil R&D {IMG_TAG}", "Rám <30x30>", "<img src='/etc/hostname'/>"],
    poznamka=f"Poznámka <img src='/etc/hostname'/> {IMG_TAG}", platba=f"Převod <b>&</b> {IMG_TAG}", vystavil=f"Admin <script>x</script> {IMG_TAG}")

print("== A hostilni data v kazdem typu dokladu")
pdfs = {}
for typ in TYPY:
    CAPTURED.clear()
    try:
        pdf = documents.render_document_pdf(doklad(typ, **HOSTILE))
        pdfs[typ] = (pdf, CAPTURED[-1])
        over(f"A1 {typ}: PDF se vygeneruje i s hostilnim textem (nespadne na neplatne znacce)", pdf[:4] == b"%PDF", pdf[:20])
    except Exception as e:
        over(f"A1 {typ}: PDF se vygeneruje i s hostilnim textem (nespadne na neplatne znacce)", False, f"{type(e).__name__}: {str(e)[:150]}")
    if typ in pdfs:
        pdf, tx = pdfs[typ]
        over(f"A2 {typ}: do PDF se NEVLOZI zadny obrazek (zadne cteni souboru podle cesty z textu zakaznika)", b"/Subtype /Image" not in pdf, "obrazek v PDF")
        celek = "\n".join(tx)
        over(f"A3 {typ}: nedoveryhodne znacky se vykresli DOSLOVA (img, font, a, link, script zustanou videt jako text)",
             "<img src=" in celek and "<font size='30'>1</font>" in celek and "<script>x</script>" in celek, celek[:200])

print("== B pozadovane doslovne vykresleni")
tx = "\n".join(pdfs.get("proforma_invoice", (b"", []))[1])
over("B1 `R&D` se vykresli jako `R&D` (ne `R&D;`)", "R&D" in tx and "R&D;" not in tx, tx[:200])
over("B2 `Jan <Novák>` se vykresli doslova vcetne zavorek", "Jan <Novák>" in tx, tx[:200])
over("B3 `Rám <30x30>` v nazvu polozky se vykresli doslova", "Rám <30x30>" in tx, tx[:200])
over("B4 adresa: carky se dal meni na zalomeni radku (<br/>), i kdyz je text escapovany", any("Ulice 5" in t_ for t_ in pdfs.get("proforma_invoice", (b"", []))[1]), None)

print("== C pojistka _P (kdyby nekdo zapomnel na _esc)")
st = getSampleStyleSheet()["Normal"]
if not hasattr(documents, "_P") or not hasattr(documents, "_esc"):
    over("C1-C3 pojistka _P a _esc v documents.py existuje", False, "chybi (documents.py bez opravy)")
else:
    p = documents._P("A <img src='/etc/hostname'/> B <font color='red'>c</font> <a href='http://x'>d</a> <link rel='x'/>", st)
    over("C1 _P: cizi znacky (img, font, a, link) se zmeni na text, nic se nenacita ani nepadne", "<img" in p.getPlainText() and "<font" in p.getPlainText() and "<a href" in p.getPlainText(), p.getPlainText())
    p = documents._P("<b>tucne</b><br/>dalsi <i>sikmo</i> <u>podtrzene</u>", st)
    over("C2 _P: povolene znacky b/i/u/br dal funguji (nejsou vykresleny jako text)", "<b>" not in p.getPlainText() and "tucne" in p.getPlainText() and "dalsi" in p.getPlainText(), p.getPlainText())
    over("C3 _esc: None -> prazdny retezec, & < > se escapuji, ceske znaky beze zmeny", documents._esc(None) == "" and documents._esc("a&b<c>č") == "a&amp;b&lt;c&gt;č" and documents._esc(5) == "5", None)

print("== D bezne (nehostilni) doklady se nezmenily")
BEZNE = dict(jmeno="Jan Novák", adresa="Ulice 5, 60200 Brno", ico="12345678", email="jan@example.cz", telefon="+420 777 123 456", dod_adresa="Jan Novák, Ulice 5, 60200 Brno",
             nazvy=["Profil 30x30 (3 m)", "Spojka L"], poznamka="Zasíláme fakturu k uhrazení zálohy dle vaší objednávky:", platba="Platba předem", vystavil="Systém (automaticky)")
sada = []
for typ in TYPY:
    CAPTURED.clear()
    pdf = documents.render_document_pdf(doklad(typ, **BEZNE))
    sada.append("\n".join(CAPTURED[-1]))
    over(f"D1 {typ}: bezny doklad se vygeneruje, bez obrazku, obsahuje jmeno, adresu a nazvy", pdf[:4] == b"%PDF" and b"/Subtype /Image" not in pdf and "Jan Novák" in sada[-1] and "Profil 30x30 (3 m)" in sada[-1] and "Ulice 5" in sada[-1], sada[-1][:120])
print("OTISK_BEZNYCH_DOKLADU", hashlib.sha256("\n##\n".join(sada).encode("utf-8")).hexdigest()[:16])

print("== E zdrojovy kod: zadny primy Paragraph( v render_document_pdf")
zdroj = open(documents.__file__, encoding="utf-8").read()
telo = zdroj[zdroj.index("def render_document_pdf"):]
over("E1 v render_document_pdf zbyva jen _P( (zadny primy Paragraph( s dynamickym textem)", not re.search(r"(?<![_\w])Paragraph\(", telo), re.findall(r"(?<![_\w])Paragraph\(.{0,60}", telo)[:3])

ok = sum(vysl)
print(f"\nVYSLEDEK PDF escapovani: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
