<# Run only from install_offline.cmd after every bundled payload is verified and locked. #>

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($env:DICOMXPHITS_VERIFIED_STAGE)) {
    throw "Refusing to run the offline installation stage without verified bootstrap state."
}

$BundleRoot = [System.IO.Path]::GetFullPath($env:DICOMXPHITS_BUNDLE_ROOT)
$BundlePrefix = $BundleRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
$Helper = Join-Path $BundleRoot "tools\offline_install.py"
$Installer = Join-Path $BundleRoot "python\python-3.12.10-amd64.exe"
$LogFile = Join-Path $BundleRoot "offline-install.log"
$InstallerLog = Join-Path $BundleRoot "python-installer.log"
$LockedPythonFiles = New-Object System.Collections.Generic.List[System.IO.Stream]

function Write-InstallLog([string]$Message) {
    Add-Content -LiteralPath $LogFile -Encoding UTF8 -Value $Message
}

function Assert-NoReparsePath([string]$Path, [string]$Label) {
    $Full = [System.IO.Path]::GetFullPath($Path)
    $Cursor = if ([System.IO.Directory]::Exists($Full)) {
        [System.IO.DirectoryInfo]$Full
    }
    else {
        [System.IO.DirectoryInfo][System.IO.Path]::GetDirectoryName($Full)
    }
    while ($null -ne $Cursor) {
        if (($Cursor.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "$Label contains a symbolic link, junction, or reparse point: $($Cursor.FullName)"
        }
        $Cursor = $Cursor.Parent
    }
    if ([System.IO.File]::Exists($Full)) {
        if (([System.IO.File]::GetAttributes($Full) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "$Label is a symbolic link or reparse point: $Full"
        }
    }
}

function Test-UnderAllowedPythonRoot([string]$Candidate) {
    $AllowedRoots = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:LocalAppData)) {
        $AllowedRoots.Add([System.IO.Path]::GetFullPath((Join-Path $env:LocalAppData "Programs\Python")))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
        $AllowedRoots.Add([System.IO.Path]::GetFullPath($env:ProgramFiles))
    }
    if (-not [string]::IsNullOrWhiteSpace(${env:ProgramFiles(x86)})) {
        $AllowedRoots.Add([System.IO.Path]::GetFullPath(${env:ProgramFiles(x86)}))
    }
    $Full = [System.IO.Path]::GetFullPath($Candidate)
    foreach ($AllowedRoot in $AllowedRoots) {
        $Prefix = $AllowedRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
        if ($Full.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Get-PythonCandidates {
    $Candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:LocalAppData)) {
        $Candidates.Add((Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"))
    }
    foreach ($Hive in @("HKCU:\Software\Python\PythonCore\3.12\InstallPath", "HKLM:\Software\Python\PythonCore\3.12\InstallPath", "HKLM:\Software\WOW6432Node\Python\PythonCore\3.12\InstallPath")) {
        try {
            $InstallPath = (Get-Item -LiteralPath $Hive -ErrorAction Stop).GetValue("")
            if (-not [string]::IsNullOrWhiteSpace([string]$InstallPath)) {
                $Candidates.Add((Join-Path ([string]$InstallPath) "python.exe"))
            }
        }
        catch {
            continue
        }
    }
    return $Candidates | Select-Object -Unique
}

function Select-Python312 {
    foreach ($CandidateValue in Get-PythonCandidates) {
        try {
            $Candidate = [System.IO.Path]::GetFullPath([string]$CandidateValue)
            if (-not [System.IO.File]::Exists($Candidate)) { continue }
            if (-not (Test-UnderAllowedPythonRoot $Candidate)) { continue }
            if ($Candidate.StartsWith($BundlePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            Assert-NoReparsePath $Candidate "Python executable path"

            $Stream = [System.IO.File]::Open($Candidate, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
            try {
                $Signature = Get-AuthenticodeSignature -LiteralPath $Candidate
                if ($Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) { continue }
                if ($null -eq $Signature.SignerCertificate -or [string]$Signature.SignerCertificate.Subject -notlike "*Python Software Foundation*") { continue }
                $Probe = & $Candidate -I -c "import json,struct,sys;print(json.dumps({'implementation':sys.implementation.name,'major':sys.version_info.major,'minor':sys.version_info.minor,'bits':struct.calcsize('P')*8}))" 2>$null
                if ($LASTEXITCODE -ne 0) { continue }
                $Data = ($Probe | Select-Object -Last 1) | ConvertFrom-Json
                if ($Data.implementation -ne "cpython" -or $Data.major -ne 3 -or $Data.minor -ne 12 -or $Data.bits -ne 64) { continue }
                $LockedPythonFiles.Add($Stream)
                $Stream = $null
                return $Candidate
            }
            finally {
                if ($null -ne $Stream) { $Stream.Dispose() }
            }
        }
        catch {
            continue
        }
    }
    return $null
}

try {
    Assert-NoReparsePath $BundleRoot "Bundle root"
    $SelectedPython = Select-Python312
    if ($null -eq $SelectedPython) {
        if (-not [System.IO.File]::Exists($Installer)) {
            throw "No trusted CPython 3.12 x64 installation was found and the verified bundled installer is missing."
        }
        Write-Host "No trusted existing CPython 3.12 x64 was found."
        Write-Host "Installing the verified bundled Python 3.12.10 for the current user..."
        Write-InstallLog "Starting verified bundled Python 3.12.10 current-user installation."
        & $Installer /quiet /log $InstallerLog InstallAllUsers=0 Include_pip=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_tcltk=1 Include_test=0 Include_doc=0 PrependPath=0 AssociateFiles=0 Shortcuts=0
        if ($LASTEXITCODE -ne 0) {
            throw "Bundled Python installer failed with exit code $LASTEXITCODE. See $InstallerLog"
        }
        $SelectedPython = Select-Python312
    }
    if ($null -eq $SelectedPython) {
        throw "Python setup completed but a trusted CPython 3.12 x64 executable could not be validated."
    }

    Write-Host "Using Python: $SelectedPython"
    Write-InstallLog "Initial bundle SHA-256 verification passed; protected payloads remained locked."
    & $SelectedPython -I $Helper --bundle-root $BundleRoot
    $InstallExit = $LASTEXITCODE
    if ($InstallExit -ne 0) {
        throw "Offline installation helper failed with exit code $InstallExit. See $LogFile"
    }
    Write-Host ""
    Write-Host "Installation succeeded. Log: $LogFile"
    exit 0
}
finally {
    foreach ($Stream in $LockedPythonFiles) { $Stream.Dispose() }
}
