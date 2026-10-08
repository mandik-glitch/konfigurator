"""
Podpora - 3Dbot automaticka AI odpoved - bot1, 2026-07-26.

Robert: "implementuj do okna podpory ve 3D scene naseho 3D bota aby mohl
reagovat uzivatelum na dotazy, a osetri aby vsechny nove budouci i stare
pravidla, tvary atd mel k dispozici aby reagoval vecne a dle vsech
dostupnych znalosti."

Rozhodnuto (AskUserQuestion, 2026-07-26):
  - Rezim: AI odpovida AUTOMATICKY A HNED (ne jen navrh pro Roberta cekajici
    na schvaleni) - viz support.py::support_customer_send().
  - Rozsah: POUZE zdroj 'widget_scene' (chat primo ve 3D konfiguratoru) -
    NE realizace.html, NE e-mail (tam odpovida jen Robert/tym).
  - Transparentnost: odpovedi jsou VIDITELNE OZNACENE jako od AI
    (sender_type='ai', sender_name='3Dbot') - netvari se jako clovek.

KLICOVY POZADAVEK "vsechny nove budouci i stare pravidla, tvary atd" je
resen tim, ze znalosti se ODSUD NEDUPLIKUJI rucne - `fetch_katalog_parts()`
cte ZIVOU DB tabulku cfg_dily a `load_profile_rules_doc()` cte
VLASTNOSTI_PROFILU.md PRIMO ZE SOUBORU pri KAZDEM volani (obe funkce
importovany z app.py - stejne zdroje, jake uz pouziva stavajici
/api/ai/generate pro 3Dbota v panelu 3D sceny). Jakakoli buduci zmena
katalogu (nove profily/ceny) nebo pravidel v VLASTNOSTI_PROFILU.md se tak
projevi OKAMZITE i tady, bez zasahu do tohoto souboru.

Na rozdil od /api/ai/generate tenhle modul NEMENI zakaznikovu 3D scenu -
jen odpovida textem (zadny tool-forcing, zadne 'steps'/'shape_calls').
Pokud zakaznik chce aktivne neco postavit, AI ho nasmeruje na existujici
chat '3Dbot' primo v panelu 3D sceny.

Selhani (chybejici API klic, vypadek Anthropic API, ...) NIKDY nesmi
shodit odeslani zakaznikovy zpravy - generate_ai_reply() v tom pripade
jen vrati None, volajici kod AI odpoved proste nevlozi a zprava ceka na
Roberta (stejny princip jako emails.py::send_and_log - AI vrstva je
"bonus", ne kriticka cesta).
"""
import json

from app import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    PROFILE_JOIN_PAIRS,
    cross_key,
    fetch_katalog_parts,
    load_profile_rules_doc,
)

MAX_TOKENS = 700


def _build_catalog_for_ai():
    """Stejna dedup logika jako v app.py::ai_generate() - FBX export ma pro
    nektere prurezy vice samostatnych katalogovych ID (duplicitni mesh
    instance), AI by si jinak mohla myslet, ze ma k dispozici jen tolik
    KUSU, kolik je ruznych ID. Zde jde jen o INFORMOVANI zakaznika
    (nestavi se scena), ale drzime stejnou logiku pro konzistentni odpovedi
    s tim, co by rekl 3Dbot v panelu 3D sceny."""
    parts = fetch_katalog_parts()
    seen_alu_cross = set()
    catalog = []
    for p in parts:
        pk = cross_key(p["cross_section_mm"])
        if p["layer"] == "alu" and pk:
            if pk in seen_alu_cross:
                continue
            seen_alu_cross.add(pk)
        catalog.append({
            "id": p["id"],
            "name": p["name"],
            "layer": p["layer"],
            "material": p["material_label"],
            "dims_mm": p["dims_mm"],
            "prurez": pk,
            "cena_orientacni_czk": p.get("price_czk_approx_PLACEHOLDER"),
        })
    return catalog


def _join_pairs_readable():
    return ", ".join(
        sorted(
            " = ".join(sorted(pair)) if len(pair) > 1 else next(iter(pair)) + " (jen samo se sebou)"
            for pair in PROFILE_JOIN_PAIRS if len(pair) > 1
        )
    )


def _build_system_prompt():
    catalog_for_ai = _build_catalog_for_ai()
    profile_rules_doc = load_profile_rules_doc()
    join_pairs_readable = _join_pairs_readable()
    return (
        "Jsi 3Dbot - technický asistent zákaznické podpory Konfigurátoru 3D "
        "objektů (LOGIMAN s.r.o., hliníkové profily a doplňky na míru). "
        "Odpovídáš zákazníkům v živém chatu přímo ve 3D konfigurátoru "
        "(záložka Podpora). Buď věcný, stručný a přirozený v češtině - jako "
        "zkušený kolega z podpory, ne jako robot s frázemi.\n\n"
        "Používej VÝHRADNĚ fakta z katalogu dílů a z připojené dokumentace "
        "níže - NIKDY si nevymýšlej ceny, rozměry, kompatibilitu průřezů ani "
        "pravidla, která v datech nejsou. Pokud odpověď neznáš nebo si "
        "nejsi jistý, řekni to přímo a nabídni, že se doptáš Roberta/týmu - "
        "člověk může do této konverzace kdykoli zasáhnout a odpovědět sám, "
        "takže tím konverzace nekončí ani nezklame zákazníka.\n\n"
        "Zákazník VÍ, že mluví s AI asistentem (3Dbot), ne s člověkem.\n\n"
        "NEMŮŽEŠ měnit zákazníkovu 3D scénu ani nic postavit za něj - to umí "
        "jen samostatný chat '3Dbot' přímo v panelu 3D scény (tlačítko "
        "'3Dbot' vpravo). Tady v Podpoře jen poradíš/vysvětlíš a případně "
        "na ten panel navnadíš, pokud chce zákazník aktivně něco postavit.\n\n"
        "Katalog dostupných dílů (JSON): " + json.dumps(catalog_for_ai, ensure_ascii=False) + "\n\n"
        "Pravidla spojování průřezů: každý průřez lze spojit sám se sebou, "
        "a navíc tyto dvojice: " + join_pairs_readable + ". Zatím se řeší "
        "jen KOLMÉ (90 stupňů) spoje, žádné 45stupňové ani libovolné úhly.\n\n"
        + (
            "DOPLŇKOVÁ DOKUMENTACE (VLASTNOSTI_PROFILU.md - kompletní interní "
            "zdroj pravdy o všech potvrzených výrobních/geometrických "
            "pravidlech, průběžně aktualizovaný při další práci na appce):\n\n"
            + profile_rules_doc
            if profile_rules_doc else ""
        )
    )


def generate_ai_reply(history_messages):
    """history_messages: seznam {"sender_type": "customer"|"operator"|"ai",
    "body": str} v CHRONOLOGICKEM poradi (nejstarsi prvni), VCETNE prave
    prijate zakaznicke zpravy jako POSLEDNI polozky. Vraci text odpovedi
    (str), nebo None pri jakemkoli duvodu neodpovedet (chybejici klic,
    prazdna historie, API vypadek, prazdna odpoved) - volajici kod v tom
    pripade AI zpravu proste nevlozi."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    anthropic_messages = [
        {
            "role": "user" if m["sender_type"] == "customer" else "assistant",
            "content": (m["body"] or "").strip() or "(prázdná zpráva)",
        }
        for m in history_messages
    ]
    if not anthropic_messages or anthropic_messages[-1]["role"] != "user":
        return None

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            system=_build_system_prompt(),
            messages=anthropic_messages,
        )
        text_block = next((b for b in response.content if getattr(b, "type", None) == "text"), None)
        text = text_block.text.strip() if text_block and getattr(text_block, "text", None) else ""
        return text or None
    except Exception as e:
        print(f"[support_ai] generate_ai_reply selhalo: {e}")
        return None
