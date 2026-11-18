/* 纸质自考（无数字钟表计时 + 预设分值录分）：宗门大比第 5 入口「自考」
   - 钟表默认从 9:00 起走，表盘无数字；按按钮或空格键按预设顺序记录当前板块用时并切入下一板块；
   - 录分按各板块对题数、错题数与每题分值计算得分并汇总，保存后计入宗门大比考情与战绩（无需逐题复盘）。 */
(() => {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtMMSS = (sec) => {
    const s = Math.max(0, Math.round(Number(sec) || 0));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  const fmtHMS = (sec) => {
    const s = Math.max(0, Math.floor(Number(sec) || 0));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
    return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}` : `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  };
  const round2 = (n) => Math.round((Number(n) + Number.EPSILON) * 100) / 100;

  let DATA = null;
  let STEP = "timer";        // "timer" | "score"
  let EDIT_SEASON = null;
  let START_HOUR = 9;        // 默认九点开考
  let ON_SAVED = null;       // 回调通知 contest.js 刷新 MOCK 汇总
  let TICK_ID = null;

  const TIMER = {
    presetId: "",
    phase: "idle",           // "idle" | "running" | "paused" | "done"
    idx: 0,
    splits: [],              // 各板块累计秒数
    completed: [],           // 各板块是否已打点完成
    segStart: null,          // performance.now()
    notice: "",
  };

  const DRAFT = {
    presetId: "",
    name: "",
    date: "",
    rows: [],                // {name, module, total, points, target_minutes, ok, wrong, seconds}
  };

  function activePreset(d = DATA) {
    if (!d || !Array.isArray(d.presets) || !d.presets.length) return null;
    return d.presets.find((p) => p.id === d.active_preset) || d.presets[0];
  }

  function syncWithPreset(p, forceReset = false) {
    if (!p) return;
    const secs = p.sections || [];
    if (forceReset || TIMER.presetId !== p.id || TIMER.splits.length !== secs.length) {
      TIMER.presetId = p.id;
      TIMER.phase = "idle";
      TIMER.idx = 0;
      TIMER.splits = secs.map(() => 0);
      TIMER.completed = secs.map(() => false);
      TIMER.segStart = null;
      TIMER.notice = "";
    }
    if (!EDIT_SEASON && (forceReset || DRAFT.presetId !== p.id || DRAFT.rows.length !== secs.length)) {
      DRAFT.presetId = p.id;
      if (!DRAFT.date) DRAFT.date = DATA?.today || "";
      DRAFT.rows = secs.map((s, i) => ({
        name: s.name,
        module: s.module,
        total: Number(s.total),
        points: String(s.points),
        target_minutes: Number(s.target_minutes || 0),
        ok: "",
        wrong: "",
        seconds: TIMER.splits[i] || 0,
      }));
    }
  }

  function flushRunning() {
    if (TIMER.phase === "running" && TIMER.segStart != null) {
      const delta = Math.max(0, (performance.now() - TIMER.segStart) / 1000);
      if (TIMER.idx >= 0 && TIMER.idx < TIMER.splits.length) {
        TIMER.splits[TIMER.idx] += delta;
      }
      TIMER.segStart = performance.now();
    }
  }

  function liveSplits() {
    const arr = TIMER.splits.slice();
    if (TIMER.phase === "running" && TIMER.segStart != null && TIMER.idx >= 0 && TIMER.idx < arr.length) {
      arr[TIMER.idx] += Math.max(0, (performance.now() - TIMER.segStart) / 1000);
    }
    return arr;
  }

  function syncSplitsToDraft() {
    flushRunning();
    TIMER.splits.forEach((sec, i) => {
      if (DRAFT.rows[i] && (sec > 0 || TIMER.completed[i])) {
        DRAFT.rows[i].seconds = Math.max(TIMER.completed[i] ? 1 : 0, Math.round(sec));
      }
    });
  }

  function clockAngles(elapsedSec) {
    const clockSec = START_HOUR * 3600 + Math.max(0, elapsedSec);
    return {
      hour: ((clockSec % 43200) / 43200) * 360,
      min: ((clockSec % 3600) / 3600) * 360,
      sec: ((clockSec % 60) / 60) * 360,
    };
  }

  function clockSvg(elapsedSec) {
    const ticks = [];
    for (let k = 0; k < 60; k++) {
      const rad = ((k * 6 - 90) * Math.PI) / 180;
      const rOut = 106;
      const rIn = k % 15 === 0 ? 90 : k % 5 === 0 ? 96 : 101;
      const cls = k % 15 === 0 ? "pe-tick-cardinal" : k % 5 === 0 ? "pe-tick-hr" : "pe-tick-min";
      const x1 = (120 + rIn * Math.cos(rad)).toFixed(2), y1 = (120 + rIn * Math.sin(rad)).toFixed(2);
      const x2 = (120 + rOut * Math.cos(rad)).toFixed(2), y2 = (120 + rOut * Math.sin(rad)).toFixed(2);
      ticks.push(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="${cls}"/>`);
    }
    const ang = clockAngles(elapsedSec);
    return `<svg class="pe-clock" viewBox="0 0 240 240" role="img" aria-label="纸质模考无数字钟表">
      <circle cx="120" cy="120" r="112" class="pe-clock-face"/>
      <circle cx="120" cy="120" r="84" class="pe-clock-inner"/>
      <g class="pe-clock-ticks">${ticks.join("")}</g>
      <g id="peHandHour" data-angle="${ang.hour.toFixed(2)}" transform="rotate(${ang.hour.toFixed(2)} 120 120)"><line x1="120" y1="130" x2="120" y2="62" class="pe-hand-hour"/></g>
      <g id="peHandMin" data-angle="${ang.min.toFixed(2)}" transform="rotate(${ang.min.toFixed(2)} 120 120)"><line x1="120" y1="134" x2="120" y2="38" class="pe-hand-min"/></g>
      <g id="peHandSec" data-angle="${ang.sec.toFixed(2)}" transform="rotate(${ang.sec.toFixed(2)} 120 120)"><line x1="120" y1="138" x2="120" y2="32" class="pe-hand-sec"/></g>
      <circle cx="120" cy="120" r="5" class="pe-clock-pin"/>
    </svg>`;
  }

  function calcSummary(rows) {
    let okAll = 0, wrongAll = 0, totalAll = 0, rawScore10000 = 0, fullScore10000 = 0, totalSec = 0;
    const errors = [];
    const secScores = rows.map((r) => {
      const total = Math.max(0, parseInt(r.total, 10) || 0);
      const pts10000 = Math.round(( parseFloat(r.points) || 0 ) * 10000);
      const ok = r.ok === "" || r.ok == null ? 0 : Math.max(0, parseInt(r.ok, 10) || 0);
      const wrong = r.wrong === "" || r.wrong == null ? 0 : Math.max(0, parseInt(r.wrong, 10) || 0);
      const sec = Math.max(0, Number(r.seconds) || 0);
      if (ok + wrong > total) errors.push(`「${r.name}」对题(${ok})+错题(${wrong})超出总题数(${total})`);
      okAll += ok;
      wrongAll += wrong;
      totalAll += total;
      totalSec += sec;
      rawScore10000 += ok * pts10000;
      fullScore10000 += total * pts10000;
      return {
        score: round2((ok * pts10000) / 10000),
        full: round2((total * pts10000) / 10000),
        invalid: ok + wrong > total,
      };
    });
    const rawScore = round2(rawScore10000 / 10000);
    const fullScore = round2(fullScore10000 / 10000);
    const normScore = fullScore > 100 ? round2((rawScore10000 * 100) / fullScore10000) : rawScore;
    return {
      okAll,
      wrongAll,
      blankAll: Math.max(0, totalAll - okAll - wrongAll),
      totalAll,
      totalSec,
      rawScore,
      fullScore,
      normScore,
      secScores,
      errors,
    };
  }

  function presetSelectHtml(d) {
    return (d.presets || []).map((p) => `<option value="${esc(p.id)}" ${p.id === d.active_preset ? "selected" : ""}>${esc(p.name)}${p.overridden ? "（已微调）" : ""}</option>`).join("");
  }

  function presetEditorHtml(d, p) {
    if (!p) return "";
    const modOpts = (cur) => (d.module_names || []).map((m) => `<option value="${esc(m)}" ${m === cur ? "selected" : ""}>${esc(m)}</option>`).join("");
    const rows = (p.sections || []).map((s, i) => `<div class="pe-cfg-row" data-pe-cfg-row="${i}">
      <input type="text" data-cfg-k="name" value="${esc(s.name)}" maxlength="24" placeholder="板块名称" aria-label="板块名称">
      <select data-cfg-k="module" aria-label="所属模块">${modOpts(s.module)}</select>
      <input type="number" data-cfg-k="total" min="1" max="200" value="${s.total}" placeholder="题量" title="题量">
      <input type="number" data-cfg-k="points" min="0.01" max="20" step="0.05" value="${esc(s.points)}" placeholder="每题分" title="每题分值">
      <input type="number" data-cfg-k="target_minutes" min="0" max="180" value="${s.target_minutes ?? 10}" placeholder="目标分" title="参考用时(分钟)">
      <span class="pe-cfg-actions">
        <button type="button" class="ghost small" data-cfg-act="up" title="上移" ${i === 0 ? "disabled" : ""}>↑</button>
        <button type="button" class="ghost small" data-cfg-act="down" title="下移" ${i === p.sections.length - 1 ? "disabled" : ""}>↓</button>
        <button type="button" class="ghost small" data-cfg-act="del" title="移除板块" ${p.sections.length <= 1 ? "disabled" : ""}>×</button>
      </span>
    </div>`).join("");
    return `<details class="fold" id="pePresetFold" style="margin-bottom:12px">
      <summary>⚙ 预设做题顺序 · 题量与小题分值（当前共 ${p.total_questions} 题 · 满分 ${p.full_score} 分）</summary>
      <p class="small muted" style="margin:6px 0">表头依次为：板块名、归属六大模块、题量、每题分值、目标分钟。调好后可覆盖当前预设，或另存为新省考/自用方案。</p>
      <div id="peCfgList">${rows}</div>
      <div class="row" style="gap:8px;margin-top:8px">
        <button type="button" class="ghost small" id="peCfgAdd">＋ 添加板块</button>
        <button type="button" class="primary small" id="peCfgSave">保存当前预设修改</button>
        ${p.builtin && p.overridden ? '<button type="button" class="ghost small" id="peCfgReset">恢复内置默认</button>' : ""}
        ${!p.builtin ? '<button type="button" class="ghost small" id="peCfgDelete">删除此自定义预设</button>' : ""}
        <span class="spacer"></span>
        <input type="text" id="peCfgNewName" maxlength="36" placeholder="新预设名，如 四川省考100题" style="width:190px;max-width:100%">
        <button type="button" class="ghost small" id="peCfgSaveAs">另存为新预设</button>
      </div>
    </details>`;
  }

  function timerHtml(d, p) {
    const splits = liveSplits();
    const totalSec = splits.reduce((a, b) => a + b, 0);
    const secs = p?.sections || [];
    const curSec = secs[TIMER.idx];
    const canReorder = TIMER.phase === "idle" && splits.every((x) => x === 0);
    let lapLabel = "开始计时（空格键）";
    if (TIMER.phase === "running" && curSec) {
      lapLabel = TIMER.idx + 1 < secs.length
        ? `记录「${curSec.name}」用时并切下一块（空格）`
        : `记录「${curSec.name}」并完成整卷计时（空格）`;
    } else if (TIMER.phase === "paused") {
      lapLabel = `继续「${curSec ? curSec.name : "当前板块"}」计时（空格）`;
    } else if (TIMER.phase === "done") {
      lapLabel = "整卷计时已完成 · 去录分 →";
    }
    const statusText = TIMER.phase === "idle"
      ? `默认从 ${START_HOUR}:00 开考 · 共 ${secs.length} 个板块（按预设顺序，空格键一键打点）`
      : TIMER.phase === "done"
      ? `全部 ${secs.length} 个板块计时完成！${TIMER.notice ? " · " + TIMER.notice : ""}`
      : `${TIMER.phase === "paused" ? "⏸ 已暂停 · " : "🕯 正在做："}第 ${TIMER.idx + 1}/${secs.length} 块「${curSec ? curSec.name : ""}」${TIMER.notice ? " · " + TIMER.notice : ""}`;

    const qItems = secs.map((s, i) => {
      const active = (TIMER.phase === "running" || TIMER.phase === "paused") && TIMER.idx === i;
      const done = !!TIMER.completed[i];
      const sec = splits[i] || 0;
      return `<div class="pe-q-item${active ? " is-active" : ""}${done ? " is-done" : ""}" data-pe-q="${i}">
        <span class="pe-q-idx">${i + 1}</span>
        <div class="pe-q-main" data-pe-jump="${i}" title="点此切换到该板块计时">
          <b>${esc(s.name)}</b>
          <span class="small muted">${s.total}题 · 参考 ${s.target_minutes || 0}分</span>
        </div>
        <span class="pe-q-time" data-pe-qtime="${i}">${sec > 0 || active ? fmtMMSS(sec) : (done ? "0:00" : "待计")}</span>
        ${canReorder ? `<span class="pe-q-move">
          <button type="button" class="ghost small" data-pe-move="${i}:-1" title="上移" ${i === 0 ? "disabled" : ""}>↑</button>
          <button type="button" class="ghost small" data-pe-move="${i}:1" title="下移" ${i === secs.length - 1 ? "disabled" : ""}>↓</button>
        </span>` : `<span class="small muted">${done ? "✓" : active ? "进行中" : ""}</span>`}
      </div>`;
    }).join("");

    return `<div class="pe-timer-grid">
      <div class="pe-clock-box">
        ${clockSvg(totalSec)}
        <div class="pe-clock-meta">
          <span id="peDigitalWrap" class="pe-digital" ${d.show_digital ? "" : "hidden"}>已用时 <span id="peDigitalTotal">${fmtHMS(totalSec)}</span></span>
          <button type="button" class="ghost small" id="peToggleDigital">${d.show_digital ? "隐藏数字时间" : "显示数字时间"}</button>
        </div>
        <div class="pe-cur-banner" id="peCurBanner">${esc(statusText)}</div>
        <div class="pe-clock-actions">
          <button type="button" class="primary" id="peLapBtn">${esc(lapLabel)}</button>
          <div class="pe-clock-subbtns">
            <button type="button" id="pePauseBtn" ${TIMER.phase === "idle" || TIMER.phase === "done" ? "disabled" : ""}>${TIMER.phase === "paused" ? "继续" : "暂停"}</button>
            <button type="button" class="ghost" id="peResetBtn" ${TIMER.phase === "idle" && totalSec === 0 ? "disabled" : ""}>重置钟表</button>
            <button type="button" id="peToScore">完成计时 · 去录分 →</button>
          </div>
        </div>
      </div>
      <div class="pe-queue-box">
        <div class="pe-queue-head">
          <b>做题顺序与各板块用时</b>
          <span class="small muted">${canReorder ? "开考前可点 ↑↓ 调整做题顺序" : "做题中点任意板块可临时跳块计时"}</span>
        </div>
        <div class="pe-queue-list">${qItems}</div>
      </div>
    </div>`;
  }

  function scoreHtml(d, p) {
    const calc = calcSummary(DRAFT.rows);
    const rowsHtml = DRAFT.rows.map((r, i) => {
      const sc = calc.secScores[i];
      const minVal = r.seconds > 0 ? round2(r.seconds / 60) : "";
      return `<div class="pe-s-row${sc.invalid ? " has-err" : ""}" data-pe-srow="${i}">
        <div class="pe-s-name">
          <b>${i + 1}. ${esc(r.name)}</b>
          <small>${esc(r.module)} · 共 ${r.total} 题 × ${esc(r.points)} 分${r.seconds > 0 ? ` · 计时 ${fmtMMSS(r.seconds)}` : ""}</small>
        </div>
        <label class="small"><span class="muted">对题</span><input type="number" min="0" max="${r.total}" step="1" data-pe-ok="${i}" value="${esc(r.ok)}" placeholder="0～${r.total}"></label>
        <label class="small"><span class="muted">错题</span><input type="number" min="0" max="${r.total}" step="1" data-pe-wrong="${i}" value="${esc(r.wrong)}" placeholder="0～${r.total}"></label>
        <label class="small"><span class="muted">用时(分)</span><input type="number" min="0" max="300" step="0.01" data-pe-min="${i}" value="${minVal}" placeholder="分钟"></label>
        <div class="pe-s-pts"><b data-pe-sec-score="${i}">${sc.score}</b> <small class="muted">/ ${sc.full}分</small></div>
      </div>`;
    }).join("");

    const recs = d.records || [];
    const histHtml = recs.length ? `<div class="pe-history">
      <h4>📋 已录入的纸质自考（共 ${recs.length} 场 · 已同步至考情与战绩）</h4>
      ${recs.map((r) => `<div class="pe-hist-row">
        <div>
          <b>${esc(r.name)}</b> <span class="small muted">${esc(r.date || "")}</span>
          <div class="small muted">得分 <b>${r.score}</b> 分${r.full_score > 100 ? `（卷面 ${r.raw_score}/${r.full_score}）` : ""} · 答对 ${r.ok}/${r.total} 题 · 错 ${r.wrong} 题${r.total_minutes != null ? ` · 用时 ${r.total_minutes} 分钟` : ""}</div>
        </div>
        <div class="row" style="gap:6px">
          <button type="button" class="ghost small" data-pe-edit="${r.season}">修改</button>
          <button type="button" class="ghost small" data-pe-del="${r.season}">删除</button>
        </div>
      </div>`).join("")}
    </div>` : "";

    return `<div>
      <div class="pe-score-meta">
        <label><span class="small muted">试卷名称</span><input type="text" id="peName" maxlength="40" value="${esc(DRAFT.name)}" placeholder="如 2025四川省考行测纸质卷"></label>
        <label><span class="small muted">考试日期</span><input type="date" id="peDate" value="${esc(DRAFT.date || d.today || "")}"></label>
      </div>
      <div class="row" style="gap:12px;margin-bottom:8px;align-items:center">
        <label class="small" style="display:inline-flex;gap:6px;align-items:center;cursor:pointer">
          <input type="checkbox" id="peBlankWrong" style="width:auto" ${d.blank_as_wrong ? "checked" : ""}>
          填对题数时，剩余题数自动填为错题（也可手动修改错题数）
        </label>
        ${EDIT_SEASON ? `<span class="small" style="color:var(--gold)">正在修改：#${EDIT_SEASON}</span><button type="button" class="ghost small" id="peCancelEdit">取消修改，新建一场</button>` : ""}
      </div>
      <div class="pe-score-head-wrap">
        <div class="pe-s-head"><span>板块（题量×分值）</span><span>对题数</span><span>错题数</span><span>用时（分钟）</span><span style="text-align:right">板块得分</span></div>
        <div class="pe-score-list" id="peScoreRows">${rowsHtml}</div>
      </div>
      <div class="pe-summary-bar" id="peSummaryBar">
        <div>
          <div id="peSumStats">答对 <b>${calc.okAll}</b>/${calc.totalAll} 题 · 错 <b>${calc.wrongAll}</b> 题 · 未做 <b>${calc.blankAll}</b> 题 · 总用时 <b>${round2(calc.totalSec / 60)}</b> 分钟</div>
          <div class="small" id="peSumErr" style="color:var(--ds-danger)" ${calc.errors.length ? "" : "hidden"}>${esc(calc.errors.join("；"))}</div>
        </div>
        <div class="row" style="gap:12px;align-items:center">
          <span class="pe-total-score" id="peSumScore">${calc.fullScore > 100 ? `折合 ${calc.normScore} 分（卷面 ${calc.rawScore}/${calc.fullScore}）` : `汇总 ${calc.rawScore} 分`}</span>
          <button type="button" class="primary" id="peSaveExam">${EDIT_SEASON ? "保存修改" : `保存并计入${W("boss")}`}</button>
        </div>
      </div>
      ${histHtml}
    </div>`;
  }

  function html(d) {
    if (!d || d.error) return "";
    DATA = d;
    const p = activePreset(d);
    syncWithPreset(p, false);
    return `<div class="card contest-card pe-card" id="peCard">
      <div class="pe-head-bar">
        <div class="pe-steps" role="group" aria-label="自考辅助模式">
          <button type="button" class="pe-step-btn${STEP === "timer" ? " active" : ""}" data-pe-step="timer">⏱ 钟表计时</button>
          <button type="button" class="pe-step-btn${STEP === "score" ? " active" : ""}" data-pe-step="score">🧮 录分算分</button>
        </div>
        <div class="pe-preset-bar">
          <label class="small muted" for="pePresetSel">预设方案</label>
          <select id="pePresetSel" ${EDIT_SEASON ? "disabled title='修改历史记录时沿用原卷板块，取消修改后可切换预设'" : ""}>${presetSelectHtml(d)}</select>
        </div>
      </div>
      ${EDIT_SEASON ? "" : presetEditorHtml(d, p)}
      ${STEP === "timer" ? timerHtml(d, p) : scoreHtml(d, p)}
    </div>`;
  }

  function updateClockDom() {
    const card = document.getElementById("peCard");
    if (!card || STEP !== "timer") return;
    const splits = liveSplits();
    const totalSec = splits.reduce((a, b) => a + b, 0);
    const ang = clockAngles(totalSec);
    const h = document.getElementById("peHandHour");
    const m = document.getElementById("peHandMin");
    const s = document.getElementById("peHandSec");
    if (h) { h.setAttribute("transform", `rotate(${ang.hour.toFixed(2)} 120 120)`); h.dataset.angle = ang.hour.toFixed(2); }
    if (m) { m.setAttribute("transform", `rotate(${ang.min.toFixed(2)} 120 120)`); m.dataset.angle = ang.min.toFixed(2); }
    if (s) { s.setAttribute("transform", `rotate(${ang.sec.toFixed(2)} 120 120)`); s.dataset.angle = ang.sec.toFixed(2); }
    const dig = document.getElementById("peDigitalTotal");
    if (dig) dig.textContent = fmtHMS(totalSec);
    splits.forEach((sec, i) => {
      const el = card.querySelector(`[data-pe-qtime="${i}"]`);
      if (!el) return;
      const active = (TIMER.phase === "running" || TIMER.phase === "paused") && TIMER.idx === i;
      el.textContent = sec > 0 || active ? fmtMMSS(sec) : (TIMER.completed[i] ? "0:00" : "待计");
    });
  }

  function ensureTicker() {
    clearInterval(TICK_ID);
    if (TIMER.phase === "running") {
      TICK_ID = setInterval(() => {
        if (!document.getElementById("peCard") && TIMER.phase !== "running") {
          clearInterval(TICK_ID);
          return;
        }
        updateClockDom();
      }, 200);
    }
  }

  function rerenderSelf() {
    const pane = document.querySelector('[data-cs-pane="self_exam"]');
    if (!pane || !DATA) return;
    const tmp = document.createElement("div");
    tmp.innerHTML = html(DATA);
    pane.innerHTML = "";
    pane.append(tmp.firstElementChild);
    bind(ON_SAVED);
  }

  function lapOrStart() {
    const p = activePreset(DATA);
    const secs = p?.sections || [];
    if (!secs.length) return;
    if (TIMER.phase === "idle") {
      TIMER.phase = "running";
      TIMER.idx = 0;
      TIMER.segStart = performance.now();
      TIMER.notice = "";
      ensureTicker();
      rerenderSelf();
      return;
    }
    if (TIMER.phase === "paused") {
      TIMER.phase = "running";
      TIMER.segStart = performance.now();
      ensureTicker();
      rerenderSelf();
      return;
    }
    if (TIMER.phase === "running") {
      flushRunning();
      const curIdx = TIMER.idx;
      const curName = secs[curIdx]?.name || "";
      const used = TIMER.splits[curIdx] || 0;
      TIMER.completed[curIdx] = true;
      if (DRAFT.rows[curIdx]) DRAFT.rows[curIdx].seconds = Math.max(1, Math.round(used));
      const nextIdx = secs.findIndex((_, k) => k > curIdx && !TIMER.completed[k]);
      const anyLeft = nextIdx >= 0 ? nextIdx : secs.findIndex((_, k) => !TIMER.completed[k]);
      if (anyLeft >= 0) {
        TIMER.idx = anyLeft;
        TIMER.segStart = performance.now();
        TIMER.notice = `已记「${curName}」${fmtMMSS(used)}`;
      } else {
        TIMER.phase = "done";
        TIMER.segStart = null;
        TIMER.notice = `已记「${curName}」${fmtMMSS(used)}`;
        clearInterval(TICK_ID);
        syncSplitsToDraft();
      }
      rerenderSelf();
      return;
    }
    if (TIMER.phase === "done") {
      syncSplitsToDraft();
      STEP = "score";
      rerenderSelf();
    }
  }

  function readCfgRows() {
    const list = document.getElementById("peCfgList");
    if (!list) return [];
    return [...list.querySelectorAll("[data-pe-cfg-row]")].map((row) => ({
      name: row.querySelector('[data-cfg-k="name"]').value.trim(),
      module: row.querySelector('[data-cfg-k="module"]').value,
      total: Number(row.querySelector('[data-cfg-k="total"]').value),
      points: row.querySelector('[data-cfg-k="points"]').value.trim(),
      target_minutes: Number(row.querySelector('[data-cfg-k="target_minutes"]').value || 0),
    }));
  }

  function refreshScoreSummaryDom() {
    const calc = calcSummary(DRAFT.rows);
    DRAFT.rows.forEach((_, i) => {
      const sc = calc.secScores[i];
      const rowEl = document.querySelector(`[data-pe-srow="${i}"]`);
      const ptsEl = document.querySelector(`[data-pe-sec-score="${i}"]`);
      if (rowEl) rowEl.classList.toggle("has-err", sc.invalid);
      if (ptsEl) ptsEl.textContent = String(sc.score);
    });
    const st = document.getElementById("peSumStats");
    if (st) st.innerHTML = `答对 <b>${calc.okAll}</b>/${calc.totalAll} 题 · 错 <b>${calc.wrongAll}</b> 题 · 未做 <b>${calc.blankAll}</b> 题 · 总用时 <b>${round2(calc.totalSec / 60)}</b> 分钟`;
    const er = document.getElementById("peSumErr");
    if (er) { er.hidden = !calc.errors.length; er.textContent = calc.errors.join("；"); }
    const sp = document.getElementById("peSumScore");
    if (sp) sp.textContent = calc.fullScore > 100 ? `折合 ${calc.normScore} 分（卷面 ${calc.rawScore}/${calc.fullScore}）` : `汇总 ${calc.rawScore} 分`;
  }

  function editSeason(season) {
    if (!DATA) return false;
    const rec = (DATA.records || []).find((r) => String(r.season) === String(season));
    if (!rec) return false;
    EDIT_SEASON = rec.season;
    STEP = "score";
    DRAFT.presetId = rec.preset_id || DATA.active_preset;
    DRAFT.name = rec.name || "";
    DRAFT.date = rec.date || DATA.today || "";
    DRAFT.rows = (rec.sections || []).map((s) => ({
      name: s.name,
      module: s.module,
      total: Number(s.total),
      points: String(s.points),
      target_minutes: 0,
      ok: s.ok != null ? String(s.ok) : "",
      wrong: s.wrong != null ? String(s.wrong) : "",
      seconds: Number(s.seconds || 0),
    }));
    return true;
  }

  function bind(onSaved) {
    ON_SAVED = onSaved || ON_SAVED;
    const card = document.getElementById("peCard");
    if (!card || !DATA) return;
    ensureTicker();

    card.querySelectorAll("[data-pe-step]").forEach((btn) => (btn.onclick = () => {
      const next = btn.dataset.peStep;
      if (next === "score") {
        if (TIMER.phase === "running") {
          flushRunning();
          TIMER.phase = "paused";
          TIMER.segStart = null;
          clearInterval(TICK_ID);
        }
        syncSplitsToDraft();
      }
      STEP = next;
      rerenderSelf();
    }));

    const presetSel = document.getElementById("pePresetSel");
    if (presetSel) presetSel.onchange = async () => {
      try {
        DATA = await api("/api/paper-exam/prefs", { action: "select", preset_id: presetSel.value });
        syncWithPreset(activePreset(DATA), true);
        rerenderSelf();
      } catch (e) { showError(e); }
    };

    // 预设编辑器事件
    const cfgList = document.getElementById("peCfgList");
    if (cfgList) {
      const rerenderCfgDom = (secs) => {
        const p = activePreset(DATA);
        if (p) { p.sections = secs; }
        const open = document.getElementById("pePresetFold")?.open;
        rerenderSelf();
        const fold = document.getElementById("pePresetFold");
        if (fold && open) fold.open = true;
      };
      cfgList.querySelectorAll("[data-cfg-act]").forEach((b) => (b.onclick = () => {
        const rows = readCfgRows();
        const idx = Number(b.closest("[data-pe-cfg-row]").dataset.peCfgRow);
        const act = b.dataset.cfgAct;
        if (act === "up" && idx > 0) [rows[idx - 1], rows[idx]] = [rows[idx], rows[idx - 1]];
        else if (act === "down" && idx < rows.length - 1) [rows[idx + 1], rows[idx]] = [rows[idx], rows[idx + 1]];
        else if (act === "del" && rows.length > 1) rows.splice(idx, 1);
        rerenderCfgDom(rows);
      }));
      const addBtn = document.getElementById("peCfgAdd");
      if (addBtn) addBtn.onclick = () => {
        const rows = readCfgRows();
        rows.push({ name: "新板块", module: DATA.module_names[0] || "常识判断", total: 10, points: "1", target_minutes: 10 });
        rerenderCfgDom(rows);
      };
      const saveBtn = document.getElementById("peCfgSave");
      if (saveBtn) saveBtn.onclick = async () => {
        const p = activePreset(DATA);
        try {
          DATA = await api("/api/paper-exam/prefs", { action: "save_preset", preset_id: p.id, name: p.name, sections: readCfgRows(), as_new: false });
          syncWithPreset(activePreset(DATA), true);
          toast("预设已更新");
          rerenderSelf();
        } catch (e) { showError(e); }
      };
      const saveAsBtn = document.getElementById("peCfgSaveAs");
      if (saveAsBtn) saveAsBtn.onclick = async () => {
        const newName = document.getElementById("peCfgNewName")?.value.trim();
        if (!newName) return toast("请先输入新预设名称");
        try {
          DATA = await api("/api/paper-exam/prefs", { action: "save_preset", name: newName, sections: readCfgRows(), as_new: true });
          syncWithPreset(activePreset(DATA), true);
          toast(`已另存预设「${newName}」`);
          rerenderSelf();
        } catch (e) { showError(e); }
      };
      const resetBtn = document.getElementById("peCfgReset");
      if (resetBtn) resetBtn.onclick = async () => {
        const p = activePreset(DATA);
        try {
          DATA = await api("/api/paper-exam/prefs", { action: "reset_builtin", preset_id: p.id });
          syncWithPreset(activePreset(DATA), true);
          toast("已恢复内置默认");
          rerenderSelf();
        } catch (e) { showError(e); }
      };
      const delPresetBtn = document.getElementById("peCfgDelete");
      if (delPresetBtn) delPresetBtn.onclick = async () => {
        const p = activePreset(DATA);
        try {
          DATA = await api("/api/paper-exam/prefs", { action: "delete_preset", preset_id: p.id });
          syncWithPreset(activePreset(DATA), true);
          toast("已删除自定义预设");
          rerenderSelf();
        } catch (e) { showError(e); }
      };
    }

    // 计时器事件
    const lapBtn = document.getElementById("peLapBtn");
    if (lapBtn) lapBtn.onclick = () => lapOrStart();
    const pauseBtn = document.getElementById("pePauseBtn");
    if (pauseBtn) pauseBtn.onclick = () => {
      if (TIMER.phase === "running") {
        flushRunning();
        TIMER.phase = "paused";
        TIMER.segStart = null;
        clearInterval(TICK_ID);
      } else if (TIMER.phase === "paused") {
        TIMER.phase = "running";
        TIMER.segStart = performance.now();
        ensureTicker();
      }
      rerenderSelf();
    };
    const resetBtn = document.getElementById("peResetBtn");
    if (resetBtn) resetBtn.onclick = () => {
      clearInterval(TICK_ID);
      syncWithPreset(activePreset(DATA), true);
      rerenderSelf();
    };
    const toScoreBtn = document.getElementById("peToScore");
    if (toScoreBtn) toScoreBtn.onclick = () => {
      if (TIMER.phase === "running") {
        flushRunning();
        TIMER.phase = "paused";
        TIMER.segStart = null;
        clearInterval(TICK_ID);
      }
      syncSplitsToDraft();
      STEP = "score";
      rerenderSelf();
    };
    const toggleDig = document.getElementById("peToggleDigital");
    if (toggleDig) toggleDig.onclick = async () => {
      const next = !DATA.show_digital;
      DATA.show_digital = next;
      rerenderSelf();
      try { await api("/api/paper-exam/prefs", { action: "update", show_digital: next }); } catch (_) {}
    };
    card.querySelectorAll("[data-pe-jump]").forEach((el) => (el.onclick = () => {
      const idx = Number(el.dataset.peJump);
      if (TIMER.phase === "running") flushRunning();
      TIMER.idx = idx;
      if (TIMER.phase === "done") TIMER.phase = "paused";
      rerenderSelf();
    }));
    card.querySelectorAll("[data-pe-move]").forEach((btn) => (btn.onclick = async () => {
      const [rawIdx, rawDir] = btn.dataset.peMove.split(":");
      const idx = Number(rawIdx), dir = Number(rawDir);
      const p = activePreset(DATA);
      if (!p) return;
      const secs = p.sections.map((s) => ({ ...s }));
      const target = idx + dir;
      if (target < 0 || target >= secs.length) return;
      [secs[idx], secs[target]] = [secs[target], secs[idx]];
      try {
        DATA = await api("/api/paper-exam/prefs", { action: "reorder", preset_id: p.id, sections: secs });
        syncWithPreset(activePreset(DATA), true);
        rerenderSelf();
      } catch (e) { showError(e); }
    }));

    // 录分表单事件
    const nameIn = document.getElementById("peName");
    if (nameIn) nameIn.oninput = () => { DRAFT.name = nameIn.value; };
    const dateIn = document.getElementById("peDate");
    if (dateIn) dateIn.oninput = () => { DRAFT.date = dateIn.value; };
    const bwChk = document.getElementById("peBlankWrong");
    if (bwChk) bwChk.onchange = async () => {
      DATA.blank_as_wrong = bwChk.checked;
      if (bwChk.checked) {
        DRAFT.rows.forEach((r, i) => {
          if (r.ok !== "" && r.wrong === "") {
            const ok = Math.max(0, Math.min(r.total, parseInt(r.ok, 10) || 0));
            r.wrong = String(Math.max(0, r.total - ok));
            const wEl = card.querySelector(`[data-pe-wrong="${i}"]`);
            if (wEl) wEl.value = r.wrong;
          }
        });
        refreshScoreSummaryDom();
      }
      try { await api("/api/paper-exam/prefs", { action: "update", blank_as_wrong: bwChk.checked }); } catch (_) {}
    };
    card.querySelectorAll("[data-pe-ok]").forEach((inp) => (inp.oninput = () => {
      const i = Number(inp.dataset.peOk);
      const r = DRAFT.rows[i];
      if (!r) return;
      r.ok = inp.value;
      if (DATA.blank_as_wrong && inp.value !== "") {
        const ok = Math.max(0, Math.min(r.total, parseInt(inp.value, 10) || 0));
        r.wrong = String(Math.max(0, r.total - ok));
        const wEl = card.querySelector(`[data-pe-wrong="${i}"]`);
        if (wEl) wEl.value = r.wrong;
      }
      refreshScoreSummaryDom();
    }));
    card.querySelectorAll("[data-pe-wrong]").forEach((inp) => (inp.oninput = () => {
      const i = Number(inp.dataset.peWrong);
      if (DRAFT.rows[i]) DRAFT.rows[i].wrong = inp.value;
      refreshScoreSummaryDom();
    }));
    card.querySelectorAll("[data-pe-min]").forEach((inp) => (inp.oninput = () => {
      const i = Number(inp.dataset.peMin);
      if (DRAFT.rows[i]) {
        const v = inp.value === "" ? 0 : Math.max(0, parseFloat(inp.value) || 0);
        DRAFT.rows[i].seconds = Math.round(v * 60);
      }
      refreshScoreSummaryDom();
    }));
    const cancelEdit = document.getElementById("peCancelEdit");
    if (cancelEdit) cancelEdit.onclick = () => {
      EDIT_SEASON = null;
      syncWithPreset(activePreset(DATA), true);
      rerenderSelf();
    };
    const saveExamBtn = document.getElementById("peSaveExam");
    if (saveExamBtn) saveExamBtn.onclick = async () => {
      const calc = calcSummary(DRAFT.rows);
      if (calc.errors.length) return toast(calc.errors[0]);
      const p = activePreset(DATA);
      saveExamBtn.disabled = true;
      try {
        const r = await api("/api/paper-exam/save", {
          season: EDIT_SEASON,
          name: DRAFT.name.trim(),
          date: DRAFT.date || DATA.today || "",
          preset_id: p?.id || "",
          preset_name: p?.name || "",
          sections: DRAFT.rows.map((row) => ({
            name: row.name,
            module: row.module,
            total: row.total,
            points: row.points,
            ok: row.ok === "" ? 0 : parseInt(row.ok, 10) || 0,
            wrong: row.wrong === "" ? 0 : parseInt(row.wrong, 10) || 0,
            seconds: row.seconds || 0,
          })),
        });
        const wasEdit = !!EDIT_SEASON;
        DATA = r.paper_exam;
        EDIT_SEASON = null;
        syncWithPreset(activePreset(DATA), true);
        DRAFT.name = "";
        toast(wasEdit ? `已更新纸质模考（${r.score} 分）` : `已记入${W("boss")}：${r.score} 分`);
        if (ON_SAVED) await ON_SAVED(r, !wasEdit);
        else rerenderSelf();
      } catch (e) { showError(e); } finally { saveExamBtn.disabled = false; }
    };
    card.querySelectorAll("[data-pe-edit]").forEach((btn) => (btn.onclick = () => {
      if (editSeason(btn.dataset.peEdit)) rerenderSelf();
    }));
    card.querySelectorAll("[data-pe-del]").forEach((btn) => (btn.onclick = async () => {
      const s = Number(btn.dataset.peDel);
      btn.disabled = true;
      try {
        const r = await api("/api/paper-exam/delete", { season: s });
        DATA = r.paper_exam;
        if (EDIT_SEASON === s) {
          EDIT_SEASON = null;
          syncWithPreset(activePreset(DATA), true);
        }
        toast("已删除该场纸质自考记录");
        if (ON_SAVED) await ON_SAVED(r, false);
        else rerenderSelf();
      } catch (e) { showError(e); } finally { btn.disabled = false; }
    }));
  }

  // 空格键快捷记录当前板块用时：仅当「自考 → 钟表计时」卷宗打开且焦点不在输入框/次要操作钮时触发
  window.addEventListener("keydown", (e) => {
    if (e.repeat || e.code !== "Space" || e.ctrlKey || e.metaKey || e.altKey) return;
    const scene = document.querySelector('.contest-scene[data-cs-view="self_exam"]');
    const dlg = scene?.querySelector("dialog.cs-dialog[open]");
    if (!dlg || STEP !== "timer") return;
    const ae = document.activeElement;
    const tag = ae?.tagName || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || tag === "SUMMARY" || ae?.isContentEditable) return;
    if (tag === "BUTTON" && ae.id !== "peLapBtn" && !ae.hasAttribute("data-cs-close")) return;
    e.preventDefault();
    lapOrStart();
  });

  window.PAPER_EXAM = { html, bind, editSeason };
})();
