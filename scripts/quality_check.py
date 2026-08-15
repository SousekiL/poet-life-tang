#!/usr/bin/env python3
"""
Data quality check for Tang-networks.

Validates data integrity and reports statistics.

Usage:
    python scripts/quality_check.py [--data-dir PATH]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def check_people(people_path: Path) -> dict:
    """Check people data quality."""
    if not people_path.exists():
        return {"error": f"File not found: {people_path}"}
    
    df = pd.read_csv(people_path)
    
    stats = {
        "total_records": len(df),
        "missing_fields": {},
        "invalid_years": 0,
        "duplicate_ids": 0
    }
    
    # Check missing fields
    for col in df.columns:
        missing = df[col].isna().sum()
        if missing > 0:
            stats["missing_fields"][col] = int(missing)
    
    # Check invalid years (birth > death)
    if 'birth_year' in df.columns and 'death_year' in df.columns:
        invalid = df[df['birth_year'] > df['death_year']].shape[0]
        stats["invalid_years"] = int(invalid)
    
    # Check duplicate IDs
    if 'cbdb_id' in df.columns:
        duplicates = df['cbdb_id'].duplicated().sum()
        stats["duplicate_ids"] = int(duplicates)
    
    return stats


def check_relationships(rels_path: Path) -> dict:
    """Check relationships data quality."""
    if not rels_path.exists():
        return {"error": f"File not found: {rels_path}"}
    
    df = pd.read_csv(rels_path)
    
    stats = {
        "total_records": len(df),
        "missing_fields": {},
        "relationship_types": {},
        "duplicate_edges": 0
    }
    
    # Check missing fields
    for col in df.columns:
        missing = df[col].isna().sum()
        if missing > 0:
            stats["missing_fields"][col] = int(missing)
    
    # Relationship type distribution
    if 'relationship_type' in df.columns:
        type_counts = df['relationship_type'].value_counts().to_dict()
        stats["relationship_types"] = {str(k): int(v) for k, v in type_counts.items()}
    
    # Check duplicate edges
    if 'person1_cbdb_id' in df.columns and 'person2_cbdb_id' in df.columns:
        duplicates = df.duplicated(subset=['person1_cbdb_id', 'person2_cbdb_id']).sum()
        stats["duplicate_edges"] = int(duplicates)
    
    return stats


def check_network_consistency(people_path: Path, rels_path: Path) -> dict:
    """Check consistency between people and relationships."""
    if not people_path.exists() or not rels_path.exists():
        return {"error": "Missing data files"}
    
    people = pd.read_csv(people_path)
    rels = pd.read_csv(rels_path)
    
    people_ids = set(people['cbdb_id'].unique())
    
    # Check for relationships referencing non-existent people
    rels_p1 = set(rels['person1_cbdb_id'].unique())
    rels_p2 = set(rels['person2_cbdb_id'].unique())
    all_rel_ids = rels_p1 | rels_p2
    
    missing_ids = all_rel_ids - people_ids
    
    return {
        "people_count": len(people_ids),
        "relationship_count": len(rels),
        "referenced_person_ids": len(all_rel_ids),
        "missing_person_ids": len(missing_ids),
        "missing_ids_sample": list(missing_ids)[:10] if missing_ids else []
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Data quality check")
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path("data/processed"),
        help="Data directory"
    )
    args = parser.parse_args()
    
    people_path = args.data_dir / "people.csv"
    rels_path = args.data_dir / "relationships.csv"
    
    print("=" * 60)
    print("Tang-networks Data Quality Report")
    print("=" * 60)
    
    # Check people
    print("\n[People]")
    people_stats = check_people(people_path)
    if "error" in people_stats:
        print(f"  Error: {people_stats['error']}")
    else:
        print(f"  Total records: {people_stats['total_records']}")
        print(f"  Duplicate IDs: {people_stats['duplicate_ids']}")
        print(f"  Invalid years (birth > death): {people_stats['invalid_years']}")
        if people_stats['missing_fields']:
            print(f"  Missing fields:")
            for field, count in people_stats['missing_fields'].items():
                print(f"    - {field}: {count}")
    
    # Check relationships
    print("\n[Relationships]")
    rels_stats = check_relationships(rels_path)
    if "error" in rels_stats:
        print(f"  Error: {rels_stats['error']}")
    else:
        print(f"  Total records: {rels_stats['total_records']}")
        print(f"  Duplicate edges: {rels_stats['duplicate_edges']}")
        if rels_stats['relationship_types']:
            print(f"  Relationship types:")
            for rtype, count in rels_stats['relationship_types'].items():
                print(f"    - {rtype}: {count}")
        if rels_stats['missing_fields']:
            print(f"  Missing fields:")
            for field, count in rels_stats['missing_fields'].items():
                print(f"    - {field}: {count}")
    
    # Check consistency
    print("\n[Network Consistency]")
    consistency = check_network_consistency(people_path, rels_path)
    if "error" in consistency:
        print(f"  Error: {consistency['error']}")
    else:
        print(f"  People count: {consistency['people_count']}")
        print(f"  Relationship count: {consistency['relationship_count']}")
        print(f"  Referenced person IDs: {consistency['referenced_person_ids']}")
        print(f"  Missing person IDs: {consistency['missing_person_ids']}")
        if consistency['missing_ids_sample']:
            print(f"  Sample missing IDs: {consistency['missing_ids_sample']}")
    
    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
