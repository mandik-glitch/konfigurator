"""
Sdilene bezpecne stahovani z CIZICH URL (bot6, 2026-09-02, revize 17 pres
bot3). Jedno misto pro SSRF ochranu + limit velikosti, misto aby si kazdy
modul psal vlastni `urlopen` - HLAVNI PRAVIDLO z CLAUDE.md ("nejdriv se
podivej, jestli to uz nekde je").

Historie, proc to vzniklo (at se nezopakuje):
  - 2026-08-18 (bot11, AUDIT_SYSTEM nalez 1.4): `urllib.request` ma ve
    vychozim stavu zaregistrovany `FileHandler`, takze BEZ kontroly
    schematu by `file:///opt/konfigurator/api/.env` STAHLO lokalni soubor
    ze serveru. Opraveno tehdy jen v `gallery.py`.
  - 2026-09-02 (bot3, commit 4d67bd5): `gallery_items.py` dostal navic
    kontrolu cilove IP po DNS resolve + zakaz presmerovani.
  - 2026-09-02 (bot6, revize 17): stejna dira zustala v
    `remeslo_price_refresh.py` a `remeslo_price_search.py` - URL tam
    navic casto pochazi z PARSOVANEHO CIZIHO HTML, ne od admina. Navic
    nikde nebyl limit velikosti odpovedi (`resp.read()` bez argumentu),
    takze jedna obri odpoved umela natahnout RAM na sdilenem VPS.

`ensure_public_host` a `NoRedirectHandler` jsou PRESUNUTE z
`gallery_items.py` beze zmeny chovani - ten soubor si je odsud jen
importuje, aby jeho dosavadni (prisnejsi) rezim "zadne presmerovani
vubec" zustal presne takovy, jaky byl.
"""
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorFetch/1.0)"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """SSRF ochrana (bot3/revize kodu, 2026-09-02) - blokuje nasledovani
    3xx presmerovani. Overeni cilove IP (`ensure_public_host` nize) se
    dela jen na URL, kterou zadal uzivatel - presmerovani by mohlo vest
    na internal adresu bez dalsi kontroly. Misto nasledovani se vyhodi
    HTTPError, ktery volajici prevede na srozumitelnou 400 hlasku (nebo
    ho zpracuje `fetch_public_url`, ktery skok povoli a znovu overi)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, "Redirect blocked (SSRF ochrana)", headers, fp)


def ensure_public_host(hostname, port):
    """SSRF ochrana (bot3/revize kodu, 2026-09-02, navazuje na puvodni
    scheme-allowlist z 2026-08-18, AUDIT_SYSTEM_2026-08-18.md nalez 1.4):
    overi, ze VSECHNY IP adresy, na ktere se hostname prelozi, jsou
    verejne (ne loopback/privatni/link-local 169.254.*/CGNAT/multicast/
    unspecified) - jinak by prihlaseny stazitel (staff/remeslnik) mohl
    donutit server stahnout interni zdroj (napr. cloud metadata endpoint,
    admin rozhrani na localhost) a ulozit ho jako "gallery item". Vraci
    None na uspech, nebo ceskou chybovou hlasku k vraceni klientovi.

    POZOR - zbyva teoreticke DNS rebinding riziko (cas mezi timhle
    resolve a skutecnym connectem uvnitr urlopen muze u DNS s velmi
    kratkym TTL vratit JINOU IP) - bez vlastniho low-level connectu
    primo na uz overenou IP (misto hostname, coz by slozitejsi na TLS
    SNI) se nedá uplne vyloucit; tady jde o "dost dobrou" ochranu proti
    bezne dostupnym URL na interni sluzby, ne o kompletni reseni vsech
    SSRF variant."""
    if not hostname:
        return "Neplatná URL (chybí hostname)."
    try:
        addrinfo = socket.getaddrinfo(hostname, port)
    except socket.gaierror:
        return "Nepodařilo se přeložit doménu."
    for _family, _type, _proto, _canonname, sockaddr in addrinfo:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return "URL míří na interní adresu."
        # POZOR (overeno testem): ipaddress.is_global u multicastu (224-
        # 239.x.x.x) vraci True - neni "privatni" v terminologii stdlib,
        # ale rozhodne to neni verejny web server. is_global sam o sobe
        # multicast NEVYLOUCI, proto explicitni is_multicast navic.
        if not ip.is_global or ip.is_multicast:
            return "URL míří na interní adresu."
    return None


def _check_target(url):
    """Schema + cilova IP. Vraci normalizovanou (percent-encodovanou) URL
    nebo vyhodi ValueError s ceskou hlaskou pro uzivatele."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Nepovolené schéma URL (jen http/https).")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    host_err = ensure_public_host(parsed.hostname, port)
    if host_err:
        raise ValueError(host_err)
    # Zdrojove URL muzou mit mezery/diakritiku primo v ceste (Shoptet
    # nazvy souboru v URL) - bez tohohle urllib odmitne "control
    # characters"/non-ASCII. Stejny vzor jako puvodni gallery.py.
    return urllib.parse.quote(url, safe=":/?&=%")


def fetch_public_url(url, *, timeout, max_bytes, max_redirects=3,
                     user_agent=DEFAULT_USER_AGENT):
    """Stahne obsah VEREJNE http/https URL s SSRF ochranou a limitem
    velikosti. Vraci bytes.

    Presmerovani se NENASLEDUJE automaticky (to by obeslo kontrolu cile);
    misto toho se zpracuje rucne, nejvys `max_redirects` skoku, a KAZDY
    skok se znovu overi pres `_check_target`. Uplny zakaz nejde - cenove
    scrapery bezne narazi na http->https redirect e-shopu, ktery je
    legitimni.

    Vyhazuje:
      ValueError    - nepovolene schema, interni cil, prekroceny limit
                      velikosti, prilis mnoho presmerovani (hlaska je
                      cesky text urceny uzivateli)
      urllib.error.* / OSError - bezne sitove chyby, resi volajici
    """
    current = url
    for _hop in range(max_redirects + 1):
        safe_url = _check_target(current)
        req = urllib.request.Request(safe_url, headers={"User-Agent": user_agent})
        opener = urllib.request.build_opener(NoRedirectHandler)
        try:
            with opener.open(req, timeout=timeout) as resp:
                # +1 bajt navic: kdyz ho dostaneme, vime, ze zdroj limit
                # PREKROCIL (ne ze ho presne naplnil).
                data = resp.read(max_bytes + 1)
        except urllib.error.HTTPError as e:
            if e.code not in (301, 302, 303, 307, 308):
                raise
            location = (e.headers or {}).get("Location")
            if not location:
                raise
            current = urllib.parse.urljoin(current, location)
            continue
        if len(data) > max_bytes:
            raise ValueError(f"Odpověď je větší než povolený limit ({max_bytes} B).")
        return data
    raise ValueError(f"Příliš mnoho přesměrování (max {max_redirects}).")
