#!/usr/bin/env python3
"""
Build two-layer network data for Tang Dynasty social network.

Layer 1: Core figures with primary relationship marking + evidence aggregation
Layer 2: k=1 bridge-figure expansion (filtered to prevent data explosion)

Bridge figure filter (strict):
  - All bridge figures must connect 2+ core figures that are NOT already
    directly connected in Layer 1.
  - No single-core dead-end exception. Orphan core figures that cannot be
    bridged to the main component remain documented as unresolved.
  - Tier B: connects 3+ core figures with at least one new path
  - Tier C: connects 2+ core figures with at least one new path

Relationship priority for primary_rel marking:
  KIN(1) > TEACHER_STUDENT(2) > COLLEAGUE(3) > LITERARY(4) > POLITICAL(5) > SOCIAL(6)
  Within same type, prefer higher weight.

Evidence aggregation:
  When multiple CBDB records map to the same network edge (same source_id, target_id,
  rel_type, rel_subtype), they are aggregated into a single row with:
    - evidence_count: number of original records
    - evidence_list: JSON array of provenance entries (source_table, c_source, c_pages,
      c_sequence, c_text_title, orig_personid, orig_assoc_id)
  The best evidence_level is chosen: primary > unsourced.
"""

import argparse
import csv
import json
import os
import sqlite3
from collections import defaultdict

DEFAULT_DB_PATH = "/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/cbdb202409.db"
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


def parse_args():
    parser = argparse.ArgumentParser(description="Build Tang Dynasty network layers")
    parser.add_argument("--db", default=os.environ.get("CBDB_PATH", DEFAULT_DB_PATH),
                        help="Path to CBDB SQLite database")
    return parser.parse_args()


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


def aggregate_relationships(rels):
    """Aggregate raw records by (source_id, target_id, rel_type, rel_subtype).

    Returns deduplicated list with evidence_count and evidence_list.
    """
    groups = defaultdict(list)
    for r in rels:
        key = (int(r["source_id"]), int(r["target_id"]), r["rel_type"], r["rel_subtype"])
        groups[key].append(r)

    aggregated = []
    for key, records in groups.items():
        # Choose best evidence_level: primary > unsourced
        has_primary = any(r["evidence_level"] == "primary" for r in records)
        best_evidence = "primary" if has_primary else "unsourced"

        # Choose best primary record (with source_ref if available, else first)
        best_record = None
        for r in records:
            if r["evidence_level"] == "primary" and r.get("source_ref"):
                best_record = r
                break
        if best_record is None:
            best_record = records[0]

        # Build evidence list for provenance
        evidence_entries = []
        for r in records:
            entry = {
                "source_table": r.get("source_table", ""),
                "c_source": r.get("c_source", ""),
                "c_pages": r.get("c_pages", ""),
                "c_sequence": r.get("c_sequence", ""),
                "c_text_title": r.get("c_text_title", ""),
                "orig_personid": r.get("orig_personid", ""),
                "orig_assoc_id": r.get("orig_assoc_id", ""),
                "cbdb_assoc_code": r.get("cbdb_assoc_code", ""),
            }
            evidence_entries.append(entry)

        # Build aggregated row
        agg = {
            "source_id": key[0],
            "target_id": key[1],
            "rel_type": key[2],
            "rel_subtype": key[3],
            "rel_desc_chn": best_record.get("rel_desc_chn", ""),
            "direction": best_record.get("direction", ""),
            "year_start": best_record.get("year_start", ""),
            "year_end": best_record.get("year_end", ""),
            "weight": best_record.get("weight", ""),
            "evidence_level": best_evidence,
            "source_ref": best_record.get("source_ref", ""),
            "cbdb_assoc_code": best_record.get("cbdb_assoc_code", ""),
            "cbdb_role_type": best_record.get("cbdb_role_type", ""),
            "evidence_count": len(records),
            "evidence_list": json.dumps(evidence_entries, ensure_ascii=False),
        }
        aggregated.append(agg)

    return aggregated


def select_primary_rel(rels_for_pair):
    best = None
    best_priority = 999
    best_weight = -1
    for r in rels_for_pair:
        priority = REL_PRIORITY.get(r["rel_type"], 99)
        weight = float(r["weight"]) if r.get("weight") else 0
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

    # ASSOC_DATA — fetch full provenance fields
    cursor.execute(f"""
        SELECT c_assoc_code, c_personid, c_assoc_id,
               c_assoc_year, c_assoc_nh_code, c_source, c_pages, c_notes,
               c_text_title, c_sequence
        FROM ASSOC_DATA
        WHERE (c_personid IN ({id_placeholders}) OR c_assoc_id IN ({id_placeholders}))
          AND c_assoc_code NOT IN (-1, 0)
    """, core_ids + core_ids)
    assoc_rows = cursor.fetchall()

    # KIN_DATA — fetch c_pages too
    cursor.execute(f"""
        SELECT c_personid, c_kin_id, c_kin_code, c_source, c_pages, c_notes
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

    # Full TEXT_CODES load (no LIMIT)
    cursor.execute("SELECT c_textid, c_title_chn, c_title FROM TEXT_CODES")
    text_lookup = {r[0]: (r[1] or r[2] or "") for r in cursor.fetchall()}

    periph_core_map = defaultdict(set)
    raw_rels = []

    # Process ASSOC_DATA
    for row in assoc_rows:
        assoc_code, personid, assoc_id, assoc_year, nh_code, source, pages, notes, text_title, sequence = row

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

        # Evidence: primary if has source, unsourced otherwise
        c_source_val = source if source and source > 0 else None
        evidence = "primary" if c_source_val is not None else "unsourced"

        source_ref = ""
        if c_source_val is not None:
            source_ref = text_lookup.get(c_source_val, f"textid={c_source_val}")

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
            "source_table": "ASSOC_DATA",
            "c_source": c_source_val if c_source_val is not None else "",
            "c_pages": pages or "",
            "c_sequence": sequence if sequence is not None else "",
            "c_text_title": text_title or "",
            "orig_personid": personid,
            "orig_assoc_id": assoc_id,
            "core_id": core_id,
            "periph_id": periph_id,
        })

    # Process KIN_DATA
    for row in kin_rows:
        personid, kin_id, kin_code, source, pages, notes = row

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

        c_source_val = source if source and source > 0 else None
        evidence = "primary" if c_source_val is not None else "unsourced"

        source_ref = ""
        if c_source_val is not None:
            source_ref = text_lookup.get(c_source_val, f"textid={c_source_val}")

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
            "source_table": "KIN_DATA",
            "c_source": c_source_val if c_source_val is not None else "",
            "c_pages": pages or "",
            "c_sequence": "",
            "c_text_title": "",
            "orig_personid": personid,
            "orig_assoc_id": kin_id,
            "core_id": core_id,
            "periph_id": periph_id,
        })

    return raw_rels, periph_core_map


def filter_bridge_figures(raw_rels, periph_core_map, core_ids, l1_edges, orphan_core_ids):
    """Strict bridge figure filter.

    All bridge figures must connect 2+ core figures with at least one new path.
    No Tier A single-core exception.

    Returns: dict of bridge_id -> tier label.
    """
    core_set = set(core_ids)
    bridge_tiers = {}

    for pid, cores in periph_core_map.items():
        connected_cores = sorted(cores & core_set)
        if len(connected_cores) < 2:
            # Strict: no single-core exception. Skip dead-end nodes.
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
    args = parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Loading existing data ===")
    persons = load_persons(PERSONS_CSV)
    raw_rels = load_relationships(RELATIONSHIPS_CSV)
    core_ids = list(persons.keys())
    core_set = set(core_ids)
    print(f"  Core figures: {len(core_ids)}")
    print(f"  Raw relationship records: {len(raw_rels)}")

    # Aggregate raw records into unique edges with evidence_list
    print("\n=== Aggregating Layer 1 relationships ===")
    aggregated_rels = aggregate_relationships(raw_rels)
    print(f"  Aggregated edges: {len(aggregated_rels)}")

    # Build L1 edge set (undirected) for bridge filtering
    l1_edges = set()
    l1_connected = set()
    for r in aggregated_rels:
        s, t = int(r["source_id"]), int(r["target_id"])
        l1_edges.add((min(s, t), max(s, t)))
        l1_connected.add(s)
        l1_connected.add(t)
    orphan_core_ids = core_set - l1_connected
    orphan_names = [persons[p]["name_chn"] for p in orphan_core_ids]
    print(f"  L1 unique edges: {len(l1_edges)}")
    print(f"  Orphan core figures: {len(orphan_core_ids)} -> {orphan_names}")

    # Add primary_rel flag
    layer1_rels = add_primary_rel_flag(aggregated_rels)
    primary_count = sum(1 for r in layer1_rels if r["primary_rel"] == 1)
    print(f"  Primary relationships: {primary_count}/{len(layer1_rels)}")

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
        "source_ref", "cbdb_assoc_code", "cbdb_role_type",
        "evidence_count", "evidence_list", "primary_rel"
    ]
    l1_path = os.path.join(OUTPUT_DIR, "relationships_layer1.csv")
    with open(l1_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=l1_fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(layer1_rels, key=lambda x: (int(x["source_id"]), int(x["target_id"]))):
            writer.writerow(r)
    print(f"  Wrote {l1_path} ({len(layer1_rels)} rows)")

    # === LAYER 2: Bridge-figure expansion ===
    print("\n=== Building Layer 2 ===")
    code_mapping = build_code_mapping(REL_TYPES_CSV)
    kin_code_mapping = build_kin_code_mapping(REL_TYPES_CSV)

    conn = sqlite3.connect(args.db)

    print("  Extracting all peripheral relationships from CBDB...")
    raw_periph_rels, periph_core_map = extract_all_peripheral_rels(conn, core_ids, code_mapping, kin_code_mapping)
    print(f"  Raw peripheral records: {len(raw_periph_rels)}")
    print(f"  Peripheral figures with core connections: {len(periph_core_map)}")

    print("  Applying strict bridge filter (2+ core, new path, no single-core exception)...")
    bridge_tiers = filter_bridge_figures(raw_periph_rels, periph_core_map, core_ids, l1_edges, orphan_core_ids)
    print(f"  Bridge figures: {len(bridge_tiers)}")
    tier_counts = defaultdict(int)
    for pid, tier in bridge_tiers.items():
        tier_counts[tier] += 1
    for t in sorted(tier_counts.keys()):
        print(f"    Tier {t}: {tier_counts[t]}")

    bridge_ids = set(bridge_tiers.keys())

    # Fetch bridge figure BIOG_MAIN data
    print("  Fetching bridge figure biographical data...")
    bridge_persons = get_bridge_persons_data(conn, bridge_ids)
    for pid, p in bridge_persons.items():
        p["bridge_tier"] = bridge_tiers.get(pid, "C")
    print(f"  Bridge persons loaded: {len(bridge_persons)}")

    conn.close()

    # Filter raw_periph_rels to only bridge figures, aggregate
    bridge_raw = []
    for r in raw_periph_rels:
        periph_id = r["periph_id"]
        if periph_id not in bridge_ids:
            continue
        bridge_raw.append(r)

    print(f"  Bridge raw records: {len(bridge_raw)}")
    bridge_aggregated = aggregate_relationships(bridge_raw)
    print(f"  Bridge aggregated edges: {len(bridge_aggregated)}")

    # Add primary_rel flag
    bridge_rels_flagged = add_primary_rel_flag(bridge_aggregated)

    primary_bridge = sum(1 for r in bridge_rels_flagged if r["primary_rel"] == 1)
    print(f"  Primary bridge relationships: {primary_bridge}")

    # Write Layer 2 relationships
    l2_fields = [
        "source_id", "target_id", "rel_type", "rel_subtype", "rel_desc_chn",
        "direction", "year_start", "year_end", "weight", "evidence_level",
        "source_ref", "cbdb_assoc_code", "cbdb_role_type",
        "evidence_count", "evidence_list", "primary_rel", "is_bridge"
    ]
    l2_rel_path = os.path.join(OUTPUT_DIR, "relationships_layer2.csv")
    with open(l2_rel_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=l2_fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(bridge_rels_flagged, key=lambda x: (int(x["source_id"]), int(x["target_id"]))):
            writer.writerow(r)
    print(f"  Wrote {l2_rel_path} ({len(bridge_rels_flagged)} rows)")

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
    print(f"  Wrote {l2_person_path} ({len(bridge_persons)} rows)")

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
    print(f"  Wrote {combined_person_path} ({len(combined_persons)} rows)")

    # Write combined relationships
    combined_rel_path = os.path.join(OUTPUT_DIR, "relationships_combined.csv")
    with open(combined_rel_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source_id", "target_id", "rel_type", "rel_subtype", "rel_desc_chn",
            "direction", "year_start", "year_end", "weight", "evidence_level",
            "source_ref", "cbdb_assoc_code", "cbdb_role_type",
            "evidence_count", "evidence_list", "primary_rel", "is_bridge"
        ], extrasaction="ignore")
        writer.writeheader()
        for r in sorted(combined_rels, key=lambda x: (int(x["source_id"]), int(x["target_id"]))):
            row = dict(r)
            if "is_bridge" not in row:
                row["is_bridge"] = 0
            if "evidence_count" not in row:
                row["evidence_count"] = 1
            if "evidence_list" not in row:
                row["evidence_list"] = "[]"
            writer.writerow(row)
    print(f"  Wrote {combined_rel_path} ({len(combined_rels)} rows)")

    # === Connectivity analysis ===
    print("\n=== Connectivity Analysis ===")
    from collections import deque

    # Build adjacency from combined
    adj = defaultdict(set)
    for r in combined_rels:
        s, t = int(r["source_id"]), int(r["target_id"])
        adj[s].add(t)
        adj[t].add(s)

    # Find connected components
    all_nodes = set(combined_persons.keys())
    visited = set()
    components = []
    for n in sorted(all_nodes):
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
    print(f"  Total persons: {len(all_nodes)}")
    print(f"  Persons in network (with edges): {len(all_nodes - (all_nodes - set().union(*[c for c in components])))}")
    print(f"  Connected components: {len(components)}")
    for i, comp in enumerate(components[:5]):
        comp_names = [combined_persons[p]["name_chn"] for p in comp if p in combined_persons]
        print(f"    Component {i+1}: {len(comp)} persons — e.g. {comp_names[:5]}")

    # Report persons NOT in the largest component
    if len(components) > 1:
        main_component = components[0]
        core_in_main = sum(1 for p in main_component if p in core_set)
        print(f"\n  Main component: {len(main_component)} persons ({core_in_main} core)")
        not_in_main = all_nodes - main_component
        not_in_main_names = [combined_persons[p]["name_chn"] for p in not_in_main]
        print(f"  NOT in main component: {len(not_in_main)} persons: {not_in_main_names}")

        # Specifically report orphan core figures
        orphan_in_main = orphan_core_ids & main_component
        orphan_not_in_main = orphan_core_ids - main_component
        if orphan_in_main:
            print(f"  Orphan core figures now in main component: {[persons[p]['name_chn'] for p in orphan_in_main]}")
        if orphan_not_in_main:
            print(f"  Orphan core figures still NOT in main component: {[persons[p]['name_chn'] for p in orphan_not_in_main]}")

    # Persons with no edges at all
    no_edges = all_nodes - set(adj.keys())
    if no_edges:
        no_edge_names = [combined_persons[p]["name_chn"] for p in no_edges]
        print(f"  Persons with no edges at all: {len(no_edges)}: {no_edge_names}")

    # === Final stats ===
    print("\n=== Final Statistics ===")
    print(f"Layer 1: {len(persons)} core figures, {len(layer1_rels)} aggregated edges ({primary_count} primary)")
    print(f"Layer 2: {len(bridge_persons)} bridge figures, {len(bridge_rels_flagged)} aggregated edges ({primary_bridge} primary)")
    print(f"Combined: {len(combined_persons)} persons, {len(combined_rels)} aggregated edges")

    print("\nDone!")


if __name__ == "__main__":
    main()
