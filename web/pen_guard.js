/* 手写笔防丢笔（3.5.8）：红格答题卡、材料勾画、做题勾画共用。手札（notes.js）里有同样逻辑的内联版。
   iPad + Apple Pencil 快速连写（写完一画立刻写下一画）会丢笔，已知原因：
   ①Safari 的滚动 / 双击缩放手势抢走新一笔 → 在 touchstart/touchmove 上阻止默认行为；
   ②上一笔的 pointerup / lostpointercapture 晚到（笔的 pointerId 每笔相同），把刚落下的新一笔收掉 → lateUp() 忽略它；
   ③落笔事件被吞 → missedDown() 补一笔；笔已离开纸面却没收到抬笔 → lifted()；笔迹中断太久 → idle() 自动收笔。
   用法：const g = PEN_GUARD.make(canvas); 落笔时 g.down(已有一笔?)；抬笔时 if (g.lateUp(e)) return；移动时 g.missedDown(e,有没有笔) / g.lifted(e,有没有笔)；g.idle(fn) 每次有笔迹动作时续期。 */
(function () {
  const stop = (e) => e.preventDefault();
  function make(canvas) {
    for (const ev of ['touchstart', 'touchmove']) canvas.addEventListener(ev, stop, { passive: false });
    for (const ev of ['gesturestart', 'gesturechange', 'contextmenu', 'selectstart']) canvas.addEventListener(ev, stop);
    let overlapAt = 0, noContact = 0, idleT = 0;
    return {
      down(hadStroke) { overlapAt = hadStroke ? performance.now() : 0; noContact = 0; },
      // 新一笔落下时上一笔没收尾：它的 pointerup 随后才到，属于上一笔，不能收掉新一笔
      lateUp(e) {
        if ((e.type === 'pointerup' || e.type === 'lostpointercapture') && overlapAt && performance.now() - overlapAt < 250) { overlapAt = 0; return true; }
        return false;
      },
      missedDown(e, hasStroke) { return e.pointerType === 'pen' && !hasStroke && (e.buttons & 1) === 1 && e.pressure > 0; },
      lifted(e, hasStroke) {                                   // 笔已离开纸面（连续两次才算，防个别设备压力读数为 0）
        if (hasStroke && e.pointerType === 'pen' && e.buttons === 0 && e.pressure === 0) return ++noContact >= 2;
        noContact = 0; return false;
      },
      idle(fn) { clearTimeout(idleT); if (fn) idleT = setTimeout(fn, 900); },
    };
  }
  window.PEN_GUARD = { make };
})();
