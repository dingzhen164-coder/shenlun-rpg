/* 人物第一版实际HTTP与浏览器交互：电脑/平板，假AI、假HOME和临时资料。
   程序检查先行，失败才截图。无手机尺寸，不连接真实AI。 */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const out=path.resolve('ui-artifacts/characters');
function server(subject){
  const child=spawn(process.env.PYTHON||'python3',['tests/ui_characters_server.py',subject],{env:{...process.env,PYTHONIOENCODING:'utf-8'}});
  let logs='';child.stderr.on('data',x=>logs+=x);
  const ready=new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('人物服务未启动：'+logs)),20000);
    child.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
    child.on('exit',code=>{clearTimeout(timer);reject(Error('人物服务退出'+code+'\n'+logs));});});
  return {child,ready};
}
async function inspect(page){
  const problems=await page.evaluate(()=>{
    const out=[],d=document.querySelector('.npc-dialog');
    if(document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2)out.push('整页溢出');
    if(!d)return out;
    for(const el of [d,...d.querySelectorAll('button,textarea,select')]){
      const r=el.getBoundingClientRect();if(!r.width||!r.height)continue;
      if(r.left<0||r.right>innerWidth+1||r.top<0||r.bottom>innerHeight+1)out.push('控件伸出屏幕：'+el.className);
    }
    const r=d.getBoundingClientRect();if(r.width<400||r.height<400)out.push('人物框异常');
    return out;
  });assert.deepEqual(problems,[]);
}
(async()=>{
 const services=[];let browser,activePage;
 try{
  const launch={headless:true};
  const exe=process.env.CHROMIUM_PATH||(fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':null);
  if(exe)launch.executablePath=exe;
  browser=await chromium.launch(launch);
  const svc=server('行测');services.push(svc);const base=await svc.ready;
  for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
   for(const theme of ['light','dark']){
    const context=await browser.newContext({viewport});const page=await context.newPage();activePage=page;
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);await page.waitForSelector('.npc-person');
    await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    const first=page.locator('.npc-person').first();const cid=await first.getAttribute('data-npc-id');
    await first.click();await page.waitForSelector('.npc-dialog[open]');
    assert.match(await page.locator('.npc-portrait-image').getAttribute('src'),/three-quarter/);
    await inspect(page);
    await page.getByRole('button',{name:'交流',exact:true}).click();
    assert.match(await page.locator('.npc-portrait-image').getAttribute('src'),/bust/);
    const message=label+'-'+theme+' <img src=x onerror=alert(1)> 自编闲聊';
    await page.locator('.npc-input').fill(message);await page.getByRole('button',{name:'发送',exact:true}).click();
    await page.waitForFunction(expected=>document.querySelector('.npc-messages')?.textContent.includes(expected),'自编交流：'+message);
    assert.equal(await page.locator('.npc-messages img').count(),0);
    assert.equal(await page.locator('.npc-input').inputValue(),'');await inspect(page);
    await page.locator('.npc-input').fill('草稿要保留');
    await page.getByRole('button',{name:'← 返回人物'}).click();await page.getByRole('button',{name:'交流',exact:true}).click();
    assert.equal(await page.locator('.npc-input').inputValue(),'草稿要保留');
    await page.getByRole('button',{name:'← 返回人物'}).click();await page.getByRole('button',{name:'论道',exact:true}).click();
    const daoText=label+'-'+theme+' 请解释一个方法的适用条件';
    await page.locator('.npc-input').fill(daoText);await page.getByRole('button',{name:'发送',exact:true}).click();
    await page.waitForFunction(expected=>document.querySelector('.npc-messages')?.textContent.includes(expected),'自编论道：'+daoText);
    await page.getByRole('button',{name:'← 返回人物'}).click();await page.getByRole('button',{name:'赠礼',exact:true}).click();
    await page.locator('.npc-give').click();await page.waitForFunction(()=>document.querySelector('.npc-status')?.textContent.includes('已赠送'));
    assert.match(await page.locator('.npc-gift-history').textContent(),/护心丹/);
    await page.getByRole('button',{name:'← 返回人物'}).click();await page.getByRole('button',{name:'人物记忆',exact:true}).click();
    await page.locator('.npc-memory').fill('自编约定：先讲一个例子。');await page.locator('.npc-save-memory').click();
    await page.waitForFunction(()=>document.querySelector('.npc-status')?.textContent.includes('记忆已保存'));
    await inspect(page);await page.keyboard.press('Escape');assert.equal(await page.locator('.npc-dialog').count(),0);
    await page.reload();await page.waitForSelector('.npc-person');
    await page.locator(`[data-npc-id="${cid}"]`).click();await page.getByRole('button',{name:'交流',exact:true}).click();
    assert.match(await page.locator('.npc-messages').textContent(),/自编交流/);
    // 失败保留输入且不追加；主动离开后迟到回复不重新弹窗。
    await page.locator('.npc-input').fill('__fail__ 自编失败');await page.getByRole('button',{name:'发送',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.npc-status')?.textContent.includes('自编失败'));
    assert.equal(await page.locator('.npc-input').inputValue(),'__fail__ 自编失败');
    await page.locator('.npc-input').fill('__delay__ 自编延迟');await page.getByRole('button',{name:'发送',exact:true}).click();
    await page.locator('.npc-close').click();await page.evaluate(()=>go('dwelling'));
    await page.waitForTimeout(900);assert.equal(await page.locator('.npc-dialog,.npc-encounters').count(),0);
    await page.evaluate(()=>go('notes'));assert.equal(await page.locator('.npc-encounters').count(),0);
    await page.evaluate(()=>{STUDY_REGIONS.select('yan');return go('train');});
    await page.waitForSelector('.npc-person');await inspect(page);
    await page.evaluate(()=>CARDS.review(''));
    await page.waitForSelector('.yj-stage');
    await page.waitForFunction(()=>!document.querySelector('.npc-encounters'));
    await page.evaluate(()=>CARDS.close());await page.waitForSelector('.npc-person');
    await page.evaluate(()=>document.documentElement.classList.add('drawing'));
    await page.waitForFunction(()=>!document.querySelector('.npc-encounters'));
    await page.evaluate(()=>document.documentElement.classList.remove('drawing'));await page.waitForSelector('.npc-person');
    assert.deepEqual(errors,[]);
    await context.close();console.log(label+' '+theme+' 人物闭环通过');
   }
  }
  const sl=server('申论');services.push(sl);const slbase=await sl.ready;const ctx=await browser.newContext({viewport:{width:800,height:1280}});const page=await ctx.newPage();activePage=page;
  let npcRequests=0;page.on('request',r=>{if(r.url().includes('/api/characters/'))npcRequests++;});
  await page.goto(slbase);await page.waitForFunction(()=>typeof DASH!=='undefined'&&DASH);
  await page.evaluate(()=>go('train'));assert.equal(await page.locator('.npc-encounters').count(),0);assert.equal(npcRequests,0);
  const result=await page.evaluate(async()=>{const r=await fetch('/api/characters/encounter',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scene:'home'})});return r.json();});
  assert.equal(result.enabled,false);await ctx.close();console.log('申论无人物入口、无自动人物请求通过');
  console.log('人物浏览器检查全部通过（临时资料、假AI）');
 }catch(e){
  if(activePage&&!activePage.isClosed()){fs.mkdirSync(out,{recursive:true});await activePage.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}
  console.error(e.stack||e);process.exitCode=1;
 }finally{await browser?.close();for(const s of services)s.child.kill();}
})();
