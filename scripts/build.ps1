$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path tmp | Out-Null
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
$env:PYINSTALLER_CONFIG_DIR = Join-Path (Get-Location) 'tmp\pyinstaller'
& '.\.venv\Scripts\ruff.exe' check quiz_simulator tests scripts run_quiz.py
if ($LASTEXITCODE -ne 0) { throw 'Controllo del codice non riuscito.' }
& '.\.venv\Scripts\python.exe' -m pytest
if ($LASTEXITCODE -ne 0) { throw 'Test automatici non riusciti.' }
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --clean --onedir --windowed --name QuizSimulator --add-data 'schemas;schemas' --add-data 'GUIDA_UTENTE.md;.' --add-data 'examples;examples' --add-data 'docs;docs' --add-data 'README.md;.' run_quiz.py
if ($LASTEXITCODE -ne 0) { throw 'Creazione eseguibile non riuscita.' }

# Alcuni ambienti di sviluppo aggiungono Poppler al PATH. Le sue librerie ICU
# hanno nomi uguali a quelle di Windows, ma non sono compatibili con Qt.
$internalDir = (Resolve-Path -LiteralPath 'dist\QuizSimulator\_internal').Path
foreach ($library in @('icuuc.dll', 'icudt78.dll')) {
    $candidate = Join-Path $internalDir $library
    if (Test-Path -LiteralPath $candidate) {
        Remove-Item -LiteralPath $candidate -Force
    }
}

Copy-Item -LiteralPath 'GUIDA_UTENTE.md','README.md','LICENSE' -Destination 'dist\QuizSimulator'
Copy-Item -LiteralPath 'examples' -Destination 'dist\QuizSimulator' -Recurse -Force
Copy-Item -LiteralPath 'docs' -Destination 'dist\QuizSimulator' -Recurse -Force

$smokeResult = Join-Path (Get-Location) 'tmp\smoke-test\smoke-result.json'
if (Test-Path -LiteralPath $smokeResult) {
    Remove-Item -LiteralPath $smokeResult -Force
}
$executable = (Resolve-Path -LiteralPath 'dist\QuizSimulator\QuizSimulator.exe').Path
$smoke = Start-Process -FilePath $executable -ArgumentList '--smoke-test' -Wait -PassThru -WindowStyle Hidden
if ($smoke.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $smokeResult)) {
    throw 'Collaudo dell''eseguibile non riuscito.'
}
$smokeData = Get-Content -Raw -LiteralPath $smokeResult | ConvertFrom-Json
if (-not $smokeData.ok -or -not $smokeData.guide -or -not $smokeData.examples) {
    throw 'L''eseguibile non trova tutte le risorse incluse.'
}

Compress-Archive -Path 'dist\QuizSimulator\*' -DestinationPath 'dist\QuizSimulator-Windows.zip' -Force
Write-Output 'Eseguibile pronto in dist\QuizSimulator\QuizSimulator.exe'
Write-Output 'Pacchetto pronto in dist\QuizSimulator-Windows.zip'
