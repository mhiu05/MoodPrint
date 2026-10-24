$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $taskRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run uv sync --locked in backend first.' }
if (-not $env:TEST_DATABASE_URL -or $env:TEST_DATABASE_URL -notmatch '/[^/]+_test$') { throw 'Set TEST_DATABASE_URL to a disposable local *_test database.' }
$env:MOODPRINT_API_PROXY = 'http://127.0.0.1:8002'
$logRoot = Join-Path $env:TEMP 'moodprint-fullstack'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$backendProcess = $null
$frontendProcess = $null
try {
  foreach ($taskPort in @(8002,5174)) {
    if (Get-NetTCPConnection -LocalPort $taskPort -State Listen -ErrorAction SilentlyContinue) { throw "Port $taskPort is already in use; the full-stack harness will not stop another process." }
  }
  $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','tests.e2e_server') -WorkingDirectory (Join-Path $taskRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot 'backend.log') -RedirectStandardError (Join-Path $logRoot 'backend-error.log')
  $frontendProcess = Start-Process -FilePath 'node.exe' -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5174','--strictPort') -WorkingDirectory (Join-Path $taskRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot 'frontend.log') -RedirectStandardError (Join-Path $logRoot 'frontend-error.log')
  foreach ($taskUrl in @('http://127.0.0.1:8002/api/v1/health/live','http://127.0.0.1:5174')) {
    $isReady = $false
    for ($attempt=0; $attempt -lt 50; $attempt++) {
      try { Invoke-WebRequest -Uri $taskUrl -UseBasicParsing -TimeoutSec 1 | Out-Null; $isReady=$true; break } catch { Start-Sleep -Milliseconds 400 }
    }
    if (-not $isReady) { throw "Test server did not become ready: $taskUrl. Logs are in $logRoot" }
  }
  Push-Location (Join-Path $taskRoot 'frontend')
  try { & npx.cmd playwright test --config playwright.fullstack.config.ts; $testExitCode=$LASTEXITCODE } finally { Pop-Location }
  if ($testExitCode -ne 0) { throw "Full-stack Playwright failed with exit code $testExitCode" }
} finally {
  foreach ($taskProcess in @($backendProcess,$frontendProcess)) {
    if ($taskProcess -and -not $taskProcess.HasExited) { Stop-Process -Id $taskProcess.Id -ErrorAction SilentlyContinue }
  }
}
