# Transit Supply Stress Test — 実データ検証

このディレクトリは、Project LINKS 2025年度公開データとGTFSデータリポジトリの公開データを、事業者単位で照合するための再現可能な全国調査です。

## 現在の実行範囲

- GTFS公式API `/v2/feeds` の605 feed-pair応答を保存し、日付基準は現行ZIP内部の `feed_info.txt` で検証します。`agency.txt` 内の `agency_name` と routes.txt のバス系 `route_type` から444件のagency由来entityを確認します（法的事業者数ではありません）。
- LINKS については、公式データセット・CKAN API・resource downloadを試しましたが、この実行環境ではHTTP 403でした。CSV本体を取得できていないため、照合・LINKS列充足・LINKS側件数は未確定です。
- LINKS未取得をMatch Eや「欠損0」と読み替えていません。未評価と実測ゼロを区別します。

## 実行手順

作業ディレクトリのルートで次を実行します。

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

世代数・履歴年数を確認したあと、`prev_12` まで全版が存在してさらに古い履歴も必要なfeedだけをID一覧にして、同じコマンドの `--history-depth 48` で拡張します。48世代まで取得できたfeedは上限打ち切りとして「それ以降の履歴なし」と断定せず、404で終了したfeedだけを履歴探索完了とします。ダウンロード済みZIPの再実行では本体を取り直さず、distinct schedule generationに限り公開APIの1-byte Range GETで版名メタデータを復元します。

LINKS本体が取得可能な環境では、`fetch_links.py` を実行した後に `analyze_links_fields.py` 以降を実行してください。手作業で別名を承認する場合は `data/aliases.csv` を作り、`operator_id,links_operator_id,evidence,location_validation,review_status` を記録します。`review_status=approved` と証拠・所在地検証が揃ったC候補だけが確定します。

## 成果物

- `final_assessment.md`: 全国の採用判断
- `match_summary.csv`, `matched_operators.csv`, `unmatched_gtfs.csv`, `unmatched_links.csv`: 事業者名寄せ
- `field_completeness.csv`: LINKS実列と年度別の非欠損状況
- `prefecture_summary.csv`, `ehime_detail.csv`: 地域集計
- `gtfs_history_summary.csv`, `gtfs_history_versions.csv`: 時刻表世代と履歴期間
- `gtfs_history_feeds.csv`, `gtfs_version_metrics.csv`, `gtfs_supply_yoy.csv`: feed別履歴・世代別GTFS供給量・前年比比較
- `indicator_feasibility.csv`: 指標ごとの実計算可能数・条件
- `funnel_summary.csv`: 7段階ファネル
- `data_gap_summary.csv`, `grain_summary.csv`, `anchor_feed_selection.csv`: 欠損理由、集計粒度、基準日のfeed選択根拠
- `data/raw/gtfs_history_metadata_recovery.csv`, `data/raw/gtfs_history_fetch_coverage.csv`: distinct世代版名の追加取得記録とfeed別履歴探索深度

取得した原本とハッシュは `data/raw/` 以下にあります。定義、誤差、粒度は `methodology.md`、取得経路と失敗記録は `data_sources.md` を参照してください。


## Snapshot status in this repository

現在保存した分析CSVは、履歴延長前のGTFS集計です。LINKS公開本体が取得できていないため、A〜E照合とLINKS項目充足は未評価。履歴延長分も分析CSVに反映していません。都道府県・指標・愛媛・ファネル・最終評価のCSV/Markdownは未生成です。
