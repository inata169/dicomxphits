@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>&1

for %%I in ("%~dp0.") do set "DICOMXPHITS_BUNDLE_ROOT=%%~fI"
set "__APPDIR__="
set "TrustedPowerShell=%__APPDIR__%WindowsPowerShell\v1.0\powershell.exe"
set "COR_ENABLE_PROFILING="
set "COR_PROFILER="
set "COR_PROFILER_PATH="
set "COR_PROFILER_PATH_32="
set "COR_PROFILER_PATH_64="
set "CORECLR_ENABLE_PROFILING="
set "CORECLR_PROFILER="
set "CORECLR_PROFILER_PATH="
set "CORECLR_PROFILER_PATH_32="
set "CORECLR_PROFILER_PATH_64="
set "APPDOMAIN_MANAGER_ASM="
set "APPDOMAIN_MANAGER_TYPE="
set "COMPLUS_ApplicationMigrationRuntimeActivationConfigPath="
set "COMPLUS_Version="
set "DOTNET_STARTUP_HOOKS="
set "DOTNET_ADDITIONAL_DEPS="
set "DOTNET_SHARED_STORE="
cd /d "%__APPDIR__%"

echo dicomxphits offline uninstaller
echo.
echo This removes only this extracted installation and its matching protected runtime.
echo Case folders, external tools, other installations, and GUI settings are preserved.
echo.

if not exist "%TrustedPowerShell%" (
  echo ERROR: Trusted Windows PowerShell was not found in the Windows system directory. 1>&2
  exit /b 1
)

"%TrustedPowerShell%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$env:PSModulePath=[IO.Path]::Combine($PSHOME,'Modules');$ErrorActionPreference='Stop';Set-StrictMode -Version Latest;" ^
  "function Get-Sha256([IO.Stream]$stream){$sha=[Security.Cryptography.SHA256]::Create();try{$stream.Position=0;return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}};" ^
  "function Assert-SafeDirectory([string]$path){$cursor=[IO.DirectoryInfo][IO.Path]::GetFullPath($path);while($null-ne $cursor){if(($cursor.Attributes-band [IO.FileAttributes]::ReparsePoint)-ne 0){throw ('Uninstall path contains a symbolic link, junction, or reparse point: '+$cursor.FullName)};$cursor=$cursor.Parent}};" ^
  "$root=[IO.Path]::GetFullPath($env:DICOMXPHITS_BUNDLE_ROOT);Assert-SafeDirectory $root;$prefix=$root.TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar;$checksumPath=Join-Path $root 'SHA256SUMS.txt';if(-not [IO.File]::Exists($checksumPath)){throw ('Missing checksum inventory: '+$checksumPath)};" ^
  "$seen=@{};$seenPaths=@{};$lockedFiles=New-Object Collections.Generic.List[IO.Stream];$lockedDirectories=@();$directoryLockScript=$null;$exitCode=1;" ^
  "try{if(([IO.File]::GetAttributes($checksumPath)-band [IO.FileAttributes]::ReparsePoint)-ne 0){throw 'SHA256SUMS.txt is a reparse point'};$checksumStream=[IO.File]::Open($checksumPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read -bor [IO.FileShare]::Delete);$reader=[IO.StreamReader]::new($checksumStream,[Text.Encoding]::UTF8,$true,4096,$true);try{$checksumText=$reader.ReadToEnd()}finally{$reader.Dispose()};$lockedFiles.Add($checksumStream);foreach($line in ($checksumText-split '\r?\n')){if([string]::IsNullOrWhiteSpace($line)){continue};if($line-notmatch '^([0-9a-f]{64}) \*(.+)$'){throw ('Invalid checksum line: '+$line)};$expected=$matches[1];$relative=$matches[2].Replace('/',[IO.Path]::DirectorySeparatorChar);if([IO.Path]::IsPathRooted($relative)-or $relative.Contains(':')){throw ('Unsafe checksum path: '+$relative)};$full=[IO.Path]::GetFullPath((Join-Path $root $relative));if(-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw ('Escaping checksum path: '+$relative)};Assert-SafeDirectory ([IO.Path]::GetDirectoryName($full));$key=$full.ToLowerInvariant();if($seen.ContainsKey($key)){throw ('Duplicate checksum path: '+$relative)};if(-not [IO.File]::Exists($full)){throw ('Missing bundle payload: '+$relative)};if(([IO.File]::GetAttributes($full)-band [IO.FileAttributes]::ReparsePoint)-ne 0){throw ('Bundle payload is a reparse point: '+$relative)};$stream=[IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read -bor [IO.FileShare]::Delete);try{$actual=Get-Sha256 $stream;if($actual-ne $expected){throw ('SHA-256 mismatch: '+$relative)};if($relative-ieq 'tools\lock_bundle_directories.ps1'){$stream.Position=0;$lockReader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8,$true,4096,$true);try{$directoryLockScript=$lockReader.ReadToEnd()}finally{$lockReader.Dispose()}};$seen[$key]=$expected;$seenPaths[$key]=$full;$lockedFiles.Add($stream);$stream=$null}finally{if($null-ne $stream){$stream.Dispose()}}};" ^
  "$required=@('uninstall_offline.cmd','bundle-manifest.json','tools/uninstall_offline_verified.ps1','tools/lock_bundle_directories.ps1');foreach($item in $required){$full=[IO.Path]::GetFullPath((Join-Path $root $item));if(-not $seen.ContainsKey($full.ToLowerInvariant())){throw ('Required uninstall checksum entry is missing: '+$item)}};$manifestPath=Join-Path $root 'bundle-manifest.json';$manifest=Get-Content -Raw -LiteralPath $manifestPath -Encoding UTF8|ConvertFrom-Json;if($manifest.schema_version-ne 1-or $null-eq $manifest.files){throw 'Unsupported or malformed bundle manifest'};$records=@($manifest.files);if($records.Count-eq 0){throw 'Bundle manifest files list is empty'};$manifestSeen=@{};foreach($record in $records){$manifestRelative=[string]$record.path;if([string]::IsNullOrWhiteSpace($manifestRelative)){throw 'Manifest file path is missing'};$relative=$manifestRelative.Replace('/',[IO.Path]::DirectorySeparatorChar);if([IO.Path]::IsPathRooted($relative) -or $relative.Contains(':') -or $relative.Split([IO.Path]::DirectorySeparatorChar) -contains '..'){throw ('Unsafe manifest path: '+$manifestRelative)};$full=[IO.Path]::GetFullPath((Join-Path $root $relative));if(-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw ('Escaping manifest path: '+$manifestRelative)};$key=$full.ToLowerInvariant();if($manifestSeen.ContainsKey($key)){throw ('Duplicate manifest path: '+$manifestRelative)};$manifestSeen[$key]=$true;$recordHash=[string]$record.sha256;if($recordHash -notmatch '^[0-9a-f]{64}$' -or -not $seen.ContainsKey($key) -or $seen[$key] -ne $recordHash -or ([long]$record.size) -ne ([IO.FileInfo]$full).Length){throw ('Manifest/checksum mismatch: '+$manifestRelative)}};$manifestKey=$manifestPath.ToLowerInvariant();if($seen.Count -ne ($manifestSeen.Count+1)){throw 'Checksum inventory and manifest file set differ'};foreach($key in $seen.Keys){if($key -ne $manifestKey -and -not $manifestSeen.ContainsKey($key)){throw 'Checksum entry is absent from manifest'}};" ^
  "if([string]::IsNullOrWhiteSpace($directoryLockScript)){throw 'Authenticated directory lock helper is unavailable'};. ([scriptblock]::Create($directoryLockScript));$lockedDirectories=@(Lock-BundleDirectoryPaths $root @($seenPaths.Values));foreach($key in @($seen.Keys)){$path=$seenPaths[$key];$stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read);try{if((Get-Sha256 $stream)-ne$seen[$key]){throw ('Bundle payload changed before uninstall verification: '+$path)};$lockedFiles.Add($stream);$stream=$null}finally{if($null-ne$stream){$stream.Dispose()}}};$env:DICOMXPHITS_UNINSTALL_VERIFIED_STAGE=[Guid]::NewGuid().ToString('N');& (Join-Path $root 'tools\uninstall_offline_verified.ps1');$exitCode=$LASTEXITCODE;if($null-eq$exitCode){$exitCode=0}" ^
  "}catch{Write-Error ([string]$_.Exception.Message)}finally{[Environment]::SetEnvironmentVariable('DICOMXPHITS_UNINSTALL_VERIFIED_STAGE',$null,'Process');foreach($stream in $lockedFiles){$stream.Dispose()};foreach($handle in $lockedDirectories){$handle.Dispose()}};exit $exitCode"
if errorlevel 1 (
  echo ERROR: Verified offline uninstallation failed. 1>&2
  exit /b 1
)
exit /b 0
