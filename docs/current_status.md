# Current Status

Snapshot date: **2026-09-29 JST**

## GTFS registry and current feeds

- 公式API `/v2/feeds`: **605 feed-pair rows**。
- 2026-09-29に有効なZIP: **551**。`feed_info.txt` の実期間を確認。
- バス系フィード: **525**。
- 選択したZIPの内部agency行: **530**。
- 名称等で集約したagency由来エンティティ: **444**。これは道路運送法上の事業者数ではない。

## GTFS history — extension前の分析値

- 2年以上: **195 / 444 agency-derived entities**。
- 3年以上: **119 / 444 agency-derived entities**。
- いずれも全構成フィードの履歴を要求する保守的な定義。
- 33フィード、最大48世代の追加探索は途中停止。ZIP総数は2,823だが、延長分はマニフェストと集計に未反映。したがって195/119を延長後の値として扱わない。

## Project LINKS — blocked

CKAN `package_show` API、dataset landing page、resource downloadへのGETがHTTP 403。代替ホストでは502を確認。公開CSV・仕様書本体は取得できていない。

次の件数・項目有無はすべて未確定であり、0とは扱わない。

- GTFSとのA〜E名寄せ数
- 輸送人員・車両関連指標・営業収入の充足数
- 事業概況・運転者数の充足数、年度・粒度
- 都道府県別の完全充足数・充足率
- 指標A〜JのLINKS連結計算可能数
- 最終Supply Stress Test適格事業者数

## Available artifacts

分析CSVと再現用スクリプトをこのリポジトリに保存した。`analysis/links_gtfs_match/` のファイル一覧を参照。`prefecture_summary.csv`、`indicator_feasibility.csv`、`ehime_detail.csv`、`funnel_summary.csv`、`final_assessment.md` はまだ生成していない。

## Decision status

**NOT YET EVALUATED**。全国版を本命採用できる証拠はまだそろっていない。一方、Project LINKSに必要列がないと判明したわけではない。データ本体未取得による未確定である。
