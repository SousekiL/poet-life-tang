#!/usr/bin/env python3
"""
从 CHGIS v6 州级时序面（v6_time_pref_pgn_gbk_wgs84）导出 SVG 预览，核对唐/宋是否有面数据。

只扫描 shapefile 一次；多部分要素按环拆成多个 Polygon（不做 unary_union，预览更快）。

依赖：pyshp、shapely

用法（仓库根目录）：
  python3 scripts/preview_chgis_maps.py

输出：CHGIS/preview/*.svg
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
SHP_PATH = ROOT / "CHGIS" / "extracted" / "v6_time_pref_pgn_gbk_wgs84.shp"
OUT_DIR = ROOT / "CHGIS" / "preview"

# 唐 / 宋代表年（与 build_chgis_territory 切片年一致 + 边界年）
YEARS: list[tuple[int, str]] = [
    (618, "tang_618"),
    (741, "tang_741"),
    (907, "tang_907"),
    (960, "song_960"),
    (1100, "song_beisong_1100"),
    (1200, "song_nansong_1200"),
    (1279, "song_1279"),
]

SIMPLIFY_TOL = 0.04  # 度，预览用减点


def shape_to_polygons(shp: shapefile.Shape) -> list[Polygon]:
    if shp.shapeType != 5:
        return []
    parts = shp.parts
    pts = shp.points
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


def load_pref_features(reader: shapefile.Reader) -> list[tuple[int, int, list[Polygon]]]:
    names = [f[0] for f in reader.fields[1:]]
    bi = names.index("BEG_YR")
    ei = names.index("END_YR")
    feats: list[tuple[int, int, list[Polygon]]] = []
    for i in range(len(reader)):
        rec = reader.record(i)
        beg = int(rec[bi])
        end = int(rec[ei])
        polys = shape_to_polygons(reader.shape(i))
        if polys:
            feats.append((beg, end, polys))
    return feats


def polys_for_year(feats: list[tuple[int, int, list[Polygon]]], year: int) -> list[Polygon]:
    out: list[Polygon] = []
    for beg, end, polys in feats:
        if beg > year or end < year:
            continue
        out.extend(polys)
    return out


def bounds_of_polys(polys: list[Polygon]) -> tuple[float, float, float, float]:
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for p in polys:
        a, b, c, d = p.bounds
        minx, miny = min(minx, a), min(miny, b)
        maxx, maxy = max(maxx, c), max(maxy, d)
    return minx, miny, maxx, maxy


def iter_poly_rings(poly: Polygon):
    yield poly.exterior.coords
    for inn in poly.interiors:
        yield inn.coords


def write_svg(path: Path, year: int, polys: list[Polygon]) -> None:
    if not polys:
        raise ValueError("no polygons")
    minx, miny, maxx, maxy = bounds_of_polys(polys)
    pad = max((maxx - minx), (maxy - miny)) * 0.06 or 0.5
    minx -= pad
    maxx += pad
    miny -= pad
    maxy += pad
    w = maxx - minx
    h = maxy - miny

    def tx(x: float) -> float:
        return (x - minx) / w * 1000.0

    def ty(y: float) -> float:
        return (maxy - y) / h * 700.0

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": "1000",
            "height": "760",
            "viewBox": "0 0 1000 760",
        },
    )
    title = ET.SubElement(svg, "title")
    title.text = f"CHGIS v6_time_pref_pgn @ {year}"
    desc = ET.SubElement(svg, "desc")
    desc.text = f"BEG_YR≤{year}≤END_YR；约 {len(polys)} 个多边形环（简化 {SIMPLIFY_TOL}°）"
    ET.SubElement(svg, "rect", {"x": "0", "y": "0", "width": "1000", "height": "760", "fill": "#f6f7fb"})
    g = ET.SubElement(
        svg,
        "g",
        {"fill": "#d4e4f4", "stroke": "#2c3e50", "stroke-width": "0.2", "fill-opacity": "0.9"},
    )
    for poly in polys:
        gpoly = poly.simplify(SIMPLIFY_TOL, preserve_topology=True)
        if gpoly.geom_type != "Polygon" or gpoly.is_empty:
            continue
        for ring in iter_poly_rings(gpoly):
            pts = " ".join(f"{tx(x):.2f},{ty(y):.2f}" for x, y in ring)
            ET.SubElement(g, "polygon", {"points": pts})
    tx_el = ET.SubElement(svg, "text", {"x": "16", "y": "36", "font-size": "22", "fill": "#1a1a1a"})
    tx_el.text = f"CHGIS v6 州级政区面 @ {year} 年"
    tx2 = ET.SubElement(svg, "text", {"x": "16", "y": "62", "font-size": "14", "fill": "#555"})
    tx2.text = "行政辖境示意（非国界）；数据 v6_time_pref_pgn_gbk_wgs84"
    tree = ET.ElementTree(svg)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print("wrote", path, "polys", len(polys))


def main() -> None:
    if not SHP_PATH.exists():
        print(f"缺少 shapefile: {SHP_PATH}\n请将 zip 解压到 CHGIS/extracted/", file=sys.stderr)
        raise SystemExit(2)
    r = shapefile.Reader(str(SHP_PATH.with_suffix("")), encoding="gbk")
    print("loading features…")
    feats = load_pref_features(r)
    print("loaded", len(feats), "records with geometry")
    for year, stem in YEARS:
        polys = polys_for_year(feats, year)
        if not polys:
            print(f"skip {year}: no polygons")
            continue
        write_svg(OUT_DIR / f"{stem}.svg", year, polys)


if __name__ == "__main__":
    main()
