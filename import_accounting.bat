@echo off
REM ========================================
REM Import Accounting Receivable Details
REM ========================================
REM
REM BRUK: Dra og slipp en Excel-fil på denne batch-filen
REM       eller kjør: import_accounting.bat "path/to/file.xlsx"
REM

echo.
echo ========================================
echo IMPORT ACCOUNTING RECEIVABLE DETAILS
echo ========================================
echo.

REM Check if file path was provided
if "%~1"=="" (
    echo FEIL: Ingen fil spesifisert!
    echo.
    echo BRUK:
    echo   - Dra og slipp en Excel-fil paa denne batch-filen
    echo   - Eller kjor: import_accounting.bat "path/to/file.xlsx"
    echo.
    pause
    exit /b 1
)

REM Check if file exists
if not exist "%~1" (
    echo FEIL: Filen finnes ikke: %~1
    echo.
    pause
    exit /b 1
)

echo Importerer fil: %~1
echo.

REM Run the Python script
python import_monthly_accounting.py "%~1"

echo.
echo ========================================
echo Trykk en tast for aa lukke...
echo ========================================
pause >nul
