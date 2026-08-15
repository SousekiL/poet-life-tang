# 轨迹构建规则（`build_tang_trajectories.py`）

- **唐范围**：默认时间跨度与公元 **[618, 907]** 有交集（`birthYear <= 907` 且 `deathYear >= 618`）。
- **时间跨度来源**（`time_span_source`）：
  - **`title`**：`trace_title` / `person_name_raw` 中括号生卒年可解析时，用其为 `birthYear`/`deathYear`。
  - **`waypoints`**：解析不到生卒年时，用时间线各行 `beginYear`/`endYear` 的 **最小/最大** 作为跨度；**不生成** `birth`/`death` 与出生/卒脉冲事件，地图上动点用灰色略小圆点区分。
- **出生（仅 title 且有标记行）**：`place_title` 含 `(出生地)` 且能算 `place_key` 时写入 `birth` 并产生出生事件。
- **死亡（仅 title）**：在解析到的卒年内优先选 `detail_text` 含卒/去世… 的轨迹段；否则同年重叠末条；再无则记 `death_missing`。
- **place_key**：`region_id` 数字推导地级 `CN######`；失败则用 `GRID:lat:lng`（一位小数）。
- **可选覆盖**：`--overrides CSV` 两列 `region_suffix,prefecture_suffix`（纯数字，无 `CN`）。
