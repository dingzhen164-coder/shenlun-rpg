/* 学习蜡烛：手动开关覆盖当前页面的自动检测；离页/换阅读材料恢复自动。
   前台且120秒内有操作才计时，凭据由服务端签发；不在前端计算经验。 */
(() => {
 'use strict';
 let options={},context='',override=null,reading=null,token='',generation=0,starting=false,lastAction=Date.now(),lastTouch=0,failed=false;
 const visible=()=>document.visibilityState==='visible'&&Date.now()-lastAction<120000;
 const allows=()=>override!==false;
 const wanted=()=>!failed&&allows()&&visible()&&(override===true||!!reading);
 const active=()=>wanted()&&!!token;
 const paint=()=>{options.update?.();const el=document.getElementById('todayPill');if(el){el.setAttribute('role','button');el.tabIndex=0;el.setAttribute('aria-pressed',String(el.classList.contains('on')));el.setAttribute('aria-label',el.classList.contains('on')?'关闭学习蜡烛，暂停学习计时':'点亮学习蜡烛，开始学习计时');}};
 const request=async(path,body)=>{const r=await fetch('/api/study-lamp/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok||d.error)throw Error(d.error||'学习计时暂时不可用');return d;};
 async function closeToken(old){if(!old)return;try{await window.finishLampReading?.(old);await request('stop',{token:old});}catch(_){} }
 function reset(){generation++;const old=token;token='';starting=false;failed=false;closeToken(old);}
 async function ensure(){
  if(!wanted()||token||starting)return;starting=true;const version=generation;
  try{const d=await request('start',{board:reading?.board||options.board?.()||''});if(version!==generation||!wanted()){closeToken(d.token);return;}token=d.token;lastTouch=Date.now();}
  catch(e){if(version===generation){failed=true;window.showError?.(e);}}
  finally{if(version===generation){starting=false;paint();}}
 }
 function sync(){paint();ensure();}
 function act(){lastAction=Date.now();if(active()&&Date.now()-lastTouch>20000){lastTouch=Date.now();const old=token;request('touch',{token:old}).then(d=>{if(token===old&&!d.active){reset();sync();}}).catch(()=>{});}sync();}
 function toggle(){const on=allows()&&(wanted()||!!options.autoOn?.());override=!on;lastAction=Date.now();reset();sync();}
 for(const event of ['pointerdown','pointermove','keydown','scroll','input','touchmove'])window.addEventListener(event,()=>{lastAction=Date.now();if(Date.now()-lastTouch>20000)act();},{passive:true,capture:true});
 document.addEventListener('click',e=>{if(e.target.closest('#todayPill'))toggle();else act();});
 document.addEventListener('keydown',e=>{if(e.target.closest('#todayPill')&&['Enter',' '].includes(e.key)){e.preventDefault();toggle();}});
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState!=='visible')reset();sync();});
 window.STUDY_LAMP={configure:o=>{options=o;sync();},allows,wanted,active,token:()=>active()?token:'',
  context:value=>{if(value===context)return;context=value;override=null;reading=null;lastAction=Date.now();reset();sync();},
  reader:value=>{const key=value?.key||'';if(key!==(reading?.key||'')){override=null;reading=value||null;lastAction=Date.now();reset();}else reading=value||null;sync();},
  interaction:act,toggle,sync};
})();
