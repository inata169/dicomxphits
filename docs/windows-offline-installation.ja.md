# Windowsオフラインインストール

この手順は、インターネットに接続できないWindows 10/11 64-bit PCへ、
公開版dicomxphitsのPython環境を導入するためのものです。PHITS、RT-PHITS、
phits2dicom、Sumtally、GPR-comparingの導入や実行は行いません。

英語版は[Windows Offline Installation](windows-offline-installation.md)を参照
してください。

## 安全境界と配布範囲

dicomxphitsは、確認済みの非患者ファントムと、文書化された固定照射野
3D-CRTを対象とする教育・研究用ソフトウェアです。インストールしても、
臨床コミッショニング、患者QA、ベンダー認証、臨床利用可能性を意味しません。

PHITS、RT-PHITS、`RTphits_win.bat`、`HumanVoxelTable.data`、phits2dicom、
GPR-comparingは、利用者が正規に取得して別途導入する外部ツールです。
オフラインZIPには含まれません。実患者または非公開DICOM、PHITS計算結果、
ローカル設定、privateリポジトリ由来ファイル、認証情報、個人情報、施設情報も
含めません。インストーラーからPHITS計算を開始することはありません。

## オンラインPCでUSB用ZIPを作成する

インターネット接続済みWindows 10/11 64-bit PCで、次を準備します。

- レビュー済みの本リポジトリのGit checkout
- `PATH`から利用できるGit
- PowerShell 5.1以降
- pipを含むローカルCPython 3.12 64-bit

リポジトリ直下のPowerShellで実行します。

```powershell
.\tools\prepare_offline_bundle.ps1
```

Python 3.12を`py -3.12`または`python`で検出できない場合は明示します。

```powershell
.\tools\prepare_offline_bundle.ps1 -PythonExe "C:\path\to\Python312\python.exe"
```

スクリプトはZIP作成前に次を自動実行します。

1. 公開ツリー監査を実行する
2. `pyproject.toml`からversionを、`requirements/offline-win64.txt`から
   wheelの正確なversion、filename、SHA-256を読む
3. Python公式のCPython 3.12.10 application-local NuGet package、x64 Tcl/Tk
   MSI component、固定versionのNuGet CLIをHTTPSで取得する
4. CPython packageの期待するNuGet repository署名とpackage identity、Tcl/Tk
   componentのPython Software Foundation Authenticode署名、NuGet CLIの
   Microsoft Authenticode署名を必須とし、provenanceとSHA-256を記録する
5. pipへCPython 3.12、`win_amd64`、binary-only、`--require-hashes`での
   wheel取得を要求する
6. wheelの不足、追加、rename、hash不一致を拒否し、NumPyについて
   `cp312-cp312-win_amd64`の完全一致を確認する
7. 監査済みGit indexに存在する通常ファイルblobだけをコピーし、未追跡または
   未stageのbyteはコピーしない
8. `bundle-manifest.json`、`SHA256SUMS.txt`、最終ZIPを生成する

出力先は次です。

```text
dist/dicomxphits-offline-win64-<version>.zip
```

同名ファイルがある場合は停止します。既存の生成済みZIPを置き換えてよいことを
確認した場合だけ`-Force`を使用してください。`dist/`、取得したruntime source、
wheel、作業用ファイルはGit管理対象外であり、コミットしないでください。

完成したZIPをUSBストレージへコピーします。組織で媒体持込み手順がある場合は、
作成スクリプトが表示したZIPのSHA-256も転送記録として保存してください。

## オフラインPCでの基本操作：2段階

1. USBからZIPをローカルディスク上の書込み可能なフォルダーへコピーし、完全に
   展開します。ZIP内のファイルを直接開いたり、USB上をeditable projectの場所に
   したりしないでください。
2. 展開先の`install_offline.cmd`を1回実行します。

PowerShellでは`cd install_offline.cmd`ではなく、次のように実行します。`cd`は
フォルダー移動用であり、ファイルの実行には使用しません。

```powershell
.\install_offline.cmd
```

bundle検証前に起動する実行ファイルは、quoted absolute pathの
`%__APPDIR__%WindowsPowerShell\v1.0\powershell.exe`だけです。継承された
`__APPDIR__`の上書きを消去して、cmd.exe自身のapplication directoryを使用します。
呼出元の`SystemRoot`、current directory、`PATH`からPowerShell、`py.exe`、
`python.exe`を探索しません。
bootstrapは、保護対象pathのreparse pointと展開root直下の想定外の実行ファイルを
拒否し、全payloadを検証してread-lockした後だけ検証済みinstall stageを実行します。
その後、次を行います。

- 同梱NuGet verifier、CPython package、Tcl/Tk componentを検証してread-lockする
- 認証済みsourceだけから完全な`.python-runtime`を安全に構成し、必要fileを
  検証して、最初のPython起動前から導入終了まで全runtime fileをread-lockする
- そのapplication-local CPython 3.12.10 x64だけを`-I -S -B`で使用する。
  host Python、registry candidate、`py.exe`、bare `python.exe`を探索、probe、
  install、repair、実行しない
- 展開したプロジェクト直下へ`.venv`を作成する
- exact lock済み依存だけを、`--require-hashes`、`--no-index`、
  `--find-links`、`--no-build-isolation`で`wheelhouse/`から導入する
- dicomxphitsをeditable installする
- `tkinter`、`numpy`、`pydicom`、`dicomxphits`をimport確認する
- Python、NumPy、pydicomのversionを`offline-install.log`へ記録する
- 既存の`launchers\run_gui_venv.cmd`起動コマンドを表示する

最後の質問へ`y`または`yes`と明示した場合だけGUIを起動します。起動しなくても
インストールは成功です。後で次を実行できます。

```cmd
launchers\run_gui_venv.cmd
```

## 整合性ファイル

`bundle-manifest.json`には、source HEAD commit、正確なGit index entry列の
SHA-256 fingerprint、target、実行時依存関係、wheel tag、runtime sourceの
URLとNuGet・Authenticode署名情報、各payloadの役割・size・SHA-256を記録します。
review済みwheel lockも記録し、通常CIは`requirements/runtime.txt`から同じ
NumPyおよびpydicom versionを使用します。

`SHA256SUMS.txt`には全payloadとmanifestのdigestを記録します。自己参照になるため、
`SHA256SUMS.txt`自身のdigestだけは含みません。この検証は転送破損や内容変更を
検出しますが、組織のUSB媒体管理手順を置き換えるものではありません。

## トラブルシューティング

### SHA-256不一致

何もインストールせず停止します。展開済みコピーを削除し、オンラインPCで生成した
ZIPを再コピーして、作成時に表示されたZIP SHA-256と比較してください。変更済み内容を
受け入れる目的で`SHA256SUMS.txt`を書き換えないでください。

### 既存`.venv`が別のPythonを使用している

`.venv`を削除・変更せず停止します。その環境が不要であることを人間が確認した後、
手動でrenameまたは削除し、`install_offline.cmd`を再実行してください。
インストーラーはこの破壊的判断を自動実行しません。

### wheel不足または非互換

インターネットへフォールバックしません。オンラインPCでバンドルを作り直し、表示された
binary wheelの問題をオンライン側で解決してください。未レビューのsource archiveを
`wheelhouse/`へ追加しないでください。

### Python runtime構成失敗

展開先の`offline-install.log`と`python-runtime.log`を確認してください。
localに導入済みのPythonへ差し替えたり、checksum保護されたruntime sourceを編集
したりせず、producer作成済みZIPを新しい通常のlocal folderへ再展開してください。
host Python productはinstallしませんが、組織policyによってWindows Installerの
administrative extractionが制限される場合があります。

### 想定外実行ファイルまたはreparse pointのerror

checkを削除したりchecksum保護対象を編集したりせず、新しい通常のlocal directoryへ
ZIPを再展開してください。現在のinstallerは、展開rootの実行ファイルlookalike、
またはbundle root・保護対象path上のsymbolic link、junction、reparse pointを
検出すると安全側で停止します。

### `offline-install.log`のpath末尾に余分な`"`が表示される

修正前のbundleで、script directory末尾のseparatorがWindowsのquoted argumentと
干渉した場合の症状です。現在のinstallerは末尾separatorを除いた絶対pathを渡します。
この場合も、checksumで保護されたfileを部分的に差し替えず、修正版ZIP全体を使用して
ください。

### 最後の`[y/N]`prompt

`Enter`または`n`は、GUIを今すぐ起動しない選択です。導入成功は取り消されません。
後から`launchers\run_gui_venv.cmd`で起動できます。

### 複数の展開folderがある

editable installと`.venv`は展開folderの絶対pathを使用します。使用する新しいfolderで
GUI起動を確認してから、古い失敗folderまたは不要になった旧install folderを削除して
ください。使用中の成功folderは削除、移動、renameしないでください。

### オンライン準備スクリプトがPowerShell policyで拒否される

組織またはPCのexecution policyを維持してください。管理者が承認した方法でレビュー済み
checkoutから実行し、ZIP作成だけを目的にpolicyを弱めないでください。

### 空白または日本語を含むパス

スクリプトはpathをquoted argumentとして渡し、Unicode対応のPython path処理を
使用します。security productや展開toolが拒否する場合は、別の書込み可能な
ローカルフォルダーへ展開してください。USB上で実行する回避策は使用しないでください。

### GUIは起動するが外部toolがない

Python packageの導入は完了しています。別途正規に取得したPHITS、RT-PHITS、
phits2dicomを、確認済み非患者ファントムで使用する場合だけGUIへ設定してください。
インストール処理はこれらのtoolを探索・コピー・実行しません。

## 実機検証記録

2026-08-07の限定的なWindows実機確認と修正履歴は、
[Windowsオフライン導入実機検証記録](windows-offline-installation-validation-2026-08-07.ja.md)
に記録しています。これは導入経路の確認であり、臨床検証ではありません。
