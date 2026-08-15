# Tang-networks

唐代重要人物社会关系网络项目。以 CBDB（中国历代人物传记资料库）为主要数据来源，围绕约 100 位知名度较高的唐代人物，建立可追溯的人物与关系数据，并形成静态和交互式网络可视化。

## 项目目标

- **人物范围**：唐代（618–907）人物，目标规模约 100 人（根据数据质量调整）
- **数据产出**：人物表、关系表、关系类型与证据字段
- **可视化**：静态网络图（优先）→ 交互式网络图
- **可追溯性**：保留来源、处理过程和数据口径

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 从 CBDB 提取唐代人物数据
python scripts/extract_cbdb.py

# 构建关系网络
python scripts/build_network.py

# 生成静态网络可视化
python viz/static/generate_network.py
```

## 目录结构

```
tang-networks/
├── data/                          # 数据目录
│   ├── raw/                       # 原始数据（CBDB 导出等）
│   ├── processed/                 # 处理后的数据
│   │   ├── people.csv             # 人物表
│   │   ├── relationships.csv      # 关系表
│   │   └── network.json           # 网络数据（可视化用）
│   └── dictionaries/              # 数据字典与映射表
├── scripts/                       # 数据处理脚本
│   ├── extract_cbdb.py            # 从 CBDB 提取数据
│   ├── build_network.py           # 构建关系网络
│   └── quality_check.py           # 数据质量检查
├── viz/                           # 可视化
│   ├── static/                    # 静态网络图
│   └── interactive/               # 交互式网络图
├── docs/                          # 文档
│   ├── methodology.md             # 方法论
│   └── data_dictionary.md         # 数据字典
├── _archive/                      # 旧项目归档
│   └── poet-life-tang/            # 唐宋诗人迁移可视化项目（归档）
├── README.md
├── AGENTS.md
└── requirements.txt
```

## 数据来源

- **主要数据**：CBDB（中国历代人物传记资料库）`cbdb202409.db`
- **数据路径**：`/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/`

## 技术栈

| 层级 | 技术 |
|------|------|
| 数据处理 | Python 3（sqlite3, pandas, networkx） |
| 静态可视化 | matplotlib, networkx |
| 交互式可视化 | D3.js / Sigma.js（待定） |
| 数据存储 | CSV, JSON |

## 关键约束

1. **人物筛选**：明确筛选标准，区分直接证据与推断关系
2. **关系判定**：区分关系类型（亲属、师友、同僚等），标注证据来源
3. **不确定关系**：用概率或置信度标记，不混入确定关系
4. **数据可追溯**：每条关系记录来源和处理过程

## 归档说明

旧项目（唐宋诗人迁移可视化）完整归档于 `_archive/poet-life-tang/`，包括：
- `viz/` — 交互式地图可视化
- `scripts/` — 数据处理脚本
- `data/` — 诗人轨迹数据
- `CHGIS/` — 历史地理数据
- `output/` — 视频录制输出

如需恢复旧项目，可从归档目录直接复制。

## 许可证

数据仅限非商业研究与学习用途。CBDB 数据按其许可协议使用。
