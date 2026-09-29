#!/usr/bin/env python3
"""Recover published archive filenames only for distinct historical schedules.

Run analyze_history.py once first. This avoids a metadata request for duplicate
uploads and validity-window-only archive versions.
"""
from __future__ import annotations

import concurrent.futures
import csv
import datetime as dt
import urllib.error
import urllib.request
from pathlib import Path

from common import ANALYSIS, RAW, now_utc, read_csv, write_csv


def range_metadata(row: dict[str, str]) -> dict[str, object]:
    url = row["source_url"]
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; public-data-audit/1.0)",
        "Accept": "application/zip,*/*", "Range": "bytes=0-0",
    })
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response.read()
            status = response.status
            headers = dict(response.headers.items())
        if status not in (200, 206):
            raise ValueError(f"Unexpected HTTP status {status}")
        content_disposition = headers.get("Content-Disposition", "")
        if not content_disposition:
            raise ValueError("Content-Disposition missing from public archive response")
        local_size = Path(row["path"]).stat().st_size
        content_range = headers.get("Content-Range", "")
        if status == 206 and "/" in content_range:
            remote_size = int(content_range.rsplit("/", 1)[1])
            if remote_size != local_size:
                raise ValueError(f"Local size {local_size} differs from API archive size {remote_size}")
        elif status == 200 and headers.get("Content-Length") and int(headers["Content-Length"]) != local_size:
            raise ValueError("Local size differs from API archive Content-Length")
        return {"key": (row["organization_id"], row["feed_id"], row["version_selector"]), "metadata_http_status": status, "content_disposition": content_disposition, "metadata_retrieved_utc": now_utc(), "metadata_recovered_by": "public_HTTP_Range_1_byte_for_distinct_timetable_generation", "error": ""}
    except urllib.error.HTTPError as exc:
        return {"key": (row["organization_id"], row["feed_id"], row["version_selector"]), "metadata_http_status": exc.code, "content_disposition": "", "metadata_retrieved_utc": now_utc(), "metadata_recovered_by": "public_HTTP_Range_1_byte_for_distinct_timetable_generation", "error": f"HTTP {exc.code}: {exc.reason}"}
    except Exception as exc:
        return {"key": (row["organization_id"], row["feed_id"], row["version_selector"]), "metadata_http_status": "ERROR", "content_disposition": "", "metadata_retrieved_utc": now_utc(), "metadata_recovered_by": "public_HTTP_Range_1_byte_for_distinct_timetable_generation", "error": repr(exc)}


def main() -> None:
    manifest_path = RAW / "gtfs_download_manifest.csv"
    manifest = read_csv(manifest_path)
    by_key = {(x.get("organization_id", ""), x.get("feed_id", ""), x.get("version_selector", "")): x for x in manifest}
    versions = read_csv(ANALYSIS / "gtfs_history_versions.csv")
    distinct_labels = {"latest_distinct_generation", "timetable_content_changed"}
    todo = []
    for version in versions:
        key = (version.get("organization_id", ""), version.get("feed_id", ""), version.get("version_selector", ""))
        row = by_key.get(key)
        if (row and str(row.get("version_selector", "")).startswith("prev_")
                and row.get("status") == "200" and Path(row.get("path", "")).exists()
                and not row.get("content_disposition")
                and version.get("classification_vs_newest_seen") in distinct_labels):
            todo.append(row)
    print(f"Recovering public filename metadata for {len(todo)} distinct historical timetable generations", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(range_metadata, todo))
    by_result = {x["key"]: x for x in results}
    for row in manifest:
        key = (row.get("organization_id", ""), row.get("feed_id", ""), row.get("version_selector", ""))
        result = by_result.get(key)
        if result:
            row["metadata_http_status"] = result["metadata_http_status"]
            if result["content_disposition"]:
                row["content_disposition"] = result["content_disposition"]
            row["metadata_retrieved_utc"] = result["metadata_retrieved_utc"]
            row["metadata_recovered_by"] = result["metadata_recovered_by"]
            row["metadata_error"] = result["error"]
    write_csv(manifest_path, manifest)
    errors = [x for x in results if x.get("error")]
    recovery_rows = []
    for source, result in zip(todo, results):
        recovery_rows.append({"organization_id": source["organization_id"], "feed_id": source["feed_id"], "version_selector": source["version_selector"], "url": source["source_url"], "path": source["path"], "sha256": source.get("sha256", ""), "metadata_http_status": result["metadata_http_status"], "content_disposition": result["content_disposition"], "retrieved_utc": result["metadata_retrieved_utc"], "error": result["error"]})
    write_csv(RAW / "gtfs_history_metadata_recovery.csv", recovery_rows)
    print({"metadata_requests": len(todo), "success": len(todo) - len(errors), "errors": len(errors), "manifest": str(manifest_path), "recovery_log": str(RAW / "gtfs_history_metadata_recovery.csv")})


if __name__ == "__main__":
    main()
