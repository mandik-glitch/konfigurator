"""Admin > Prodej > E-maily ucetni: kam posilat SCHVALENE doklady podle typu dokladu (bot16, 2026-10-06).

Robert (2026-10-06): "chceme schvalene doklady automaticky posilat na emaily ucetni, budou to ruzne emaily podle typu dokladu, postav nato tabulku v adminu".

TOHLE JE JEN TABULKA (adresy + aktivni + poznamka). NIC NEODESILA. Ucetni je EXTERNI prijemce, takze pravidlo 16 (WORKFLOW.md) plati beze zbytku: e-mail smi jen do fronty
`pending` a odejde az po schvaleni adminem; "automaticky" musi Robert pro tenhle pripad VYSLOVNE odvolat. Hak na schvaleni dokladu (approvals.py = vydane, incoming_documents.py =
prijate) po rozhodnuti zapoji bot5 (vlastnik dokladu a e-mailu) a adresy si vezme z `prijemci(cur, typ)`; do te doby se nic nezapojuje (ODESILANI_ZAPOJENO = False).

Ulozeni: app_settings `ucetni_emaily` (JSON, BEZ DDL):
  {"v": 1, "radky": {<typ>: {"adresy": [...], "aktivni": bool, "poznamka": str, "upraveno": ISO, "upravil_id": int, "upravil": str}}}
Typy jsou STABILNI KLICE: documents.DOCUMENT_TYPES (vydane doklady) + "prijaty_doklad" (incoming_documents); stitek se muze prejmenovat, klic ne. Novy typ v documents.DOCUMENT_TYPES se v tabulce
objevi sam (na konci, prazdny).
  GET /api/admin/ucetni-emaily          ("ucetni_emaily"/"zobrazit")  {"typy": [{kod, nazev, smer, adresy, aktivni, poznamka, upraveno, upravil}], "max_adres", "odesilani_zapojeno"}
  PUT /api/admin/ucetni-emaily/<kod>    ("ucetni_emaily"/"upravit")   body {adresy: [..] | "a, b", aktivni: bool, poznamka: str} -> upraveny radek; audit_log
  prijemci(cur, typ) -> [adresy]        jen cteni; [] kdyz je radek neaktivni / prazdny / poskozeny (fail closed); adresy se pri cteni znovu overuji
Adresy se pri ulozeni NORMALIZUJI (strip, mala pisma, bez duplicit, max 5 na typ) a OVERUJI (jeden platny tvar, zadne mezery/zavorky/uvozovky = zadna injekce do hlavicek).
"""
import datetime
import json
import re

from flask import request, jsonify

from app import app, get_conn, get_setting, require_permission, current_user, log_audit
from documents import DOCUMENT_TYPES, DOCUMENT_TYPE_LABELS

KLIC = "ucetni_emaily"
MAX_ADRES = 5
MAX_POZNAMKA = 200
ODESILANI_ZAPOJENO = False          # zmenit v KODU az bot5 zapoji hak na schvaleni dokladu (po Robertove vyslovnem rozhodnuti k pravidlu 16); UI podle toho ukazuje, ze se zatim nic neposila
PRIJATY = "prijaty_doklad"
_POREDI = ("invoice", "proforma_invoice", "payment_tax_document", "credit_note", "delivery_note")      # pro ucetni: faktura prvni
_NAZVY = {PRIJATY: "Přijaté doklady (od dodavatelů)"}
_ADRESA = re.compile(r"^[^\s@<>(),;:\\\"\[\]]{1,64}@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,24}$")
_DELIM = re.compile(r"[,;\s]+")
_ORIZNI = re.compile(r"[\x00-\x1f\x7f]+")


def typy():
    """[(kod, nazev, smer)] ve stabilnim poradi; typy pridane do documents.DOCUMENT_TYPES se pripoji na konec."""
    kody = [k for k in _POREDI if k in DOCUMENT_TYPES] + [k for k in DOCUMENT_TYPES if k not in _POREDI]
    return [(k, DOCUMENT_TYPE_LABELS.get(k, k), "vydany") for k in kody] + [(PRIJATY, _NAZVY[PRIJATY], "prijaty")]


def normalizuj_adresy(v):
    """-> (adresy, chyby): seznam (nebo text oddeleny carkou/strednikem/mezerou) -> male pismeno, bez duplicit, kazda overena; chyby = seznam textu pro uzivatele."""
    if v is None or v == "":
        return [], []
    if isinstance(v, str):
        polozky = _DELIM.split(v.strip())
    elif isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v):
        polozky = [p for x in v for p in _DELIM.split(x.strip())]
    else:
        return [], ["Adresy musí být seznam textů."]
    out, spatne = [], []
    for p in polozky:
        p = p.strip().lower()
        if not p:
            continue
        if len(p) > 254 or not _ADRESA.match(p):
            spatne.append(p[:80])
        elif p not in out:
            out.append(p)
    chyby = []
    if spatne:
        chyby.append("Neplatná adresa: %s." % ", ".join(spatne[:5]))
    if len(out) > MAX_ADRES:
        chyby.append("Nejvýš %d adres na jeden typ dokladu." % MAX_ADRES)
    return out, chyby


def _poznamka(v):
    return _ORIZNI.sub(" ", v).strip()[:MAX_POZNAMKA] if isinstance(v, str) else ""


def _nacti(cur):
    """ulozene radky {typ: {...}}; chybejici/rozbity JSON = prazdne (nic se neposila)"""
    raw = get_setting(cur, KLIC, None)
    try:
        d = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        d = {}
    radky = d.get("radky") if isinstance(d, dict) else None
    return radky if isinstance(radky, dict) else {}


def _verejny(kod, nazev, smer, r):
    r = r if isinstance(r, dict) else {}
    adresy = r.get("adresy") if isinstance(r.get("adresy"), list) else []
    return {
        "kod": kod, "nazev": nazev, "smer": smer,
        "adresy": [str(a) for a in adresy][:MAX_ADRES], "aktivni": r.get("aktivni") is True, "poznamka": _poznamka(r.get("poznamka")),
        "upraveno": r.get("upraveno") if isinstance(r.get("upraveno"), str) else None, "upravil": r.get("upravil") if isinstance(r.get("upravil"), str) else None,
    }


def prijemci(cur, kod):
    """Adresy ucetni pro typ dokladu: JEN CTENI. [] kdyz je radek neaktivni, prazdny nebo poskozeny (fail closed). Pro hak na schvaleni dokladu (bot5) - NEODESILA, vraci jen adresy;
    odeslani musi jit pres frontu `pending` (pravidlo 16)."""
    r = _nacti(cur).get(kod)
    if not isinstance(r, dict) or r.get("aktivni") is not True:
        return []
    adresy, chyby = normalizuj_adresy(r.get("adresy"))
    return [] if chyby else adresy


def _odpoved(radky):
    return {"typy": [_verejny(k, n, s, radky.get(k)) for k, n, s in typy()], "max_adres": MAX_ADRES, "odesilani_zapojeno": ODESILANI_ZAPOJENO}


@app.get("/api/admin/ucetni-emaily")
@require_permission("ucetni_emaily", "zobrazit")
def ucetni_emaily_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            radky = _nacti(cur)
    finally:
        conn.close()
    r = jsonify(_odpoved(radky))
    r.headers["Cache-Control"] = "no-store"
    return r


@app.put("/api/admin/ucetni-emaily/<kod>")
@require_permission("ucetni_emaily", "upravit")
def ucetni_emaily_put(kod):
    znamy = {k: (n, s) for k, n, s in typy()}
    if kod not in znamy:
        return jsonify({"error": "typ_neznamy", "message": "Neznámý typ dokladu."}), 404
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "telo_neplatne", "message": "Neplatné tělo požadavku."}), 400
    aktivni = body.get("aktivni", False)
    if not isinstance(aktivni, bool):
        return jsonify({"error": "aktivni_neplatne", "message": "„Aktivní“ musí být ano/ne."}), 400
    adresy, chyby = normalizuj_adresy(body.get("adresy"))
    if chyby:
        return jsonify({"error": "adresy_neplatne", "message": " ".join(chyby)}), 400
    if aktivni and not adresy:
        return jsonify({"error": "aktivni_bez_adres", "message": "Aktivní řádek musí mít aspoň jednu adresu."}), 400
    if "poznamka" in body and body["poznamka"] is not None and not isinstance(body["poznamka"], str):
        return jsonify({"error": "poznamka_neplatna", "message": "Poznámka musí být text."}), 400
    user = current_user()                                    # PRED get_conn() (pooled spojeni)
    novy = {"adresy": adresy, "aktivni": aktivni, "poznamka": _poznamka(body.get("poznamka")),
            "upraveno": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "upravil_id": user["id"], "upravil": (user.get("name") or user.get("email") or "")[:120]}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE setting_key=setting_key", (KLIC, json.dumps({"v": 1, "radky": {}})))
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s FOR UPDATE", (KLIC,))
            row = cur.fetchone()
            try:
                doc = json.loads(row["setting_value"]) if row and row["setting_value"] else {}
            except (TypeError, ValueError):
                doc = {}
            radky = doc.get("radky") if isinstance(doc, dict) and isinstance(doc.get("radky"), dict) else {}
            stary = radky.get(kod) if isinstance(radky.get(kod), dict) else {}
            radky[kod] = novy
            cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s", (json.dumps({"v": 1, "radky": radky}, ensure_ascii=False), KLIC))
        conn.commit()
    finally:
        conn.close()
    meta = ("upraveno", "upravil_id", "upravil")
    log_audit(user["id"], "update", "ucetni_emaily", None, {"typ": kod, "z": {k: v for k, v in stary.items() if k not in meta}, "na": {k: v for k, v in novy.items() if k not in meta}})
    n, s = znamy[kod]
    r = jsonify({"ok": True, "radek": _verejny(kod, n, s, novy)})
    r.headers["Cache-Control"] = "no-store"
    return r
