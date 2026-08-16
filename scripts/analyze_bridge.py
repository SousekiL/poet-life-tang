#!/usr/bin/env python3
"""
Analyze bridge figures in the Tang Dynasty social network.

Runs from the repository root directory. Uses relative paths for all data files.

Usage:
    cd /path/to/poet-life-tang
    python scripts/analyze_bridge.py
"""

import csv
import os
import sys
from collections import defaultdict

# Use relative paths from repo root
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Load Layer 1 edges (undirected pairs)
l1_edges = set()
l1_rels = []
with open(os.path.join(DATA_DIR, "relationships.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        s, t = int(r["source_id"]), int(r["target_id"])
        l1_edges.add((min(s, t), max(s, t)))
        l1_rels.append(r)

# Load core IDs and names
core_ids = set()
names = {}
with open(os.path.join(DATA_DIR, "persons.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        pid = int(r["c_personid"])
        core_ids.add(pid)
        names[pid] = r["name_chn"]

print(f"Core: {len(core_ids)}, Layer 1 edges: {len(l1_edges)}")

# Load Layer 2 raw
l2_rels = []
with open(os.path.join(DATA_DIR, "relationships_layer2.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        l2_rels.append(r)

periph_ids = set()
for r in l2_rels:
    s, t = int(r["source_id"]), int(r["target_id"])
    if s not in core_ids: periph_ids.add(s)
    if t not in core_ids: periph_ids.add(t)

# Build periph->core mapping
periph_core_map = defaultdict(set)
for r in l2_rels:
    s, t = int(r["source_id"]), int(r["target_id"])
    if s in periph_ids and t in core_ids:
        periph_core_map[s].add(t)
    if t in periph_ids and s in core_ids:
        periph_core_map[t].add(s)

# Stricter bridge filter: peripheral connects 2+ core figures that are NOT
# already directly connected in Layer 1
strict_bridge = {}
for pid, cores in periph_core_map.items():
    core_list = sorted(cores & core_ids)
    if len(core_list) < 2:
        continue
    has_new_connection = False
    for i in range(len(core_list)):
        for j in range(i + 1, len(core_list)):
            pair = (min(core_list[i], core_list[j]), max(core_list[i], core_list[j]))
            if pair not in l1_edges:
                has_new_connection = True
                break
        if has_new_connection:
            break
    if has_new_connection:
        strict_bridge[pid] = core_list

print(f"Strict bridge figures: {len(strict_bridge)}")

for pid in sorted(strict_bridge.keys())[:20]:
    cores = strict_bridge[pid]
    core_names = [names.get(c, str(c)) for c in cores]
    new_pairs = []
    for i in range(len(cores)):
        for j in range(i + 1, len(cores)):
            pair = (min(cores[i], cores[j]), max(cores[i], cores[j]))
            if pair not in l1_edges:
                new_pairs.append(f"{names.get(cores[i], '?')}<->{names.get(cores[j], '?')}")
    print(f"  {pid}: {core_names}, NEW: {new_pairs[:3]}")

# Also check: how many orphans resolved?
l1_connected = set()
for r in l1_rels:
    l1_connected.add(int(r["source_id"]))
    l1_connected.add(int(r["target_id"]))
orphans = core_ids - l1_connected
print(f"\nOrphan core figures (no L1 connections): {len(orphans)}")
print(f"  {[names[p] for p in orphans]}")

# Which orphans are resolved by strict bridge?
orphan_resolved = set()
for pid, cores in strict_bridge.items():
    for c in cores:
        if c in orphans:
            orphan_resolved.add(c)
print(f"Orphans resolved by strict bridge: {len(orphan_resolved)}")
print(f"  {[names[p] for p in orphan_resolved]}")
still_orphan = orphans - orphan_resolved
print(f"Still orphan: {len(still_orphan)}")
print(f"  {[names[p] for p in still_orphan]}")
