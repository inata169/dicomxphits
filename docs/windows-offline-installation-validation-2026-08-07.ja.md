# Windowsオフライン導入実機検証記録 - 2026-08-07

この日付付き記録は、Windowsオフライン導入について人間から報告された限定的な
実機確認をまとめたものです。導入経路の証拠であり、臨床検証、commissioning、
患者QA、vendor認証、臨床利用可能性の主張ではありません。

英語版は
[Windows Offline Installation Validation](windows-offline-installation-validation-2026-08-07.md)
を参照してください。

## 範囲と承認

人間は最初に重要度の低いオフラインWindows PCで確認し、その後、TPSに関連する
オフラインworkstationで確認しました。人間の報告では、施設IT、医療情報部門、
TPS vendor、施設責任者から、そのworkstationへのPythonおよび別管理の外部toolの
導入許可を得ていました。承認資料、施設identity、workstation path、患者data、
DICOM、外部tool配布物、計算結果は本repositoryへ保存していません。

dicomxphits bundleはVisual Studio、PHITS、RT-PHITS、phits2dicom、
GPR-comparingを導入せず、PHITS計算も開始していません。

## 確認経過と修正

最初のoffline hostにはCPython 3.12がありませんでした。同梱した公式Python
3.12.10 installerは完了しましたが、修正前のCMDは新しいcurrent-user Pythonを
再検出できませんでした。その後、標準libraryだけのhelperを直接実行し、bundle
検証、`.venv`作成、binary wheel限定install、editable install、import検証まで
完了しました。提供されたlogにはPython 3.12.10、NumPy 2.5.1、pydicom 3.0.2、
dicomxphits 1.0.1が記録されていました。

段階的な人間確認中に、さらに2件のCMD境界不具合を特定しました。

- bundle root末尾のdirectory separatorがPythonへ渡すquoted argumentの閉じquoteと
  干渉し、log path末尾へ余分な`"`が残る場合があった
- Python Launcherは存在するがCPython 3.12がないhostで、Launcherの
  `Python 3.12 not found!`を実行ファイルpathとして取得する場合があった

修正後は、末尾separatorのないbundle rootを使用し、通常のcurrent-user Python
locationを直接検証し、LauncherまたはPATHから取得した値は実在する実行ファイルを
示す場合だけ採用します。Windows `cmd.exe`回帰testはUnicode・空白pathのargumentと
Launcher not-found messageを対象にしています。

## 最終的な人間報告

人間が最終確認した修正版artifactは次です。

```text
dicomxphits-offline-win64-1.0.1.zip
SHA-256: 143603e20d90d839cb2da775497d3d6f50d99753eff35f213ad14f30d0f83675
Size: 42,892,882 bytes
```

人間は、承認済みoffline workstationで`install_offline.cmd`が正常完了したと
報告しました。agentはそのworkstationへaccessせず、最終logも独立には確認して
いません。したがって、この報告が支持する結論は、手動確認した環境で修正版の
単一entry導入が完了したことに限定されます。

online producer側では、このartifactについてPython Software Foundationの有効な
Authenticode署名、manifest保護対象158 files、NumPyの完全な
`cp312-cp312-win_amd64`互換性、必要な5 wheels、禁止対象名の外部tool配布物が
ないことを確認しました。

## 自動検証証拠

最終的なLauncher出力修正後、local checkは次の結果でした。

```text
Windows offline install焦点test: 13 passed
全public suite: 614 passed, 1 skipped
Python compileall: passed
Windows offline OpenSpec strict validation: passed
Public-tree audit: 152 tracked files passed
Git diff check: passed
```

OpenSpec全体には、今回と無関係な既存の`rtdose-dicom-semantics` strict記述形式
failureが残っています。Windows offline installation spec自体はstrict validationに
合格しました。

## 証拠の境界

- この検証記録では患者または非公開DICOMを使用・記録していません。
- installer確認ではPHITS計算、dose比較、physics結果、臨床workflowを検証して
  いません。
- 公開版の非患者phantom限定、教育・研究用、固定照射野3D-CRTという安全境界は
  変更していません。
- 上記SHA-256は、人間報告の対象となった正確なbundleを識別します。文書だけの
  変更でも再buildしたZIPのdigestは変わるため、別のproducer出力で識別します。
