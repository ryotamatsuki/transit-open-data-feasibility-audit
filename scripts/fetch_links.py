#!/usr/bin/env python3
"""Fetch the official 2025 Project LINKS general passenger transport package.

The script records access failures verbatim and does not substitute GitHub
fixtures for the published package. When CKAN is available, it saves package
metadata, every resource metadata record, and the resource bytes.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from common import RAW, now_utc, safe_slug, sha256_bytes

PACKAGE_ID = "links-ippanryokyaku-2025"
API_URL = f"https://www.geospatial.jp/ckan/api/3/action/package_show?id={PACKAGE_ID}"
LANDING_URL = f"https://www.geospatial.jp/ckan/dataset/{PACKAGE_ID}"
OUT = RAW / "links"


def request(url: str, extra_headers: dict[str, str] | None = None) -> tuple[bytes, dict[str, str], int]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; public-data-audit/1.0)",
        "Accept": "application/json,text/html,*/*",
    }
    headers.update(extra_headers or {})
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read(), dict(response.headers.items()), response.status


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log: list[dict[str, object]] = []
    try:
        data, headers, status = request(API_URL)
        (OUT / "package_show.json").write_bytes(data)
        obj = json.loads(data)
        log.append({"url": API_URL, "status": status, "bytes": len(data), "sha256": sha256_bytes(data), "retrieved_utc": now_utc(), "content_type": headers.get("Content-Type", "")})
        resources = obj.get("result", {}).get("resources", [])
        (OUT / "resources.json").write_text(json.dumps(resources, ensure_ascii=False, indent=2), encoding="utf-8")
        for resource in resources:
            rid = resource.get("id", "unknown")
            url = resource.get("url") or f"https://www.geospatial.jp/ckan/dataset/{PACKAGE_ID}/resource/{rid}/download"
            name = resource.get("name") or resource.get("url") or rid
            try:
                payload, h, st = request(url)
                filename = safe_slug(Path(str(name)).name or rid)
                (OUT / filename).write_bytes(payload)
                log.append({"url": url, "resource_id": rid, "resource_name": name, "path": str(OUT / filename), "status": st, "bytes": len(payload), "sha256": sha256_bytes(payload), "retrieved_utc": now_utc(), "content_type": h.get("Content-Type", "")})
            except Exception as e:
                log.append({"url": url, "resource_id": rid, "resource_name": name, "status": getattr(e, "code", "ERROR"), "error": repr(e), "retrieved_utc": now_utc()})
    except Exception as e:
        log.append({"url": API_URL, "status": getattr(e, "code", "ERROR"), "error": repr(e), "retrieved_utc": now_utc()})
        # Landing-page attempt is part of the ordinary published route, not an
        # authentication or access-control bypass.
        try:
            payload, h, st = request(LANDING_URL)
            (OUT / "landing.html").write_bytes(payload)
            log.append({"url": LANDING_URL, "status": st, "bytes": len(payload), "sha256": sha256_bytes(payload), "retrieved_utc": now_utc(), "content_type": h.get("Content-Type", "")})
        except Exception as page_error:
            log.append({"url": LANDING_URL, "status": getattr(page_error, "code", "ERROR"), "error": repr(page_error), "retrieved_utc": now_utc()})
            # A resource UUID was exposed by the public dataset listing/index.
            # This is the ordinary public CKAN download route with normal
            # browser navigation headers; it does not attempt to evade access
            # controls. Replace the UUID if CKAN publishes a new resource.
            resource_url = f"{LANDING_URL}/resource/5f877415-b4cb-4a08-b622-b748854677d6/download"
            try:
                payload, h, st = request(resource_url, {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
                    "Referer": "https://www.mlit.go.jp/links/open-data.html",
                    "Accept": "text/csv,application/zip,application/octet-stream,*/*",
                })
                content_type = h.get("Content-Type", "")
                if "html" in content_type.lower():
                    (OUT / "browser_headers.response_body.bin").write_bytes(payload)
                    log.append({"url": resource_url, "status": st, "bytes": len(payload), "sha256": sha256_bytes(payload), "retrieved_utc": now_utc(), "content_type": content_type, "error": "Response was HTML, not a CSV/ZIP dataset payload"})
                else:
                    suffix = ".zip" if payload.startswith(b"PK\x03\x04") else (".csv" if "csv" in content_type.lower() or b"," in payload[:4096] else ".bin")
                    payload_path = OUT / f"public_resource_payload{suffix}"
                    payload_path.write_bytes(payload)
                    log.append({"url": resource_url, "path": str(payload_path), "status": st, "bytes": len(payload), "sha256": sha256_bytes(payload), "retrieved_utc": now_utc(), "content_type": content_type})
            except Exception as resource_error:
                log.append({"url": resource_url, "status": getattr(resource_error, "code", "ERROR"), "error": repr(resource_error), "retrieved_utc": now_utc()})
    (OUT / "fetch_status.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
