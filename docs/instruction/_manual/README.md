# dicomxphits GUI 操作説明書 / GUI operating manuals

操作説明書を日本語・英語で作成しました。まず以下の本文を開いてください。
Start with the Japanese or English operating manual below.

- [日本語 操作説明書](gui-manual.ja.md)
- [English operating manual](gui-manual.en.md)
- [2026年9月24日の作業引き継ぎ書](handoff-2026-09-24.ja.md)
- [修正版GUIの実動作確認手順・記録表](live-verification.ja.md)
- [Repaired GUI verification procedure and record sheet](live-verification.en.md)
- [具体的な検証条件案](verification-conditions.ja.md)
- [Proposed verification conditions](verification-conditions.en.md)
- [本文の検証結果・制約 / Manual validation and limitations](manual-validation.md)
- [説明書公開前の検証 / Documentation publication validation](publication-validation.md)
- [Structure相対誤差の変更検出の原因調査 / Structure-result change-detection investigation](structure-rerr-investigation.md)
- [観測表示・Structure変更検出の修正（PR #84マージ済み） / Observation and Structure freshness repair (PR #84 merged)](observation-refresh-fix.md)

対象はv1.1.0の機能とPR #83・#84の修正を含む版です。両PRはmainへマージ済みですが、公開済みv1.1.0タグには含まれません。実ツールによる検証範囲・制約は本文末尾に記載しています。
The manuals cover v1.1.0 functionality plus the repairs in PR #83 and #84. Both PRs are merged into main but absent from the published v1.1.0 tag. See the closing verification-scope notes for limitations.

## 調査・検証資料 / Research and verification records

以下は本文の根拠となる時点別の記録です。修正前の画面や当時の未完了事項も含みます。
These are dated supporting records, including pre-fix screenshots and work that was pending at the time.

| 資料 / Document | 日本語 | English |
| --- | --- | --- |
| 必要な章・事前調査 / Contents research | [調査資料](manual-research.ja.md) | [Research](manual-research.en.md) |
| 操作確認・画面一覧 / Verification and screenshots | [検証記録](gui-verification.ja.md) | [Verification record](gui-verification.en.md) |
| 再実行後の状態表示・継続不能の原因 / Retry state and blocked continuation | [原因調査](retry-state-investigation.ja.md) | [Investigation](retry-state-investigation.en.md) |
| 再実行後の継続不能の修正 / Retry continuation repair | [修正記録](retry-fix.ja.md) | [Repair record](retry-fix.en.md) |

画面はすべてタイトルに`SYNTHETIC MANUAL CHECK`のある独立した検証用GUIから撮影しました。基本6画面に加え、個人PCの合成パス部分だけを強くぼかした13枚を本文に掲載します。未加工の原本はローカル保存とし、[公開範囲](screenshots/README.md)を記載しています。
All screenshots show an isolated `SYNTHETIC MANUAL CHECK` GUI. Publication includes six basic screens with empty path fields and thirteen copies with personal path regions strongly blurred. Unedited originals remain local. See the [screenshot scope](screenshots/README.md).

[検証用スクリプト / Synthetic session script](support/synthetic_gui_session.py)は開発環境専用です。
通常のGUI起動には使用しません。合成DICOM・模擬結果・設定ファイルはリポジトリ外に保持し、このフォルダには含めていません。
The script is for development verification, not normal GUI startup. Synthetic DICOM, simulated results, and settings are kept outside the repository.
