# Import invoice data to Railway PostgreSQL
# Usage: .\import_to_railway.ps1

Write-Host "=" * 80
Write-Host "IMPORT INVOICES TO RAILWAY POSTGRESQL"
Write-Host "=" * 80

# Check if Railway DATABASE_URL is provided
if (-not $env:RAILWAY_DATABASE_URL) {
    Write-Host ""
    Write-Host "ERROR: RAILWAY_DATABASE_URL environment variable not set" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please set it first:" -ForegroundColor Yellow
    Write-Host '  $env:RAILWAY_DATABASE_URL="postgresql://postgres:password@roundhouse.proxy.rlwy.net:12345/railway"' -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "Railway Database URL detected" -ForegroundColor Green
Write-Host "Running import with Railway database..." -ForegroundColor Yellow
Write-Host ""

# Temporarily set DATABASE_URL to Railway
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:RAILWAY_DATABASE_URL

try {
    # Run the import script
    & .venv\Scripts\python.exe import_invoices_xlsx.py

    Write-Host ""
    Write-Host "=" * 80
    Write-Host "IMPORT COMPLETE!" -ForegroundColor Green
    Write-Host "=" * 80

} finally {
    # Restore original DATABASE_URL
    if ($originalDatabaseUrl) {
        $env:DATABASE_URL = $originalDatabaseUrl
    }
}
