# Data

このディレクトリのraw/processedデータは原則ローカル生成とし、GitHubには直接コミットしない。

想定構成:

```text
data/
├─ raw/
│  ├─ gtfs/
│  └─ links/
├─ processed/
└─ cache/
```

## raw

公開元から取得した原本。変更しない。

## processed

分析用に正規化・集約した中間データ。

## cache

再取得・解析時間短縮用。再生成可能であること。

## Provenance

各取得物について可能な限り以下を台帳化する。

- source URL
- resource/feed ID
- acquisition timestamp
- effective date
- SHA256
- HTTP status
- license / redistribution notes
