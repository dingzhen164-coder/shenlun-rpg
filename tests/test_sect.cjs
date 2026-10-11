/* 宗门交互快速检查：章节跳过/重读、阅读失败可重试、锁定章节与申论隔离。 */
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
async function main(){
 let click,spoken='',controls='',saves=0,refreshes=0,errors=0,fail=false;
 const ctx={window:{},document:{addEventListener:(name,fn)=>click=fn},XC_GUIDE:{greeting:()=>'<真实进度>',show:(text,html)=>{spoken=text;controls=html;},close(){}},console};
 vm.runInNewContext(fs.readFileSync('web/xiuxian_sect.js','utf8'),ctx);
 const d={subject:'行测',sect:{unread:1,remaining:8,chapters:[{id:'arrival',title:'初入山门',unlocked:true,read:false,lines:['一','二']},{id:'tower',title:'登塔炼心',unlocked:false,condition:'真题',lines:['锁定']}]}};
 const handlers={saveStory:async()=>{saves++;if(fail)throw Error('网络失败');return {...d.sect,unread:0};},refresh:async()=>refreshes++,error:()=>errors++};
 ctx.window.XC_SECT.mount(d,handlers);
 function event(key,value){click({target:{closest:selector=>selector===`[${key}]`?{dataset:{[key.replace(/^data-/,'').replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]:value}}:null}});}
 const roomHtml=ctx.window.XC_SECT.chamberHtml();assert.ok(roomHtml.includes('assets/sect/li.webp'));assert.equal((roomHtml.match(/data-xc-room=/g)||[]).length,5);
 const html=ctx.window.XC_SECT.homeHtml(d);assert.ok(html.includes('&lt;真实进度&gt;'));assert.ok(html.includes('青衡宗'));assert.equal((html.match(/class="xc-sect-place /g)||[]).length,7);
 event('data-xc-sect','story');assert.ok(controls.includes('disabled'));
 event('data-xc-chapter','tower');assert.ok(!spoken.includes('锁定'));
 event('data-xc-chapter','arrival');assert.equal(spoken,'一');event('data-xc-story','next');assert.equal(spoken,'二');
 event('data-xc-story','prev');assert.equal(spoken,'一');
 fail=true;event('data-xc-story','skip');await new Promise(setImmediate);assert.equal(errors,1);assert.equal(refreshes,0);
 fail=false;event('data-xc-story','skip');await new Promise(setImmediate);assert.equal(saves,2);assert.equal(refreshes,1);
 ctx.window.XC_SECT.mount({subject:'申论'},handlers);event('data-xc-chapter','arrival');event('data-xc-story','skip');await new Promise(setImmediate);assert.equal(saves,2);
 console.log('SECT-QUICK-OK');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
