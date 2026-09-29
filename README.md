# Transit Open Data Feasibility Audit

公共交通オープンデータを用いた新規サービス案について、**実データの取得可能性・接続可能性・項目充足率を先に検証し、テーマ採否を判断する**ための再現可能なデータ監査リポジトリです。

現在の主対象は、公共交通オープンデータチャレンジ2026向け候補 **Transit Supply Stress Test / 交通供給力ストレステスト** です。

## 原則

- 推測値でデータ充足件数を埋めない。
- GTFS feed数を事業者数とみなさない。
- GTFS publisherを道路運送法上の運行事業者とみなさない。
- Project LINKSの行数を事業者数とみなさない。
- fuzzy matchはスコアだけで自動確定しない。
- 欠損値を0として扱わない。
- 取得不能は「0件」ではなく「未確定」として記録する。
- rawデータのライセンス・再配布条件を確認し、原則としてGitへ直接格納しない。

## Status — 2026-09-29

### GTFS

| 項目 | 現時点の集計 |
|---|---:|
| GTFS公式APIのフィード登録 | 605 |
| 有効ZIPを解析して確認したagency由来エンティティ | 444 |
| 2年以上の履歴 | 195 feeds |
| 3年以上の履歴 | 119 feeds |

注意事項:

- 444は **道路運送法上の事業者数ではありません**。
- 2年以上195件、3年以上119件は履歴延長前の確定値です。
- 33フィードを最大48世代まで調べる延長処理は停止済みです。
- 停止時点で25/33フィードの処理完了ログを確認しています。
- 履歴ZIPは2,823件ありますが、延長分は取得台帳・正式集計へ未反映です。

### Project LINKS

対象: 「一般旅客自動車運送事業関連データ（路線バス・貸切バス・タクシー）（2025年度）」

現時点では、CKAN API、データセットページ、公開resource URLのいずれもHTTP 403となり、CSV・仕様書本体を取得できていません。

したがって以下は **未確定** です。

- GTFSとの事業者名寄せ数
- 輸送実績の完全充足数
- 車両関連指標の完全充足数
- 営業収入の完全充足数
- 運転者数の取得可能事業者数
- Supply Stress Test完全版の対象事業者数

## Repository structure

```text
.
├─ README.md
├─ docs/
│  ├─ methodology.md
│  ├─ data_sources.md
│  ├─ current_status.md
│  └─ decisions.md
├─ analysis/
│  └─ links_gtfs_match/
│     └─ README.md
├─ scripts/
│  └─ README.md
├─ data/
│  └─ README.md
├─ requirements.txt
├─ .gitignore
└─ .github/
   └─ workflows/
      └─ ci.yml
```

## Planned outputs

最終的には以下を生成します。

```text
analysis/links_gtfs_match/
├─ match_summary.csv
├─ matched_operators.csv
├─ unmatched_gtfs.csv
├─ unmatched_links.csv
├─ field_completeness.csv
├─ prefecture_summary.csv
├─ gtfs_history_summary.csv
├─ indicator_feasibility.csv
├─ ehime_detail.csv
└─ final_assessment.md
```

## Final decision rule

最終評価は次の3段階とします。

- **PASS**: 全国または複数地域で十分なデータが揃い、作品として成立する。
- **CONDITIONAL PASS**: 指標・地域・年度を限定すれば成立する。
- **FAIL**: データ不足、名寄せ困難、粒度不整合等により本命テーマにすべきでない。

現時点の判定は **NOT YET EVALUATED** です。Project LINKS実データの取得・突合が完了するまでPASS/FAILを確定しません。
