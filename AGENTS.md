# 给 AI / 开发者的说明

本项目是“公考模拟器”（2.0.0 起一个程序两个科目）：本地运行的公考训练网页（Python 标准库后端 + 原生 JS 前端），配合用户的 Obsidian 申论库使用。
代码以行测版 [xingce-rpg](https://github.com/dingzhen164-coder/xingce-rpg) 3.3.0 为底座，加上申论采分点批改和“官场”风格；设置里一键切换科目（`rpg/subjects.py`）。行测仓库不再单独更新。

**先读 [CLAUDE.md](CLAUDE.md)（长期规矩：流程、口令、版本号、汇报格式），再读 [DESIGN.md](DESIGN.md)**（决策、分层、数据格式、判分规则都在里面）。当前进度见 DESIGN.md 第 10 节。 **踩坑记录（用户2026-10-25要求，Claude Code 与 Codex 都遵守）：每修复一个 bug，都要在 [踩坑记录.md](踩坑记录.md) 补一条“现象→根因→以后怎么做→回归测试”，与修复同一批提交；改背景图/场景美术、测试发布、界面、PDF 识别前先读对应章节。**

## 必须遵守

1. 只用 Python 标准库，兼容 Python 3.8；前端不引入构建工具和外部 CDN（离线也要能用）。
2. 只写库里的 `训练/` 文件夹；skill 和真题原文只读。
3. **分数和经验只由程序计算，AI 只做判断**（采分点命中、量表档位、失分类型）。AI 输出必须是校验过的 JSON。
4. 用户可调的数值放 `规则.md`，不要写死在代码里。
5. 结构：`rpg/`（后端）、`web/`（前端）、`defaults/`（首次启动写进库里的默认规则和台词；申论的在 `defaults/申论/`）。**科目差异靠 `rpg/subjects.py` 的科目表和 `Game.subject`**：申论专有代码放 `rpg/shenlun*.py`、`web/shenlun.js`、`web/contest_sl.js`；行测专有（题库、试炼塔、成语录、模考）在申论下用 `g.subject` 判断后跳过，网页用 `DASH.features` / `isSL()` 隐藏。两个科目共用一套**标准规则键**（行测叫法），申论规则文件的官场叫法在 `config.ALIASES_SHENLUN` 翻回标准键；风格名词在 `rpg/themes.py`（修仙、玄幻）和 `rpg/themes_guanchang.py`（官场）。
6. 不要提交真题原文、参考答案、粉笔库数据；不要复制 GPL 项目（shenlun-review-pro）的代码或文本。
7. 中文注释，风格与 xingce-rpg 一致；新增模块在文件顶部写清“做什么、数据格式、谁调用它”。
8. 日常开发做相关快速检查并推送开发分支；用户要求统一验证发布时，运行 `python -m unittest discover -s tests -v`、浏览器与三端验证。改了规则或数据结构，同步更新 DESIGN.md。
9. 每次升版本改 `rpg/version.py`，并在 `rpg/data/changelog.md` 顶部写一节（有测试检查两者一致）。
10. 批量替换脚本先断言“只匹配一次”；新增 CSS 类名先搜有没有冲突；涉及界面先跑 `node tests/ui_layout_check.cjs`，出问题或改外观才看截图（见 CLAUDE.md 第 3 节第 6 条）。
11. 开工前先读 [交接.md](交接.md)。
12. **统一验证发布时省额度**（用户2026-10-22约定，细则见 CLAUDE.md「发布验证省额度」）：只验证一次；失败先读日志定位再改；等云端用一次长等待，不反复查状态；本机已验证过的不在云端重做。
13. **所有 UI 更新与高清图制作同时兼顾电脑、平板**（用户2026-10-23约定，细则见 CLAUDE.md「所有 UI 更新与高清图制作」）：出图前规划电脑与平板横竖屏构图、主体安全区域及界面留白；接入后检查两端取景、清晰度、文字可读和入口可点，不能只验电脑横屏。

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
| 申论完整真题题库、材料对应、作答草稿 | `rpg/shenlun_bank.py` |
| 综合批改（标准、提示词、校验、校准、复盘） | `rpg/shenlun_review.py` |
| 大作文写作支架（立意拆解、提纲点评） | `rpg/shenlun_essay.py` |
| 申论作答计时活动记录 / 接口 | `rpg/shenlun.py` / `rpg/api.py` 里的 `/api/shenlun/*` |
| 题库、试炼塔、成语录、模考（行测） | `rpg/question_bank.py`、`rpg/importer.py`、`rpg/idioms.py`、`rpg/mock.py` |
| 行测 `训练/` 六大类目录映射与自动迁移 | `rpg/paths.py`（`XINGCE_6_TOP_DIRS`、`XINGCE_6_MAP`、`XingceTrainPath`、`migrate_xingce_dirs`）；本地 Agent 与 `gk-skill` 规则说明在 `defaults/gk-skill-AGENTS.md` |
| 思过崖（数量关系只收错题/慢题、十八讲可展开目录）与政治理论易错题集 | `rpg/siguo.py`（`SHULIANG_18_LECTURES`、`prune_shuliang_doc`、`politics_wrong_*`）、`web/siguo.js` |
| 万象峰时政地图（新增/编辑时政范围/删除、导出 `.md`、五栏含分类时政与易错题） | `rpg/politics.py`（`exams_list`、`exam_save`、`exam_delete`、`export_exam_markdowns`、`classified_items`）、`web/study_regions.js`、`web/atlas.js` |
| 页面、样式（设计令牌在 `style.css` 顶部；`body.xiuxian / xuanhuan / guantu` 三套配色） | `web/app.js`、`web/shenlun.js`、`web/style.css` |
| 测试（每个测试文件顶部 `setUpModule` 指定本文件跑在哪个科目）；假 AI | `tests/`；`tests/fake_grade_ai.py` |

## 行测本地 Agent 与 `gk-skill` 协同规则（用户2026-11-20约定，详见 `defaults/gk-skill-AGENTS.md`）

1. **行测 `训练/` 六大类目录**：`思过崖/`、`万象峰/`、`藏经阁/`、`试炼与大比/`、`规则与设定/`、`系统/`（由 `rpg/paths.py` 的 `XingceTrainPath` 与 `migrate_xingce_dirs` 自动映射与无损迁移）。
2. **数量关系分流（十八讲 vs 思过崖错题集）**：正常数量关系训练题按题型归入「数量关系十八讲」对应 `.md` 文档；**只有错题和慢题（含不会/蒙对/有思维卡点）**才计入 `错题集/数量关系.md`（思过崖），且必须注明 `所属课程：第XX课-XXX`，在思过崖左侧按十八讲目录可展开显示。
3. **万象峰时政地图与政治理论双重检索**：
   - 每个时政地图有明确的时政时间范围（可在政治理论页新增、编辑范围、删除）；月半时政与专题时政按时间归入对应地图，并在 `训练/万象峰/<时政地图名>/{月半时政,专题时政,冲刺学习}/*.md`（同步镜像至 `gk-skill/时政地图/`）自动保存为 Markdown 文档。
   - 用户发政治理论题目时，Agent 必须**同时检索小黑政治理论 skill 与对应时政地图下的 `.md` 时政内容，并明确注明出自哪个具体文件**。
   - 政治理论错题记入独立的政治理论易错题集（`gk-skill/错题集/政治理论.md` → 同步至 `训练/万象峰/易错题.md`），**不在思过崖 7 石碑显示**，而是在时政地图顶栏五栏（`月半时政 · 专题时政 · 冲刺学习 · 分类时政 · 易错题`）的「易错题」栏按思过崖模板展示。

**多个AI并行开发与统一发布（用户2026-10-25约定）：推送开发分支≠发布；推送前先合并远端开发分支、不 force；版本号与更新记录只在发布时改一次；创建 validate 分支前必须先运行 `python3 tools/release_precheck.py --tests`，有“失败”项不得发布。详见 CLAUDE.md「多个AI并行开发与统一发布」。**

