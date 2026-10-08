"""Hak: SCHVALENY doklad -> e-mail ucetni do FRONTY ke schvaleni (bot5, 2026-10-06).

Robert 2026-10-06 (volba v okne bot16): schvalene doklady pujdou ucetni DO FRONTY KE SCHVALENI - `pending` v "Emaily odchozi", odejde az po jeho schvaleni; pravidlo 16 BEZ ZMENY, zadna vyjimka
(ucetni je EXTERNI prijemce). Adresy podle typu dokladu z tabulky "E-maily ucetni" (`ucetni_emaily.prijemci`, bot16): prazdne / neaktivni / poskozene = nic se nezaradi.
  * vydane doklady (approvals.approve_document): e-mail s `document_id`, PDF se pri schvaleni e-mailu vygeneruje cerstve (jako u vsech e-mailu s dokladem), `template_key` = ucetni_doklad;
  * prijate doklady (incoming_documents approve / bulk-approve): e-mail se souborem ze Sdileneho disku (priloha se nacte az pri schvaleni e-mailu, viz emails.approve_pending_email),
    `template_key` = prijaty_doklad:<id>. Prijaty doklad bez souboru (jen text e-mailu) se nezarazuje.
Dvojite zarazeni se brani (stejny doklad uz ve fronte / odeslany = nic). Volano AZ PO commitu schvaleni a vzdy best-effort: chyba se zaloguje a schvaleni dokladu nikdy nerozbije.
Import tohoto modulu (app.py) prepne `ucetni_emaily.ODESILANI_ZAPOJENO = True` (tabulka v adminu pak nehlasi "odesilani zatim nezapojeno").
"""
import os

from app import app, get_conn
import documents
import emails
import ucetni_emaily

ucetni_emaily.ODESILANI_ZAPOJENO = True

TK_VYDANY = "ucetni_doklad"
TK_PRIJATY = "prijaty_doklad"              # + ":<id>" (varchar(30) v shop_emails.template_key)
PODPIS = "S pozdravem\nLOGIMAN s.r.o."


def _uz_zarazeno(cur, template_key, document_id=None):
    where, params = ["template_key=%s", "status IN ('pending','sending','sent')"], [template_key]
    if document_id is not None:
        where.append("document_id=%s")
        params.append(document_id)
    cur.execute(f"SELECT id FROM shop_emails WHERE {' AND '.join(where)} LIMIT 1", params)
    return cur.fetchone() is not None


def zaradit_vydany(doc_id):
    """Po schvaleni vydaneho dokladu: e-mail ucetni do fronty. -> id radku shop_emails, nebo None (zadne adresy / uz zarazeno / doklad neni schvaleny)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            doc = documents._fetch_document(cur, doc_id)
            if not doc or doc.get("approval_status") != "schvaleno":
                return None
            adresy = ucetni_emaily.prijemci(cur, doc["document_type"])
            if not adresy or _uz_zarazeno(cur, TK_VYDANY, doc_id):
                return None
            popis = documents.DOCUMENT_TYPE_LABELS.get(doc["document_type"], doc["document_type"])
            cislo = doc.get("document_number") or f"#{doc_id}"
            order_id = doc.get("order_id")
    finally:
        conn.close()
    log_id, _status, _err = emails.send_and_log(
        order_id, template_key=TK_VYDANY, recipient=adresy[0], cc=", ".join(adresy[1:]) or None, subject=f"{popis} č. {cislo}",
        body=f"Dobrý den,\n\nv příloze zasíláme doklad: {popis} č. {cislo}.\n\n{PODPIS}", document_id=doc_id, auto=True)
    return log_id


def zaradit_prijaty(doc_id):
    """Po schvaleni PRIJATEHO dokladu (soubor uz je na Sdilenem disku): e-mail ucetni do fronty. -> id radku shop_emails, nebo None."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM incoming_documents WHERE id=%s", (doc_id,))
            row = cur.fetchone()
            if not row or row.get("approval_status") != "schvaleno" or not row.get("drive_file_id") or not row.get("filename"):
                return None
            adresy = ucetni_emaily.prijemci(cur, ucetni_emaily.PRIJATY)
            tk = f"{TK_PRIJATY}:{doc_id}"
            if not adresy or _uz_zarazeno(cur, tk):
                return None
            od = row.get("supplier_name") or row.get("source_name") or row.get("source_email") or "-"
            prijato = row["received_at"].strftime("%d.%m.%Y") if row.get("received_at") else "-"
            nazev = str(row["filename"])
    finally:
        conn.close()
    log_id, _status, _err = emails.send_and_log(
        None, template_key=tk, recipient=adresy[0], cc=", ".join(adresy[1:]) or None, subject=f"Přijatý doklad: {nazev}"[:500],
        body=f"Dobrý den,\n\nv příloze zasíláme přijatý doklad „{nazev}“ (od: {od}, přijato {prijato}).\n\n{PODPIS}", auto=True)
    return log_id


def priloha_prijateho(cur, doc_id):
    """Priloha k e-mailu `prijaty_doklad:<id>` pri JEHO schvaleni: (filename, bytes, mime_subtype) ze Sdileneho disku, nebo None (soubor chybi)."""
    from drive import DRIVE_FILES_DIR
    cur.execute("SELECT drive_file_id FROM incoming_documents WHERE id=%s", (doc_id,))
    d = cur.fetchone()
    if not d or not d.get("drive_file_id"):
        return None
    cur.execute("SELECT filename, stored_filename, content_type FROM shared_drive_files WHERE id=%s", (d["drive_file_id"],))
    f = cur.fetchone()
    if not f or not f.get("stored_filename"):
        return None
    cesta = os.path.join(DRIVE_FILES_DIR, os.path.basename(f["stored_filename"]))
    try:
        with open(cesta, "rb") as fh:
            data = fh.read()
    except OSError:
        app.logger.warning("ucetni hak: soubor prijateho dokladu %s chybi na disku (%s)", doc_id, cesta)
        return None
    typ = (f.get("content_type") or "").lower()
    return f["filename"], data, ("pdf" if typ == "application/pdf" else "octet-stream")
