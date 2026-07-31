# Launch the public dicomxphits GUI from an existing local virtual environment.
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvScripts = Split-Path -Parent $PythonExe

if (-not (Test-Path -LiteralPath $PythonExe)) {
  Write-Error "Missing virtual environment Python: $PythonExe. Create the environment explicitly before running this launcher."
  exit 1
}

$env:Path = "$VenvScripts;$env:Path"

& $PythonExe -m dicomxphits.gui
