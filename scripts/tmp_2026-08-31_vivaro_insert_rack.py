import json, re, pymysql

env = {}
for line in open('/opt/konfigurator/api/.env'):
    line = line.rstrip('\n')
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v

conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

with open("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_full_rack.json") as f:
    rack_parts = json.load(f)

car_body_parts = [
    {"part_id": "car_body_642", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
    {"part_id": "car_body_643", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
    {"part_id": "car_body_644", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
]

all_parts = car_body_parts + rack_parts

name = "Vivaro OP18 - boxy43-270x2-220x2-120x12"
payload = {
    "parts": all_parts,
    "join_groups": [],
    "frame_groups": [],
    "bom": [],
    "price_summary": {},
    "_note": (
        "PILOT sestava (bot16, 2026-08-31) - regal na euroboxy pro LEVOU "
        "stenu prazdneho Opel/Vauxhall/Renault/Citroen Vivaro OP18 2019- "
        "(car_bodies 642 L / 643 R_D / 644 B), profil noh prevedeny 40x40 -> "
        "30x30 (custom_shapes.id=528 plna / 529 vyrez, odvozeno ze "
        "STEJNYCH 40x40 dat jako Jumpy CI14 - custom_shapes 516/517 jsou "
        "byte-identicke s 503/504, prevod tedy vysel numericky identicky s "
        "jiz overenym Jumpy 526/527). "
        "KAROSERIE: Vivaro OP18 GLB (642/643/644) byla TETO session FYZICKY "
        "OTOCENA o 180 stupnu kolem Y (zMidB pred flipem +2643.2, needs_flip "
        "potvrzeno nezavisle i auditem car_bodies katalogu) - stejny binarni "
        "patch jako CI14/CI25, zalohy originalu v "
        "backups/2026-08-31_car_body_vivaro_op18_pre_180_flip/. "
        "KRITICKY METODICKY NALEZ (nove, relevantni pro VSECHNY dalsi "
        "flipnute karoserie se stenou L na ZAPORNE strane X): "
        "puvodni 'offsetX + localX' konvence pro mapovani leg-dilu do "
        "sveta (pouzivana beze zmeny na CI24/CI25/Movano, kde stena L byla "
        "na KLADNE strane X) davala na Vivaru (stena L na ZAPORNE strane X) "
        "OBRACENE role - dil urceny jako 'zadni-svislice'/'cap' (ma byt u "
        "steny) vysel FYZICKY DAL od steny nez 'predni-svislice' (ma byt "
        "daleko od steny, plna vyska bez vyrezu) - objeveno diagnostikou "
        "(nizka sonda 0-395mm kolidovala na local-X 15-75, tj. u 'predni' "
        "strany, ne u 'zadni'). OPRAVENO na 'worldX = offsetX - localX' "
        "(mirror) - po oprave offsetX zmenilo hodnotu z -688 na -425 a "
        "vyrezova noha spravne cisti skutecny podbeh (viz nasledujici bod). "
        "KOLIZNI KROKOVANI (car_body_placement_methods.id=1): noha0 (plain, "
        "u prepazky) anchorZ=-2373 (offsetX=-425, offsetY=2, po opravene "
        "mirror konvenci). Diagnostickym skenem (tmp_2026-08-31_vivaro_"
        "scan_wall.js) zjisteno: PLNA noha koliduje s podbehem od "
        "anchorZ=-1223 dal (smerem k otevrenemu konci), VYREZOVA noha az od "
        "anchorZ=-33 - podbeh je tedy dlouhy usek (~1190mm), ktery jen "
        "vyrezova noha dokaze prekonat/prejet - presne situace 'nezastavovat "
        "se u podbehu' (Movano pouceni) - v teto sestave POKRACUJEME dalsimi "
        "sloupci PRES cely tento usek az k realne zadni hranici vozidla. "
        "max_rozpon_nohou: kolize nalezena pri anchorZ=-35, 20mm zpet -> "
        "REAR_ANCHOR_Z=-55 (maxSpan=2318mm od prepazky). "
        "SLOUPCE (shape_geometry_methods.id=5, hladove nejsirsi-nejdriv): "
        "sloupec0 N=3 (1232mm) mezi noha0(plain,Z=-2373) a noha1(vyrez,"
        "Z=-1111) - noha1 je JIZ HLUBOKO V ZONE PODBEHU (podbeh zacina "
        "-1223), vyrezovy tvar ji tam umoznuje stat bez kolize. sloupec1 "
        "N=2 (832mm) mezi noha1 a noha2(vyrez,Z=-249) - take v zone podbehu "
        "(podbeh konci az -33). Za noha2 zbyva jen 164mm do REAR_ANCHOR_Z "
        "(-55) - nestaci ani na nejmensi 1box (430mm), koneckoncu plneni. "
        "PROTAZENI VYREZOVYCH NOH (shape_geometry_methods.id=6): noha1 "
        "Y_new=213mm (DELTA_Y=182), noha2 Y_new=139mm (DELTA_Y=256) - "
        "nejednotne podel steny, potvrzuje ze tvar podbehu neni konstantni "
        "(stejny vzorec jako u CI25). RAIL FLOOR PRES CELY ROZPON SLOUPCE "
        "(dodatecna kontrola z CI25 nalezu): sloupec0 floor=213 (leg-based, "
        "bez kolize primo na leg-based kandidatu), sloupec1 floor=318 "
        "(leg-based 213 KOLIDOVALO na nosniku/spojnicich pres cely rozpon, "
        "fresh 1mm krokovani nahoru + 20mm rezerva -> 318mm). "
        "FYZICKY STROP PRO PRESAHOVY BOX (nova kontrola, shape_geometry_"
        "methods.id=3 box_muze_presahovat_zadni_profil_2026_08_31): siroky "
        "sondovaci box (cela hloubka D=326mm) kolizne krokovan nahoru pro "
        "kazdy sloupec zvlast - sloupec0 kolize pri Y=924, 2mm zpet -> "
        "fyzicky strop=922mm; sloupec1 kolize pri Y=926 -> strop=924mm. Oba "
        "jen ~2-4mm nad starym joint-containment stropem 920mm (H-CAP_H) - "
        "NOVE pravidlo bylo spravne implementovano a testovano (top-patro "
        "smi presahnout 920 az do tohoto fyzickeho stropu, RAIL zustava "
        "<=905 stred/920 horni hrana beze zmeny), ale u teto konkretni "
        "karoserie a hrube 50mm granularite dostupnych vysek (120/170/220/"
        "270) zadna dosazitelna kombinace prakticky nevyuziva presah nad "
        "920 (nejlepsi nalezene kombinace vychazeji na topBox=903mm a "
        "898mm, tedy pod 920 i bez noveho pravidla) - viz report pro "
        "detailni vysvetleni (uzka ~2-4mm rezerva vs. 50mm kroky vysek boxu "
        "zabranuje presnemu 'padnuti' do demonstracniho okna u TETO "
        "karoserie, mechanismus je ale spravne zapojen a bude vyuzitelny u "
        "jinych vozidel s vetsi rezervou strechy nad 920mm). "
        "VYSKOVA VARIABILITA (shape_geometry_methods.id=3, min. 3 vysky): "
        "sloupec0 4 patra x 120mm (12 boxu), sloupec1 2 patra 270mm+220mm "
        "(4 boxy) - CELKEM 3 ruzne vysky pouzite v cele sestave (120/220/"
        "270), diverzifikovano napric sloupci (sloupec0 uniformni pro "
        "maximalni pocet, sloupec1 diverzifikovany). "
        "VYSLEDEK: 3 nohy, 2 sloupce, 16 euroboxu celkem (12x120mm + "
        "2x220mm + 2x270mm). Overeno: bez kolize s karoserii Vivaro "
        "(collidesWithWalls na vsech Object_7 profilech I na vsech "
        "euroboxech samostatne - kriticke kvuli presahovemu pravidlu), bez "
        "neocekavanych vzajemnych presahu dilu (73 ocekavanych nestingu "
        "eurobox/zaslepka do profilu, 0 neocekavanych, 78 dilu celkem)."
    ),
}


def generate_sku(cur, name):
    base = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").upper()[:40] or "SESTAVA"
    candidate = f"SEST-{base}"
    n = 1
    while True:
        cur.execute("SELECT id FROM shop_products WHERE sku=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        n += 1
        candidate = f"SEST-{base}-{n}"


with conn.cursor() as cur:
    sku = generate_sku(cur, name)
    cur.execute("INSERT INTO shop_products (sku, name, unit, active) VALUES (%s,%s,%s,0)", (sku, name, "ks"))
    shop_product_id = cur.lastrowid
    cur.execute(
        "INSERT INTO product_assemblies (name, category_id, data, created_by, is_public, shop_product_id) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (name, None, json.dumps(payload, ensure_ascii=False), None, 1, shop_product_id),
    )
    new_id = cur.lastrowid
    print(f"product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku}, celkem dilu={len(all_parts)}")
conn.commit()
conn.close()
