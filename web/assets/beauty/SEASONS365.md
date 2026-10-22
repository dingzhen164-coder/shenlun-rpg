# 3.6.5 四季全景与小Q版素材

以项目自有sect/xc-sect-day.webp及night.webp为参考，经OpenAI imagegen逐张绘制8张四季昼夜图。三色Q版为原创虚构人物，不用第三方图。授权按生成服务条款，来源登记见REGISTRY.md。原PNG留开发工作区，不进仓库；随包WebP，背景1536×864且每张<=350KiB，透明人物288×192，显示18–26px高。仅缩放/压缩，没有程序调色。

全景共同提示词：
> Edit the attached panoramic Chinese xianxia monastery game map into an exquisite high-resolution seasonal version. Preserve EXACTLY the reference camera, composition, positions, sizes and silhouettes of ALL mountains, buildings, paths, terraces and gates: central main hall at x=.52,y=.56, small library at .70,.64, tall pagoda at .87,.66, meditation cave at .09,.83, left floating orrery platform at .09,.45, waterfall at .37,.31, wooden bridges, top mountain terraces, observatory at .87,.20. This is a navigable map, do not add, remove, relocate or enlarge any architecture. Keep the same full-width 16:9 framing, entire left and right edges present. Paint richly detailed elegant traditional fantasy environment art, crisp architectural carvings and foliage, atmospheric layered clouds, harmonious premium jade and gold style. No people, no labels, no letters, no UI, no watermarks. Seasonal changes must be genuinely painted into vegetation, rock and roof surfaces and lighting, not an overall color filter.

各季补充：
- spring: SPRING: fresh tender jade-green foliage, delicate pale pink peach blossoms and white flowers clustered naturally among foreground trees and a few cliffside shrubs; soft airy mist, vigorous clear waterfalls. No snow, no orange autumn leaves.
- summer: SUMMER: deep vibrant emerald bamboo and lush abundant pine foliage, dense green shrubs, humid distant cloud banks, energetic waterfalls, clear summer sky. No pink blossoms, no autumn leaves, no snow.
- autumn: AUTUMN: richly painted rust-red maple, amber and gold deciduous foliage mixed with evergreen pines, dry golden grasses on rock ledges, transparent cool haze, crisp mountains. No pink blossoms, no snow. Make autumn unmistakable.
- winter: WINTER: fresh finely textured white snow coating mountain ledges, ground, bridge rails and ALL roofs while retaining visible dark jade tiles beneath the edges, snow-laden pine boughs, sparse frosted bamboo, icicles near cave and waterfall edges, crisp dry wintry atmosphere. Do not bury or change buildings. Unmistakable winter, not recolored green.

白天：自然日照、柔和阴影、干净中间调；夜晚：真实月光、靛蓝星空、灯窗与灯笼的暖光、季节植被或雪面的局部反射，月亮位置沿参照。禁止新增人物、文字、UI和水印；保留完整左右边缘与所有建筑道路位置。

Q版提示词：
> Create ONE exceptionally refined tiny CHIBI Chinese xianxia sword-flying traveler sprite, full body side profile facing RIGHT, standing with BOTH FEET on one thin horizontal flying sword. Adorable but elegant, head about one third total body height, visible tiny face, dark topknot, flowing miniature robes in DISTINCT jade green and ivory / cinnabar red and cream / deep indigo blue and soft lavender, small gold trim, clean readable silhouette at 22px high. Painterly polished fantasy game miniature with subtle cel-shaded volume and precise delicate outlines. One figure only, full sword and ribbons visible, short ribbons trail LEFT, absolutely transparent background, no scenery, no floor, no square/glow/border, no text, no particles. Compact wide 3:2 layout with figure around center-right. Every element comfortably inside frame.

三种配色分别生成，路径sword-chibi-jade/vermilion/indigo.webp；旧sword-traveler.webp不再随包。飞行曲线与尾迹为程序绘制，不是贴在背景中的静态人物。季节关闭仅停止粒子，背景继续按月份；法考和申论不载入本组修仙图。

四季8图加入后，清单唯一素材约13.08MiB，总预算公考16MiB；法考仍10MiB。
