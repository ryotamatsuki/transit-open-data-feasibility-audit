#!/usr/bin/env python3
"""Inspect downloaded GTFS ZIPs at internal agency/operator level.

Bus agencies are selected by GTFS route_type 3, 11, or the 700-799 bus
extension range. No publisher-only record is counted as an operator.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from common import ANALYSIS, RAW, normalize_name, read_csv, write_csv

ANCHOR = dt.date(2026, 9, 29)
PREFS = ["北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県","茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県","新潟県","富山県","石川県","福井県","山梨県","長野県","岐阜県","静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県","鳥取県","島根県","岡山県","広島県","山口県","徳島県","香川県","愛媛県","高知県","福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"]
BUS_CODES = {3, 11, *range(700, 800)}


def rows_from_zip(zf: zipfile.ZipFile, name: str):
    found = next((n for n in zf.namelist() if n.lower() == name.lower()), None)
    if not found:
        return
    with zf.open(found) as binary:
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", errors="replace", newline="")
        yield from csv.DictReader(text)


def num(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return None


def seconds(value: str | None) -> int | None:
    try:
        p = str(value).strip().split(":")
        if len(p) != 3:
            return None
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except Exception:
        return None


def fmt_time(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value // 3600:02d}:{(value % 3600) // 60:02d}"


def date_val(value: str | None) -> dt.date | None:
    if not value:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def archive_validity(path: Path) -> tuple[dt.date | None, dt.date | None]:
    """Read an archive's own feed_info validity window when available."""
    try:
        with zipfile.ZipFile(path) as zf:
            rows = list(rows_from_zip(zf, "feed_info.txt") or [])
        if rows:
            return date_val(rows[0].get("feed_start_date")), date_val(rows[0].get("feed_end_date"))
    except Exception:
        pass
    return None, None


def haversine(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    x = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(x)))


def classify_bus(code: str | None) -> bool:
    value = num(code)
    return value in BUS_CODES if value is not None else False


def canonical_operator(name: str, agency_url: str, pref: str, org_id: str) -> str:
    key = normalize_name(name)
    host = (urlparse(agency_url).hostname or "").lower().removeprefix("www.")
    # URL host disambiguates equal names. If an agency URL is absent, keep
    # publisher provenance in the key instead of merging same-named agencies
    # merely because they occur in the same prefecture. This may leave a real
    # operator duplicated across publishers, but does not fabricate a match.
    identity = host or f"publisher:{org_id}|pref:{pref}"
    return f"{key}|{identity}"


def analyze_zip(path: Path, manifest: dict[str, str], feed_meta: dict[tuple[str, str], dict[str, object]], anchor_date: dt.date = ANCHOR) -> tuple[list[dict[str, object]], dict[str, object]]:
    org, fid = manifest.get("organization_id", ""), manifest.get("feed_id", "")
    meta = feed_meta.get((org, fid), {})
    pref_id = num(str(meta.get("feed_pref_id", "")))
    pref = PREFS[pref_id - 1] if pref_id and 1 <= pref_id <= 47 else ("全国" if pref_id == 99 else "不明")
    publisher = str(meta.get("organization_name", manifest.get("organization_name", "")))
    feed_name = str(meta.get("feed_name", manifest.get("feed_name", "")))
    with zipfile.ZipFile(path) as zf:
        agencies = list(rows_from_zip(zf, "agency.txt") or [])
        if not agencies:
            return [], {"organization_id": org, "feed_id": fid, "feed_name": feed_name, "status": "agency_txt_missing", "path": str(path)}
        agency_names: dict[str, dict[str, str]] = {}
        if len(agencies) == 1 and not agencies[0].get("agency_id"):
            agencies[0]["agency_id"] = "__single__"
        for a in agencies:
            aid = a.get("agency_id", "") or (agencies[0].get("agency_id", "") if len(agencies) == 1 else "")
            agency_names[aid] = dict(a)

        routes: dict[str, tuple[str, str]] = {}
        agency_route_types: dict[str, set[str]] = defaultdict(set)
        agency_route_ids: dict[str, set[str]] = defaultdict(set)
        for r in rows_from_zip(zf, "routes.txt") or []:
            rt = str(r.get("route_type", "")).strip()
            aid = r.get("agency_id", "") or (next(iter(agency_names)) if len(agency_names) == 1 else "")
            if classify_bus(rt):
                routes[r.get("route_id", "")] = (aid, rt)
                agency_route_types[aid].add(rt)
                agency_route_ids[aid].add(r.get("route_id", ""))
        if not routes:
            return [], {"organization_id": org, "feed_id": fid, "feed_name": feed_name, "status": "no_bus_route_type", "path": str(path), "agency_count": len(agencies)}

        # Per-service and per-route trip counts plus scheduled time metrics.
        trip_map: dict[str, tuple[str, str, str]] = {}
        trips_by_service: dict[tuple[str, str], int] = defaultdict(int)
        trip_hours_by_service: dict[tuple[str, str], float] = defaultdict(float)
        trip_km_by_service: dict[tuple[str, str], float] = defaultdict(float)
        first_depart_by_service: dict[tuple[str, str], int] = {}
        last_arrive_by_service: dict[tuple[str, str], int] = {}
        departures_by_service_route: dict[tuple[str, str, str], list[int]] = defaultdict(list)
        agency_trip_count: dict[str, int] = defaultdict(int)
        agency_routes: dict[str, set[str]] = defaultdict(set)
        agency_services: dict[str, set[str]] = defaultdict(set)
        first_depart: dict[str, int] = {}
        last_arrive: dict[str, int] = {}
        for trip in rows_from_zip(zf, "trips.txt") or []:
            route_id = trip.get("route_id", "")
            if route_id not in routes:
                continue
            aid = routes[route_id][0]
            service = trip.get("service_id", "")
            trip_id = trip.get("trip_id", "")
            trip_map[trip_id] = (aid, service, route_id)
            agency_trip_count[aid] += 1
            agency_routes[aid].add(route_id)
            agency_services[aid].add(service)
            trips_by_service[(aid, service)] += 1
            st = seconds(trip.get("departure_time"))
            if st is not None:
                departures_by_service_route[(aid, service, route_id)].append(st)

        # Stop coordinates support a straight-line stop-to-stop distance proxy.
        stop_coords: dict[str, tuple[float, float]] = {}
        for stop in rows_from_zip(zf, "stops.txt") or []:
            try:
                stop_coords[stop.get("stop_id", "")] = (float(stop["stop_lat"]), float(stop["stop_lon"]))
            except Exception:
                pass
        agency_stops: dict[str, set[str]] = defaultdict(set)
        # Accumulate one trip at a time. The repository feeds are normally
        # ordered by trip_id/stop_sequence; if a trip reappears, this code still
        # retains its rows in a compact per-trip list and sorts before summing.
        trip_stops: dict[str, list[tuple[int, int | None, int | None, str, float | None]]] = defaultdict(list)
        for st in rows_from_zip(zf, "stop_times.txt") or []:
            trip_id = st.get("trip_id", "")
            if trip_id not in trip_map:
                continue
            aid, service, _route = trip_map[trip_id]
            sid = st.get("stop_id", "")
            agency_stops[aid].add(sid)
            seq = num(st.get("stop_sequence")) or 0
            arr, dep = seconds(st.get("arrival_time")), seconds(st.get("departure_time"))
            shape_dist = None
            try:
                shape_dist = float(st.get("shape_dist_traveled", ""))
            except Exception:
                pass
            trip_stops[trip_id].append((seq, arr, dep, sid, shape_dist))

        for trip_id, entries in trip_stops.items():
            aid, service, route_id = trip_map[trip_id]
            entries.sort(key=lambda x: x[0])
            first = next((x[1] if x[1] is not None else x[2] for x in entries if x[1] is not None or x[2] is not None), None)
            last = next((x[1] if x[1] is not None else x[2] for x in reversed(entries) if x[1] is not None or x[2] is not None), None)
            if first is not None and last is not None:
                duration = max(0, last - first) / 3600
                trip_hours_by_service[(aid, service)] += duration
                first_depart_by_service[(aid, service)] = min(first_depart_by_service.get((aid, service), first), first)
                last_arrive_by_service[(aid, service)] = max(last_arrive_by_service.get((aid, service), last), last)
                departures_by_service_route[(aid, service, route_id)].append(first)
            distance = 0.0
            valid_segments = 0
            for prev, curr in zip(entries, entries[1:]):
                # Prefer the stop-to-stop coordinate path; it is explicitly a
                # straight-line approximation, not routed vehicle kilometres.
                km = haversine(stop_coords.get(prev[3]), stop_coords.get(curr[3]))
                if km is not None:
                    distance += km
                    valid_segments += 1
            if valid_segments:
                trip_km_by_service[(aid, service)] += distance

        # Calendar and calendar_dates are combined per GTFS rules.
        calendars: dict[tuple[str, str], dict[str, object]] = {}
        exceptions: dict[tuple[str, dt.date], dict[str, int]] = defaultdict(dict)
        dates: list[dt.date] = []
        weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        for c in rows_from_zip(zf, "calendar.txt") or []:
            sid = c.get("service_id", "")
            start, end = date_val(c.get("start_date")), date_val(c.get("end_date"))
            flags = tuple(str(c.get(day, "0")) == "1" for day in weekdays)
            aids = {a for a, service in trips_by_service if service == sid}
            for aid in aids:
                calendars[(aid, sid)] = {"start": start, "end": end, "flags": flags}
            if aids and start:
                dates.append(start)
            if aids and end:
                dates.append(end)
        for c in rows_from_zip(zf, "calendar_dates.txt") or []:
            sid = c.get("service_id", "")
            d = date_val(c.get("date"))
            ex = num(c.get("exception_type"))
            aids = {a for a, service in trips_by_service if service == sid}
            if aids and d and ex in (1, 2):
                for aid in aids:
                    exceptions[(aid, d)][sid] = ex
                dates.append(d)
        fi_rows = list(rows_from_zip(zf, "feed_info.txt") or [])
        if fi_rows:
            for col in ("feed_start_date", "feed_end_date"):
                d = date_val(fi_rows[0].get(col))
                if d:
                    dates.append(d)
        min_date, max_date = (min(dates), max(dates)) if dates else (None, None)
        # Evaluate a bounded window spanning up to one year either side of the
        # audit date. This captures the current feed's schedule cycle even when
        # only a few days remain in its formal validity period.
        window_start = max(anchor_date - dt.timedelta(days=365), min_date) if min_date else None
        window_end = min(anchor_date + dt.timedelta(days=365), max_date) if max_date else None
        if window_start and window_end and window_start > window_end:
            window_start = window_end = None
        daily: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
        headways: dict[str, list[float]] = defaultdict(list)
        if window_start and window_end:
            day = window_start
            while day <= window_end:
                dow = day.weekday()
                day_trips: dict[str, int] = defaultdict(int)
                day_hours: dict[str, float] = defaultdict(float)
                day_km: dict[str, float] = defaultdict(float)
                active_by_agency: dict[str, set[str]] = defaultdict(set)
                for (aid, sid), cal in calendars.items():
                    start, end, flags = cal["start"], cal["end"], cal["flags"]
                    if start and end and start <= day <= end and flags[dow]:
                        active_by_agency[aid].add(sid)
                for (aid, exday), changes in exceptions.items():
                    if exday != day:
                        continue
                    for sid, etype in changes.items():
                        if etype == 1:
                            active_by_agency[aid].add(sid)
                        elif etype == 2:
                            active_by_agency[aid].discard(sid)
                for aid, active in active_by_agency.items():
                    for sid in active:
                        day_trips[aid] += trips_by_service.get((aid, sid), 0)
                        day_hours[aid] += trip_hours_by_service.get((aid, sid), 0.0)
                        day_km[aid] += trip_km_by_service.get((aid, sid), 0.0)
                        service_key = (aid, sid)
                        if service_key in first_depart_by_service:
                            first_depart[aid] = min(first_depart.get(aid, first_depart_by_service[service_key]), first_depart_by_service[service_key])
                        if service_key in last_arrive_by_service:
                            last_arrive[aid] = max(last_arrive.get(aid, last_arrive_by_service[service_key]), last_arrive_by_service[service_key])
                    # Per-route headway on this actual calendar day, with active
                    # service exceptions applied.
                    route_times: dict[str, set[int]] = defaultdict(set)
                    for (said, sid, route), times in departures_by_service_route.items():
                        if said == aid and sid in active:
                            route_times[route].update(times)
                    for times in route_times.values():
                        ordered = sorted(times)
                        gaps = [(b - a) / 60 for a, b in zip(ordered, ordered[1:]) if b > a]
                        if gaps:
                            headways[aid].append(sum(gaps) / len(gaps))
                agencies_with_trips = set(agency_trip_count) | set(agency_route_types)
                for aid in agencies_with_trips:
                    daily[aid].append((day_trips.get(aid, 0), day_hours.get(aid, 0.0), day_km.get(aid, 0.0)))
                day += dt.timedelta(days=1)

        out = []
        for aid, route_types in agency_route_types.items():
            a = agency_names.get(aid, {})
            agency_name = a.get("agency_name", "")
            agency_url = a.get("agency_url", "")
            if not agency_name.strip():
                continue
            canonical = canonical_operator(agency_name, agency_url, pref, org)
            vals = daily.get(aid, [])
            week_idx = [i for i in range(len(vals)) if (window_start + dt.timedelta(days=i)).weekday() < 5] if window_start and window_end else []
            weekend_idx = [i for i in range(len(vals)) if (window_start + dt.timedelta(days=i)).weekday() >= 5] if window_start and window_end else []
            weekday_trip_avg = sum(vals[i][0] for i in week_idx) / len(week_idx) if week_idx else None
            weekend_trip_avg = sum(vals[i][0] for i in weekend_idx) / len(weekend_idx) if weekend_idx else None
            weekday_hours = sum(vals[i][1] for i in week_idx) / len(week_idx) if week_idx else None
            weekend_hours = sum(vals[i][1] for i in weekend_idx) / len(weekend_idx) if weekend_idx else None
            weekday_km = sum(vals[i][2] for i in week_idx) / len(week_idx) if week_idx else None
            weekend_km = sum(vals[i][2] for i in weekend_idx) / len(weekend_idx) if weekend_idx else None
            op_days = sum(1 for x in vals if x[0] > 0)
            weekday_op_days = sum(1 for i in week_idx if vals[i][0] > 0)
            weekend_op_days = sum(1 for i in weekend_idx if vals[i][0] > 0)
            out.append({
                "operator_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16], "operator_identity_key": canonical,
                "agency_name": agency_name, "agency_id": aid, "agency_url": agency_url, "publisher_name": publisher,
                "organization_id": org, "feed_id": fid, "feed_name": feed_name, "prefecture": pref,
                "route_count": len(agency_route_ids.get(aid, set())), "trip_count": agency_trip_count.get(aid, 0),
                "stop_count": len(agency_stops.get(aid, set())), "service_id_count": len(agency_services.get(aid, set())),
                "route_types": "|".join(sorted(route_types, key=lambda x: int(x))),
                "version_selector": manifest.get("version_selector", "current"),
                "operating_days_in_window": op_days, "weekday_operating_days_in_window": weekday_op_days,
                "weekend_operating_days_in_window": weekend_op_days,
                "weekday_trips_per_day_avg": "" if weekday_trip_avg is None else round(weekday_trip_avg, 3),
                "weekend_trips_per_day_avg": "" if weekend_trip_avg is None else round(weekend_trip_avg, 3),
                "weekday_trip_hours_per_day_approx": "" if weekday_hours is None else round(weekday_hours, 3),
                "weekend_trip_hours_per_day_approx": "" if weekend_hours is None else round(weekend_hours, 3),
                "weekday_km_per_day_straight_line_approx": "" if weekday_km is None else round(weekday_km, 3),
                "weekend_km_per_day_straight_line_approx": "" if weekend_km is None else round(weekend_km, 3),
                "first_departure": fmt_time(first_depart.get(aid)), "last_arrival": fmt_time(last_arrive.get(aid)),
                "mean_route_headway_min_approx": "" if not headways.get(aid) else round(sum(headways[aid]) / len(headways[aid]), 2),
                "schedule_window_start": window_start.isoformat() if window_start else "",
                "schedule_window_end": window_end.isoformat() if window_end else "",
                "schedule_status": "dated_calendar_applied" if window_start and window_end and (calendars or exceptions) else "missing_calendar_or_validity",
                "source_zip": str(path), "source_zip_sha256": manifest.get("sha256", ""),
            })
        feed_summary = {"organization_id": org, "feed_id": fid, "version_selector": manifest.get("version_selector", "current"), "feed_name": feed_name, "publisher_name": publisher, "prefecture": pref, "bus_agency_count": len(out), "bus_route_count": len(routes), "status": "bus_feed_analyzed", "source_zip": str(path), "source_zip_sha256": manifest.get("sha256", "")}
        return out, feed_summary


def main() -> None:
    registry = json.loads((RAW / "gtfs_registry.json").read_text(encoding="utf-8"))["body"]
    feed_meta = {(x["organization_id"], x["feed_id"]): x for x in registry}
    manifest_rows = read_csv(RAW / "gtfs_download_manifest.csv") if (RAW / "gtfs_download_manifest.csv").exists() else []
    successful = [x for x in manifest_rows if str(x.get("status")) == "200" and Path(x.get("path", "")).exists()]
    versions_by_feed: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in successful:
        versions_by_feed[(row.get("organization_id", ""), row.get("feed_id", ""))].append(row)
    selection_rows: list[dict[str, object]] = []
    current = []
    for meta in registry:
        org, fid = str(meta.get("organization_id", "")), str(meta.get("feed_id", ""))
        discontinued = bool(meta.get("feed_is_discontinued"))
        disc_date = date_val(str(meta.get("feed_discontinued_date", "")))
        if discontinued and (disc_date is None or disc_date <= ANCHOR):
            disc_status = "excluded_discontinued_date_unknown" if disc_date is None else "excluded_discontinued_on_or_before_anchor"
            selection_rows.append({"organization_id": org, "feed_id": fid, "selected_version_selector": "", "status": disc_status, "registry_latest_start": meta.get("latest_feed_start_date", ""), "registry_latest_end": meta.get("latest_feed_end_date", ""), "feed_is_discontinued": meta.get("feed_is_discontinued", ""), "feed_discontinued_date": meta.get("feed_discontinued_date", ""), "validity_start": "", "validity_end": ""})
            continue
        starts = date_val(str(meta.get("latest_feed_start_date", "")))
        ends = date_val(str(meta.get("latest_feed_end_date", "")))
        ordered = versions_by_feed.get((org, fid), [])
        ordered.sort(key=lambda x: (0 if x.get("version_selector") == "current" else int(str(x.get("version_selector", "prev_999")).replace("prev_", "") or 999)))
        chosen = None
        chosen_start = chosen_end = None
        chosen_basis = ""
        for row in ordered:
            start, end = archive_validity(Path(row["path"]))
            if start and end and start <= ANCHOR <= end:
                chosen, chosen_start, chosen_end = row, start, end
                chosen_basis = "archive_feed_info_window"
                break
            if row.get("version_selector") == "current" and starts and ends and starts <= ANCHOR <= ends:
                chosen, chosen_start, chosen_end = row, starts, ends
                chosen_basis = "registry_latest_window_feed_info_missing_or_noncovering"
                break
        if chosen:
            chosen = dict(chosen)
            chosen["anchor_selection_basis"] = chosen_basis
            current.append(chosen)
            selection_rows.append({"organization_id": org, "feed_id": fid, "selected_version_selector": chosen.get("version_selector"), "status": "selected", "registry_latest_start": meta.get("latest_feed_start_date", ""), "registry_latest_end": meta.get("latest_feed_end_date", ""), "feed_is_discontinued": meta.get("feed_is_discontinued", ""), "feed_discontinued_date": meta.get("feed_discontinued_date", ""), "validity_start": chosen_start.isoformat() if chosen_start else "", "validity_end": chosen_end.isoformat() if chosen_end else "", "selection_basis": chosen_basis})
        else:
            selection_rows.append({"organization_id": org, "feed_id": fid, "selected_version_selector": "", "status": "no_downloaded_archive_valid_on_anchor", "registry_latest_start": meta.get("latest_feed_start_date", ""), "registry_latest_end": meta.get("latest_feed_end_date", ""), "feed_is_discontinued": meta.get("feed_is_discontinued", ""), "feed_discontinued_date": meta.get("feed_discontinued_date", ""), "validity_start": "", "validity_end": ""})
    write_csv(ANALYSIS / "anchor_feed_selection.csv", selection_rows)
    agencies: list[dict[str, object]] = []
    feed_summaries: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for i, row in enumerate(current, 1):
        try:
            a, f = analyze_zip(Path(row["path"]), row, feed_meta)
            agencies.extend(a)
            feed_summaries.append(f)
        except Exception as e:
            errors.append({"organization_id": row.get("organization_id"), "feed_id": row.get("feed_id"), "path": row.get("path"), "error": repr(e)})
        if i % 50 == 0 or i == len(current):
            print(f"analyzed {i}/{len(current)} current zips", flush=True)
    write_csv(ANALYSIS / "gtfs_agency_metrics.csv", agencies)
    write_csv(ANALYSIS / "gtfs_feed_metrics.csv", feed_summaries)

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in agencies:
        grouped[str(row["operator_identity_key"])].append(row)
    operators: list[dict[str, object]] = []
    for identity, group in grouped.items():
        def sum_numeric(field: str) -> int:
            return sum(int(x.get(field) or 0) for x in group)
        pref_set = sorted({str(x["prefecture"]) for x in group})
        types = sorted({rt for x in group for rt in str(x["route_types"]).split("|") if rt})
        operators.append({
            "operator_id": group[0]["operator_id"], "operator_identity_key": identity, "agency_name": group[0]["agency_name"],
            "agency_url": group[0]["agency_url"], "prefectures": "|".join(pref_set), "publisher_names": "|".join(sorted({str(x["publisher_name"]) for x in group})),
            "feed_ids": "|".join(sorted({str(x["feed_id"]) for x in group})), "organization_feed_pairs": "|".join(sorted({f"{x['organization_id']}/{x['feed_id']}" for x in group})), "agency_ids": "|".join(sorted({str(x["agency_id"]) for x in group})),
            "feed_count": len({str(x["feed_id"]) for x in group}), "agency_record_count": len(group),
            "routes_sum_across_feeds": sum_numeric("route_count"), "trips_sum_across_feeds": sum_numeric("trip_count"),
            "stops_sum_across_feeds": sum_numeric("stop_count"), "service_id_sum_across_feeds": sum_numeric("service_id_count"),
            "route_types": "|".join(types),
            "weekday_trips_per_day_sum_approx": round(sum(float(x["weekday_trips_per_day_avg"]) for x in group if str(x.get("weekday_trips_per_day_avg", "")) != ""), 3),
            "weekend_trips_per_day_sum_approx": round(sum(float(x["weekend_trips_per_day_avg"]) for x in group if str(x.get("weekend_trips_per_day_avg", "")) != ""), 3),
            "weekday_trip_hours_sum_approx": round(sum(float(x["weekday_trip_hours_per_day_approx"]) for x in group if str(x.get("weekday_trip_hours_per_day_approx", "")) != ""), 3),
            "weekend_trip_hours_sum_approx": round(sum(float(x["weekend_trip_hours_per_day_approx"]) for x in group if str(x.get("weekend_trip_hours_per_day_approx", "")) != ""), 3),
            "weekday_km_sum_approx": round(sum(float(x["weekday_km_per_day_straight_line_approx"]) for x in group if str(x.get("weekday_km_per_day_straight_line_approx", "")) != ""), 3),
            "weekend_km_sum_approx": round(sum(float(x["weekend_km_per_day_straight_line_approx"]) for x in group if str(x.get("weekend_km_per_day_straight_line_approx", "")) != ""), 3),
            "schedule_status_all_dated": all(x["schedule_status"] == "dated_calendar_applied" for x in group),
        })
    write_csv(ANALYSIS / "gtfs_operator_metrics.csv", operators)
    write_csv(ANALYSIS / "gtfs_analysis_errors.csv", errors)
    selector_counts: dict[str, int] = defaultdict(int)
    for row in current:
        selector_counts[str(row.get("version_selector", "current"))] += 1
    (ANALYSIS / "gtfs_analysis_metadata.json").write_text(json.dumps({"anchor_date": ANCHOR.isoformat(), "selected_anchor_feed_archives": len(current), "selected_archive_versions": dict(selector_counts), "bus_agency_rows": len(agencies), "gtfs_bus_operator_entities": len(operators), "excluded_feeds": len(current) - len(feed_summaries) + sum(1 for x in feed_summaries if x.get("status") != "bus_feed_analyzed"), "errors": len(errors), "route_type_rule": "3, 11, 700-799", "trip_hours_note": "sum of scheduled trip elapsed times; not vehicle duty hours", "km_note": "sum of stop-to-stop great-circle distances; straight-line proxy, not routed vehicle-km", "headway_note": "mean per-route gap among service dates in the evaluation window; approximate"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"anchor_feed_archives": len(current), "archive_versions": dict(selector_counts), "bus_agency_records": len(agencies), "unique_gtfs_bus_operators": len(operators), "feed_records": len(feed_summaries), "errors": len(errors)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
