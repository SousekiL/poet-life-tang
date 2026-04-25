# AGENTS.md

唐宋诗人迁移可视化项目（618–1279）。面向后续 OpenCode 代理，记录代码基事实与操作规范。

## 项目 DNA

- **viz/ 是纯前端**（静态 HTML + Leaflet IIFE，无 bundler），`viz/index.html` 为主图，`viz/vip-path-trilogy.html` 为李白→苏轼→李清照三人连播专题。
- **时间轴** `T0=618`, `T1=1279`，播放速率由 `PLAYBACK_DIVISOR = 270`（`app.js`）控制。
- **轨迹数据** `viz/data/trajectories.json` 由 `scripts/build_tang_trajectories.py` 从 `data/out/poetlife_flat.sqlite` 生成；不要手改。
- **Hartwell 朝代外廓** `viz/data/hartwell_dynasty_outlines.json` 由 `scripts/build_hartwell_dynasty_outlines.py` 生成；主图与 trilogy 共用切片键（`tang741`/`chin1080`/`chin1200`），改键须两边一起验。
- `viz/data/` 下还有 `*_territory.geojson`（tang/song_beisong/song_nansong）是**遗留构建产物，前端不再 fetch**；不要误以为它们在用。
- **数据源**：`scripts/fetch_poetlife.py` 从 `cnkgraph.com` 拉取（仅限非商业研究用途）。详细 API 见 `scripts/discover_endpoints.md`。

## 关键约束（改前必读）

1. **`frame()` 内的播放逻辑顺序不要动**——先保播放稳定。
2. **`HIST_EVENTS` 和 `CITY_ERAS` 仍硬编码在 `app.js`**（~205 行起 / ~101 行起），必须保持按年升序；同年事件合并为单条文案。
3. **VIP 诗人**：名单为 14 位宋代人物（`VIP_PALETTE`），出生/卒年分区展示（`vipDockBirth`/`vipDockDeath`）；同年错峰用 `VIP_CAPTION_STAGGER_MS`。改动时保持 `ensureVipDockSlots` / `pushVipDockCard` / `clearAllVipCaptions` 行为一致，关注 reset / scrub / playback-end 分支。
4. **李清照诗词叠层（trilogy 页 `LIQZ_POETRY_TRIGGERS`）**：
   - `freezeTimeline === true` 仅当「当前词之后 `queue` 仍有下一首」；最后一首或单首触发**不**冻结 `playU`。
   - 展示时 `#mapStage` 加 `has-poem-dock` 类收窄 `#phaseHud`，`hidePoemDock`/`abortPoetryForScrub`/`finishPoetrySession` 必须清掉。
5. **不要默认恢复疆域叠层**——除非明确用户需求。

## 精确命令

```bash
# 前端预览
cd viz && python3 -m http.server 8765
# → http://127.0.0.1:8765/index.html
# → http://127.0.0.1:8765/vip-path-trilogy.html

# 重建轨迹数据
python3 scripts/build_tang_trajectories.py --tang-lo 618 --tang-hi 1279 --output viz/data/trajectories.json

# 重建 Hartwell 朝代外廓
python3 scripts/build_hartwell_dynasty_outlines.py

# 校验
python3 scripts/validate_trajectory_samples.py
node -e "new Function(require('fs').readFileSync('viz/app.js','utf8')); console.log('app.js ok')"
node --check viz/vip-path-trilogy.js

# 视频录制（需先启动预览服务）
npm install && npx playwright install chromium
npm run record:viz-video -- --seconds 120
```

## URL 参数

- `?video=1` — 竖屏录屏模式（隐藏顶栏、VIP dock、HUD 等），配合 `&autoplay=1` 自动播放。
- 录制脚本默认打开 `http://127.0.0.1:8765/index.html?video=1&autoplay=1`。

## 脚本依赖

| 脚本 | 用途 | 注意 |
|------|------|------|
| `build_tang_trajectories.py` | 核心：sqlite → trajectories.json | 读 `data/out/poetlife_flat.sqlite` |
| `build_hartwell_dynasty_outlines.py` | Hartwell .prj → WGS84 GeoJSON | 需 `pyproj` |
| `build_chgis_territory.py` | CHGIS → GeoJSON（可选） | 需 `pyshp`+`shapely` |
| `fetch_poetlife.py` | cnkgraph API 拉取（可选） | 需 `httpx` |
| `record-poet-viz-video.mjs` | Playwright 竖屏录制 | 输出 `./output/viz-{timestamp}/` |

## 已知技术债

- `HIST_EVENTS` 和 `CITY_ERAS` 硬编码 → 抽到 `viz/data/` 的外部 JSON 是推荐的第一改进。
- 缺任何自动化测试。
- CHGIS 生成脚本存在但前端未用，容易产生认知误导。
- `viz/data/*_territory.geojson` 为遗留产物，前端不再消费。
