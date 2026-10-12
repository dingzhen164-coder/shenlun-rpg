/* 无浏览器时的真实接口+DOM回归；jsdom仅开发依赖，不能替代像素/触控检查。
   Python临时库服务真实读写存档，验证页面与服务端续读/CAS/跳过等契约。 */
const {JSDOM}=require('jsdom'),{spawn}=require('node:child_process'),fs=require('node:fs'),assert=require('node:assert/strict');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[])],{env:process.env});
let logs='';srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(logs||'服务未启动')),20000);
 srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});srv.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出 '+c+logs));});});
const tick=()=>new Promise(r=>setTimeout(r,10));
async function until(fn){for(let i=0;i<300;i++){if(fn())return;await tick();}throw Error('DOM等待超时');}
let dom;
(async()=>{
 try{
  const base=await ready;
  const api=async(path,body)=>{const r=await fetch(new URL(path,base),body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error);return data;};
  const before=await api('/api/dashboard'),world=before.narrative.world;
  dom=new JSDOM('<main id="view"></main>',{url:base,runScripts:'outside-only'});
  const w=dom.window,d=w.document;
  w.fetch=url=>fetch(new URL(url,base));
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.eval(fs.readFileSync('web/vendor/inkjs/ink.js','utf8'));w.eval(fs.readFileSync('web/narrative.js','utf8'));
  const select=s=>d.querySelector(s),click=s=>{assert.ok(select(s),s);select(s).click();};
  const errors=[],moves=[];const handlers={api,error:e=>errors.push(e.message),study:()=>moves.push('study'),review:()=>moves.push('review'),tutor:()=>moves.push('tutor')};
  const mount=async()=>{const narrative=await api('/api/narrative');w.NARRATIVE.mount({narrative},'home',handlers);d.querySelector('#view').innerHTML=w.NARRATIVE.homeHtml(narrative);};
  const open=async()=>{click('[data-narrative="catalogue"]');await until(()=>select('.narrative-dialog'));};
  const chapter=async()=>{click('[data-narrative-chapter="prologue"]');await until(()=>select('[data-narrative-choice="understand"]'));};
  await mount();await open();assert.equal(select('[data-narrative-chapter="study_echo"]').disabled,true);
  await chapter();assert.equal(select('[data-narrative-choice="recorded"]'),null);
  click('[data-narrative-choice="practice"]');await until(()=>select('[data-narrative-choice="continue"]'));
  assert.equal((await api('/api/narrative')).revision,1);
  click('[data-narrative="close"]');await open();click('[data-narrative-chapter="prologue"]');await until(()=>select('[data-narrative-choice="continue"]'));
  assert.match(select('.narrative-transcript').textContent,/我想先试着作答/);
  // 第二个客户端已选择；旧窗口明确报冲突，不会重复覆盖或领奖。
  const current=await api('/api/narrative',{world,chapter:'prologue',action:'open'});
  await api('/api/narrative',{world,chapter:'prologue',action:'choose',choice:'continue',node:current.scene.node,revision:current.revision});
  click('[data-narrative-choice="continue"]');await until(()=>select('.narrative-error')?.textContent.includes('另一窗口'));
  assert.equal((await api('/api/narrative')).revision,2);
  click('[data-narrative="close"]');await open();click('[data-narrative-chapter="prologue"]');await until(()=>select('[data-narrative="finish"]'));
  click('[data-narrative="finish"]');await until(()=>select('[data-narrative="replay"]')&&!select('[data-narrative="finish"]'));
  click('[data-narrative="replay"]');await until(()=>select('[data-narrative-choice="understand"]'));
  select('[data-narrative-brief]').checked=true;select('[data-narrative-brief]').dispatchEvent(new w.Event('change',{bubbles:true}));
  await until(()=>d.querySelectorAll('.narrative-text p').length===1);
  click('[data-narrative="skip"]');await until(()=>!select('[data-narrative="skip"]'));
  assert.equal((await api('/api/narrative')).chapters[0].read,true);
  assert.equal(w.NARRATIVE.close(),true);assert.equal(w.NARRATIVE.close(),false);
  // 迟到的打开回包不得在学习页面挂出人物对话。
  const delayed={...handlers,api:async(...args)=>{await new Promise(r=>setTimeout(r,40));return api(...args);}};
  w.NARRATIVE.mount(before,'home',delayed);click('[data-narrative="catalogue"]');w.NARRATIVE.mount(before,'train',handlers);
  await new Promise(r=>setTimeout(r,100));assert.equal(select('.narrative-dialog'),null);
  await mount();await open();click('[data-narrative="study"]');assert.deepEqual(moves,['study']);assert.equal(select('.narrative-dialog'),null);
  const after=await api('/api/dashboard');assert.equal(after.xp,before.xp);assert.equal(after.minutes.today,before.minutes.today);assert.deepEqual(errors,[]);
  console.log('真实接口与DOM交互通过：'+(subject||'法考')+'（不含浏览器布局）');
 }finally{dom?.window.close();srv.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
