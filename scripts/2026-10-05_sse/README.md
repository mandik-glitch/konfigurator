# Ergonomický stůl SSE = systém 41, čtvrtý generátor stolu (bot8, 2026-10-05)

Robert (tvar `#581 „Noha SSE“`): *„postav nový generátor, kompatibilní jako ostatní, v podstatě jde o system 40, jen nohy používá pouze tyto jeklové s vnitřním profilem 35×35 pro výškovou stavitelnost“*,
*„podélníky s pracovní deskou směrem dolů už nemají profily 40, ale nohy SSE“*, *„délku stolu určuje podélník tzn deska max 3000 mm, podélník má o 10 mm méně aby vešly záslepky“*,
*„jeklová spojnice nohy SSE může mít libovolnou délku, od 400 do 1100 mm, což určuje hloubku stolu“*, *„mezera mezi nohama v základu: 1570 mm“*. Rozsah v1 (Robertova volba): základ + spodní police + šuplíky.

## Kde co je
| Co | Soubor |
|---|---|
| jádro generátoru (bez šablony), normalizace, šuplíky, střední noha, 3D ovládání | `api/stul_sse.py` |
| konstanty `SSE_*`, `SYSTEMY[41]`, rozcestníky, pravidla po systémech | `api/stul_konfigurator.py` |
| veřejné API (schema, výběr, resolve) | `api/stul_shop_sse.py` (+ přesměrování v `api/stul_shop.py`) |
| procedurální díly nohy (jekl, plech, vnitřní profil, zaslepka), materiály, hash | `api/stul_glb.py` |
| cena nohy (pravidlo), pravidla stolu | `api/stul_api.py` |
| kóta mezery mezi nohami | `api/stul_koty.py` |
| stránka Generátor stolu 04 | `webapp/stul-konfigurator-41.html`, `webapp/js/stul-host.js` |
| karta + kategorie (neaktivní) | `zaloz_kartu_sse.py`, `zaloz_kategorii_sse.py` |

## Geometrie (osy: x hloubka, y nahoru, z šířka; vzor SSE.vzor.01 = custom_shapes #561)
Deska W × D, spodek desky T = H − 18 = horní konec jeklů = horní plocha podélníků. Podélníky Object_11 délky W − 10 v x = 46–86 a D − 86…D − 46 (pod plechy 150×40×6).
Noha: svislé jekly 40×40×675 (x = 0–40 a D − 40…D), spojnice 40×40×(D − 80) 90 mm nad spodkem jeklu, vnitřní profil 35×35×425 (+ zaslepka 3 mm) od podlahy; vnější líc nohy 175 mm od konce desky.
Spodní police 18 mm leží na spojnicích (délka W − 335, hloubka D − 100). Šuplíky: stejné uchycení jako systém 40 (vztahy ze zmrazené šablony 40). Nad prahem šířky (výchozí 2000 mm, Pravidla stolu SSE) třetí noha, desky se dělí v její ose.

## Testy (vše bez zápisu do produkce)
```
api/venv/bin/python3 scripts/2026-10-05_sse/test_sse_jadro.py                       # jádro, hash, GLB, kóty, 3D ovládání (bez DB)
scripts/2026-10-05_sse/mutace_jadro.sh                                               # 29 mutací – každá musí test shodit
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
    api/venv/bin/python3 scripts/2026-10-05_sse/test_sse_shop.py                      # veřejné API (DB jen čte)
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID41=9879 --setenv=PID40=9877 --setenv=PRAVIDLA_TEST={} --working-directory=/opt/konfigurator \
    api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-05_sse/test_sse_stranka.js 4934   # stránka v prohlížeči
```

`PRAVIDLA_TEST={}` je u testu stránky POVINNÉ: most (`_most_stul.py`) jinak čte živá Pravidla stolu z `app_settings` a test počítá s výchozími (cena nohy SSE nezadaná → upozornění v kusovníku, práh střední nohy 2000 mm). Robert 2026-10-05 zadal ceny noh (2 550 / 2 900 Kč) a práh 2 600 mm a kontroly 1l a 2a spadly; kontrola 0a teď selže hned s jasnou příčinou. Python testy (`test_sse_jadro.py`, `test_sse_shop.py`) si výchozí pravidla nastavují samy.

## Co zatím NENÍ (další kroky)
Stojky se zadními panely, LED, elektrožlab, držák PET, výřezy, ložiska; vložení do Scény (nohy SSE nejsou ve Scéně); výrobní list s oddílem nohou; ceny nohy SSE (zadá Robert v Pravidlech stolu).
