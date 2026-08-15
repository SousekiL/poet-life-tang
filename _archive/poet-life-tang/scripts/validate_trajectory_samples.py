#!/usr/bin/env python3
"""Print trajectory sanity checks for a few famous poets; write viz/validation_log.txt."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "viz" / "data" / "trajectories.json"
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    poets = {p["name"]: p for p in data["poets"]}
    names = ["李白", "杜甫", "李商隐", "王维", "白居易"]
    lines: list[str] = []
    for n in names:
        p = poets.get(n)
        if not p:
            lines.append(f"[missing] {n} not in Tang-filtered set")
            continue
        wps = p.get("waypoints") or []
        lines.append(f"=== {n} ===")
        lines.append(
            f"  life {p.get('birthYear')}-{p.get('deathYear')} "
            f"birth_key={p.get('birth', {}).get('place_key')} "
            f"death_key={(p.get('death') or {}).get('place_key')}"
        )
        lines.append(f"  waypoints={len(wps)}")
        if wps:
            lines.append(
                f"  first_wp {wps[0].get('yearStart')}-{wps[0].get('yearEnd')} "
                f"{wps[0].get('place_key')} {wps[0].get('place', '')[:40]}"
            )
            lines.append(
                f"  last_wp {wps[-1].get('yearStart')}-{wps[-1].get('yearEnd')} "
                f"{wps[-1].get('place_key')} {wps[-1].get('place', '')[:40]}"
            )
        lines.append(f"  needs_review={p.get('needs_review')}")
    stats = data.get("meta", {}).get("stats", {})
    lines.append("=== meta.stats ===")
    lines.append(json.dumps(stats, ensure_ascii=False, indent=2))
    out = root / "viz" / "validation_log.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
