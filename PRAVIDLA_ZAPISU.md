# Pravidla zápisu pravidel

Robert, 2026-09-15 — čte se, když bot (typicky bot9) zapisuje nové
pravidlo/postup do libovolného MD registru nebo DB. **Není** povinné
čtení při startu session (viz `CLAUDE.md`) — je to referenční příručka
pro tenhle konkrétní úkon, ne obecný proces.

Navazuje na `WORKFLOW.md` pravidla 37 (jen důležité body), 39 (úkol vs.
trvalé pravidlo vs. incident), 40 (jednorázový úkol se nezapisuje
vůbec). Tenhle soubor řeší HLOUBKU/STRUKTURU zápisu, ne JESTLI/KAM
zapsat — to řeší pravidla výš.

## 1. Kam pravidlo patří (MD prosa vs. DB řádek)

| Obsah | Cíl |
|---|---|
| Strukturovaný fakt/číslo/kód/mapování, který bot dotazuje JEDNOTLIVĚ | DB tabulka (`karoserie_verze`, `regal_umisteni`, `horni_blok_varianty`, `shape_geometry_methods`, `car_body_placement_methods`...) |
| Princip/postup/zdůvodnění, který musí bot pochopit CELKOVĚ | MD prosa (registr podle domény, pravidlo 39) |

DB řádek se čte jen ten jeden, co bot potřebuje — nulový dopad na
velikost čtení ostatních. Prosa se čte jako celý blok, proto musí být
krátká (body 2-3 níž).

## 2. Šablona jednoho zápisu v MD (tři pevné sloty)

```
N. **Stručné tvrzení pravidla, jedna věta.** (Zdroj: kdo/kdy, doslovná
   citace pokud existuje.) Proč to platí - 1-2 věty, ne víc.
   [Jen pokud reálně existuje: konkrétní výjimka/hranice.]
```

Žádný čtvrtý slot bez důvodu. Žádné vyprávění cesty k rozhodnutí
(to už zakazuje pravidlo 37) - jen výsledek. Cíl: bot najde pravidlo
přes `grep -n "^N\."` a pochopí ho BEZ čtení okolních řádků.

## 3. Krátké hledání = samostatnost bloku, ne krátký soubor

`grep` je rychlý bez ohledu na velikost souboru - úzké hrdlo je AŽ
čtení kontextu KOLEM nálezu. Proto:

- Každé pravidlo musí být pochopitelné ze svého vlastního bloku (šablona
  výš), ne rozprostřené přes víc odstavců/pravidel.
- Číslování musí být souvislé a předvídatelné (`^\d+\.`) ve všech
  registrech stejně - bot nemusí hádat formát, jen zopakovat stejný
  grep vzor.
- Necpat do jednoho pravidla víc nesouvisejících tvrzení jen proto, že
  spolu souvisela v debatě - raději dvě krátká pravidla než jedno dlouhé
  se dvěma tématy.

## 4. Kdy rozdělit soubor na víc souborů

Registr se štěpí na samostatný tematický soubor (stejný vzor jako
`VLASTNOSTI_PROFILU.md` → 8 podsouborů, `VANDR_*` → 3 soubory), když
nastane KTERÉKOLI:

- Aktivní číslovaný seznam v jedné sekci přesáhne **~40-50 položek**,
- NEBO uvnitř jednoho registru vznikne jasně oddělitelný tematický
  shluk (5+ pravidel o jedné podoblasti, čitelně jiné publikum než
  zbytek souboru).

Rodičovský soubor po rozdělení nechává jen krátký ukazatel (věta +
odkaz), ne kopii obsahu - stejně jako `CLAUDE.md` dnes ukazuje na
`VLASTNOSTI_PROFILU.md` rodinu. **Sledovat** (K 2026-09-15: 40 pravidel,
k 2026-09-16 už 42): WORKFLOW.md sekce "AKTIVNÍ POKYNY" roste a má
různorodé publikum (git/BOT_ID disciplína vs. produktová/byznys
rozhodnutí) - kandidát na budoucí rozdělení, zatím neprovedeno, jen
zapsáno jako sledovaná hranice.

## 5. Role bota9: filtr komunikace bot3 ↔ ostatní

Cokoli proteče komunikací mezi bot3 (koordinace) a ostatními boty a MÁ
charakter trvalého pravidla (kategorie B/C z pravidla 39), musí bot9
sám:

1. **Pochopit** obsah nezávisle na formě, ve které dorazil (přeposlaná
   zpráva, citace, shrnutí debaty - často neformální/rozvláčné).
2. **Rozhodnout kam** (MD registr podle domény, nebo DB tabulka - bod 1
   výš).
3. **Přepsat do šablony** (bod 2 výš) - NIKDY nekopírovat přeposlaný
   text 1:1, vždy destilovat na tři sloty.
4. Teprve pak zapsat a dát vědět vlastníkovi domény (pravidlo 39 krok
   5), pokud to není vlastní soubor bota9.

Bot9 je tedy poslední krok kvality mezi "co se řeklo v debatě" a "co
zůstane napsané napořád" - odpovědnost za přesnost i stručnost zápisu
je na něm, ne na tom, kdo zprávu poslal.

## 6. Trvalý úkol: průběžně zeštíhlovat EXISTUJÍCÍ obsah

Robert (chat, 2026-09-16), doslova: *„to jsou tvoje trvalé úkoly, které
máš za úkol optimalizovat, uhladit, aby neztratily myšlenku, kontext,
ale byly rychlejší na čtení."* Body 1-5 výš řeší NOVÉ zápisy - tenhle
bod je jiný: bot9 nečeká, až mu někdo pošle nález, ale sám průběžně
prochází UŽ EXISTUJÍCÍ mandatory-read soubory (`STAV.md`, `TASKS.md`,
`WORKFLOW.md`) a hledá, co jde zkrátit/přesunout/smazat, beze ztráty
myšlenky.

Kritérium obsahu, co ZŮSTÁVÁ (Robert, doslova): *„zajímají nás v
podstatě jen používané kódy, postupy, pravidla."* Konkrétně:
- **Zůstává**: aktuální architektura/kódy v provozu, postupy (jak na
  co), pravidla (co platí napořád).
- **Jde do koše** (git historie stačí, žádný samostatný archivní
  soubor): jednorázové změny, které už proběhly (changelogy typu
  "hotovo, live"), historické snímky/checkpointy sebe sama označené
  jako historické, task-tracking duplicitní s `TASKS.md`.

Bezpečnostní záruka pro agresivní mazání: **git je už samo o sobě
plná verzovaná záloha** (`git log -p -- <soubor>`) - žádný smazaný
obsah není ztracený, jen ho běžně nikdo znovu nečte (Robert to potvrdil
přímo: „číst se budou jen poslední verze").
