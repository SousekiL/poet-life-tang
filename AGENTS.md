# AGENTS.md

唐代重要人物社会关系网络项目（Tang-networks）。面向后续代理，记录代码基事实与操作规范。

## 项目 DNA

- **数据源**：CBDB（中国历代人物传记资料库）`cbdb202409.db`，路径通过 `--db` 参数或 `CBDB_PATH` 环境变量配置
- **人物范围**：唐代（618–907）人物，128 人
- **核心产出**：人物表（`data/persons.csv`）、关系表（`data/relationships.csv`，未去重原始记录）、聚合层（`data/relationships_layer1.csv`、`data/relationships_layer2.csv`、`data/relationships_combined.csv`）
- **关系类型**：59 种子类型，6 大类（KIN / TEACHER_STUDENT / COLLEAGUE / SOCIAL / POLITICAL / LITERARY）
- **可视化**：静态网络图优先，再做交互式

## CBDB 关键表

| 表名 | 用途 |
|------|------|
| `BIOG_MAIN` | 人物主表（姓名、字号、生卒年、籍贯） |
| `ASSOC_DATA` | 关系数据（人物间关系记录） |
| `ASSOC_CODES` | 关系类型编码 |
| `KIN_DATA` | 亲属关系 |
| `KINSHIP_CODES` | 亲属关系类型编码 |
| `TEXT_CODES` | 文献来源编码（全量加载，无 LIMIT） |
| `NIAN_HAO` | 年号表（用于年份转换） |
| `DYNASTIES` | 朝代信息 |
| `ALTNAME_DATA` | 别名数据 |

## 关键约束（改前必读）

1. **人物清单**：`stage_outputs/tang_figures_v2.csv`，128 人。不要使用其他文件名或人数。
2. **关系类型定义**：`stage_outputs/relationship_types.csv`，59 行数据（不含表头）。
3. **证据语义**：`primary`（有 c_source）/ `unsourced`（CBDB 直接记录但 c_source 为空）。本项目未实现推断算法，不得使用 `inferred`。
4. **溯源字段**：每条原始关系记录保留 source_table, c_source, c_pages, c_sequence, c_text_title, orig_personid, orig_assoc_id。
5. **不去重**：`data/relationships.csv` 保留所有原始 CBDB 记录。聚合视图（layer1/combined）通过 evidence_list 保留证据明细。
6. **桥接筛选**：桥接人物必须连接 2+ 核心人物且提供新路径。不允许单核心死胡同。
7. **来源解析**：TEXT_CODES 全量加载，不做 LIMIT 截断。
8. **路径规范**：所有脚本从仓库根目录通过相对路径运行。数据库路径用 `--db` 参数或 `CBDB_PATH` 环境变量。

## 精确命令

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 CBDB 路径（可选，有默认值）
export CBDB_PATH="/path/to/cbdb202409.db"

# 提取人物与关系数据（Layer 0）
python scripts/extract_persons_and_relationships.py [--db PATH]

# 构建网络层（Layer 1 + Layer 2 + Combined）
python scripts/build_network_layers.py [--db PATH]

# 数据质量检查
python scripts/quality_check.py [--data-dir PATH]

# 桥接分析
python scripts/analyze_bridge.py

# 生成静态网络可视化
python viz/static/generate_network.py
```

## 数据处理流程

1. **提取**：从 CBDB 提取 128 位唐代人物及其关系数据（`extract_persons_and_relationships.py`）
2. **聚合**：构建 Layer 1（核心网络）、Layer 2（桥接扩展）、Combined（合并）（`build_network_layers.py`）
3. **验证**：质量检查、连通分量分析（`quality_check.py`）
4. **输出**：生成 CSV 数据文件和可视化

## 归档说明

旧项目（唐宋诗人迁移可视化）完整归档于 `_archive/poet-life-tang/`，如需恢复可从归档目录复制。
