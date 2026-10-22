/* 3.3.7：固定满高研习、默认双栏及本机阅读位置、稳定地图/慢请求竞态。
   临时自编资料+假HOME，不读真实资料，不连接AI；电脑与平板。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1],service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--art-fixture'],{env:process.env});
let browser,active,logs='';service.stderr.on('data',x=>logs+=x);
const ready=new Promise((ok,no)=>{let text='';const timer=setTimeout(()=>no(Error(logs||'服务启动超时')),20000);service.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});service.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
const out=path.resolve('ui-artifacts/layout337');
async function position(p){return p.evaluate(()=>{const k=Object.keys(localStorage).find(k=>k.startsWith('mindmap-reading-v1:')&&k.includes(encodeURIComponent('自编阅读导图')));return k?JSON.parse(localStorage[k]):null;});}
async function graph(p){return p.locator('#lnCanvas svg>g').first().getAttribute('transform');}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const sizes=process.argv.find(a=>a.startsWith('--sizes='))?.split('=')[1]?.split(',');
 for(const [size,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]].filter(([size])=>!sizes||sizes.includes(size))){
  const p=await browser.newPage({viewport});active=p;const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(()=>{window.__intervals=[];const raw=setInterval;window.setInterval=(f,ms,...args)=>{__intervals.push({f,ms});return raw(f,ms,...args);};});
  await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());await p.waitForSelector('.portal-stage');
  assert(await p.evaluate(async()=>{const stage=document.querySelector('.portal-stage'),img=stage.querySelector('img');dispatchEvent(new Event('resize'));dispatchEvent(new Event('resize'));await new Promise(ok=>requestAnimationFrame(()=>requestAnimationFrame(ok)));return stage===document.querySelector('.portal-stage')&&img===stage.querySelector('img');}),'尺寸事件保留原地图与图片');
  assert(await p.evaluate(()=>{const h=document.querySelector('#studyHud .study-hud-player');STUDY_HUD.refresh();updatePill();return h===document.querySelector('#studyHud .study-hud-player');}),'同值后台刷新保留HUD节点');
  // 真实心跳回调不操作页面也会触发：返回未变化数据时不重建地图。
  assert(await p.evaluate(async()=>{const stage=document.querySelector('.portal-stage');const beat=__intervals.find(x=>x.ms===BEAT*1000);await beat.f();await beat.f();return stage===document.querySelector('.portal-stage');}));
  let release,seen;const gate=new Promise(ok=>release=ok),held=new Promise(ok=>seen=ok);
  await p.route('**/api/settings',async route=>{if(route.request().method()==='GET'){seen();await gate;}await route.continue();});
  await p.evaluate(()=>{window.__pendingRoute=go('settings');});await held;
  assert(await p.locator('.portal-world').isVisible(),'慢请求时旧地图保持可见');assert(await p.locator('body').evaluate(e=>e.classList.contains('portal-home')),'不提前撤掉旧地图样式');
  await p.evaluate(()=>go('bank'));release();await p.evaluate(()=>__pendingRoute);await p.unroute('**/api/settings');
  if(subject==='申论')assert.equal(await p.locator('#sSave').count(),0);else assert(await p.locator('.trial-hall').isVisible(),'旧设置响应不能覆盖新塔景');
  const board=subject==='行测'?'逻辑填空':await p.evaluate(()=>DASH.tree[0].board),region=subject==='行测'?'yan':'board-0';
  await p.evaluate(async board=>{
   await api('/api/cards/add',{deck:board,type:'问答',front:'自编条件是什么？',back:'说明边界。'});
   const root={data:{text:'自编知识整理'},children:Array.from({length:65},(_,i)=>({data:{text:'自编方法'+i+'：先核对条件，再说明适用边界。'},children:[]}))};
   const list=await api('/api/mindmap');if(!list.boards.some(b=>b.board===board&&b.maps.some(m=>m.name==='自编阅读导图')))await api('/api/mindmap/create',{board,name:'自编阅读导图',data:{root}});
  },board);
  await p.evaluate(async region=>{STUDY_REGIONS.select(region);await go('train');},region);await p.locator('.fx-region-work').waitFor();
  assert.equal(await p.locator('[data-study-regions-back]').count(),0);assert(await p.locator('.subpage-place').innerText().then(s=>s.includes(subject==='行测'?'辨言峰':board)));
  const geometry=await p.evaluate(()=>{const a=document.querySelector('.fx-region-work').getBoundingClientRect(),v=document.querySelector('#view').getBoundingClientRect(),h=document.querySelector('#studyHud').getBoundingClientRect(),cards=[...document.querySelectorAll('.fx-region-work>.card')].map(e=>({height:e.clientHeight,scroll:e.scrollHeight}));return {top:a.top,bottom:a.bottom,viewBottom:v.bottom,hudBottom:h.bottom,cards};});
  if(subject==='行测'){
   const panel=await p.locator('.fx-scenic-peak').boundingBox();
   assert(panel.width<viewport.width*.95&&panel.height<viewport.height*.8,'四峰选择页收拢、留出山景 '+JSON.stringify(panel));
   assert(geometry.top>geometry.hudBottom+24&&geometry.bottom<geometry.viewBottom-24,'四峰上下留景 '+JSON.stringify(geometry));
  }else assert(Math.abs(geometry.bottom-geometry.viewBottom)<20&&Math.abs(geometry.top-geometry.hudBottom)<24,'资料用满顶栏下工作区 '+JSON.stringify(geometry));
  assert(geometry.cards.every(c=>c.height>100));
  if(process.argv.includes('--shots')&&size==='tablet'){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,(subject||'法考')+'-region.png')});}
  // 两峰请求乱序时，温简范围也必须跟随当前页面，不能被旧全局scope覆盖。
  const secondBoard=subject==='行测'?'数量关系':await p.evaluate(()=>DASH.tree[1].board),secondRegion=subject==='行测'?'shu':'board-1';
  await p.evaluate(async b=>api('/api/cards/add',{deck:b,type:'问答',front:'自编第二分区的条件？',back:'第二分区的答案。'}),secondBoard);
  let releaseCards,seenCards;const cardsGate=new Promise(ok=>releaseCards=ok),cardsHeld=new Promise(ok=>seenCards=ok);
  await p.route('**/api/cards',async route=>{const request=route.request(),body=request.method()==='POST'?request.postDataJSON():{};if(body?.scope?.includes(board)){seenCards();await cardsGate;}await route.continue();});
  await p.evaluate(r=>{STUDY_REGIONS.select(r);window.__oldPeak=go('train');},region);await cardsHeld;
  await p.evaluate(async r=>{STUDY_REGIONS.select(r);await go('train');},secondRegion);releaseCards();await p.evaluate(()=>__oldPeak);await p.unroute('**/api/cards');
  await p.locator('button[data-yjgo=""]').click();await p.locator('#yjShow').waitFor();assert((await p.locator('.yj-stage').textContent()).includes('自编第二分区'),'当前峰温简不得串到旧峰');await p.locator('#yjBack').click();await p.locator('.yj-stage').waitFor({state:'detached'});
  await p.evaluate(async r=>{STUDY_REGIONS.select(r);await go('train');},region);
  await p.locator('[data-ln]').first().click();await p.locator('#lnCanvas svg>g').first().waitFor();assert.equal(await p.locator('.ln-reading-body').getAttribute('data-mode'),'split');assert(await p.locator('#lnMarkdown').isVisible());assert.equal(await p.locator('#lnFile,#lnLayout').count(),0);assert.equal(await p.locator('.yj-top>.ln-reading-tabs').count(),1,'阅读工具并入图名同一栏');assert(await p.locator('.yj-top').evaluate(e=>{const a=e.getBoundingClientRect(),b=e.querySelector('.ln-reading-tabs').getBoundingClientRect();return b.top>=a.top&&b.bottom<=a.bottom+1;}));
  const reader=await p.locator('.ln-stage').boundingBox();
  const hudBottom=await p.locator('#studyHud').evaluate(e=>e.getBoundingClientRect().bottom);
  assert(reader.width>=viewport.width-2&&Math.abs(reader.y-hudBottom)<2&&Math.abs(reader.y+reader.height-viewport.height)<2,'实际阅读器用满顶栏下工作区 '+JSON.stringify(reader));
  await p.locator('#lnMarkdown').evaluate(e=>e.scrollTop=850);const canvas=await p.locator('#lnCanvas').boundingBox();await p.mouse.move(canvas.x+canvas.width*.5,canvas.y+canvas.height*.5);await p.mouse.wheel(0,-350);
  await p.waitForFunction(()=>Object.keys(localStorage).some(k=>k.startsWith('mindmap-reading-v1:')&&JSON.parse(localStorage[k]).top>100));
  await p.waitForTimeout(230);const saved=await position(p),matrix=await graph(p);assert(saved.view&&saved.top>100);
  await p.locator('[data-ln-mode=document]').click();await p.locator('[data-ln-mode=split]').click();await p.waitForTimeout(100);assert.equal(await graph(p),matrix,'切换显示方式不重新适应整幅图');
  await p.locator('#lnBack').click();await p.locator('.ln-stage').waitFor({state:'detached'});await p.locator('[data-ln]').first().click();await p.locator('#lnCanvas svg>g').first().waitFor();await p.waitForTimeout(200);
  assert.equal(await p.locator('.ln-reading-body').getAttribute('data-mode'),'split');assert(Math.abs(await p.locator('#lnMarkdown').evaluate(e=>e.scrollTop)-saved.top)<2,'重开恢复文档位置');assert.equal(await graph(p),matrix,'重开恢复导图位置与缩放');
  await p.reload();await p.waitForFunction(()=>!!window.DASH_REF?.());await p.evaluate(async board=>MINDMAP.open(board,'自编阅读导图',false),board);await p.locator('#lnCanvas svg>g').first().waitFor();await p.waitForTimeout(200);assert(Math.abs(await p.locator('#lnMarkdown').evaluate(e=>e.scrollTop)-saved.top)<2,'刷新应用也保留阅读位置');assert.equal(await graph(p),matrix);
  if(process.argv.includes('--shots')&&size==='tablet'){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,(subject||'法考')+'-split.png')});}
  assert.deepEqual(errors,[]);await p.close();console.log((subject||'法考')+' '+size+'：地图保留、后台心跳、慢请求竞态、选择页布局、全屏阅读、双栏及阅读位置恢复通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+(subject||'法考')+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exit(1);});
