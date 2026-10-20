/* 手写笔防丢笔（web/pen_guard.js）：触摸/手势拦截、晚到的抬笔、落笔被吞、笔离开纸面、闲置收笔。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const events={};const canvas={addEventListener(t,f,o){(events[t]=events[t]||[]).push([f,o]);}};
const ctx={window:{},performance:{now:()=>now},setTimeout,clearTimeout};let now=1000;vm.createContext(ctx);
vm.runInContext(fs.readFileSync('web/pen_guard.js','utf8'),ctx);
const g=ctx.window.PEN_GUARD.make(canvas);
for(const t of ['touchstart','touchmove']){assert.ok(events[t],t+' 已监听');assert.equal(events[t][0][1].passive,false,t+' 必须非passive才能preventDefault');let prevented=false;events[t][0][0]({preventDefault(){prevented=true;}});assert.ok(prevented);}
for(const t of ['gesturestart','gesturechange','contextmenu','selectstart'])assert.ok(events[t],t);
// 晚到的抬笔：新一笔落下时上一笔还没收尾
g.down(true);now+=20;assert.equal(g.lateUp({type:'pointerup'}),true,'第一个pointerup属于上一笔');assert.equal(g.lateUp({type:'pointerup'}),false,'第二个才是这一笔的');
g.down(true);now+=400;assert.equal(g.lateUp({type:'pointerup'}),false,'超过250ms不当作晚到');
g.down(false);assert.equal(g.lateUp({type:'pointerup'}),false,'没有重叠时不忽略');
g.down(true);assert.equal(g.lateUp({type:'pointercancel'}),false,'pointercancel不忽略');
// 落笔被吞
assert.equal(g.missedDown({pointerType:'pen',buttons:1,pressure:.5},false),true);
assert.equal(g.missedDown({pointerType:'pen',buttons:0,pressure:0},false),false,'悬停不算');
assert.equal(g.missedDown({pointerType:'touch',buttons:1,pressure:.5},false),false,'手指不补笔');
assert.equal(g.missedDown({pointerType:'pen',buttons:1,pressure:.5},true),false,'已有笔不补');
// 笔离开纸面：连续两次
const hover={pointerType:'pen',buttons:0,pressure:0},press={pointerType:'pen',buttons:1,pressure:.4};
assert.equal(g.lifted(hover,true),false);assert.equal(g.lifted(press,true),false);assert.equal(g.lifted(hover,true),false);assert.equal(g.lifted(hover,true),true);
// 闲置收笔
let fired=0;g.idle(()=>fired++);g.idle(()=>fired++);g.idle();
setTimeout(()=>{assert.equal(fired,0,'idle()取消后不触发');let f2=0;g.idle(()=>f2++);setTimeout(()=>{assert.equal(f2,1,'900ms后自动收笔');console.log('PEN-GUARD-OK');},1000);},50);
