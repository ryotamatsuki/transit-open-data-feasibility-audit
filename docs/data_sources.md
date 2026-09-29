# Data Sources

## GTFS Data Repository

- Source: https://gtfs-data.jp/
- Role: 全国のGTFS feed、現行データ、取得可能な履歴
- Required files:
  - agency.txt
  - routes.txt
  - trips.txt
  - stop_times.txt
  - stops.txt
  - calendar.txt / calendar_dates.txt
- Current acquisition status: **available**

### Current observed snapshot

- Registered feeds: 605
- Agency-derived entities identified from selected active ZIPs: 444

444は法的な道路運送事業者数ではない。

## Project LINKS

- Entry: https://www.mlit.go.jp/links/open-data.html
- Dataset: 一般旅客自動車運送事業関連データ（路線バス・貸切バス・タクシー）（2025年度）
- CKAN dataset ID: `links-ippanryokyaku-2025`
- Intended files:
  - バス事業概況報告書
  - バス輸送実績報告
  - データ仕様書

### Current acquisition status

**BLOCKED**

Tried:

- CKAN API
- dataset landing page
- public resource URL

Observed response: HTTP 403.

この状態は「データが存在しない」ことを意味しない。現時点では公開CSV本体を取得できていないため、Project LINKS側の項目充足率とGTFSとの名寄せ数は未評価。

## Reference implementation

国土交通省公式OSS:

- https://github.com/Project-LINKS-mlitoss/LINKS-Veda-2

確認対象:

- `bi-app/packages/frontend/src/test/ai-regression/busReportCleansing.browser.test.ts`

同テストは以下のデータ名を参照する。

- `バス事業概況報告書_2024.csv`
- `輸送実績報告（ネスト様式）_-_merged_all__data.csv`

公式実装側でも法人格、空白、全半角等の事業者名クレンジングを前提としている。
