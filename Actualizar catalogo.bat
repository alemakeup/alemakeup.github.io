@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   Alemakeup - Actualizando catalogo del mayorista
echo ================================================
python -m pip install -q -r requirements.txt
python scraper\sync.py
echo.
pause
