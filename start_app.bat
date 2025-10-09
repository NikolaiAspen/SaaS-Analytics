@echo off
echo Starting SaaS Analytics Application...
echo.

cd /d "%~dp0"

if not exist .venv (
    echo Virtual environment not found. Creating it now...
    python -m venv .venv
    call .venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

if not exist .env (
    echo.
    echo WARNING: .env file not found!
    echo Please copy .env.example to .env and fill in your credentials.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting server on http://127.0.0.1:8000
echo Press Ctrl+C to stop the server
echo.

uvicorn app:app --host 127.0.0.1 --port 8000

pause
