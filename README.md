# Transit Open Data Feasibility Audit

公共交通オープンデータを使う候補サービスについて、実データの取得可能性・接続可能性・項目充足率を先に測る監査リポジトリです。対象は公共交通オープンデータチャレンジ2026向けの **Transit Supply Stress Test / 交通供給力ストレステスト** です。

## Current snapshot — 2026-09-29 JST

| 実測項目 | 件数 | 定義・状態 |
|---|---:|---|
| GTFS公式APIの登録フィード | 605 | feed-pair登録行 |
| 基準日に有効な取得ZIP | 551 | ZIP内部の有効期間を照合 |
| バス系フィード | 525 | bus route_typeを含むフィード |
| 内部agency行 | 530 | agency.txtのバス関連行 |
| agency由来エンティティ | 444 | 名称等による集約。法的事業者数ではない |
| 2年以上のGTFS履歴 | 195 | 延長前。全構成フィードで確認したエンティティ数 |
| 3年以上のGTFS履歴 | 119 | 延長前。全構成フィードで確認したエンティティ数 |
| LINKS照合・完全充足 | 未確定 | LINKS本体を取得できず、0件とは扱わない |

Project LINKSの2025年度CSV・仕様書は、CKAN API、データセットページ、公開resource URLでHTTP 403となり未取得です。そのため名寄せ数、運転者数、輸送実績、全国完全ファネルは未確定です。詳細は[現状報告](docs/current_status.md)を参照してください。

GTFSの履歴延長33フィードは途中停止しています。停止時点で履歴ZIPが2,823件ありましたが、追加分は台帳・分析に反映されていません。195/119は延長前の分析値です。

## 主な成果物

- [全国GTFS・LINKS分析CSV](analysis/links_gtfs_match/)
- [方法](docs/methodology.md)
- [取得元・取得記録](docs/data_sources.md)
- [現状と未完了項目](docs/current_status.md)
- [データ方針](data/README.md)
- [再現用スクリプト](scripts/)

取得・分析スクリプトは `scripts/` にあります。raw GTFS ZIPはリポジトリに含めず、URL、取得時刻、SHA256等をマニフェストに記録しています。2026-09-29時点で確認した採用判定は未確定です。
