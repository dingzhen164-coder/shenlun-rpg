/* 3.0.5地图导航：app.js提供go/current回调；隐藏旧导航节点保留内部状态钩子。
   本机localStorage map-shortcuts-v1={settings:'Tab',home:'Escape'}，兼容旧dwelling按键，两科共用。
   设置里录入/保存/恢复快捷键；不写学习存档，输入及弹窗中保留Tab焦点操作。 */
(() => {
  'use strict';
  const KEY='map-shortcuts-v1', DEFAULTS={settings:'Tab',home:'Escape'};
  let actions, bindings, recording='', draft, busy=false, settingsReturn='home';
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label=s=>s.replace('Escape','Esc').replace(/Key([A-Z])/g,'$1').replace(/Digit([0-9])/g,'$1');
  function valid(s) {
    if(typeof s!=='string'||s.length>45)return false;
    const parts=s.split('+'),key=parts.pop();
    return /^(Escape|Tab|F[1-9]|F10)$/.test(key)&&parts.length===0
      || /^(Escape|Tab|F[1-9]|F10|Key[A-Z]|Digit[0-9])$/.test(key)
        && parts.length>0&&parts.every((p,i)=>['Ctrl','Alt','Shift','Meta'].includes(p)&&parts.indexOf(p)===i)
        && !(parts.includes('Ctrl')||parts.includes('Meta')? /^(Key[ACLNPRQTVWXYZ])$/.test(key):false);
  }
  function load() {
    try{const raw=JSON.parse(localStorage.getItem(KEY));const home=raw?.home??raw?.dwelling;if(raw&&valid(raw.settings)&&valid(home)&&raw.settings!==home){if(raw.schema!==2&&raw.settings==='Escape'&&home==='Tab')return {...DEFAULTS};return {settings:raw.settings,home};}}catch(e){}
    return {...DEFAULTS};
  }
  function chord(e) {
    return [e.ctrlKey?'Ctrl':'',e.altKey?'Alt':'',e.shiftKey?'Shift':'',e.metaKey?'Meta':'',e.code||e.key].filter(Boolean).join('+');
  }
  function configure(a){actions=a;bindings=load();}
  function settingsHtml() {
    draft={...bindings};recording='';
    return `<section class="card shortcut-settings"><h3>键盘快捷键</h3><p class="small muted">点击修改后按下新快捷键，再保存。本机两科共用；输入和弹窗中的Tab仍用于移动焦点。</p>${['settings','home'].map(id=>`<div class="shortcut-row"><label>${id==='settings'?'设置':'返回地图'}<input data-shortcut-value="${id}" value="${esc(label(draft[id]))}" readonly aria-label="${id==='settings'?'设置':'返回地图'}快捷键"></label><button data-shortcut-record="${id}">修改</button></div>`).join('')}<p class="small muted">支持Esc、Tab、F1—F10或带修饰键的字母/数字组合；常用编辑及浏览器快捷键保留。</p><div class="row"><button class="primary" data-shortcut-save>保存快捷键</button><button data-shortcut-reset>恢复默认</button><span data-shortcut-status role="status"></span></div></section><section class="card scene-utility-tools"><h3>界面工具</h3><div data-scene-tools></div><p>学习时长、音乐、专注与草稿工具移到这里；各板块由地图进入。</p></section>`;
  }
  function status(s){const el=document.querySelector('[data-shortcut-status]');if(el)el.textContent=s;}
  function updateFields(){for(const id of ['settings','home']){const el=document.querySelector(`[data-shortcut-value="${id}"]`);if(el)el.value=label(draft[id]);}}
  function beforeRender(){const tools=document.querySelector('.top-tools');if(tools)document.querySelector('.topbar')?.appendChild(tools);}
  function mount(view) {
    document.getElementById('mapPageTools')?.remove();
    if(!document.getElementById('pageSettingsGear')){const b=document.createElement('button');b.id='pageSettingsGear';b.type='button';b.dataset.hudSettings='';b.className='page-settings-gear';b.setAttribute('aria-label','打开设置');b.title='打开设置';b.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 2 3 3-1 1 4 4 2-2 3 1 4-4 1-3 4-2-3-4 1-1-4-4-2 2-3-1-4 4-1Z"/><circle cx="12" cy="12" r="3"/></svg>';document.body.append(b);}
    // 3.5.6 iPad没有Esc键：左下角放与设置齿轮同大的返回钮；地图首页没有上一层，隐藏
    let back=document.getElementById('pageBackBtn');
    if(!back){back=document.createElement('button');back.id='pageBackBtn';back.type='button';back.className='page-back-btn';back.setAttribute('aria-label','返回上一界面');back.title='返回上一界面';
      back.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5 8 12l7 7"/></svg>';document.body.append(back);}
    back.hidden=view==='home';
    const tools=document.querySelector('.top-tools'),slot=document.querySelector('[data-scene-tools]');
    if(tools)(view==='settings'&&slot?slot:document.querySelector('.topbar'))?.appendChild(tools);
    if(view!=='settings')recording='';
  }
  async function toggle(id) {
    if(busy||!actions)return;busy=true;
    try{
      const current=actions.current();
      const target=id==='home'?'home':current==='settings'?settingsReturn:'settings';
      if(target===current)return;
      if(document.documentElement.classList.contains('in-chat')&&!confirm('离开这次功课，切换界面？'))return;
      await actions.go(target);
      if(id==='settings'&&actions.current()==='settings'&&current!=='settings')settingsReturn=current;
    }finally{busy=false;}
  }
  function closeTransient() {
    if(window.NARRATIVE?.close()||window.XC_GUIDE?.close(true))return true;
    for(const s of ['.img-zoom','.cer-ok','.st-btn']){const el=document.querySelector(s);if(el){el.click();return true;}}
    if(document.documentElement.classList.contains('drawing')&&window.DRAW){DRAW.close();return true;}
    if(window.NOTES?.isFull()){NOTES.exitFull();return true;}
    if(window.CARDS?.isOpen()){CARDS.close();return true;}
    if(window.MINDMAP?.isOpen()){MINDMAP.close();return true;}
    const m=document.getElementById('modal');if(m&&!m.classList.contains('hidden')){m.classList.add('hidden');return true;}
    if(window.FOCUS?.isOn()){FOCUS.exit();return true;}
    return false;
  }
  document.addEventListener('keydown',e=>{
    if(!actions||e.repeat||e.isComposing)return;
    if(recording){
      e.preventDefault();e.stopImmediatePropagation();if(['Control','Alt','Shift','Meta'].includes(e.key))return;
      const next=chord(e);if(!valid(next)){status('请选择支持的快捷键，常用编辑和浏览器快捷键不可占用。');return;}
      const other=recording==='settings'?'home':'settings';if(next===draft[other]){status('两项快捷键不能相同，请换一个。');return;}
      draft[recording]=next;recording='';updateFields();status('尚未保存');return;
    }
    if(e.key==='Escape'&&!e.ctrlKey&&!e.altKey&&!e.shiftKey&&!e.metaKey&&closeTransient()){e.preventDefault();e.stopImmediatePropagation();return;}
    const id=Object.keys(bindings).find(id=>bindings[id]===chord(e));if(!id)return;
    if(e.target?.closest?.('input,textarea,select,[contenteditable]:not([contenteditable="false"])')&&e.key!=='Escape')return;
    if(document.querySelector('.narrative-dialog,.xc-guide-dialogue,dialog[open],[role="dialog"],.modal:not(.hidden),.img-zoom')||document.documentElement.classList.contains('drawing'))return;
    // 输入、临时层保留Tab；普通页面（含设置）返回地图，Shift+Tab继续移动焦点。
    e.preventDefault();e.stopImmediatePropagation();toggle(id).catch(err=>actions.error(err));
  },true);
  document.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    if(b.hasAttribute('data-hud-home'))return toggle('home').catch(err=>actions.error(err));
    if(b.id==='pageBackBtn'){if(closeTransient())return;return toggle(actions.current()==='settings'?'settings':'home').catch(err=>actions.error(err));}
    if(b.hasAttribute('data-hud-settings')){closeTransient();return toggle('settings').catch(err=>actions.error(err));}
    if(b.dataset.shortcutRecord){recording=b.dataset.shortcutRecord;status('现在按下新的快捷键…');return;}
    if(b.hasAttribute('data-shortcut-reset')){draft={...DEFAULTS};recording='';updateFields();status('已恢复默认，保存后生效');}
    if(b.hasAttribute('data-shortcut-save')){
      if(recording){status('请先完成快捷键录入');return;}
      try{localStorage.setItem(KEY,JSON.stringify({...draft,schema:2}));bindings={...draft};status('快捷键已保存');mount('settings');}
      catch(err){status('保存失败，原快捷键保持，请检查浏览器存储权限。');}
    }
  });
  window.MAP_NAVIGATION={configure,settingsHtml,mount,beforeRender,valid};
})();
