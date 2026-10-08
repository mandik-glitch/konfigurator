"""
Podpora - Faze 2 (e-mailova synchronizace) - bot1, 2026-07-26.

Robert: "[ktere prichozi e-maily maji spadnout do Podpory] Uplne vsechny
nove e-maily" + "[oznacit jako precteno] Ano" + potvrdil pouziti
STAVAJICIHO Gmail App Password (uz je v .env jako SMTP_PASSWORD - funguje
shodne pro SMTP i IMAP, zadny novy klic netreba).

OPRAVENO 2026-07-26 (po prvnim ostrem behu, kdy se do Podpory dostalo
upozorneni od pojistovny): "ne kazdy novy email se stane konverzaci, jen
tykajici se objednavek eshopu" - viz _is_shop_related_email() nize. Puvodni
"uplne vsechny" tedy uz NEPLATI doslovne - filtruje se podle toho, jestli
odesilatel ma nejaky vztah k eshopu (ucet, zakaznicky profil, objednavka,
nebo uz existujici konverzace v Podpore).

Spousteno periodicky systemd timerem
(konfigurator-support-email-sync.timer), NE pres HTTP/Flask - stejny
vzor jako nocni obnoveni cen (`python3 app.py refresh-prices`, viz
run_price_refresh_cli() v app.py). Pouziti:
    python3 app.py support-email-sync
(dispatch pridan do `if __name__ == "__main__":` v app.py). Modul NENI
soucasti retezu `import orders/cart/.../gallery/support/cutting` na konci
app.py - neregistruje zadne Flask routy, je to cisty CLI skript, proto se
importuje jen LOKALNE uvnitr __main__ vetve (stejne jako refresh-prices
nepotrebuje byt naimportovany pri kazdem startu gunicorn workeru).

Kazdy NOVY (IMAP UNSEEN) e-mail v INBOX na mandik@logiman.cz, ktery
souvisi s eshopem (viz _is_shop_related_email), se stane konverzaci/
zpravou v Podpore - sparovani s konverzaci resi _find_or_create_conversation()
(OPRAVENO 2026-08-17, viz sql/2026-08-17_support_message_threading.sql
pro kontext incidentu #42): skutecne e-mailove threadovani (In-Reply-To/
References -> Message-ID drivejsi zpravy), fallback na shodny "normalizovany"
predmet (bez Re:/Fwd:/Aw:) u stejne adresy, teprve pak nova konverzace.
PUVODNI verze parovala VYHRADNE podle shodne odesilatelovy adresy (bez
ohledu na obsah/predmet) - to uz NEPLATI, zpusobovalo to slevani zcela
nesouvisejicich e-mailu do jednoho vlakna navzdy. Nova konverzace ma
`source='email'`; pokud odesilatel ma ucet v app_users, priradi se i
customer_user_id (pro kontext v adminu), i kdyz identifikace probehla
pres e-mail, ne pres login.
Zpracovane (eshop-souvisejici) e-maily se oznaci \\Seen (Robert: "ano"),
aby se nezpracovaly znovu - v beznem Gmail webu je pak uvidis jako
precteno. E-maily BEZ vztahu k eshopu se NEDOTKNOU (zustanou nepreteny,
appka je jen znovu preskoci pri pristim behu).

ZMENENO 2026-08-18 (bot23, Robert pres bot3): _is_shop_related_email()
branka vyse (a jeji "ostatni/nezaraditelne -> email_review_queue" vetev
pridana 2026-08-17) uz se v sync_incoming_emails() NEPOUZIVA - Robert
zjistil, ze e-mailum, ktere touhle brankou neprosly, chybelo jakekoli
admin UI/API (jen rucni CLI skript na vyzadani), takze mu fakticky
mizely z dohledu. Rozhodl "nejdriv at tam vsechny zacnou chodit, filtr/
spam se bude resit az podle skutecneho objemu, ne teoreticky predem" -
KAZDY e-mail, ktery neni poptavka/doklad, ted konci primo v Podpore
(shop_support_conversations), stejne jako driv skutecne shop-souvisejici
posta. Funkce _is_shop_related_email() a tabulka email_review_queue
zustavaji v kodu/DB (historicka data, snadny navrat), jen uz nejsou na
teto ceste volane.

ZMENENO 2026-07-31: puvodne se zpravy od vlastni adresy (IMAP_USER)
preskakovaly (ochrana proti smycce). Robert vyslovne potvrdil zruseni
NATRVALO - "ja si sam sobe posilam e-maily normalne abych na neco
nezapomnel" + explicitne odsouhlasil, ze se ted i jeho vlastni e-maily
budou zpracovavat/ukladat stejne jako cokoliv jineho. Skutecne riziko
smycky je nizke - tento modul sam zadne automaticke odpovedi neposila
(viz nize), takze "smycka" by vyzadovala rucni odpoved administratora
pres support.py, ktera se navic posila jako beznou SMTP zpravou, ne
znovu-cteni ze stejne INBOX schranky.

Odpovedi napsane v operatorske konzoli (viz support.py::support_admin_reply)
se odesilaji zpet jako REALNY e-mail pres uz existujici SMTP konfiguraci
(app.py::send_email) - ne z tohoto souboru, ale je to druha polovina te
same "sjednocene" smycky.

DOPLNENO 2026-07-31 (bot5, CRM/poptavky): PRED vyse popsanou
_is_shop_related_email() branou se ted kazdy e-mail nejdriv obsahove
klasifikuje (crm.classify_incoming_email) - "poptavka" konci v novem
crm_leads/crm_lead_messages (viz crm.py), bez ohledu na to, jestli
odesilatel uz ma vztah k eshopu (Robert: "ale i nove" kontakty se maji
zachytit). Vse ostatni pokracuje puvodni logikou nezmeneno.

DOPLNENO 2026-08-01 (bot5, Nabidky - viz api/quotes.py pro cely
kontext): PRILOHY poptavkovych e-mailu se uz NEZAHAZUJI (puvodne
_extract_plain_text() nize kazdou cast s Content-Disposition:
attachment tise preskocila) - Robert: "kdyz vznikne adresar pro
konkretni poptavku ulozi se do nej vsechny prilohy z toho daneho
e-mailu" + "zaroven ... i pripadne budouci prilohy jinych e-mailu
vlakno". _extract_attachments() nize vytahne prilohy z KAZDEHO
e-mailu klasifikovaneho jako "poptavka", quotes.save_lead_attachment()
je ulozi (od bot10 2026-08-22 primo do Drive slozky dane poptavky -
Poptavky > nabidky > rok > mesic > vanRM-..., viz crm.py::
ensure_lead_drive_folder - drive pred tim slo do soukromeho
crm_lead_message_attachments, viz TASKS.md/AGENTS_LOG.md - navic do
aktivni nabidky, pokud uz existuje).
"""
import email
import imaplib
import os
import re
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from app import get_conn, SMTP_USER, SMTP_PASSWORD
import crm
import quotes
import incoming_documents

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER = os.environ.get("IMAP_USER") or SMTP_USER
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD") or SMTP_PASSWORD

# PUVODNE (bot11, 2026-08-19) plosny staging - KAZDA priloha KAZDEHO
# prichoziho support e-mailu se ukladala na disk PRI SYNCHRONIZACI, bez
# ohledu na pozdejsi klasifikaci. ZRUSENO (bot11, 2026-08-22, Robert
# pres bot3: "nemůžeme do nekonečna ukládat" -> "staging příloh
# nechceme, ukládat budeme až v dalších krocích") - viz
# _record_support_message_attachment_meta() nize, ktera misto toho
# zaznamena jen METADATA (nazev/typ/velikost), zadne bajty na disku.
# Skutecny soubor se stahuje az na vyzadani PRIMO Z IMAPU podle
# Message-ID (fetch_attachment_from_imap nize) - Gmail e-maily z IMAPu
# nemaze, jen oznacuje \\Seen, takze tam porad jsou (na rozdil od
# puvodniho zduvodneni v sql/2026-08-19_shop_support_message_attachments.sql,
# ktere pocitalo s tim, ze Robert e-maily rucnim stazenim ze serveru
# maze - Robert 2026-08-22 tohle vyslovne opravil).
#
# Adresar SUPPORT_ATTACHMENTS_DIR zustava (zpetna kompatibilita pro
# uz drive stazene/stagovane soubory - viz support.py, ktere je porad
# umi precist podle vyplneneho stored_filename), ale NOVE prilohy uz
# se do nej neukladaji.
SUPPORT_ATTACHMENTS_DIR = os.path.join(quotes.PRIVATE_FILES_DIR, "support-attachments")
os.makedirs(SUPPORT_ATTACHMENTS_DIR, exist_ok=True)

# Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): prichozi e-mail je
# nedoveryhodny vstup - zadny strop na velikost prilohy pred zapisem na
# disk (quotes.save_lead_attachment pro "poptavka" klasifikaci) umoznoval
# zaplnit disk jednim velkym prichozim emailem. Stejny rad velikosti
# jako turntable.py MAX_BYTES (max tier 6 MB) - o neco vyssi, protoze
# prilohy e-mailu byvaji vicestrankove sken/PDF, ne jen JPEG snimek.
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def _record_support_message_attachment_meta(cur, message_id, attachments):
    """Zaznamena METADATA (nazev/typ/velikost) prilohy dane
    shop_support_messages zpravy - `stored_filename` zustava NULL
    (zadny soubor na disku, viz komentar u SUPPORT_ATTACHMENTS_DIR
    vyse). `attachments` je format _extract_attachments() (filename,
    content_type, bytes) - bajty se pouziji jen na zjisteni presne
    velikosti, nikam se neukladaji."""
    for filename, content_type, data in attachments:
        cur.execute(
            "INSERT INTO shop_support_message_attachments "
            "(message_id, filename, stored_filename, content_type, size_bytes) "
            "VALUES (%s,%s,NULL,%s,%s)",
            (message_id, filename, content_type, len(data)),
        )


def _all_mail_folder(M):
    """Najde IMAP slozku se specialni-use flagou \\All (Gmail "Vsechny
    zpravy"/"All Mail" - union VSECH doruc./odeslanych/archivovanych
    zprav krome Kose/Spamu). Nazev NEHARDCODOVAT - je lokalizovany
    (cesky ucet ma slozku zakodovanou jako "V&AWE-echny zpr&AOE-vy" v
    IMAP modified UTF-7), hleda se podle flagy z LIST odpovedi.
    Fallback na INBOX, kdyby flaga chybela (jiny mail server nez
    Gmail)."""
    try:
        typ, data = M.list()
    except Exception:
        return "INBOX"
    if typ == "OK":
        for line in data:
            line_str = line.decode() if isinstance(line, bytes) else line
            if "\\All" in line_str:
                m = re.search(r'"([^"]*)"$', line_str)
                if m:
                    return m.group(1)
    return "INBOX"


def fetch_attachment_from_imap(message_id_header, filename):
    """Stahne JEDNU konkretni prilohu az na vyzadani, primo z IMAPu,
    podle Message-ID hlavicky puvodni zpravy - pouziva se pro prilohy
    zaznamenane jen jako metadata (viz
    _record_support_message_attachment_meta vyse), kdyz je potreba
    skutecny obsah (nahled v triazi, schvaleni kategorie 'doklad',
    prevod konverzace na poptavku). Vraci (content_type, bytes), nebo
    None, kdyz zpravu/prilohu uz v IMAPu nejde najit vubec (rucne
    smazana adminem) - zadna vyjimka, volajici to musi osetrit stejne
    jako drivejsi "priloha chybi na disku".

    DULEZITE (zjisteno zive, bot11 2026-08-22): Robert e-maily po
    prectyeni tridi do vlastnich slozek (napr. "05 Objednavky",
    "01 Urgent") - v momente schvaleni triage uz zprava CASTO neni v
    INBOXu (proto se hleda ve "Vsechny zpravy"/\\All, ne v INBOXu -
    puvodni verze hledala jen v INBOXu a u 4 z 5 testovanych starsich
    priloh selhala presne z tohohle duvodu, i kdyz zprava v IMAPu
    porad existovala)."""
    if not message_id_header or not IMAP_PASSWORD:
        return None
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
    try:
        M.login(IMAP_USER, IMAP_PASSWORD)
        folder = _all_mail_folder(M)
        M.select(f'"{folder}"', readonly=True)
        typ, data = M.uid("search", None, "HEADER", "Message-ID", f'"{message_id_header}"')
        if typ != "OK" or not data or not data[0]:
            return None
        uid = data[0].split()[0]
        typ, msg_data = M.uid("fetch", uid, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            return None
        msg = email.message_from_bytes(msg_data[0][1])
        for att_filename, content_type, payload in _extract_attachments(msg):
            if att_filename == filename:
                return content_type, payload
        return None
    except Exception as e:
        print(f"[support-email-sync] fetch_attachment_from_imap selhalo ({message_id_header}, {filename}): {e}")
        return None
    finally:
        try:
            M.logout()
        except Exception:
            pass
MAX_BODY_CHARS = 20000
MAX_HTML_BODY_CHARS = 100000

# Robert pres bot3, 2026-08-23: legacy (patrne Shoptet) objednavkove
# potvrzeni ("Vazeny zakazniku, Vasi objednavku jsme v poradku
# prijali...") nekdy skonci zpet ve VLASTNI INBOX (mandik@logiman.cz)
# jako kopie - technicka adresa odesilatele je nase vlastni SMTP_USER,
# i kdyz "jmeno" v hlavicce "Od" ukazuje zakaznika. Klasifikator
# (crm.classify_incoming_email) ji pak mylne oznaci jako "doklad" -
# text obsahuje "zálohová faktura"/"variabilní symbol platby", stejna
# slova jako u skutecne prijate faktury od dodavatele (viz
# incoming_documents.id=2, nahlaseno Robertem). Je to jen KOPIE stavu,
# ktery uz existuje jinde (shop_orders) - neni potreba nikde jinde.
_ORDER_CONFIRMATION_COPY_SUBJECT_RE = re.compile(r"^\[LOGiMAN\]\s*Objedn[aá]vka\s+\d+", re.IGNORECASE)


def _decode_header_value(raw):
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _decode_part(part):
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except Exception:
        return ""


def _extract_body(msg):
    """Vrati (plain, html) - plain text pro klasifikaci/hledani/zobrazeni
    beznych zprav (beze zmeny chovani oproti puvodni _extract_plain_text:
    preferuje text/plain cast, pri jejim chybeni oholi text/html na hruby
    text), html RAW (nezmenene, jen dekodovane z bytes) pro pripady, kdy
    admin.html umi zobrazit skutecnou HTML verzi (tabulky objednavek apod. -
    Robert 2026-08-06 "dejme tomu nejaky format tabulky", viz
    sql/2026-08-06_support_crm_html_body.sql) - None, pokud e-mail zadnou
    text/html cast nema."""
    if msg.is_multipart():
        plain, html = None, None
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            if ctype == "text/plain" and plain is None:
                plain = _decode_part(part)
            elif ctype == "text/html" and html is None:
                html = _decode_part(part)
        if plain:
            plain_text = plain.strip()
        elif html:
            text = re.sub(r"<[^>]+>", " ", html)
            plain_text = re.sub(r"\s+", " ", text).strip()
        else:
            plain_text = ""
        return plain_text, (html.strip() if html else None)
    return _decode_part(msg).strip(), None


def _extract_attachments(msg):
    """Analogicka _extract_plain_text() vyse, ale misto textu vytahne
    PRILOHY (Content-Disposition: attachment) jako seznam (filename,
    content_type, bytes). Viz modulovy docstring - puvodne se tiše
    zahazovaly, ted se musi zachytit pro Nabidky (api/quotes.py).

    ROZSIRENO 2026-08-24 (Robert: "chceme umet zpracovat v emailu i
    obrazky prilozene v tele emailu") - puvodne se chytaly VYHRADNE
    casti s `Content-Disposition: attachment`. Obrazek VLOZENY primo do
    HTML tela (typicky z "vlozit obrazek"/screenshot vlozeny primo do
    editoru, ne pretazeny jako priloha) ma `Content-Disposition: inline`
    (nebo casto ZADNY Content-Disposition header vubec) a odkazuje se
    na nej z HTML tela pres `<img src="cid:...">` - takove casti
    puvodni filtr uplne preskocil (nebyly ani v tele - obrazek neni
    text, ani v prilohach - neni "attachment"), ticha ztrata dat presne
    stejneho druhu, jako driv u skutecnych priloh. Ted: cokoli s
    image/* Content-Type se zachyti bez ohledu na Content-Disposition
    (chybejici nazev souboru u cist inline obrazku bez Content-ID se
    nahradi generickym "obrazek-N.<pripona>", at neni prazdny)."""
    attachments = []
    if not msg.is_multipart():
        return attachments
    img_counter = 0
    for part in msg.walk():
        disp = str(part.get("Content-Disposition") or "")
        ctype = part.get_content_type()
        is_inline_image = ctype.startswith("image/")
        if not is_inline_image and "attachment" not in disp:
            continue
        filename = part.get_filename()
        if filename:
            filename = _decode_header_value(filename)
        elif is_inline_image:
            img_counter += 1
            ext = (ctype.split("/", 1)[1] or "png").split(";")[0].strip()
            filename = f"obrazek-{img_counter}.{ext}"
        else:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if len(payload) > MAX_ATTACHMENT_BYTES:
            print(f"[support-email-sync] příloha '{filename}' zahozena "
                  f"({len(payload)} B > {MAX_ATTACHMENT_BYTES} B limit)")
            continue
        attachments.append((filename, ctype, payload))
    return attachments


def _is_shop_related_email(cur, from_email):
    """Robert 2026-07-26 (oprava puvodniho 'uplne vsechny e-maily'): 'jen
    tykajici se objednavek eshopu' - ne kazdy e-mail v INBOXu (napr.
    upozorneni od pojistovny apod. NEMAJI se stat konverzaci v Podpore).
    Odesilatel se povazuje za 'eshopoveho zakaznika', pokud jeho e-mail
    najdeme v NEKTERE z techto existujicich evidenci:
      - app_users (ma ucet v konfiguratoru),
      - shop_customers (ma zalozeny zakaznicky profil),
      - shop_orders.customer_email (uz nekdy neco objednal, i bez uctu),
      - jiz existujici shop_support_conversations (pokracovani konverzace
        zalozene drive pres widget/rucne).
    Jinak se e-mail PRESKOCI (nezpracuje se do Podpory).

    DOPLNENO (Robert: admin panel "pro nastavovani filtru") - kazda ze
    4 podminek se ted da jednotlive vypnout (crm.get_classifier_settings) -
    vypnuta podminka se proste nekontroluje. Kdyz jsou vypnute VSECHNY,
    funkce vzdy vrati False (zadna cesta do Podpory bez explicitniho
    force_shop_related pravidla - viz sync_incoming_emails)."""
    settings = crm.get_classifier_settings(cur)
    if settings["check_app_users"]:
        cur.execute("SELECT 1 FROM app_users WHERE email=%s", (from_email,))
        if cur.fetchone():
            return True
    if settings["check_shop_customers"]:
        cur.execute("SELECT 1 FROM shop_customers WHERE email=%s", (from_email,))
        if cur.fetchone():
            return True
    if settings["check_shop_orders"]:
        cur.execute("SELECT 1 FROM shop_orders WHERE customer_email=%s LIMIT 1", (from_email,))
        if cur.fetchone():
            return True
    if settings["check_support_conversations"]:
        cur.execute("SELECT 1 FROM shop_support_conversations WHERE customer_email=%s LIMIT 1", (from_email,))
        if cur.fetchone():
            return True
    return False


def _normalize_subject(subject):
    """Vytahne "jadro" predmetu bez Re:/Fwd:/Aw: prefixu (i vicenasobnych,
    napr. "Re: Fwd: Re: neco") - pro fallback threadovani v
    _find_or_create_conversation() nize, kdyz e-mail nema pouzitelne
    Message-ID hlavicky (nektere klienty je neposilaji/menit)."""
    s = (subject or "").strip()
    while True:
        m = re.match(r"^(re|fwd?|aw)\s*:\s*", s, re.IGNORECASE)
        if not m:
            break
        s = s[m.end():].strip()
    return s.lower()


def _referenced_message_ids(msg):
    """Vsechny Message-ID, na ktere prichozi e-mail odkazuje (podle
    hlavicek In-Reply-To/References) - RFC 5322 <id> tokeny, References
    jich muze obsahovat vic (cely retezec vlakna)."""
    raw = " ".join(filter(None, [msg.get("In-Reply-To"), msg.get("References")]))
    return re.findall(r"<[^<>]+>", raw)


def _find_or_create_conversation(cur, from_email, from_name, subject, referenced_ids):
    """Sparuje prichozi e-mail se SPRAVNOU existujici konverzaci, nebo
    zalozi novou - bot10 2026-08-17, oprava puvodniho chovani (viz
    sql/2026-08-17_support_message_threading.sql pro cely kontext
    incidentu, kdy konverzace #42 smichala nekolik zcela nesouvisejicich
    e-mailu jen proto, ze mely stejnou odesilatelovu adresu). Puvodni
    verze parovala VYHRADNE podle from_email, bez ohledu na obsah/predmet -
    ted se pouziva skutecne threadovani, s from_email jako POSLEDNI
    zachrannou siti, ne prvnim/jedinym kriteriem.

    Priorita (prvni uspesna cesta vyhrava):
      1. **Skutecne threadovani** - kdyz tenhle e-mail (In-Reply-To/
         References) odkazuje na Message-ID nektere jiz ulozene zpravy
         (shop_support_messages.message_id_header), pouzije se JEJI
         konverzace - nejsilnejsi/nejspolehlivejsi signal, funguje i
         kdyby si odesilatel mezitim zmenil zobrazovane jmeno/alias.
      2. **Fallback bez pouzitelnych hlavicek** - existujici e-mailova
         konverzace se STEJNOU adresou A STEJNYM "jadrem" predmetu (bez
         Re:/Fwd:/Aw: prefixu, viz _normalize_subject) - jen kdyz #1
         neuspeje (napr. odesilateluv klient Message-ID neposila).
      3. **Jinak nova konverzace** - i kdyz uz pro tuhle adresu existuje
         JINA konverzace, ROZDILNE tema (jiny predmet, zadna threadovaci
         hlavicka) dostane VLASTNI radku, misto aby se prilepilo do
         stare/nesouvisejici."""
    if referenced_ids:
        cur.execute(
            "SELECT conversation_id FROM shop_support_messages "
            "WHERE message_id_header IN %s ORDER BY id DESC LIMIT 1",
            (tuple(referenced_ids),),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "SELECT customer_user_id FROM shop_support_conversations WHERE id=%s",
                (row["conversation_id"],),
            )
            conv = cur.fetchone()
            if conv:
                return row["conversation_id"], conv["customer_user_id"]

    normalized = _normalize_subject(subject)
    # Robert 2026-08-24 - stejna oprava jako crm.find_or_create_lead():
    # prazdny predmet (bezne u "sdilet fotku" z mobilu) se pari s jinym
    # prazdnym predmetem stejneho kontaktu, ne jen ignoruje fallback uplne.
    cur.execute(
        "SELECT id, customer_user_id, email_subject FROM shop_support_conversations "
        "WHERE customer_email=%s AND source='email' "
        "ORDER BY (status='open') DESC, last_message_at DESC",
        (from_email,),
    )
    for cand in cur.fetchall():
        cand_normalized = _normalize_subject(cand["email_subject"])
        if (normalized and cand_normalized == normalized) or (not normalized and not cand_normalized):
            return cand["id"], cand["customer_user_id"]

    cur.execute("SELECT id FROM app_users WHERE email=%s", (from_email,))
    user_row = cur.fetchone()
    user_id = user_row["id"] if user_row else None

    cur.execute(
        "INSERT INTO shop_support_conversations "
        "(customer_user_id, customer_email, customer_name, source, email_subject, status, unread_by_admin) "
        "VALUES (%s,%s,%s,'email',%s,'open',1)",
        (user_id, from_email, from_name or from_email, subject or None),
    )
    return cur.lastrowid, user_id


def _log_sync_outcome(conn, *, uid=None, message_id_header=None, from_email=None, from_name=None,
                       subject=None, outcome, lead_id=None, conversation_id=None, document_id=None, note=None):
    """
    Robert 2026-08-24 ("chci videt, co hromadime v mailboxu u nas") -
    KOMPLETNI audit KAZDE zpravy, kterou tenhle modul kdy zpracoval,
    bez ohledu na vysledek - vc. ignorovanych/duplicitnich/auto-
    archivovanych, ktere driv nezanechaly zadnou stopu NIKDE (jen
    posunuly last_uid kurzor). Dnesni incidenty (ztracena priloha,
    objednavka v dokladech, duplicitni poptavka - vsechny nahlasil
    Robert, ne systém sám) ukazaly, ze bez tohohle neni videt, co se
    skutecne deje se VSIM, co projde mailboxem, jen s tim, co
    "vyhralo" a skoncilo v nekterym z existujicich front (Poptavky/
    Doklady/Podpora). Vlastni commit (nezavisly na commitu volajiciho) -
    logovaci zaznam nesmi zavislet na uspesnem dokonceni business
    transakce, at je videt i to, co selhalo/bylo zahozeno."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO email_sync_log "
                "(imap_uid, message_id_header, from_email, from_name, subject, outcome, "
                " lead_id, conversation_id, document_id, note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (uid, message_id_header, from_email, from_name, subject, outcome,
                 lead_id, conversation_id, document_id, note),
            )
        conn.commit()
    except Exception as e:
        # Logovani nesmi shodit samotne zpracovani zpravy - stejny
        # princip jako "selhani odeslani e-mailu nesmi shodit odpoved".
        print(f"[support-email-sync] zapis do email_sync_log selhal (uid={uid}): {e}")


def _advance_uid(conn, uid):
    """Posune trvaly kurzor (email_sync_state.last_uid) - vola se po
    KAZDE uspesne vyhodnocene zprave (i te, ktera se nikam neulozila,
    napr. "nesouvisi s eshopem" - jednou vyhodnocena, podruhe uz
    zkoumat netreba). Vlastni commit, nezavisly na commitu business dat
    volajiciho (viz sync_incoming_emails - u zprav, ktere NECO ukladaji,
    se posunuti kurzoru deje ve STEJNE transakci jako ten zapis, aby byla
    atomicka; tahle funkce je pro pripady, kdy se nic jineho neuklada)."""
    with conn.cursor() as cur:
        cur.execute("UPDATE email_sync_state SET last_uid=%s WHERE id=1 AND last_uid<%s", (uid, uid))
    conn.commit()


def sync_incoming_emails():
    if not IMAP_PASSWORD:
        print("[support-email-sync] IMAP_PASSWORD/SMTP_PASSWORD není nastaven, přeskakuji.")
        return 0

    processed = 0
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
    try:
        M.login(IMAP_USER, IMAP_PASSWORD)
        M.select("INBOX")

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT last_uid FROM email_sync_state WHERE id=1")
                row = cur.fetchone()
            last_uid = row["last_uid"] if row else 0

            # DULEZITE (viz AGENTS_LOG.md pro cely kontext incidentu):
            # puvodne se hledalo pres "SEARCH UNSEEN" (podle priznaku
            # precteno/neprecteno) - ten ale meni i cokoliv jineho, co
            # schranku cte (Gmail appka/web), a to rychleji nez 2minutovy
            # tik tehle synchronizace - realne e-maily tak proklouzavaly
            # bez povsimnuti. UID SEARCH ALL + filtr v Pythonu podle
            # trvale ulozeneho last_uid je na tomhle zcela nezavisly -
            # "ALL" vraci jen levny seznam cisel (ne stahovani zprav), i
            # pro tisice zprav ve schrance.
            typ, data = M.uid("search", None, "ALL")
            if typ != "OK":
                print(f"[support-email-sync] IMAP UID search selhalo: {typ}")
                return 0
            uids = sorted(int(u) for u in data[0].split() if int(u) > last_uid)

            for uid in uids:
                try:
                    typ, msg_data = M.uid("fetch", str(uid), "(RFC822)")
                    if typ != "OK" or not msg_data or not msg_data[0]:
                        # bot23 2026-08-18: NE continue - kurzor (last_uid)
                        # se pro tenhle uid neposune, ale kdyby dalsi uid v
                        # teto davce uspel, jeho VLASTNI _advance_uid by
                        # last_uid presunul AZ ZA tenhle neuspesny -
                        # priste by uz "last_uid > uid" filtr (radek 341)
                        # tenhle e-mail navzdy preskocil (ztraceny, i kdyz
                        # slo jen o prechodny IMAP hik - "ZADNA ZTRATA DAT"
                        # je vyslovny cil modulu, viz komentar vyse). break
                        # misto continue: zastavit celou davku tady, zbyle
                        # uidy (vc. tohohle) se zkusi znovu za 2 min.
                        break
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    from_name, from_email = parseaddr(_decode_header_value(msg.get("From")))
                    from_email = (from_email or "").strip().lower()
                    # Robert 2026-07-31: "ja si sam sobe posilam e-maily
                    # normalne abych na neco nezapomnel" + vyslovne potvrdil
                    # zruseni pojistky NATRVALO ("i moje vlastni e-maily") -
                    # puvodne se e-maily od vlastni adresy (IMAP_USER)
                    # preskakovaly (ochrana proti smycce, viz komentar v
                    # docstringu vyse) - ted uz ne, prochazi stejnou
                    # obsahovou klasifikaci jako cokoliv jineho. Skutecne
                    # riziko smycky bylo uz drive nizke (tento modul sam
                    # zadne automaticke odpovedi neposila, viz docstring),
                    # takze hlavni dopad je: Robertovy osobni pripominkove
                    # e-maily se ted taky zpracuji/ulozi (pravdepodobne jako
                    # "jine", pokud neobsahuji poptavkova klicova slova).
                    if not from_email:
                        _log_sync_outcome(conn, uid=uid, outcome="no_sender",
                                           subject=_decode_header_value(msg.get("Subject")))
                        M.uid("store", str(uid), "+FLAGS", "\\Seen")
                        _advance_uid(conn, uid)
                        continue
                    subject = _decode_header_value(msg.get("Subject"))
                    body_plain, body_html = _extract_body(msg)
                    body = body_plain[:MAX_BODY_CHARS] or "(prázdný e-mail)"
                    body_html = body_html[:MAX_HTML_BODY_CHARS] if body_html else None
                    # bot10 2026-08-22: vytazeno sem (drive jen tesne pred
                    # Podpora vetvi nize) - CRM/poptavka vetev potrebuje
                    # tytez hodnoty pro skutecne threadovani leadu (viz
                    # crm.find_or_create_lead(), sql/2026-08-22_crm_lead_
                    # message_threading.sql), ne jen Podpora.
                    email_message_id_header = (msg.get("Message-ID") or "").strip() or None
                    referenced_ids = _referenced_message_ids(msg)

                    # Robert 2026-08-24 (David Kalina - stejny e-mail
                    # zpracovan 2x, o den pozdeji, vznikly 2 samostatne
                    # poptavky se stejnym message_id_header): najit_or_
                    # vytvorit_lead/konverzaci resi jen threadovani PODLE
                    # ODKAZU NA JINE zpravy (In-Reply-To/References), ne
                    # jestli tahle KONKRETNI zprava uz nekdy byla ulozena -
                    # kdyz se e-mail zpracuje podruhe (napr. UID marker se
                    # neposunul spravne), vznikne uplny duplikat s TOTOZNYM
                    # Message-ID misto detekce "uz mam". Tvrdá pojistka
                    # navic k UID trackingu, ne nahrada za nej.
                    if email_message_id_header:
                        with conn.cursor() as dup_cur:
                            dup_cur.execute(
                                "SELECT 1 FROM crm_lead_messages WHERE message_id_header=%s "
                                "UNION SELECT 1 FROM shop_support_messages WHERE message_id_header=%s LIMIT 1",
                                (email_message_id_header, email_message_id_header),
                            )
                            already_seen = dup_cur.fetchone() is not None
                        if already_seen:
                            _log_sync_outcome(conn, uid=uid, message_id_header=email_message_id_header,
                                               from_email=from_email, from_name=from_name, subject=subject,
                                               outcome="duplicate", note="stejne Message-ID uz zpracovano drive")
                            M.uid("store", str(uid), "+FLAGS", "\\Seen")
                            _advance_uid(conn, uid)
                            continue

                    # Robert: admin panel "pro nastavovani filtru" - vyjimka
                    # podle odesilatele/domeny se kontroluje JAKO PRVNI,
                    # pred slovnim klasifikatorem. 'ignore' = absolutni
                    # override, email se nikam neulozi (presne resi
                    # incident, kdy potvrzeni objednavky z CIZIHO e-shopu
                    # omylem skoncilo v Podpore).
                    with conn.cursor() as rule_cur:
                        sender_rule = crm.match_sender_rule(rule_cur, from_email)
                    if sender_rule and sender_rule["rule_type"] == "ignore":
                        _log_sync_outcome(conn, uid=uid, message_id_header=email_message_id_header,
                                           from_email=from_email, from_name=from_name, subject=subject,
                                           outcome="ignored", note=f"sender_rule #{sender_rule['id']}")
                        M.uid("store", str(uid), "+FLAGS", "\\Seen")
                        _advance_uid(conn, uid)
                        continue

                    # Robert pres bot3, 2026-08-23 ("ad 1 jiste") - viz
                    # komentar u _ORDER_CONFIRMATION_COPY_SUBJECT_RE vyse.
                    # OBOJI podminka soucasne (ne jen jedna z nich) -
                    # konzervativnejsi nez holy predmet-pattern samotny,
                    # at se omylem nepreskoci skutecna zakaznicka zprava,
                    # ktera by nahodou mela podobne formulovany predmet.
                    if from_email == SMTP_USER.strip().lower() and \
                            _ORDER_CONFIRMATION_COPY_SUBJECT_RE.match(subject or ""):
                        _log_sync_outcome(conn, uid=uid, message_id_header=email_message_id_header,
                                           from_email=from_email, from_name=from_name, subject=subject,
                                           outcome="self_copy_skipped", note="kopie objednavkoveho potvrzeni z vlastni schranky")
                        M.uid("store", str(uid), "+FLAGS", "\\Seen")
                        _advance_uid(conn, uid)
                        continue

                    # CRM/poptavky (bot5, 2026-07-31): Robert "chodi ruzne
                    # maily, zdaleka ne vse jsou poptavky" + CRM musi
                    # zachytit i UPLNE NOVE kontakty ("Ale i nove") - proto
                    # klasifikace bezi PRED _is_shop_related_email() branou
                    # nize, ktera by noveho (jeste nikdy neobjednavajiciho)
                    # kontaktu e-mail jinak tise zahodila. Kdyz je to
                    # poptavka, konci tady - existujici shop-related vetev
                    # se preskoci (ne zdvoji).
                    # Robert 2026-08-24: odesilatel, ktery je NASIM evidovanym
                    # dodavatelem (shop_suppliers), nebo ma rucni pravidlo
                    # force_objednavka, se NIKDY nema klasifikovat jako
                    # poptavka - bez ohledu na to, co usoudi slovni
                    # klasifikator (viz incident "RE: Objednavka NO-2026-
                    # 00037" skoncil v Poptavkach jen kvuli slovu
                    # "objednavka" v predmetu). Kontrola PRED klasifikatorem,
                    # ne dodatecna oprava vysledku.
                    with conn.cursor() as supplier_cur:
                        is_known_supplier = crm.is_known_supplier_email(supplier_cur, from_email)
                    is_forced_not_poptavka = is_known_supplier or (
                        sender_rule and sender_rule["rule_type"] == "force_objednavka"
                    )
                    if sender_rule and sender_rule["rule_type"] == "force_poptavka":
                        label = "poptavka"
                    elif is_forced_not_poptavka:
                        label = "jine"
                    else:
                        label = crm.classify_incoming_email(subject, body)
                    # Robert 2026-08-24 ("objednávka skončila v dokladech...
                    # chyba!") - druhy vyskyt stejneho zakladniho problemu
                    # jako 958aaf9 (_ORDER_CONFIRMATION_COPY_SUBJECT_RE), ale
                    # TENTOKRAT od RUZNEHO odesilatele (Ing. Roman Vrana), ne
                    # nasi vlastni SMTP_USER kopie - puvodni fix proto
                    # nezabral (vyzadoval OBOJI podminky soucasne, viz jeho
                    # komentar). Predmet "[LOGiMAN] Objednavka <cislo>" ma
                    # sablonovy text ("zálohová faktura"/"variabilní symbol
                    # platby"), ktery klasifikator spolehlive plete s
                    # doklad - ALE narozdil od puvodniho pripadu (cista
                    # kopie, bezpecne uplne zahodit) tohle muze byt SKUTECNA
                    # zprava od zakaznika/dodavatele k teto objednavce, ne
                    # jen ozvena - nezahazovat, jen vyloucit z "doklad" (at
                    # skonci normalne v Podpore, ne ve fronte Prijate doklady
                    # na schvaleni jako faktura).
                    if label == "doklad" and _ORDER_CONFIRMATION_COPY_SUBJECT_RE.match(subject or ""):
                        label = "jine"
                    if label == "poptavka":
                        attachments = _extract_attachments(msg)
                        with conn.cursor() as cur:
                            lead_id = crm.find_or_create_lead(
                                cur, from_email, from_name, subject, referenced_ids
                            )
                            cur.execute(
                                "INSERT INTO crm_lead_messages "
                                "(lead_id, sender_type, sender_name, body, body_html, message_id_header) "
                                "VALUES (%s,'contact',%s,%s,%s,%s)",
                                (lead_id, from_name or from_email, body, body_html, email_message_id_header),
                            )
                            message_id = cur.lastrowid
                            for att_filename, att_content_type, att_data in attachments:
                                quotes.save_lead_attachment(cur, message_id, lead_id, att_filename, att_content_type, att_data)
                            cur.execute(
                                "UPDATE crm_leads SET unread_by_admin=1, last_message_at=NOW() WHERE id=%s",
                                (lead_id,),
                            )
                            # "Poptavka jako stitek v E-mailech prichozich"
                            # (bot10, 2026-08-23, Robert pres bot3: "jako
                            # stitek opticky uz v emailech") - DUAL-WRITE,
                            # ne nahrada: lead vyse zustava plnohodnotnym
                            # zaznamem (hodnota obchodu/ukoly/poznamky), ale
                            # navic se zrcadli i do shop_support_conversations
                            # (stejne threadovani jako normalni e-maily,
                            # viz _find_or_create_conversation nize v
                            # souboru), aby byl e-mail videt i v hlavni
                            # schrance E-maily prichozi - s viditelnym
                            # stitkem (linked_lead_id, viz webapp/admin.html),
                            # ne jen v oddelene zalozce Poptavky. Zadny zasah
                            # do stavajici query/paginace E-mailu prichozich -
                            # jen dalsi bezny radek navic.
                            conv_id, user_id = _find_or_create_conversation(
                                cur, from_email, from_name, subject, referenced_ids
                            )
                            cur.execute(
                                "INSERT INTO shop_support_messages "
                                "(conversation_id, sender_type, sender_user_id, sender_name, body, body_html, message_id_header) "
                                "VALUES (%s,'customer',%s,%s,%s,%s,%s)",
                                (conv_id, user_id, from_name or from_email, body, body_html, email_message_id_header),
                            )
                            support_message_id = cur.lastrowid
                            if attachments:
                                _record_support_message_attachment_meta(cur, support_message_id, attachments)
                            cur.execute(
                                "UPDATE shop_support_conversations SET unread_by_admin=1, last_message_at=NOW(), "
                                "status='open', linked_lead_id=%s WHERE id=%s",
                                (lead_id, conv_id),
                            )
                            cur.execute("UPDATE email_sync_state SET last_uid=%s WHERE id=1 AND last_uid<%s", (uid, uid))
                        conn.commit()
                        _log_sync_outcome(conn, uid=uid, message_id_header=email_message_id_header,
                                           from_email=from_email, from_name=from_name, subject=subject,
                                           outcome="poptavka", lead_id=lead_id, conversation_id=conv_id)
                        M.uid("store", str(uid), "+FLAGS", "\\Seen")
                        processed += 1
                        continue

                    # Prijate ucetni doklady (bot8, 2026-08-17, Robert
                    # pres bot3: "aby se emaily analyzovali na... opravdu
                    # doklady, ktere musime zavadet do ucetnictvi") -
                    # stejny princip jako poptavka vyse (klasifikace PRED
                    # _is_shop_related_email branou, protoze odesilatel
                    # faktury temer nikdy neni "eshopovy zakaznik" a driv
                    # by tak tise propadl). Konci ve schvalovaci fronte
                    # (incoming_documents.approval_status='ceka_schvaleni'),
                    # NE primo ve Sdilenem disku - viz modulovy docstring
                    # incoming_documents.py pro cely kontext.
                    if label == "doklad":
                        attachments = _extract_attachments(msg)
                        try:
                            received_at = parsedate_to_datetime(msg.get("Date"))
                            if received_at.tzinfo is not None:
                                received_at = received_at.astimezone().replace(tzinfo=None)
                        except (TypeError, ValueError):
                            received_at = None
                        with conn.cursor() as cur:
                            if received_at is None:
                                cur.execute("SELECT NOW() AS n")
                                received_at = cur.fetchone()["n"]
                            incoming_documents.save_incoming_document(
                                cur, from_email, from_name, subject, body, received_at, attachments,
                            )
                            new_document_id = cur.lastrowid
                            cur.execute("UPDATE email_sync_state SET last_uid=%s WHERE id=1 AND last_uid<%s", (uid, uid))
                        conn.commit()
                        _log_sync_outcome(conn, uid=uid, message_id_header=email_message_id_header,
                                           from_email=from_email, from_name=from_name, subject=subject,
                                           outcome="doklad", document_id=new_document_id,
                                           note=f"{len(attachments)} příloh" if attachments else "bez přílohy")
                        M.uid("store", str(uid), "+FLAGS", "\\Seen")
                        processed += 1
                        continue

                    # bot23 2026-08-18 (Robert pres bot3): DRIVE se tady
                    # kontrolovalo _is_shop_related_email() a "ne-shopove"
                    # e-maily koncily v email_review_queue - tabulce BEZ
                    # jakehokoli admin UI/API, cetne jen rucnim CLI skriptem
                    # na vyzadani. V praxi to znamenalo, ze Robert nektere
                    # e-maily proste nikdy nevidel ("nikde se neobjevily").
                    # Robert vyslovne zadal (po zvazeni varianty s
                    # oddelenou frontou "Ostatni posta"): VSECHNY e-maily,
                    # ktere nejsou poptavka/doklad, ted konci primo v
                    # Podpore ("Emaily prichozi") - zadna neviditelna
                    # fronta. Filtrovani spamu/notifikaci reseno az podle
                    # skutecneho objemu, ne predem teoreticky. Branka
                    # _is_shop_related_email()/email_review_queue proto uz
                    # NENI v teto ceste pouzivana (funkce/tabulka zustavaji
                    # v kodu/DB, jen se sem nevola).
                    # message_id/referenced_ids uz vytazeny vys (sdileno s CRM vetvi).
                    # 'objednavka' (bot11, 2026-08-19, PREPSANO bot9
                    # 2026-08-22): odesilatel s deterministickym pravidlem
                    # force_objednavka (napr. Logy.cz) - nemusi cekat na
                    # rucni triazi, protoze klasifikace uz probehla
                    # spolehlive podle odesilatele. PUVODNE rovnou
                    # archivovana - Robert (2026-08-22, durazne):
                    # "objednavka se nearchivuje !!! jde do objednavek".
                    # Ted misto archivace PROPOJENI na shop_orders zaznam
                    # (support._link_conversation_to_order, stejna funkce
                    # jako u rucni/triage cesty nize) - kdyz se cislo
                    # objednavky nenajde, konverzace zustava beze zmeny v
                    # Emaily prichozi (zadne tiche mizeni dat).
                    is_forced_objednavka = bool(sender_rule and sender_rule["rule_type"] == "force_objednavka")
                    with conn.cursor() as cur:
                        conv_id, user_id = _find_or_create_conversation(
                            cur, from_email, from_name, subject, referenced_ids
                        )
                        cur.execute(
                            "INSERT INTO shop_support_messages "
                            "(conversation_id, sender_type, sender_user_id, sender_name, body, body_html, message_id_header) "
                            "VALUES (%s,'customer',%s,%s,%s,%s,%s)",
                            (conv_id, user_id, from_name or from_email, body, body_html, email_message_id_header),
                        )
                        new_message_id = cur.lastrowid
                        # Robert 2026-08-24 (no-reply@demos-trade.com) - u
                        # sender-rule 'auto_archive' se prilohy vubec
                        # nezaznamenavaji (na rozdil od normalni cesty, kde
                        # se aspon metadata ulozi - viz komentar u
                        # _record_support_message_attachment_meta, obsah
                        # souboru se stejne nikdy neuklada na disk).
                        is_auto_archive = bool(sender_rule and sender_rule["rule_type"] == "auto_archive")
                        attachments = _extract_attachments(msg)
                        if attachments and not is_auto_archive:
                            _record_support_message_attachment_meta(cur, new_message_id, attachments)
                        if is_forced_objednavka:
                            import support  # lazy - viz support.py::_move_conversation_to_crm pro stejny duvod
                            support._link_conversation_to_order(cur, conv_id)
                            cur.execute(
                                "UPDATE shop_support_conversations SET unread_by_admin=0, last_message_at=NOW(), "
                                "status='open' WHERE id=%s",
                                (conv_id,),
                            )
                        elif is_auto_archive:
                            cur.execute(
                                "UPDATE shop_support_conversations SET unread_by_admin=0, last_message_at=NOW(), "
                                "status='closed', archived=1 WHERE id=%s",
                                (conv_id,),
                            )
                        else:
                            cur.execute(
                                "UPDATE shop_support_conversations SET unread_by_admin=1, last_message_at=NOW(), "
                                "status='open' WHERE id=%s",
                                (conv_id,),
                            )
                        cur.execute("UPDATE email_sync_state SET last_uid=%s WHERE id=1 AND last_uid<%s", (uid, uid))
                    conn.commit()
                    _log_sync_outcome(
                        conn, uid=uid, message_id_header=email_message_id_header,
                        from_email=from_email, from_name=from_name, subject=subject,
                        outcome=("objednavka_link" if is_forced_objednavka else "auto_archived" if is_auto_archive else "podpora"),
                        conversation_id=conv_id,
                    )
                    M.uid("store", str(uid), "+FLAGS", "\\Seen")
                    processed += 1
                except Exception as e:
                    # Kurzor se NEPOSOUVA (na rozdil od vsech vyse uvedenych
                    # uspesnych cest) - tahle zprava se zkusi znovu priste.
                    print(f"[support-email-sync] chyba při zpracování zprávy {uid}: {e}")
        finally:
            conn.close()
    finally:
        try:
            M.logout()
        except Exception:
            pass
    print(f"[support-email-sync] zpracováno {processed} nových e-mailů")
    return processed


if __name__ == "__main__":
    sync_incoming_emails()
