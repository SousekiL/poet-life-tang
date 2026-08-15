#!/usr/bin/env python3
"""
Build network graph from extracted CBDB data.

Reads from data/processed/people.csv and data/processed/relationships.csv,
outputs data/processed/network.json.

Usage:
    python scripts/build_network.py [--input-dir PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import networkx as nx


def build_network(people_path: Path, rels_path: Path) -> nx.Graph:
    """Build network graph from people and relationships data."""
    # Load data
    people = pd.read_csv(people_path)
    rels = pd.read_csv(rels_path)
    
    # Create graph
    G = nx.Graph()
    
    # Add nodes (people)
    for _, person in people.iterrows():
        G.add_node(
            person['cbdb_id'],
            name=person['name'],
            courtesy_name=person.get('courtesy_name', ''),
            birth_year=person.get('birth_year'),
            death_year=person.get('death_year'),
            dynasty=person.get('dynasty', '唐'),
            native_place_id=person.get('native_place_id'),
            gender=person.get('gender')
        )
    
    # Add edges (relationships)
    for _, rel in rels.iterrows():
        p1 = rel['person1_cbdb_id']
        p2 = rel['person2_cbdb_id']
        
        # Only add edge if both nodes exist
        if p1 in G.nodes and p2 in G.nodes:
            G.add_edge(
                p1, p2,
                relationship_type=rel.get('relationship_type', ''),
                relationship_subtype=rel.get('relationship_subtype', ''),
                evidence=rel.get('evidence', ''),
                cbdb_assoc_id=rel.get('cbdb_assoc_id')
            )
    
    return G


def graph_to_json(G: nx.Graph) -> dict:
    """Convert networkx graph to JSON-serializable format."""
    nodes = []
    for node_id, data in G.nodes(data=True):
        nodes.append({
            'id': node_id,
            **data
        })
    
    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({
            'source': u,
            'target': v,
            **data
        })
    
    return {
        'nodes': nodes,
        'edges': edges
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build network from CBDB data")
    parser.add_argument(
        "--input-dir", type=Path,
        default=Path("data/processed"),
        help="Input directory with CSV files"
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/processed/network.json"),
        help="Output JSON file"
    )
    args = parser.parse_args()
    
    people_path = args.input_dir / "people.csv"
    rels_path = args.input_dir / "relationships.csv"
    
    if not people_path.exists():
        print(f"Error: People file not found: {people_path}")
        return 1
    if not rels_path.exists():
        print(f"Error: Relationships file not found: {rels_path}")
        return 1
    
    G = build_network(people_path, rels_path)
    
    # Convert to JSON
    network_data = graph_to_json(G)
    
    # Add metadata
    network_data['metadata'] = {
        'node_count': G.number_of_nodes(),
        'edge_count': G.number_of_edges(),
        'density': nx.density(G),
        'components': nx.number_connected_components(G)
    }
    
    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(network_data, f, ensure_ascii=False, indent=2)
    
    print(f"Network built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"Density: {nx.density(G):.4f}")
    print(f"Connected components: {nx.number_connected_components(G)}")
    print(f"Saved to {args.output}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
