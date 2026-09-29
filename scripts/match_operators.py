#!/usr/bin/env python3
"""Match GTFS internal agency names to LINKS legal operators conservatively."""
from __future__ import annotations

import csv
import difflib
import json
from collections import defaultdict
from pathlib import Path

from common import ANALYSIS, ROOT, links_dataset_files, normalize_name, read_csv, write_csv


def main() -> None:
    gtfs = read_csv(ANALYSIS / "gtfs_operator_metrics.csv") if (ANALYSIS / "gtfs_operator_metrics.csv").exists() else []
    links_path = ANALYSIS / "links_operator_metrics.csv"
    raw_links_path = ANALYSIS / "links_raw_rows.csv"
    acquired = links_path.exists() and raw_links_path.exists() and bool(links_dataset_files())
    links = read_csv(links_path) if acquired else []
    raw_links = read_csv(raw_links_path) if acquired else []
    by_raw: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_key: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in links:
        raw_name = row.get("operator_name", "").strip()
        if not raw_name:
            continue
        by_raw[raw_name].append(row)
        by_key[normalize_name(raw_name)].append(row)

    aliases_path = ROOT / "data" / "aliases.csv"
    aliases: dict[str, list[dict[str, str]]] = defaultdict(list)
    if aliases_path.exists():
        for row in read_csv(aliases_path):
            if row.get("review_status", "").lower() == "approved" and row.get("evidence") and row.get("location_validation"):
                aliases[row.get("operator_id", "")].append(row)

    matched: list[dict[str, object]] = []
    fuzzy: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []
    confirmed_links: set[str] = set()
    class_counts = {k: 0 for k in "ABCDE"}
    if not acquired:
        for op in gtfs:
            unmatched.append({"operator_id": op.get("operator_id"), "agency_name": op.get("agency_name"), "agency_url": op.get("agency_url"), "prefectures": op.get("prefectures"), "match_class": "not_evaluable", "reason": "official LINKS raw files were not acquired; this is not Match E"})
    else:
        for op in gtfs:
            raw_name = op.get("agency_name", "").strip()
            key = normalize_name(raw_name)
            exact = by_raw.get(raw_name, [])
            normalized = by_key.get(key, [])
            chosen = None
            match_class = ""
            basis = ""
            if len({x.get("links_operator_id") for x in exact}) == 1 and exact:
                chosen, match_class, basis = exact[0], "A", "raw agency_name equals LINKS operator_name"
            elif exact:
                fuzzy.extend({"operator_id": op.get("operator_id"), "agency_name": raw_name, "candidate_links_operator_id": x.get("links_operator_id"), "candidate_links_name": x.get("operator_name"), "score": 1.0, "candidate_type": "exact_name_ambiguous_multiple_LINKS_entities", "auto_accepted": False} for x in exact)
            elif len({x.get("links_operator_id") for x in normalized}) == 1 and normalized:
                chosen, match_class, basis = normalized[0], "B", "NFKC/whitespace/legal-form normalized name equality"
            elif normalized:
                fuzzy.extend({"operator_id": op.get("operator_id"), "agency_name": raw_name, "candidate_links_operator_id": x.get("links_operator_id"), "candidate_links_name": x.get("operator_name"), "score": 1.0, "candidate_type": "normalized_name_ambiguous_multiple_LINKS_entities", "auto_accepted": False} for x in normalized)
            else:
                for alias in aliases.get(str(op.get("operator_id")), []):
                    candidate = next((x for x in links if x.get("links_operator_id") == alias.get("links_operator_id")), None)
                    if candidate:
                        chosen, match_class, basis = candidate, "C", "manually reviewed alias; evidence and location validation supplied"
                        break
            if chosen:
                class_counts[match_class] += 1
                confirmed_links.add(str(chosen.get("links_operator_id", "")))
                matched.append({"operator_id": op.get("operator_id"), "gtfs_agency_name": raw_name, "agency_url": op.get("agency_url"), "gtfs_prefectures": op.get("prefectures"), "links_operator_id": chosen.get("links_operator_id"), "links_operator_name": chosen.get("operator_name"), "links_location": chosen.get("prefecture_address"), "links_operator_number": chosen.get("operator_number"), "match_class": match_class, "match_basis": basis, "link_validation": "unique name candidate; C alias additionally reviewed", "source_rows": chosen.get("source_rows")})
                continue

            candidates = []
            for candidate in links:
                candidate_name = candidate.get("operator_name", "")
                score = difflib.SequenceMatcher(None, key, normalize_name(candidate_name)).ratio() if key and candidate_name else 0.0
                if score >= 0.55:
                    candidates.append((score, candidate))
            candidates.sort(key=lambda item: (-item[0], item[1].get("operator_name", "")))
            for score, candidate in candidates[:3]:
                fuzzy.append({"operator_id": op.get("operator_id"), "agency_name": raw_name, "agency_url": op.get("agency_url"), "prefectures": op.get("prefectures"), "candidate_links_operator_id": candidate.get("links_operator_id"), "candidate_links_name": candidate.get("operator_name"), "candidate_location": candidate.get("prefecture_address"), "score": round(score, 4), "candidate_type": "fuzzy_review_required", "auto_accepted": False})
            if candidates:
                class_counts["D"] += 1
                unmatched.append({"operator_id": op.get("operator_id"), "agency_name": raw_name, "agency_url": op.get("agency_url"), "prefectures": op.get("prefectures"), "match_class": "D", "reason": "fuzzy candidate(s) exist; no automatic acceptance"})
            else:
                class_counts["E"] += 1
                unmatched.append({"operator_id": op.get("operator_id"), "agency_name": raw_name, "agency_url": op.get("agency_url"), "prefectures": op.get("prefectures"), "match_class": "E", "reason": "no exact, normalized, approved-alias, or fuzzy candidate"})

    unmatched_links = []
    if acquired:
        for row in links:
            if str(row.get("links_operator_id", "")) not in confirmed_links:
                unmatched_links.append({**row, "reason": "not confirmed as a GTFS bus agency match"})
    else:
        unmatched_links.append({"status": "not_evaluable", "reason": "LINKS source rows not acquired; no national unmatched LINKS count can be calculated"})

    write_csv(ANALYSIS / "matched_operators.csv", matched)
    write_csv(ANALYSIS / "unmatched_gtfs.csv", unmatched)
    write_csv(ANALYSIS / "unmatched_links.csv", unmatched_links)
    write_csv(ANALYSIS / "fuzzy_candidates.csv", fuzzy)
    summary = []
    for cls in "ABCDE":
        summary.append({"match_class": cls, "confirmed_or_candidate_count": class_counts[cls] if acquired else "", "status": "measured" if acquired else "not_evaluable_LINKS_data_unavailable", "note": {"A":"raw exact name", "B":"normalized exact name", "C":"manual approved alias", "D":"fuzzy candidates only, not accepted", "E":"no candidate after a complete LINKS comparison"}[cls]})
    summary.append({"match_class": "GTFS_total", "confirmed_or_candidate_count": len(gtfs), "status": "measured_from_internal_GTFS_agency_names", "note": "Canonical entities across current GTFS feeds, not feed count"})
    write_csv(ANALYSIS / "match_summary.csv", summary)
    print(json.dumps({"gtfs_operators": len(gtfs), "links_source_acquired": bool(acquired), "matched": len(matched), "unmatched_or_not_evaluable": len(unmatched), "fuzzy_candidates": len(fuzzy)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
