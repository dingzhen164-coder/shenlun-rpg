/* 延迟 API 回包不能覆盖已离开的页面或新选择的题；离开思过崖停止自动计时。 */
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup(){
 const actions={},storage=new Map();let html='';
 const root={get innerHTML(){return html;},set innerHTML(v){html=v;},querySelector(){return null;},querySelectorAll(sel){
  const button=dataset=>{const b={dataset};actions[sel]=b;return [b];};
  if(sel==='[data-sgboard]')return button({sgboard:'中心理解'});
  if(sel==='[data-sgpick]')return button({sgpick:'C'});
  if(sel==='[data-sgq]')return button({sgq:'second'});
  return [];
 }};
 const question=key=>({key,title:key,stem:'自编题干',options:{A:'甲',C:'乙'},sections:[]});
 const board={name:'中心理解',board:'片段阅读',exists:true,questions:[question('first'),question('second')],problems:[],file:'中心理解.md'};
 const ctx={console,Date,VIEW:'tianji',document:{visibilityState:'visible'},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},showError:e=>{throw e;},handleEvents:()=>{}};
 ctx.window=ctx;ctx.addEventListener=()=>{};
 ctx.api=async url=>url==='/api/siguo'?{boards:[{name:'中心理解',total:2}],folder:'思过崖',template:'_模板.md'}:board;
 vm.runInNewContext(fs.readFileSync('web/siguo.js','utf8'),ctx);
 return {ctx,root,actions,board};
}
(async()=>{
 {
  const {ctx,root,actions,board}=setup();await ctx.SIGUO.render(root,()=>true);
  let resolve;ctx.api=()=>new Promise(r=>resolve=r);
  const pending=actions['[data-sgboard]'].onclick();ctx.VIEW='home';root.innerHTML='首页';resolve(board);await pending;
  assert.equal(root.innerHTML,'首页','离开后板块回包不能重画首页');
 }
 {
  const {ctx,root,actions}=setup();await ctx.SIGUO.render(root,()=>true);await actions['[data-sgboard]'].onclick();
  let resolve;ctx.api=()=>new Promise(r=>resolve=r);
  const pending=actions['[data-sgpick]'].onclick();actions['[data-sgq]'].onclick();
  resolve({ok:true,answer:'C',choice:'C',sections:[{title:'上一题解析',md:'FIRST_ANSWER'}],record:{last:'ok'},events:[]});await pending;
  assert(!root.innerHTML.includes('FIRST_ANSWER'),'切题后不显示上一题的解析');
  ctx.VIEW='home';assert.equal(ctx.SIGUO.active(),'','首页不能累计思过崖学习时间');
 }
 console.log('思过崖：延迟板块/答题回包隔离、离开停止计时通过');
})().catch(e=>{console.error(e);process.exitCode=1;});
