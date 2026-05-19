/**
 * 与 Python 核心层通信的桥接 API (v2.0)
 */
window.bridge = {
  isReady: false,

  init() {
    return new Promise((resolve) => {
      window.addEventListener('pywebviewready', () => {
        this.isReady = true;
        resolve();
      });
      setTimeout(() => { if (!this.isReady) resolve(); }, 500);
    });
  },

  // ─── 快捷调用工厂 ───
  async _call(method, ...args) {
    if (window.pywebview && window.pywebview.api && window.pywebview.api[method]) {
      return await window.pywebview.api[method](...args);
    }
    console.warn(`pywebview.api.${method} 不可用`);
    return { code: 503, message: 'pywebview 未就绪' };
  },

  // 机器人控制
  startBot()   { return this._call('start_bot'); },
  stopBot()    { return this._call('stop_bot'); },
  getStatus()  { return this._call('get_status'); },

  // 配置
  getConfig()         { return this._call('get_config'); },
  saveConfig(config)  { return this._call('save_config', config); },

  // 子弹百科 CRUD
  getBulletLibrary()                            { return this._call('get_bullet_library'); },
  addCaliber(name)                              { return this._call('add_caliber', name); },
  updateCaliber(caliberId, name)                { return this._call('update_caliber', caliberId, name); },
  removeCaliber(caliberId)                      { return this._call('remove_caliber', caliberId); },
  addVariant(caliberId, name, tier)             { return this._call('add_variant', caliberId, name, tier); },
  updateVariant(caliberId, variantId, fields)   { return this._call('update_variant', caliberId, variantId, fields); },
  removeVariant(caliberId, variantId)           { return this._call('remove_variant', caliberId, variantId); },
  
  testOcr(coords)                               { return this._call('test_ocr', coords); },

  // 今日清单
  getTodayBullets()                    { return this._call('get_today_bullets'); },
  addTodayBullet(name, caliber, price) { return this._call('add_today_bullet', name, caliber, price); },
  removeTodayBullet(id)                { return this._call('remove_today_bullet', id); },
  updateTodayBullet(id, fields)        { return this._call('update_today_bullet', id, fields); },
  reorderTodayBullets(ids)             { return this._call('reorder_today_bullets', ids); },
};
