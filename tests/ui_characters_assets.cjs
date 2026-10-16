/* 实际用户立绘HTTP解码与人物舞台检查；临时库/假HOME/假AI，仅电脑和平板。 */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
  const service=spawn(process.env.PYTHON||'python3',['tests/ui_characters_server.py','行测','--real-portraits']);
  let logs='',browser;service.stderr.on('data',x=>logs+=x);
  try{
    const base=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error(logs||'立绘服务启动超时')),20000);
      service.stdout.on('data',x=>{const m=String(x).match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
      service.on('exit',code=>{clearTimeout(timer);reject(Error('立绘服务退出'+code+' '+logs));});
    });
    const launch={headless:true};
    if(process.env.CHROMIUM_PATH)launch.executablePath=process.env.CHROMIUM_PATH;
    else if(fs.existsSync('/usr/bin/chromium'))launch.executablePath='/usr/bin/chromium';
    browser=await chromium.launch(launch);
    const ids=fs.readdirSync('defaults/人物/行测').filter(x=>x.startsWith('xc-'));assert.equal(ids.length,12);
    const out=path.resolve('ui-artifacts/characters-assets');
    for(const [label,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
      const page=await browser.newPage({viewport});const errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.goto(base);await page.waitForSelector('.npc-drawer-toggle');
      const decoded=await page.evaluate(async ids=>{
        const results=[];
        for(const id of ids)for(const kind of ['three-quarter','bust']){
          const url='/vault-file?p='+encodeURIComponent('训练/人物/行测/'+id+'/立绘/'+id+'-'+kind+'.png');
          const img=new Image();img.src=url;await img.decode();results.push([id,kind,img.naturalWidth,img.naturalHeight]);
        }return results;
      },ids);
      assert.equal(decoded.length,24);assert(decoded.every(x=>x[2]>=1000&&x[3]>=1000));
      await page.locator('.npc-drawer-toggle').click();await page.locator('.npc-person').first().click();
      const inspect=async()=>{
        const result=await page.evaluate(()=>{
          const img=document.querySelector('.npc-portrait-image'),r=img.getBoundingClientRect();
          const content=document.querySelector('.npc-content').getBoundingClientRect();
          return {decoded:img.complete&&img.naturalWidth>1000,centered:Math.abs((r.left+r.right)/2-innerWidth/2)<2,inside:r.top>=0&&r.bottom<=innerHeight&&content.bottom<=innerHeight,overflow:document.documentElement.scrollHeight>innerHeight+2};
        });assert.deepEqual(result,{decoded:true,centered:true,inside:true,overflow:false});
      };
      await page.locator('.npc-portrait-image').evaluate(img=>img.decode());await inspect();
      assert.match(await page.locator('.npc-portrait-image').getAttribute('src'),/three-quarter/);
      if(label==='desktop'){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'desktop-menu.png')});}
      await page.getByRole('button',{name:'交流',exact:true}).click();
      await page.locator('.npc-portrait-image').evaluate(img=>img.decode());await inspect();
      assert.match(await page.locator('.npc-portrait-image').getAttribute('src'),/bust/);
      await page.locator('.npc-input').fill('今天我们聊聊学习。');await page.getByRole('button',{name:'发送',exact:true}).click();
      await page.waitForFunction(()=>document.querySelector('.npc-messages')?.textContent.includes('自编交流'));
      if(label==='tablet'){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'tablet-chat.png')});}
      assert.deepEqual(errors,[]);await page.close();console.log(label+'：24张实际立绘解码、中央舞台与底部聊天通过');
    }
  }finally{await browser?.close();service.kill();}
})().catch(e=>{console.error(e);process.exit(1);});
