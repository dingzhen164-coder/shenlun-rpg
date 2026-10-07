# 给 AI / 开发者的说明

本项目是“申论官途（申论 RPG）”：本地运行的申论训练网页（Python 标准库后端 + 原生 JS 前端），配合用户的 Obsidian 申论库使用。
姊妹项目 [xingce-rpg](https://github.com/dingzhen164-coder/xingce-rpg) 是行测版，日后会合并。

**先读 [CLAUDE.md](CLAUDE.md)（长期规矩：流程、口令、版本号、汇报格式），再读 [DESIGN.md](DESIGN.md)**（决策、分层、数据格式、判分规则都在里面）。当前进度见 DESIGN.md 第 10 节（M0 完成，M1 进行中：采分点、批改、作答页已可用）。

## 必须遵守

1. 只用 Python 标准库，兼容 Python 3.8；前端不引入构建工具和外部 CDN（离线也要能用）。
2. 只写库里的 `训练/` 文件夹；skill 和真题原文只读。
3. **分数和经验只由程序计算，AI 只做判断**（采分点命中、量表档位、失分类型）。AI 输出必须是校验过的 JSON。
4. 用户可调的数值放 `规则.md`，不要写死在代码里。
5. `core/` 不得出现申论或行测的科目词汇；科目差异放 `subjects/<科目>/`，事件和进度带 `subject` 字段。
6. 不要提交真题原文、参考答案、粉笔库数据；不要复制 GPL 项目（shenlun-review-pro）的代码或文本。
7. 中文注释，风格与 xingce-rpg 一致；新增模块在文件顶部写清“做什么、数据格式、谁调用它”。
8. 改完运行 `python -m unittest discover -s tests -v`；改了规则或数据结构，同步更新 DESIGN.md。
9. 每次升版本改 `VERSION`，并在 `changelog.md` 顶部写一节（有测试检查两者一致）。
10. 批量替换脚本先断言“只匹配一次”；新增 CSS 类名先搜有没有冲突；涉及界面要截图自查（见 CLAUDE.md 第 3 节）。

## 快速定位

| 想改的东西 | 去哪里 |
|---|---|
| 采分点文件格式、校验、分值分配、程序算分 | `subjects/shenlun/rubric.py` |
| 从解析文档起草采分点（切题、清洗水印、AI 抄表、关键词核验） | `subjects/shenlun/analysis.py` |
| 批改提示词、AI 返回校验、重试、标定 | `subjects/shenlun/grader.py` |
| 申论接口（题目列表、批改、定稿、写复盘文件） | `subjects/shenlun/routes.py`（由 `core/api.py` 转发） |
| 页面、样式（设计令牌在 `style.css` 顶部） | `web/app.js`、`web/style.css` |
| 测试用假 AI（不联网） | `tests/fake_ai_server.py` |
