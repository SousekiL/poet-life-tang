# 唐代人物关系类型与提取规则

## 1. 关系类型体系

基于 CBDB 数据库中 ASSOC_DATA（187,878 条）、KIN_DATA（540,631 条）、STATUS_DATA 和 ENTRY_DATA 四张表的可用字段，定义以下六类关系。只保留有 CBDB 数据依据的类型。

### 1.1 亲属关系（KIN_DATA）

| 关系代号 | 中文 | CBDB c_kinrel_simplified | 方向 | 说明 |
|---------|------|--------------------------|------|------|
| K_PARENT | 父母 | F, M | 有向（A→B：A 是 B 的父母） | 含生父、嗣父、继父、养父、庶母等 |
| K_CHILD | 子女 | S, D | 有向（A→B：A 是 B 的子女） | 含长子、次子、养子、庶子、女儿等 |
| K_SPOUSE | 配偶 | W, H | 无向（等价互换） | 含第一任妻、妾、丈夫等 |
| K_SIBLING | 兄弟姊妹 | B, Z | 无向 | 含兄、弟、姊、妹、同母异父兄弟等 |
| K_UNCLE_AUNT | 伯叔姑舅姨 | FB, FZ, MB, MZ | 有向 | 父系、母系旁系长辈 |
| K_NEPHEW_NIECE | 侄甥 | BS, BD, ZS, ZD | 有向 | 旁系晚辈 |
| K_AFFINAL | 姻亲 | WF, WM, WB, HF, HM, HZ, SW, DH | 有向 | 通过婚姻建立的亲属关系 |

**提取规则：**
- 源表：`KIN_DATA`（c_personid → c_kin_id，c_kin_code 关联 KINSHIP_CODES）
- 同一条 KIN_DATA 记录通过 c_kincode 的 c_kin_pair1/c_kin_pair2 自动派生反向关系
- 亲属关系不需要额外的时间字段，生卒年可从 BIOG_MAIN 获取

### 1.2 师生关系（ASSOC_DATA）

| CBDB 代号 | 中文 | 方向 | c_role_type |
|-----------|------|------|-------------|
| 19/20 | 门人 | A=门人，P=师 | A/P |
| 22/23 | 学生 | A=学生，P=师 | A/P |
| 36/37 | 弟子 | A=弟子，P=师 | A/P |
| 49/50 | 从游 | A=从游者 | A/P |
| 126/127 | 传学 | A=传学者 | A/P |
| 208/209 | 宗学 | A=宗学者 | A/P |
| 217/218 | 受经/传经 | A=受经者 | A/P |
| 231/232 | 从学/教授 | A=从学者 | A/P |
| 256/257 | 私淑 | A=私淑者 | A/P |
| 646/647 | 法嗣 | A=法嗣 | A/P |
| 650/651 | 门孙 | A=门孙 | A/P |

**提取规则：**
- 源表：`ASSOC_DATA`，筛选 c_assoc_code 属于上述代号
- 方向：c_assoc_role_type = 'A' 表示 c_personid 是关系发起方（学生/门人），'P' 表示 c_personid 是师方
- 时间：c_assoc_year 可用，c_assoc_nh_code + c_assoc_nh_year 可转换为公元年
- 统一为有向边：学生 → 师（A 方向）

### 1.3 同僚/官场关系（ASSOC_DATA + ENTRY_DATA）

| CBDB 代号 | 中文 | 方向 | 说明 |
|-----------|------|------|------|
| 197 | 同僚 | 无向(M) | 在同一机构任职 |
| 66/67 | 幕僚 | A=幕僚，P=主官 | A/P |
| 64/65 | 部将 | A=部将，P=主帅 | A/P |
| 481/482 | 上下级 | A=下级，P=上级 | A/P |
| 24/25 | 辟 | A=被辟者 | A/P |
| 13/14 | 推荐 | A=推荐者 | A/P |
| 55/56 | 制科推荐 | A=推荐者 | A/P |
| 185/186 | 定科举次第 | A=定者 | A/P |
| 558/559 | 考官 | A=考官 | A/P |
| 10/11 | 同年友 | 无向(M) | 同年登第 |

**提取规则：**
- 同僚关系（197）：无向边，记录 c_personid 和 c_assoc_id
- 其余：统一为有向边，A→P（下级→上级、被推荐者→推荐者）
- 时间：使用 c_assoc_year 或 c_assoc_nh_year
- ENTRY_DATA 中的 c_assoc_code / c_assoc_id 字段也可提取师生关系（进士与座主）

### 1.4 交游关系（ASSOC_DATA）

| CBDB 代号 | 中文 | 方向 | 说明 |
|-----------|------|------|------|
| 9 | 友 | 无向(M) | 一般朋友 |
| 94 | 同乡 | 无向(M) | 同一籍贯 |
| 95 | 相识 | 无向(M) | 相识 |
| 108 | 论学 | 无向(M) | 讨论学术 |
| 113 | 诗社成员 | 无向(M) | 同一诗社 |
| 114 | 唱和 | 无向(M) | 诗歌唱和 |
| 117 | 同学/同门 | 无向(M) | 同一师门 |
| 120 | 同场屋 | 无向(M) | 同年应举 |
| 268 | 同会 | 无向(M) | 同一社团 |
| 277 | 同游 | 无向(M) | 一起游历 |
| 339/340 | 拜访 | A=拜访者 | A/P |
| 437/438 | 赠诗文 | A=赠者 | A/P |
| 445 | 同道 | 无向(M) | 志同道合 |
| 555 | 同旅 | 无向(M) | 一起旅行 |

**提取规则：**
- c_assoc_role_type = 'M' 的记录直接生成无向边
- c_assoc_role_type = 'A'/'P' 的生成有向边（拜访、赠诗等）
- 唱和关系（114）出现频率高，可作为衡量两人关系强度的指标

### 1.5 政治/军事关联（ASSOC_DATA）

| CBDB 代号 | 中文 | 方向 | 说明 |
|-----------|------|------|------|
| 4/5 | 恩主/门客 | A=恩主，P=门客 | 政治庇护 |
| 7/8 | 党羽/党魁 | A=党羽 | 政治联盟 |
| 11/12 | 弹劾 | A=弹劾者 | 政治冲突 |
| 15/16 | 反对/攻讦 | A=攻讦者 | 政治冲突 |
| 17/18 | 欣赏/器重 | A=欣赏者 | 政治支持 |
| 26/27 | 支持 | A=支持者 | 政治支持 |
| 83/84 | 忌/恶 | A=忌恶者 | 政治冲突 |
| 136/137 | 反对政策 | A=反对者 | 政治冲突 |
| 262/263 | 拥立 | A=拥立者 | 政治支持 |
| 294 | 争权 | 无向(M) | 政治对抗 |
| 367 | 政见趋同 | 无向(M) | 政治一致 |
| 404 | 战友 | 无向(M) | 军事同盟 |

**提取规则：**
- 支持类（4/5, 17/18, 26/27, 262/263）：有向边，A→P
- 冲突类（11/12, 15/16, 83/84, 136/137）：有向边，A→P
- 无向类（294, 367, 404）：无向边
- 政治关系带有明确的时间标记（c_assoc_year），可用于追踪关系变化

### 1.6 文学/学术关联（ASSOC_DATA）

| CBDB 代号 | 中文 | 方向 | 说明 |
|-----------|------|------|------|
| 32/33 | 书序 | A=作序者 | A/P |
| 43/44 | 墓志铭 | A=撰写者 | A/P |
| 44/43 | 神道碑 | A=撰写者 | A/P |
| 57/58 | 效法文风 | A=效法者 | A/P |
| 70/71 | 称道诗作 | A=称道者 | A/P |
| 132/133 | 作传 | A=撰写者 | A/P |
| 172/173 | 称道文风 | A=称道者 | A/P |
| 251 | 合撰 | 无向(M) | 合作著述 |
| 341/342 | 编辑诗文 | A=编辑者 | A/P |
| 361/362 | 研读著作 | A=研读者 | A/P |
| 429/430 | 致书 | A=致书者 | A/P |
| 431/432 | 答书 | A=答书者 | A/P |

**提取规则：**
- 为某人作序、作墓志铭等：有向边，撰写者→被写者
- 文学唱和、合撰：无向边
- 致书/答书：有向边，可用于构建通信网络

---

## 2. 关系属性定义

每条关系记录需包含以下属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| source_id | INT | 关系发起方 c_personid |
| target_id | INT | 关系目标方 c_personid |
| rel_type | ENUM | 关系大类（KIN/TEACHER_STUDENT/COLLEAGUE/SOCIAL/POLITICAL/LITERARY） |
| rel_subtype | INT | CBDB 原始 c_assoc_code 或 c_kin_code |
| direction | ENUM | directed / undirected |
| year_start | INT | 关系起始年（公元），可为空 |
| year_end | INT | 关系结束年（公元），可为空 |
| weight | FLOAT | 关系强度权重（见下文计算规则） |
| evidence_level | ENUM | primary / secondary / inferred（见下文） |
| source_ref | TEXT | CBDB c_source 对应的文献来源 |
| cbdb_assoc_id | INT | CBDB ASSOC_DATA 原始行 ID（用于溯源） |

### 2.1 方向性

- **有向关系**（directed）：师生、弹劾、推荐、恩主、作序等——从 A 指向 B，表示 A 对 B 施加了该关系
- **无向关系**（undirected）：友、同僚、同乡、唱和、争权等——两端等价
- CBDB 的 c_assoc_role_type 字段直接标识方向：
  - `A` = Active（发起方）
  - `P` = Passive（接受方）
  - `M` = Mutual（无向）

### 2.2 时间范围

- **year_start**：优先取 c_assoc_year；若仅有 nianhao，先查 NIAN_HAO 表转换为公元年
- **year_end**：多数 ASSOC_DATA 记录只有单一年份；year_end 留空，或根据人物生卒年推断上限
- 对于无法确定具体年份的记录，year_start = NULL，标记为"时间不详"

### 2.3 权重（weight）

权重计算规则（取值 0.1–1.0）：

| 权重 | 条件 |
|------|------|
| 1.0 | 直系亲属（父/母/子/女/配偶） |
| 0.8 | 师生关系、同僚关系 |
| 0.6 | 友、同乡、同学、唱和、诗社 |
| 0.4 | 文学关联（作序、墓志铭、致书等） |
| 0.3 | 政治关联（支持、反对、弹劾等） |
| 0.2 | 相识、论学、研读著作等弱关联 |

若同一对人物存在多条同类关系，权重叠加但上限 1.0（公式：`w = 1 - (1-w1)(1-w2)...`）。

### 2.4 证据等级

| 等级 | 标准 | 对应 CBDB 字段 |
|------|------|----------------|
| **primary** | CBDB 记录有明确来源编号（c_source 非空且非 0） | c_source > 0 |
| **secondary** | CBDB 记录有来源但为二手材料 | c_source > 0，且来源类型为类书/总集 |
| **inferred** | 关系通过其他关系推断（如：A 是 B 的学生，B 是 C 的学生 → A、C 有间接师承关系） | 无 CBDB 直接记录 |

- 只有 primary 和 secondary 从 CBDB 直接提取
- inferred 关系在可视化中用虚线表示，不计入关系强度统计

---

## 3. 数据处理规则

### 3.1 同名与异体名

- CBDB 的 ALTNAME_DATA 表记录了别名、字、号等异体名
- 以 BIOG_MAIN.c_personid 为唯一标识，不以姓名为标识
- 在人物表中保留 c_name_chn（正名）和 c_name（罗马化），另加一列 aliases 存放 ALTNAME_DATA 中的别名
- 同名不同人：通过 c_personid + c_birthyear + c_dy（朝代）区分

### 3.2 重复记录

- CBDB 中同一人物可能出现多个 c_personid（如"李白"有 c_personid=32540 和 196395）
- 处理方式：以人物清单（tang_100_figures.csv）中确认的 c_personid 为准
- 对于关联到非清单人物的 ASSOC_DATA 记录：若该人物与清单人物有直接关系，保留并记录；否则忽略

### 3.3 关系冲突

- 当同一对人物存在矛盾关系（如同时有"友"和"反对"），保留两条记录，分别标注 evidence_level
- 不做自动消歧，在关系表中标记 `conflict_flag = TRUE`，供人工复核
- 可视化时以颜色区分正面/负面关系

### 3.4 不确定关系

- CBDB 中 c_assoc_code = 0（未详）的记录：直接排除
- c_assoc_code = -1（缺乏信息）的记录：直接排除
- c_source = 0 或 NULL 的记录：标记 evidence_level = 'inferred'，仍保留但在可视化中降低透明度

---

## 4. 提取流程

```
1. 读取人物清单 (tang_100_figures.csv) → person_ids[]
2. 从 KIN_DATA 提取亲属关系
   WHERE c_personid IN (person_ids) OR c_kin_id IN (person_ids)
3. 从 ASSOC_DATA 提取社会关系
   WHERE c_personid IN (person_ids) OR c_assoc_id IN (person_ids)
   AND c_assoc_code NOT IN (-1, 0)
4. 关联 ASSOC_CODES / KINSHIP_CODES 获取关系描述
5. 关联 BIOG_SOURCE_DATA 获取来源信息
6. 转换 nianhao → 公元年
7. 计算权重
8. 输出 relationships.csv
```

---

## 5. 示例（人工复核基准）

### 示例 1：李白与杜甫（友 + 赠诗）

| 字段 | 值 |
|------|-----|
| source_id | 32540（李白） |
| target_id | 3915（杜甫） |
| rel_type | SOCIAL |
| rel_subtype | 9（友） |
| direction | undirected |
| year_start | ~744（天宝三年） |
| weight | 0.6 |
| evidence_level | primary |
| 来源 | ASSOC_DATA 中李白 c_assoc_id=3915, code=9 |

### 示例 2：杜甫与李白（赠诗文）

| 字段 | 值 |
|------|-----|
| source_id | 3915（杜甫） |
| target_id | 32540（李白） |
| rel_type | LITERARY |
| rel_subtype | 437（赠诗文） |
| direction | directed（杜甫→李白） |
| year_start | ~744 |
| weight | 0.4 |
| evidence_level | primary |

### 示例 3：李白的亲属关系

| 字段 | 值 |
|------|-----|
| source_id | 32540（李白） |
| target_id | 512561（父） |
| rel_type | KIN |
| rel_subtype | 75（父） |
| direction | directed（父→李白） |
| weight | 1.0 |
| evidence_level | primary |

### 示例 4：杜甫与房琯（推荐/政治冲突）

杜甫因上疏救房琯而遭贬，此为政治关联的重要案例。在 ASSOC_DATA 中检查 c_personid=3915 的政治相关 c_assoc_code 记录即可提取。

---

## 6. 产出文件

| 文件 | 格式 | 说明 |
|------|------|------|
| relationship_types.csv | CSV | 关系类型定义表（rel_type, rel_subtype, c_assoc_code, chn_desc, direction, default_weight） |
| relationships.csv | CSV | 提取的关系数据（source_id, target_id, rel_type, rel_subtype, direction, year_start, year_end, weight, evidence_level, source_ref, cbdb_assoc_id） |
| tang_relationship_rules.md | Markdown | 本文档 |
