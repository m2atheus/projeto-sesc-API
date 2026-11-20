param(
    [Parameter(Position = 0)]
    [ValidateSet("dev", "ingest", "public")]
    [string]$Role = "dev"
)

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $rootDir ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Instale primeiro com python scripts/install.py."
}
Push-Location -LiteralPath $rootDir
try {
    & $pythonExe -m app.serve $Role
    $statusCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $statusCode
