# Deska pokračuje dozadu bez zadních stojek (bot10, 2026-10-08)

Robert 2026-10-08: „stoly generator, když se odejmou zadní stojky (zkrátí), deska musí pokračovat dozadu překrýt svislé profily“.

**Řešení:** `api/stul_konfigurator.py` `deska_zadni_pokracovani(sd, stojky)`: bez zadních stojek je pracovní deska o tloušťku profilu (`profil_mm`: 30 / 35 / 40 / 40) delší a její zadní hrana leží v rovině zadního líce zadních noh
(přední hrana, výška a šířka beze změny); se stojkami a u SSE (41) vše beze změny. Použito v jádru (rozměr a poloha desky, `celek` pro cenu), v normalizaci výřezů (`hloubka_desky`) a v mezích posuvníků výřezů v obchodě (`api/stul_shop.py`).
Záslepky na horních koncích zadních noh zmizí samy (konec už není volný). `api/stul_glb.py` `kanonicky_hash`: stoly BEZ stojek nesou značku `_deska_zad` (nový hash a kód jen u nich; `RULES_VERSION` se nemění, hashe stolů se stojkami beze změny).
Souvislosti: ložiskové jednotky na desce se rozmístí podle nového obrysu; výřez zadaný až k zadní hraně sedí u nové zadní hrany (police pod ním s ním). Dokumentace: `docs/KONTRAKT_KONFIGURATOR_UI.md` (sekce Deska pokračuje dozadu), `MAPA_3D_A_GENERATORU.md`.

**Test** `test_deska_pres_nohy.py` (DB pro cenu přes `systemd-run`, viz hlavička; `N` výběrů na systém, `SEED`, kandidát `DESKA_DIR=<kořen překryvu s api/>`, základ `ZAKLAD=<git revize>`, výchozí `d7dde610^` = revize těsně před změnou (HEAD ji už obsahuje)): dva samostatné procesy (kandidát a `git show` základ)
počítají TYTÉŽ výběry (30 / 35 / 40 / 45, šířka vč. střední nohy a dělení desky, hloubka vč. > 900 a 2500, výška, přesah, kolečka / patky / návlek, šuplíky, police, držák PET na všech nohách a stranách, výřezy, ložiska) ve trojici A = bez stojek /
B = se stojkami bez příslušenství / C = se stojkami s příslušenstvím. Hlídá: se stojkami VŠE shodné (díly, cena, kusovník, problémy, rozměry); bez stojek vše mimo desku, záslepky a ložiska shodné, zmizely jen záslepky horních konců zadních noh (počet = počet zadních noh),
přední hrana / výška / šířka desky stejné, zadní hrana v rovině zadního líce zadních noh (nezávisle z AABB), plocha o tloušťku × šířku větší, kusy se nepřekrývají, žádné nové problémy, cena nikdy nižší, ložiska uvnitř desky; meze posuvníků výřezů o tloušťku větší; SSE beze změny;
`RULES_VERSION` beze změny, hash se stojkami stejný a bez stojek jiný; GLB projde kontrolou zákaznického modelu.
Souběžně upraveno: `scripts/2026-10-02_stul_testy/test_stul_koty.py` (očekávaná hloubka desky u stolů bez stojek o tloušťku profilu větší).
