#!/usr/bin/env python3
"""
从 CHGIS v5 Hartwell「中国宏观政区」面图层导出 SVG 预览。

用户约定（与文件名一致）：
  - v5_0741_chin_chn_0741_p.shp ：741 年前后；筛 H_SUP_PROV ≈ Tang → 唐疆域示意
  - v5_1080_chin_chn_1080_l.shp ：1080；含北宋、辽、西夏等（按 H_SUP_PROV 上色）
  - v5_1200_chin_chn_1200_l.shp ：1200；含金、南宋、西夏等

说明：本仓库里 *_l 图层在 pyshp 中报告为 Polygon（非折线），按面绘制。

依赖：pyshp、shapely

用法（仓库根）：
  python3 scripts/preview_hartwell_chin_maps.py
输出：CHGIS/preview/hartwell_*.svg
"""
from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import shapefile
    from shapely.geometry import Polygon
except ImportError as e:
    print("请先安装: pip install pyshp shapely", file=sys.stderr)
    raise SystemExit(1) from e

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "CHGIS" / "v5_Hartwell"
OUT_DIR = ROOT / "CHGIS" / "preview"

SIMPLIFY = 0.05

# 宏观政权上色（其余灰色）
PALETTE: dict[str, str] = {
    "tang dynasty": "#2e86ab",
    "song dynasty": "#a23b72",
    "liao dynasty": "#6c757d",
    "jin dynasty": "#c1121f",
    "xixia": "#f4a261",
    "dali": "#2a9d8f",
    "tufan tribes": "#8d99ae",
    "jiannan tribes": "#8d99ae",
    "tibetan tribes": "#8d99ae",
    "kara-qitay": "#e9c46a",
    "heihan": "#adb5bd",
    "yutian": "#adb5bd",
    "xizhou huihu": "#adb5bd",
    "dongping fu": "#adb5bd",
    "": "#dee2e6",
}


def norm_sup(v: object) -> str:
    return str(v or "").strip().lower()


def color_for(sup: str) -> str:
    return PALETTE.get(norm_sup(sup), "#ced4da")


def shape_to_polygons(shp: shapefile.Shape) -> list[Polygon]:
    if shp.shapeType != 5:
        return []
    parts, pts = shp.parts, shp.points
    out: list[Polygon] = []
    for j, prt in enumerate(parts):
        end = parts[j + 1] if j + 1 < len(parts) else len(pts)
        ring = [tuple(pts[k]) for k in range(prt, end)]
        if len(ring) < 4:
            continue
        try:
            out.append(Polygon(ring))
        except Exception:
            continue
    return out


def load_rows(shp_path: Path, encoding: str = "latin1"):
    r = shapefile.Reader(str(shp_path.with_suffix("")), encoding=encoding)
    names = [f[0] for f in r.fields[1:]]
    if "H_SUP_PROV" not in names:
        raise SystemExit(f"缺少字段 H_SUP_PROV: {shp_path}")
    si = names.index("H_SUP_PROV")
    rows: list[tuple[str, list[Polygon]]] = []
    for i in range(len(r)):
        sup = str(r.record(i)[si])
        polys = shape_to_polygons(r.shape(i))
        if polys:
            rows.append((sup, polys))
    return rows


def bounds(rows: list[tuple[str, list[Polygon]]]) -> tuple[float, float, float, float]:
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for _, polys in rows:
        for p in polys:
            a, b, c, d = p.bounds
            minx, miny = min(minx, a), min(miny, b)
            maxx, maxy = max(maxx, c), max(maxy, d)
    return minx, miny, maxx, maxy


def iter_poly_rings(poly: Polygon):
    yield poly.exterior.coords
    for inn in poly.interiors:
        yield inn.coords


def write_svg(path: Path, title: str, subtitle: str, rows: list[tuple[str, list[Polygon]]]) -> None:
    if not rows:
        raise ValueError("no rows")
    minx, miny, maxx, maxy = bounds(rows)
    pad = max((maxx - minx), (maxy - miny)) * 0.05 or 0.5
    minx -= pad
    maxx += pad
    miny -= pad
    maxy += pad
    w = maxx - minx
    h = maxy - miny

    def tx(x: float) -> float:
        return (x - minx) / w * 1000.0

    def ty(y: float) -> float:
        return (maxy - y) / h * 720.0

    svg = ET.Element(
        "svg",
        {"xmlns": "http://www.w3.org/2000/svg", "width": "1000", "height": "780", "viewBox": "0 0 1000 780"},
    )
    ET.SubElement(svg, "title").text = title
    ET.SubElement(svg, "desc").text = subtitle
    ET.SubElement(svg, "rect", {"x": "0", "y": "0", "width": "1000", "height": "780", "fill": "#fafafa"})
    ET.SubElement(svg, "text", {"x": "14", "y": "34", "font-size": "20", "fill": "#111"}).text = title
    ET.SubElement(svg, "text", {"x": "14", "y": "58", "font-size": "13", "fill": "#555"}).text = subtitle

    yl = 78
    for label in sorted({norm_sup(s) for s, _ in rows if norm_sup(s)}):
        fill = color_for(label)
        ET.SubElement(svg, "rect", {"x": "14", "y": str(yl), "width": "12", "height": "12", "fill": fill, "stroke": "#333", "stroke-width": "0.3"})
        ET.SubElement(svg, "text", {"x": "32", "y": str(yl + 11), "font-size": "11", "fill": "#333"}).text = label or "(empty)"
        yl += 16

    g0 = ET.SubElement(svg, "g", {"stroke": "#222", "stroke-width": "0.25"})
    for sup, polys in rows:
        fill = color_for(sup)
        g = ET.SubElement(g0, "g", {"fill": fill, "fill-opacity": "0.82"})
        for poly in polys:
            gp = poly.simplify(SIMPLIFY, preserve_topology=True)
            if gp.geom_type != "Polygon" or gp.is_empty:
                continue
            for ring in iter_poly_rings(gp):
                pts = " ".join(f"{tx(x):.2f},{ty(y):.2f}" for x, y in ring)
                ET.SubElement(g, "polygon", {"points": pts})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(svg).write(path, encoding="utf-8", xml_declaration=True)
    print("wrote", path)


def main() -> None:
    p741 = HW / "v5_0741_chin_chn_0741_p.shp"
    p1080 = HW / "v5_1080_chin_chn_1080_l.shp"
    p1200 = HW / "v5_1200_chin_chn_1200_l.shp"
    for p in (p741, p1080, p1200):
        if not p.exists():
            print("missing", p, file=sys.stderr)
            raise SystemExit(2)

    rows741 = load_rows(p741)
    tang = [(s, ps) for s, ps in rows741 if "tang" in norm_sup(s)]
    write_svg(
        OUT_DIR / "hartwell_0741_tang_H_SUP_PROV.svg",
        "Hartwell v5 · 741 中国面（H_SUP_PROV 含 tang）",
        "字段名是 H_SUP_PROV（不是 H_SUB_PROV）；另含少量部落面可另筛",
        tang,
    )

    write_svg(
        OUT_DIR / "hartwell_1080_chin_multistate.svg",
        "Hartwell v5 · 1080 中国（北宋 / 辽 / 西夏等，按 H_SUP_PROV）",
        "同一图层内含多政权；上色按 H_SUP_PROV",
        load_rows(p1080),
    )

    write_svg(
        OUT_DIR / "hartwell_1200_chin_multistate.svg",
        "Hartwell v5 · 1200 中国（金 / 南宋 / 西夏等，按 H_SUP_PROV）",
        "1200 为金主导版图 + 南宋等；上色按 H_SUP_PROV",
        load_rows(p1200),
    )


if __name__ == "__main__":
    main()
