"""
CRM / poptavky (bot5, 2026-07-31).

Robert: "chodi ruzne maily, zdaleka ne vse jsou poptavky" + "aby se s
tim mohl dal pracovat zalozime zaroven vedeni poptavek a cele CRM" +
upresneno pres AskUserQuestion, ze CRM musi zachytit i UPLNE NOVE
kontakty, ne jen stavajici zakazniky ("Ale i nove").

NENI to obecny e-mailovy klient pro celou schranku - je to rozsireni
existujiciho tridiciho bodu v support_email_sync.py. Kazdy prichozi
e-mail se PRED stavajici _is_shop_related_email() branou klasifikuje
na "poptavka"/"jine". Poptavky konci tady (crm_leads/crm_lead_messages),
vse ostatni pokracuje beze zmeny stavajici support-related vetvi (nebo
tichym preskocenim, presne jako dnes).

Samostatne tabulky od shop_support_conversations/shop_support_messages -
jiny zivotni cyklus (pipeline stav, prirazeni obchodnikovi, konverze na
zakaznika/objednavku).

PUVODNE klasifikace bezela pres Anthropic API - zjisteno ale, ze
ANTHROPIC_API_KEY v .env je neplatny (viz AGENTS_LOG), takze fail-open
vzdy vracelo "jine" a CRM nic nezachytilo. Robert 2026-07-31: "nechme
to zatim na klicovych slovech, spatne zarazene e-maily oznacim kam
patri a system se to bude ucit" - klasifikace je ted ciste na
crm_classifier_words (viz sql/2026-07-31_crm_classifier_words.sql):
skore = soucet (poptavka_count - jine_count) pres slova v predmetu+
textu. Admin muze spatne zarazeny e-mail rucne prehodit (CRM tlacitko
"Toto neni poptavka" -> /reject nize, Podpora tlacitko "Toto je
poptavka" -> support.py::support_admin_mark_lead) - kazda takova
oprava zavola train_words() a posili prislusna pocitadla, takze system
se pri pouzivani sam uci bez zasahu do kodu.

Endpointy (admin, @require_permission("crm", ...)):
  GET    /api/admin/crm/leads                    - seznam + filtry + status_counts
  POST   /api/admin/crm/leads                    - rucni zalozeni poptavky (telefon/osobne)
  GET    /api/admin/crm/leads/<id>/messages       - detail + vlakno, oznaci precteno
  POST   /api/admin/crm/leads/<id>/reply          - odpoved (zapis + realny e-mail)
  PUT    /api/admin/crm/leads/<id>                - status/assigned_to/company_name/estimated_value
  POST   /api/admin/crm/leads/bulk-status         - hromadna zmena stavu
  DELETE /api/admin/crm/leads/bulk                - hromadne smazani vybranych poptavek
  POST   /api/admin/crm/leads/<id>/convert        - navrh/propojeni na shop_customers
  POST   /api/admin/crm/leads/<id>/reject         - "neni to poptavka" -> presun do Podpory + uceni
  GET    /api/admin/crm/leads/<id>/tasks          - ukoly/pripomenuti k poptavce
  POST   /api/admin/crm/leads/<id>/tasks          - novy ukol
  PUT    /api/admin/crm/leads/<id>/tasks/<tid>    - done/title/due_at
  DELETE /api/admin/crm/leads/<id>/tasks/<tid>
  GET    /api/admin/crm/leads/<id>/notes          - interni poznamky (NIKDY neposilane jako e-mail)
  POST   /api/admin/crm/leads/<id>/notes
  DELETE /api/admin/crm/leads/<id>/notes/<nid>
  GET    /api/admin/crm/dashboard                 - hodnota pipeline, win rate mesic, zpozdene ukoly
  GET    /api/admin/crm/assignable-users          - kdo muze mit lead prirazeny
  POST   /api/admin/crm/leads/<id>/create-quote   - rucni zalozeni/otevreni nabidky pro tento lead

Service-to-service (bot14, 2026-09-03, rozdeleni Remesla do /opt/remeslo,
zadano bot3): Remeslo backend uz nebeti ve stejnem originu/session jako
konfigurator, takze zalozeni leadu z remeslo-hlas.js (drive primy fetch
z prohlizece na tenhle modul) nahrazeno server-to-server volanim s
sdilenym klicem (viz REMESLO_INTERNAL_KEY nize) - stejny vzor jako
api/render_worker.py (X-Worker-Token/RENDER_WORKER_TOKEN pro vzdaleny
render worker), jen jina hlavicka/klic:
  POST   /api/internal/crm-leads                  - server-to-server zalozeni leadu (X-Internal-Service-Key)

Aktivace: `import crm` na konec app.py (za ostatnimi moduly) - a
DRIVE nez support_email_sync.py, ktery na `crm.*` primo vola.

DOPLNENO 2026-07-31 (tyz den, po srovnani s bežnymi CRM funkcemi):
Robert "Crm ma přece více funkcí ... tak tam všechno doplň" - pridana
hodnota obchodu (estimated_value), ukoly/pripomenuti, interni poznamky
a dashboard (viz sql/2026-07-31_crm_leads_extended.sql).

DOPLNENO 2026-08-01 (Nabidky, viz api/quotes.py pro cely kontext):
prechod leadu do stavu 'nabidnuto' (_apply_lead_update nize) ted
automaticky zalozi navazanou "nabidku" (adresarovou strukturu na
soubory/doklady) pres quotes.get_or_create_quote_for_lead() -
idempotentni, bezpecne volat opakovane. crm_admin_lead_messages()
navic vraci info o existujici nabidce pro CRM modal.
"""
import re
import os
import hmac
import datetime

from flask import request, jsonify

from app import (
    app, get_conn, require_permission, current_user, log_audit,
    parse_bulk_ids, bulk_delete, get_pagination_args, paginated_query,
    PERMISSION_ROLES, create_party,
)
from products import now_local
import customers
import gallery_items
import quotes

CRM_LEAD_STATUSES = ("nova", "v_jednani", "nabidnuto", "vyhrano", "prohrano")
CRM_CLOSED_STATUSES = ("vyhrano", "prohrano")

# Service-to-service autentizace pro Remeslo (bot14, 2026-09-03) - stejny
# vzor jako api/render_worker.py::_require_token()/RENDER_WORKER_TOKEN,
# jen jina hlavicka a klic (samostatny secret, at kompromitace jednoho
# volajiciho neohrozi ten druhy).
REMESLO_INTERNAL_KEY = os.environ.get("REMESLO_INTERNAL_KEY", "")


def _require_internal_service_key():
    if not REMESLO_INTERNAL_KEY:
        return jsonify({"error": "Service-to-service integrace neni na serveru nakonfigurovana (chybi REMESLO_INTERNAL_KEY)."}), 503
    # compare_digest - konstantni cas, at nejde klic odhadovat po znacich
    if not hmac.compare_digest(request.headers.get("X-Internal-Service-Key") or "", REMESLO_INTERNAL_KEY):
        return jsonify({"error": "Neplatny service klic."}), 401
    return None


def _recent_duplicate_lead(cur, *, craftsman_id, contact_email, window_seconds=60):
    """Ochrana proti timeoutu/retry na volajici (Remeslo) strane - server-
    to-server volani pres sit, ne klik ve stejnem prohlizeci, takze retry
    po neobdrzene odpovedi je realne riziko (viz koordinace s bot15/
    bot17). Jen KRATKE okno, ne trvala blokace - stejny princip jako
    api/emails.py::_recent_duplicate_send. Klic = craftsman_id +
    contact_email (jeden remeslnik muze mit vic zakazniku se stejnym
    e-mailem jen vyjimecne, ale ne v ramci 60s)."""
    cur.execute(
        "SELECT id FROM crm_leads WHERE craftsman_id=%s AND contact_email=%s "
        "AND source='remeslo' AND created_at >= NOW() - INTERVAL %s SECOND LIMIT 1",
        (craftsman_id, contact_email, window_seconds),
    )
    return cur.fetchone()
_MISSING = object()  # rozlisuje "klic v body vubec neni" od "je tam explicitni null"


def _tokenize(text):
    """Mnozina unikatnich slov (>=3 znaky, bez cislic) z textu - stejny
    tokenizer pro klasifikaci i uceni, aby oboji pocitalo se stejnymi
    "slovy". Mnozina (ne seznam) zamerne - opakovane slovo v jednom
    e-mailu se ma pocitat/ucit jen jednou, jinak by dlouhy e-mail
    prevazil skore jednim casto se opakujicim slovem."""
    return {w for w in re.findall(r"[^\W\d_]+", (text or "").lower()) if len(w) >= 3}


def classify_incoming_email(subject, body):
    """Vraci 'doklad' nebo 'jine' - klicova slova s ucenim (viz modulovy
    docstring). Fail-open na 'jine' (zadna slova, vypadek DB, ...) -
    nikdy nesmi shodit support_email_sync smycku a bezpecnejsi vychozi
    stav je "nezachytit" nez zaplavit CRM/Doklady omylem.

    AUTOMATICKA KLASIFIKACE NA 'poptavka' VYPNUTA (2026-09-03, Robert
    pres bot3: "boti zde nejsou vubec schopni rozeznat poptavku v
    prichozi poste, prestan to stitkovat") - slovni klasifikator byl
    na tuhle kategorii nespolehlivy. `poptavka_count` sloupec v
    crm_classifier_words a uceni (`train_words`) zustavaji funkcni
    beze zmeny - jde jen o RUCNI cestu (admin oznaci konverzaci jako
    poptavku, viz support.py::support_admin_mark_lead), a rucni
    sender-rule `force_poptavka` (viz support_email_sync.py) je
    lidske rozhodnuti pro konkretniho odesilatele, ne "bot co nepozna
    poptavku" - oboji dal funguje beze zmeny. Doklad/jine logika NENI
    zmenena (viz puvodni popis nize pro jeji kontext).

    DOPLNENO 2026-08-17 (bot8, Robert pres bot3: "nastavte potrebne k
    tomu, aby se emaily analyzovali na spam a opravdu doklady, ktere
    musime zavadet do ucetnictvi"): puvodne cisty binarni klasifikator
    (jedno skore poptavka_count-jine_count) rozsiren na 3 nezavisle
    soucty (poptavka/jine/doklad) + argmax mezi nimi - stejna
    crm_classifier_words tabulka, jen 3. sloupec (doklad_count).
    DULEZITE zjisteni pri rozsirovani: existujici seed data uz mela
    'faktura'/'fakturu' apod. SILNE svazane s 'jine' (0 poptavka, 4-5
    jine, viz sql/2026-07-31_crm_classifier_words.sql) - takze doklady
    (faktury od dodavatelu) uz driv spolehlive konci v 'jine', a
    protoze odesilatel faktury temer nikdy neni "eshopovy zakaznik"
    (_is_shop_related_email v support_email_sync.py), tise mizely bez
    ulozeni kamkoli - presne to, co Robert popsal ("proc chodi tak malo
    emailu"/"doklady, ktere musime zavadet"). Proto pri remíze mezi
    'jine' a 'doklad' vyhrava 'doklad' (radeji falesne pozitivni doklad
    v cekaci fronte na schvaleni, ktery admin jednim klikem zamitne, nez
    znovu tise ztraceny skutecny doklad)."""
    tokens = _tokenize(f"{subject}\n{body}")
    if not tokens:
        return "jine"
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(tokens))
                cur.execute(
                    f"SELECT jine_count, doklad_count FROM crm_classifier_words WHERE word IN ({placeholders})",
                    tuple(tokens),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        jine_score = sum(r["jine_count"] for r in rows)
        doklad_score = sum(r["doklad_count"] for r in rows)
        if doklad_score > 0 and doklad_score >= jine_score:
            return "doklad"
        return "jine"
    except Exception as e:
        print(f"[crm] classify_incoming_email selhalo: {e}")
        return "jine"


def train_words(cur, subject, body, label):
    """Zapise zpetnou vazbu (label = 'poptavka'/'doklad'/'jine') do
    crm_classifier_words - kazde unikatni slovo z predmetu+textu se
    posili o 1 v pocitadle prislusejicim label. Vola se na SDILENE
    cursoru (uz otevrena transakce volajiciho - viz /reject nize a
    support.py::support_admin_mark_lead), sama nic necommituje.
    DOPLNENO 2026-08-17 (bot8): 'doklad' pridan vedle puvodnich dvou
    (viz classify_incoming_email vyse pro plny kontext 3. kategorie)."""
    tokens = _tokenize(f"{subject}\n{body}")
    if not tokens:
        return
    col = {"poptavka": "poptavka_count", "doklad": "doklad_count"}.get(label, "jine_count")
    cur.executemany(
        f"INSERT INTO crm_classifier_words (word, {col}) VALUES (%s, 1) "
        f"ON DUPLICATE KEY UPDATE {col} = {col} + 1",
        [(t,) for t in tokens],
    )


def is_known_supplier_email(cur, from_email):
    """
    Robert 2026-08-24 (odpověď dodavatele TBA Plastové obaly na naši
    nákupní objednávku NO-2026-00037 - "RE: Objednávka ..." - skončila
    v Poptávkách): "objednávka v předmětu zprávy nemůže skončit v
    poptávkách, byla to reakce na naši nákupní objednávku". Bez ohledu
    na slovní klasifikátor (crm_classifier_words) - odesilatel, který je
    NAŠÍM evidovaným dodavatelem (shop_suppliers.email), nemůže být
    zákaznická poptávka. Kontrolováno stejně brzy jako match_sender_rule
    (viz support_email_sync.py) - PŘED klasifikátorem, ne dodatečnou
    opravou. Netýká se to jen force_objednavka sender-rule (ta vyžaduje
    ruční nastavení admina per odesílatel) - tohle je AUTOMATICKÉ pro
    KAŽDÉHO dodavatele, co už v systému evidujeme, bez nutnosti ho
    ručně přidávat.
    """
    if not from_email:
        return False
    cur.execute(
        "SELECT 1 FROM shop_suppliers WHERE LOWER(email)=%s AND active=1 LIMIT 1",
        (from_email.strip().lower(),),
    )
    return cur.fetchone() is not None


def match_sender_rule(cur, from_email):
    """Robert: admin panel "pro nastavovani filtru" - vyjimka podle
    odesilatele/domeny, kontroluje se PRED slovnim klasifikatorem
    (viz support_email_sync.py). Vzor zacinajici na "@" = shoda CELE
    domeny (from_email koncí na tenhle vzor), jinak presna shoda cele
    adresy. Kdyz matchuje vic pravidel, bere se nejnovejsi (ORDER BY id
    DESC) - admin muze pridanim noveho pravidla prekryt starsi, aniz by
    to staré musel mazat."""
    if not from_email:
        return None
    cur.execute("SELECT * FROM crm_classifier_sender_rules ORDER BY id DESC")
    for rule in cur.fetchall():
        pattern = (rule["pattern"] or "").strip().lower()
        if not pattern:
            continue
        if pattern.startswith("@"):
            if from_email.endswith(pattern):
                return rule
        elif from_email == pattern:
            return rule
    return None


def get_classifier_settings(cur):
    cur.execute("SELECT * FROM crm_classifier_settings WHERE id=1")
    row = cur.fetchone()
    return row or {
        "check_app_users": 1, "check_shop_customers": 1,
        "check_shop_orders": 1, "check_support_conversations": 1,
    }


def _looks_like_test_lead(subject):
    """Testovaci poptavka podle PREDMETU (Robert 2026-08-06: "testovaci
    poptavky automaticky archivujme") - slovo zacinajici na "test"
    (test, testovaci, TESTOVACI, [TEST...]), nezavisle na velikosti
    pismen. Zamerne jen predmet, ne telo - slovo "test" v bezne vete
    tela (napr. "potrebuji stul na testovani vzorku") nesmi realnou
    poptavku archivovat."""
    return bool(re.search(r"(?:^|[^a-zá-ž])test", (subject or ""), re.IGNORECASE))


def _normalize_subject(subject):
    """Vytahne "jadro" predmetu bez Re:/Fwd:/Aw: prefixu (i vicenasobnych,
    napr. "Re: Fwd: Re: neco") - pro fallback threadovani v
    find_or_create_lead() nize, kdyz e-mail nema pouzitelne Message-ID
    hlavicky (nektere klienty je neposilaji/meni). Zdrojova kopie
    support_email_sync.py::_normalize_subject - nejde importovat primo
    (support_email_sync.py uz importuje crm, cyklicky import), funkce
    je ale malinka/bezstavova, drzet 1:1 shodnou pri pripadne uprave."""
    s = (subject or "").strip()
    while True:
        m = re.match(r"^(re|fwd?|aw)\s*:\s*", s, re.IGNORECASE)
        if not m:
            break
        s = s[m.end():].strip()
    return s.lower()


LEAD_DRIVE_ROOT_FOLDER_NAME = "Nabídky"  # bot5, 2026-09-26 (nalezeno pri
# vysetrovani "kde je zakres?" u leadu 117): puvodni koren "Poptávky >
# nabídky" (a s nim kaskadove i vsech 50 uz vytvorenych vanRM- podslozek,
# viz crm_lead_folder_sequence.next_number=1050) byl nekdy mezi
# 2026-08-22 a 2026-08-31 smazan - shared_drive_folders.id=195 "Nabídky"
# vznikla 2026-08-31 jako NAHRADNI koren, ale tenhle retezec se od te
# doby nikdy neaktualizoval. Kazde volani ensure_lead_drive_folder() od
# 2026-08-31 tise vracelo None (root nenalezen, viz nize) - zadna
# vyjimka, zadny rollback, jen osirely radek v shared_drive_files.

MONTH_NAMES_CZ = (
    "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
)  # 1:1 kopie incoming_documents.MONTH_NAMES_CZ - nejde sdilet konstantu (cyklicky import), drzet shodne


def _next_lead_folder_number(cur):
    """VLASTNI sekvence pro nazvy Drive slozek poptavek (Robert 2026-08-22:
    "vanRM-<cislo>-<zakaznik>", cislo zacina na 1000, NEZAVISLE na
    crm_leads.id) - FOR UPDATE zamek na jedinem radku, stejny vzor jako
    quotes._next_quote_number()/crm.find_or_create_lead (TOCTOU ochrana
    pri soubeznem vzniku dvou poptavek)."""
    cur.execute("SELECT next_number FROM crm_lead_folder_sequence WHERE id=1 FOR UPDATE")
    n = cur.fetchone()["next_number"]
    cur.execute("UPDATE crm_lead_folder_sequence SET next_number=next_number+1 WHERE id=1")
    return n


def _lead_folder_label(lead):
    """Cast nazvu slozky za cislem - firma, jinak kontakt, jinak e-mail.
    Znaky nevhodne pro citelny nazev slozky nahrazeny podtrzitkem (slozky
    jsou jen DB radky, ne skutecne FS cesty, ale konzistentni citelny
    nazev at nepusobi rozbite v UI Sdileneho disku)."""
    base = (lead.get("company_name") or lead.get("contact_name") or lead.get("contact_email") or "").strip()
    base = re.sub(r'[\\/:*?"<>|]', "_", base)[:80]
    return base or "bez-jmena"


def ensure_lead_drive_folder(cur, lead_id):
    """Najde/zalozi Drive slozku poptavky - Robert 2026-08-22 (spojuje 2
    drivejsi ukoly, viz TASKS.md "CRM: automaticka slozka poptavky..."):
    `Poptavky > nabidky > <rok> > <mesic> > vanRM-<cislo>-<zakaznik>`.
    Idempotentni (kontroluje crm_leads.drive_folder_id) - bezpecne volat
    opakovane, i pro STAROU poptavku bez slozky (donacte se pri prvni
    dalsi zprave po zavedeni teto funkce). Pouziva
    drive._find_or_create_folder_path() (nezavisly `import drive` - crm.py
    se nacita PRED drive.py, viz app.py poradi importu, top-level import
    by byl nefunkcni). Pristupova prava nove slozky se dedi automaticky
    (drive._user_can_access_folder kontroluje jen KORENOVEHO predka, viz
    shared_drive_folder_roles pro folder_id=7) - nic dalsiho nastavovat
    netreba (otevrena otazka (c) z TASKS.md vyresena beze zmeny kodu)."""
    import drive
    cur.execute(
        "SELECT id, drive_folder_id, drive_folder_number, contact_name, company_name, contact_email, created_at "
        "FROM crm_leads WHERE id=%s FOR UPDATE",
        (lead_id,),
    )
    lead = cur.fetchone()
    if not lead or lead["drive_folder_id"]:
        return lead["drive_folder_id"] if lead else None

    cur.execute(
        "SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s",
        (LEAD_DRIVE_ROOT_FOLDER_NAME,),
    )
    root = cur.fetchone()
    if not root:
        # korenova slozka "Poptavky > nabidky" chybi (nemelo by nastat -
        # Robert: "korenova uz existuje") - bez ni nemame kam zalozit
        # podslozku, radeji nic nedelat nez zalozit vlastni novy koren
        print("[crm] ensure_lead_drive_folder: chybi korenova slozka "
              f"'{LEAD_DRIVE_ROOT_FOLDER_NAME}' na Sdilenem disku")
        return None

    number = lead["drive_folder_number"] or _next_lead_folder_number(cur)
    when = lead["created_at"] or datetime.datetime.now()
    segments = [
        str(when.year),
        MONTH_NAMES_CZ[when.month - 1],
        f"vanRM-{number}-{_lead_folder_label(lead)}",
    ]
    folder_id = drive._find_or_create_folder_path(cur, {"id": None}, root["id"], segments, {})
    cur.execute(
        "UPDATE crm_leads SET drive_folder_id=%s, drive_folder_number=%s WHERE id=%s",
        (folder_id, number, lead_id),
    )
    return folder_id


def find_or_create_lead(cur, contact_email, contact_name, subject, referenced_ids=None):
    """Zrcadli _find_or_create_conversation() v support_email_sync.py -
    bot10 2026-08-22, oprava puvodniho chovani (presna obdoba incidentu
    #42 opraveneho pro Podporu 2026-08-17, viz
    sql/2026-08-22_crm_lead_message_threading.sql pro cely kontext).
    Puvodni verze parovala VYHRADNE podle contact_email, bez ohledu na
    predmet/vlakno - dusledek: nesouvisejici nova poptavka od stejneho
    kontaktu se mohla mylne slit se starou otevrenou, a skutecna
    odpoved k uz uzavrene/archivovane poptavce zalozila zbytecne novy
    lead misto napojeni. Ted se pouziva skutecne threadovani, s
    parovanim podle e-mailu jako POSLEDNI zachrannou siti, ne prvnim/
    jedinym kriteriem.

    Priorita (prvni uspesna cesta vyhrava):
      1. **Skutecne threadovani** - kdyz tenhle e-mail (In-Reply-To/
         References, viz support_email_sync.py::_referenced_message_ids)
         odkazuje na Message-ID nektere jiz ulozene zpravy
         (crm_lead_messages.message_id_header), pouzije se JEJI lead -
         BEZ OHLEDU NA JEHO STAV (i vyhrano/prohrano/archivovano) -
         jde o definitivni dukaz souvislosti, ne jen shodu adresy, takze
         i odpoved na davno uzavrenou poptavku se spravne napoji.
      2. **Fallback bez pouzitelnych hlavicek** - existujici OTEVRENY,
         NEARCHIVOVANY lead se STEJNOU adresou A STEJNYM "jadrem"
         predmetu (bez Re:/Fwd:/Aw: prefixu) - jen kdyz #1 neuspeje
         (napr. odesilateluv klient Message-ID neposila). Stejne
         konzervativni omezeni na otevrene/nearchivovane jako puvodni
         kod - FOR UPDATE zachovano (bot23 2026-08-18 - TOCTOU race
         ochrana, viz puvodni komentar nize).
      3. **Jinak novy lead** - i kdyz uz pro tuhle adresu existuje JINY
         lead s ROZDILNYM tematem (jiny predmet, zadna threadovaci
         hlavicka), dostane VLASTNI radku, misto aby se prilepil do
         stare/nesouvisejici poptavky. Zkusi best-effort dohledat
         shop_customers.email podle stejne adresy (nikdy neblokuje -
         kontakt muze byt uplne novy). Testovaci predmet -> rovnou
         archived=1."""
    lead_id = None
    if referenced_ids:
        cur.execute(
            "SELECT lead_id FROM crm_lead_messages WHERE message_id_header IN %s "
            "ORDER BY id DESC LIMIT 1",
            (tuple(referenced_ids),),
        )
        row = cur.fetchone()
        if row:
            lead_id = row["lead_id"]

    # bot23 2026-08-18: FOR UPDATE - bez toho muze TOCTOU race (dva
    # souvisejici pozadavky pro stejny contact_email skoro soucasne,
    # napr. dvojite odeslani verejneho formulare + email sync tik)
    # vytvorit 2 samostatne leady pro jeden kontakt, misto sloucenych
    # zprav do jednoho vlakna. Neni to uplna zaruka bez unique indexu
    # na contact_email (InnoDB gap-locking bez indexu je slabsi), ale
    # zavazny/casty scenar to neni (nizka zavaznost, viz bug-hunt).
    if lead_id is None:
        normalized = _normalize_subject(subject)
        # Robert 2026-08-24 (David Kalina - fotky poslane z mobilu bez
        # predmetu, kazda skoncila jako VLASTNI poptavka misto sparovani):
        # puvodne `if normalized:` fallback preskocil ÚPLNĚ, kdyz byl
        # predmet prazdny - u e-mailu bez predmetu (bezne u "sdilet
        # fotku" z mobilu) tak KAZDA dalsi zprava od stejneho kontaktu
        # bez pouzitelnych threadovacich hlavicek vytvorila novou
        # poptavku, misto aby se prilepila ke stavajici otevrene. Ted:
        # prazdny predmet se pari s JINYM prazdnym predmetem (stejny
        # kontakt, existujici otevrena poptavka) - realny predmet se
        # porad pari jen s presnou shodou jako drive.
        cur.execute(
            "SELECT id, subject FROM crm_leads WHERE contact_email=%s AND status NOT IN ('vyhrano','prohrano') "
            "AND archived=0 ORDER BY last_message_at DESC FOR UPDATE",
            (contact_email,),
        )
        for cand in cur.fetchall():
            cand_normalized = _normalize_subject(cand["subject"])
            if (normalized and cand_normalized == normalized) or (not normalized and not cand_normalized):
                lead_id = cand["id"]
                break

    if lead_id is None:
        cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (contact_email,))
        cust = cur.fetchone()
        cur.execute(
            "INSERT INTO crm_leads (customer_id, contact_name, contact_email, subject, archived) "
            "VALUES (%s,%s,%s,%s,%s)",
            (cust["id"] if cust else None, contact_name, contact_email, subject,
             1 if _looks_like_test_lead(subject) else 0),
        )
        lead_id = cur.lastrowid

    # bot10 2026-08-22 (Robert): kazda poptavka mela mit vlastni slozku na
    # Sdilenem disku (Poptavky > nabidky > rok > mesic > vanRM-...) - viz
    # ensure_lead_drive_folder() nize. VYPNUTO (Robert pres bot3,
    # 2026-09-14): "emaily uz nechodí, celé to nefungovalo skrze spatne
    # stitkovani" - classify_incoming_email() spatne rozpoznavala
    # poptavky, takze automaticke vanRM-* slozky vznikaly i pro
    # neco, co poptavka vubec nebyla. Robert existujici vanRM-* slozky
    # na Sdilenem disku smaze rucne sam. Funkce ensure_lead_drive_folder
    # samotna ZUSTAVA (pouziva ji dal support.py/quotes.py pro
    # ULOZENI SKUTECNE prilohy/nabidky do existujici/donactene slozky -
    # to je zamerne odlisne od TOHOTO automatickeho vytvareni na kazdou
    # (i spatne rozpoznanou) poptavku) - jen tenhle jeden automaticky
    # call site je odpojeny, at jde snadno zapnout zpet, kdyz se
    # stitkovani opravi.
    return lead_id


def _serialize_lead(row):
    return {
        "id": row["id"], "customer_id": row["customer_id"],
        # Modul 3 (REMESLO_KONCEPT.md, bot11 2026-08-19) - NULL = puvodni
        # vyznam (nas eshopovy lead), vyplnene = leadu "mini-CRM" zaznam
        # KONKRETNIHO remeslnika.
        "craftsman_id": row.get("craftsman_id"),
        "contact_name": row["contact_name"], "contact_email": row["contact_email"],
        "contact_phone": row["contact_phone"], "company_name": row["company_name"],
        "estimated_value": float(row["estimated_value"]) if row.get("estimated_value") is not None else None,
        "source": row["source"], "subject": row["subject"], "status": row["status"],
        "assigned_to": row["assigned_to"], "order_id": row["order_id"],
        "unread_by_admin": bool(row["unread_by_admin"]),
        "archived": bool(row.get("archived")),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
        "closed_at": row["closed_at"].isoformat() if row.get("closed_at") else None,
        # bot5, 2026-09-27 - viz komentar u crm_admin_leads_list(): nahled
        # posledni zpravy, at je v seznamu videt i kdyz se noveho tema
        # slouci do stareho vlakna se starym `subject`. Pritomne jen kdyz
        # base_sql poslal last_message_body (detail-endpoint ho neposila,
        # tam uz admin vidi cele vlakno primo).
        "last_message_preview": _message_preview(row["last_message_body"]) if "last_message_body" in row else None,
        # bot5, 2026-09-28 (Robert primo: "úkol z poptávky by se měl
        # propsat do přehledu do nového sloupce") - nejblizsi nesplneny
        # ukol, jen kdyz base_sql poslal next_task_title (viz
        # crm_admin_leads_list, detail-endpoint ma vlastni tasky primo).
        "next_task_title": row["next_task_title"] if "next_task_title" in row else None,
        "next_task_due_at": (row["next_task_due_at"].isoformat() if row.get("next_task_due_at") else None) if "next_task_due_at" in row else None,
    }


def _message_preview(body, max_len=80):
    if not body:
        return None
    flat = re.sub(r"\s+", " ", body).strip()
    return (flat[:max_len] + "…") if len(flat) > max_len else flat


def _serialize_message(row):
    return {
        "id": row["id"], "lead_id": row["lead_id"], "sender_type": row["sender_type"],
        "sender_user_id": row["sender_user_id"], "sender_name": row["sender_name"],
        "body": row["body"],
        # body_html - viz stejne pole v api/support.py._serialize_message
        "body_html": row.get("body_html"),
        # email_status (Robert 2026-08-24: "fajfka pokud je odpoved
        # odeslana") - pending/sent/failed z propojeneho shop_emails
        # zaznamu (viz email_log_id, crm_admin_lead_reply), None u
        # zprav bez e-mailu (napr. zakaznikuv puvodni dotaz).
        "email_status": row.get("email_status"),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@app.get("/api/admin/crm/leads")
@require_permission("crm", "zobrazit")
def crm_admin_leads_list():
    status = request.args.get("status")
    assigned_to = request.args.get("assigned_to", type=int)
    craftsman_id = request.args.get("craftsman_id", type=int)
    q = (request.args.get("q") or "").strip()
    unread_only = request.args.get("unread_only") == "1"
    sort = "ASC" if request.args.get("sort") == "oldest" else "DESC"

    archived = request.args.get("archived") == "1"

    where, params = [], []
    # Archiv je vlastni pohled - bezne zalozky archivovane poptavky
    # nikdy neukazuji (Robert 2026-08-06: auto-archivace testovacich).
    where.append("archived=1" if archived else "archived=0")
    if status:
        where.append("status=%s"); params.append(status)
    if assigned_to:
        where.append("assigned_to=%s"); params.append(assigned_to)
    if craftsman_id:
        # Modul 3 (bot11 2026-08-19) - filtr na "mini-CRM" leady
        # konkretniho remeslnika, viz REMESLO_KONCEPT.md.
        where.append("craftsman_id=%s"); params.append(craftsman_id)
    if q:
        where.append("(contact_name LIKE %s OR contact_email LIKE %s OR company_name LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])
    if unread_only:
        where.append("unread_by_admin=1")

    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # bot5, 2026-09-27 (Robert 2x zmateny "žádný dotaz sem nespadl" -
            # bot3 zjistil, ze zprava DORAZILA spravne, jen se sloucila do
            # STAREHO vlakna se starym zamrzlym `subject` - seznam nikde
            # neukazoval, ze prislo neco NOVEHO). last_message_body =
            # nahled POSLEDNI zpravy vlakna (korelovany subselect, ne JOIN -
            # jednodussi na LIMIT 1 "posledni radek"), nezavisi na
            # find_or_create_lead() slucovaci logice, jen zobrazeni.
            # bot5, 2026-09-28 (Robert primo: "úkol z poptávky by se měl
            # propsat do přehledu do nového sloupce") - nejblizsi NESPLNENY
            # ukol (stejne razeni jako v samotnem detailu poptavky, viz
            # crm_admin_lead_tasks_list - nejdriv s terminem, driv splatny
            # napřed), korelovany subselect stejneho stylu jako
            # last_message_body vyse.
            base_sql = (
                "SELECT crm_leads.*, "
                "(SELECT body FROM crm_lead_messages m WHERE m.lead_id = crm_leads.id "
                " ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS last_message_body, "
                "(SELECT title FROM crm_lead_tasks t WHERE t.lead_id = crm_leads.id AND t.done=0 "
                " ORDER BY (t.due_at IS NULL) ASC, t.due_at ASC, t.id ASC LIMIT 1) AS next_task_title, "
                "(SELECT due_at FROM crm_lead_tasks t WHERE t.lead_id = crm_leads.id AND t.done=0 "
                " ORDER BY (t.due_at IS NULL) ASC, t.due_at ASC, t.id ASC LIMIT 1) AS next_task_due_at "
                "FROM crm_leads"
            )
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params,
                                           f" ORDER BY unread_by_admin DESC, last_message_at {sort}", page, page_size)

            cur.execute("SELECT status, COUNT(*) AS n FROM crm_leads WHERE archived=0 GROUP BY status")
            status_counts = {r["status"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) AS n FROM crm_leads WHERE unread_by_admin=1 AND archived=0")
            unread_count = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM crm_leads WHERE archived=1")
            archived_count = cur.fetchone()["n"]
    finally:
        conn.close()
    resp = {
        "leads": [_serialize_lead(r) for r in rows],
        "unread_count": unread_count,
        "status_counts": status_counts,
        "archived_count": archived_count,
    }
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.post("/api/admin/crm/leads")
@require_permission("crm", "vytvorit")
def crm_admin_lead_create():
    """Rucni zalozeni poptavky (Robert: "Crm ma přece více funkcí ...
    tak tam všechno doplň" - dosud leady vznikaly VYHRADNE z e-mailu,
    telefonicky/osobni kontakt sel zapsat jen jako Podpora, ne jako
    obchodni prilezitost s pipeline stavem). Na rozdil od
    find_or_create_lead() (pouziva e-mailova synchronizace) VZDY zalozi
    novy radek - rucni pridani je vedoma akce operatora, ne automaticke
    deduplikovani prichoziho e-mailu. Novy lead se rovnou priradi tomu,
    kdo ho zalozil (bezny CRM zvyk - kdo prijal poptavku, ten ji resi)."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    contact_email = (body.get("contact_email") or "").strip().lower()
    if not contact_email:
        return jsonify({"error": "E-mail kontaktu je povinný."}), 400
    contact_name = (body.get("contact_name") or "").strip() or None
    contact_phone = (body.get("contact_phone") or "").strip() or None
    company_name = (body.get("company_name") or "").strip() or None
    subject = (body.get("subject") or "").strip() or None
    estimated_value = body.get("estimated_value")
    if estimated_value not in (None, ""):
        try:
            estimated_value = float(estimated_value)
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatná hodnota obchodu."}), 400
    else:
        estimated_value = None
    # Modul 3 (bot11 2026-08-19) - volitelne rovnou pri zalozeni oznacit
    # lead jako "mini-CRM" zaznam konkretniho remeslnika.
    craftsman_id = body.get("craftsman_id") or None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (contact_email,))
            cust = cur.fetchone()
            cur.execute(
                "INSERT INTO crm_leads (customer_id, craftsman_id, contact_name, contact_email, contact_phone, "
                "company_name, subject, estimated_value, source, assigned_to, unread_by_admin) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'manual',%s,0)",
                (cust["id"] if cust else None, craftsman_id, contact_name, contact_email, contact_phone,
                 company_name, subject, estimated_value, admin["id"]),
            )
            lead_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "crm_lead", lead_id, contact_email)
    return jsonify({"status": "ok", "id": lead_id}), 201


@app.post("/api/internal/crm-leads")
def crm_internal_lead_create():
    """Server-to-server varianta crm_admin_lead_create() pro Remeslo
    (viz modulovy docstring) - zadna admin session/current_user(), misto
    toho X-Internal-Service-Key. craftsman_id POVINNE (na rozdil od
    admin verze) - kazde volani vznika z konkretniho remeslnika v
    Remeslu, ne z rucniho zalozeni administratorem. source='remeslo'
    (ne 'manual', at jde v CRM UI rozlisit puvod), assigned_to=NULL
    (zadny konkretni admin), log_audit(None, ...) - zavedena konvence
    pro systemove akce bez lidskeho aktera (viz api/bank_statements.py)."""
    err = _require_internal_service_key()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    craftsman_id = body.get("craftsman_id")
    if not craftsman_id:
        return jsonify({"error": "Chybí craftsman_id."}), 400
    contact_email = (body.get("contact_email") or "").strip().lower()
    if not contact_email:
        return jsonify({"error": "E-mail kontaktu je povinný."}), 400
    contact_name = (body.get("contact_name") or "").strip() or None
    contact_phone = (body.get("contact_phone") or "").strip() or None
    company_name = (body.get("company_name") or "").strip() or None
    subject = (body.get("subject") or "").strip() or None
    estimated_value = body.get("estimated_value")
    if estimated_value not in (None, ""):
        try:
            estimated_value = float(estimated_value)
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatná hodnota obchodu."}), 400
    else:
        estimated_value = None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            dup = _recent_duplicate_lead(cur, craftsman_id=craftsman_id, contact_email=contact_email)
            if dup:
                return jsonify({"status": "ok", "id": dup["id"], "duplicate": True}), 200
            cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (contact_email,))
            cust = cur.fetchone()
            cur.execute(
                "INSERT INTO crm_leads (customer_id, craftsman_id, contact_name, contact_email, contact_phone, "
                "company_name, subject, estimated_value, source, assigned_to, unread_by_admin) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'remeslo',NULL,1)",
                (cust["id"] if cust else None, craftsman_id, contact_name, contact_email, contact_phone,
                 company_name, subject, estimated_value),
            )
            lead_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(None, "create", "crm_lead", lead_id, f"remeslo craftsman_id={craftsman_id}: {contact_email}")
    return jsonify({"status": "ok", "id": lead_id}), 201


@app.get("/api/admin/crm/leads/<int:lead_id>/messages")
@require_permission("crm", "zobrazit")
def crm_admin_lead_messages(lead_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crm_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Poptávka neexistuje."}), 404
            cur.execute(
                "SELECT m.*, e.status AS email_status FROM crm_lead_messages m "
                "LEFT JOIN shop_emails e ON e.id = m.email_log_id "
                "WHERE m.lead_id=%s ORDER BY m.created_at ASC, m.id ASC",
                (lead_id,),
            )
            messages = cur.fetchall()
            if lead["unread_by_admin"]:
                cur.execute("UPDATE crm_leads SET unread_by_admin=0 WHERE id=%s", (lead_id,))
                conn.commit()
                lead["unread_by_admin"] = 0
            # Nabidky (viz api/quotes.py) - jen pro detail (NE do
            # crm_admin_leads_list, aby se seznam zbytecne nezatezoval JOINem).
            cur.execute(
                "SELECT id, quote_number, client_label FROM crm_quotes WHERE lead_id=%s "
                "ORDER BY created_at DESC LIMIT 1",
                (lead_id,),
            )
            quote = cur.fetchone()
    finally:
        conn.close()
    return jsonify({
        "lead": _serialize_lead(lead),
        "messages": [_serialize_message(m) for m in messages],
        "quote": ({"id": quote["id"], "quote_number": f"{quotes.QUOTE_PREFIX}{quote['quote_number']}",
                    "client_label": quote["client_label"]} if quote else None),
    })


@app.put("/api/admin/crm/leads/<int:lead_id>/messages/<int:message_id>/move")
@require_permission("crm", "upravit")
def crm_admin_lead_message_move(lead_id, message_id):
    """Presun jedne existujici zpravy na JINY lead - obecny admin
    nastroj pro opravu spatne sparovane zpravy (bot10, 2026-08-26,
    schvaleno bot3, navazuje na audit AUDIT_OPTIMALIZACE_2026-08-26.md
    "inquiries.py bod 2"). WORKFLOW.md bod 17 ("kdekoli appka
    automaticky sloucuje do existujiciho zaznamu, potrebuje vedle sebe
    rucni override") uz je zaveden PRI trideni (support.py::
    _move_conversation_to_crm lead_id_override) - tohle je ZPETNA verze
    stejneho principu (oprava PO faktu, ne jen volba predem), a je
    zamerne obecna (funguje pro zpravu z JAKEHOKOLI zdroje - web
    formular, e-mail, rucne pridana), ne vazana jen na inquiries.py."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    target_lead_id = body.get("target_lead_id")
    if not target_lead_id:
        return jsonify({"error": "Chybí target_lead_id."}), 400
    try:
        target_lead_id = int(target_lead_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné target_lead_id."}), 400
    if target_lead_id == lead_id:
        return jsonify({"error": "Zpráva už u téhle poptávky je."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_leads WHERE id=%s", (lead_id,))
            if not cur.fetchone():
                return jsonify({"error": "Zdrojová poptávka neexistuje."}), 404
            cur.execute("SELECT id FROM crm_leads WHERE id=%s", (target_lead_id,))
            if not cur.fetchone():
                return jsonify({"error": "Cílová poptávka neexistuje."}), 404
            cur.execute("SELECT id, lead_id FROM crm_lead_messages WHERE id=%s", (message_id,))
            msg = cur.fetchone()
            if not msg:
                return jsonify({"error": "Zpráva neexistuje."}), 404
            if msg["lead_id"] != lead_id:
                return jsonify({"error": "Zpráva nepatří k uvedené zdrojové poptávce."}), 400
            cur.execute("UPDATE crm_lead_messages SET lead_id=%s WHERE id=%s", (target_lead_id, message_id))
            # last_message_at prepocitat ze SKUTECNEHO stavu (ne jen
            # NOW()) - zdrojovy lead muze mit i jine, novejsi zpravy.
            for lid in (lead_id, target_lead_id):
                cur.execute("SELECT MAX(created_at) AS m FROM crm_lead_messages WHERE lead_id=%s", (lid,))
                row = cur.fetchone()
                cur.execute("UPDATE crm_leads SET last_message_at=%s WHERE id=%s", (row["m"], lid))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "crm_lead_message", message_id,
              f"přesunuto z poptávky {lead_id} na {target_lead_id}")
    return jsonify({"status": "ok"})


@app.post("/api/admin/crm/leads/<int:lead_id>/reply")
@require_permission("crm", "vytvorit")
def crm_admin_lead_reply(lead_id):
    """Stejny princip jako support.py::support_admin_reply - odpoved se
    KROME zapisu do vlakna posle i jako skutecny e-mail. Selhani
    odeslani nesmi shodit samotnou odpoved (potichu se zaloguje)."""
    admin = current_user()
    body = (request.get_json(silent=True) or {}).get("body", "").strip()
    if not body:
        return jsonify({"error": "Zpráva je prázdná."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, contact_email, subject FROM crm_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Poptávka neexistuje."}), 404
            cur.execute(
                "INSERT INTO crm_lead_messages (lead_id, sender_type, sender_user_id, sender_name, body) "
                "VALUES (%s,'operator',%s,%s,%s)",
                (lead_id, admin["id"], admin.get("name") or admin["email"], body),
            )
            new_message_id = cur.lastrowid
            cur.execute("UPDATE crm_leads SET last_message_at=NOW() WHERE id=%s", (lead_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "reply", "crm_lead", lead_id, body[:200])
    email_status = email_error = None
    if lead.get("contact_email"):
        # Robert 2026-08-24: "v poptávce se odpovědi musí brát jako
        # požadavky odeslání e-mailu" - odpověď napsal, ale nic viditelně
        # neodešlo. Kořen: primý send_email() bez emails.send_and_log()
        # (na rozdíl od zbytku appky) - žádný záznam v shop_emails, žádná
        # viditelnost v "Emaily odchozí", a selhání SMTP se tiše ztratilo
        # jen do server logu (print).
        #
        # ZPŘESNĚNO (Robert, stejný den): "odpověď odeslaná z poptávky
        # musí skončit ve schvalovací frontě e-mailů k odeslání" - ne
        # rovnou odeslat (auto=False), i kdyz to napsal admin - VZDY
        # auto=True, zalogovana jako 'pending', ceka na schvaleni v
        # "Emaily odchozí" jako cokoliv jineho automaticke. Dusledna
        # aplikace WORKFLOW.md bodu 16 i na tenhle posledni vyjimkovy
        # pripad primeho send_email().
        import emails  # lazy - stejny duvod jako "import support"/"import orders" jinde
        subject = f"Re: {lead['subject']}" if lead.get("subject") else "Odpověď na Vaši poptávku – LOGIMAN"
        _log_id, email_status, email_error = emails.send_and_log(
            None, template_key="custom", recipient=lead["contact_email"],
            subject=subject, body=body, admin=admin, auto=True,
        )
        # Robert 2026-08-24: "udělej fajfku pokud je odpověď odeslána" -
        # propojeni teto konkretni zpravy ve vlakne na jeji shop_emails
        # zaznam, aby se dal zobrazit AKTUALNI stav (pending pri odeslani
        # se casem zmeni na sent/failed po schvaleni v Emaily odchozí -
        # viz crm_admin_lead_messages, ktery ho pri kazdem nacteni vlakna
        # cte znovu, ne jen jednorazovy vysledek z okamziku odeslani).
        if _log_id:
            conn2 = get_conn()
            try:
                with conn2.cursor() as cur2:
                    cur2.execute(
                        "UPDATE crm_lead_messages SET email_log_id=%s WHERE id=%s",
                        (_log_id, new_message_id),
                    )
                conn2.commit()
            finally:
                conn2.close()
    return jsonify({"status": "ok", "email_status": email_status, "email_error": email_error})


@app.post("/api/admin/crm/leads/<int:lead_id>/create-quote")
@require_permission("crm", "upravit")
def crm_admin_lead_create_quote(lead_id):
    """Rucni protejsek k automatickemu vzniku nabidky pri prechodu do
    'nabidnuto' (viz _apply_lead_update nize) - pro pripad, ze admin
    chce nabidku pripravit driv, nez oficialne zmeni stav. Idempotentni
    (stejna funkce jako automaticky trigger)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crm_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Poptávka neexistuje."}), 404
            quote_id = quotes.get_or_create_quote_for_lead(cur, lead, created_by=admin["id"])
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "quote_id": quote_id})


def _apply_lead_update(lead_id, new_status=None, assigned_to=None, company_name=None, estimated_value=_MISSING, archived=None, craftsman_id=None):
    if new_status is not None and new_status not in CRM_LEAD_STATUSES:
        return False, "Neplatný status."
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crm_leads WHERE id=%s FOR UPDATE", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                conn.rollback()
                return False, "Poptávka neexistuje."
            fields, params = [], []
            if new_status is not None:
                fields.append("status=%s"); params.append(new_status)
                # closed_at drzi kdy lead presel do vyhrano/prohrano - viz
                # modulovy docstring, potreba pro dashboard "win rate tento
                # mesic" (last_message_at odrazi zpravu, ne zmenu stavu).
                # SQL literal NOW()/NULL, ne parametr - proto mimo fields/params.
                fields.append("closed_at=NOW()" if new_status in CRM_CLOSED_STATUSES else "closed_at=NULL")
            if assigned_to is not None:
                fields.append("assigned_to=%s"); params.append(assigned_to or None)
            if company_name is not None:
                fields.append("company_name=%s"); params.append(company_name or None)
            if estimated_value is not _MISSING:
                if estimated_value in (None, ""):
                    fields.append("estimated_value=%s"); params.append(None)
                else:
                    try:
                        estimated_value = float(estimated_value)
                    except (TypeError, ValueError):
                        conn.rollback()
                        return False, "Neplatná hodnota obchodu."
                    fields.append("estimated_value=%s"); params.append(estimated_value)
            if archived is not None:
                # rucni archivace/obnova z detailu poptavky
                fields.append("archived=%s"); params.append(1 if archived else 0)
            if craftsman_id is not None:
                # Modul 3 (bot11 2026-08-19) - preradit/odebrat "mini-CRM"
                # vazbu na remeslnika, stejny idiom jako assigned_to vyse.
                fields.append("craftsman_id=%s"); params.append(craftsman_id or None)
            if not fields:
                conn.rollback()
                return False, "Nebyla zadána žádná změna."
            params.append(lead_id)
            cur.execute(f"UPDATE crm_leads SET {', '.join(fields)} WHERE id=%s", params)
            # Nabidky (Robert 2026-08-01, viz api/quotes.py): prechod do
            # "nabidnuto" automaticky zalozi navazanou nabidku.
            # get_or_create_quote_for_lead je idempotentni - bezpecne
            # volat i pri opakovanem ulozeni stejneho stavu (vc.
            # crm_admin_leads_bulk_status nize, ktera tuhle funkci vola
            # v cyklu).
            if new_status == "nabidnuto":
                quotes.get_or_create_quote_for_lead(cur, lead, created_by=None)
        conn.commit()
    finally:
        conn.close()
    return True, None


@app.put("/api/admin/crm/leads/<int:lead_id>")
@require_permission("crm", "upravit")
def crm_admin_lead_update(lead_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ok, err = _apply_lead_update(
        lead_id,
        new_status=body.get("status"),
        assigned_to=body.get("assigned_to") if "assigned_to" in body else None,
        company_name=body.get("company_name") if "company_name" in body else None,
        estimated_value=body.get("estimated_value") if "estimated_value" in body else _MISSING,
        archived=bool(body.get("archived")) if "archived" in body else None,
        craftsman_id=body.get("craftsman_id") if "craftsman_id" in body else None,
    )
    if not ok:
        return jsonify({"error": err}), 400
    log_audit(admin["id"], "update", "crm_lead", lead_id, str(body))
    return jsonify({"status": "ok"})


@app.post("/api/admin/crm/leads/bulk-status")
@require_permission("crm", "upravit")
def crm_admin_leads_bulk_status():
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    new_status = body.get("status")
    if new_status not in CRM_LEAD_STATUSES:
        return jsonify({"error": "Neplatný status."}), 400
    updated, failed = 0, []
    for lead_id in ids:
        ok, e = _apply_lead_update(lead_id, new_status=new_status)
        if ok:
            updated += 1
        else:
            failed.append({"id": lead_id, "error": e})
    admin = current_user()
    log_audit(admin["id"], "bulk_update", "crm_lead", None, f"{updated} poptávek -> {new_status}")
    return jsonify({"status": "ok", "updated": updated, "failed": failed})


@app.delete("/api/admin/crm/leads/bulk")
@require_permission("crm", "smazat")
def crm_admin_leads_bulk_delete():
    """Hromadne smazani VYBRANYCH poptavek (Robert: "v poptávkách chybí
    bulk mazání poptávek") - stejny vzor jako
    support.py::support_admin_bulk_delete. Na rozdil od /reject (ktery
    poptavku PRESOUVA do Podpory a uci klasifikator) je tohle proste
    tvrde smazani. crm_lead_messages/crm_lead_tasks/crm_lead_notes/
    crm_lead_message_attachments kaskaduji na urovni DB (ON DELETE
    CASCADE), ale fotky (gallery_items, owner_type='lead') a e-mailove
    prilohy NA DISKU ne - uklizeny explicitne, stejny princip jako
    crm_admin_lead_reject vyse. crm_quotes.lead_id ma ON DELETE SET
    NULL - navazane nabidky PREZIJI (stejne jako u /reject)."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    attachment_filenames = []
    try:
        with conn.cursor() as cur:
            for lead_id in ids:
                attachment_filenames.extend(quotes.lead_attachment_filenames(cur, lead_id))
            deleted = bulk_delete(cur, "crm_leads", ids)
        conn.commit()
    finally:
        conn.close()
    for lead_id in ids:
        gallery_items.delete_items_for_owner("lead", lead_id)
    quotes.remove_lead_attachment_files(attachment_filenames)
    log_audit(admin["id"], "bulk_delete", "crm_lead", None, f"{deleted} poptávek smazáno")
    return jsonify({"status": "ok", "deleted": deleted})


# bot9, 2026-08-21 oprava: puvodni [CC]/[CC] tridy byly preklep (2x
# ASCII "C" - nic navic oproti holemu "C"), realna ceska podepsani pisi
# diakritiku ("IČO"/"DIČ") - bez [ČC] tenhle typicky pripad vubec
# nesedel (overeno na skutecnem leadu #39 "dič: CZ25247841"). Zaroven
# _SIGNATURE_COMPANY_RE puvodne vyzadovala ^...$ na cele "radce" - e-maily
# ale chodi jako jeden zaplacenty HTML blok bez internich \n, takze
# kotva $ (konec radky) nikdy nesedela na nic uprostred textu. Nahrazeno
# necislovanou kotvou - captures 1-4 slova s velkym pocatecnim pismenem
# bezprostredne pred pravni formou (odriznuti "Martin Lacina - jednatel"
# funguje diky tomu, ze "jednatel" zacina malym pismenem).
_SIGNATURE_ICO_RE = re.compile(r"\bI[ČC]O\s*:?\s*(\d{8})\b", re.IGNORECASE)
_SIGNATURE_DIC_RE = re.compile(r"\bDI[ČC]\s*:?\s*(CZ\d{8,10})\b", re.IGNORECASE)
_SIGNATURE_PHONE_RE = re.compile(r"(?:tel(?:efon)?|mobil)\.?\s*:?\s*([+\d][\d\s]{7,})", re.IGNORECASE)
_SIGNATURE_COMPANY_RE = re.compile(
    r"((?:[A-ZÁ-Ž][\w.&-]*\s+){1,4}(?:s\.\s?r\.\s?o\.|a\.\s?s\.|spol\.\s?s\s?r\.\s?o\.|v\.\s?o\.\s?s\.|k\.\s?s\.))"
)


def _extract_signature_fields(text):
    """Best-effort vytazeni firemnich udaju z volneho textu e-mailu
    (typicky podpis) - Robert 2026-08-21: chce, aby fungoval prevod na
    zakaznika primo z udaju v tele e-mailu. Pouziva se jako fallback v
    crm_admin_lead_convert, kdyz lead.company_name/contact_phone nejsou
    vyplnene. Nikdy nehadat - kdyz vzor nesedi, prislusne pole zustane
    None a rozhodnuti necha na clovekovi."""
    if not text:
        return {"company_name": None, "ico": None, "dic": None, "phone": None}

    company_match = _SIGNATURE_COMPANY_RE.search(text)
    company_name = company_match.group(1).strip() if company_match else None

    ico_match = _SIGNATURE_ICO_RE.search(text)
    ico = ico_match.group(1) if ico_match else None

    dic_match = _SIGNATURE_DIC_RE.search(text)
    dic = dic_match.group(1).upper() if dic_match else None

    # CZ+8 cislic je u standardnich platcu DIC = "CZ" + ICO - kdyz ICO
    # samo v textu nebylo (jen DIC), odvodit ho odtud (jen tenhle bezny
    # tvar, ne delsi/jine DIC formaty).
    if not ico and dic and re.match(r"^CZ\d{8}$", dic):
        ico = dic[2:]

    phone = None
    phone_match = _SIGNATURE_PHONE_RE.search(text)
    if phone_match:
        digits = re.sub(r"[^\d+]", "", phone_match.group(1))
        if len(re.sub(r"\D", "", digits)) >= 9:
            phone = digits

    return {"company_name": company_name, "ico": ico, "dic": dic, "phone": phone}


@app.post("/api/admin/crm/leads/<int:lead_id>/convert")
@require_permission("crm", "vytvorit")
def crm_admin_lead_convert(lead_id):
    """Navrh/propojeni na shop_customers. Kdyz existuje mozna shoda
    (email/ICO), NIKDY tise - vrati navrhy a ceka na explicitni potvrzeny
    customer_id presne jako drivi. Kdyz ale ZADNA shoda neexistuje A mame
    aspon jmeno+email, NOVE (Robert 2026-08-21: chce prevod na zakaznika
    rovnou z udaju v tele e-mailu) rovnou ZALOZI zakaznika -
    company_name/ico/dic/telefon se doplni z podpisu v tele zprav
    (_extract_signature_fields), kdyz je lead sam nema. Porad to spousti
    jen explicitni klik admina na "Prevest na zakaznika", nejde o tichy
    pozadi-proces. Samotna objednavka se nezaklada tady - admin dostane
    customer_id/prefill data a otevre stavajici formular Nova
    objednavka."""
    body = request.get_json(silent=True) or {}
    confirmed_customer_id = body.get("customer_id")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crm_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Poptávka neexistuje."}), 404

            if confirmed_customer_id:
                cur.execute("SELECT id, party_id FROM shop_customers WHERE id=%s", (confirmed_customer_id,))
                confirmed_customer = cur.fetchone()
                if not confirmed_customer:
                    return jsonify({"error": "Zákazník neexistuje."}), 400
                cur.execute(
                    "UPDATE crm_leads SET customer_id=%s, party_id=%s WHERE id=%s",
                    (confirmed_customer_id, confirmed_customer["party_id"], lead_id),
                )
                conn.commit()
                return jsonify({"status": "ok", "customer_id": confirmed_customer_id})

            cur.execute(
                "SELECT body FROM crm_lead_messages WHERE lead_id=%s ORDER BY created_at ASC, id ASC",
                (lead_id,),
            )
            combined_text = "\n".join((r["body"] or "") for r in cur.fetchall())
            parsed = _extract_signature_fields(combined_text)
            company_name = lead["company_name"] or parsed["company_name"]
            phone = lead["contact_phone"] or parsed["phone"]
            prefill = {
                "full_name": lead["contact_name"], "email": lead["contact_email"],
                "phone": phone, "company_name": company_name,
                "ico": parsed["ico"], "dic": parsed["dic"],
            }

            suggestions = customers.find_duplicate_customers(
                cur, email=lead["contact_email"], ico=parsed["ico"], dic=parsed["dic"],
                full_name=lead["contact_name"], phone=phone,
            )
            if suggestions:
                return jsonify({
                    "status": "suggestions",
                    "duplicate_suggestions": suggestions,
                    "prefill": prefill,
                })

            new_customer_id = None
            full_name = (lead["contact_name"] or "").strip()
            email = (lead["contact_email"] or "").strip().lower()
            if full_name and email and customers._EMAIL_RE.match(email):
                cur.execute("SELECT id FROM app_users WHERE email=%s", (email,))
                if not cur.fetchone():
                    clean, err = customers._validate_and_clean({
                        "customer_type": "firma" if company_name else "osoba",
                        "full_name": full_name, "company_name": company_name,
                        "ico": parsed["ico"], "dic": parsed["dic"],
                        "email": email, "phone": phone,
                    }, existing_email_fallback=email)
                    if not err:
                        random_password = customers.secrets.token_urlsafe(24)
                        party_id = create_party(
                            cur, party_type=clean["customer_type"], full_name=clean["full_name"],
                            primary_email=clean["email"], primary_phone=clean["phone"],
                            ico=clean["ico"], dic=clean["dic"],
                        )
                        cur.execute(
                            "INSERT INTO app_users (email, password_hash, name, role, active, party_id) "
                            "VALUES (%s,%s,%s,'user',1,%s)",
                            (email, customers.generate_password_hash(random_password), full_name, party_id),
                        )
                        new_user_id = cur.lastrowid
                        cols_sql, placeholders, values = customers._customer_insert_clause(clean)
                        cur.execute(
                            f"INSERT INTO shop_customers (user_id, party_id, {cols_sql}, group_id, note) "
                            f"VALUES (%s, %s, {placeholders}, %s, %s)",
                            (new_user_id, party_id) + values
                            + (None, f"Automaticky založeno z poptávky #{lead_id} (údaje z e-mailu)."),
                        )
                        new_customer_id = cur.lastrowid
                        # party_id se pripojuje ve STEJNEM kroku jako
                        # customer_id - je to porad ta samá tvrda FK,
                        # zadne nove dohadovani (bot18, 2026-09-05).
                        cur.execute(
                            "UPDATE crm_leads SET customer_id=%s, party_id=%s WHERE id=%s",
                            (new_customer_id, party_id, lead_id),
                        )
                        conn.commit()

            if new_customer_id:
                admin = current_user()
                log_audit(admin["id"], "create", "customer", new_customer_id,
                          f"Automaticky založen z poptávky #{lead_id}: {full_name} ({email}).")
                return jsonify({"status": "created", "customer_id": new_customer_id, "prefill": prefill})
    finally:
        conn.close()

    return jsonify({"status": "no_match", "prefill": prefill})


@app.get("/api/admin/crm/assignable-users")
@require_permission("crm", "zobrazit")
def crm_admin_assignable_users():
    """Vlastni endpoint (ne recyklace /api/admin/users, ta vyzaduje
    sekci 'uzivatele') - manazer s pravem jen na 'crm' musi umet
    naplnit vyber prirazeni."""
    placeholders = ",".join(["%s"] * len(PERMISSION_ROLES))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, name, email, role FROM app_users WHERE role IN ({placeholders}) AND active=1 ORDER BY name",
                PERMISSION_ROLES,
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"users": rows})


@app.post("/api/admin/crm/leads/<int:lead_id>/reject")
@require_permission("crm", "upravit")
def crm_admin_lead_reject(lead_id):
    """"Toto neni poptavka" (viz modulovy docstring) - zprava/y se
    presunou do Podpory presne jako by tam skoncily puvodne (mirror
    support_email_sync.py::_find_or_create_conversation), text se
    zauci jako negativni priklad, a lead zmizi z CRM."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crm_leads WHERE id=%s", (lead_id,))
            lead = cur.fetchone()
            if not lead:
                return jsonify({"error": "Poptávka neexistuje."}), 404
            cur.execute(
                "SELECT * FROM crm_lead_messages WHERE lead_id=%s ORDER BY created_at ASC, id ASC",
                (lead_id,),
            )
            messages = cur.fetchall()

            contact_text = "\n".join(m["body"] for m in messages if m["sender_type"] == "contact")
            train_words(cur, lead["subject"], contact_text, "jine")

            cur.execute(
                "SELECT id, customer_user_id FROM shop_support_conversations WHERE customer_email=%s "
                "ORDER BY (status='open') DESC, last_message_at DESC LIMIT 1",
                (lead["contact_email"],),
            )
            conv = cur.fetchone()
            if conv:
                conv_id, user_id = conv["id"], conv["customer_user_id"]
            else:
                cur.execute("SELECT id FROM app_users WHERE email=%s", (lead["contact_email"],))
                user_row = cur.fetchone()
                user_id = user_row["id"] if user_row else None
                cur.execute(
                    "INSERT INTO shop_support_conversations "
                    "(customer_user_id, customer_email, customer_name, source, email_subject, status, unread_by_admin) "
                    "VALUES (%s,%s,%s,'email',%s,'open',1)",
                    (user_id, lead["contact_email"], lead["contact_name"] or lead["contact_email"], lead["subject"]),
                )
                conv_id = cur.lastrowid

            for m in messages:
                sender_type = "operator" if m["sender_type"] == "operator" else "customer"
                cur.execute(
                    "INSERT INTO shop_support_messages "
                    "(conversation_id, sender_type, sender_user_id, sender_name, body, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (conv_id, sender_type, user_id if sender_type == "customer" else m["sender_user_id"],
                     m["sender_name"], m["body"], m["created_at"]),
                )
            cur.execute(
                "UPDATE shop_support_conversations SET unread_by_admin=1, last_message_at=NOW(), status='open' WHERE id=%s",
                (conv_id,),
            )
            # Nabidky (viz api/quotes.py): e-mailove prilohy k tomuto
            # leadu MUSI se zjistit PRED DELETE FROM crm_leads nize -
            # kaskaduje na crm_lead_messages/crm_lead_message_attachments,
            # DB radky zaniknou, ale fyzicke soubory na disku by bez
            # tohohle zustaly navzdy osirele.
            attachment_filenames = quotes.lead_attachment_filenames(cur, lead_id)
            cur.execute("DELETE FROM crm_leads WHERE id=%s", (lead_id,))
        conn.commit()
    finally:
        conn.close()
    # Uklid fotek pripojenych k leadu (viz gallery_items.py) - AZ PO
    # commitu hlavniho DELETE, stejny vzor jako u kategorie/produktu/
    # dokladu jinde v projektu (app.py/documents.py/purchase_orders.py).
    gallery_items.delete_items_for_owner("lead", lead_id)
    quotes.remove_lead_attachment_files(attachment_filenames)
    log_audit(admin["id"], "reject_to_support", "crm_lead", lead_id, None)
    return jsonify({"status": "ok", "conversation_id": conv_id})


# ---------------------------------------------------------------------------
# Ukoly/pripomenuti (Robert: "Crm ma přece více funkcí ... tak tam
# všechno doplň") - "zavolat v patek", "poslat nabidku do 3 dnu" apod.,
# s terminem. Oddelene od crm_lead_messages (to je vlakno KOMUNIKACE se
# zakaznikem, tohle je interni TODO operatora).
# ---------------------------------------------------------------------------

def _serialize_task(row):
    return {
        "id": row["id"], "lead_id": row["lead_id"], "title": row["title"],
        "due_at": row["due_at"].isoformat() if row["due_at"] else None,
        "done": bool(row["done"]), "created_by": row["created_by"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@app.get("/api/admin/crm/leads/<int:lead_id>/tasks")
@require_permission("crm", "zobrazit")
def crm_admin_lead_tasks_list(lead_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_leads WHERE id=%s", (lead_id,))
            if not cur.fetchone():
                return jsonify({"error": "Poptávka neexistuje."}), 404
            cur.execute(
                "SELECT * FROM crm_lead_tasks WHERE lead_id=%s "
                "ORDER BY done ASC, (due_at IS NULL) ASC, due_at ASC, id ASC",
                (lead_id,),
            )
            tasks = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"tasks": [_serialize_task(t) for t in tasks]})


@app.post("/api/admin/crm/leads/<int:lead_id>/tasks")
@require_permission("crm", "vytvorit")
def crm_admin_lead_tasks_create(lead_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Text úkolu je prázdný."}), 400
    due_at = (body.get("due_at") or "").strip() or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_leads WHERE id=%s", (lead_id,))
            if not cur.fetchone():
                return jsonify({"error": "Poptávka neexistuje."}), 404
            cur.execute(
                "INSERT INTO crm_lead_tasks (lead_id, title, due_at, created_by) VALUES (%s,%s,%s,%s)",
                (lead_id, title, due_at, admin["id"]),
            )
            task_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": task_id}), 201


@app.put("/api/admin/crm/leads/<int:lead_id>/tasks/<int:task_id>")
@require_permission("crm", "upravit")
def crm_admin_lead_tasks_update(lead_id, task_id):
    """Existence se overuje SELECTem, ne cur.rowcount po UPDATE - MySQL
    bez CLIENT_FOUND_ROWS hlasi rowcount=0 i pro "zaskrtnout uz hotovy
    ukol znovu" (zadna hodnota se nezmenila), coz NENI stejne jako
    "ukol neexistuje" a nesmi to tak byt hlaseno."""
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "done" in body:
        fields.append("done=%s"); params.append(1 if body.get("done") else 0)
    if "title" in body:
        title = (body.get("title") or "").strip()
        if not title:
            return jsonify({"error": "Text úkolu je prázdný."}), 400
        fields.append("title=%s"); params.append(title)
    if "due_at" in body:
        fields.append("due_at=%s"); params.append((body.get("due_at") or "").strip() or None)
    if not fields:
        return jsonify({"error": "Nebyla zadána žádná změna."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_lead_tasks WHERE lead_id=%s AND id=%s", (lead_id, task_id))
            if not cur.fetchone():
                return jsonify({"error": "Úkol neexistuje."}), 404
            params.extend([lead_id, task_id])
            cur.execute(f"UPDATE crm_lead_tasks SET {', '.join(fields)} WHERE lead_id=%s AND id=%s", params)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.delete("/api/admin/crm/leads/<int:lead_id>/tasks/<int:task_id>")
@require_permission("crm", "upravit")
def crm_admin_lead_tasks_delete(lead_id, task_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM crm_lead_tasks WHERE lead_id=%s AND id=%s", (lead_id, task_id))
            if cur.rowcount == 0:
                return jsonify({"error": "Úkol neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Interni poznamky - NIKDY se neposilaji jako e-mail (na rozdil od
# /reply, ktera realny e-mail posila) - proto vlastni tabulka
# crm_lead_notes, zadna vazba na send_email() nikde nize.
# ---------------------------------------------------------------------------

def _serialize_note(row):
    return {
        "id": row["id"], "lead_id": row["lead_id"],
        "author_id": row["author_id"], "author_name": row["author_name"],
        "body": row["body"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@app.get("/api/admin/crm/leads/<int:lead_id>/notes")
@require_permission("crm", "zobrazit")
def crm_admin_lead_notes_list(lead_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_leads WHERE id=%s", (lead_id,))
            if not cur.fetchone():
                return jsonify({"error": "Poptávka neexistuje."}), 404
            cur.execute(
                "SELECT * FROM crm_lead_notes WHERE lead_id=%s ORDER BY created_at ASC, id ASC",
                (lead_id,),
            )
            notes = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"notes": [_serialize_note(n) for n in notes]})


@app.post("/api/admin/crm/leads/<int:lead_id>/notes")
@require_permission("crm", "vytvorit")
def crm_admin_lead_notes_create(lead_id):
    admin = current_user()
    body = (request.get_json(silent=True) or {}).get("body", "").strip()
    if not body:
        return jsonify({"error": "Poznámka je prázdná."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_leads WHERE id=%s", (lead_id,))
            if not cur.fetchone():
                return jsonify({"error": "Poptávka neexistuje."}), 404
            cur.execute(
                "INSERT INTO crm_lead_notes (lead_id, author_id, author_name, body) VALUES (%s,%s,%s,%s)",
                (lead_id, admin["id"], admin.get("name") or admin["email"], body),
            )
            note_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": note_id}), 201


@app.delete("/api/admin/crm/leads/<int:lead_id>/notes/<int:note_id>")
@require_permission("crm", "upravit")
def crm_admin_lead_notes_delete(lead_id, note_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM crm_lead_notes WHERE lead_id=%s AND id=%s", (lead_id, note_id))
            if cur.rowcount == 0:
                return jsonify({"error": "Poznámka neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.get("/api/admin/crm/dashboard")
@require_permission("crm", "zobrazit")
def crm_admin_dashboard():
    """Souhrn pro Poptavky (Robert: "Crm ma přece více funkcí ... tak
    tam všechno doplň" - chybelo cokoli agregovaneho, jen seznam se
    stavy). Hodnota pipeline se pocita jen z OTEVRENYCH stavu (nova/
    v_jednani/nabidnuto) - vyhrano/prohrano uz "v pipeline" neni."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, COUNT(*) AS n, COALESCE(SUM(estimated_value),0) AS value_sum "
                "FROM crm_leads GROUP BY status"
            )
            by_status = {r["status"]: {"count": r["n"], "value_sum": float(r["value_sum"])} for r in cur.fetchall()}
            pipeline_value = sum(
                by_status.get(s, {}).get("value_sum", 0.0) for s in ("nova", "v_jednani", "nabidnuto")
            )

            cur.execute(
                "SELECT status, COUNT(*) AS n FROM crm_leads "
                "WHERE status IN ('vyhrano','prohrano') AND closed_at >= DATE_FORMAT(NOW(), '%Y-%m-01') "
                "GROUP BY status"
            )
            month = {r["status"]: r["n"] for r in cur.fetchall()}
            won, lost = month.get("vyhrano", 0), month.get("prohrano", 0)
            win_rate = round(100 * won / (won + lost), 1) if (won + lost) else None

            # now_local() (bezpecnostni nalez, bot3/revize kodu, 2026-09-02) -
            # due_at je ulozen jako naivni prazsky mistni cas (admin.html
            # datetime-local vstup, 1:1 do DATETIME), NE UTC - MySQL NOW()
            # by porovnavalo UTC se skutecne prazskym casem a "po terminu"
            # by se ukazovalo o 1-2h posunute. products.py::now_local() je
            # jediny zdroj tehle logiky v repu, nedupluje se.
            cur.execute(
                "SELECT COUNT(*) AS n FROM crm_lead_tasks WHERE done=0 AND due_at IS NOT NULL AND due_at < %s",
                (now_local(),),
            )
            overdue_tasks = cur.fetchone()["n"]
    finally:
        conn.close()
    return jsonify({
        "by_status": by_status,
        "pipeline_value": pipeline_value,
        "month_won": won,
        "month_lost": lost,
        "win_rate": win_rate,
        "overdue_tasks": overdue_tasks,
    })


# ============================================================
# Admin panel klasifikace (Robert: "chci v administraci panel, pro
# nastavovani filtru a klicovych spojeni ktere slouzi k vyhodnocovani")
# - primy CRUD nad tim, co dnes support_email_sync.py pouziva k
# rozhodovani poptavka/Podpora/ignorovat. Stejna sekce opravneni jako
# zbytek CRM.
# ============================================================

@app.get("/api/admin/crm/classifier/words")
@require_permission("crm", "zobrazit")
def crm_classifier_words_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT word, poptavka_count, jine_count FROM crm_classifier_words ORDER BY word")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"words": [
        {"word": r["word"], "poptavka_count": r["poptavka_count"], "jine_count": r["jine_count"]}
        for r in rows
    ]})


@app.post("/api/admin/crm/classifier/words")
@require_permission("crm", "upravit")
def crm_classifier_words_upsert():
    body = request.get_json(silent=True) or {}
    word = (body.get("word") or "").strip().lower()
    if not word:
        return jsonify({"error": "Vyplňte slovo."}), 400
    try:
        poptavka_count = max(0, int(body.get("poptavka_count") or 0))
        jine_count = max(0, int(body.get("jine_count") or 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatná čísla."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO crm_classifier_words (word, poptavka_count, jine_count) VALUES (%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE poptavka_count=%s, jine_count=%s",
                (word, poptavka_count, jine_count, poptavka_count, jine_count),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"}), 201


@app.delete("/api/admin/crm/classifier/words/<word>")
@require_permission("crm", "smazat")
def crm_classifier_words_delete(word):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM crm_classifier_words WHERE word=%s", (word.strip().lower(),))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


SENDER_RULE_TYPES = ("ignore", "force_poptavka", "force_shop_related", "force_objednavka", "auto_archive")
# 'auto_archive' (Robert 2026-08-24, no-reply@demos-trade.com) - na
# rozdil od 'ignore' (email se NIKAM neulozi, zadna stopa) se konverzace
# porad zalozi/aktualizuje v Podpore (Robert chce vedet, ze prisla, jde
# dohledat), jen rovnou archived=1 (nezavali "netridene") a prilohy se
# vubec nezaznamenaji (viz support_email_sync.py). 'ignore' zustava pro
# pripady, kdy Robert nechce ANI stopu (napr. spam).


@app.get("/api/admin/crm/classifier/sender-rules")
@require_permission("crm", "zobrazit")
def crm_classifier_sender_rules_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crm_classifier_sender_rules ORDER BY created_at DESC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"rules": [
        {
            "id": r["id"], "pattern": r["pattern"], "rule_type": r["rule_type"], "note": r["note"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        } for r in rows
    ]})


@app.post("/api/admin/crm/classifier/sender-rules")
@require_permission("crm", "upravit")
def crm_classifier_sender_rules_create():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    pattern = (body.get("pattern") or "").strip().lower()
    rule_type = (body.get("rule_type") or "").strip()
    note = (body.get("note") or "").strip() or None
    if not pattern:
        return jsonify({"error": "Vyplňte adresu nebo doménu (@domena.cz)."}), 400
    if rule_type not in SENDER_RULE_TYPES:
        return jsonify({"error": "Neplatný typ pravidla."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO crm_classifier_sender_rules (pattern, rule_type, note, created_by) VALUES (%s,%s,%s,%s)",
                (pattern, rule_type, note, admin["id"]),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"}), 201


@app.delete("/api/admin/crm/classifier/sender-rules/<int:rule_id>")
@require_permission("crm", "smazat")
def crm_classifier_sender_rules_delete(rule_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM crm_classifier_sender_rules WHERE id=%s", (rule_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.get("/api/admin/crm/classifier/settings")
@require_permission("crm", "zobrazit")
def crm_classifier_settings_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            settings = get_classifier_settings(cur)
    finally:
        conn.close()
    return jsonify({
        "check_app_users": bool(settings["check_app_users"]),
        "check_shop_customers": bool(settings["check_shop_customers"]),
        "check_shop_orders": bool(settings["check_shop_orders"]),
        "check_support_conversations": bool(settings["check_support_conversations"]),
    })


@app.put("/api/admin/crm/classifier/settings")
@require_permission("crm", "upravit")
def crm_classifier_settings_update():
    body = request.get_json(silent=True) or {}
    fields = ("check_app_users", "check_shop_customers", "check_shop_orders", "check_support_conversations")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sets = ", ".join(f"{f}=%s" for f in fields if f in body)
            if sets:
                params = [1 if body[f] else 0 for f in fields if f in body]
                cur.execute(f"UPDATE crm_classifier_settings SET {sets} WHERE id=1", params)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})
