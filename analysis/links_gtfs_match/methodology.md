# 方法

## 1. 基準日と母集団

- 集計基準日は2026-09-29（日本時間）です。
- GTFS公式 `/v2/feeds` は605件のfeed-pairを返しました。`?target_date=20260929` も605件を返し、一覧自体は日付で絞られません。
- レジストリの `latest_feed_start_date` / `latest_feed_end_date` と現行ZIPの `feed_info.txt` が一致しない例を実測したため、ZIPがある場合はそのZIP内部の `feed_start_date` / `feed_end_date` を優先し、2026-09-29を含むアーカイブだけを選びます。廃止フラグがあり廃止日が基準日以前、または廃止日不明のfeedは保守的に除外します。ZIPの期間情報が取れず現行ZIPの場合だけ、レジストリ期間をfallbackに使います。
- feedは取得単位であり、事業者数ではありません。選択したfeed数、agency行数、正規化したagency entity数を別々に報告します。
- GTFSバスagencyは、ZIP内の `agency.txt` の `agency_name` があり、同じfeedの `routes.txt` にバス系route_typeの路線があるものです。route_type 3、11、700–799を対象にします。publisherやorganization_nameだけのレコードは数えません。

## 2. GTFSの事業者単位

同一agencyが複数feedに分かれている場合にfeed数を事業者数へ転用しないよう、内部agency名を主キーにします。集約キーは、NFKC・空白・法人格を正規化したagency_nameと、agency_urlのホスト名です。agency_urlがない場合は、同名機関を都道府県だけで統合しないよう、publisher IDとfeed都道府県を補助識別子に使います。

このキーは公開GTFSだけで作る監査用のentity keyで、法人番号と同等の法的IDではありません。同名法人やagency_urlの登録誤りが判明したときは、所在地・website・運行範囲の検証で分割・統合します。GTFS raw agency行数、内部agency名のdistinct数、正規化entity数は別々に保持します。

## 3. GTFS指標

- routes数: route_typeが対象バスコードであるroutes.txt行をagencyへ割り当てた数。
- trips数・service_id数: 対象路線を参照するtrips.txt行と、その異なるservice_id数。
- stops数: 当該agency便のstop_times.txtが参照する異なるstop_id数。
- 平日/土休日便数: calendar.txtの曜日フラグで運行日を作り、calendar_dates.txtの例外（1=追加、2=除外）を適用します。カレンダーの有効期間内の日ごとに便数を計算し、月曜〜金曜と土曜・日曜それぞれの平均を出します。551選択feedすべてで`frequencies.txt`も確認し、1feedに空ファイルがあっただけでfrequency rowは0件でした。カレンダーが欠けるfeedは未知として空欄にし、0便に置換しません。
- 運行日数: 評価窓内で対象agencyに1便以上ある実日数。評価窓は有効期間と監査日を踏まえ、監査日前後最大1年ずつに制限します。
- first departure / last arrival: 評価窓内にcalendar上の運行日があるservice_idだけを対象に、バス便のstop_times内の最初と最後の有効時刻を使います。
- trip-hours近似: tripごとの最初の時刻から最後の時刻までの経過時間を、service_idごとに日次運行数へ掛けて合算します。車両ブロック、回送、重複運行、休憩は表現しないため、実車両の勤務時間ではありません。
- vehicle-km近似: 連続停留所の座標間の大円距離をtripごとに合計し、運行日数で加重します。道路網上の距離ではなく、停留所間直線距離の代理量です。
- headway近似: 同一route・実運行日の出発時刻差を計算したroute-day平均です。異なる曜日・季節の混在を避けるため実際のcalendarを適用します。

## 4. 名寄せ規則

正規化はUnicode NFKC、全角・半角スペース削除、株式会社・有限会社・社団法人・財団法人等の法人格表記除去までです。「バス」「交通」「自動車」「鉄道」は削除しません。

- A: raw名の完全一致。LINKS側のoperator entityが一意の場合のみ確定。
- B: 正規化後完全一致。LINKS entityが一意の場合のみ確定。
- C: 旧称・略称等を `data/aliases.csv` に登録し、evidenceと所在地検証を記した承認済み対応のみ確定。
- D: 類似候補を候補として出力するだけで、自動採用しません。
- E: LINKS全データを取得して比較できた場合に候補なしと判定します。LINKS本体未取得時はEではなくnot_evaluableです。

同名のLINKS entityが複数ある場合は、文字列一致だけで自動結合しません。所在地、都道府県、agency_url、website、停留所の分布等で判定し、その根拠を残します。

## 5. LINKSの事業者・レコード粒度

CSVを取得できた場合、元行を削除せず保持します。事業者番号があれば第一キーとし、ない場合は正規化名と所在地を仮キーにします。同一名でも番号・所在地が異なる行は分け、同一事業者の年次・許可区分・提出様式別の反復行は保持します。事業者単位の車両・乗客・収入・運転者合計を作る前に、仕様書と列・年度・許可区分から重複の意味を確認します。

輸送実績の完全性は、同一事業者・同一年の輸送人員、車両関連値、営業/運送収入が欠損なく揃う場合に限ります。概況・運転者も同じ事業者ID・年度で確認します。「運転者」の列が存在することと、GTFS operatorの運転者数が得られることを区別します。

## 6. GTFS履歴

gtfs-data.jpの公開された相対世代selector `rid=prev_N` から過去ZIPを取得します。同一ZIPの再取得だけでは履歴に数えません。ZIP SHA256に加え、時刻表世代signatureを比較します。routes/trips/stop_timesはCSVの行・列順、引用符、改行コードに左右されない正規化テーブルhashとし、calendarの曜日patternとcalendar_datesの例外日も含めます。agency/feed_info等のmetadata-only変更は除外します。calendarのstart/end dateだけ異なる版は、時刻表世代数に加えず `validity_window_only` として分離します。

各ZIP名から時刻表の適用開始日と登録タイムスタンプを別々に記録します。1年/2年/3年履歴の年数は、現行世代と最古の異なる世代の適用開始日の差（365/730/1095日以上）で測り、登録タイムスタンプの差も補助列に残します。適用開始日が取れない場合、年数履歴は未計測です。事業者が複数の現行feedに依存する場合、同じagencyが全feedの各異なる世代に存在し、すべてのfeedで閾値を満たすときだけ事業者全体の履歴充足とします。

## 7. ファネル・欠損・指標

累積ファネルは、GTFS内部agency、確定A/B/C名寄せ、同一年度輸送実績、概況、運転者、2年以上、3年以上の順です。Dは確定数に含めません。Eは全LINKSデータ取得後のみ数えます。

割合の分母は各段階のGTFS operator entity数です。source unavailable / year unavailable / field absent / field blank / ambiguous match / incomplete GTFS historyを区別し、空欄は0ではありません。

指標A–Fは同じ事業者・同一年度・比較可能な粒度が確認できた場合だけ可能とします。Gは同一feed構成の異なるschedule generation間でGTFSサービス量が比較できる場合、H–JはLINKSの同一事業者・比較可能な許可区分で2年度分が実在する場合だけ前年比を計算します。
