# Sentinel Core — Start both Backend + Frontend
# Usage: .\start-dev.ps1

Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║      SENTINEL CORE — DEV SERVER      ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Start FastAPI backend ──────────────────────────────────
Write-Host "  [1/2] Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList '/k set PYTHONPATH=src && .\.venv\Scripts\python.exe -m api.main' -WorkingDirectory "c:\Users\AMAL\Desktop\sentinel-core-mvp"

Start-Sleep -Seconds 3

# ── 2. Start Next.js frontend ─────────────────────────────────
Write-Host "  [2/2] Starting Next.js frontend on http://localhost:3000 ..." -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList "/k npm run dev" -WorkingDirectory "c:\Users\AMAL\Desktop\sentinel-core-mvp\frontend"

Write-Host ""
Write-Host "  ✓ Backend  → http://localhost:8000" -ForegroundColor Cyan
Write-Host "  ✓ Frontend → http://localhost:3000" -ForegroundColor Cyan  
Write-Host "  ✓ API Docs → http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  The servers are running in separate terminal windows." -ForegroundColor Gray
Write-Host "  Close those windows to stop the servers." -ForegroundColor Gray
Write-Host ""
