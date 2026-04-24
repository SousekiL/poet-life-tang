# AGENTS.md

本文件给后续协作代理/工程师使用，记录项目现状、约束、操作规范与推荐任务流。

## 1. 项目目标

构建一个可播放的唐宋诗人迁移时间地图（当前窗口 618–1279），突出：

- 诗人轨迹（平滑线段）
- 出生/卒年事件脉冲
- 关键历史大事 HUD
- VIP 诗人强调展示（颜色、右侧说明）

## 2. 关键文件与职责

- `viz/index.html`：UI 容器、样式、控制栏、overlay 文案。
- `viz/app.js`：核心播放逻辑、地图图层、HUD、VIP 机制。
- `viz/data/trajectories.json`：前端主数据源（由构建脚本生成）。
- `scripts/build_tang_trajectories.py`：从 `data/out/poetlife_flat.sqlite` 生成 `trajectories.json`。
- `scripts/fetch_poetlife.py`：原始数据抓取。
- `scripts/validate_trajectory_samples.py`：样本校验。
- `scripts/build_chgis_territory.py`：可选，CHGIS 面数据转换脚本（当前前端未启用疆域叠层）。

## 3. 当前功能基线

- 时间轴：`T0=618`, `T1=1279`。
- 宋朝大事记已按用户定稿写入 `HIST_EVENTS`。
- VIP 列表为 14 位宋代人物（见 `VIP_PALETTE`）。
- 右侧说明区为双 dock：
  - `vipDockBirth`（出生）
  - `vipDockDeath`（卒年）
- 同年多 VIP 说明采用 `VIP_CAPTION_STAGGER_MS` 错峰。
- 疆域叠层相关逻辑已移除（代码层面不再调用 `*_territory.geojson`）。

## 4. 代码修改约束

1. **先保播放稳定**：`frame()` 内逻辑顺序不要随意改动。
2. **事件类改动必须保持按年有序**：
   - `HIST_EVENTS` 升序；
   - 同年冲突应合并为单条文案。
3. **VIP 相关改动**：
   - 保持 `ensureVipDockSlots` / `pushVipDockCard` / `clearAllVipCaptions` 行为一致性；
   - 关注 reset、拖进度、播放结束等分支的清理。
4. **不要默认恢复疆域叠层**，除非明确用户需求。
5. **`viz/data/trajectories.json` 为产物文件**，优先通过脚本重建，不手改。

## 5. 常用命令

### 前端预览

```bash
cd viz
python3 -m http.server 8765
```

### 重建轨迹数据

```bash
python3 scripts/build_tang_trajectories.py \
  --tang-lo 618 \
  --tang-hi 1279 \
  --output viz/data/trajectories.json
```

### 校验

```bash
python3 scripts/validate_trajectory_samples.py
node -e "new Function(require('fs').readFileSync('viz/app.js','utf8')); console.log('app.js ok')"
```

## 6. 已知风险与技术债

1. `HIST_EVENTS` 仍硬编码在 `app.js`，维护成本较高。
2. 缺自动化测试（排序、重复年份、UI 回归）。
3. CHGIS 生成脚本与前端解耦后，容易产生“生成了但没启用”的认知偏差。
4. 当前仓库不是标准 git 工作树（本地环境可能未初始化 `.git`）。

## 7. 建议后续任务（优先级）

### P1

- 把 `HIST_EVENTS` 抽到 `viz/data/hist_events.json`，并在 `app.js` 加载。
- 加一个轻量校验脚本：检查事件升序、无重复年份、文本非空。

### P2

- 为 VIP 名单建立配置文件（例如 `viz/data/vip_poets.json`），减少 `app.js` 硬编码。
- 给 HUD 增加“长文自动换行/截断策略”与移动端字号下限。

### P3

- 若用户再次要求疆域层：以“开关式 overlay”重接入，默认关闭。
- 增加录屏预设（横屏/竖屏、时长、是否自动播放）。

## 8. 协作约定

- 任何影响叙事节奏的改动（`T0/T1`、`PLAYBACK_DIVISOR`、`HIST_EVENTS`）都要在 PR 描述中写明“为什么改”。
- 对外发布内容需明确数据来源与许可范围（特别是 CHGIS 相关）。
