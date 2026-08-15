# poet-life-tang

唐宋诗人迁移可视化项目（618–1279）。以交互式地图展示唐、宋诗人生平行迹，叠加 CHGIS Hartwell 历史疆域轮廓，支持时间轴播放、VIP 诗人专题连播与竖屏视频录制。

## 快速开始

```bash
# 前端预览（纯静态，无需构建）
cd viz && python3 -m http.server 8765
# → http://127.0.0.1:8765/index.html         主图
# → http://127.0.0.1:8765/vip-path-trilogy.html  李白→苏轼→李清照专题

# 数据管线（由 sqlite 生成前端 JSON）
python3 scripts/build_tang_trajectories.py

# 重建 Hartwell 朝代外廓
python3 scripts/build_hartwell_dynasty_outlines.py

# 视频录制（需先启动预览服务）
npm install && npx playwright install chromium
npm run record:viz-video -- --seconds 120
```

## 目录结构

```
poet-life-tang/
├── viz/                          # 纯前端（静态 HTML + MapLibre GL JS）
│   ├── index.html                # 主图页面
│   ├── app.js                    # 核心应用逻辑
│   ├── vip-path-trilogy.html     # 李白→苏轼→李清照三人连播专题
│   ├── vip-path-trilogy.js       # 专题脚本
│   ├── liqz-cinematic.html       # 李清照导演版
│   ├── maplibre-liqz-camera-demo.html   # 李清照镜头演示
│   ├── maplibre-sushi-camera-demo.html  # 苏轼镜头演示
│   └── data/
│       ├── trajectories.json             # 诗人轨迹（由 build_tang_trajectories.py 生成）
│       └── hartwell_dynasty_outlines.json # Hartwell 朝代外廓
├── scripts/                      # 数据处理脚本
│   ├── fetch_poetlife.py                # 从 cnkgraph.com 拉取诗人数据
│   ├── build_tang_trajectories.py       # sqlite → trajectories.json
│   ├── build_hartwell_dynasty_outlines.py # Hartwell Shapefile → WGS84 GeoJSON
│   ├── build_chgis_territory.py         # CHGIS v6 → 唐/宋疆域 GeoJSON（可选）
│   ├── preview_chgis_maps.py            # CHGIS 预览 SVG
│   ├── preview_hartwell_chin_maps.py    # Hartwell 预览 SVG
│   ├── validate_trajectory_samples.py   # 轨迹数据校验
│   ├── record-poet-viz-video.mjs        # Playwright 竖屏录制
│   ├── discover_endpoints.md            # cnkgraph API 文档
│   └── trajectory_rules.md              # 轨迹构建规则
├── CHGIS/                        # 中国历史地理信息系统数据
│   ├── extracted/                 # CHGIS v6 州级时序面（Shapefile）
│   ├── v1_Hartwell_2002/          # Hartwell 原始数据（741/1080/1200）
│   ├── v5_Hartwell/               # Hartwell v5 省/府/县边界（~2500 文件）
│   └── preview/                   # SVG/PNG 预览图
├── data/
│   ├── schema.json               # 诗人数据导出 JSON Schema
│   ├── admin/prefecture_overrides.sample.csv  # 府级覆盖样例
│   └── out/                      # API 拉取输出（fetch.log / poetlife_flat.sqlite）
└── output/                       # 视频录制输出
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端地图 | MapLibre GL JS（主图）、Leaflet（部分页面） |
| 前端 | 原生 JavaScript（无 bundler）、Bootstrap CSS |
| 数据处理 | Python 3（pyshp、shapely、pyproj、httpx） |
| GIS 数据 | CHGIS v5/v6、Hartwell Dataset、Shapefile、GeoJSON |
| 视频录制 | Playwright（Node.js） |
| 底图 | Carto Light（无标注） + 阿里云中国省界 |

## 数据来源

- 诗人行迹数据：[唐宋文学编年地图](https://cnkgraph.com/Map/PoetLife)（cnkgraph.com）
- 历史疆域：CHGIS Version 5/6（Hartwell China Historical GIS）
- API 接口文档见 `scripts/discover_endpoints.md`

数据仅限非商业研究与学习用途，批量使用前应联系运营方。

## URL 参数

| 参数 | 效果 |
|------|------|
| `?video=1` | 竖屏录屏模式（隐藏顶栏、VIP dock、HUD） |
| `?autoplay=1` | 自动播放（配合 video 模式） |
| `?mapbox=token` | MapLibre 地形 token（镜头演示页可选） |

## 许可证

本项目基于非商业研究目的创作。诗人数据版权归属 cnkgraph.com / 搜韵网；CHGIS 数据按 CHGIS 许可用于学术/非商业用途。
