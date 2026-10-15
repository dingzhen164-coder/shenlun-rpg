/* 3.2.9前置：音效与背景音乐（素材在 assets/beauty/audio/，固定文件名见该目录 README；缺文件就静音，不报错）。
 * 规则：不改成绩与学习记录；浏览器要求先点一下页面才允许发声，所以第一次点击后才开始放；右下角 🔊 可关、可调音量；
 * 答题时音乐自动降低；页面隐藏时暂停。设置只存在本机浏览器（localStorage）。 */
(function () {
  "use strict";
  var BASE = "assets/beauty/audio/", KEY = "beauty-audio-v1";
  var S = { sfx: true, bgm: true, vs: 0.6, vb: 0.35 };
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
  function targetVol() { return S.bgm ? S.vb * (want === "study" ? 0.6 : 1) : 0; }
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
    if (old) ramp(old, 0, 1200, function () { old.pause(); });
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
  function refresh() { want = context(); setBgm(want); }
  function soon() { clearTimeout(timer); timer = setTimeout(refresh, 500); }

  function unlock() {
    if (unlocked) return; unlocked = true;
    refresh();
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
    if (v) new MutationObserver(function (ms) {
      for (var i = 0; i < ms.length; i++) {
        var r = ms[i];
        if (r.type === "attributes" && r.target.classList && r.target.classList.contains("tj-opt")) {
          if (r.target.classList.contains("right")) sfx("correct"); else if (r.target.classList.contains("wrong")) sfx("wrong");
        }
      }
      soon();
    }).observe(v, { attributes: true, attributeFilter: ["class"], subtree: true, childList: true });
    new MutationObserver(soon).observe(document.body, { attributes: true, attributeFilter: ["class"] });
    new MutationObserver(soon).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-scene-time"] });
  }
  window.addEventListener("hashchange", function () { sfx("page", 0.7); });
  document.addEventListener("visibilitychange", function () {
    if (!cur) return; if (document.hidden) cur.pause(); else if (unlocked && S.bgm) cur.play().catch(function () {});
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

  // ---- 右下角控制钮
  function ui() {
    var box = document.createElement("div"); box.id = "beautyAudio"; box.className = "beauty-audio";
    box.innerHTML = '<button type="button" class="beauty-audio-btn" aria-label="声音设置" title="声音设置"></button>' +
      '<div class="beauty-audio-pop" hidden><label><input type="checkbox" data-k="sfx"> 音效</label><input type="range" min="0" max="100" data-v="vs" aria-label="音效音量">' +
      '<label><input type="checkbox" data-k="bgm"> 背景音乐</label><input type="range" min="0" max="100" data-v="vb" aria-label="音乐音量"></div>';
    document.body.appendChild(box);
    var btn = box.querySelector(".beauty-audio-btn"), pop = box.querySelector(".beauty-audio-pop");
    function paint() {
      btn.textContent = (S.sfx || S.bgm) ? "🔊" : "🔇";
      box.querySelectorAll("[data-k]").forEach(function (i) { i.checked = !!S[i.dataset.k]; });
      box.querySelectorAll("[data-v]").forEach(function (i) { i.value = Math.round(S[i.dataset.v] * 100); });
      if (window.BeautyIcons) BeautyIcons.scan(box);
    }
    btn.addEventListener("click", function () { pop.hidden = !pop.hidden; });
    document.addEventListener("pointerdown", function (e) { if (!box.contains(e.target)) pop.hidden = true; }, true);
    box.addEventListener("change", function (e) {
      var k = e.target.dataset.k; if (k) { S[k] = e.target.checked; save(); paint(); if (cur) { if (S.bgm) { cur.play().catch(function () {}); } ramp(cur, targetVol(), 300); } if (k === "bgm" && !S.bgm && cur) setTimeout(function () { cur.pause(); }, 350); }
    });
    box.addEventListener("input", function (e) {
      var v = e.target.dataset.v; if (!v) return; S[v] = e.target.value / 100; save();
      if (v === "vb" && cur) cur.volume = targetVol(); else if (v === "vs") sfx("click");
    });
    paint();
  }
  window.BeautyAudio = { sfx: sfx, bgm: function (n) { override = n || ""; refresh(); }, settings: S };
  function init() { ui(); watch(); wrapCeremony(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
