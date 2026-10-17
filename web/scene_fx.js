/* 3.2.3 场景动态层（行测青衡宗等全景首页）：按真实时钟切换时段、季节飘落物、光点与飞鸟。
 * 只改外观，不碰学习数据。设置在 设置→地点排布 页顶部（场景时间、季节效果），存 localStorage：
 *   scene-time = auto(默认，跟随时钟) | day | night | theme(跟随亮暗主题，旧行为)
 *   scene-season = auto(默认，按月份) | spring | summer | autumn | winter | off
 * 时段（auto）：5:30—8:00 清晨、8:00—17:00 白天、17:00—19:30 黄昏、其余夜晚；清晨/黄昏在白天（清晨）或夜晚图（黄昏偏白天图）上叠暖色。
 * 减少动画（data-motion=reduced）、页面隐藏、系统减少动画时不画粒子，只留静态时段色。 */
(() => {
  'use strict';
  const LS = (k, d) => { try { return localStorage.getItem(k) || d; } catch (e) { return d; } };
  const SET = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* 只管本次 */ } };
  const root = document.documentElement;

  function phase(d = new Date()) {
    const h = d.getHours() + d.getMinutes() / 60;
    return h >= 5.5 && h < 8 ? 'dawn' : h >= 8 && h < 17 ? 'day' : h >= 17 && h < 19.5 ? 'dusk' : 'night';
  }
  function season(d = new Date()) {
    const m = d.getMonth() + 1;
    return m >= 3 && m <= 5 ? 'spring' : m >= 6 && m <= 8 ? 'summer' : m >= 9 && m <= 11 ? 'autumn' : 'winter';
  }
  function resolve() {
    const mode = LS('scene-time', 'auto');
    let ph, img;
    if (mode === 'theme') { img = root.dataset.theme === 'dark' ? 'night' : 'day'; ph = img; }
    else if (mode === 'day' || mode === 'night') { img = ph = mode; }
    else { ph = phase(); img = ph === 'night' ? 'night' : 'day'; }
    const sm = LS('scene-season', 'auto');
    const se = sm === 'off' ? 'off' : sm === 'auto' ? season() : sm;
    return { ph, img, se };
  }
  function apply() {
    const r = resolve();
    if (root.dataset.sceneTime !== r.img) root.dataset.sceneTime = r.img;
    if (root.dataset.scenePhase !== r.ph) root.dataset.scenePhase = r.ph;
    if (root.dataset.sceneSeason !== r.se) root.dataset.sceneSeason = r.se;
  }

  const rnd = (a, b) => a + Math.random() * (b - a);
  const KINDS = {
    spring: { n: 26, color: ['#f6c9d3', '#fbe1e6', '#ffffff'], make: (w, h) => ({ x: rnd(0, w), y: rnd(-h * .2, h), r: rnd(4, 8), vx: rnd(.2, .7), vy: rnd(.35, .8), a: rnd(0, 6.28), va: rnd(-.03, .03), shape: 'petal' }) },
    summer: { n: 22, color: ['#d9f27a', '#f8f0a0'], make: (w, h) => ({ x: rnd(0, w), y: rnd(h * .35, h), r: rnd(1.6, 3), vx: rnd(-.15, .15), vy: rnd(-.12, .12), a: rnd(0, 6.28), va: rnd(.01, .03), shape: 'glow', fire: true }) },
    autumn: { n: 22, color: ['#d98a3d', '#c4642b', '#e8b24f'], make: (w, h) => ({ x: rnd(0, w), y: rnd(-h * .2, h), r: rnd(6, 10), vx: rnd(-.3, .5), vy: rnd(.4, .9), a: rnd(0, 6.28), va: rnd(-.05, .05), shape: 'leaf' }) },
    winter: { n: 50, color: ['#ffffff', '#e7f1fb'], make: (w, h) => ({ x: rnd(0, w), y: rnd(-h * .2, h), r: rnd(1.8, 3.8), vx: rnd(-.25, .25), vy: rnd(.35, .9), a: rnd(0, 6.28), va: rnd(.01, .04), shape: 'dot' }) },
  };
  const MOTE = '#f3d98b';

  function mount(atm) {
    if (atm.dataset.fx) return; atm.dataset.fx = '1';
    const cv = document.createElement('canvas'); cv.className = 'portal-fx'; cv.setAttribute('aria-hidden', 'true'); atm.appendChild(cv);
    const tint = document.createElement('i'); tint.className = 'portal-tint'; atm.insertBefore(tint, atm.firstChild);
    const rays = document.createElement('div'); rays.className = 'portal-rays'; rays.innerHTML = '<i></i><i></i><i></i>'; atm.insertBefore(rays, tint.nextSibling);
    ['m1', 'm2'].forEach((c) => { const m = document.createElement('i'); m.className = 'portal-mist ' + c; atm.insertBefore(m, cv); });
    const ctx = cv.getContext('2d'); if (!ctx) return;
    const indoor = !atm.parentElement?.querySelector('.portal-night');   // 单图室内场景（申论政务大厅）：不飘樱叶雪、不放飞鸟，只留灵光点
    let W = 0, H = 0, parts = [], motes = [], birds = [], stars = [], shoot = null, nextShoot = Date.now() + rnd(12000, 30000), key = '', raf = 0, last = 0, nextBird = Date.now() + rnd(6000, 14000);
    const still = () => root.dataset.motion === 'reduced' || document.hidden || matchMedia('(prefers-reduced-motion: reduce)').matches;
    function size() {
      const r = atm.getBoundingClientRect(); const dpr = Math.min(2, window.devicePixelRatio || 1);
      W = Math.max(1, r.width); H = Math.max(1, r.height);
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function seed() {
      const r = resolve(); key = r.se + r.ph;
      const k = indoor ? null : KINDS[r.se];
      parts = k ? Array.from({ length: Math.round(k.n * (W < 700 ? .6 : 1)) }, () => Object.assign(k.make(W, H), { c: k.color[Math.floor(Math.random() * k.color.length)] })) : [];
      // 夏季萤火夜里才明显：白天减半
      if (r.se === 'summer' && r.ph !== 'night' && r.ph !== 'dusk') parts = parts.slice(0, 6);
      stars = r.ph === 'night' ? Array.from({ length: 34 }, () => ({ x: rnd(0, W), y: rnd(0, H * .38), r: rnd(.5, 1.3), p: rnd(0, 6.28), s: rnd(.0006, .0018) })) : [];
      motes = Array.from({ length: r.ph === 'night' ? 26 : 14 }, () => ({ x: rnd(0, W), y: rnd(H * .2, H), r: rnd(.8, 2.2), vy: -rnd(.08, .3), vx: rnd(-.08, .08), p: rnd(0, 6.28) }));
    }
    function draw(dt, t) {
      ctx.clearRect(0, 0, W, H);
      const r = resolve();
      parts.forEach((p) => {
        p.x += p.vx * dt * .06; p.y += p.vy * dt * .06; p.a += p.va * dt * .06;
        if (p.fire) { p.vx += rnd(-.01, .01); p.vy += rnd(-.01, .01); p.vx *= .98; p.vy *= .98; }
        if (p.y > H + 12 && !p.fire) { p.y = -10; p.x = rnd(0, W); } if (p.x > W + 12) p.x = -10; if (p.x < -12) p.x = W + 10;
        if (p.fire) { if (p.y < H * .3) p.vy += .02; if (p.y > H) p.vy -= .02; }
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.a); ctx.fillStyle = p.c;
        if (p.shape === 'petal') { ctx.globalAlpha = .85; ctx.beginPath(); ctx.ellipse(0, 0, p.r, p.r * .55, 0, 0, 6.28); ctx.fill(); }
        else if (p.shape === 'leaf') { ctx.globalAlpha = .85; ctx.beginPath(); ctx.moveTo(-p.r, 0); ctx.quadraticCurveTo(0, -p.r * .8, p.r, 0); ctx.quadraticCurveTo(0, p.r * .8, -p.r, 0); ctx.fill(); }
        else if (p.shape === 'glow') { const g = .35 + .65 * Math.abs(Math.sin(t / 700 + p.a * 3)); const gr = ctx.createRadialGradient(0, 0, 0, 0, 0, p.r * 4); gr.addColorStop(0, p.c); gr.addColorStop(1, 'rgba(217,242,122,0)'); ctx.globalAlpha = g * (r.ph === 'night' ? 1 : .5); ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(0, 0, p.r * 4, 0, 6.28); ctx.fill(); }
        else { ctx.globalAlpha = .9; ctx.beginPath(); ctx.arc(0, 0, p.r, 0, 6.28); ctx.fill(); }
        ctx.restore();
      });
      // 夜空：星点闪烁，偶尔划过流星
      stars.forEach((s) => { ctx.globalAlpha = .25 + .55 * Math.abs(Math.sin(t * s.s * 6 + s.p)); ctx.fillStyle = '#fff8e0'; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.28); ctx.fill(); });
      if (r.ph === 'night' && !shoot && Date.now() > nextShoot) { shoot = { x: rnd(W * .3, W * .9), y: rnd(0, H * .2), t0: t }; nextShoot = Date.now() + rnd(18000, 40000); }
      if (shoot) { const k = (t - shoot.t0) / 800; if (k > 1) shoot = null; else { const x1 = shoot.x - k * 220, y1 = shoot.y + k * 90; const g = ctx.createLinearGradient(x1, y1, x1 + 70, y1 - 28); g.addColorStop(0, 'rgba(255,248,224,0.9)'); g.addColorStop(1, 'rgba(255,248,224,0)'); ctx.globalAlpha = 1 - k; ctx.strokeStyle = g; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x1 + 70, y1 - 28); ctx.stroke(); } }
      ctx.globalAlpha = 1;
      // 金色灵光点：缓慢上浮并呼吸
      motes.forEach((m) => {
        m.x += m.vx * dt * .06 + Math.sin(t / 2000 + m.p) * .1; m.y += m.vy * dt * .06; if (m.y < -6) { m.y = H + 6; m.x = rnd(0, W); }
        const a = (.35 + .4 * Math.sin(t / 900 + m.p)) * (r.ph === 'night' ? 1 : .55);
        ctx.globalAlpha = Math.max(0, a); const gr = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, m.r * 5); gr.addColorStop(0, MOTE); gr.addColorStop(1, 'rgba(243,217,139,0)');
        ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(m.x, m.y, m.r * 5, 0, 6.28); ctx.fill();
      });
      ctx.globalAlpha = 1;
      // 飞鸟：白天偶尔掠过（几何小V）
      if (!indoor && r.ph !== 'night' && Date.now() > nextBird) { birds.push({ x: -20, y: rnd(H * .12, H * .4), v: rnd(.07, .12), s: rnd(5, 8), ph: rnd(0, 6) }); nextBird = Date.now() + rnd(14000, 30000); }
      birds = birds.filter((b) => b.x < W + 30);
      birds.forEach((b) => {
        b.x += b.v * dt; const f = Math.sin(t / 130 + b.ph) * b.s * .5;
        ctx.strokeStyle = r.ph === 'dusk' ? '#4a2f3c' : '#3a4a45'; ctx.globalAlpha = .75; ctx.lineWidth = 1.4; ctx.beginPath();
        ctx.moveTo(b.x - b.s, b.y - f); ctx.quadraticCurveTo(b.x - b.s / 3, b.y - b.s * .5 + f, b.x, b.y); ctx.quadraticCurveTo(b.x + b.s / 3, b.y - b.s * .5 + f, b.x + b.s, b.y - f); ctx.stroke();
      }); ctx.globalAlpha = 1;
    }
    function loop(ts) {
      if (!atm.isConnected) { cancelAnimationFrame(raf);resize.disconnect();return; }
      raf = requestAnimationFrame(loop);
      if (still()) { if (last) { ctx.clearRect(0, 0, W, H); last = 0; } return; }
      if (ts - last < 33) return;            // 约30帧
      const dt = last ? Math.min(100, ts - last) : 16; last = ts;
      const r = resolve(); if (key !== r.se + r.ph) seed();
      draw(dt, ts);
    }
    size(); seed(); raf = requestAnimationFrame(loop);
    const resize=new ResizeObserver(()=>{if(!atm.isConnected){resize.disconnect();cancelAnimationFrame(raf);return;}size();seed();});resize.observe(atm);
  }
  function scan() { apply(); document.querySelectorAll('.portal-atmosphere').forEach(mount); }

  apply();
  setInterval(apply, 60000);
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', apply);
  new MutationObserver(() => { if (root.dataset.theme && LS('scene-time', 'auto') === 'theme') apply(); }).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
  const start = () => { scan(); new MutationObserver(scan).observe(document.getElementById('view') || document.body, { childList: true, subtree: true }); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();

  // 设置页控件（scene_portal 设置卡里的 data-scene-fx 区域由 app 渲染后，这里监听变化）
  document.addEventListener('change', (e) => {
    const t = e.target.closest?.('[data-scene-time],[data-scene-season]'); if (!t) return;
    if (t.hasAttribute('data-scene-time')) SET('scene-time', t.value); else SET('scene-season', t.value);
    apply();
  });
  window.SCENE_FX = {
    phase, season, resolve, apply,
    settingsHtml() {
      const comp = (window.BeautyCompanion ? `<p>${BeautyCompanion.settingsHtml()}</p>` : '') + (window.BeautySway ? `<p>${BeautySway.settingsHtml()}</p>` : '');
      const o = (k, cur, list) => list.map(([v, n]) => `<option value="${v}" ${cur === v ? 'selected' : ''}>${n}</option>`).join('');
      return `<div class="portal-editor-tools"><label>场景时间<select data-scene-time>${o('t', LS('scene-time', 'auto'), [['auto', '自动（跟随时钟）'], ['day', '一直白天'], ['night', '一直夜晚'], ['theme', '跟随亮暗主题']])}</select></label>` +
        `<label>季节效果<select data-scene-season>${o('s', LS('scene-season', 'auto'), [['auto', '自动（按月份）'], ['spring', '春·落樱'], ['summer', '夏·萤火'], ['autumn', '秋·落叶'], ['winter', '冬·飘雪'], ['off', '关闭']])}</select></label></div>` + comp;
    },
  };
})();
