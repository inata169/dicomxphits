<# Run only from install_offline.cmd after every bundled payload is verified and locked. #>

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($env:DICOMXPHITS_VERIFIED_STAGE)) {
    throw "Refusing to run the offline installation stage without verified bootstrap state."
}

$BundleRoot = [System.IO.Path]::GetFullPath($env:DICOMXPHITS_BUNDLE_ROOT)
$BundlePrefix = $BundleRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
$Helper = Join-Path $BundleRoot "tools\offline_install.py"
$PythonNuGet = Join-Path $BundleRoot "python\python.3.12.10.nupkg"
$TclTkMsi = Join-Path $BundleRoot "python\tcltk.msi"
$NuGetVerifier = Join-Path $BundleRoot "python\verifier\nuget.exe"
$RuntimeRoot = Join-Path $BundleRoot ".python-runtime"
$ProtectedSourceRoot = Join-Path $RuntimeRoot "dicomxphits-source"
$ProtectedRuntimeParent = $null
$ProtectedRuntimeReceipt = $null
$ProtectedRuntimeId = $null
$LogFile = Join-Path $BundleRoot "offline-install.log"
$RuntimeLog = $null
$PythonNuGetSignerSha256 = "1F4B311D9ACC115C8DC8018B5A49E00FCE6DA8E2855F9F014CA6F34570BC482D"
$LockedPythonFiles = New-Object System.Collections.Generic.List[System.IO.Stream]
$CreatedWorkingDirectories = New-Object System.Collections.Generic.List[string]
$ExpectedRuntimeHashes = New-Object 'System.Collections.Generic.Dictionary[string,string]' ([System.StringComparer]::OrdinalIgnoreCase)
$ExpectedRuntimeDirectories = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$InstallingUserSid = $null
$AdministratorsSid = New-Object System.Security.Principal.SecurityIdentifier(
    [System.Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,
    $null
)
$SystemSid = New-Object System.Security.Principal.SecurityIdentifier(
    [System.Security.Principal.WellKnownSidType]::LocalSystemSid,
    $null
)
$OwnerRightsSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-3-4")

function Write-InstallLog([string]$Message) {
    Add-Content -LiteralPath $LogFile -Encoding UTF8 -Value $Message
}

function Test-IsAdministrator {
    $Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object System.Security.Principal.WindowsPrincipal -ArgumentList $Identity
    return $Principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Assert-TrustedPowerShellProcess {
    $TrustedPowerShell = Join-Path (
        Join-Path [System.Environment]::SystemDirectory "WindowsPowerShell\v1.0"
    ) "powershell.exe"
    $CurrentExecutable = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    if (-not [string]::Equals(
        [System.IO.Path]::GetFullPath($CurrentExecutable),
        [System.IO.Path]::GetFullPath($TrustedPowerShell),
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Verified stage is not running in the trusted Windows PowerShell executable."
    }
    Assert-NoReparsePath $TrustedPowerShell "Trusted Windows PowerShell"
    return $TrustedPowerShell
}

function Invoke-ElevatedRuntimeConstruction {
    $TrustedPowerShell = Assert-TrustedPowerShellProcess
    if (Test-IsAdministrator) {
        throw "Start install_offline.cmd without elevation; approve only its verified administrator prompt."
    }

    $ParentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $ChildState = @{}
    foreach ($Entry in @{
        BUNDLE_ROOT = $BundleRoot
        VERIFIED_STAGE = $env:DICOMXPHITS_VERIFIED_STAGE
        INSTALLING_USER_SID = $ParentIdentity.User.Value
        ELEVATED_STAGE = $env:DICOMXPHITS_VERIFIED_STAGE
        ELEVATED_ACTION = "construct-runtime"
    }.GetEnumerator()) {
        $ChildState[$Entry.Key] = [Convert]::ToBase64String(
            [Text.Encoding]::UTF8.GetBytes([string]$Entry.Value)
        )
    }

    $ChildCommand = @'
$env:PSModulePath=[IO.Path]::Combine($PSHOME,'Modules')
$ErrorActionPreference='Stop'
$decode={param($value)[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($value))}
$env:DICOMXPHITS_BUNDLE_ROOT=& $decode '{BUNDLE_ROOT}'
$env:DICOMXPHITS_VERIFIED_STAGE=& $decode '{VERIFIED_STAGE}'
$env:DICOMXPHITS_INSTALLING_USER_SID=& $decode '{INSTALLING_USER_SID}'
$env:DICOMXPHITS_ELEVATED_STAGE=& $decode '{ELEVATED_STAGE}'
$env:DICOMXPHITS_ELEVATED_ACTION=& $decode '{ELEVATED_ACTION}'
& ([IO.Path]::Combine([IO.Path]::GetFullPath($env:DICOMXPHITS_BUNDLE_ROOT),'tools','install_offline_verified.ps1'))
exit $LASTEXITCODE
'@
    foreach ($Entry in $ChildState.GetEnumerator()) {
        $ChildCommand = $ChildCommand.Replace("{$($Entry.Key)}", $Entry.Value)
    }
    $EncodedCommand = [Convert]::ToBase64String(
        [Text.Encoding]::Unicode.GetBytes($ChildCommand)
    )
    try {
        $Process = Start-Process -FilePath $TrustedPowerShell -Verb RunAs -Wait -PassThru `
            -ArgumentList @(
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                $EncodedCommand
            )
    }
    catch {
        throw "Administrator approval is required before runtime construction."
    }
    if ($Process.ExitCode -ne 0) {
        throw "Protected runtime construction failed with exit code $($Process.ExitCode)."
    }
}

function Get-ProtectedRuntimeSecurity([bool]$IsDirectory) {
    if ($null -eq $InstallingUserSid) {
        throw "Installing-user identity is unavailable."
    }
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
    else {
        [System.Security.AccessControl.InheritanceFlags]::None
    }
    $Propagation = [System.Security.AccessControl.PropagationFlags]::None
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
            $Propagation,
            [System.Security.AccessControl.AccessControlType]::Allow
        )))
    }
    return $Security
}

function Assert-ProtectedRuntimeSecurity(
    [string]$Path,
    [bool]$IsDirectory,
    [string]$Label
) {
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
    $ActualOwner = $Actual.GetOwner(
        [System.Security.Principal.SecurityIdentifier]
    )
    $ExpectedOwner = $Expected.GetOwner(
        [System.Security.Principal.SecurityIdentifier]
    )
    $InheritedRules = @($Actual.GetAccessRules(
        $false,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    ))
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
    $ActualRules = @(Get-RuleSignatures $Actual)
    $ExpectedRules = @(Get-RuleSignatures $Expected)
    if (
        $ActualOwner.Value -ne $ExpectedOwner.Value -or
        -not $Actual.AreAccessRulesProtected -or
        $InheritedRules.Count -ne 0 -or
        $ActualRules.Count -ne $ExpectedRules.Count -or
        [string]::Join("`n", $ActualRules) -ne [string]::Join("`n", $ExpectedRules)
    ) {
        throw "$Label does not have the exact protected owner and access rules: $Path"
    }
}

function New-ProtectedRuntimeDirectory([string]$Path, [string]$Label) {
    if ([System.IO.File]::Exists($Path) -or [System.IO.Directory]::Exists($Path)) {
        throw "$Label already exists: $Path"
    }
    [System.IO.Directory]::CreateDirectory(
        $Path,
        (Get-ProtectedRuntimeSecurity $true)
    ) | Out-Null
    Assert-NoReparsePath $Path $Label
    Assert-ProtectedRuntimeSecurity $Path $true $Label
}

function Set-ProtectedRuntimeIdentity {
    $InstallingSidValue = if ([string]::IsNullOrWhiteSpace(
        $env:DICOMXPHITS_INSTALLING_USER_SID
    )) {
        [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    }
    else {
        $env:DICOMXPHITS_INSTALLING_USER_SID
    }
    try {
        $script:InstallingUserSid = New-Object System.Security.Principal.SecurityIdentifier(
            $InstallingSidValue
        )
    }
    catch {
        throw "Installing-user SID is invalid."
    }
    $CommonData = [System.Environment]::GetFolderPath(
        [System.Environment+SpecialFolder]::CommonApplicationData
    )
    if ([string]::IsNullOrWhiteSpace($CommonData)) {
        throw "Windows Common Application Data is unavailable."
    }
    Assert-NoReparsePath $CommonData "Windows Common Application Data"

    $ProductRoot = Join-Path $CommonData "dicomxphits"
    $RuntimeParent = Join-Path $ProductRoot "offline-runtimes"
    $Sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $IdentityBytes = [System.Text.Encoding]::UTF8.GetBytes(
            $BundleRoot.ToUpperInvariant()
        )
        $RuntimeId = [System.BitConverter]::ToString(
            $Sha256.ComputeHash($IdentityBytes)
        ).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $Sha256.Dispose()
    }
    $script:ProtectedRuntimeParent = $RuntimeParent
    $script:ProtectedRuntimeId = $RuntimeId
    $script:RuntimeRoot = Join-Path $RuntimeParent $RuntimeId
    $script:ProtectedSourceRoot = Join-Path $script:RuntimeRoot "dicomxphits-source"
    $script:ProtectedRuntimeReceipt = Join-Path $RuntimeParent "$RuntimeId.json"
    $script:RuntimeLog = Join-Path $RuntimeParent "$RuntimeId-msi.log"
}

function Initialize-ProtectedRuntimePath {
    if (-not (Test-IsAdministrator)) {
        throw "Protected runtime initialization requires administrator authority."
    }
    Set-ProtectedRuntimeIdentity
    $ProductRoot = [System.IO.Path]::GetDirectoryName($ProtectedRuntimeParent)
    $RuntimeParent = $ProtectedRuntimeParent
    foreach ($ProtectedDirectory in @($ProductRoot, $RuntimeParent)) {
        if ([System.IO.File]::Exists($ProtectedDirectory)) {
            throw "Protected runtime parent is not a directory: $ProtectedDirectory"
        }
        if (-not [System.IO.Directory]::Exists($ProtectedDirectory)) {
            New-ProtectedRuntimeDirectory $ProtectedDirectory "Protected runtime parent"
        }
        else {
            Assert-NoReparsePath $ProtectedDirectory "Protected runtime parent"
            Assert-ProtectedRuntimeSecurity $ProtectedDirectory $true "Protected runtime parent"
        }
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
    if ([System.IO.File]::Exists($Full)) {
        if (([System.IO.File]::GetAttributes($Full) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "$Label is a symbolic link or reparse point: $Full"
        }
    }
}

function Add-SignedFileLock(
    [string]$Path,
    [string]$Label,
    [string]$ExpectedSigner
) {
    $Full = [System.IO.Path]::GetFullPath($Path)
    if (-not [System.IO.File]::Exists($Full)) {
        throw "$Label is missing or is not a regular file: $Full"
    }
    Assert-NoReparsePath $Full $Label
    $Stream = $null
    try {
        $Stream = [System.IO.File]::Open(
            $Full,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::Read
        )
        $Signature = Get-AuthenticodeSignature -LiteralPath $Full
        if ($Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
            throw "$Label Authenticode validation failed: $Full"
        }
        if (
            $null -eq $Signature.SignerCertificate -or
            [string]$Signature.SignerCertificate.Subject -notlike $ExpectedSigner
        ) {
            throw "$Label has an unexpected Authenticode signer: $Full"
        }
        $LockedPythonFiles.Add($Stream)
        $Stream = $null
    }
    finally {
        if ($null -ne $Stream) { $Stream.Dispose() }
    }
}

function Assert-IsolatedVerifierDirectory {
    $Directory = [System.IO.DirectoryInfo][System.IO.Path]::GetDirectoryName($NuGetVerifier)
    Assert-NoReparsePath $Directory.FullName "NuGet verifier directory"
    $Entries = @($Directory.EnumerateFileSystemInfos())
    if (
        $Entries.Count -ne 1 -or
        $Entries[0].Name -ine "nuget.exe" -or
        ($Entries[0].Attributes -band [System.IO.FileAttributes]::Directory) -ne 0 -or
        ($Entries[0].Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
    ) {
        throw "NuGet verifier directory must contain only the verified nuget.exe."
    }
}

function Invoke-NuGetPackageVerification {
    $PreviousRevocationMode = $env:NUGET_CERT_REVOCATION_MODE
    $PreviousLocation = Get-Location
    try {
        $env:NUGET_CERT_REVOCATION_MODE = "offline"
        Set-Location -LiteralPath ([System.IO.Path]::GetDirectoryName($NuGetVerifier))
        $Output = @(
            & $NuGetVerifier verify -Signatures $PythonNuGet `
                -CertificateFingerprint $PythonNuGetSignerSha256 `
                -NonInteractive -ForceEnglishOutput 2>&1
        )
        $ExitCode = $LASTEXITCODE
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
    if ($ExitCode -ne 0) {
        throw "Python NuGet repository signature validation failed: $($Output -join [Environment]::NewLine)"
    }
    if (($Output -join [Environment]::NewLine) -notmatch "Successfully verified package 'python\.3\.12\.10'\.") {
        throw "NuGet verification did not confirm the expected Python package identity."
    }
}

function New-BoundedWorkingDirectory([string]$Label) {
    $Name = ".python-runtime-$Label-" + [Guid]::NewGuid().ToString("N")
    $WorkingRoot = if ([string]::IsNullOrWhiteSpace($ProtectedRuntimeParent)) {
        $BundleRoot
    }
    else {
        $ProtectedRuntimeParent
    }
    $WorkingPrefix = [System.IO.Path]::GetFullPath($WorkingRoot).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    $Path = [System.IO.Path]::GetFullPath((Join-Path $WorkingRoot $Name))
    if (-not $Path.StartsWith($WorkingPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Runtime working directory escaped its protected root: $Path"
    }
    if ([System.IO.File]::Exists($Path) -or [System.IO.Directory]::Exists($Path)) {
        throw "Runtime working directory already exists: $Path"
    }
    if ([string]::IsNullOrWhiteSpace($ProtectedRuntimeParent)) {
        [System.IO.Directory]::CreateDirectory($Path) | Out-Null
    }
    else {
        New-ProtectedRuntimeDirectory $Path "Runtime working directory"
    }
    Assert-NoReparsePath $Path "Runtime working directory"
    $CreatedWorkingDirectories.Add($Path)
    return $Path
}

function Get-SafeRuntimeDestination([string]$Root, [string]$Relative) {
    $Normalized = $Relative.Replace("\", "/")
    if (
        [string]::IsNullOrWhiteSpace($Normalized) -or
        $Normalized.StartsWith("/") -or
        $Normalized.StartsWith("//") -or
        $Normalized -match "^[A-Za-z]:" -or
        $Normalized.IndexOf([char]0) -ge 0
    ) {
        throw "Unsafe Python runtime archive path: $Relative"
    }
    $Parts = @($Normalized.Split('/') | Where-Object { $_ -ne "" })
    if ($Parts.Count -eq 0 -or @($Parts | Where-Object { $_ -eq "." -or $_ -eq ".." -or $_.Contains(":") }).Count -ne 0) {
        throw "Unsafe Python runtime archive path: $Relative"
    }
    $RelativePath = [string]$Parts[0]
    for ($Index = 1; $Index -lt $Parts.Count; $Index++) {
        $RelativePath = [System.IO.Path]::Combine($RelativePath, [string]$Parts[$Index])
    }
    $Destination = [System.IO.Path]::GetFullPath((Join-Path $Root $RelativePath))
    $RootPrefix = [System.IO.Path]::GetFullPath($Root).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $Destination.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Python runtime archive path escaped the staging root: $Relative"
    }
    return $Destination
}

function Get-StreamSha256([System.IO.Stream]$Stream) {
    $Sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $Stream.Position = 0
        return [System.BitConverter]::ToString(
            $Sha256.ComputeHash($Stream)
        ).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $Sha256.Dispose()
    }
}

function Copy-ProtectedBundleSnapshot {
    New-ProtectedRuntimeDirectory $ProtectedSourceRoot "Protected bundle source"
    $ChecksumPath = Join-Path $BundleRoot "SHA256SUMS.txt"
    Assert-NoReparsePath $ChecksumPath "Bundle checksum inventory"
    $ChecksumStream = [System.IO.File]::Open(
        $ChecksumPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    try {
        $Reader = New-Object System.IO.StreamReader(
            $ChecksumStream,
            [System.Text.Encoding]::UTF8,
            $true,
            4096,
            $true
        )
        try { $ChecksumText = $Reader.ReadToEnd() }
        finally { $Reader.Dispose() }
        $Records = New-Object 'System.Collections.Generic.Dictionary[string,string]' (
            [System.StringComparer]::OrdinalIgnoreCase
        )
        foreach ($Line in ($ChecksumText -split "\r?\n")) {
            if ([string]::IsNullOrEmpty($Line)) { continue }
            if ($Line -notmatch "^([0-9a-f]{64}) \*(.+)$") {
                throw "Invalid protected bundle checksum entry: $Line"
            }
            $Relative = [string]$Matches[2]
            $Source = Get-SafeRuntimeDestination $BundleRoot $Relative
            if ($Records.ContainsKey($Source)) {
                throw "Duplicate protected bundle checksum path: $Relative"
            }
            $Records.Add($Source, [string]$Matches[1])
        }
        if ($Records.Count -eq 0) {
            throw "Protected bundle checksum inventory is empty."
        }
        $Records.Add($ChecksumPath, (Get-StreamSha256 $ChecksumStream))
        foreach ($Record in $Records.GetEnumerator()) {
            $Source = [System.IO.Path]::GetFullPath($Record.Key)
            if (-not [System.IO.File]::Exists($Source)) {
                throw "Protected bundle payload is missing or non-regular: $Source"
            }
            Assert-NoReparsePath $Source "Protected bundle payload"
            $Relative = $Source.Substring($BundleRoot.Length).TrimStart(
                [System.IO.Path]::DirectorySeparatorChar
            )
            $Destination = Get-SafeRuntimeDestination $ProtectedSourceRoot $Relative
            $Parent = [System.IO.Path]::GetDirectoryName($Destination)
            [System.IO.Directory]::CreateDirectory($Parent) | Out-Null
            $Input = [System.IO.File]::Open(
                $Source,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::Read
            )
            $Output = $null
            try {
                $Actual = Get-StreamSha256 $Input
                if ($Actual -ne $Record.Value) {
                    throw "Protected bundle payload hash changed: $Relative"
                }
                $Input.Position = 0
                $Output = [System.IO.File]::Open(
                    $Destination,
                    [System.IO.FileMode]::CreateNew,
                    [System.IO.FileAccess]::Write,
                    [System.IO.FileShare]::None
                )
                $Input.CopyTo($Output)
                $Output.Flush()
                $ExpectedRuntimeHashes.Add($Destination, $Actual)
            }
            finally {
                if ($null -ne $Output) { $Output.Dispose() }
                $Input.Dispose()
            }
        }
    }
    finally {
        $ChecksumStream.Dispose()
    }
}

function Expand-VerifiedPythonPackage([string]$DestinationRoot) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($PythonNuGet)
    try {
        foreach ($Entry in $Archive.Entries) {
            $Name = [string]$Entry.FullName
            if (-not $Name.StartsWith("tools/", [System.StringComparison]::Ordinal)) {
                continue
            }
            $Relative = $Name.Substring(6)
            if ([string]::IsNullOrEmpty($Relative) -or $Relative.EndsWith("/")) {
                continue
            }
            $UnixType = ([int64]$Entry.ExternalAttributes -shr 16) -band 0xF000
            $DosAttributes = [int64]$Entry.ExternalAttributes -band 0xFFFF
            if (
                ($UnixType -ne 0 -and $UnixType -ne 0x8000) -or
                ($DosAttributes -band [int][System.IO.FileAttributes]::ReparsePoint) -ne 0
            ) {
                throw "Python runtime package contains a link-like or non-regular entry: $Name"
            }
            $Destination = Get-SafeRuntimeDestination $DestinationRoot $Relative
            if (-not $Seen.Add($Destination)) {
                throw "Python runtime package contains a duplicate destination: $Relative"
            }
            $Parent = [System.IO.Path]::GetDirectoryName($Destination)
            [System.IO.Directory]::CreateDirectory($Parent) | Out-Null
            Assert-NoReparsePath $Parent "Python runtime extraction parent"
            $Input = $null
            $Output = $null
            $Content = $null
            try {
                $Input = $Entry.Open()
                $Content = New-Object System.IO.MemoryStream
                $Input.CopyTo($Content)
                $Sha256 = [System.Security.Cryptography.SHA256]::Create()
                try {
                    $ExpectedHash = [System.BitConverter]::ToString(
                        $Sha256.ComputeHash($Content.ToArray())
                    ).Replace("-", "").ToLowerInvariant()
                }
                finally {
                    $Sha256.Dispose()
                }
                $Output = [System.IO.File]::Open(
                    $Destination,
                    [System.IO.FileMode]::CreateNew,
                    [System.IO.FileAccess]::Write,
                    [System.IO.FileShare]::None
                )
                $Content.Position = 0
                $Content.CopyTo($Output)
                $Output.Flush()
                if ($ExpectedRuntimeHashes.ContainsKey($Destination)) {
                    throw "Python runtime package contains a duplicate hashed destination: $Relative"
                }
                $ExpectedRuntimeHashes.Add($Destination, $ExpectedHash)
            }
            finally {
                if ($null -ne $Output) { $Output.Dispose() }
                if ($null -ne $Content) { $Content.Dispose() }
                if ($null -ne $Input) { $Input.Dispose() }
            }
        }
    }
    finally {
        $Archive.Dispose()
    }
}

function Get-TclTkMsiRuntimeRecords {
    $Installer = New-Object -ComObject WindowsInstaller.Installer
    $Database = $Installer.GetType().InvokeMember(
        "OpenDatabase",
        [System.Reflection.BindingFlags]::InvokeMethod,
        $null,
        $Installer,
        [object[]]@([string]$TclTkMsi, [int]0)
    )

    function Get-MsiRows([string]$Sql) {
        $View = $Database.GetType().InvokeMember(
            "OpenView",
            [System.Reflection.BindingFlags]::InvokeMethod,
            $null,
            $Database,
            [object[]]@([string]$Sql)
        )
        $View.GetType().InvokeMember(
            "Execute",
            [System.Reflection.BindingFlags]::InvokeMethod,
            $null,
            $View,
            $null
        ) | Out-Null
        $Rows = @()
        while ($true) {
            $Record = $View.GetType().InvokeMember(
                "Fetch",
                [System.Reflection.BindingFlags]::InvokeMethod,
                $null,
                $View,
                $null
            )
            if ($null -eq $Record) { break }
            $Rows += $Record
        }
        return $Rows
    }

    function Get-MsiString($Record, [int]$Field) {
        return [string]$Record.GetType().InvokeMember(
            "StringData",
            [System.Reflection.BindingFlags]::GetProperty,
            $null,
            $Record,
            $Field
        )
    }

    function Get-MsiInteger($Record, [int]$Field) {
        return [int]$Record.GetType().InvokeMember(
            "IntegerData",
            [System.Reflection.BindingFlags]::GetProperty,
            $null,
            $Record,
            $Field
        )
    }

    function Get-MsiTargetName([string]$Value) {
        $Target = @($Value -split ":", 2)[0]
        if ($Target.Contains("|")) {
            $Target = @($Target -split "\|", 2)[1]
        }
        return $Target
    }

    $Directories = @{}
    foreach ($Record in Get-MsiRows 'SELECT `Directory`,`Directory_Parent`,`DefaultDir` FROM `Directory`') {
        $Directories[(Get-MsiString $Record 1)] = @(
            (Get-MsiString $Record 2),
            (Get-MsiString $Record 3)
        )
    }

    function Get-MsiDirectoryPath([string]$DirectoryId) {
        $Parts = New-Object System.Collections.Generic.List[string]
        $Visited = @{}
        while (-not [string]::IsNullOrEmpty($DirectoryId) -and $Directories.ContainsKey($DirectoryId)) {
            if ($Visited.ContainsKey($DirectoryId)) {
                throw "Tcl/Tk MSI directory table contains a cycle."
            }
            $Visited[$DirectoryId] = $true
            $Parent, $DefaultDir = $Directories[$DirectoryId]
            $Name = Get-MsiTargetName $DefaultDir
            if (-not [string]::IsNullOrEmpty($Name) -and $Name -ne "." -and $Name -ne "SourceDir") {
                $Parts.Insert(0, $Name)
            }
            $DirectoryId = $Parent
        }
        return ($Parts -join "\")
    }

    $Components = @{}
    foreach ($Record in Get-MsiRows 'SELECT `Component`,`Directory_` FROM `Component`') {
        $Components[(Get-MsiString $Record 1)] = Get-MsiString $Record 2
    }
    $Hashes = @{}
    foreach ($Record in Get-MsiRows 'SELECT `File_`,`HashPart1`,`HashPart2`,`HashPart3`,`HashPart4` FROM `MsiFileHash`') {
        $Hashes[(Get-MsiString $Record 1)] = @(
            (Get-MsiInteger $Record 2),
            (Get-MsiInteger $Record 3),
            (Get-MsiInteger $Record 4),
            (Get-MsiInteger $Record 5)
        )
    }

    $RuntimeRecords = @{}
    foreach ($Record in Get-MsiRows 'SELECT `File`,`Component_`,`FileName`,`FileSize`,`Version` FROM `File`') {
        $FileId = Get-MsiString $Record 1
        $ComponentId = Get-MsiString $Record 2
        if (-not $Components.ContainsKey($ComponentId)) {
            throw "Tcl/Tk MSI file references an unknown component: $FileId"
        }
        $Directory = Get-MsiDirectoryPath $Components[$ComponentId]
        $FileName = Get-MsiTargetName (Get-MsiString $Record 3)
        $Relative = if ([string]::IsNullOrEmpty($Directory)) {
            $FileName
        }
        else {
            [System.IO.Path]::Combine($Directory, $FileName)
        }
        $Key = $Relative.ToLowerInvariant()
        if ($RuntimeRecords.ContainsKey($Key)) {
            throw "Tcl/Tk MSI contains a duplicate target path: $Relative"
        }
        $RuntimeRecords[$Key] = [pscustomobject]@{
            RelativePath = $Relative
            Size = [int64](Get-MsiInteger $Record 4)
            Version = Get-MsiString $Record 5
            HashParts = if ($Hashes.ContainsKey($FileId)) { @($Hashes[$FileId]) } else { $null }
        }
    }
    return $RuntimeRecords
}

function Invoke-TclTkAdministrativeExtraction([string]$DestinationRoot) {
    $SystemDirectory = [System.Environment]::SystemDirectory
    $MsiExec = Join-Path $SystemDirectory "msiexec.exe"
    if (-not [System.IO.File]::Exists($MsiExec)) {
        throw "Trusted Windows Installer executable is missing: $MsiExec"
    }
    Assert-NoReparsePath $MsiExec "Windows Installer executable"
    $Arguments = @(
        "/a",
        ('"{0}"' -f $TclTkMsi),
        "/qn",
        ('TARGETDIR="{0}"' -f $DestinationRoot),
        "/norestart",
        "/l*v",
        ('"{0}"' -f $RuntimeLog)
    )
    $Process = Start-Process -WindowStyle Hidden -FilePath $MsiExec `
        -WorkingDirectory $SystemDirectory -ArgumentList $Arguments -Wait -PassThru
    if ($Process.ExitCode -ne 0) {
        throw "Tcl/Tk administrative extraction failed with exit code $($Process.ExitCode). See $RuntimeLog"
    }
    Assert-NoReparsePath $DestinationRoot "Tcl/Tk administrative image"
}

function Copy-AuthenticatedTclTkFile(
    [string]$Source,
    [string]$Destination,
    $Record
) {
    $SourceFull = [System.IO.Path]::GetFullPath($Source)
    $DestinationFull = [System.IO.Path]::GetFullPath($Destination)
    if (-not [System.IO.File]::Exists($SourceFull)) {
        throw "Required Tcl/Tk runtime file is missing: $SourceFull"
    }
    Assert-NoReparsePath $SourceFull "Tcl/Tk runtime source"
    $Parent = [System.IO.Path]::GetDirectoryName($DestinationFull)
    [System.IO.Directory]::CreateDirectory($Parent) | Out-Null
    Assert-NoReparsePath $Parent "Tcl/Tk runtime destination parent"
    if ([System.IO.File]::Exists($DestinationFull) -or [System.IO.Directory]::Exists($DestinationFull)) {
        throw "Tcl/Tk runtime destination already exists: $DestinationFull"
    }
    $Input = [System.IO.File]::Open($SourceFull, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        if ($Input.Length -ne $Record.Size) {
            throw "Tcl/Tk runtime file size does not match the signed MSI: $($Record.RelativePath)"
        }
        if ($null -ne $Record.HashParts) {
            $Md5 = [System.Security.Cryptography.MD5]::Create()
            try {
                $Input.Position = 0
                $ActualHash = $Md5.ComputeHash($Input)
            }
            finally {
                $Md5.Dispose()
            }
            for ($Index = 0; $Index -lt 4; $Index++) {
                if ([System.BitConverter]::ToInt32($ActualHash, $Index * 4) -ne $Record.HashParts[$Index]) {
                    throw "Tcl/Tk runtime file hash does not match the signed MSI: $($Record.RelativePath)"
                }
            }
        }
        else {
            if ([string]::IsNullOrWhiteSpace($Record.Version)) {
                throw "Tcl/Tk MSI provides neither a file hash nor version metadata: $($Record.RelativePath)"
            }
            $Signature = Get-AuthenticodeSignature -LiteralPath $SourceFull
            if (
                $Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -or
                $null -eq $Signature.SignerCertificate -or
                [string]$Signature.SignerCertificate.Subject -notlike "*Python Software Foundation*"
            ) {
                throw "Versioned Tcl/Tk runtime file has an unexpected Authenticode signature: $($Record.RelativePath)"
            }
        }
        $Sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $Input.Position = 0
            $ExpectedHash = [System.BitConverter]::ToString(
                $Sha256.ComputeHash($Input)
            ).Replace("-", "").ToLowerInvariant()
        }
        finally {
            $Sha256.Dispose()
        }
        $Input.Position = 0
        $Output = [System.IO.File]::Open(
            $DestinationFull,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        try {
            $Input.CopyTo($Output)
            $Output.Flush()
            if ($ExpectedRuntimeHashes.ContainsKey($DestinationFull)) {
                throw "Tcl/Tk runtime has a duplicate hashed destination: $DestinationFull"
            }
            $ExpectedRuntimeHashes.Add($DestinationFull, $ExpectedHash)
        }
        finally {
            if ($null -ne $Output) { $Output.Dispose() }
        }
    }
    finally {
        $Input.Dispose()
    }
}

function Copy-AuthenticatedTclTkTree(
    [string]$SourceRoot,
    [string]$DestinationRoot,
    [string]$SourceBase,
    [hashtable]$Records,
    [System.Collections.Generic.HashSet[string]]$Copied
) {
    $SourceFull = [System.IO.Path]::GetFullPath($SourceRoot)
    $SourceBaseFull = [System.IO.Path]::GetFullPath($SourceBase).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
    if (-not [System.IO.Directory]::Exists($SourceFull)) {
        throw "Required Tcl/Tk runtime directory is missing: $SourceFull"
    }
    Assert-NoReparsePath $SourceFull "Tcl/Tk runtime directory"
    $Pending = New-Object System.Collections.Generic.Stack[System.IO.DirectoryInfo]
    $Pending.Push([System.IO.DirectoryInfo]$SourceFull)
    while ($Pending.Count -gt 0) {
        $Directory = $Pending.Pop()
        foreach ($Entry in $Directory.EnumerateFileSystemInfos()) {
            if (($Entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Tcl/Tk runtime contains a symbolic link, junction, or reparse point: $($Entry.FullName)"
            }
            $Relative = $Entry.FullName.Substring($SourceFull.Length).TrimStart([System.IO.Path]::DirectorySeparatorChar)
            $Destination = Get-SafeRuntimeDestination $DestinationRoot $Relative
            if (($Entry.Attributes -band [System.IO.FileAttributes]::Directory) -ne 0) {
                [System.IO.Directory]::CreateDirectory($Destination) | Out-Null
                $Pending.Push([System.IO.DirectoryInfo]$Entry.FullName)
            }
            else {
                $MsiRelative = $Entry.FullName.Substring($SourceBaseFull.Length + 1)
                $Key = $MsiRelative.ToLowerInvariant()
                if (-not $Records.ContainsKey($Key)) {
                    throw "Tcl/Tk administrative image contains an unexpected runtime file: $MsiRelative"
                }
                Copy-AuthenticatedTclTkFile $Entry.FullName $Destination $Records[$Key]
                if (-not $Copied.Add($Key)) {
                    throw "Tcl/Tk administrative image contains a duplicate runtime file: $MsiRelative"
                }
            }
        }
    }
}

function Set-ProtectedRuntimeTreeSecurity([string]$Root) {
    $RootFull = [System.IO.Path]::GetFullPath($Root)
    [System.IO.Directory]::SetAccessControl(
        $RootFull,
        (Get-ProtectedRuntimeSecurity $true)
    )
    $Pending = New-Object System.Collections.Generic.Stack[System.IO.DirectoryInfo]
    $Pending.Push([System.IO.DirectoryInfo]$RootFull)
    while ($Pending.Count -gt 0) {
        $Directory = $Pending.Pop()
        foreach ($Entry in $Directory.EnumerateFileSystemInfos()) {
            if (($Entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Application-local Python runtime contains a symbolic link, junction, or reparse point: $($Entry.FullName)"
            }
            if (($Entry.Attributes -band [System.IO.FileAttributes]::Directory) -ne 0) {
                [System.IO.Directory]::SetAccessControl(
                    $Entry.FullName,
                    (Get-ProtectedRuntimeSecurity $true)
                )
                $Pending.Push([System.IO.DirectoryInfo]$Entry.FullName)
            }
            else {
                if (-not [System.IO.File]::Exists($Entry.FullName)) {
                    throw "Application-local Python runtime contains a non-regular file: $($Entry.FullName)"
                }
                [System.IO.File]::SetAccessControl(
                    $Entry.FullName,
                    (Get-ProtectedRuntimeSecurity $false)
                )
            }
        }
    }
}

function Set-ExpectedRuntimeDirectories([string]$Root) {
    $RootFull = [System.IO.Path]::GetFullPath($Root)
    $ExpectedRuntimeDirectories.Clear()
    if (-not $ExpectedRuntimeDirectories.Add($RootFull)) {
        throw "Cannot initialize the expected runtime directory inventory."
    }
    foreach ($FilePath in $ExpectedRuntimeHashes.Keys) {
        $Directory = [System.IO.Path]::GetDirectoryName($FilePath)
        while ($Directory.StartsWith(
            $RootFull,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            $ExpectedRuntimeDirectories.Add($Directory) | Out-Null
            if ([string]::Equals(
                $Directory,
                $RootFull,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                break
            }
            $Directory = [System.IO.Path]::GetDirectoryName($Directory)
        }
    }
}

function Assert-AuthenticatedRuntimeInventory([string]$Root) {
    $RootFull = [System.IO.Path]::GetFullPath($Root)
    $SeenFiles = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $SeenDirectories = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $Pending = New-Object System.Collections.Generic.Stack[System.IO.DirectoryInfo]
    $Pending.Push([System.IO.DirectoryInfo]$RootFull)
    while ($Pending.Count -gt 0) {
        $Directory = $Pending.Pop()
        $DirectoryPath = [System.IO.Path]::GetFullPath($Directory.FullName)
        if (-not $ExpectedRuntimeDirectories.Contains($DirectoryPath)) {
            throw "Application-local Python runtime contains an unexpected directory: $DirectoryPath"
        }
        $SeenDirectories.Add($DirectoryPath) | Out-Null
        foreach ($Entry in $Directory.EnumerateFileSystemInfos()) {
            if (($Entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Application-local Python runtime contains a symbolic link, junction, or reparse point: $($Entry.FullName)"
            }
            if (($Entry.Attributes -band [System.IO.FileAttributes]::Directory) -ne 0) {
                $Pending.Push([System.IO.DirectoryInfo]$Entry.FullName)
                continue
            }
            $Path = [System.IO.Path]::GetFullPath($Entry.FullName)
            if (-not [System.IO.File]::Exists($Path) -or -not $ExpectedRuntimeHashes.ContainsKey($Path)) {
                throw "Application-local Python runtime contains a non-regular or unauthenticated file: $Path"
            }
            $SeenFiles.Add($Path) | Out-Null
        }
    }
    if (
        $SeenFiles.Count -ne $ExpectedRuntimeHashes.Count -or
        $SeenDirectories.Count -ne $ExpectedRuntimeDirectories.Count
    ) {
        throw "Application-local Python runtime inventory is incomplete."
    }
}

function Lock-AuthenticatedRuntimeTree([string]$Root) {
    $RootFull = [System.IO.Path]::GetFullPath($Root)
    Assert-NoReparsePath $RootFull "Application-local Python runtime"
    if ($ExpectedRuntimeDirectories.Count -eq 0) {
        Set-ExpectedRuntimeDirectories $RootFull
    }
    $RequireProtectedSecurity = -not [string]::IsNullOrWhiteSpace(
        $ProtectedRuntimeParent
    )
    $Pending = New-Object System.Collections.Generic.Stack[System.IO.DirectoryInfo]
    $Pending.Push([System.IO.DirectoryInfo]$RootFull)
    while ($Pending.Count -gt 0) {
        $Directory = $Pending.Pop()
        $DirectoryPath = [System.IO.Path]::GetFullPath($Directory.FullName)
        if (-not $ExpectedRuntimeDirectories.Contains($DirectoryPath)) {
            throw "Application-local Python runtime contains an unexpected directory: $DirectoryPath"
        }
        if ($RequireProtectedSecurity) {
            Assert-ProtectedRuntimeSecurity $DirectoryPath $true "Application-local Python runtime directory"
        }
        foreach ($Entry in $Directory.EnumerateFileSystemInfos()) {
            if (($Entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Application-local Python runtime contains a symbolic link, junction, or reparse point: $($Entry.FullName)"
            }
            if (($Entry.Attributes -band [System.IO.FileAttributes]::Directory) -ne 0) {
                $Pending.Push([System.IO.DirectoryInfo]$Entry.FullName)
                continue
            }
            if (-not [System.IO.File]::Exists($Entry.FullName)) {
                throw "Application-local Python runtime contains a non-regular file: $($Entry.FullName)"
            }
            $Path = [System.IO.Path]::GetFullPath($Entry.FullName)
            if ($RequireProtectedSecurity) {
                Assert-ProtectedRuntimeSecurity $Path $false "Application-local Python runtime file"
            }
            if (-not $ExpectedRuntimeHashes.ContainsKey($Path)) {
                throw "Application-local Python runtime contains a file not created from an authenticated source: $($Entry.FullName)"
            }
            $Stream = [System.IO.File]::Open(
                $Path,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::Read
            )
            try {
                $Sha256 = [System.Security.Cryptography.SHA256]::Create()
                try {
                    $ActualHash = [System.BitConverter]::ToString(
                        $Sha256.ComputeHash($Stream)
                    ).Replace("-", "").ToLowerInvariant()
                }
                finally {
                    $Sha256.Dispose()
                }
                if ($ActualHash -ne $ExpectedRuntimeHashes[$Path]) {
                    throw "Application-local Python runtime file changed after authenticated extraction: $Path"
                }
                $LockedPythonFiles.Add($Stream)
                $Stream = $null
            }
            finally {
                if ($null -ne $Stream) { $Stream.Dispose() }
            }
        }
    }
    Assert-AuthenticatedRuntimeInventory $RootFull
}

function Assert-RequiredRuntimeFiles([string]$Root) {
    $Required = @(
        "python.exe",
        "python312.dll",
        "vcruntime140.dll",
        "Lib\encodings\__init__.py",
        "Lib\venv\__init__.py",
        "Lib\ensurepip\__init__.py",
        "Lib\tkinter\__init__.py",
        "DLLs\_tkinter.pyd",
        "DLLs\tcl86t.dll",
        "DLLs\tk86t.dll",
        "DLLs\zlib1.dll",
        "tcl\tcl8.6\init.tcl",
        "tcl\tk8.6\tk.tcl"
    )
    foreach ($Relative in $Required) {
        $Path = Join-Path $Root $Relative
        if (-not [System.IO.File]::Exists($Path)) {
            throw "Application-local Python runtime is incomplete: $Relative"
        }
        Assert-NoReparsePath $Path "Application-local Python runtime file"
    }
}

function Write-ProtectedRuntimeReceipt {
    if ([System.IO.File]::Exists($ProtectedRuntimeReceipt) -or [System.IO.Directory]::Exists($ProtectedRuntimeReceipt)) {
        throw "Protected runtime receipt already exists: $ProtectedRuntimeReceipt"
    }
    $Files = @(
        $ExpectedRuntimeHashes.Keys | Sort-Object | ForEach-Object {
            [pscustomobject]@{
                path = $_.Substring($RuntimeRoot.Length).TrimStart(
                    [System.IO.Path]::DirectorySeparatorChar
                ).Replace("\", "/")
                sha256 = $ExpectedRuntimeHashes[$_]
            }
        }
    )
    $Directories = @(
        $ExpectedRuntimeDirectories | Sort-Object | ForEach-Object {
            $_.Substring($RuntimeRoot.Length).TrimStart(
                [System.IO.Path]::DirectorySeparatorChar
            ).Replace("\", "/")
        }
    )
    $Receipt = [pscustomobject]@{
        schema_version = 1
        verified_stage = $env:DICOMXPHITS_VERIFIED_STAGE
        bundle_root = $BundleRoot
        runtime_root = $RuntimeRoot
        protected_source_root = $ProtectedSourceRoot
        installing_user_sid = $InstallingUserSid.Value
        files = $Files
        directories = $Directories
    }
    $Json = $Receipt | ConvertTo-Json -Depth 5
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Json + [Environment]::NewLine)
    $Stream = [System.IO.File]::Open(
        $ProtectedRuntimeReceipt,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $Stream.Write($Bytes, 0, $Bytes.Length)
        $Stream.Flush()
    }
    finally {
        $Stream.Dispose()
    }
    [System.IO.File]::SetAccessControl(
        $ProtectedRuntimeReceipt,
        (Get-ProtectedRuntimeSecurity $false)
    )
    Assert-ProtectedRuntimeSecurity $ProtectedRuntimeReceipt $false "Protected runtime receipt"
}

function Import-ProtectedRuntimeReceipt {
    if (-not [System.IO.File]::Exists($ProtectedRuntimeReceipt)) {
        throw "Protected runtime construction did not produce its receipt."
    }
    Assert-NoReparsePath $ProtectedRuntimeReceipt "Protected runtime receipt"
    Assert-ProtectedRuntimeSecurity $ProtectedRuntimeReceipt $false "Protected runtime receipt"
    $Stream = [System.IO.File]::Open(
        $ProtectedRuntimeReceipt,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    try {
        $Reader = New-Object System.IO.StreamReader(
            $Stream,
            [System.Text.Encoding]::UTF8,
            $true,
            4096,
            $true
        )
        try {
            $Receipt = $Reader.ReadToEnd() | ConvertFrom-Json
        }
        finally {
            $Reader.Dispose()
        }
        if (
            $Receipt.schema_version -ne 1 -or
            [string]$Receipt.verified_stage -ne $env:DICOMXPHITS_VERIFIED_STAGE -or
            -not [string]::Equals([string]$Receipt.bundle_root, $BundleRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
            -not [string]::Equals([string]$Receipt.runtime_root, $RuntimeRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
            -not [string]::Equals([string]$Receipt.protected_source_root, $ProtectedSourceRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
            [string]$Receipt.installing_user_sid -ne $InstallingUserSid.Value
        ) {
            throw "Protected runtime receipt identity is invalid."
        }
        $ExpectedRuntimeHashes.Clear()
        foreach ($Record in @($Receipt.files)) {
            $Path = Get-SafeRuntimeDestination $RuntimeRoot ([string]$Record.path)
            $Hash = [string]$Record.sha256
            if ($Hash -notmatch "^[0-9a-f]{64}$" -or $ExpectedRuntimeHashes.ContainsKey($Path)) {
                throw "Protected runtime receipt contains an invalid file record."
            }
            $ExpectedRuntimeHashes.Add($Path, $Hash)
        }
        $ExpectedRuntimeDirectories.Clear()
        foreach ($Relative in @($Receipt.directories)) {
            $Path = if ([string]::IsNullOrEmpty([string]$Relative)) {
                $RuntimeRoot
            }
            else {
                Get-SafeRuntimeDestination $RuntimeRoot ([string]$Relative)
            }
            if (-not $ExpectedRuntimeDirectories.Add($Path)) {
                throw "Protected runtime receipt contains a duplicate directory record."
            }
        }
        if ($ExpectedRuntimeHashes.Count -eq 0 -or $ExpectedRuntimeDirectories.Count -eq 0) {
            throw "Protected runtime receipt inventory is empty."
        }
        $LockedPythonFiles.Add($Stream)
        $Stream = $null
    }
    finally {
        if ($null -ne $Stream) { $Stream.Dispose() }
    }
}

function New-AuthenticatedPythonRuntime {
    if ([System.IO.File]::Exists($RuntimeRoot) -or [System.IO.Directory]::Exists($RuntimeRoot)) {
        throw "Protected Python runtime already exists. Use a fresh verified bundle extraction path: $RuntimeRoot"
    }
    if (
        [System.IO.File]::Exists($ProtectedRuntimeReceipt) -or
        [System.IO.Directory]::Exists($ProtectedRuntimeReceipt) -or
        [System.IO.File]::Exists($RuntimeLog) -or
        [System.IO.Directory]::Exists($RuntimeLog)
    ) {
        throw "Protected runtime control content already exists. Use a fresh verified bundle extraction path."
    }

    Assert-IsolatedVerifierDirectory
    Add-SignedFileLock $NuGetVerifier "NuGet verifier" "*Microsoft Corporation*"
    Add-SignedFileLock $TclTkMsi "CPython Tcl/Tk MSI" "*Python Software Foundation*"
    if (-not [System.IO.File]::Exists($PythonNuGet)) {
        throw "Python NuGet package is missing: $PythonNuGet"
    }
    Assert-NoReparsePath $PythonNuGet "Python NuGet package"
    $PackageStream = [System.IO.File]::Open($PythonNuGet, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    $LockedPythonFiles.Add($PackageStream)

    Invoke-NuGetPackageVerification
    $TclTkRecords = Get-TclTkMsiRuntimeRecords
    New-ProtectedRuntimeDirectory $RuntimeRoot "Protected Python runtime"
    Assert-NoReparsePath $RuntimeRoot "Application-local Python runtime"
    $TclTkStaging = New-BoundedWorkingDirectory "tcltk"
    Expand-VerifiedPythonPackage $RuntimeRoot
    Invoke-TclTkAdministrativeExtraction $TclTkStaging
    Assert-NoReparsePath $RuntimeLog "Windows Installer runtime log"
    [System.IO.File]::SetAccessControl(
        $RuntimeLog,
        (Get-ProtectedRuntimeSecurity $false)
    )
    Assert-ProtectedRuntimeSecurity $RuntimeLog $false "Windows Installer runtime log"

    $CopiedTclTkFiles = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $ExpectedTclTkFiles = @(
        $TclTkRecords.Keys | Where-Object {
            $_ -like "lib\tkinter\*" -or
            $_ -like "tcl\*" -or
            $_ -in @("dlls\_tkinter.pyd", "dlls\tcl86t.dll", "dlls\tk86t.dll", "dlls\zlib1.dll")
        }
    )
    foreach ($Name in @("_tkinter.pyd", "tcl86t.dll", "tk86t.dll", "zlib1.dll")) {
        $Relative = "dlls\$Name"
        if (-not $TclTkRecords.ContainsKey($Relative)) {
            throw "Signed Tcl/Tk MSI is missing a required runtime record: $Relative"
        }
        Copy-AuthenticatedTclTkFile `
            (Join-Path $TclTkStaging "DLLs\$Name") `
            (Join-Path $RuntimeRoot "DLLs\$Name") `
            $TclTkRecords[$Relative]
        if (-not $CopiedTclTkFiles.Add($Relative)) {
            throw "Tcl/Tk runtime contains a duplicate selected file: $Relative"
        }
    }
    Copy-AuthenticatedTclTkTree `
        (Join-Path $TclTkStaging "Lib\tkinter") `
        (Join-Path $RuntimeRoot "Lib\tkinter") `
        $TclTkStaging $TclTkRecords $CopiedTclTkFiles
    Copy-AuthenticatedTclTkTree `
        (Join-Path $TclTkStaging "tcl") `
        (Join-Path $RuntimeRoot "tcl") `
        $TclTkStaging $TclTkRecords $CopiedTclTkFiles
    if (
        $CopiedTclTkFiles.Count -ne $ExpectedTclTkFiles.Count -or
        @($ExpectedTclTkFiles | Where-Object { -not $CopiedTclTkFiles.Contains($_) }).Count -ne 0
    ) {
        throw "Tcl/Tk administrative image does not match the signed MSI runtime inventory."
    }
    Assert-RequiredRuntimeFiles $RuntimeRoot
    Copy-ProtectedBundleSnapshot
    Assert-NoReparsePath $RuntimeRoot "Application-local Python runtime"
    Set-ExpectedRuntimeDirectories $RuntimeRoot
    Set-ProtectedRuntimeTreeSecurity $RuntimeRoot
    Lock-AuthenticatedRuntimeTree $RuntimeRoot

    Add-SignedFileLock (Join-Path $RuntimeRoot "python.exe") "Python executable" "*Python Software Foundation*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "python312.dll") "Python runtime DLL" "*Python Software Foundation*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "vcruntime140.dll") "Visual C++ runtime DLL" "*Microsoft Windows Software Compatibility Publisher*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "DLLs\_tkinter.pyd") "Tkinter extension" "*Python Software Foundation*"

    Write-ProtectedRuntimeReceipt

    return (Join-Path $RuntimeRoot "python.exe")
}

try {
    Assert-NoReparsePath $BundleRoot "Bundle root"
    Assert-TrustedPowerShellProcess | Out-Null
    if ($env:DICOMXPHITS_ELEVATED_ACTION -eq "construct-runtime") {
        if (
            -not (Test-IsAdministrator) -or
            $env:DICOMXPHITS_ELEVATED_STAGE -ne $env:DICOMXPHITS_VERIFIED_STAGE
        ) {
            throw "Protected runtime construction lacks verified administrator state."
        }
        Initialize-ProtectedRuntimePath
        $null = New-AuthenticatedPythonRuntime
        exit 0
    }
    if (Test-IsAdministrator) {
        throw "Start install_offline.cmd without elevation; approve only its verified administrator prompt."
    }

    $env:DICOMXPHITS_INSTALLING_USER_SID = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    Set-ProtectedRuntimeIdentity
    Invoke-ElevatedRuntimeConstruction
    Import-ProtectedRuntimeReceipt
    Assert-NoReparsePath $RuntimeRoot "Application-local Python runtime"
    Lock-AuthenticatedRuntimeTree $RuntimeRoot
    Add-SignedFileLock (Join-Path $RuntimeRoot "python.exe") "Python executable" "*Python Software Foundation*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "python312.dll") "Python runtime DLL" "*Python Software Foundation*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "vcruntime140.dll") "Visual C++ runtime DLL" "*Microsoft Windows Software Compatibility Publisher*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "DLLs\_tkinter.pyd") "Tkinter extension" "*Python Software Foundation*"
    $SelectedPython = Join-Path $RuntimeRoot "python.exe"
    $Probe = & $SelectedPython -I -S -B -c "import sys;print('|'.join((sys.implementation.name,str(sys.version_info.major),str(sys.version_info.minor),'64' if sys.maxsize > 2**32 else '32')))" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Application-local Python probe failed."
    }
    $Data = @(($Probe | Select-Object -Last 1) -split '\|')
    if ($Data.Count -ne 4 -or $Data[0] -ne "cpython" -or $Data[1] -ne "3" -or $Data[2] -ne "12" -or $Data[3] -ne "64") {
        throw "Application-local runtime is not CPython 3.12 x64."
    }

    Write-Host "Using authenticated application-local Python: $SelectedPython"
    Write-InstallLog "Initial bundle verification passed; application-local Python runtime sources and files remained locked."
    $ProtectedHelper = Join-Path $ProtectedSourceRoot "tools\offline_install.py"
    & $SelectedPython -I -S -B $ProtectedHelper `
        --bundle-root $ProtectedSourceRoot --install-root $BundleRoot
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
    foreach ($WorkingDirectory in $CreatedWorkingDirectories) {
        $WorkingRoot = if ([string]::IsNullOrWhiteSpace($ProtectedRuntimeParent)) {
            $BundleRoot
        }
        else {
            $ProtectedRuntimeParent
        }
        $WorkingPrefix = [System.IO.Path]::GetFullPath($WorkingRoot).TrimEnd(
            [System.IO.Path]::DirectorySeparatorChar
        ) + [System.IO.Path]::DirectorySeparatorChar
        if (
            [System.IO.Directory]::Exists($WorkingDirectory) -and
            $WorkingDirectory.StartsWith($WorkingPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
            [System.IO.Path]::GetFileName($WorkingDirectory).StartsWith(".python-runtime-", [System.StringComparison]::Ordinal)
        ) {
            [System.IO.Directory]::Delete($WorkingDirectory, $true)
        }
    }
}
