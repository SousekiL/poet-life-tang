#!/usr/bin/env python3
"""
Extract person and relationship data for the Tang Dynasty social network project.

Input:
  - stage_outputs/tang_figures_v2.csv: 129 figures selected in Stage 1
  - stage_outputs/relationship_types.csv: 59 relationship subtypes defined in Stage 2
  - CBDB database (configurable via --db or CBDB_PATH env var)

Output:
  - data/persons.csv: person table (129 rows)
  - data/relationships.csv: raw relationship table (no dedup; full provenance)
  - data/quality_report.md: quality check report

Changes from prior version:
  - Evidence semantics: 'primary' (c_source > 0) or 'unsourced' (record exists but c_source is NULL/0).
    No 'inferred' label — all records here come from direct CBDB ASSOC_DATA / KIN_DATA rows.
  - Full provenance: each row carries c_source, c_pages, c_sequence, c_text_title, source_table.
  - No deduplication at extraction: all raw CBDB records are preserved.
    Aggregation with evidence_list happens in build_network_layers.py.
  - TEXT_CODES loaded in full (no LIMIT 5000).
  - DB_PATH configurable via --db argument or CBDB_PATH env var.
"""

import argparse
import csv
import json
import os
import sqlite3
from collections import defaultdict

DEFAULT_DB_PATH = "/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/cbdb202409.db"
FIGURES_CSV = "stage_outputs/tang_figures_v2.csv"
REL_TYPES_CSV = "stage_outputs/relationship_types.csv"
OUTPUT_DIR = "data"


def parse_args():
    parser = argparse.ArgumentParser(description="Extract Tang Dynasty person/relationship data from CBDB")
    parser.add_argument("--db", default=os.environ.get("CBDB_PATH", DEFAULT_DB_PATH),
                        help="Path to CBDB SQLite database")
    return parser.parse_args()


def load_figures(path):
    """Load the figure list."""
    figures = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            figures.append(row)
    return figures


def load_rel_types(path):
    """Load relationship type definitions."""
    types = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            types.append(row)
    return types


def parse_cbdb_codes(code_str):
    """Parse CBDB code string like '75,82,98,107' or '180,182-186,188' into a set of ints."""
    codes = set()
    for part in code_str.split(","):
        part = part.strip().strip('"')
        if "-" in part:
            lo, hi = part.split("-", 1)
            codes.update(range(int(lo), int(hi) + 1))
        else:
            codes.add(int(part))
    return codes


def build_code_to_reltype(rel_types):
    """Build a mapping from CBDB c_assoc_code -> (rel_type, rel_subtype, direction, default_weight)."""
    mapping = {}
    for rt in rel_types:
        if rt["rel_type"] == "KIN":
            continue
        codes = parse_cbdb_codes(rt["cbdb_assoc_codes"])
        for code in codes:
            mapping[code] = {
                "rel_type": rt["rel_type"],
                "rel_subtype": rt["rel_subtype_code"],
                "direction": rt["direction"],
                "default_weight": float(rt["default_weight"]),
            }
    return mapping


def build_kin_code_to_reltype(rel_types):
    """Build a mapping from KINSHIP c_kin_code -> (rel_type, rel_subtype, direction, default_weight)."""
    mapping = {}
    for rt in rel_types:
        if rt["rel_type"] != "KIN":
            continue
        codes = parse_cbdb_codes(rt["cbdb_assoc_codes"])
        for code in codes:
            mapping[code] = {
                "rel_type": rt["rel_type"],
                "rel_subtype": rt["rel_subtype_code"],
                "direction": rt["direction"],
                "default_weight": float(rt["default_weight"]),
            }
    return mapping


def extract_persons(conn, person_ids):
    """Extract person data from BIOG_MAIN + ALTNAME_DATA."""
    cursor = conn.cursor()
    id_placeholders = ",".join("?" * len(person_ids))

    cursor.execute(f"""
        SELECT c_personid, c_name, c_name_chn, c_surname, c_surname_chn,
               c_mingzi, c_mingzi_chn, c_surname_proper, c_mingzi_proper,
               c_name_proper, c_surname_rm, c_mingzi_rm, c_name_rm,
               c_birthyear, c_deathyear, c_female, c_dy,
               c_index_year, c_index_year_type_code,
               c_fl_earliest_year, c_fl_latest_year,
               c_ethnicity_code, c_choronym_code, c_notes
        FROM BIOG_MAIN
        WHERE c_personid IN ({id_placeholders})
    """, person_ids)
    biog_rows = cursor.fetchall()

    cursor.execute("SELECT c_dy, c_dynasty, c_dynasty_chn FROM DYNASTIES")
    dynasties = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    cursor.execute(f"""
        SELECT a.c_personid, a.c_alt_name_chn, a.c_alt_name, a.c_alt_name_type_code,
               t.c_name_type_desc_chn
        FROM ALTNAME_DATA a
        LEFT JOIN ALTNAME_CODES t ON a.c_alt_name_type_code = t.c_name_type_code
        WHERE a.c_personid IN ({id_placeholders})
        ORDER BY a.c_personid, a.c_alt_name_type_code, a.c_sequence
    """, person_ids)
    altname_rows = cursor.fetchall()

    aliases_by_person = defaultdict(list)
    for row in altname_rows:
        pid = row[0]
        name_chn = row[1]
        name_rm = row[2] if row[2] and row[2].strip() else ""
        type_desc = row[4] if row[4] else f"type_{row[3]}"
        aliases_by_person[pid].append((name_chn, name_rm, type_desc))

    persons = []
    for row in biog_rows:
        (pid, name_rm, name_chn, surname_rm, surname_chn,
         mingzi_rm, mingzi_chn, surname_proper, mingzi_proper,
         name_proper, surname_rm2, mingzi_rm2, name_rm2,
         birthyear, deathyear, female, dy,
         index_year, index_year_type,
         fl_earliest, fl_latest,
         ethnicity, choronym, notes) = row

        std_name_chn = name_proper if name_proper and name_proper.strip() else (name_chn if name_chn and name_chn.strip() else "")
        std_name_rm = name_rm2 if name_rm2 and name_rm2.strip() else (name_rm if name_rm and name_rm.strip() else "")

        dy_info = dynasties.get(dy, ("unknown", "未知"))
        dynasty_en, dynasty_chn = dy_info

        by = birthyear if birthyear and birthyear != 0 else None
        dy_yr = deathyear if deathyear and deathyear != 0 else None
        fl_e = fl_earliest if fl_earliest and fl_earliest != 0 else None
        fl_l = fl_latest if fl_latest and fl_latest != 0 else None

        alts = aliases_by_person.get(pid, [])
        alias_str = "; ".join(f"{a[0]}({a[2]})" for a in alts) if alts else ""

        persons.append({
            "c_personid": pid,
            "name_chn": std_name_chn,
            "name_rm": std_name_rm,
            "surname_chn": surname_chn if surname_chn and surname_chn.strip() else "",
            "given_name_chn": mingzi_chn if mingzi_chn and mingzi_chn.strip() else "",
            "birthyear": by,
            "deathyear": dy_yr,
            "fl_earliest_year": fl_e,
            "fl_latest_year": fl_l,
            "is_female": 1 if female else 0,
            "dynasty_code": dy,
            "dynasty_chn": dynasty_chn,
            "dynasty_en": dynasty_en,
            "aliases": alias_str,
        })

    return persons


def extract_assoc_relationships(conn, person_ids, code_mapping):
    """Extract ASSOC_DATA relationships between people in the person list.

    No deduplication: all raw records are preserved for provenance.
    """
    cursor = conn.cursor()
    id_set = set(person_ids)
    id_placeholders = ",".join("?" * len(person_ids))

    cursor.execute(f"""
        SELECT c_assoc_code, c_personid, c_assoc_id,
               c_assoc_year, c_assoc_nh_code, c_assoc_nh_year, c_assoc_range,
               c_source, c_pages, c_notes, c_text_title,
               c_addr_id, c_sequence
        FROM ASSOC_DATA
        WHERE (c_personid IN ({id_placeholders}) OR c_assoc_id IN ({id_placeholders}))
          AND c_assoc_code NOT IN (-1, 0)
    """, person_ids + person_ids)
    rows = cursor.fetchall()

    cursor.execute("SELECT c_assoc_code, c_assoc_desc_chn, c_assoc_desc, c_assoc_role_type FROM ASSOC_CODES")
    assoc_code_info = {r[0]: (r[1], r[2], r[3]) for r in cursor.fetchall()}

    cursor.execute("SELECT c_nianhao_id, c_firstyear, c_lastyear FROM NIAN_HAO")
    nh_lookup = {}
    for r in cursor.fetchall():
        nh_lookup[r[0]] = (r[1], r[2])

    # Full TEXT_CODES load (no LIMIT)
    cursor.execute("SELECT c_textid, c_title_chn, c_title FROM TEXT_CODES")
    text_lookup = {r[0]: (r[1] or r[2] or "") for r in cursor.fetchall()}

    relationships = []

    for row in rows:
        (assoc_code, personid, assoc_id,
         assoc_year, nh_code, nh_year, assoc_range,
         source, pages, notes, text_title,
         addr_id, sequence) = row

        # Both persons must be in our list
        if personid not in id_set or assoc_id not in id_set:
            continue
        if personid == assoc_id:
            continue

        rel_info = code_mapping.get(assoc_code)
        if not rel_info:
            continue

        role_type = assoc_code_info.get(assoc_code, (None, None, None))[2]
        rel_type = rel_info["rel_type"]
        rel_subtype = rel_info["rel_subtype"]
        default_direction = rel_info["direction"]
        weight = rel_info["default_weight"]

        # Determine direction and normalized endpoints
        if role_type == "M" or default_direction == "undirected":
            direction = "undirected"
            source_id = min(personid, assoc_id)
            target_id = max(personid, assoc_id)
        elif role_type == "A":
            direction = "directed"
            source_id = personid
            target_id = assoc_id
        elif role_type == "P":
            direction = "directed"
            source_id = assoc_id
            target_id = personid
        else:
            direction = default_direction
            if direction == "undirected":
                source_id = min(personid, assoc_id)
                target_id = max(personid, assoc_id)
            else:
                source_id = personid
                target_id = assoc_id

        # Year
        year_start = None
        if assoc_year and assoc_year != 0:
            year_start = assoc_year
        elif nh_code and nh_code != 0:
            nh_info = nh_lookup.get(nh_code)
            if nh_info and nh_info[0]:
                year_start = nh_info[0]

        # Evidence level: 'primary' if has source, 'unsourced' otherwise
        # All records here are direct CBDB ASSOC_DATA rows — none are inferred.
        c_source_val = source if source and source > 0 else None
        evidence = "primary" if c_source_val is not None else "unsourced"

        # Source reference: full TEXT_CODES lookup (no LIMIT truncation)
        source_ref = ""
        if c_source_val is not None:
            source_ref = text_lookup.get(c_source_val, f"textid={c_source_val}")

        cbdb_desc = assoc_code_info.get(assoc_code, (None, None, None))
        rel_desc_chn = cbdb_desc[0] or ""

        # Full provenance fields
        relationships.append({
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_type,
            "rel_subtype": rel_subtype,
            "rel_desc_chn": rel_desc_chn,
            "direction": direction,
            "year_start": year_start,
            "year_end": None,
            "weight": weight,
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
        })

    return relationships


def extract_kin_relationships(conn, person_ids, kin_code_mapping):
    """Extract KIN_DATA relationships between people in the person list.

    No deduplication: all raw records are preserved for provenance.
    """
    cursor = conn.cursor()
    id_set = set(person_ids)
    id_placeholders = ",".join("?" * len(person_ids))

    cursor.execute(f"""
        SELECT c_personid, c_kin_id, c_kin_code, c_source, c_pages, c_notes
        FROM KIN_DATA
        WHERE c_personid IN ({id_placeholders}) OR c_kin_id IN ({id_placeholders})
    """, person_ids + person_ids)
    rows = cursor.fetchall()

    cursor.execute("SELECT c_kincode, c_kinrel_chn, c_kinrel, c_kinrel_simplified FROM KINSHIP_CODES")
    kin_info = {r[0]: (r[1], r[2], r[3]) for r in cursor.fetchall()}

    # Full TEXT_CODES load (no LIMIT)
    cursor.execute("SELECT c_textid, c_title_chn, c_title FROM TEXT_CODES")
    text_lookup = {r[0]: (r[1] or r[2] or "") for r in cursor.fetchall()}

    relationships = []

    for row in rows:
        personid, kin_id, kin_code, source, pages, notes = row

        if personid not in id_set or kin_id not in id_set:
            continue
        if personid == kin_id:
            continue

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

        rel_type = rel_info["rel_type"]
        rel_subtype = rel_info["rel_subtype"]
        direction = rel_info["direction"]
        weight = rel_info["default_weight"]

        if direction == "undirected":
            source_id = min(personid, kin_id)
            target_id = max(personid, kin_id)
        else:
            source_id = personid
            target_id = kin_id

        # Evidence level: 'primary' if has source, 'unsourced' otherwise
        c_source_val = source if source and source > 0 else None
        evidence = "primary" if c_source_val is not None else "unsourced"

        source_ref = ""
        if c_source_val is not None:
            source_ref = text_lookup.get(c_source_val, f"textid={c_source_val}")

        kin_detail = kin_info.get(kin_code, ("", "", ""))
        rel_desc_chn = kin_detail[0] or ""

        relationships.append({
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_type,
            "rel_subtype": rel_subtype,
            "rel_desc_chn": rel_desc_chn,
            "direction": direction,
            "year_start": None,
            "year_end": None,
            "weight": weight,
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
        })

    return relationships


def run_quality_checks(persons, relationships, person_ids):
    """Run quality checks and return report."""
    report = []
    report.append("# 质量检查报告\n")
    report.append(f"生成时间: 2026-08-16\n")
    report.append(f"人物总数: {len(persons)}\n")
    report.append(f"关系记录总数（未去重）: {len(relationships)}\n")

    # Unique edges
    edge_set = set()
    for r in relationships:
        edge_set.add((r["source_id"], r["target_id"], r["rel_type"], r["rel_subtype"]))
    report.append(f"唯一关系边数: {len(edge_set)}\n")

    # 1. Duplicate check
    report.append("\n## 1. 去重检查\n")
    id_counts = defaultdict(int)
    for p in persons:
        id_counts[p["c_personid"]] += 1
    dups = {k: v for k, v in id_counts.items() if v > 1}
    if dups:
        report.append(f"⚠️ 发现重复人物ID: {dups}\n")
    else:
        report.append("✅ 无人物ID重复\n")

    # Count multi-evidence edges
    edge_counts = defaultdict(int)
    for r in relationships:
        key = (r["source_id"], r["target_id"], r["rel_type"], r["rel_subtype"])
        edge_counts[key] += 1
    multi_evidence = {k: v for k, v in edge_counts.items() if v > 1}
    report.append(f"有多条原始证据的边: {len(multi_evidence)} 条\n")
    if multi_evidence:
        for k, v in list(multi_evidence.items())[:5]:
            report.append(f"  - {k}: {v}条原始记录\n")

    # 2. Entity alignment check
    report.append("\n## 2. 实体对齐检查\n")
    persons_in_rels = set()
    for r in relationships:
        persons_in_rels.add(r["source_id"])
        persons_in_rels.add(r["target_id"])
    orphan_persons = set(person_ids) - persons_in_rels
    external_refs = persons_in_rels - set(person_ids)
    report.append(f"人物表中无任何关系的人物: {len(orphan_persons)} 人\n")
    if orphan_persons:
        id_to_name = {p["c_personid"]: p["name_chn"] for p in persons}
        for pid in sorted(orphan_persons):
            report.append(f"  - {pid}: {id_to_name.get(pid, '未知')}\n")
    report.append(f"关系中引用的非清单人物: {len(external_refs)} 人（已过滤，不在输出中）\n")

    # 3. Missing values check
    report.append("\n## 3. 缺失值检查\n")
    missing_name = [p for p in persons if not p["name_chn"]]
    missing_birth = [p for p in persons if p["birthyear"] is None]
    missing_death = [p for p in persons if p["deathyear"] is None]
    missing_dy = [p for p in persons if not p["dynasty_chn"]]
    report.append(f"姓名缺失: {len(missing_name)} 人\n")
    if missing_name:
        for p in missing_name:
            report.append(f"  - c_personid={p['c_personid']}, name_rm={p['name_rm']}\n")
    report.append(f"生年缺失: {len(missing_birth)} 人\n")
    report.append(f"卒年缺失: {len(missing_death)} 人\n")
    report.append(f"朝代缺失: {len(missing_dy)} 人\n")

    missing_source_ref = sum(1 for r in relationships if not r["source_ref"])
    missing_year = sum(1 for r in relationships if r["year_start"] is None)
    report.append(f"关系来源缺失: {missing_source_ref}/{len(relationships)} 条\n")
    report.append(f"关系时间缺失: {missing_year}/{len(relationships)} 条\n")

    # 4. Anomaly relationship check
    report.append("\n## 4. 异常关系检查\n")
    self_loops = [r for r in relationships if r["source_id"] == r["target_id"]]
    report.append(f"自环关系: {len(self_loops)} 条\n")

    # 5. Relationship type distribution
    report.append("\n## 5. 关系类型分布\n")
    type_dist = defaultdict(int)
    for r in relationships:
        type_dist[r["rel_type"]] += 1
    for rt in sorted(type_dist.keys()):
        report.append(f"  {rt}: {type_dist[rt]} 条\n")

    # 6. Evidence level distribution
    report.append("\n## 6. 证据等级分布\n")
    ev_dist = defaultdict(int)
    for r in relationships:
        ev_dist[r["evidence_level"]] += 1
    for ev in sorted(ev_dist.keys()):
        report.append(f"  {ev}: {ev_dist[ev]} 条\n")

    # 7. Source coverage
    report.append("\n## 7. 来源覆盖度\n")
    sourced = sum(1 for r in relationships if r["evidence_level"] == "primary")
    unsourced = sum(1 for r in relationships if r["evidence_level"] == "unsourced")
    report.append(f"有来源(primary): {sourced} 条\n")
    report.append(f"无来源(unsourced): {unsourced} 条\n")
    report.append(f"注意: unsourced 表示 CBDB 中存在直接记录但 c_source 字段为空，"
                  f"并非推断关系。本项目未实现推断算法，故无 inferred 标记。\n")

    return "".join(report)


def main():
    args = parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading figures from {FIGURES_CSV}...")
    figures = load_figures(FIGURES_CSV)
    person_ids = [int(f["c_personid"]) for f in figures]
    print(f"  Loaded {len(person_ids)} persons")

    print(f"Loading relationship types from {REL_TYPES_CSV}...")
    rel_types = load_rel_types(REL_TYPES_CSV)
    print(f"  Loaded {len(rel_types)} relationship type rows")
    code_mapping = build_code_to_reltype(rel_types)
    kin_code_mapping = build_kin_code_to_reltype(rel_types)
    print(f"  Mapped {len(code_mapping)} ASSOC codes, {len(kin_code_mapping)} KIN codes")

    print(f"Connecting to CBDB: {args.db}")
    conn = sqlite3.connect(args.db)

    print("Extracting persons...")
    persons = extract_persons(conn, person_ids)
    print(f"  Extracted {len(persons)} persons from BIOG_MAIN")

    print("Extracting ASSOC relationships...")
    assoc_rels = extract_assoc_relationships(conn, person_ids, code_mapping)
    print(f"  Found {len(assoc_rels)} ASSOC relationship records within network")

    print("Extracting KIN relationships...")
    kin_rels = extract_kin_relationships(conn, person_ids, kin_code_mapping)
    print(f"  Found {len(kin_rels)} KIN relationship records within network")

    all_rels = assoc_rels + kin_rels
    print(f"  Total: {len(all_rels)} raw relationship records")

    # Unique edges summary
    edge_set = set()
    for r in all_rels:
        edge_set.add((r["source_id"], r["target_id"], r["rel_type"], r["rel_subtype"]))
    print(f"  Unique edges: {len(edge_set)}")

    conn.close()

    # Write persons.csv
    person_fields = [
        "c_personid", "name_chn", "name_rm", "surname_chn", "given_name_chn",
        "birthyear", "deathyear", "fl_earliest_year", "fl_latest_year",
        "is_female", "dynasty_code", "dynasty_chn", "dynasty_en", "aliases"
    ]
    person_path = os.path.join(OUTPUT_DIR, "persons.csv")
    with open(person_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=person_fields, extrasaction="ignore")
        writer.writeheader()
        for p in sorted(persons, key=lambda x: x["c_personid"]):
            writer.writerow(p)
    print(f"Wrote {person_path} ({len(persons)} rows)")

    # Write relationships.csv — full raw records, NO dedup, with provenance
    rel_fields = [
        "source_id", "target_id", "rel_type", "rel_subtype", "rel_desc_chn",
        "direction", "year_start", "year_end", "weight", "evidence_level",
        "source_ref", "cbdb_assoc_code", "cbdb_role_type",
        "source_table", "c_source", "c_pages", "c_sequence", "c_text_title",
        "orig_personid", "orig_assoc_id",
    ]
    rel_path = os.path.join(OUTPUT_DIR, "relationships.csv")
    with open(rel_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rel_fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(all_rels, key=lambda x: (x["source_id"], x["target_id"])):
            writer.writerow(r)
    print(f"Wrote {rel_path} ({len(all_rels)} rows, {len(edge_set)} unique edges)")

    # Quality check
    print("Running quality checks...")
    report = run_quality_checks(persons, all_rels, person_ids)
    report_path = os.path.join(OUTPUT_DIR, "quality_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Wrote {report_path}")

    print("Done!")


if __name__ == "__main__":
    main()
