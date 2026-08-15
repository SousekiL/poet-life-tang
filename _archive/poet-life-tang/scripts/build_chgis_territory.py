#!/usr/bin/env python3
"""
从本地 CHGIS v6 州级时间序列面（v6_time_pref_pgn_gbk_wgs84）生成 viz 用 GeoJSON。

依赖：pip install pyshp shapely

用法（在仓库根目录）：
  python3 scripts/build_chgis_territory.py

默认切片年：唐 741、北宋 1100、南宋 1200（可在下方常量修改）。
数据路径：CHGIS/v6_time_pref_pgn_gbk_wgs84.zip（首次运行会解压到 CHGIS/extracted/）。
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

try:
    import shapefile
    from shapely.geometry import MultiPolygon, Polygon, mapping
    from shapely.ops import unary_union
except ImportError as e:
    print("请先安装依赖: pip install pyshp shapely", file=sys.stderr)
    raise SystemExit(1) from e

ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "CHGIS" / "v6_time_pref_pgn_gbk_wgs84.zip"
SHP_STEM = "v6_time_pref_pgn_gbk_wgs84"
EXTRACT_DIR = ROOT / "CHGIS" / "extracted"
SHP_PATH = EXTRACT_DIR / f"{SHP_STEM}.shp"

# 切片年（CHGIS 记录：BEG_YR <= year <= END_YR 的州面参与合并）
YEAR_TANG = 741
YEAR_BEISONG = 1100
YEAR_NANSONG = 1200

SIMPLIFY_TOL = 0.035  # 度，约 3–4 km，兼顾体积与轮廓

CITATION = (
    "CHGIS, Version: 6. (c) Fairbank Center for Chinese Studies of Harvard University "
    "and the Center for Historical Geographical Studies at Fudan University, 2016. "
    "Layer: v6_time_pref_pgn (prefecture time-series polygons, WGS84)."
)


def ensure_shapefile() -> None:
    if SHP_PATH.exists():
        return
    if not ZIP_PATH.exists():
        raise FileNotFoundError(
            f"未找到 {ZIP_PATH}，请将 CHGIS v6_time_pref_pgn_gbk_wgs84.zip 放在 CHGIS/ 目录下。"
        )
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(EXTRACT_DIR)


def polys_valid_in_year(reader: shapefile.Reader, year: int) -> list[Polygon]:
    names = [f[0] for f in reader.fields[1:]]
    bi = names.index("BEG_YR")
    ei = names.index("END_YR")
    out: list[Polygon] = []
    for i in range(len(reader)):
        rec = reader.record(i)
        if rec[bi] > year or rec[ei] < year:
            continue
        shp = reader.shape(i)
        if shp.shapeType != 5:  # Polygon
            continue
        parts = shp.parts
        pts = shp.points
        polys: list[Polygon] = []
        for j, prt in enumerate(parts):
            end = parts[j + 1] if j + 1 < len(parts) else len(pts)
            ring = [tuple(pts[k]) for k in range(prt, end)]
            if len(ring) < 4:
                continue
            try:
                polys.append(Polygon(ring))
            except Exception:
                continue
        if not polys:
            continue
        out.append(unary_union(polys) if len(polys) > 1 else polys[0])
    return out


def merge_and_simplify(polys: list[Polygon]) -> Polygon | MultiPolygon:
    u = unary_union(polys)
    if not u.is_valid:
        u = u.buffer(0)
    return u.simplify(SIMPLIFY_TOL, preserve_topology=True)


def write_geojson(path: Path, name: str, note: str, year: int, geom) -> None:
    fc = {
        "type": "FeatureCollection",
        "properties": {
            "name": name,
            "reference": CITATION,
            "source_year": year,
            "note": note,
        },
        "features": [{"type": "Feature", "properties": {"year": year}, "geometry": mapping(geom)}],
    }
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print("wrote", path, "geom", geom.geom_type)


def main() -> None:
    ensure_shapefile()
    r = shapefile.Reader(str(SHP_PATH.with_suffix("")), encoding="gbk")

    pt = polys_valid_in_year(r, YEAR_TANG)
    pb = polys_valid_in_year(r, YEAR_BEISONG)
    pn = polys_valid_in_year(r, YEAR_NANSONG)
    print("prefecture count:", len(pt), len(pb), len(pn), "for years", YEAR_TANG, YEAR_BEISONG, YEAR_NANSONG)

    (ROOT / "viz" / "data").mkdir(parents=True, exist_ok=True)

    write_geojson(
        ROOT / "viz" / "data" / "tang_territory.geojson",
        "唐（CHGIS 州面合并）",
        f"合并 BEG_YR≤{YEAR_TANG}≤END_YR 的州级多边形后简化；为行政辖境拼合，非「帝国宣称」边界。",
        YEAR_TANG,
        merge_and_simplify(pt),
    )
    write_geojson(
        ROOT / "viz" / "data" / "song_territory_beisong.geojson",
        "北宋（CHGIS 州面合并）",
        f"合并 BEG_YR≤{YEAR_BEISONG}≤END_YR 的州级多边形后简化。",
        YEAR_BEISONG,
        merge_and_simplify(pb),
    )
    write_geojson(
        ROOT / "viz" / "data" / "song_territory_nansong.geojson",
        "南宋（CHGIS 州面合并）",
        f"合并 BEG_YR≤{YEAR_NANSONG}≤END_YR 的州级多边形后简化。",
        YEAR_NANSONG,
        merge_and_simplify(pn),
    )


if __name__ == "__main__":
    main()
