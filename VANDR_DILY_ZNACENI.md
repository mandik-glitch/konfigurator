# Vandr — značení modelů a drobné díly (odděleně od naší vlastní logiky)

**Robert, 2026-09-06: oddělit od naší vlastní logiky, nemíchat v jednom
souboru.** Tenhle soubor drží POZOROVÁNÍ o zdrojových modelech a
katalogu Vandr (Unity/Laravel) — jiný soubor než
`VANDR_SKLADANI_REGALU.md` (tam je algoritmus skládání) a jiný než
naše vlastní `PRISLUSENSTVI_PRIPOJENI.md`/`PRAVIDLA_SPOJU.md`.

## Vizuální konvence ve zdrojových modelech

- **Červené plošky na komponentách** = dorazové/kontaktní body
  (Robert, 2026-09-06: "červené plošky komponent ber jako dorazové
  body, nesmí se zanořit, jen dotknout"). Při importu/skládání
  komponenty podle Vandr předlohy je to nápověda, KTERÁ plocha má
  být tou přesně dosedající (na nohu/stěnu/sousední díl) — ne teprve
  odhadovat z tvaru. Je to konvence ZDROJOVÉHO systému, naše appka
  žádné takové barevné značení nemá zavedené.
  - **ZÁVAZNÉ (Robert 2026-09-07, po reálné chybě): tohle NENÍ jen
    vizuální nápověda, je to TVRDÝ geometrický dorazový limit** —
    "červené plošky, které se nemůžou překročit, slouží jako dorazy".
    Skutečná chyba: při stohování 2 šuplíků na sebe (Movano bottom
    zóna) jsem druhý šuplík umístil s libovolnou rezervou (+60mm nad
    celým bboxem prvního) — díky tomu se HORNÍ šuplík zabořil do
    DOLNÍHO, protože jsem dorazy vůbec nekontroloval.
  - **Jak na to programově:** dorazy jsou meshe s `parent.name ===
    'red'` — TOHLE je nezávislé na `colorize()` (ta mění jen
    `n.material`, ne hierarchii rodičů), takže se dá číst kdykoli,
    není nutné to zjišťovat před přebarvením. Najdi jejich Y-rozsah
    (`redStopsYRange()` v `render_movano_assembly.html`) a při stohování
    komponenty NA JINOU KOMPONENTU (ne na nohu — tam platí zvlášť
    zdokumentovaný `endBracketOf()`/podlaha z `VANDR_SKLADANI_REGALU.md`)
    zarovnej spodní doraz horního dílu PŘESNĚ na horní doraz dolního
    dílu (mezera = 0, žádná rezerva) — stejný princip "čelo dosedá,
    nezanoří", jen jiný zdroj reference (nativní barva modelu, ne
    počítaná geometrie profilu).

## Drobné díly — co má a nemá geometrii

- **Šrouby, T-matice, závrtné matice nejsou v 3D modelu vůbec
  přítomny** (ověřeno na reálném FBX nohy `Noha.1.Jumpy.H1.1180.459.
  vyrez.fbx`, 2026-09-06) — počítají se jen do ceny/kusovníku, nikdy
  se nevykreslují. Nepotřebují GLB ani žádnou geometrii.
- Viditelné drobné díly (záslepky, patky/CUB10 destičky, madla, zámky)
  jsou v FBX jako samostatné pojmenované meshe vedle profilových
  segmentů — potřebují vlastní GLB.
