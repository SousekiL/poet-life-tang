# 数据目录说明

## 目录结构

```
data/
├── persons.csv                # Layer 1 核心人物表（128 人）
├── relationships.csv          # 原始关系记录（未去重，含完整溯源字段）
├── relationships_layer1.csv   # Layer 1 聚合后的关系边（含 evidence_list）
├── persons_layer2.csv         # Layer 2 桥接人物表
├── relationships_layer2.csv   # Layer 2 桥接关系边（含 evidence_list）
├── persons_combined.csv       # 合并人物表（核心 + 桥接）
├── relationships_combined.csv # 合并关系边
├── quality_report.md          # 质量检查报告
```

## 数据文件说明

### persons.csv（核心人物表）

| 字段 | 类型 | 说明 |
|------|------|------|
| c_personid | int | CBDB 原始 ID（主键） |
| name_chn | str | 中文姓名 |
| name_rm | str | 罗马字姓名 |
| surname_chn | str | 姓 |
| given_name_chn | str | 名 |
| birthyear | int | 出生年（空值表示未知） |
| deathyear | int | 去世年（空值表示未知） |
| fl_earliest_year | int | 活动最早年份 |
| fl_latest_year | int | 活动最晚年份 |
| is_female | int | 1=女性, 0=男性 |
| dynasty_code | int | 朝代代码 |
| dynasty_chn | str | 朝代中文名 |
| dynasty_en | str | 朝代英文名 |
| aliases | str | 别名字（字、号、谥号等） |

### relationships.csv（原始关系记录）

每条记录对应 CBDB 中的一条 ASSOC_DATA 或 KIN_DATA 记录，**未去重**。同一人物对/类型可能有多条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| source_id | int | 关系起点人物 ID（按方向规则确定） |
| target_id | int | 关系终点人物 ID |
| rel_type | str | 关系大类（KIN / TEACHER_STUDENT / COLLEAGUE / SOCIAL / POLITICAL / LITERARY） |
| rel_subtype | str | 关系子类型代码 |
| rel_desc_chn | str | 关系中文描述 |
| direction | str | directed / undirected |
| year_start | int | 关系起始年 |
| year_end | int | 关系结束年 |
| weight | float | 关系权重（0–1） |
| evidence_level | str | **primary**（有来源）/ **unsourced**（CBDB 直接记录但 c_source 为空） |
| source_ref | str | 来源文献名称（经 TEXT_CODES 全量解析） |
| cbdb_assoc_code | int | CBDB 原始关系代码 |
| cbdb_role_type | str | 角色类型（A=主动, P=被动, M=互向, KIN=亲属） |
| source_table | str | 原始来源表（ASSOC_DATA / KIN_DATA） |
| c_source | int | CBDB 原始来源 ID（可用于定位 TEXT_CODES） |
| c_pages | str | 页码 |
| c_sequence | int | 序号 |
| c_text_title | str | 文献标题（ASSOC_DATA 原始字段） |
| orig_personid | int | 原始记录中的 c_personid（方向归一化前） |
| orig_assoc_id | int | 原始记录中的 c_assoc_id / c_kin_id（方向归一化前） |

### relationships_layer1.csv（Layer 1 聚合边）

将原始记录按 (source_id, target_id, rel_type, rel_subtype) 聚合。

| 字段 | 类型 | 说明 |
|------|------|------|
| source_id – cbdb_role_type | | 同 relationships.csv |
| evidence_count | int | 聚合的原始记录数 |
| evidence_list | JSON | 原始证据明细数组，每项含 source_table, c_source, c_pages, c_sequence, c_text_title, orig_personid, orig_assoc_id, cbdb_assoc_code |
| primary_rel | int | 该人物对的主要关系标记（1=是, 0=否），按 KIN > TS > CL > LI > PO > SO 优先级 |

### persons_layer2.csv / relationships_layer2.csv

Layer 2 为桥接人物扩展。桥接人物必须连接 2 个以上核心人物，且提供 Layer 1 中不存在的新路径。字段与 Layer 1 相同，额外包含 `is_bridge=1` 和 `bridge_tier`（B=连接 3+ 核心, C=连接 2 核心）。

### persons_combined.csv / relationships_combined.csv

Layer 1 + Layer 2 合并。核心人物 `role=core`，桥接人物 `role=bridge`。

## 证据等级说明

| 等级 | 含义 |
|------|------|
| primary | CBDB 中存在直接记录，且 c_source > 0（有文献来源） |
| unsourced | CBDB 中存在直接记录，但 c_source 为空（无文献来源引用） |

**注意**：本项目未实现推断算法，所有关系均来自 CBDB ASSOC_DATA / KIN_DATA 的直接记录，不存在 `inferred` 等级。

## 数据来源

- **CBDB**：中国历代人物传记资料库
  - 本地路径：通过 `--db` 参数或 `CBDB_PATH` 环境变量配置
  - 官方网站：https://projects.iq.harvard.edu/cbdb

## 数据处理原则

1. **可追溯性**：每条记录保留 CBDB 原始 ID 和完整溯源字段（source_table, c_source, c_pages, c_sequence, c_text_title, orig_personid, orig_assoc_id）
2. **不丢弃证据**：原始记录不去重，聚合视图保留 evidence_list
3. **来源全量解析**：TEXT_CODES 全表加载，不做 LIMIT 截断
4. **标准化**：关系类型统一编码，方向归一化
5. **质量检查**：运行 `python scripts/quality_check.py` 验证
