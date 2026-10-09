# 给 AI / 开发者的说明

本项目是“申论官途（申论 RPG）”：本地运行的申论训练网页（Python 标准库后端 + 原生 JS 前端），配合用户的 Obsidian 申论库使用。
代码以行测版 [xingce-rpg](https://github.com/dingzhen164-coder/xingce-rpg) 3.3.0 为底座（1.0.0 起），加上申论采分点批改；风格只保留“官场”。

**先读 [CLAUDE.md](CLAUDE.md)（长期规矩：流程、口令、版本号、汇报格式），再读 [DESIGN.md](DESIGN.md)**（决策、分层、数据格式、判分规则都在里面）。当前进度见 DESIGN.md 第 10 节。

## 必须遵守

1. 只用 Python 标准库，兼容 Python 3.8；前端不引入构建工具和外部 CDN（离线也要能用）。
2. 只写库里的 `训练/` 文件夹；skill 和真题原文只读。
3. **分数和经验只由程序计算，AI 只做判断**（采分点命中、量表档位、失分类型）。AI 输出必须是校验过的 JSON。
4. 用户可调的数值放 `规则.md`，不要写死在代码里。
5. 结构沿用行测：`rpg/`（后端）、`web/`（前端）、`defaults/`（首次启动写进库里的默认规则和台词）。申论专有的代码放 `rpg/shenlun*.py`、`web/shenlun.js`；风格名词集中在 `rpg/themes.py`。
6. 不要提交真题原文、参考答案、粉笔库数据；不要复制 GPL 项目（shenlun-review-pro）的代码或文本。
7. 中文注释，风格与 xingce-rpg 一致；新增模块在文件顶部写清“做什么、数据格式、谁调用它”。
8. 改完运行 `python -m unittest discover -s tests -v`；改了规则或数据结构，同步更新 DESIGN.md。
9. 每次升版本改 `VERSION`，并在 `changelog.md` 顶部写一节（有测试检查两者一致）。
10. 批量替换脚本先断言“只匹配一次”；新增 CSS 类名先搜有没有冲突；涉及界面要截图自查（见 CLAUDE.md 第 3 节）。

## 快速定位

| 想改的东西 | 去哪里 |
|---|---|
| 采分点文件格式、校验、分值分配、程序算分 | `rpg/shenlun_rubric.py` |
| 从解析文档起草采分点（切题、清洗水印、AI 抄表、关键词核验） | `rpg/shenlun_analysis.py` |
| 批改提示词、AI 返回校验、重试、标定 | `rpg/shenlun_grader.py` |
| 申论服务层（题目列表、批改、定稿、写复盘文件） / 接口 | `rpg/shenlun.py` / `rpg/api.py` 里的 `/api/shenlun/*` |
| 批改如何进政绩、专长、练习记录 | `rpg/engine.py`（`on_grade`、`_grade_accuracy`） |
| 职级、专长、关卡等名词 | `rpg/themes.py`、`defaults/规则.md` |
| 页面、样式（设计令牌在 `style.css` 顶部） | `web/app.js`、`web/shenlun.js`、`web/style.css` |
| 测试用假 AI（不联网） | `tests/fake_grade_ai.py` |
