/* 第二批：真实临时库HTTP接口 + DOM交互，卡片证据来自原复习接口，不伪造完成。
   无AI、隔离设置；覆盖按钮、撤销、并发/幂等、陈列/恢复。jsdom不替代浏览器布局。 */
const {JSDOM}=require('jsdom'),{spawn}=require('node:child_process');
const fs=require('node:fs'),assert=require('node:assert/strict');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--journey-fixture'],{env:process.env});
let logs='',out='',dom;srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error(logs||'临时库未启动')),20000);
  srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
  srv.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出 '+c+' '+logs));});});
const tick=()=>new Promise(r=>setTimeout(r,10));
async function until(fn){for(let n=0;n<300;n++){if(fn())return;await tick();}throw Error('DOM等待超时');}
(async()=>{
 try{
  const base=await ready;
  const api=async(path,body)=>{const r=await fetch(new URL(path,base),body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await r.json();if(!r.ok)throw Error(data.error);return data;};
  const get=async()=> (await api('/api/narrative')).journey;
  const first=await api('/api/dashboard'),world=first.narrative.world;
  dom=new JSDOM('<main id="view"></main>',{url:base,runScripts:'outside-only'});
  const w=dom.window,d=w.document;w.fetch=url=>fetch(new URL(url,base));
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.eval(fs.readFileSync('web/vendor/inkjs/ink.js','utf8'));w.eval(fs.readFileSync('web/narrative.js','utf8'));
  const q=s=>d.querySelector(s),click=s=>{assert.ok(q(s),s);q(s).click();};
  const mount=async()=>{const narrative=await api('/api/narrative');w.NARRATIVE.mount({narrative},'home',{api,study:()=>{},task:()=>{},error:e=>{throw e;}});q('#view').innerHTML=w.NARRATIVE.homeHtml(narrative);};
  const open=async()=>{click('[data-narrative="catalogue"]');await until(()=>q('.narrative-dialog'));};
  const fresh=async()=>{click('[data-journey-refresh]');await tick();};
  await mount();await open();click('[data-journey-claim="main:study"][data-journey-approach="practice"]');
  await until(()=>q('[data-journey-start="main:study"]'));
  assert.equal(q('[data-journey-deliver="main:study"]'),null);
  // 原接口写入评分，之后的撤销必须撤回未交付证明。
  let card=(await api('/api/cards/next',{})).card;
  await api('/api/cards/answer',{key:card.key,rating:4});await fresh();
  await until(()=>q('[data-journey-deliver="main:study"]'));
  await api('/api/cards/undo',{});await fresh();await until(()=>q('[data-journey-start="main:study"]'));
  card=(await api('/api/cards/next',{})).card;await api('/api/cards/answer',{key:card.key,rating:4});await fresh();
  await until(()=>q('[data-journey-deliver="main:study"]'));click('[data-journey-deliver="main:study"]');
  await until(()=>q('[data-journey-claim="main:review"]'));
  assert.equal((await get()).collection.length,1);
  await api('/api/journey',{world,action:'deliver',id:'main:study',revision:0});assert.equal((await get()).collection.length,1);
  click('[data-journey-claim="main:review"]');await until(()=>q('[data-journey-start="main:review"]'));
  const stale=await get();
  card=(await api('/api/cards/next',{})).card;await api('/api/cards/answer',{key:card.key,rating:4});
  await assert.rejects(()=>api('/api/journey',{world,action:'deliver',id:'main:review',revision:stale.revision}),/另一窗口/);
  await fresh();await until(()=>q('[data-journey-deliver="main:review"]'));click('[data-journey-deliver="main:review"]');
  await until(()=>q('.journey-collection summary').textContent.includes('4件'));
  q('.journey-collection').open=true;click('[data-journey-place="main:study:reward"]');
  await until(()=>q('[data-journey-place=""][data-journey-slot="desk"]'));
  assert.equal(q('.journey-collection').open,true);
  click('[data-journey-place="main:ornament"]');await until(()=>q('[data-journey-place=""][data-journey-slot="shelf"]'));
  click('[data-narrative="close"]');await mount();assert.match(q('.journey-display').textContent,/法典|卷宗|竹卷/);
  await open();assert.equal((await get()).stage,2);assert.equal((await get()).collection.length,4);
  // 陈列/剧情操作不额外授予学习经验。原卡片的评分经验保留。
  const xp=(await api('/api/dashboard')).xp;click('[data-journey-place=""][data-journey-slot="desk"]');
  await until(()=>!q('[data-journey-place=""][data-journey-slot="desk"]'));
  assert.equal((await api('/api/dashboard')).xp,xp);
  console.log('任务/收藏真实接口与DOM交互通过：'+(subject||'法考'));
 }finally{dom?.window.close();srv.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
