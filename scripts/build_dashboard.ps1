Write-Host "Building dashboard.exe..." -ForegroundColor Cyan
$cFile   = "dashboard\dashboard.c"
$exeFile = "dashboard\dashboard.exe"
if (-not (Test-Path $cFile)) {
    Write-Host "X $cFile not found" -ForegroundColor Red
    exit 1
}
gcc -O2 -Wall $cFile -o $exeFile -lws2_32
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK Build success: $exeFile" -ForegroundColor Green
} else {
    Write-Host "X Build failed" -ForegroundColor Red
}
