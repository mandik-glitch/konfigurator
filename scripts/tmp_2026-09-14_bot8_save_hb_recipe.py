#!/usr/bin/env python3
import sys, json
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn

SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad"
with open(f"{SCRATCH}/verify_after_revert.json") as f:
    V = json.load(f)

HB_PREFIXES = ("podelnik-", "pricka-spodni", "pricka-horni", "pricka-police", "vypln-")


def is_hb(p):
    return (p.get("role") or "").startswith(HB_PREFIXES)


VARIANTY = {
    "01": {"a": 369, "b": 370, "kod_metody_9": 2, "nazev": "Jedno pásmo, rám + dna [ZÁKLAD]"},
    "02": {"a": 382, "b": 379, "kod_metody_9": 4, "nazev": "Dvě pásma, police jen příčky"},
    "03": {"a": 383, "b": 380, "kod_metody_9": 5, "nazev": "Dvě pásma, plné výplně, bez police"},
    "04": {"a": 384, "b": 385, "kod_metody_9": 6, "nazev": "Dvě pásma, plné výplně, s policí"},
}


def part_slim(p):
    return {
        "role": p["role"],
        "part_id": p["part_id"],
        "position": [round(v, 3) for v in p["position"]],
        "quaternion": [round(v, 4) for v in p["quaternion"]],
        "scale": [round(v, 4) for v in p["scale"]],
    }


varianty_out = {}
for label, info in VARIANTY.items():
    a_id = str(info["a"])
    parts = [part_slim(p) for p in V[a_id]["data"]["parts"] if is_hb(p)]
    varianty_out[label] = {
        "nazev": info["nazev"],
        "assembly_ids": {"A": info["a"], "B": info["b"]},
        "pocet_dilu": len(parts),
        "odpovida_metode_9_kodu": info["kod_metody_9"],
        "dily": parts,
    }

definition = {
    "popis": (
        "Konkretni, OVERENA a FINALNI geometrie horniho bloku pro Doblo K-075 A/B, "
        "varianty 01-04 (product_assemblies 369/370, 382/379, 383/380, 384/385). "
        "Ucel zapisu (Robert 2026-09-14): 'potrebujeme optimalizovat cely postup, aby "
        "neobsahoval vsechny ty zmeny opravy, aby podle zapsaneho postupu nova session "
        "postavila stejne horni bloky tak jak je vidime ve scene' - tedy CISTY vysledek "
        "bez historie dnesniho ladeni (posun horniho bloku +17mm kvuli 25mm bezpecnostni "
        "mezere nad boxem, vymena eurobox 120->170mm, nasledny kolizni nesoulad a uplny "
        "navrat obojiho zpet) - to VSE byl SLEPY MEZIKROK, NENI soucasti tohoto postupu "
        "a nema se opakovat."
    ),
    "vztah_k_obecne_metode_id_9": (
        "Toto NENI nova obecna metoda, je to KONKRETNI APLIKACE obecne parametricke "
        "metody 'horni-blok-pro-dlouhe-predmety' (shape_geometry_methods.id=9) na Doblo "
        "K-075 A/B. Mapovani na jeji uzavreny seznam kod 1-6 (varianty_provedeni.seznam): "
        "01->kod 2 (Jedno pasmo, ram+dna), 02->kod 4 (Dve pasma, police jen pricky), "
        "03->kod 5 (Dve pasma, plne vyplne bez police, presna shoda - 0 odchylek), "
        "04->kod 6 (Dve pasma, plne vyplne s polici, presna shoda - 0 odchylek). "
        "JEDINA odchylka od generickeho seznamu je v 01 a 02, viz 'dorazova_deska_odchylka' nize."
    ),
    "vztah_k_c_rodine": (
        "DULEZITA ZMENA OPROTI DRIVEJSIMU POSTUPU (Robert 2026-09-14, doslovne): "
        "'C uz neni vzor. Vzorem pro horni bloky A/B jsou samotne horni bloky A/B [...], "
        "chceme aby vymeny boxu byly ponechany, ale horni bloky chceme stejne jake byly "
        "pred upravou boxu.' Drive se pri opravach A/B kopirovala geometrie z C-rodiny "
        "(342/344/346/341/343/345/347, technicky_ok=1) jako vzor. To uz NEPLATI - A/B "
        "je od 2026-09-14 SAMOSTATNY, na C nezavisly zdroj pravdy pro svou vlastni radu "
        "01-04. Pri budouci oprave A/B NEKOPIROVAT z C, vychazet z tohoto zapisu."
    ),
    "dorazova_deska_odchylka": (
        "Robert (drive v teto session): varianty BEZ (nebo jen s castecnymi) vyplnemi maji "
        "presto dostat JEDNU vyplen do predni nohy u prepazky jako dorazovou plochu na "
        "tyce/trubky, aby se pri 'eko' zpusobu ukladani (predmety lezici primo na profilech, "
        "viz metoda id=9 'EKO - POTVRZENO ROBERTEM') nesesmykavaly az k prepazce. Realizace: "
        "role 'vypln-bok-prepazka' (product_3939, Z=-1350.5 = noha u prepazky) je pritomna "
        "ve VSECH ctyrech variantach 01-04, i tam, kde by ciste podle metody id=9 kod 2/4 "
        "zadna vyplen nebyla. V 01 (kod 2) je to CISTY PRIDANY dil navic (9->10 dilu celkem). "
        "V 02 (kod 4) NAHRAZUJE jednu z generickych 3 pricek police - 'pricka-police-0' u "
        "prepazky CHYBI (jsou jen -1 a -2), misto ni je na jejim miste tahle vyplen (12 dilu "
        "celkem sedi na generickych 12, ale SLOZENI je jine - nekontrolovat jen pocet dilu, "
        "vzdy roli). V 03 (kod 5) a 04 (kod 6) uz je 'vypln-bok-prepazka'(-a/-b) SOUCASTI "
        "generickeho seznamu samotneho (plne vyplne pocitaji s ni uz ve sve zakladni podobe) "
        "- tam zadna odchylka neni, sedi 1:1 na id=9."
    ),
    "spolecne_pro_A_i_B": (
        "Overeno 2026-09-14 (viz current_8.json/verify_after_revert.json diff): horni blok "
        "je geometricky ZCELA IDENTICKY mezi A a B protejskem kazde varianty (369=370, "
        "382=379, 383=380, 384=385) - stejne role, part_id, position, quaternion, scale. "
        "A/B se lisi VYHRADNE v noze/karoserii-specifickych dilech MIMO horni blok. Staci "
        "tedy stavet/kontrolovat na JEDNE strane (A) a vysledek zkopirovat 1:1 na B."
    ),
    "postup_pro_novou_session": (
        "1. Over, ze cilova sestava uz ma hotovou nohu + eurobox regal (role 'predni-svislice'/"
        "'cap'/'eurobox-*' pritomne, technicky_ok mimo horni blok). "
        "2. Uisti se, ze ZADNA role horniho bloku (prefix 'podelnik-', 'pricka-spodni/horni/"
        "police', 'vypln-') v sestave jeste neexistuje (kod 0 test z id=9, "
        "'past_v_nazvoslovi') - pokud existuje stara/necista verze, nejdriv ji celou smazat "
        "(role, ne jen pozice), az pak pridavat novou. "
        "3. Vyber variantu 01-04 podle pozadavku zakaznika/Roberta a VEZMI PRESNE pole "
        "'dily' z odpovidajici varianty nize - zkopiruj role/part_id/position/quaternion/"
        "scale 1:1 do noveho pole parts (zadne prepocitavani, tyto hodnoty jsou jiz overene "
        "pro tuto konkretni geometrii noh Doblo K-075 A/B). "
        "4. Zapis stejnou sadu dilu i do B-protejsku (viz 'spolecna_pro_A_i_B'). "
        "5. Over realnou GLB kolizi (Box3 pairwise, tolerance 0.5mm na vsech 3 osach) proti "
        "CELE sestave (ne jen proti hornimu bloku) - ocekavane neskodne prekryvy jsou popsany "
        "v metode id=9 '4_zamerny_zasun_neni_kolize' (zasun do drazky <= 7mm) a v obecnych "
        "pravidlech bota8 (razitko-v-drazce [~8-10,~8-10,~222.2]mm, profil+vlastni zaslepka "
        "[5.25-8]mm) - COKOLI JINEHO je skutecny problem, nezanedbavat. "
        "6. Pokud sestava ma i box-upgrade (vetsi eurobox nez puvodnich 120mm) NAD touto "
        "kolonou, znovu OVER mezeru nad nejvyssim boxem podle AKTUALNE platneho bezpecnostniho "
        "pravidla (2026-09-14: 25mm) - tenhle zapis sam o sobe zadny box-upgrade neresi ani "
        "nepredpoklada (viz 'poznamky_a_otevrene_body')."
    ),
    "poznamky_a_otevrene_body": (
        "(a) Tento zapis odpovida stavu k 2026-09-14 PO uplnem zruseni dnesniho pokusu o "
        "box-upgrade (25mm pravidlo) - eurobox v kolonach je tedy na PUVODNI velikosti "
        "(120mm, product_3788). Box-upgrade zustava OTEVRENA, samostatna uloha - kdyz se "
        "bude znovu resit, musi pocitat s tim, ze KAZDY posun/uprava horniho bloku kvuli "
        "mezere OPUSTI tento zapis a je treba ho pak aktualizovat (bump verze), ne nechat "
        "zastarat mlcky. "
        "(b) Explicitni potvrzeni 'primo ve scene' (kanonicky posledni krok postupu uceni "
        "dilu) pro TENTO KONKRETNI zapis Robert dosud nedal - hodnoty pochazeji primo z "
        "live DB stavu po revertu, ktery Robert schvalil vecne (zrusit box-upgrade), ale "
        "vizualne znovu neprohledl. Doporuceno pred dalsim pouzitim jako sablony."
    ),
    "varianty": varianty_out,
}

conn = get_conn()
try:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO shape_geometry_methods (name, version, definition, verified_by, created_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            ("doblo-k075-ab-horni-blok-01-04", 1, json.dumps(definition, ensure_ascii=False), None, "bot8"),
        )
        new_id = cur.lastrowid
    conn.commit()
finally:
    conn.close()
print("INSERTED id=", new_id)
