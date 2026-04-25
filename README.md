# poet-life-tang

唐宋诗人迁移可视化项目（618–1279），包含数据抓取、轨迹构建、前端地图播放与视频录制脚本。

## 项目内容

- `scripts/fetch_poetlife.py`：从 `cnkgraph.com` 拉取诗人生平轨迹原始数据，输出 `jsonl/sqlite`。
- `scripts/build_tang_trajectories.py`：把原始库重建为前端消费的 `viz/data/trajectories.json`。
- `scripts/validate_trajectory_samples.py`：做样本诗人轨迹与统计快速校验，输出 `viz/validation_log.txt`。
- `viz/index.html` + `viz/app.js`：Leaflet 前端，可播放 618–1279 时间轴。
- `viz/vip-path-trilogy.html` + `viz/vip-path-trilogy.js`：李白 → 苏轼 → 李清照三人**连续**动态行迹（与主图同型控件），叠 CHGIS Hartwell 朝代外廓；李清照时段在地图**右侧**内嵌全词卡片（篇幅自适应、长词滚动），**仅当当前首之后队列里还有下一首时**暂停时间轴，单首或每段最后一首时时间照常走动；展示时收窄顶栏 `#phaseHud`（`#mapStage.has-poem-dock`）以免与诗词重叠。
- `viz/data/hartwell_dynasty_outlines.json`：Hartwell 朝代线框快照（主图与 trilogy 共用），由 `scripts/build_hartwell_dynasty_outlines.py` 生成；**v4** 起含 `borderHard`、`borderSoft`，以及与今中国国界重合段对应的 **`borderChinaFade`**（国界外淡色面，示意政权范围可能外延；非精确历史边界）。
- `scripts/record-poet-viz-video.mjs`：Playwright 竖屏录制脚本（1080x1920）。
- `CHGIS/`：本地历史 GIS 数据目录（当前有 `v6_time_pref_pgn_gbk_wgs84.zip`）。

## 当前可视化状态（2026-04）

- 时间轴范围：`618–1279`（`T0=618`, `T1=1279`）。
- 轨迹数据：`viz/data/trajectories.json`。
  - `meta.tang_range = [618, 1279]`
  - `poets = 356`
  - `events = 691`
  - `meta.stats.timeline_rows = 93279`
- 宋朝大事记已扩充（由用户筛选），并在 HUD 按年份显示。
- 右侧名人说明已拆为上下双区：
  - `#vipDockBirth`（出生）
  - `#vipDockDeath`（卒年）
  - 同年多 VIP 使用短延迟错峰弹出。
- 疆域叠层逻辑已在前端停用（不再 fetch `*_territory.geojson`）。
- 另见独立页 **`vip-path-trilogy.html`**（三人行迹 + Hartwell + 李清照全词叠层），主图页脚/提示中有入口链接。

## 本轮核心更改记录

1. 时间轴从唐扩至唐宋（618–1279），并重建轨迹数据。
2. `CITY_ERAS` 增补 907 之后分段，支持宋代城市标签。
3. `HIST_EVENTS` 宋朝条目扩充并按用户最终清单更新。
4. VIP 机制改造：
   - 名单切换为 14 位宋代人物。
   - 出生/卒年说明分区展示。
   - 同年事件错峰展示，降低重叠。
5. 历史疆域尝试（CHGIS / 手工示意）后按用户要求先移除前端叠层。
6. 新增 `scripts/build_chgis_territory.py`（可选，用于从 CHGIS 面数据构建 GeoJSON）。
7. 新增 `vip-path-trilogy` 独立页：三人行迹连播 + Hartwell 叠层 + 李清照代表作全词叠层（右侧、约 8–14 秒/首，与顶卡避让逻辑见上）。

## 运行方式

### 1) 启动前端

```bash
cd viz
python3 -m http.server 8765
```

浏览器打开：

- 主图：`http://127.0.0.1:8765/index.html`
- 三人行迹专题：`http://127.0.0.1:8765/vip-path-trilogy.html`
- 李清照 MapLibre 镜头 Demo（约 65s+ 循环，可选地形 token）：`http://127.0.0.1:8765/maplibre-liqz-camera-demo.html`

### 2) 录制视频（可选）

```bash
npm install
npx playwright install chromium
npm run record:viz-video -- --seconds 120
```

## 数据构建流程

### A. 抓取原始数据（可选）

```bash
python3 scripts/fetch_poetlife.py --authors 李白,陈子昂 --output-dir data/out --sqlite
```

### B. 构建轨迹 JSON（核心）

```bash
python3 scripts/build_tang_trajectories.py \
  --tang-lo 618 \
  --tang-hi 1279 \
  --output viz/data/trajectories.json
```

### C. 样本校验（建议）

```bash
python3 scripts/validate_trajectory_samples.py
```

### D. Hartwell 朝代外廓 JSON（主图 / trilogy 共用）

```bash
python3 scripts/build_hartwell_dynasty_outlines.py
```

### E. 校验 trilogy 脚本语法（可选）

```bash
node --check viz/vip-path-trilogy.js
```

## 依赖

- Python：`requirements.txt`
  - `httpx`
  - `pyshp`（可选）
  - `shapely`（可选）
- Node：`playwright`

## CHGIS 说明

- `CHGIS/v6_time_pref_pgn_gbk_wgs84.zip` 可用于本地生成唐/宋疆域 GeoJSON。
- 生成脚本：`scripts/build_chgis_territory.py`。
- 注意 CHGIS 自带许可约束（非商用、再分发限制等），使用前请自行确认合规。

## 后续计划（简版）

1. 把宋朝大事记拆分为可配置清单（JSON）而非硬编码在 `app.js`。
2. 为 `HIST_EVENTS` 增加“主事件 + 子说明”结构，提升 HUD 可读性。
3. 引入轻量测试脚本，校验事件按年排序与无重复年份。
4. 视需要恢复疆域叠层，但改为可开关（URL 参数或 UI 开关）。
