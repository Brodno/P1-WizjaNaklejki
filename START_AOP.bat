@echo off
:: Ustawienie kodowania na UTF-8 dla polskich znakow
chcp 65001 >nul
setlocal enabledelayedexpansion
title AOP MASTER v4.6 - CLEAN START
echo ======================================================
echo    AOP MASTER v4.6 - CZYSZCZENIE I START
echo ======================================================

cd /d "%~dp0"

:: 1. Agresywne uwalnianie portu 8501
echo - Sprawdzanie portu 8501...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /C:":8501" ^| findstr /C:"LISTENING"') do (
    set "PID=%%a"
    if not "!PID!"=="" (
        echo [!] Port 8501 blokowany przez PID: !PID!. Zamykanie...
        taskkill /PID !PID! /F /T >nul 2>&1
        timeout /t 1 >nul
    )
)

:: 2. Zamykanie procesow widmo
echo - Sprzątanie procesów Python/Streamlit...
taskkill /IM streamlit.exe /F >nul 2>&1
taskkill /IM python.exe /F /FI "WINDOWTITLE eq AOP MASTER*" >nul 2>&1

:: 3. Usuwanie plików blokad SQLite
if exist "aop_production.db-wal" del /f /q "aop_production.db-wal" >nul 2>&1
if exist "aop_production.db-shm" del /f /q "aop_production.db-shm" >nul 2>&1

echo ✅ System oczyszczony.

:: 4. Aktywacja srodowiska
if exist ".venv\Scripts\activate.bat" (
    echo [1/2] Aktywacja srodowiska...
    call .venv\Scripts\activate
) else (
    echo ❌ BLAD: Brak .venv!
    pause
    exit
)

echo [2/2] Uruchamianie panelu Sonnet 4.6...
echo.

:: Otwarcie przegladarki
start http://localhost:8501

:: Start aplikacji
python -m streamlit run dashboard.py --server.port 8501 --browser.serverAddress localhost --server.headless false --browser.gatherUsageStats false

pause
