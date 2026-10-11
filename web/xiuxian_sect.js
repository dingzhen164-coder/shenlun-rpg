/* 青衡宗地图与剧情阅读：app.js 注入旧入口及 API；数据来自 dashboard.sect。
   按实际记录解锁，阅读/跳过只记录章节已读，不增奖励；用户上传场景随程序离线分发，洞府选择仅记本机显示偏好。
   无自动弹出、不调用 AI；对话使用 XC_GUIDE 的立绘/逐字文本/键盘收起。 */
(() => {
  'use strict';
  const escape = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let data, handlers, page = 0, current, pending = false;
  const places = [
    ['guide','清禾静室','今日建议',17,54],['study','五脉修炼殿','复习 · 训练',46,38],
    ['library','藏经阁','知识 · 手札',76,34],['tower','试炼塔','真题实战',87,57],
    ['wrong','照心台','错题复盘',64,76],['contest','演武场','模考 · 大比',33,77],['schedule','洞府','备考日程',12,88],
  ];
  const rooms = [
    {id:'yan',name:'辨言阁',subject:'言语理解',hint:'看透措辞，辨明主旨'},
    {id:'shu',name:'演数峰',subject:'数量关系',hint:'推演变化，寻找解法'},
    {id:'li',name:'明理殿',subject:'判断推理',hint:'理清论证，识破迷障'},
    {id:'zi',name:'观星台',subject:'资料分析',hint:'从数据中看清趋势'},
    {id:'chang',name:'万象院',subject:'常识判断',hint:'认识天地与世间运行'},
  ];
  let room = 'li';
  try { const saved = localStorage.getItem('xc-sect-room'); if(rooms.some(r=>r.id===saved))room=saved; } catch(e){}
  function chamberHtml() {
    const r=rooms.find(r=>r.id===room);
    return `<section class="xc-sect-chamber" aria-label="五脉洞府场景"><img class="xc-sect-room-image" src="assets/sect/${r.id}.webp" alt="${r.name}洞府内景"><div class="xc-sect-room-copy"><span>五脉修炼殿 · 洞府场景</span><h3>${r.name}</h3><p>${r.subject} · ${r.hint}</p></div><div class="xc-sect-room-tabs" role="group" aria-label="切换洞府场景">${rooms.map(a=>`<button data-xc-room="${a.id}" aria-pressed="${a.id===room}">${a.name}<small>${a.subject}</small></button>`).join('')}</div></section>`;
  }
  function showRooms() {
    XC_GUIDE.show('五脉各有所长。先选一处洞府，再进入修炼殿按你的实际板块安排功课。这里切换场景，不替你更改训练或奖励。',chamberHtml()+'<button class="xc-sect-room-enter" data-xc-sect="enter">进入修炼殿</button>');
  }
  function homeHtml(d) {
    const sect=d.sect, tasks=d.plan?.tasks||[], tower=d.tower||{};
    if(!sect)return window.XC_GUIDE.homeHtml(d);
    return `<section class="xc-sect-scene" aria-label="青衡宗宗门地图"><header class="xc-sect-header"><div><span>五脉同修 · 明理致用</span><h2>青衡宗</h2></div><button data-xc-sect="story">宗门纪事${sect.unread?` <em>${sect.unread}段新剧情</em>`:''}</button></header><div class="xc-sect-landscape"><svg class="xc-sect-land" viewBox="0 0 1000 550" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs><linearGradient id="xcSectSky" x2="0" y2="1"><stop stop-color="#bdcfc5"/><stop offset="1" stop-color="#f3eedc"/></linearGradient></defs><rect width="1000" height="550" fill="url(#xcSectSky)"/><circle cx="765" cy="75" r="47" fill="#fff8df" opacity=".8"/><path d="M0 255 125 80 225 215 370 32 500 190 650 60 780 205 890 70 1000 225V550H0" fill="#78988d" opacity=".45"/><path d="M0 345 140 200 260 320 430 150 580 325 700 205 850 300 1000 190V550H0" fill="#486e61" opacity=".4"/><path d="M0 435Q240 280 500 405T1000 350V550H0" fill="#627c59"/><path d="M95 535Q170 365 430 400T850 310" stroke="#dbcda6" stroke-width="19" fill="none" opacity=".7"/><path d="M60 195Q270 150 470 205T980 195M0 310Q270 260 490 305T1000 280" fill="none" stroke="#f5f5e7" stroke-width="20" opacity=".3"/></svg><img class="xc-sect-map-image" src="assets/sect/map.webp" alt="青衡宗山水庭院">${places.map(([id,name,hint,x,y])=>`<button class="xc-sect-place xc-sect-${id}" data-xc-sect="${id}" style="--x:${x}%;--y:${y}%"><span class="xc-sect-map-mark" aria-hidden="true">◆</span><b>${name}</b><small>${id==='tower'?`第${escape(tower.current||1)}层 · ${escape(tower.completed||0)}题`:id==='wrong'?`${escape(d.redo||0)}道待复盘`:hint}</small></button>`).join('')}</div><footer class="xc-sect-footer"><button class="xc-sect-master" data-xc-guide="open" aria-label="与清禾师尊交谈"><img src="assets/guide/shen-qinghe.webp" alt="清禾师尊"><b>清禾师尊</b></button><div><p>${escape(XC_GUIDE.greeting(d))}</p><span>今日功课 ${tasks.filter(t=>t.done).length}/${tasks.length} · ${sect.remaining==null?'请设置仙门大选日期':sect.remaining>=0?`距仙门大选 ${sect.remaining} 天`:'本次赴选日期已过，可在洞府调整日程'}</span></div></footer></section><details class="xc-sect-lore"><summary>宗门五脉 · 修行由来</summary><p>青衡宗昔以辨理、推演、识势立道，典籍散失后五脉渐衰。你随沈清禾重修所学，以真题验道，最终赴仙门大选。</p><div>${[['辨言阁','言语理解'],['演数峰','数量关系'],['明理殿','判断推理'],['观星台','资料分析'],['万象院','常识判断']].map(([a,b])=>`<span><b>${a}</b> · ${b}</span>`).join('')}</div></details>`;
  }
  function mount(d, actions) {data=d;handlers=actions;current=null;page=0;}
  function catalogue() {
    current=null;
    XC_GUIDE.show('青衡宗昔日五脉并立，今日由你续写修行。剧情随真实学习记录解锁；可重读，也可跳过，不影响学习与成绩。',
      `<div class="xc-sect-chapters">${data.sect.chapters.map(c=>`<button data-xc-chapter="${escape(c.id)}" ${c.unlocked?'':'disabled'}><b>${escape(c.title)}</b><small>${c.unlocked?(c.read?'已读 · 可重读':'可阅读'):escape(c.condition)}</small></button>`).join('')}</div>`);
  }
  function showPage() {
    XC_GUIDE.show(current.lines[page],`<div class="xc-sect-story-controls"><span>${escape(current.title)} · ${page+1}/${current.lines.length}</span><button data-xc-story="skip">跳过本章</button>${page>0?'<button data-xc-story="prev">上一段</button>':''}<button data-xc-story="next">${page+1===current.lines.length?'记入宗门纪事':'下一段'}</button></div>`);
  }
  async function finish() {
    if(pending)return;pending=true;
    try { const sect=await handlers.saveStory(current.id);data.sect=sect;current=null;XC_GUIDE.close();await handlers.refresh(); }
    catch(e){handlers.error(e);}
    finally{pending=false;}
  }
  document.addEventListener('click',e=>{
    if(data?.subject!=='行测'||!data.sect)return;
    const choice=e.target.closest('[data-xc-room]');
    if(choice && rooms.some(r=>r.id===choice.dataset.xcRoom)) {
      room=choice.dataset.xcRoom;try{localStorage.setItem('xc-sect-room',room);}catch(e){}
      document.querySelectorAll('.xc-sect-chamber').forEach(el=>el.outerHTML=chamberHtml());
      document.querySelector(`[data-xc-room="${room}"]`)?.focus();return;
    }
    const place=e.target.closest('[data-xc-sect]');
    if(place){const action=place.dataset.xcSect;if(action==='story')catalogue();else if(action==='study')showRooms();else if(action==='enter'){XC_GUIDE.close();handlers?.study?.();}else handlers?.[action]?.();return;}
    const chapter=e.target.closest('[data-xc-chapter]');
    if(chapter){current=data.sect.chapters.find(c=>c.id===chapter.dataset.xcChapter&&c.unlocked);if(current){page=0;showPage();}return;}
    const control=e.target.closest('[data-xc-story]');if(!control||!current||pending)return;
    if(control.dataset.xcStory==='skip')return finish();
    if(control.dataset.xcStory==='prev'){page=Math.max(0,page-1);showPage();}
    if(control.dataset.xcStory==='next'){if(page+1===current.lines.length)finish();else{page++;showPage();}}
  });
  window.XC_SECT={homeHtml,mount,chamberHtml};
})();
