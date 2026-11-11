/* 旧内核兜底与“镂空”淡底框（2026-11-11 用户反馈：安卓平板上万象峰研读的顶栏、正文底板全透明，字压在风景上；电脑/iPad 正常）。
   同一页面分别走正常路径和 ?legacycss=1 强制兜底，逐个比较镂空外壳、纸面、研习目录、研读正文、时政工具条的实际底色：
   颜色差 ≤4、透明度差 ≤0.03；再调设置里的透明度，兜底路径跟着变；深色主题同样比较。自编资料、隔离临时库。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const server=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测','--politics-fixture'],{env:process.env});let logs='';server.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let text='';const timer=setTimeout(()=>no(Error(logs)),30000);server.stdout.on('data',b=>{text+=b;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});server.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
// 把 rgb()/rgba()/color(srgb …) 统一成 [r,g,b,a]
const PARSE=`(c)=>{let m=c.match(/^color\\(srgb ([\\d.e-]+) ([\\d.e-]+) ([\\d.e-]+)(?: \\/ ([\\d.e-]+))?\\)$/);if(m)return [m[1]*255,m[2]*255,m[3]*255,m[4]==null?1:+m[4]];m=c.match(/rgba?\\(([\\d.]+), ([\\d.]+), ([\\d.]+)(?:, ([\\d.]+))?\\)/);return m?[+m[1],+m[2],+m[3],m[4]==null?1:+m[4]]:null;}`;
async function colors(target,selectors){return target.evaluate(([sels,parse])=>{const P=eval(parse);const out={};for(const s of sels){const e=[...document.querySelectorAll(s)].find(x=>x.offsetParent!==null||getComputedStyle(x).position==='fixed');if(e)out[s]=P(getComputedStyle(e).backgroundColor);}return out;},[selectors,PARSE]);}
function same(a,b,label){for(const k of Object.keys(a)){assert(b[k],`${label} 兜底路径缺少 ${k}`);const x=a[k],y=b[k];
  if(x[3]<0.02){assert(y[3]<0.05,`${label} ${k} 应透明 ${y}`);continue;}
  assert(Math.abs(x[3]-y[3])<=0.03,`${label} ${k} 透明度不同：正常 ${x[3].toFixed(3)} 兜底 ${y[3].toFixed(3)}`);
  for(let i=0;i<3;i++)assert(Math.abs(x[i]-y[i])<=4,`${label} ${k} 颜色不同：正常 ${x.map(Math.round)} 兜底 ${y.map(Math.round)}`);}}
async function atlas(page){await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();await page.locator('[data-wx-exam]').first().click();
 const f=page.frameLocator('.wx-atlas-frame');await f.locator('#nav [data-go=sprint]').click();await f.locator('.sprint-workspace').waitFor();await f.locator('[data-material=m1]').click();await f.locator('.sprint-document-body').waitFor();await page.waitForTimeout(500);
 return page.frames().find(x=>/political_atlas/.test(x.url()));}
const HOME=['#studyHud .subpage-tools','.hx381-shell','.hx381-paper','.fx-panel','.card','.study-hud-player','.study-hud-world'];
const ATLAS=['.sprint-index','.sprint-document-body','.atlas-toolbar','.atlas-reading-tools'];
(async()=>{let browser;try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,width,height] of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]])for(const theme of ['light','dark']){
  const result={};
  for(const mode of ['modern','legacy']){
   const page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(t=>{try{localStorage.setItem('theme',t);}catch(_){}},theme);
   await page.goto(base+(mode==='legacy'?'/?legacycss=1':'/'));await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&DASH);
   if(mode==='legacy')assert(await page.evaluate(()=>document.documentElement.classList.contains('legacy-css')),'走了兜底路径');
   await page.evaluate(()=>go('dwelling'));await page.waitForTimeout(900);
   result[mode]={home:await colors(page,HOME)};
   const frame=await atlas(page);
   if(mode==='legacy')assert(await frame.evaluate(()=>document.documentElement.classList.contains('legacy-css')),'时政地图也走兜底');
   result[mode].atlas=await colors(frame,ATLAS);
   // 设置里的透明度滑块：兜底路径同样跟着变
   await page.evaluate(()=>{document.documentElement.style.setProperty('--interface-panel-alpha','80%');document.documentElement.style.setProperty('--interface-inner-alpha','48%');});
   await page.evaluate(()=>go('dwelling'));await page.waitForTimeout(600);
   result[mode].alpha=await colors(page,['.hx381-shell']);
   assert.deepEqual(errors,[],`${mode} 脚本报错`);await page.close();
  }
  assert(Object.keys(result.modern.home).length>=2&&Object.keys(result.modern.atlas).length>=2,'找到了要比较的框 '+JSON.stringify(Object.keys(result.modern.home))+JSON.stringify(Object.keys(result.modern.atlas)));
  same(result.modern.home,result.legacy.home,`${size}/${theme} 住处`);
  same(result.modern.atlas,result.legacy.atlas,`${size}/${theme} 万象峰研读`);
  same(result.modern.alpha,result.legacy.alpha,`${size}/${theme} 透明度滑块`);
  console.log(`旧内核淡底框 ${size}/${theme}：与正常路径一致`);
 }
}finally{await browser?.close();server.kill();}})().catch(e=>{console.error(e);process.exit(1);});
