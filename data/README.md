# Data and provenance

公開データの再配布条件と容量を考慮し、raw GTFS ZIP（現行・履歴）はGitに含めない。今回ローカルで取得したGTFS ZIPは合計約829MBであり、URL、feed ID、版、取得日時、byte数、SHA256を `data/raw/gtfs_download_manifest.csv` に記録した。過去版APIの`prev_N`は相対指定なので、後日の再取得結果が同一とは限らない。

Gitには次を保存する。

- GTFS公式レジストリの**連絡先メール・free-form memoを除いた**2026-09-29スナップショットと原本SHA256
- GTFS ZIP取得・履歴探索・メタデータ回収のマニフェスト
- Project LINKSの取得試行日時、URL、HTTP status、エラー内容
- 解析後の集計CSV、再現用スクリプト

## Directory meaning

- `raw/`: 取得結果または取得台帳。Gitには小規模なprovenanceファイルだけを含める。
- `processed/`: 分析に使用できるよう加工したレジストリスナップショット。メールアドレス等の連絡先項目は除外。
- GTFS ZIP原本は各feedの公開元からスクリプトで取得する。
