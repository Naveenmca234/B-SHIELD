<#
.SYNOPSIS
    B-SHIELD (IBVAP) — One-Command Windows Demo Launcher
.DESCRIPTION
    Checks prerequisites (Python, Node.js/npm, MongoDB), seeds demo data,
    launches backend (FastAPI/Uvicorn) and frontend (Vite/React), and provides
    instant access credentials and demo walkthrough guide for judges.
#>

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " B-SHIELD (IBVAP)" -ForegroundColor Yellow
Write-Host " AI-Powered Intelligent Border Surveillance Command Center" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MODE: DEMO / EVALUATION ONLY`n" -ForegroundColor Magenta

# 1. Check Python
Write-Host "[1/5] Checking Python environment..." -ForegroundColor White
$pythonCmd = $null
if (Test-Path "$PSScriptRoot\..\backend\.venv\Scripts\python.exe") {
    $pythonCmd = "$PSScriptRoot\..\backend\.venv\Scripts\python.exe"
    Write-Host "  Found virtualenv Python: $pythonCmd" -ForegroundColor Green
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
    $pyVer = python --version
    Write-Host "  Found system Python: $pyVer" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Python 3.10+ not found in PATH or backend\.venv." -ForegroundColor Red
    Write-Host "  Please install Python 3.10+ from python.org or activate a virtualenv." -ForegroundColor Yellow
    Exit 1
}

# 2. Check Node.js and npm
Write-Host "`n[2/5] Checking Node.js / npm..." -ForegroundColor White
if (Get-Command npm -ErrorAction SilentlyContinue) {
    $npmVer = npm --version
    $nodeVer = node --version
    Write-Host "  Found Node.js $nodeVer (npm $npmVer)" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Node.js / npm not found in PATH." -ForegroundColor Red
    Write-Host "  Please install Node.js 18+ from https://nodejs.org/" -ForegroundColor Yellow
    Exit 1
}

# 3. Check MongoDB
Write-Host "`n[3/5] Checking MongoDB status on port 27017..." -ForegroundColor White
$mongoAvailable = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("127.0.0.1", 27017)
    $tcp.Close()
    $mongoAvailable = $true
    Write-Host "  MongoDB is running on port 27017." -ForegroundColor Green
} catch {
    Write-Host "  MongoDB is NOT running on 127.0.0.1:27017." -ForegroundColor Yellow
    Write-Host "  NOTE: B-SHIELD includes an edge-resilient offline queue backlog." -ForegroundColor Cyan
    Write-Host "        If MongoDB is offline, events are safely queued to local disk." -ForegroundColor Cyan
    Write-Host "  To start MongoDB as a Windows service:" -ForegroundColor White
    Write-Host "    net start MongoDB" -ForegroundColor Gray
    Write-Host "  Or start manually via mongod:" -ForegroundColor White
    Write-Host "    mongod --dbpath <data_directory>" -ForegroundColor Gray
}

# 4. Seed Demo Data
Write-Host "`n[4/5] Initializing demo database and snapshots..." -ForegroundColor White
$backendDir = Resolve-Path "$PSScriptRoot\..\backend"
$frontendDir = Resolve-Path "$PSScriptRoot\..\frontend"

Push-Location $backendDir
try {
    & $pythonCmd database/seed.py
} catch {
    Write-Host "  Warning: Seed script exited with notice (expected if MongoDB is currently offline)." -ForegroundColor Yellow
}
Pop-Location

# 5. Launch Backend and Frontend
Write-Host "`n[5/5] Launching B-SHIELD application processes..." -ForegroundColor White

# Start Backend
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$backendDir'; & '$pythonCmd' -m uvicorn main:app --reload --port 8000" -WindowStyle Normal
Write-Host "  Backend server starting at http://127.0.0.1:8000" -ForegroundColor Green

# Start Frontend
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$frontendDir'; npm run dev" -WindowStyle Normal
Write-Host "  Frontend application starting at http://localhost:5173" -ForegroundColor Green

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " B-SHIELD (IBVAP) READY FOR DEMONSTRATION" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "FRONTEND URL:  http://localhost:5173" -ForegroundColor White
Write-Host "BACKEND API:   http://127.0.0.1:8000" -ForegroundColor White
Write-Host "API DOCS:      http://127.0.0.1:8000/docs`n" -ForegroundColor White

Write-Host "DEMO CREDENTIALS [DEMO / DEVELOPMENT ONLY]:" -ForegroundColor Yellow
Write-Host "  1. Operator Console:  Username: operator  | Password: Operator@123" -ForegroundColor White
Write-Host "  2. Administrator:     Username: admin     | Password: IBVAP@123" -ForegroundColor White
Write-Host "  3. Viewer (Read-only):Username: viewer    | Password: Viewer@123`n" -ForegroundColor White

Write-Host "OPERATOR DEMO WALKTHROUGH SEQUENCE:" -ForegroundColor Cyan
Write-Host "  1. Open http://localhost:5173 in browser." -ForegroundColor Gray
Write-Host "  2. Click 'Operator' to autofill credentials and click 'Sign In'." -ForegroundColor Gray
Write-Host "  3. Navigate to 'Live Surveillance' from sidebar." -ForegroundColor Gray
Write-Host "  4. Observe video stream with real-time detection, tracking IDs, and dwell tracking." -ForegroundColor Gray
Write-Host "  5. Switch between 'Live Video' and 'Event-Only' mode to demonstrate low-bandwidth mode." -ForegroundColor Gray
Write-Host "  6. Navigate to 'Alerts' or 'Dashboard' to view real-time intrusion alert." -ForegroundColor Gray
Write-Host "  7. Click 'Acknowledge' -> 'Responding' -> 'Resolve'." -ForegroundColor Gray
Write-Host "  8. Click 'Verify Integrity' on snapshot to verify cryptographic SHA-256." -ForegroundColor Gray
Write-Host "  9. Record operator false-alarm feedback analytics." -ForegroundColor Gray
Write-Host "============================================================`n" -ForegroundColor Cyan
