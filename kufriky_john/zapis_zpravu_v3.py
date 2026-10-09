"""Zpráva a stavová tabulka z ověřených souborů; čistý místní výpočet."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
URL='https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v3/'
cat=json.loads((ROOT/'kufriky.json').read_text())
geometry=json.loads((ROOT/'overeni-tvar-v3/rozmery.json').read_text())
attachments=json.loads((ROOT/'overeni-tvar-v3/uchyceni.json').read_text())
collisions=json.loads((ROOT/'overeni-tvar-v3/kolize.json').read_text())
review=json.loads((ROOT/'zdroje/doladeni-v3/review.json').read_text())
photos=json.loads((ROOT/'zdroje/doladeni-v3/fotografie.json').read_text())
rows=[next(r for r in cat['records'] if r['id']==i) for i in cat['model_order']]
maximum=max(r['bytes'] for r in geometry['rows'])
lines=[
 '# Nářadové kufříky – doladění modelů v3',
 '',
 'John, 6. 10. 2026. Přečteno celé AGENTS.md včetně 4d, 4e a 4f, celé zadání včetně doplnění 1–5 a geometrické podklady. Samostatná práce pouze na výstupech a povoleném statickém náhledu.',
 '',
 f'Náhled: [kufříky v3]({URL}). V2 zůstává na původní adrese beze změny. Upraveno 20 typů / 21 SKU; dalších 14 dílů systému zůstává mimo modelování.',
 '',
 '## Vidím ve zdrojích a v souborech',
 '',
 f'Z galerií konkrétních variant bylo přečteno {sum(len(r["photos"]) for r in photos["records"])} fotografií. John prohlédl všechny soukromé přehledy. Každá fotografie má přímou URL, produktovou stránku, místní soubor, rozlišení a SHA-256 v `zdroje/doladeni-v3/fotografie.json` a CSV. Dostupné jsou zavřené a otevřené kusy, spodní pohledy organizérů, zadní pohled pojízdného boxu, čelní pohledy zásuvek a detailní snímky spon a vnitřních vložek. Pokrytí úhlů není úplné pro každý typ. Profesní kufry mají pouze jediný výrobní snímek; veřejné CZ/SK nabídky opakují tentýž záběr. To není nezávislé potvrzení jejich vložek.',
 '',
 'Soukromé fotografie nebyly vložené do veřejného v3. V náhledu jsou pouze vlastní rendery v2/v3, odkazy na použité fotografie, seznam oprav, stav shody a konkrétní neověřené body. Porovnání fotografie–vlastní render je lokálně v `zdroje/doladeni-v3/porovnani-soukrome/<SKU>.jpg`. Směr pohledu byl přiblížen vybranému snímku; perspektiva není kalibrovaná a není to měřicí porovnání každého povrchu. U zdvižených či vysunutých madel se fotografie liší od přepravní polohy modelu.',
 '',
 'Nový průzkum CAD navázal na dřívější kandidáty; žádný úplný licencovaný CAD správného EU SKU se stažením bez účtu nebyl získán. Nebyl založen účet, odeslán formulář ani použit přihlašovací údaj. Dočasný soubor `zdroje/doladeni-v3/stranka-organizery.html` obsahoval vložený přístupový údaj z veřejné stránky; plná kopie byla odstraněna a podklady nyní obsahují pouze galerii a seznam variant.',
 '',
 'V3 neprovádí dodatečné natažení celého modelu. Ve všech GLB je `axis_scale=[1,1,1]` a `applied=false`. Kóty dutin a průměry kol proto nebyly přizpůsobením obálce zdeformovány. Konvence zůstává mm, X = šířka, Y = délka, Z = výška; kompaktní typy mají čelo na krátké straně. Všechny uzly mají souřadnice přímo ve vrcholech; katalogový parser přezkoumal 21 modelů a 3 původní katalogové reference.',
 '',
 '### Ověřené příčiny a opravy',
 '',
 '- `vytvor_realne_tvary.js:183–194` (původní v2): součet trčících detailů určil obálku, poté se celý model nestejně natahoval po osách. Kolo bedny 230 mm tak mělo digitální rozsah 246,234 × 229,585 mm. Nový generátor kontroluje obálku bez škálování; kola i známé dutiny měří nezávislý skript.',
 '- V2 řadila kompaktní organizér a kompaktní box stejně jako široké kufry; kompaktní organizér měl jednu sponu. Fotografie dokládají krátké čelo a dvě spony organizéru. V3 opravuje orientaci a počet, kompaktní box si ponechává jedinou širokou sponu.',
 '- V2 opakovala deset červených vložek i v hlubokém organizéru. Otevřené fotografie ukazují tři přední oddíly a zadní dlouhou přihrádku. V3 změnila vnitřní topologii.',
 '- V2 otáčela dvířka skříně do strany. Fotografie otevřeného kusu ukazuje horní vodorovný pant. V3 mění pant i směr otevření a odstraňuje vzorkováním zjištěný průnik panelu dvířek se stropem.',
 '- V2 umísťovala kola bedny na opačné konce a osy podél délky. Fotografie dokládají obě kola na jednom konci; ve v3 mají osu X a shodnou polohu Y. Doplněny dvě horní stohovací pozice.',
 '- V3 propojuje jednotlivé vrstvy víka, spodní spojovací patky, madla, zajišťovací rámy a úchopy s oporami. Profesní vložky mají duté kapsy a spočívají na dně. Žádný výsledek kontroly kontaktu není založen pouze na obálce.',
 '',
 '## Domnívám se / přesnost zůstává neověřená',
 '',
 '**Jde o vlastní modely se znovu upraveným reálným uspořádáním, nikoli o výrobcem ověřený přesný CAD všech povrchů.** Fotografie dokládají přítomnost a topologii dílů; nekótované proporce, poloměry, tloušťky a polohy zůstávají rekonstrukční parametry. Žádná z těchto hodnot nebyla zapsána jako ověřená technická vlastnost. Počet přesných CAD zůstává 0.',
 '',
 'Zjednodušené zůstává jemné odlehčení spodku, výztužná síť uvnitř víka, textová loga a drobné prolisy. Spojovací profily PACKOUT, vůle, montážní otvory, dráhy mechanismů, šířky kol a rozsahy madel je nutné doměřit nebo získat z kótovaného CAD. Barvy a povrch jsou pouze vzhledové. U nového XL SKU je galerie starší revize; u pojízdné zásuvky zůstává rozpor zdrojových vnějších rozměrů. Náhled tato slabá místa ukazuje.',
 '',
 '## Čisté kontroly a jejich rozsah',
 '',
 f'Všech {geometry["models_measured"]} GLB: {geometry["vertices_measured"]} skutečných vrcholů, {geometry["triangles_measured"]} trojúhelníků, normály, indexy a digitální obálka. Tolerance obálky 0,01 mm; největší soubor {maximum} B, všechny pod 3 MB. Nejde o toleranci fyzického výrobku.',
 '',
 f'Raycasting ověřil {len(geometry["cavities"])} zdrojových dutin přímo proti skutečným stěnám. Kontakt dokládá bod na trojúhelníku nebo průsečík hrany: {attachments["parts_measured"]} vyčnívajících dílů, {attachments["candidate_pairs_measured"]} kandidátních párů, {len(attachments["unresolved"])} nedoložených kontaktů. Samostatná kontrola ověřuje opory přihrádek a vložek.',
 '',
 f'Objemové vzorkování vnitřních nádob, zásuvek a dvířek proti nosnému tělu: {collisions["candidate_pairs_measured"]} kandidátních párů, {collisions["material_samples_measured"]} materiálových vzorků, {len(collisions["overlaps"])} zachycených průniků po opravě. Záměrně nejsou tímto kritériem hodnocené styky uvnitř jednoho výlisku, osy a upevňovací uložení. Není to důkaz úplné absence všech kolizí ani ověření pohybu mechanismu.',
 '',
 '```bash',
 'node vystupy/kufriky/vytvor_doladene_tvary_v3.js',
 'python3 vystupy/kufriky/sestav_nahled_v3.py',
 'python3 vystupy/kufriky/over_doladeni_v3.py',
 'python3 vystupy/kufriky/audit_kolizi_v3.py',
 'node vystupy/kufriky/over_v3_katalogovym_parserem.js',
 'node vystupy/kufriky/renderuj_porovnani_v3.js',
 'node vystupy/kufriky/over_nahled_v3.js',
 '```',
 '',
 'Všechny tyto přípravy a kontroly jsou místní, bez DB, sítě a hesel. Síť používá pouze oddělený průzkum veřejným GET a přečtení hotového statického náhledu. Historické generátory v1/v2 nespouštět přes nový katalog: vrátily by modely na starší stav.',
 '',
 '## Tabulka kontroly všech typů',
 '',
 '| SKU | Typ | Fotografií | Vidím na snímcích | Opraveno | Stav shody / slabé místo |',
 '|---|---|---:|---|---|---|',
]
for r in rows:
    rv=r['review'];lines.append('| '+' / '.join(r['sku'])+' | '+r['name']+' | '+str(rv['photo_count'])+' | '+rv['seen']+' | '+rv['changed']+' | '+rv['match']+' |')
lines += ['', '## Rozměrové výpočty v mm', '', 'Rozsah = maximum − minimum všech skutečných vrcholů. Bez posunu měřítka po osách.', '', '| SKU | Výpočet X; Y; Z [mm] | Odchylka [mm] | Zdroj |', '|---|---|---|---|']
for row in geometry['rows']:
    a=row['actual'];formula='; '.join(f'{hi:g} − ({lo:g}) = {hi-lo:g}' for lo,hi in zip(a['min_mm'],a['max_mm']))
    lines.append(f'| {row["sku"]} | {formula} | '+', '.join(f'{v:.6f}' for v in row['deviation_xyz_mm'])+f' | [rozměry]({row["source_url"]}) |')
lines += ['', '### Kola a známé dutiny', '', 'Bedna: D = 23 cm × 10 = 230 mm, R = 230 / 2 = 115 mm; skutečné vrcholy pneumatiky mají Y = 230 a Z = 230 mm. Pojízdný box a zásuvka: R = 228 / 2 = 114 mm; jejich skutečný rozsah X = 228 a Z = 228 mm. Osa kola bedny X, ostatních Y.', '', 'Zdrojové dutiny mají šířku a délku ověřenou jako součet prvních zásahů paprsků od středu k protilehlým stěnám. Výšku měří rozsah skutečné duté stěny:', '', '| SKU | Komponenta | X: levá + pravá stěna [mm] | Y: přední + zadní stěna [mm] | Z: výška stěny [mm] |', '|---|---|---:|---:|---:|']
for r in geometry['cavities']:
    lines.append(f'| {r["sku"]} | {r["component"]} | {r["ray_distances_mm"][0][0]:.3f} + {r["ray_distances_mm"][0][1]:.3f} = {r["measured_opening_xy_mm"][0]:.3f} | {r["ray_distances_mm"][1][0]:.3f} + {r["ray_distances_mm"][1][1]:.3f} = {r["measured_opening_xy_mm"][1]:.3f} | {r["measured_height_mm"]:.3f} |')
lines += ['', '## Uložení výsledků', '', '- Aktuální GLB: `modely/`; zachované modely v2: `modely-v2/` a původní místní/veřejný náhled v2.', '- Úplný katalog: `kufriky.json` a CSV; poznámky shody v poli `review`, odkazy na fotografie v `photo_sources`.', '- Soukromé galerie a porovnání: `zdroje/doladeni-v3/`; veřejné vlastní rendery: `nahled-modely-v3/porovnani/`.', '- Zprávy skutečné geometrie: `mereni-tvar-v3/`; nezávislé výsledky a snímky prohlížeče: `overeni-tvar-v3/`.', '', '## Zbývá', '', 'Robert posoudí náhled v3. K potvrzení přesných nekótovaných detailů je potřeba měření kusu, kalibrovaný sken nebo licencovaný kótovaný CAD. Zapojení schválených modelů do živého katalogu provede vlastník. Produkční kód, služby a databáze nebyly změněné.', '', 'John.']
browser_file=ROOT/'overeni-tvar-v3/prohlizec.json'
http_file=ROOT/'overeni-tvar-v3/verejny-get.json'
if browser_file.exists():
    browser=json.loads(browser_file.read_text());lines += ['', 'Ověření prohlížeče: '+browser['status']+'; '+str(len(browser['models']))+' typů, '+str(len(browser['errors']))+' chyb, '+str(len(browser['blocked']))+' nepovolených požadavků.']
if http_file.exists():
    http=json.loads(http_file.read_text());lines += ['', 'Veřejné čtení: '+http['status']+'; '+str(len(http['rows']))+' statických souborů se shodným SHA-256.']
(ROOT/'README_doladeni_v3.md').write_text('\n'.join(lines)+'\n')
(ROOT.parent/'kufriky.md').write_text(f'Doladil jsem všech 20 typů / 21 SKU podle dalších fotografií; měření a opravy jsou v README_doladeni_v3.md.\nNáhled: {URL} — podklady a modely ve vystupy/kufriky/.\nZbývá Robertovo posouzení a doměření nekótovaných detailů, spojů a nejasných variant. — John\n')
print('Zpráva v3 a třířádkový souhrn aktualizovány.')
