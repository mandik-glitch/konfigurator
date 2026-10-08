# Stavitelné patky = šroub s maticí + černý plastový kužel (bot10, 2026-10-08)

Robert 2026-10-08: „stavitelné patky se skládají ze dvou částí: šroub s maticí a plastový kužel – dát do černé barvy, je potřeba to v 3D modelech tak upravit“.

**Řešení:** `api/stul_glb.py` (`KUZEL_PATKY`, `_kuzel_patky`, rozdělení v `poskladej_glb`): katalogové GLB patek (`product_3251` = M8 v systémech 30 / 35, `product_3283` = M10 v 40 / 45) je JEDEN svařený mesh bez materiálů
(souvislá komponenta), proto se kužel pozná geometricky – trojúhelníky s těžištěm pod rovinou horní plochy kužele (lokálně y = −50 / −48 mm; kužel 25 / 31 mm vysoký, Ø 41 / 60 mm). Kužel jde do uzlu materiálu „cerna“
(černý plast jako záslepky; žádný nový klíč materiálu → renderům nic nechybí), šroub s maticí zůstává v „ocel“. Rozsah dílu pro živé tažení = šroub, kužel = extra rozsah (`zive_rozsahy_extra`). Hash, `rules_version`,
kusovník a cena se nemění; modely bez patek jsou bajt po bajtu stejné. Katalogové GLB se nemění. Scéna (`scene.html`) dělá 3D pohledy a výkresy online nabídky z generátoru z VLASTNÍCH katalogových dílů, ne z GLB generátoru – viz „Scéna“ níže.

`test_patky_kuzel.py` (DB přes systemd-run, viz hlavička; `KUZEL_DIR=<kandidát>`, `ZAKLAD=<git revize>`, výchozí `d1f2950a^` = revize těsně před změnou): rozdělení obou katalogových patek, GEOMETRIE modelu stejná jako před změnou (multimnožina trojúhelníků všech uzlů),
kužel v „cerna“ / šroub v „ocel“, rozsahy přesně na vrcholy, výška kuželu na podlaze, kontrola zákaznického GLB, hash beze změny.
Souběžně upraveno: `scripts/2026-10-02_stul_testy/test_stul_shop.py` (extra rozsahy teď i u kuželů patek), `scripts/2026-10-06_nabidka_z_konfigurace_testy/test_nabidka_z_konfigurace.py` (Y0: karty 5 systémů vč. 45).
Odkaz na ukázku (admin): `/stul-konfigurator-40.html#wheels=false&feet=true`.

## Scéna (Robert 2026-10-08: „když udělám nabídku z generátoru, 3D scéna není ta nová ale stará“)
Model generátoru (karta, košík, online nabídka) měl černý kužel hned po nasazení API; **Scéna** ho neznala. Nález: patka M8 (`product_3251`, systémy 30 a 35) má `visible_in_scene=0`, katalog Scény (`/api/katalog`) ji nevrací
a vkládání stolu se na ní přerušilo (alert „neznámý díl product_3251 v katalogu“, ve Scéně 21 z 51 dílů – i ve výkresech nabídky).
- `webapp/js/scene/patky-kuzel.js` (nový, v `scene.html` AŽ PO `#app-script` a před `stul-konfigurator.js`): obalí sdílený `loader` – GLB patek 3251 / 3283 rozdělí geometricky (stejná rovina jako `KUZEL_PATKY`) na meshe `sroub_matice` a `plast_cerny` –, `applyPartMaterial`
  (kužel = černý plast `#242424` přes `userData.meshColors`, šroub s maticí BEZE ZMĚNY v barvě dílu) a `serializeEntryForSave` (výchozí černá kužele se neukládá do `mesh_colors`, jinak by obnova sestavy vzala šroubu katalogovou barvu dílu).
  „Obarvit díl“ obarví šroub s maticí (a uloží se jako výchozí barva katalogového dílu), kužel zůstává černý; klik na kužel ho obarví samostatně. Katalog ani DB se nemění.
- `webapp/js/scene/stul-konfigurator.js`: chybějící produkt se před vložením doplní do `CATALOG` z `GET /api/shop/products/<id>` (jen pro relaci, `visible_in_scene: false`); po vložení se kontroluje úplnost – stůl se NEVLOŽÍ napůl.
- Nezměněno: staré nabídky, uložené výkresy a už hotové rendery (z DB sestav / starých modelů) mají původní jednobarevné patky; přerenderování jen na Robertův pokyn.
- `test_patky_scena.js` (skutečná Scéna přes `scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py`, spuštění v hlavičce; `ROZDELENO=0` ověří původní stav): 5 konfigurací (systémy 30 / 35 / 40 / 45, M8 i M10), stůl celý, rozdělení patky,
  barvy, rozměry kuželu, ostatní díly nedotčené, obnova a round trip uložené sestavy, obarvování, stůl nikdy napůl (404 karty / 404 modelu). `scripts/2026-10-02_stul_testy/test_stul_panel.js` má nové T6c–T6e (atrapa katalogu `katalogPartById`).
