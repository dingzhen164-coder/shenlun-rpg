/* 申论官途 · 前端外壳
   原生 JS，无构建、无外部依赖。页面：今日概览 / AI 对练 / 练习记录已成形，其余页面是带里程碑标注的空状态。 */
"use strict";

/* ---------- 图标（线性 SVG，统一 24 栅格） ---------- */
const P = {
  home: '<rect x="3" y="3" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2"/>',
  spark: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
  news: '<path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z"/><path d="M18 8h1a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
  book: '<path d="M6 3h11a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6z"/><path d="M6 3v18M10 8h5M10 12h5"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2"/>',
  flame: '<path d="M12 3c1 3.2 4.5 5 4.5 9.2A4.5 4.5 0 0 1 12 17a4.5 4.5 0 0 1-4.5-4.8c0-1.8 1-3 2-4 0 1.5.8 2.3 1.5 2.5C10.5 8.5 11 5.5 12 3z"/><path d="M9.5 21h5"/>',
  pen: '<path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19z"/><path d="M14 7l3 3"/>',
  redo: '<path d="M4 9a6 6 0 0 1 6-5h8"/><path d="M15 1l3 3-3 3"/><path d="M20 15a6 6 0 0 1-6 5H6"/><path d="M9 23l-3-3 3-3"/>',
  chart: '<path d="M4 20V4"/><path d="M4 20h16"/><path d="M8 15l3-4 3 2 5-6"/>',
  cal: '<rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M9 14l2 2 4-4"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  play: '<path d="M8 5.5v13l11-6.5z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
  bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
  alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.1"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  file: '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
};
const ico = (n) => `<span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true">${P[n] || ""}</svg></span>`;
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- 导航 ---------- */
const NAV = [
  { group: "开始" },
  { id: "overview", label: "今日概览", icon: "home" },
  { id: "partner", label: "AI 伙伴", icon: "spark", ms: "M4" },
  { group: "学习内容" },
  { id: "articles", label: "每日文章", icon: "news", ms: "M5" },
  { id: "notes", label: "知识积累", icon: "book", ms: "M4" },
  { group: "实战练习" },
  { id: "practice", label: "AI 对练", icon: "target" },
  { id: "questions", label: "题库选题", icon: "search" },
  { id: "hot", label: "高频考点", icon: "flame", ms: "M4" },
  { id: "essay", label: "大作文训练", icon: "pen", ms: "M4" },
  { id: "redo", label: "整改重做", icon: "redo", ms: "M2" },
  { group: "复盘统计" },
  { id: "records", label: "练习记录", icon: "chart" },
  { id: "plan", label: "学习计划", icon: "cal", ms: "M2" },
  { group: "" },
  { id: "settings", label: "设置", icon: "gear", ms: "M1" },
];

let D = null; // dashboard 数据
const $ = (s) => document.querySelector(s);

/* ---------- 空状态插画（内联 SVG，随主题取色） ---------- */
const ART = `<svg viewBox="0 0 160 110" aria-hidden="true"><ellipse cx="80" cy="98" rx="52" ry="7" fill="var(--surface-3)"/>
<rect x="38" y="16" width="84" height="76" rx="9" fill="var(--surface)" stroke="var(--line-strong)" stroke-width="2"/>
<rect x="38" y="16" width="84" height="16" rx="9" fill="var(--primary-soft)"/>
<path d="M52 48h56M52 60h40M52 72h48" stroke="var(--line-strong)" stroke-width="3" stroke-linecap="round"/>
<g transform="rotate(-8 112 32)"><rect x="100" y="20" width="26" height="26" rx="6" fill="var(--cinnabar)"/><text x="113" y="40" font-size="17" font-family="serif" font-weight="700" text-anchor="middle" fill="#fff4e4">阅</text></g></svg>`;
const emptyBox = (title, text) => `<div class="card empty rise">${ART}<b>${esc(title)}</b><span>${esc(text)}</span></div>`;

/* ---------- 页面 ---------- */
const PAGES = {
  overview: {
    title: () => "今日概览",
    sub: () => D ? `${D.date.replace(/^(\d+)-(\d+)-(\d+)$/, (_, y, m, d) => `${y}年${+m}月${+d}日`)} 星期${D.weekday}` : "",
    actions: () => `<button class="btn primary" data-go="practice">${ico("check")}<span class="lbl">开始练习</span></button>`,
    render() {
      const t = D.theme.terms, s = D.stats, r = D.rank, q = D.daily.question;
      const pct = r.score == null || r.next_at == null ? 0 : Math.max(4, Math.min(100, Math.round(((r.score - (r.next_at - 5)) / 5) * 100)));
      const week = ["一", "二", "三", "四", "五", "六", "日"].map((n, i) => {
        const today = i === (new Date().getDay() + 6) % 7;
        return `<div class="day${today ? " today" : ""}"><i></i>${n}</div>`;
      }).join("");
      return `
      <div class="stack">
        <section class="card hero rise">
          <div class="rank-badge"><div><b>${esc(r.name)}</b><small>${esc(t.rank)}</small></div></div>
          <div>
            <div class="eyebrow">${esc(t.score)}</div>
            <h2>${r.score == null ? "完成首次批改，评定你的职级" : r.next ? `距「${esc(r.next)}」还差 ${(r.next_at - r.score).toFixed(1)} 分` : "已达最高职级"}</h2>
            <div class="meter" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>
            <div class="meter-cap"><span>${esc(r.name)}</span><span>${r.next ? esc(r.next) + " · " + r.next_at + " 分" : ""}</span></div>
          </div>
          <div class="hero-score"><div class="eyebrow">预估分</div><div class="num${r.score == null ? " none" : ""}">${r.score == null ? "——" : r.score}</div></div>
        </section>

        <section class="grid c4">
          ${stat("t-red", "clock", `今日待${t.wrong}`, s.wrong_due, "", s.wrong_due ? "到期题等你回头看" : `今日无到期${t.wrong}题`)}
          ${stat("t-green", "news", "今日新文章", 0, "", "文章抓取将在 M5 开放")}
          ${stat("t-gold", "flame", t.streak, s.streak, "天", s.streak ? "保持住，别断档" : "今天从一题开始")}
          ${stat("t-violet", "chart", "累计练习", s.total, "", s.total ? `其中 ${s.rated} 道已批改` : "道练习记录")}
        </section>

        <section class="card daily rise">
          <div class="card-head">
            ${ico("spark")}<h3>${esc(t.daily)}</h3><span class="sub">按高频考点智能推荐 · 每天一道</span>
            <span class="right pill ${D.daily.done ? "soft" : "gold"}">${D.daily.done ? "今日已打卡" : "今日待打卡"}</span>
          </div>
          <div class="daily-body">
            <div>
              <div class="meta-row"><span class="pill solid">${esc(q.type)}</span>${q.real ? "" : `<span class="pill soft">${esc(q.topic)}</span>`}<span>${esc(q.source)} · ${q.score} 分 · ${q.words} 字</span></div>
              <p class="stem">${esc(q.stem)}</p>
            </div>
            <button class="btn primary" data-go="${q.real ? "answer?qid=" + encodeURIComponent(q.id) : "questions"}">${ico("play")}<span>${esc(t.start)}</span></button>
          </div>
        </section>

        <div class="grid c2">
          <section class="card pishi rise">
            <div class="avatar" aria-hidden="true">${esc(D.theme.tutor.name.slice(0, 1))}</div>
            <div>
              <div class="pishi-name">${esc(D.theme.tutor.name)}<small>${esc(D.theme.tutor.title)}</small></div>
              <div class="quote">${D.ai ? "小同志，今天先把这道题吃透，材料里的原词，一个都别漏。" : "还没有接入 AI。在「设置」里填入 DeepSeek 的 key，批示才会结合你的真实进度来写。"}</div>
            </div>
          </section>
          <section class="card card-pad rise">
            <div class="eyebrow" style="margin-bottom:12px">本周出勤</div>
            <div class="week">${week}</div>
          </section>
        </div>
      </div>`;
    },
  },

  practice: {
    title: () => "AI 对练",
    sub: () => "AI 批阅 · 对练 · 辅导一体",
    actions: () => `<button class="btn primary">${ico("play")}<span class="lbl">开始练习</span></button>`,
    render() {
      const entries = [
        ["spark", "t-green", "AI 出题", "自定义主题、难度与题型，让 AI 现场生成一套专属于你的新题", "难度可选 · 题型自定"],
        ["target", "t-gold", "智能选题", "根据薄弱题型，从真题库自动匹配最该练的那一道题", "弱项优先 · 自动匹配"],
        ["search", "", "手动选题", "按省份、年份翻历年真题，自己挑一道想练的题", "国考行政执法 · 贵州联考"],
        ["bulb", "t-violet", "要点提取", "只练圈采分点：读材料 → 列要点 → AI 只评命中率", "随机抽题 · 专项突破"],
      ].map(([i, tone, h, p, f]) => `
        <article class="card hover entry rise" ${h === "手动选题" ? 'data-go="questions"' : ""}><div class="chip-ico ${tone}" style="width:46px;height:46px">${ico(i)}</div><h3>${h}</h3><p>${p}</p><div class="foot">${f}</div></article>`).join("");
      const seg = (arr, on) => arr.map((x) => `<button class="pill${x === on ? " on" : ""}">${x}</button>`).join("");
      return `
      <div class="stack">
        <section class="grid c4">${entries}</section>
        <section class="grid c3">
          <div class="card card-pad rise">
            <div class="eyebrow" style="margin-bottom:12px">AI 出题参数</div>
            <div class="stack" style="gap:14px">
              <div><div class="sub" style="color:var(--ink-3);font-size:13px;margin-bottom:6px">难度</div><div class="filters">${seg(["入门", "进阶", "实战"], "进阶")}</div></div>
              <div><div style="color:var(--ink-3);font-size:13px;margin-bottom:6px">题型</div><div class="filters">${seg(["随机", "归纳概括", "综合分析", "公文写作", "提出对策", "大作文"], "随机")}</div></div>
            </div>
          </div>
          <div class="card card-pad rise"><div class="eyebrow" style="margin-bottom:12px">弱项分析</div><div class="empty" style="padding:var(--s-6) 0">多练几题，AI 帮你看哪里最薄弱</div></div>
          <div class="card card-pad rise"><div class="eyebrow" style="margin-bottom:12px">练习概况</div><div class="empty" style="padding:var(--s-6) 0">还没有练习记录，加油吧</div></div>
        </section>
      </div>`;
    },
  },


  questions: {
    title: () => "题库选题",
    sub: () => "国考行政执法 · 贵州联考 · 已导入的题目",
    actions: () => "",
    render() { return `<div id="qlist" class="stack"><div class="skeleton" style="height:96px"></div><div class="skeleton" style="height:96px"></div></div>`; },
    async mount() {
      const box = $("#qlist");
      try {
        const qs = (await (await fetch("/api/shenlun/questions")).json()).questions || [];
        box.innerHTML = qs.length ? qs.map((q) => `
          <article class="card hover qrow rise" data-go="answer?qid=${encodeURIComponent(q.qid)}">
            <div><div class="meta-row"><span class="pill solid">${esc(q.type || "未分类")}</span><span class="pill ${q.status === "已定稿" ? "soft" : "gold"}">${esc(q.status)}</span><span>${esc(q.qid)} · ${q.total} 分${q.words ? " · " + q.words + " 字" : ""} · ${q.points} 个采分点</span></div>
            <p class="stem">${esc((q.stem || "（未录入题干）").split("\n")[0])}</p></div>
            <span class="btn sm">${ico("pen")}<span>去作答</span></span>
          </article>`).join("") : emptyBox("题库是空的", "用 python -m subjects.shenlun.analysis 从解析文档起草采分点，放进 训练/采分点/");
      } catch (e) { box.innerHTML = emptyBox("读取失败", "请确认本地服务仍在运行"); }
    },
  },

  answer: {
    title: () => "作答与批改",
    sub: () => "写完点“交卷批改”，AI 逐个采分点判断，分数由程序计算",
    actions: () => "",
    render() {
      return `<div class="answer-grid">
        <div class="stack" id="qside"><div class="skeleton" style="height:180px"></div></div>
        <div class="stack" id="rside">${emptyBox("等你交卷", "批改结果会出现在这里")}</div></div>`;
    },
    async mount(params) {
      const qid = params.get("qid");
      let q;
      try {
        const r = await fetch("/api/shenlun/question?qid=" + encodeURIComponent(qid));
        q = await r.json();
        if (!r.ok) throw new Error(q.error);
      } catch (e) { $("#qside").innerHTML = emptyBox("找不到这道题", String(e.message || e)); return; }
      const draft = q.status !== "已定稿";
      $("#qside").innerHTML = `
        <section class="card rise">
          <div class="card-head"><h3>${esc(q.qid)}</h3><span class="sub">${esc(q.type || "未分类")} · ${q.total} 分${q.words ? " · 不超过 " + q.words + " 字" : ""}</span>
            <span class="right pill ${draft ? "gold" : "soft"}">${esc(q.status)}</span></div>
          <div class="card-pad"><p class="stem">${esc(q.stem || "（未录入题干）").replace(/\n/g, "<br>")}</p></div>
        </section>
        ${draft ? `<div class="notice rise"><span>采分点还是草稿：可以试批，但不计入预估分。</span><button class="btn sm" id="finalizeBtn">审定并定稿</button></div>` : ""}
        <section class="card card-pad rise">
          <textarea id="ans" class="ans" placeholder="在这里作答……" spellcheck="false"></textarea>
          <div class="ans-foot"><span class="count" id="cnt">0 字</span><button class="btn primary" id="submitBtn">${ico("check")}<span>交卷批改</span></button></div>
        </section>`;
      const ans = $("#ans"), cnt = $("#cnt");
      ans.addEventListener("input", () => {
        const n = ans.value.replace(/\s/g, "").length;
        cnt.textContent = n + " 字" + (q.words ? " / " + q.words : "");
        cnt.classList.toggle("over", !!q.words && n > q.words * 1.1);
      });
      const fin = $("#finalizeBtn");
      if (fin) fin.onclick = async () => {
        const r = await fetch("/api/shenlun/finalize", { method: "POST", body: JSON.stringify({ qid }) });
        const j = await r.json();
        if (!r.ok) return toast(j.error); toast("已定稿"); route();
      };
      $("#submitBtn").onclick = async (ev) => {
        const btn = ev.currentTarget;
        if (!ans.value.trim()) return toast("先写点什么再交卷");
        btn.disabled = true; btn.querySelector("span:last-child").textContent = "阅卷中…";
        $("#rside").innerHTML = `<div class="skeleton" style="height:140px"></div><div class="skeleton" style="height:260px"></div>`;
        try {
          const r = await fetch("/api/shenlun/grade", { method: "POST", body: JSON.stringify({ qid, answer: ans.value }) });
          const j = await r.json();
          if (!r.ok) throw new Error(j.error);
          $("#rside").innerHTML = resultView(j, q);
        } catch (e) {
          $("#rside").innerHTML = emptyBox("批改没成功", String(e.message || e));
        }
        btn.disabled = false; btn.querySelector("span:last-child").textContent = "交卷批改";
      };
    },
  },

  records: {
    title: () => "练习记录",
    sub: () => "回顾练习、整改与统计",
    actions: () => `<div class="seg"><button class="on">练习记录</button><button>索引</button><button>整改本</button></div>`,
    render() {
      const s = D.stats;
      return `
      <div class="stack">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
          <div class="filters">${["全部", "归纳概括", "综合分析", "公文写作", "提出对策", "大作文"].map((x, i) => `<button class="pill${i ? "" : " on"}">${x}</button>`).join("")}</div>
          <div class="seg"><button>近 7 天</button><button>近 30 天</button><button class="on">全部</button></div>
        </div>
        <section class="grid c4">
          ${stat("t-green", "file", "总练习", s.total, "", `${s.rated} 次有评分`)}
          ${stat("t-gold", "chart", "平均得分率", "—", "", "暂无数据")}
          ${stat("t-green", "check", "最强题型", "—", "", "暂无数据")}
          ${stat("t-red", "alert", "薄弱题型", "—", "", "暂无数据")}
        </section>
        ${emptyBox("暂无练习记录", "完成 AI 对练并批改后，记录会自动保存到这里")}
      </div>`;
    },
  },
};

function stat(tone, icon, label, num, unit, cap) {
  return `<article class="card hover stat ${tone} rise"><div class="stat-top"><span>${esc(label)}</span><span class="chip-ico">${ico(icon)}</span></div>
    <div class="stat-num">${esc(num)}${unit ? `<small>${esc(unit)}</small>` : ""}</div><div class="stat-cap">${esc(cap)}</div></article>`;
}


function resultView(j, q) {
  const pct = Math.round(j.rate * 100);
  const hitLabel = { full: ["落实", "ok"], half: ["部分落实", "half"], none: ["未落实", "none"] };
  const rows = j.points.map((p) => {
    const [lab, cls] = hitLabel[p.hit];
    return `<li class="pt ${cls}"><div class="pt-top"><b>${p.bonus ? "加分 · " : ""}${esc(p.name)}</b><span class="badge ${cls}">${lab}</span><span class="pt-sc">${p.earned} / ${p.score}</span></div>
      ${p.reason ? `<div class="pt-reason">${esc(p.reason)}</div>` : ""}
      ${p.evidence ? `<blockquote>${esc(p.evidence)}</blockquote>` : ""}${p.flag ? `<div class="pt-flag">${esc(p.flag)}</div>` : ""}</li>`;
  }).join("");
  const ded = j.deductions.map((d) => `<li class="pt none"><div class="pt-top"><b>${esc(d.reason)}</b><span class="pt-sc">-${d.points}</span></div></li>`).join("");
  const lost = j.lost.length ? `<div class="filters" style="margin-top:12px">${j.lost.map((x) => `<span class="pill red" title="${esc(x.note)}">${esc(x.code)} ${esc(x.name)}</span>`).join("")}</div>` : "";
  return `
    <section class="card score-card rise ${j.draft ? "trial" : ""}">
      <div class="ring" style="--p:${pct}"><div><b>${j.total}</b><small>/ ${j.full}</small></div></div>
      <div><div class="eyebrow">${j.draft ? "试批 · 不计入预估分" : "本次得分"}</div>
        <div class="score-line">得分率 ${pct}% · ${j.words} 字</div>
        ${lost}</div>
    </section>
    ${j.summary ? `<section class="card pishi rise"><div class="avatar" aria-hidden="true">${esc(D.theme.tutor.name.slice(0, 1))}</div><div><div class="pishi-name">${esc(D.theme.tutor.name)}<small>批示</small></div><div class="quote">${esc(j.summary)}</div></div></section>` : ""}
    <section class="card rise"><div class="card-head"><h3>采分点</h3><span class="sub">${j.points.filter((p) => !p.bonus).length} 个</span></div><ul class="pts">${rows}${ded}</ul></section>
    <div class="sub" style="color:var(--ink-3);font-size:12px">复盘已保存到 ${esc(j.review_file)}</div>`;
}

/* ---------- 路由 ---------- */
function placeholder(item) {
  return {
    title: () => item.label,
    sub: () => "",
    actions: () => "",
    render: () => emptyBox(`${item.label} · 筹备中`, `计划在 ${item.ms} 里程碑开放，详见 DESIGN.md`),
  };
}

function route() {
  const [id, qs] = (location.hash || "#overview").slice(1).split("?");
  const params = new URLSearchParams(qs || "");
  const item = NAV.find((n) => n.id === id) || (id === "answer" ? { id: "answer", label: "作答" } : NAV[1]);
  const page = PAGES[item.id] || placeholder(item);
  document.title = `${page.title()} · ${D ? D.theme.app : "申论官途"}`;
  $("#pageTitle").textContent = page.title();
  $("#pageSub").textContent = page.sub();
  $("#pageActions").innerHTML = page.actions();
  $("#content").innerHTML = D ? page.render(params) : `<div class="grid c4"><div class="skeleton" style="height:130px"></div><div class="skeleton" style="height:130px"></div><div class="skeleton" style="height:130px"></div><div class="skeleton" style="height:130px"></div></div>`;
  document.querySelectorAll(".nav-item[data-id]").forEach((el) => el.classList.toggle("active", el.dataset.id === (item.id === "answer" ? "questions" : item.id)));
  if (D && page.mount) page.mount(params);
  $("#app").classList.remove("nav-open");
  window.scrollTo(0, 0);
}

function buildNav() {
  $("#nav").innerHTML = NAV.map((n) => n.group !== undefined
    ? (n.group ? `<div class="nav-group">${n.group}</div>` : `<div style="flex:1"></div>`)
    : `<a class="nav-item" href="#${n.id}" data-id="${n.id}">${ico(n.icon)}<span>${n.label}</span>${n.ms ? `<span class="tag">${n.ms}</span>` : ""}</a>`).join("");
  document.querySelectorAll("[data-ico]").forEach((el) => { el.innerHTML = `<svg viewBox="0 0 24 24">${P[el.dataset.ico]}</svg>`; });
}

function toast(msg) {
  const el = document.createElement("div");
  el.className = "toast"; el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

/* ---------- 主题（亮 / 暗） ---------- */
function applyTheme(t) {
  if (t) document.documentElement.setAttribute("data-theme", t); else document.documentElement.removeAttribute("data-theme");
  try { t ? localStorage.setItem("theme", t) : localStorage.removeItem("theme"); } catch (e) { /* 隐私模式 */ }
}
function initTheme() {
  let t = null;
  try { t = localStorage.getItem("theme"); } catch (e) { /* 忽略 */ }
  const q = new URLSearchParams(location.search).get("theme");
  if (q === "dark" || q === "light") t = q;
  if (!t && window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches) t = "dark";
  applyTheme(t === "dark" ? "dark" : null);
}

document.addEventListener("click", (e) => {
  const go = e.target.closest("[data-go]");
  if (go) { location.hash = go.dataset.go; return; }
  if (e.target.closest("#menuBtn")) $("#app").classList.add("nav-open");
  if (e.target.closest("#scrim")) $("#app").classList.remove("nav-open");
  if (e.target.closest("#themeToggle")) applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? null : "dark");
  const pill = e.target.closest(".filters .pill");
  if (pill) { pill.parentElement.querySelectorAll(".pill").forEach((p) => p.classList.remove("on")); pill.classList.add("on"); }
  const sg = e.target.closest(".seg button");
  if (sg) { sg.parentElement.querySelectorAll("button").forEach((p) => p.classList.remove("on")); sg.classList.add("on"); }
});
window.addEventListener("hashchange", route);

(async function init() {
  initTheme();
  buildNav();
  route();
  try {
    const r = await fetch("/api/dashboard");
    D = await r.json();
    $("#brandName").textContent = D.theme.app;
    $("#brandVer").textContent = "v" + D.version;
    $("#footNote").textContent = D.ai ? "AI 批示已就绪" : "AI 未连接 · 在设置里填 key";
  } catch (e) {
    toast("连不上本地服务，请确认 server.py 仍在运行");
    return;
  }
  route();
})();
