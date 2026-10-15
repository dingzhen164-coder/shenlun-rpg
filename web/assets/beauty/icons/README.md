# 图标

来源：开源图标库统一调色（候选 Lucide〔ISC〕、Tabler Icons〔MIT〕、Phosphor〔MIT〕；采用前核对许可证并登记）。
- 一律 SVG，`stroke`/`fill` 用 `currentColor`，主题色由 CSS 令牌控制，换肤不改文件。
- 文件名＝图标语义（如 `home.svg`、`book.svg`、`sword.svg`、`bag.svg`、`scroll.svg`、`gear.svg`），清单随 3.2.1 开发补全。
- 许可证文本放 `LICENSES/`，每个图标库一个文件。

## 实际结构（3.2.1）
- `svg/<名字>.svg`：每个图标一个文件（来自 Lucide，24×24，描边 currentColor）。
- `emoji-map.json`：界面文字里的 emoji → 图标文件名。界面里任何出现这些 emoji 的地方，会自动显示成对应图标（原 emoji 字符仍保留在页面里，只是不可见；图标加载失败则显示原 emoji）。
- `sprite.svg`：由 `python3 tools/build_icons.py` 把 `svg/` 合成，程序只读它。
- **换图标**：覆盖 `svg/` 里同名文件 → 运行 `python3 tools/build_icons.py` → 刷新。想用别的图标，把新 svg 放进 `svg/`，在 `emoji-map.json` 改对应行，再运行脚本。
- 想让更多 emoji 变成图标：在 `emoji-map.json` 加一行。图标色跟随文字颜色，换主题自动变色。
