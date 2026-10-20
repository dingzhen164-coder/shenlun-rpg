/* 3.2.9前置：音效与背景音乐（素材在 assets/beauty/audio/，固定文件名见该目录 README；缺文件就静音，不报错）。
 * 规则：不改成绩与学习记录；浏览器要求先点一下页面才允许发声，所以第一次点击后才开始放；右下角 🔊 可关、可调音量；
 * 答题时音乐自动降低；页面隐藏时暂停。设置只存在本机浏览器（localStorage）。 */
(function () {
  "use strict";
  var BASE = "assets/beauty/audio/", KEY = "beauty-audio-v1";
  var S = { sfx: true, bgm: true, vs: 0.6, vb: 0.35, src: "builtin" };
  try { var o = JSON.parse(localStorage.getItem(KEY) || "{}"); for (var k in o) if (k in S) S[k] = o[k]; } catch (e) { /* 读不到就用默认 */ }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* 存不了只管这次 */ } }

  var missing = {}, cache = {}, unlocked = false, last = {};
  function sfx(name, vol) {
    if (!S.sfx || !unlocked || missing[name]) return;
    var now = Date.now(); if (last[name] && now - last[name] < 80) return; last[name] = now;
    try {
      var a = cache[name];
      if (!a) { a = cache[name] = new Audio(BASE + "sfx/" + name + ".ogg"); a.preload = "auto"; a.addEventListener("error", function () { missing[name] = 1; }); }
      var c = a.cloneNode(); c.volume = Math.min(1, S.vs * (vol || 1)); c.play().catch(function () {});
    } catch (e) { /* 静音 */ }
  }

  // ---- 背景音乐：当前曲目 + 淡入淡出
  var cur = null, curName = "", want = "", override = "", timer = 0;
  function targetVol() { return S.bgm && S.src === "builtin" ? S.vb * (want === "study" ? 0.6 : 1) : 0; }
  function ramp(a, to, ms, done) {
    var from = a.volume, t0 = Date.now(); clearInterval(a._r);
    a._r = setInterval(function () {
      var k = Math.min(1, (Date.now() - t0) / ms); a.volume = Math.max(0, Math.min(1, from + (to - from) * k));
      if (k >= 1) { clearInterval(a._r); if (done) done(); }
    }, 50);
  }
  function setBgm(name) {
    if (name === curName) { if (cur) ramp(cur, targetVol(), 400); return; }
    var old = cur; curName = name;
    if (old) { if (S.src !== "builtin") { clearInterval(old._r); old.pause(); } else ramp(old, 0, 1200, function () { old.pause(); }); }
    cur = null;
    if (!name || missing["bgm/" + name]) return;
    var a = new Audio(BASE + "bgm/" + name + ".ogg"); a.loop = true; a.volume = 0;
    a.addEventListener("error", function () { missing["bgm/" + name] = 1; if (cur === a) cur = null; });
    cur = a;
    if (unlocked && S.bgm) a.play().then(function () { ramp(a, targetVol(), 1500); }).catch(function () {});
  }
  function context() {
    if (override) return override;
    var d = document, dark = (d.documentElement.dataset.sceneTime || d.documentElement.dataset.theme) === "dark" || d.documentElement.dataset.sceneTime === "night";
    if (d.querySelector(".tj-opt, .study-session, .train-active")) return "study";
    if (d.querySelector("#modal:not(.hidden) .narrative-stage, dialog[open] .narrative-stage, .narrative-dialog[open]")) return "dialog";
    if (d.body.classList.contains("portal-home")) return dark ? "map-night" : "map-day";
    return "dongfu";
  }
  // ---- 环境声：地图白天鸟鸣、夜晚虫鸣、洞府流水；跟“音效”开关与音量走（音量取一半）；答题和对话时不放
  var amb = null, ambName = "";
  var AMB_OF = { "map-day": "ambient-day", "map-night": "ambient-night", dongfu: "ambient-water" };
  function ambVol() { return S.sfx ? S.vs * 0.5 : 0; }
  function setAmb(name) {
    if (name === ambName) { if (amb) ramp(amb, ambVol(), 400); return; }
    var old = amb; ambName = name; amb = null;
    if (old) ramp(old, 0, 1200, function () { old.pause(); });
    if (!name || missing["sfx/" + name]) return;
    var a = new Audio(BASE + "sfx/" + name + ".ogg"); a.loop = true; a.volume = 0;
    a.addEventListener("error", function () { missing["sfx/" + name] = 1; if (amb === a) amb = null; });
    amb = a;
    if (unlocked && S.sfx) a.play().then(function () { ramp(a, ambVol(), 1500); }).catch(function () {});
  }
  function refresh() { want = context(); setBgm(S.src === "builtin" ? want : ""); setAmb(S.sfx ? (AMB_OF[want] || "") : ""); }
  function soon() { clearTimeout(timer); timer = setTimeout(refresh, 500); }

  function unlock() {
    if (unlocked) return; unlocked = true;
    apply();
  }

  // ---- 事件：点击、悬停、弹窗、答对答错、奖励
  document.addEventListener("pointerdown", function (e) {
    unlock();
    var t = e.target.closest && e.target.closest("button, a[data-view], .portal-place, summary, [role=button], .tj-opt");
    if (t && !t.disabled && !t.closest("#beautyAudio")) sfx("click", 0.8);
  }, true);
  document.addEventListener("mouseover", function (e) {
    var t = e.target.closest && e.target.closest(".portal-place");
    if (t && !t.contains(e.relatedTarget)) sfx("hover", 0.5);
  }, true);

  var modalOpen = false;
  function watch() {
    var m = document.getElementById("modal");
    if (m) new MutationObserver(function () {
      var o = !m.classList.contains("hidden"); if (o !== modalOpen) { modalOpen = o; sfx(o ? "open" : "close", 0.7); soon(); }
    }).observe(m, { attributes: true, attributeFilter: ["class"] });
    var tt = document.getElementById("toasts");
    if (tt) new MutationObserver(function (ms) {
      ms.forEach(function (r) { r.addedNodes.forEach(function (n) { if (n.classList && n.classList.contains("xp")) sfx("reward"); }); });
    }).observe(tt, { childList: true });
    var v = document.getElementById("view");
    document.addEventListener("beauty:answer", function (e) { sfx(e.detail && e.detail.right ? "correct" : "wrong"); });
    if (v) new MutationObserver(function () {
      soon();
    }).observe(v, { attributes: true, attributeFilter: ["class"], subtree: true, childList: true });
    new MutationObserver(soon).observe(document.body, { attributes: true, attributeFilter: ["class"] });
    new MutationObserver(soon).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-scene-time"] });
  }
  document.addEventListener("beauty:view", function () { sfx("page", 0.7); });
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { if (cur) cur.pause(); if (amb) amb.pause(); window.AMB?.bgm.pauseHidden(); } else { syncMine(); if (cur && unlocked && S.bgm && S.src === "builtin") cur.play().catch(function () {}); if (amb && unlocked && S.sfx) amb.play().catch(function () {}); }
  });

  // 仪式：升级/破境时放对应音效，并短暂切到仪式曲
  function wrapCeremony() {
    var C = window.CEREMONY; if (!C || C._beauty) return; C._beauty = 1;
    ["show", "realm", "contest"].forEach(function (fn) {
      var f = C[fn]; if (typeof f !== "function") return;
      C[fn] = function () {
        sfx(fn === "realm" ? "breakthrough" : "levelup"); override = "ceremony"; refresh();
        setTimeout(function () { override = ""; refresh(); }, 14000);
        return f.apply(this, arguments);
      };
    });
  }

  // ---- 与设置页“背景音乐”合并的控制接口（ambience.js 的设置卡调用）。来源：内置场景音乐 / 我的音乐（库里 训练/外观/音乐/，由 AMB.bgm 播放）
  var mineOn = function () { return !!(window.AMB && AMB.bgm && AMB.bgm.on); };
  function syncMine() {
    if (!window.AMB || !AMB.bgm) return;
    var should = S.bgm && S.src === "mine" && unlocked;
    if (should && !document.hidden) { if (!mineOn()) AMB.bgm.start(); else AMB.bgm.resume(); }
    else if (!should && mineOn()) AMB.bgm.stop();
  }
  function apply() {
    refresh();
    if (cur) { if (S.bgm && S.src === "builtin" && unlocked) cur.play().catch(function () {}); ramp(cur, targetVol(), 300); if (!(S.bgm && S.src === "builtin")) setTimeout(function () { if (cur && !(S.bgm && S.src === "builtin")) cur.pause(); }, 350); }
    syncMine();
  }
  function paintBtn() { var b = document.querySelector(".beauty-audio-btn"); if (b) { b.textContent = (S.sfx || S.bgm) ? "🔊" : "🔇"; if (window.BeautyIcons) BeautyIcons.scan(b.parentNode); } }
  var API = {
    sync: apply,
    sfx: sfx, bgm: function (n) { override = n || ""; refresh(); },
    settings: S,
    set: function (patch) { for (var k in patch) if (k in S) S[k] = patch[k]; save(); apply(); paintBtn(); },
    setBgmVolume: function (v) { S.vb = v; save(); if (cur) cur.volume = targetVol(); },
    setSfxVolume: function (v) { S.vs = v; save(); if (amb) amb.volume = ambVol(); sfx("click"); }
  };
  // 右下角只留一个“全部静音/恢复”小按钮（详细设置在 设置 → 外观与音乐）
  function ui() {
    var box = document.createElement("div"); box.id = "beautyAudio"; box.className = "beauty-audio";
    box.innerHTML = '<button type="button" class="beauty-audio-btn" aria-label="静音 / 恢复声音" title="静音 / 恢复声音（详细设置在 设置 → 外观与音乐）"></button>';
    document.body.appendChild(box);
    var last = { sfx: true, bgm: true };
    box.querySelector("button").addEventListener("click", function () {
      if (S.sfx || S.bgm) { last = { sfx: S.sfx, bgm: S.bgm }; API.set({ sfx: false, bgm: false }); } else API.set({ sfx: last.sfx || true, bgm: last.bgm || true });
    });
    paintBtn();
  }
  window.BeautyAudio = API;
  function init() { ui(); watch(); wrapCeremony(); if (S.src === "mine") setTimeout(syncMine, 600); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
