$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path tmp | Out-Null
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.14 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Creazione ambiente non riuscita.' }
}
& '.\.venv\Scripts\python.exe' -m pip install --no-cache-dir --disable-pip-version-check -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze non riuscita.' }
