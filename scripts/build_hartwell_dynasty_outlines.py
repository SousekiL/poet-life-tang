#!/usr/bin/env python3
"""
将 CHGIS v5 Hartwell 中国宏观面按 H_SUP_PROV 合并为「朝代外轮廓」（去掉同朝内部的省/府界线），
并投影到 WGS84，供 viz 动态页使用。

切片与年份窗（与 viz/app.js 一致）：
  - tang741：741 面，仅保留 H_SUP_PROV 含 tang → 用于 618–907
  - chin1080：1080 面，按 H_SUP_PROV 合并 → 用于 960–1126
  - chin1200：1200 面，按 H_SUP_PROV 合并 → 用于 1127–1279
  - 907–959 五代十国：本数据未单独切片，页面不叠朝代界

依赖：pyshp、shapely、pyproj

用法（仓库根）：
  python3 scripts/build_hartwell_dynasty_outlines.py
输出：viz/data/hartwell_dynasty_outlines.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable

try:
    import shapefile
    from pyproj import Transformer
    from shapely import make_valid
    from shapely.geometry import mapping, MultiPolygon, Polygon
    from shapely.ops import transform as shp_transform, unary_union
except ImportError as e:
    print("请先安装: pip install pyshp shapely pyproj", file=sys.stderr)
    raise SystemExit(1) from e

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "CHGIS" / "v5_Hartwell"
OUT = ROOT / "viz" / "data" / "hartwell_dynasty_outlines.json"

SIMPLIFY_DEG = 0.045
# 度；约 2m 量级，用于弥合相邻政区面之间的拓扑缝隙以便 unary_union 成块
SNAP_BUFFER_DEG = 2.2e-5

CITATION = (
    "CHGIS Version 5, Hartwell China Historical GIS dataset. "
    "Dynasty-level polygons merged from H_SUP_PROV; not modern international boundaries. "
    "Academic / non-commercial use per CHGIS license."
)

# 英文键（小写）→ 展示名 + 线/填色（与 preview_hartwell 接近）
STYLE: dict[str, tuple[str, str, str]] = {
    "tang dynasty": ("唐", "#1a5276", "#2980b9"),
    "song dynasty": ("宋", "#6c3483", "#a569bd"),
    "liao dynasty": ("辽", "#424949", "#707b7c"),
    "jin dynasty": ("金", "#922b21", "#cb4335"),
    "xixia": ("西夏", "#b9770e", "#f4d03f"),
    "dali": ("大理", "#117864", "#48c9b0"),
    "kara-qitay": ("西辽", "#9a7d0a", "#d4ac0d"),
    "tufan tribes": ("吐蕃诸部", "#566573", "#85929e"),
    "jiannan tribes": ("剑南诸部", "#566573", "#85929e"),
    "tibetan tribes": ("吐蕃诸部", "#566573", "#85929e"),
    "heihan": ("于阗等", "#7f8c8d", "#bdc3c7"),
    "yutian": ("于阗", "#7f8c8d", "#bdc3c7"),
    "xizhou huihu": ("西州回鹘", "#7f8c8d", "#bdc3c7"),
    "dongping fu": ("东平府", "#7f8c8d", "#bdc3c7"),
}


def style_for_key(key: str) -> tuple[str, str, str]:
    if key in STYLE:
        return STYLE[key]
    return (key.title() if key else "其他", "#5d6d7e", "#aeb6bf")


def norm_key(s: object) -> str:
    return str(s or "").strip().lower()


def shape_to_polygons_proj(shp: shapefile.Shape) -> list[Polygon]:
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


def load_grouped(
    path: Path,
    encoding: str = "latin1",
    *,
    treat_empty_h_sup_prov_as: str | None = None,
) -> dict[str, list[Polygon]]:
    """
    treat_empty_h_sup_prov_as:
      v5_1080 中曾有一条湖南境内记录 H_SUP_PROV 为空，若跳过会在北宋版图留下缺口；
      按学界常见处理并入北宋（song dynasty）。
    """
    r = shapefile.Reader(str(path.with_suffix("")), encoding=encoding)
    names = [f[0] for f in r.fields[1:]]
    si = names.index("H_SUP_PROV")
    groups: dict[str, list[Polygon]] = defaultdict(list)
    for i in range(len(r)):
        raw = r.record(i)[si]
        key = norm_key(raw)
        if not key:
            if not treat_empty_h_sup_prov_as:
                continue
            key = treat_empty_h_sup_prov_as
        for poly in shape_to_polygons_proj(r.shape(i)):
            groups[key].append(poly)
    return groups


def merge_group_keys(groups: dict[str, list[Polygon]], src: str, dst: str) -> None:
    """把 src 键下的面并入 dst（用于 1200 东平府并入金）。"""
    if src not in groups:
        return
    polys = groups.pop(src)
    if not polys:
        return
    groups[dst].extend(polys)


def to_wgs84(transformer: Transformer, geom: Polygon | MultiPolygon):
    return shp_transform(lambda x, y: transformer.transform(x, y), geom)


def merge_group(polys: list[Polygon], transformer: Transformer):
    if not polys:
        return None
    wgs_polys = []
    for p in polys:
        g = to_wgs84(transformer, p)
        if not g.is_valid:
            g = make_valid(g)
        wgs_polys.append(g)
    snapped = [g.buffer(SNAP_BUFFER_DEG) for g in wgs_polys]
    u = unary_union(snapped).buffer(-SNAP_BUFFER_DEG)
    if u.is_empty:
        u = unary_union(wgs_polys)
    if not u.is_valid:
        u = make_valid(u)
    u = u.simplify(SIMPLIFY_DEG, preserve_topology=True)
    if not u.is_valid:
        u = make_valid(u)
    return u


def geom_to_features(geom, props: dict) -> list[dict]:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        return []
    return [{"type": "Feature", "properties": props, "geometry": mapping(geom)}]


def build_fc_from_groups(
    groups: dict[str, list[Polygon]],
    transformer: Transformer,
    *,
    key_filter: Callable[[str], bool] | None = None,
) -> dict:
    feats: list[dict] = []
    for key, polys in sorted(groups.items()):
        if key_filter is not None and not key_filter(key):
            continue
        label, stroke, fill = style_for_key(key)
        merged = merge_group(polys, transformer)
        props = {
            "dynastyKey": key,
            "label": label,
            "stroke": stroke,
            "fill": fill,
            "fillOpacity": 0.07,
            "weight": 1.35,
        }
        feats.extend(geom_to_features(merged, props))
    return {"type": "FeatureCollection", "features": feats}


def main() -> None:
    p741 = HW / "v5_0741_chin_chn_0741_p.shp"
    p1080 = HW / "v5_1080_chin_chn_1080_l.shp"
    p1200 = HW / "v5_1200_chin_chn_1200_l.shp"
    prj = p741.with_suffix(".prj")
    for p in (p741, p1080, p1200, prj):
        if not p.exists():
            print("缺少文件:", p, file=sys.stderr)
            raise SystemExit(2)

    from pyproj import CRS

    crs = CRS.from_wkt(prj.read_text(encoding="utf-8"))
    epsg = crs.to_epsg()
    if not epsg:
        raise SystemExit("无法从 .prj 解析 EPSG")
    transformer = Transformer.from_crs(epsg, 4326, always_xy=True)

    g741 = load_grouped(p741)
    g1080 = load_grouped(p1080, treat_empty_h_sup_prov_as="song dynasty")
    g1200 = load_grouped(p1200)
    # 1200：东平府在数据中单列一类，地理上属金朝河北东路一带，并入金以免山东南侧出现「飞地缺口」
    merge_group_keys(g1200, "dongping fu", "jin dynasty")

    bundle = {
        "version": 2,
        "citation": CITATION,
        "snapshots": {
            "tang741": {
                "fromYear": 618,
                "toYear": 907,
                "sourceShp": "CHGIS/v5_Hartwell/v5_0741_chin_chn_0741_p.shp",
                "note": "仅合并 H_SUP_PROV 含 tang 的记录（741 年前后）",
                "geo": build_fc_from_groups(g741, transformer, key_filter=lambda k: "tang" in k),
            },
            "chin1080": {
                "fromYear": 960,
                "toYear": 1126,
                "sourceShp": "CHGIS/v5_Hartwell/v5_1080_chin_chn_1080_l.shp",
                "note": "按 H_SUP_PROV 合并；空字段记录并入北宋（原数据湖南缺口）",
                "geo": build_fc_from_groups(g1080, transformer),
            },
            "chin1200": {
                "fromYear": 1127,
                "toYear": 1279,
                "sourceShp": "CHGIS/v5_Hartwell/v5_1200_chin_chn_1200_l.shp",
                "note": "按 H_SUP_PROV 合并；东平府并入金（原数据山东附近缺口）",
                "geo": build_fc_from_groups(g1200, transformer),
            },
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    sz = OUT.stat().st_size
    print("wrote", OUT, f"({sz/1024:.1f} KiB)")
    for sid, snap in bundle["snapshots"].items():
        n = len(snap["geo"]["features"])
        print(" ", sid, "features", n)


if __name__ == "__main__":
    main()
