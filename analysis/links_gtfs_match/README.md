# LINKS × GTFS Match Audit

Project LINKS一般旅客自動車運送事業データと全国GTFSを突合し、Transit Supply Stress Testに必要なデータの実在件数を測定する。

## Planned outputs

- `match_summary.csv`
- `matched_operators.csv`
- `unmatched_gtfs.csv`
- `unmatched_links.csv`
- `field_completeness.csv`
- `prefecture_summary.csv`
- `gtfs_history_summary.csv`
- `indicator_feasibility.csv`
- `ehime_detail.csv`
- `final_assessment.md`

## Current state

GTFS側の取得・履歴分析は進行済み。Project LINKSの公開CSV取得がHTTP 403でブロックされているため、operator matchingと完全充足ファネルは未評価。

結果CSVは、実データから生成された時点で追加する。空の結果ファイルや推定値は置かない。
