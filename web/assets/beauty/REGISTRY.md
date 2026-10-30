# 素材登记表

每放入或更换一个素材，追加一行。来源写清楚（工具/网址/作者），授权写清楚（许可证名称或“用户自有/生成服务条款”）。

| 编号 | 路径（相对 web/assets） | 用途 | 来源 | 授权 | 日期 | 生成提示词/备注 |
|---|---|---|---|---|---|---|
| art384-shenlun-p1 | beauty/scenes/shenlun/hd/384/{dwelling,bank,contest}-{day,dusk,night}.webp（9张） | 申论办公室、训练中心、年度考核分时背景 | OpenAI imagegen 原创构图及每张8个原生细绘块 | 生成服务条款；无第三方参考图 | 2026-10-29 | 3840×2880，原生分块只缩小合成；来源及摘要见相邻 provenance；不用于法考 |
| art381-six-scenes | beauty/scenes/xingce/hd/381/{dwelling,bank,contest,skeleton,tianji,settings}-{day,dusk,night}.webp、bank-dawn.webp、selection-{dawn,day,dusk,night}.webp（23张） | 六处独立昼/昏/夜与塔清晨、选择厅；电脑/平板横竖屏 | OpenAI imagegen原创构图+每张8个原生细绘块，参考仅项目自有素材 | 生成服务条款；无第三方参考图 | 2026-10-25 | 3840×2880，只降采样合成，无放大冒充4K；每图provenance含原生尺寸/坐标/来源ID/SHA256，提示词及安全区见ART381.md；不随法考打包 |
| trial-hall-369 | beauty/trial/hd/369/hall-day.webp | 行测完整试炼塔与双门场景，电脑/平板横竖屏 | OpenAI imagegen原创构图与8个原生细绘块 | 生成服务条款 | 2026-10-23 | 3840×2880，3.47MiB；青绿云海、同光照塔门、无字匾额；不补全裁块边缘建筑，按原构图细绘后只缩小合成；提示词要求兼顾电脑/平板，实际采用完整contain画框保护主体，出处/原生尺寸/SHA256见同目录provenance.json |
| xc-sect-day | sect/xc-sect-day.webp | 青衡宗白天全景 | Gemini 生成 | 以生成服务条款为准（用户确认） | 2026-10-15 | 见 sect/README.md |
| xc-sect-night | sect/xc-sect-night.webp | 青衡宗夜晚全景 | Gemini 生成 | 同上 | 2026-10-15 | 见 sect/README.md |
| xc-qinghe-* | guide/xc-qinghe-*.webp | 沈清禾半身立绘与眨眼叠层 | Gemini 生成 | 同上 | 2026-10-15 | 见 guide/README.md |
| icons | beauty/icons/svg/*.svg、sprite.svg | 全站统一图标（109个，替换界面里的emoji） | Lucide v0.468.0（lucide.dev） | ISC（LICENSE-lucide.txt） | 2026-10-15 | 对照表 emoji-map.json；换图标见 icons/README.md |
| font-title | beauty/fonts/zcool-xiaowei/ | 行测标题字体（--display，分片woff2） | ZCOOL XiaoWei（@fontsource/zcool-xiaowei 5.3.0） | SIL OFL 1.1（OFL.txt） | 2026-10-15 | 只用于 body.xiuxian 的 --display |
| paper-grain | beauty/materials/paper-grain.svg | 纸笺弹窗纹理 | 本项目用SVG滤镜自制 | 无限制 | 2026-10-15 | feTurbulence 噪点 |
| sfx-* | beauty/audio/sfx/*.ogg（14个） | 通用音效 | Kenney：Interface Sounds、RPG Audio、Music Jingles（kenney.nl） | CC0 | 2026-10-15 | 文件名与来源对应见 audio/README.md |
| bgm-map-day | beauty/audio/bgm/map-day.ogg | 地图白天 | "Asianoriental2" by tozan（opengameart.org/content/asianoriental2） | CC0 | 2026-10-15 | 截取前120秒并淡出，转 ogg |
| bgm-map-night | beauty/audio/bgm/map-night.ogg | 地图夜晚 | "Yoiyami Core Theme" by yoiyami（OpenGameArt） | CC0 | 2026-10-15 | 同上 |
| bgm-dongfu | beauty/audio/bgm/dongfu.ogg | 洞府 | "First Light Particles" by yoiyami（OpenGameArt） | CC0 | 2026-10-15 | 同上 |
| bgm-study | beauty/audio/bgm/study.ogg | 学习 | "Calm Loop" by wipics（OpenGameArt） | CC0 | 2026-10-15 | 原曲约19秒，循环 |
| bgm-ceremony | beauty/audio/bgm/ceremony.ogg | 突破/升级仪式 | "Forgotten Victory" by yd（OpenGameArt） | CC0 | 2026-10-15 | 截取前120秒 |
| bgm-dialog | beauty/audio/bgm/dialog.ogg | 对话/剧情 | "A New Town (RPG Theme)" by cynicmusic（OpenGameArt） | CC0 | 2026-10-15 | 约62秒，循环 |
| scene-fx | web/scene_fx.js、scene_fx.css | 时段切换、季节飘落物、光点、飞鸟（纯代码，无贴图） | 本项目自写 | 无限制 | 2026-10-15 | 设置→地点排布里可调 |
| empty-scroll | beauty/ui/empty-scroll.svg | 空状态小插画（CSS mask，随文字色） | 本项目自绘 | 无限制 | 2026-10-15 | ds.css .ds-empty::before |
| cursors | xiuxian-cursor/*.svg 等 | 行测灵光法阵光标 | 本项目原创SVG | 无限制 | 2.x | 见 cursors/README.md |
| ambient-day | beauty/audio/sfx/ambient-day.ogg | 地图白天环境声（鸟鸣） | "Ambient Bird Sounds" by isaiah658（OpenGameArt） | CC0 | 2026-10-15 | 转 ogg 单声道 |
| ambient-night | beauty/audio/sfx/ambient-night.ogg | 地图夜晚环境声（虫鸣） | "Crickets Ambient Noise - loopable" by wolfgang（OpenGameArt） | CC0 | 2026-10-15 | 转 ogg 单声道 |
| ambient-water | beauty/audio/sfx/ambient-water.ogg | 洞府环境声（流水） | "Park ambiences" 的 river 段 by thimras（OpenGameArt） | CC0 | 2026-10-15 | 截取40秒并淡入淡出 |
| font-noto-serif | beauty/fonts/noto-serif-sc/ | 申论、法考标题字体（--display 前置，仅700粗体分片woff2） | Noto Serif SC（@fontsource/noto-serif-sc） | SIL OFL 1.1（OFL.txt） | 2026-10-15 | 申论 body.guantu、法考默认 --display |
| bb-badge | web/beauty_badge.js | 境界徽章（8档颜色/形状，纯SVG） | 本项目自绘 | 无限制 | 2026-10-15 | 洞府卡、大典画面 |
| trial-tower | beauty/trial/tower.png | 青衡宗古塔建筑立绘 | 本项目提示词，OpenAI imagegen生成，无第三方参考图 | 生成素材，项目内使用 | 2026-10-16 | 透明PNG，两仓库保留各自世界观；见trial/README.md |
| trial-gate | beauty/trial/gate.png | 试炼场景石门 | 本项目提示词，OpenAI imagegen生成，无第三方参考图 | 生成素材，项目内使用 | 2026-10-16 | 透明PNG，左右入口共用；世界观各自保留 |
| trial-landscape | beauty/trial/landscape.png | 云海石台场景 | 本项目提示词，OpenAI imagegen生成，无第三方参考图 | 生成素材，项目内使用 | 2026-10-16 | 横向PNG，见trial/README.md |
| contest-arena | beauty/contest/arena.png | 大比/学院竞技场场景 | 本项目提示词，OpenAI imagegen生成，无第三方参考图 | 生成素材，项目内使用 | 2026-10-16 | 1536×1024，世界观各自保留；见contest/README.md |

| art338-scenes | beauty/scenes/<主题>/*.webp | 三科个人空间、研习分区与普通页面背景 | 本项目原创提示词，经 OpenAI imagegen 生成 | 生成服务条款；未用第三方图 | 2026-10-17 | 提示词见各主题 README；深色复用同图加遮罩，减少体积 |
| art338-shenlun | beauty/characters/shenlun/sl-*-calm.webp | 九位既有申论人物，每人一张 | 本项目原创设定，经 OpenAI imagegen 生成并透明化 | 生成服务条款；原创虚构人物 | 2026-10-17 | 姓名/岗位沿用职务履历，不扩展自由偶遇阵容；法考包不含本组图 |
| art338-peers | beauty/characters/{xingce,fakao}/*-calm.webp | 陆衡/苏苓、莉娅/诺亚既有支线单张立绘 | OpenAI imagegen 原创生成 | 生成服务条款 | 2026-10-17 | 详见各人物目录README；按科目分发，不新增人物 |

| art364-night-xc | beauty/scenes/xingce/*-night.webp（12张） | 洞府五页/五峰/设置/群峰独立夜景 | OpenAI imagegen，参照项目自有白天图逐场景重绘 | 生成服务条款，项目内使用 | 2026-10-22 | 提示词及清单见NIGHT364.md，不是调色图 |
| art364-night-sl | beauty/scenes/shenlun/*-night.webp（新增12张，不含已有home-night） | 办公室三页/五类学习区/档案/手账/设置/中心 | 同上 | 同上 | 2026-10-22 | 现实政务环境，无修仙元素 |
| art364-night-world | beauty/trial/{landscape,tower,gate}-night.webp、beauty/contest/arena-night.webp | 云台、塔、石门、演武场夜景（4张） | OpenAI imagegen参照项目自有场景 | 同上 | 2026-10-22 | 塔/门保留透明通道，灯火直接入画 |
| art364-sword | beauty/fx/sword-traveler.webp | 青衡宗主页小型御剑行旅 | OpenAI imagegen原创虚构人物 | 同上 | 2026-10-22 | 360×240透明WebP，运行时弧线与尾迹为项目代码 |

| art366-seasons | beauty/scenes/xingce/hd/home-{spring,summer,autumn,winter}-{day,night}.webp（8张） | 青衡宗四季昼夜全景 | OpenAI imagegen，参照项目自有昼夜图分别绘制 | 生成服务条款，项目内使用 | 2026-10-22 | 3840×2880扩绘与逐块新细节，替换旧图；提示词/来源/摘要见SEASONS366.md |
| art365-chibi | beauty/fx/sword-chibi-{jade,vermilion,indigo}.webp（3张） | 小型Q版御剑行旅 | OpenAI imagegen原创虚构人物 | 同上 | 2026-10-22 | 透明WebP，替换art364-sword旧写实人物，后者不再随包 |

| art368-peaks | beauty/scenes/xingce/hd/368/train-{chang,yan,li,shu,zi}-{day,dusk,night}.webp（15张） | 行测五峰高清昼/昏/夜 | OpenAI imagegen，参考项目自有场景，完整构图后逐原生块重绘 | 生成服务条款，项目内使用；无第三方参考图 | 2026-10-22 | 每张3840×2880，8个原生块；来源ID/原生尺寸/坐标/SHA256见hd/368/provenance.json及根目录ART368.md；旧观星图保留供天机台 |
| art3610-selection | beauty/trial/hd/3610/selection.webp | 套卷/板块选择殿堂背景 | OpenAI imagegen原创构图，各8块原生重绘合成 | 生成服务条款，项目内使用；无第三方参考图 | 2026-10-23 | 3840×2880；相邻provenance及根目录ART3610.md；不用于法考 |
| art3610-loading | beauty/loading/3610/{dawn,night}.webp | 晨云/夜湖启动加载背景 | OpenAI imagegen原创构图，每幅8块原生重绘合成 | 生成服务条款，项目内使用；无第三方参考图 | 2026-10-23 | 各3840×2880；相邻provenance及根目录ART3610.md；电脑/平板中央安全区 |
| art368-seasons | beauty/scenes/xingce/hd/368/home-{spring,summer,autumn,winter}-{day,night}.webp（8张） | 行测宗丰富四季昼夜全景，替换art366八图 | 同上，保留现有固定地标与季节主调，增加混合植物/景物层次 | 同上 | 2026-10-22 | 原生分块3840×2880，无AI超分；项目当前使用本组，art366为可从Git恢复的历史记录；详细提示词要点见ART368.md |
