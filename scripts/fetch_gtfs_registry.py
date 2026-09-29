#!/usr/bin/env python3
"""Fetch the official gtfs-data.jp registry and the requested Atlas reference."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from common import RAW, now_utc, sha256_bytes, write_csv

API = "https://api.gtfs-data.jp/v2/feeds"
ATLAS = "https://raw.githubusercontent.com/transitland/transitland-atlas/main/feeds/gtfs-data-jp.dmfr.json"


def get(url: str) -> tuple[bytes, str, int]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; public-data-audit/1.0)", "Accept": "application/json,*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get("Content-Type", ""), r.status


def main() -> None:
    out = RAW / "gtfs_registry.json"
    data, ctype, status = get(API)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    response = json.loads(data)
    if response.get("code") != 200 or not isinstance(response.get("body"), list):
        raise RuntimeError(f"Unexpected registry response: {str(response)[:500]}")
    feeds = response["body"]
    write_csv(RAW / "gtfs_registry.csv", feeds)
    manifest = [{"source_name": "gtfs-data.jp official feed registry", "url": API, "status": status, "content_type": ctype, "bytes": len(data), "sha256": sha256_bytes(data), "retrieved_utc": now_utc(), "records": len(feeds)}]
    atlas_path = RAW / "source" / "gtfs-data-jp.dmfr.json"
    try:
        atlas_data, atlas_type, atlas_status = get(ATLAS)
        atlas_path.parent.mkdir(parents=True, exist_ok=True)
        atlas_path.write_bytes(atlas_data)
        manifest.append({"source_name": "Transitland Atlas reference", "url": ATLAS, "status": atlas_status, "content_type": atlas_type, "bytes": len(atlas_data), "sha256": sha256_bytes(atlas_data), "retrieved_utc": now_utc()})
    except Exception as e:
        manifest.append({"source_name": "Transitland Atlas reference", "url": ATLAS, "status": getattr(e, "code", "ERROR"), "error": repr(e), "retrieved_utc": now_utc()})
    (RAW / "gtfs_registry_fetch.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"registry_records": len(feeds), "feed_pairs": len({(x.get('organization_id'), x.get('feed_id')) for x in feeds}), "unique_publishers": len({x.get('organization_id') for x in feeds}), "manifest": manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
