/*
  外观与音乐（rpg/appearance.py 提供数据）：背景、语录、BGM。
  - 背景：用 训练/外观/背景/ 里自己放的图片（程序不再自带背景）。
  - 语录：训练/语录.md 一行一句；竖排淡淡地浮在页面右侧（窄屏时在底部）。
  - 语录大小：quote_size 是倍数（0.5 ~ 2），乘在 CSS 的字号上（宽屏竖排、窄屏底部横排都按它缩放）。
  - BGM：默认关闭，顶栏 ♪ 打开，顺序循环或随机播放 训练/外观/音乐/ 里的音频（程序不自带音乐）。
  对外：AMB.load()、AMB.apply(cur)、AMB.save(patch)、AMB.settingsHtml()、AMB.bindSettings()。
*/
const AMB = (() => {
  let DATA = null;            // /api/appearance 的返回
  let QUOTE = "";             // 本次打开显示的语录（随机模式每次打开换一句）
  // 明暗：每台设备各自记（localStorage），默认亮色；"auto" = 跟随系统
  const themeMode = () => { try { return localStorage.getItem("xrpg-theme") || "light"; } catch (e) { return "light"; } };
  function setTheme(mode) {
    try { localStorage.setItem("xrpg-theme", mode); } catch (e) { /* 存不了就只管这一次 */ }
    const m = mode === "auto" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : mode;
    document.documentElement.dataset.theme = m;
    document.documentElement.style.colorScheme = m;
  }
  function bgCss(key) {
    if (!key || key === "none") return "";
    if (key.startsWith("file:")) return `url("/vault-file?p=${encodeURIComponent(key.slice(5))}")`;
    return "";
  }

  function pickQuote(cur) {
    const qs = DATA?.quotes || [];
    if (cur.quote === "off" || !qs.length && cur.quote !== "fixed") return "";
    if (cur.quote === "fixed") return cur.fixed || qs[0] || "";
    if (cur.quote === "daily") return DATA.daily || qs[0];
    if (!QUOTE || !qs.includes(QUOTE)) QUOTE = qs[Math.floor(Math.random() * qs.length)];
    return QUOTE;
  }

  function apply(cur) {
    cur = cur || DATA?.current;
    if (!cur) return;
    const layer = document.getElementById("bgLayer"), ql = document.getElementById("quoteLayer");
    const css = bgCss(cur.bg);
    layer.style.backgroundImage = css || "none";
    layer.style.setProperty("--dim", String(cur.dim ?? 0.35));
    document.body.classList.toggle("has-bg", !!css);
    ql.textContent = pickQuote(cur);
    ql.style.setProperty("--quote-scale", String(cur.quote_size ?? 1));
    BGM.setVolume(cur.volume);
    window.BeautyAudio?.setBgmVolume(cur.volume ?? 0.35);
  }

  let loadedAt=0;
  async function load({cached=false}={}) {
    if(cached&&DATA&&Date.now()-loadedAt<30000)return;
    try { DATA = await fetch("/api/appearance").then((r) => r.json());loadedAt=Date.now();apply(); } catch (e) { /* 没有库时不影响使用 */ }
  }
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => { if (themeMode() === "auto") { setTheme("auto"); apply(); } });

  async function save(patch) {
    const r = await fetch("/api/appearance", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }).then((x) => x.json());
    if (r.error) throw new Error(r.error);
    DATA.current = r.current;
    apply();
    return r.current;
  }

  // ---------------------------------------------------------------- BGM
  const BGM = (() => {
    let on = false, audio = null, list = [], idx = 0, vol = 0.35;

    function playFile() {
      if (!list.length) return;
      audio = new Audio(`/vault-file?p=${encodeURIComponent(list[idx % list.length])}`);
      audio.volume = vol;
      audio.onended = () => { idx = nextIdx(); if (on) playFile(); };
      audio.play().catch(() => {});
    }

    // 随机播放：把整个列表洗一遍，放完一轮再洗（不会连着两首一样，也不会一首老不轮到）
    let bag = [];
    function nextIdx() {
      if (!(DATA?.current?.shuffle) || list.length < 2) return (idx + 1) % list.length;
      if (!bag.length) bag = list.map((_, i) => i).filter((i) => i !== idx).sort(() => Math.random() - 0.5);
      return bag.shift();
    }
    function start() {
      const cur = DATA?.current || {};
      const music = DATA?.music || [];
      if (!music.length) {
        alert(`还没有背景音乐：把 mp3 / ogg / m4a / wav 放进库里的「${DATA?.folders?.music || "训练/外观/音乐/"}」，刷新网页后再点 ♪。`);
        return;
      }
      vol = cur.volume ?? 0.35;
      list = music; bag = [];
      idx = cur.shuffle ? Math.floor(Math.random() * music.length) : Math.max(0, music.indexOf(cur.track));
      playFile();
      on = true; btn();
    }
    function stop() {
      on = false;
      if (audio) { audio.pause(); audio = null; }
      btn();
    }
    function btn() {
      const b = document.getElementById("bgmBtn");
      if (!b) return;
      b.classList.toggle("on", on);
      b.title = on ? "背景音乐：开（点一下关闭）" : "背景音乐：关（点一下打开）";
    }
    return {
      toggle() { on ? stop() : start(); },
      restart() { if (on) { stop(); start(); } },
      setVolume(v) { vol = v ?? vol; if (audio) audio.volume = vol; },
      get on() { return on; },
    };
  })();

  // ---------------------------------------------------------------- 设置页
  function settingsHtml() {
    if (!DATA?.current) return `<div class="card"><h3>🌄 外观与音乐</h3><p class="small muted">先在下面设置好行测库路径。</p></div>`;
    const c = DATA.current, esc2 = (s) => String(s ?? "").replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
    const tile = (key, label) => `<button class="bg-tile ${c.bg === key ? "sel" : ""}" data-bg="${esc2(key)}" title="${esc2(label)}">
      <span class="bg-thumb" style='background-image:${bgCss(key) || "none"}'></span><span class="bg-name">${esc2(label)}</span></button>`;
    const files = DATA.backgrounds.map((p) => tile("file:" + p, p.split("/").pop())).join("");
    const qOpt = (v, t) => `<option value="${v}" ${c.quote === v ? "selected" : ""}>${t}</option>`;
    const tm = themeMode(), tOpt = (v, t) => `<option value="${v}" ${tm === v ? "selected" : ""}>${t}</option>`;
    return `<div class="card"><h3>🌄 外观与音乐 <small>选择会同步到另一台电脑（明暗除外）</small></h3>
      <div class="row" style="align-items:center;gap:10px;margin-bottom:8px"><label>明暗 <select id="ambTheme" style="width:auto">
        ${tOpt("light", "浅色 · 宣纸（默认）")}${tOpt("dark", "深色 · 墨夜")}${tOpt("auto", "跟随系统")}</select></label>
        <span class="small muted">只影响这台设备（电脑、平板各选各的）</span></div>
      <label class="small muted">背景（点一下立即换）</label>
      <div class="bg-grid">${tile("none", "不用背景")}${files}</div>
      <p class="small muted">背景用自己的图片：放进库里的 <b>${esc2(DATA.folders.bg)}</b>（jpg / png / webp），刷新本页就会出现在上面。</p><p class="small muted">分区图片：放入 <b>训练/外观/五脉/</b>，以分区名称命名，例如万象峰.png；申论按题型名，法考按科目名命名。返回分区选择页即可刷新。</p>
      <div class="row"><label style="flex:1">背景遮罩（越大越暗、字越清楚）<input type="range" id="ambDim" min="0" max="0.85" step="0.05" value="${c.dim}"></label></div>
      <hr class="soft">
      <div class="row"><label style="flex:1">语录 <select id="ambQuote">${qOpt("daily", "每日一句")}${qOpt("random", "每次打开随机")}${qOpt("fixed", "固定一句")}${qOpt("off", "不显示")}</select></label>
        <label style="flex:2">固定显示哪一句 <select id="ambFixed">${DATA.quotes.map((q) => `<option ${q === c.fixed ? "selected" : ""}>${esc2(q)}</option>`).join("")}</select></label></div>
      <div class="row" style="align-items:center;gap:12px;margin-top:6px"><label style="flex:1">语录大小 <b id="ambQSizeV">${Math.round((c.quote_size ?? 1) * 100)}%</b>
        <input type="range" id="ambQSize" min="0.5" max="2" step="0.1" value="${c.quote_size ?? 1}"></label></div>
      <p class="small muted">语录在库里的 <b>${esc2(DATA.folders.quotes)}</b>，一行一句（“- ”开头），自己加、改、删，刷新生效。现在共 ${DATA.quotes.length} 句。</p>
      <hr class="soft">
      ${musicHtml(c, esc2)}
      <hr class="soft">
      <label class="small muted">美术文件夹（换首页全景、每个子地图的背景、人物立绘、内置音乐音效，不用改源代码）</label>
      <p class="small" style="margin:4px 0">位置：库里的 <b>训练/外观/美术/</b>（<span id="artState">…</span>）。里面按中文名分文件夹：<b>首页全景</b>（白天、夜晚）、<b>子地图背景</b>（地点名、地点名-白天、地点名-夜晚）、<b>人物立绘</b>、<b>音乐</b>、<b>音效</b>。放进去、刷新网页就生效；删掉文件就恢复程序自带的。</p>
      <div class="row" style="align-items:center;gap:10px;flex-wrap:wrap"><button id="artExport" class="small">导出程序自带美术（当模板）</button><span id="artMsg" class="small muted"></span></div>
      <p class="small muted">导出会把程序自带的全景、立绘、音乐、音效按上面的名字复制进美术文件夹（已有的不覆盖）；文件夹里的“说明.txt”写了每个文件的用途和建议尺寸。</p></div>`;
  }

  // 背景音乐与声音（3.2.x：内置场景音乐、我的音乐、音效合在一起）
  function musicHtml(c, esc2) {
    const st = window.BeautyAudio?.settings || { sfx: true, bgm: true, vs: 0.6, src: "builtin" }, has = DATA.music.length > 0;
    const src = st.src === "mine" && has ? "mine" : "builtin";
    return `<label class="small muted">背景音乐与音效</label>
      <div class="row" style="align-items:center;gap:14px;flex-wrap:wrap"><label style="flex:none"><input type="checkbox" id="baBgm" ${st.bgm ? "checked" : ""} style="width:auto"> 背景音乐</label>
        <label style="flex:2;min-width:200px">来源 <select id="baSrc"><option value="builtin" ${src === "builtin" ? "selected" : ""}>内置场景音乐（随地图、洞府、答题自动切换）</option>
          <option value="mine" ${src === "mine" ? "selected" : ""} ${has ? "" : "disabled"}>我的音乐${has ? "" : "（库里还没有）"}</option></select></label>
        <label style="flex:1;min-width:160px">音乐音量 <input type="range" id="ambVol" min="0" max="1" step="0.05" value="${c.volume}"></label></div>
      <div class="row" id="ambMine" style="${src === "mine" ? "" : "display:none"}">${has ? `<label style="flex:2">曲目 <select id="ambTrack">
          ${DATA.music.map((p) => `<option value="${esc2(p)}" ${c.track === p ? "selected" : ""}>${esc2(p.split("/").pop())}（顺序循环时从这首开始）</option>`).join("")}</select></label>
        <label style="flex:1">播放顺序 <select id="ambShuffle"><option value="0" ${c.shuffle ? "" : "selected"}>顺序循环</option><option value="1" ${c.shuffle ? "selected" : ""}>随机播放</option></select></label>` : ""}</div>
      <div class="row" style="align-items:center;gap:14px;flex-wrap:wrap"><label style="flex:none"><input type="checkbox" id="baSfx" ${st.sfx ? "checked" : ""} style="width:auto"> 音效与环境声（点击、答题、翻页、鸟虫流水等）</label>
        <label style="flex:1;min-width:160px">音效音量 <input type="range" id="baSfxVol" min="0" max="1" step="0.05" value="${st.vs}"></label></div>
      <p class="small muted">第一次点一下页面后才会发声。内置音乐和音效在 <b>web/assets/beauty/audio/</b>，想换成自己的，同名覆盖即可（见该文件夹说明）。“我的音乐”放进 <b>${esc2(DATA.folders.music)}</b>（mp3 / ogg / m4a / wav），刷新本页后在上面选。右下角喇叭可一键静音。</p>`;
  }

  function bindSettings(onErr) {
    const guard = (p) => p.catch((e) => onErr ? onErr(e) : alert(e.message));
    document.querySelectorAll("[data-bg]").forEach((b) => (b.onclick = () => guard(save({ bg: b.dataset.bg }).then(() => {
      document.querySelectorAll("[data-bg]").forEach((x) => x.classList.toggle("sel", x === b));
    }))));
    const th = document.getElementById("ambTheme");
    if (th) th.onchange = () => { setTheme(th.value); apply(); if (typeof render === "function") render(); };
    fetch("/api/art").then((r) => r.json()).then((d) => { const el = document.getElementById("artState"); if (el) el.textContent = d.path ? `${d.path}，已有 ${d.count} 个覆盖文件${d.characters && d.characters.length ? "；人物立绘：" + d.characters.join("、") : ""}${d.pillow === false ? "；⚠ 没装 Pillow，纯色底立绘无法自动去底（pip install pillow）" : ""}` : (d.exists ? `已有 ${d.count} 个覆盖文件` : "还没创建，点下面导出会自动创建"); }).catch(() => {});
    const ex = document.getElementById("artExport");
    if (ex) ex.onclick = () => { ex.disabled = true; fetch("/api/art/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).then((r) => r.json()).then((d) => { const m = document.getElementById("artMsg"); if (d.error) throw new Error(d.error); if (m) m.textContent = `已复制 ${d.copied} 个，已有 ${d.skipped} 个未覆盖。到 ${d.folder} 里看看。`; }).catch((e) => { const m = document.getElementById("artMsg"); if (m) m.textContent = "导出失败：" + e.message; }).finally(() => { ex.disabled = false; }); };
    const dim = document.getElementById("ambDim");
    if (!dim) return;
    dim.oninput = () => document.getElementById("bgLayer").style.setProperty("--dim", dim.value);
    dim.onchange = () => guard(save({ dim: Number(dim.value) }));
    document.getElementById("ambQuote").onchange = (e) => { QUOTE = ""; guard(save({ quote: e.target.value })); };
    const qs = document.getElementById("ambQSize");
    qs.oninput = () => { document.getElementById("quoteLayer").style.setProperty("--quote-scale", qs.value);
      document.getElementById("ambQSizeV").textContent = Math.round(qs.value * 100) + "%"; };
    qs.onchange = () => guard(save({ quote_size: Number(qs.value) }));
    document.getElementById("ambFixed").onchange = (e) => guard(save({ fixed: e.target.value, quote: "fixed" }).then(() => { document.getElementById("ambQuote").value = "fixed"; }));
    const BA = window.BeautyAudio, vol = document.getElementById("ambVol");
    vol.oninput = () => { BGM.setVolume(Number(vol.value)); BA?.setBgmVolume(Number(vol.value)); };
    vol.onchange = () => guard(save({ volume: Number(vol.value) }));
    const mine = document.getElementById("ambMine");
    document.getElementById("baBgm").onchange = (e) => BA?.set({ bgm: e.target.checked });
    document.getElementById("baSrc").onchange = (e) => { if (mine) mine.style.display = e.target.value === "mine" ? "" : "none"; BA?.set({ src: e.target.value }); };
    document.getElementById("baSfx").onchange = (e) => BA?.set({ sfx: e.target.checked });
    document.getElementById("baSfxVol").oninput = (e) => BA?.setSfxVolume(Number(e.target.value));
    const tr = document.getElementById("ambTrack");
    if (tr) {
      tr.onchange = (e) => guard(save({ track: e.target.value }).then(() => BGM.restart()));
      document.getElementById("ambShuffle").onchange = (e) => guard(save({ shuffle: e.target.value === "1" }).then(() => BGM.restart()));
    }
  }

  return { load, apply, save, settingsHtml, bindSettings, bgm: BGM };
})();
