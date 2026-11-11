@echo off
rem Instala os pacotes que a versao do codigo precisa (so uma vez).
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt || python -m pip install -r requirements.txt
echo.
echo Pronto. Agora de dois cliques em run.bat
pause
