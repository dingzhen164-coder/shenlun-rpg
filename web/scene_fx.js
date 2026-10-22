/* 3.6.4 首页装饰：多景深四季、御剑与流星，只管外观。
 * localStorage scene-season=auto|random|四季|off；scene-season-minutes=15|30|60|120|240；
 * scene-season-cycle-v1={season,at,minutes}。刷新不重抽，离开/隐藏/减少动画停止RAF。
 * scene_clock.js统一时钟；申论室内仅微尘，御剑贴图只用于青衡宗。 */
(() => {
  'use strict';
  const root=document.documentElement, memory=new Map(), controllers=new Set();
  const LS=(k,d)=>{try{return localStorage.getItem(k)||memory.get(k)||d;}catch(_){return memory.get(k)||d;}};
  const SET=(k,v)=>{memory.set(k,v);try{localStorage.setItem(k,v);}catch(_){/* 本次有效 */}};
  const seasons=['spring','summer','autumn','winter'], intervals=[15,30,60,120,240];
  const names={spring:'春 · 花雨',summer:'夏 · 流萤',autumn:'秋 · 金叶',winter:'冬 · 瑞雪',off:'关闭'};
  const rnd=(a,b)=>a+Math.random()*(b-a), tau=Math.PI*2, phase=d=>SCENE_CLOCK.phase(d);
  function season(d=new Date()){const m=d.getMonth()+1;return m>=3&&m<=5?'spring':m>=6&&m<=8?'summer':m>=9&&m<=11?'autumn':'winter';}
  const minutes=()=>{const n=Number(LS('scene-season-minutes','60'));return intervals.includes(n)?n:60;};
  function cycle(now){
    const m=minutes(), duration=m*60000;let s;
    try{s=JSON.parse(LS('scene-season-cycle-v1','null'));}catch(_){}
    if(!s||!seasons.includes(s.season)||!Number.isFinite(s.at)||s.at>now||s.minutes!==m){
      s={season:s&&seasons.includes(s.season)?s.season:seasons[Math.floor(rnd(0,4))],at:now,minutes:m};SET('scene-season-cycle-v1',JSON.stringify(s));
    }else if(now-s.at>=duration){
      // 离开多个周期也只补当前状态，不逐次补播，不连续重复。
      const pool=seasons.filter(x=>x!==s.season);
      s={season:pool[Math.floor(rnd(0,3))],at:s.at+Math.floor((now-s.at)/duration)*duration,minutes:m};SET('scene-season-cycle-v1',JSON.stringify(s));
    }return s;
  }
  function resolve(d=new Date()){
    const {ph,img}=SCENE_CLOCK.resolve(),mode=LS('scene-season','auto'),s=mode==='random'?cycle(d.getTime()):null;
    return {ph,img,se:s?s.season:mode==='off'?'off':seasons.includes(mode)?mode:season(d),next:s?s.at+s.minutes*60000:null};
  }
  let current,timer;
  function settingsState(){
    const random=LS('scene-season','auto')==='random';
    document.querySelectorAll('[data-scene-interval]').forEach(el=>{el.hidden=!random;});
    document.querySelectorAll('[data-scene-season-status]').forEach(el=>{
      const text=random?`当前：${names[current.se]} · 每${minutes()}分钟随机轮换（不会连续重复）`:'只影响场景装饰；减少动画时停止飘落、御剑与流星。';
      if(el.textContent!==text)el.textContent=text;
    });
  }
  function apply(){
    current=resolve();SCENE_CLOCK.apply();if(root.dataset.sceneSeason!==current.se)root.dataset.sceneSeason=current.se;
    settingsState();controllers.forEach(c=>c.sync());clearTimeout(timer);
    timer=setTimeout(apply,Math.max(200,Math.min(60000,current.next?current.next-Date.now():60000)));
  }
  const palette={spring:['#f6c3d1','#fff1e8','#e4a5bb'],summer:['#e0f3a4','#f4d997'],autumn:['#d8a04a','#bb6a38','#e6c781'],winter:['#eef5ff','#bdd5e8']};
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  const still=()=>['reduced','paused'].includes(root.dataset.motion)||document.hidden||media.matches;
  function mount(atm){
    if(atm.dataset.fx)return;atm.dataset.fx='1';
    const indoor=!!atm.closest('.portal-guantu'),swords=!!atm.closest('.portal-xingce');atm.dataset.fxRoom=indoor?'indoor':'outdoor';
    const cv=document.createElement('canvas');cv.className='portal-fx';cv.setAttribute('aria-hidden','true');atm.appendChild(cv);
    const tint=document.createElement('i');tint.className='portal-tint';atm.prepend(tint);
    const rays=document.createElement('div');rays.className='portal-rays';rays.innerHTML='<i></i><i></i><i></i>';atm.insertBefore(rays,cv);
    ['m1','m2','m3'].forEach(c=>{const m=document.createElement('i');m.className='portal-mist '+c;atm.insertBefore(m,cv);});
    const ctx=cv.getContext('2d');if(!ctx)return;
    const traveler=swords?new Image():null;if(traveler)traveler.src='assets/beauty/fx/sword-traveler.webp';
    let W=1,H=1,key='',parts=[],stars=[],dust=[],flight=null,meteor=null,birds=[],elapsed=0,raf=0,last=0;
    let nextFlight=rnd(7000,14000),nextMeteor=rnd(9000,18000),nextBird=rnd(9000,18000);
    const state=()=>({...current,ph:root.dataset.scenePhase||current.ph,img:root.dataset.sceneTime||current.img});
    function seed(){
      const r=state();key=r.se+r.img;const count=r.se==='winter'?70:r.se==='summer'?32:38;
      parts=!indoor&&palette[r.se]?Array.from({length:Math.round(count*Math.min(1,W/1000))},()=>{
        const depth=rnd(.25,1);return {x:rnd(0,W),y:rnd(-H*.15,H),depth,r:(r.se==='winter'?3:7)*depth,a:rnd(0,tau),spin:rnd(-.0007,.0007),p:rnd(0,tau),c:palette[r.se][Math.floor(rnd(0,palette[r.se].length))]};
      }):[];
      stars=!indoor&&r.img==='night'?Array.from({length:42},()=>({x:rnd(0,W),y:rnd(0,H*.32),r:rnd(.45,1.2),p:rnd(0,tau)})):[];
      dust=Array.from({length:indoor?12:18},()=>({x:rnd(0,W),y:rnd(H*.2,H),r:rnd(.5,1.6),p:rnd(0,tau)}));if(r.img!=='night')meteor=null;
    }
    function size(){const b=atm.getBoundingClientRect(),dpr=Math.min(1.5,window.devicePixelRatio||1);W=Math.max(1,b.width);H=Math.max(1,b.height);cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);seed();}
    function glow(x,y,r,color,alpha){const g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,color);g.addColorStop(1,'rgba(255,255,255,0)');ctx.globalAlpha=alpha;ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2);}
    function particle(p,dt,t,r){
      const summer=r.se==='summer',winter=r.se==='winter';
      p.x+=(summer?Math.sin(t/1800+p.p)*.007:.008+p.depth*.014+Math.sin(t/5000+p.p)*.008)*dt;
      p.y+=(summer?Math.sin(t/2700+p.p)*.006:.012+p.depth*.023)*dt;p.a+=p.spin*dt;
      if(p.y>H+15){p.y=-15;p.x=rnd(0,W);}if(p.x>W+15)p.x=-15;if(p.x<-15)p.x=W+15;
      if(summer){
        if(p.y<H*.35)p.y+=dt*.015;const a=(.2+.6*Math.pow((1+Math.sin(t/1200+p.p))/2,2))*(r.img==='night'?1:.3);
        glow(p.x,p.y,5+p.depth*7,p.c,a*.55);ctx.globalAlpha=a;ctx.fillStyle=p.c;ctx.beginPath();ctx.arc(p.x,p.y,.65+p.depth,0,tau);ctx.fill();return;
      }
      ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.a);ctx.scale(1,.35+.65*Math.abs(Math.sin(t/1600+p.p)));ctx.globalAlpha=.35+p.depth*.48;ctx.fillStyle=p.c;const s=p.r;
      if(winter){
        if(p.depth>.75){ctx.strokeStyle=p.c;ctx.lineWidth=.65;for(let i=0;i<3;i++){ctx.rotate(Math.PI/3);ctx.beginPath();ctx.moveTo(-s,0);ctx.lineTo(s,0);ctx.stroke();}}
        else{ctx.beginPath();ctx.arc(0,0,s*.65,0,tau);ctx.fill();}
      }else if(r.se==='spring'){
        ctx.beginPath();ctx.moveTo(-s,0);ctx.bezierCurveTo(-s,-s*.8,s*.3,-s*.75,s,0);ctx.bezierCurveTo(s*.35,s*.4,-s*.15,s*.85,-s,0);ctx.fill();
        ctx.strokeStyle='#fff6ed';ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(-s*.7,0);ctx.quadraticCurveTo(0,-s*.2,s*.7,0);ctx.stroke();
      }else{
        ctx.beginPath();ctx.moveTo(-s,0);ctx.lineTo(-s*.45,-s*.3);ctx.lineTo(-s*.3,-s*.75);ctx.lineTo(0,-s*.5);ctx.lineTo(s*.25,-s*.8);ctx.lineTo(s*.45,-s*.3);ctx.lineTo(s,0);ctx.quadraticCurveTo(s*.3,s*.65,-s,0);ctx.fill();
        ctx.strokeStyle='#926336';ctx.lineWidth=.65;ctx.beginPath();ctx.moveTo(-s,0);ctx.lineTo(s*.7,0);ctx.moveTo(0,0);ctx.lineTo(s*.25,-s*.55);ctx.moveTo(-s*.3,0);ctx.lineTo(-s*.3,-s*.4);ctx.stroke();
      }ctx.restore();
    }
    function sky(dt,t,r){
      stars.forEach(s=>{ctx.globalAlpha=.18+.5*(1+Math.sin(t/1900+s.p))/2;ctx.fillStyle='#e5edf5';ctx.beginPath();ctx.arc(s.x,s.y,s.r,0,tau);ctx.fill();});
      if(!indoor&&r.img==='night'&&!meteor&&t>nextMeteor){meteor={x:rnd(W*.35,W*.9),y:rnd(H*.02,H*.12),start:t,duration:rnd(1400,2200),span:rnd(W*.17,W*.3)};nextMeteor=t+rnd(26000,58000);}
      if(meteor){const k=(t-meteor.start)/meteor.duration;if(k>1)meteor=null;else{
        const x=meteor.x-k*meteor.span,y=meteor.y+k*H*.14,tail=meteor.span*.28,a=Math.sin(k*Math.PI),g=ctx.createLinearGradient(x,y,x+tail,y-tail*.42);
        g.addColorStop(0,'#f4ead7');g.addColorStop(.25,'#b6d7ee');g.addColorStop(1,'rgba(182,215,238,0)');ctx.globalAlpha=a*.85;ctx.strokeStyle=g;ctx.lineWidth=1.4;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+tail,y-tail*.42);ctx.stroke();glow(x,y,5,'#f6edda',a*.7);
      }}
      // 小幅弧线、衣袂贴图和剑气；只在青衡宗出现，始终不接收指针。
      if(swords&&traveler?.complete&&traveler.naturalWidth&&!flight&&t>nextFlight){flight={start:t,duration:rnd(14000,21000),y:rnd(H*.13,H*.3),dir:Math.random()<.5?1:-1,size:rnd(38,58)};nextFlight=t+rnd(43000,76000);}
      if(flight){const k=(t-flight.start)/flight.duration;if(k>1)flight=null;else{
        const x=flight.dir===1?-90+(W+180)*k:W+90-(W+180)*k,y=flight.y-Math.sin(k*Math.PI)*H*.045;
        ctx.save();ctx.translate(x,y);ctx.scale(flight.dir,1);ctx.globalAlpha=Math.min(1,k*8,(1-k)*8)*.78;
        const trail=ctx.createLinearGradient(-85,0,-8,0);trail.addColorStop(0,'rgba(190,225,232,0)');trail.addColorStop(1,'rgba(190,225,232,.4)');ctx.strokeStyle=trail;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(-85,9);ctx.quadraticCurveTo(-45,14,-5,5);ctx.stroke();ctx.drawImage(traveler,-flight.size*.6,-flight.size*.65,flight.size*1.6,flight.size);ctx.restore();
      }}
      if(!indoor&&r.img!=='night'&&t>nextBird){birds=[0,1,2].map(i=>({x:-30-i*24,y:rnd(H*.12,H*.18),p:i*1.3,s:3+i*.5}));nextBird=t+rnd(32000,54000);}
      birds=birds.filter(b=>b.x<W+30);birds.forEach(b=>{b.x+=dt*.035;const f=Math.sin(t/210+b.p)*b.s;ctx.globalAlpha=.45;ctx.strokeStyle='#5b6d6d';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(b.x-b.s,b.y-f);ctx.quadraticCurveTo(b.x-b.s/2,b.y-1,b.x,b.y);ctx.quadraticCurveTo(b.x+b.s/2,b.y-1,b.x+b.s,b.y-f);ctx.stroke();});
    }
    function draw(dt,t){
      const r=state();if(key!==r.se+r.img)seed();ctx.clearRect(0,0,W,H);if(!indoor)sky(dt,t,r);
      dust.forEach(p=>{p.y-=dt*.005;p.x+=Math.sin(t/4000+p.p)*dt*.003;if(p.y<0)p.y=H;glow(p.x,p.y,p.r*3,'#e6ce94',(.13+.13*Math.sin(t/2200+p.p))*(r.img==='night'?1:.55));});
      parts.forEach(p=>particle(p,dt,t,r));ctx.globalAlpha=1;
    }
    function loop(ts){raf=0;if(!atm.isConnected){dispose();return;}if(still()){last=0;return;}raf=requestAnimationFrame(loop);if(last&&ts-last<33.3)return;const dt=last?Math.min(80,ts-last):16;last=ts;elapsed+=dt;draw(dt,elapsed);}
    function sync(){
      if(!atm.isConnected){dispose();return;}
      if(still()){cancelAnimationFrame(raf);raf=0;last=0;ctx.clearRect(0,0,W,H);atm.dataset.fxRunning='false';}
      else{atm.dataset.fxRunning='true';if(!raf)raf=requestAnimationFrame(loop);}
    }
    function dispose(){cancelAnimationFrame(raf);resize.disconnect();controllers.delete(controller);}
    const controller={sync,dispose,node:atm},resize=new ResizeObserver(()=>{if(!atm.isConnected)dispose();else size();});resize.observe(atm);controllers.add(controller);size();sync();
  }
  function scan(){controllers.forEach(c=>{if(!c.node.isConnected)c.dispose();});document.querySelectorAll('.portal-atmosphere').forEach(mount);settingsState();}
  document.addEventListener('change',e=>{
    const t=e.target.closest?.('select[data-scene-time],select[data-scene-season],select[data-scene-minutes]');if(!t)return;
    if(t.hasAttribute('data-scene-time'))SET('scene-time',t.value);else if(t.hasAttribute('data-scene-season'))SET('scene-season',t.value);else if(intervals.includes(Number(t.value)))SET('scene-season-minutes',t.value);apply();
  });
  document.addEventListener('visibilitychange',apply);window.addEventListener('pageshow',apply);window.addEventListener('storage',apply);media.addEventListener?.('change',()=>controllers.forEach(c=>c.sync()));
  new MutationObserver(()=>{if(LS('scene-time','auto')==='theme')apply();else controllers.forEach(c=>c.sync());}).observe(root,{attributes:true,attributeFilter:['data-theme','data-motion']});
  const start=()=>{scan();new MutationObserver(scan).observe(document.getElementById('view')||document.body,{childList:true,subtree:true});};
  apply();if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
  window.SCENE_FX={phase,season,resolve,apply,settingsHtml(){
    const opts=(cur,list)=>list.map(([v,n])=>`<option value="${v}" ${cur===v?'selected':''}>${n}</option>`).join('');
    const comp=(window.BeautyCompanion?`<p>${BeautyCompanion.settingsHtml()}</p>`:'')+(window.BeautySway?`<p>${BeautySway.settingsHtml()}</p>`:'');
    return `<div class="portal-editor-tools"><label>场景时间<select data-scene-time>${opts(LS('scene-time','auto'),[['auto','自动（跟随时钟）'],['day','一直白天'],['night','一直夜晚'],['theme','跟随亮暗主题']])}</select></label>`+
      `<label>季节效果<select data-scene-season>${opts(LS('scene-season','auto'),[['auto','自动（按月份）'],['random','随机轮换'],...seasons.map(s=>[s,names[s]]),['off','关闭']])}</select></label>`+
      `<label data-scene-interval ${LS('scene-season','auto')==='random'?'':'hidden'}>轮换间隔<select data-scene-minutes>${opts(String(minutes()),intervals.map(m=>[String(m),m<60?`${m}分钟`:`${m/60}小时`]))}</select></label></div><p class="small muted" data-scene-season-status></p>`+comp;
  }};
})();
