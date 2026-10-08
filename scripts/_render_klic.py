"""Klic k zarazovani renderovacich uloh - kontrola pri vstupu do fronty.

Robert 2026-09-11: *„dej si na renderovaci ulohu zamek a klíč abys vedel
jen ty bot3, vydej plošný zákaz že žadny jiný bot než bot3 nesmi sahat na
PC s GPU."* (historicky citat - PUVODNI drzitel klice byl bot3).

AKTUALIZACE 2026-09-12: Robert primo bot4 ("Ano, ty (bot4) od teď") i
bot3 ("od dneška je správce GPU a renderů bot4") - spravcem GPU stanice
a renderu je ted bot4, ne bot3. Mechanismus/klic/duvody se NEMENI, meni
se jen KDO ho drzi a KOMU se ma neopravnene volani hlasit (viz _ROBERT/
_CO_TED nize). WORKFLOW.md pravidlo 31 uz bylo opraveno (bot9 2026-09-13).

AKTUALIZACE 2026-09-23 (Robert, pres bot3: "renderovat budete oba,
protoze nestihame"): bot10 pridan jako DRUHY drzitel klice, vyhradne
pro VANDR vetev (materialy, razitka, FBX/GLB dispatch) - nativni
Logiman render_auto_dispatch zustava jen u bot4. Klic (cesta v
KONFIGURATOR_RENDER_KLIC_SOUBOR) drzi bot4 i bot10; kdo z obou nema
nastaveno, ulohu nezaradi. Fronta je porad jedna (FIFO, jediny stroj),
takze zdvorilostni kontrola pred zarazenim (`2026-09-09_turntable_
status.py`) plati pro oba, ne cekani na svoleni druheho.

    from _render_klic import over_klic
    otisk = over_klic("zarazeni otocky")   # pri chybejicim klici ukonci skript

=== TOHLE NENI BEZPECNOSTNI OPATRENI A NESMI SE TAK TVARIT ===
Jde OBEJIT. Boti bezi jako `root`, takze si soubor s klicem muzou precist,
stejne jako ctou `api/.env`. Je to TYZ STROP, na jaky narazil bot9 u
pristupu k databazi (viz hlavicka scripts/_env.py) - a plati tu tentyz
zaver: pojistka, ktera se vydava za vic, nez je, je HORSI nez zadna,
protoze si nekdo mysli, ze neco drzi.

Co to tedy je: **zabrana proti jednani z vlastni iniciativy a proti omylu**,
umistena tam, kde vznika skoda. Jedna davka je ~3 hodiny GPU na JEDINE
stanici (Robertove `Logiman2`), takze omylem zarazena uloha stoji realny
cas na cizim stroji. Zabrana nuti zastavit se - to je cely ucel (od
2026-09-12 uz to neni "napsat bot3", protoze rozhodovani o renderech
delá primo bot4 - viz aktualizace vyse).

=== CO ZAMEK NEPOKRYVA ===
Zarazeni do fronty NENI jediny zpusob, jak render rozbehnout. Overeno
2026-09-11 pruchodem kodu; nezamcene cesty jsou tyhle:

  1. `POST /api/admin/blender-render` a `/api/admin/blender-render-blend`
     (api/blender_render.py) -> `dispatch_to_worker_or_local()`
     (api/render_worker.py:948). Kdyz je worker online, uloha jde NA GPU.
     ZAMERNE NEZAMCENO: je to `@admin_required` cesta, kterou pouziva
     Robert z prohlizece; zamek by zablokoval jeho. Na teto vrstve nejde
     odlisit "Robertuv prohlizec" od "bot se session cookie" - ochranou
     je tu pravidlo, ne mechanismus.
  2. Blender spusteny primo (`blender -b -noaudio -P
     api/blender_render_turntable.py -- <cfg>`). Na VPS to jede na CPU,
     ne na GPU stanici; na GPU stanici to vyzaduje se na ni pripojit, coz
     zakazuje plosny zakaz (WORKFLOW.md pravidlo 31).
  3. Rezim `--local` teze fronty renderuje na VPS (CPU, hodiny), ne na
     GPU. Presto se klic vyzaduje i pro nej - viz nize.

Kdo tenhle seznam cte pozdeji: over ho znovu, kod se meni. Prehled celeho
procesu je v PRODUKTOVE_RENDERY.md.

=== PROC SE KLIC VYZADUJE I PRO --local, --test A --prstenec ===
`--local` sice na GPU nesaha, ale porad je to render spusteny z vlastni
iniciative - jen mistto tri hodin GPU sezere hodiny CPU na produkcnim
serveru. A hlavne: vyjimka by byla navod, jak zamek obejit. Totez plati
pro jednosnimkove rezimy; PLAN_TVORBY_SESTAV.md rika vyslovne, ze zadani
plati "i pro jednosnimkove behy, --test a --prstenec".
"""
import hashlib
import os
import sys

ENV_PROMENNA = "KONFIGURATOR_RENDER_KLIC_SOUBOR"

_ROBERT = (
    "Robert 2026-09-11: \"rendery může zadávat jen bot3 který má přehled.\"\n"
    "  AKTUALIZACE 2026-09-12: správcem GPU stanice a renderů je teď bot4\n"
    "  (Robert přímo bot4 i bot3, viz hlavička souboru).\n"
    "  AKTUALIZACE 2026-09-23: bot10 přidán jako druhý držitel klíče,\n"
    "  výhradně pro VANDR větev (Robert přes bot3: \"renderovat budete\n"
    "  oba, protože nestíháme\"). Žádný JINÝ bot nespouští rendery z\n"
    "  vlastní iniciativy - ani zkušební, ani jednorázové, ani když má\n"
    "  hotový kód a je si jistý."
)

_CO_TED = (
    "CO S TÍM: napiš bot4 (nativní Logiman) nebo bot10 (Vandr větev) a\n"
    "  počkej. Ten z nich určí, která sestava a kdy. Znovuspuštění zabité\n"
    "  úlohy je NOVÉ zadání - i pro tentýž snímek, tutéž sestavu a tentýž\n"
    "  důvod. Změna způsobu běhu (mimo frontu, mimo službu, jiný stroj,\n"
    "  jiné parametry) se NAVRHUJE, neprovádí.\n"
    "  Podrobně: WORKFLOW.md pravidlo 31, PLAN_TVORBY_SESTAV.md fáze 4."
)

_STROP = (
    "POZNÁMKA K TOMUHLE ZÁMKU: není to bezpečnostní opatření a netváří se\n"
    "  tak. Boti běží jako root a soubor s klíčem si přečíst umí - je to\n"
    "  zábrana proti jednání z vlastní iniciativy a proti omylu, ne zeď.\n"
    "  Že ho obejít jde, není svolení ho obejít."
)


def _odmitni(duvod):
    raise SystemExit(
        "\nODMÍTNUTO: renderovací úloha se NEZAŘADILA.\n\n"
        "  DŮVOD: %s\n\n"
        "  %s\n\n"
        "  %s\n\n"
        "  %s\n" % (duvod, _ROBERT, _CO_TED, _STROP)
    )


def over_klic(co_delam="zařazení renderovací úlohy"):
    """Overi klic. Pri chybejicim/prazdnem klici skript UKONCI (SystemExit).

    Vraci OTISK klice (prvnich 12 znaku sha256) - ten se zapisuje do stavu
    ulohy. Neni to overeni spravnosti (spravnou hodnotu tenhle kod nezna a
    znat nema), je to ZAZNAM: kdyz nekdo zaradi ulohu s jinym souborem,
    bude to v `<job>.status.json` videt a bot4 to pozna.
    """
    cesta = os.environ.get(ENV_PROMENNA)
    if not cesta:
        _odmitni("proměnná prostředí %s není nastavená, takže ke klíči nevede "
                 "cesta.\n          Bez klíče se %s neprovede." % (ENV_PROMENNA, co_delam))
    if not os.path.isfile(cesta):
        _odmitni("%s ukazuje na %r, což není soubor." % (ENV_PROMENNA, cesta))
    try:
        with open(cesta, "rb") as fh:
            obsah = fh.read()
    except OSError as e:
        _odmitni("soubor s klíčem %r nejde přečíst: %s" % (cesta, e))
    if not obsah.strip():
        _odmitni("soubor s klíčem %r je prázdný." % cesta)
    _checkin_best_effort(co_delam)
    return hashlib.sha256(obsah.strip()).hexdigest()[:12]


def _checkin_best_effort(co_delam):
    """Robert 2026-09-12 ("uz hodinu neaktivni? to je pravda?"): tabulka
    Boti ukazovala bot4 (spravce GPU/renderu) jako "neaktivni", protoze
    jeho skutecna prace (zarazovani renderu) NEJDE pres git commit -
    checkin pres post-commit hook (viz .git/hooks/post-commit) ho tedy
    nikdy nezachyti. `over_klic()` je presne to misto, kudy VZDY prochazi
    KAZDA jeho render-souvisejici akce (i --test/--local), takze je to
    spravny druhy checkin bod pro tuhle konkretni roli - stejny princip
    jako git commit pro kodici boty, jina udalost. Best-effort/tichy fail
    (nikdy nesmí shodit render kvuli tomuhle vedlejsimu mechanismu)."""
    bot_id = os.environ.get("BOT_ID", "").strip()
    if not bot_id:
        return
    try:
        import urllib.request
        import urllib.parse
        q = urllib.parse.urlencode({"bot_id": bot_id, "cinnost": co_delam[:300]})
        urllib.request.urlopen("http://127.0.0.1:8090/api/bots/checkin?" + q, timeout=3)
    except Exception:
        pass


def kdo_zaradil():
    """`BOT_ID` volajiciho - do stavu ulohy, at jde zpetne poznat, kdo co
    pustil. Chybejici BOT_ID ulohu NEBLOKUJE (skript pousti i Robert rucne),
    jen se to hlasite napise a do stavu se ulozi, ze se to nevi."""
    bot = (os.environ.get("BOT_ID") or "").strip()
    if not bot:
        print("POZOR: BOT_ID není nastavené, do stavu úlohy se zapíše "
              "'(neuvedeno)'. Kdo úlohu zařadil, pak zpětně nepoznáš.",
              file=sys.stderr)
        return "(neuvedeno)"
    return bot
