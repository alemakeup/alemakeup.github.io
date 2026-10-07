@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   Alemakeup - Preparando el Excel de precios
echo ================================================
git pull --rebase --autostash
python -m pip install -q -r requirements.txt
python scraper\sync.py
python scraper\precios_excel.py exportar
if errorlevel 1 (pause & exit /b)
start "" "Precios Alemakeup.xlsx"
