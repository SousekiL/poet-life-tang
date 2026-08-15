# 数据字典

## CBDB 主要表结构

### BIOG_MAIN（人物主表）

| 字段 | 类型 | 说明 |
|------|------|------|
| c_personid | int | 人物唯一 ID |
| c_name_chn | str | 中文姓名 |
| c_name | str | 拼音姓名 |
| c_surname_chn | str | 中文姓 |
| c_surname | str | 拼音姓 |
| c_mingzi_chn | str | 中文名（字） |
| c_mingzi | str | 拼音名 |
| c_birthyear | int | 出生年 |
| c_deathyear | int | 去世年 |
| c_dynasty | str | 朝代 |
| c_dy | int | 朝代代码 |
| c_gender | int | 性别代码 |
| c_ethnicity_tribe | str | 民族 |
| c_native_place_id | int | 籍贯地址 ID |
| c_notes | str | 备注 |

### ASSOC_DATA（关系数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| c_assoc_id | int | 关系记录 ID |
| c_personid | int | 人物1 ID |
| c_assoc_personid | int | 人物2 ID |
| c_assoc_code | int | 关系类型代码 |
| c_assoc_type_code | int | 关系子类型代码 |
| c_sdf | int | 来源方向 |
| c_notes | str | 备注 |

### ASSOC_CODES（关系类型编码）

| 字段 | 类型 | 说明 |
|------|------|------|
| c_assoc_code | int | 关系类型代码 |
| c_assoc_desc_chn | str | 中文描述 |
| c_assoc_desc | str | 拼音描述 |

### KIN_DATA（亲属关系）

| 字段 | 类型 | 说明 |
|------|------|------|
| c_personid | int | 人物 ID |
| c_kin_id | int | 亲属 ID |
| c_kin_code | int | 亲属关系代码 |
| c_notes | str | 备注 |

## 项目自定义字段

### confidence（置信度）

| 值 | 说明 |
|------|------|
| 1.0 | 直接证据，CBDB 明确记录 |
| 0.8 | 强间接证据（如共同任职记录） |
| 0.6 | 中等间接证据（如同时期同地点） |
| 0.4 | 弱间接证据（如同时代但无直接关联） |

### relationship_type（关系类型）

| 类型 | 说明 | CBDB 来源 |
|------|------|----------|
| kinship | 亲属关系 | KIN_DATA |
| teacher_student | 师生关系 | ASSOC_DATA |
| friend | 朋友关系 | ASSOC_DATA |
| colleague | 同僚关系 | ENTRY_DATA, STATUS_DATA |
| political | 政治关系 | ASSOC_DATA |
| literary | 文学关系 | ASSOC_DATA |

## 地址相关表

### ADDR_CODES（地址编码）

| 字段 | 类型 | 说明 |
|------|------|------|
| c_addr_id | int | 地址 ID |
| c_name_chn | str | 中文地名 |
| c_name | str | 拼音地名 |
| c_parent_addr_id | int | 上级地址 ID |

### BIOG_ADDR_DATA（人物地址关联）

| 字段 | 类型 | 说明 |
|------|------|------|
| c_personid | int | 人物 ID |
| c_addr_id | int | 地址 ID |
| c_addr_type | int | 地址类型 |
| c_notes | str | 备注 |

## 朝代信息

### DYNASTIES（朝代表）

| 字段 | 类型 | 说明 |
|------|------|------|
| c_dy | int | 朝代代码 |
| c_dynasty_chn | str | 中文朝代名 |
| c_dynasty | str | 拼音朝代名 |
| c_start_year | int | 起始年 |
| c_end_year | int | 结束年 |
