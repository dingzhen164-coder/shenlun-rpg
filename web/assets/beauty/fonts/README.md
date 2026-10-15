# 字体

标题字体（离线 woff2，不用 CDN）。放入后在 `REGISTRY.md` 写字体名、作者、许可证（需允许嵌入和再分发，如 SIL OFL）。文件名：`title.woff2`、`title-bold.woff2`。缺失时用系统楷体/宋体。

## 已放入（3.2.x）
- `zcool-xiaowei/`：行测标题字体（ZCOOL XiaoWei，OFL）。
- `noto-serif-sc/`：申论、法考标题字体（Noto Serif SC 700，OFL），分片 woff2 按需加载（总约5MB，只下载用到的片）。
换字体：新建同结构文件夹（woff2 分片 + font.css + OFL 文本），在 `web/index.html` 加 `<link>`，再改 `style.css`/`shenlun_ui.css` 里对应科目的 `--display` 把字体名放最前。
