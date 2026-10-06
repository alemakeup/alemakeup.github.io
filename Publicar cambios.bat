@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   Alemakeup - Publicando cambios en internet
echo ================================================
git pull --rebase --autostash
python scraper\sync.py --solo-tienda
git add -A
git commit -m "Cambios desde el computador"
git push
echo.
echo Listo. En 1 a 2 minutos se ven en https://alemakeup.github.io
pause
