$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($null -eq ("Dicomxphits.BundleDirectoryNative" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace Dicomxphits {
    public static class BundleDirectoryNative {
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
    }
}
'@
}

function Lock-BundleDirectoryPaths(
    [string]$BundleRoot,
    [string[]]$PayloadPaths
) {
    $BundleDirectory = [System.IO.DirectoryInfo][System.IO.Path]::GetFullPath(
        $BundleRoot
    )
    if ($null -eq $BundleDirectory.Parent) {
        throw "Bundle root cannot be a filesystem root: $BundleRoot"
    }
    $BundlePath = $BundleDirectory.FullName
    $BundlePrefix = $BundlePath.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    $DirectoryPaths = New-Object 'System.Collections.Generic.HashSet[string]' (
        [System.StringComparer]::OrdinalIgnoreCase
    )
    foreach ($PayloadPath in $PayloadPaths) {
        $FullPayloadPath = [System.IO.Path]::GetFullPath($PayloadPath)
        if (-not $FullPayloadPath.StartsWith(
            $BundlePrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Bundle payload is outside the bundle root: $PayloadPath"
        }
        $Cursor = [System.IO.DirectoryInfo][System.IO.Path]::GetDirectoryName(
            $FullPayloadPath
        )
        while ($null -ne $Cursor) {
            $DirectoryPaths.Add($Cursor.FullName) | Out-Null
            if ($Cursor.FullName.Equals(
                $BundlePath,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                break
            }
            $Cursor = $Cursor.Parent
        }
        if ($null -eq $Cursor) {
            throw "Bundle payload parent chain escaped the bundle root: $PayloadPath"
        }
    }

    $Handles = New-Object 'System.Collections.Generic.List[Microsoft.Win32.SafeHandles.SafeFileHandle]'
    try {
        foreach ($DirectoryPath in @($DirectoryPaths | Sort-Object Length)) {
            if (-not [System.IO.Directory]::Exists($DirectoryPath)) {
                throw "Bundle directory disappeared before locking: $DirectoryPath"
            }
            if (
                ([System.IO.File]::GetAttributes($DirectoryPath) -band
                    [System.IO.FileAttributes]::ReparsePoint) -ne 0
            ) {
                throw "Bundle directory is a reparse point: $DirectoryPath"
            }
            $Handle = [Dicomxphits.BundleDirectoryNative]::CreateFile(
                $DirectoryPath,
                0x10080,
                [System.IO.FileShare]::Read -bor [System.IO.FileShare]::Write,
                [System.IntPtr]::Zero,
                [System.IO.FileMode]::Open,
                0x02000000,
                [System.IntPtr]::Zero
            )
            if ($Handle.IsInvalid) {
                $ErrorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
                $Handle.Dispose()
                if ($ErrorCode -eq 5) {
                    # Without DELETE access this token cannot rename the directory.
                    continue
                }
                $Message = "Cannot lock bundle directory against rename: " +
                    "$DirectoryPath (Windows error $ErrorCode)"
                throw (New-Object System.ComponentModel.Win32Exception(
                    $ErrorCode,
                    $Message
                ))
            }
            $Handles.Add($Handle)
        }
        return $Handles
    }
    catch {
        foreach ($Handle in $Handles) { $Handle.Dispose() }
        throw
    }
}
