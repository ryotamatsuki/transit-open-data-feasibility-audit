# データ取得元と取得記録

## Project LINKS

- 国土交通省公式入口: <https://www.mlit.go.jp/links/open-data.html>
- 指定dataset: <https://www.geospatial.jp/ckan/dataset/links-ippanryokyaku-2025>
- 試行CKAN API: <https://www.geospatial.jp/ckan/api/3/action/package_show?id=links-ippanryokyaku-2025>
- 期待リソース: バス事業概況報告書、バス輸送実績報告、2025年度データ仕様書。
- 取得結果: MLIT公式案内ページはHTTP 200で保存しました。G空間情報センターのpackage_show APIはHTTP 403、dataset landing pageはHTTP 403、索引で特定した公開resource downloadのcurl GETもHTTP 403でした。Chrome表示はCloudFrontの「Request blocked」ページでした。API・ページのURL、日時、status、例外は `data/raw/links/fetch_status.json` に記録します。
- 試行したresource URL: dataset slug `links-ippanryokyaku-2025` のresource ID `5f877415-b4cb-4a08-b622-b748854677d6` の公開download route。応答HTTP 403、919 bytesのCloudFront HTMLです。内容はCSVとして解析していません。
- `requests` は実行環境にインストールされておらずimport時に `ModuleNotFoundError`。標準ライブラリurllibでもCKAN APIとlanding pageを試しました。認証取得、WAF回避、別network経路の使用はしていません。
- 検索索引上の dataset/resource metadata はファイル形式・resource名の確認に限り、CSV値・列件数・事業者数の推定には使っていません。
- 公式Project LINKSユースケース紹介: <https://www.mlit.go.jp/links/use-cases/4446.html>。同ページは2022–2024年度の輸送実績等の用途とサンプルレコード数を説明しますが、本調査のoperator-level集計には転用していません。
- 公式GitHub回帰テスト: <https://github.com/Project-LINKS-mlitoss/LINKS-Veda-2/blob/main/bi-app/packages/frontend/src/test/ai-regression/busReportCleansing.browser.test.ts>。fixture filenameとクレンジング検証の確認だけに用い、国全国CSVの代理データとはしていません。

## GTFS Data Repository

- 公式ページ: <https://gtfs-data.jp/>
- 公式registry API: <https://api.gtfs-data.jp/v2/feeds>
- 公式feed ZIP pattern: `https://api.gtfs-data.jp/v2/organizations/{organization_id}/feeds/{feed_id}/files/feed.zip`
- 過去世代: 同じ公開ZIP endpointで `?rid=prev_1`, `?rid=prev_2`, … を使用。
- API応答はUTF-8 JSON原本 `data/raw/gtfs_registry.json` とCSV `data/raw/gtfs_registry.csv` に保存。HTTP応答・取得時刻・SHA256は `data/raw/gtfs_registry_fetch.json` / `data/raw/source_manifest.csv` に記録します。
- 実測では `/v2/feeds` と `?target_date=20260929` の両方が同じSHA256の605 feed-pairを返しました。target_date queryはレジストリ行を絞りません。
- 現行の個別feed ZIPは `data/raw/gtfs/current/`、履歴版は `data/raw/gtfs/history/`。各URL/status/Content-Disposition/byte数/SHA256/UTC取得日時は `data/raw/gtfs_download_manifest.csv`。
- 現行版の選定はレジストリ日付だけでなくZIP内部 `feed_info.txt` の実日付で検証します。今回、選択した551 feedのうち88件でregistryのlatest日付と現行ZIPのfeed_info期間が異なりました。最終のfeed別根拠は `analysis/links_gtfs_match/anchor_feed_selection.csv`。
- 途中終了した履歴取得のローカルZIPはSHA256を再計算して台帳に復元し、同一内容の再アップロードや期間延長を識別した後、異なる時刻表世代に限って通常のHTTP Range GETで公開ZIP名の適用日・登録日時を取得します。取得したURL、HTTP status、ファイルhash、メタデータ再取得時刻は `data/raw/gtfs_download_manifest.csv` と `data/raw/gtfs_history_metadata_recovery.csv` に記録します。対象外や取得失敗は履歴不足ではなく未確定として保持します。
- Transitland Atlas参照: <https://github.com/transitland/transitland-atlas/blob/main/feeds/gtfs-data-jp.dmfr.json>。取得snapshotはfeed 436件・operator 18件で、gtfs-data.jpの公式API結果を主データとし、Atlasは照合用の参考一覧として保存。snapshotにも「愛媛」「伊予鉄」等の一致はありませんでした。
- GTFS Data Repository API reference: <https://docs.gtfs-data.jp/api.v2.html>。web検索では現行APIリファレンスと対象日検索・過去generation情報を確認。ドキュメントページ自体の直接取得はtimeoutとなったため、個々のZIPと公式API実応答を主証拠にします。

## 取得時点

日付基準は2026-09-29 JSTです。全取得URL・UTC取得時刻・HTTP結果・Content-Type・サイズ・SHA256をmanifestに残します。後日同じ公開URLが更新されても、保存した原本とhashによって今回の分析対象を識別できます。
