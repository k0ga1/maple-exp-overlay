@echo off
rem Opens Maple Classic Exp Overlay from the source code, without a console window.
rem (Double-clicking "Abrir Overlay.pyw" does the same with no flash at all.)
cd /d "%~dp0"
py -3 -c "import cv2, mss, numpy, PIL" >nul 2>nul && (
    start "" pyw -3 maple_exp.py
    exit /b
)
python -c "import cv2, mss, numpy, PIL" >nul 2>nul && (
    start "" pythonw maple_exp.py
    exit /b
)
echo Couldn't find Python with the packages this needs.
echo Install Python from python.org, then run instalar.bat once.
pause
