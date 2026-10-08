# Předávka: třídění Emailů příchozích (Robert: "přehoď to na Bot3")

Stav (bot8, 2026-08-20 ~12:40):
- V adminu tlačítko "Třídit" ukazovalo starý běh id=1 (18.8., 7 návrhů, 6 vyřízeno) -> Robertovi nabízel "1 email". Nové e-maily v žádném běhu nejsou.
- Založen NOVÝ čekající běh **id=5** (pending) - čeká na zápis návrhů.
- Otevřených konverzací je 40 - výpis: `api/venv/bin/python3 scripts/2026-08-18_support_triage_submit.py --list`
- Zápis: `--submit 5 --proposals '[...]'` (viz hlavička skriptu).

Můj rozpracovaný návrh klasifikace (bot8 - zkontroluj, uprav, odešli;
conversation_id: destinace - zdůvodnění):
- 116: spam - bounce na testovací adresy botů (test.local)
- 115: objednavka - přijatá objednávka (PO) DHL Supply Chain, příloha PO_CZE20019592_0.pdf
- 114: jine - Robertův vlastní e-mail "kluzak profil 45 4ks - klein" (poznámka k zakázce)
- 113: crm - poptávka výměny 2 pracovních desek (Houra/HP Tronic)
- 110: podpora - aktivní obchod (Lacina potvrzuje objednávku regálu)
- 112: objednavka - notifikace vlastního e-shopu (obj. 26080092)
- 111: podpora - Démos: termín dokončení zakázky 28.8.
- 109: jine - FORPSI potvrzení dobití kreditu (bez dokladu)
- 99: doklad - FORPSI informace o zaplacení, příloha 5260820633.pdf (invoice_attachment_filename)
- 98: spam - GOPAY notifikace platby (doklad chodí od FORPSI)
- 108: jine - FORPSI potvrzení objednávky dobití
- 104: podpora - PREDICOR žádá doplnění chybějících dokladů (akce)
- 102: spam - DHL marketing (webinář)
- 101: crm - poptávka dílenské vestavby 2x VW Transporter (BRICK), příloha konkurenční konfigurace
- 100: jine - FORPSI potvrzení registrace domény remeslnik.pro
- 97: spam - Mastercard notifikace nového zařízení (Robertova vlastní akce)
- 96: jine - FORPSI potvrzení objednávky 5260820525
- 95: spam - TikTok "možná znáš"
- 72: podpora - FTP Plastics potvrzení objednávky přířezů, závoz 26.8.
- 94: spam - VANK marketing (IFA/IAW)
- 93: jine - Maršálková: vyřízené poděkování (faktury směřovat na mandik@)
- 92: spam - Google Ads novinky
- 91: spam - DHL marketing (UK přeprava)
- 90: doklad - Seligerová: příkazy k úhradě srážkové daně + výplata podílu (přílohy)
- 89: spam - Alibaba nabídka (terminal blocks)
- 88: spam - Alibaba notifikace zprávy
- 87: doklad - PREDICOR: příkaz k úhradě DPH 07/2026 (29 800 Kč)
- 86: spam - Ardea tracking zásilky (faktura je zvlášť v id 84)
- 85: doklad - Fwd faktura Pragconstruct (od asistentky)
- 84: doklad - Ardea faktura č. 22609267 (PDF)
- 83: podpora - Lacina: regál Ducato nesedí (chybí šuplíky, foto) - akce
- 82: podpora - Lacina: držák panelů, aktivní vlákno
- 80: jine - Robertův prázdný e-mail "Svoboda Vin"
- 79: jine - Robertovo přeposlání staré nabídky držáku panelů (podklad k Lacinovi)
- 78: spam - marketing dotačního vzdělávání
- 76: jine - Demos24Plus stavy objednávky (3x, bez akce)
- 77: spam - Seznam.cz statistiky profilu
- 75: jine - Démos storno zakázky 3dLab (ověřit, zda očekávané)
- 73: jine - brslik: přechod na nový portál od 1.9.
- 42: jine - Robertovo testovací/interní vlákno ("test kuk")
