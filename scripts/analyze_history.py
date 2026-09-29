#!/usr/bin/env python3
"""Measure actual GTFS schedule generations, excluding metadata-only edits."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from common import ANALYSIS, RAW, read_csv, write_csv
from analyze_gtfs import analyze_zip


def upload_datetime(row: dict[str, str]) -> dt.datetime | None:
    cd = row.get("content_disposition", "")
    filename = re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
    candidate = filename.group(1).strip().strip('"') if filename else Path(row.get("path", "")).name
    m = re.search(r"_(20\d{12})\.zip$", candidate)
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def date_from_filename(row: dict[str, str]) -> dt.date | None:
    cd = row.get("content_disposition", "")
    filename = re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
    candidate = filename.group(1).strip().strip('"') if filename else Path(row.get("path", "")).name
    m = re.search(r"_(20\d{6})_20\d{12}\.zip$", candidate)
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def canonical_table_hash(zf: zipfile.ZipFile, member_name: str) -> str:
    """Hash GTFS table values independent of line endings, row/column order.

    ZIP metadata, CSV quoting, and row order are not timetable generations.
    Sorting preserves duplicate rows and all cell values while avoiding false
    changes caused by a publisher reserializing the same table.
    """
    with zf.open(member_name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace", newline="")
        reader = csv.DictReader(text)
        headers = sorted(reader.fieldnames or [])
        row_hashes = []
        for row in reader:
            canonical_row = json.dumps(tuple((row.get(key) or "") for key in headers), ensure_ascii=False, separators=(",", ":"))
            row_hashes.append(hashlib.sha256(canonical_row.encode("utf-8")).hexdigest())
    digest = hashlib.sha256(json.dumps(headers, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    for row_hash in sorted(row_hashes):
        digest.update(row_hash.encode("ascii"))
    return digest.hexdigest()


def csv_dicts(zf: zipfile.ZipFile, wanted: str):
    name = next((n for n in zf.namelist() if n.lower() == wanted.lower()), None)
    if not name:
        return []
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace", newline="")
        return list(csv.DictReader(text))


def signatures(path: Path) -> tuple[str, str, list[str]]:
    with zipfile.ZipFile(path) as zf:
        names = {n.lower(): n for n in zf.namelist()}
        # The trip service core is exact schedule content, line-ending
        # normalized; feed_info, agency, stops/labels and archive ZIP metadata
        # are intentionally excluded from timetable-generation identity.
        core = []
        for name in ("routes.txt", "trips.txt", "stop_times.txt"):
            actual = names.get(name)
            core.append(name + ":" + (canonical_table_hash(zf, actual) if actual else "MISSING"))
        calendar = csv_dicts(zf, "calendar.txt")
        pattern_rows = []
        validity_rows = []
        days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        for row in calendar:
            pattern_rows.append("|".join([row.get("service_id", "")] + [row.get(x, "") for x in days]))
            validity_rows.append("|".join([row.get("service_id", ""), row.get("start_date", ""), row.get("end_date", "")]))
        exception_rows = ["|".join([r.get("service_id", ""), r.get("date", ""), r.get("exception_type", "")]) for r in csv_dicts(zf, "calendar_dates.txt")]
        pattern = "\n".join(core + ["calendar_patterns:" + "\n".join(sorted(pattern_rows)), "calendar_exceptions:" + "\n".join(sorted(exception_rows))])
        validity = "\n".join(sorted(validity_rows))
        p_sig = hashlib.sha256(pattern.encode("utf-8")).hexdigest()
        v_sig = hashlib.sha256(validity.encode("utf-8")).hexdigest()
        return p_sig, v_sig, zf.namelist()


def main() -> None:
    manifest_path = RAW / "gtfs_download_manifest.csv"
    manifest = read_csv(manifest_path) if manifest_path.exists() else []
    successful = [r for r in manifest if r.get("status") == "200" and Path(r.get("path", "")).exists()]
    by_feed: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in successful:
        by_feed[(row.get("organization_id", ""), row.get("feed_id", ""))].append(row)
    feed_rows: list[dict[str, object]] = []
    version_rows: list[dict[str, object]] = []
    for (org, fid), rows in by_feed.items():
        rows.sort(key=lambda r: (0 if r.get("version_selector") == "current" else int(r.get("version_selector", "prev_999").replace("prev_", "") or 999)))
        signatures_seen: dict[str, dict[str, str]] = {}
        for row in rows:
            try:
                pattern_sig, validity_sig, members = signatures(Path(row["path"]))
                up = upload_datetime(row)
                dt_from_name = date_from_filename(row)
                if pattern_sig not in signatures_seen:
                    signatures_seen[pattern_sig] = row
                    generation = len(signatures_seen)
                    if generation == 1:
                        change_type = "latest_distinct_generation"
                    else:
                        change_type = "timetable_content_changed"
                else:
                    generation = ""
                    prior = signatures_seen[pattern_sig]
                    prior_pattern, prior_validity, _ = signatures(Path(prior["path"]))
                    if validity_sig != prior_validity:
                        change_type = "validity_window_only"
                    elif row.get("sha256") != prior.get("sha256"):
                        change_type = "same_timetable_reupload_or_metadata_only"
                    else:
                        change_type = "byte_identical_duplicate"
                version_rows.append({"organization_id": org, "feed_id": fid, "version_selector": row.get("version_selector"), "upload_utc": up.isoformat() if up else "", "effective_start_from_filename": dt_from_name.isoformat() if dt_from_name else "", "archive_sha256": row.get("sha256"), "timetable_signature": pattern_sig, "validity_signature": validity_sig, "distinct_generation_number": generation, "classification_vs_newest_seen": change_type, "path": row.get("path"), "gtfs_members": "|".join(members)})
            except Exception as e:
                version_rows.append({"organization_id": org, "feed_id": fid, "version_selector": row.get("version_selector"), "archive_sha256": row.get("sha256"), "classification_vs_newest_seen": "analysis_error", "error": repr(e), "path": row.get("path")})
        good = [v for v in version_rows if v.get("organization_id") == org and v.get("feed_id") == fid and v.get("timetable_signature")]
        distinct_versions = []
        seen = set()
        for v in good:
            sig = str(v["timetable_signature"])
            if sig not in seen:
                seen.add(sig)
                distinct_versions.append(v)
        latest = next((v for v in distinct_versions if v.get("version_selector") == "current"), None)
        latest_upload = dt.datetime.fromisoformat(latest["upload_utc"]) if latest and latest.get("upload_utc") else None
        historic_distinct = [v for v in distinct_versions if v.get("version_selector") != "current"]
        dated_historic = [(v, dt.datetime.fromisoformat(v["upload_utc"])) for v in historic_distinct if v.get("upload_utc")]
        oldest_distinct = min((d for _, d in dated_historic), default=None)
        latest_effective = dt.date.fromisoformat(latest["effective_start_from_filename"]) if latest and latest.get("effective_start_from_filename") else None
        dated_old_effective = [dt.date.fromisoformat(v["effective_start_from_filename"]) for v in historic_distinct if v.get("effective_start_from_filename")]
        oldest_effective = min(dated_old_effective, default=None)
        schedule_span = (latest_effective - oldest_effective).days if latest_effective and oldest_effective else None
        publication_span = (latest_upload - oldest_distinct).days if latest_upload and oldest_distinct else None
        feed_rows.append({"organization_id": org, "feed_id": fid, "distinct_timetable_generations": len(distinct_versions), "distinct_old_generations": len(historic_distinct), "archive_versions_downloaded": len(rows), "latest_upload_utc": latest_upload.isoformat() if latest_upload else "", "oldest_distinct_old_upload_utc": oldest_distinct.isoformat() if oldest_distinct else "", "current_generation_effective_start": latest_effective.isoformat() if latest_effective else "", "oldest_distinct_generation_effective_start": oldest_effective.isoformat() if oldest_effective else "", "history_span_days": schedule_span if schedule_span is not None else "", "archive_publication_span_days": publication_span if publication_span is not None else "", "has_2plus_generations": len(distinct_versions) >= 2, "history_1plus_year": schedule_span is not None and schedule_span >= 365, "history_2plus_year": schedule_span is not None and schedule_span >= 730, "history_3plus_year": schedule_span is not None and schedule_span >= 1095, "date_evidence_status": "measured" if schedule_span is not None else "effective_schedule_date_unavailable", "history_status": "measured"})

    write_csv(ANALYSIS / "gtfs_history_versions.csv", version_rows)
    write_csv(ANALYSIS / "gtfs_history_feeds.csv", feed_rows)

    op_path = ANALYSIS / "gtfs_operator_metrics.csv"
    operators = read_csv(op_path) if op_path.exists() else []
    hist_by_feed = {(x["organization_id"], x["feed_id"]): x for x in feed_rows}
    operator_rows = []
    for op in operators:
        feeds = []
        for pair in op.get("organization_feed_pairs", "").split("|"):
            if "/" in pair:
                feeds.append(tuple(pair.split("/", 1)))
        states = [hist_by_feed.get(k) for k in feeds]
        states_known = [s for s in states if s is not None]
        all_feeds = len(states_known) == len(feeds) and bool(feeds)
        operator_rows.append({"operator_id": op.get("operator_id"), "agency_name": op.get("agency_name"), "prefectures": op.get("prefectures"), "feed_ids": op.get("feed_ids"), "current_feed_count": len(feeds), "history_feed_rows_found": len(states_known), "all_component_feeds_measured": all_feeds,
            "distinct_generations_min_across_feeds": min((int(s["distinct_timetable_generations"]) for s in states_known), default=""),
            "current_only_all_feeds": all_feeds and all(int(s["distinct_timetable_generations"]) == 1 for s in states_known),
            "2plus_generations_all_feeds": all_feeds and all(int(s["distinct_timetable_generations"]) >= 2 for s in states_known),
            "1plus_year_all_feeds": all_feeds and all(s["history_1plus_year"] == "True" for s in states_known),
            "2plus_year_all_feeds": all_feeds and all(s["history_2plus_year"] == "True" for s in states_known),
            "3plus_year_all_feeds": all_feeds and all(s["history_3plus_year"] == "True" for s in states_known),
            "minimum_component_history_span_days": min((int(s["history_span_days"]) for s in states_known if str(s.get("history_span_days", "")).isdigit()), default=""),
            "history_status": "measured" if all_feeds else "incomplete_component_feed_history"})
    write_csv(ANALYSIS / "gtfs_history_summary.csv", operator_rows)

    # Calculate current-like weekly metrics from each distinct old timetable
    # generation at the generation's reported effective start date.
    registry = json.loads((RAW / "gtfs_registry.json").read_text(encoding="utf-8"))["body"] if (RAW / "gtfs_registry.json").exists() else []
    feed_meta = {(x["organization_id"], x["feed_id"]): x for x in registry}
    metrics = []
    if operators:
        unique_paths = {(x.get("organization_id"), x.get("feed_id"), x.get("timetable_signature")): x for x in version_rows if x.get("classification_vs_newest_seen") in ("latest_distinct_generation", "timetable_content_changed") and x.get("timetable_signature")}
        manifest_by_key = {(x.get("organization_id"), x.get("feed_id"), x.get("version_selector")): x for x in successful}
        for v in unique_paths.values():
            d = dt.date.fromisoformat(v["effective_start_from_filename"]) if v.get("effective_start_from_filename") else None
            if not d:
                continue
            row = manifest_by_key.get((v.get("organization_id"), v.get("feed_id"), v.get("version_selector")), {})
            try:
                ag_rows, _ = analyze_zip(Path(v["path"]), row, feed_meta, d)
                for ag in ag_rows:
                    ag["version_selector"] = v.get("version_selector")
                    ag["timetable_signature"] = v.get("timetable_signature")
                    ag["generation_effective_start"] = d.isoformat()
                    metrics.append(ag)
            except Exception as e:
                metrics.append({"organization_id": v.get("organization_id"), "feed_id": v.get("feed_id"), "version_selector": v.get("version_selector"), "error": repr(e)})
    write_csv(ANALYSIS / "gtfs_version_metrics.csv", metrics)

    # Tighten operator-level history to generations where that same current
    # agency identity is present in every component feed. A feed archive alone
    # is not enough to claim history for an agency that appears only later.
    metric_by_operator_feed: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in metrics:
        if row.get("operator_id") and row.get("timetable_signature"):
            metric_by_operator_feed[(str(row.get("operator_id")), str(row.get("organization_id")), str(row.get("feed_id")))].append(row)
    version_by_signature: dict[tuple[str, str, str], dict[str, str]] = {}
    for v in version_rows:
        if not v.get("timetable_signature"):
            continue
        key = (str(v.get("organization_id")), str(v.get("feed_id")), str(v.get("timetable_signature")))
        old = version_by_signature.get(key)
        if old is None or v.get("version_selector") == "current":
            version_by_signature[key] = v
            continue
        if old.get("version_selector") == "current":
            continue
        v_date, old_date = v.get("effective_start_from_filename", ""), old.get("effective_start_from_filename", "")
        if v_date and (not old_date or v_date < old_date):
            version_by_signature[key] = v
    feed_history_by_key = {(str(x.get("organization_id", "")), str(x.get("feed_id", ""))): x for x in feed_rows}
    coverage_rows = read_csv(RAW / "gtfs_history_fetch_coverage.csv") if (RAW / "gtfs_history_fetch_coverage.csv").exists() else []
    requested_depth_by_feed = {(str(x.get("organization_id", "")), str(x.get("feed_id", ""))): int(x.get("requested_history_depth") or 0) for x in coverage_rows}
    rows_by_feed: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in manifest:
        if str(row.get("version_selector", "")).startswith("prev_"):
            rows_by_feed[(str(row.get("organization_id", "")), str(row.get("feed_id", "")))].append(row)
    terminal_404_by_feed = {key: any(str(x.get("status")) == "404" for x in rows) for key, rows in rows_by_feed.items()}
    cap_by_feed = {}
    for key, rows in rows_by_feed.items():
        depth = requested_depth_by_feed.get(key, 0)
        max_success = max((int(str(x.get("version_selector")).replace("prev_", "")) for x in rows if str(x.get("status")) == "200" and Path(x.get("path", "")).exists()), default=0)
        cap_by_feed[key] = bool(depth and max_success >= depth and not terminal_404_by_feed.get(key, False))
    api_error_pairs = {(str(r.get("organization_id", "")), str(r.get("feed_id", ""))) for r in manifest
        if str(r.get("version_selector", "")).startswith("prev_") and str(r.get("status")) not in ("200", "404")}
    strict_operator_rows = []
    for op in operators:
        opid = str(op.get("operator_id", ""))
        feeds = [tuple(pair.split("/", 1)) for pair in op.get("organization_feed_pairs", "").split("|") if "/" in pair]
        per_feed = []
        for org, fid in feeds:
            agency_metrics = metric_by_operator_feed.get((opid, org, fid), [])
            signatures_for_operator = {str(x.get("timetable_signature")) for x in agency_metrics}
            feed_state = feed_history_by_key.get((org, fid), {})
            feed_generation_count = int(feed_state.get("distinct_timetable_generations") or 0)
            current_rows = [x for x in agency_metrics if x.get("version_selector") == "current"]
            current_sigs = {str(x.get("timetable_signature")) for x in current_rows}
            current_starts = [dt.date.fromisoformat(str(version_by_signature.get((org, fid, sig), {}).get("effective_start_from_filename"))) for sig in current_sigs if version_by_signature.get((org, fid, sig), {}).get("effective_start_from_filename")]
            latest_start = max(current_starts, default=None)
            old_starts = []
            for sig in signatures_for_operator - current_sigs:
                v = version_by_signature.get((org, fid, sig), {})
                if v.get("effective_start_from_filename"):
                    old_starts.append(dt.date.fromisoformat(str(v["effective_start_from_filename"])))
            span = (latest_start - min(old_starts)).days if latest_start and old_starts else None
            per_feed.append({"organization_id": org, "feed_id": fid, "current_agency_present": bool(current_rows), "distinct_generations_for_agency": len(signatures_for_operator), "feed_distinct_generation_count": feed_generation_count, "agency_seen_in_every_distinct_feed_generation": bool(feed_generation_count and len(signatures_for_operator) == feed_generation_count), "history_span_days_for_agency": span})
        all_current_feeds = len(per_feed) == len(feeds) and bool(feeds) and all(x["current_agency_present"] for x in per_feed)
        all_entity_versions_comparable = all_current_feeds and all(x["agency_seen_in_every_distinct_feed_generation"] for x in per_feed)
        spans = [int(x["history_span_days_for_agency"]) for x in per_feed if x["history_span_days_for_agency"] is not None]
        generation_counts = [int(x["distinct_generations_for_agency"]) for x in per_feed]
        capped = any(cap_by_feed.get((org, fid), False) for org, fid in feeds)
        all_exhausted = bool(feeds) and all(terminal_404_by_feed.get((org, fid), False) for org, fid in feeds)
        api_error = any((org, fid) in api_error_pairs for org, fid in feeds)
        absence_known = all_entity_versions_comparable and all_exhausted and not api_error
        generations_2plus = (all_entity_versions_comparable and all(n >= 2 for n in generation_counts)) if all_entity_versions_comparable and all(n >= 2 for n in generation_counts) else (False if absence_known else "")
        history_1plus = (True if len(spans) == len(feeds) and all(s >= 365 for s in spans) else (False if absence_known else "")) if all_entity_versions_comparable else ""
        history_2plus = (True if len(spans) == len(feeds) and all(s >= 730 for s in spans) else (False if absence_known else "")) if all_entity_versions_comparable else ""
        history_3plus = (True if len(spans) == len(feeds) and all(s >= 1095 for s in spans) else (False if absence_known else "")) if all_entity_versions_comparable else ""
        current_only = (absence_known and all(n == 1 for n in generation_counts)) if absence_known and all(n == 1 for n in generation_counts) else (False if absence_known else "")
        strict_operator_rows.append({"operator_id": opid, "agency_name": op.get("agency_name"), "prefectures": op.get("prefectures"), "feed_ids": op.get("feed_ids"),
            "current_feed_count": len(feeds), "agency_present_current_in_all_component_feeds": all_current_feeds,
            "agency_identity_present_in_all_distinct_feed_generations": all_entity_versions_comparable,
            "distinct_generations_min_across_feeds": min(generation_counts, default=""),
            "current_only_all_feeds": current_only,
            "2plus_generations_all_feeds": generations_2plus,
            "1plus_year_all_feeds": history_1plus,
            "2plus_year_all_feeds": history_2plus,
            "3plus_year_all_feeds": history_3plus,
            "minimum_component_history_span_days": min(spans, default=""),
            "all_component_feeds_history_exhausted": all_exhausted,
            "history_depth_cap_reached": capped,
            "history_status": "history_api_error" if api_error else ("depth_cap_reached" if capped else ("history_exhaustion_unconfirmed" if not all_exhausted else ("agency_identity_not_stable_across_generations" if all_current_feeds and not all_entity_versions_comparable else ("measured_same_agency_across_all_feeds" if all_entity_versions_comparable else "current_agency_not_confirmed_in_all_component_feeds"))))})
    operator_rows = strict_operator_rows
    write_csv(ANALYSIS / "gtfs_history_summary.csv", operator_rows)

    # Confirm a GTFS-only year-over-year supply comparison using dated,
    # different schedule generations in every component feed. Pair effective
    # start dates 365-455 days apart and require component comparisons to be
    # within a 90-day band.
    metrics_by_op_feed_sig: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in metrics:
        if row.get("operator_id") and row.get("timetable_signature"):
            metrics_by_op_feed_sig[(str(row.get("operator_id")), str(row.get("organization_id")), str(row.get("feed_id")), str(row.get("timetable_signature")))].append(row)

    def sum_metric(rows: list[dict[str, object]], field: str) -> float | None:
        vals=[]
        for row in rows:
            try:
                v=float(row.get(field, ""))
                vals.append(v)
            except (TypeError,ValueError):
                pass
        return sum(vals) if vals else None

    supply_change_rows=[]
    for op in operators:
        opid=str(op.get("operator_id", ""))
        component_pairs=[tuple(pair.split("/",1)) for pair in op.get("organization_feed_pairs", "").split("|") if "/" in pair]
        component_results=[]
        for org,fid in component_pairs:
            current_versions=[]
            historical_versions=[]
            sigs={sig for oid,o,fid0,sig in metrics_by_op_feed_sig if oid==opid and o==org and fid0==fid}
            for sig in sigs:
                rows=metrics_by_op_feed_sig[(opid,org,fid,sig)]
                selector=rows[0].get("version_selector","")
                try: effective=dt.date.fromisoformat(str(rows[0].get("generation_effective_start", "")))
                except ValueError: continue
                trip_service=sum_metric(rows,"weekday_trips_per_day_avg")
                hours_service=sum_metric(rows,"weekday_trip_hours_per_day_approx")
                km_service=sum_metric(rows,"weekday_km_per_day_straight_line_approx")
                info={"signature":sig,"selector":selector,"effective":effective,"trips":trip_service,"hours":hours_service,"km":km_service}
                (current_versions if selector=="current" else historical_versions).append(info)
            if not current_versions:
                component_results.append({"organization_id":org,"feed_id":fid,"comparable":False,"reason":"current_agency_schedule_metric_unavailable"})
                continue
            current=max(current_versions,key=lambda x:x["effective"])
            candidates=[]
            for old in historical_versions:
                gap=(current["effective"]-old["effective"]).days
                if 365<=gap<=455 and current["trips"] is not None and old["trips"] is not None:
                    candidates.append((gap,old))
            if not candidates:
                component_results.append({"organization_id":org,"feed_id":fid,"comparable":False,"reason":"no_distinct_agency_schedule_365_455_days_prior"})
                continue
            gap,old=min(candidates,key=lambda x:abs(x[0]-365))
            component_results.append({"organization_id":org,"feed_id":fid,"comparable":True,"gap_days":gap,"old_date":old["effective"],"current_date":current["effective"],"old_trips":old["trips"],"current_trips":current["trips"],"old_hours":old["hours"],"current_hours":current["hours"],"old_km":old["km"],"current_km":current["km"]})
        chosen=[x for x in component_results if x.get("comparable")]
        comparable=bool(component_pairs) and len(chosen)==len(component_pairs) and (max((x["old_date"] for x in chosen),default=dt.date.min)-min((x["old_date"] for x in chosen),default=dt.date.min)).days<=90
        old_trips=sum(x["old_trips"] for x in chosen) if comparable else None
        current_trips=sum(x["current_trips"] for x in chosen) if comparable else None
        old_hours=sum(x["old_hours"] for x in chosen) if comparable and all(x.get("old_hours") is not None for x in chosen) else None
        current_hours=sum(x["current_hours"] for x in chosen) if comparable and all(x.get("current_hours") is not None for x in chosen) else None
        old_km=sum(x["old_km"] for x in chosen) if comparable and all(x.get("old_km") is not None for x in chosen) else None
        current_km=sum(x["current_km"] for x in chosen) if comparable and all(x.get("current_km") is not None for x in chosen) else None
        supply_change_rows.append({"operator_id":opid,"agency_name":op.get("agency_name"),"prefectures":op.get("prefectures"),"component_feed_count":len(component_pairs),"comparable_component_feed_count":len(chosen),"gtfs_supply_yoy_computable":comparable,
            "previous_effective_date_min":min((x["old_date"] for x in chosen),default="").isoformat() if comparable else "",
            "previous_effective_date_max":max((x["old_date"] for x in chosen),default="").isoformat() if comparable else "",
            "current_effective_date_min":min((x["current_date"] for x in chosen),default="").isoformat() if comparable else "",
            "current_effective_date_max":max((x["current_date"] for x in chosen),default="").isoformat() if comparable else "",
            "weekday_trips_per_day_previous":round(old_trips,3) if old_trips is not None else "","weekday_trips_per_day_current":round(current_trips,3) if current_trips is not None else "",
            "weekday_trips_yoy_pct":round((current_trips-old_trips)/old_trips*100,3) if comparable and old_trips else "",
            "weekday_trip_hours_per_day_previous":round(old_hours,3) if old_hours is not None else "","weekday_trip_hours_per_day_current":round(current_hours,3) if current_hours is not None else "",
            "weekday_trip_hours_yoy_pct":round((current_hours-old_hours)/old_hours*100,3) if comparable and old_hours else "",
            "weekday_straight_line_km_per_day_previous":round(old_km,3) if old_km is not None else "","weekday_straight_line_km_per_day_current":round(current_km,3) if current_km is not None else "",
            "weekday_straight_line_km_yoy_pct":round((current_km-old_km)/old_km*100,3) if comparable and old_km else "",
            "comparison_status":"measured_all_component_feeds" if comparable else "not_confirmed_in_downloaded_distinct_history"})
    write_csv(ANALYSIS / "gtfs_supply_yoy.csv", supply_change_rows)
    print(json.dumps({"feed_versions_analyzed": len(version_rows), "feed_history_rows": len(feed_rows), "operator_history_rows": len(operator_rows), "distinct_old_version_metrics": len(metrics)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
