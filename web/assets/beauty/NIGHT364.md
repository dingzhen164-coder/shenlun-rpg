# 3.6.4 独立夜景与御剑素材

原图：项目自有`scenes/xingce/*.webp`、`scenes/shenlun/*.webp`（不含home）、`trial/*.png`、`contest/arena.png`。逐张参照原构图经OpenAI imagegen重新绘制，来源/授权见REGISTRY.md。生成原PNG保留在开发工作区、不随包；随包只存WebP，素材离线加载。两个仓库美术分开，法考不复制本组素材。

夜景统一提示词（每张追加主题/原文件名）：
> Create a lavish, finely detailed dedicated NIGHT painting of the attached game background. Preserve the exact camera, perspective, architecture, objects, framing, empty central workspace and landscape silhouette of the reference. Repaint lighting physically: deep indigo night sky outside, soft silver moonlight entering windows or open terraces, warm amber practical lamps and lanterns in the same locations, detailed localized bounce light, subtle reflected gold on stone or polished wood, distant lights. Readable midtones, atmospheric layered depth, painterly high-end game environment art, tranquil and refined, no global blue filter, no daylight remaining outside, no new text, no people, no UI, no watermark. Landscape 16:9, high resolution. Keep theme accurate: Chinese xianxia mountain monastery for xingce; realistic contemporary civic office for shenlun with only desk lamps, ceiling lighting and night city windows, no fantasy motifs.

塔与石门单独提示词：
> Edit this isolated Chinese fantasy tower/gate building sprite into an exceptionally detailed genuine nighttime version. Preserve exactly the original overall silhouette, dimensions, camera angle, placement, staircase, every roof and door. Rich natural blue-grey moonlight over stone and jade tile, warm amber glowing lanterns and lit windows, subtle localized reflected light, readable intricate carved details. NO surroundings. Keep a fully transparent background, including through gate opening, no floor rectangle, no sky, no text or symbols added. Portrait 2:3. Not a global tint.

御剑人物提示词：
> Create ONE beautifully painted small game sprite of a distant Chinese xianxia traveler flying on a straight elegant silver sword, full body side view facing right, clearly standing on sword, flowing ivory and desaturated teal robes, long dark hair and silk ribbons trailing to LEFT, delicate gold details, confident calm posture, refined realistic hand-painted fantasy miniature, strong readable silhouette at tiny 60px size, wide composition 3:2. Isolated with transparent background, no scenery, no clouds, no particles, no stars, no text, no frame. Entire sword, hair and clothes comfortably inside bounds. No large magical glow.

格式：24张房间/分区夜景1536宽；云台1536×1024，演武场1536×864；塔/门768×1152 RGBA；御剑360×240 RGBA。背景每张<=350KiB，人物约26KiB。仅缩放/转换压缩，没有程序调色或抠背景。各页别名见builtin-art.json；已有申论首页夜图保留。唯一清单素材约10.51MiB，上限12MiB；法考仍10MiB。

3.6.5起御剑人物已用SEASONS365.md中的三色小Q版替换，历史写实人物提示词留作来源记录，旧sprite不再随包。
