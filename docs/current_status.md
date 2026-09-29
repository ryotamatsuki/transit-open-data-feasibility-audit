# Current Status

Snapshot date: **2026-09-29**

## Completed

### GTFS registry / current feeds

- GTFS公式APIのフィード登録: **605**
- 基準日2026-09-29で有効なZIPを選択
- バス系feedと内部`agency.txt`を解析
- agency由来エンティティ: **444**

注意: 444は道路運送法上の事業者数ではない。

### GTFS history — official aggregate before extension

- 2年以上: **195 feeds**
- 3年以上: **119 feeds**

### Reproducibility

- 再現用スクリプト群は別作業環境で作成済み
- `py_compile` による構文確認済み

## Blocked

### Project LINKS

CKAN API、データセットページ、公開resource URLの取得を試したがHTTP 403。

そのため以下は未確定。

- GTFS ↔ LINKSの名寄せ件数
- 運転者数の取得可能件数
- 輸送実績の項目充足件数
- 事業概況の項目充足件数
- 都道府県別の完全充足率
- 愛媛県の完全充足事業者
- Supply Stress Test指標の実計算可能事業者数

## Interrupted history extension

追加対象: 33 feeds  
探索上限: 最大48世代

停止時点:

- 完了ログ確認: **25 / 33 feeds**
- ローカルに存在する履歴ZIP: **2,823**
- 延長分の取得台帳反映: 未実施
- 延長分の2年/3年再集計: 未実施

したがって、195 / 119を延長後の件数として更新しない。

## Missing final outputs

- prefecture_summary.csv
- indicator_feasibility.csv
- ehime_detail.csv
- funnel summary
- final_assessment.md

## Current decision

**NOT YET EVALUATED**

全国版Transit Supply Stress Testを本命採用できるだけの検証は完了していない。ただし、LINKSの必要項目が存在しないと判明したわけではなく、公開データ本体の取得が完了していないため未確定。
