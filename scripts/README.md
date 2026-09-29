# Scripts

最終的に以下の再現用スクリプトを配置する予定。

- `fetch_links.py`
- `fetch_gtfs_registry.py`
- `fetch_gtfs.py`
- `normalize_operator_names.py`
- `match_operators.py`
- `analyze_links_fields.py`
- `analyze_gtfs.py`
- `analyze_history.py`
- `build_funnel.py`

## Rules

- 取得失敗を空データに変換しない。
- HTTP status、URL、試行時刻を記録する。
- 名寄せはMatch A〜Eを保持する。
- fuzzy match候補を自動確定しない。
- rawとprocessedを分離する。
- 同一結果が再現できるよう入力バージョンを記録する。
