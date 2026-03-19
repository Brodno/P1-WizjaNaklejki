@echo off
cd /d "%~dp0"
echo Sprawdzam PyQt6...
.venv\Scripts\python.exe -c "import PyQt6" 2>nul || (
    echo Instaluję PyQt6 - chwila...
    .venv\Scripts\pip install PyQt6
)
echo Uruchamiam AOP VISION MASTER v6.0 (PyQt6)...
.venv\Scripts\python.exe app_qt.py
pause
