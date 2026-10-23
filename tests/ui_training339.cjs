/* 3.3.9：假HOME自编题；顶栏计时/材料开合、倒计时保存与场景入口，电脑平板明暗。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const service=spawn('python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--art-fixture','--fixes359-fixture'],{env:process.env});
let browser,active,logs='';service.stderr.on('data',x=>logs+=x);
const ready=new Promise((ok,no)=>{let output='';const timer=setTimeout(()=>no(Error(logs||'服务启动超时')),20000);service.stdout.on('data',x=>{output+=x;const m=output.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});service.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
const out=path.resolve('ui-artifacts/training339');
async function fits(p){assert.deepEqual(await p.evaluate(()=>{const bad=[];if(document.documentElement.scrollWidth>innerWidth+2||document.documentElement.scrollHeight>innerHeight+2||scrollY)bad.push('页面溢出');for(const e of document.querySelectorAll('#studyHud,.cs-calendar,.train,.composer')){const r=e.getBoundingClientRect();if(r.width&&r.height&&(r.left<0||r.right>innerWidth+2||r.bottom>innerHeight+2))bad.push(e.className+'越界');}return bad;}),[]);}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]].filter(([size])=>!process.argv.some(x=>x.startsWith('--sizes='))||process.argv.find(x=>x.startsWith('--sizes=')).split('=')[1].split(',').includes(size))){
  const p=await browser.newPage({viewport});active=p;const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());
  await p.evaluate(()=>go('settings'));await p.locator('#ccName').waitFor({state:'attached'});
  const group=p.locator('.fx-settings-group').filter({has:p.locator('#ccSave')});await group.locator(':scope>summary').click();
  await p.locator('#ccName').fill('自编年度考试');await p.locator('#ccExam').fill('2026-11-15');await p.locator('#ccSave').click();await p.locator('#ccStatus').filter({hasText:'已保存'}).waitFor();
  assert.deepEqual(await p.evaluate(async()=>{const c=await api('/api/contest/calendar',{});return[c.name,c.exam];}),['自编年度考试','2026-11-15']);
  if(subject==='申论'){
   await p.reload();await p.waitForFunction(()=>!!window.DASH_REF?.());await p.evaluate(()=>go('settings'));assert.equal(await p.locator('#ccName').inputValue(),'自编年度考试');await fits(p);
  }else{
   await p.evaluate(()=>go('contest'));await p.locator('.cs-calendar').waitFor();assert.equal(await p.locator('.cs-calendar-mock').count(),subject==='行测'?1:0);assert((await p.locator('.cs-calendar-exam').innerText()).includes('自编年度考试'));
   for(const theme of ['light','dark']){await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);await fits(p);assert(await p.evaluate(()=>{const c=document.querySelector('.cs-calendar').getBoundingClientRect();return [...document.querySelectorAll('[data-cs-enter]')].every(e=>{const r=e.getBoundingClientRect();return r.right<=c.left||r.left>=c.right||r.bottom<=c.top||r.top>=c.bottom;});}),'横幅不能遮住入口');if(process.argv.includes('--shots')){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,(subject||'法考')+'-'+size+'-'+theme+'-calendar.png')});}}
   await p.locator('[data-cs-enter=overview]').click();await p.locator('[data-cs-close]').click();
   await p.evaluate(()=>go('bank'));await p.locator('.trial-hall').waitFor();assert.equal(await p.locator('[data-th-motion]').count(),0);
   const board=await p.evaluate(async subject=>{const b=subject==='行测'?'资料分析':DASH.tree[0].board;for(let i=0;i<25;i++)await api('/api/bank/add',{board:b,topic:'自编',source:'隔离测试',stem:(subject==='行测'?'自编材料组'+Math.floor(i/5)+'：这一段数据仅用于隔离测试，甲乙丙丁各有不同的统计结果。\n\n![[训练/题库/图片/题目图/自编大图.png]]\n\n':'')+'自编第'+i+'题：哪项符合条件？',options:{A:'符合',B:'不符',C:'无关',D:'未说明'},answer:'A',analysis:'核对条件。'});await api('/api/bank/count',{count:20});return b;},subject);
   await p.evaluate(b=>startTask({task:{type:'bank',board:b}}),board);await p.locator('.subpage-nav .bank-head').waitFor();assert.equal(await p.evaluate(()=>T.battle.total),20);assert.equal(await p.locator('.chat>.review-head').count(),0);
   const timer=await p.locator('#tT').textContent();await p.waitForFunction(t=>document.getElementById('tT')?.textContent!==t,timer);
   const timeNode=await p.locator('#tT').evaluate(e=>{window.__timeNode=e;STUDY_HUD.refresh();return e===document.getElementById('tT');});assert(timeNode,'同值HUD刷新保留计时节点');
   if(subject==='行测'){
    await p.locator('.mat-pane').waitFor();assert.equal(await p.locator('.mat-head').count(),0);assert.equal(await p.locator('.mat-btn').count(),1);
    await p.locator('.mat-pane img').first().click();await p.locator('.img-zoom').waitFor();await p.keyboard.press('Escape');
    await p.locator('.mat-btn').click();await p.locator('.mat-pane').waitFor({state:'detached'});await p.locator('.mat-btn').click();await p.locator('.mat-pane').waitFor();
   }
   for(const theme of ['light','dark']){await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);await fits(p);assert(await p.locator('[data-act^=exam_pick]').first().isVisible());if(process.argv.includes('--shots')&&subject==='行测'&&theme==='light'){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,subject+'-'+size+'-training.png')});}}
   await p.locator('[data-act^=exam_pick]').first().click();await p.waitForFunction(()=>!T.busy&&T.battle.answered>=1);await p.locator('.subpage-nav .bank-head').waitFor();assert.equal(await p.locator('.subpage-nav .bank-head').count(),1);await fits(p);
   if(subject==='行测'&&size==='desktop'){
    while(await p.evaluate(()=>T.battle.position)>1){const pos=await p.evaluate(()=>T.battle.position);await p.locator('[data-act=exam_prev]').click();await p.waitForFunction(n=>!T.busy&&T.battle.position===n,pos-1);}
    const materials=[];
    for(let i=0;i<6;i++){materials.push(await p.evaluate(()=>JSON.stringify(currentMaterial())));if(i<5){await p.locator('[data-act=exam_next]').click();await p.waitForFunction(n=>!T.busy&&T.battle.position===n,i+2);}}
    assert.equal(new Set(materials.slice(0,5)).size,1,'前五题必须连续使用同一材料');assert.notEqual(materials[4],materials[5],'第六题进入下一份完整材料');
   }

  }
  assert.deepEqual(errors,[]);await p.close();console.log((subject||'法考')+' '+size+'：倒计时设置/场景、紧凑顶栏、计时/材料及固定布局通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+(subject||'法考')+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
