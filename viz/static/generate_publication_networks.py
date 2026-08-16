#!/usr/bin/env python3
"""Generate publication-ready overview and focal network figures.

The figures use one shared visual grammar:

* node colour and shape encode gender;
* edge colour and line style encode relationship type;
* node area encodes the number of primary relationships.

Only the largest connected component is plotted. The underlying CSV files are
not modified. All outputs use a fixed 3:2 canvas at 300 DPI for reproducibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch
import networkx as nx
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PERSONS_PATH = ROOT / "data" / "persons_combined.csv"
RELATIONSHIPS_PATH = ROOT / "data" / "relationships_combined.csv"
OUTPUT_DIR = ROOT / "docs" / "images" / "publication"

BG = "#0f141a"
PANEL = "#151b22"
TEXT = "#f1eee6"
TEXT_SECONDARY = "#aeb7c2"
RULE = "#303945"
MALE = "#5b9bd5"
FEMALE = "#e56b6f"
FOCUS = "#f1c75b"

RELATION_STYLES = {
    "KIN": ("亲属", "#d7a928", "solid"),
    "TEACHER_STUDENT": ("师生", "#9f86d9", "dashed"),
    "COLLEAGUE": ("同僚", "#27a8b8", "dashdot"),
    "LITERARY": ("文学", "#4da66d", "dotted"),
    "POLITICAL": ("政治", "#d98242", (0, (5, 2))),
    "SOCIAL": ("社交", "#8993a1", "solid"),
}

OVERVIEW_LABELS = [
    "李白", "杜甫", "王維", "高適", "白居易", "劉禹錫", "元稹",
    "李商隱", "杜牧", "韓愈", "柳宗元", "孟郊", "賈島", "張說",
    "李隆基（唐玄宗）",
]


@dataclass(frozen=True)
class FigureSpec:
    filename: str
    title: str
    subtitle: str
    centers: tuple[str, ...] = ()
    seed: int = 42


FIGURES = [
    FigureSpec(
        "00_overview_with_legend.png",
        "唐代重要人物社會關係網絡",
        "679 位人物 · 2,279 條主要關係｜僅呈現最大連通網絡",
    ),
    FigureSpec(
        "01_lidu_with_legend.png",
        "李白與杜甫：盛唐詩歌網絡",
        "兩位詩人及其直接關係人物；保留區域內部的全部主要關係",
        ("李白", "杜甫"),
        51,
    ),
    FigureSpec(
        "02_wanggao_with_legend.png",
        "王維與高適：盛唐交遊網絡",
        "兩位詩人及其直接關係人物；保留區域內部的全部主要關係",
        ("王維", "高適"),
        67,
    ),
    FigureSpec(
        "03_bailiu_with_legend.png",
        "白居易與劉禹錫：中唐詩友網絡",
        "兩位詩人及其直接關係人物；保留區域內部的全部主要關係",
        ("白居易", "劉禹錫"),
        83,
    ),
    FigureSpec(
        "04_xiaolidu_with_legend.png",
        "李商隱與杜牧：晚唐「小李杜」網絡",
        "兩位詩人及其直接關係人物；保留區域內部的全部主要關係",
        ("李商隱", "杜牧"),
        97,
    ),
    FigureSpec(
        "05_hanliu_with_legend.png",
        "韓愈與柳宗元：中唐文壇網絡",
        "兩位文學家及其直接關係人物；保留區域內部的全部主要關係",
        ("韓愈", "柳宗元"),
        113,
    ),
    FigureSpec(
        "06_yuanbai_with_legend.png",
        "元稹與白居易：元白詩派網絡",
        "兩位詩人及其直接關係人物；保留區域內部的全部主要關係",
        ("元稹", "白居易"),
        131,
    ),
]


LISONG_PATH = "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/6372627020b45393e500bb1661c460d4a93aff49.asset/AssetData/LiSongPro.ttf"
HIRAGINO_SANS_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_SERIF = FontProperties(fname=LISONG_PATH)
FONT_SERIF_BOLD = FontProperties(fname=LISONG_PATH, weight="bold")
FONT_SANS = FontProperties(fname=HIRAGINO_SANS_PATH)
FONT_SANS_BOLD = FontProperties(fname=HIRAGINO_SANS_PATH, weight="semibold")


def clean_name(name: str) -> str:
    return str(name).split("（", 1)[0]


def node_area(degree: int) -> float:
    """Matplotlib marker area in pt²; consistent across every figure."""
    return 18 + 16 * (max(degree, 1) ** 0.72)


def load_main_network() -> tuple[nx.Graph, pd.DataFrame, pd.DataFrame]:
    persons = pd.read_csv(PERSONS_PATH)
    relationships = pd.read_csv(RELATIONSHIPS_PATH)
    relationships = relationships[relationships["primary_rel"].eq(1)].copy()

    graph = nx.Graph()
    for row in persons.itertuples(index=False):
        graph.add_node(
            int(row.c_personid),
            name=row.name_chn,
            female=bool(row.is_female),
            role=row.role,
        )
    for row in relationships.itertuples(index=False):
        graph.add_edge(
            int(row.source_id),
            int(row.target_id),
            rel_type=row.rel_type,
            layout_weight=0.5 + float(row.weight),
        )

    main_ids = max(nx.connected_components(graph), key=len)
    graph = graph.subgraph(main_ids).copy()
    persons = persons[persons["c_personid"].isin(main_ids)].copy()
    relationships = relationships[
        relationships["source_id"].isin(main_ids)
        & relationships["target_id"].isin(main_ids)
    ].copy()
    return graph, persons, relationships


def compact_layout(graph: nx.Graph, seed: int) -> dict[int, np.ndarray]:
    count = max(graph.number_of_nodes(), 1)
    return nx.spring_layout(
        graph,
        k=1.15 / np.sqrt(count),
        iterations=450,
        seed=seed,
        weight="layout_weight",
        scale=1.0,
        method="energy",
        gravity=2.2,
    )


def focal_graph(
    graph: nx.Graph,
    name_to_id: dict[str, int],
    center_names: tuple[str, ...],
    seed: int,
) -> tuple[nx.Graph, dict[int, np.ndarray], list[int]]:
    center_ids = [name_to_id[name] for name in center_names]
    selected = set(center_ids)
    for center_id in center_ids:
        selected.update(graph.neighbors(center_id))
    subgraph = graph.subgraph(selected).copy()
    for source, target in subgraph.edges:
        multiplier = 2.2 if source in center_ids or target in center_ids else 1.0
        subgraph[source][target]["layout_weight"] *= multiplier

    initial = nx.spring_layout(
        subgraph,
        k=1.2 / np.sqrt(max(subgraph.number_of_nodes(), 1)),
        iterations=80,
        seed=seed,
        weight="layout_weight",
    )
    if len(center_ids) == 2:
        initial[center_ids[0]] = np.array([-0.22, 0.0])
        initial[center_ids[1]] = np.array([0.22, 0.0])
    positions = nx.spring_layout(
        subgraph,
        pos=initial,
        fixed=center_ids,
        k=1.35 / np.sqrt(max(subgraph.number_of_nodes(), 1)),
        iterations=400,
        seed=seed,
        weight="layout_weight",
    )
    positions = nx.rescale_layout_dict(positions, scale=1.0)
    return subgraph, positions, center_ids


def set_plot_limits(ax: plt.Axes, positions: dict[int, np.ndarray]) -> None:
    values = np.array(list(positions.values()))
    x_min, y_min = values.min(axis=0)
    x_max, y_max = values.max(axis=0)
    x_pad = max((x_max - x_min) * 0.10, 0.08)
    y_pad = max((y_max - y_min) * 0.12, 0.08)
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)


def draw_edges(ax: plt.Axes, graph: nx.Graph, positions: dict[int, np.ndarray], focal: bool) -> None:
    width = 0.95 if focal else 0.62
    alpha = 0.48 if focal else 0.25
    draw_order = ["SOCIAL", "COLLEAGUE", "POLITICAL", "LITERARY", "TEACHER_STUDENT", "KIN"]
    for relation_type in draw_order:
        edges = [
            (source, target)
            for source, target, attrs in graph.edges(data=True)
            if attrs.get("rel_type") == relation_type
        ]
        if not edges:
            continue
        _, color, style = RELATION_STYLES[relation_type]
        nx.draw_networkx_edges(
            graph,
            positions,
            edgelist=edges,
            edge_color=color,
            style=style,
            width=width,
            alpha=alpha,
            ax=ax,
        )


def draw_nodes(
    ax: plt.Axes,
    graph: nx.Graph,
    positions: dict[int, np.ndarray],
    global_degree: dict[int, int],
    center_ids: list[int],
) -> None:
    for female, marker, color in [(False, "o", MALE), (True, "D", FEMALE)]:
        nodes = [node for node in graph if bool(graph.nodes[node].get("female")) == female]
        non_centers = [node for node in nodes if node not in center_ids]
        centers = [node for node in nodes if node in center_ids]
        if non_centers:
            nx.draw_networkx_nodes(
                graph,
                positions,
                nodelist=non_centers,
                node_size=[node_area(global_degree[node]) for node in non_centers],
                node_color=color,
                node_shape=marker,
                edgecolors=BG,
                linewidths=0.45,
                alpha=0.94,
                ax=ax,
            )
        if centers:
            nx.draw_networkx_nodes(
                graph,
                positions,
                nodelist=centers,
                node_size=[node_area(global_degree[node]) * 1.45 for node in centers],
                node_color=color,
                node_shape=marker,
                edgecolors=FOCUS,
                linewidths=2.1,
                alpha=1.0,
                ax=ax,
            )


def rectangles_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def draw_labels(
    fig: plt.Figure,
    ax: plt.Axes,
    graph: nx.Graph,
    positions: dict[int, np.ndarray],
    label_ids: list[int],
    global_degree: dict[int, int],
    center_ids: list[int],
    focal: bool,
) -> None:
    fig.canvas.draw()
    axes_box = ax.get_window_extent()
    occupied: list[tuple[float, float, float, float]] = []
    font_size = 12.5 if focal else 10.8
    candidates = [
        (0, 10, "center", "bottom"),
        (10, 3, "left", "center"),
        (-10, 3, "right", "center"),
        (9, 9, "left", "bottom"),
        (-9, 9, "right", "bottom"),
        (0, -10, "center", "top"),
        (9, -8, "left", "top"),
        (-9, -8, "right", "top"),
    ]

    for node_id in sorted(label_ids, key=lambda node: global_degree[node], reverse=True):
        label = clean_name(graph.nodes[node_id]["name"])
        anchor_x, anchor_y = ax.transData.transform(positions[node_id])
        width = max(len(label), 2) * font_size * fig.dpi / 72 * 0.96
        height = font_size * fig.dpi / 72 * 1.25
        start = 0 if node_id in center_ids else node_id % len(candidates)
        ordered = candidates[start:] + candidates[:start]
        chosen = ordered[0]
        for candidate in ordered:
            dx, dy, horizontal, vertical = candidate
            px = anchor_x + dx * fig.dpi / 72
            py = anchor_y + dy * fig.dpi / 72
            left = px if horizontal == "left" else px - width if horizontal == "right" else px - width / 2
            bottom = py if vertical == "bottom" else py - height if vertical == "top" else py - height / 2
            rectangle = (left - 3, bottom - 3, left + width + 3, bottom + height + 3)
            within_axes = (
                rectangle[0] >= axes_box.x0
                and rectangle[2] <= axes_box.x1
                and rectangle[1] >= axes_box.y0
                and rectangle[3] <= axes_box.y1
            )
            if within_axes and not any(rectangles_overlap(rectangle, prior) for prior in occupied):
                chosen = candidate
                occupied.append(rectangle)
                break
        dx, dy, horizontal, vertical = chosen
        annotation = ax.annotate(
            label,
            xy=positions[node_id],
            xytext=(dx, dy),
            textcoords="offset points",
            color=FOCUS if node_id in center_ids else TEXT,
            fontsize=font_size + (1.2 if node_id in center_ids else 0),
            fontproperties=FONT_SERIF_BOLD,
            ha=horizontal,
            va=vertical,
            zorder=10,
            arrowprops={"arrowstyle": "-", "color": TEXT_SECONDARY, "lw": 0.45, "alpha": 0.7},
        )
        annotation.set_path_effects([path_effects.withStroke(linewidth=2.6, foreground=BG)])


def draw_legend(fig: plt.Figure) -> None:
    ax = fig.add_axes([0.035, 0.018, 0.93, 0.105])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    panel = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.008,rounding_size=0.015",
        facecolor=PANEL,
        edgecolor=RULE,
        linewidth=0.8,
        transform=ax.transAxes,
    )
    ax.add_patch(panel)

    ax.text(0.02, 0.75, "人物性别", color=TEXT_SECONDARY, fontsize=9.5, fontproperties=FONT_SANS_BOLD)
    for x, marker, color, label in [(0.035, "o", MALE, "男性"), (0.115, "D", FEMALE, "女性")]:
        ax.scatter([x], [0.38], s=58, marker=marker, c=color, edgecolors=BG, linewidths=0.6, zorder=3)
        ax.text(x + 0.018, 0.38, label, va="center", color=TEXT, fontsize=9.5, fontproperties=FONT_SANS)

    ax.plot([0.205, 0.205], [0.14, 0.84], color=RULE, lw=0.8)
    ax.text(0.225, 0.75, "关系类型", color=TEXT_SECONDARY, fontsize=9.5, fontproperties=FONT_SANS_BOLD)
    relation_order = ["KIN", "TEACHER_STUDENT", "COLLEAGUE", "LITERARY", "POLITICAL", "SOCIAL"]
    for index, relation_type in enumerate(relation_order):
        row, column = divmod(index, 3)
        x = 0.225 + column * 0.115
        y = 0.48 - row * 0.30
        label, color, style = RELATION_STYLES[relation_type]
        ax.plot([x, x + 0.035], [y, y], color=color, lw=1.7, linestyle=style)
        ax.text(x + 0.043, y, label, va="center", color=TEXT, fontsize=9.2, fontproperties=FONT_SANS)

    ax.plot([0.57, 0.57], [0.14, 0.84], color=RULE, lw=0.8)
    ax.text(0.59, 0.75, "节点大小", color=TEXT_SECONDARY, fontsize=9.5, fontproperties=FONT_SANS_BOLD)
    for x, degree in [(0.62, 5), (0.72, 25), (0.83, 80)]:
        ax.scatter([x], [0.38], s=node_area(degree), marker="o", c=MALE, edgecolors=BG, linewidths=0.5)
        ax.text(x + 0.028, 0.38, f"{degree} 条", va="center", color=TEXT, fontsize=9.2, fontproperties=FONT_SANS)
    ax.text(0.59, 0.13, "面积 ∝ 主要关系数量", color=TEXT_SECONDARY, fontsize=8.4, fontproperties=FONT_SANS)

    ax.text(
        0.98,
        0.13,
        "资料来源：CBDB｜主关系口径",
        ha="right",
        color=TEXT_SECONDARY,
        fontsize=8.2,
        fontproperties=FONT_SANS,
    )


def label_ids_for_focal(
    graph: nx.Graph,
    center_ids: list[int],
    global_degree: dict[int, int],
    limit: int = 24,
) -> list[int]:
    ranked = sorted(
        graph.nodes,
        key=lambda node: (
            node in center_ids,
            graph.nodes[node].get("role") == "core",
            global_degree[node],
        ),
        reverse=True,
    )
    chosen = list(dict.fromkeys(center_ids + ranked[:limit]))
    return chosen[:limit]


def render_figure(
    graph: nx.Graph,
    positions: dict[int, np.ndarray],
    spec: FigureSpec,
    global_degree: dict[int, int],
    center_ids: list[int],
    label_ids: list[int],
) -> Path:
    fig = plt.figure(figsize=(15, 10), dpi=150, facecolor=BG)
    ax = fig.add_axes([0.035, 0.145, 0.93, 0.765], facecolor=BG)
    ax.axis("off")
    set_plot_limits(ax, positions)
    focal = bool(center_ids)
    draw_edges(ax, graph, positions, focal=focal)
    draw_nodes(ax, graph, positions, global_degree, center_ids)
    draw_labels(fig, ax, graph, positions, label_ids, global_degree, center_ids, focal=focal)

    fig.text(0.04, 0.965, spec.title, color=TEXT, fontsize=24, fontproperties=FONT_SERIF_BOLD, va="top")
    fig.text(0.04, 0.925, spec.subtitle, color=TEXT_SECONDARY, fontsize=11.5, fontproperties=FONT_SANS, va="top")
    draw_legend(fig)

    output_path = OUTPUT_DIR / spec.filename
    fig.savefig(
        output_path,
        dpi=300,
        facecolor=BG,
        edgecolor="none",
        metadata={"Title": spec.title, "Creator": "Tang-networks publication figure generator"},
    )
    plt.close(fig)
    return output_path


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    graph, persons, relationships = load_main_network()
    name_to_id = dict(zip(persons["name_chn"], persons["c_personid"]))
    global_degree = dict(graph.degree())
    overview_positions = compact_layout(graph, FIGURES[0].seed)

    overview_labels = [name_to_id[name] for name in OVERVIEW_LABELS if name in name_to_id]
    output = render_figure(
        graph,
        overview_positions,
        FIGURES[0],
        global_degree,
        [],
        overview_labels,
    )
    print(f"generated {output.relative_to(ROOT)}")

    for spec in FIGURES[1:]:
        subgraph, positions, center_ids = focal_graph(graph, name_to_id, spec.centers, spec.seed)
        label_ids = label_ids_for_focal(subgraph, center_ids, global_degree)
        output = render_figure(
            subgraph,
            positions,
            spec,
            global_degree,
            center_ids,
            label_ids,
        )
        print(
            f"generated {output.relative_to(ROOT)} "
            f"({subgraph.number_of_nodes()} nodes, {subgraph.number_of_edges()} edges)"
        )

    print(
        f"source network: {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} primary relationships; "
        f"CSV rows retained: {len(persons)} persons, {len(relationships)} relationships"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
