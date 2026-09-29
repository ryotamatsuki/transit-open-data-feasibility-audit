"""Shared helpers for the LINKS/GTFS public-data audit."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "links_gtfs_match"
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fieldnames is None:
        fieldnames = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def links_dataset_files() -> list[Path]:
    """Return candidate LINKS payload files, excluding audit logs and errors."""
    root = RAW / "links"
    if not root.exists():
        return []
    return sorted(
        p for p in root.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".csv", ".zip", ".xlsx", ".xls"}
        and p.name.lower() not in {"fetch_status.csv"}
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def safe_slug(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value)).strip("._")
    return value or "blank"


LEGAL_FORMS = [
    "一般社団法人", "公益社団法人", "公益財団法人", "一般財団法人",
    "特定非営利活動法人", "社会福祉法人", "合同会社", "合資会社", "合名会社",
    "株式会社", "有限会社", "（株）", "(株)", "㈱", "（有）", "(有)", "㈲",
    "（一社）", "(一社)", "（公社）", "(公社)", "（公財）", "(公財)",
]


def normalize_name(value: str | None, remove_legal: bool = True) -> str:
    """NFKC, whitespace removal, and optional legal-form removal only.

    Words such as バス, 交通, 自動車, 鉄道 are intentionally retained.
    """
    s = unicodedata.normalize("NFKC", value or "")
    s = re.sub(r"[\s\u3000]+", "", s)
    if remove_legal:
        for form in sorted(LEGAL_FORMS, key=len, reverse=True):
            s = s.replace(unicodedata.normalize("NFKC", form), "")
    return s


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
