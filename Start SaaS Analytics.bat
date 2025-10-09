@echo off
title SaaS Analytics Dashboard

cd /d "%~dp0"

if not exist .venv (
    echo Virtual environment ikke funnet. Oppretter det naa...
    python -m venv .venv
    call .venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

if not exist .env (
    echo.
    echo ADVARSEL: .env fil ikke funnet!
    echo Vennligst kopier .env.example til .env og fyll inn dine credentials.
    echo.
    pause
    exit /b 1
)

cls
echo ========================================
echo   SaaS Analytics Dashboard
echo ========================================
echo.
echo Serveren starter paa http://127.0.0.1:8000
echo Aapner nettleser automatisk...
echo.
echo Trykk Ctrl+C for aa stoppe serveren
echo ========================================
echo.

start http://127.0.0.1:8000
uvicorn app:app --host 127.0.0.1 --port 8000

pause
