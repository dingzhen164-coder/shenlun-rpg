# 素材登记表

每放入或更换一个素材，追加一行。来源写清楚（工具/网址/作者），授权写清楚（许可证名称或“用户自有/生成服务条款”）。

| 编号 | 路径（相对 web/assets） | 用途 | 来源 | 授权 | 日期 | 生成提示词/备注 |
|---|---|---|---|---|---|---|
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
