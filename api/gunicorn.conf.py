# Konfigurace gunicornu (gunicorn ji bere sam z pracovniho adresare sluzby /opt/konfigurator/api, nacte se pri startu i pri kazdem HUP).
#
# PROC (incident 2026-10-02 17:37, beh nasazeni #10, vypadek obsluhy 19,8 s): gunicorn 22 loguje v handleru SIGCHLD (Arbiter.handle_chld ->
# reap_workers -> log.error). Kdyz zrovna hlavni vlakno arbitra pise log na stderr (journald pomaly / pri HUP se najednou meni vsechny
# workery a loguje se hodne radku), signal handler vstoupi do TOHO SAMEHO BufferedWriteru a Python vyhodi
# "RuntimeError: reentrant call inside <_io.BufferedWriter name='<stderr>'>". logging.Handler.handleError ho nechyti (sam pise na stderr),
# vyjimka vyleti z handleru az do Arbiter.run -> "Unhandled exception in main loop" -> arbiter se vypne (exit -1), systemd ho spusti
# znovu po RestartSec=5 a start aplikace trva dalsich ~6 s => ~20 s bez obsluhy.
#
# OPATRENI: logging.raiseExceptions = False. Chyba pri ZAPISU logu se pak tise zahodi (ztrati se jedina radka logu) misto aby shodila arbitra.
# Overeno na zkusebni instanci (scripts/2026-10-02_gunicorn_incident_testy/test_arbiter_reentrant.py): bez opatreni arbiter zemrel 5 z 8,
# s opatrenim 0 z 8 (od startu i pri nacteni az za behu pres HUP).
import logging

logging.raiseExceptions = False
