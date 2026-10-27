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
    try { DATA = await fetch("/api/appearance").then((r) => r.json());loadedAt=Date.now();apply(); window.BeautyAudio?.sync(); } catch (e) { /* 没有库时不影响使用 */ }
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
      if (!list.length || !on) return;
      if (audio) { audio.onended = null; audio.pause(); }
      const current = audio = new Audio(`/vault-file?p=${encodeURIComponent(list[idx % list.length])}`);
      window.AudioBus.volume(current, vol);
      current.onended = () => { idx = nextIdx(); if (on) playFile(); };
      current.onerror = () => { if (audio === current) { on = false; current.pause(); btn(); status('这首音乐无法播放，请检查文件格式或换一首。'); } };
      current.play().catch(() => { if (audio === current) { on = false; btn(); status('音乐未能开始，请再点一次播放。'); } });
    }
    function status(text) { const el = document.getElementById('ambMusicStatus'); if (el) el.textContent = text; }

    // 随机播放：把整个列表洗一遍，放完一轮再洗（不会连着两首一样，也不会一首老不轮到）
    let bag = [];
    function nextIdx() {
      if (!(DATA?.current?.shuffle) || list.length < 2) return (idx + 1) % list.length;
      if (!bag.length) bag = list.map((_, i) => i).filter((i) => i !== idx).sort(() => Math.random() - 0.5);
      return bag.shift();
    }
    function start() {
      if (on) return;
      const cur = DATA?.current || {}, music = DATA?.music || [];
      if (!music.length) { status('音乐库为空，请先放入音乐文件，再刷新本页。'); return; }
      vol = cur.volume ?? 0.35;
      list = music; bag = [];
      idx = cur.shuffle ? Math.floor(Math.random() * music.length) : Math.max(0, music.indexOf(cur.track));
      on = true; playFile(); btn(); status('');
    }
    function stop() {
      on = false;
      if (audio) { audio.onended = null; audio.pause(); audio = null; }
      btn();
    }
    function btn() {
      const b = document.getElementById("bgmBtn");
      if (!b) return;
      b.classList.toggle("on", on);
      b.title = on ? "背景音乐：开（点一下关闭）" : "背景音乐：关（点一下打开）";
    }
    return {
      start, stop,
      pauseHidden() { if (audio) audio.pause(); },
      resume() { if (on && audio?.paused) audio.play().catch(() => {}); },
      toggle() { if (window.BeautyAudio) { const st = BeautyAudio.settings; BeautyAudio.set({ src: 'mine', bgm: !(st.src === 'mine' && st.bgm) }); } else on ? stop() : start(); },
      restart() { if (on) { stop(); start(); } },
      setVolume(v) { vol = v ?? vol; if (audio) window.AudioBus.volume(audio, vol); },
      get on() { return on; },
    };
  })();

  // ---------------------------------------------------------------- 设置页
  function settingsHtml() {
    if (!DATA?.current) return `<div class="card"><h3>🌄 外观与音乐</h3>${window.INTERFACE_GLASS?.settingsHtml()||''}<p class="small muted">先在下面设置好行测库路径。</p></div>`;
    const c = DATA.current, esc2 = (s) => String(s ?? "").replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
    const qOpt = (v, t) => `<option value="${v}" ${c.quote === v ? "selected" : ""}>${t}</option>`;
    return `<div class="card"><h3>语录与声音</h3>${window.INTERFACE_GLASS?.settingsHtml()||''}
      <div class="row"><label style="flex:1">语录 <select id="ambQuote">${qOpt("daily", "每日一句")}${qOpt("random", "每次打开随机")}${qOpt("fixed", "固定一句")}${qOpt("off", "不显示")}</select></label>
        <label style="flex:2">固定显示哪一句 <select id="ambFixed">${DATA.quotes.map((q) => `<option ${q === c.fixed ? "selected" : ""}>${esc2(q)}</option>`).join("")}</select></label></div>
      <div class="row" style="align-items:center;gap:12px;margin-top:6px"><label style="flex:1">语录大小 <b id="ambQSizeV">${Math.round((c.quote_size ?? 1) * 100)}%</b>
        <input type="range" id="ambQSize" min="0.5" max="2" step="0.1" value="${c.quote_size ?? 1}"></label></div>
      <p class="small muted">语录在库里的 <b>${esc2(DATA.folders.quotes)}</b>，一行一句（“- ”开头），自己加、改、删，刷新生效。现在共 ${DATA.quotes.length} 句。</p>
      <hr class="soft">
      ${musicHtml(c, esc2)}
      </div>`;
  }

  // 背景音乐与声音（3.2.x：内置场景音乐、我的音乐、音效合在一起）
  function musicHtml(c, esc2) {
    const st = window.BeautyAudio?.settings || { sfx: false, bgm: BGM.on, vs: 0.6, src: "mine" }, has = DATA.music.length > 0;
    const src = st.src === "mine" ? "mine" : "builtin";
    return `<label class="small muted">背景音乐与音效</label>
      <div class="row" style="align-items:center;gap:14px;flex-wrap:wrap"><label style="flex:none"><input type="checkbox" id="baBgm" ${st.bgm ? "checked" : ""} style="width:auto"> 背景音乐</label>
        <label style="flex:2;min-width:200px">来源 <select id="baSrc"><option value="builtin" ${!window.BeautyAudio ? "disabled" : ""} ${src === "builtin" ? "selected" : ""}>内置场景音乐（随地图、洞府、答题自动切换）</option>
          <option value="mine" ${src === "mine" ? "selected" : ""} ${has ? "" : "disabled"}>我的音乐${has ? "" : "（库里还没有）"}</option></select></label>
        <label style="flex:1;min-width:160px">音乐音量 <input type="range" id="ambVol" min="0" max="1" step="0.05" value="${c.volume}"></label></div>
      <div class="row" id="ambMine" style="${src === "mine" ? "" : "display:none"}">${has ? `<label style="flex:2">曲目 <select id="ambTrack">
          ${DATA.music.map((p) => `<option value="${esc2(p)}" ${c.track === p ? "selected" : ""}>${esc2(p.split("/").pop())}（顺序循环时从这首开始）</option>`).join("")}</select></label>
        <label style="flex:1">播放顺序 <select id="ambShuffle"><option value="0" ${c.shuffle ? "" : "selected"}>顺序循环</option><option value="1" ${c.shuffle ? "selected" : ""}>随机播放</option></select></label>` : ""}</div>
      <div class="row" style="align-items:center;gap:14px;flex-wrap:wrap"><label style="flex:none"><input type="checkbox" id="baSfx" ${st.sfx ? "checked" : ""} style="width:auto"> 音效与环境声（点击、答题、翻页、鸟虫流水等）</label>
        <label style="flex:1;min-width:160px">音效音量 <input type="range" id="baSfxVol" min="0" max="1" step="0.05" value="${st.vs}"></label></div>
      <p id="ambMusicStatus" class="small muted" role="status"></p><p class="small muted">第一次点一下页面后才会发声。内置音乐和音效在 <b>web/assets/beauty/audio/</b>，“我的音乐”放进 <b>${esc2(DATA.folders.music)}</b>（mp3 / ogg / m4a / wav），刷新本页后在上面选。右下角喇叭可一键静音。</p>`;
  }

  function bindSettings(onErr) {
    const guard = (p) => p.catch((e) => onErr ? onErr(e) : alert(e.message));
    if (!document.getElementById("ambQuote")) return;
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
    document.getElementById("baBgm").onchange = (e) => BA ? BA.set({ bgm: e.target.checked }) : e.target.checked ? BGM.start() : BGM.stop();
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

// 场景播放器与设置共用同一个音乐库实例（const全局绑定不等于window属性）。
window.AMB = AMB;
