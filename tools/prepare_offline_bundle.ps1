<#
.SYNOPSIS
Build the dicomxphits Windows x64 offline-installation ZIP.

.DESCRIPTION
Run this script on an internet-connected Windows computer from a reviewed Git
worktree. It downloads the authenticated application-local CPython 3.12.10 x64
runtime sources and the binary wheels resolved from the reviewed lock.
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
$PythonNuGetName = "python.$PythonVersion.nupkg"
$PythonNuGetUrl = "https://api.nuget.org/v3-flatcontainer/python/$PythonVersion/$PythonNuGetName"
$PythonNuGetSignerSha256 = "1F4B311D9ACC115C8DC8018B5A49E00FCE6DA8E2855F9F014CA6F34570BC482D"
$TclTkMsiName = "tcltk.msi"
$TclTkMsiUrl = "https://www.python.org/ftp/python/$PythonVersion/amd64/tcltk.msi"
$NuGetVersion = "7.9.0"
$NuGetName = "nuget.exe"
$NuGetUrl = "https://dist.nuget.org/win-x86-commandline/v$NuGetVersion/nuget.exe"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$PyprojectPath = Join-Path $RepoRoot "pyproject.toml"
$OfflineLockPath = Join-Path $RepoRoot "requirements\offline-win64.txt"
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

function Get-ValidatedAuthenticodeRecord {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedSigner
    )

    $HashBefore = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    $Signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
        throw "$Label Authenticode validation failed: $($Signature.Status) $($Signature.StatusMessage)"
    }
    if ($null -eq $Signature.SignerCertificate) {
        throw "$Label has no Authenticode signer certificate."
    }
    $SignerSubject = [string]$Signature.SignerCertificate.Subject
    if ($SignerSubject -notlike "*$ExpectedSigner*") {
        throw "Unexpected $Label signer: $SignerSubject"
    }
    $HashAfter = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($HashAfter -ne $HashBefore) {
        throw "$Label changed during Authenticode validation."
    }
    $TimestampSubject = $null
    if ($null -ne $Signature.TimeStamperCertificate) {
        $TimestampSubject = [string]$Signature.TimeStamperCertificate.Subject
    }
    return [ordered]@{
        status = [string]$Signature.Status
        status_message = [string]$Signature.StatusMessage
        signer_subject = $SignerSubject
        signer_thumbprint = [string]$Signature.SignerCertificate.Thumbprint
        signer_not_before = $Signature.SignerCertificate.NotBefore.ToUniversalTime().ToString("o")
        signer_not_after = $Signature.SignerCertificate.NotAfter.ToUniversalTime().ToString("o")
        timestamp_signer_subject = $TimestampSubject
        sha256 = $HashAfter
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
$PythonNuGet = Join-Path $DownloadRoot $PythonNuGetName
$TclTkMsi = Join-Path $DownloadRoot $TclTkMsiName
$NuGetCli = Join-Path $DownloadRoot $NuGetName
$RuntimeMetadata = Join-Path $WorkRoot "python-runtime-provenance.json"

try {
    New-Item -ItemType Directory -Path $DownloadRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $Wheelhouse -Force | Out-Null

    Write-Host "Downloading authenticated application-local CPython runtime sources..."
    Invoke-WebRequest -UseBasicParsing -Uri $PythonNuGetUrl -OutFile $PythonNuGet
    Invoke-WebRequest -UseBasicParsing -Uri $TclTkMsiUrl -OutFile $TclTkMsi
    Invoke-WebRequest -UseBasicParsing -Uri $NuGetUrl -OutFile $NuGetCli

    $NuGetRecord = Get-ValidatedAuthenticodeRecord -Path $NuGetCli -Label "NuGet CLI" -ExpectedSigner "Microsoft Corporation"
    $NuGetFileVersion = [string](Get-Item -LiteralPath $NuGetCli).VersionInfo.FileVersion
    if (-not $NuGetFileVersion.StartsWith("$NuGetVersion.", [System.StringComparison]::Ordinal)) {
        throw "NuGet CLI version is not ${NuGetVersion}: $NuGetFileVersion"
    }
    $NuGetRecord["version"] = $NuGetVersion
    $NuGetRecord["file_version"] = $NuGetFileVersion
    $NuGetRecord["url"] = $NuGetUrl

    $TclTkRecord = Get-ValidatedAuthenticodeRecord -Path $TclTkMsi -Label "CPython Tcl/Tk MSI" -ExpectedSigner "Python Software Foundation"
    $TclTkRecord["url"] = $TclTkMsiUrl

    $PythonHashBeforeSignature = (Get-FileHash -LiteralPath $PythonNuGet -Algorithm SHA256).Hash.ToLowerInvariant()
    $PreviousRevocationMode = $env:NUGET_CERT_REVOCATION_MODE
    $PreviousLocation = Get-Location
    try {
        $env:NUGET_CERT_REVOCATION_MODE = "online"
        Set-Location -LiteralPath $DownloadRoot
        $NuGetVerification = @(
            & $NuGetCli verify -Signatures $PythonNuGet `
                -CertificateFingerprint $PythonNuGetSignerSha256 `
                -NonInteractive -ForceEnglishOutput 2>&1
        )
        $NuGetExit = $LASTEXITCODE
    }
    finally {
        Set-Location -LiteralPath $PreviousLocation.ProviderPath
        if ($null -eq $PreviousRevocationMode) {
            Remove-Item Env:NUGET_CERT_REVOCATION_MODE -ErrorAction SilentlyContinue
        }
        else {
            $env:NUGET_CERT_REVOCATION_MODE = $PreviousRevocationMode
        }
    }
    if ($NuGetExit -ne 0) {
        throw "Python NuGet repository signature validation failed: $($NuGetVerification -join [Environment]::NewLine)"
    }
    $PythonHashAfterSignature = (Get-FileHash -LiteralPath $PythonNuGet -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($PythonHashAfterSignature -ne $PythonHashBeforeSignature) {
        throw "Python NuGet package changed during signature validation."
    }
    $VerificationText = $NuGetVerification -join [Environment]::NewLine
    if ($VerificationText -notmatch "Successfully verified package 'python\.3\.12\.10'\.") {
        throw "NuGet verification did not confirm the expected Python package identity."
    }
    $PythonNuGetRecord = [ordered]@{
        status = "Valid"
        signature_type = "Repository"
        signer_subject = "CN=NuGet.org Repository by Microsoft"
        signer_sha256 = $PythonNuGetSignerSha256
        package_id = "python"
        version = $PythonVersion
        sha256 = $PythonHashAfterSignature
        url = $PythonNuGetUrl
    }
    $RuntimeRecord = [ordered]@{
        schema_version = 1
        nuget_cli = $NuGetRecord
        python_nuget = $PythonNuGetRecord
        tcltk_msi = $TclTkRecord
    }
    $RuntimeRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $RuntimeMetadata -Encoding UTF8
    Write-Host "Application-local CPython runtime source signatures: Valid"

    Write-Host "Downloading hash-locked binary-only CPython 3.12 Windows x64 wheels..."
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
        "cp312",
        "--require-hashes",
        "--requirement",
        $OfflineLockPath
    ))

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
        "--python-nuget",
        $PythonNuGet,
        "--tcltk-msi",
        $TclTkMsi,
        "--nuget-cli",
        $NuGetCli,
        "--runtime-metadata",
        $RuntimeMetadata,
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
