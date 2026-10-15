# xingce 场景

约定文件名（3.2.3 起补全）：
- 时间段全景：`dawn.webp`、`day.webp`、`dusk.webp`、`night.webp`（16:9，≤350KB；目前行测用 `sect/xc-sect-day/night.webp`）
- 季节叠加：`season-spring.webp`、`season-summer.webp`、`season-autumn.webp`、`season-winter.webp`（透明层，叠在全景上）
- 动态层：`cloud-1.webp`、`mist.webp`、`mote.webp`（光点）、`bird.webp`、`lantern-glow.webp`
缺失时：只显示基础全景，动态层不出现。

## 现状（3.2.3）
时段与季节效果目前由代码实现（web/scene_fx.js），**不需要贴图**：白天/夜晚仍用 `sect/xc-sect-day|night.webp`，清晨黄昏是暖色叠层，季节是粒子。想用自己的四时段全景：放 `dawn/day/dusk/night.webp` 后告诉 AI 接入；想改粒子样式/数量，改 `scene_fx.js` 顶部的 KINDS。
