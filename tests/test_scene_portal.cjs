/* 百分比布局：损坏数据兜底、两设备/两主题隔离、保存失败与触控取消回滚。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const listeners={},values=new Map(),storage=new Map();let fail=false;
for(const s of ['[data-portal-x]','[data-portal-y]','[data-portal-selected]','[data-portal-status]','[data-portal-preview]'])values.set(s,{});
const doc={addEventListener:(name,f)=>listeners[name]=f,querySelector:s=>values.get(s)||null,querySelectorAll:()=>[],body:{classList:{toggle(){},contains:()=>false}},documentElement:{style:{setProperty(){}}}};
const ctx={window:{innerWidth:1280,innerHeight:860,addEventListener(){}},document:doc,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>{if(fail)throw Error('quota');storage.set(k,v);}}};
vm.runInNewContext(fs.readFileSync('web/scene_portal.js','utf8'),ctx);
const api=ctx.window.SCENE_PORTAL,places=[{id:'dwelling',label:'洞府',view:'dwelling',x:12,y:78},{id:'train',label:'训练',view:'train',x:40,y:33}];
const raw={desktop:{dwelling:{x:Infinity,y:'10'},train:{x:-20,y:150}},narrow:{dwelling:{x:33,y:44}},names:{dwelling:'  新洞府  ',train:42,unknown:'忽略'},extra:'bad'};
const n=api.normalize(raw,places);assert.equal(n.desktop.dwelling.x,12);assert.equal(n.desktop.dwelling.y,78);assert.equal(n.desktop.train.x,5);assert.equal(n.desktop.train.y,95);assert.equal(n.narrow.dwelling.x,33);
assert.equal(n.names.dwelling,'新洞府');assert.equal(n.names.train,undefined);assert.equal(n.names.unknown,undefined);
// 法考天机台内置0%坐标：保存其他地点时，未调整的边缘默认位置不应被裁到5%。
const edge=[{id:'edge',label:'边缘地点',x:59,y:0,nx:72,ny:2}];
const defaults=api.normalize(null,edge),roundtrip=api.normalize(JSON.parse(JSON.stringify(defaults)),edge);
assert.equal(roundtrip.desktop.edge.y,0);assert.equal(roundtrip.narrow.edge.y,2);
api.configure({id:'xingce',title:'宗门',image:'map.webp',places},()=>{});api.settingsHtml();api.mount('settings');
const changed={matches:s=>s.includes('data-portal-x'),valueAsNumber:37};listeners.change({target:changed});
const click=selector=>listeners.click({target:{closest:s=>s===selector?{}:null}});
click('[data-portal-save]');assert.equal(JSON.parse(storage.get('scene-layout:xingce:saved')).desktop.dwelling.x,37);
api.configure({id:'guantu',title:'政务',image:'hall.webp',places},()=>{});api.settingsHtml();api.mount('settings');assert.equal(values.get('[data-portal-x]').value,12);
const point={dataset:{portalPoint:'dwelling'},setPointerCapture(){},closest:()=>({getBoundingClientRect:()=>({left:0,top:0,width:100,height:100})})};
listeners.pointerdown({target:{closest:()=>point},button:0,pointerId:2,preventDefault(){}});listeners.pointermove({pointerId:2,clientX:88,clientY:22});assert.equal(values.get('[data-portal-x]').value,88);
listeners.pointercancel();assert.equal(values.get('[data-portal-x]').value,12);
fail=true;click('[data-portal-save]');assert.ok(values.get('[data-portal-status]').textContent.includes('保存失败'));assert.equal(storage.has('scene-layout:guantu:saved'),false);
ctx.window.innerWidth=800;ctx.window.innerHeight=1280;assert.equal(api.profile(),'narrow');
console.log('SCENE-LAYOUT-OK');
