# 数据字典与生成说明

## 1. 文件清单

| 文件 | 说明 |
|------|------|
| `data/persons.csv` | 人物表（128 人） |
| `data/relationships.csv` | 关系表（561 条） |
| `data/quality_report.md` | 质量检查报告 |
| `scripts/extract_persons_and_relationships.py` | 数据提取脚本 |
| `stage_outputs/tang_figures_v2.csv` | 阶段1产出：人物清单（输入） |
| `stage_outputs/relationship_types.csv` | 阶段2产出：关系类型定义（输入） |
| `stage_outputs/tang_relationship_rules.md` | 阶段2产出：关系规则文档（输入） |

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

## 3. 关系表（relationships.csv）

**主键**: 无单一主键；唯一约束为 `(source_id, target_id, rel_type, rel_subtype)`

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `source_id` | INT | 关系发起方 c_personid | 32540 |
| `target_id` | INT | 关系目标方 c_personid | 3915 |
| `rel_type` | TEXT | 关系大类 | SOCIAL |
| `rel_subtype` | TEXT | 关系子类型代号 | SO_FRIEND |
| `rel_desc_chn` | TEXT | 关系中文描述 | 友 |
| `direction` | TEXT | directed / undirected | undirected |
| `year_start` | INT/NULL | 关系起始年（公元） | 744 |
| `year_end` | INT/NULL | 关系结束年（公元） | — |
| `weight` | FLOAT | 关系权重（0.1–1.0） | 0.6 |
| `evidence_level` | TEXT | primary / inferred | primary |
| `source_ref` | TEXT | 文献来源 | 唐才子傳 |
| `cbdb_assoc_code` | INT | CBDB 原始关系代号（可溯源） | 9 |
| `cbdb_role_type` | TEXT | CBDB 角色类型（A/P/M/KIN） | M |

### 关系大类分布

| 大类 | 条数 | 说明 |
|------|------|------|
| SOCIAL | 468 | 交游关系（友、同乡、唱和、赠诗等） |
| KIN | 38 | 亲属关系 |
| LITERARY | 22 | 文学关联（书序、墓志铭等） |
| COLLEAGUE | 16 | 同僚/官场关系 |
| POLITICAL | 11 | 政治/军事关联 |
| TEACHER_STUDENT | 6 | 师生关系 |

### 证据等级

| 等级 | 条数 | 标准 |
|------|------|------|
| primary | 506 | CBDB 记录有 c_source > 0 |
| inferred | 55 | c_source 为空或 0 |

---

## 4. 数据生成步骤

### 4.1 前置条件

- CBDB 数据库: `/Users/sousekilyu/Documents/Data/biography_literature_CBDB_china_historical/cbdb202409.db`
- 阶段1产出: `stage_outputs/tang_figures_v2.csv`（128 人）
- 阶段2产出: `stage_outputs/relationship_types.csv`（60 条关系子类型）

### 4.2 提取流程

```
1. 读取 tang_figures_v2.csv → 128 个 c_personid
2. 从 BIOG_MAIN 提取人物基本信息（姓名、生卒年、朝代、性别等）
3. 从 ALTNAME_DATA 提取别名/字/号，合并到 aliases 字段
4. 从 ASSOC_DATA 提取社会关系
   - 条件: c_personid 和 c_assoc_id 均在 128 人清单中
   - 排除: c_assoc_code = -1 或 0
   - 关联 ASSOC_CODES 获取关系描述和角色类型
   - 关联 NIAN_HAO 转换年号为公元年
   - 关联 TEXT_CODES 获取来源文献
5. 从 KIN_DATA 提取亲属关系
   - 条件: c_personid 和 c_kin_id 均在 128 人清单中
   - 关联 KINSHIP_CODES 获取关系描述
6. 按 (source_id, target_id, rel_type, rel_subtype) 去重
7. 计算权重、判定证据等级
8. 输出 persons.csv、relationships.csv
9. 运行质量检查，输出 quality_report.md
```

### 4.3 复现方法

```bash
# 在项目根目录
source .venv/bin/activate
python scripts/extract_persons_and_relationships.py
```

### 4.4 关键设计决策

1. **有向/无向**: 直接使用 CBDB 的 `c_assoc_role_type`：A=发起方，P=接受方，M=无向
2. **权重**: 按阶段2定义的权重体系（亲属 1.0 → 师生/同僚 0.8 → 交游 0.6 → 文学 0.4 → 政治 0.3）
3. **去重**: 同一对人物+同一关系类型只保留一条记录
4. **网络边界**: 只保留两个人物均在 128 人清单中的关系，过滤"向外部人物"的单向关系
5. **自环过滤**: source_id == target_id 的记录被排除

---

## 5. 已知限制

1. **时间缺失**: 540/561 条关系缺少精确时间，原因: CBDB ASSOC_DATA 中多数记录只有年号代号而无对应公元年映射
2. **7 人孤立**: 黃巢、蕭穎士、李璟、吳道子、尉遲恭、李煜、釋鑒真在 128 人网络内无任何关系——这些人物在 CBDB 中有 ASSOC_DATA，但其关系对象不在 128 人清单中
3. **SOCIAL 占比过高**: 468/561 (83%)，原因是 CBDB 中"友"(code=9) 和"赠诗文"(code=437) 记录最多
4. **来源文本代号**: source_ref 字段显示的是 CBDB TEXT_CODES 的 textid，需关联 TEXT_CODES 表获取完整文献名
