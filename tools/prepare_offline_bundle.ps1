<#
.SYNOPSIS
Build the dicomxphits Windows x64 offline-installation ZIP.

.DESCRIPTION
Run this script on an internet-connected Windows computer from a reviewed Git
worktree. It downloads only the official CPython 3.12.10 x64 installer and the
binary wheels resolved from pyproject.toml plus setuptools and wheel.
#>

[CmdletBinding()]
param(
    [Parameter()]
    [string]$PythonExe,

    [Parameter()]
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$PythonVersion = "3.12.10"
$PythonInstallerName = "python-$PythonVersion-amd64.exe"
$PythonInstallerUrl = "https://www.python.org/ftp/python/$PythonVersion/$PythonInstallerName"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$PyprojectPath = Join-Path $RepoRoot "pyproject.toml"
$HelperPath = Join-Path $RepoRoot "tools\offline_bundle.py"
$DistRoot = Join-Path $RepoRoot "dist"

function Resolve-ProducerPython {
    $Candidates = @()
    if ($PythonExe) {
        $Candidates += [pscustomobject]@{
            Executable = $PythonExe
            Prefix = @()
        }
    }
    else {
        $PyCommand = Get-Command "py.exe" -ErrorAction SilentlyContinue
        if ($null -ne $PyCommand) {
            $Candidates += [pscustomobject]@{
                Executable = $PyCommand.Source
                Prefix = @("-3.12")
            }
        }
        $PythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
        if ($null -ne $PythonCommand) {
            $Candidates += [pscustomobject]@{
                Executable = $PythonCommand.Source
                Prefix = @()
            }
        }
    }

    foreach ($Candidate in $Candidates) {
        $Probe = & $Candidate.Executable @($Candidate.Prefix) -c `
            "import struct,sys; print('ok' if sys.version_info[:2] == (3, 12) and struct.calcsize('P') * 8 == 64 else 'unsupported')" `
            2>$null
        if ($LASTEXITCODE -eq 0 -and ($Probe | Select-Object -Last 1) -eq "ok") {
            return $Candidate
        }
    }
    throw "A local CPython 3.12 x64 with pip is required to prepare the bundle. Specify -PythonExe if it is not discoverable."
}

function Invoke-ProducerPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter()]
        [switch]$Capture
    )

    if ($Capture) {
        $Output = & $script:ProducerPython.Executable @($script:ProducerPython.Prefix) @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Producer Python command failed with exit code $LASTEXITCODE."
        }
        return $Output
    }

    & $script:ProducerPython.Executable @($script:ProducerPython.Prefix) @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Producer Python command failed with exit code $LASTEXITCODE."
    }
}

if ($env:OS -ne "Windows_NT") {
    throw "Offline bundle preparation is supported only on Windows because Authenticode validation is required."
}
if (-not (Test-Path -LiteralPath $PyprojectPath -PathType Leaf)) {
    throw "pyproject.toml is missing from the repository root."
}
if (-not (Test-Path -LiteralPath $HelperPath -PathType Leaf)) {
    throw "Offline bundle helper is missing: $HelperPath"
}

$script:ProducerPython = Resolve-ProducerPython
Write-Host "Producer Python: $($script:ProducerPython.Executable) $($script:ProducerPython.Prefix -join ' ')"

$MetadataJson = Invoke-ProducerPython -Capture -Arguments @(
    $HelperPath,
    "metadata",
    "--repo-root",
    $RepoRoot
)
$Metadata = ($MetadataJson -join [Environment]::NewLine) | ConvertFrom-Json
$Version = [string]$Metadata.version
if ([string]::IsNullOrWhiteSpace($Version)) {
    throw "Project version is missing from pyproject.toml."
}

New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null
$OutputZip = Join-Path $DistRoot "dicomxphits-offline-win64-$Version.zip"
if (Test-Path -LiteralPath $OutputZip) {
    if (-not $Force) {
        throw "Output ZIP already exists: $OutputZip. Rerun with -Force only after confirming it may be replaced."
    }
    Remove-Item -LiteralPath $OutputZip -Force
}

$WorkRoot = Join-Path $DistRoot (".offline-bundle-work-" + [Guid]::NewGuid().ToString("N"))
$DownloadRoot = Join-Path $WorkRoot "downloads"
$Wheelhouse = Join-Path $WorkRoot "wheelhouse"
$PythonInstaller = Join-Path $DownloadRoot $PythonInstallerName
$SignatureMetadata = Join-Path $WorkRoot "python-authenticode.json"

try {
    New-Item -ItemType Directory -Path $DownloadRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $Wheelhouse -Force | Out-Null

    Write-Host "Downloading official CPython $PythonVersion x64 installer..."
    Invoke-WebRequest -UseBasicParsing -Uri $PythonInstallerUrl -OutFile $PythonInstaller

    $InstallerHashBeforeSignature = (Get-FileHash -LiteralPath $PythonInstaller -Algorithm SHA256).Hash.ToLowerInvariant()
    $Signature = Get-AuthenticodeSignature -LiteralPath $PythonInstaller
    if ($Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
        throw "Python installer Authenticode validation failed: $($Signature.Status) $($Signature.StatusMessage)"
    }
    if ($null -eq $Signature.SignerCertificate) {
        throw "Python installer has no Authenticode signer certificate."
    }
    $SignerSubject = [string]$Signature.SignerCertificate.Subject
    if ($SignerSubject -notlike "*Python Software Foundation*") {
        throw "Unexpected Python installer signer: $SignerSubject"
    }
    $TimestampSubject = $null
    if ($null -ne $Signature.TimeStamperCertificate) {
        $TimestampSubject = [string]$Signature.TimeStamperCertificate.Subject
    }
    $InstallerHash = (Get-FileHash -LiteralPath $PythonInstaller -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($InstallerHash -ne $InstallerHashBeforeSignature) {
        throw "Python installer changed during Authenticode validation."
    }
    $AuthenticodeRecord = [ordered]@{
        status = [string]$Signature.Status
        status_message = [string]$Signature.StatusMessage
        signer_subject = $SignerSubject
        signer_thumbprint = [string]$Signature.SignerCertificate.Thumbprint
        signer_not_before = $Signature.SignerCertificate.NotBefore.ToUniversalTime().ToString("o")
        signer_not_after = $Signature.SignerCertificate.NotAfter.ToUniversalTime().ToString("o")
        timestamp_signer_subject = $TimestampSubject
        installer_sha256 = $InstallerHash
    }
    $AuthenticodeRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $SignatureMetadata -Encoding UTF8
    Write-Host "Python installer Authenticode: Valid"
    Write-Host "Python installer SHA-256: $InstallerHash"

    $Requirements = @($Metadata.dependencies) + @("setuptools", "wheel")
    Write-Host "Downloading binary-only CPython 3.12 Windows x64 wheels..."
    Invoke-ProducerPython -Arguments (@(
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--dest",
        $Wheelhouse,
        "--only-binary=:all:",
        "--platform",
        "win_amd64",
        "--python-version",
        "3.12",
        "--implementation",
        "cp",
        "--abi",
        "cp312"
    ) + $Requirements)

    Invoke-ProducerPython -Arguments @(
        $HelperPath,
        "validate-wheels",
        "--repo-root",
        $RepoRoot,
        "--wheelhouse",
        $Wheelhouse
    ) | Out-Null

    Write-Host "Building tracked-public-source bundle..."
    $BuildResultJson = Invoke-ProducerPython -Capture -Arguments @(
        $HelperPath,
        "build",
        "--repo-root",
        $RepoRoot,
        "--wheelhouse",
        $Wheelhouse,
        "--python-installer",
        $PythonInstaller,
        "--signature-metadata",
        $SignatureMetadata,
        "--output-zip",
        $OutputZip
    )
    $BuildResult = ($BuildResultJson -join [Environment]::NewLine) | ConvertFrom-Json
    Write-Host "Offline bundle created: $($BuildResult.output_zip)"
    Write-Host "ZIP SHA-256: $($BuildResult.output_sha256)"
    Write-Host "Wheels: $($BuildResult.wheel_count); public source files: $($BuildResult.source_file_count)"
}
finally {
    if (Test-Path -LiteralPath $WorkRoot) {
        $ResolvedWork = [System.IO.Path]::GetFullPath($WorkRoot)
        $ResolvedDist = [System.IO.Path]::GetFullPath($DistRoot).TrimEnd("\") + "\"
        if (-not $ResolvedWork.StartsWith($ResolvedDist, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean a work directory outside dist: $ResolvedWork"
        }
        Remove-Item -LiteralPath $ResolvedWork -Recurse -Force
    }
}
