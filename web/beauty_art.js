/* 美术文件夹（rpg/art.py）的前端部分：服务器在 index.html 里注入 window.ART_FILES（库里 训练/外观/美术/ 有哪些覆盖文件及修改时间）。
 * 1) 子地图背景：当前页（洞府、修炼、试炼塔…）若有 beauty/page/<页>-day|night.webp 或 <页>.webp，就把它当作这一页背后的背景（按统一场景时钟选-day/-night，缺项使用无后缀或另一时段单图并调色），
 *    没有就用程序默认的淡透全景；覆盖图本身给得更清晰，遮罩调淡。
 * 2) BeautyArt.has / url：给别的脚本判断某个资源是否被覆盖（申论首页夜景用）。
 * 首页全景、人物立绘、音乐、音效不需要前端处理：它们请求的原路径会被服务器直接换成美术文件夹里的文件。 */
(() => {
  'use strict';
  const F = new Map((Array.isArray(window.ART_FILES) ? window.ART_FILES : []).map((x) => [x[0], x[1]]));
  const custom = new Set(Array.isArray(window.ART_CUSTOM) ? window.ART_CUSTOM : F.keys());
  const has = (r) => F.has(r), url = (r) => 'assets/' + r + '?v=' + F.get(r);
  // 洞府页签名 → key（与 rpg/art.py 的 DWELLING_TABS 对应）
  const TAB_KEY = { '修为与突破': 'growth', '仕途与晋升': 'growth', '成长与晋升': 'growth', '十二经': 'shier', '修行记录': 'records', '学习记录': 'records', '储物袋': 'bag', '修行日志': 'diary', '学时与出勤': 'daily', '时辰与日课': 'daily' };
  const REGION_KEY = { '万象峰': 'chang', '辨言峰': 'yan', '明理峰': 'li', '演数峰': 'shu', '观星峰': 'zi', '归纳概括': 'guina', '综合分析': 'zonghe', '提出对策': 'duice', '贯彻执行': 'guanche', '大作文': 'dazuowen',
    '民法': 'minfa', '刑法': 'xingfa', '民诉': 'minsu', '刑诉': 'xingsu', '行政法': 'xingzheng', '商经知': 'shangjing', '三国法': 'sanguo', '理论法': 'lilun' };
  const regionName = () => { try { return window.STUDY_REGIONS ? STUDY_REGIONS.title() : ''; } catch (e) { return ''; } };
  const tabLabel = () => { const t = document.querySelector('.fx-tab[aria-selected="true"]'); return t ? t.textContent.trim() : ''; };
  let view = '', applied='';
  function findHit(page, dn=document.documentElement.dataset.scenePhase==='dusk'?'dusk':document.documentElement.dataset.sceneTime || 'day') {
    const others=dn==='dusk'?['day','night']:[dn==='night'?'day':'night'], want = [], fallback=[];
    if (page && page !== 'home') {
      const tk = page === 'dwelling' ? TAB_KEY[tabLabel()] : '';              // 洞府每个页签可单独配背景，没有就回退洞府整体背景
      if (tk) {want.push(`beauty/page/dwelling-${tk}-${dn}.webp`, `beauty/page/dwelling-${tk}.webp`);fallback.push(...others.map(t=>`beauty/page/dwelling-${tk}-${t}.webp`));}
      const rk = page === 'train' ? REGION_KEY[regionName()] : '';          // 修炼页选中某个分区（五峰等）时可单独配背景
      if (rk) {want.push(`beauty/page/train-${rk}-${dn}.webp`, `beauty/page/train-${rk}.webp`);fallback.push(...others.map(t=>`beauty/page/train-${rk}-${t}.webp`));}
      want.push(`beauty/page/${page}-${dn}.webp`, `beauty/page/${page}.webp`);fallback.push(...others.map(t=>`beauty/page/${page}-${t}.webp`));
      want.push(...fallback);
    }
    // 用户给的整页背景也应优先于随包的分区/页签背景。
    return want.find(r => custom.has(r) && has(r)) || want.find(has);
  }
  const decoded=new Map();
  function decode(src){if(!decoded.has(src))decoded.set(src,new Promise(resolve=>{const img=new Image();img.onload=()=>{if(img.decode)img.decode().catch(()=>{}).then(resolve);else resolve();};img.onerror=()=>resolve();img.src=src;}));return decoded.get(src);}
  function prepare(page){const hit=findHit(page),urls=hit?[url(hit)]:[];
    const opposite=findHit(page,document.documentElement.dataset.sceneTime==='night'?'day':'night');if(opposite&&opposite!==hit)urls.push(url(opposite));
    const examScene=!(typeof isSL==='function'&&isSL());
    if(page==='bank'&&examScene)urls.push(...['tower','gate','landscape'].map(k=>has(`beauty/trial/${k}-night.webp`)&&document.documentElement.dataset.sceneTime==='night'?url(`beauty/trial/${k}-night.webp`):`assets/beauty/trial/${k}.png`));
    if(page==='contest'&&examScene)urls.push('assets/beauty/contest/arena.png');
    return Promise.all(urls.map(decode));
  }
  function apply(){const b=document.body;if(!b)return;let hit=findHit(view);
    // 五峰是独立地点，不再被旧全局背景压住；专门设置的峰/页背景仍优先。
    const peakScene=view==='train'&&['万象峰','辨言峰','明理峰','演数峰','观星峰'].includes(regionName());
    if(hit&&!custom.has(hit)&&b.classList.contains('has-bg')&&!peakScene)hit='';
    // 专用夜景/黄昏不重复调色；单张图与用户全局图使用程序光照。
    b.dataset.sceneRelight=(hit?/(?:-night|-dusk)\.webp$/.test(hit):!b.classList.contains('has-bg')&&document.documentElement.dataset.sceneTime==='night')?'native':'synthetic';
    b.dataset.sceneRoom=['dwelling','skeleton','notes','settings'].includes(view)||b.classList.contains('guantu')?'indoor':'outdoor';
    // 原建筑节点原位换图，不重建练习卷宗；缺夜图或旧用户建筑覆盖仍沿兼容光照。
    const trialNight=document.documentElement.dataset.sceneTime==='night'&&['tower','gate','landscape'].every(k=>has(`beauty/trial/${k}-night.webp`)&&!custom.has(`beauty/trial/${k}.png`));
    b.dataset.trialNight=String(trialNight);
    if(trialNight)b.style.setProperty('--trial-night-art',`url("${url('beauty/trial/landscape-night.webp')}")`);
    document.querySelectorAll?.('[data-night-art]').forEach(img=>{
      const next=trialNight?url(img.dataset.nightArt):img.dataset.dayArt;
      if(img.getAttribute('src')!==next)img.setAttribute('src',next);
    });
    if(applied===(hit||''))return;applied=hit||'';
    if(hit){b.style.setProperty('--ds-page-art',`url("${url(hit)}")`);b.classList.add('has-page-art');}
    else{b.style.removeProperty('--ds-page-art');b.classList.remove('has-page-art');}
  }
  function readView() {                                                       // 当前页取 app.js 的 VIEW（试炼塔 bank 等不在顶栏里，不能靠顶栏判断）
    let v = ''; try { v = typeof VIEW !== 'undefined' ? VIEW : ''; } catch (e) { v = ''; }
    if (v !== view) { view = v; apply(); }
  }
  const start = () => {
    new MutationObserver(apply).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme','data-scene-time','data-scene-phase'] });
    new MutationObserver(apply).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    readView();
    const v = document.getElementById('view'); let q = 0;                    // 洞府切页签时更新背景
    if (v) new MutationObserver(() => { if (!q) { q = 1; queueMicrotask(() => { q = 0; apply(); }); } }).observe(v, { attributes: true, attributeFilter: ['aria-selected'], subtree: true, childList: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  window.BeautyArt = { prepare, mount(page){view=page;apply();}, has, url, files: () => Array.from(F.keys()) };
})();
