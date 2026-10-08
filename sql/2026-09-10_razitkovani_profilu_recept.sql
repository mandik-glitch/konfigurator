-- Recept razitkovani profilu ochrannym 3D logem LOGIMAN.CZ.
-- Robert 2026-09-10: "uloz funkci razitkovani vcetne zmen resp tak jak je
-- nyni do DB, natrvalo".
--
-- Kod zije v scripts/razitkovac.py; tenhle zaznam je ZDROJ PRAVDY PRO CISLA
-- a pravidla (stejna konvence jako u ostatnich shape_geometry_methods -
-- markdown vysvetluje PROC, DB drzi hodnoty).

INSERT INTO shape_geometry_methods (id, name, version, definition, verified_by, created_by)
VALUES (10, 'razitkovani-profilu-ochranne-logo', 1, JSON_OBJECT(
  'popis', 'Automaticke umisteni ochranneho 3D loga LOGIMAN.CZ na profily produktove sestavy pri renderu otocneho nahledu. Razitko je dvojice dilu: vypln drazky (aby melo logo na cem sedet) a logo samotne.',
  'stav', 'Postaveno a overeno renderem na sestave 279 (Doblo K-075 C) 2026-09-10. Ceka na Robertovo potvrzeni vzhledu.',
  'kde_zije_kod', 'scripts/razitkovac.py, vola se z scripts/2026-09-09_turntable_job.py::build_job()',

  'pravidla_doslovne', JSON_ARRAY(
    'logem musi byt pokryto 10% profilu z celni / pohledove strany regalu',
    '10% znamena kazdy desaty profil ktery ma viditelnou stenu na celni strane regalu',
    'tzn kazdy desaty profil ma logo nahodne umistene nekde po jeho delce',
    'loga musi byt v ruznych mistech podelne, nahodne',
    'pri pohledu na obrazek musi byt dojem ze jsou rovnomerne rozmistena',
    'pod razitkem chceme zaroven vyplneni prostoru drazky (slotu)',
    'vypln licuje se stenou profilu, stejne jako logo',
    'vypln pod logo znamena ze nebude delsi nez logo',
    'horni hrany loga chceme srazene',
    'za srazeni hran nechci oblouk ale primku, a jeste srazit lehce vic',
    'psal jsem srazit hrany loga 1 milimetr',
    'dnes budeme razit jen profily 30x30',
    'kazdy desaty predni bude asi malo -> dejme kazdy treti',
    'ze stran tzn zboku dejme take kazdy treti, z obou stran, tzn na nohach',
    'pruhlednost vyplne drazky 50%, a logo i vypln drazky nech maji material hlinik jako profily'
  ),

  'proc_vypln', 'Profil 30x30 ma ve stredu kazde steny otevrenou sterbinu 8,2 mm sirokou a 10 mm hlubokou. Logo je 28 mm vysoke, takze lezi pres celou sirku steny a prostrednich 8,2 mm mu visi nad prazdnem - pismena se v tom pasu lamou (doloseno na renderu sestavy 134). Vypln ten prostor zaplni az do roviny steny.',

  'geometrie_zmerena', JSON_OBJECT(
    'zdroj', 'reálná .glb geometrie, ne katalogovy list',
    'profil_prurez_mm', 30.0,
    'profil_povrch_od_osy_mm', 15.0,
    'profil_delka_zakladu_glb_mm', 1000.0,
    'profil_rohy_srazene_na_mm', JSON_ARRAY(13.67, 14.335),
    'drazka_sirka_mm', 8.2,
    'drazka_hloubka_mm', 10.0,
    'drazka_dno_od_osy_mm', 5.0,
    'centralni_dutina', 'osmiuhelnik +-5 / +-4,1 mm',
    'logo_delka_mm', 223.217,
    'logo_vyska_mm', 28.0,
    'logo_relief_mm', 3.0,
    'logo_relief_puvodni_mm', 1.392,
    'logo_odsazeni_pivotu_mm', 0.696,
    'logo_srazeni_hran_mm', 1.0,
    'drazky_ostatnich_profilu_mm', JSON_OBJECT('rada_20', 6.295, 'rada_30', 8.2, 'profil_35x35', 8.2, 'profil_30x30_uzavreny', 'bez drazky')
  ),

  'parametry', JSON_OBJECT(
    'kazdy_nty_profil', 3,
    'pohledy', JSON_ARRAY('celni', 'levy bok (front+90)', 'pravy bok (front+270)'),
    'okraj_mm', 40.0,
    'min_delka_profilu_mm', 303.217,
    'max_soubeznost_s_pohledem', 0.90,
    'min_natoceni_steny', 0.30,
    'vypln_alfa', 0.5,
    'vypln_delka', 'presne delka loga, zadny presah',
    'material', 'kopiruje se z profilu, na kterem razitko sedi (vcetne TT_ALU ze sablony)',
    'razene_profily', JSON_ARRAY('Object_7', 'Object_8', 'Object_9')
  ),

  'algoritmus', JSON_ARRAY(
    '1. Pro kazdy ze tri pohledu (celni + oba boky) vyber profily 30x30 delsi nez min_delka.',
    '2. Vyrad profily, jejichz osa miri na kameru (videt jen celo) - |osa . pohled| > 0,90.',
    '3. Ze ctyr sten vyber tu s normalou nejblizsi smeru k divakovi; vyrad odvracene (< 0,30).',
    '4. Zakryte profily pryc pres median hloubky - neni to raycasting, ale odfiltruje zadni sloupky.',
    '5. Setrid deterministicky (hloubka, y, x, index) a vezmi kazdy treti, s posunem ze sha256(assembly_id).',
    '6. Pozice po delce: sha256(assembly_id, index, azimut) v ramci volnosti = delka - 2*okraj - delka_loga.',
    '7. Vloz vypln (stred 10 mm od osy = stred drazky) a logo (15,696 mm od osy = povrch + pivot).',
    '8. Baze razitka: X = podel profilu, Z = ven ze steny, Y = KRIZOVY SOUCIN (tri nezavisle osy mohou dat zrcadleni).',
    '9. Jeden profil muze dostat razitko na vic sten, ale nikdy dve na tutez.'
  ),

  'proc_deterministicke', 'Vyber i pozice se pocitaji ze sha256 z assembly_id, ne z nahodneho generatoru. Skutecna nahoda by znamenala, ze kazdy snimek otocky ma razitka jinde a sada se rozsype; take by nesly porovnat dva rendery teze sestavy.',

  'overeni_2026_09_10', JSON_OBJECT(
    'sestava', 279,
    'vypln_kolmo_od_osy_mm', 10.000,
    'logo_kolmo_od_osy_mm', 15.696,
    'vypln_scale_x', 0.2232,
    'vypln_skutecna_delka_mm', 223.2,
    'razitek_doblo_c', 7,
    'razitek_doblo_a', 8,
    'render_gpu_s', 162.2
  ),

  'pasti', JSON_ARRAY(
    'GLB exportuje mesh s ROZPOJENYMI vrcholy (logo: 12468 vrcholu / 12468 hran, kazda hrana jen s JEDNOU prilehlou ploskou). Bevel v takovem meshi tise neudela NIC - kvuli tomu vypadaly vsechny drivejsi varianty srazeni identicky. Nutne remove_doubles (-> 2094 vrcholu / 6234 hran).',
    'Srazeni 1 mm se do reliefu 1,392 mm nevejde: s clamp_overlap ho Blender orizne, bez clampu se geometrie protne (tloustka vyskoci na 3,2 mm s artefakty). Proto byl relief zesilen na 3,0 mm.',
    'Zesileni reliefu POSOUVA pivot. Geometrie je proto posunuta tak, aby strana prilehajici k profilu zustala na miste - stavajici data sestav (offset 0,696) tim sedi beze zmeny.',
    'glTF export prehazuje osy (Blender Y -> glTF -Z, Blender Z -> glTF Y). Vypln drazky se proto v Blenderu stavi s prohozenym poradim, aby v .glb vysla stejna konvence jako u loga.',
    'Material se KOPIRUJE z profilu a poloprusvitna varianta vznika kopii materialu, nikdy zmenou na miste - jinak by pruhlednost chytly i profily sdilejici tentyz TT_ALU ze sablony.'
  ),

  'mimo_rozsah', JSON_ARRAY(
    'Profily rady 20 (drazka 6,295 mm) a 35x35 (8,2 mm) - jdou stejnym vzorcem, ale dnes se nerazitkuji.',
    'profil_30x30_uzavreny drazku nema, vypln by u nej nemela co vyplnovat.',
    '3D scena (webapp/scene.html) - razitka jsou ochrana RENDERU, do sceny se nepridavaji.'
  ),

  'otevrene', JSON_ARRAY(
    'Na svislicich bezi logo svisle (po ose profilu) - Robert zatim nerekl, jestli to tak ma byt, nebo je na nohach nechtit.',
    'Na renderu 2026-09-10 razitko na leve svislici pretekalo pres konec profilu - okraj 40 mm nestaci nebo se spatne pocita volnost u kratsich profilu.',
    'Relief je pri plochem svetle malo vyrazny; jako ochranny prvek by mel byt vic videt.'
  )
), NULL, 'bot3')
ON DUPLICATE KEY UPDATE
  version = version + 1,
  definition = VALUES(definition),
  created_by = VALUES(created_by);
