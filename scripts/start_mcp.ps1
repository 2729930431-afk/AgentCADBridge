$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'CADBridge runtime missing. Run scripts\install.ps1 first.'
}
& $pythonPath (Join-Path $PSScriptRoot 'start_mcp.py')
exit $LASTEXITCODE
