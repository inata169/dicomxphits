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

## 公開bundleのwithdrawal

現在、supported public Windows offline bundleはありません。
[v1.0.2 GitHub Release](https://github.com/inata169/dicomxphits/releases/tag/v1.0.2)
のcustom asset `dicomxphits-offline-win64-1.0.2.zip`は、同じ関連installer・
uninstaller実装を使う後続candidateのverified uninstallがbehavior-based
endpoint protectionに阻止されたため、withdrawしてGitHubから削除しました。保持されて
いるcustom ZIPのcopyをdownload元として案内したり、install、再配布したりしないで
ください。回避策としてendpoint protectionを停止したり、system PowerShellを除外
したりしないでください。

次の値は、withdrawn v1.0.2 assetのhistorical identityとしてのみ保持します。
download手順ではありません。

```text
6b957e1ff236ef787d791db0921edabd18ea459a27fbe745f7c2d98979e86217
```

historical assetのmanifest source HEADは
`efb0dace568fbcb12019f3d320a468dcfb446e34`です。以下の作成手順は、
maintainer evaluationと将来のcompatibility対応のためだけに保持します。生成物は
public release artifactではなく、supported replacement bundleとして表示・配布しては
いけません。将来public offline assetを提供するには、別途reviewし、予定するendpoint
protection環境で新しいexact-HEAD candidateのinstall、GUI起動、verified uninstallの
完全なlifecycleを合格させる必要があります。

人間のmaintainerが施設管理用にローカル生成candidateを保持する場合でも、
それは未公開であり、supported public assetやend-user向け配布物にはなりません。
endpoint protectionがverified uninstallerを終局的に阻止した後の例外的な
手動撤去は、施設管理者が実施するローカルrecoveryであり、公開uninstall手順の
代替ではありません。具体的なcommand checklistはGitで特定してignoreした
`docs/local-offline-manual-uninstall.ja.md`にのみローカル保持できます。その手順は
receiptとbundle rootの完全一致を必須とし、endpoint protectionの停止、共有parent、
別installation、GUI設定、workspace、DICOM、外部tool、計算結果の削除を禁止します。
detached cleanupが存在する、または結果がindeterminateな場合は手動削除せず、
下記のverified-uninstall手順に従ってevidenceを保持します。

## オンラインPCでevaluation用ZIPを作成する（maintainerのみ）

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

限定的なmaintainer testでは、組織の管理された媒体手順だけで完成ZIPを転送し、
作成スクリプトが表示したSHA-256を転送記録として保存してください。これはZIPを
publicまたはsupported release assetにするものではありません。

## オフラインPCでのmaintainer evaluation：3段階

以下のinstall・uninstall手順は、管理されたmaintainer evaluationと将来の再検証用に
保持しています。現在supported public bundleを対象とするend-user導入手順ではありません。

1. USBからZIPをローカルディスク上の書込み可能なフォルダーへコピーし、完全に
   展開します。ZIP内のファイルを直接開いたり、USB上をeditable projectの場所に
   したりしないでください。
2. 展開先の`install_offline.cmd`を1回実行します。
3. 検証済みinstall stageに対するWindowsの管理者確認を承認します。拒否した場合は、
   Pythonを起動する前に停止します。

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
拒否し、全payloadを検証してread-lockし、bundle directory pathをrename不能に保持して
全payloadを再検証した後だけprotected runtime構築の管理者承認を要求します。昇格childは
Windows system directoryの絶対pathだけを使用し、runtimeと
protected hash receiptを作成して、Python起動前に終了します。
protected runtime identityは、正規化した展開rootの絶対pathと検証済み
bundle-manifest SHA-256の両方へ結び付けられます。異なる認証済みbundleを空にした同じ
絶対pathへ再展開した場合は別runtime identityになり、同一bundleの再実行は既存内容を
再利用せず従来どおり安全側で停止します。
元の非昇格stageがその後、次を行います。

- 同梱NuGet verifier、CPython package、Tcl/Tk componentを検証してread-lockする
- 認証済みsourceだけから、Windows Common Application Data配下の管理者保護領域へ
  installation固有runtimeを安全に構成する。変更できるのは`SYSTEM`と昇格済み
  Administratorsだけで、導入ユーザーにはread/executeだけを許可する
- exactなownerとaccess ruleを確認し、各fileを認証済みsource由来digestと比較しながら
  read-lockする。protected完全inventoryを再確認し、最初のPython起動前から導入終了まで
  全file lockを保持する
- inventoryに含まれるbundle fileだけをexactなprotected snapshotへコピーし、helper、
  wheelhouse、editable sourceはそのsnapshotから使用する。追加された`setup.py`などの
  未検証fileは拒否し、コピーも実行もしない
- setuptools PEP 660 backendを明示し、editable build metadataはread-only protected
  sourceではなくtemporary build storageへ書き込む
- 最初のPowerShell起動前に継承されたCLR profiler、startup hook、AppDomain manager
  設定を消去し、必要なbundle directoryをrename防止handleで保持できなければ停止する
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

protected runtimeとsource snapshotは、`.venv`のbase interpreterおよびeditable
sourceとして記録されるため、導入成功後も保持されます。installerは自動削除やrepairを
行いません。展開済みinstallation全体が不要になった場合は、次の検証済み
uninstallerを使用します。

## 1つのoffline installationを削除する

対象GUIと、Python・PHITS関連processをすべて終了します。展開folderをcurrent directoryに
しているterminal、File Explorer、editorなどもすべて閉じます。File Explorerから実行するか、
current directoryが展開folderの外にあるterminalから、次のように実行します。

```powershell
Set-Location D:\
& "D:\path\to\dicomxphits-offline-win64-<version>\uninstall_offline.cmd"
```

local検証成功後、確認語`UNINSTALL`を正確に入力し、Windowsの管理者promptを承認します。
検証済みuninstallerは、正規化した現在の展開pathとmanifest digestをprotected receiptへ
結び付け、receiptのownerとaccess ruleを確認します。別runtimeを探索または推測しません。

削除前に、認証済みbundle payloadが変更されていないことを確認し、installerが作成した
`.venv`とinstallation logだけを追加pathとして許可します。未知file、未知directory、
reparse point、関連する実行中process、またはWindowsがcleanup processとの削除共有を許可した
状態で開けないexact targetがあれば、一件も削除せず停止します。この最後のcheckにより、展開
folderをcurrent directoryにしているterminalが部分削除を起こすことを防ぎます。意図的に追加した
fileは別folderへ移動し、対象を使用しているprocessをすべて閉じてから再実行してください。
checkを弱めないでください。

成功時に削除するのは、その展開bundle、`.venv`、installation log、対応する正確な
protected runtimeとsource snapshot、receipt、Windows Installer log、限定cleanup staging
だけです。他の展開installation、別runtime ID、case folder、DICOM、PHITSなどの外部tool、
per-user GUI設定は削除しません。GUI設定は
`%LOCALAPPDATA%\dicomxphits\dicomxphits.gui.local.json`に残ります。将来のinstallationと共有する
設定も破棄するとユーザーが明示判断した場合だけ、この正確なfileを別途削除してください。

local diskの展開先とprotected `ProgramData`をまたぐ削除はtransactionにできません。
削除開始後にWindowsが対象を削除できなかった場合、uninstallは失敗のままとし、残った正確な
installation-owned pathを報告します。削除範囲を自動的に拡大しません。検証bootstrap自身の
folderを削除する前にread lockを解放する必要があるため、commandは最後の管理者削除を予約し、
protected `failure.json`の正確な場所を表示します。成功時はそのstaging pathも消えます。残った
場合は、表示されたfileで、次に説明する正確なpending sentinel、別のterminal error、または
indeterminate evidenceのどれであるかを確認してください。

`Verified cleanup was scheduled`という表示と呼出元promptへの復帰は、認証済みparentから
detached elevated finalizerへ処理を引き渡したことを意味します。削除完了も失敗も意味しません。
parentが終了してbundleのread lockを解放し、finalizerが限定checkと削除を完了するまで、展開
folderが短時間残ることがあります。この間はuninstallerを再実行せず、対象を手動削除しないで
ください。

観察可能なoutcomeまで待ってください。finalizerはinstallation targetが存在しないことを確認した後、
childがcleanup stagingを削除する前に、protected `failure.json`へ正確なmessage
`Final cleanup staging removal is pending.`を書き込みます。この正確なmessageは処理中を示すsentinelで、
失敗ではありません。待機を続け、uninstallerの再実行や手動削除を行わないでください。

成功が完了したと判断するのは、展開folderと表示されたcleanup-staging directoryが両方消えた後だけ
です。finalizerはstaging directoryを削除する前に、すべての正確なinstallation-owned targetが
存在しないことを確認します。terminal cleanup failureではstaging directoryが残り、pending sentinelが
別のerror messageに置き換わり、`remaining_paths`に正確な残存path一覧が記録されます。reportがない、
読めない、malformed、またはpending sentinelのままどちらのoutcomeにも到達しない場合は、成功・失敗
ではなくindeterminateです。evidenceを保持して調査し、uninstall再実行や対象の手動削除を行わないで
ください。uninstallerは固定の完了期限を提示しません。prompt復帰直後に展開folderが見えることだけ
ではuninstall失敗ではなく、処理中の観察結果です。

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

展開先の`offline-install.log`を確認してください。protected Windows Installer logは
`%ProgramData%\dicomxphits\offline-runtimes\*-msi.log`にあります。
localに導入済みのPythonへ差し替えたり、checksum保護されたruntime sourceを編集
したりせず、producer作成済みZIPを新しい通常のlocal folderへ再展開してください。
host Python productはinstallしませんが、組織policyによってWindows Installerの
administrative extractionが制限される場合があります。

### 管理者承認を拒否した、または利用できない

NuGet verifier、Windows Installer、Python、helper、pipを起動する前に停止します。
`install_offline.cmd`を再実行し、検証済みWindows system PowerShell stageを承認して
ください。folder権限を弱めたり、host Pythonをbundleへコピーしたり、部分的なruntimeを
実行したりしないでください。

### protected runtimeが既に存在する

installerは同一bundle再実行時の対象を再利用、repair、削除しません。以前のinstallationが
残っている場合は、hash名の`ProgramData` directoryを手作業で推測せず、そのfolderの
`uninstall_offline.cmd`を実行してください。異なるmanifestを持つ新しいproducer作成済み
bundleは、空にした同じ絶対pathへ再展開しても別のprotected runtimeを使用できます。
既存installation treeへ新bundleのfileを上書きしないでください。

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
GUI起動を確認してから、不要になった旧folderの`uninstall_offline.cmd`を実行してください。
使用中の成功folderは削除、移動、renameしないでください。uninstaller導入前または不完全な
失敗bundleは明示的な管理者cleanupが必要な場合があります。共有`offline-runtimes` parentを
削除したり、runtime IDを推測したりしないでください。

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
