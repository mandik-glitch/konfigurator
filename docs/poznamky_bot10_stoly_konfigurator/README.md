# Poznámky bot10: průzkum konfigurátoru stolů (2026-10-02) - NENÍ produkce

**Stav:** jen poznámky a prototypy z průzkumu. Nic z toho není napojené na `api/*.py` ani nasazené. Konfigurátor stolu #577
staví **bot8** (rozhodnutí Roberta 2026-10-02: „bot10 s tím nemá co do činění, tohle je prvotní konfigurátor“); bot10 na něm nepracuje.
Složka je tu proto, aby se nevymýšlelo dvakrát to, co se už zkusilo. Vše čte DB jen přes SELECT (`db.py`, session READ ONLY).

## Co prototypy dělají (podrobnosti jsou v hlavičkách souborů)
- `prototyp_compose_glb.py` - server složí GLB z uložené sestavy (`custom_shapes.data` nebo `product_assemblies.data`) čistě v Pythonu (numpy):
  `part_id` -> katalogový GLB, TRS jako scéna, normály přes inv(M3), slepení podle materiálu, uzly jen `{g}` (číslo slotu), bez jmen. Závisí na `v3d_glb.py`
  (kopie sanitizeru/čtečky GLB; v repu zatím není, `api/v3d_glb.py` neexistuje).
- `prototyp_parametric_morph.py` - parametrická změna rozměru „rovinným rozkladem“: rovina na ose, díly pod ní stojí, díly nad ní se posunou o delta,
  natažitelné díly (profil podélně, deska) přes rovinu se natáhnou; komponenty se řadí podle středu nebo podle přepisu (`anchors`).
  Ověřuje na #577: stejné dvojice spojů, délky profilů +delta, žádný nový průnik profil-profil.
- `varianty_demo.py` - volby -> placement -> `compose_entries()` -> export GLB -> kontrola (včetně času).
- `batch_joints.py`, `batch_node_vs_py.py`, `analyze_pairs.py` - srovnání počtu spojů/dvojic skládání v Pythonu proti referenčnímu výpočtu ve scéně (`node_ref.js`).
- `survey_katalog.py`, `survey_profiles.py`, `inspect_glb.py`, `glbnp.py` - průzkum katalogových GLB (rozměry, osy, počet meshů).
- `shape_572.json`, `shape_577.json` - výpis dat obou tvarů (stůl systém 30) z DB k 2026-10-02.
- `viewer_smoke.js`, `run_all.sh` - hrubý kouřový test (offline Playwright); `run_all.sh` předpokládá pracovní složku z session, upravit cesty.

## Co neplatí / není ověřeno
- Žádný ze skriptů neprošel schválením ani nasazením. Rozsah rozměrů, pravidla přidávání nohou a LED panelů určuje Robert přes bot8 (TASKS.md).
- Kanonický hash výběru voleb a cenová funkce jsou návrh domluvený s bot5/bot16, v těchto souborech nejsou.
- Nález: `product_4930.glb` (dvojitý ocelový šuplík) má šuplík vysunutý; pro konfigurátor je potřeba zavřená poloha (předáno bot3 -> bot8).
