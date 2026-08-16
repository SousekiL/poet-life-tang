#!/usr/bin/env python3
"""
Generate comprehensive relationship mapping and network JSON for visualization.

This script preserves original relationship subtypes while maintaining major type categorization.
"""

import csv
import json
import os
from collections import defaultdict

DATA_DIR = "data"
OUTPUT_DIR = "data/dimensions"

# Relationship types (6 major categories)
REL_TYPES = ["KIN", "TEACHER_STUDENT", "COLLEAGUE", "LITERARY", "POLITICAL", "SOCIAL"]

def load_relationships(path):
    rels = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rels.append(r)
    return rels

def load_persons(path):
    persons = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            persons[int(r["c_personid"])] = r
    return persons

def generate_relationship_mapping(rels):
    """Generate mapping between major types and original subtypes."""
    mapping = defaultdict(lambda: {"subtypes": defaultdict(int), "count": 0})
    
    for r in rels:
        rel_type = r["rel_type"]
        rel_subtype = r.get("rel_subtype", "unknown")
        mapping[rel_type]["subtypes"][rel_subtype] += 1
        mapping[rel_type]["count"] += 1
    
    return mapping

def generate_network_json(persons, rels, output_path):
    """Generate network JSON file for visualization."""
    # Create nodes
    nodes = []
    for pid, p in persons.items():
        node = {
            "id": pid,
            "name": p.get("name_chn", ""),
            "name_rm": p.get("name_rm", ""),
            "birthyear": p.get("birthyear"),
            "deathyear": p.get("deathyear"),
            "dynasty": p.get("dynasty_chn", ""),
            "is_female": p.get("is_female", "0"),
            "role": p.get("role", "core"),
            "bridge_tier": p.get("bridge_tier", "")
        }
        nodes.append(node)
    
    # Create edges with both major type and original subtype
    edges = []
    for r in rels:
        edge = {
            "source": int(r["source_id"]),
            "target": int(r["target_id"]),
            "rel_type": r["rel_type"],  # Major type (KIN, SOCIAL, etc.)
            "rel_subtype": r.get("rel_subtype", ""),  # Original subtype
            "rel_desc_chn": r.get("rel_desc_chn", ""),  # Chinese description
            "direction": r.get("direction", ""),
            "weight": float(r.get("weight", 0.5)),
            "evidence_level": r.get("evidence_level", ""),
            "year_start": r.get("year_start"),
            "year_end": r.get("year_end")
        }
        edges.append(edge)
    
    network = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "total_persons": len(nodes),
            "total_relationships": len(edges),
            "relationship_types": list(set(r["rel_type"] for r in rels)),
            "relationship_subtypes": list(set(r.get("rel_subtype", "") for r in rels if r.get("rel_subtype")))
        }
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(network, f, ensure_ascii=False, indent=2)
    
    return network

def write_mapping_report(mapping, output_path):
    """Write comprehensive relationship mapping report."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 关系类型与原始子类型映射\n\n")
        f.write("本文档展示关系大类与原始子类型的完整映射关系，便于可视化时保留原始关系信息。\n\n")
        
        for rel_type in REL_TYPES:
            if rel_type in mapping:
                data = mapping[rel_type]
                f.write(f"## {rel_type}\n\n")
                f.write(f"- **总关系数**: {data['count']}\n")
                f.write(f"- **子类型数**: {len(data['subtypes'])}\n\n")
                
                f.write("| 原始子类型 | 数量 | 占比 |\n")
                f.write("|------------|------|------|\n")
                
                for subtype, count in sorted(data['subtypes'].items(), key=lambda x: -x[1]):
                    percentage = (count / data['count'] * 100) if data['count'] > 0 else 0
                    f.write(f"| {subtype} | {count} | {percentage:.1f}% |\n")
                
                f.write("\n")

def write_relationship_types_report(mapping_core, mapping_all, output_path):
    """Write comprehensive relationship types report with all subtypes."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 关系类型维度分析\n\n")
        
        f.write("## 核心人物关系\n\n")
        f.write("| 关系类型 | 关系数量 | 子类型数 |\n")
        f.write("|----------|----------|----------|\n")
        for rel_type in REL_TYPES:
            if rel_type in mapping_core:
                data = mapping_core[rel_type]
                f.write(f"| {rel_type} | {data['count']} | {len(data['subtypes'])} |\n")
        
        f.write("\n## 全部人物关系（含桥接）\n\n")
        f.write("| 关系类型 | 关系数量 | 子类型数 |\n")
        f.write("|----------|----------|----------|\n")
        for rel_type in REL_TYPES:
            if rel_type in mapping_all:
                data = mapping_all[rel_type]
                f.write(f"| {rel_type} | {data['count']} | {len(data['subtypes'])} |\n")
        
        f.write("\n## 各类型详情（核心网络）\n\n")
        for rel_type in REL_TYPES:
            if rel_type in mapping_core:
                data = mapping_core[rel_type]
                f.write(f"### {rel_type}\n\n")
                f.write(f"- 关系数量: {data['count']}\n")
                f.write(f"- 子类型数: {len(data['subtypes'])}\n")
                f.write("- 所有子类型:\n")
                for subtype, count in sorted(data['subtypes'].items(), key=lambda x: -x[1]):
                    percentage = (count / data['count'] * 100) if data['count'] > 0 else 0
                    f.write(f"  - {subtype}: {count} ({percentage:.1f}%)\n")
                f.write("\n")
        
        f.write("\n## 各类型详情（全部网络）\n\n")
        for rel_type in REL_TYPES:
            if rel_type in mapping_all:
                data = mapping_all[rel_type]
                f.write(f"### {rel_type}\n\n")
                f.write(f"- 关系数量: {data['count']}\n")
                f.write(f"- 子类型数: {len(data['subtypes'])}\n")
                f.write("- 所有子类型:\n")
                for subtype, count in sorted(data['subtypes'].items(), key=lambda x: -x[1]):
                    percentage = (count / data['count'] * 100) if data['count'] > 0 else 0
                    f.write(f"  - {subtype}: {count} ({percentage:.1f}%)\n")
                f.write("\n")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=== Loading data ===")
    persons_core = load_persons(os.path.join(DATA_DIR, "persons.csv"))
    rels_core = load_relationships(os.path.join(DATA_DIR, "relationships.csv"))
    persons_all = load_persons(os.path.join(DATA_DIR, "persons_combined.csv"))
    rels_all = load_relationships(os.path.join(DATA_DIR, "relationships_combined.csv"))
    
    print(f"Core: {len(persons_core)} persons, {len(rels_core)} relationships")
    print(f"All: {len(persons_all)} persons, {len(rels_all)} relationships")
    
    print("\n=== Generating relationship mapping ===")
    mapping_core = generate_relationship_mapping(rels_core)
    mapping_all = generate_relationship_mapping(rels_all)
    
    print("Writing mapping reports...")
    write_mapping_report(mapping_core, os.path.join(OUTPUT_DIR, "relationship_mapping_core.md"))
    write_mapping_report(mapping_all, os.path.join(OUTPUT_DIR, "relationship_mapping_all.md"))

    print("\n=== Writing relationship types report ===")
    write_relationship_types_report(mapping_core, mapping_all, os.path.join(OUTPUT_DIR, "relationship_types.md"))
    print(f"Wrote {OUTPUT_DIR}/relationship_types.md")
    
    print("\n=== Generating network JSON ===")
    print("Generating core network JSON...")
    network_core = generate_network_json(persons_core, rels_core, os.path.join(OUTPUT_DIR, "network_core.json"))
    print(f"  Core network: {network_core['metadata']['total_persons']} nodes, {network_core['metadata']['total_relationships']} edges")
    
    print("Generating all network JSON...")
    network_all = generate_network_json(persons_all, rels_all, os.path.join(OUTPUT_DIR, "network_all.json"))
    print(f"  All network: {network_all['metadata']['total_persons']} nodes, {network_all['metadata']['total_relationships']} edges")
    
    print("\n=== Done! ===")
    print(f"Output files in {OUTPUT_DIR}/")
    print("- relationship_mapping_core.md: Core network relationship mapping")
    print("- relationship_mapping_all.md: All network relationship mapping")
    print("- network_core.json: Core network JSON for visualization")
    print("- network_all.json: All network JSON for visualization")

if __name__ == "__main__":
    main()

