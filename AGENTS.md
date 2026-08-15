# AGENTS.md

唐代重要人物社会关系网络项目（Tang-networks）。面向后续代理，记录代码基事实与操作规范。

## 项目 DNA

- **数据源**：CBDB（中国历代人物传记资料库）`cbdb202409.db`，路径 `/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/`
- **人物范围**：唐代（618–907）人物，目标约 100 人
- **核心产出**：人物表（`data/processed/people.csv`）、关系表（`data/processed/relationships.csv`）、网络数据（`data/processed/network.json`）
- **可视化**：静态网络图优先，再做交互式

## CBDB 关键表

| 表名 | 用途 |
|------|------|
| `BIOG_MAIN` | 人物主表（姓名、字号、生卒年、籍贯） |
| `ASSOC_DATA` | 关系数据（人物间关系记录） |
| `ASSOC_CODES` | 关系类型编码 |
| `KIN_DATA` | 亲属关系 |
| `BIOG_ADDR_DATA` | 人物地址关联 |
| `BIOG_INST_DATA` | 人物机构关联 |
| `ENTRY_DATA` | 入仕记录 |
| `STATUS_DATA` | 身份状态 |
| `DYNASTIES` | 朝代信息 |

## 关键约束（改前必读）

1. **人物筛选标准**：唐代知名人物，需有足够关系数据支撑网络构建
2. **关系类型**：区分亲属、师友、同僚、政治关系等，每条关系标注证据来源
3. **不确定关系**：用置信度标记，不混入确定关系
4. **数据可追溯**：每条记录保留 CBDB 原始 ID 和来源信息

## 精确命令

```bash
# 安装依赖
pip install -r requirements.txt

# 从 CBDB 提取唐代人物数据
python scripts/extract_cbdb.py

# 构建关系网络
python scripts/build_network.py

# 数据质量检查
python scripts/quality_check.py

# 生成静态网络可视化
python viz/static/generate_network.py
```

## 数据处理流程

1. **提取**：从 CBDB 提取唐代人物及其关系数据
2. **清洗**：去重、标准化姓名、处理缺失值
3. **构建**：建立人物-关系网络数据结构
4. **验证**：质量检查、边界案例处理
5. **输出**：生成 CSV/JSON 数据文件和可视化

## 已知技术债

- 人物筛选标准待细化
- 关系判定规则待完善
- 交互式可视化技术栈待选定
- 缺少自动化测试

## 归档说明

旧项目（唐宋诗人迁移可视化）完整归档于 `_archive/poet-life-tang/`，如需恢复可从归档目录复制。
