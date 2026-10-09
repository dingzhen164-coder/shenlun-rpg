# 申论官途（shenlun-rpg）

把申论备考做成“官场”主题的本地训练网页：**采分点批改** + 职级成长（办事员 → 正厅级）。
只在你自己的电脑上运行（浏览器打开 `127.0.0.1`），数据放在你的 Obsidian 申论库里，AI 用你自己的 DeepSeek key。

- 姊妹项目：[xingce-rpg](https://github.com/dingzhen164-coder/xingce-rpg)（行测修仙传），日后合并
- 开发者 / AI：先读 [AGENTS.md](AGENTS.md) 和 [DESIGN.md](DESIGN.md)

---

## 一、安装 / 更新（Windows PowerShell，一条命令，装和更新是同一条）

程序会装到你的申论库里：`C:\Users\29356\Desktop\申论obsidian\申论\训练\程序\`。
你的数据（采分点、作答、存档）在「程序」文件夹外面，**更新只替换「程序」，数据不动**，旧程序会备份到 `训练\更新备份\`。
因为程序在这个位置，它**自动认得你的申论库**，不用再设路径。

**1. 装 Python**（装过就跳过）：https://www.python.org/downloads/ ，安装界面最下面务必勾 “Add Python to PATH”。

**2. 打开 PowerShell，粘贴这一段运行**（自动从 GitHub 下载）：

```powershell
$s="$env:TEMP\update-shenlun.ps1"; Invoke-WebRequest "https://raw.githubusercontent.com/dingzhen164-coder/shenlun-rpg/claude/dazzling-fermat-0n9kbc/scripts/update-local.ps1" -OutFile $s -UseBasicParsing; powershell -ExecutionPolicy Bypass -File $s
```

如果直连 GitHub 不通，就用浏览器在仓库页点 Code → Download ZIP（存到「下载」文件夹），然后把上面最后的 `-File $s` 改成 `-File $s -Local`。

**3. 启动**（二选一）：

```powershell
python "C:\Users\29356\Desktop\申论obsidian\申论\训练\程序\server.py"
```

或者双击 `训练\程序\启动申论官途.bat`。黑色窗口不要关，关了就退出。浏览器会自动打开。

**4. 网页里用**：
- 顶栏「设置」→ 填 DeepSeek API Key → 点「测试连接」；
- 「档案室」→「题库 · 采分点」→ 导入解析文档 → 选真题解析 PDF → 前缀填 `国考2026-副省` → 「让 AI 起草采分点」
  （第一次导入 PDF 若提示缺组件，点页面上的「安装 PDF 读取组件」，需联网，只装一次）；
- 「办理」→「实操」→ 点一道题 →（采分点草稿先「审定并定稿」）→ 写答案 →「交卷批改」。
  每次批改会自动在 `训练\作答\日期\` 存一份复盘，Obsidian 里直接能看。

**以后更新**：先关掉黑色窗口，再重新运行第 2 步那一段，然后重新启动。

> 想放别的位置：给脚本加参数 `-TrainPath "D:\你的路径\训练"`（装在别处时，到网页「设置」里填申论库路径）。

Mac / 不想用 PowerShell：下载 ZIP 解压，双击 `启动申论官途.command`（Windows 双击 `启动申论官途.bat`）；
更新用 `更新.bat` / `python3 update.py`。

## 二、你的数据都在哪

| 位置 | 内容 |
|---|---|
| `<申论库>/训练/程序/` | 程序本体（更新只换这里） |
| `<申论库>/训练/资料/` | 你导入的解析文档副本 |
| `<申论库>/训练/采分点/` | 每题一个 .md，可以在 Obsidian 里直接改（改完回网页刷新） |
| `<申论库>/训练/作答/` | 每次批改的复盘 |
| `<申论库>/训练/存档/` | 练习记录（每天自动备份，保留 14 份）；0.x 旧存档自动备份为 `存档-旧版.json` |
| `C:\Users\你\.shenlun-rpg\settings.json` | API key、库路径（只在这台电脑，不进仓库） |

没设置库路径时，数据放在程序旁边的 `data/` 文件夹。

## 三、常见问题

- **双击闪退 / 提示没有 Python**：回到第 1 步，确认勾了 “Add Python to PATH”，装完重新双击。
- **浏览器没自动打开**：看黑色窗口里的地址（`http://127.0.0.1:8766/`），手动粘贴到浏览器。
- **识别不到题 / 版式不支持**：不同机构的文档版式不一样，把文件发给开发者适配。
- **采分点要改**：直接在 Obsidian 里打开 `训练/采分点/某题.md` 改，格式见文件里的例子；
  每行 `- [分值] 名称 | 关键词: 词1；词2 | 依据: 第几段`，所有分值加起来要等于总分才能定稿。
- **AI 批改失败**：多半是 key 没填或没网；网页会提示原因，这次不计分、不进记录，重试即可。

## 四、开发

```bash
python server.py                              # 启动
python -m unittest discover -s tests -v       # 测试（用假 AI，不联网、不花钱）
python -m rpg.shenlun_analysis 文档.pdf --prefix 前缀 --list   # 命令行查看识别结果
python -m rpg.shenlun_grader 文档.pdf --prefix 前缀             # 用参考答案标定采分点
```
