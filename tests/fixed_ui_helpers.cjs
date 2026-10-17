/* 旧交互用例适配3.0.4模块内标签：通过真实标签按钮展示目标面板，再操作原控件。
   不强制点击、不删除hidden、不绕过遮挡；等待移除/隐藏时不切换页面。 */
async function reveal(page,locator){
  await page.waitForTimeout(60);
  if(await locator.count())await locator.first().evaluate(el=>{for(let p=el;p;p=p.parentElement)if(p.tagName==='DETAILS'&&p!==el.closest('summary')?.parentElement)p.open=true;});
  if(!await locator.count())return;
  const scene=await locator.first().evaluate(el=>{const p=el.closest('.cs-pane');return p?{mode:p.dataset.csPane,open:!!p.closest('dialog')?.open}:null;});
  if(scene){
    const pane=locator.first();
    if(!await pane.isVisible()){
      if(scene.open)await page.locator('[data-cs-close]').first().click();
      await page.locator(`[data-cs-enter="${scene.mode}"]`).click();
    }
  }
  const ids=await locator.first().evaluate(el=>{const ids=[];for(let p=el;p;p=p.parentElement)if(p.hidden&&getComputedStyle(p).display==='none'&&p.getAttribute('role')==='tabpanel')ids.unshift(p.id);return ids;});
  for(const id of ids){const tab=page.locator(`[role="tab"][aria-controls="${id}"]`);if(await tab.count())await tab.click();}
}
function install(page){
  const proto=Object.getPrototypeOf(page.locator('body'));
  const waitAttached=proto.waitFor;
  for(const name of ['click','fill','selectOption','check','uncheck','focus','press','waitFor']){
    const original=proto[name];proto[name]=async function(...args){
      if(name!=='waitFor'||!args[0]?.state||args[0].state==='visible'){await waitAttached.call(this,{state:'attached',timeout:args[0]?.timeout});await reveal(page,this);}
      return original.apply(this,args);
    };
  }
}
module.exports={install,reveal};
