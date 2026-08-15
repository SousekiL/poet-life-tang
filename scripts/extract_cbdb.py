#!/usr/bin/env python3
"""
Extract Tang dynasty (618–907) person and relationship data from CBDB.

Reads from CBDB SQLite database and outputs:
- data/processed/people.csv
- data/processed/relationships.csv

Usage:
    python scripts/extract_cbdb.py [--db PATH] [--output-dir PATH]
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


def extract_people(con: sqlite3.Connection, output_path: Path) -> int:
    """Extract Tang dynasty persons from BIOG_MAIN."""
    query = """
    SELECT 
        bm.c_personid as cbdb_id,
        bm.c_name_chn as name,
        bm.c_mingzi_chn as courtesy_name,
        bm.c_birthyear as birth_year,
        bm.c_deathyear as death_year,
        d.c_dynasty_chn as dynasty,
        bm.c_native_place_id as native_place_id,
        bm.c_gender as gender
    FROM BIOG_MAIN bm
    LEFT JOIN DYNASTIES d ON bm.c_dy = d.c_dy
    WHERE bm.c_dy IN (
        SELECT c_dy FROM DYNASTIES 
        WHERE c_dynasty_chn LIKE '%唐%'
        AND c_start_year >= 618 
        AND c_end_year <= 907
    )
    AND bm.c_birthyear IS NOT NULL
    ORDER BY bm.c_birthyear
    """
    
    cur = con.execute(query)
    rows = cur.fetchall()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'cbdb_id', 'name', 'courtesy_name', 'birth_year', 'death_year',
            'dynasty', 'native_place_id', 'gender'
        ])
        writer.writerows(rows)
    
    return len(rows)


def extract_relationships(con: sqlite3.Connection, output_path: Path) -> int:
    """Extract relationships from ASSOC_DATA."""
    query = """
    SELECT 
        ad.c_personid as person1_cbdb_id,
        ad.c_assoc_personid as person2_cbdb_id,
        ac.c_assoc_desc_chn as relationship_type,
        ad.c_assoc_type_code as relationship_subtype,
        ad.c_notes as evidence,
        ad.c_assoc_id as cbdb_assoc_id
    FROM ASSOC_DATA ad
    LEFT JOIN ASSOC_CODES ac ON ad.c_assoc_code = ac.c_assoc_code
    WHERE ad.c_personid IN (
        SELECT c_personid FROM BIOG_MAIN 
        WHERE c_dy IN (
            SELECT c_dy FROM DYNASTIES 
            WHERE c_dynasty_chn LIKE '%唐%'
            AND c_start_year >= 618 
            AND c_end_year <= 907
        )
    )
    ORDER BY ad.c_personid
    """
    
    cur = con.execute(query)
    rows = cur.fetchall()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'person1_cbdb_id', 'person2_cbdb_id', 'relationship_type',
            'relationship_subtype', 'evidence', 'cbdb_assoc_id'
        ])
        writer.writerows(rows)
    
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Tang dynasty data from CBDB")
    parser.add_argument(
        "--db", type=Path,
        default=Path("/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/cbdb202409.db"),
        help="Path to CBDB SQLite database"
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("data/processed"),
        help="Output directory for CSV files"
    )
    args = parser.parse_args()
    
    if not args.db.exists():
        print(f"Error: Database not found: {args.db}")
        return 1
    
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    con = sqlite3.connect(str(args.db))
    
    people_path = args.output_dir / "people.csv"
    relationships_path = args.output_dir / "relationships.csv"
    
    n_people = extract_people(con, people_path)
    print(f"Extracted {n_people} people to {people_path}")
    
    n_rels = extract_relationships(con, relationships_path)
    print(f"Extracted {n_rels} relationships to {relationships_path}")
    
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
