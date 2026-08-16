# 出版用静态网络图

本目录包含一张总图与六张重点区域图，均为 4500 × 3000 像素、300 DPI 的 PNG，并使用同一套图例与视觉编码。

## 图件

- `00_overview_with_legend.png`：唐代重要人物社会关系网络总图
- `01_lidu_with_legend.png`：李白—杜甫区域
- `02_wanggao_with_legend.png`：王维—高适区域
- `03_bailiu_with_legend.png`：白居易—刘禹锡区域
- `04_xiaolidu_with_legend.png`：李商隐—杜牧区域
- `05_hanliu_with_legend.png`：韩愈—柳宗元区域
- `06_yuanbai_with_legend.png`：元稹—白居易区域

## 统一图例

- 男性：蓝色圆形；女性：珊瑚红菱形。
- 边的颜色和线型共同表示亲属、师生、同僚、文学、政治、社交六类关系。
- 节点面积与人物在主网络中的主要关系数量成比例。
- 金色外圈只用于标出区域图的中心人物，不增加新的数据类别。

总图仅呈现最大连通分量（679 人、2,279 条主要关系），不改动源 CSV。区域图由中心人物、其所有直接关系人物，以及这些人物之间的主要关系组成。

## 复现

从仓库根目录运行：

```bash
python viz/static/generate_publication_networks.py
```

脚本读取 `data/persons_combined.csv` 与 `data/relationships_combined.csv`，输出覆盖本目录中的七张图。
