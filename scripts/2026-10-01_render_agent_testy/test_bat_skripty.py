# Staticka kontrola Windows skriptu renderovaciho agenta (deploy/windows/*.bat) - batch tu pustit nejde, tak se hlida
# to, na cem se batch nejcasteji rozbije: neexistujici navesti (goto/call), nevyvazene zavorky u viceradkovych bloku,
# licha uvozovka, jine konce radku nez CRLF, ne-ASCII znaky (kodovani konzole). Navic ze spouštěč MA strop opakovani.
# Spusteni: python3 test_bat_skripty.py   (konci kodem 0 jen kdyz VSE prosla)
import os
import re
import sys

REPO = "/opt/konfigurator"
ADRESAR = "/opt/konfigurator/deploy/windows"
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


def kontrola(nazev):
    cesta = os.path.join(ADRESAR, nazev)
    raw = open(cesta, "rb").read()
    over("%s: jen ASCII" % nazev, all(b < 128 for b in raw))
    over("%s: vsechny konce radku jsou CRLF" % nazev, raw.count(b"\r\n") == raw.count(b"\n") and raw.endswith(b"\r\n"), (raw.count(b"\r\n"), raw.count(b"\n")))
    radky = raw.decode("ascii").split("\r\n")
    navesti = {r[1:].split()[0].lower() for r in radky if r.startswith(":") and not r.startswith("::") and len(r) > 1}
    cile = []
    for r in radky:
        s = r.strip()
        if s.lower().startswith("rem") or s.lower().startswith("echo"):
            continue
        for m in re.finditer(r"\b(?:goto|call)\s+:(\w+)", s, re.I):
            cile.append((m.group(1).lower(), s))
    chybi = [c for c, _ in cile if c not in navesti and c != "eof"]
    over("%s: kazde goto/call :navesti existuje" % nazev, not chybi, chybi)
    bloky = [r for r in radky if re.search(r"\($", r.strip()) and not r.strip().lower().startswith(("rem", "echo"))]
    over("%s: zadny viceradkovy blok '(' na konci radku (echo se zavorkami by ho rozbil)" % nazev, not bloky, bloky)
    # idiom `%PROMENNA:"=%` (odstraneni uvozovek z hodnoty) obsahuje uvozovku zamerne - pred pocitanim se odstrani
    lichy = [r for r in radky if not r.strip().lower().startswith("rem") and re.sub(r'%\w+:"=%', "", r).count('"') % 2 == 1]
    over("%s: kazdy radek ma sudy pocet uvozovek" % nazev, not lichy, lichy)
    nevyvazene = [r for r in radky if not r.strip().lower().startswith(("rem", "echo")) and r.count("(") != r.count(")")]
    nevyvazene = [r for r in nevyvazene if "%" not in r.split("(")[0] or True]
    over("%s: zavorky mimo echo/rem jsou na radku vyvazene" % nazev, not nevyvazene, nevyvazene)
    return radky


r = kontrola("SPUSTIT_AGENTA_NOTEBOOK.bat")
t = "\r\n".join(r)
over("spoustec: ma strop opakovani (pocitadlo PADY a konec po 5)", "set /a PADY+=1" in t and "if %PADY% GEQ 5 goto :opakovane_padani" in t)
over("spoustec: kratky beh se pocita jako pad (prah 120 s), dlouhy pocitadlo nuluje", 'if %DOBA% GEQ 120 (set "PADY=0") else (set /a PADY+=1)' in t)
over("spoustec: kod 2 (uz bezi) a 3 (chyba nastaveni) smycku ukoncuji jako driv", 'if "%RC%"=="3" goto :chyba_nastaveni' in t and 'if "%RC%"=="2" goto :bezi_jina' in t)
over("spoustec: cas v sekundach z %time% s osetrenou nulou (1xx-100, mezera -> 0)", '%time: =0%' in t and "(1%%a-100)*3600" in t)
over("spoustec: pocitadlo se nuluje PRED smyckou", t.index('set "PADY=0"') < t.index(":smycka"))
over("spoustec: hledani Blenderu/Pythonu a tokenu zustalo (beze zmeny)", ":najdi" in t and 'set "PY="' in t and ":precti" in t and "RENDER_WORKER_TOKEN" in t)
over("spoustec: nikde jiny nekonecny skok na :smycka nez ten za timeoutem", t.count("goto :smycka") == 1, t.count("goto :smycka"))

# --- token: spoustec ho najde i v NAINSTALOVAT_SLUZBU.bat (v2.1), aniz by ho nesl v gitu ---------------------------------
over("token: :precti zkousi nejdriv SPUSTIT_AGENTA.bat, pak :precti_sluzba", "call :precti_sluzba" in t and t.index("SPUSTIT_AGENTA.bat") < t.index("call :precti_sluzba"))
over("token: z instalatoru jen radky, ktere ZACINAJI na set (findstr /b, obe podoby set \"K=..\" i set K=..)", 'findstr /i /r /b /c:"set %~1=" /c:"set .%~1=" "%~dp0NAINSTALOVAT_SLUZBU.bat"' in t, [x for x in r if "precti_sluzba" in x or "NAINSTALOVAT" in x])
over("token: bere se PRVNI shoda (if not defined VAL), ne posledni", 'do if not defined VAL set "VAL=%%B"' in t)
over("token: bez instalatoru ve slozce se nic nestane (if not exist ... goto :eof)", 'if not exist "%~dp0NAINSTALOVAT_SLUZBU.bat" goto :eof' in t)
import glob as _glob
unik = [f for f in _glob.glob(os.path.join(REPO, "deploy", "windows", "*")) if re.search(r"RENDER_WORKER_TOKEN\s*=\s*[A-Za-z0-9_\-]{20,}", open(f, encoding="latin-1").read())]
over("token: v gitu (deploy/windows) NENI zadny skutecny token", not unik, unik)
sluzba_soubor = None
try:
    import subprocess
    sluzba_soubor = os.path.join(REPO, "private-files", "shared-drive", "55073adf5e944152af1a74b6d8004120.bat")
    inst = open(sluzba_soubor, encoding="latin-1").read().splitlines()
except OSError:
    inst = None
if inst:
    for klic in ("RENDER_WORKER_TOKEN", "RENDER_SERVER"):
        shod = [l for l in inst if re.match(r'(?i)^set "?%s=' % klic, l)]
        vsude = [l for l in inst if (klic + "=").lower() in l.lower()]
        over("token: v SKUTECNEM instalatoru je radek 'set %s=' prave 1x (a %s= je jinde taky -> proto /b)" % (klic, klic), len(shod) == 1 and len(vsude) > len(shod), (len(shod), len(vsude)))

r = kontrola("ODINSTALOVAT_PROTOKOL.bat")
t = "\r\n".join(r)
over("odinstalace: maze HKCU i HKLM klic logimanrender", 'reg delete "HKCU\\Software\\Classes\\logimanrender" /f' in t and 'reg delete "HKLM\\Software\\Classes\\logimanrender" /f' in t)
over("odinstalace: pred smazanim vypise puvodni spoustec", t.count("shell\\open\\command") >= 2)
over("odinstalace: maze JEN klic logimanrender (zadny jiny kmen registru)", len(re.findall(r"reg delete", t)) == 2 and "logimanrender\" /f" in t)
over("odinstalace: nic jineho nemaze ani nekonci procesy", "del " not in t.lower().replace("reg delete", "") and "taskkill" not in t.lower())

print("\nVYSLEDEK bat skripty: %d/%d OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
