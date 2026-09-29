# Decisions

## D001 — Keep feasibility audit separate from product repositories

**Decision:** 本リポジトリを候補アプリ本体から分離する。

**Reason:** 調査結果がFAILになっても、データ取得・名寄せ・充足率・棄却理由を独立した再現可能資産として残すため。

## D002 — Do not commit raw GTFS ZIP files by default

**Decision:** raw ZIPは原則としてGit管理外とする。

**Reason:** 容量、更新頻度、各feedの再配布条件が異なるため。URL、ID、取得日時、ハッシュ等の取得台帳を残し、再取得可能性を優先する。

## D003 — No inferred completion counts

**Decision:** Project LINKSが取得不能な段階では、名寄せ成功数や完全充足事業者数を推定しない。

**Reason:** 本調査の目的が「現実に何事業者分そろうか」の実測だから。

## D004 — Publisher is not operator

**Decision:** GTFS repository publisherと`agency.txt`上のagency、法的事業者を分離して扱う。

**Reason:** 自治体・協議会がGTFS公開主体になり、実運行会社が別法人であるケースがあるため。

## D005 — Product adoption follows feasibility

**Decision:** 候補プロダクトの本格実装は、データ監査でPASSまたはCONDITIONAL PASSとなった後に別リポジトリで行う。
