#!/usr/bin/env python3
"""Create auditable comparison keys for GTFS agencies and LINKS operators."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from common import ANALYSIS, normalize_name, links_dataset_files, read_csv, write_csv
from analyze_links_fields import csv_records_from


def main() -> None:
    gtfs_path = ANALYSIS / "gtfs_operator_metrics.csv"
    rows = read_csv(gtfs_path) if gtfs_path.exists() else []
    for row in rows:
        row["agency_name_key"] = normalize_name(row.get("agency_name"))
        row["publisher_name_key"] = normalize_name(row.get("publisher_name"))
    write_csv(ANALYSIS / "normalized_gtfs_operators.csv", rows)

    links_files = links_dataset_files()
    links_rows: list[dict[str, str]] = []
    for file in links_files:
        for member, columns, rows in csv_records_from(file):
            for idx, row in enumerate(rows, 1):
                name_col = next((c for c in columns if any(k in c for k in ("事業者名", "事業者", "会社名"))), "")
                raw_name = row.get(name_col, "") if name_col else ""
                links_rows.append({"source_file": member, "source_row": str(idx), "links_name_column": name_col, "links_name_raw": raw_name, "links_name_key": normalize_name(raw_name), **{f"field_{k}": v for k, v in row.items()}})
    write_csv(ANALYSIS / "normalized_links_rows.csv", links_rows)
    print(json.dumps({"gtfs_agency_rows": len(rows), "links_csv_files": len(links_files), "links_rows": len(links_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
