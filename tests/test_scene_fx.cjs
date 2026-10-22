/* 四季轮换：可控时钟、刷新/离开、坏数据与禁用存储；不启动浏览器或真实库。 */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/scene_fx.js','utf8');
function app(storage=new Map(),fail=false){
 const events={},timers=[],root={dataset:{}},doc={readyState:'loading',documentElement:root,querySelectorAll:()=>[],addEventListener:(k,f)=>events[k]=f};
 const ctx={window:{addEventListener(){}},document:doc,localStorage:{getItem:k=>{if(fail)throw Error('blocked');return storage.get(k);},setItem:(k,v)=>{if(fail)throw Error('blocked');storage.set(k,v);}},SCENE_CLOCK:{phase:()=> 'day',resolve:()=>({ph:'day',img:'day'}),apply(){}},MutationObserver:class{observe(){}},matchMedia:()=>({matches:false}),setTimeout:(f,t)=>{timers.push(t);return timers.length;},clearTimeout(){}};
 vm.runInNewContext(source,ctx);return {api:ctx.window.SCENE_FX,events,root,timers};
}
const store=new Map([['scene-season','random']]);let a=app(store),start=JSON.parse(store.get('scene-season-cycle-v1')),at=start.at;
assert.equal(start.minutes,60);assert.equal(a.api.resolve(new Date(at+3599999)).se,start.season);
a=app(store);assert.equal(a.api.resolve(new Date(at+1000)).se,start.season,'重载不重抽');
const next=a.api.resolve(new Date(at+3600000));assert.notEqual(next.se,start.season);assert.equal(next.next,at+7200000);
assert.equal(a.api.resolve(new Date(at+3600020)).se,next.se,'同周期稳定');
let far=a.api.resolve(new Date(at+25*3600000+100));assert.notEqual(far.se,next.se);assert.equal(far.next,at+26*3600000);
store.set('scene-season-minutes','30');const shorter=a.api.resolve(new Date(at+26*3600000));assert.equal(shorter.next,at+26*3600000+1800000);
store.set('scene-season','winter');assert.equal(a.api.resolve(new Date(at+90*3600000)).se,'winter');assert.equal(a.api.resolve().next,null);
store.set('scene-season','off');assert.equal(a.api.resolve().se,'off');
store.set('scene-season','auto');assert.deepEqual([0,3,6,9].map(m=>a.api.resolve(new Date(2026,m,10)).se),['winter','spring','summer','autumn']);
for(const bad of ['{','null','{"season":"garbage","at":0,"minutes":60}','{"season":"spring","at":1e99,"minutes":60}']){
 store.set('scene-season','random');store.set('scene-season-minutes','bad');store.set('scene-season-cycle-v1',bad);a=app(store);assert(['spring','summer','autumn','winter'].includes(a.api.resolve().se));assert.equal(JSON.parse(store.get('scene-season-cycle-v1')).minutes,60);
}
a=app(new Map(),true);a.events.change({target:{value:'random',closest(){return this;},hasAttribute:k=>k==='data-scene-season'}});const stable=a.api.resolve().se;assert.equal(a.api.resolve().se,stable,'存储受限仍记本次');
assert.match(a.api.settingsHtml(),/随机轮换/);assert.match(a.api.settingsHtml(),/1小时/);
console.log('SCENE-FX-CYCLE-OK');
