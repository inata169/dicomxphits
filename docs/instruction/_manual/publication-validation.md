# 説明書公開の検証 / Documentation publication validation

2026-09-24。Branch: `codex/publish-gui-manuals`.

利用者は説明書の公開前確認、専用PR作成、レビュー対応、合格後のマージとリモートブランチ削除を承認した。実PHITSの実行承認は含まれない。
The user authorized documentation publication, PR review handling, merge after successful checks/review, and remote branch deletion. This does not authorize real PHITS execution.

## 公開内容 / Contents

- Japanese and English operating manuals, verification procedures and blank record sheets, proposed verification conditions.
- Research, synthetic GUI verification, repair history and the dated handoff. Historical pending statuses are checkpoint records, not outstanding repair work. PR #83 and #84 are merged.
- Six previously captured synthetic GUI screenshots with empty path fields, and two development-only synthetic reproduction scripts. All nineteen original images were visually inspected; thirteen containing personal-computer synthetic paths are excluded from publication and remain local. No patient images, real calculation screenshots, outputs or saved machine configuration are included.
- The repository README links to both operating manuals. The manual index and both manuals identify the PR #83/#84 baseline and distinguish it from the v1.1.0 tag.

本文は両言語12章。STOP、未完了再実行、下流復旧、フォルダ管理の操作を説明する。`stale`は長いバッチでも正常に発生することを明記した。製品ソース・テスト・公開仕様・物理・DICOM意味は変更していない。新規OpenSpec変更は不要な説明書公開である。
Both manuals contain twelve matching chapters, including STOP, incomplete-segment retry, downstream recovery and folder handling. They clarify that long batches can normally show `stale`. Runtime source, tests, public specifications, physics and DICOM meaning are unchanged; no new OpenSpec change is needed.

## チェック / Checks

- UTF-8, relative links, trailing whitespace, bilingual section/table structure and JPEG signatures checked.
- `python -m compileall -q src docs/instruction/_manual/support`: passed.
- The first sandboxed full pytest attempt encountered temporary-directory access errors and was interrupted. A diagnostic `pytest -x` confirmed `PermissionError` during `tmp_path` setup (14 passed, 1 error), before the affected test body ran. No product assertion or guard was changed. The same full command was then run with permission to access pytest's existing temporary directory.

| Command / check | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (with temporary-directory access) | 1474 passed, 15 skipped; 162.41 seconds |
| `.venv/Scripts/python.exe tools/verify_public_tree.py` | Initially passed at 408 files; final publication passed at 396 tracked files after excluding thirteen images and adding the screenshot-scope note |
| `git diff --cached --check`, `git diff --cached b45e623 --stat` | Passed/reviewed; final publication changes 30 documentation/support files |
| `git diff --name-only HEAD -- src tests openspec` | Empty; runtime, tests and specifications unchanged |
| Markdown and images | 20 manual-folder Markdown files; relative links, encoding and whitespace passed; matching bilingual sections/tables; 19 JPEGs inspected |

The local runtime tree before these documentation additions matches merged PR #84 (`af1194c71cc2d84ae91fa40b1265c87a2547f83e`). Publication uses merged main as its parent. Fifteen skipped tests are not counted as executed passes. CI and review results are recorded on the documentation PR; merge is conditional on their success.

### Image publication check

Automatic approval review rejected the first image upload because personal-computer paths or metadata might be disclosed. No image was uploaded by that rejected request. The publication set was reduced to six visually checked empty-path layout images. JPEG marker parsing verified that these contain only a 14-byte JFIF header, no EXIF, XMP or comment payload. An initial whole-binary substring scan falsely matched compressed image bytes; the check was corrected to examine metadata segments rather than compressed pixels. Thirteen other images remain local and are represented by a [scope note](screenshots/README.md). No redaction or generated reconstruction of the GUI was used.

After this evidence and reduced scope were supplied, the first clean image upload was accepted. The remote documentation commit is built directly on merged main, so local commits containing excluded images are not pushed. Final link checks require every local target to be in the Git index, not merely present on disk.

## 未検証 / Unverified

No real tools, live GUI operations, calculation-directory reads/writes, GUI restart, power-loss simulation or real folder deletion were performed for publication. Real-run observation refresh, long-duration behavior and full-dataset Structure hashing performance remain unverified. Blank real-verification records remain blank. The proposed real execution still requires its own exact conditions and approval.
