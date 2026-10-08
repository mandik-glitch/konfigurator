@echo off
title Logiman - odebrani odkazu logimanrender
echo.
echo Odkaz logimanrender:// probouzi renderovaciho agenta z prohlizece. Pokud je na tomto PC zaregistrovany
echo zastaraly spoustec, otevre okno, ktere se porad dokola restartuje. Tenhle soubor odkaz z tohoto PC odebere.
echo Agent na GPU stanici bezi jako sluzba, notebook se spousti pres SPUSTIT_AGENTA_NOTEBOOK.bat - odkaz nepotrebuji.
echo.
set "NIC=1"

reg query "HKCU\Software\Classes\logimanrender" >nul 2>&1
if errorlevel 1 goto :hklm
set "NIC="
echo Nalezeno v uzivatelskem nastaveni, spoustec:
reg query "HKCU\Software\Classes\logimanrender\shell\open\command" /ve 2>nul | findstr /i "REG_SZ"
reg delete "HKCU\Software\Classes\logimanrender" /f >nul 2>&1
if errorlevel 1 echo   ODEBRANI SE NEPODARILO.
if not errorlevel 1 echo   odebrano.
echo.

:hklm
reg query "HKLM\Software\Classes\logimanrender" >nul 2>&1
if errorlevel 1 goto :hotovo
set "NIC="
echo Nalezeno v systemovem nastaveni, spoustec:
reg query "HKLM\Software\Classes\logimanrender\shell\open\command" /ve 2>nul | findstr /i "REG_SZ"
reg delete "HKLM\Software\Classes\logimanrender" /f >nul 2>&1
if errorlevel 1 echo   ODEBRANI SE NEPODARILO - spust tento soubor znovu jako spravce: pravy klik, Spustit jako spravce.
if not errorlevel 1 echo   odebrano.
echo.

:hotovo
if defined NIC echo Na tomto PC odkaz zaregistrovany neni, neni co odebirat.
if not defined NIC echo Hotovo. Tlacitka "+ rendery" a "Test" ve scene uz na tomto PC nic nespousteji.
echo Okno s napisem RenderAgent, ktere se porad restartuje, zavri krizkem v rohu.
echo.
pause
