# RAM watchdog (VPS-wide)

> OPRAVENO bot9 2026-09-13: název "VerticalStocks" a IP `80.211.210.103`
> patřily starému serveru před přestěhováním (viz `PRISTUPY.md`,
> aktuální IP `75.119.132.164`). Podle `scripts/qa/health.py`
> (`_check_ram_watchdog`) `ram-watchdog.service` na dnešním stroji vůbec
> není nasazený - obsah dokumentu níž popisuje záměr/postup, ne aktuální
> stav.

Zapsáno 2026-08-18 (bot3), po pádu celé flotily botů na přesaženou RAM
během paralelního hloubkového průzkumu (houbový/řemeslnický research -
víc botů spustilo náročnou práci naráz). Robert: bot3 sice `free -m`
hlídal, ale jen jednorázově před zadáním úkolu - to nezachytí "rychlý
náběh práce" (RAM vyskočí během pár desítek sekund POTÉ, co se
oslovení boti rozjedou souběžně, další kontrola bota3 přijde až při
jeho příštím tool-callu).

## Co je nasazené

**Zdroj je od 2026-09-02 v repu (bot16):** `deploy/ram-watchdog.sh`,
`deploy/ram-watchdog.service`, `deploy/ram-watchdog.logrotate`,
`deploy/ram-watchdog-selftest.sh` (instalační kroky v hlavičce
skriptu; po změně skriptu `install` + `systemctl restart ram-watchdog`).
Verze z 2026-08-18 žila jen mimo repo a 2026-09-02 už na serveru
NEBYLA (`/usr/local/sbin/ram-watchdog.sh` ani unit neexistovaly) -
proto znovu nasazeno z repa, `systemctl enable --now` 2026-09-02 23:12.

Test bez dotyku živých procesů: `bash deploy/ram-watchdog-selftest.sh`
(dry-run se simulovanou pamětí `RAM_WATCHDOG_FAKE_MEM_FILE`, swap
"0 0", STOP/CONT jen na vlastní kopii `sleep`, reálná eskalace jen do
vlastní dočasné tmux session). Ruční simulace:
`RAM_WATCHDOG_DRY_RUN=1 RAM_WATCHDOG_FAKE_MEM="400 0 0" LOG_FILE=/tmp/x
STATE_DIR=/tmp/xs ALERT_FILE=/tmp/xa ram-watchdog.sh --once`.
Prahy/koordinátora lze přepsat v `/etc/default/ram-watchdog`
(`COORDINATOR_TMUX_SESSION=...`), pak `systemctl restart ram-watchdog`.

`/usr/local/sbin/ram-watchdog.sh` + `ram-watchdog.service` (systemd,
`enabled`, běží nezávisle na jakékoli Claude session; unit bez
`PrivateTmp`, jinak by neviděl tmux socket `/tmp/tmux-0`) - kontroluje
`/proc/meminfo` (= `free -m`) každých 10 s:

- **SOFT alert** (dostupná RAM < 1500 MB): zapíše `/run/ram-watchdog-
  alert` s časovou značkou. Boti/bot3 by si ho měli číst PŘED
  zadáním další náročné paralelní práce, místo ručního `free -m`.
- **HARD alert** (dostupná RAM < 500 MB NEBO swap využitý ≥ 90 %):
  navíc pozastaví (`SIGSTOP`, ne kill - jde vrátit) procesy z
  bezpečného seznamu - **výhradně přesným jménem/cestou binárky**
  (`yt-dlp`, `ffmpeg`, playwright Chromium pod `/ms-playwright/`),
  NIKDY volným textovým vzorem přes celou příkazovou řádku (to by
  omylem chytlo i bash příkaz, který slovo jen zmiňuje, např. `grep
  ffmpeg soubor.md` - ověřeno/opraveno při testování 2026-08-18).
  Až RAM klesne zpátky pod SOFT práh, pozastavené procesy se
  probudí (`SIGCONT`) automaticky.

- **ESCALATE** (HARD trvá ≥30 s i po pozastavení bezpečného seznamu):
  pošle zprávu přímo do tmux session koordinátora (`tmux send-keys`),
  proměnná `COORDINATOR_TMUX_SESSION` (výchozí `bot3`, cíl `=bot3:` =
  přesná shoda jména, ne prefix). Opakuje se každých 600 s, dokud
  HARD trvá. Když session neexistuje: řádek `ESCALATE SELHAL` v logu +
  `logger -p user.crit` (journal) + soubor
  `/run/ram-watchdog-escalate-failed` - NE potichu (viz incident níž).

**Incident 2026-08-23**: `COORDINATOR_TMUX_SESSION` mělo výchozí
hodnotu `bot12` (zbytek z dřívějšího přiřazení rolí) - HARD alert běžel
nepřetržitě od 03:32 do 21:03 (skoro 18h), ESCALATE selhal potichu
(`tmux session 'bot12' neexistuje, nemam koho upozornit`), nikdo
včetně bota3 se to nedozvěděl. Opraveno na `bot3` (pevná role od
2026-08-21, viz bot_roles.md) + service restartován. Poučení: při
změně role/jména koordinátora zkontrolovat i tenhle skript, ne jen
projektovou dokumentaci.

Log: `/var/log/ram-watchdog.log` (logrotate `/etc/logrotate.d/
ram-watchdog`, týdně, 4 kopie).

**Záměrně se NEDOTÝKÁ** žádných živých služeb (gunicorn/nginx/mysql/
redis/sshd/systemd) ani samotného `claude` procesu bota - pozastavení
vlastního `claude` procesu by jen zamrzlo celou session bota, ne
smysluplně uvolnilo RAM.

Otestováno živě 2026-08-18: reálný `ffmpeg` proces pozastaven při
vynuceném HARD prahu a automaticky probuzen po návratu k normálu -
plný cyklus STOP→CONT ověřen v logu.

## Rozpočet RAM podle služby (strop pro VPS)

- `konfigurator-remeslo-voice-worker.service` (lokální faster-whisper,
  **od 2026-08-21 model "large-v3"** místo "medium", CPU/int8) -
  **1,75 GB** ustálený stav po startu, reálně naměřeno `ps` (RSS
  1 836 796 KB) pár desítek sekund po úspěšném nastartování v
  produkci (bot3, 2026-08-21) - shoduje se s dřívějším izolovaným
  měřením bot14 (~1,75 GB, 2026-08-21). Nahrazuje dřívější hodnotu
  pro "medium" (1,6 GB, bot13 2026-08-19) - **RAM strop pro VPS tím
  posunut na 12,45 GB** (12,6 GB − 0,15 GB rozdíl mezi medium a
  large-v3).

  **Nedořešené (přesně stejná otevřená otázka jako dřív u medium)**:
  medium měl zdokumentovaný leak (rostl z ~1,5 GB na 3,1 GB během
  provozu, viz `konfigurator-remeslo-voice-worker.service` komentář
  v unit souboru) - jestli large-v3 leakuje podobně/víc, zatím NENÍ
  ověřeno, jen jednorázové měření hned po startu. `MemoryMax` v unit
  souboru byl kvůli přechodu zvýšen z 2200M na **3500M** (2200M
  nestačilo ani na samotné načtení - živě zachycen OOM-kill v `dmesg`
  s anon-rss ~2,24 GB PŘED dokončením loadu). Pokud se ukáže reálný
  leak podobný medium, přepočítat znovu podle skutečného ustáleného
  maxima, ne podle 3500M stropu (ten je jen bezpečnostní pojistka
  proti neomezenému růstu, ne rozpočet).

## Co NENÍ hotové (odloženo, Robert 2026-08-18: "dvojku dáme až spadnem")

**Tvrdý strop RAM per bot** (`systemd-run --scope -p MemoryMax=...`
při zakládání nové tmux/`claude` relace) - kernel by pak zastavil jen
přetíženého bota, ne celý server. Zatím se nezakládá, řeší se až po
dalším reálném incidentu.

## Pro boty: jak s tím pracovat

Před spuštěním náročné paralelní práce (víc botů najednou spouští
yt-dlp/ffmpeg/playwright/hloubkový research) zkontroluj `/run/
ram-watchdog-alert` (`cat` - pokud existuje, RAM je už napjatá, počkej
nebo omez rozsah). Kontrola `free -m` před zadáním úkolu (viz i
paměť `feedback_bot_ram_rules.md`) zůstává v platnosti jako první
rychlá kontrola - watchdog je DOPLNĚK, ne náhrada.
