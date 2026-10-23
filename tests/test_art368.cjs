/* 黄昏分区图接入：纯JS检查时钟、专用图、用户优先和旧单图回退，不请求网络。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function choice(files,{phase='dusk',time='day',custom=[],region='万象峰',page='train',global=false}={}){
 const values={},classes=new Set(global?['has-bg']:[]),body={dataset:{},style:{setProperty:(k,v)=>values[k]=v,removeProperty:k=>delete values[k]},classList:{contains:k=>classes.has(k),add:k=>classes.add(k),remove:k=>classes.delete(k)}};
 const context={window:{ART_FILES:files.map(f=>[f,1]),ART_CUSTOM:custom,STUDY_REGIONS:{title:()=>region}},document:{readyState:'loading',body,documentElement:{dataset:{scenePhase:phase,sceneTime:time}},querySelector:()=>null,addEventListener:()=>{}}};
 context.STUDY_REGIONS=context.window.STUDY_REGIONS;
 vm.runInNewContext(fs.readFileSync('web/beauty_art.js','utf8'),context);context.window.BeautyArt.mount(page);return {url:values['--ds-page-art'],kind:body.dataset.sceneRelight};
}
const root='beauty/page/train-chang';
assert.match(choice([root+'.webp',root+'-night.webp',root+'-dusk.webp']).url,/-dusk.webp/);
assert.equal(choice([root+'-dusk.webp']).kind,'native','专门画的黄昏不再套暖色滤镜');
assert.equal(choice([root+'.webp',root+'-night.webp']).kind,'synthetic','旧单图继续晨昏调色');
assert.match(choice([root+'-day.webp',root+'-night.webp']).url,/-day.webp/);
assert.match(choice([root+'-dusk.webp','beauty/page/train.webp'],{custom:['beauty/page/train.webp']}).url,/train.webp/,'用户覆盖优先');
assert.match(choice([root+'-night.webp',root+'-dusk.webp'],{phase:'night',time:'night'}).url,/-night.webp/);
assert.match(choice([root+'-dusk.webp'],{global:true}).url,/-dusk.webp/,'旧全站背景不压住五峰新图');
assert.equal(choice(['beauty/page/dwelling.webp'],{page:'dwelling',global:true}).url,undefined,'其他页面仍尊重全局背景');
let mode='dusk';const html={dataset:{theme:'dark'}},context={document:{documentElement:html,addEventListener:()=>{}},localStorage:{getItem:()=>mode},MutationObserver:class{observe(){}},window:{addEventListener:()=>{}},setInterval:()=>{},Date};
vm.runInNewContext(fs.readFileSync('web/scene_clock.js','utf8'),context);
assert.equal(html.dataset.scenePhase,'dusk');assert.equal(html.dataset.sceneTime,'day','保留主页昼夜两图接口');
mode='night';context.window.SCENE_CLOCK.apply();assert.equal(html.dataset.scenePhase,'night');
assert(context.window.SCENE_CLOCK.settingsHtml().includes('一直黄昏'));
console.log('ART368-LOGIC-OK：黄昏时钟、独立图、旧图回退及用户覆盖');
