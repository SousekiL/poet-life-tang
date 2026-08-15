#!/usr/bin/env python3
"""
Generate static network visualization.

Reads from data/processed/network.json and generates a static network graph.

Usage:
    python viz/static/generate_network.py [--input PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd


def load_network(network_path: Path) -> nx.Graph:
    """Load network from JSON file."""
    with open(network_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    G = nx.Graph()
    
    for node in data['nodes']:
        G.add_node(node['id'], **node)
    
    for edge in data['edges']:
        G.add_edge(edge['source'], edge['target'], **edge)
    
    return G


def generate_network_plot(G: nx.Graph, output_path: Path) -> None:
    """Generate static network plot."""
    fig, ax = plt.subplots(figsize=(16, 12))
    
    # Calculate node sizes based on degree
    degrees = dict(G.degree())
    max_degree = max(degrees.values()) if degrees else 1
    node_sizes = [300 + 2000 * (degrees[n] / max_degree) for n in G.nodes()]
    
    # Color nodes by degree
    node_colors = [degrees[n] for n in G.nodes()]
    
    # Layout
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    # Draw edges
    nx.draw_networkx_edges(
        G, pos, 
        alpha=0.3, 
        edge_color='gray',
        width=0.5,
        ax=ax
    )
    
    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos,
        node_size=node_sizes,
        node_color=node_colors,
        cmap=plt.colormaps['YlOrRd'],
        alpha=0.8,
        ax=ax
    )
    
    # Draw labels for high-degree nodes
    high_degree_nodes = {n: G.nodes[n].get('name', str(n)) 
                        for n in G.nodes() 
                        if degrees[n] >= max_degree * 0.3}
    
    nx.draw_networkx_labels(
        G, pos,
        labels=high_degree_nodes,
        font_size=8,
        font_weight='bold',
        ax=ax
    )
    
    ax.set_title('Tang Dynasty Social Network', fontsize=16, fontweight='bold')
    ax.axis('off')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved network plot to {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate static network visualization")
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/processed/network.json"),
        help="Input network JSON file"
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("viz/static/network.png"),
        help="Output image file"
    )
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Error: Network file not found: {args.input}")
        return 1
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    G = load_network(args.input)
    print(f"Loaded network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    generate_network_plot(G, args.output)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
