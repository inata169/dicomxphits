@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>&1

rem One-entry Windows x64 offline installer. Keep all paths relative to this file.
rem Resolve the script directory without a trailing separator. A quoted Windows
rem argument ending in a backslash can escape its closing quote for Python.
for %%I in ("%~dp0.") do set "BundleRoot=%%~fI"
set "ChecksumFile=%BundleRoot%\SHA256SUMS.txt"
set "Helper=%BundleRoot%\tools\offline_install.py"
set "Installer=%BundleRoot%\python\python-3.12.10-amd64.exe"
set "LogFile=%BundleRoot%\offline-install.log"
set "InstallerLog=%BundleRoot%\python-installer.log"
set "DICOMXPHITS_BUNDLE_ROOT=%BundleRoot%"

echo dicomxphits offline installer
echo.
echo IMPORTANT: Copy and extract this ZIP to a writable local-disk folder first.
echo Do not create the editable environment directly on USB storage.
echo.

if not exist "%ChecksumFile%" (
  echo ERROR: Missing checksum inventory: "%ChecksumFile%" 1>&2
  >>"%LogFile%" echo ERROR: Missing SHA256SUMS.txt before installation.
  exit /b 1
)

rem Verify every protected payload before any bundled executable is started.
powershell.exe -NoProfile -NonInteractive -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$root=[IO.Path]::GetFullPath($env:DICOMXPHITS_BUNDLE_ROOT);" ^
  "$prefix=$root.TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar;" ^
  "$seen=@{};" ^
  "$lines=Get-Content -LiteralPath (Join-Path $root 'SHA256SUMS.txt') -Encoding UTF8;" ^
  "foreach($line in $lines){" ^
  "if([string]::IsNullOrWhiteSpace($line)){continue};" ^
  "if($line -notmatch '^([0-9a-f]{64}) \*(.+)$'){throw ('Invalid checksum line: '+$line)};" ^
  "$expected=$matches[1];$relative=$matches[2].Replace('/',[IO.Path]::DirectorySeparatorChar);" ^
  "if([IO.Path]::IsPathRooted($relative)){throw ('Absolute checksum path: '+$relative)};" ^
  "$full=[IO.Path]::GetFullPath((Join-Path $root $relative));" ^
  "if(-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw ('Escaping checksum path: '+$relative)};" ^
  "$key=$full.ToLowerInvariant();if($seen.ContainsKey($key)){throw ('Duplicate checksum path: '+$relative)};$seen[$key]=$true;" ^
  "if(-not [IO.File]::Exists($full)){throw ('Missing bundle payload: '+$relative)};" ^
  "$actual=(Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant();" ^
  "if($actual -ne $expected){throw ('SHA-256 mismatch: '+$relative)}" ^
  "};Write-Host 'Initial SHA-256 verification passed.'"
if errorlevel 1 (
  echo ERROR: Bundle integrity verification failed. Nothing was installed. 1>&2
  >>"%LogFile%" echo ERROR: Initial bundle SHA-256 verification failed before installation.
  exit /b 1
)
>>"%LogFile%" echo Initial bundle SHA-256 verification passed.

if not exist "%Helper%" (
  echo ERROR: Missing offline installation helper: "%Helper%" 1>&2
  >>"%LogFile%" echo ERROR: Missing tools\offline_install.py.
  exit /b 1
)

call :FindPython312
if not defined SelectedPython (
  if not exist "%Installer%" (
    echo ERROR: No CPython 3.12 x64 was found and the bundled installer is missing. 1>&2
    >>"%LogFile%" echo ERROR: Python 3.12 x64 and bundled installer are unavailable.
    exit /b 1
  )
  echo No existing CPython 3.12 x64 was found.
  echo Installing the verified bundled Python 3.12.10 for the current user...
  >>"%LogFile%" echo Starting bundled Python 3.12.10 current-user installation.
  "%Installer%" /quiet /log "%InstallerLog%" InstallAllUsers=0 Include_pip=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_tcltk=1 Include_test=0 Include_doc=0 PrependPath=0 AssociateFiles=0 Shortcuts=0
  if errorlevel 1 (
    echo ERROR: Python installer failed. 1>&2
    echo See "%InstallerLog%" for installer details. 1>&2
    >>"%LogFile%" echo ERROR: Bundled Python installer failed; see python-installer.log.
    exit /b 1
  )
  >>"%LogFile%" echo Bundled Python installer returned success.
  call :FindPython312
)

if not defined SelectedPython (
  echo ERROR: Python setup completed but CPython 3.12 x64 could not be validated. 1>&2
  >>"%LogFile%" echo ERROR: CPython 3.12 x64 validation failed after setup.
  exit /b 1
)

echo Using Python: "%SelectedPython%"
"%SelectedPython%" "%Helper%" --bundle-root "%BundleRoot%"
set "InstallExit=%ERRORLEVEL%"
if not "%InstallExit%"=="0" (
  echo ERROR: Offline installation failed. See "%LogFile%". 1>&2
  exit /b %InstallExit%
)

echo.
echo Installation succeeded. Log: "%LogFile%"
exit /b 0

:FindPython312
set "SelectedPython="
if defined LocalAppData if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  "%LocalAppData%\Programs\Python\Python312\python.exe" "%Helper%" --probe >nul 2>&1
  if not errorlevel 1 set "SelectedPython=%LocalAppData%\Programs\Python\Python312\python.exe"
)
if defined SelectedPython exit /b 0
rem Some Python Launcher versions print "Python 3.12 not found!" to stdout.
rem Accept captured output only when it names an existing executable.
for /f "usebackq delims=" %%P in (`py.exe -3.12 "%Helper%" --probe 2^>nul`) do if not defined SelectedPython if exist "%%P" set "SelectedPython=%%P"
if defined SelectedPython exit /b 0
for /f "usebackq delims=" %%P in (`python.exe "%Helper%" --probe 2^>nul`) do if not defined SelectedPython if exist "%%P" set "SelectedPython=%%P"
exit /b 0
