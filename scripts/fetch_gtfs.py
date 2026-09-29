#!/usr/bin/env python3
"""Fetch valid current GTFS packages and, optionally, relative old generations.

Current packages come from the official /v2/feeds registry. Relative history
uses the repository's documented rid=prev_N download parameter. The script
keeps the original ZIP bytes and records content hashes and response filenames.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from common import RAW, now_utc, parse_date, safe_slug, sha256_bytes, sha256_file, write_csv

ANCHOR = dt.date(2026, 9, 29)
BASE = "https://api.gtfs-data.jp/v2/organizations/{org}/feeds/{feed}/files/feed.zip"


def get_bytes(url: str) -> tuple[bytes, dict[str, str], int]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; public-data-audit/1.0)", "Accept": "application/zip,*/*"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read(), dict(r.headers.items()), r.status


def slug_pair(feed: dict[str, object]) -> str:
    return safe_slug(str(feed.get("organization_id", "org"))) + "__" + safe_slug(str(feed.get("feed_id", "feed")))


def is_active(feed: dict[str, object], anchor: dt.date) -> tuple[bool, str]:
    if feed.get("feed_is_discontinued"):
        discontinued = parse_date(str(feed.get("feed_discontinued_date", "")))
        if not discontinued:
            return False, "discontinued_date_unknown"
        if discontinued <= anchor:
            return False, "discontinued_on_or_before_anchor"
    start = parse_date(str(feed.get("latest_feed_start_date", "")))
    end = parse_date(str(feed.get("latest_feed_end_date", "")))
    if not start or not end:
        return False, "missing_validity_dates"
    if start <= anchor <= end:
        return True, "valid_on_anchor_date"
    return False, "outside_anchor_date"


def fetch_one(item: tuple[dict[str, object], str, int, Path, set[tuple[str, str, str]], dict[tuple[str, str], int]]) -> list[dict[str, object]]:
    feed, mode, depth, out_root, skip_existing, terminal_404 = item
    pair = slug_pair(feed)
    base = BASE.format(org=feed["organization_id"], feed=feed["feed_id"])
    versions = [("current", base)] if mode in ("current", "both") else []
    if mode in ("history", "both"):
        versions.extend((f"prev_{i}", base + f"?rid=prev_{i}") for i in range(1, depth + 1))
    records: list[dict[str, object]] = []
    for version, url in versions:
        if version.startswith("prev_"):
            pair_key = (str(feed.get("organization_id")), str(feed.get("feed_id")))
            selector_number = int(version.replace("prev_", ""))
            if selector_number >= terminal_404.get(pair_key, depth + 1):
                return records
        if (str(feed.get("organization_id")), str(feed.get("feed_id")), version) in skip_existing:
            continue
        directory = out_root / ("current" if version == "current" else "history")
        existing_path = directory / f"{pair}__{version}.zip"
        if version.startswith("prev_") and existing_path.exists():
            # This archive was already downloaded and validated as a ZIP. Keep
            # the actual bytes and hash; recover publication metadata later
            # only for content-distinct timetable generations.
            stat = existing_path.stat()
            local_mtime = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat()
            records.append({"organization_id": feed.get("organization_id"), "organization_name": feed.get("organization_name"), "feed_id": feed.get("feed_id"), "feed_name": feed.get("feed_name"), "feed_pref_id": feed.get("feed_pref_id"), "version_selector": version, "source_url": url, "status": 200, "path": str(existing_path), "bytes": stat.st_size, "sha256": sha256_file(existing_path), "content_disposition": "", "retrieved_utc": local_mtime, "metadata_recovered_by": "previously_downloaded_public_archive_local_bytes"})
            continue
        try:
            # Normal retry only for transient failures. 404 means no such old generation.
            for attempt in range(3):
                try:
                    payload, headers, status = get_bytes(url)
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        if version != "current":
                            records.append({"organization_id": feed.get("organization_id"), "organization_name": feed.get("organization_name"), "feed_id": feed.get("feed_id"), "feed_name": feed.get("feed_name"), "feed_pref_id": feed.get("feed_pref_id"), "version_selector": version, "source_url": url, "status": 404, "error": "No generation available for this relative history selector", "retrieved_utc": now_utc()})
                        return records
                    if attempt == 2 or e.code not in (429, 500, 502, 503, 504):
                        raise
                    time.sleep(1.0 * (attempt + 1))
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(1.0 * (attempt + 1))
            if not payload.startswith(b"PK\x03\x04"):
                raise ValueError(f"Response is not a ZIP archive ({headers.get('Content-Type')})")
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{pair}__{version}.zip"
            path.write_bytes(payload)
            records.append({"organization_id": feed.get("organization_id"), "organization_name": feed.get("organization_name"), "feed_id": feed.get("feed_id"), "feed_name": feed.get("feed_name"), "feed_pref_id": feed.get("feed_pref_id"), "version_selector": version, "source_url": url, "status": status, "path": str(path), "bytes": len(payload), "sha256": sha256_bytes(payload), "content_disposition": headers.get("Content-Disposition", ""), "retrieved_utc": now_utc()})
        except Exception as e:
            records.append({"organization_id": feed.get("organization_id"), "organization_name": feed.get("organization_name"), "feed_id": feed.get("feed_id"), "feed_name": feed.get("feed_name"), "feed_pref_id": feed.get("feed_pref_id"), "version_selector": version, "source_url": url, "status": getattr(e, "code", "ERROR"), "error": repr(e), "retrieved_utc": now_utc()})
            if version != "current":
                break
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("current", "history", "both"), default="current")
    ap.add_argument("--history-depth", type=int, default=0)
    ap.add_argument("--all-listed", action="store_true", help="Include discontinued and out-of-date feeds")
    ap.add_argument("--ids-file", help="Optional UTF-8 text file of org_id,feed_id pairs (one comma-separated pair per line)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-existing", action="store_true", help="Skip successful archive selectors already present in the manifest")
    args = ap.parse_args()
    registry_path = RAW / "gtfs_registry.json"
    if not registry_path.exists():
        raise SystemExit("Run scripts/fetch_gtfs_registry.py first")
    feeds = json.loads(registry_path.read_text(encoding="utf-8"))["body"]
    selected: set[tuple[str, str]] | None = None
    if args.ids_file:
        selected = set()
        for line in Path(args.ids_file).read_text(encoding="utf-8").splitlines():
            cells = [s.strip() for s in line.split(",", 1)]
            if len(cells) == 2:
                selected.add((cells[0], cells[1]))
    manifest_path = RAW / "gtfs_download_manifest.csv"
    existing_rows = []
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
            existing_rows = list(csv.DictReader(f))
    skip_existing: set[tuple[str, str, str]] = set()
    terminal_404: dict[tuple[str, str], int] = {}
    if args.skip_existing:
        skip_existing = {(str(r.get("organization_id")), str(r.get("feed_id")), str(r.get("version_selector"))) for r in existing_rows if r.get("status") == "200" and Path(r.get("path", "")).exists()}
        for r in existing_rows:
            if str(r.get("version_selector", "")).startswith("prev_") and str(r.get("status")) == "404":
                key = (str(r.get("organization_id")), str(r.get("feed_id")))
                number = int(str(r.get("version_selector")).replace("prev_", ""))
                terminal_404[key] = min(number, terminal_404.get(key, number))
    todo = []
    excluded = []
    for feed in feeds:
        if selected is not None and (str(feed.get("organization_id")), str(feed.get("feed_id"))) not in selected:
            continue
        active, why = is_active(feed, ANCHOR)
        if not args.all_listed and args.mode != "history" and not active:
            excluded.append({"organization_id": feed.get("organization_id"), "feed_id": feed.get("feed_id"), "reason": why, "latest_feed_start_date": feed.get("latest_feed_start_date"), "latest_feed_end_date": feed.get("latest_feed_end_date"), "feed_is_discontinued": feed.get("feed_is_discontinued")})
            continue
        if args.mode == "history" and args.history_depth <= 0:
            continue
        todo.append((feed, args.mode, args.history_depth, RAW / "gtfs", skip_existing, terminal_404))
    all_records: list[dict[str, object]] = []
    print(f"Downloading {len(todo)} feeds; mode={args.mode}; anchor={ANCHOR}; workers={args.workers}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(fetch_one, item) for item in todo]
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            all_records.extend(future.result())
            if index % 25 == 0 or index == len(futures):
                print(f"completed {index}/{len(futures)} feeds; records={len(all_records)}", flush=True)
    previous = existing_rows
    # Keep prior rows for other modes; replace rows for exact feed/version selectors.
    keys = {(r.get("organization_id"), r.get("feed_id"), r.get("version_selector")) for r in all_records}
    previous = [r for r in previous if (r.get("organization_id"), r.get("feed_id"), r.get("version_selector")) not in keys]
    write_csv(manifest_path, previous + all_records)
    if args.mode in ("history", "both") and args.history_depth > 0:
        coverage_path = RAW / "gtfs_history_fetch_coverage.csv"
        existing_coverage = []
        if coverage_path.exists():
            with coverage_path.open("r", encoding="utf-8-sig", newline="") as f:
                existing_coverage = list(csv.DictReader(f))
        coverage_by_key = {(x.get("organization_id", ""), x.get("feed_id", "")): x for x in existing_coverage}
        for feed, *_ in todo:
            key = (str(feed.get("organization_id", "")), str(feed.get("feed_id", "")))
            previous_depth = int(coverage_by_key.get(key, {}).get("requested_history_depth") or 0)
            coverage_by_key[key] = {"organization_id": key[0], "feed_id": key[1], "organization_name": feed.get("organization_name", ""), "feed_name": feed.get("feed_name", ""), "requested_history_depth": max(previous_depth, args.history_depth), "last_completed_utc": now_utc()}
        write_csv(coverage_path, list(coverage_by_key.values()))
    write_csv(RAW / "gtfs_excluded_registry_feeds.csv", excluded)
    print(json.dumps({"requested_feeds": len(todo), "records_written": len(all_records), "zip_success": sum(str(r.get("status")) == "200" for r in all_records), "history_empty_or_failed": sum(str(r.get("version_selector", "")).startswith("prev_") and str(r.get("status")) != "200" for r in all_records), "excluded_from_current": len(excluded), "manifest": str(manifest_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
