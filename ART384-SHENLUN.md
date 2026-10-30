# 申论 P1 场景图记录

办公室、实操训练中心、年度考核各一组昼/昏/夜，构图参考与各 8 张原生细绘块由 OpenAI imagegen 生成；输入为该时段构图的对应裁剪，要求保留物件位置，仅细绘纹理。以 `tools/art369_pack.cjs` 对齐低频色调并在 32px 重叠区羽化，每块只缩小，输出 3840×2880。相邻 provenance 记录构图参考、原生尺寸、坐标、来源文件名和 SHA-256；原图与分块不进仓库。

色相统计：Pillow HSV（8 位），色相 7–42、饱和度 ≥51、亮度 ≥38，统计该范围占整图全部像素的百分比；它是可复现的颜色筛选口径，接近灰色或暗色的像素不计为黄橙色。实际成图结果如下：

| 场景时段（`web/assets/beauty/scenes/shenlun/hd/384/`） | 字节 | 黄橙占比 |
|---|---:|---:|
| dwelling-day.webp | 3,142,008 | 16.74% |
| dwelling-dusk.webp | 2,984,472 | 0.15% |
| dwelling-night.webp | 2,803,586 | 0.03% |
| bank-day.webp | 2,763,448 | 5.30% |
| bank-dusk.webp | 2,734,976 | 17.75% |
| bank-night.webp | 2,720,530 | 9.45% |
| contest-day.webp | 3,163,502 | 11.49% |
| contest-dusk.webp | 2,967,966 | 0.02% |
| contest-night.webp | 3,102,632 | 16.40% |

训练中心夜景屏幕中央连接处存在轻微边缘错位；办公室夜景左侧书脊交界有极小的空白方块样标记，无可辨文字。浏览器模拟不能代替真机观察。

以上两处为已知小瑕疵：曾各尝试一次局部像素克隆修补，100% 局部对比发现引入块状痕迹，故未采用，原图与 provenance 保持不变。

## 申论 P2 场景图记录

知识办理中心、档案室、天机台、设置各一组昼/昏/夜；沿用上述原生分块、低频对齐和 32px 羽化流程。部分分块因出现疑似标记而以参考裁剪重新生成。色相占比与 P1 使用相同的 Pillow HSV 统计口径。

| 场景时段（`web/assets/beauty/scenes/shenlun/hd/384/`） | 字节 | 黄橙占比 |
|---|---:|---:|
| train-day.webp | 2,108,776 | 10.07% |
| train-dusk.webp | 2,052,726 | 0.11% |
| train-night.webp | 2,173,878 | 0.22% |
| skeleton-day.webp | 2,351,290 | 0.68% |
| skeleton-dusk.webp | 2,473,266 | 1.07% |
| skeleton-night.webp | 2,094,978 | 0.08% |
| tianji-day.webp | 2,414,338 | 8.00% |
| tianji-dusk.webp | 2,757,196 | 21.90% |
| tianji-night.webp | 2,427,126 | 0.18% |
| settings-day.webp | 2,679,894 | 0.15% |
| settings-dusk.webp | 2,674,412 | 0.06% |
| settings-night.webp | 2,608,834 | 0.07% |
