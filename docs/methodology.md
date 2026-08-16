# 方法论

## 人物筛选标准

### 筛选原则

1. **知名度**：在唐代文学、政治、艺术等领域有显著影响
2. **数据充足性**：CBDB 中有足够关系数据支撑网络构建（至少 3 条关系记录）
3. **代表性**：覆盖不同领域、时期、地域

### 筛选流程

1. 从 CBDB 提取所有唐代（618–907）人物
2. 按关系记录数量排序
3. 结合历史知名度人工筛选
4. 最终名单 128 人（根据数据质量调整）

人物清单文件：`stage_outputs/tang_figures_v2.csv`

## 关系判定规则

### 关系类型分类

关系类型定义在 `stage_outputs/relationship_types.csv` 中，共 59 种关系子类型，分为 6 大类：

| 类型 | 说明 | 数据来源 |
|------|------|----------|
| KIN | 血缘、婚姻关系 | KIN_DATA |
| TEACHER_STUDENT | 师生关系 | ASSOC_DATA |
| COLLEAGUE | 官场同事关系 | ASSOC_DATA |
| SOCIAL | 社交关系（友、同乡、唱和等） | ASSOC_DATA |
| POLITICAL | 政治关系（联盟、对立等） | ASSOC_DATA |
| LITERARY | 文学关系（书序、墓志铭、唱和等） | ASSOC_DATA |

### 关系确认标准

1. **直接证据**：CBDB ASSOC_DATA / KIN_DATA 中有明确记录
2. **来源标注**：每条关系标注 c_source（CBDB 来源 ID），可追溯到 TEXT_CODES
3. **证据等级**：
   - primary：有 c_source > 0 的直接记录
   - unsourced：CBDB 直接记录但 c_source 为空

**注意**：本项目未实现推断算法，所有关系均来自 CBDB 直接记录。

### 证据溯源

每条关系记录保留以下溯源字段：
- `source_table`：原始来源表（ASSOC_DATA / KIN_DATA）
- `c_source`：CBDB 来源 ID（对应 TEXT_CODES.c_textid）
- `c_pages`：页码
- `c_sequence`：序号
- `c_text_title`：文献标题
- `orig_personid` / `orig_assoc_id`：方向归一化前的原始端点

当多条原始记录映射到同一条网络边时，聚合后的边包含 `evidence_list`（JSON 数组），保留所有原始证据。

## 网络构建方法

### Layer 1：核心网络

- 128 位核心人物之间的直接关系
- 按 (source_id, target_id, rel_type, rel_subtype) 聚合
- 每个人物对标记一条 `primary_rel`（按 KIN > TS > CL > LI > PO > SO 优先级）

### Layer 2：桥接扩展

- 桥接人物：连接 2+ 核心人物，且提供 Layer 1 中不存在的新路径
- Tier B：连接 3+ 核心人物
- Tier C：连接 2 核心人物
- **严格筛选**：不允许仅连接单个核心人物的死胡同节点
- 孤立核心人物（无法通过桥接连接到主分量）如实记录为未解决

### 合并网络

- 核心人物（role=core）+ 桥接人物（role=bridge）
- 连通分量分析报告每个分量的大小和组成

## 数据质量控制

### 质量检查项

1. **完整性**：关键字段（姓名、生卒年、关系）不能为空
2. **一致性**：人物 ID 唯一、关系端点在人物表中、无自环
3. **唯一性**：每个人物对恰好一条 primary_rel
4. **准确性**：关系类型在预定义范围内
5. **溯源性**：每条关系有 source_table 和 c_source（或标记为 unsourced）
6. **连通性**：报告连通分量大小、未进入主分量的人物

### 质量检查脚本

```bash
cd /path/to/poet-life-tang
python scripts/quality_check.py [--data-dir PATH]
```

输出：
- 人物去重与缺失值统计
- 关系去重与证据分布
- 合并网络连通分量分析
- 未进入主分量的人物清单

## 数据更新流程

1. 确认 CBDB 数据库路径（`--db` 参数或 `CBDB_PATH` 环境变量）
2. 运行提取脚本：`python scripts/extract_persons_and_relationships.py`
3. 运行网络构建：`python scripts/build_network_layers.py`
4. 运行质量检查：`python scripts/quality_check.py`
5. 更新可视化
6. 记录变更日志

所有脚本从仓库根目录运行，使用相对路径。
