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

  function paint() {
    if (!root) return;
    root.innerHTML = `<div class="sg-root">${sceneHtml()}${BOARD ? roomHtml() : ""}</div>`;
    bind(); fit();
  }

  async function openBoard(name, key) {
    BOARD = await api("/api/siguo/board", { name });
    const keys = BOARD.questions.map((q) => q.key);
    CUR = keys.includes(key) ? key : keys.includes(pos()[name]) ? pos()[name] : keys[0] || "";
    RESULT = null; touch(); savePos({ board: name, [name]: CUR }); paint();
  }

  function bind() {
    root.querySelectorAll("[data-sgboard]").forEach((b) => (b.onclick = () => openBoard(b.dataset.sgboard).catch(showError)));
    root.querySelector("[data-sgback]")?.addEventListener("click", () => close());
    root.querySelectorAll("[data-sgq]").forEach((b) => (b.onclick = () => {
      CUR = b.dataset.sgq; RESULT = null; touch(); savePos({ [BOARD.name]: CUR }); paint();
      root.querySelector(".sg-main")?.scrollTo?.({ top: 0 });
    }));
    root.querySelector("[data-sgredo]")?.addEventListener("click", () => { RESULT = null; touch(); paint(); });
    root.querySelectorAll("[data-sgpick]").forEach((b) => (b.onclick = async () => {
      touch();
      try {
        const r = await api("/api/siguo/answer", { name: BOARD.name, key: CUR, choice: b.dataset.sgpick });
        RESULT = Object.assign({ key: CUR }, r);
        const q = BOARD.questions.find((x) => x.key === CUR); if (q) q.record = r.record;
        if (typeof handleEvents === "function") handleEvents(r.events || []);
        paint();
      } catch (e) { showError(e); }
    }));
  }

  async function render(v, prepare) {
    DATA = await api("/api/siguo", {});
    if (BOARD && !DATA.boards.some((b) => b.name === BOARD.name)) BOARD = null;
    if (prepare && !prepare()) return;
    root = v;
    v.innerHTML = `<div class="sg-root">${sceneHtml()}</div>`;
    bind(); fit();
    if (ro) ro.disconnect();
    if (window.ResizeObserver) { ro = new ResizeObserver(fit); ro.observe(v.querySelector(".sg-stage") || v); } else window.addEventListener("resize", fit);
    if (BOARD) openBoard(BOARD.name, CUR).catch(() => {});
  }

  function close() { BOARD = null; RESULT = null; CUR = ""; savePos({ board: "" }); if (root && DATA) paint(); }
  window.SIGUO = {
    render, close,
    isOpen: () => !!BOARD,
    active: () => (BOARD && Date.now() - lastAct < 120000 && document.visibilityState !== "hidden" ? BOARD.board : ""),
    board: () => (BOARD ? BOARD.board : ""),
  };
})();
