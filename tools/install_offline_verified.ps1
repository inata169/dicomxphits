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
$LogFile = Join-Path $BundleRoot "offline-install.log"
$RuntimeLog = Join-Path $BundleRoot "python-runtime.log"
$PythonNuGetSignerSha256 = "1F4B311D9ACC115C8DC8018B5A49E00FCE6DA8E2855F9F014CA6F34570BC482D"
$LockedPythonFiles = New-Object System.Collections.Generic.List[System.IO.Stream]
$CreatedWorkingDirectories = New-Object System.Collections.Generic.List[string]
$ExpectedRuntimeHashes = New-Object 'System.Collections.Generic.Dictionary[string,string]' ([System.StringComparer]::OrdinalIgnoreCase)

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
    $Path = [System.IO.Path]::GetFullPath((Join-Path $BundleRoot $Name))
    if (-not $Path.StartsWith($BundlePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Runtime working directory escaped the bundle root: $Path"
    }
    if ([System.IO.File]::Exists($Path) -or [System.IO.Directory]::Exists($Path)) {
        throw "Runtime working directory already exists: $Path"
    }
    [System.IO.Directory]::CreateDirectory($Path) | Out-Null
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

function Lock-AuthenticatedRuntimeTree([string]$Root) {
    $RootFull = [System.IO.Path]::GetFullPath($Root)
    Assert-NoReparsePath $RootFull "Application-local Python runtime"
    $Pending = New-Object System.Collections.Generic.Stack[System.IO.DirectoryInfo]
    $Pending.Push([System.IO.DirectoryInfo]$RootFull)
    while ($Pending.Count -gt 0) {
        $Directory = $Pending.Pop()
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
    if (@([System.IO.Directory]::EnumerateFiles($RootFull, "*", [System.IO.SearchOption]::AllDirectories)).Count -ne $ExpectedRuntimeHashes.Count) {
        throw "Application-local Python runtime inventory is incomplete."
    }
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

function New-AuthenticatedPythonRuntime {
    if ([System.IO.File]::Exists($RuntimeRoot) -or [System.IO.Directory]::Exists($RuntimeRoot)) {
        throw "Application-local Python runtime already exists. Use a fresh verified bundle extraction: $RuntimeRoot"
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
    [System.IO.Directory]::CreateDirectory($RuntimeRoot) | Out-Null
    Assert-NoReparsePath $RuntimeRoot "Application-local Python runtime"
    $TclTkStaging = New-BoundedWorkingDirectory "tcltk"
    Expand-VerifiedPythonPackage $RuntimeRoot
    Invoke-TclTkAdministrativeExtraction $TclTkStaging

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
    Assert-NoReparsePath $RuntimeRoot "Application-local Python runtime"
    Lock-AuthenticatedRuntimeTree $RuntimeRoot

    Add-SignedFileLock (Join-Path $RuntimeRoot "python.exe") "Python executable" "*Python Software Foundation*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "python312.dll") "Python runtime DLL" "*Python Software Foundation*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "vcruntime140.dll") "Visual C++ runtime DLL" "*Microsoft Windows Software Compatibility Publisher*"
    Add-SignedFileLock (Join-Path $RuntimeRoot "DLLs\_tkinter.pyd") "Tkinter extension" "*Python Software Foundation*"

    return (Join-Path $RuntimeRoot "python.exe")
}

try {
    Assert-NoReparsePath $BundleRoot "Bundle root"
    $SelectedPython = New-AuthenticatedPythonRuntime
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
    & $SelectedPython -I -S -B $Helper --bundle-root $BundleRoot
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
        if (
            [System.IO.Directory]::Exists($WorkingDirectory) -and
            $WorkingDirectory.StartsWith($BundlePrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
            [System.IO.Path]::GetFileName($WorkingDirectory).StartsWith(".python-runtime-", [System.StringComparison]::Ordinal)
        ) {
            [System.IO.Directory]::Delete($WorkingDirectory, $true)
        }
    }
}
