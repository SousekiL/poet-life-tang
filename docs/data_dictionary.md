# 数据字典与生成说明

## 1. 文件清单

| 文件 | 说明 |
|------|------|
| `data/persons.csv` | Layer 1 核心人物表（128 人） |
| `data/relationships.csv` | 原始关系记录（未去重，含完整溯源字段） |
| `data/relationships_layer1.csv` | Layer 1 聚合边（含 evidence_list） |
| `data/persons_layer2.csv` | Layer 2 桥接人物表 |
| `data/relationships_layer2.csv` | Layer 2 桥接关系边 |
| `data/persons_combined.csv` | 合并人物表（核心 + 桥接） |
| `data/relationships_combined.csv` | 合并关系边 |
| `data/quality_report.md` | 质量检查报告 |
| `scripts/extract_persons_and_relationships.py` | 数据提取脚本（Layer 0） |
| `scripts/build_network_layers.py` | 网络层构建脚本（Layer 1/2/Combined） |
| `scripts/quality_check.py` | 质量检查脚本 |
| `scripts/analyze_bridge.py` | 桥接分析脚本 |
| `stage_outputs/tang_figures_v2.csv` | 阶段1产出：人物清单（128 人） |
| `stage_outputs/relationship_types.csv` | 阶段2产出：关系类型定义（59 行数据） |

---

## 2. 人物表（persons.csv）

**主键**: `c_personid`（CBDB 人物唯一标识）

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `c_personid` | INT | CBDB 人物唯一标识 | 32540 |
| `name_chn` | TEXT | 标准中文姓名（优先用 c_name_proper） | 李白 |
| `name_rm` | TEXT | 罗马化姓名 | Li Bai |
| `surname_chn` | TEXT | 姓（中文） | 李 |
| `given_name_chn` | TEXT | 名（中文） | 白 |
| `birthyear` | INT/NULL | 出生年（公元），0 或空表示不详 | 701 |
| `deathyear` | INT/NULL | 去世年（公元），0 或空表示不详 | 762 |
| `fl_earliest_year` | INT/NULL | 活动最早年份（公元） | 720 |
| `fl_latest_year` | INT/NULL | 活动最晚年份（公元） | 762 |
| `is_female` | 0/1 | 性别标记（1=女性） | 0 |
| `dynasty_code` | INT | CBDB 朝代代号 | 6 |
| `dynasty_chn` | TEXT | 朝代中文名 | 唐 |
| `dynasty_en` | TEXT | 朝代英文名 | Tang |
| `aliases` | TEXT | 别名、字、号（来自 ALTNAME_DATA） | 太白(字); 青蓮居士(室名、別號) |

---

## 3. 原始关系表（relationships.csv）

每条记录对应 CBDB ASSOC_DATA 或 KIN_DATA 的一条原始记录，**未去重**。

**主键**: 无单一主键；同一 (source_id, target_id, rel_type, rel_subtype) 可能有多条记录。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `source_id` | INT | 关系起点（方向归一化后） | 32540 |
| `target_id` | INT | 关系终点（方向归一化后） | 3915 |
| `rel_type` | TEXT | 关系大类 | SOCIAL |
| `rel_subtype` | TEXT | 关系子类型代号 | SO_FRIEND |
| `rel_desc_chn` | TEXT | 关系中文描述 | 友 |
| `direction` | TEXT | directed / undirected | undirected |
| `year_start` | INT/NULL | 关系起始年（公元） | 744 |
| `year_end` | INT/NULL | 关系结束年（公元） | — |
| `weight` | FLOAT | 关系权重（0.1–1.0） | 0.6 |
| `evidence_level` | TEXT | primary / unsourced | primary |
| `source_ref` | TEXT | 来源文献名称（TEXT_CODES 全量解析） | 唐才子傳 |
| `cbdb_assoc_code` | INT | CBDB 原始关系代号 | 9 |
| `cbdb_role_type` | TEXT | CBDB 角色类型（A/P/M/KIN） | M |
| `source_table` | TEXT | 原始来源表 | ASSOC_DATA |
| `c_source` | INT/空 | CBDB 来源 ID（对应 TEXT_CODES.c_textid） | 40303 |
| `c_pages` | TEXT | 页码 | 257 |
| `c_sequence` | INT/空 | 记录序号 | 1 |
| `c_text_title` | TEXT | ASSOC_DATA 原始文献标题字段 | — |
| `orig_personid` | INT | 方向归一化前的 c_personid | 32540 |
| `orig_assoc_id` | INT | 方向归一化前的 c_assoc_id / c_kin_id | 3915 |

---

## 4. 聚合关系表（relationships_layer1.csv / layer2 / combined）

将原始记录按 (source_id, target_id, rel_type, rel_subtype) 聚合。

| 字段 | 类型 | 说明 |
|------|------|------|
| source_id – cbdb_role_type | | 同原始关系表 |
| `evidence_count` | INT | 聚合的原始记录数 |
| `evidence_list` | JSON | 原始证据明细数组 |
| `primary_rel` | 0/1 | 该人物对的主要关系标记 |
| `is_bridge` | 0/1 | 是否为桥接关系（仅 Layer 2/Combined） |

### evidence_list 结构

```json
[
  {
    "source_table": "ASSOC_DATA",
    "c_source": 40303,
    "c_pages": "257",
    "c_sequence": 1,
    "c_text_title": "",
    "orig_personid": 32540,
    "orig_assoc_id": 3915,
    "cbdb_assoc_code": 9
  }
]
```

---

## 5. 证据等级

| 等级 | 说明 |
|------|------|
| primary | CBDB 直接记录，c_source > 0（有文献来源） |
| unsourced | CBDB 直接记录，c_source 为空（无文献来源引用） |

本项目未实现推断算法，所有关系均来自 CBDB ASSOC_DATA / KIN_DATA 直接记录，不存在 `inferred` 等级。

---

## 6. 数据生成步骤

### 6.1 前置条件

- CBDB 数据库：通过 `--db` 参数或 `CBDB_PATH` 环境变量配置
- 阶段1产出：`stage_outputs/tang_figures_v2.csv`（128 人）
- 阶段2产出：`stage_outputs/relationship_types.csv`（59 行数据）

### 6.2 提取流程

```
1. 读取 tang_figures_v2.csv → 128 个 c_personid
2. 从 BIOG_MAIN 提取人物基本信息
3. 从 ALTNAME_DATA 提取别名/字/号
4. 从 ASSOC_DATA 提取社会关系（不去重，保留完整溯源字段）
5. 从 KIN_DATA 提取亲属关系（不去重，保留完整溯源字段）
6. TEXT_CODES 全量加载（无 LIMIT），用于解析 c_source
7. 输出 persons.csv、relationships.csv（原始记录）
```

### 6.3 网络构建流程

```
1. 读取 persons.csv 和 relationships.csv
2. 按 (source_id, target_id, rel_type, rel_subtype) 聚合，生成 evidence_list
3. 添加 primary_rel 标记
4. 从 CBDB 提取桥接人物关系
5. 应用严格桥接筛选（2+ 核心人物，新路径，无单核心例外）
6. 生成 Layer 1、Layer 2、Combined 数据
7. 连通分量分析
```

### 6.4 复现方法

```bash
cd /path/to/poet-life-tang
export CBDB_PATH="/path/to/cbdb202409.db"  # 可选，有默认值
python scripts/extract_persons_and_relationships.py
python scripts/build_network_layers.py
python scripts/quality_check.py
```

### 6.5 关键设计决策

1. **有向/无向**: 使用 CBDB 的 `c_assoc_role_type`：A=发起方，P=接受方，M=无向
2. **权重**: 按阶段2定义的权重体系
3. **不去重**: 原始记录全部保留，聚合视图通过 evidence_list 保留证据明细
4. **来源全量解析**: TEXT_CODES 全表加载，不做 LIMIT 截断
5. **桥接筛选**: 必须连接 2+ 核心人物且提供新路径
6. **自环过滤**: source_id == target_id 的记录被排除
7. **路径规范**: 所有脚本从仓库根目录通过相对路径运行

---

## 7. 已知限制

1. **3 人孤立**: 釋鑒真、吳道子、黃巢在合并网络中仍无边连接——这些人物在 CBDB 中的关系对象不在核心或桥接人物范围内
2. **SOCIAL 占比高**: 社交关系占多数，原因是 CBDB 中"友"和"赠诗文"记录最多
3. **时间缺失**: 多数关系缺少精确时间
