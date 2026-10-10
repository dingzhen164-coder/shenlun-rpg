# 给 AI / 开发者的说明

本项目是“公考模拟器”（2.0.0 起一个程序两个科目）：本地运行的公考训练网页（Python 标准库后端 + 原生 JS 前端），配合用户的 Obsidian 申论库使用。
代码以行测版 [xingce-rpg](https://github.com/dingzhen164-coder/xingce-rpg) 3.3.0 为底座，加上申论采分点批改和“官场”风格；设置里一键切换科目（`rpg/subjects.py`）。行测仓库不再单独更新。

**先读 [CLAUDE.md](CLAUDE.md)（长期规矩：流程、口令、版本号、汇报格式），再读 [DESIGN.md](DESIGN.md)**（决策、分层、数据格式、判分规则都在里面）。当前进度见 DESIGN.md 第 10 节。

## 必须遵守

1. 只用 Python 标准库，兼容 Python 3.8；前端不引入构建工具和外部 CDN（离线也要能用）。
2. 只写库里的 `训练/` 文件夹；skill 和真题原文只读。
3. **分数和经验只由程序计算，AI 只做判断**（采分点命中、量表档位、失分类型）。AI 输出必须是校验过的 JSON。
4. 用户可调的数值放 `规则.md`，不要写死在代码里。
5. 结构：`rpg/`（后端）、`web/`（前端）、`defaults/`（首次启动写进库里的默认规则和台词；申论的在 `defaults/申论/`）。**科目差异靠 `rpg/subjects.py` 的科目表和 `Game.subject`**：申论专有代码放 `rpg/shenlun*.py`、`web/shenlun.js`、`web/contest_sl.js`；行测专有（题库、试炼塔、成语录、模考）在申论下用 `g.subject` 判断后跳过，网页用 `DASH.features` / `isSL()` 隐藏。两个科目共用一套**标准规则键**（行测叫法），申论规则文件的官场叫法在 `config.ALIASES_SHENLUN` 翻回标准键；风格名词在 `rpg/themes.py`（修仙、玄幻）和 `rpg/themes_guanchang.py`（官场）。
6. 不要提交真题原文、参考答案、粉笔库数据；不要复制 GPL 项目（shenlun-review-pro）的代码或文本。
7. 中文注释，风格与 xingce-rpg 一致；新增模块在文件顶部写清“做什么、数据格式、谁调用它”。
8. 改完运行 `python -m unittest discover -s tests -v`；改了规则或数据结构，同步更新 DESIGN.md。
9. 每次升版本改 `rpg/version.py`，并在 `rpg/data/changelog.md` 顶部写一节（有测试检查两者一致）。
10. 批量替换脚本先断言“只匹配一次”；新增 CSS 类名先搜有没有冲突；涉及界面要截图自查（见 CLAUDE.md 第 3 节）。

## 快速定位

| 想改的东西 | 去哪里 |
|---|---|
| 科目表（库路径、风格、功能开关）、当前科目 | `rpg/subjects.py`；设置里切换 `/api/subject` |
| 找库、本机设置、每个科目的默认文件 | `rpg/paths.py`（`find_vault(subject)`、`Paths(vault, subject)`、`load_settings`） |
| 规则键、规则别名（申论官场叫法 → 标准键）、默认分批 / 题型 | `rpg/config.py`（改规则要同步 `defaults/规则.md` 和 `defaults/申论/规则.md`；有测试检查申论文件的键都认识） |
| 申论的仕途（单位、岗位、职级、背景、直属领导；导师随阶段切换）：数据 `defaults/申论/职务履历.md`（用户的在 `训练/职务履历.md`），解析与取值 `rpg/career.py`，引擎接入 `engine.realm_label / career_info / _apply_career` |
| 风格名词（修仙 / 玄幻 / 官场）、职级、专长名 | `rpg/themes.py`、`rpg/themes_guanchang.py` |
| 申论科目下网页和提示词里的措辞改写 | `rpg/wording.py`（`MAP`、`WEB_EXTRA`；只改程序写的字，不改用户内容） |
| 游戏规则逻辑（政绩、职级、打卡、周例会、批改成绩计入）| `rpg/engine.py`（`on_grade`、`_grade_accuracy`） |
| 训练流程（要点 / 汇报 / 整改 / 晋升考核……的对话步骤） | `rpg/trainer.py`、`rpg/prompts.py` |
| 采分点文件格式、校验、分值分配、程序算分 | `rpg/shenlun_rubric.py` |
| 从解析文档起草采分点 | `rpg/shenlun_analysis.py` |
| 批改提示词、AI 返回校验、重试、标定 | `rpg/shenlun_grader.py` |
| 申论服务层 / 接口 | `rpg/shenlun.py` / `rpg/api.py` 里的 `/api/shenlun/*` |
| 题库、试炼塔、成语录、模考（行测） | `rpg/question_bank.py`、`rpg/importer.py`、`rpg/idioms.py`、`rpg/mock.py` |
| 页面、样式（设计令牌在 `style.css` 顶部；`body.xiuxian / xuanhuan / guantu` 三套配色） | `web/app.js`、`web/shenlun.js`、`web/style.css` |
| 测试（每个测试文件顶部 `setUpModule` 指定本文件跑在哪个科目）；假 AI | `tests/`；`tests/fake_grade_ai.py` |
