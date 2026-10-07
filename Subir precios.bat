@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   Alemakeup - Subiendo los precios de Alexandra
echo ================================================
python scraper\precios_excel.py importar
if errorlevel 1 (pause & exit /b)
git pull --rebase --autostash
python scraper\sync.py
git add -A
git commit -m "Precios de Alexandra actualizados"
git push
echo.
echo Listo. En 1 a 2 minutos se ven en https://alemakeup.github.io
pause
