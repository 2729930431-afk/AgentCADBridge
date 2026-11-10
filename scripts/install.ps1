param([switch]$SkipCodex, [switch]$Dev)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $syncArgs = @('sync', '--frozen', '--project', $projectRoot)
    if ($Dev) { $syncArgs += @('--extra', 'dev') }
    & uv @syncArgs
    if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
} else {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        & py -3.12 -m venv (Join-Path $projectRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12+ or uv first' }
    }
    $requirements = Join-Path $projectRoot 'requirements-lock.txt'
    & $pythonPath -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    if ($Dev) { & $pythonPath -m pip install 'pytest>=8' 'ruff>=0.9' }
}
& $pythonPath (Join-Path $PSScriptRoot 'install_codex.py')
if ($LASTEXITCODE -ne 0) { throw 'Plugin staging failed' }
if (-not $SkipCodex) {
    if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
        throw 'Codex CLI is required for automatic registration. Use -SkipCodex and add the printed marketplace path in Codex.'
    }
    $marketRoot = Join-Path $env:LOCALAPPDATA 'CADBridge\codex-marketplace'
    & codex plugin marketplace add $marketRoot
    if ($LASTEXITCODE -ne 0) { throw 'Codex marketplace registration failed' }
    & codex plugin add 'cad@agent-cad-bridge-local' --json
    if ($LASTEXITCODE -ne 0) { throw 'Codex plugin installation failed' }
}
Write-Host 'CAD plugin installed. Restart Codex and start a new chat. Keep this repository and its .venv in place.'
