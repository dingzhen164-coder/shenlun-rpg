/* 固定场景内容区：fixed_layout挂载时标记面板，尺寸由CSS适配电脑/平板。
   不再读取旧scene-panels-v1宽高偏好，已有学习内容和字号保持不变。 */
(() => {
  'use strict';
  function mount(root,route) {
    if(route==='home')return;
    root.querySelectorAll('.fx-shell,.fx-region-detail,.tj-hub,.tj-issue,.ex-page').forEach(node=>node.classList.add('scene-panel'));
  }
  window.SCENE_PANELS={mount};
})();
