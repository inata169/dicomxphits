@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>&1

rem Security bootstrap: the only executable started before bundle verification is
rem Windows PowerShell from the Windows system directory. Never search CWD/PATH.
for %%I in ("%~dp0.") do set "BundleRoot=%%~fI"
rem Remove any inherited override so cmd.exe exposes its own dynamic app directory.
set "__APPDIR__="
set "TrustedPowerShell=%__APPDIR__%WindowsPowerShell\v1.0\powershell.exe"
set "DICOMXPHITS_BUNDLE_ROOT=%BundleRoot%"

echo dicomxphits offline installer
echo.
echo IMPORTANT: Copy and extract this ZIP to a writable local-disk folder first.
echo Do not create the editable environment directly on USB storage.
echo.

if not exist "%TrustedPowerShell%" (
  echo ERROR: Trusted Windows PowerShell was not found in the Windows system directory. 1>&2
  exit /b 1
)

"%TrustedPowerShell%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';Set-StrictMode -Version Latest;" ^
  "function Get-Sha256([IO.Stream]$stream){$sha=[Security.Cryptography.SHA256]::Create();try{$stream.Position=0;return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}};" ^
  "function Assert-SafeDirectory([string]$path){$cursor=[IO.DirectoryInfo][IO.Path]::GetFullPath($path);while($null-ne $cursor){if(($cursor.Attributes-band [IO.FileAttributes]::ReparsePoint)-ne 0){throw ('Bundle path contains a symbolic link, junction, or reparse point: '+$cursor.FullName)};$cursor=$cursor.Parent}};" ^
  "$root=[IO.Path]::GetFullPath($env:DICOMXPHITS_BUNDLE_ROOT);Assert-SafeDirectory $root;" ^
  "$prefix=$root.TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar;$checksumPath=Join-Path $root 'SHA256SUMS.txt';" ^
  "if(-not [IO.File]::Exists($checksumPath)){throw ('Missing checksum inventory: '+$checksumPath)};" ^
  "$dangerous=@('.exe','.com','.bat','.cmd','.ps1','.psm1','.vbs','.js','.jse','.wsf','.wsh','.scr','.msi');foreach($entry in [IO.Directory]::EnumerateFileSystemEntries($root)){if(([IO.File]::GetAttributes($entry)-band [IO.FileAttributes]::ReparsePoint)-ne 0){throw ('Unexpected reparse point at bundle root: '+$entry)};if([IO.File]::Exists($entry)-and $dangerous-contains [IO.Path]::GetExtension($entry).ToLowerInvariant()){if([IO.Path]::GetFileName($entry)-ine 'install_offline.cmd'){throw ('Unexpected executable or script at bundle root: '+$entry)}}};" ^
  "$seen=@{};$lockedFiles=New-Object Collections.Generic.List[IO.Stream];$exitCode=1;" ^
  "try{" ^
  "if(([IO.File]::GetAttributes($checksumPath)-band [IO.FileAttributes]::ReparsePoint)-ne 0){throw 'SHA256SUMS.txt is a reparse point'};$checksumStream=[IO.File]::Open($checksumPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read);$reader=[IO.StreamReader]::new($checksumStream,[Text.Encoding]::UTF8,$true,4096,$true);try{$checksumText=$reader.ReadToEnd()}finally{$reader.Dispose()};$lockedFiles.Add($checksumStream);$lines=$checksumText-split '\r?\n';foreach($line in $lines){if([string]::IsNullOrWhiteSpace($line)){continue};if($line-notmatch '^([0-9a-f]{64}) \*(.+)$'){throw ('Invalid checksum line: '+$line)};$expected=$matches[1];$relative=$matches[2].Replace('/',[IO.Path]::DirectorySeparatorChar);if([IO.Path]::IsPathRooted($relative)-or $relative.Contains(':')){throw ('Unsafe checksum path: '+$relative)};$full=[IO.Path]::GetFullPath((Join-Path $root $relative));if(-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw ('Escaping checksum path: '+$relative)};Assert-SafeDirectory ([IO.Path]::GetDirectoryName($full));$key=$full.ToLowerInvariant();if($seen.ContainsKey($key)){throw ('Duplicate checksum path: '+$relative)};if(-not [IO.File]::Exists($full)){throw ('Missing bundle payload: '+$relative)};if(([IO.File]::GetAttributes($full)-band [IO.FileAttributes]::ReparsePoint)-ne 0){throw ('Bundle payload is a reparse point: '+$relative)};$stream=[IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read);try{$actual=Get-Sha256 $stream;if($actual-ne $expected){throw ('SHA-256 mismatch: '+$relative)};$seen[$key]=$expected;$lockedFiles.Add($stream);$stream=$null}finally{if($null-ne $stream){$stream.Dispose()}}};" ^
  "if($seen.Count-eq 0){throw 'SHA256SUMS.txt is empty'};$required=@('install_offline.cmd','bundle-manifest.json','tools/offline_install.py','tools/install_offline_verified.ps1','python/python-3.12.10-amd64.exe');foreach($item in $required){$full=[IO.Path]::GetFullPath((Join-Path $root $item));if(-not $seen.ContainsKey($full.ToLowerInvariant())){throw ('Required checksum entry is missing: '+$item)}};" ^
  "$manifestPath=Join-Path $root 'bundle-manifest.json';$manifest=Get-Content -Raw -LiteralPath $manifestPath -Encoding UTF8|ConvertFrom-Json;if($manifest.schema_version-ne 1-or $null-eq $manifest.files){throw 'Unsupported or malformed bundle manifest'};$records=@($manifest.files);if($records.Count-eq 0){throw 'Bundle manifest files list is empty'};$manifestSeen=@{};foreach($record in $records){$manifestRelative=[string]$record.path;if([string]::IsNullOrWhiteSpace($manifestRelative)){throw 'Manifest file path is missing'};$relative=$manifestRelative.Replace('/',[IO.Path]::DirectorySeparatorChar);if([IO.Path]::IsPathRooted($relative)-or $relative.Contains(':')){throw ('Unsafe manifest path: '+$manifestRelative)};$full=[IO.Path]::GetFullPath((Join-Path $root $relative));if(-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw ('Escaping manifest path: '+$manifestRelative)};$key=$full.ToLowerInvariant();if($manifestSeen.ContainsKey($key)){throw ('Duplicate manifest path: '+$manifestRelative)};$manifestSeen[$key]=$true;$manifestHash=[string]$record.sha256;if($manifestHash-notmatch '^[0-9a-f]{64}$'){throw ('Invalid manifest SHA-256: '+$manifestRelative)};if(-not $seen.ContainsKey($key)-or $seen[$key]-ne $manifestHash){throw ('Manifest/checksum mismatch: '+$manifestRelative)};if(([long]$record.size)-ne ([IO.FileInfo]$full).Length){throw ('Manifest size mismatch: '+$manifestRelative)}};" ^
  "$manifestKey=$manifestPath.ToLowerInvariant();if($seen.Count-ne ($manifestSeen.Count+1)){throw 'Checksum inventory and manifest file set differ'};foreach($key in $seen.Keys){if($key-ne $manifestKey-and-not $manifestSeen.ContainsKey($key)){throw 'Checksum entry is absent from manifest'}};Write-Host 'Initial SHA-256 verification passed.';Write-Host 'Protected payloads are read-locked during installation.';" ^
  "$env:DICOMXPHITS_VERIFIED_STAGE=[Guid]::NewGuid().ToString('N');& (Join-Path $root 'tools\install_offline_verified.ps1');$exitCode=$LASTEXITCODE;if($null-eq $exitCode){$exitCode=0}" ^
  "}catch{Write-Error $_}finally{[Environment]::SetEnvironmentVariable('DICOMXPHITS_VERIFIED_STAGE',$null,'Process');foreach($stream in $lockedFiles){$stream.Dispose()}};exit $exitCode"

if errorlevel 1 (
  echo ERROR: Verified offline installation failed. 1>&2
  exit /b 1
)
exit /b 0
