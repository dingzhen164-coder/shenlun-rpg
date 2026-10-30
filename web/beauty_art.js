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
  const PEAK_NAMES = ['万象峰', '辨言峰', '明理峰', '演数峰', '观星峰'];
  const ACADEMY_NAMES = ['民法','刑法','民诉','刑诉','行政法','商经知','三国法','理论法'];
  // 法考：只有营地、试炼塔（塔前全景+选择厅）、咒文书馆、魔法手记有新的独立昼/夜场景（没有黄昏图：黄昏用白天图+程序调色）。
  const ROOMS_FAKAO=['dwelling','bank','skeleton','notes'];
  const ROOMS381=['dwelling','bank','contest','skeleton','tianji','settings'];
  // 科目守卫用转义：申论wording会改写源码中的“行测”字面量，不能让专属场景误启用。
  const isXingce=()=>{try{return (typeof DASH!=='undefined'?DASH.subject:'')==='\u884c\u6d4b';}catch(_){return false;}};
  const isFakao=()=>{try{return (typeof DASH!=='undefined'?DASH.subject:'')==='\u6cd5\u8003';}catch(_){return false;}};
  const isShenlun=()=>{try{return (typeof DASH!=='undefined'?DASH.subject:'')==='\u7533\u8bba';}catch(_){return false;}};
  const SL_ROOMS=['dwelling','bank','contest','train','skeleton','tianji','settings'];
  // 训练题型仍沿用各自的独立场景，只有大厅使用整体背景。
  const isSlRoom=(page)=>isShenlun()&&SL_ROOMS.includes(page)&&(page!=='train'||!REGION_KEY[regionName()]);
  const phase=()=>document.documentElement.dataset.scenePhase||document.documentElement.dataset.sceneTime||'day';
  const regionName = () => { try { return window.STUDY_REGIONS ? STUDY_REGIONS.title() : ''; } catch (e) { return ''; } };
  const tabLabel = () => { const t = document.querySelector('.fx-tab[aria-selected="true"]'); return t ? t.textContent.trim() : ''; };
  let view = '', applied='';
  function findHit(page, dn=document.documentElement.dataset.scenePhase==='dusk'?'dusk':document.documentElement.dataset.sceneTime || 'day') {
    if(isSlRoom(page)){
      const other=dn==='dusk'?['day','night']:[dn==='night'?'day':'night'];
      const tk=page==='dwelling'?TAB_KEY[tabLabel()]:'';
      const own=[...(tk?[`beauty/page/dwelling-${tk}-${dn}.webp`,`beauty/page/dwelling-${tk}.webp`,...other.map(t=>`beauty/page/dwelling-${tk}-${t}.webp`)]:[]),`beauty/page/${page}-${dn}.webp`,`beauty/page/${page}.webp`,...other.map(t=>`beauty/page/${page}-${t}.webp`)];
      const override=own.find(r=>custom.has(r)&&has(r));
      if(override)return override;
      const built=`beauty/page/${page}-${dn}.webp`;
      if(has(built))return built;
    }
    if((isXingce()&&ROOMS381.includes(page))||(isFakao()&&ROOMS_FAKAO.includes(page))){
      const p=page==='bank'&&phase()==='dawn'&&isXingce()?'dawn':dn;
      // 明确的专用覆盖仍优先；旧内置洞府页签不能抢过新整体分时场景。
      const own=[`beauty/page/${page}-${p}.webp`].find(r=>custom.has(r)&&has(r));
      if(own)return own;
      if(has(`beauty/page/${page}-${p}.webp`))return `beauty/page/${page}-${p}.webp`;
    }
    const others=dn==='dusk'?['day','night']:[dn==='night'?'day':'night'], want = [], fallback=[];
    if (page && page !== 'home') {
      const tk = page === 'dwelling' ? TAB_KEY[tabLabel()] : '';              // 洞府每个页签可单独配背景，没有就回退洞府整体背景
      if (tk) {want.push(`beauty/page/dwelling-${tk}-${dn}.webp`, `beauty/page/dwelling-${tk}.webp`);fallback.push(...others.map(t=>`beauty/page/dwelling-${tk}-${t}.webp`));}
      const rk = page === 'train' ? REGION_KEY[regionName()] : '';          // 修炼页选中某个分区（五峰等）时可单独配背景
      // 独立分区的背景只在本分区选择；通用“修炼”图不覆盖五峰或八科楼。
      if (rk && [...PEAK_NAMES,...ACADEMY_NAMES].includes(regionName())) {
        const own=[`beauty/page/train-${rk}-${dn}.webp`, `beauty/page/train-${rk}.webp`, ...others.map(t => `beauty/page/train-${rk}-${t}.webp`)];
        return own.find(r => custom.has(r) && has(r)) || own.find(has);
      }
      if (rk) {want.push(`beauty/page/train-${rk}-${dn}.webp`, `beauty/page/train-${rk}.webp`);fallback.push(...others.map(t=>`beauty/page/train-${rk}-${t}.webp`));}
      want.push(`beauty/page/${page}-${dn}.webp`, `beauty/page/${page}.webp`);fallback.push(...others.map(t=>`beauty/page/${page}-${t}.webp`));
      want.push(...fallback);
    }
    // 用户给的整页背景也应优先于随包的分区/页签背景。
    return want.find(r => custom.has(r) && has(r)) || want.find(has);
  }
  const decoded=new Map();
  function decode(src){if(!decoded.has(src))decoded.set(src,new Promise(resolve=>{const img=new Image();img.onload=()=>{if(img.decode)img.decode().then(()=>resolve(true),()=>resolve(false));else resolve(true);};img.onerror=()=>resolve(false);img.src=src;}));return decoded.get(src);}
  // 进页面前只等“这一页现在要显示的图”；另一时段（夜/昼）的图过一会儿再悄悄下，不拖慢进门。
  function prepare(page,quiet){const hit=findHit(page),urls=hit?[url(hit)]:[],extra=[];
    const opposite=findHit(page,document.documentElement.dataset.sceneTime==='night'?'day':'night');if(opposite&&opposite!==hit)extra.push(url(opposite));
    if((isXingce()||isFakao())&&page==='bank'){const selection=selectionArt();if(selection)urls.push(url(selection));}
    const examScene=!(typeof isSL==='function'&&isSL());
    // 行测的试炼塔是一整张画（hall），三层拆件图只有法考版在用，不再白下近8MB。
    if(page==='bank'&&examScene&&!isXingce()&&!isFakao())urls.push(...['tower','gate','landscape'].map(k=>has(`beauty/trial/${k}-night.webp`)&&document.documentElement.dataset.sceneTime==='night'?url(`beauty/trial/${k}-night.webp`):`assets/beauty/trial/${k}.png`));
    if(page==='contest'&&examScene)urls.push('assets/beauty/contest/arena.png');
    if(!quiet&&extra.length)setTimeout(()=>extra.forEach(decode),2500);
    return Promise.all(urls.map(decode));
  }
  // 软件打开、首页画出来之后，空闲时把常去的地点背景一张张提前下好并解码（只下当前时段那一张）；之后点进去就不用再等。
  // 浏览器缓存靠服务器的 ETag：图没换就不重下。省流量模式、或还在处理别的事时不抢带宽。
  let warmed='';
  const WARM_PAGES=['bank','skeleton','contest','dwelling','notes','tianji'];
  function warm(){
    const key=phase()+'/'+(isXingce()?'x':'o');if(warmed===key)return;warmed=key;
    try{if(navigator.connection?.saveData)return;}catch(_){}
    const idle=fn=>(window.requestIdleCallback?requestIdleCallback(fn,{timeout:4000}):setTimeout(fn,300));
    const queue=[...WARM_PAGES.map(pg=>()=>prepare(pg,true)),
      // 五峰没有清晨专图，预加载与实际显示一样回退白天；试炼塔仍用自己的清晨图。
      ()=>Promise.all(PEAK_NAMES.map(n=>{const imagePhase=phase()==='dawn'?'day':phase(),r=`beauty/page/train-${REGION_KEY[n]}-${imagePhase}.webp`;return has(r)?decode(url(r)):null;})),
      ()=>fetch('political_atlas.html').then(r=>r.text()).then(t=>Promise.all([...t.matchAll(/(?:src|href)="([^":]+\.(?:js|css))"/g)].map(m=>fetch(m[1]).then(r=>r.arrayBuffer())))).catch(()=>0)];
    const step=()=>{if(warmed!==key)return;const job=queue.shift();if(!job)return;idle(()=>{Promise.resolve().then(job).catch(()=>0).then(()=>setTimeout(step,400));});};
    step();
  }
  // 选择厅图：优先当前时段，缺了（法考没有黄昏/清晨）就用当前白天/夜晚那张。
  function selectionArt(){return [`beauty/trial/selection-${phase()}.webp`,`beauty/trial/selection-${document.documentElement.dataset.sceneTime==='night'?'night':'day'}.webp`].find(r=>has(r))||'';}
  function heroFor(page){const hit=findHit(page);return hit?url(hit):'';}
  function apply(){const b=document.body;if(!b)return;let hit=findHit(view);
    // 五峰是独立地点，不再被旧全局背景压住；专门设置的峰/页背景仍优先。
    const peakScene=view==='train'&&PEAK_NAMES.includes(regionName());
    const roomScene=view==='train'&&b.classList.contains('academy-room');
    const independent=(isXingce()&&ROOMS381.includes(view))||(isFakao()&&ROOMS_FAKAO.includes(view))||isSlRoom(view),nativeRoom=independent&&hit&&(!custom.has(hit)||/-(day|dusk|night|dawn)\.webp$/.test(hit));
    // 当前时段没有专图（法考黄昏只有白天/夜晚图）：用邻近时段的图，并保留程序调色，不能当成“原生光照”。
    const curDn=document.documentElement.dataset.scenePhase==='dusk'?'dusk':document.documentElement.dataset.sceneTime||'day';
    const hitPhase=(String(hit||'').match(/-(day|dusk|night|dawn)\.webp$/)||[])[1];
    const phaseOk=!nativeRoom||!hitPhase||hitPhase===curDn;
    if(hit&&!custom.has(hit)&&b.classList.contains('has-bg')&&!peakScene&&!roomScene&&!independent)hit='';
    // 专用夜景/黄昏不重复调色；单张图与用户全局图使用程序光照。
    b.dataset.sceneRelight=(hit?(peakScene||(nativeRoom&&phaseOk)||/(?:-night|-dusk)\.webp$/.test(hit)):!b.classList.contains('has-bg')&&document.documentElement.dataset.sceneTime==='night')?'native':'synthetic';
    // 五峰自己的昼/昏/夜画面按原图显示：不再叠整页遮罩（遮罩会把浅色洗白、深色压成灰黑）。
    if(hit&&peakScene)b.dataset.sceneArt='peak';else if(nativeRoom)b.dataset.sceneArt=isShenlun()?'roomSL4k':'room381';else delete b.dataset.sceneArt;
    if(isXingce()&&independent&&view==='bank'&&hit){
      const src=url(hit),img=document.querySelector('.th-panorama');
      b.style.setProperty('--scene381-tower',`url("${src}")`);
      if(img&&img.getAttribute('src')!==src)decode(src).then(ok=>{if(ok&&img.isConnected&&findHit(view)===hit){img.src=src;img.dataset.native381='true';}});
      const selection=selectionArt();
      if(selection){b.style.setProperty('--scene381-selection',`url("${url(selection)}")`);b.dataset.sceneSelection='native381';}
      else{b.style.removeProperty('--scene381-selection');delete b.dataset.sceneSelection;}
    }else delete b.dataset.sceneSelection;
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
    new MutationObserver(()=>{if(warmed)warm();}).observe(document.documentElement, { attributes: true, attributeFilter: ['data-scene-time','data-scene-phase'] });   // 昼夜换了：把新时段的图接着预下
    readView();
    const v = document.getElementById('view'); let q = 0;                    // 洞府切页签时更新背景
    if (v) new MutationObserver(() => { if (!q) { q = 1; queueMicrotask(() => { q = 0; apply(); }); } }).observe(v, { attributes: true, attributeFilter: ['aria-selected'], subtree: true, childList: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  window.BeautyArt = { prepare, warm, heroFor, mount(page){view=page;apply();}, has, url, files: () => Array.from(F.keys()) };
})();
