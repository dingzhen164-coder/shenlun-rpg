/* 宗门相遇与人物交互。api.py提供相遇凭据和每人独立记录；无后台AI或计时奖励。
   configure接入当前公共场景；左侧抽屉只保存本机开合偏好，中央立绘与底部聊天沿用独立人物记录。 */
(() => {
  'use strict';
  let options = null, sceneKey = '', sequence = 0, opening = 0, meeting = null, panel = null, focusBack = null, queued = false;
  const drafts = new Map();
  let drawerExpanded = false;
  try { drawerExpanded = localStorage.getItem('npc-drawer-v1') === 'open'; } catch (_) {}
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const requestId = () => crypto.randomUUID ? crypto.randomUUID() : 'npc-' + Date.now() + '-' + Math.random().toString(36).slice(2);
  const draftKey = p => p.scope + ':' + p.body.id + ':' + p.mode;
  function rememberDraft() {
    const input = document.querySelector('.npc-input');
    if (panel && input) drafts.set(draftKey(panel), input.value);
  }
  function close() {
    ++opening;
    const dialog = document.querySelector('.npc-dialog');
    if (!dialog) return false;
    rememberDraft(); panel = null;
    dialog.close(); dialog.remove();
    if (focusBack?.isConnected) focusBack.focus();
    return true;
  }
  function image(p, kind, className) {
    const src = p.portraits?.[kind] || p.portraits?.bust || p.portraits?.three_quarter;
    return src ? `<img class="${className}" src="${esc(src)}" alt="${esc(p.name)}立绘">` : `<span class="${className} npc-monogram" aria-label="${esc(p.name)}，待添加立绘">${esc(p.name.slice(0, 2))}</span>`;
  }
  function renderPanel(focusInput = false) {
    if (!panel) return;
    const p = panel, data = p.data, person = data.character;
    let dialog = document.querySelector('.npc-dialog');
    if (!dialog) {
      dialog = document.createElement('dialog'); dialog.className = 'npc-dialog';
      dialog.setAttribute('role', 'dialog'); dialog.setAttribute('aria-labelledby', 'npc-name');
      dialog.addEventListener('cancel', e => { e.preventDefault(); close(); });
      document.body.append(dialog); dialog.showModal();
    }
    const chatting = ['chat', 'dao'].includes(p.mode), busy = p.busy ? 'disabled' : '';
    let content = '';
    if (chatting) {
      content = `<div class="npc-messages" tabindex="0" aria-label="与${esc(person.name)}的对话记录">${data.messages.length ? data.messages.map(m => `<article class="npc-message npc-${m.role === 'user' ? 'user' : 'reply'}"><b>${m.role === 'user' ? '你' : esc(person.name)}${m.mode === 'dao' ? ' · 论道' : m.mode === 'gift' ? ' · 收礼' : ''}</b><div>${esc(m.content)}</div></article>`).join('') : `<p>${esc(data.greeting)}</p>`}</div>
      <form class="npc-composer"><label for="npc-input">${p.mode === 'dao' ? '与对方论道：说一个问题，或解释你的思路' : '想说些什么？'}</label><textarea id="npc-input" class="npc-input" rows="3" maxlength="3000" placeholder="输入内容，Ctrl / Command + Enter 发送" ${busy}>${esc(drafts.get(draftKey(p)) || '')}</textarea><div class="npc-send-row"><small>${options.ai() ? '发送会调用你设置的 AI；聊天与论道不计分。' : '请先在设置中配置 AI，现有记录仍可查看。'}</small><button type="submit" ${busy || !options.ai() ? 'disabled' : ''}>${p.busy ? '正在回复…' : '发送'}</button></div></form>`;
    } else if (p.mode === 'gift') {
      content = `<h3>赠送物品</h3><p>送出后，储物袋扣除1件，该物品将不能再用于护心或渡劫。</p>${data.bag.length ? `<label>选择礼物<select class="npc-gift-select" ${busy}>${data.bag.map(x => `<option value="${esc(x.name)}">${esc(x.name)} · 持有${x.count}件</option>`).join('')}</select></label><button class="npc-give" ${busy}>赠送所选物品 ×1</button>` : '<p>储物袋暂无可赠送物品，先继续原有学习与任务即可。</p>'}<h3>送礼记录</h3><div class="npc-gift-history">${data.gifts.slice().reverse().map(x => `<p>${esc(x.date)} · ${esc(x.item)} ×1 · ${esc(x.feeling)}</p>`).join('') || '<p>还没有送过礼物。</p>'}</div>`;
    } else if (p.mode === 'memory') {
      content = `<h3>人物记忆</h3><p>留下希望对方记住的偏好和约定，只用于这位人物的后续对话。留空保存即可清除。</p><textarea class="npc-input npc-memory" aria-label="人物记忆" maxlength="3000" rows="10" ${busy}>${esc(drafts.has(draftKey(p)) ? drafts.get(draftKey(p)) : data.memory)}</textarea><button class="npc-save-memory" ${busy}>保存记忆</button>`;
    }
    dialog.classList.toggle('npc-talking', chatting);
    const choices = [['chat', '交流'], ['dao', '论道'], ['gift', '赠礼'], ['memory', '人物记忆']]
      .map(([mode, label]) => `<button data-npc-mode="${mode}" aria-pressed="${p.mode === mode}" ${busy}>${label}</button>`).join('');
    if (p.mode === 'menu') content = `<p class="npc-greeting">${esc(data.greeting)}</p><details class="npc-folder"><summary>人物资料</summary><p>人物卡、语录和立绘可自行修改：<br>${esc(data.folder)}</p><p>${data.messages.length ? `已保存${data.messages.length}条对话与收礼消息。` : '首次交谈，尚无对话记录。'} 游戏对话由AI生成。</p></details>`;
    dialog.innerHTML = `<header class="npc-header"><div class="npc-nameplate"><h2 id="npc-name">${esc(person.name)}</h2><span>${esc(person.role)} · ${esc(data.scene)}</span></div><button class="npc-close" aria-label="告辞，关闭人物界面">告辞 ×</button></header><div class="npc-main"><aside class="npc-portrait">${image(person, chatting ? 'bust' : 'three_quarter', 'npc-portrait-image')}</aside>${!chatting ? `<nav class="npc-choices" aria-label="与${esc(person.name)}互动">${choices}</nav>` : ''}</div><section class="npc-content ${chatting ? 'npc-chat-content' : p.mode === 'menu' ? 'npc-intro' : 'npc-utility-dock'}">${content}</section><footer class="npc-footer"><span class="npc-status" role="status">${esc(p.status || '')}</span>${p.mode !== 'menu' ? `<button class="npc-return" ${busy}>← 返回人物</button>` : ''}<button class="npc-reload" ${busy}>重新读取</button></footer>`;
    dialog.querySelectorAll('img').forEach(img => img.addEventListener('error', () => { const mark = document.createElement('span'); mark.className = img.className + ' npc-monogram'; mark.textContent = person.name.slice(0, 2); img.replaceWith(mark); }, {once: true}));
    dialog.querySelector('.npc-close').onclick = close;
    dialog.querySelectorAll('[data-npc-mode]').forEach(b => b.onclick = () => { rememberDraft(); p.mode = b.dataset.npcMode; p.status = ''; renderPanel(true); });
    dialog.querySelector('.npc-return')?.addEventListener('click', () => { rememberDraft(); p.mode = 'menu'; p.status = ''; renderPanel(); });
    dialog.querySelector('.npc-reload').onclick = () => perform('/api/characters/view');
    dialog.querySelector('.npc-composer')?.addEventListener('submit', e => { e.preventDefault(); sendChat(); });
    dialog.querySelector('.npc-input')?.addEventListener('keydown', e => { if (chatting && e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); sendChat(); } });
    dialog.querySelector('.npc-input')?.addEventListener('input', () => { rememberDraft(); p.pending = null; });
    dialog.querySelector('.npc-give')?.addEventListener('click', () => { const item = dialog.querySelector('.npc-gift-select').value; perform('/api/characters/action', {action:'gift', item}, '已赠送「' + item + '」×1'); });
    dialog.querySelector('.npc-save-memory')?.addEventListener('click', () => perform('/api/characters/action', {action:'memory', memory:dialog.querySelector('.npc-input').value}, '记忆已保存'));
    const select = dialog.querySelector('.npc-gift-select');
    if (select) { const label = () => { dialog.querySelector('.npc-give').textContent = '赠送「' + select.value + '」×1'; }; select.onchange = label; label(); }
    const messages = dialog.querySelector('.npc-messages'); if (messages) messages.scrollTop = messages.scrollHeight;
    if (focusInput) dialog.querySelector('.npc-input')?.focus();
    else if (!dialog.contains(document.activeElement)) dialog.querySelector('.npc-close')?.focus();
  }
  async function perform(url, extra = null, success = '') {
    const p = panel;
    if (!p || p.busy) return;
    rememberDraft(); p.busy = true; p.status = '';
    const pendingKey = JSON.stringify(extra);
    let body = {...p.body};
    if (extra) {
      if (!p.pending || p.pending.key !== pendingKey) p.pending = {key:pendingKey, body:{...body, ...extra, revision:p.data.revision, request_id:requestId()}};
      body = p.pending.body;
    }
    renderPanel();
    try {
      const data = await options.api(url, body);
      if (panel !== p) return;
      p.data = data; p.pending = null; p.status = success;
      if (url.endsWith('/chat')) drafts.delete(draftKey(p));
      if (extra?.action === 'memory') drafts.delete(p.scope + ':' + p.body.id + ':memory');
    } catch (e) {
      if (panel !== p) return;
      p.status = e.message + '；输入已保留，可重试或重新读取人物记录。';
    } finally {
      if (panel === p) { p.busy = false; renderPanel(true); }
    }
  }
  function sendChat() {
    if (!panel || panel.busy || !options.ai()) return;
    const text = document.querySelector('.npc-input')?.value.trim();
    if (!text) return;
    perform('/api/characters/chat', {action:'chat', mode:panel.mode, text});
  }
  async function open(id, opener) {
    if (!meeting || panel) return;
    const body = {id, scene:meeting.scene, token:meeting.token}, currentSequence = sequence, ticket = ++opening, scope = options.scope();
    focusBack = opener;
    try {
      const data = await options.api('/api/characters/view', body);
      if (sequence !== currentSequence || ticket !== opening || options.scope() !== scope || !options.context()) return;
      panel = {body, data, scope:options.scope(), mode:'menu', busy:false, status:'', pending:null}; renderPanel();
    } catch (e) { if (sequence === currentSequence) options.error(e); }
  }
  function renderMeeting(root, data) {
    root.querySelector('.npc-encounters')?.remove();
    if (!data.characters?.length && !data.warnings?.length) return;
    root.classList.add('npc-map-host');
    const bar = document.createElement('section'); bar.className = 'npc-encounters'; bar.setAttribute('aria-label', '此处偶遇');
    bar.innerHTML = `<button class="npc-drawer-toggle" aria-expanded="${drawerExpanded}" aria-controls="npc-encounter-body"><span>此处偶遇 · ${data.characters.length}${data.warnings?.length ? ' !' : ''}</span><span class="npc-drawer-arrow" aria-hidden="true">${drawerExpanded ? '‹' : '›'}</span></button><div class="npc-encounter-body" id="npc-encounter-body" ${drawerExpanded ? '' : 'hidden'}><div class="npc-encounter-people">${data.characters.map(p => `<button class="npc-person" data-npc-id="${esc(p.id)}" aria-label="与${esc(p.name)}交谈">${image(p, 'bust', 'npc-avatar')}<span><b>${esc(p.name)}</b><small>${esc(p.role)}</small></span></button>`).join('')}</div>${data.warnings?.length ? `<p class="npc-config-warning">人物配置提示：${esc(data.warnings.join('；'))}</p>` : ''}</div>`;
    const toggle = bar.querySelector('.npc-drawer-toggle');
    toggle.onclick = () => {
      drawerExpanded = !drawerExpanded;
      toggle.setAttribute('aria-expanded', String(drawerExpanded));
      bar.querySelector('.npc-encounter-body').hidden = !drawerExpanded;
      bar.querySelector('.npc-drawer-arrow').textContent = drawerExpanded ? '‹' : '›';
      try { localStorage.setItem('npc-drawer-v1', drawerExpanded ? 'open' : 'closed'); } catch (_) {}
    };
    bar.querySelectorAll('[data-npc-id]').forEach(b => b.onclick = () => open(b.dataset.npcId, b));
    bar.querySelectorAll('img').forEach(img => img.addEventListener('error', () => { const mark=document.createElement('span'); mark.className='npc-avatar npc-monogram'; mark.textContent='人'; img.replaceWith(mark); }, {once:true}));
    (root.querySelector(':scope > .portal-world') || root).append(bar);
  }
  async function mount() {
    if (!options) return;
    const root = document.querySelector('#view'), scene = options.context();
    const scope = options.scope(), key = scope + ':' + scene;
    if (!scene || !root) {
      if (sceneKey) { ++sequence; sceneKey = ''; meeting = null; close(); }
      root?.querySelectorAll('.npc-encounters').forEach(x => x.remove()); root?.classList.remove('npc-map-host'); return;
    }
    if (key === sceneKey) {
      if (meeting && (meeting.characters.length || meeting.warnings?.length) && !root.querySelector('.npc-encounters')) renderMeeting(root, meeting);
      return;
    }
    close(); sceneKey = key; const seq = ++sequence; meeting = null;
    root.querySelectorAll('.npc-encounters').forEach(x => x.remove());
    try {
      const data = await options.api('/api/characters/encounter', {scene});
      if (seq !== sequence || options.context() !== scene || options.scope() !== scope) return;
      meeting = data; renderMeeting(root, data);
    } catch (e) { if (seq === sequence) options.error(e); }
  }
  function queueMount() { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; mount(); }); } }
  function configure(value) {
    options = value;
    const root = document.querySelector('#view');
    if (root) new MutationObserver(queueMount).observe(root, {childList:true, subtree:true});
    new MutationObserver(queueMount).observe(document.body, {childList:true});
    new MutationObserver(queueMount).observe(document.documentElement, {attributes:true, attributeFilter:['class']});
    queueMount();
  }
  window.CHARACTERS = {configure, mount, close};
})();
