# Methodology

## Objective

公共交通オープンデータを用いた候補サービスが、机上ではなく**現実の公開データだけで成立するか**を検証する。

現在の対象は Transit Supply Stress Test / 交通供給力ストレステスト。

## Unit of analysis

GTFS側の公開主体と実運行主体を混同しない。

原則として以下を分離する。

1. GTFS repository publisher
2. GTFS feed
3. `agency.txt` の agency
4. 実運行主体
5. Project LINKS上の法的事業者

名寄せの基本単位は **GTFS agency ↔ Project LINKS operator** とする。

## Operator-name normalization

比較用キーでは最低限以下を正規化する。

- Unicode NFKC
- 全角/半角
- 空白
- 株式会社 / （株） / (株) / ㈱
- 有限会社 / （有） / (有) / ㈲
- 一般社団法人
- 公益社団法人

「交通」「バス」「鉄道」「自動車」等の実体識別に関係する語は原則として削除しない。

## Match classes

- **A**: 原表記で完全一致
- **B**: 法人格・空白・Unicode正規化後の完全一致
- **C**: 明確な別名・旧称・略称。所在地やURL等で検証済み
- **D**: fuzzy matching候補。未確定
- **E**: 一致不能

C/Dは文字列類似度だけで確定しない。所在地、都道府県、agency_url、停留所分布等を補助情報として使う。

## Funnel

1. GTFSが存在するバスoperator
2. Project LINKSと名寄せ可能
3. GTFS + LINKS輸送実績が揃う
4. さらに事業概況が揃う
5. さらに運転者数が揃う
6. さらに2年以上のGTFS履歴が揃う
7. さらに3年以上のGTFS履歴が揃う

最終的にSupply Stress Test完全版を構築できるoperator数を実測する。

## Missingness

以下を区別して集計する。

- GTFSなし
- LINKSなし
- 運行主体不明
- 名寄せ不能
- 輸送人員欠損
- 車両関連指標欠損
- 営業収入欠損
- 運転者数欠損
- 年度不足
- GTFS履歴不足
- データ取得自体がブロック

取得不能は欠損値や0件に変換しない。

## GTFS history

同一内容の再アップロード、単純な有効期限延長、metadata修正と、実質的な時刻表変更を可能な範囲で区別する。

集計は「ZIPファイル数」ではなく「異なる時刻表世代を持つfeed/operator数」を主とする。

## Reproducibility

取得元URL、取得日時、feed/resource ID、可能ならSHA256を保存する。

rawデータをGitHubへ直接再配布しない場合でも、同じ公開データを再取得できる台帳を残す。

## Decision

推測による補完をせず、実データの充足件数に基づき PASS / CONDITIONAL PASS / FAIL を判定する。
