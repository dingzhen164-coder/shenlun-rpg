/*
  申论官途 / 申论官途 前端（原生 JS，无需编译）。改完刷新浏览器即可。

  界面上的说法全部来自后端 /api/dashboard 的 theme.terms（见 rpg/themes.py），用 W("键") 取；
  所以切换风格（设置页）只需要后端改存档里的 theme，前端自动换词、换配色（body 的 class）。

  结构：
    api()            调后端接口（接口说明见 rpg/api.py 顶部）
    views.*          各页面：home 办公室 / train 办理 / skeleton 档案室 / wrong 整改录 / pill 补课室 / log 政绩录 / settings 设置
    handleEvents()   处理后端事件：+政绩提示、职级突破弹窗、导师台词
    heartbeat        每 60 秒上报一次办理时间（页面可见且 2 分钟内有操作才算）
*/
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\n/g, "<br>");
const pct = (x) => Math.round((x || 0) * 100);

let DASH = null;
window.DASH_REF = () => DASH;   // settle.js 用
let SESSION_SNAP = null;         // 开始一项功课时的进度快照，做完后收功结算对比
let VIEW = "home";
const T = { session: null, title: "", msgs: [], input: { mode: "none" }, busy: false, finished: false, battle: null };
const W = (k) => DASH?.theme?.terms?.[k] ?? k;   // 当前风格的说法
const NAV = (k) => W("nav." + k).replace(/^\S+\s/, "");  // 去掉图标的页面名

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({ error: "服务器没有返回数据（程序是不是关掉了？）" }));
  if (!r.ok || data.error) throw new Error(data.error || r.statusText);
  return data;
}

// ------------------------------------------------------------ 提示与事件
function toast(html, cls = "", ms = 4200) {
  const el = document.createElement("div");
  el.className = "toast " + cls;
  el.innerHTML = html;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
}
function tutorFace() {
  const u = DASH?.persona?.tutor_avatar;
  return u ? `<div class="face"><img src="${esc(u)}" alt=""></div>` : `<div class="face">${esc(DASH?.theme?.face || "🏛")}</div>`;
}
function npcToast(msg) {
  if (window.FOCUS && FOCUS.isOn()) return;          // ◎ 专注时导师不打扰
  if (!msg) return;
  toast(`<div class="npc">${tutorFace()}<div><div class="who">${esc(DASH?.persona?.tutor || "导师")}</div>${md(msg)}</div></div>`, "", 9000);
}
function showError(e) { toast("⚠ " + esc(e.message || e), "err", 6000); }

function handleEvents(events, { inChat = false } = {}) {
  for (const e of events || []) {
    if (e.kind === "xp") toast(`+${e.v} ${esc(W("xp"))} <span class="small muted">${esc(e.msg || "")}</span>`, "xp");
    else if (e.kind === "realm") realmUp(e);
    else if (e.kind === "npc" && e.msg) inChat ? T.msgs.push({ who: "npc", text: e.msg }) : npcToast(e.msg);
    else if (e.kind === "info") toast("✦ " + esc(e.msg), "info", 6000);
    else if (e.kind === "ready") readyToast(e);
  }
}
let readyShown = "";
function readyToast(e) {         // 政绩圆满：只提醒，突破要自己去办公室按
  if (readyShown === e.next) return;
  readyShown = e.next;
  const el = document.createElement("div");
  el.className = "toast ready";
  el.innerHTML = `<div><b>✦ ${esc(W("xp"))}圆满 ✦</b><div class="small">可以突破至「${esc(e.next || "")}」了</div></div><button class="small primary">去突破</button>`;
  $("button", el).onclick = () => { el.remove(); if (document.documentElement.classList.contains("in-chat") && !confirm("离开这次功课，回办公室突破？")) return; go("home"); };
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 12000);
}
// ⚡ 按住突破：按住约 1.5 秒蓄力 → 全屏蓄力 → 大典画面。松手就散，不会误触
function bindBreak() {
  const b = $("#rbBtn"); if (!b) return;
  const HOLD = 1500;
  let t0 = 0, raf = 0, done = false;
  const fill = $(".rb-fill", b);
  const stop = () => { if (done) return; cancelAnimationFrame(raf); t0 = 0; b.classList.remove("holding"); fill.style.setProperty("--p", 0); };
  const step = () => {
    const p = Math.min(1, (performance.now() - t0) / HOLD);
    fill.style.setProperty("--p", p);
    if (p >= 1) { done = true; b.classList.remove("holding"); fire(); return; }
    raf = requestAnimationFrame(step);
  };
  b.addEventListener("pointerdown", (ev) => { if (done) return; ev.preventDefault(); try { b.setPointerCapture(ev.pointerId); } catch (e) { /* 不支持就算了 */ } t0 = performance.now(); b.classList.add("holding"); raf = requestAnimationFrame(step); });
  ["pointerup", "pointercancel", "pointerleave"].forEach((k) => b.addEventListener(k, stop));
  b.addEventListener("contextmenu", (ev) => ev.preventDefault());
  b.addEventListener("keydown", (ev) => { if ((ev.key === " " || ev.key === "Enter") && !t0 && !done) { ev.preventDefault(); t0 = performance.now(); b.classList.add("holding"); raf = requestAnimationFrame(step); } });
  b.addEventListener("keyup", (ev) => { if (ev.key === " " || ev.key === "Enter") stop(); });
  async function fire() {
    const ov = document.createElement("div");
    ov.className = "rb-charge";
    ov.innerHTML = `<div class="rb-orb"></div><div class="rb-ring"></div><div class="rb-ring r2"></div><div class="rb-say">整装待发 · 晋升「${esc(DASH.realm.next)}」</div>`;
    document.body.appendChild(ov);
    let res, err;
    await Promise.all([api("/api/realm/break", {}).then((r) => (res = r), (e) => (err = e)), new Promise((r) => setTimeout(r, 1700))]);
    ov.classList.add("burst");
    await new Promise((r) => setTimeout(r, 450));
    ov.remove();
    if (err) { showError(err); await refresh(); render(); return; }
    readyShown = "";
    await refresh(); render();
    handleEvents(res.events);
  }
}
function realmUp(e) {
  if (window.CEREMONY) return CEREMONY.realm(e);      // 觅长生式大典画面（web/ceremony.js）
  const m = $("#modal");
  m.innerHTML = `<div class="levelup ${e.major ? "major" : ""}"><div class="muted rune">${e.major ? `✦ ${esc(W("breakthrough"))} ✦` : `✦ ${esc(W("realm"))}精进 ✦`}</div>
    <div class="lv">${esc(e.name)}</div>
    <div style="font-size:18px;margin-top:8px">${esc(W("score"))} <b style="color:var(--gold)">${e.score}</b> 分</div>
    <br><button class="primary">继续办公</button></div>`;
  m.classList.remove("hidden");
  $("button", m).onclick = () => m.classList.add("hidden");
}

// ------------------------------------------------------------ 导航 / 风格
function go(view) {
  if (VIEW === "notes" && view !== "notes" && window.NOTES) NOTES.flush();
  if (view === "tianji" && VIEW === "tianji" && window.TIANJI && TIANJI.isOpen()) TIANJI.close();   // 在一期里再点顶栏：回时政简报首页
  if (window.CARDS && CARDS.isOpen()) CARDS.close();
  if (window.MINDMAP && MINDMAP.isOpen()) MINDMAP.close();
  VIEW = view;
  if (window.DRAW) setTimeout(() => DRAW.refresh(), 0);
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
  render();
}
document.querySelectorAll("#nav a").forEach((a) => (a.onclick = () => go(a.dataset.view)));
// 平板 App 的返回键（android/…/MainActivity.java 调这个）：先关画面、弹窗、草稿，再回办公室；返回 false 表示没得退了
window.xcBack = () => {
  const click = (sel) => { const b = document.querySelector(sel); if (b) b.click(); return !!b; };
  if (click(".img-zoom") || click(".cer-ok") || click(".st-btn")) return true;
  if (document.documentElement.classList.contains("drawing") && window.DRAW) { DRAW.close(); return true; }
  if (window.NOTES && NOTES.isFull()) { NOTES.exitFull(); return true; }
  if (window.CARDS && CARDS.isOpen()) { CARDS.close(); return true; }
  if (window.MINDMAP && MINDMAP.isOpen()) { MINDMAP.close(); return true; }
  const m0 = $("#modal");
  if (VIEW === "tianji" && window.TIANJI && TIANJI.isOpen() && (!m0 || m0.classList.contains("hidden"))) { TIANJI.close(); return true; }
  const m = $("#modal");
  if (m && !m.classList.contains("hidden")) { m.classList.add("hidden"); return true; }
  if (window.FOCUS && FOCUS.isOn()) { FOCUS.exit(); return true; }
  if (VIEW === "home") return false;
  if (document.documentElement.classList.contains("in-chat") && !confirm("离开这次功课，回办公室？")) return true;
  go("home");
  return true;
};
$("#bgmBtn").onclick = () => AMB.bgm.toggle();   // 背景音乐默认关闭，点了才响
AMB.load();                                        // 背景、语录

function applyTheme() {
  if (!DASH?.theme) return;
  document.body.classList.add("guantu");
  $(".brand").textContent = W("brand");
  document.title = W("brand").replace(/^\S+\s/, "");
  document.querySelectorAll("#nav a").forEach((a) => (a.textContent = W("nav." + a.dataset.view)));
}

async function refresh() {
  try {
    DASH = await api("/api/dashboard");
    applyTheme();
    handleEvents(DASH.events);
    updatePill();
    banner();
    if (DASH.first_today && DASH.greeting && VIEW !== "home") npcToast(DASH.greeting);
  } catch (e) { showError(e); }
}
function updatePill() {
  if (!DASH) return;
  const m = DASH.minutes;
  $("#todayPill").textContent = `🕯 今日学时 ${m.today} / ${m.goal} 分钟（${W("study")} ${m.study ?? m.today} · ${W("lecture")} ${m.lecture ?? 0}）` + (m.today >= m.goal ? " ✦" : "");
  updateStudyDot();
}
function banner() {
  const w = [];
  if (!DASH.vault) w.push("还没找到申论库，请到“设置”里填写库的路径。");
  if (!DASH.ai) w.push(`还没填写 AI 的 API key：${W("yj_review")}、读采分点都能用；作答批改、导师聊天、「🙋 领导讲讲」、「🧙 领导制卡」需要 AI。去“设置”填写。`);
  if (DASH.rest > 0) w.push(`${W("qi")}预警：还需休息 ${DASH.rest} 分钟。站起来走走、喝口水。`);
  (DASH.notices || []).forEach((n) => w.push(esc(n)));
  if (DASH.upgraded?.length) w.push("程序升级了配置文件：" + DASH.upgraded.map((n) => `训练/${esc(n)}`).join("、") + "。原来的版本备份成了同名的“.旧版.md”。");
  if (DASH.other_device) w.push(`另一台电脑（${esc(DASH.other_device)}）10 分钟内在用本程序。两台同时用，坚果云同步可能冲突，请先关掉那台。`);
  if (DASH.conflicts?.length) w.push("存档文件夹里有坚果云冲突副本：" + DASH.conflicts.map(esc).join("、") + "。保留较新的一份，删掉另一份。");
  $("#banner").innerHTML = w.map((x) => `<div class="warn">${x}</div>`).join("");
}

async function render() {
  const v = $("#view");
  document.documentElement.classList.remove("in-chat");
  document.documentElement.classList.toggle("in-notes", VIEW === "notes");
  try {
    if (VIEW === "home") { await refresh(); v.innerHTML = views.home(); bindHome(); }
    else if (VIEW === "train") { if (!DASH) await refresh(); v.innerHTML = await views.train(); bindTrain(); }
    else if (VIEW === "contest") { if (!DASH) await refresh(); await CONTEST.render(v); }
    else if (VIEW === "tianji") { if (!DASH) await refresh(); await TIANJI.render(v); }
    else if (VIEW === "notes") { if (!DASH) await refresh(); await NOTES.render(v); }
    else if (VIEW === "skeleton") { if (!DASH) await refresh(); v.innerHTML = await views.skeleton(); bindSkeleton(); }
    else if (VIEW === "bank") { HALL = 'shizhan'; return go('train'); }   // 实操并进了办理殿
    else if (VIEW === "wrong" || VIEW === "pill") { VIEW = "log"; return go("log"); }   // 整改录、补课室在 3.0 去掉了
    else if (VIEW === "log") { await refresh(); v.innerHTML = views.log(); bindLog(); }
    else if (VIEW === "settings") { await refresh(); await AMB.load(); v.innerHTML = await views.settings(); bindSettings(); }
  } catch (e) { showError(e); }
}

// ------------------------------------------------------------ 小组件
const STATE_TAG = { current: `<span class="tag cur">◆当前</span>`, mastered: `<span class="tag ok">★圆满</span>`,
  cleared: `<span class="tag ok">已打通</span>`, locked: `<span class="tag lock">🔒未解锁</span>`, later: "" };

function rootBadge(r) {
  if (!r) return "";
  if (!r.on) return `<span class="tag lock">${esc(r.name)}未养成</span>`;
  return `<span class="tag root t${r.tier}">${esc(r.name)} · ${esc(r.grade_name)}</span>`;
}
function bar(frac, cls = "") { return `<div class="bar ${cls}"><div style="width:${Math.max(0, Math.min(100, pct(frac)))}%"></div></div>`; }
function taskRow(t) {
  const ck = t.done ? (t.ok === false ? "❌" : "✅") : "⬜";
  return `<div class="task ${t.done ? "done" : ""} ${t.type === "tribulation" ? "trib" : ""}" data-task="${esc(t.id)}">
    <span class="ck">${ck}</span><span class="ttl">${esc(t.title)}</span><span class="spacer"></span><span class="min">${t.minutes} 分钟</span></div>`;
}
function recentList(ev) {
  if (!ev?.length) return '<div class="muted small">还没有记录</div>';
  return ev.map((e) => `<div class="row small"><span class="faint">${esc(e.t?.slice(5, 16).replace("T", " ") || e.d)}</span>
    <span>${esc(e.note)}</span><span class="spacer"></span>${e.xp ? `<b style="color:var(--gold)">+${e.xp}</b>` : ""}</div>`).join("");
}
// 消息里的网页块：文字（夹着的 ![[库内路径]] 是行内小图，如公式）、图片、成绩表
// 题目：去掉题干、问题、选项之间的空行；连着的 A/B/C/D 行排成选项格（layoutOpts 按最长选项决定一行放 4 个、2 个还是 1 个）
const OPT_RE = /^\s*-?\s*(?:\*\*)?([A-D])\s*[.．、](?:\*\*)?\s*(.*)$/;
function qTextHtml(text, inline) {
  const lines = String(text || "").split("\n").filter((l) => l.trim());
  const out = [];
  let buf = [], opts = [];
  const flushText = () => { if (buf.length) { out.push(`<div class="q-text">${inline(md(buf.join("\n")))}</div>`); buf = []; } };
  const flushOpts = () => {
    if (!opts.length) return;
    if (opts.length < 2 || opts[0][0] !== "A") { buf.push(...opts.map((o) => o[2])); opts = []; return; }   // 不像选项：当正文
    flushText();
    out.push(`<div class="opts">${opts.map(([k, v]) => `<div class="opt"><b>${k}.</b> ${inline(md(v))}</div>`).join("")}</div>`);
    opts = [];
  };
  for (const l of lines) {
    const m = l.match(OPT_RE);
    if (m && (!opts.length || m[1].charCodeAt(0) === opts[opts.length - 1][0].charCodeAt(0) + 1)) { if (!opts.length) flushText(); opts.push([m[1], m[2], l]); }
    else { flushOpts(); buf.push(l); }
  }
  flushOpts(); flushText();
  return out.join("");
}
function layoutOpts(root = document) {
  root.querySelectorAll(".opts").forEach((el) => {
    const W = el.clientWidth;
    if (!W) return;
    el.classList.add("measure");
    const widest = Math.max(...[...el.children].map((c) => c.getBoundingClientRect().width));
    el.classList.remove("measure");
    const gap = 18;
    const cols = widest * 4 + gap * 3 <= W ? 4 : widest * 2 + gap <= W ? 2 : 1;
    el.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
  });
}
let OPT_T = null;
addEventListener("resize", () => { clearTimeout(OPT_T); OPT_T = setTimeout(() => layoutOpts(), 150); });
function blocksHtml(list, trim = false, question = false) {
  const inline = (h) => h.replace(/!\[\[([^\]]+)\]\]/g, (_, p) => `<img class="inline-img" src="/vault-file?p=${encodeURIComponent(p.replace(/&amp;/g, '&'))}">`);
  const table = (b) => `<div class="tbl-wrap"><table class="result-table"><thead><tr>${b.head.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${
    b.rows.map(r => `<tr class="${r.includes('✗') ? 'bad' : r.includes('✓') ? 'good' : 'sum'}">${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  return (list || []).map((b) => b.t === "img" ? `<img src="/vault-file?p=${encodeURIComponent(b.v)}${trim ? "&trim=1" : ""}">` : b.t === "table" ? table(b)
    : question ? qTextHtml(b.v, inline) : `<div>${inline(md(b.v))}</div>`).join("");
}
function msgHtml(m) {
  const blocks = blocksHtml(m.blocks, false, !!m.pin);
  if (m.fold) return `<details class="fold"><summary>${esc(m.fold)}</summary><div>${md(m.text)}</div></details>`;
  if (m.who === "npc") return `<div class="npc">${tutorFace()}<div class="say"><div class="who">${esc(DASH?.persona?.tutor || "导师")}</div>${md(m.text)}</div></div>`;
  if (m.who === "me") return `<div class="msg me">${esc(m.text)}</div>`;
  if (m.pin) return `<div class="q-pin ${PIN_MINI ? "mini" : ""}"><div class="msg sys pin-body"><span class="pin-tools">${m.material?.length
      ? `<button class="pin-btn mat-btn ${MAT_OPEN ? "on" : ""}" title="材料放在左边，对照着看">📄 ${MAT_OPEN ? "收起材料" : "弹出材料"}</button>` : ""}<button class="pin-btn pin-fold" title="${PIN_MINI ? "展开题目" : "把题目收成一行"}">📌 ${PIN_MINI ? "展开" : "收起"}</button></span>${md(m.text)}${blocks}</div>
      <div class="pin-drag" title="按住上下拖：调题目框和下面解析各占多少"></div></div>`;
  return `<div class="msg sys">${md(m.text)}${blocks}</div>`;
}
// 题目钉在对话框顶上（往下翻解析时不动）；📌 收成一行 / 展开，每台设备记住
let PIN_MINI = (() => { try { return localStorage.getItem("srpg-pin-mini") === "1"; } catch (e) { return false; } })();
// 资料分析 / 一拖五：材料放在对话框左边（像粉笔的“弹出材料”），题目和解析在右边；默认弹出，收起后每台设备记住
let MAT_OPEN = (() => { try { return localStorage.getItem("srpg-mat-open") !== "0"; } catch (e) { return true; } })();
function currentMaterial() {
  for (let i = T.msgs.length - 1; i >= 0; i--) if (T.msgs[i].material?.length) return T.msgs[i].material;
  return null;
}
function materialPane() {
  const mat = currentMaterial();
  if (!mat || !MAT_OPEN) return "";
  return `<div class="mat-pane"><div class="mat-head"><b>📄 材料</b><span class="small faint" style="margin-left:8px">点图片放大</span><span class="spacer"></span><button class="ghost small mat-btn">收起材料</button></div>${blocksHtml(mat, true)}</div>`;
}
// 材料里的图：点一下全屏看（再点 / Esc / 返回键关）
function zoomImg(src) {
  const el = document.createElement("div");
  el.className = "img-zoom";
  el.innerHTML = `<img src="${src}"><span class="small">点任意处关闭</span>`;
  const close = () => { el.remove(); document.removeEventListener("keydown", key); };
  const key = (e) => { if (e.key === "Escape") close(); };
  el.onclick = close;
  document.addEventListener("keydown", key);
  document.body.appendChild(el);
}
// 草稿笔记按题存（web/draw.js）：做题 / 复盘时是屏幕上这道题，别的页面按页面
window.DRAW_KEY = () => {
  if (window.CARDS && CARDS.drawKey()) return CARDS.drawKey();      // 过便笺：每张卡一份草稿
  if (VIEW === "train" && T.session) for (let i = T.msgs.length - 1; i >= 0; i--) if (T.msgs[i].qkey) return T.msgs[i].qkey;
  return "page:" + VIEW;
};
// 资料分析 / 一拖五：左边材料上的笔记按这段材料存（同一组几道题共用）；材料收起时不算
window.DRAW_MKEY = () => {
  if (VIEW !== "train" || !MAT_OPEN) return "";
  const mat = currentMaterial();
  if (!mat) return "";
  const t = JSON.stringify(mat);
  let h = 5381;
  for (let i = 0; i < t.length; i++) h = ((h * 33) ^ t.charCodeAt(i)) >>> 0;
  return "mat:" + h.toString(36) + ":" + t.length;
};
window.DRAW_IN_MAT = (x, y) => {
  const p = document.querySelector(".mat-pane");
  if (!p) return false;
  const r = p.getBoundingClientRect();
  return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
};
// 题目框和下面解析之间的分隔条：按住上下拖，题目框高度记在这台设备（占屏幕高度的百分比）
let PIN_H = (() => { try { return Number(localStorage.getItem("srpg-pin-h")) || 0; } catch (e) { return 0; } })();
function applyPinH() { document.documentElement.style.setProperty("--pin-h", PIN_H ? PIN_H + "vh" : "46vh"); }
applyPinH();
function bindPinDrag() {
  document.querySelectorAll(".q-pin .pin-drag").forEach((h) => (h.onpointerdown = (e) => {
    const pin = h.closest(".q-pin"), box = $("#msgs");
    if (!pin || !box) return;
    e.preventDefault();
    h.setPointerCapture(e.pointerId);
    pin.classList.add("dragging");
    const y0 = e.clientY, h0 = pin.getBoundingClientRect().height, maxH = box.clientHeight - 60;
    const mv = (ev) => {
      const px = Math.max(70, Math.min(maxH, h0 + ev.clientY - y0));
      PIN_H = Math.round(px / innerHeight * 1000) / 10;
      applyPinH();
    };
    const upf = () => {
      h.removeEventListener("pointermove", mv); h.removeEventListener("pointerup", upf); h.removeEventListener("pointercancel", upf);
      pin.classList.remove("dragging");
      try { localStorage.setItem("srpg-pin-h", String(PIN_H)); } catch (err) { /* 只管这一次 */ }
    };
    h.addEventListener("pointermove", mv); h.addEventListener("pointerup", upf); h.addEventListener("pointercancel", upf);
  }));
  bindPinReset();
}
function bindPinReset() {   // 双击分隔条：恢复默认高度
  document.querySelectorAll(".q-pin .pin-drag").forEach((h) => (h.ondblclick = () => {
    PIN_H = 0; applyPinH();
    try { localStorage.removeItem("srpg-pin-h"); } catch (err) { /* 只管这一次 */ }
  }));
}
function bindPins() {
  layoutOpts();
  bindPinDrag();
  if (window.DRAW) DRAW.refresh();
  document.querySelectorAll(".mat-pane img:not(.inline-img), .q-pin img:not(.inline-img)").forEach((im) => (im.onclick = () => zoomImg(im.src)));
  document.querySelectorAll(".mat-btn").forEach((b) => (b.onclick = (e) => {
    e.stopPropagation();
    MAT_OPEN = !MAT_OPEN;
    try { localStorage.setItem("srpg-mat-open", MAT_OPEN ? "1" : "0"); } catch (err) { /* 只管这一次 */ }
    const keep = $("#msgs")?.scrollTop || 0;
    renderTrain().then(() => { const m = $("#msgs"); if (m) m.scrollTop = keep; });
  }));
  document.querySelectorAll(".q-pin .pin-fold").forEach((b) => (b.onclick = (e) => {
    e.stopPropagation();
    PIN_MINI = !PIN_MINI;
    try { localStorage.setItem("srpg-pin-mini", PIN_MINI ? "1" : "0"); } catch (err) { /* 只管这一次 */ }
    document.querySelectorAll(".q-pin").forEach((q) => {
      q.classList.toggle("mini", PIN_MINI);
      const btn = q.querySelector(".pin-fold"); btn.textContent = "📌 " + (PIN_MINI ? "展开" : "收起"); btn.title = PIN_MINI ? "展开题目" : "把题目收成一行";
    });
  }));
}
function boardOptions(list) { return list.map((b) => `<option>${esc(b)}</option>`).join(""); }

// ------------------------------------------------------------ 政绩录里的办理进度：今日功课、办理进度、专长、整改榜、周例会、文件袋、年度考核战绩
function progressParts(d) {
    const tasks = d.plan.tasks;
    const doneN = tasks.filter((t) => t.done).length;
    const totalMin = tasks.reduce((a, t) => a + t.minutes, 0);
    let lastBatch = 0;
    const tree = d.tree.map((s) => {
      let h = "";
      if (s.batch !== lastBatch) { lastBatch = s.batch; h += `<div class="batch-h">第 ${s.batch} ${esc(W("batch"))}</div>`; }
      const acc = s.acc ? `实战 ${pct(s.acc.rate)}% ${s.acc.trend}` : "实战 —";
      const sk = s.state === "locked" ? "" : s.skeleton === "none" ? `<span class="tag draft">无${esc(W("skeleton"))}</span>` : s.skeleton === "draft" ? `<span class="tag draft">${esc(W("skeleton"))}草稿</span>` : "";
      const color = s.state === "mastered" ? "green" : s.state === "current" ? "yellow" : "";
      return h + `<div class="skill ${s.state === "locked" ? "locked" : ""}"><div class="top"><span>${esc(s.board)} ${STATE_TAG[s.state] || ""}${sk}</span>
        <span class="muted small">${acc}</span></div>${bar(s.progress, "thin " + color)}
        <div class="faint small">${s.items ? `${s.mastered}/${s.items} ${esc(W("item"))}圆满 · ${pct(s.progress)}%` : ""} ${s.root?.on ? rootBadge(s.root) : ""}</div></div>`;
    }).join("");
    const roots = d.roots.map((r) => `<div class="root ${r.on ? "on t" + r.tier : ""}"><div class="row"><b>${esc(r.name)}</b><span class="spacer"></span><span class="small">${esc(r.grade_name)}</span></div>
        <div class="small muted">${r.acc != null ? `正确率 ${pct(r.acc)}%` : "暂无数据"}${r.on && r.bonus ? ` · ${esc(W("xp"))} +${pct(r.bonus)}%` : ""}${!r.on ? ` · 养成：${r.route === "业务手册" ? `${esc(W("skeleton"))}全部圆满` : "两季正确率达线"}` : ""}</div></div>`).join("");
    const demon = d.demon.slice(0, 6).map((r, i) => `<div class="row small"><span class="rank">${i + 1}</span><span>${esc(r.board)}</span><span class="spacer"></span><b style="color:${i < 2 ? "var(--red)" : "var(--muted)"}">${pct(r.acc)}%</b></div>`).join("") || '<div class="muted small">还没有模考数据</div>';
    const weekly = d.weekly.map((q) => `<div class="small"><div class="row"><span>${q.done ? "✅" : "⬜"} ${esc(q.name)}</span><span class="spacer"></span><span class="muted">${q.progress}/${q.target}</span></div>${bar(q.progress / q.target, "thin " + (q.done ? "green" : ""))}</div>`).join("");
    const bag = d.bag.length ? d.bag.map((b) => `<div class="small row"><b>${esc(b.name)}</b><span class="muted">×${b.count}</span><span class="spacer"></span><span class="faint">${esc(b.desc)}</span></div>`).join("") : `<div class="muted small">空空如也。${esc(W("boss"))}达到${esc(W("tribulation"))}线得突破信物，${esc(W("weekly"))}全勤得护身之物。</div>`;
    const boss = d.boss.length ? d.boss.slice().reverse().map((b) => `${esc(b.name)} <b>${b.score}</b> <span class="faint small">${b.d}</span>`).join(" · ") : `<span class="muted">还没有战绩。模考出分后在上面「记录${esc(W("boss"))}」里记。</span>`;
    const ascend = d.ascend.length ? `<div class="ascend">🌈 ${esc(W("ascend"))}：${d.ascend.map((b) => `${esc(b.name)} ${b.score} 分`).join("；")}</div>` : "";
  return { tasks, doneN, totalMin, tree, roots, demon, weekly, bag, boss, ascend };
}

// ------------------------------------------------------------ 页面
const views = {
  home() {
    const d = DASH; if (!d) return "";
    const R = d.realm, p = d.persona, I = d.ideal, F = d.forecast;
    const avatar = p.avatar ? `<img src="${esc(p.avatar)}" alt="头像">` : `<div class="def">${esc((p.id || "修").slice(0, 1))}</div>`;
    const diff = I.diff_days;
    const ideal = diff > 0.5 ? `<div class="v bad">落后 ${diff} 天</div><div class="d">${I.catch ? `每天多修 ${I.catch.per_day} 分钟约 ${I.catch.days} 天追平，或多做几道题` : ""}</div>`
      : diff < -0.5 ? `<div class="v good">领先 ${-diff} 天</div><div class="d">保持住</div>` : `<div class="v">恰在线上</div><div class="d">按计划修行</div>`;
    const barLabel = R.ready
      ? `<span class="rb-label">✦ ${esc(W("xp"))}圆满 → 可突破至「${esc(R.next)}」${R.ready_count > 1 ? `（攒够了 ${R.ready_count} 层，可一层层连破）` : ""}</span>`
      : R.bottleneck
      ? `<span style="color:var(--gold)">⚡ ${esc(W("bottleneck"))}：积压${esc(W("xp"))} ${R.overflow}，${esc(W("tribulation"))}成功后一次涌入</span>`
      : `${esc(W("xp"))} ${R.into} / ${R.need}${R.next ? ` → ${esc(R.next)}` : ""}`;
    const trib = d.trib ? `<div class="card trib-card"><h3>⚡ ${esc(W("tribulation"))} · 冲击${esc(d.trib.realm)} <small>${d.trib.thunders} 道关卡 · ${esc(d.trib.pill)} ×${d.trib.pills}</small></h3>
        <div class="conds">${d.trib.conds.map((c) => `<div class="cond ${c.ok ? "ok" : "no"}"><b>${c.ok ? "✓" : "✗"} ${esc(c.name)}</b><span class="small">${esc(c.text)}${c.need && !c.ok ? `（${esc(c.need)}）` : ""}</span></div>`).join("")}</div>
        ${d.trib.ready ? `<div class="row" style="margin-top:10px"><button class="primary big" id="tribBtn">⚡ 开始${esc(W("tribulation"))}</button><span class="small muted">开始后不能跳过；失败会状态受损，冷却几天并需${esc(W("heal"))}</span></div>` : ""}</div>` : "";
    const retreat = d.retreat ? `<div class="card retreat row"><b>🧘 ${esc(W("retreat"))}中：${esc(d.retreat.board)}</b> <span id="retreatLeft" class="muted"></span>
        <span class="spacer"></span><button class="small" id="retreatEnd">${esc(W("retreat_end"))}</button></div>` : "";
    return `
    <div class="card npc greet">${tutorFace()}<div><div class="who">${esc(p.tutor)}</div><div id="greet">${md(d.greeting)}${d.greet_pending ? '<div class="thinking small">正在打量你</div>' : ""}</div></div></div>
    ${retreat}
    <div class="card hero">
      <div class="avatar">${avatar}</div>
      <div class="hero-main">
        <div class="hero-name">${esc(p.id)}<small>「${esc(p.call)}」</small></div>
        <div class="realm-name">${esc(R.name)}${R.bottleneck ? ` <span class="tag cur">${esc(W("bottleneck"))}</span>` : ""}</div>
        <div class="hero-title">第 ${d.lap} 个${esc(W("lap"))} · ${d.batch.index ? `第 ${d.batch.index}/${d.batch.count} ${esc(W("batch"))}：${d.batch.boards.map(esc).join("、")}` : "本轮已圆满"}</div>
        <div class="row small muted" style="margin-top:8px"><span>${barLabel}</span><span class="spacer"></span><span>累计 ${d.xp}</span></div>
        ${bar(R.frac, R.ready ? "full" : "")}
        ${R.ready ? `<div class="rb-row"><button class="rb-btn" id="rbBtn" type="button"><span class="rb-fill"></span><span class="rb-txt">⚡ 按住突破 · ${esc(R.next)}</span></button>
          <span class="small muted">按住约 1.5 秒确认晋升，松手则取消</span></div>` : ""}
      </div>
      <div class="hero-score"><div class="small muted">${esc(W("score"))}</div><div class="big">${R.score}<span>分</span></div>
        <div class="small muted">目标 ${R.target} 分</div>
        <button class="ghost small ps-open" id="psHero" title="今日办理战报：画成一张海报，可以存图、分享">🖼 办理战报</button></div>
    </div>
    ${timeCard(d)}
    <div class="grid g5" style="margin-top:14px">
      <div class="stat"><div class="k">🔥 ${esc(W("streak"))}</div><div class="v">${d.streak.days} 天</div><div class="d">${esc(W("xp"))}加成 +${pct(d.streak.bonus)}%</div></div>
      <div class="stat"><div class="k">🪷 ${esc(W("dao"))}</div><div class="v ${d.dao.value < 60 ? "bad" : ""}">${d.dao.value} · ${esc(d.dao.label)}</div><div class="d">近 14 天办理的稳定度</div></div>
      <div class="stat"><div class="k">🧵 ${esc(W("ideal"))}</div>${ideal}</div>
      <div class="stat"><div class="k">🗺 本轮进度</div><div class="v">${pct(F.progress)}%</div><div class="d">${F.days_left ? `按近 7 天速度还需 ${F.days_left} 天` : "修几天后给出预测"}</div></div>
      <div class="stat"><div class="k">🎯 预计 ${I.target_score} 分</div><div class="v">${I.eta || "—"}</div><div class="d">目标日 ${I.target}</div></div>
    </div>
    ${trib}
    ${boardTimeCard(d)}
    ${lectureCard(d)}
    ${practiceCard(d)}
    ${selfstudyCard(d)}
    `;
  },

  async train() {
    const tasks = DASH?.plan?.tasks || [];
    const idle = () => !T.session && !T.msgs.length && !T.busy;
    if (idle()) {
      const hub = await hubHtml();
      if (idle()) return hub;   // 殿里的数据还没载完就点了功课：以功课对话框为准，不能被殿覆盖
    }
    const inp = T.input;
    let composer = "";
    if (T.busy) composer = `<div class="thinking">${esc(DASH?.persona?.tutor || "导师")}正在判定</div>`;
    else if (inp.mode === "text" && inp.buttons) {
      // 复盘类（复盘 / 考核复盘 / 题后讨论）：打字框默认收起，点左下角「主任求助」才打开，题目区域更大
      composer = `${ASK_OPEN ? `<textarea id="answer" placeholder="${esc(inp.placeholder || "")}"></textarea>` : ""}
        <div class="row composer-row" style="margin-top:${ASK_OPEN ? 8 : 0}px"><button class="${ASK_OPEN ? "" : "ghost"} ask-btn" id="askToggle">🙋 ${ASK_OPEN ? "收起" : "主任求助"}</button>${ASK_OPEN ? `<button class="primary" id="send">问主任</button>` : ""}<span class="spacer"></span>
        ${inp.buttons.map((b) => `<button class="ghost" data-act="${esc(b.id)}">${esc(b.label)}</button>`).join("")}</div>`;
    }
    else if (inp.mode === "text") composer = `<textarea id="answer" placeholder="${esc(inp.placeholder || "")}"></textarea>
        <div class="row" style="margin-top:8px"><span class="spacer"></span>
        <button class="ghost" data-act="skip">跳过</button><button class="primary" id="send">提交</button></div>`;
    else if (inp.mode === "buttons") composer = `<div class="row">${inp.buttons.map((b) => `<button class="${b.id === "skip" ? "ghost" : "primary"}" data-act="${esc(b.id)}">${esc(b.label)}</button>`).join("")}</div>`;
    else if (T.finished) composer = `<div class="row"><button class="primary" id="nextTask">下一项功课</button><button class="ghost" id="backHome">回办理殿</button></div>`;
    return `<div class="train">
      <div class="card"><h3>📜 主任荐课</h3>${tasks.map(taskRow).join("")}<button class="ghost small" id="toHall" style="margin-top:8px">↩ 回办理殿</button></div>
      <div class="card chat ${MAT_OPEN && currentMaterial() ? "with-mat" : ""}">${sessionHead()}${materialPane()}<div class="msgs" id="msgs">${T.msgs.map(msgHtml).join("")}</div>
        <div class="composer">${composer}</div></div></div>`;
  },

  async skeleton() {
    const tabs = `<div class="lib-head"><h2>${esc(NAV('skeleton'))}</h2><div class="lib-tabs">
      <button class="${LIB.tab === 'cards' ? 'on' : ''}" data-libtab="cards">📗 ${esc(W('yj'))} · 知识点</button>
      <button class="${LIB.tab === 'bank' ? 'on' : ''}" data-libtab="bank">📑 题库 · 采分点</button>
      <button class="${LIB.tab === 'jiaocai' ? 'on' : ''}" data-libtab="jiaocai">📜 ${esc(W('skeleton'))} · 教材</button></div></div>`;
    if (LIB.tab === 'bank' && window.SHENLUN) return tabs + await SHENLUN.libHtml();
    if (LIB.tab === 'jiaocai') return tabs + await jiaocaiHtml();
    return tabs + await cardsLibHtml();
  },

  log() {
    const d = DASH;
    const P = progressParts(d);
    return `<div class="card ascend-card"><h3>🌈 ${esc(W("ascend"))}（国考） <small>真正的那一场：出分后在这里留下记录</small></h3>
        <div class="ascend-row">
          <div class="ascend-list">${d.ascend.length ? d.ascend.map((b) => `<div><b>${esc(b.name)}</b> ${b.score} 分 <span class="faint small">${b.d}</span></div>`).join("") : '<p class="muted small">还没有上岸记录。</p>'}</div>
          <details class="fold form-fold"><summary>✍ 记录${esc(W("ascend"))}</summary><div class="row"><input id="asName" placeholder="如 2026 国考" style="flex:2"><input id="asScore" placeholder="申论分数" style="flex:1">
          <select id="asResult" style="width:auto"><option>进面</option><option>上岸</option><option>未进面</option></select><button class="primary" id="asBtn">记录</button></div></details></div></div>
    <div class="log-cols">
      <div class="log-col">
        <div class="card"><h3>📜 ${esc(W("tasks"))} <small>${P.doneN}/${P.tasks.length} · 约 ${P.totalMin} 分钟</small></h3>
          <div id="tasks">${P.tasks.map(taskRow).join("") || `<div class="muted">今天没有功课。</div>`}</div>
          <div class="row" style="margin-top:8px"><button class="ghost small" id="regen">重新生成${esc(W("tasks"))}</button>
          <button class="small" id="chatBtn">💬 ${esc(W("chat_btn"))}</button></div></div>
        <div class="card"><h3>⚔ 记录${esc(W("boss"))}（模考成绩）</h3>
          <details class="fold form-fold"><summary>✍ 记一次成绩</summary>
          <div class="row"><input id="bossName" placeholder="名称，如 第37季" style="flex:2"><input id="bossScore" placeholder="分数" style="flex:1"><button class="primary" id="bossBtn">记录</button></div>
          <div class="small muted" style="margin-top:6px">最近两次的较低分若高于当前${esc(W("score"))}，${esc(W("xp"))}直接补上；达到下一道${esc(W("tribulation"))}线得推荐函</div></details></div>
        <div class="card"><h3>📜 ${esc(W("leave"))} <small>本月已用 ${d.leave.used}/${d.leave.total}</small></h3>
          <p class="muted small">生病、家里有事、加班……用一份${esc(W("leave"))}：今天${esc(W("streak"))}不断，也不计入${esc(W("ideal"))}。</p>
          <button id="leaveBtn" ${d.leave.today ? "disabled" : ""}>${d.leave.today ? "今天已调休" : "使用" + esc(W("leave"))}</button></div>
      </div>
      <div class="card"><h3>⚔ 办理进度 <small>${esc(W("skeleton"))}圆满度 · 实战正确率 · ${esc(W("root"))}</small></h3><div class="tree">${P.tree}</div></div>
    </div>
    <div class="grid g3" style="margin-top:14px">
      <div class="card"><h3>🌱 ${esc(W("root"))}</h3><div class="roots">${P.roots}</div></div>
      <div class="card"><h3>👹 ${esc(W("demon_rank"))} <small>正确率越低，${esc(W("wrong"))}越凶</small></h3>${P.demon}
        <h3 style="margin-top:14px">🏢 ${esc(W("weekly"))}</h3>${P.weekly}</div>
      <div class="card"><h3>🎒 ${esc(W("bag"))}</h3>${P.bag}
        <h3 style="margin-top:14px">⚔ ${esc(W("boss"))}战绩</h3><div>${P.boss}</div>${P.ascend}</div>
    </div>
    <div class="card" style="margin-top:14px"><h3>📖 工作日志</h3>${recentList(d.recent)}</div>`;
  },

  async settings() {
    const s = await api("/api/settings");
    const cur = DASH?.theme?.name;
    const cp = chatPrefs();
    return (await DEVICE.html()) + AMB.settingsHtml() + `<div class="card"><h3>🪟 对话框大小与字体 <small>做功课时的对话框；只存在这台设备里（电脑、平板各调各的）</small></h3>
      <div class="row"><label style="flex:1">宽度 <b id="cwV">${cp.w}%</b><input type="range" id="cwR" min="40" max="100" step="5" value="${cp.w}" style="width:100%"></label>
        <label style="flex:1">高度 <b id="chV">${cp.h}%</b><input type="range" id="chR" min="40" max="100" step="5" value="${cp.h}" style="width:100%"></label></div>
      <div class="row"><label style="flex:1">对话框字体 <b id="cfV">${cp.fs}%</b><input type="range" id="cfR" min="80" max="160" step="5" value="${cp.fs}" style="width:100%"></label>
        <div style="flex:1" class="small muted" id="cfDemo">示例：<span style="font-size:calc(15px * ${cp.fs / 100})">人民是历史的创造者，人民是真正的英雄。</span></div></div>
      <div class="row"><label style="display:inline-flex;align-items:center;gap:6px"><input type="checkbox" id="csideR" style="width:auto" ${cp.side ? "checked" : ""}> 左边显示“主任荐课”栏</label><span class="spacer"></span>
        <button class="ghost small" id="cResetR">恢复默认（宽 80%、高 100%、字体 110%）</button></div>
      <p class="small muted">高度 100% = 从顶栏下面一直到屏幕底；对话框底边总是贴着屏幕底。改了马上生效，下次做功课就是这个大小。</p></div>
      <div class="card"><h3>本机设置 <small>保存在本机 ~/.shenlun-rpg/settings.json，不会同步、不会上传</small></h3>
      <label class="small muted">申论库路径（含 copilot/skills 的文件夹；程序放在库里时会自动找到）</label>
      <input id="sVault" value="${esc(s.vault_setting)}" placeholder="${esc(s.vault || "例如 C:\\Users\\你\\Desktop\\申论obsidian\\申论")}">
      <div class="small faint">当前使用：${esc(s.vault || "未找到")}</div><br>
      <div class="ai-switch"><b>🤖 当前 AI</b>
        <select id="sProf">${(s.ai_profiles || []).map(p => `<option value="${esc(p.name)}" ${p.name === s.ai_active ? "selected" : ""}>${esc(p.name)} · ${esc(p.model)}</option>`).join("")}
          ${s.ai_active && (s.ai_profiles || []).some(p => p.name === s.ai_active) ? "" : `<option value="" selected>（当前设置：${esc(s.model)}，还没存成方案）</option>`}</select>
        <button class="small" id="sProfSave" title="把下面这套 接口地址 + 模型 + key 存成一套，起个名字">💾 存为一套</button>
        ${(s.ai_profiles || []).length ? '<button class="small ghost" id="sProfDel" title="删掉下拉里选中的这套">🗑</button>' : ""}</div>
      <p class="small muted" style="margin-top:2px">常用的几套（DeepSeek、通义千问、Kimi、智谱…）各存一套，下拉一选就换；导师、领导解惑、领导讲讲、领导制卡都跟着换。新加一套：下面「常用接口」选一个、填 key 和模型 → 保存 → 「存为一套」。</p>
      <label class="small muted">AI 的 API key ${s.has_key ? `（已填写，末尾 ${esc(s.key_tail)}；不改就留空）` : ""}</label>
      <input id="sKey" type="password" placeholder="sk-……">
      <div class="row" style="margin-top:8px">
        <div style="flex:2"><label class="small muted">接口地址 <select id="sPreset" class="ai-preset"><option value="">常用接口…</option>${AI_PRESETS.map((p, i) => `<option value="${i}">${esc(p[0])}</option>`).join("")}</select></label><input id="sBase" value="${esc(s.base_url)}"></div>
        <div style="flex:1"><label class="small muted">模型</label><input id="sModel" value="${esc(s.model)}"></div></div>
      <details class="sv-vision" style="margin-top:10px"${s.vision_model ? " open" : ""}><summary class="small">🪶 识图模型（领导制卡读扫描版 PDF 用，可不填）</summary>
      <p class="small muted">填一个能看图的模型（如 qwen-vl-max、gpt-4o、glm-4v）：「🧙 领导制卡」遇到扫描版 PDF（页面是图片）时让它看图认字。接口地址、key 和上面一样时留空。</p>
      <div class="row">
        <div style="flex:1"><label class="small muted">识图模型</label><input id="sVModel" value="${esc(s.vision_model || "")}" placeholder="如 qwen-vl-max"></div>
        <div style="flex:2"><label class="small muted">接口地址（留空 = 同上）</label><input id="sVBase" value="${esc(s.vision_base_url || "")}" placeholder="${esc(s.base_url)}"></div></div>
      <label class="small muted">识图 API key ${s.vision_has_key ? "（已单独填写；不改就留空）" : "（留空 = 用上面的 key）"}</label>
      <input id="sVKey" type="password" placeholder="sk-……"></details>
      <div class="row" style="margin-top:12px"><button class="primary" id="sSave">保存</button><button id="sTest">测试 AI 连接</button><span id="sMsg" class="small muted"></span></div></div>
      <div class="card"><h3>改规则 / 人设 / 台词</h3>
      <p>在 Obsidian 里直接编辑库里的这些文件，保存后刷新网页就生效：</p>
      <ul><li><b>训练/规则.md</b>：目标日、职级分数线、晋升考核条件、专长门槛、补课券、周例会、政绩值……</li>
      <li><b>训练/角色设定.md</b>：ID、头像；称呼、导师名 / 头像 / 人设</li>
      <li><b>训练/台词库.md</b>：导师的备用台词（没连 AI 时用）</li>
      <li><b>训练/骨架/题型.md</b>：每个题型的${esc(W("skeleton"))}（默写标准）</li></ul>
      <p class="small muted">头像：把图片放进 <b>训练/</b>，文件名写进角色设定.md 的“头像”“官场.导师头像”。</p></div>`;
  },
};

// 设置里「常用接口」：[名字, 接口地址, 默认模型]（都是 OpenAI 兼容接口；模型名可以自己改）
const AI_PRESETS = [
  ["DeepSeek", "https://api.deepseek.com", "deepseek-chat"],
  ["DeepSeek（深度思考）", "https://api.deepseek.com", "deepseek-reasoner"],
  ["通义千问（阿里百炼）", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"],
  ["Kimi（月之暗面）", "https://api.moonshot.cn/v1", ""],
  ["智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"],
  ["硅基流动", "https://api.siliconflow.cn/v1", ""],
  ["OpenAI", "https://api.openai.com/v1", ""],
];

// ------------------------------------------------------------ 交互绑定
function bindTaskClicks(root) {
  root.querySelectorAll("[data-task]").forEach((el) => (el.onclick = () => el.dataset.task === "cards:all" && window.CARDS
    ? (VIEW === "train" ? CARDS.review("") : (HALL = "xiulian", go("train"), setTimeout(() => CARDS.review(""), 300)))
    : startTask({ task_id: el.dataset.task })));
}
function bindRetreatTimer() {
  const el = $("#retreatLeft"), btn = $("#retreatEnd");
  if (btn) btn.onclick = async () => { try { const r = await api("/api/retreat/end", {}); handleEvents(r.events); render(); } catch (e) { showError(e); } };
  if (!el || !DASH?.retreat) return;
  const tick = () => {
    const s = Math.max(0, Math.round(DASH.retreat.end - Date.now() / 1000));
    el.textContent = `还剩 ${Math.floor(s / 60)} 分 ${s % 60} 秒`;
    if (s <= 0) { clearInterval(window._rt); render(); }
  };
  tick();
  clearInterval(window._rt);
  window._rt = setInterval(() => { if (!document.body.contains(el)) return clearInterval(window._rt); tick(); }, 1000);
}
// ------------------------------------------------------------ 听课（其他平台看网课）：首页记录，计入每日学时
function lectureCard(d) {
  const m = d.minutes, goal = m.goal || 300;
  const lec7 = (d.lectures || []).reduce((a, x) => a + x.minutes, 0);
  const days = lastDays();
  const allBoards = d.tree.map((t) => t.board).concat(d.side.map((s) => s.board));
  const rows = (d.lectures || []).map((x) => `<div class="lec-row"><span class="faint">${esc(x.d.slice(5))}</span><b>${x.minutes} 分钟</b>
      <span class="muted">${esc(x.note || "")}</span><span class="spacer"></span>
      <select class="lec-board" data-lec-board="${esc(x.id)}" title="这笔听课算哪个模块${x.board ? "" : x.board_auto ? "（从“讲的什么”里认的）" : ""}">
        <option value="">不分模块</option>${allBoards.map((b) => `<option ${b === (x.board || x.board_auto) ? "selected" : ""}>${esc(b)}</option>`).join("")}</select>
      ${!x.board && x.board_auto ? '<span class="faint small">自动</span>' : ""}<button class="ghost small" data-lec-del="${esc(x.id)}" title="记错了，删掉这笔">删</button></div>`).join("");
  return `<div class="card lecture-card tone-lecture" style="margin-top:14px">
    <h3>📿 ${esc(W("lecture_title"))} <small>今日${esc(W("lecture"))} ${m.lecture ?? 0} 分钟 · 近 7 天 ${lec7} 分钟</small></h3>
    <div title="今日${esc(W("lecture"))} ${m.lecture ?? 0} 分钟（占每日目标 ${goal} 分钟）">${sancaiBar({ lecture: m.lecture ?? 0 }, goal, ["lecture"])}</div>
    <details class="fold form-fold"><summary>✍ 记一笔${esc(W("lecture"))}</summary>
    <p class="small muted">${esc(W("lecture_hint"))}</p>
    <div class="row lec-form">
      <label>${esc(W("lecture"))}几分钟 <input type="number" id="lecMin" min="1" max="600" placeholder="如 90"></label>
      <span class="lec-quick">${[30, 60, 90, 120].map((n) => `<button class="ghost small" data-lec-q="${n}">${n}</button>`).join("")}</span>
      <label>模块（可不选） <select id="lecBoard"><option value="">不分模块</option>${boardOptions(d.tree.map((t) => t.board).concat(d.side.map((s) => s.board)))}</select></label>
      <label style="flex:2">讲的什么（可不填） <input id="lecNote" maxlength="40" placeholder="如：粉笔 判断推理 第3讲"></label>
      <label>哪天 <select id="lecDay">${days.map((ds, k) => `<option value="${ds}">${dayName(ds, k)}</option>`).join("")}</select></label>
      <button class="primary" id="lecGo">📿 记入</button></div></details>
    <details class="fold" style="margin-top:8px"><summary>近 7 天${esc(W("lecture"))}记录 <span class="muted small">· ${(d.lectures || []).length} 次 · ${lec7} 分钟</span></summary>${rows || `<div class="muted small">近 7 天还没有${esc(W("lecture"))}记录</div>`}</details>
  </div>`;
}
// ------------------------------------------------------------ 学时分类：听课 / 做题 / 复习，以听课为 1 看比例
let TIME_SPAN = (() => { try { return localStorage.getItem("timeSpan") || "today"; } catch { return "today"; } })();
function hm(m) { m = Math.round(m || 0); return m >= 60 ? `<b>${Math.floor(m / 60)}</b><i>时</i>${m % 60 ? `<b>${m % 60}</b><i>分</i>` : ""}` : `<b>${m}</b><i>分</i>`; }
function timeCard(d) {
  const ts = d.timesplit; if (!ts) return "";
  const t = ts[TIME_SPAN] || ts.today;
  const total = t.lecture + t.practice + t.review;
  const orbs = [
    ["lecture", "听", "听课", "听课", `网课、讲座（${W("lecture")}）`],
    ["practice", "办", "做题", "办理", `试炼、${W("kill")}、实操、加班补课${t.self ? ` · 自练 ${t.self} 分` : " · 含自练"}`],
    ["review", "复", "复习", "复核", `传授、汇报要点、向领导汇报、复核${t.self_review ? ` · ${W("selfstudy")} ${t.self_review} 分` : ` · 含${W("selfstudy")}`}`],
  ].map(([k, seal, name, alias, hint]) => {
    const share = total ? t[k] / total : 0;
    return `<div class="orb orb-${k}" style="--share:${(share * 360).toFixed(1)}deg">
      <div class="orb-ring"><div class="orb-core">
        <div class="orb-seal">${seal}</div>
        <div class="orb-name">${name}<small>${alias}</small></div>
        <div class="orb-num">${hm(t[k])}</div>
        <div class="orb-pct">${total ? Math.round(share * 100) + "%" : "—"}</div>
      </div></div>
      <div class="orb-hint">${esc(hint)}</div></div>`;
  }).join("");
  const base = t.lecture;
  const ratio = (v) => base ? (v / base).toFixed(v / base >= 10 ? 0 : 1).replace(/\.0$/, "") : "—";
  const seg = (k, v) => total ? `<span class="seg seg-${k}" style="flex:${v || 0}" title="${v} 分钟"></span>` : "";
  const ratioLine = base
    ? `听课 <b>1</b> <em>:</em> 做题 <b>${ratio(t.practice)}</b> <em>:</em> 复习 <b>${ratio(t.review)}</b>`
    : `<span class="muted">${total ? "这段时间还没听课，比例以听课为 1，暂时算不出来" : "这段时间还没有记录"}</span>`;
  // 刻度：每一格是一份“听课时长”
  const units = base && total ? Math.min(40, Math.round(total / base)) : 0;
  const ticks = units > 1 ? Array.from({ length: units - 1 }, (_, i) => `<span style="left:${((i + 1) * base / total * 100).toFixed(2)}%"></span>`).join("") : "";
  return `<div class="card sancai" style="margin-top:14px">
    <div class="sancai-head"><h3>⏱ 学时分类 <small>听课 · 做题 · 复习</small></h3><span class="spacer"></span>
      <button class="ghost small ps-open" id="psOpen" title="把这段时间的办理成果画成一张海报，可以存图、分享">🖼 战报</button>
      <div class="sancai-tabs">${[["today", "今日"], ["week", "近七日"], ["all", "累计"]].map(([k, n]) => `<a data-tspan="${k}" class="${k === TIME_SPAN ? "on" : ""}">${n}</a>`).join("")}</div></div>
    <div class="orbs">${orbs}</div>
    <div class="ratio">
      <div class="ratio-line">${ratioLine}<span class="spacer"></span><span class="faint small">共 ${Math.round(total)} 分钟 · 以听课为 1</span></div>
      <div class="ratio-bar">${seg("lecture", t.lecture)}${seg("practice", t.practice)}${seg("review", t.review)}<div class="ticks">${ticks}</div></div>
    </div></div>`;
}
function bindTimeCard() {
  const ps = $("#psOpen"); if (ps) ps.onclick = () => POSTER.open(TIME_SPAN === "week" ? "week" : "day");
  document.querySelectorAll("[data-tspan]").forEach((a) => (a.onclick = () => {
    TIME_SPAN = a.dataset.tspan;
    try { localStorage.setItem("timeSpan", TIME_SPAN); } catch {}
    const el = document.querySelector(".sancai");
    if (el) { el.outerHTML = timeCard(DASH); bindTimeCard(); }
  }));
}
// ------------------------------------------------------------ 十二经：各模块的时辰（同三类学时法印，一排四枚，每个模块一种颜色）
const BOARD_COLORS = ["#c2463a", "#d9822b", "#c9a227", "#6e9f3a", "#2e9d6b", "#b03a5b", "#3f9e8f", "#2f7fb8", "#5b5fc7", "#8a4fbf", "#b85fa6", "#8c6d46"];
let BOARD_SPAN = (() => { try { return localStorage.getItem("boardSpan") || "week"; } catch { return "week"; } })();
function boardTimeCard(d) {
  const bt = d.boardtime; if (!bt) return "";
  const cur = bt[BOARD_SPAN] || bt.week, list = cur.boards;
  const total = list.reduce((a, b) => a + b.total, 0);
  const top = Math.max(1, ...list.map((b) => b.total));
  const orbs = list.map((b, i) => {
    const share = total ? b.total / total : 0;
    return `<div class="orb mini" style="--c:${BOARD_COLORS[i % BOARD_COLORS.length]};--share:${(share * 360).toFixed(1)}deg">
      <div class="orb-ring"><div class="orb-core">
        <div class="orb-seal">${esc(b.board.slice(0, 1))}</div>
        <div class="orb-name">${esc(b.board)}</div>
        <div class="orb-num">${hm(b.total)}</div>
        <div class="orb-pct">${total ? Math.round(share * 100) + "%" : "—"}${b.total === top && total ? " · 最勤" : ""}</div>
      </div></div>
      <div class="orb-split"><span class="l" title="听课">听 ${b.lecture}</span><span class="p" title="做题（含自练）">题 ${b.practice}</span><span class="r" title="复习">复 ${b.review}</span></div></div>`;
  }).join("");
  return `<div class="card sancai shier" style="margin-top:14px">
    <div class="sancai-head"><h3>⏱ 各题型学时 <small>听课（记听课时选了模块的）· 做题（含自练）· 复习，单位分钟</small></h3><span class="spacer"></span>
      <div class="sancai-tabs">${[["today", "今日"], ["week", "近七日"], ["all", "累计"]].map(([k, n]) => `<a data-bspan="${k}" class="${k === BOARD_SPAN ? "on" : ""}">${n}</a>`).join("")}</div></div>
    <div class="orbs orbs4">${orbs}</div>
    <p class="small muted" style="margin:6px 0 0">共 ${Math.round(total)} 分钟${cur.loose ? `，另有 ${cur.loose} 分钟认不出模块（学时分类里照算）` : ""}。办理时间按当时在练的模块记；早先没记模块的，按那天办理记录里各模块练了几次分摊。听课没选模块的，从“讲的什么”里认（写了“图形推理”“图推”“资料”等），认错了在近 7 天听课记录里改。</p></div>`;
}
function bindBoardTime() {
  document.querySelectorAll("[data-bspan]").forEach((a) => (a.onclick = () => {
    BOARD_SPAN = a.dataset.bspan;
    try { localStorage.setItem("boardSpan", BOARD_SPAN); } catch {}
    const el = document.querySelector(".shier");
    if (el) { el.outerHTML = boardTimeCard(DASH); bindBoardTime(); }
  }));
}
// ------------------------------------------------------------ 自练 · 练习记：首页记自己做题（好题收进题库在政绩录）
function lastDays() {
  return [0, 1, 2, 3, 4, 5, 6].map((k) => { const t = new Date(Date.now() - k * 864e5); return t.getFullYear() + "-" + String(t.getMonth() + 1).padStart(2, "0") + "-" + String(t.getDate()).padStart(2, "0"); });
}
function dayName(ds, k) { return k === 0 ? "今天" : k === 1 ? "昨天" : k === 2 ? "前天" : ds.slice(5); }
// 学时分类的颜色条：做题（朱）· 复习（金）· 听课（青），按每日目标算宽度；only 只画其中几段
function sancaiBar(t, goal, only) {
  const keys = only || ["practice", "review", "lecture"];
  let used = 0;
  return `<div class="tri-bar">${keys.map((k) => {
    const w = Math.max(0, Math.min(100 - used, (t[k] || 0) / goal * 100)); used += w;
    return w ? `<span class="seg-${k}" style="width:${w}%"></span>` : "";
  }).join("")}</div>`;
}
function practiceCard(d) {
  const boards = d.tree.map((t) => t.board).concat(d.side.map((s) => s.board));
  const goal = d.minutes.goal || 300, t = d.timesplit?.today || { practice: 0, self: 0 };
  const list = d.practice || [];
  const today = list.filter((p) => p.d === d.today);
  const sum = (xs, k) => xs.reduce((a, p) => a + (p[k] || 0), 0);
  const rate = (ok, n) => n ? Math.round(ok / n * 100) + "%" : "—";
  const n = sum(today, "total"), ok = sum(today, "correct");
  const wn = sum(list, "total"), wok = sum(list, "correct"), wmin = sum(list, "minutes");
  const days = lastDays();
  const rows = list.map((x) => {
    const r = x.total ? x.correct / x.total : null;
    const pace = x.total && x.minutes ? `${(x.minutes * 60 / x.total).toFixed(0)} 秒/题` : "";
    return `<div class="lec-row pr-row"><span class="faint">${esc(x.d.slice(5))}</span><b>${esc(x.board)}</b>
      ${x.total ? `<span>${x.correct}/${x.total} 题</span><span class="pr-rate ${r >= 0.8 ? "good" : r < 0.6 ? "bad" : ""}">正确率 ${rate(x.correct, x.total)}</span>` : `<span class="muted">只记心得</span>`}
      ${x.minutes ? `<span>${x.minutes} 分钟</span>` : ""}${pace ? `<span class="muted">${pace}</span>` : ""}
      ${x.source ? `<span class="muted">· ${esc(x.source)}</span>` : ""}<span class="spacer"></span>${x.id ? `<button class="ghost small" data-pr-del="${esc(x.id)}" title="记错了，删掉这笔">删</button>` : ""}</div>
      ${x.note ? `<div class="pr-note">${esc(x.note)}</div>` : ""}`;
  }).join("");
  return `<div class="card lecture-card tone-practice" style="margin-top:14px">
    <h3>⚔ ${esc(W("practice_title"))} <small>今日做题 ${t.practice} 分钟 · 其中自练 ${t.self} 分钟${n ? ` · ${ok}/${n} 题 · 正确率 ${rate(ok, n)}` : ""}</small></h3>
    ${sancaiBar({ practice: t.self, drill: t.practice - t.self }, goal, ["practice", "drill"])}
    <details class="fold form-fold"><summary>✍ 记一笔${esc(W("practice"))}</summary>
    <p class="small muted">纸质资料、其他 App 上自己刷题，也是自练。练完来此记一笔：分钟算进「做题」，心得写进 训练/自练录/${esc((d.today || "").slice(0, 7))}.md。</p>
    <div class="row lec-form">
      <label>题型 <select id="prBoard">${boardOptions(boards)}<option>其他</option></select></label>
      <label>题数 <input type="number" id="prTotal" min="0" placeholder="如 20"></label>
      <label>对了几题 <input type="number" id="prOk" min="0" placeholder="如 16"></label>
      <label>几分钟 <input type="number" id="prMin" min="0" placeholder="如 40"></label>
      <label style="flex:1">资料（可不填） <input id="prSrc" maxlength="60" placeholder="如：粉笔980 P120"></label>
      <label style="flex:2">心得（可不填） <input id="prNote" maxlength="500" placeholder="错在哪、悟到了什么；只写心得题数留空"></label>
      <label>哪天 <select id="prDay">${days.map((ds, k) => `<option value="${ds}">${dayName(ds, k)}</option>`).join("")}</select></label>
      <button class="primary" id="prBtn">⚔ 记入</button></div></details>
    <details class="fold" style="margin-top:8px"><summary>近 7 天${esc(W("practice"))}记录 <span class="muted small">· ${list.length} 次 · ${wn} 题 · 正确率 ${rate(wok, wn)} · ${wmin} 分钟</span></summary>${rows || `<div class="muted small">近 7 天还没有${esc(W("practice"))}记录：记一笔就会出现在这里</div>`}</details>
  </div>`;
}
// ------------------------------------------------------------ 静修 · 复核记：首页记自己复习（背要点、看笔记、整理错题本……）
function selfstudyCard(d) {
  const boards = d.tree.map((t) => t.board).concat(d.side.map((s) => s.board));
  const goal = d.minutes.goal || 300, t = d.timesplit?.today || { review: 0, self_review: 0 };
  const list = d.selfstudy || [];
  const w7 = list.reduce((a, x) => a + x.minutes, 0);
  const days = lastDays();
  const rows = list.map((x) => `<div class="lec-row pr-row"><span class="faint">${esc(x.d.slice(5))}</span><b>${x.minutes} 分钟</b>
      ${x.board ? `<span class="tag">${esc(x.board)}</span>` : ""}<span>${esc(x.topic || "")}</span><span class="spacer"></span>
      <button class="ghost small" data-ss-del="${esc(x.id)}" title="记错了，删掉这笔">删</button></div>
      ${x.note ? `<div class="pr-note">${esc(x.note)}</div>` : ""}`).join("");
  return `<div class="card lecture-card tone-review" style="margin-top:14px">
    <h3>🪷 ${esc(W("selfstudy_title"))} <small>今日${esc(W("selfstudy"))} ${t.self_review || 0} 分钟 · 今日复习共 ${t.review} 分钟 · 近 7 天${esc(W("selfstudy"))} ${w7} 分钟</small></h3>
    ${sancaiBar({ review: t.self_review || 0, rdrill: Math.max(0, t.review - (t.self_review || 0)) }, goal, ["review", "rdrill"])}
    <details class="fold form-fold"><summary>✍ 记一笔${esc(W("selfstudy"))}</summary>
    <p class="small muted">不在程序里、自己闭门复习（背要点、看笔记、整理错题本、回看网课笔记……）也是复核。复习完来此记一笔：分钟算进「复习」，写进 训练/静修录/${esc((d.today || "").slice(0, 7))}.md。</p>
    <div class="row lec-form">
      <label>${esc(W("selfstudy"))}几分钟 <input type="number" id="ssMin" min="1" max="600" placeholder="如 60"></label>
      <span class="lec-quick">${[30, 60, 90].map((n) => `<button class="ghost small" data-ss-q="${n}">${n}</button>`).join("")}</span>
      <label>模块（可不选） <select id="ssBoard"><option value="">不分模块</option>${boardOptions(boards)}</select></label>
      <label style="flex:1.2">复习了什么（可不填） <input id="ssTopic" maxlength="60" placeholder="如：削弱题要点、错题本"></label>
      <label style="flex:1.6">心得（可不填） <input id="ssNote" maxlength="500" placeholder="哪里还不熟、下次怎么练"></label>
      <label>哪天 <select id="ssDay">${days.map((ds, k) => `<option value="${ds}">${dayName(ds, k)}</option>`).join("")}</select></label>
      <button class="primary" id="ssBtn">🪷 记入</button></div></details>
    <details class="fold" style="margin-top:8px"><summary>近 7 天${esc(W("selfstudy"))}记录 <span class="muted small">· ${list.length} 次 · ${w7} 分钟</span></summary>${rows || `<div class="muted small">近 7 天还没有${esc(W("selfstudy"))}记录：记一笔就会出现在这里</div>`}</details>
  </div>`;
}
function bindSelfstudy() {
  const b = $("#ssBtn"); if (!b) return;
  document.querySelectorAll("[data-ss-q]").forEach((x) => (x.onclick = () => { $("#ssMin").value = x.dataset.ssQ; }));
  b.onclick = async () => {
    const minutes = Number($("#ssMin").value);
    if (!minutes) return toast(`先填${W("selfstudy")}了几分钟`);
    try {
      const s0 = SETTLE.snap(), day = $("#ssDay");
      const body = { minutes, board: $("#ssBoard").value, topic: $("#ssTopic").value.trim(), note: $("#ssNote").value.trim(), date: day.value };
      const r = await api("/api/selfstudy", body);
      handleEvents(r.events); await refresh(); render();
      SETTLE.show({ kind: "review", title: `${W("selfstudy")} ${minutes} 分钟`, sub: body.topic, before: s0,
        lines: [body.board, day.selectedIndex ? `补记 ${day.options[day.selectedIndex].text}` : ""].filter(Boolean) });
    } catch (e) { showError(e); }
  };
  document.querySelectorAll("[data-ss-del]").forEach((x) => (x.onclick = async () => {
    if (!confirm("删掉这笔记录？（那次的分钟和政绩会扣回；静修录文件里的那段请在 Obsidian 里自己删）")) return;
    try { await api("/api/selfstudy/delete", { id: x.dataset.ssDel }); await refresh(); render(); } catch (e) { showError(e); }
  }));
}
function bindPractice() {
  const b = $("#prBtn"); if (!b) return;
  b.onclick = async () => {
    try {
      const s0 = SETTLE.snap();
      const body = { board: $("#prBoard").value, source: $("#prSrc").value, total: $("#prTotal").value, correct: $("#prOk").value,
                     minutes: $("#prMin").value, note: $("#prNote").value, date: $("#prDay").value };
      const r = await api("/api/practice", body);
      handleEvents(r.events); await refresh(); render();
      const n = Number(body.total) || 0, ok = Number(body.correct) || 0, m = Number(body.minutes) || 0;
      SETTLE.show({ kind: "practice", title: `${body.board} · 自练`, sub: body.source, before: s0,
        lines: [n ? `${ok}/${n} 题` : "", n ? `正确率 ${Math.round(ok / n * 100)}%` : "", m ? `${m} 分钟` : "", n && m ? `${Math.round(m * 60 / n)} 秒/题` : ""].filter(Boolean) });
    } catch (e) { showError(e); }
  };
  document.querySelectorAll("[data-pr-del]").forEach((x) => (x.onclick = async () => {
    if (!confirm("删掉这笔记录？（那次的分钟和政绩会扣回；日志文件里的那段请在 Obsidian 里自己删）")) return;
    try { await api("/api/practice/delete", { id: x.dataset.prDel }); await refresh(); render(); } catch (e) { showError(e); }
  }));
}
function bindLecture() {
  const go = $("#lecGo"); if (!go) return;
  document.querySelectorAll("[data-lec-q]").forEach((b) => (b.onclick = () => { $("#lecMin").value = b.dataset.lecQ; }));
  go.onclick = async () => {
    const minutes = Number($("#lecMin").value);
    if (!minutes) return toast(`先填${W("lecture")}了几分钟`);
    try {
      const s0 = SETTLE.snap(), note = $("#lecNote").value.trim(), day = $("#lecDay");
      const lb = $("#lecBoard").value;
      const r = await api("/api/lecture", { minutes, note, date: day.value, board: lb });
      handleEvents(r.events); await refresh(); render();
      SETTLE.show({ kind: "lecture", title: `${W("lecture")} ${minutes} 分钟`, sub: note, before: s0,
        lines: [lb, day.selectedIndex ? `补记 ${day.options[day.selectedIndex].text}` : ""].filter(Boolean) });
    } catch (e) { showError(e); }
  };
  document.querySelectorAll("[data-lec-board]").forEach((sel) => (sel.onchange = async () => {
    try { await api("/api/lecture/board", { id: sel.dataset.lecBoard, board: sel.value }); toast(sel.value ? `已算进「${sel.value}」` : "已改成不分模块"); await refresh(); render(); }
    catch (e) { showError(e); }
  }));
  document.querySelectorAll("[data-lec-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm("删掉这笔记录？（那次得到的政绩也会扣回）")) return;
    try { await api("/api/lecture/delete", { id: b.dataset.lecDel }); await refresh(); render(); } catch (e) { showError(e); }
  }));
}
function bindHome() {
  bindLecture();
  bindPractice();
  bindSelfstudy();
  bindTimeCard();
  bindBoardTime();
  const ph = $("#psHero"); if (ph) ph.onclick = () => POSTER.open("day");
  bindBreak();
  const tb = $("#tribBtn"); if (tb) tb.onclick = () => startTask({ task: { type: "tribulation", board: "", target: String(DASH.trib.gate), title: `⚡ ${W("tribulation")} · ${DASH.trib.realm}` } });
  bindRetreatTimer();
  if (DASH?.greet_pending) {
    DASH.greet_pending = false;
    api("/api/tutor/greet", {}).then((r) => {
      if (r.text) { DASH.greeting = r.text; const el = $("#greet"); if (el) el.innerHTML = md(r.text); }
      else { const t = $("#greet .thinking"); if (t) t.remove(); }
    }).catch(() => { const t = $("#greet .thinking"); if (t) t.remove(); });
  }
}

async function startTask(body) {
  SESSION_SNAP = window.SETTLE ? SETTLE.snap() : null;
  Object.assign(T, { session: null, title: "准备中…", msgs: [], input: { mode: "none" }, busy: true, finished: false, battle: null });
  go("train");
  try { applyResp(await api("/api/session/start", body)); }
  catch (e) { T.busy = false; T.msgs.push({ who: "sys", text: "⚠ " + e.message }); T.finished = true; }
  renderTrain();
}
let ASK_OPEN = false;     // 复盘时“主任求助”打字框开着没有（换题就收起，追问中保持打开）
function applyResp(r) {
  T.session = r.session; T.title = r.title; T.busy = false; T_TYPE = r.type;
  if (r.replace && r.scroll !== 'bottom') ASK_OPEN = false;
  // 试炼答题 / 复盘：每一屏只显示当前这道题（不在聊天里越堆越长），从顶上看起
  if (r.replace) T.msgs = [];
  T.top = !!r.replace && r.scroll !== 'bottom';
  T.msgs.push(...r.messages);
  handleEvents(r.events, { inChat: true });
  T.input = r.input || { mode: "none" };
  T.finished = r.finished;
  T.battle = r.battle || null;
  if (r.finished) {
    const kind = window.SETTLE && SETTLE.kindOf(r.type || T_TYPE), before = SESSION_SNAP, title = r.title || T.title, battle = r.battle;
    SESSION_SNAP = null;
    refresh().then(() => {
      if (VIEW === "train") renderTrain();
      if (kind && before) SETTLE.show({ kind, title, before,
        lines: battle && battle.correct != null && battle.total ? [`破关 ${battle.correct}/${battle.total}`, `正确率 ${Math.round(battle.correct / battle.total * 100)}%`] : [] });
    });
  }
}
// 做功课时对话框钉在屏幕上：底边贴着屏幕底，宽高在“设置 → 对话框大小”里调（存在本机浏览器）
const CHAT_DEF = { w: 80, h: 100, side: true, fs: 110 };   // fs：对话框里的字号（%）
function chatPrefs() {
  try { return Object.assign({}, CHAT_DEF, JSON.parse(localStorage.getItem("chatLayout") || "{}")); } catch { return { ...CHAT_DEF }; }
}
function applyChatLayout(p = chatPrefs()) {
  const root = document.documentElement;
  const hdr = document.querySelector("header");
  const ban = $("#banner");
  const top = root.classList.contains("focus") ? 52      // ◎ 专注：顶栏藏起来了，只给顶上的小胶囊留位置
    : Math.max(hdr ? hdr.getBoundingClientRect().bottom : 60, ban && ban.offsetHeight ? ban.getBoundingClientRect().bottom : 0) + 8;
  const avail = Math.max(240, innerHeight - top);
  root.style.setProperty("--chat-w", Math.max(40, Math.min(100, p.w)) + "vw");
  root.style.setProperty("--chat-top", Math.round(innerHeight - avail * Math.max(40, Math.min(100, p.h)) / 100) + "px");
  root.classList.toggle("chat-noside", !p.side);
  root.style.setProperty("--chat-fs", String(Math.max(80, Math.min(160, p.fs || 100)) / 100));
}
function fitChat() {
  const tr = $(".train");
  document.documentElement.classList.toggle("in-chat", !!tr);
  if (!tr) return;
  window.scrollTo(0, 0);
  applyChatLayout();
}
window.addEventListener("resize", () => { if ($(".train")) fitChat(); });
async function renderTrain() {
  if (VIEW !== "train") return;
  const html = await views.train().catch((e) => { showError(e); return ''; });
  if (VIEW !== "train") return;
  $("#view").innerHTML = html;
  bindTrain();
  fitChat();
  const box = $("#msgs"); if (box) box.scrollTop = T.top ? 0 : box.scrollHeight;
  startTimer();
  const ta = $("#answer"); if (ta) ta.focus();
}
function bindTrain() {
  fitChat();
  if (!T.session && !T.msgs.length && !T.busy) return bindHub();
  bindTaskClicks($("#view"));
  bindPins();
  const at = $("#askToggle");
  if (at) at.onclick = () => { ASK_OPEN = !ASK_OPEN; renderTrain(); if (ASK_OPEN) { const a = $("#answer"); if (a) a.focus(); } };
  const send = $("#send");
  if (send) {
    send.onclick = submitText;
    $("#answer").onkeydown = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submitText(); };
  }
  document.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => doAction(b.dataset.act)));
  const nx = $("#nextTask");
  if (nx) nx.onclick = () => {
    const t = (DASH?.plan?.tasks || []).find((x) => !x.done);
    t ? startTask({ task_id: t.id }) : (toast(`${W("tasks")}全部完成 ✦`), go("home"));
  };
  const th = $("#toHall");
  if (th) th.onclick = () => {
    if (T.session && !T.finished && !confirm("这项功课还没结束，先回办理殿吗？（试炼的进度会保存，其他功课需要重新开始）")) return;
    Object.assign(T, { session: null, msgs: [], battle: null }); clearInterval(TIMER); renderTrain();
  };
  const bh = $("#backHome"); if (bh) bh.onclick = () => { Object.assign(T, { session: null, msgs: [], battle: null }); renderTrain(); };
  const bc = $("#backContest"); if (bc) bc.onclick = () => { Object.assign(T, { session: null, msgs: [], battle: null }); go("contest"); };
}
async function submitText() {
  const text = $("#answer").value.trim();
  if (!text) return;
  T.msgs.push({ who: "me", text }); T.busy = true; renderTrain();
  try { applyResp(await api("/api/session/reply", { session: T.session, text })); }
  catch (e) { T.busy = false; T.msgs.push({ who: "sys", text: "⚠ " + e.message }); }
  renderTrain();
}
async function doAction(act) {
  T.busy = true; renderTrain();
  try { applyResp(await api("/api/session/action", { session: T.session, action: act })); }
  catch (e) { T.busy = false; T.msgs.push({ who: "sys", text: "⚠ " + e.message }); }
  renderTrain();
}
// ------------------------------------------------------------ 办理殿：两扇门（办理 / 实操），没在做功课时显示
let HALL = 'xiulian';            // xiulian 办理（便笺、脉络图、业务手册）| shizhan 实操（申论作答与采分点批改，见 web/shenlun.js）
let XL_BOARD = '';               // 办理殿里选中的题型
async function hubHtml() {
  const gates = `<div class="hall-gates">
    <div class="gate ${HALL === 'xiulian' ? 'on' : ''}" data-hall="xiulian"><div class="gate-cloud"></div><div class="gate-icon">📝</div>
      <div class="gate-name">办 理</div><div class="gate-sub">${esc(W('yj'))}复习 · 脉络图</div><div class="gate-stat">${esc(W('yj_review'))} · ${esc(W('yj_rule'))} · 脉络图</div></div>
    <div class="gate ${HALL === 'shizhan' ? 'on' : ''}" data-hall="shizhan"><div class="gate-cloud"></div><div class="gate-icon">✍</div>
      <div class="gate-name">实 操</div><div class="gate-sub">作答 · 采分点批改</div><div class="gate-stat">${window.SHENLUN ? esc(SHENLUN.hallStat()) : '作答批改'}</div></div></div>`;
  const body = HALL === 'shizhan' && window.SHENLUN ? await SHENLUN.hallHtml() : await xiulianHtml();
  return gates + `<div class="hall-body">${body}</div>`;
}

// 办理：上面是便笺（照 Anki 的记忆卡片，web/cards.js），下面整改销号（模考错题）
async function xiulianHtml() {
  const [yj, ln] = await Promise.all([window.CARDS ? CARDS.hubHtml() : '', window.MINDMAP ? MINDMAP.hubHtml() : '']);
  return yj + ln;
}

function bindHub() {
  document.querySelectorAll('[data-hall]').forEach(g => g.onclick = () => { HALL = g.dataset.hall; renderTrain(); });
  document.querySelectorAll('[data-xlboard]').forEach(a => a.onclick = () => { XL_BOARD = a.dataset.xlboard; renderTrain(); });
  document.querySelectorAll('[data-xlwrong]').forEach(b => b.onclick = () =>
    startTask({ task: { type: 'wrong', board: b.dataset.xlwrong, target: '', title: `📌 ${W('kill')} · ${b.dataset.xlwrong}` } }));
  document.querySelectorAll('[data-xlpill]').forEach(b => b.onclick = () =>
    startTask({ task: { type: 'alchemy', board: b.dataset.xlpill, target: b.dataset.xlpill, title: `⏱ ${W('alchemy')} · ${b.dataset.xlpill}` } }));
  bindTaskClicks($('#view'));
  if (window.CARDS) CARDS.bindHub($('#view'));
  if (window.MINDMAP) MINDMAP.bindHub($('#view'));
  bindSkeleton();   // 大项练习按钮、编撰业务手册
  if (HALL === 'shizhan' && window.SHENLUN) SHENLUN.bindHall($('#view'));
}
// 竖排题签：一个字一行（不用 writing-mode，有些字体竖排会叠字）
const vlabel = (t) => [...String(t)].map(esc).join('<br>');
let LIB = { tab: 'cards' };   // 档案室当前标签：cards 便笺 | bank 题库 · 采分点 | jiaocai 教材
// 档案室 · 便笺 · 知识点：办理殿里刻的便笺，每个便笺夹一枚会浮动的便笺，点开像过便笺一样一枚枚翻看（不打分）
async function cardsLibHtml() {
  let ov;
  try { ov = await api('/api/cards'); } catch (e) { return `<div class="card muted">${esc(e.message)}</div>`; }
  const tops = ov.decks.filter((d) => d.depth === 0);
  const subs = (name) => ov.decks.filter((d) => d.depth > 0 && d.name.startsWith(name + '::') && d.total);
  return `${CARDS.toolsHtml()}<p class="small muted lib-tip">共 ${ov.cards} 枚${esc(W('yj'))}。点一枚便笺先看这一匣的目录（像${esc(W('yj_browse'))}），点哪一张就从哪一张翻起（只是看，不记温习进度）；想按记忆曲线背，到办理殿过便笺。</p>
    <div class="tome-grid">${tops.map((d, i) => `<div class="tome-slot"><div class="slip" data-deck="${esc(d.name)}" style="--d:${(i % 6) * 0.7}s">
      <div class="slip-label">${vlabel(d.label)}</div><div class="slip-count">${d.total}</div></div>
      <div class="tome-cap">${d.total ? `${d.total} 枚 · 待复习 ${d.review + d.learn} · 新 ${d.new}` : '空匣'}</div>
      ${subs(d.name).length ? `<div class="deck-subs">${subs(d.name).map((x) => `<a data-deck="${esc(x.name)}">${esc(x.label)} <span>${x.total}</span></a>`).join('')}</div>` : ''}</div>`).join('')}</div>`;
}
// 档案室 · 业务手册 · 教材：库里所有的 PDF，每本一卷古籍；点开跳到公务手账里，可以直接在上面勾画
async function jiaocaiHtml() {
  let files;
  try { files = (await api('/api/notes/pdfs')).files; } catch (e) { return `<div class="card muted">${esc(e.message)}</div>`; }
  if (!files.length) return `<div class="card"><p class="muted">库里还没有 PDF。把讲义、教材的 PDF 放进库里（比如各题型的文件夹），这里就会出现。</p></div>`;
  const hues = [28, 200, 340, 150, 260, 45, 180, 10, 300, 90, 220, 120];
  const groups = {};
  files.forEach((f) => (groups[f.dir] = groups[f.dir] || []).push(f));
  const nice = (d) => d === '训练/时政简报/原文' ? '时政简报 · 原文' : d ? d.replace(/\//g, ' › ') : '库根目录';
  let k = 0;
  return `<p class="small muted lib-tip">库里的 ${files.length} 本 PDF。每本是一卷古籍，点开会到「${esc(NAV('notes'))}」里打开，可以直接用笔勾画（自动保存，原 PDF 不改）。</p>
    ${Object.keys(groups).map((dir, g) => `<h3 class="tome-group">${esc(nice(dir))} <small>${groups[dir].length}</small></h3>
    <div class="tome-grid">${groups[dir].map((f) => { const i = k++; const short = [...f.name.replace(/^(专题时政|月半时政)-/, '').replace(/^20\d\d(年|-)?/, '') || f.name].slice(0, 6).join('');
      return `<div class="tome-slot"><div class="tome" data-pdfbook="${esc(f.path)}" title="${esc(f.path)}" style="--d:${(i % 6) * 0.8}s;--h:${hues[g % hues.length]}">
        <div class="tome-cover"><div class="tome-label ${short.length > 4 ? 'long' : ''}">${vlabel(short)}</div><div class="tome-seal">教材</div></div></div>
        <div class="tome-cap tome-name">${esc(f.name)}</div></div>`; }).join('')}</div>`).join('')}`;
}
function bindLibrary() {
  document.querySelectorAll('[data-libtab]').forEach(b => b.onclick = () => { LIB.tab = b.dataset.libtab; render(); });
  document.querySelectorAll('[data-deck]').forEach(t => t.onclick = () => CARDS.browseDeck(t.dataset.deck));
  if (LIB.tab === 'cards' && window.CARDS) CARDS.bindTools($('#view'));
  document.querySelectorAll('[data-pdfbook]').forEach(t => t.onclick = () => { NOTES.openPdfLater(t.dataset.pdfbook); go('notes'); });
  if (LIB.tab === 'bank' && window.SHENLUN) SHENLUN.bindLib($('#view'));
}
function bindSkeleton() {
  bindLibrary();
  document.querySelectorAll("[data-skel]").forEach((b) => (b.onclick = () =>
    startTask({ task: { type: "skeleton", board: b.dataset.skel, target: b.dataset.skel, title: `📜 「${b.dataset.skel}」${W("skeleton")}` } })));
  document.querySelectorAll("[data-free]").forEach((a) => (a.onclick = () =>
    startTask({ task: { type: a.dataset.train || "recite", board: a.dataset.board, target: a.dataset.free, title: `${W(a.dataset.train || "recite")} · ${a.dataset.board}「${a.dataset.name}」` } })));
}
function bindLog() {
  $("#bossBtn").onclick = async () => {
    try { const r = await api("/api/boss", { name: $("#bossName").value, score: $("#bossScore").value }); handleEvents(r.events); render(); } catch (e) { showError(e); }
  };
  bindTaskClicks($("#view"));
  $("#regen").onclick = async () => { try { await api("/api/plan/regenerate", {}); render(); } catch (e) { showError(e); } };
  $("#chatBtn").onclick = () => startTask({ task: { type: "chat", board: "", target: "", title: `💬 ${W("tutor_room")}` } });
  $("#leaveBtn").onclick = async () => { try { const r = await api("/api/leave", {}); handleEvents(r.events); render(); } catch (e) { showError(e); } };
  $("#asBtn").onclick = async () => {
    try { const r = await api("/api/boss", { kind: "上岸", name: $("#asName").value || "国考", score: $("#asScore").value, result: $("#asResult").value }); handleEvents(r.events); render(); } catch (e) { showError(e); }
  };
}
// 设置页：有输入框 / 下拉框的卡片都收成可展开的（默认收起，点标题展开）
function foldCards(root) {
  root.querySelectorAll(":scope > .card, :scope > div > .card").forEach((c) => {
    const h = c.firstElementChild;
    if (!h || h.tagName !== "H3" || !c.querySelector("input, select, textarea") || c.closest("details")) return;
    const d = document.createElement("details");
    d.className = c.className + " card-fold";
    if (c.id) d.id = c.id;
    const s = document.createElement("summary");
    s.innerHTML = h.innerHTML;
    d.appendChild(s);
    h.remove();
    while (c.firstChild) d.appendChild(c.firstChild);
    c.replaceWith(d);
  });
}
function bindSettings() {
  foldCards($("#view"));
  DEVICE.bind();
  const saveChat = (p) => { try { localStorage.setItem("chatLayout", JSON.stringify(p)); } catch {} };
  const readChat = () => ({ w: Number($("#cwR").value), h: Number($("#chR").value), side: $("#csideR").checked, fs: Number($("#cfR").value) });
  if ($("#cwR")) {
    const upd = () => { const p = readChat(); $("#cwV").textContent = p.w + "%"; $("#chV").textContent = p.h + "%"; $("#cfV").textContent = p.fs + "%";
      $("#cfDemo span").style.fontSize = `calc(15px * ${p.fs / 100})`; saveChat(p); applyChatLayout(p); };
    $("#cwR").oninput = upd; $("#chR").oninput = upd; $("#cfR").oninput = upd; $("#csideR").onchange = upd;
    $("#cResetR").onclick = () => { $("#cwR").value = CHAT_DEF.w; $("#chR").value = CHAT_DEF.h; $("#csideR").checked = CHAT_DEF.side; $("#cfR").value = CHAT_DEF.fs; upd(); };
  }
  AMB.bindSettings(showError);
  const prof = $("#sProf");
  if (prof) prof.onchange = async () => {
    if (!prof.value) return;
    try { await api("/api/settings/ai_profile", { action: "use", name: prof.value }); toast(`🤖 已换成「${esc(prof.value)}」`); await refresh(); render(); } catch (e) { showError(e); }
  };
  const ps = $("#sProfSave");
  if (ps) ps.onclick = async () => {
    const name = prompt("给这套 AI 起个名字（如 DeepSeek、通义千问、Kimi）。会存下面填的接口地址、模型和 key：", $("#sModel").value || "");
    if (!name) return;
    try { await api("/api/settings", formBody()); await api("/api/settings/ai_profile", { action: "save", name }); toast(`💾 已存为「${esc(name)}」`); await refresh(); render(); } catch (e) { showError(e); }
  };
  const pd = $("#sProfDel");
  if (pd) pd.onclick = async () => {
    if (!prof.value || !confirm(`删掉「${prof.value}」这套？（当前用着的设置不变）`)) return;
    try { await api("/api/settings/ai_profile", { action: "delete", name: prof.value }); render(); } catch (e) { showError(e); }
  };
  const pre = $("#sPreset");
  if (pre) pre.onchange = () => {
    const p = AI_PRESETS[+pre.value];
    if (!p) return;
    $("#sBase").value = p[1]; $("#sModel").value = p[2]; $("#sKey").value = ""; $("#sKey").placeholder = `${p[0]} 的 API key`;
    toast(`已填好 ${esc(p[0])} 的接口地址${p[2] ? "和模型" : "，模型名填一下"}；再填 key，点「保存」`);
    pre.value = "";
  };
  function formBody() {
    const body = { vault: $("#sVault").value, base_url: $("#sBase").value, model: $("#sModel").value };
    if ($("#sKey").value.trim()) body.api_key = $("#sKey").value.trim();
    body.vision_model = $("#sVModel").value.trim(); body.vision_base_url = $("#sVBase").value.trim();
    if ($("#sVKey").value.trim()) body.vision_api_key = $("#sVKey").value.trim();
    return body;
  }
  $("#sSave").onclick = async () => {
    try { await api("/api/settings", formBody()); $("#sMsg").textContent = "已保存"; await refresh(); } catch (e) { showError(e); }
  };
  $("#sTest").onclick = async () => {
    $("#sMsg").textContent = "测试中…";
    try { const r = await api("/api/settings/test", {}); $("#sMsg").textContent = "✅ " + r.reply; } catch (e) { $("#sMsg").textContent = ""; showError(e); }
  };
}

// ------------------------------------------------------------ 办理计时（心跳）
// 只在“真正办理”时计时：开着一项功课（真题试炼 / 整改销号 / 晋升考核 / 加班补课……，或刚做完在看解析）、在过便笺、在公务手账里写字，
// 页面可见，并且 2 分钟内有键盘鼠标操作（或正在等 AI 判题）。只是开着网页、看面板、和导师闲聊都不计时。
// 后端也会核对会话是否真的在进行（rpg/trainer.is_studying），前端条件只是省掉无用的上报。
const BEAT = 30;
const STUDY = ["teach", "recite", "review", "speedrun", "feynman", "example", "apply", "wrong", "tribulation", "alchemy"];
let lastActive = Date.now();
let T_TYPE = "";
["mousemove", "keydown", "click", "scroll", "input"].forEach((ev) => addEventListener(ev, () => (lastActive = Date.now()), { passive: true }));
function studyingNow() {
  return VIEW === "train" && !!T.session && STUDY.includes(T_TYPE) && document.visibilityState === "visible"
    && (T.busy || Date.now() - lastActive < 120000);
}
// 在 🪶 公务手账里写字也算复习：按秒累计“1 分钟内写过字”的时间，心跳时连同本子编号一起报（服务器核对这本最近真的存过笔迹）
let noteSec = 0;
let cardSec = 0;   // 过便笺也算复习：按秒累计正在过便笺的时间（web/cards.js 的 active：在温、看得见、2 分钟内有操作）
let tjSec = 0;     // 🔮 时政简报：开着一期、2 分钟内动过（web/tianji.js 的 active）
let tjMode = "";
let slSec = 0;     // ✍ 实操：在作答页写答案（web/shenlun.js 的 active：看得见、2 分钟内敲过键盘）
setInterval(() => {
  if (window.NOTES && NOTES.writingId()) noteSec += 1;
  if (window.CARDS && CARDS.active()) cardSec += 1;
  const tj = window.TIANJI ? TIANJI.active() : "";
  if (tj) { tjSec += 1; tjMode = tj; }
  if (window.SHENLUN && SHENLUN.active()) slSec += 1;
}, 1000);
function updateStudyDot() {
  const on = studyingNow() || !!(window.NOTES && NOTES.writingId()) || !!(window.CARDS && CARDS.active()) || !!(window.TIANJI && TIANJI.active()) || !!(window.SHENLUN && SHENLUN.active());
  $("#todayPill").classList.toggle("on", on);
  $("#todayPill").title = on ? "正在计时：办理中" : "未计时：只有做功课时才算办理时间";
}
let beatCount = 0;
setInterval(async () => {
  updateStudyDot();
  const on = studyingNow();
  beatCount += 1;
  if (!on && !noteSec && !cardSec && !tjSec && !slSec && beatCount % 2) return;          // 不办理时每分钟只刷新一次状态（多设备提醒、休息、下乡调研）
  try {
    const nid = !on && window.NOTES ? NOTES.writingId() || (noteSec ? NOTES.lastId() : "") : "";
    const carding = !on && !nid && cardSec > 0;
    const tj = !on && !nid && !carding && tjSec > 0 ? tjMode : "";
    const sl = !on && !nid && !carding && !tj && slSec > 0 && window.SHENLUN ? SHENLUN.board() || "作答" : "";
    const sec = on ? BEAT : Math.min(BEAT, nid ? noteSec : carding ? cardSec : tj ? tjSec : slSec);
    noteSec = 0; cardSec = 0; tjSec = 0; slSec = 0;
    if (nid && sec) await NOTES.save();          // 先把刚写的存上，服务器才认得“最近写过”
    const r = await api("/api/heartbeat", { seconds: sec, session: on ? T.session : null, notes: nid || null,
      cards: carding || null, cards_board: carding ? CARDS.board() : null, tianji: tj || null, answering: sl || null });
    if (DASH) { DASH.minutes.today = r.minutes; DASH.other_device = r.other_device; DASH.rest = r.rest; updatePill(); banner(); }
    handleEvents(r.events);
    if (DASH?.retreat && !r.retreat_on && VIEW === "home") render();
  } catch (e) { /* 程序关了就不提示 */ }
}, BEAT * 1000);
setInterval(updateStudyDot, 5000);

render();



// 试炼进度与破关数，不显示任何未提交题目的答案。
const clock = (s) => { s = Math.max(0, Math.round(s)); return s >= 3600 ? `${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
// （试炼塔的答题计时已随真题试炼一起去掉）
let TIMER = null;
function startTimer() { clearInterval(TIMER); }
// 办理对话框顶上：标题和进度合成一行（标题后面跟小标签，底边一道细进度线），不再占一大块
function sessionHead() {
  return `<div class="review-head"><b>${esc(T.title)}</b></div>`;
}
function headRow(title, tags, ratio) {
  return `<div class="review-head"><b>${esc(title)}</b><span class="rh-stats">${tags.filter(Boolean).join("")}</span>
    <i class="rh-bar" style="width:${Math.round(100 * Math.max(0, Math.min(1, ratio)))}%"></i></div>`;
}
// 考核复盘
