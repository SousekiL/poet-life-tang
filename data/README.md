# 数据目录说明

## 目录结构

```
data/
├── raw/                       # 原始数据
│   └── cbdb202409.db         # CBDB 数据库（本地路径，不入库）
├── processed/                 # 处理后的数据
│   ├── people.csv            # 人物表
│   ├── relationships.csv     # 关系表
│   └── network.json          # 网络数据（可视化用）
└── dictionaries/              # 数据字典与映射表
```

## 数据文件说明

### people.csv（人物表）

| 字段 | 类型 | 说明 |
|------|------|------|
| cbdb_id | int | CBDB 原始 ID |
| name | str | 姓名 |
| courtesy_name | str | 字 |
| birth_year | int | 出生年 |
| death_year | int | 去世年 |
| dynasty | str | 朝代 |
| native_place | str | 籍贯 |
| gender | str | 性别 |
| source | str | 数据来源 |

### relationships.csv（关系表）

| 字段 | 类型 | 说明 |
|------|------|------|
| person1_cbdb_id | int | 人物1 CBDB ID |
| person2_cbdb_id | int | 人物2 CBDB ID |
| relationship_type | str | 关系类型 |
| relationship_subtype | str | 关系子类型 |
| evidence | str | 证据描述 |
| confidence | float | 置信度（0-1） |
| source | str | 数据来源 |
| cbdb_assoc_id | int | CBDB 关系记录 ID |

### network.json（网络数据）

```json
{
  "nodes": [
    {"id": "cbdb_id", "name": "姓名", "birth_year": 618, ...}
  ],
  "edges": [
    {"source": "cbdb_id1", "target": "cbdb_id2", "type": "关系类型", "confidence": 0.9}
  ]
}
```

## 数据来源

- **CBDB**：中国历代人物传记资料库
  - 本地路径：`/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/cbdb202409.db`
  - 官方网站：https://projects.iq.harvard.edu/cbdb

## 数据处理原则

1. **可追溯性**：每条记录保留 CBDB 原始 ID
2. **去重**：基于 cbdb_id 去重人物，基于 (person1, person2, type) 去重关系
3. **标准化**：姓名统一格式，关系类型统一编码
4. **质量检查**：处理后运行 quality_check.py 验证
