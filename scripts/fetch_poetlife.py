#!/usr/bin/env python3
"""
Fetch Tang-Song PoetLife data from cnkgraph.com (same JSON as the web map).

Compliance: see scripts/discover_endpoints.md — use for research/learning, respect rate limits,
non-commercial per site OpenResources policy unless you have written permission.

Examples:
  python scripts/fetch_poetlife.py --authors 李白,陈子昂 --output-dir data/out
  python scripts/fetch_poetlife.py --index-from-html --all-authors --output-dir data/out --delay 0.6
  python scripts/fetch_poetlife.py --authors 陈子昂 --output-dir data/out --sqlite
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.parse
from html import unescape
from pathlib import Path
from typing import Any, Iterator

import httpx

BASE = "https://cnkgraph.com"
MAP_PATH = "/Map/PoetLife"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": BASE + MAP_PATH,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-hant",
}

# Embedded in Map/PoetLife HTML: "RequestUri":"scope=&author=李白&beginYear=0&endYear=0"
AUTHOR_URI_RE = re.compile(
    r'"RequestUri"\s*:\s*"scope=&author=([^"&]+)&beginYear=0&endYear=0"',
    re.UNICODE,
)

def strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_person_name(trace: dict[str, Any], request_uri: str) -> tuple[str, str]:
    raw_title = (trace.get("Title") or "").strip()
    plain = strip_html(raw_title)
    m = re.search(r"author=([^&]+)", request_uri)
    from_param = urllib.parse.unquote(m.group(1)) if m else ""
    # Prefer explicit author param; fallback to title (may include lifespan HTML).
    name = from_param or plain
    name = re.sub(r"\s+", "", name)
    return name, raw_title


def parse_marker_timeline(detail_html: str) -> list[dict[str, str]]:
    """Extract <a href=\"javascript: ViewDetail('...')\">label</a> and following text until the next such link."""
    if not detail_html:
        return []
    entries: list[dict[str, str]] = []
    # Only match full anchors so we never slice inside an opening <a ...> (which breaks strip_html).
    # href="javascript: ViewDetail('scope=...')">659年</a>  (href may use " or ')
    link_pat = re.compile(
        r"<a[^>]*\bhref\s*=\s*(?P<hq>[\"'])javascript:\s*ViewDetail\s*\(\s*(?P<qq>[\"'])(?P<q>[^\"']+)(?P=qq)\s*\)\s*(?P=hq)\s*>(?P<label>[^<]*)</a>",
        re.IGNORECASE,
    )
    matches = list(link_pat.finditer(detail_html))
    for i, m in enumerate(matches):
        q, label = m.group("q"), m.group("label").strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(detail_html)
        body_html = detail_html[start:end]
        # Drop trailing break tags so detail_text does not glue to next line in plain text.
        body_html = re.split(r"<br\s*/?>", body_html, maxsplit=1, flags=re.I)[0]
        entries.append(
            {
                "time_view_query": q,
                "time_label": strip_html(label) or label,
                "detail_text": strip_html(body_html),
            }
        )
    return entries


def iter_authors_from_map_html(html: str) -> Iterator[str]:
    seen: set[str] = set()
    for m in AUTHOR_URI_RE.finditer(html):
        name = urllib.parse.unquote(m.group(1))
        name = name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        yield name


def fetch_map_index(client: httpx.Client) -> list[str]:
    r = client.get(BASE + MAP_PATH, headers={**DEFAULT_HEADERS, "Accept": "text/html,*/*"})
    r.raise_for_status()
    return sorted(iter_authors_from_map_html(r.text))


def fetch_biography(client: httpx.Client, query: str) -> dict[str, Any]:
    """GET /Api/Biography with browser-like headers; retry on empty/invalid JSON or transient HTTP errors."""
    url = f"{BASE}/Api/Biography?{query.lstrip('?')}"
    headers = {**DEFAULT_HEADERS, "Accept": "application/json, text/javascript, */*; q=0.01"}
    last: BaseException | None = None
    for attempt in range(5):
        try:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            raw = (r.text or "").strip()
            if not raw:
                raise ValueError("empty biography response")
            return json.loads(raw)
        except (httpx.HTTPStatusError, httpx.TransportError, json.JSONDecodeError, ValueError) as e:
            last = e
            if attempt < 4:
                time.sleep(1.2 * (2**attempt))
    assert last is not None
    raise last


def flatten_trace(
    payload: dict[str, Any],
    source_query: str,
    include_marker_html: bool,
) -> list[dict[str, Any]]:
    traces = payload.get("Traces") or []
    if not traces:
        return []
    trace = traces[0]
    person_name, person_raw = extract_person_name(trace, source_query)
    rows: list[dict[str, Any]] = []
    seq = 0

    for marker in trace.get("Markers") or []:
        title = strip_html(marker.get("Title") or "")
        lat = marker.get("Latitude")
        lng = marker.get("Longitude")
        rid = marker.get("RegionId")
        detail_html = marker.get("Detail") or ""
        timeline = parse_marker_timeline(detail_html)

        if timeline:
            for ent in timeline:
                row: dict[str, Any] = {
                    "person_name": person_name,
                    "person_name_raw": person_raw,
                    "source_request_uri": source_query,
                    "trace_title": strip_html(trace.get("Title") or ""),
                    "record_kind": "timeline_entry",
                    "sequence": seq,
                    "time_label": ent["time_label"],
                    "time_view_query": ent["time_view_query"],
                    "place_title": title,
                    "latitude": lat,
                    "longitude": lng,
                    "region_id": rid,
                    "detail_text": ent["detail_text"],
                }
                if include_marker_html:
                    row["marker_detail_html"] = detail_html
                rows.append(row)
                seq += 1
        else:
            row = {
                "person_name": person_name,
                "person_name_raw": person_raw,
                "source_request_uri": source_query,
                "trace_title": strip_html(trace.get("Title") or ""),
                "record_kind": "marker_fallback",
                "sequence": seq,
                "time_label": None,
                "time_view_query": None,
                "place_title": title,
                "latitude": lat,
                "longitude": lng,
                "region_id": rid,
                "detail_text": strip_html(detail_html) if detail_html else None,
            }
            if include_marker_html and detail_html:
                row["marker_detail_html"] = detail_html
            rows.append(row)
            seq += 1

    top_summary = payload.get("Summary")
    top_detail = payload.get("Detail")
    if top_summary or top_detail:
        rows.append(
            {
                "person_name": person_name,
                "person_name_raw": person_raw,
                "source_request_uri": source_query,
                "trace_title": strip_html(trace.get("Title") or ""),
                "record_kind": "trace_summary",
                "sequence": seq,
                "time_label": None,
                "time_view_query": None,
                "place_title": None,
                "latitude": None,
                "longitude": None,
                "region_id": None,
                "detail_text": strip_html((top_summary or "") + "\n" + (top_detail or "")),
                "trace_summary_html": top_summary,
                "trace_detail_html": top_detail,
            }
        )
    return rows


def default_author_query(name: str) -> str:
    enc = urllib.parse.quote(name, safe="")
    return f"scope=&author={enc}&beginYear=0&endYear=0"


SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS poetlife_flat (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_name TEXT NOT NULL,
  person_name_raw TEXT,
  source_request_uri TEXT,
  trace_title TEXT,
  record_kind TEXT NOT NULL,
  sequence INTEGER,
  time_label TEXT,
  time_view_query TEXT,
  place_title TEXT,
  latitude REAL,
  longitude REAL,
  region_id TEXT,
  detail_text TEXT,
  marker_detail_html TEXT,
  trace_summary_html TEXT,
  trace_detail_html TEXT
);
"""

SQLITE_INSERT = """
INSERT INTO poetlife_flat (
  person_name, person_name_raw, source_request_uri, trace_title, record_kind,
  sequence, time_label, time_view_query, place_title, latitude, longitude,
  region_id, detail_text, marker_detail_html, trace_summary_html, trace_detail_html
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


def sqlite_row_values(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("person_name"),
        row.get("person_name_raw"),
        row.get("source_request_uri"),
        row.get("trace_title"),
        row.get("record_kind"),
        row.get("sequence"),
        row.get("time_label"),
        row.get("time_view_query"),
        row.get("place_title"),
        row.get("latitude"),
        row.get("longitude"),
        row.get("region_id"),
        row.get("detail_text"),
        row.get("marker_detail_html"),
        row.get("trace_summary_html"),
        row.get("trace_detail_html"),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch cnkgraph PoetLife /Api/Biography data.")
    ap.add_argument("--authors", help="Comma-separated author names, e.g. 李白,杜甫")
    ap.add_argument("--all-authors", action="store_true", help="Use every author found in Map/PoetLife HTML index.")
    ap.add_argument("--index-from-html", action="store_true", help="Fetch Map/PoetLife to build author list (implies --all-authors if --authors omitted).")
    ap.add_argument("--output-dir", type=Path, default=Path("data/out"), help="Directory for json / jsonl outputs.")
    ap.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls.")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--include-marker-html", action="store_true", help="Include full Marker.Detail HTML in jsonl (large).")
    ap.add_argument("--raw-json", action="store_true", help="Also save raw /Api/Biography JSON per author.")
    ap.add_argument(
        "--sqlite",
        action="store_true",
        help="Also write poetlife_flat.sqlite in output-dir (same rows as jsonl).",
    )
    args = ap.parse_args()

    authors: list[str] = []
    if args.authors:
        authors.extend(a.strip() for a in args.authors.split(",") if a.strip())

    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    with httpx.Client(timeout=args.timeout, follow_redirects=True, limits=limits) as client:
        if args.index_from_html or (args.all_authors and not authors):
            found = fetch_map_index(client)
            if args.all_authors or not authors:
                authors = found
            else:
                # merge unique
                authors = sorted(set(authors) | set(found))

        if not authors:
            print("No authors to fetch: pass --authors or --all-authors/--index-from-html", file=sys.stderr)
            return 2

        jsonl_path = out_dir / "poetlife_flat.jsonl"
        sqlite_path = out_dir / "poetlife_flat.sqlite"
        db: sqlite3.Connection | None = None
        if args.sqlite:
            if sqlite_path.exists():
                sqlite_path.unlink()
            db = sqlite3.connect(str(sqlite_path))
            db.executescript(SQLITE_DDL)

        with jsonl_path.open("w", encoding="utf-8") as jf:
            for i, name in enumerate(authors):
                q = default_author_query(name)
                try:
                    payload = fetch_biography(client, q)
                except (httpx.HTTPError, ValueError, json.JSONDecodeError) as e:
                    print(f"[warn] {name}: {e}", file=sys.stderr)
                    time.sleep(args.delay)
                    continue

                if args.raw_json:
                    raw_path = out_dir / "raw" / f"{name}.json"
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

                for row in flatten_trace(payload, q, args.include_marker_html):
                    jf.write(json.dumps(row, ensure_ascii=False) + "\n")
                    if db is not None:
                        db.execute(SQLITE_INSERT, sqlite_row_values(row))

                if db is not None:
                    db.commit()
                print(f"[ok] ({i+1}/{len(authors)}) {name}")
                time.sleep(args.delay)

        if db is not None:
            db.close()
            print(f"Wrote {sqlite_path}")

    print(f"Wrote {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
