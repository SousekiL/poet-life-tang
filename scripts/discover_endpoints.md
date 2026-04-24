# cnkgraph PoetLife — 数据源与接口（Network / 静态分析）

分析日期：以仓库脚本可复现为准。页面脚本：[`/js/poetlife.js`](https://cnkgraph.com/js/poetlife.js)（版本号随部署变化）。

## 主站与入口

- 地图页：`https://cnkgraph.com/Map/PoetLife`
- 首屏「作家总览」列表与各地市总览锚点：内嵌在页面内联脚本变量 `travelData`（`CreatePoetLifeMap`）中，非单独 XHR。
- 每位作家的 `RequestUri` 形如：`scope=&author=李白&beginYear=0&endYear=0`（需 URL 编码）。

## 核心 JSON API（同源）

| 用途 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 作家行迹/详情 | GET | `/Api/Biography?{query}` | `query` 与 `RequestUri` 一致；可加 `isXianTang=true`（汉魏六朝专题）。返回 `Traces[]`，每条含 `Markers`（经纬、`Title`、`Detail` HTML、`RequestUri` 等）、`Lines`、`Summary`、`Detail` 等。 |
| 年段/年视图 | GET | `/Api/Biography?scope=&author=&beginYear=659&endYear=659` | 与页面 `ViewDetail('...')` 一致，用于更细时间粒度。 |
| 地区作品统计 | GET | `/Api/Biography/Stat?beginYear=&endYear=` | 可选 `isXianTang`。 |
| 作品统计表 | GET | `/Api/Biography/WritingStat?...` | 与当前视图 query 拼接。 |
| 地名索引 | GET | `/Api/Biography/Places` | 可选 `?isXianTang=true`。 |
| 按作品关键词 | GET | `/Api/Biography/Poems/{key}` | 可选 `?isXianTang=true`。 |

前端另有 `DetailsInRaw=true`（用于「导出当前数据」Excel），实测与不加该参数返回体大小一致，**`Markers[].Activities` 仍为空**；结构化活动字段以页面内 **`Detail` HTML** 为主。

## 第三方（非作家行迹核心数据）

- `POST https://api.sou-yun.cn/api/MapLayer` — 历史地图图层线数据，与作家年谱无直接关系。

## 建议请求头

- `User-Agent`：使用真实浏览器串，避免默认 `python-requests`。
- `Referer: https://cnkgraph.com/Map/PoetLife`（与浏览器一致，降低异常拦截概率）。
- 繁简：`Accept-Language: zh-hant` 可返回未经简体转换的原文（见官网开放资源说明）。

## Legal / 使用边界

- `robots.txt`：`Disallow: /book/`；`/Map/` 未禁止。
- 官网「开放资源」说明：Web API 面向研究、学习，**仅限非商业用途**；详见 [开放资源](https://cnkgraph.com/Home/OpenResources)。
- 批量下载请自行控制频率；大规模商用或再分发前应联系运营方或取得书面授权。
