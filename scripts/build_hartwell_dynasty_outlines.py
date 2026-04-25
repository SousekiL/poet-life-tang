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
输出：viz/data/hartwell_dynasty_outlines.json（v4：borderHard / borderSoft 线 + borderChinaFade 面；
      与今中国陆地边界重合的朝代外缘从线中剔除，以外侧淡色环暗示疆域可能外延）。
      可选将阿里云 100000 边界存为 viz/data/china_outline_land.geojson 以便离线构建。
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
    from shapely.geometry import GeometryCollection, mapping, MultiPolygon, Polygon, shape
    from shapely.ops import linemerge, transform as shp_transform, unary_union
except ImportError as e:
    print("请先安装: pip install pyshp shapely pyproj", file=sys.stderr)
    raise SystemExit(1) from e

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "CHGIS" / "v5_Hartwell"
OUT = ROOT / "viz" / "data" / "hartwell_dynasty_outlines.json"
# 与 viz/app.js 同源；构建时优先读本地，缺失则尝试网络拉取（失败则不做国界重合处理）
CHINA_OUTLINE_LOCAL = ROOT / "viz" / "data" / "china_outline_land.geojson"
CHINA_OUTLINE_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"

SIMPLIFY_DEG = 0.045
# 度；约 2m 量级，用于弥合相邻政区面之间的拓扑缝隙以便 unary_union 成块
SNAP_BUFFER_DEG = 2.2e-5

CITATION = (
    "CHGIS Version 5, Hartwell China Historical GIS dataset. "
    "Dynasty-level polygons merged from H_SUP_PROV; not modern international boundaries. "
    "Academic / non-commercial use per CHGIS license."
)

# 英文键（小写）→ 展示名 + 线/填色（与 preview_hartwell 接近）
# 交界处保留清晰「硬线」的政权对（均为本切片中出现的 H_SUP_PROV 合并面）；
# 与大理、吐蕃、西辽等相邻的一侧归为 borderSoft，用宽线+低不透明度弱化。
CORE_BORDER_KEYS: frozenset[str] = frozenset(
    {"song dynasty", "liao dynasty", "jin dynasty", "xixia"}
)

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


def merged_geoms_by_key(
    groups: dict[str, list[Polygon]],
    transformer: Transformer,
    *,
    key_filter: Callable[[str], bool] | None = None,
) -> dict[str, Polygon | MultiPolygon]:
    """各 dynastyKey 合并后的面（WGS84），用于计算硬/软边界。"""
    out: dict[str, Polygon | MultiPolygon] = {}
    for key, polys in sorted(groups.items()):
        if key_filter is not None and not key_filter(key):
            continue
        merged = merge_group(polys, transformer)
        if merged is None or merged.is_empty:
            continue
        out[key] = merged
    return out


def geometry_to_line_fc(geom) -> dict:
    """压平为仅含 LineString 的 FeatureCollection（供前端线层使用）。"""
    feats: list[dict] = []

    def add_ls(g) -> None:
        feats.append({"type": "Feature", "properties": {}, "geometry": mapping(g)})

    def walk(g) -> None:
        if g is None or g.is_empty:
            return
        gt = g.geom_type
        if gt == "LineString":
            add_ls(g)
        elif gt == "MultiLineString":
            for seg in g.geoms:
                add_ls(seg)
        elif gt == "GeometryCollection":
            for part in g.geoms:
                walk(part)

    walk(geom)
    return {"type": "FeatureCollection", "features": feats}


def empty_feature_collection() -> dict:
    return {"type": "FeatureCollection", "features": []}


def geometry_to_polygon_fc(geom, props: dict | None = None) -> dict:
    """Polygon / MultiPolygon → FeatureCollection（用于国界外延渐变面）。"""
    base = dict(props or {})
    feats: list[dict] = []

    def add_poly(poly: Polygon) -> None:
        feats.append({"type": "Feature", "properties": dict(base), "geometry": mapping(poly)})

    def walk(g) -> None:
        if g is None or g.is_empty:
            return
        gt = g.geom_type
        if gt == "Polygon":
            add_poly(g)
        elif gt == "MultiPolygon":
            for p in g.geoms:
                add_poly(p)
        elif gt == "GeometryCollection":
            for part in g.geoms:
                walk(part)

    walk(geom)
    return {"type": "FeatureCollection", "features": feats}


def load_china_land_geometry() -> Polygon | MultiPolygon | None:
    """今中国陆地外廓（WGS84），用于识别 Hartwell 外缘与国界重合处。"""
    raw: dict | None = None
    if CHINA_OUTLINE_LOCAL.exists():
        try:
            raw = json.loads(CHINA_OUTLINE_LOCAL.read_text(encoding="utf-8"))
        except Exception as e:
            print("warn: 读取本地中国轮廓失败:", e, file=sys.stderr)
    if raw is None:
        try:
            import urllib.request

            req = urllib.request.Request(
                CHINA_OUTLINE_URL,
                headers={"User-Agent": "poet-life-tang-hartwell-build/1.0"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print("warn: 拉取中国轮廓失败，borderChinaFade 将跳过:", e, file=sys.stderr)
            return None

    polys: list = []

    def walk_geo(g) -> None:
        if g is None or g.is_empty:
            return
        gt = g.geom_type
        if gt == "Polygon":
            polys.append(g)
        elif gt == "MultiPolygon":
            polys.extend(g.geoms)
        elif gt == "GeometryCollection":
            for part in g.geoms:
                walk_geo(part)

    try:
        if raw["type"] == "FeatureCollection":
            for f in raw.get("features") or []:
                walk_geo(shape(f["geometry"]))
        elif raw["type"] == "Feature":
            walk_geo(shape(raw["geometry"]))
    except Exception as e:
        print("warn: 解析中国 GeoJSON 失败:", e, file=sys.stderr)
        return None
    if not polys:
        return None
    flat: list = []
    for p in polys:
        pv = make_valid(p)
        if pv.is_empty:
            continue
        if pv.geom_type == "Polygon":
            flat.append(pv)
        elif pv.geom_type == "MultiPolygon":
            flat.extend([make_valid(x) for x in pv.geoms if not x.is_empty])
    if not flat:
        return None
    try:
        u = unary_union(flat)
    except Exception:
        u = max(flat, key=lambda x: x.area)
    if u.is_empty:
        return None
    if not u.is_valid:
        u = make_valid(u)
    if u.geom_type == "GeometryCollection":
        u = unary_union([g for g in u.geoms if g.geom_type in ("Polygon", "MultiPolygon")])
    return u


def build_border_layers(
    merged: dict[str, Polygon | MultiPolygon],
    china_land: Polygon | MultiPolygon | None,
) -> tuple[dict, dict, dict]:
    """
    borderHard：两两均属 CORE_BORDER_KEYS 的共用界线。
    borderSoft：其余外廓线；与今中国陆地边界重合的一段会剔除（改由面表示）。
    borderChinaFade：沿「朝代全域外廓 ∩ 中国国界」外侧的窄环面，暗示疆域可能在中国外延续。
    """
    keys_core = sorted(k for k in merged if k in CORE_BORDER_KEYS)
    hard_parts: list = []
    for i, k1 in enumerate(keys_core):
        for k2 in keys_core[i + 1 :]:
            g1, g2 = merged[k1], merged[k2]
            hit = g1.boundary.intersection(g2)
            hit2 = g2.boundary.intersection(g1)
            hit_u = unary_union([hit, hit2])
            if hit_u.is_empty:
                continue
            hard_parts.append(hit_u)
    hard_geom = unary_union(hard_parts) if hard_parts else None
    if hard_geom is not None and not hard_geom.is_empty:
        try:
            hm = linemerge(hard_geom)
            if not hm.is_empty:
                hard_geom = hm
        except Exception:
            pass

    buf_strip = 8e-7
    soft_parts: list = []
    for _key, g in merged.items():
        b = g.boundary
        if hard_geom is not None and not hard_geom.is_empty:
            soft = b.difference(hard_geom.buffer(buf_strip))
        else:
            soft = b
        if not soft.is_empty:
            soft_parts.append(soft)
    soft_geom = unary_union(soft_parts) if soft_parts else None
    if soft_geom is not None and not soft_geom.is_empty:
        try:
            sm = linemerge(soft_geom)
            if not sm.is_empty:
                soft_geom = sm
        except Exception:
            pass

    hard_fc = geometry_to_line_fc(hard_geom)
    fade_fc = empty_feature_collection()
    soft_display_geom = soft_geom

    union_dyn = unary_union(list(merged.values())) if merged else None
    if (
        china_land is not None
        and not china_land.is_empty
        and union_dyn is not None
        and not union_dyn.is_empty
        and soft_geom is not None
        and not soft_geom.is_empty
    ):
        china_bdry = china_land.boundary
        eps = 0.00024
        ub = union_dyn.boundary
        coinc = ub.intersection(china_bdry.buffer(eps))
        if not coinc.is_empty:
            strip = coinc.buffer(eps * 2.0)
            try:
                sd = soft_geom.difference(strip)
            except Exception:
                sd = soft_geom
            if not sd.is_empty:
                try:
                    sm2 = linemerge(sd)
                    if not sm2.is_empty:
                        soft_display_geom = sm2
                    else:
                        soft_display_geom = sd
                except Exception:
                    soft_display_geom = sd

            fade_w = 0.055
            max_halo = 0.26
            try:
                fade = coinc.buffer(fade_w).difference(china_land)
                cap = china_land.buffer(max_halo).difference(china_land)
                fade = fade.intersection(cap)
                if not fade.is_valid:
                    fade = make_valid(fade)
                fade = fade.simplify(0.02, preserve_topology=True)
                if fade.geom_type == "MultiPolygon" and len(fade.geoms) > 1:
                    try:
                        fade = unary_union([g for g in fade.geoms])
                        if not fade.is_valid:
                            fade = make_valid(fade)
                    except Exception:
                        pass
                if not fade.is_empty:
                    fade_fc = geometry_to_polygon_fc(fade, {"kind": "chinaFrameHalo"})
            except Exception:
                pass

    soft_fc = geometry_to_line_fc(soft_display_geom)
    return hard_fc, soft_fc, fade_fc


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

    china_land = load_china_land_geometry()
    if china_land is not None:
        print("loaded China land outline for borderChinaFade")

    m741 = merged_geoms_by_key(g741, transformer, key_filter=lambda k: "tang" in k)
    m1080 = merged_geoms_by_key(g1080, transformer)
    m1200 = merged_geoms_by_key(g1200, transformer)
    b741h, b741s, b741f = build_border_layers(m741, china_land)
    b1080h, b1080s, b1080f = build_border_layers(m1080, china_land)
    b1200h, b1200s, b1200f = build_border_layers(m1200, china_land)

    bundle = {
        "version": 4,
        "citation": CITATION,
        "borderNote": (
            "borderHard：song/liao/jin/xixia 两两相邻的界线；"
            "borderSoft：其余外廓线（与今中国陆地国界重合的一段已从线中剔除）；"
            "borderChinaFade：沿该重合段在中国外侧的窄环面，暗示疆域可能外延（非精确历史边界）。"
        ),
        "snapshots": {
            "tang741": {
                "fromYear": 618,
                "toYear": 907,
                "sourceShp": "CHGIS/v5_Hartwell/v5_0741_chin_chn_0741_p.shp",
                "note": "仅合并 H_SUP_PROV 含 tang 的记录（741 年前后）",
                "geo": build_fc_from_groups(g741, transformer, key_filter=lambda k: "tang" in k),
                "borderHard": b741h,
                "borderSoft": b741s,
                "borderChinaFade": b741f,
            },
            "chin1080": {
                "fromYear": 960,
                "toYear": 1126,
                "sourceShp": "CHGIS/v5_Hartwell/v5_1080_chin_chn_1080_l.shp",
                "note": "按 H_SUP_PROV 合并；空字段记录并入北宋（原数据湖南缺口）",
                "geo": build_fc_from_groups(g1080, transformer),
                "borderHard": b1080h,
                "borderSoft": b1080s,
                "borderChinaFade": b1080f,
            },
            "chin1200": {
                "fromYear": 1127,
                "toYear": 1279,
                "sourceShp": "CHGIS/v5_Hartwell/v5_1200_chin_chn_1200_l.shp",
                "note": "按 H_SUP_PROV 合并；东平府并入金（原数据山东附近缺口）",
                "geo": build_fc_from_groups(g1200, transformer),
                "borderHard": b1200h,
                "borderSoft": b1200s,
                "borderChinaFade": b1200f,
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
