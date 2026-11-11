/* 行测 · 思过崖（后端 rpg/siguo.py）：悬崖边七块石碑，一碑一个板块；点碑进入该板块的错题文档。
   重做：先只显示题干和选项 → 选一个 → 判对错并展开文档里的其余小节（区别、解析、错因、教训……）。
   场景图按原比例完整显示（contain + 模糊底衬），石碑热区按图片坐标定位。类名统一 sg- 前缀。
   对外：SIGUO.render(v, prepare) / isOpen() / close() / active()（2 分钟内在这里动过 → 板块名，供学习心跳）/ board()。 */
(function () {
  const IMG = { w: 1672, h: 941 };
  // 七块石碑在图上的位置（像素，左上 x,y → 右下 x,y），从左到右对应 BOARDS 顺序
  const STELES = [[402, 360, 497, 558], [528, 368, 623, 550], [655, 345, 750, 545], [781, 338, 880, 545],
    [913, 352, 1008, 550], [1043, 362, 1138, 552], [1169, 362, 1255, 560]];
  const POS_KEY = "sg-pos-v1";
  let DATA = null, BOARD = null, CUR = "", RESULT = null, lastAct = 0, root = null, ro = null;
  let generation = 0, boardRequest = 0, answerRequest = 0;
  const current = () => typeof VIEW === 'undefined' || VIEW === 'tianji';
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const md = (t) => (window.MDLITE ? MDLITE.render(t || "") : `<p>${esc(t)}</p>`);
  const pos = () => { try { return JSON.parse(localStorage.getItem(POS_KEY) || "{}"); } catch (_) { return {}; } };
  const savePos = (p) => { try { localStorage.setItem(POS_KEY, JSON.stringify(Object.assign(pos(), p))); } catch (_) {} };
  const touch = () => { lastAct = Date.now(); };
  const pct = (v, total) => (100 * v / total).toFixed(3) + "%";

  function hero() {
    return window.BeautyArt?.heroFor?.("tianji") || "assets/beauty/scenes/xingce/hd/siguo/siguo-day.webp";
  }

  function sceneHtml() {
    const img = hero();
    const steles = DATA.boards.map((b, i) => {
      const [x0, y0, x1, y1] = STELES[i];
      const label = b.total ? `${b.total} 题${b.bad ? ` · 再错 ${b.bad}` : ""}${b.done ? ` · 做过 ${b.done}` : ""}` : (b.exists ? "还没有题" : "未建文档");
      return `<button type="button" class="sg-stele ${b.total ? "" : "empty"}" data-sgboard="${esc(b.name)}"
        style="left:${pct(x0, IMG.w)};top:${pct(y0, IMG.h)};width:${pct(x1 - x0, IMG.w)};height:${pct(y1 - y0, IMG.h)}"
        aria-label="${esc(b.name)}，${esc(label)}"><span class="sg-carve">${esc(b.name)}</span><span class="sg-count">${esc(label)}</span></button>`;
    }).join("");
    return `<div class="sg-stage"><div class="sg-back" style="--sg-img:url('${esc(img)}')" aria-hidden="true"></div>
      <div class="sg-frame"><img src="${esc(img)}" alt="" class="sg-art" draggable="false">${steles}</div>
      <p class="sg-hint">面壁思过：点一块石碑，重做那个板块记下的错题。内容来自 ${esc(DATA.folder)}（照 ${esc(DATA.template)} 的格式增改）。</p></div>`;
  }

  function fit() {
    const st = root?.querySelector(".sg-stage"), fr = root?.querySelector(".sg-frame");
    if (!st || !fr) return;
    const W = st.clientWidth, H = st.clientHeight, k = Math.min(W / IMG.w, H / IMG.h);
    fr.style.width = Math.floor(IMG.w * k) + "px"; fr.style.height = Math.floor(IMG.h * k) + "px";
    fr.style.setProperty("--sg-fs", Math.max(12, Math.round(IMG.w * k * 0.0155)) + "px");   // 碑上刻字随画面大小缩放
  }

  function listHtml() {
    return BOARD.questions.map((q) => {
      const r = q.record, st = !r ? "new" : r.last === "ok" ? "ok" : "bad";
      return `<button type="button" class="sg-q ${q.key === CUR ? "on" : ""}" data-sgq="${esc(q.key)}" aria-current="${q.key === CUR}">
        <i class="sg-dot ${st}" aria-hidden="true"></i><span>${esc(q.title)}</span><small>${st === "new" ? "未重做" : st === "ok" ? "上次对" : "上次错"}</small></button>`;
    }).join("");
  }

  function questionHtml() {
    const q = BOARD.questions.find((x) => x.key === CUR);
    if (!q) return `<div class="sg-empty">左边选一道题。</div>`;
    const R = RESULT && RESULT.key === q.key ? RESULT : null;
    const opts = Object.entries(q.options).map(([k, v]) => {
      const cls = !R ? "" : k === R.answer ? "right" : k === R.choice ? "wrong" : "dim";
      return `<button type="button" class="sg-opt ${cls}" data-sgpick="${k}" ${R ? "disabled" : ""}><b>${k}</b><span>${esc(v)}</span></button>`;
    }).join("");
    const verdict = !R ? "" : `<div class="sg-verdict ${R.ok === null ? "" : R.ok ? "ok" : "bad"}" role="status">${
      R.ok === null ? "文档里没写正确答案" : R.ok ? "✓ 这次做对了" : `✗ 又错了：正确答案 ${esc(R.answer)}`}${R.mine ? `<span>当时选 ${esc(R.mine)}</span>` : ""}</div>`;
    const secs = R ? R.sections.map((s) => `<section class="sg-sec"><h4>${esc(s.title)}</h4><div class="sg-md">${md(s.md)}</div></section>`).join("") : "";
    const idx = BOARD.questions.findIndex((x) => x.key === q.key), next = BOARD.questions[idx + 1];
    return `<article class="sg-card"><strong class="sg-qtitle">${esc(q.title)}</strong><div class="sg-md sg-stem">${md(q.stem)}</div>
      <div class="sg-opts" role="group" aria-label="选项">${opts}</div>${verdict}${secs}
      <div class="sg-acts">${R ? `<button type="button" class="ghost small" data-sgredo>再做一次</button>` : ""}${next ? `<button type="button" class="primary small" data-sgq="${esc(next.key)}">下一题 →</button>` : ""}</div></article>`;
  }

  function roomHtml() {
    const b = BOARD;
    const head = `<header class="sg-head"><button type="button" class="ghost small" data-sgback>← 回思过崖</button><strong class="sg-title">${esc(b.name)}</strong>
      <span class="small sg-file">${esc(b.file)}</span></header>`;
    if (!b.exists || !b.questions.length) {
      return `<div class="sg-room sg-paper">${head}<div class="sg-empty"><p>${b.exists ? "这个文档里还没读到题。" : "还没有这个板块的文档。"}</p>
        <p>在本地新建或补充 <b>${esc(b.file)}</b>，照 <b>${esc(b.template || "训练/思过崖/_模板.md")}</b> 的格式：每道题 <code>## 编号 · 标题</code>，下面 <code>### 原题</code>（题干 + “- A. ……”）、<code>### 答案</code>（正确答案：C；我的选择：B），其余小节随便加。</p>
        ${b.problems.length ? `<div class="sg-warn">${b.problems.map((p) => `<div>${esc(p)}</div>`).join("")}</div>` : ""}</div></div>`;
    }
    const warn = b.problems.length ? `<div class="sg-warn" role="alert"><b>文档里有几处没读懂：</b>${b.problems.map((p) => `<div>${esc(p)}</div>`).join("")}</div>` : "";
    return `<div class="sg-room sg-paper">${head}${warn}<div class="sg-body"><nav class="sg-list" aria-label="题目">${listHtml()}</nav>
      <div class="sg-main">${questionHtml()}</div></div></div>`;
  }

  // 整页重画会把左侧目录的滚动位置清零（点下面的题就跳回第一页）：画之前记下，画完放回。
  // opts.fresh：刚进板块，不沿用旧位置；opts.reveal：当前题不在可见范围才挪一点（"center"=放到中间）；opts.keepMain：正文也保持原位（作答、再做一次）。
  function paint(opts = {}) {
    if (!root || !current()) return;
    const list = root.querySelector(".sg-list"), main = root.querySelector(".sg-main");
    const keep = list && !opts.fresh ? [list.scrollTop, list.scrollLeft] : null, mainTop = main ? main.scrollTop : 0;
    // 只换 .sg-root：#view 里还挂着学习顶栏（#studyHud），整块 innerHTML 会把它冲掉、再被补回来，高度一变目录位置就对不上
    const html = `<div class="sg-root">${sceneHtml()}${BOARD ? roomHtml() : ""}</div>`, host = root.querySelector(":scope > .sg-root");
    if (host) host.outerHTML = html; else root.innerHTML = html;
    bind(); fit();
    const nl = root.querySelector(".sg-list"), nm = root.querySelector(".sg-main");
    if (nl && keep) { nl.scrollTop = keep[0]; nl.scrollLeft = keep[1]; }
    if (nm && opts.keepMain) nm.scrollTop = mainTop;
    if (nl && opts.reveal) reveal(nl, opts.reveal === "center");
    window.READING_TOOLS?.hud?.(!!(BOARD && BOARD.questions.length));   // 题目字号按钮只在重做题目时出现
  }

  // 只滚目录自己（scrollIntoView 会连带滚外层页面）
  function reveal(list, center) {
    const on = list.querySelector(".sg-q.on"); if (!on) return;
    const lr = list.getBoundingClientRect(), r = on.getBoundingClientRect(), pad = 8;
    const row = getComputedStyle(list).flexDirection === "row";
    const [a0, a1, b0, b1] = row ? [lr.left, lr.right, r.left, r.right] : [lr.top, lr.bottom, r.top, r.bottom];
    let d = 0;
    if (center) d = (b0 + b1) / 2 - (a0 + a1) / 2;
    else if (b0 < a0) d = b0 - a0 - pad;
    else if (b1 > a1) d = b1 - a1 + pad;
    if (row) list.scrollLeft += d; else list.scrollTop += d;
  }

  async function openBoard(name, key) {
    const epoch = generation, request = ++boardRequest;
    const result = await api("/api/siguo/board", { name });
    if (epoch !== generation || request !== boardRequest || !current()) return;
    ++answerRequest;
    BOARD = result;
    const keys = BOARD.questions.map((q) => q.key);
    CUR = keys.includes(key) ? key : keys.includes(pos()[name]) ? pos()[name] : keys[0] || "";
    RESULT = null; touch(); savePos({ board: name, [name]: CUR }); paint({ fresh: true, reveal: "center" });
  }

  function bind() {
    root.querySelectorAll("[data-sgboard]").forEach((b) => (b.onclick = () => openBoard(b.dataset.sgboard).catch(showError)));
    root.querySelector("[data-sgback]")?.addEventListener("click", () => close());
    root.querySelectorAll("[data-sgq]").forEach((b) => (b.onclick = () => {
      ++answerRequest; CUR = b.dataset.sgq; RESULT = null; touch(); savePos({ [BOARD.name]: CUR }); paint({ reveal: true });
      root.querySelector(".sg-main")?.scrollTo?.({ top: 0 });
    }));
    root.querySelector("[data-sgredo]")?.addEventListener("click", () => { ++answerRequest; RESULT = null; touch(); paint({ keepMain: true }); });
    root.querySelectorAll("[data-sgpick]").forEach((b) => (b.onclick = async () => {
      touch();
      try {
        const epoch = generation, request = ++answerRequest, board = BOARD, key = CUR;
        const r = await api("/api/siguo/answer", { name: board.name, key, choice: b.dataset.sgpick });
        if (typeof handleEvents === "function") handleEvents(r.events || []);
        if (epoch !== generation || request !== answerRequest || BOARD !== board || CUR !== key || !current()) return;
        RESULT = Object.assign({ key }, r);
        const q = board.questions.find((x) => x.key === key); if (q) q.record = r.record;
        paint({ keepMain: true });
      } catch (e) { showError(e); }
    }));
  }

  async function render(v, prepare) {
    const epoch = ++generation;
    ++boardRequest; ++answerRequest;
    const data = await api("/api/siguo", {});
    if (epoch !== generation || !current() || (prepare && !prepare())) return;
    DATA = data;
    if (BOARD && !DATA.boards.some((b) => b.name === BOARD.name)) BOARD = null;
    root = v;
    v.innerHTML = `<div class="sg-root">${sceneHtml()}</div>`;
    bind(); fit();
    if (ro) ro.disconnect();
    if (window.ResizeObserver) { ro = new ResizeObserver(fit); ro.observe(v.querySelector(".sg-stage") || v); } else window.addEventListener("resize", fit);
    if (BOARD) openBoard(BOARD.name, CUR).catch(() => {});
  }

  function close() { ++generation; ++boardRequest; ++answerRequest; BOARD = null; RESULT = null; CUR = ""; savePos({ board: "" }); if (root && DATA) paint(); }
  window.SIGUO = {
    render, close,
    isOpen: () => !!BOARD,
    active: () => (current() && BOARD && Date.now() - lastAct < 120000 && document.visibilityState !== "hidden" ? BOARD.board : ""),
    board: () => (BOARD ? BOARD.board : ""),
  };
})();
