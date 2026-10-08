"""GET /api/site-brand - logo znacky jen pro hostitele, kde se smi ukazat (bot16, 2026-10-01, Robert pres bot3: "at ma
Logiman jednotny vzhled jako na homepage").

PROC TAKHLE A NE LOGO V HTML: login/register/forgot-password/reset-password/verify-email jsou STATICKE stranky SDILENE s
domenami mini-eshopu (nginx `location /` s root webapp/ na storefront vhostech) a forgot/reset i s app.remeslnik.pro (jina
znacka). Na storefrontech nesmi byt zminena materska firma NIKDE v HTML zdroji (TEXT_FILTR.md pravidlo 5, Robert
2026-08-30: "Logiman nemuze byt uveden ani v paticce"; hlida to QA storefront_brand_mention a static_page_brand_leak).
Proto je v tech strankach jen prazdne misto #siteLogoSlot a maly vlozeny skript, ktery zavola tenhle endpoint a logo vlozi,
jen kdyz ho server vrati pro dany Host. VSECHNY retezce znacky jsou TADY na serveru. Vzhled loga: webapp/css/brand-logo.css
(jedine misto pravdy - jeho kopie jsou jeste v ostatnich strankach, viz poznamka tam).

PISMO: homepage a dalsi stranky dostavaji pismo webu (--font-main, volba admina v site_font.py) pri SSR; staticke formulare
ho nemaji, takze logo (font-weight 800 na systemovem fontu casto skoci na nejtezsi rez) by vypadalo jinak nez na homepage
(stejna past jako moje-objednavky.html, 2026-09-27). Server proto k logu posle i aktualni pismo (stejny stack a stejny
Google Fonts dotaz jako site_font_ssr_head - JEN s display=block, aby se logo neukazalo nejdriv v nahradnim pismu).
Pismo se aplikuje jen na logo (--font-main na #siteLogoSlot), ne na zbytek formulare.

FAIL-SAFE: neznamy nebo novy host = zadne logo (nova domena zustane anonymni, dokud ji nekdo vyslovne nepovoli nize).
Povolene hosty: host z PUBLIC_BASE_URL (+ www.) a IP vhost hlavniho webu (Robertuv pristup).
Pozn.: Host se predava z nginx (`proxy_set_header Host $host`); na remeslnik.pro `/api/` nemiri na tenhle backend, takze
tam endpoint neexistuje (404) a skript to bere jako "zadne logo".
"""
from urllib.parse import urlparse

from flask import jsonify, request

from app import app, get_conn, get_setting, PUBLIC_BASE_URL
from site_font import FONT_OPTIONS, SETTING_KEY, _resolve_key

_HLAVNI = (urlparse(PUBLIC_BASE_URL).hostname or "").lower()
# Hosty (bez portu), pro ktere se logo ukazuje. IP vhost = pristup k hlavnimu webu pres IP:8090.
_LOGO_HOSTS = frozenset(h for h in (_HLAVNI, "www." + _HLAVNI if _HLAVNI else "", "75.119.132.164") if h)

_LOGO_HTML = ('<a class="brand-logo" href="/" aria-label="Logiman">'
              '<span class="brand-logo-hl">LOGi</span><span class="brand-logo-lt">MAN</span></a>')
_LOGO_CSS = "/css/brand-logo.css"


def _pismo_webu():
    """(stack, google_css_url | None) - stejna volba pisma jako na homepage; pri chybe DB (None, None) = logo v systemovem pismu."""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                key = _resolve_key(get_setting(cur, SETTING_KEY))
        finally:
            conn.close()
    except Exception as e:  # logo se ma ukazat i kdyz nejde precist pismo
        app.logger.warning("site-brand: pismo webu se nepodarilo nacist (%s)", e)
        return None, None
    opt = FONT_OPTIONS[key]
    css = "https://fonts.googleapis.com/css2?family=%s&display=block" % opt["google"] if opt["google"] else None
    return opt["stack"], css


@app.get("/api/site-brand")
def site_brand_get():
    host = (request.host or "").split(":")[0].strip().lower()
    logo = None
    if host in _LOGO_HOSTS:
        stack, font_css = _pismo_webu()
        logo = {"html": _LOGO_HTML, "css": _LOGO_CSS, "font_stack": stack, "font_css": font_css}
    resp = jsonify({"logo": logo})
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp
