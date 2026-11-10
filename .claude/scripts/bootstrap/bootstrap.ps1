# Restores the Claude Code toolkit on Windows. Run from the project root:
#   powershell -ExecutionPolicy Bypass -File .claude/scripts/bootstrap/bootstrap.ps1 [-Check]
param([switch]$Check)
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Write-Error "Node.js >= 22.22 is required."; exit 1 }
$argsList = @(".claude/scripts/bootstrap/bootstrap.mjs")
if ($Check) { $argsList += "--check" }
& node @argsList
exit $LASTEXITCODE
