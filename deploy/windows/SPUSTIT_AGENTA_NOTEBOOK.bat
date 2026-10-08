@echo off
title Logiman - renderovaci agent (notebook)
cd /d "%~dp0"
rem v2 2026-10-01 (bot4): STROP OPAKOVANI. Agent, ktery skonci drive nez za 2 minuty po startu, se pocita jako pad hned
rem po startu; 5 takovych padu za sebou = konec (misto smycky bez konce, ktera porad dokola otevirala totez -
rem Robert 2026-09-30, "Agent skoncil, restartuji za 3s..."). Agent, ktery bezel dele, pocitadlo vynuluje.

rem Token a server si bere ze stareho SPUSTIT_AGENTA.bat ve stejne slozce, a kdyz tam neni, z NAINSTALOVAT_SLUZBU.bat
rem (v2.1 2026-10-01: Robert na notebooku dostal "Token nenalezen" - SPUSTIT_AGENTA.bat tam nikdy nebyl).
if not defined RENDER_WORKER_TOKEN call :precti RENDER_WORKER_TOKEN
if not defined RENDER_SERVER call :precti RENDER_SERVER
if not defined RENDER_WORKER_TOKEN set /p RENDER_WORKER_TOKEN=Token nenalezen. Vloz ho a stiskni Enter: 
if not defined RENDER_WORKER_TOKEN goto :konec

echo Hledam Blender...
set "BE="
call :najdi "C:\Program Files\Blender Foundation"
call :najdi "%LOCALAPPDATA%\Programs\Blender Foundation"
if not defined BE goto :nenasel_blender
set "BLENDER_EXE=%BE%"
for %%A in ("%BE%") do set "BDIR=%%~dpA"
set "PY="
for /f "delims=" %%F in ('dir /b /s "%BDIR%python.exe" 2^>nul') do if not defined PY set "PY=%%F"
if not defined PY goto :nenasel_python
set "AG=%~dp0render_worker_agent_2026-08-11_1455.py"
if not exist "%AG%" goto :nenasel_agenta

echo   Blender: %BLENDER_EXE%
echo   Python:  %PY%
echo   Agent:   %AG%
if defined RENDER_SERVER (echo   Server:  %RENDER_SERVER%) else echo   Server:  vychozi
echo   Token:   nalezen
echo.

set "PADY=0"
:smycka
call :cas S0
"%PY%" "%AG%"
set "RC=%ERRORLEVEL%"
call :cas S1
set /a DOBA=S1-S0
if %DOBA% LSS 0 set /a DOBA+=86400
echo.
if "%RC%"=="3" goto :chyba_nastaveni
if "%RC%"=="2" goto :bezi_jina
if %DOBA% GEQ 120 (set "PADY=0") else (set /a PADY+=1)
if %PADY% GEQ 5 goto :opakovane_padani
echo Agent skoncil, kod %RC%, bezel %DOBA% s. Restartuji za 3s... Rychlych padu za sebou: %PADY% z 5.
timeout /t 3 /nobreak >nul
goto :smycka

:cas
rem do promenne %1 da pocet sekund od pulnoci (z %%time%%, tvar H:MM:SS,cc; mezeru nahradi nulou)
for /f "tokens=1-3 delims=:.," %%a in ("%time: =0%") do set /a "%~1=(1%%a-100)*3600+(1%%b-100)*60+(1%%c-100)"
goto :eof

:precti
set "VAL="
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /c:"%~1=" "%~dp0SPUSTIT_AGENTA.bat" 2^>nul`) do set "VAL=%%B"
if not defined VAL call :precti_sluzba "%~1"
if defined VAL set "VAL=%VAL:"=%"
if defined VAL set "%~1=%VAL%"
goto :eof

:precti_sluzba
rem jen radek, ktery ZACINA na: set "KLIC=...  (nebo set KLIC=...) - v instalatoru je KLIC= i v radku nssm AppEnvironmentExtra a ten se nesmi vzit
if not exist "%~dp0NAINSTALOVAT_SLUZBU.bat" goto :eof
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r /b /c:"set %~1=" /c:"set .%~1=" "%~dp0NAINSTALOVAT_SLUZBU.bat" 2^>nul`) do if not defined VAL set "VAL=%%B"
goto :eof

:najdi
if defined BE goto :eof
if not exist "%~1" goto :eof
for /f "delims=" %%D in ('dir /b /ad /o-n "%~1" 2^>nul') do if not defined BE if exist "%~1\%%D\blender.exe" set "BE=%~1\%%D\blender.exe"
goto :eof

:nenasel_blender
echo.
echo NENASEL JSEM BLENDER v C:\Program Files\Blender Foundation ani v %LOCALAPPDATA%\Programs.
echo Nainstaluj Blender 5.2.1 nebo novejsi do vychozi slozky.
goto :konec

:nenasel_python
echo.
echo Nenasel jsem python.exe uvnitr Blenderu (%BDIR%).
goto :konec

:nenasel_agenta
echo.
echo Chybi %AG%
echo Stahni ho ze Sdileneho disku (slozka Renderovaci agent) sem, vedle tohoto souboru.
goto :konec

:chyba_nastaveni
echo Chyba nastaveni (viz vyse).
goto :konec

:opakovane_padani
echo.
echo AGENT OPAKOVANE PADA HNED PO STARTU, 5x za sebou, posledni kod %RC%. Dal ho nerestartuji.
echo Zkontroluj hlasky vyse. Nejcastejsi pricina: Blender nebo Python v jine slozce, chybejici agent .py
echo vedle tohoto souboru nebo spatny token. Az to opravis, spust tento soubor znovu.
goto :konec

:bezi_jina
echo Uz bezi jina kopie agenta - zavri ostatni okna agenta.
goto :konec

:konec
echo.
pause
exit /b 1
