/* 师傅解惑的讲解：Markdown（分段、加粗小标题、选项表格）渲染成真正的分段 / 加粗 / 表格；纯文字仍按原样换行。电脑与平板不横向溢出。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1]||'行测';
const text=`选 B 吗？被“横空出世”带跑了。\n\n**结论：选 D**，“纷至沓来”对应“接连、陆续涌现”。\n\n**用什么方法**\n直接对应＋词义辨析。\n\n| 选项 | 判断 | 理由 |\n|---|---|---|\n| A 比比皆是 | ✗ | 写**空间密度** |\n| D 纷至沓来 | ✓ | 接连不断到来 |\n\n**一招：** 先白话化。`;
(async()=>{let srv,b;try{
 srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',subject],{env:process.env});let s='';
 const base=await new Promise((r,j)=>{setTimeout(()=>j(Error('服务启动超时')),20000);srv.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m)r(m[1]);});});
 b=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
  const p=await b.newPage({viewport});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto(base);await p.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await p.evaluate((t)=>{const d=document.createElement('div');d.id='fmtbox';d.className='card chat';d.style.cssText='position:fixed;inset:10px;z-index:99999;overflow:auto;padding:12px;background:var(--panel)';d.innerHTML='<div class="msgs">'+msgHtml({who:'npc',text:t})+msgHtml({who:'npc',text:'一句普通的话\n换行不丢'})+'</div>';document.body.appendChild(d);},text);
  assert.equal(await p.locator('#fmtbox .tutor-md table').count(),1,'表格渲染成真正的 table');
  assert.equal(await p.locator('#fmtbox .tutor-md tbody tr').count(),2);
  assert((await p.locator('#fmtbox .tutor-md b').count())>=4,'加粗');
  const titles=await p.locator('#fmtbox .tutor-md p').allTextContents();
  assert(titles.some(t=>t.trim()==='用什么方法'),'加粗小标题自成一段');
  assert.doesNotMatch(await p.locator('#fmtbox .tutor-md').first().innerHTML(),/\*\*|\|---/,'没有残留的 Markdown 符号');
  assert.equal(await p.locator('#fmtbox .tutor-md').count(),1,'纯文字不走富文本');
  // 旧讲解里的 LaTeX（\\( … \\)）显示成读得懂的普通文字，富文本和纯文字两条渲染路径都一样
  const latex='设总人数为 \\(100a+10b+c\\)，得 \\(90(a-b)=270\\)，所以 \\(b=a-3\\)；\\(x\\equiv3\\pmod4\\)。';
  for(const html of await p.evaluate((t)=>[msgHtml({who:'npc',text:t}),msgHtml({who:'npc',text:'**结论**\n\n'+t}),blocksHtml([{t:'text',v:t}])],latex)){
   assert(html.includes('100a+10b+c')&&html.includes('90(a-b)=270')&&html.includes('b=a-3')&&html.includes('x≡3（mod 4）'),'公式换成普通文字：'+html);
   assert(!/\\\(|\\\)|\\equiv|\\pmod/.test(html),'没有残留的LaTeX：'+html);
  }
  assert.match(await p.locator('#fmtbox .say').nth(1).innerHTML(),/一句普通的话<br>换行不丢/);
  const over=await p.evaluate(()=>{const r=document.querySelector('#fmtbox .tutor-md table').getBoundingClientRect();return r.right>innerWidth+2||document.documentElement.scrollWidth>innerWidth+2;});
  assert(!over,label+' 表格不伸出屏幕');
  assert.deepEqual(errors,[]);await p.close();console.log(subject+' '+label+'：师傅解惑版式 通过');
 }
}finally{await b?.close();srv?.kill();}})().catch(e=>{console.error(e);process.exit(1);});
