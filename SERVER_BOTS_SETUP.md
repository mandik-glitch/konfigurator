# Claude Code přímo na serveru

Zapsáno 2026-07-26 (bot2), na žádost Roberta - cíl: obejít pomalé
připojení, boti pracují lokálně na serveru místo přes SSH-relay z
jiného stroje.

> OPRAVENO bot9 2026-09-13: server "VerticalStocks" na staré IP
> `80.211.210.103` z doby zápisu tohohle souboru už neplatí - server se
> přestěhoval (viz `PRISTUPY.md`), aktuální IP je `75.119.132.164`.
> Příkazy níž opraveny na aktuální IP, ale konkrétní seznam tmux relací
> (bot5/6/7/8) je z 2026-07-26 a neodpovídá dnešní flotile.

## Co je hotové

- Node.js 24 (LTS) + npm nainstalováno (`node -v` / `npm -v`).
- Claude Code CLI nainstalováno globálně (`claude --version` -> 2.1.220).
- Přihlášení přes Robertovo Claude Max předplatné - **plnohodnotný
  `/login`** (ne `claude setup-token`, viz níže proč), uloženo v
  `~/.claude/.credentials.json` pro roota. Platí pro všechny `claude`
  relace spuštěné jako root na tomhle serveru.
- **Remote Control aktivní** - `bot5` a `bot6` běží každý ve své `tmux`
  relaci s `claude --remote-control <jméno>`, dostupné z
  [claude.ai/code](https://claude.ai/code) i z mobilní appky Claude
  (iOS/Android). Robert tak může z PC (prohlížeč, žádné SSH potřeba) i
  z mobilu sledovat průběh, schvalovat/odmítat nástrojové akce a psát
  instrukce - přesně jako by seděl v terminálu.

**Proč `/login`, ne `claude setup-token`:** Remote Control vyžaduje
plnohodnotný přihlašovací token. Token z `claude setup-token` (nebo
proměnná `CLAUDE_CODE_OAUTH_TOKEN`) je omezen jen na dotazy modelu
("inference-only") a Remote Control s ním NEJDE spustit - ověřeno chybou
`Remote Control requires a full-scope login token`. Proto byl
`/etc/profile.d/claude_code_token.sh` (starší přístup) smazán a nahrazen
plným loginem.

**Důležité:** všichni boti (Cowork i serveroví) sdílí JEDNO Robertovo
předplatné - takže 5hodinové/týdenní limity Claude Code se počítají
dohromady za všechny souběžně běžící boty, ne zvlášť pro každého. Pokud
narazíte na rate limit dřív, než byste čekali, tohle je důvod.

## Kolik botů zatím (2026-07-28, Robertovo rozhodnutí)

Původně (2026-07-26) jen 2 boty na serveru, s tím že rozšíření vyřeší
Robert později. 2026-07-27 rozšířeno na 3 ("založ mi nového bota") -
`bot7` přidán stejným postupem jako `bot5`/`bot6` níže. **2026-07-28
rozšířeno na 4** ("udelej mi bot8") - `bot8` přidán stejným postupem.
Další rozšíření opět na Robertovo rozhodnutí (sdílený limit
předplatného, viz výše).

## AKTUALIZACE 2026-08-05: `bot2`-`bot4` uvolněny, teď taky serveroví boti (`bot1` ZŮSTÁVÁ vyhrazený)

Z původních Cowork botů (běželi mimo server přes SSH-relay z Robertova
PC) byli smazáni `bot2`, `bot3`, `bot4`. **`bot1` STÁLE BĚŽÍ na
Robertově PC** (Robert 2026-08-05: "Bot1 je ještě u mě na PC, tak bot1
vynech") - jeho jméno zůstává REZERVOVANÉ, přesně jako předtím byla
`bot1`-`bot4` dohromady. Nepoužívat `bot1` pro nový serverový bot.

Jména `bot2`-`bot4` NEKOLIDUJÍ se žádným jiným aktivním agentem a
Robert je chce použít pro DALŠÍ serverové boty (stejný postup jako
`bot5`-`bot8` níže - "práce bude dost"). **Aktuálně tedy může běžet až
7 serverových botů: `bot2`-`bot8`** (`bot1` zůstává mimo, viz výše).

Založení `bot3`+`bot4` (tmux + `claude --remote-control`) OPRAVA
2026-08-05 (bot6): předchozí verze týhle poznámky tvrdila, že tohle
musí vždy dělat přímo Robert ("autonomní spouštění nových přihlášených
claude relací je bezpečnostně blokovaná akce") - neplatí to tak plošně.
Robert se zeptal "jak ho mam zalozit stejne jako tebe (na VPS)?" a
bot6 relace `tmux new-session`+`claude --remote-control` pro `bot3`+
`bot4` bez problému spustil PŘÍMO ZE SVÉHO Bash nastroje (žádná
blokace) - protože `~/.claude/.credentials.json` uz obsahuje platny
plnohodnotny login (viz vyse), zadny NOVY prihlasovaci flow se tedy
vubec nespoustel, jen se znovupouzila uz existujici autorizace. Tohle
je bezpecne delat i pro bota (nejde o zalozeni noveho uctu/prihlaseni,
jen o novou tmux relaci se stejnymi pristupovymi udaji) - Robert to
tedy NEMUSI zakladat rucne, staci pozadat existujiciho bota.

**Historická poznámka (proč byl tenhle zápis původně jinak):** Než byli
staří Cowork boti smazáni, jména `bot1`-`bot4` byla REZERVOVANÁ a
serveroví boti záměrně používali jen `bot5`+ (viz vysvětlení kolize
níže - stále platí jako obecný princip, kdyby se v budoucnu znovu
objevili jiní souběžní agenti se stejnými jmény). Otestováno smoke
testem 2026-07-26 (`git log`, commity `bot5 acquire`/`bot5 release`) -
cizí bot (`bot6`) se pokusil sáhnout na hlídaný soubor bez zámku a hook
ho správně zablokoval - to platí úplně stejně pro `bot2`-`bot4` teď.

## Jak se připojit a pracovat (3 způsoby, dají se kombinovat)

### 1. Z mobilu / odkudkoliv - přes claude.ai/code nebo appku Claude

Všechny relace už běží a jsou dostupné bez SSH. **Role platné od
2026-08-10** (Robert) uvedeny u každého bota - viz i tabulka v
`WORKFLOW.md`/`TASKS.md`:

- **bot2 (Koordinace):** URL viz seznam relací na
  [claude.ai/code](https://claude.ai/code) pod jménem `bot2` (`bot1`
  ZŮSTÁVÁ na Robertově PC, nepoužívat pro server).
- **bot3 (SEO):** https://claude.ai/code/session_018684X18ZgfzgywcGa5hduF
  (znovuzalozeno 2026-08-10 botem1 na zadost Roberta - po restartu VPS
  spadl CELY tmux server, vsechny bot relace vc. bot3 byly mrtve;
  bot5-bot8 zatim NEobnoveny, stare URL nize/vyse neplati)
- **bot4 (bez role):** https://claude.ai/code/session_01LGJbQYKga77Jrfgzg2AwxJ
- **bot5 (Frontend e-shop):** https://claude.ai/code/session_01CWMaSj7Z6cDw4xCx8qHULK
  (znovuzaloženo 2026-08-08 botem7, tmux relace `bot5` na VPS byla
  mezitím ukončená - stará URL výše přestala fungovat)
- **bot6 (Scéna - 3D konfigurátor):** https://claude.ai/code/session_01B1K9cR6GgTpL9CSiKo4goM
  (znovuzaloženo 2026-08-08 botem7, tmux relace `bot6` na VPS byla
  mezitím ukončená - stará URL výše přestala fungovat)
- **bot7 (Nabídky):** https://claude.ai/code/session_01JL6TzaERC1eNH79auAtEyX
- **bot8 (Backend):** https://claude.ai/code/session_01CRwdsQKBes4wuo6xkEQgXU
  (bot5-bot8 znovuzalozeny 2026-08-10 botem1 na zadost Roberta po restartu VPS - vsechny relace bezi, stare URL neplatily)

Nebo otevři [claude.ai/code](https://claude.ai/code) (v prohlížeči na
PC) nebo appku Claude na mobilu (záložka "Code") a najdi relaci podle
jména `bot2`-`bot8` v seznamu. Odsud jde psát instrukce,
sledovat průběh živě a schvalovat/odmítat nástrojové akce - přesně jako
v terminálu. URL se po restartu relace může změnit, hledání podle jména
je spolehlivější.

Pro push notifikace na mobil (upozornění, když bot něco dokončí nebo
potřebuje rozhodnutí): v appce Claude přihlásit stejným účtem, povolit
notifikace, a v terminálové relaci spustit `/config` -> zapnout
**Push when actions required** (a/nebo **Push when Claude decides**).

### 2. Přes SSH + tmux (jako doteď)

```
ssh root@75.119.132.164
# bezheslový přístup (SSH klíč), viz PRISTUPY.md
tmux attach -t bot5     # nebo bot6/bot7/bot8 - všechny 4 relace uz bezi
```

Nová relace (kdyby bylo potřeba restartovat):

```
tmux new -s bot8
export BOT_ID=bot8      # nebo bot5/bot6/bot7 - MUSÍ sedět s názvem relace, NASTAVIT PŘED "claude"
cd /opt/konfigurator
claude --remote-control bot8    # --remote-control = dostupné i z mobilu/prohlížeče
```

Odpojení bez ukončení: `Ctrl+b` pak `d`.

### 3. Kombinovaně

Díky Remote Control lze psát z terminálu (SSH) i z mobilu/prohlížeče do
STEJNÉ relace - synchronizuje se to napříč zařízeními automaticky.

**Důležité pro `BOT_ID`:** musí být nastavený v prostředí PŘED spuštěním
`claude` (dědí se do bash nástroje, který Claude Code používá pro
`git commit`). Když se spouští nová relace, `export BOT_ID=botX` musí
být první příkaz.

## Co dělat po přihlášení

Přečti `TASKS.md` (aktuální otevřené úkoly) a `AGENTS_LOG.md` (historie -
stačí posledních pár desítek řádků pro kontext). `TASKS.md` funguje jako
sdílený task board - vezmi si úkol, zapiš se do sloupce "Vlastník",
commitni, po dokončení přesuň do sekce Hotovo a zapiš záznam do
`AGENTS_LOG.md`. Podrobnosti viz hlavička `TASKS.md`.

## Zámková konvence

`DEPLOY_LOCK.json` + `AGENTS_LOG.md` + git hooky (`pre-commit`,
`commit-msg`) fungují úplně stejně jako doteď - je to konvence
repozitáře, ne vlastnost žádného konkrétního nástroje/klienta. Platí i
tady:

**Krok 1-2 (acquire) dělej přes `scripts/lock.sh`, ne ručně** (bot3,
2026-08-06, po reálné race-kolizi mezi bot3 a bot4 - ruční "přečti
`DEPLOY_LOCK.json`, je-li volno, zapiš" NENÍ atomické, viz WORKFLOW.md
sekce "scripts/lock.sh"):

1. Před úpravou `api/*.py` nebo `webapp/*`:
   `scripts/lock.sh acquire botX "<co chystáš>"` (nebo s `--wait`/
   `--wait=SEKUNDY`, pokud zámek zrovna drží někdo jiný - čeká místo
   vlastní psané smyčky a acquirne hned, jak se uvolní). Selže hned a
   jasně, pokud zámek už drží jiný bot.
2. Proveď a otestuj změnu, commitni ji (`BOT_ID=botX git commit ...`).
3. Uvolni zámek: `scripts/lock.sh release botX`.
4. Zapiš záznam do `AGENTS_LOG.md` (co, proč, jak otestováno).

`scripts/lock.sh require botX` (exit 1 beze změny, pokud zámek zrovna
nedrží `botX`) je vhodná pojistka před čímkoli citlivým (deploy,
restart), ne jen před samotným commitem. `scripts/lock.sh status`
vypíše aktuální stav bez vedlejších účinků.

Ruční postup (Read/Write `DEPLOY_LOCK.json` přímo) dál funguje - hook
ověřuje jen výsledný commitnutý obsah - ale `scripts/lock.sh` je od
2026-08-06 preferovaný způsob.

## Jeden rozdíl oproti SSH-relay přístupu - DŮLEŽITÉ

Dosud každý bot (běžící mimo server) upravoval soubory v IZOLOVANÉ kopii
a do `/opt/konfigurator` (což je zároveň živě servírovaná appka -
gunicorn/nginx čtou přímo odsud) nahrával až hotovou, otestovanou verzi.

Bota běžícího přímo na serveru bude lákat editovat soubory rovnou v
`/opt/konfigurator` - ale to znamená, že rozpracovaná/neotestovaná verze
souboru může být chvíli živě servírovaná návštěvníkům, ještě než dojde
k commitu. **Doporučení: i na serveru si drž vlastní scratch kopii**
(např. `/root/scratch-bot5/`), tam uprav a otestuj (syntax check,
případně lokální test), a do `/opt/konfigurator` zkopíruj až finální
verzi - ve chvíli, kdy už držíš zámek. Přesně stejný princip jako doteď,
jen bez SFTP/SSH roundtripu navíc.

Pro `.py` soubory (změna `app.py` a modulů) platí nasazení podle
`WORKFLOW.md` pravidla 57: automaticky 2× denně, bot službu nerestartuje;
ověřuje se změněný endpoint, ne `/api/health`.
