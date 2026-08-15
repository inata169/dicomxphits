<# Remove one exact verified offline installation without discovering candidates. #>

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RuntimeIdentitySchema = "bundle-root-manifest-v1"
$BundleRoot = [System.IO.Path]::GetFullPath($env:DICOMXPHITS_BUNDLE_ROOT)
$BundlePrefix = $BundleRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
$ManifestPath = Join-Path $BundleRoot "bundle-manifest.json"
$ChecksumPath = Join-Path $BundleRoot "SHA256SUMS.txt"
$ProtectedRuntimeParent = $null
$ProtectedRuntimeId = $null
$RuntimeRoot = $null
$ProtectedSourceRoot = $null
$ProtectedRuntimeReceipt = $null
$RuntimeLog = $null
$FailureDiagnostic = $null
$CleanupDirectory = $null
$InstallingUserSid = $null
$BundleManifestSha256 = $null
$AdministratorsSid = New-Object System.Security.Principal.SecurityIdentifier(
    [System.Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,
    $null
)
$SystemSid = New-Object System.Security.Principal.SecurityIdentifier(
    [System.Security.Principal.WellKnownSidType]::LocalSystemSid,
    $null
)
$OwnerRightsSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-3-4")

if ($null -eq ("Dicomxphits.OfflineUninstallNative" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace Dicomxphits {
    public static class OfflineUninstallNative {
        [StructLayout(LayoutKind.Sequential)]
        private struct FileDispositionInfo {
            [MarshalAs(UnmanagedType.Bool)]
            public bool DeleteFile;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern SafeFileHandle CreateFile(
            string fileName,
            uint desiredAccess,
            FileShare shareMode,
            IntPtr securityAttributes,
            FileMode creationDisposition,
            uint flagsAndAttributes,
            IntPtr templateFile
        );

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetFileInformationByHandle(
            SafeFileHandle fileHandle,
            int fileInformationClass,
            ref FileDispositionInfo fileInformation,
            uint bufferSize
        );

        public static bool MarkDeletePending(SafeFileHandle fileHandle) {
            FileDispositionInfo information = new FileDispositionInfo {
                DeleteFile = true
            };
            return SetFileInformationByHandle(
                fileHandle,
                4,
                ref information,
                (uint)Marshal.SizeOf(information)
            );
        }
    }
}
'@
}
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Test-IsAdministrator {
    $Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object System.Security.Principal.WindowsPrincipal -ArgumentList $Identity
    return $Principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Assert-TrustedPowerShellProcess {
    $Trusted = [System.IO.Path]::Combine(
        [System.Environment]::SystemDirectory,
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe"
    )
    $Current = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    if (-not [string]::Equals(
        [System.IO.Path]::GetFullPath($Current),
        [System.IO.Path]::GetFullPath($Trusted),
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Uninstaller is not running in the trusted Windows PowerShell executable."
    }
    return $Trusted
}

function Get-FileSha256([string]$Path) {
    $Stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    $Sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [System.BitConverter]::ToString(
            $Sha256.ComputeHash($Stream)
        ).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $Sha256.Dispose()
        $Stream.Dispose()
    }
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
    if (
        ([System.IO.File]::Exists($Full) -or [System.IO.Directory]::Exists($Full)) -and
        (([System.IO.File]::GetAttributes($Full) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
    ) {
        throw "$Label is a symbolic link, junction, or reparse point: $Full"
    }
}

function Get-ProtectedRuntimeSecurity([bool]$IsDirectory) {
    if ($null -eq $InstallingUserSid) { throw "Installing-user identity is unavailable." }
    $Security = if ($IsDirectory) {
        New-Object System.Security.AccessControl.DirectorySecurity
    }
    else {
        New-Object System.Security.AccessControl.FileSecurity
    }
    $Security.SetAccessRuleProtection($true, $false)
    $Security.SetOwner($AdministratorsSid)
    $Inheritance = if ($IsDirectory) {
        [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
            [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    }
    else { [System.Security.AccessControl.InheritanceFlags]::None }
    foreach ($Rule in @(
        @($SystemSid, [System.Security.AccessControl.FileSystemRights]::FullControl),
        @($AdministratorsSid, [System.Security.AccessControl.FileSystemRights]::FullControl),
        @($InstallingUserSid, [System.Security.AccessControl.FileSystemRights]::ReadAndExecute),
        @($OwnerRightsSid, [System.Security.AccessControl.FileSystemRights]::ReadAndExecute)
    )) {
        $Security.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            $Rule[0],
            $Rule[1],
            $Inheritance,
            [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow
        )))
    }
    return $Security
}

function Assert-ProtectedSecurity([string]$Path, [bool]$IsDirectory, [string]$Label) {
    $Actual = if ($IsDirectory) {
        [System.IO.Directory]::GetAccessControl(
            $Path,
            [System.Security.AccessControl.AccessControlSections]::Owner -bor
                [System.Security.AccessControl.AccessControlSections]::Access
        )
    }
    else {
        [System.IO.File]::GetAccessControl(
            $Path,
            [System.Security.AccessControl.AccessControlSections]::Owner -bor
                [System.Security.AccessControl.AccessControlSections]::Access
        )
    }
    $Expected = Get-ProtectedRuntimeSecurity $IsDirectory
    function Get-RuleSignatures($Security) {
        return @(
            $Security.GetAccessRules(
                $true,
                $false,
                [System.Security.Principal.SecurityIdentifier]
            ) | ForEach-Object {
                [string]::Join("|", @(
                    $_.IdentityReference.Value,
                    [int64]$_.FileSystemRights,
                    [int]$_.InheritanceFlags,
                    [int]$_.PropagationFlags,
                    [int]$_.AccessControlType
                ))
            } | Sort-Object
        )
    }
    $ActualOwner = $Actual.GetOwner([System.Security.Principal.SecurityIdentifier])
    $ExpectedOwner = $Expected.GetOwner([System.Security.Principal.SecurityIdentifier])
    $Inherited = @($Actual.GetAccessRules(
        $false,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    ))
    $ActualRules = @(Get-RuleSignatures $Actual)
    $ExpectedRules = @(Get-RuleSignatures $Expected)
    if (
        $ActualOwner.Value -ne $ExpectedOwner.Value -or
        -not $Actual.AreAccessRulesProtected -or
        $Inherited.Count -ne 0 -or
        [string]::Join("`n", $ActualRules) -ne [string]::Join("`n", $ExpectedRules)
    ) {
        throw "$Label does not have the exact protected owner and access rules: $Path"
    }
}

function Get-ProtectedRuntimeId([string]$Root, [string]$ManifestSha256) {
    if ($ManifestSha256 -notmatch "^[0-9a-f]{64}$") {
        throw "Verified bundle manifest SHA-256 is missing or malformed."
    }
    $IdentityText = [string]::Join("`n", @(
        $RuntimeIdentitySchema,
        ([System.IO.Path]::GetFullPath($Root)).ToUpperInvariant(),
        $ManifestSha256.ToLowerInvariant()
    ))
    $Sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [System.BitConverter]::ToString(
            $Sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($IdentityText))
        ).Replace("-", "").ToLowerInvariant()
    }
    finally { $Sha256.Dispose() }
}

function Get-VerifiedManifestIdentity {
    Assert-NoReparsePath $BundleRoot "Bundle root"
    if (-not [System.IO.File]::Exists($ManifestPath)) {
        throw "Bundle manifest is missing: $ManifestPath"
    }
    if (-not [System.IO.File]::Exists($ChecksumPath)) {
        throw "Checksum inventory is missing: $ChecksumPath"
    }
    Assert-NoReparsePath $ManifestPath "Bundle manifest"
    Assert-NoReparsePath $ChecksumPath "Checksum inventory"
    $ManifestDigest = Get-FileSha256 $ManifestPath
    $ManifestLine = @(
        [System.IO.File]::ReadAllLines($ChecksumPath, [System.Text.Encoding]::UTF8) |
            Where-Object { $_ -eq "$ManifestDigest *bundle-manifest.json" }
    )
    if ($ManifestLine.Count -ne 1) {
        throw "Checksum inventory does not bind the current bundle manifest."
    }
    return $ManifestDigest
}

function Set-ProtectedRuntimeIdentity([string]$SidValue) {
    try {
        $script:InstallingUserSid = New-Object System.Security.Principal.SecurityIdentifier(
            $SidValue
        )
    }
    catch { throw "Installing-user SID is invalid." }
    $CommonData = [System.Environment]::GetFolderPath(
        [System.Environment+SpecialFolder]::CommonApplicationData
    )
    if ([string]::IsNullOrWhiteSpace($CommonData)) {
        throw "Windows Common Application Data is unavailable."
    }
    Assert-NoReparsePath $CommonData "Windows Common Application Data"
    $RuntimeParent = Join-Path (Join-Path $CommonData "dicomxphits") "offline-runtimes"
    $RuntimeId = Get-ProtectedRuntimeId $BundleRoot $BundleManifestSha256
    $script:ProtectedRuntimeParent = $RuntimeParent
    $script:ProtectedRuntimeId = $RuntimeId
    $script:RuntimeRoot = Join-Path $RuntimeParent $RuntimeId
    $script:ProtectedSourceRoot = Join-Path $script:RuntimeRoot "dicomxphits-source"
    $script:ProtectedRuntimeReceipt = Join-Path $RuntimeParent "$RuntimeId.json"
    $script:RuntimeLog = Join-Path $RuntimeParent "$RuntimeId-msi.log"
    $script:FailureDiagnostic = Join-Path $RuntimeParent "$RuntimeId-failure.json"
}

function Import-ExactProtectedReceipt {
    if (-not [System.IO.File]::Exists($ProtectedRuntimeReceipt)) {
        throw "Matching protected runtime receipt is missing: $ProtectedRuntimeReceipt"
    }
    Assert-NoReparsePath $ProtectedRuntimeReceipt "Protected runtime receipt"
    Assert-ProtectedSecurity $ProtectedRuntimeReceipt $false "Protected runtime receipt"
    $Receipt = [System.IO.File]::ReadAllText(
        $ProtectedRuntimeReceipt,
        [System.Text.Encoding]::UTF8
    ) | ConvertFrom-Json
    if (
        $Receipt.schema_version -ne 1 -or
        [string]$Receipt.runtime_identity_schema -ne $RuntimeIdentitySchema -or
        [string]$Receipt.bundle_manifest_sha256 -ne $BundleManifestSha256 -or
        -not [string]::Equals([string]$Receipt.bundle_root, $BundleRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals([string]$Receipt.runtime_root, $RuntimeRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals([string]$Receipt.protected_source_root, $ProtectedSourceRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]$Receipt.installing_user_sid -ne $InstallingUserSid.Value
    ) {
        throw "Protected runtime receipt does not identify this exact installation."
    }
    if (-not [System.IO.Directory]::Exists($RuntimeRoot)) {
        throw "Matching protected runtime is missing: $RuntimeRoot"
    }
    Assert-NoReparsePath $RuntimeRoot "Protected runtime"
    Assert-ProtectedSecurity $RuntimeRoot $true "Protected runtime"
    return $Receipt
}

function Get-ManifestRecords([string]$ProtectedManifestPath) {
    if ((Get-FileSha256 $ProtectedManifestPath) -ne $BundleManifestSha256) {
        throw "Protected manifest does not match the installed bundle identity."
    }
    $Manifest = [System.IO.File]::ReadAllText(
        $ProtectedManifestPath,
        [System.Text.Encoding]::UTF8
    ) | ConvertFrom-Json
    if ($Manifest.schema_version -ne 1 -or $null -eq $Manifest.files) {
        throw "Protected bundle manifest is malformed."
    }
    return @($Manifest.files)
}

function Add-ExpectedVenvDirectory(
    [string]$Path,
    [string]$VenvRoot,
    [System.Collections.Generic.HashSet[string]]$ExpectedDirectories
) {
    $Full = [System.IO.Path]::GetFullPath($Path)
    $Prefix = $VenvRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
        [System.IO.Path]::DirectorySeparatorChar
    if (
        -not [string]::Equals($Full, $VenvRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        -not $Full.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)
    ) { throw "Generated virtual-environment path escaped .venv: $Full" }
    $null = $ExpectedDirectories.Add($Full)
}

function Add-ExpectedVenvFile(
    [string]$Path,
    [string]$VenvRoot,
    [System.Collections.Generic.HashSet[string]]$ExpectedFiles,
    [System.Collections.Generic.HashSet[string]]$ExpectedDirectories
) {
    $Full = [System.IO.Path]::GetFullPath($Path)
    $Prefix = $VenvRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
        [System.IO.Path]::DirectorySeparatorChar
    if (-not $Full.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Generated virtual-environment file escaped .venv: $Full"
    }
    $null = $ExpectedFiles.Add($Full)
    $Cursor = [System.IO.Path]::GetDirectoryName($Full)
    while (
        [string]::Equals($Cursor, $VenvRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $Cursor.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        $null = $ExpectedDirectories.Add($Cursor)
        if ([string]::Equals($Cursor, $VenvRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $Cursor = [System.IO.Path]::GetDirectoryName($Cursor)
    }
}

function Read-ZipEntryText([System.IO.Compression.ZipArchiveEntry]$Entry) {
    $Stream = $Entry.Open()
    $Reader = New-Object System.IO.StreamReader(
        $Stream,
        [System.Text.Encoding]::UTF8,
        $true,
        4096,
        $false
    )
    try { return $Reader.ReadToEnd() }
    finally { $Reader.Dispose() }
}

function Add-TrustedWheelVenvPaths(
    [string]$WheelPath,
    [string]$VenvRoot,
    [System.Collections.Generic.HashSet[string]]$ExpectedFiles,
    [System.Collections.Generic.HashSet[string]]$ExpectedDirectories
) {
    Assert-NoReparsePath $WheelPath "Authenticated virtual-environment wheel"
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($WheelPath)
    try {
        $RecordEntries = @($Archive.Entries | Where-Object {
            $_.FullName -match '^[^/]+\.dist-info/RECORD$'
        })
        if ($RecordEntries.Count -ne 1) {
            throw "Authenticated wheel has no unique RECORD inventory: $WheelPath"
        }
        $Rows = @(Read-ZipEntryText $RecordEntries[0] | ConvertFrom-Csv -Header Path,Hash,Size)
        foreach ($Row in $Rows) {
            $Relative = [string]$Row.Path
            if (
                [string]::IsNullOrWhiteSpace($Relative) -or
                [System.IO.Path]::IsPathRooted($Relative) -or
                $Relative.Contains(":") -or
                $Relative.Split('/') -contains ".."
            ) { throw "Authenticated wheel contains an unsafe RECORD path: $Relative" }
            $DestinationRelative = $Relative
            if ($Relative -match '^[^/]+\.data/(purelib|platlib)/(.+)$') {
                $DestinationRelative = $Matches[2]
            }
            elseif ($Relative -match '^[^/]+\.data/scripts/(.+)$') {
                $Destination = Join-Path (Join-Path $VenvRoot "Scripts") $Matches[1].Replace(
                    "/",
                    [System.IO.Path]::DirectorySeparatorChar
                )
                Add-ExpectedVenvFile $Destination $VenvRoot $ExpectedFiles $ExpectedDirectories
                continue
            }
            elseif ($Relative -match '^[^/]+\.data/') {
                throw "Authenticated wheel uses an unsupported installation path: $Relative"
            }
            $Destination = Join-Path (Join-Path $VenvRoot "Lib\site-packages") (
                $DestinationRelative.Replace("/", [System.IO.Path]::DirectorySeparatorChar)
            )
            Add-ExpectedVenvFile $Destination $VenvRoot $ExpectedFiles $ExpectedDirectories
            if ([System.IO.Path]::GetExtension($Destination) -ieq ".py") {
                $Cache = Join-Path ([System.IO.Path]::GetDirectoryName($Destination)) "__pycache__"
                $Compiled = Join-Path $Cache (
                    [System.IO.Path]::GetFileNameWithoutExtension($Destination) + ".cpython-312.pyc"
                )
                Add-ExpectedVenvFile $Compiled $VenvRoot $ExpectedFiles $ExpectedDirectories
            }
        }
        foreach ($EntryPoint in @($Archive.Entries | Where-Object {
            $_.FullName -match '^[^/]+\.dist-info/entry_points\.txt$'
        })) {
            $InConsoleScripts = $false
            foreach ($Line in (Read-ZipEntryText $EntryPoint) -split "`r?`n") {
                $Trimmed = $Line.Trim()
                if ($Trimmed -match '^\[(.+)\]$') {
                    $InConsoleScripts = $Matches[1] -ieq "console_scripts"
                    continue
                }
                if ($InConsoleScripts -and $Trimmed -match '^([A-Za-z0-9_.-]+)\s*=') {
                    Add-ExpectedVenvFile `
                        (Join-Path (Join-Path $VenvRoot "Scripts") ($Matches[1] + ".exe")) `
                        $VenvRoot $ExpectedFiles $ExpectedDirectories
                }
            }
        }
        $DistInfo = [System.IO.Path]::GetDirectoryName(
            $RecordEntries[0].FullName.Replace("/", [System.IO.Path]::DirectorySeparatorChar)
        )
        if ([System.IO.Path]::GetFileName($DistInfo) -match '^pip-[^-]+\.dist-info$') {
            Add-ExpectedVenvFile `
                (Join-Path (Join-Path $VenvRoot "Scripts") "pip3.12.exe") `
                $VenvRoot $ExpectedFiles $ExpectedDirectories
        }
        foreach ($Name in @("INSTALLER", "REQUESTED")) {
            Add-ExpectedVenvFile `
                (Join-Path (Join-Path $VenvRoot "Lib\site-packages") (Join-Path $DistInfo $Name)) `
                $VenvRoot $ExpectedFiles $ExpectedDirectories
        }
    }
    finally { $Archive.Dispose() }
}

function Assert-ExactVenvTree([string]$VenvRoot, [object[]]$TrustedWheels, [string]$PyprojectPath) {
    if ([System.IO.File]::Exists($VenvRoot)) {
        throw "Installation-generated .venv path must be a directory: $VenvRoot"
    }
    if (-not [System.IO.Directory]::Exists($VenvRoot)) { return }
    $ExpectedFiles = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $ExpectedDirectories = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($Directory in @("", "Include", "Lib", "Lib\site-packages", "Scripts")) {
        Add-ExpectedVenvDirectory (Join-Path $VenvRoot $Directory) $VenvRoot $ExpectedDirectories
    }
    foreach ($Relative in @(
        "pyvenv.cfg",
        "Scripts\activate",
        "Scripts\activate.bat",
        "Scripts\Activate.ps1",
        "Scripts\deactivate.bat",
        "Scripts\python.exe",
        "Scripts\pythonw.exe"
    )) {
        Add-ExpectedVenvFile (Join-Path $VenvRoot $Relative) $VenvRoot $ExpectedFiles $ExpectedDirectories
    }
    foreach ($Wheel in $TrustedWheels) {
        Add-TrustedWheelVenvPaths $Wheel $VenvRoot $ExpectedFiles $ExpectedDirectories
    }

    $Pyproject = [System.IO.File]::ReadAllText($PyprojectPath, [System.Text.Encoding]::UTF8)
    $VersionMatch = [regex]::Match($Pyproject, '(?m)^version\s*=\s*"([^"]+)"\s*$')
    if (-not $VersionMatch.Success -or $VersionMatch.Groups[1].Value -notmatch '^[A-Za-z0-9_.+-]+$') {
        throw "Protected project metadata has no safe version for .venv validation."
    }
    $Version = $VersionMatch.Groups[1].Value
    $DistInfo = "dicomxphits-$Version.dist-info"
    foreach ($Relative in @(
        "__editable__.dicomxphits-$Version.pth",
        "$DistInfo\INSTALLER",
        "$DistInfo\METADATA",
        "$DistInfo\RECORD",
        "$DistInfo\REQUESTED",
        "$DistInfo\WHEEL",
        "$DistInfo\direct_url.json",
        "$DistInfo\entry_points.txt",
        "$DistInfo\licenses\LICENSE",
        "$DistInfo\top_level.txt"
    )) {
        Add-ExpectedVenvFile `
            (Join-Path (Join-Path $VenvRoot "Lib\site-packages") $Relative) `
            $VenvRoot $ExpectedFiles $ExpectedDirectories
    }
    $InScripts = $false
    foreach ($Line in $Pyproject -split "`r?`n") {
        $Trimmed = $Line.Trim()
        if ($Trimmed -match '^\[(.+)\]$') {
            $InScripts = $Matches[1] -ieq "project.scripts"
            continue
        }
        if ($InScripts -and $Trimmed -match '^([A-Za-z0-9_.-]+)\s*=') {
            Add-ExpectedVenvFile `
                (Join-Path (Join-Path $VenvRoot "Scripts") ($Matches[1] + ".exe")) `
                $VenvRoot $ExpectedFiles $ExpectedDirectories
        }
    }

    foreach ($Entry in [System.IO.Directory]::EnumerateFileSystemEntries(
        $VenvRoot,
        "*",
        [System.IO.SearchOption]::AllDirectories
    )) {
        $Full = [System.IO.Path]::GetFullPath($Entry)
        if (([System.IO.File]::GetAttributes($Full) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Installation contains a symbolic link, junction, or reparse point: $Full"
        }
        if ([System.IO.File]::Exists($Full)) {
            if (-not $ExpectedFiles.Contains($Full)) {
                throw "Installation .venv contains an unknown file; preserve or remove it before uninstalling: $Full"
            }
        }
        elseif ([System.IO.Directory]::Exists($Full)) {
            if (-not $ExpectedDirectories.Contains($Full)) {
                throw "Installation .venv contains an unknown directory; preserve or remove it before uninstalling: $Full"
            }
        }
        else { throw "Installation contains a non-regular .venv entry: $Full" }
    }
}

function Assert-ExactInstallationRoot {
    if (-not [System.IO.Directory]::Exists($BundleRoot)) {
        throw "Installation root is missing: $BundleRoot"
    }
    Assert-NoReparsePath $BundleRoot "Installation root"
    $ProtectedManifest = Join-Path $ProtectedSourceRoot "bundle-manifest.json"
    $ProtectedChecksums = Join-Path $ProtectedSourceRoot "SHA256SUMS.txt"
    foreach ($ProtectedPath in @($ProtectedManifest, $ProtectedChecksums)) {
        if (-not [System.IO.File]::Exists($ProtectedPath)) {
            throw "Protected uninstall evidence is missing: $ProtectedPath"
        }
        Assert-NoReparsePath $ProtectedPath "Protected uninstall evidence"
        Assert-ProtectedSecurity $ProtectedPath $false "Protected uninstall evidence"
    }
    $Records = Get-ManifestRecords $ProtectedManifest
    $ExpectedFiles = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $ExpectedDirectories = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $null = $ExpectedDirectories.Add($BundleRoot)
    foreach ($Record in $Records) {
        $Relative = ([string]$Record.path).Replace("/", [System.IO.Path]::DirectorySeparatorChar)
        if (
            [string]::IsNullOrWhiteSpace($Relative) -or
            [System.IO.Path]::IsPathRooted($Relative) -or
            $Relative.Contains(":") -or
            $Relative.Split([System.IO.Path]::DirectorySeparatorChar) -contains ".."
        ) { throw "Protected manifest contains an unsafe uninstall path: $Relative" }
        $Path = [System.IO.Path]::GetFullPath((Join-Path $BundleRoot $Relative))
        if (-not $Path.StartsWith($BundlePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Protected manifest uninstall path escaped the installation root: $Relative"
        }
        if (-not [System.IO.File]::Exists($Path)) {
            throw "Authenticated bundle payload is missing: $Relative"
        }
        Assert-NoReparsePath $Path "Authenticated bundle payload"
        if ((Get-FileSha256 $Path) -ne [string]$Record.sha256) {
            throw "Authenticated bundle payload was modified: $Relative"
        }
        $null = $ExpectedFiles.Add($Path)
        $Cursor = [System.IO.Path]::GetDirectoryName($Path)
        while ($Cursor.StartsWith($BundlePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            $null = $ExpectedDirectories.Add($Cursor)
            $Cursor = [System.IO.Path]::GetDirectoryName($Cursor)
        }
    }
    foreach ($Relative in @("bundle-manifest.json", "SHA256SUMS.txt")) {
        $RootPath = Join-Path $BundleRoot $Relative
        $ProtectedPath = Join-Path $ProtectedSourceRoot $Relative
        if (-not [System.IO.File]::Exists($RootPath) -or (Get-FileSha256 $RootPath) -ne (Get-FileSha256 $ProtectedPath)) {
            throw "Installed integrity evidence was modified: $Relative"
        }
        $null = $ExpectedFiles.Add([System.IO.Path]::GetFullPath($RootPath))
    }
    $VenvRoot = Join-Path $BundleRoot ".venv"
    $InstallLog = Join-Path $BundleRoot "offline-install.log"
    if ([System.IO.Directory]::Exists($InstallLog)) {
        throw "Installation-generated offline install log must be a regular file: $InstallLog"
    }
    $TrustedWheels = @(
        $Records | ForEach-Object {
            $Relative = ([string]$_.path).Replace("\", "/")
            if ($Relative -match '^wheelhouse/[^/]+\.whl$') {
                Join-Path $ProtectedSourceRoot $Relative.Replace(
                    "/",
                    [System.IO.Path]::DirectorySeparatorChar
                )
            }
        }
    )
    $EnsurePip = Join-Path $RuntimeRoot "Lib\ensurepip\_bundled"
    if ([System.IO.Directory]::Exists($EnsurePip)) {
        $TrustedWheels += @([System.IO.Directory]::GetFiles(
            $EnsurePip,
            "pip-*.whl",
            [System.IO.SearchOption]::TopDirectoryOnly
        ))
    }
    Assert-ExactVenvTree $VenvRoot $TrustedWheels (Join-Path $ProtectedSourceRoot "pyproject.toml")
    foreach ($Entry in [System.IO.Directory]::EnumerateFileSystemEntries(
        $BundleRoot,
        "*",
        [System.IO.SearchOption]::AllDirectories
    )) {
        $Full = [System.IO.Path]::GetFullPath($Entry)
        if (([System.IO.File]::GetAttributes($Full) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Installation contains a symbolic link, junction, or reparse point: $Full"
        }
        $AllowedGenerated =
            # Assert-ExactVenvTree has already checked every descendant against
            # the authenticated wheel and finite venv inventories.
            ([System.IO.Directory]::Exists($VenvRoot) -and (
                $Full.StartsWith(($VenvRoot + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase) -or
                [string]::Equals($Full, $VenvRoot, [System.StringComparison]::OrdinalIgnoreCase)
            )) -or
            ([System.IO.File]::Exists($InstallLog) -and
                [string]::Equals($Full, $InstallLog, [System.StringComparison]::OrdinalIgnoreCase))
        if ([System.IO.File]::Exists($Full)) {
            if (-not $ExpectedFiles.Contains($Full) -and -not $AllowedGenerated) {
                throw "Installation contains an unknown file; preserve or remove it before uninstalling: $Full"
            }
        }
        elseif ([System.IO.Directory]::Exists($Full)) {
            if (-not $ExpectedDirectories.Contains($Full) -and -not $AllowedGenerated) {
                throw "Installation contains an unknown directory; preserve or remove it before uninstalling: $Full"
            }
        }
        else { throw "Installation contains a non-regular entry: $Full" }
    }
}

function Assert-NoAssociatedProcesses {
    param(
        [int[]]$ExcludedProcessIds,
        [int]$BootstrapCallerProcessId = 0
    )
    $Excluded = New-Object 'System.Collections.Generic.HashSet[int]'
    foreach ($Id in $ExcludedProcessIds) { $null = $Excluded.Add($Id) }
    $RuntimePrefix = $RuntimeRoot.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    try { $Processes = @(Get-CimInstance Win32_Process -ErrorAction Stop) }
    catch { throw "Cannot verify that associated processes are stopped." }
    foreach ($Process in $Processes) {
        if ($Excluded.Contains([int]$Process.ProcessId)) { continue }
        if (
            $BootstrapCallerProcessId -gt 0 -and
            [int]$Process.ProcessId -eq $BootstrapCallerProcessId
        ) {
            $TrustedCmd = [System.IO.Path]::Combine(
                [System.Environment]::SystemDirectory,
                "cmd.exe"
            )
            $Uninstaller = Join-Path $BundleRoot "uninstall_offline.cmd"
            $UninstallerPattern = '(?:^|[\s"])' +
                [System.Text.RegularExpressions.Regex]::Escape($Uninstaller) +
                '(?=$|[\s"])'
            $CallerExecutable = [string]$Process.ExecutablePath
            $CallerCommandLine = [string]$Process.CommandLine
            if (
                -not [string]::IsNullOrWhiteSpace($CallerExecutable) -and
                [string]::Equals(
                    [System.IO.Path]::GetFullPath($CallerExecutable),
                    [System.IO.Path]::GetFullPath($TrustedCmd),
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -and
                -not [string]::IsNullOrWhiteSpace($CallerCommandLine) -and
                [System.Text.RegularExpressions.Regex]::IsMatch(
                    $CallerCommandLine,
                    $UninstallerPattern,
                    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
                )
            ) { continue }
        }
        $Executable = [string]$Process.ExecutablePath
        $CommandLine = [string]$Process.CommandLine
        $InsideInstallation = -not [string]::IsNullOrWhiteSpace($Executable) -and (
            $Executable.StartsWith($BundlePrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
            $Executable.StartsWith($RuntimePrefix, [System.StringComparison]::OrdinalIgnoreCase)
        )
        $CommandUsesInstallation = -not [string]::IsNullOrWhiteSpace($CommandLine) -and (
            $CommandLine.IndexOf($BundlePrefix, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $CommandLine.IndexOf($RuntimePrefix, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        )
        if ($InsideInstallation -or $CommandUsesInstallation) {
            throw "Associated process must be closed before uninstallation: $($Process.Name) (PID $($Process.ProcessId))"
        }
    }
}

function Get-BootstrapCallerProcessId {
    try {
        $CurrentProcesses = @(
            Get-CimInstance Win32_Process -Filter "ProcessId = $PID" -ErrorAction Stop
        )
    }
    catch { throw "Cannot verify the uninstall bootstrap caller." }
    if ($CurrentProcesses.Count -ne 1) {
        throw "Cannot identify the uninstall bootstrap caller."
    }
    $ParentProcessId = [string]$CurrentProcesses[0].ParentProcessId
    if ($ParentProcessId -notmatch '^\d+$' -or [int]$ParentProcessId -le 0) {
        throw "Uninstall bootstrap caller process ID is invalid."
    }
    return [int]$ParentProcessId
}

function Open-ExactUninstallDeleteHandle([string]$Path) {
    $Flags = 0x00200000
    if ([System.IO.Directory]::Exists($Path)) { $Flags = $Flags -bor 0x02000000 }
    $Handle = [Dicomxphits.OfflineUninstallNative]::CreateFile(
        $Path,
        0x00010000,
        [System.IO.FileShare]::Read -bor
            [System.IO.FileShare]::Write -bor
            [System.IO.FileShare]::Delete,
        [System.IntPtr]::Zero,
        [System.IO.FileMode]::Open,
        $Flags,
        [System.IntPtr]::Zero
    )
    if ($Handle.IsInvalid) {
        $ErrorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
        $Handle.Dispose()
        $Message = if ($ErrorCode -in @(32, 33)) {
            "Cannot safely begin uninstallation because a target is in use. " +
                "Close every terminal, File Explorer window, editor, or other " +
                "process using this offline installation, then retry: $Path " +
                "(Windows error $ErrorCode)"
        }
        else {
            "Cannot prove that an exact uninstall target is deletable before " +
                "cleanup: $Path (Windows error $ErrorCode)"
        }
        throw (New-Object System.ComponentModel.Win32Exception($ErrorCode, $Message))
    }
    return $Handle
}

function Open-ExactUninstallWriteGuardHandle([string]$Path) {
    $Flags = 0x00200000
    if ([System.IO.Directory]::Exists($Path)) { $Flags = $Flags -bor 0x02000000 }
    $Handle = [Dicomxphits.OfflineUninstallNative]::CreateFile(
        $Path,
        0x00000081,
        [System.IO.FileShare]::Read -bor [System.IO.FileShare]::Delete,
        [System.IntPtr]::Zero,
        [System.IO.FileMode]::Open,
        $Flags,
        [System.IntPtr]::Zero
    )
    if ($Handle.IsInvalid) {
        $ErrorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
        $Handle.Dispose()
        $Message =
            "Cannot freeze an exact uninstall target against writes before cleanup: " +
                "$Path (Windows error $ErrorCode)"
        throw (New-Object System.ComponentModel.Win32Exception($ErrorCode, $Message))
    }
    return $Handle
}

function Open-ExactUninstallWriteGuardPlan([string[]]$Targets) {
    $Handles = New-Object 'System.Collections.Generic.List[Microsoft.Win32.SafeHandles.SafeFileHandle]'
    $Entries = New-Object 'System.Collections.Generic.List[object]'
    $Roots = New-Object 'System.Collections.Generic.List[object]'
    try {
        function Open-TargetTree([string]$Target, [bool]$Required) {
            $IsDirectory = [System.IO.Directory]::Exists($Target)
            $IsFile = [System.IO.File]::Exists($Target)
            if (-not ($IsFile -or $IsDirectory)) {
                if ($Required) {
                    throw "Exact uninstall target disappeared during deletion preflight: $Target"
                }
                return
            }
            Assert-NoReparsePath $Target "Exact uninstall target"
            $GuardHandle = Open-ExactUninstallWriteGuardHandle $Target
            $Handles.Add($GuardHandle)
            $Entries.Add([pscustomobject]@{
                path = [System.IO.Path]::GetFullPath($Target)
                is_directory = $IsDirectory
                guard_handle = $GuardHandle
                delete_handle = $null
            })
            if ($IsDirectory) {
                try {
                    $Children = @([System.IO.Directory]::GetFileSystemEntries($Target))
                }
                catch {
                    throw "Cannot enumerate exact uninstall target before cleanup: $Target"
                }
                foreach ($Child in $Children) {
                    Open-TargetTree $Child $true
                }
            }
        }
        foreach ($Target in $Targets) {
            $FullTarget = [System.IO.Path]::GetFullPath($Target)
            $Roots.Add([pscustomobject]@{
                path = $FullTarget
                existed = [System.IO.File]::Exists($FullTarget) -or
                    [System.IO.Directory]::Exists($FullTarget)
            })
            Open-TargetTree $Target $false
        }
        return [pscustomobject]@{
            roots = $Roots
            entries = $Entries
            handles = $Handles
        }
    }
    catch {
        foreach ($Handle in $Handles) { $Handle.Dispose() }
        throw
    }
}

function Assert-ExactUninstallPlanSnapshot([object]$Plan) {
    $Expected = New-Object 'System.Collections.Generic.Dictionary[string,bool]' (
        [System.StringComparer]::OrdinalIgnoreCase
    )
    foreach ($Entry in $Plan.entries) {
        $Expected.Add([string]$Entry.path, [bool]$Entry.is_directory)
    }
    $Observed = New-Object 'System.Collections.Generic.Dictionary[string,bool]' (
        [System.StringComparer]::OrdinalIgnoreCase
    )
    function Add-ObservedTree([string]$Path) {
        $IsDirectory = [System.IO.Directory]::Exists($Path)
        $IsFile = [System.IO.File]::Exists($Path)
        if (-not ($IsDirectory -or $IsFile)) { return }
        $Full = [System.IO.Path]::GetFullPath($Path)
        Assert-NoReparsePath $Full "Exact uninstall target"
        $Observed.Add($Full, $IsDirectory)
        if ($IsDirectory) {
            foreach ($Child in [System.IO.Directory]::GetFileSystemEntries($Full)) {
                Add-ObservedTree $Child
            }
        }
    }
    foreach ($Root in $Plan.roots) {
        $Exists = [System.IO.File]::Exists([string]$Root.path) -or
            [System.IO.Directory]::Exists([string]$Root.path)
        if ([bool]$Root.existed -ne $Exists) {
            throw "Exact uninstall target tree changed after deletion preflight: $($Root.path)"
        }
        Add-ObservedTree ([string]$Root.path)
    }
    foreach ($Item in $Observed.GetEnumerator()) {
        if (-not $Expected.ContainsKey($Item.Key) -or $Expected[$Item.Key] -ne $Item.Value) {
            throw "Exact uninstall target tree changed after deletion preflight: $($Item.Key)"
        }
    }
    foreach ($Item in $Expected.GetEnumerator()) {
        if (-not $Observed.ContainsKey($Item.Key)) {
            throw "Exact uninstall target tree changed after deletion preflight: $($Item.Key)"
        }
    }
}

function Open-ExactUninstallDeleteHandles([object]$Plan) {
    Assert-ExactUninstallPlanSnapshot $Plan
    foreach ($Entry in $Plan.entries) {
        $Handle = Open-ExactUninstallDeleteHandle ([string]$Entry.path)
        $Entry.delete_handle = $Handle
        $Plan.handles.Add($Handle)
    }
    Assert-ExactUninstallPlanSnapshot $Plan
}

function Close-ExactUninstallPlan([object]$Plan) {
    foreach ($Handle in $Plan.handles) { $Handle.Dispose() }
}

function New-ProtectedCleanupDirectory([string]$Path) {
    if ([System.IO.File]::Exists($Path) -or [System.IO.Directory]::Exists($Path)) {
        throw "Cleanup staging already exists: $Path"
    }
    [System.IO.Directory]::CreateDirectory($Path, (Get-ProtectedRuntimeSecurity $true)) | Out-Null
    Assert-NoReparsePath $Path "Cleanup staging"
    Assert-ProtectedSecurity $Path $true "Cleanup staging"
}

function Copy-ProtectedCleanupFile([string]$Source, [string]$Destination) {
    $ExpectedHash = Get-FileSha256 $Source
    $Input = [System.IO.File]::Open($Source, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    $Output = $null
    try {
        $Output = [System.IO.File]::Open($Destination, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $Input.CopyTo($Output)
        $Output.Flush()
    }
    finally {
        if ($null -ne $Output) { $Output.Dispose() }
        $Input.Dispose()
    }
    [System.IO.File]::SetAccessControl($Destination, (Get-ProtectedRuntimeSecurity $false))
    Assert-ProtectedSecurity $Destination $false "Cleanup staging file"
    if ((Get-FileSha256 $Destination) -ne $ExpectedHash) {
        throw "Cleanup staging file changed during protected copy: $Destination"
    }
}

function Write-ProtectedCleanupPlan([string]$CleanupDirectory, [string]$Nonce) {
    $PlanPath = Join-Path $CleanupDirectory "cleanup-plan.json"
    $CleanupHelper = Join-Path $CleanupDirectory "uninstall_offline_verified.ps1"
    $Plan = [pscustomobject]@{
        schema_version = 1
        runtime_identity_schema = $RuntimeIdentitySchema
        nonce = $Nonce
        bundle_root = $BundleRoot
        bundle_manifest_sha256 = $BundleManifestSha256
        runtime_id = $ProtectedRuntimeId
        runtime_root = $RuntimeRoot
        protected_source_root = $ProtectedSourceRoot
        receipt = $ProtectedRuntimeReceipt
        runtime_log = $RuntimeLog
        failure_diagnostic = $FailureDiagnostic
        installing_user_sid = $InstallingUserSid.Value
        cleanup_helper_sha256 = Get-FileSha256 $CleanupHelper
    }
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes(
        (($Plan | ConvertTo-Json -Compress) + [Environment]::NewLine)
    )
    $Stream = [System.IO.File]::Open(
        $PlanPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try { $Stream.Write($Bytes, 0, $Bytes.Length); $Stream.Flush() }
    finally { $Stream.Dispose() }
    [System.IO.File]::SetAccessControl($PlanPath, (Get-ProtectedRuntimeSecurity $false))
    Assert-ProtectedSecurity $PlanPath $false "Cleanup plan"
}

function Assert-ProtectedCleanupPlan(
    [string]$CleanupDirectory,
    [string]$Nonce,
    [bool]$RequireProtectedHelper = $true
) {
    $PlanPath = Join-Path $CleanupDirectory "cleanup-plan.json"
    $CleanupHelper = Join-Path $CleanupDirectory "uninstall_offline_verified.ps1"
    $ProtectedHelper = Join-Path $ProtectedSourceRoot "tools\uninstall_offline_verified.ps1"
    if (-not [System.IO.File]::Exists($PlanPath)) {
        throw "Cleanup plan is missing: $PlanPath"
    }
    Assert-NoReparsePath $PlanPath "Cleanup plan"
    Assert-ProtectedSecurity $PlanPath $false "Cleanup plan"
    $Plan = [System.IO.File]::ReadAllText(
        $PlanPath,
        [System.Text.Encoding]::UTF8
    ) | ConvertFrom-Json
    if (
        $Plan.schema_version -ne 1 -or
        [string]$Plan.runtime_identity_schema -ne $RuntimeIdentitySchema -or
        [string]$Plan.nonce -ne $Nonce -or
        -not [string]::Equals([string]$Plan.bundle_root, $BundleRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]$Plan.bundle_manifest_sha256 -ne $BundleManifestSha256 -or
        [string]$Plan.runtime_id -ne $ProtectedRuntimeId -or
        -not [string]::Equals([string]$Plan.runtime_root, $RuntimeRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals([string]$Plan.protected_source_root, $ProtectedSourceRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals([string]$Plan.receipt, $ProtectedRuntimeReceipt, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals([string]$Plan.runtime_log, $RuntimeLog, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals([string]$Plan.failure_diagnostic, $FailureDiagnostic, [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]$Plan.installing_user_sid -ne $InstallingUserSid.Value -or
        [string]$Plan.cleanup_helper_sha256 -notmatch "^[0-9a-f]{64}$" -or
        [string]$Plan.cleanup_helper_sha256 -ne (Get-FileSha256 $CleanupHelper) -or
        ($RequireProtectedHelper -and (
            -not [System.IO.File]::Exists($ProtectedHelper) -or
            [string]$Plan.cleanup_helper_sha256 -ne (Get-FileSha256 $ProtectedHelper)
        ))
    ) {
        throw "Cleanup plan does not identify the exact verified installation."
    }
}

function Assert-ExactCleanupStaging(
    [string]$Directory,
    [bool]$RequireFailureReport = $false
) {
    if (-not [System.IO.Directory]::Exists($Directory)) {
        throw "Cleanup staging is missing: $Directory"
    }
    Assert-NoReparsePath $Directory "Cleanup staging"
    Assert-ProtectedSecurity $Directory $true "Cleanup staging"
    $Expected = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $ExpectedNames = @("uninstall_offline_verified.ps1", "cleanup-plan.json")
    if ($RequireFailureReport) { $ExpectedNames += "failure.json" }
    foreach ($Name in $ExpectedNames) {
        $Path = [System.IO.Path]::GetFullPath((Join-Path $Directory $Name))
        if (-not [System.IO.File]::Exists($Path)) {
            throw "Cleanup staging payload is missing: $Path"
        }
        Assert-NoReparsePath $Path "Cleanup staging payload"
        Assert-ProtectedSecurity $Path $false "Cleanup staging payload"
        $null = $Expected.Add($Path)
    }
    $Actual = @([System.IO.Directory]::EnumerateFileSystemEntries(
        $Directory,
        "*",
        [System.IO.SearchOption]::AllDirectories
    ))
    foreach ($Entry in $Actual) {
        $Full = [System.IO.Path]::GetFullPath($Entry)
        if (
            ([System.IO.File]::GetAttributes($Full) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
            -not [System.IO.File]::Exists($Full) -or
            -not $Expected.Contains($Full)
        ) {
            throw "Cleanup staging contains an unexpected entry: $Full"
        }
    }
    if ($Actual.Count -ne $Expected.Count) {
        throw "Cleanup staging inventory is incomplete or ambiguous."
    }
    $CleanupHelper = Join-Path $Directory "uninstall_offline_verified.ps1"
    $ProtectedHelper = Join-Path $ProtectedSourceRoot "tools\uninstall_offline_verified.ps1"
    if (
        -not $RequireFailureReport -and
        (Get-FileSha256 $CleanupHelper) -ne (Get-FileSha256 $ProtectedHelper)
    ) {
        throw "Cleanup staging helper does not match the authenticated protected helper."
    }
}

function Write-ProtectedCleanupFailure([string]$Directory, [string]$Message) {
    if (
        [string]::IsNullOrWhiteSpace($Directory) -or
        -not [System.IO.Directory]::Exists($Directory)
    ) { return }
    try {
        Assert-NoReparsePath $Directory "Cleanup failure staging"
        Assert-ProtectedSecurity $Directory $true "Cleanup failure staging"
        $Remaining = @(
            @($BundleRoot, $RuntimeRoot, $ProtectedRuntimeReceipt, $RuntimeLog, $FailureDiagnostic, $Directory) |
                Where-Object { [System.IO.File]::Exists($_) -or [System.IO.Directory]::Exists($_) }
        )
        $Controlled = ($Message -replace "[\r\n]+", " ").Trim()
        if ($Controlled.Length -gt 2048) { $Controlled = $Controlled.Substring(0, 2048) }
        $Record = [pscustomobject]@{
            schema_version = 1
            nonce = [string]$env:DICOMXPHITS_UNINSTALL_NONCE
            runtime_id = $ProtectedRuntimeId
            message = $Controlled
            remaining_paths = $Remaining
        }
        $Path = Join-Path $Directory "failure.json"
        if ([System.IO.File]::Exists($Path)) { Remove-Item -LiteralPath $Path -Force }
        $Bytes = [System.Text.Encoding]::UTF8.GetBytes(
            (($Record | ConvertTo-Json -Depth 4) + [Environment]::NewLine)
        )
        $Stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try { $Stream.Write($Bytes, 0, $Bytes.Length); $Stream.Flush() }
        finally { $Stream.Dispose() }
        [System.IO.File]::SetAccessControl($Path, (Get-ProtectedRuntimeSecurity $false))
        Assert-ProtectedSecurity $Path $false "Cleanup failure report"
    }
    catch { }
}

function Invoke-ElevatedCleanup(
    [string]$TrustedPowerShell,
    [int]$BootstrapCallerProcessId
) {
    $CurrentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $Nonce = [System.Guid]::NewGuid().ToString("N")
    $State = @{
        ROOT = $BundleRoot
        MANIFEST = $BundleManifestSha256
        SID = $CurrentIdentity.User.Value
        ACTION = "stage"
        NONCE = $Nonce
        # This bootstrap PowerShell process owns the verified file and
        # directory locks. Its caller may be a persistent cmd.exe and does not
        # own those handles, so waiting for that shell would deadlock cleanup.
        WAIT_PIDS = "$PID"
        CALLER_PID = "$BootstrapCallerProcessId"
        PROTECTED_SOURCE = $ProtectedSourceRoot
    }
    $Command = @'
$env:PSModulePath=[IO.Path]::Combine($PSHOME,'Modules')
$ErrorActionPreference='Stop'
$decode={param($value)[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($value))}
$env:DICOMXPHITS_BUNDLE_ROOT=& $decode '{ROOT}'
$env:DICOMXPHITS_BUNDLE_MANIFEST_SHA256=& $decode '{MANIFEST}'
$env:DICOMXPHITS_UNINSTALLING_USER_SID=& $decode '{SID}'
$env:DICOMXPHITS_UNINSTALL_ACTION=& $decode '{ACTION}'
$env:DICOMXPHITS_UNINSTALL_NONCE=& $decode '{NONCE}'
$env:DICOMXPHITS_UNINSTALL_WAIT_PIDS=& $decode '{WAIT_PIDS}'
$env:DICOMXPHITS_UNINSTALL_BOOTSTRAP_CALLER_PID=& $decode '{CALLER_PID}'
$env:DICOMXPHITS_PROTECTED_SOURCE_ROOT=& $decode '{PROTECTED_SOURCE}'
& ([IO.Path]::Combine([IO.Path]::GetFullPath($env:DICOMXPHITS_PROTECTED_SOURCE_ROOT),'tools','uninstall_offline_verified.ps1'))
exit $LASTEXITCODE
'@
    foreach ($Entry in $State.GetEnumerator()) {
        $EncodedValue = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes([string]$Entry.Value))
        $Command = $Command.Replace("{$($Entry.Key)}", $EncodedValue)
    }
    $EncodedCommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Command))
    try {
        $Process = Start-Process -FilePath $TrustedPowerShell -Verb RunAs -PassThru -WindowStyle Hidden -ArgumentList @(
            "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $EncodedCommand
        )
        # Process.WaitForExit waits for this elevated stage only. Start-Process
        # -Wait also waits for descendants on Windows, which deadlocks because
        # the detached finalizer must wait for this non-elevated parent to exit.
        $Process.WaitForExit()
    }
    catch { throw "Administrator approval is required for verified uninstallation." }
    if ($Process.ExitCode -ne 0) {
        throw "Elevated uninstall staging failed with exit code $($Process.ExitCode)."
    }
    $CleanupParent = Join-Path ([System.IO.Path]::GetDirectoryName($ProtectedRuntimeParent)) "offline-cleanup"
    return (Join-Path $CleanupParent "$ProtectedRuntimeId-$Nonce")
}

function Start-DetachedFinalizer([string]$TrustedPowerShell, [string]$CleanupDirectory) {
    $StagedHelper = Join-Path $CleanupDirectory "uninstall_offline_verified.ps1"
    $StateNames = @(
        "DICOMXPHITS_BUNDLE_ROOT",
        "DICOMXPHITS_BUNDLE_MANIFEST_SHA256",
        "DICOMXPHITS_UNINSTALLING_USER_SID",
        "DICOMXPHITS_UNINSTALL_NONCE",
        "DICOMXPHITS_UNINSTALL_WAIT_PIDS",
        "DICOMXPHITS_UNINSTALL_BOOTSTRAP_CALLER_PID"
    )
    $Command = "`$env:PSModulePath=[IO.Path]::Combine(`$PSHOME,'Modules');`$ErrorActionPreference='Stop';`$env:DICOMXPHITS_UNINSTALL_ACTION='finalize';"
    foreach ($Name in $StateNames) {
        $Value = [Environment]::GetEnvironmentVariable($Name, "Process")
        $EncodedValue = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes([string]$Value))
        $Command += "`$env:$Name=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$EncodedValue'));"
    }
    $EncodedPath = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($StagedHelper))
    $Command += "& ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$EncodedPath')));exit `$LASTEXITCODE"
    $EncodedCommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Command))
    Start-Process -FilePath $TrustedPowerShell -WindowStyle Hidden -ArgumentList @(
        "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $EncodedCommand
    ) | Out-Null
}

function Remove-ExactInstallationTargets([object]$Plan) {
    Assert-ExactUninstallPlanSnapshot $Plan
    $Entries = @($Plan.entries | Sort-Object { ([string]$_.path).Length } -Descending)
    foreach ($Entry in $Entries) {
        $Path = [string]$Entry.path
        Assert-NoReparsePath $Path "Exact uninstall target"
        if ($null -eq $Entry.delete_handle) {
            throw "Exact uninstall target has no retained deletion handle: $Path"
        }
        if (-not [Dicomxphits.OfflineUninstallNative]::MarkDeletePending(
            $Entry.delete_handle
        )) {
            $ErrorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
            throw (New-Object System.ComponentModel.Win32Exception(
                $ErrorCode,
                "Exact uninstall target could not be removed from the frozen inventory: " +
                    "$Path (Windows error $ErrorCode)"
            ))
        }
        $Entry.delete_handle.Dispose()
        $Entry.guard_handle.Dispose()
    }
    foreach ($Target in @($BundleRoot, $RuntimeRoot, $ProtectedRuntimeReceipt, $RuntimeLog, $FailureDiagnostic)) {
        if ([System.IO.File]::Exists($Target) -or [System.IO.Directory]::Exists($Target)) {
            throw "Uninstall target remains after cleanup: $Target"
        }
    }
}

function Remove-ExactCleanupStaging([object]$Plan, [string]$CleanupDirectory) {
    Assert-ExactUninstallPlanSnapshot $Plan
    $Entries = @($Plan.entries | Sort-Object { ([string]$_.path).Length } -Descending)
    foreach ($Entry in $Entries) {
        $Path = [string]$Entry.path
        Assert-NoReparsePath $Path "Exact cleanup staging target"
        if ($null -eq $Entry.delete_handle) {
            throw "Exact cleanup staging target has no retained deletion handle: $Path"
        }
        if (-not [Dicomxphits.OfflineUninstallNative]::MarkDeletePending(
            $Entry.delete_handle
        )) {
            $ErrorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
            throw (New-Object System.ComponentModel.Win32Exception(
                $ErrorCode,
                "Exact cleanup staging target could not be removed from the frozen inventory: " +
                    "$Path (Windows error $ErrorCode)"
            ))
        }
        $Entry.delete_handle.Dispose()
        $Entry.guard_handle.Dispose()
    }
    if (
        [System.IO.Directory]::Exists($CleanupDirectory) -or
        [System.IO.File]::Exists($CleanupDirectory)
    ) { throw "Cleanup staging remains after cleanup: $CleanupDirectory" }
}

function Invoke-CleanupStagingRemoval([string]$CleanupDirectory, [int]$WaitProcessId) {
    if ($WaitProcessId -le 0 -or $WaitProcessId -eq $PID) {
        throw "Cleanup staging parent process ID is invalid."
    }
    Wait-Process -Id $WaitProcessId -ErrorAction SilentlyContinue
    Assert-ExactCleanupStaging $CleanupDirectory $true
    Assert-ProtectedCleanupPlan `
        $CleanupDirectory `
        ([string]$env:DICOMXPHITS_UNINSTALL_NONCE) `
        $false
    $CleanupPlan = Open-ExactUninstallWriteGuardPlan @($CleanupDirectory)
    try {
        Assert-ExactCleanupStaging $CleanupDirectory $true
        Assert-ExactUninstallPlanSnapshot $CleanupPlan
        Open-ExactUninstallDeleteHandles $CleanupPlan
        Remove-ExactCleanupStaging $CleanupPlan $CleanupDirectory
    }
    finally { Close-ExactUninstallPlan $CleanupPlan }
}

function Invoke-FinalCleanup(
    [string]$CleanupDirectory,
    [int[]]$WaitProcessIds,
    [int]$BootstrapCallerProcessId
) {
    foreach ($WaitPid in $WaitProcessIds) {
        if ($WaitPid -le 0 -or $WaitPid -eq $PID) { continue }
        $Deadline = [System.DateTime]::UtcNow.AddSeconds(60)
        while (
            $null -ne (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue) -and
            [System.DateTime]::UtcNow -lt $Deadline
        ) {
            Start-Sleep -Milliseconds 100
        }
        if (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue) {
            throw "Timed out waiting for uninstall parent process $WaitPid."
        }
    }
    Assert-ExactCleanupStaging $CleanupDirectory
    Assert-ProtectedCleanupPlan $CleanupDirectory ([string]$env:DICOMXPHITS_UNINSTALL_NONCE)
    Assert-NoAssociatedProcesses @($PID) $BootstrapCallerProcessId
    Assert-ExactInstallationRoot
    $DeletePlan = Open-ExactUninstallWriteGuardPlan @(
        $BundleRoot,
        $RuntimeRoot,
        $ProtectedRuntimeReceipt,
        $RuntimeLog,
        $FailureDiagnostic
    )
    $CleanupPlan = $null
    try {
        $CleanupPlan = Open-ExactUninstallWriteGuardPlan @($CleanupDirectory)
        # Revalidate after existing files are write-frozen. Snapshot checks
        # catch arrivals before mutation; exact non-recursive deletion never
        # removes an arrival that races a later check.
        Assert-ExactInstallationRoot
        Assert-ExactUninstallPlanSnapshot $DeletePlan
        Assert-ExactUninstallPlanSnapshot $CleanupPlan
        Open-ExactUninstallDeleteHandles $DeletePlan
        Open-ExactUninstallDeleteHandles $CleanupPlan
        Remove-ExactInstallationTargets $DeletePlan
    }
    finally {
        Close-ExactUninstallPlan $DeletePlan
        if ($null -ne $CleanupPlan) { Close-ExactUninstallPlan $CleanupPlan }
    }
    $CleanupParent = [System.IO.Path]::GetDirectoryName($CleanupDirectory)
    if (-not [string]::Equals(
        $CleanupParent,
        (Join-Path ([System.IO.Path]::GetDirectoryName($ProtectedRuntimeParent)) "offline-cleanup"),
        [System.StringComparison]::OrdinalIgnoreCase
    )) { throw "Cleanup staging parent is unexpected." }
    Write-ProtectedCleanupFailure $CleanupDirectory "Final cleanup staging removal is pending."
    Assert-ExactCleanupStaging $CleanupDirectory $true
    Assert-ProtectedCleanupPlan `
        $CleanupDirectory `
        ([string]$env:DICOMXPHITS_UNINSTALL_NONCE) `
        $false
    $TrustedPowerShell = Assert-TrustedPowerShellProcess
    $StagedHelper = Join-Path $CleanupDirectory "uninstall_offline_verified.ps1"
    $EncodedHelper = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($StagedHelper))
    $FinalCommand = "`$env:PSModulePath=[IO.Path]::Combine(`$PSHOME,'Modules');`$ErrorActionPreference='Stop';`$env:DICOMXPHITS_UNINSTALL_ACTION='cleanup-staging';`$env:DICOMXPHITS_UNINSTALL_FINALIZER_PID='$PID';& ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$EncodedHelper')));exit `$LASTEXITCODE"
    $EncodedCommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($FinalCommand))
    Start-Process -FilePath $TrustedPowerShell -WindowStyle Hidden -ArgumentList @(
        "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $EncodedCommand
    ) | Out-Null
}

try {
    $TrustedPowerShell = Assert-TrustedPowerShellProcess
    $Action = [string]$env:DICOMXPHITS_UNINSTALL_ACTION
    if ([string]::IsNullOrWhiteSpace($Action)) {
        if ([string]::IsNullOrWhiteSpace($env:DICOMXPHITS_UNINSTALL_VERIFIED_STAGE)) {
            throw "Refusing to uninstall without verified bootstrap state."
        }
        if (Test-IsAdministrator) {
            throw "Start uninstall_offline.cmd without elevation; approve only its verified administrator prompt."
        }
        $script:BundleManifestSha256 = Get-VerifiedManifestIdentity
        $CurrentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
        Set-ProtectedRuntimeIdentity $CurrentIdentity.User.Value
        $null = Import-ExactProtectedReceipt
        Assert-ExactInstallationRoot
        $BootstrapCallerProcessId = Get-BootstrapCallerProcessId
        Assert-NoAssociatedProcesses @($PID) $BootstrapCallerProcessId
        $ProtectedHelper = Join-Path $ProtectedSourceRoot "tools\uninstall_offline_verified.ps1"
        if ((Get-FileSha256 $PSCommandPath) -ne (Get-FileSha256 $ProtectedHelper)) {
            throw "Writable uninstall helper does not match the authenticated protected helper."
        }
        $Confirmation = Read-Host "Type UNINSTALL to remove this exact offline installation"
        if ($Confirmation -cne "UNINSTALL") {
            Write-Host "Uninstallation cancelled. No files were changed."
            exit 0
        }
        $PendingCleanup = Invoke-ElevatedCleanup `
            $TrustedPowerShell `
            $BootstrapCallerProcessId
        Write-Host "Verified cleanup was scheduled. This window may now close."
        Write-Host "On success, cleanup staging disappears. On failure, review: $PendingCleanup\failure.json"
        exit 0
    }

    $script:BundleManifestSha256 = [string]$env:DICOMXPHITS_BUNDLE_MANIFEST_SHA256
    Set-ProtectedRuntimeIdentity ([string]$env:DICOMXPHITS_UNINSTALLING_USER_SID)
    if (-not (Test-IsAdministrator)) { throw "Verified uninstall action requires administrator authority." }
    $Nonce = [string]$env:DICOMXPHITS_UNINSTALL_NONCE
    if ($Nonce -notmatch "^[0-9a-f]{32}$") { throw "Uninstall nonce is invalid." }
    $CleanupParent = Join-Path ([System.IO.Path]::GetDirectoryName($ProtectedRuntimeParent)) "offline-cleanup"
    if (-not [System.IO.Directory]::Exists($CleanupParent)) {
        [System.IO.Directory]::CreateDirectory($CleanupParent, (Get-ProtectedRuntimeSecurity $true)) | Out-Null
    }
    Assert-NoReparsePath $CleanupParent "Cleanup parent"
    Assert-ProtectedSecurity $CleanupParent $true "Cleanup parent"
    $CleanupDirectory = Join-Path $CleanupParent "$ProtectedRuntimeId-$Nonce"
    if ($Action -eq "cleanup-staging") {
        if (-not [string]::Equals(
            [System.IO.Path]::GetDirectoryName($PSCommandPath),
            $CleanupDirectory,
            [System.StringComparison]::OrdinalIgnoreCase
        )) { throw "Cleanup removal helper is outside its exact cleanup staging directory." }
        Assert-ProtectedSecurity $PSCommandPath $false "Cleanup removal helper"
        $FinalizerPidText = [string]$env:DICOMXPHITS_UNINSTALL_FINALIZER_PID
        if ($FinalizerPidText -notmatch '^\d+$') {
            throw "Cleanup staging parent process ID is invalid."
        }
        Invoke-CleanupStagingRemoval $CleanupDirectory ([int]$FinalizerPidText)
        exit 0
    }
    $null = Import-ExactProtectedReceipt
    Assert-ExactInstallationRoot
    $WaitPids = @(
        ([string]$env:DICOMXPHITS_UNINSTALL_WAIT_PIDS).Split(',') |
            Where-Object { $_ -match '^\d+$' } |
            ForEach-Object { [int]$_ }
    )
    $BootstrapCallerProcessIdText = [string]$env:DICOMXPHITS_UNINSTALL_BOOTSTRAP_CALLER_PID
    if (
        $BootstrapCallerProcessIdText -notmatch '^\d+$' -or
        [int]$BootstrapCallerProcessIdText -le 0
    ) { throw "Uninstall bootstrap caller process ID is invalid." }
    $BootstrapCallerProcessId = [int]$BootstrapCallerProcessIdText
    Assert-NoAssociatedProcesses `
        @($WaitPids + $PID) `
        $BootstrapCallerProcessId
    if ($Action -eq "stage") {
        New-ProtectedCleanupDirectory $CleanupDirectory
        Copy-ProtectedCleanupFile $PSCommandPath (Join-Path $CleanupDirectory "uninstall_offline_verified.ps1")
        Write-ProtectedCleanupPlan $CleanupDirectory $Nonce
        Assert-ExactCleanupStaging $CleanupDirectory
        Assert-ProtectedCleanupPlan $CleanupDirectory $Nonce
        Start-DetachedFinalizer $TrustedPowerShell $CleanupDirectory
        exit 0
    }
    if ($Action -eq "finalize") {
        if (-not [string]::Equals(
            [System.IO.Path]::GetDirectoryName($PSCommandPath),
            $CleanupDirectory,
            [System.StringComparison]::OrdinalIgnoreCase
        )) { throw "Final uninstall helper is outside its exact cleanup staging directory." }
        Assert-ProtectedSecurity $PSCommandPath $false "Final uninstall helper"
        Assert-ExactCleanupStaging $CleanupDirectory
        Assert-ProtectedCleanupPlan $CleanupDirectory $Nonce
        Invoke-FinalCleanup `
            $CleanupDirectory `
            $WaitPids `
            $BootstrapCallerProcessId
        exit 0
    }
    throw "Unsupported verified uninstall action."
}
catch {
    if (
        $env:DICOMXPHITS_UNINSTALL_ACTION -in @("stage", "finalize", "cleanup-staging") -and
        -not [string]::IsNullOrWhiteSpace($CleanupDirectory)
    ) {
        Write-ProtectedCleanupFailure $CleanupDirectory $_.Exception.Message
    }
    Write-Error $_
    exit 1
}
