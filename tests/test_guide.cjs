/* 清禾师尊快速检查：真实进度、不篡改输入/数据、科目隔离与入口路由；无需浏览器。 */
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const listeners = {}, elements = new Map();
const doc = {activeElement:null, hidden:false,
 addEventListener:(name,fn)=>listeners[name]=fn, getElementById:id=>elements.get(id),
 createElement:()=>({dataset:{},setAttribute(){},remove(){elements.delete(this.id);},innerHTML:''}),
 body:{appendChild(el){elements.set(el.id,el);}}};
const ctx = {window:{},document:doc,clearInterval,setInterval,matchMedia:()=>({matches:true})};
vm.runInNewContext(fs.readFileSync('web/xiuxian_guide.js','utf8'),ctx);
const g=ctx.window.XC_GUIDE;
const d={subject:'行测',plan:{tasks:[{id:'done',done:true},{id:'cards:all',done:false},{id:'t1',done:false}]},redo:4};
const original=JSON.stringify(d);
assert.ok(g.greeting(d).includes('1/3'));assert.ok(g.greeting(d).includes('4 道'));
assert.equal(g.nextTask(d).id,'t1');assert.equal(JSON.stringify(d),original);
assert.ok(g.greeting({}).includes('尚无功课'));assert.equal(g.nextTask({plan:{tasks:[{id:'t',done:true}]}}),undefined);
assert.ok(!g.homeHtml(d).includes('undefined'));
let called=0;g.mount(d,'train',{study:()=>called++});assert.ok(elements.has('xcGuideAvatar'));
listeners.click({target:{closest:()=>({dataset:{xcGuide:'study'}})}});assert.equal(called,1);
g.mount({subject:'申论'},'home',{study:()=>called++});assert.equal(elements.size,0);
listeners.click({target:{closest:()=>({dataset:{xcGuide:'study'}})}});assert.equal(called,1);
g.mount(d,'home',{});assert.equal(elements.size,0);assert.equal(g.close(),false);
console.log('GUIDE-QUICK-OK');
