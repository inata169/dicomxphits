# 公開画像の範囲 / Published screenshot scope

基本6画面（01〜06）は、パス欄が空の合成GUI画像です。従来のJPEGを変更していません。
The six basic screenshots (01–06) are unchanged synthetic GUI JPEGs with empty path fields.

07〜19番は、利用者の承認に基づき2026-09-25にローカル画像処理で作成した公開用PNGです。個人PCのパスが表示された入力欄・ダイアログ・ログの領域だけを強くぼかしています。生成AIによる画面の再生成は行っていません。ぼかした欄は元から空欄だったことを意味しません。
Images 07–19 are PNG publication copies created with user-approved local image processing on 2026-09-25. Only personal-computer path regions in fields, dialogs and logs are strongly blurred. No generative reconstruction was used. A blurred field does not mean that the original field was empty.

すべて独立した合成GUIの記録です。実PHITS計算の成功証拠ではありません。13・14番はPR #83修正前の不具合の記録で、現行の正常動作例ではありません。
All images record an isolated synthetic GUI, not successful real PHITS execution. Images 13 and 14 record a defect before PR #83; they are not examples of current successful behavior.

| 番号 / Number | 場面 / Scene | 加工画像 / Edited image |
| --- | --- | --- |
| 07 | PHITS実行中の合成例 / Synthetic PHITS segment running | [PNG](07-synthetic-running-redacted.png) |
| 08 | STOP受理後の待機（合成例） / Accepted STOP waiting for the current synthetic segment | [PNG](08-stop-pending-redacted.png) |
| 09 | 実行中のGUI終了を拒否する画面（合成例） / GUI closure blocked during a synthetic stage | [PNG](09-close-blocked-while-running-redacted.png) |
| 10 | セグメント境界で停止した状態（合成例） / Stopped at a synthetic segment boundary | [PNG](10-user-stopped-redacted.png) |
| 11 | 未完了ケースを開き直した状態（合成例） / Reopened incomplete synthetic case | [PNG](11-reopened-incomplete-case-redacted.png) |
| 12 | 保持分・再実行分の確認（合成例） / Retained and scheduled synthetic segments | [PNG](12-retry-preview-redacted.png) |
| 13 | 修正前の記録：再実行完了後に古い拒否表示が残る / Historical pre-fix record: stale rejection labels after retry success | [PNG](13-retry-completed-redacted.png) |
| 14 | 修正前の記録：下流復旧が拒否された画面 / Historical pre-fix record: downstream recovery rejected | [PNG](14-recovery-evidence-blocked-redacted.png) |
| 15 | PHITS起動前の準備中（合成例） / Synthetic preparation before PHITS launch | [PNG](15-preparation-before-launch-redacted.png) |
| 16 | 準備キャンセル完了（合成例） / Synthetic preparation cancelled | [PNG](16-preparation-cancelled-redacted.png) |
| 17 | RTDOSE復旧可能な状態（合成例） / Synthetic RTDOSE recovery ready | [PNG](17-rtdose-recovery-ready-redacted.png) |
| 18 | RTDOSE Runのみを実行する確認（合成例） / Synthetic recovery confirmation for RTDOSE Run only | [PNG](18-rtdose-recovery-confirmation-redacted.png) |
| 19 | RTDOSE完了（合成例） / Synthetic RTDOSE completed | [PNG](19-rtdose-completed-redacted.png) |

## 加工と確認 / Processing and verification

- 未加工JPEG13枚は元のローカル保存先に保持し、Gitへ追加しません。
- パス領域の文字構造を縮小平均化してから強くぼかし、元の解像度のPNGとして保存しました。
- 指定領域外の画素が元JPEGの復号画素と完全一致すること、原本のハッシュが不変であることを13枚すべてで確認しました。
- PNGにはEXIF・XMP・コメント・原本サムネイル等のメタデータを保存していません。
- 加工後の13枚を目視確認し、ダイアログ後方のパスも含めて確認しました。12番で残った文字の下端は追加でぼかしました。
- 過去の検証記録にある「公開対象外」は未加工原本を指します。このページと現行本文では加工画像を参照します。

Unedited JPEG originals remain local and untracked. Glyph detail within the selected regions was removed by averaging before strong smoothing. Every output preserves the original dimensions and exactly matches the decoded original pixels outside those regions. Original hashes remain unchanged. PNG files contain no embedded metadata or original thumbnails. All thirteen outputs were visually inspected, including paths behind dialogs; residual glyph edges in image 12 were additionally blurred. Historical “excluded from publication” notes refer to the unedited originals; current manuals link the edited copies.

## 2026-09-25 validation

- Focused artifact checks: 13 source hashes unchanged; pixels outside blur regions identical; PNG chunks restricted to IHDR/IDAT/IEND; all edited images visually inspected.
- Documentation checks: five UTF-8 Markdown files, 138 local links, thirteen edited images in each language and matching twelve-chapter structure passed.
- `python -m compileall src`: passed.
- `python -m pytest -q -p no:cacheprovider`: 1474 passed, 15 skipped (170.03 s). Skips are not successful executions.
- `python tools/verify_public_tree.py`: passed, 410 tracked files including the edited images.
- `git diff --check`, `git diff --cached --check`, diff/stat and status checks: passed.

Only stored synthetic screenshots and documentation were edited. No running GUI, real PHITS process or calculation folder was operated or captured. Runtime, physics, DICOM semantics and public specifications are unchanged. Real-tool validation and v1.1.1 publication are separate work; these images provide no new real-tool evidence.
