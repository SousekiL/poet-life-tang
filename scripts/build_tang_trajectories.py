#!/usr/bin/env python3
"""
Build Tang-era (618–907) poet trajectories from poetlife_flat.sqlite for map animation.

Writes viz/data/trajectories.json with place_key (prefecture-level bucketing), waypoints,
birth/death points, and sorted life events for time-prefix density in the browser.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

YEAR_RE = re.compile(r"beginYear=(\d+).*?endYear=(\d+)", re.I)
LIFE_SPAN_RE = re.compile(r"\((\d{3,4})\s*-\s*(\d{3,4})\)")
DEATH_HINT_RE = re.compile(r"卒|去世|病逝|病卒|暴卒|卒于|殁|逝世|薨")
BIRTH_PLACE_MARK = "(出生地)"


def parse_year_span_from_query(q: str | None) -> tuple[int | None, int | None]:
    if not q:
        return None, None
    m = YEAR_RE.search(q)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def parse_life_years(trace_title: str, person_name_raw: str) -> tuple[int | None, int | None]:
    for s in (trace_title, person_name_raw):
        m = LIFE_SPAN_RE.search(s or "")
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def tang_overlaps(birth: int | None, death: int | None, lo: int = 618, hi: int = 907) -> bool:
    if birth is None or death is None:
        return False
    return birth <= hi and death >= lo


def raw_waypoint_year_span(rows: list[Row]) -> tuple[int | None, int | None]:
    """Min/max calendar years from timeline rows (before place_key merge)."""
    lows: list[int] = []
    highs: list[int] = []
    for r in rows:
        if r.begin_y is None or r.end_y is None:
            continue
        if r.begin_y == 0 and r.end_y == 0:
            continue
        lows.append(int(r.begin_y))
        highs.append(int(r.end_y))
    if not lows:
        return None, None
    return min(lows), max(highs)


def region_to_place_key(
    region_id: str | None, lat: float | None, lng: float | None
) -> tuple[str, str, str | None]:
    """
    Returns (place_key, method, display_hint).
    place_key: CN###### (prefecture GB style) or GRID:lat:lng for fallback.
    """
    if region_id:
        rid = region_id.strip().upper()
        digits = re.sub(r"\D", "", rid[2:] if rid.startswith("CN") else rid)
        if digits:
            d = digits[:9] if len(digits) > 9 else digits
            pref: int | None = None
            if len(d) >= 6:
                core = int(d[:6])
                pref = core // 100 * 100
            elif len(d) == 5:
                pref = int(d) * 10
            elif len(d) == 4:
                pref = int(d) * 100
            elif len(d) == 3:
                pref = int(d) * 1000
            if pref is not None and pref > 0:
                return (f"CN{pref:06d}", "gb_digits", None)

    if lat is not None and lng is not None:
        glat = round(float(lat), 1)
        glng = round(float(lng), 1)
        return (f"GRID:{glat}:{glng}", "grid", None)

    return ("", "none", None)


def load_prefecture_overrides(path: Path | None) -> dict[str, str]:
    """CSV columns: region_suffix,prefecture_suffix (digits only, no CN)."""
    out: dict[str, str] = {}
    if not path or not path.is_file():
        return out
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            a = (row.get("region_suffix") or row.get("from") or "").strip()
            b = (row.get("prefecture_suffix") or row.get("to") or "").strip()
            if a and b:
                out[a] = b
    return out


@dataclass
class Row:
    person_name: str
    trace_title: str
    person_name_raw: str
    sequence: int
    time_label: str
    time_view_query: str
    place_title: str
    lat: float | None
    lng: float | None
    region_id: str | None
    detail_text: str
    begin_y: int | None = None
    end_y: int | None = None


def fetch_rows(con: sqlite3.Connection) -> list[Row]:
    cur = con.execute(
        """
        SELECT person_name, trace_title, person_name_raw, sequence, time_label,
               time_view_query, place_title, latitude, longitude, region_id, detail_text
        FROM poetlife_flat
        WHERE record_kind = 'timeline_entry'
        ORDER BY person_name, sequence, rowid
        """
    )
    rows: list[Row] = []
    for tup in cur.fetchall():
        r = Row(
            person_name=tup[0] or "",
            trace_title=tup[1] or "",
            person_name_raw=tup[2] or "",
            sequence=int(tup[3] or 0),
            time_label=tup[4] or "",
            time_view_query=tup[5] or "",
            place_title=tup[6] or "",
            lat=float(tup[7]) if tup[7] is not None else None,
            lng=float(tup[8]) if tup[8] is not None else None,
            region_id=tup[9] or None,
            detail_text=tup[10] or "",
        )
        r.begin_y, r.end_y = parse_year_span_from_query(r.time_view_query)
        rows.append(r)
    return rows


def apply_override_place_key(
    region_id: str | None, lat: float | None, lng: float | None, overrides: dict[str, str]
) -> tuple[str, str, str | None]:
    if region_id:
        digits = re.sub(r"\D", "", region_id.upper().replace("CN", ""))
        if digits in overrides:
            pref = int(overrides[digits])
            return (f"CN{pref:06d}", "override", None)
    return region_to_place_key(region_id, lat, lng)


def pick_death_waypoint(
    death_year: int, wps: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Prefer waypoint overlapping death_year with 卒 in detail; else last overlapping; else last wp."""
    candidates: list[dict[str, Any]] = []
    for wp in wps:
        b, e = wp.get("yearStart"), wp.get("yearEnd")
        if b is None or e is None:
            continue
        if b <= death_year <= e:
            candidates.append(wp)
    if not candidates and wps:
        return wps[-1]
    if not candidates:
        return None
    for wp in reversed(candidates):
        if DEATH_HINT_RE.search(wp.get("detail_text") or ""):
            return wp
    return candidates[-1]


def build_waypoints_for_person(
    person_rows: list[Row], overrides: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge consecutive same place_key; representative lat/lng = first point in run."""
    raw_segments: list[dict[str, Any]] = []
    for r in person_rows:
        if r.begin_y is None or r.end_y is None:
            continue
        if r.begin_y == 0 and r.end_y == 0:
            continue
        pk, method, _ = apply_override_place_key(r.region_id, r.lat, r.lng, overrides)
        if not pk:
            continue
        if r.lat is None or r.lng is None:
            continue
        raw_segments.append(
            {
                "yearStart": r.begin_y,
                "yearEnd": r.end_y,
                "lat": float(r.lat),
                "lng": float(r.lng),
                "place": r.place_title,
                "place_key": pk,
                "place_key_method": method,
                "detail_text": r.detail_text,
                "sequence": r.sequence,
            }
        )
    raw_segments.sort(key=lambda x: (x["yearStart"], x["yearEnd"], x["sequence"]))

    merged: list[dict[str, Any]] = []
    for seg in raw_segments:
        if merged and merged[-1]["place_key"] == seg["place_key"]:
            prev = merged[-1]
            prev["yearEnd"] = max(prev["yearEnd"], seg["yearEnd"])
            prev["yearStart"] = min(prev["yearStart"], seg["yearStart"])
            continue
        merged.append(
            {
                "yearStart": seg["yearStart"],
                "yearEnd": seg["yearEnd"],
                "lat": seg["lat"],
                "lng": seg["lng"],
                "place": seg["place"],
                "place_key": seg["place_key"],
                "place_key_method": seg["place_key_method"],
                "detail_text": seg["detail_text"],
            }
        )
    return merged, {"raw_segments": len(raw_segments), "merged_segments": len(merged)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Tang trajectories JSON for viz/")
    ap.add_argument("--sqlite", type=Path, default=Path("data/out/poetlife_flat.sqlite"))
    ap.add_argument("--output", type=Path, default=Path("viz/data/trajectories.json"))
    ap.add_argument(
        "--overrides",
        type=Path,
        default=None,
        help="Optional CSV: region_suffix,prefecture_suffix",
    )
    ap.add_argument("--tang-lo", type=int, default=618)
    ap.add_argument("--tang-hi", type=int, default=907)
    args = ap.parse_args()

    if not args.sqlite.is_file():
        raise SystemExit(f"SQLite not found: {args.sqlite}")

    overrides = load_prefecture_overrides(args.overrides)
    con = sqlite3.connect(str(args.sqlite))
    all_rows = fetch_rows(con)
    con.close()

    by_person: dict[str, list[Row]] = defaultdict(list)
    for r in all_rows:
        by_person[r.person_name].append(r)

    poets_out: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    meta_warnings = defaultdict(int)
    stats = {
        "timeline_rows": len(all_rows),
        "tang_poets": 0,
        "tang_poets_title_span": 0,
        "tang_poets_waypoint_span": 0,
        "skipped_no_year_signal": 0,
        "skipped_no_tang_overlap": 0,
        "skipped_no_waypoints": 0,
        "title_span_without_birth_marker_row": 0,
        "death_inferred_from_year": 0,
        "death_fallback_last_wp": 0,
        "death_missing": 0,
    }
    place_key_labels: dict[str, str] = {}

    pid = 0
    for name, rows in sorted(by_person.items()):
        trace_title = rows[0].trace_title if rows else ""
        raw_title = rows[0].person_name_raw if rows else ""

        waypoints, wp_meta = build_waypoints_for_person(rows, overrides)
        if not waypoints:
            stats["skipped_no_waypoints"] += 1
            meta_warnings["no_waypoints"] += 1
            continue

        title_birth, title_death = parse_life_years(trace_title, raw_title)
        wp_lo, wp_hi = raw_waypoint_year_span(rows)

        span_source: str
        birth_y: int
        death_y: int
        if title_birth is not None and title_death is not None:
            birth_y, death_y = title_birth, title_death
            span_source = "title"
        elif wp_lo is not None and wp_hi is not None:
            birth_y, death_y = wp_lo, wp_hi
            span_source = "waypoints"
            meta_warnings["life_span_from_waypoints"] += 1
        else:
            stats["skipped_no_year_signal"] += 1
            meta_warnings["no_year_signal"] += 1
            continue

        if not tang_overlaps(birth_y, death_y, args.tang_lo, args.tang_hi):
            stats["skipped_no_tang_overlap"] += 1
            continue

        birth_row = next((r for r in rows if BIRTH_PLACE_MARK in (r.place_title or "")), None)
        birth_obj: dict[str, Any] | None = None
        b_pk: str | None = None
        if span_source == "title" and birth_row and birth_row.lat is not None and birth_row.lng is not None:
            b_pk, _, _ = apply_override_place_key(
                birth_row.region_id, birth_row.lat, birth_row.lng, overrides
            )
            if b_pk:
                birth_obj = {
                    "lat": float(birth_row.lat),
                    "lng": float(birth_row.lng),
                    "place": birth_row.place_title,
                    "place_key": b_pk,
                    "year": birth_y,
                }
        elif span_source == "title" and not birth_row:
            stats["title_span_without_birth_marker_row"] += 1
            meta_warnings["title_no_birth_place"] += 1

        death_obj: dict[str, Any] | None = None
        death_event_year: int | None = None
        if span_source == "title" and title_death is not None:
            death_wp = pick_death_waypoint(title_death, waypoints)
            if death_wp:
                if DEATH_HINT_RE.search(death_wp.get("detail_text") or ""):
                    stats["death_inferred_from_year"] += 1
                else:
                    stats["death_fallback_last_wp"] += 1
                death_obj = {
                    "lat": death_wp["lat"],
                    "lng": death_wp["lng"],
                    "place": death_wp["place"],
                    "place_key": death_wp["place_key"],
                    "year": title_death,
                }
                death_event_year = title_death
            else:
                stats["death_missing"] += 1
        # waypoint-only span: no death/birth emphasis objects or events

        for pk, label in (
            *(
                [(birth_obj["place_key"], birth_obj["place"])]
                if birth_obj and birth_obj.get("place_key")
                else []
            ),
            *(
                [(death_obj["place_key"], death_obj["place"])]
                if death_obj and death_obj.get("place_key")
                else []
            ),
        ):
            if pk and pk not in place_key_labels:
                place_key_labels[str(pk)] = (label or pk) or str(pk)

        pid += 1
        poet_id = f"p{pid}"
        poets_out.append(
            {
                "id": poet_id,
                "name": name,
                "birthYear": birth_y,
                "deathYear": death_y,
                "time_span_source": span_source,
                "birth": birth_obj,
                "death": death_obj,
                "waypoints": waypoints,
                "needs_review": span_source == "title" and death_obj is None,
                "emphasize_birth_death": span_source == "title" and (birth_obj is not None or death_obj is not None),
                "_wp_stats": wp_meta,
            }
        )

        if birth_obj:
            events.append(
                {
                    "year": birth_obj["year"],
                    "kind": "birth",
                    "poet_id": poet_id,
                    "name": name,
                    "place_key": birth_obj["place_key"],
                    "lat": birth_obj["lat"],
                    "lng": birth_obj["lng"],
                }
            )
        if death_obj and death_event_year is not None:
            events.append(
                {
                    "year": death_event_year,
                    "kind": "death",
                    "poet_id": poet_id,
                    "name": name,
                    "place_key": death_obj["place_key"],
                    "lat": death_obj["lat"],
                    "lng": death_obj["lng"],
                }
            )

        stats["tang_poets"] += 1
        if span_source == "title":
            stats["tang_poets_title_span"] += 1
        else:
            stats["tang_poets_waypoint_span"] += 1

    events.sort(key=lambda e: (e["year"], 0 if e["kind"] == "birth" else 1, e["poet_id"]))

    # Prefix counts per place_key for pulse intensity (time-correct density).
    birth_pref: dict[str, int] = defaultdict(int)
    death_pref: dict[str, int] = defaultdict(int)
    for e in events:
        pk = e.get("place_key") or ""
        if e["kind"] == "birth":
            birth_pref[pk] += 1
            e["prefix_count"] = birth_pref[pk]
        else:
            death_pref[pk] += 1
            e["prefix_count"] = death_pref[pk]

    payload: dict[str, Any] = {
        "meta": {
            "tang_range": [args.tang_lo, args.tang_hi],
            "source_sqlite": str(args.sqlite),
            "stats": stats,
            "warnings": dict(meta_warnings),
            "prefecture_labels": place_key_labels,
            "rules": {
                "tang_overlap": f"birthYear <= {args.tang_hi} and deathYear >= {args.tang_lo} (birthYear/deathYear from title if present, else min/max years in timeline)",
                "birth": f"only when time_span_source=title and a row contains '{BIRTH_PLACE_MARK}'",
                "death": "only when time_span_source=title: waypoint overlapping parsed death year…",
                "waypoint_only": "no birth/death pulses; route uses merged waypoints over inferred year span",
                "place_key": "CN###### from region_id digits (6-digit county -> prefecture floor), else GRID:lat:lng",
            },
        },
        "events": events,
        "poets": poets_out,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"Wrote {args.output} poets={len(poets_out)} events={len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
