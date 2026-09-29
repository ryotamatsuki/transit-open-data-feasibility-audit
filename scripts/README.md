# Scripts

## Scripts included

- `fetch_links.py` — Project LINKS公開データ探索・取得記録
- `fetch_gtfs_registry.py` — GTFS公式APIレジストリ取得
- `fetch_gtfs.py` — 現行フィード・過去世代ZIP取得
- `normalize_operator_names.py` — 比較用名称キー作成
- `match_operators.py` — A〜E名寄せ。fuzzy候補は自動確定しない
- `analyze_links_fields.py` — LINKS列・年度・欠損状況確認
- `analyze_gtfs.py` — agency/route/trip/calendarベースのGTFS集計
- `analyze_history.py` — 時刻表世代・履歴期間分析
- `recover_gtfs_history_metadata.py` — 公開ZIP応答の版メタデータ取得
- `build_funnel.py` — ファネル、県別、愛媛、指標、判定レポート生成
- `common.py` — 共通処理

## Reproduction order

```bash
python scripts/fetch_links.py
python scripts/fetch_gtfs_registry.py
python scripts/fetch_gtfs.py --mode current --all-listed --workers 4
python scripts/analyze_gtfs.py
python scripts/analyze_links_fields.py
python scripts/normalize_operator_names.py
python scripts/match_operators.py
python scripts/fetch_gtfs.py --mode history --history-depth 12 --ids-file data/processed/gtfs_bus_feed_ids.txt --workers 8 --skip-existing
python scripts/analyze_history.py
python scripts/recover_gtfs_history_metadata.py
python scripts/analyze_history.py
python scripts/build_funnel.py
```

取得失敗は空データや0件に変換しない。GTFS履歴の取得深度上限に達したfeedは、履歴なしと断定せず未確定にする。
