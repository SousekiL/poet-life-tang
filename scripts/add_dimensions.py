#!/usr/bin/env python3
"""
Remove isolated figures (黃巢, 吳道子) and add multi-dimensional analysis:
1. k-connectivity analysis
2. Relationship type filtering (6 major types)
3. Emperor reign period analysis (年号维度)

Outputs both "all" (combined with bridge figures) and "core" (core figures only) versions.
"""

import csv
import sqlite3
import os
from collections import defaultdict, deque

DB_PATH = os.environ.get("CBDB_PATH", "/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/cbdb202409.db")
DATA_DIR = "data"
OUTPUT_DIR = "data/dimensions"

# Figures to remove (isolated)
REMOVE_IDS = {3409, 43849}  # 黃巢, 吳道子

# Relationship types (6 major categories)
REL_TYPES = ["KIN", "TEACHER_STUDENT", "COLLEAGUE", "LITERARY", "POLITICAL", "SOCIAL"]

# Tang dynasty emperor reign periods (年号)
TANG_REIGN_PERIODS = [
    (1, "武德", 618, 626, "唐高祖"),
    (2, "贞观", 627, 649, "唐太宗"),
    (3, "永徽", 650, 655, "唐高宗"),
    (4, "显庆", 656, 661, "唐高宗"),
    (5, "龙朔", 661, 663, "唐高宗"),
    (6, "麟德", 664, 665, "唐高宗"),
    (7, "乾封", 666, 668, "唐高宗"),
    (8, "总章", 668, 670, "唐高宗"),
    (9, "咸亨", 670, 674, "唐高宗"),
    (10, "上元", 674, 676, "唐高宗"),
    (11, "仪凤", 676, 679, "唐高宗"),
    (12, "调露", 679, 680, "唐高宗"),
    (13, "永隆", 680, 681, "唐高宗"),
    (14, "开耀", 681, 682, "唐高宗"),
    (15, "永淳", 682, 683, "唐高宗"),
    (16, "弘道", 683, 684, "唐高宗"),
    (17, "嗣圣", 684, 684, "唐中宗"),
    (18, "文明", 684, 684, "唐睿宗"),
    (19, "光宅", 684, 685, "武则天"),
    (20, "垂拱", 685, 688, "武则天"),
    (21, "永昌", 689, 690, "武则天"),
    (22, "载初", 690, 690, "武则天"),
    (23, "天授", 690, 692, "武则天"),
    (24, "如意", 692, 692, "武则天"),
    (25, "长寿", 692, 694, "武则天"),
    (26, "延载", 694, 695, "武则天"),
    (27, "证圣", 695, 696, "武则天"),
    (28, "天册万岁", 696, 696, "武则天"),
    (29, "万岁登封", 696, 696, "武则天"),
    (30, "万岁通天", 696, 697, "武则天"),
    (31, "神功", 697, 697, "武则天"),
    (32, "圣历", 698, 700, "武则天"),
    (33, "久视", 700, 701, "武则天"),
    (34, "大足", 701, 701, "武则天"),
    (35, "长安", 701, 704, "武则天"),
    (36, "神龙", 705, 707, "唐中宗"),
    (37, "景龙", 707, 710, "唐中宗"),
    (38, "唐隆", 710, 710, "唐殇帝"),
    (39, "景云", 710, 712, "唐睿宗"),
    (40, "太极", 712, 712, "唐睿宗"),
    (41, "延和", 712, 712, "唐睿宗"),
    (42, "先天", 712, 713, "唐玄宗"),
    (43, "开元", 713, 741, "唐玄宗"),
    (44, "天宝", 742, 756, "唐玄宗"),
    (45, "至德", 756, 758, "唐肃宗"),
    (46, "乾元", 758, 760, "唐肃宗"),
    (47, "上元", 760, 761, "唐肃宗"),
    (48, "宝应", 762, 763, "唐肃宗"),
    (49, "广德", 763, 764, "唐代宗"),
    (50, "永泰", 765, 766, "唐代宗"),
    (51, "大历", 766, 779, "唐代宗"),
    (52, "建中", 780, 783, "唐德宗"),
    (53, "兴元", 784, 784, "唐德宗"),
    (54, "贞元", 785, 805, "唐德宗"),
    (55, "永贞", 805, 805, "唐顺宗"),
    (56, "元和", 806, 820, "唐宪宗"),
    (57, "长庆", 821, 824, "唐穆宗"),
    (58, "宝历", 825, 827, "唐敬宗"),
    (59, "大和", 827, 835, "唐文宗"),
    (60, "开成", 836, 840, "唐文宗"),
    (61, "会昌", 841, 846, "唐武宗"),
    (62, "大中", 847, 860, "唐宣宗"),
    (63, "咸通", 860, 874, "唐懿宗"),
    (64, "乾符", 874, 879, "唐僖宗"),
    (65, "广明", 880, 881, "唐僖宗"),
    (66, "中和", 881, 885, "唐僖宗"),
    (67, "光启", 885, 888, "唐僖宗"),
    (68, "文德", 888, 888, "唐僖宗"),
    (69, "龙纪", 889, 889, "唐昭宗"),
    (70, "大顺", 890, 891, "唐昭宗"),
    (71, "景福", 892, 893, "唐昭宗"),
    (72, "乾宁", 894, 898, "唐昭宗"),
    (73, "光化", 898, 901, "唐昭宗"),
    (74, "天复", 901, 904, "唐昭宗"),
    (75, "天祐", 904, 907, "唐昭宗"),
]

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

def remove_figures(persons, rels, remove_ids):
    """Remove specified figures and their relationships."""
    filtered_persons = {pid: p for pid, p in persons.items() if pid not in remove_ids}
    filtered_rels = [r for r in rels if int(r["source_id"]) not in remove_ids and int(r["target_id"]) not in remove_ids]
    return filtered_persons, filtered_rels

def build_graph(rels):
    """Build adjacency list from relationships."""
    graph = defaultdict(set)
    for r in rels:
        s, t = int(r["source_id"]), int(r["target_id"])
        graph[s].add(t)
        graph[t].add(s)
    return graph

def bfs_distances(graph, source):
    """BFS to compute shortest distances from source to all reachable nodes."""
    dist = {source: 0}
    queue = deque([source])
    while queue:
        u = queue.popleft()
        for v in graph[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist

def analyze_k_connectivity(persons, rels, label):
    """Analyze k-connectivity: what k value connects all people."""
    graph = build_graph(rels)
    person_ids = set(persons.keys())
    
    # Find connected components
    visited = set()
    components = []
    for pid in person_ids:
        if pid not in visited:
            component = set()
            queue = deque([pid])
            while queue:
                u = queue.popleft()
                if u in visited:
                    continue
                visited.add(u)
                component.add(u)
                for v in graph[u]:
                    if v not in visited and v in person_ids:
                        queue.append(v)
            components.append(component)
    
    components.sort(key=len, reverse=True)
    
    # For the largest component, find the diameter (max k needed)
    max_k = 0
    if components:
        largest = components[0]
        # Sample nodes to estimate diameter (full computation is O(n^2))
        sample_nodes = list(largest)[:30]
        for node in sample_nodes:
            dist = bfs_distances(graph, node)
            for other in largest:
                if other in dist:
                    max_k = max(max_k, dist[other])
    
    return {
        "label": label,
        "total_persons": len(person_ids),
        "num_components": len(components),
        "component_sizes": [len(c) for c in components],
        "largest_component_size": len(components[0]) if components else 0,
        "max_k_diameter": max_k,
        "components": components,
        "isolated_persons": [persons[pid]["name_chn"] for pid in person_ids if pid not in graph or len(graph[pid]) == 0],
    }

def analyze_relationship_types(persons, rels, label):
    """Analyze relationships by type."""
    type_analysis = defaultdict(lambda: {"count": 0, "persons": set(), "rels": []})
    
    for r in rels:
        rel_type = r["rel_type"]
        s, t = int(r["source_id"]), int(r["target_id"])
        type_analysis[rel_type]["count"] += 1
        type_analysis[rel_type]["persons"].add(s)
        type_analysis[rel_type]["persons"].add(t)
        type_analysis[rel_type]["rels"].append(r)
    
    return {"label": label, "analysis": type_analysis}

def analyze_reign_periods(persons, rels, label):
    """Analyze persons by emperor reign periods.
    
    Rule: A person belongs to a period if their life span (birth to death)
    overlaps with that period. Overlap means: birth <= period_end AND death >= period_start.
    If only birth is known, include if birth <= period_end.
    If only death is known, include if death >= period_start.
    A person can appear in multiple periods (non-exclusive).
    """
    # Get birth/death years
    person_years = {}
    for pid, p in persons.items():
        birth = p.get("birthyear")
        death = p.get("deathyear")
        if birth and birth != "" and birth != "0":
            try:
                birth = int(birth)
            except:
                birth = None
        else:
            birth = None
        if death and death != "" and death != "0":
            try:
                death = int(death)
            except:
                death = None
        else:
            death = None
        person_years[pid] = (birth, death)
    
    # Map persons to reign periods
    period_persons = defaultdict(set)
    for pid, (birth, death) in person_years.items():
        if birth is None and death is None:
            continue
        
        for period_id, nianhao, start, end, emperor in TANG_REIGN_PERIODS:
            # Person overlaps with this period if their life span overlaps
            # Overlap: birth <= period_end AND death >= period_start
            overlap = False
            if birth is not None and death is not None:
                # Both known: standard overlap check
                overlap = birth <= end and death >= start
            elif birth is not None:
                # Only birth known: include if born before or during period
                overlap = birth <= end
            elif death is not None:
                # Only death known: include if died during or after period start
                overlap = death >= start
            
            if overlap:
                period_persons[(period_id, nianhao, start, end, emperor)].add(pid)
    
    return {"label": label, "periods": period_persons}

def write_markdown_report(output_path, k_core, k_all, type_core, type_all, period_core, period_all, persons_core, persons_all):
    """Write comprehensive markdown report with all dimensions."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 唐代人物关系网络多维度分析\n\n")
        
        # Summary
        f.write("## 概览\n\n")
        f.write(f"- **核心人物**: {k_core['total_persons']} 人\n")
        f.write(f"- **全部人物（含桥接）**: {k_all['total_persons']} 人\n")
        f.write(f"- **已移除人物**: 黃巢、吳道子（CBDB 中无有效连接）\n\n")
        
        # K-connectivity
        f.write("---\n\n## 1. K-连通性分析\n\n")
        f.write("### 核心人物网络\n\n")
        f.write(f"| 指标 | 值 |\n")
        f.write(f"|------|----|\n")
        f.write(f"| 总人数 | {k_core['total_persons']} |\n")
        f.write(f"| 连通分量数 | {k_core['num_components']} |\n")
        f.write(f"| 最大分量大小 | {k_core['largest_component_size']} |\n")
        f.write(f"| 最大分量直径 (k) | {k_core['max_k_diameter']} |\n")
        f.write(f"| 孤立人物 | {', '.join(k_core['isolated_persons']) if k_core['isolated_persons'] else '无'} |\n\n")
        
        f.write("### 全部人物网络（含桥接）\n\n")
        f.write(f"| 指标 | 值 |\n")
        f.write(f"|------|----|\n")
        f.write(f"| 总人数 | {k_all['total_persons']} |\n")
        f.write(f"| 连通分量数 | {k_all['num_components']} |\n")
        f.write(f"| 最大分量大小 | {k_all['largest_component_size']} |\n")
        f.write(f"| 最大分量直径 (k) | {k_all['max_k_diameter']} |\n")
        f.write(f"| 孤立人物 | {', '.join(k_all['isolated_persons']) if k_all['isolated_persons'] else '无'} |\n\n")
        
        f.write("### 分量分布\n\n")
        f.write("| 分量大小 | 核心网络 | 全部网络 |\n")
        f.write("|----------|----------|----------|\n")
        core_sizes = defaultdict(int)
        all_sizes = defaultdict(int)
        for size in k_core["component_sizes"]:
            core_sizes[size] += 1
        for size in k_all["component_sizes"]:
            all_sizes[size] += 1
        all_sizes_set = set(core_sizes.keys()) | set(all_sizes.keys())
        for size in sorted(all_sizes_set, reverse=True):
            f.write(f"| {size} | {core_sizes.get(size, 0)} | {all_sizes.get(size, 0)} |\n")
        
        # Relationship types
        f.write("\n---\n\n## 2. 关系类型维度\n\n")
        f.write("### 核心人物关系\n\n")
        f.write("| 关系类型 | 关系数量 | 涉及人物数 |\n")
        f.write("|----------|----------|------------|\n")
        for rel_type in REL_TYPES:
            if rel_type in type_core["analysis"]:
                data = type_core["analysis"][rel_type]
                f.write(f"| {rel_type} | {data['count']} | {len(data['persons'])} |\n")
        
        f.write("\n### 全部人物关系（含桥接）\n\n")
        f.write("| 关系类型 | 关系数量 | 涉及人物数 |\n")
        f.write("|----------|----------|------------|\n")
        for rel_type in REL_TYPES:
            if rel_type in type_all["analysis"]:
                data = type_all["analysis"][rel_type]
                f.write(f"| {rel_type} | {data['count']} | {len(data['persons'])} |\n")
        
        f.write("\n### 各类型详情（核心网络）\n\n")
        for rel_type in REL_TYPES:
            if rel_type in type_core["analysis"]:
                data = type_core["analysis"][rel_type]
                f.write(f"#### {rel_type}\n\n")
                f.write(f"- 关系数量: {data['count']}\n")
                f.write(f"- 涉及人物数: {len(data['persons'])}\n")
                # Show top subtypes
                subtypes = defaultdict(int)
                for r in data["rels"]:
                    subtypes[r.get("rel_subtype", "unknown")] += 1
                f.write("- 主要子类型:\n")
                for subtype, count in sorted(subtypes.items(), key=lambda x: -x[1])[:5]:
                    f.write(f"  - {subtype}: {count}\n")
                f.write("\n")
        
        # Reign periods
        f.write("---\n\n## 3. 皇帝年号维度\n\n")
        f.write("### 核心人物活跃时期\n\n")
        f.write("| 年号 | 时期 | 皇帝 | 活跃人物数 |\n")
        f.write("|------|------|------|------------|\n")
        for (period_id, nianhao, start, end, emperor), pids in sorted(period_core["periods"].items()):
            f.write(f"| {nianhao} | {start}-{end} | {emperor} | {len(pids)} |\n")
        
        f.write("\n### 全部人物活跃时期（含桥接）\n\n")
        f.write("| 年号 | 时期 | 皇帝 | 活跃人物数 |\n")
        f.write("|------|------|------|------------|\n")
        for (period_id, nianhao, start, end, emperor), pids in sorted(period_all["periods"].items()):
            f.write(f"| {nianhao} | {start}-{end} | {emperor} | {len(pids)} |\n")
        
        # Top periods
        f.write("\n### 人物最活跃时期 Top 10\n\n")
        f.write("| 排名 | 年号 | 时期 | 皇帝 | 核心人物数 | 全部人物数 |\n")
        f.write("|------|------|------|------|------------|------------|\n")
        core_top = sorted(period_core["periods"].items(), key=lambda x: -len(x[1]))[:10]
        for rank, ((period_id, nianhao, start, end, emperor), pids) in enumerate(core_top, 1):
            all_pids = period_all["periods"].get((period_id, nianhao, start, end, emperor), set())
            f.write(f"| {rank} | {nianhao} | {start}-{end} | {emperor} | {len(pids)} | {len(all_pids)} |\n")
        
        # Detailed period lists
        f.write("\n### 各时期人物详情（核心网络）\n\n")
        for (period_id, nianhao, start, end, emperor), pids in sorted(period_core["periods"].items()):
            if len(pids) > 0:
                f.write(f"#### {nianhao} ({start}-{end}, {emperor})\n\n")
                names = [persons_core[pid]["name_chn"] for pid in pids if pid in persons_core]
                f.write(", ".join(names))
                f.write("\n\n")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=== Loading data ===")
    # Load core data
    persons_core = load_persons(os.path.join(DATA_DIR, "persons.csv"))
    rels_core = load_relationships(os.path.join(DATA_DIR, "relationships.csv"))
    print(f"Core: {len(persons_core)} persons, {len(rels_core)} relationships")
    
    # Load combined data
    persons_all = load_persons(os.path.join(DATA_DIR, "persons_combined.csv"))
    rels_all = load_relationships(os.path.join(DATA_DIR, "relationships_combined.csv"))
    print(f"Combined: {len(persons_all)} persons, {len(rels_all)} relationships")
    
    print("\n=== Removing isolated figures ===")
    print(f"Removing: {[persons_core[pid]['name_chn'] for pid in REMOVE_IDS if pid in persons_core]}")
    
    persons_core, rels_core = remove_figures(persons_core, rels_core, REMOVE_IDS)
    persons_all, rels_all = remove_figures(persons_all, rels_all, REMOVE_IDS)
    
    print(f"Core after removal: {len(persons_core)} persons, {len(rels_core)} relationships")
    print(f"Combined after removal: {len(persons_all)} persons, {len(rels_all)} relationships")
    
    # Write filtered data
    print("\n=== Writing filtered data ===")
    
    # Core filtered
    fields = ["c_personid", "name_chn", "name_rm", "surname_chn", "given_name_chn",
              "birthyear", "deathyear", "fl_earliest_year", "fl_latest_year", "is_female",
              "dynasty_code", "dynasty_chn", "dynasty_en", "aliases"]
    with open(os.path.join(DATA_DIR, "persons_filtered.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for p in sorted(persons_core.values(), key=lambda x: int(x["c_personid"])):
            writer.writerow(p)
    print(f"Wrote {DATA_DIR}/persons_filtered.csv")
    
    rel_fields = ["source_id", "target_id", "rel_type", "rel_subtype", "rel_desc_chn",
                  "direction", "year_start", "year_end", "weight", "evidence_level",
                  "source_ref", "cbdb_assoc_code", "cbdb_role_type"]
    with open(os.path.join(DATA_DIR, "relationships_filtered.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rel_fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(rels_core, key=lambda x: (int(x["source_id"]), int(x["target_id"]))):
            writer.writerow(r)
    print(f"Wrote {DATA_DIR}/relationships_filtered.csv")
    
    # Combined filtered
    combined_fields = ["c_personid", "name_chn", "name_rm", "surname_chn", "given_name_chn",
                       "birthyear", "deathyear", "is_female", "dynasty_code", "dynasty_chn",
                       "dynasty_en", "role", "bridge_tier"]
    with open(os.path.join(DATA_DIR, "persons_combined_filtered.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=combined_fields, extrasaction="ignore")
        writer.writeheader()
        for p in sorted(persons_all.values(), key=lambda x: int(x["c_personid"])):
            writer.writerow(p)
    print(f"Wrote {DATA_DIR}/persons_combined_filtered.csv")
    
    combined_rel_fields = ["source_id", "target_id", "rel_type", "rel_subtype", "rel_desc_chn",
                           "direction", "year_start", "year_end", "weight", "evidence_level",
                           "source_ref", "cbdb_assoc_code", "cbdb_role_type", "primary_rel", "is_bridge"]
    with open(os.path.join(DATA_DIR, "relationships_combined_filtered.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=combined_rel_fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(rels_all, key=lambda x: (int(x["source_id"]), int(x["target_id"]))):
            writer.writerow(r)
    print(f"Wrote {DATA_DIR}/relationships_combined_filtered.csv")
    
    print("\n=== K-connectivity analysis ===")
    k_core = analyze_k_connectivity(persons_core, rels_core, "core")
    k_all = analyze_k_connectivity(persons_all, rels_all, "all")
    print(f"Core - Components: {k_core['num_components']}, Largest: {k_core['largest_component_size']}, Max k: {k_core['max_k_diameter']}")
    print(f"All - Components: {k_all['num_components']}, Largest: {k_all['largest_component_size']}, Max k: {k_all['max_k_diameter']}")
    
    print("\n=== Relationship type analysis ===")
    type_core = analyze_relationship_types(persons_core, rels_core, "core")
    type_all = analyze_relationship_types(persons_all, rels_all, "all")
    print("Core:")
    for rel_type in REL_TYPES:
        if rel_type in type_core["analysis"]:
            print(f"  {rel_type}: {type_core['analysis'][rel_type]['count']} rels, {len(type_core['analysis'][rel_type]['persons'])} persons")
    print("All:")
    for rel_type in REL_TYPES:
        if rel_type in type_all["analysis"]:
            print(f"  {rel_type}: {type_all['analysis'][rel_type]['count']} rels, {len(type_all['analysis'][rel_type]['persons'])} persons")
    
    print("\n=== Reign period analysis ===")
    period_core = analyze_reign_periods(persons_core, rels_core, "core")
    period_all = analyze_reign_periods(persons_all, rels_all, "all")
    print(f"Core: {len(period_core['periods'])} reign periods with active persons")
    print(f"All: {len(period_all['periods'])} reign periods with active persons")
    
    print("\n=== Writing analysis report ===")
    write_markdown_report(
        os.path.join(OUTPUT_DIR, "dimensions_analysis.md"),
        k_core, k_all, type_core, type_all, period_core, period_all,
        persons_core, persons_all
    )
    print(f"Wrote {OUTPUT_DIR}/dimensions_analysis.md")
    
    print("\n=== Done! ===")

if __name__ == "__main__":
    main()
