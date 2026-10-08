# Konfigurator

Tenhle soubor se načítá automaticky do kontextu každé Claude Code
session spuštěné v tomto adresáři - na rozdíl od souborů níže, které
si musíš přečíst sám/sama. Účel: zajistit, že se k nim vůbec dostaneš,
ne je nahradit - obsah pravidel žije v nich, tady je jen pořadí a proč.

## Než začneš pracovat, přečti si v tomhle pořadí

**Úplně první krok, ještě před čímkoli níže: zjisti, kdo jsi.** Zjisti
svůj `$BOT_ID` (env proměnná/tmux jméno session - neznáš ho automaticky,
ale nemáš ho čím jiným zjistit než tímhle) a dotaž se do DB tabulky
`bots` (`SELECT specializace FROM bots WHERE bot_id='<tvoje BOT_ID>'`,
nebo admin Přehledy → Boti) - **tenhle sloupec je JEDINÝ zdroj pravdy o
tvé náplni práce** (WORKFLOW.md pravidlo 38), ne tenhle soubor ani
žádný jiný MD. Teprve pak pokračuj čtením níže. Bez tohohle kroku
nevíš, co smíš dělat sám a co patří jinému botovi.

1. **`WORKFLOW.md`** — POVINNÉ, bez výjimky. Git/zámek/BOT_ID
   disciplína, guardované soubory (`webapp/*`, `api/app.py`) vyžadující
   `DEPLOY_LOCK.json` (`scripts/lock.sh acquire/release`), a průběžně
   doplňovaná "AKTIVNÍ POKYNY OD ROBERTA" (trvalá pravidla, co dělat
   a co ne). Vynuceno `.git/hooks/pre-commit`, ne jen dohodou.
2. **`TASKS.md`** — aktuální otevřené úkoly a jejich vlastníci (snímek
   "co ještě zbývá"). Zapiš se, než na něčem začneš pracovat.
3. **`STAV.md`** (digest aktuálního stavu, ≤150 řádků) a
   `scripts/handover.py dump` (předávky botů v DB). **Celý
   `AGENTS_LOG.md` se při startu NEČTE** (Robert 2026-09-02, tokenová
   disciplína) — do logu se jen cíleně hledá `grep -n "výraz"
   AGENTS_LOG*.md` (prohledá i archiv `AGENTS_LOG_ARCHIVE_do_*.md`)
   a čte se okno kolem nálezu. Zapisovat do logu se dál musí.
4. Pokud úkol zasahuje do 3D scény (`webapp/scene.html`, geometrie
   spojů/profilů) — navíc **`VLASTNOSTI_PROFILU.md`** (⭐ blok
   nadřazených pravidel + rozcestník na 8 tematických souborů, viz
   níže) a skill **`3d-scena-spoje`** (`.claude/skills/`,
   auto-nabízený v dostupných dovednostech) — ten obsahuje i vlastní
   krok-za-krokem onboarding pro geometrickou práci.
   Zasahuje-li úkol do 3D scén, Prohlížeče, generátorů/konfigurátorů
   produktů (stůl, mini-shopy) — navíc **`MAPA_3D_A_GENERATORU.md`**
   (jednostránková mapa pojmů: co je Scéna, Prohlížeč, Generátor,
   kde žijí a kdo je vlastní; Robert 2026-10-03 schválil odkaz).
5. Pokud úkol zasahuje do zákaznicky viditelného popisného textu
   (storefronty `car_storefronts`/`car_storefront_models`, NEBO hlavní
   kategorie `content_categories`) — navíc **`TEXT_FILTR.md`** (filtr/
   kontrolní seznam, co smí a nesmí obsahovat popisný text - vyčleněno
   z `WORKFLOW.md` bodu 21, bot20 2026-09-05, ŽIVÝ dokument).
6. Pokud úkol zasahuje do přebírání know-how z Vandr (dřívější název
   "vanDrawee" — zkráceno kvůli diktování, viz soubory samotné) Unity
   systému do Three.js konfigurátoru — navíc **tři oddělené soubory**
   (Robert: vanDrawee logika a naše vlastní logika se NESMÍ míchat v
   jednom souboru): `VANDR_SKLADANI_REGALU.md` (algoritmus skládání,
   zóny, síla profilu, čelo-dosedá-na-stěnu pravidla),
   `VANDR_RENDER_HOWTO.md` (postup krok za krokem, jak vzít FBX z Vandr
   zdrojáků a vyrenderovat/ověřit sestavu — ⭐ bloky s povinnými
   pravidly), a `VANDR_DILY_ZNACENI.md` (vizuální konvence zdrojových
   modelů — červené plošky = dorazy, drobné díly bez geometrie).

7. Pokud úkol zasahuje do produktových renderů pro e-shop (sférický/
   otočný náhled sestav, `api/turntable.py`, rendery přes Blender na
   vzdálené GPU, ochranné logo v geometrii) — navíc
   **`PRODUKTOVE_RENDERY.md`** (kontrakt otočného náhledu, šablona
   `.blend`, materiály, pasti; bot8 2026-09-09, ŽIVÝ dokument).

8. **`PLAN_TVORBY_SESTAV.md`** — výrobní linka od receptu po hotovou
   prodejní položku v e-shopu (recept → scéna → schválení → skladová
   karta → rendery → web). **Nečte se při startu.** Robert 2026-09-11:
   *„každý bot čeká na práci od bota3 a nahlíží do plánu jen když si není
   jistý"* — je to záchranná síť pro chvíli, kdy nevíš, jak tvůj kus
   navazuje na celek, ne fronta úkolů. **Zapisuje do něj jedině bot3**;
   nálezy a hotové kroky mu posílej zprávou. Renderovací dávku smí
   zadat jedině bot4 (správce GPU a renderů, pravidlo 31 — PŘEKONÁNO
   2026-09-12, dřív bot3).
9. Pokud úkol je ZÁPIS nového pravidla/postupu do MD registru nebo DB
   (typicky bot9) — navíc **`PRAVIDLA_ZAPISU.md`** (šablona zápisu, kdy
   MD vs. DB, kdy rozdělit soubor). **Nečte se při startu**, jen při
   tomhle konkrétním úkonu.

## Co je Konfigurator (stručně)

3D konfigurátor hliníkových profilových konstrukcí (Logiman) +
e-shop nad stejnou DB/API. Zákazník skládá konstrukci ve webové 3D
scéně (`webapp/scene.html`, Three.js) z profilů a příslušenství
(spojky, úhelníky, kolečka, klouby...), appka hlídá geometrickou
platnost spojů (žádné zanoření, žádné neúplně kryté čelo) a spočítá
cenu. Backend: `api/app.py` (Flask) + MySQL. Provoz na jedné VPS
sdílené s dalšími, samostatnými projekty (viz `PRISTUPY.md` pro
přístupové údaje).

## Souběžná práce více botů

Robert obvykle pouští víc Claude Code session zároveň (`bot2`, `bot8`,
...), každá pod vlastním `BOT_ID`. Rozdělení rolí (kdo dělá scénu,
kdo frontend, kdo SEO...) se v čase mění - aktuální přiřazení hledej
v posledních zápisech `AGENTS_LOG.md`/`TASKS.md`, netvař se, že je
pevné podle staršího záznamu.
