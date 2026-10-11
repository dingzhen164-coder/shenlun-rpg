/* 清禾师尊：行测洞府立绘与对话入口。app.js 在渲染后 mount；只读 dashboard 的
   plan.tasks/redo/minutes，不写存档、不算奖励。路由由 app.js 注入，闲谈为内置台词。
   用户选择的透明立绘随程序离线分发；旧角色设定里的授业导师仍负责 AI 讲解。 */
(() => {
  'use strict';
  const portrait = 'assets/guide/shen-qinghe.webp';
  const escape = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let data, actions, panel, timer, fullText = '', focusBack;
  const tasks = d => Array.isArray(d?.plan?.tasks) ? d.plan.tasks : [];
  function greeting(d) {
    const all = tasks(d), done = all.filter(t => t.done).length;
    const progress = all.length ? `今日功课已完成 ${done}/${all.length} 项。` : '今日尚无功课安排，可先去修炼殿选择功法。';
    const wrong = Number(d?.redo) || 0;
    return `徒儿，来坐。${progress}${wrong > 0 ? `心魔录中还有 ${wrong} 道待复盘错题，莫急着求快。` : '先明白要点，再用自己的话讲清、举例，最后以真题验之。'}`;
  }
  function nextTask(d) { return tasks(d).find(t => !t.done && t.id && t.id !== 'cards:all'); }
  const options = () => `<div class="xc-guide-options"><button data-xc-guide="teach"><b>请教功法</b><small>明理 · 举例 · 拆题</small></button><button data-xc-guide="study"><b>开始修炼</b><small>继续今日功课</small></button><button data-xc-guide="wrong"><b>复盘错题</b><small>照见心魔 · 查漏补缺</small></button><button data-xc-guide="chat"><b>闲谈</b><small>竹下小憩</small></button></div>`;
  function homeHtml(d) {
    return `<section class="xc-guide-scene" aria-label="清禾师尊的洞府"><div class="xc-guide-mountains" aria-hidden="true"></div><button class="xc-guide-portrait" data-xc-guide="open" aria-label="与清禾师尊交谈"><img src="${portrait}" alt="沈清禾，手持竹卷的女师尊" fetchpriority="high"></button><div class="xc-guide-intro"><span class="xc-guide-eyebrow">竹影洞府 · 引导师尊</span><h2>清禾师尊</h2><p>修行在于明理，进境在于实证。</p>${options()}</div><div class="xc-guide-home-dialogue"><b>沈清禾</b><p>${escape(greeting(d))}</p><button data-xc-guide="open">与师尊交谈 <span aria-hidden="true">▸</span></button></div></section>`;
  }
  function stop() { clearInterval(timer); timer = null; }
  function reveal() { stop(); const p = panel?.querySelector('.xc-guide-spoken'); if (p) p.textContent = fullText; }
  function speak(text) {
    stop(); fullText = text;
    panel.querySelector('.xc-guide-sr').textContent = text;
    const p = panel.querySelector('.xc-guide-spoken');
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) { p.textContent = text; return; }
    const letters = Array.from(text); let index = 0; p.textContent = '';
    timer = setInterval(() => { p.textContent = letters.slice(0, ++index).join(''); if (index >= letters.length) stop(); }, 28);
  }
  function close(restore = false) {
    const wasOpen = !!panel; stop(); panel?.remove(); panel = null;
    if (restore && focusBack?.isConnected) focusBack.focus();
    return wasOpen;
  }
  function open() {
    if (data?.subject !== '行测') return;
    close(); focusBack = document.activeElement;
    panel = document.createElement('section'); panel.className = 'xc-guide-dialogue';
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', '清禾师尊对话');
    panel.innerHTML = `<div class="xc-guide-bust" aria-hidden="true"><img class="xc-guide-panel-portrait" src="${portrait}" alt=""></div><div class="xc-guide-paper"><div class="xc-guide-dialogue-head"><b>清禾师尊 <small>沈清禾</small></b><button data-xc-guide="close" aria-label="收起师尊对话">×</button></div><p class="xc-guide-spoken" aria-hidden="true"></p><p class="xc-guide-sr" aria-live="polite"></p><button class="xc-guide-reveal" data-xc-guide="reveal">立即显示全文</button>${options()}<div class="xc-guide-followup"></div></div>`;
    document.body.appendChild(panel); speak(greeting(data)); panel.querySelector('[data-xc-guide="close"]').focus();
  }
  function show(text, controls) {
    if (data?.subject !== '行测') return;
    if (!panel) open();
    panel.querySelector('.xc-guide-options').hidden = true;
    panel.querySelector('.xc-guide-followup').innerHTML = controls;
    speak(text);
  }
  function mount(d, view, handlers) {
    data = d; actions = handlers; close();
    document.getElementById('xcGuideAvatar')?.remove();
    if (d?.subject !== '行测' || view === 'home') return;
    const avatar = document.createElement('button'); avatar.id = 'xcGuideAvatar'; avatar.className = 'xc-guide-avatar';
    avatar.dataset.xcGuide = 'open'; avatar.setAttribute('aria-label', '与清禾师尊交谈');
    avatar.innerHTML = `<img src="${portrait}" alt=""><span>清禾师尊</span>`; document.body.appendChild(avatar);
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-xc-guide]'); if (!b || data?.subject !== '行测') return;
    const action = b.dataset.xcGuide;
    if (action === 'open') return open();
    if (action === 'close') return close(true);
    if (action === 'reveal') return reveal();
    if (action === 'chat') {
      if (!panel) open();
      speak('竹下小憩，也是一程修行。今日不必与旁人比快，能把一个要点讲明白、把一道错题看透，便没有白来。若想讨论具体题目，可请授业导师与你细谈。');
      panel.querySelector('.xc-guide-followup').innerHTML = `<button data-xc-guide="tutor">向${escape(data?.persona?.tutor || '授业导师')}请教</button>`;
      return;
    }
    close(); actions?.[action]?.();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && panel) { close(true); e.preventDefault(); } });
  document.addEventListener('visibilitychange', () => { if (document.hidden) reveal(); });
  window.XC_GUIDE = { homeHtml, mount, close, greeting, nextTask, show };
})();
