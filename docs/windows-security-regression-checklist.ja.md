# Windowsネイティブ・セキュリティ回帰確認

この手順は、Linux/WSLでは実証できないCMD探索、Windows junction、reparse pointを、
患者情報や外部PHITS製品を使わずに確認するためのものです。Windows 10/11 x64、
CPython 3.12 x64、Git checkout上の通常のNTFSローカルフォルダーで実行します。

## 自動テスト

リポジトリ直下のPowerShellで次を実行します。

```powershell
python -m pytest tests/test_offline_install.py tests/test_security_boundaries.py -vv -p no:cacheprovider
```

次を確認します。

- `Windows bootstrap behavior`、`Windows cmd.exe behavior`、
  `real Windows junction behavior`によるskipが0件である
- 日本語と空白を含む展開pathのbootstrap controlが成功する
- root直下に偽の`powershell.exe`、`python.exe`、`py.exe`がある各caseが、
  helperを実行せず安全側で拒否される
- `cmd.exe /d /c mklink /J`で作った実junction経由の書込みが拒否され、
  test-controlled outside directoryに出力が作られない

## phits2dicom staging境界

今回のDev Containerクロスチェック後の修正は、実phits2dicomを使用せず、合成DICOMと
fake runnerで確認します。リポジトリ直下のPowerShellで次を実行します。

```powershell
python -m pytest tests/test_prepare_rtdose.py::test_run_requires_executable_and_detects_new_dicom tests/test_prepare_rtdose.py::test_run_rejects_final_only_phits2dicom_output_and_cleans_staging -vv -p no:cacheprovider
```

両方がpassし、次を確認します。

- fake runnerのcwdがランダムな`.p2d-*\d` staging directoryであり、永続的な
  `rtdose\DATfiles`ではない
- fake runnerへ渡すstdin中のtemplate、CT、dose、PHITS output、および出力directoryが
  staging内を指す
- 終了code 0でもstagingにexpected DICOMがなければ`stage_status`が`failed`となり、
  最終出力先へ直接作られたDICOMを後処理または成功扱いしない
- cwd相対の想定外fileはstaging cleanupで削除され、最終`DATfiles`へ作られない
- 正常なstaging出力はguard経由で最終出力へ昇格され、既存のRTDOSE意味論testがpassする

## 実bundleの処理順序

オンラインWindows PCでレビュー済みcommitからbundleを作成します。

```powershell
.\tools\prepare_offline_bundle.ps1
```

生成ZIPを日本語と空白を含む通常のlocal pathへ展開します。展開rootに想定外の
実行ファイルがないcontrolで`install_offline.cmd`を実行し、次を確認します。

```powershell
.\install_offline.cmd
```

- `Initial SHA-256 verification passed.`より前にbundle内installer/helperが動かない
- 表示されるPython pathがabsolute pathで、3.12 x64である
- networkを切断した状態で`.venv`作成、hash-lock済みwheel導入、import確認が完了する
- `offline-install.log`にNumPy 2.5.1とpydicom 3.0.2が記録される

次にZIPを別の新規folderへ再展開し、root直下へ空のlookalikeを1個ずつ置いて実行します。

```powershell
Set-Content -LiteralPath .\powershell.exe -Value "not executable"
.\install_offline.cmd
```

`powershell.exe`を削除して`python.exe`、次に`py.exe`でも繰り返します。各回で
`Unexpected executable or script at bundle root`により停止し、Python installer、
helper、`.venv`が起動・作成されないことを確認します。

## 実junction/reparse point

新しいtest rootで、case外のsentinelを指すjunctionを作成して重点testを実行します。
自動テストがjunctionを作成できずskipした場合は、管理者権限ではなくDeveloper Modeを
利用できる通常ユーザー環境を優先します。確認後はtest用一時folderだけを削除します。

```cmd
cmd.exe /d /c mklink /J "<case-root>\analysis" "<outside-root>"
```

`python -m pytest tests/test_security_boundaries.py -vv -p no:cacheprovider`を再実行し、
書込み・上書き・削除の拒否とoutside sentinelの不変を確認します。`fsutil reparsepoint
query "<case-root>\analysis"`で実際にreparse pointであることも記録します。

実行日、Windows build、filesystem、Python version、全command、return code、skip数を
検証記録へ残します。未実行またはskipされた項目を成功として扱わないでください。
