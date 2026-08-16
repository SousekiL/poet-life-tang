#!/usr/bin/env python3
"""
Data quality check for Tang-networks.

Validates data integrity and reports statistics for the actual data files.

Usage:
    cd /path/to/poet-life-tang
    python scripts/quality_check.py [--data-dir PATH]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections import defaultdict


def check_persons(persons_path: Path) -> dict:
    """Check persons data quality."""
    if not persons_path.exists():
        return {"error": f"File not found: {persons_path}"}

    import csv
    with open(persons_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    stats = {
        "total_records": len(rows),
        "duplicate_ids": 0,
        "missing_name_chn": 0,
        "missing_birthyear": 0,
        "missing_deathyear": 0,
        "female_count": 0,
        "dynasty_distribution": defaultdict(int),
    }

    seen_ids = set()
    for r in rows:
        pid = r.get("c_personid", "")
        if pid in seen_ids:
            stats["duplicate_ids"] += 1
        seen_ids.add(pid)

        if not r.get("name_chn", "").strip():
            stats["missing_name_chn"] += 1
        if not r.get("birthyear", "").strip():
            stats["missing_birthyear"] += 1
        if not r.get("deathyear", "").strip():
            stats["missing_deathyear"] += 1
        if r.get("is_female", "0") == "1":
            stats["female_count"] += 1
        dy = r.get("dynasty_chn", "未知")
        stats["dynasty_distribution"][dy] += 1

    stats["dynasty_distribution"] = dict(stats["dynasty_distribution"])
    return stats


def check_relationships(rels_path: Path) -> dict:
    """Check relationships data quality."""
    if not rels_path.exists():
        return {"error": f"File not found: {rels_path}"}

    import csv
    with open(rels_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    stats = {
        "total_records": len(rows),
        "unique_edges": 0,
        "self_loops": 0,
        "missing_source_ref": 0,
        "type_distribution": defaultdict(int),
        "evidence_distribution": defaultdict(int),
        "multi_evidence_edges": 0,
    }

    edges = set()
    edge_counts = defaultdict(int)
    for r in rows:
        s, t = r.get("source_id", ""), r.get("target_id", "")
        rel_type = r.get("rel_type", "")
        rel_subtype = r.get("rel_subtype", "")
        edge_key = (s, t, rel_type, rel_subtype)
        edges.add(edge_key)
        edge_counts[edge_key] += 1

        if s == t:
            stats["self_loops"] += 1
        if not r.get("source_ref", "").strip():
            stats["missing_source_ref"] += 1

        stats["type_distribution"][rel_type] += 1
        stats["evidence_distribution"][r.get("evidence_level", "unknown")] += 1

    stats["unique_edges"] = len(edges)
    stats["multi_evidence_edges"] = sum(1 for v in edge_counts.values() if v > 1)
    stats["type_distribution"] = dict(stats["type_distribution"])
    stats["evidence_distribution"] = dict(stats["evidence_distribution"])

    return stats


def check_combined(combined_persons_path: Path, combined_rels_path: Path) -> dict:
    """Check combined network consistency."""
    import csv

    if not combined_persons_path.exists() or not combined_rels_path.exists():
        return {"error": "Missing combined data files"}

    persons = {}
    with open(combined_persons_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            persons[int(r["c_personid"])] = r

    rels = []
    with open(combined_rels_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rels.append(r)

    person_ids = set(persons.keys())
    rel_ids = set()
    for r in rels:
        rel_ids.add(int(r["source_id"]))
        rel_ids.add(int(r["target_id"]))

    missing_in_persons = rel_ids - person_ids

    # Check connected components
    from collections import deque
    adj = defaultdict(set)
    for r in rels:
        s, t = int(r["source_id"]), int(r["target_id"])
        adj[s].add(t)
        adj[t].add(s)

    visited = set()
    components = []
    for n in sorted(person_ids):
        if n in visited:
            continue
        comp = set()
        queue = deque([n])
        while queue:
            cur = queue.popleft()
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            for nb in adj.get(cur, []):
                if nb not in visited:
                    queue.append(nb)
        components.append(comp)

    components.sort(key=len, reverse=True)

    core_count = sum(1 for p in persons.values() if p.get("role", "core") == "core")
    bridge_count = sum(1 for p in persons.values() if p.get("role", "") == "bridge")

    # primary_rel check: exactly one per person pair
    pair_primary = defaultdict(int)
    for r in rels:
        if r.get("primary_rel", "0") == "1":
            pair_key = (min(int(r["source_id"]), int(r["target_id"])),
                        max(int(r["source_id"]), int(r["target_id"])))
            pair_primary[pair_key] += 1
    multi_primary = {k: v for k, v in pair_primary.items() if v > 1}

    stats = {
        "total_persons": len(persons),
        "core_persons": core_count,
        "bridge_persons": bridge_count,
        "total_edges": len(rels),
        "persons_in_rels": len(rel_ids),
        "missing_in_persons_table": len(missing_in_persons),
        "connected_components": len(components),
        "largest_component": len(components[0]) if components else 0,
        "multi_primary_rel_pairs": len(multi_primary),
    }

    if len(components) > 1:
        not_in_main = person_ids - components[0]
        not_in_main_names = [persons[p]["name_chn"] for p in not_in_main if p in persons]
        stats["not_in_main_component"] = len(not_in_main)
        stats["not_in_main_names"] = not_in_main_names

    no_edges = person_ids - rel_ids
    if no_edges:
        stats["no_edge_persons"] = len(no_edges)
        stats["no_edge_names"] = [persons[p]["name_chn"] for p in no_edges if p in persons]

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Data quality check")
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path("data"),
        help="Data directory"
    )
    args = parser.parse_args()

    data_dir = args.data_dir

    print("=" * 60)
    print("Tang-networks Data Quality Report")
    print("=" * 60)

    # Check persons
    print("\n[Persons]")
    persons_stats = check_persons(data_dir / "persons.csv")
    if "error" in persons_stats:
        print(f"  Error: {persons_stats['error']}")
    else:
        print(f"  Total records: {persons_stats['total_records']}")
        print(f"  Duplicate IDs: {persons_stats['duplicate_ids']}")
        print(f"  Missing name_chn: {persons_stats['missing_name_chn']}")
        print(f"  Missing birthyear: {persons_stats['missing_birthyear']}")
        print(f"  Missing deathyear: {persons_stats['missing_deathyear']}")
        print(f"  Female: {persons_stats['female_count']}")

    # Check relationships (raw)
    print("\n[Relationships - Raw]")
    rels_stats = check_relationships(data_dir / "relationships.csv")
    if "error" in rels_stats:
        print(f"  Error: {rels_stats['error']}")
    else:
        print(f"  Total raw records: {rels_stats['total_records']}")
        print(f"  Unique edges: {rels_stats['unique_edges']}")
        print(f"  Self-loops: {rels_stats['self_loops']}")
        print(f"  Multi-evidence edges: {rels_stats['multi_evidence_edges']}")
        print(f"  Missing source_ref: {rels_stats['missing_source_ref']}")
        print(f"  Evidence distribution:")
        for ev, count in sorted(rels_stats['evidence_distribution'].items()):
            print(f"    {ev}: {count}")
        print(f"  Type distribution:")
        for rt, count in sorted(rels_stats['type_distribution'].items()):
            print(f"    {rt}: {count}")

    # Check Layer 1
    print("\n[Relationships - Layer 1]")
    l1_stats = check_relationships(data_dir / "relationships_layer1.csv")
    if "error" in l1_stats:
        print(f"  Error: {l1_stats['error']}")
    else:
        print(f"  Total edges: {l1_stats['total_records']}")

    # Check Layer 2
    print("\n[Relationships - Layer 2]")
    l2_stats = check_relationships(data_dir / "relationships_layer2.csv")
    if "error" in l2_stats:
        print(f"  Error: {l2_stats['error']}")
    else:
        print(f"  Total edges: {l2_stats['total_records']}")

    # Check combined
    print("\n[Combined Network]")
    combined_stats = check_combined(data_dir / "persons_combined.csv", data_dir / "relationships_combined.csv")
    if "error" in combined_stats:
        print(f"  Error: {combined_stats['error']}")
    else:
        print(f"  Total persons: {combined_stats['total_persons']} (core: {combined_stats['core_persons']}, bridge: {combined_stats['bridge_persons']})")
        print(f"  Total edges: {combined_stats['total_edges']}")
        print(f"  Persons referenced in edges: {combined_stats['persons_in_rels']}")
        print(f"  Missing from persons table: {combined_stats['missing_in_persons_table']}")
        print(f"  Connected components: {combined_stats['connected_components']}")
        print(f"  Largest component: {combined_stats['largest_component']}")
        print(f"  Multi primary_rel pairs: {combined_stats['multi_primary_rel_pairs']}")
        if "not_in_main_component" in combined_stats:
            print(f"  NOT in main component: {combined_stats['not_in_main_component']} — {combined_stats['not_in_main_names']}")
        if "no_edge_persons" in combined_stats:
            print(f"  No-edge persons: {combined_stats['no_edge_persons']} — {combined_stats['no_edge_names']}")

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
