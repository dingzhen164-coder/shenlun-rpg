/* 3.2.1 统一图标：把界面文字里的 emoji 换成同一套线条图标（Lucide，ISC）。
 * 做法：保留原 emoji 字符在 DOM 里（textContent、旧测试不变），只把它缩成 0 宽，旁边补一个 <svg>。
 * 对照表 assets/beauty/icons/emoji-map.json，图标合集 assets/beauty/icons/sprite.svg（tools/build_icons.py 生成）。
 * 任何一步失败（文件缺失、网络错误）都保持显示原 emoji。 */
(function () {
  "use strict";
  var BASE = "assets/beauty/icons/";
  var map = null, ready = false, queued = false, SKIP = /^(SCRIPT|STYLE|TEXTAREA|INPUT|SELECT|OPTION|SVG|CANVAS|TITLE|NOSCRIPT)$/;
  var re = null;

  function build() {
    var keys = Object.keys(map).sort(function (a, b) { return b.length - a.length; });
    re = new RegExp("(" + keys.map(function (k) { return k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|") + ")\\uFE0F?", "g");
  }
  function skipNode(n) {
    for (var p = n.parentNode; p && p.nodeType === 1; p = p.parentNode) {
      if (SKIP.test(p.nodeName) || p.isContentEditable || (p.classList && (p.classList.contains("ic-e") || p.classList.contains("no-ic")))) return true;
    }
    return false;
  }
  function make(ch) {
    var name = map[ch];
    var s = document.createElement("span");
    s.className = "ic-e"; s.setAttribute("aria-hidden", "true");
    var t = document.createElement("span"); t.className = "ic-t"; t.textContent = ch; s.appendChild(t);
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "ic"); svg.setAttribute("focusable", "false");
    var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#ic-" + name);
    svg.appendChild(use); s.appendChild(svg);
    return s;
  }
  function scan(root) {
    if (!ready || !root) return;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), nodes = [], n;
    while ((n = w.nextNode())) { if (n.nodeValue && re.test(n.nodeValue)) { re.lastIndex = 0; if (!skipNode(n)) nodes.push(n); } re.lastIndex = 0; }
    nodes.forEach(function (t) {
      var txt = t.nodeValue, frag = document.createDocumentFragment(), last = 0, m;
      re.lastIndex = 0;
      while ((m = re.exec(txt))) {
        if (m.index > last) frag.appendChild(document.createTextNode(txt.slice(last, m.index)));
        frag.appendChild(make(m[1]));
        last = m.index + m[0].length;
      }
      if (last < txt.length) frag.appendChild(document.createTextNode(txt.slice(last)));
      if (t.parentNode) t.parentNode.replaceChild(frag, t);
    });
  }
  function schedule() {
    if (queued) return; queued = true;
    (window.requestAnimationFrame || setTimeout)(function () { queued = false; scan(document.body); });
  }
  function start() {
    scan(document.body);
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  function load() {
    Promise.all([
      fetch(BASE + "emoji-map.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }),
      fetch(BASE + "sprite.svg").then(function (r) { if (!r.ok) throw 0; return r.text(); })
    ]).then(function (a) {
      map = a[0]; build();
      var box = document.createElement("div"); box.style.display = "none"; box.innerHTML = a[1];
      document.body.insertBefore(box, document.body.firstChild);
      ready = true; document.documentElement.classList.add("has-icons"); start();
    }).catch(function () { /* 保持原 emoji */ });
  }
  window.BeautyIcons = { scan: function (r) { scan(r || document.body); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load); else load();
})();
