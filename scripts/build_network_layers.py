#!/usr/bin/env python3
"""
Build two-layer network data for Tang Dynasty social network.

Layer 1: Core figures (128 people) with primary relationship marking
Layer 2: k=1 bridge-figure expansion (filtered to prevent data explosion)

Bridge figure filter (tiered):
  Tier A: Must-resolve — peripheral figures connecting orphan core figures to the network
  Tier B: High-value bridges — peripheral figures connecting 3+ core figures AND creating
          at least one new path between non-adjacent core figures
  Tier C: Standard bridges — peripheral figures connecting 2+ core figures AND creating
          at least one new path between non-adjacent core figures

Relationship priority for primary_rel marking:
  KIN(1) > TEACHER_STUDENT(2) > COLLEAGUE(3) > LITERARY(4) > POLITICAL(5) > SOCIAL(6)
  Within same type, prefer higher weight.
"""

import csv
import sqlite3
import os
from collections import defaultdict

DB_PATH = os.environ.get("CBDB_PATH", "/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/cbdb202409.db")
PERSONS_CSV = "data/persons.csv"
RELATIONSHIPS_CSV = "data/relationships.csv"
REL_TYPES_CSV = "stage_outputs/relationship_types.csv"
OUTPUT_DIR = "data"

REL_PRIORITY = {
    "KIN": 1,
    "TEACHER_STUDENT": 2,
    "COLLEAGUE": 3,
    "LITERARY": 4,
    "POLITICAL": 5,
    "SOCIAL": 6,
}


def load_persons(path):
    persons = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            persons[int(r["c_personid"])] = r
    return persons


def load_relationships(path):
    rels = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rels.append(r)
    return rels


def parse_cbdb_codes(code_str):
    codes = set()
    for part in code_str.split(","):
        part = part.strip().strip('"')
        if "-" in part:
            lo, hi = part.split("-", 1)
            codes.update(range(int(lo), int(hi) + 1))
        else:
            codes.add(int(part))
    return codes


def build_code_mapping(rel_types_path):
    mapping = {}
    with open(rel_types_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["rel_type"] == "KIN":
                continue
            codes = parse_cbdb_codes(r["cbdb_assoc_codes"])
            for code in codes:
                mapping[code] = {
                    "rel_type": r["rel_type"],
                    "rel_subtype": r["rel_subtype_code"],
                    "direction": r["direction"],
                    "default_weight": float(r["default_weight"]),
                }
    return mapping


def build_kin_code_mapping(rel_types_path):
    mapping = {}
    with open(rel_types_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["rel_type"] != "KIN":
                continue
            codes = parse_cbdb_codes(r["cbdb_assoc_codes"])
            for code in codes:
                mapping[code] = {
                    "rel_type": r["rel_type"],
                    "rel_subtype": r["rel_subtype_code"],
                    "direction": r["direction"],
                    "default_weight": float(r["default_weight"]),
                }
    return mapping


def select_primary_rel(rels_for_pair):
    best = None
    best_priority = 999
    best_weight = -1
    for r in rels_for_pair:
        priority = REL_PRIORITY.get(r["rel_type"], 99)
        weight = float(r["weight"])
        if priority < best_priority or (priority == best_priority and weight > best_weight):
            best = r
            best_priority = priority
            best_weight = weight
    return best


def add_primary_rel_flag(rels):
    pair_rels = defaultdict(list)
    for r in rels:
        s, t = int(r["source_id"]), int(r["target_id"])
        key = (min(s, t), max(s, t))
        pair_rels[key].append(r)

    primary_set = set()
    for key, rs in pair_rels.items():
        primary = select_primary_rel(rs)
        if primary:
            primary_set.add(id(primary))

    result = []
    for r in rels:
        r_copy = dict(r)
        r_copy["primary_rel"] = 1 if id(r) in primary_set else 0
        result.append(r_copy)
    return result


def extract_all_peripheral_rels(conn, core_ids, code_mapping, kin_code_mapping):
    """Extract ALL relationships between core and peripheral figures from CBDB."""
    cursor = conn.cursor()
    core_set = set(core_ids)
    id_placeholders = ",".join("?" * len(core_ids))

    # ASSOC_DATA
    cursor.execute(f"""
        SELECT c_assoc_code, c_personid, c_assoc_id,
               c_assoc_year, c_assoc_nh_code, c_source, c_notes, c_text_title
        FROM ASSOC_DATA
        WHERE (c_personid IN ({id_placeholders}) OR c_assoc_id IN ({id_placeholders}))
          AND c_assoc_code NOT IN (-1, 0)
    """, core_ids + core_ids)
    assoc_rows = cursor.fetchall()

    # KIN_DATA
    cursor.execute(f"""
        SELECT c_personid, c_kin_id, c_kin_code, c_source, c_notes
        FROM KIN_DATA
        WHERE c_personid IN ({id_placeholders}) OR c_kin_id IN ({id_placeholders})
    """, core_ids + core_ids)
    kin_rows = cursor.fetchall()

    # Reference tables
    cursor.execute("SELECT c_assoc_code, c_assoc_desc_chn, c_assoc_desc, c_assoc_role_type FROM ASSOC_CODES")
    assoc_code_info = {r[0]: (r[1], r[2], r[3]) for r in cursor.fetchall()}

    cursor.execute("SELECT c_kincode, c_kinrel_chn, c_kinrel, c_kinrel_simplified FROM KINSHIP_CODES")
    kin_info = {r[0]: (r[1], r[2], r[3]) for r in cursor.fetchall()}

    cursor.execute("SELECT c_nianhao_id, c_firstyear, c_lastyear FROM NIAN_HAO")
    nh_lookup = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}

    cursor.execute("SELECT c_textid, c_title_chn, c_title FROM TEXT_CODES LIMIT 5000")
    text_lookup = {r[0]: (r[1] or r[2] or "") for r in cursor.fetchall()}

    # Track peripheral->core connections
    periph_core_map = defaultdict(set)
    raw_rels = []

    # Process ASSOC_DATA
    for row in assoc_rows:
        assoc_code, personid, assoc_id, assoc_year, nh_code, source, notes, text_title = row

        if personid in core_set and assoc_id in core_set:
            continue
        if personid not in core_set and assoc_id not in core_set:
            continue

        if personid in core_set:
            core_id, periph_id = personid, assoc_id
        else:
            core_id, periph_id = assoc_id, personid

        rel_info = code_mapping.get(assoc_code)
        if not rel_info:
            continue

        periph_core_map[periph_id].add(core_id)

        code_detail = assoc_code_info.get(assoc_code, (None, None, None))
        role_type = code_detail[2]
        rel_desc_chn = code_detail[0] or ""

        if role_type == "M" or rel_info["direction"] == "undirected":
            direction = "undirected"
            source_id, target_id = min(core_id, periph_id), max(core_id, periph_id)
        elif role_type == "A":
            direction = "directed"
            if personid in core_set:
                source_id, target_id = personid, assoc_id
            else:
                source_id, target_id = assoc_id, personid
        elif role_type == "P":
            direction = "directed"
            if personid in core_set:
                source_id, target_id = assoc_id, personid
            else:
                source_id, target_id = personid, assoc_id
        else:
            direction = rel_info["direction"]
            if direction == "undirected":
                source_id, target_id = min(core_id, periph_id), max(core_id, periph_id)
            else:
                source_id, target_id = core_id, periph_id

        year_start = None
        if assoc_year and assoc_year != 0:
            year_start = assoc_year
        elif nh_code and nh_code != 0:
            nh_info = nh_lookup.get(nh_code)
            if nh_info and nh_info[0]:
                year_start = nh_info[0]

        evidence = "primary" if source and source > 0 else "inferred"
        source_ref = ""
        if source and source > 0:
            source_ref = text_lookup.get(source, f"textid={source}")

        raw_rels.append({
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_info["rel_type"],
            "rel_subtype": rel_info["rel_subtype"],
            "rel_desc_chn": rel_desc_chn,
            "direction": direction,
            "year_start": year_start,
            "year_end": None,
            "weight": rel_info["default_weight"],
            "evidence_level": evidence,
            "source_ref": source_ref,
            "cbdb_assoc_code": assoc_code,
            "cbdb_role_type": role_type or "",
            "core_id": core_id,
            "periph_id": periph_id,
        })

    # Process KIN_DATA
    for row in kin_rows:
        personid, kin_id, kin_code, source, notes = row

        if personid in core_set and kin_id in core_set:
            continue
        if personid not in core_set and kin_id not in core_set:
            continue

        if personid in core_set:
            core_id, periph_id = personid, kin_id
        else:
            core_id, periph_id = kin_id, personid

        rel_info = kin_code_mapping.get(kin_code)
        if not rel_info:
            kin_detail = kin_info.get(kin_code)
            if kin_detail:
                rel_info = {
                    "rel_type": "KIN",
                    "rel_subtype": "K_OTHER",
                    "direction": "directed",
                    "default_weight": 0.7,
                }
            else:
                continue

        periph_core_map[periph_id].add(core_id)

        direction = rel_info["direction"]
        if direction == "undirected":
            source_id, target_id = min(personid, kin_id), max(personid, kin_id)
        else:
            source_id, target_id = personid, kin_id

        evidence = "primary" if source and source > 0 else "inferred"
        source_ref = ""
        if source and source > 0:
            source_ref = text_lookup.get(source, f"textid={source}")

        kin_detail = kin_info.get(kin_code, ("", "", ""))

        raw_rels.append({
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_info["rel_type"],
            "rel_subtype": rel_info["rel_subtype"],
            "rel_desc_chn": kin_detail[0] or "",
            "direction": direction,
            "year_start": None,
            "year_end": None,
            "weight": rel_info["default_weight"],
            "evidence_level": evidence,
            "source_ref": source_ref,
            "cbdb_assoc_code": kin_code,
            "cbdb_role_type": "KIN",
            "core_id": core_id,
            "periph_id": periph_id,
        })

    return raw_rels, periph_core_map


def filter_bridge_figures(raw_rels, periph_core_map, core_ids, l1_edges, orphan_core_ids):
    """
    Tiered bridge figure filter:
    Tier A: connects to an orphan core figure (must-include)
    Tier B: connects 3+ core figures with at least one new path
    Tier C: connects 2+ core figures with at least one new path

    Returns: set of bridge peripheral IDs, and their tier labels.
    """
    core_set = set(core_ids)
    bridge_tiers = {}

    for pid, cores in periph_core_map.items():
        connected_cores = sorted(cores & core_set)
        if len(connected_cores) < 2:
            # Tier A exception: single core connection to orphan
            if connected_cores and connected_cores[0] in orphan_core_ids:
                bridge_tiers[pid] = "A"
            continue

        # Check if any pair of connected cores are NOT directly connected in L1
        has_new_path = False
        for i in range(len(connected_cores)):
            for j in range(i + 1, len(connected_cores)):
                pair = (min(connected_cores[i], connected_cores[j]),
                        max(connected_cores[i], connected_cores[j]))
                if pair not in l1_edges:
                    has_new_path = True
                    break
            if has_new_path:
                break

        if not has_new_path:
            continue

        if len(connected_cores) >= 3:
            bridge_tiers[pid] = "B"
        else:
            bridge_tiers[pid] = "C"

    return bridge_tiers


def get_bridge_persons_data(conn, bridge_ids):
    """Fetch BIOG_MAIN data for bridge figures."""
    cursor = conn.cursor()
    if not bridge_ids:
        return {}

    bp_placeholders = ",".join("?" * len(bridge_ids))
    cursor.execute(f"""
        SELECT c_personid, c_name, c_name_chn, c_surname_chn, c_mingzi_chn,
               c_birthyear, c_deathyear, c_female, c_dy,
               c_fl_earliest_year, c_fl_latest_year
        FROM BIOG_MAIN
        WHERE c_personid IN ({bp_placeholders})
    """, list(bridge_ids))
    biog_rows = cursor.fetchall()

    cursor.execute("SELECT c_dy, c_dynasty, c_dynasty_chn FROM DYNASTIES")
    dynasties = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}

    persons = {}
    for row in biog_rows:
        pid, name_rm, name_chn, surname_chn, given_name_chn, birthyear, deathyear, female, dy, fl_e, fl_l = row
        dy_info = dynasties.get(dy, ("unknown", "未知"))
        persons[pid] = {
            "c_personid": pid,
            "name_chn": name_chn or "",
            "name_rm": name_rm or "",
            "surname_chn": surname_chn or "",
            "given_name_chn": given_name_chn or "",
            "birthyear": birthyear if birthyear and birthyear != 0 else None,
            "deathyear": deathyear if deathyear and deathyear != 0 else None,
            "is_female": 1 if female else 0,
            "dynasty_code": dy,
            "dynasty_chn": dy_info[1],
            "dynasty_en": dy_info[0],
            "role": "bridge",
        }
    return persons


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Loading existing data ===")
    persons = load_persons(PERSONS_CSV)
    rels = load_relationships(RELATIONSHIPS_CSV)
    core_ids = list(persons.keys())
    core_set = set(core_ids)
    print(f"  Core figures: {len(core_ids)}")
    print(f"  Existing relationships: {len(rels)}")

    # Build L1 edge set (undirected)
    l1_edges = set()
    l1_connected = set()
    for r in rels:
        s, t = int(r["source_id"]), int(r["target_id"])
        l1_edges.add((min(s, t), max(s, t)))
        l1_connected.add(s)
        l1_connected.add(t)
    orphan_core_ids = core_set - l1_connected
    print(f"  L1 unique edges: {len(l1_edges)}")
    print(f"  Orphan core figures: {len(orphan_core_ids)} -> {[persons[p]['name_chn'] for p in orphan_core_ids]}")

    # === LAYER 1: Add primary_rel flag ===
    print("\n=== Building Layer 1 ===")
    layer1_rels = add_primary_rel_flag(rels)
    primary_count = sum(1 for r in layer1_rels if r["primary_rel"] == 1)
    print(f"  Total: {len(layer1_rels)}, Primary: {primary_count}")

    primary_by_type = defaultdict(int)
    for r in layer1_rels:
        if r["primary_rel"] == 1:
            primary_by_type[r["rel_type"]] += 1
    for rt in sorted(primary_by_type.keys()):
        print(f"    {rt}: {primary_by_type[rt]}")

    # Write Layer 1
    l1_fields = [
        "source_id", "target_id", "rel_type", "rel_subtype", "rel_desc_chn",
        "direction", "year_start", "year_end", "weight", "evidence_level",
        "source_ref", "cbdb_assoc_code", "cbdb_role_type", "primary_rel"
    ]
    l1_path = os.path.join(OUTPUT_DIR, "relationships_layer1.csv")
    with open(l1_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=l1_fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(layer1_rels, key=lambda x: (int(x["source_id"]), int(x["target_id"]))):
            writer.writerow(r)
    print(f"  Wrote {l1_path}")

    # === LAYER 2: Bridge-figure expansion ===
    print("\n=== Building Layer 2 ===")
    code_mapping = build_code_mapping(REL_TYPES_CSV)
    kin_code_mapping = build_kin_code_mapping(REL_TYPES_CSV)

    conn = sqlite3.connect(DB_PATH)

    print("  Extracting all peripheral relationships from CBDB...")
    raw_rels, periph_core_map = extract_all_peripheral_rels(conn, core_ids, code_mapping, kin_code_mapping)
    print(f"  Raw peripheral relationships: {len(raw_rels)}")
    print(f"  Peripheral figures with core connections: {len(periph_core_map)}")

    print("  Applying tiered bridge filter...")
    bridge_tiers = filter_bridge_figures(raw_rels, periph_core_map, core_ids, l1_edges, orphan_core_ids)
    print(f"  Bridge figures by tier:")
    tier_counts = defaultdict(int)
    for pid, tier in bridge_tiers.items():
        tier_counts[tier] += 1
    for t in sorted(tier_counts.keys()):
        print(f"    Tier {t}: {tier_counts[t]}")

    bridge_ids = set(bridge_tiers.keys())

    # Fetch bridge figure BIOG_MAIN data
    print("  Fetching bridge figure biographical data...")
    bridge_persons = get_bridge_persons_data(conn, bridge_ids)
    # Add tier info
    for pid, p in bridge_persons.items():
        p["bridge_tier"] = bridge_tiers.get(pid, "C")
    print(f"  Bridge persons loaded: {len(bridge_persons)}")

    conn.close()

    # Filter raw_rels to only bridge figures, deduplicate
    seen = set()
    bridge_rels = []
    for r in raw_rels:
        s, t = r["source_id"], r["target_id"]
        periph_id = r["periph_id"]
        if periph_id not in bridge_ids:
            continue
        edge_key = (s, t, r["rel_type"], r["rel_subtype"])
        if edge_key not in seen:
            seen.add(edge_key)
            rel_out = {k: v for k, v in r.items() if k not in ("core_id", "periph_id")}
            rel_out["is_bridge"] = 1
            bridge_rels.append(rel_out)

    # Add primary_rel flag
    bridge_rels_flagged = add_primary_rel_flag(bridge_rels)

    print(f"  Bridge relationships (deduplicated): {len(bridge_rels_flagged)}")
    primary_bridge = sum(1 for r in bridge_rels_flagged if r["primary_rel"] == 1)
    print(f"  Primary bridge relationships: {primary_bridge}")

    # Write Layer 2 relationships
    l2_fields = [
        "source_id", "target_id", "rel_type", "rel_subtype", "rel_desc_chn",
        "direction", "year_start", "year_end", "weight", "evidence_level",
        "source_ref", "cbdb_assoc_code", "cbdb_role_type", "primary_rel", "is_bridge"
    ]
    l2_rel_path = os.path.join(OUTPUT_DIR, "relationships_layer2.csv")
    with open(l2_rel_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=l2_fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(bridge_rels_flagged, key=lambda x: (int(x["source_id"]), int(x["target_id"]))):
            writer.writerow(r)
    print(f"  Wrote {l2_rel_path}")

    # Write Layer 2 persons
    l2_person_fields = [
        "c_personid", "name_chn", "name_rm", "surname_chn", "given_name_chn",
        "birthyear", "deathyear", "is_female", "dynasty_code", "dynasty_chn",
        "dynasty_en", "role", "bridge_tier"
    ]
    l2_person_path = os.path.join(OUTPUT_DIR, "persons_layer2.csv")
    with open(l2_person_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=l2_person_fields, extrasaction="ignore")
        writer.writeheader()
        for p in sorted(bridge_persons.values(), key=lambda x: x["c_personid"]):
            writer.writerow(p)
    print(f"  Wrote {l2_person_path}")

    # === Combined dataset ===
    print("\n=== Building combined dataset ===")
    combined_persons = dict(persons)
    for pid, p in bridge_persons.items():
        if pid not in combined_persons:
            combined_persons[pid] = p

    combined_rels = layer1_rels + bridge_rels_flagged

    # Write combined persons
    combined_person_path = os.path.join(OUTPUT_DIR, "persons_combined.csv")
    with open(combined_person_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "c_personid", "name_chn", "name_rm", "surname_chn", "given_name_chn",
            "birthyear", "deathyear", "is_female", "dynasty_code", "dynasty_chn",
            "dynasty_en", "role", "bridge_tier"
        ], extrasaction="ignore")
        writer.writeheader()
        for p in sorted(combined_persons.values(), key=lambda x: int(x["c_personid"])):
            row = dict(p)
            if "role" not in row:
                row["role"] = "core"
            if "bridge_tier" not in row:
                row["bridge_tier"] = ""
            writer.writerow(row)
    print(f"  Wrote {combined_person_path}")

    # Write combined relationships
    combined_rel_path = os.path.join(OUTPUT_DIR, "relationships_combined.csv")
    with open(combined_rel_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source_id", "target_id", "rel_type", "rel_subtype", "rel_desc_chn",
            "direction", "year_start", "year_end", "weight", "evidence_level",
            "source_ref", "cbdb_assoc_code", "cbdb_role_type", "primary_rel", "is_bridge"
        ], extrasaction="ignore")
        writer.writeheader()
        for r in sorted(combined_rels, key=lambda x: (int(x["source_id"]), int(x["target_id"]))):
            row = dict(r)
            if "is_bridge" not in row:
                row["is_bridge"] = 0
            writer.writerow(row)
    print(f"  Wrote {combined_rel_path}")

    # === Final stats ===
    print("\n=== Final Statistics ===")
    print(f"Layer 1: {len(persons)} core figures, {len(layer1_rels)} relationships ({primary_count} primary)")
    print(f"Layer 2: {len(bridge_persons)} bridge figures, {len(bridge_rels_flagged)} relationships ({primary_bridge} primary)")
    print(f"Combined: {len(combined_persons)} persons, {len(combined_rels)} relationships")

    # Check remaining orphans
    l2_connected = set()
    for r in combined_rels:
        l2_connected.add(int(r["source_id"]))
        l2_connected.add(int(r["target_id"]))
    remaining_orphans = set(combined_persons.keys()) - l2_connected
    if remaining_orphans:
        orphan_names = [combined_persons[p]["name_chn"] for p in remaining_orphans]
        print(f"Remaining orphans: {len(remaining_orphans)} - {orphan_names}")
    else:
        print("No remaining orphans!")

    print("\nDone!")


if __name__ == "__main__":
    main()
