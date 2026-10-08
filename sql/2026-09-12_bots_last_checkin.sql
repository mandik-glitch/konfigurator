-- bot3 2026-09-12
-- Robert (chat): "kdyz bot zamrzne, zmizi, nereaguje nebo je neaktivni at
-- se stav zobrazuje v tabulce" + "viditelny log kdy se naposled divail
-- na svoje ukoly na zdi".
--
-- www-data (gunicorn) NEMA pristup k root tmux socketum (overeno:
-- /tmp/tmux-0/default je 0660 root:root, www-data neni v groupe) - takze
-- primy dotaz "bezi ten bot v tmuxu?" ze serveru neni technicky mozny.
-- Misto toho: SAMOHLASENY "tep" presne stejny vzor jako uz existujici
-- render_worker_agent.py heartbeat (api/render_worker.py, worker_tepe/
-- worker_zaseknuty) - bot si sam zavola GET /api/bots/checkin (vidi
-- pritom svoje nesplnene ukoly na zdi, takze "checkin" A "podival se na
-- zed" je JEDNA a ta sama akce, ne dva mechanismy). Bot, ktery fakt
-- zamrzne/zmizi, prosty prestane volat - po prekroceni prahu (viz
-- _bot_stav() v api/bots.py) tabulka ukaze "neaktivni", presne to
-- zadane chovani, bez potreby cist skutecny OS proces.
ALTER TABLE bots ADD COLUMN last_checkin_at DATETIME NULL AFTER pipeline_uzly;

-- Robert (chat, tesne pote): "abych se te nemusel porad ptat co kdo
-- dela... abych videl stav ze neco kazdy bot dela a strucne co dela" -
-- last_checkin_at samotny rika jen "bot zije", ne CO prave dela. Kratky
-- volny text, prepisuje se pri kazdem checkinu (--cinnost parametr),
-- zadna historie (na to slouzi AGENTS_LOG.md/bot_ukoly, tohle je jen
-- "prave ted").
ALTER TABLE bots ADD COLUMN aktualni_cinnost VARCHAR(300) NULL AFTER last_checkin_at;
