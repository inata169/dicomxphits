# Structure r.err変更検出テストの原因調査 / Change-detection investigation

2026-09-24。基点 / Baseline: `566ca04`、branch `codex/gui-manual-research`。
対象 / Target: `tests/test_structure_relative_error.py::test_retained_large_sources_use_metadata_without_rehashing`。

## 結論 / Finding

**テストの期待が単に不安定なのではなく、製品の保持済み証拠の再確認処理にも内容変更を見逃す条件がある。** 同じ長さのファイルを短時間で書き換えると、この環境では比較対象のstat値とWindows ChangeTimeがすべて同じ値として返る場合があった。`poll_sha256=False`の再確認はその場合に内容の相違を確認しない。

**This is more than an unstable test expectation: the production retained-evidence check can miss content changes.** In this environment, rapid same-length rewrites sometimes produced identical compared stat fields and Windows ChangeTime values. With `poll_sha256=False`, the verifier does not check content when that metadata remains identical.

時刻が一致した理由をWindows全般、特定ファイルシステムの精度、キャッシュ等に断定したものではない。観測した条件はこのPC上の合成ファイルであり、実データ・実行中GUIでの発生率ではない。

The experiment does not identify a universal Windows timestamp resolution or distinguish every underlying filesystem/cache mechanism. These are observations on synthetic files on this PC, not an incidence estimate for real cases or the running GUI.

## 再現方法と結果 / Experiment

リポジトリ外の専用新規ディレクトリに、4条件×100個の小さなテキストファイルを作った。各ファイルで製品の`_retained_file_snapshot`を呼び、未変更状態の検証成功を確認した後に内容を変更し、製品の`_verify_retained_file_snapshot`を呼んだ。変更前後のSHA-256は別途照合した。ファイル時刻の手動復元・関数の置換は行っていない。外部ツールやGUIは使っていない。

Four groups of 100 small synthetic text files were created in a new isolated directory outside the repository. Each used the real snapshot/verifier functions, verified the unchanged file first, then rewrote it. SHA-256 was compared independently. No timestamps were restored, functions mocked, external tools run or GUI operated.

| 条件 / Condition | 回数 / Trials | 検出漏れ / Missed changes |
| --- | ---: | ---: |
| 同サイズへ即時書換え、metadataのみ / immediate same-size rewrite, metadata only | 100 | **7** |
| 異なるサイズへ書換え、metadataのみ / different-size rewrite, metadata only | 100 | 0 |
| 書換え前に20 ms待機、同サイズ、metadataのみ / 20 ms before same-size rewrite | 100 | 0 |
| 同サイズへ即時書換え、`poll_sha256=True` / immediate same-size rewrite with digest polling | 100 | 0 |

全400件でSHA-256は変化した。検出漏れ7件では比較対象stat値の差分が空で、ChangeTimeも一致した。書換え**後**に20 ms待って再検査しても、7件とも検出されなかった。従って「次のpollまで待てば必ず分かる」とは言えない。20 ms待機が全環境で安全性を保証するとの主張でもない。

All 400 rewrites changed SHA-256. In all seven misses, compared stat fields and ChangeTime were unchanged; waiting 20 ms **after** the rewrite and checking again still missed them. Waiting for another poll is therefore not a demonstrated fix. Nor does the before-write delay establish a universally safe timing threshold.

元のテストと同じ文字列を使用：`b"validated tally content"` → `b"changed tally content!!"`。どちらも23 bytes。対照群は`b"changed size"`を使用。観測JSONは隔離ディレクトリの`metadata-investigation/observations.json`へ保存した。合成出力と個人PCの絶対パスを本資料へコピーしていない。

The equal-length strings match the test: `b"validated tally content"` → `b"changed tally content!!"`, both 23 bytes. The size-changing control uses `b"changed size"`. Detailed observations remain in the isolated `metadata-investigation/observations.json`; generated files and personal absolute paths are not copied here.

再現の中心部分 / Core reproduction (use only a new disposable synthetic file):

```python
source.write_bytes(b"validated tally content")
snapshot = module._retained_file_snapshot(
    source, label="synthetic", expected_sha256=module.file_sha256(source),
    poll_sha256=False,
)
module._verify_retained_file_snapshot(snapshot)
source.write_bytes(b"changed tally content!!")
# Record metadata and both digests, then observe whether this raises:
module._verify_retained_file_snapshot(snapshot)
```

## 原因と影響 / Cause and impact

- `structure_relative_error.py::_retained_file_snapshot`は初回にハッシュを検証し、statとchange tokenを保存する。
- `_verify_retained_file_snapshot`はstat/tokenが同じなら、`poll_sha256=True`のファイルだけを再ハッシュする。
- `_capture_retained_validation`は大きな出力や固定CTなどでmetadata-only監視を使う。小さい23-byteファイルでも同じ処理を通るため、テスト上の「large」という名前が原因ではない。
- GUIの`revalidate_retained_result`はこの再確認を呼び、例外が発生したときに表示をUnavailableへ切り替える。内容変更を見逃すと、この経路から古いStructure統計表示を無効化できない可能性がある。

Initial capture checks hashes and stores metadata. Subsequent checks hash only records whose `poll_sha256` is true. The capture policy uses metadata-only monitoring for sources including large outputs and frozen CT. The GUI invalidates retained Structure results when this revalidation raises; a missed mutation can therefore leave a stale Structure display appearing current. The file need not be large to exercise this code path.

この機能はPHITS完了、STOP、Sumtally/RTDOSEの実行許可を与える証拠には使われない。今回、計算線量や既存RTDOSEファイルが変わった事実は確認していない。一方、Structure表示に対する「変更された証拠は無効化する」という[現行仕様](../../../openspec/specs/post-completion-structure-relative-error/spec.md)との不整合であり、単なるテストのsleep追加で製品の問題が解決したとは扱えない。

Structure evaluation does not authorize PHITS completion, STOP or downstream execution. This investigation did not establish changed calculated dose or RTDOSE files. The finding does conflict with the [current stale-result invalidation requirement](../../../openspec/specs/post-completion-structure-relative-error/spec.md); adding a sleep to the test alone would not resolve the production limitation.

後続の承認済みローカル修正は[修正・検証記録](observation-refresh-fix.md)を参照。以下は修正前の調査時点の記録を保持する。
See the [repair record](observation-refresh-fix.md) for the subsequently authorized local fix. The following preserves the pre-fix investigation record.

## 対応方針 / Repair direction

今回は原因調査のみ。コード・テスト・公開仕様は変更しない。次の修正では、metadata一致だけを内容不変の証明として使わず、UIを停止させない形で内容検証を行うか、変更を確実に検出できない場合に結果をUnavailableとする方式を検討する必要がある。大きいファイルのI/O負荷と検証頻度も評価対象になる。

This task is investigation only; runtime, tests and specifications remain unchanged. A repair must avoid treating identical metadata as proof of unchanged content. It should verify content without blocking the GUI, or report Unavailable when unchanged content cannot be established. Large-file I/O and verification frequency need consideration.

回帰テストは時刻が確実に変わるまで待って通すだけではなく、**内容が違い、metadataが同じ**条件を決定的に与えて検証する必要がある。既存の「大きなファイルを再ハッシュしない」テストは最適化の制約を表しているため、安全性と整合する検証方式と併せて見直す。今回、その変更は行っていない。

A regression should deterministically exercise different contents with identical metadata, rather than merely wait for a timestamp tick. The existing no-rehash assertion expresses an optimization constraint and must be reconciled with the chosen safe validation method. No such changes were made here.

## 検証記録 / Validation

単体確認 / Focused check:

```text
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_structure_relative_error.py::test_retained_large_sources_use_metadata_without_rehashing
```

1 passed、0.81秒。条件依存であるため、この成功は7件の検出漏れを否定しない。初回調査と説明書検証での失敗記録も保持する。

1 passed in 0.81 seconds. This timing-dependent pass does not negate the seven observed misses; earlier failed-suite records remain preserved.

全公開チェック / Full public checks:

| コマンド / Command | 結果 / Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 1456 passed, 15 skipped, 163.35 seconds |
| `.venv/Scripts/python.exe -m compileall src` | passed |
| `.venv/Scripts/python.exe tools/verify_public_tree.py` | passed, 367 tracked files; untracked documents excluded |
| `git diff --check`, `git diff --stat`, `git status --short` | no tracked changes; only `docs/instruction/` untracked |
| Markdown UTF-8 / trailing whitespace / relative links | passed for 13 documents |

今回の全テスト成功も修正を意味しない。再現実験の検出漏れを根拠に未修正の問題として記録した。追加ファイルは本資料、更新はREADME・manual-validation・日英本文の注意書き。runtime・テスト・公開仕様・実行中10 threads GUIは未変更。commit・PRは作成せず、原因調査完了で停止する。

The green suite does not establish a fix. The experimental misses remain evidence of an unresolved issue. This report was added; README, manual-validation and both manuals were updated with the finding. Runtime, tests, public specifications and the running ten-thread GUI are unchanged. No commit or PR was created; work stops at completed investigation.
