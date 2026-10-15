/* 3.2.x 立绘网格飘动（原型）：把对话框里的半身立绘（基础图 + 表情叠层 + 眨眼叠层）用 WebGL 画成一张可变形网格，
 * 头发、衣袖衣摆在画面两侧随“风”轻轻飘动，胸肩随呼吸起伏，头部轻微看向鼠标/倾斜方向；脸基本不动。
 * 不需要任何新素材，直接用现有立绘；表情淡入淡出、眨眼仍由 narrative.js 的 DOM 控制，这里每帧读它们的透明度来合成。
 * 任一步失败（无 WebGL、图未加载、减少动画、页面隐藏）都保持原来的 <img> 显示。开关：设置→地点排布里的勾选框（localStorage sway=0 关闭）。
 * 风的强弱在下面 PARAMS 里调。 */
(() => {
  'use strict';
  const PARAMS = { wind: 0.016, windY: 0.004, breath: 0.004, look: 0.010, fps: 30 };
  const on = () => { try { return localStorage.getItem('sway') !== '0'; } catch (e) { return true; } };
  const still = () => document.documentElement.dataset.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches;
  const VS = `attribute vec2 aUv; uniform vec4 uRect; uniform float uT; uniform vec2 uLook; uniform vec4 uP; varying vec2 vUv;
    void main(){
      vec2 s = uRect.xy + aUv * uRect.zw;
      float edge = smoothstep(0.20, 0.50, abs(s.x - 0.5));
      float low = smoothstep(0.10, 0.95, s.y);
      float amp = edge * (0.25 + 0.75 * low);
      float w = sin(uT * 1.15 + s.y * 5.0 + s.x * 2.0) + 0.5 * sin(uT * 2.3 + s.y * 9.0);
      vec2 d = vec2(w * uP.x * amp, abs(w) * uP.y * amp);
      float chest = smoothstep(0.35, 0.55, s.y) * (1.0 - smoothstep(0.75, 1.0, s.y));
      d.y -= sin(uT * 1.2) * uP.z * chest;
      float head = 1.0 - smoothstep(0.10, 0.70, s.y);
      d.x += uLook.x * uP.w * (0.3 + head); d.y += uLook.y * uP.w * 0.4 * head;
      vec2 p = s + d;
      gl_Position = vec4(p.x * 2.0 - 1.0, 1.0 - p.y * 2.0, 0.0, 1.0);
      vUv = aUv;
    }`;
  const FS = `precision mediump float; uniform sampler2D uTex; uniform float uA; varying vec2 vUv;
    void main(){ vec4 c = texture2D(uTex, vUv); gl_FragColor = c * uA; }`;

  function grid(gl, nx, ny) {
    const uv = [], idx = [];
    for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) uv.push(i / nx, j / ny);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const a = j * (nx + 1) + i, b = a + 1, c = a + nx + 1, d = c + 1; idx.push(a, b, c, b, d, c); }
    const vb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vb); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(uv), gl.STATIC_DRAW);
    const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(idx), gl.STATIC_DRAW);
    return { vb, ib, n: idx.length };
  }
  function shader(gl, type, src) { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; }

  function attach(stage) {
    if (stage.dataset.sway || !on() || still()) return; stage.dataset.sway = '1';
    const cv = document.createElement('canvas'); cv.className = 'sway-canvas'; cv.setAttribute('aria-hidden', 'true');
    let gl;
    try {
      gl = cv.getContext('webgl', { alpha: true, premultipliedAlpha: true, antialias: true });
      if (!gl) throw new Error('no webgl');
      const pr = gl.createProgram(); gl.attachShader(pr, shader(gl, gl.VERTEX_SHADER, VS)); gl.attachShader(pr, shader(gl, gl.FRAGMENT_SHADER, FS)); gl.linkProgram(pr);
      if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error('link');
      gl.useProgram(pr);
      const loc = { uv: gl.getAttribLocation(pr, 'aUv'), rect: gl.getUniformLocation(pr, 'uRect'), t: gl.getUniformLocation(pr, 'uT'), look: gl.getUniformLocation(pr, 'uLook'), p: gl.getUniformLocation(pr, 'uP'), a: gl.getUniformLocation(pr, 'uA'), tex: gl.getUniformLocation(pr, 'uTex') };
      const big = grid(gl, 16, 22), small = grid(gl, 6, 4);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
      const tex = new Map();
      const texOf = (img) => {
        if (tex.has(img)) return tex.get(img);
        if (!img.complete || !img.naturalWidth) return null;
        const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img); tex.set(img, t); return t;
      };
      const imgs = () => Array.from(stage.querySelectorAll('img'));
      const base = () => stage.querySelector('img.narrative-portrait:not(.narrative-expr)');
      stage.appendChild(cv);
      let w = 0, h = 0;
      const size = () => { const r = stage.getBoundingClientRect(), d = Math.min(2, window.devicePixelRatio || 1); w = Math.max(1, Math.round(r.width * d)); h = Math.max(1, Math.round(r.height * d)); cv.width = w; cv.height = h; };
      size(); new ResizeObserver(size).observe(stage);
      let last = 0, ready = false, bad = 0;
      const t0 = performance.now(), fail = () => { stage.classList.remove('sway-on'); cv.remove(); };
      const frame = (ts) => {
        if (!stage.isConnected) return;
        requestAnimationFrame(frame);
        if (still()) { fail(); return; }
        if (document.hidden || ts - last < 1000 / PARAMS.fps) return; last = ts;
        const bi = base(), bt = bi && texOf(bi);
        if (!bt) { if (++bad > 300) fail(); return; }
        if (!ready) { ready = true; stage.classList.add('sway-on'); }
        gl.viewport(0, 0, w, h); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
        gl.uniform1f(loc.t, (ts - t0) / 1000);
        const cs = getComputedStyle(document.documentElement);
        gl.uniform2f(loc.look, parseFloat(cs.getPropertyValue('--mx')) || 0, parseFloat(cs.getPropertyValue('--my')) || 0);
        gl.uniform4f(loc.p, PARAMS.wind, PARAMS.windY, PARAMS.breath, PARAMS.look); gl.uniform1i(loc.tex, 0);
        const draw = (img, rect, alpha, g) => {
          const t = texOf(img); if (!t || alpha <= 0.003) return;
          gl.bindTexture(gl.TEXTURE_2D, t); gl.uniform4f(loc.rect, rect[0], rect[1], rect[2], rect[3]); gl.uniform1f(loc.a, alpha);
          gl.bindBuffer(gl.ARRAY_BUFFER, g.vb); gl.enableVertexAttribArray(loc.uv); gl.vertexAttribPointer(loc.uv, 2, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, g.ib); gl.drawElements(gl.TRIANGLES, g.n, gl.UNSIGNED_SHORT, 0);
        };
        draw(bi, [0, 0, 1, 1], 1, big);
        const sr = stage.getBoundingClientRect();
        imgs().forEach((im) => {
          if (im === bi) return;
          const a = parseFloat(getComputedStyle(im).opacity);
          if (im.classList.contains('narrative-blink')) { const r = im.getBoundingClientRect(); draw(im, [(r.left - sr.left) / sr.width, (r.top - sr.top) / sr.height, r.width / sr.width, r.height / sr.height], a, small); }
          else draw(im, [0, 0, 1, 1], a, big);
        });
      };
      requestAnimationFrame(frame);
    } catch (e) { stage.classList.remove('sway-on'); cv.remove(); stage.dataset.sway = 'off'; }
  }
  const scan = (root) => (root.querySelectorAll ? root : document).querySelectorAll('.narrative-stage:not([data-sway])').forEach(attach);
  const start = () => { scan(document); new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => { if (n.nodeType === 1) { if (n.matches?.('.narrative-stage')) attach(n); else scan(n); } }))).observe(document.documentElement, { childList: true, subtree: true }); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  document.addEventListener('change', (e) => { if (e.target.matches?.('[data-sway-toggle]')) { try { localStorage.setItem('sway', e.target.checked ? '1' : '0'); } catch (err) { /* ok */ } } });
  window.BeautySway = { on, PARAMS, settingsHtml: () => `<label class="small"><input type="checkbox" data-sway-toggle ${on() ? 'checked' : ''} style="width:auto"> 立绘头发衣摆飘动（对话框，下次打开生效）</label>` };
})();
