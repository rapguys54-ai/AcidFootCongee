'use strict';
// ═══════════════════════════════════════
// AcidFootCongee — app.js v2.0
// ═══════════════════════════════════════

(function () {

  // ───── DOM 缓存 ─────
  const dom = {
    // 视图
    tabDashboard: document.getElementById('tabDashboard'),
    tabLibrary:   document.getElementById('tabLibrary'),
    viewDashboard: document.getElementById('viewDashboard'),
    viewLibrary:   document.getElementById('viewLibrary'),
    // 控制
    btnStart:     document.getElementById('btnStart'),
    btnStop:      document.getElementById('btnStop'),
    btnEmergency: document.getElementById('btnEmergency'),
    btnSaveConfig: document.getElementById('btnSaveConfig'),
    // 监控
    statusIndicator: document.getElementById('statusIndicator'),
    statusText:   document.getElementById('statusText'),
    monitorBadge: document.getElementById('monitorBadge'),
    currentPrice: document.getElementById('currentPrice'),
    priceTrend:   document.getElementById('priceTrend'),
    boughtCount:  document.getElementById('boughtCount'),
    elapsedTime:  document.getElementById('elapsedTime'),
    ocrCount:     document.getElementById('ocrCount'),
    currentBulletName:   document.getElementById('currentBulletName'),
    currentBulletBudget: document.getElementById('currentBulletBudget'),
    ocrCanvas:    document.getElementById('ocrCanvas'),
    systemTime:   document.getElementById('systemTime'),
    // 今日清单
    queueList:  document.getElementById('queueList'),
    queueEmpty: document.getElementById('queueEmpty'),
    btnGoLibrary:  document.getElementById('btnGoLibrary'),
    btnGoLibrary2: document.getElementById('btnGoLibrary2'),
    logStream: document.getElementById('logStream'),
    // 子弹百科
    caliberTree:  document.getElementById('caliberTree'),
    variantsGrid: document.getElementById('variantsGrid'),
    selectedCaliber: document.getElementById('selectedCaliber'),
    // 弹窗
    modalOverlay: document.getElementById('modalOverlay'),
    modalClose:   document.getElementById('modalClose'),
    modalCancel:  document.getElementById('modalCancel'),
    modalConfirm: document.getElementById('modalConfirm'),
    modalName:    document.getElementById('modalName'),
    modalCaliber: document.getElementById('modalCaliber'),
    modalMaxPrice: document.getElementById('modalMaxPrice'),
    // 配置
    inputScheduledTime:  document.getElementById('inputScheduledTime'),
    inputSoldOutTimeout: document.getElementById('inputSoldOutTimeout'),
    // CRUD DOM
    btnAddCaliber: document.getElementById('btnAddCaliber'),
    btnAddVariant: document.getElementById('btnAddVariant'),
    caliberModalOverlay: document.getElementById('caliberModalOverlay'),
    caliberModalClose: document.getElementById('caliberModalClose'),
    caliberModalCancel: document.getElementById('caliberModalCancel'),
    caliberModalConfirm: document.getElementById('caliberModalConfirm'),
    caliberModalName: document.getElementById('caliberModalName'),
    caliberModalTitle: document.getElementById('caliberModalTitle'),
    variantModalOverlay: document.getElementById('variantModalOverlay'),
    variantModalClose: document.getElementById('variantModalClose'),
    variantModalCancel: document.getElementById('variantModalCancel'),
    variantModalConfirm: document.getElementById('variantModalConfirm'),
    variantModalName: document.getElementById('variantModalName'),
    variantModalTier: document.getElementById('variantModalTier'),
    variantModalTitle: document.getElementById('variantModalTitle'),
  };

  // ───── 状态 ─────
  const state = {
    isRunning: false,
    prices: [],
    ocrHitCount: 0,
    startTime: null,
    timerInterval: null,
    bulletLibrary: null,   // 子弹百科数据
    todayBullets: [],      // 今日清单
    lastGrabbedCoord: null, // F8 上次抓取的坐标
    currentCaliberId: null, // 当前选中的口径ID
    editCaliberId: null,   // 正在编辑的口径ID
    editVariantId: null    // 正在编辑的变体ID
  };

  let chart = null;

  // ═══════════════════════════════════════
  // 视图切换
  // ═══════════════════════════════════════

  function switchView(viewName) {
    document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('view-tab--active'));
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('view-panel--active'));
    if (viewName === 'library') {
      dom.tabLibrary.classList.add('view-tab--active');
      dom.viewLibrary.classList.add('view-panel--active');
    } else {
      dom.tabDashboard.classList.add('view-tab--active');
      dom.viewDashboard.classList.add('view-panel--active');
    }
  }

  dom.tabDashboard.addEventListener('click', () => switchView('dashboard'));
  dom.tabLibrary.addEventListener('click', () => switchView('library'));
  dom.btnGoLibrary.addEventListener('click', () => switchView('library'));
  dom.btnGoLibrary2.addEventListener('click', () => switchView('library'));

  // ═══════════════════════════════════════
  // 坐标配置
  // ═══════════════════════════════════════

  const COORD_KEYS = ['search_box','first_card','slider_max','price_button','price_region','popup_region'];

  function loadCoordsToUI(coords) {
    if (!coords) return;
    for (const key of COORD_KEYS) {
      const val = coords[key];
      if (!val) continue;
      if (val.length === 2) {
        const ex = document.getElementById(`coord_${key}_x`);
        const ey = document.getElementById(`coord_${key}_y`);
        if (ex) ex.value = val[0];
        if (ey) ey.value = val[1];
      } else if (val.length === 4) {
        const e1 = document.getElementById(`coord_${key}_x1`);
        const e2 = document.getElementById(`coord_${key}_y1`);
        const e3 = document.getElementById(`coord_${key}_x2`);
        const e4 = document.getElementById(`coord_${key}_y2`);
        if (e1) e1.value = val[0];
        if (e2) e2.value = val[1];
        if (e3) e3.value = val[2];
        if (e4) e4.value = val[3];
      }
    }
  }

  function readCoordsFromUI() {
    const coords = {};
    for (const key of COORD_KEYS) {
      const ex = document.getElementById(`coord_${key}_x`);
      if (ex) {
        const ey = document.getElementById(`coord_${key}_y`);
        coords[key] = [parseFloat(ex.value)||0, parseFloat(ey.value)||0];
      } else {
        const e1 = document.getElementById(`coord_${key}_x1`);
        if (e1) {
          coords[key] = [
            parseFloat(e1.value)||0,
            parseFloat(document.getElementById(`coord_${key}_y1`).value)||0,
            parseFloat(document.getElementById(`coord_${key}_x2`).value)||0,
            parseFloat(document.getElementById(`coord_${key}_y2`).value)||0,
          ];
        }
      }
    }
    return coords;
  }

  let waitingGrabKey = null;
  let grabStep = 0; // 0: off, 1: point1, 2: point2

  // F8 抓取后一键应用到指定坐标
  document.querySelectorAll('.btn-grab').forEach(btn => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.key;
      waitingGrabKey = key;
      const isRegion = !!document.getElementById(`coord_${key}_x1`);
      
      if (isRegion) {
        grabStep = 1;
        addLog('info', `🎯 [范围抓取] 步骤 1/2：请将鼠标移动到左上角，按下 F8 键`);
        btn.textContent = '⏳ 左上角 (F8)...';
      } else {
        grabStep = 1;
        addLog('info', `🎯 [单点抓取] 请将鼠标移动到目标位置，按下 F8 键`);
        btn.textContent = '⏳ 等待 F8...';
      }
      
      // 按钮状态反馈
      document.querySelectorAll('.btn-grab').forEach(b => {
        b.classList.remove('btn-grab--active');
        if(b !== btn) {
          b.textContent = '🎮 抓取 (F8)';
          b.style.opacity = '0.5';
        }
      });
      btn.classList.add('btn-grab--active');
      btn.style.opacity = '1';
    });
  });

  window.addEventListener('coord-grab', e => {
    state.lastGrabbedCoord = e.detail;
    
    if (waitingGrabKey) {
      const key = waitingGrabKey;
      const ex = document.getElementById(`coord_${key}_x`);
      const ey = document.getElementById(`coord_${key}_y`);
      
      const ex1 = document.getElementById(`coord_${key}_x1`);
      const ey1 = document.getElementById(`coord_${key}_y1`);
      const ex2 = document.getElementById(`coord_${key}_x2`);
      const ey2 = document.getElementById(`coord_${key}_y2`);
      
      const btn = document.querySelector(`.btn-grab[data-key="${key}"]`);

      if (ex && ey) {
        // 单点抓取
        ex.value = e.detail.rx;
        ey.value = e.detail.ry;
        addLog('success', `✅ 已自动填入单点坐标「${key}」: [${e.detail.rx}, ${e.detail.ry}]`);
        resetGrabState();
      } else if (ex1 && ey1 && ex2 && ey2) {
        // 范围抓取
        if (grabStep === 1) {
          ex1.value = e.detail.rx;
          ey1.value = e.detail.ry;
          grabStep = 2;
          addLog('info', `🎯 [范围抓取] 步骤 2/2：请移动到右下角，再次按下 F8 键`);
          if(btn) btn.textContent = '⏳ 右下角 (F8)...';
        } else if (grabStep === 2) {
          ex2.value = e.detail.rx;
          ey2.value = e.detail.ry;
          addLog('success', `✅ 已自动填入范围坐标「${key}」`);
          resetGrabState();
        }
      }
    } else {
      addLog('warning', `[F8] 抓取了坐标: [${e.detail.rx}, ${e.detail.ry}]，但你没有先点击任意「抓取」按钮！`);
    }
  });

  function resetGrabState() {
    waitingGrabKey = null;
    grabStep = 0;
    document.querySelectorAll('.btn-grab').forEach(b => {
      b.classList.remove('btn-grab--active');
      b.textContent = '🎮 抓取 (F8)';
      b.style.opacity = '1';
    });
  }

  // ═══════════════════════════════════════
  // 子弹百科
  // ═══════════════════════════════════════

  async function loadBulletLibrary() {
    if (!window.bridge) return;
    const res = await window.bridge.getBulletLibrary();
    if (res && res.code === 200) {
      state.bulletLibrary = res.data;
      renderCaliberTree(res.data.calibers);
      
      // 保持选中状态的渲染
      if(state.currentCaliberId) {
        const cal = res.data.calibers.find(c => c.id === state.currentCaliberId);
        if(cal) renderVariants(cal);
        else {
          state.currentCaliberId = null;
          dom.selectedCaliber.textContent = '请选择口径 →';
          dom.btnAddVariant.style.display = 'none';
        }
      }
    }
  }

  function renderCaliberTree(calibers) {
    dom.caliberTree.innerHTML = '';
    calibers.forEach(cal => {
      const div = document.createElement('div');
      div.className = 'caliber-item';
      if (cal.id === state.currentCaliberId) div.classList.add('caliber-item--active');
      div.innerHTML = `
        <div class="caliber-item__name">
          <span style="flex:1;">🔹 ${cal.name}</span>
          <span class="caliber-item__count">${cal.variants.length}</span>
          <div class="caliber-actions" style="display:flex;gap:4px;margin-left:8px;">
            <button class="btn-edit-cal" style="background:none;border:none;cursor:pointer;font-size:12px;" title="编辑">✏️</button>
            <button class="btn-del-cal" style="background:none;border:none;cursor:pointer;font-size:12px;" title="删除">🗑</button>
          </div>
        </div>`;
      
      div.querySelector('.caliber-item__name').addEventListener('click', (e) => {
        if(e.target.closest('button')) return; // ignore button clicks
        document.querySelectorAll('.caliber-item').forEach(c => c.classList.remove('caliber-item--active'));
        div.classList.add('caliber-item--active');
        state.currentCaliberId = cal.id;
        dom.selectedCaliber.textContent = cal.name;
        dom.btnAddVariant.style.display = 'inline-block';
        renderVariants(cal);
      });

      div.querySelector('.btn-edit-cal').addEventListener('click', () => {
        state.editCaliberId = cal.id;
        dom.caliberModalTitle.textContent = '编辑口径';
        dom.caliberModalName.value = cal.name;
        dom.caliberModalOverlay.classList.add('modal-overlay--active');
      });

      div.querySelector('.btn-del-cal').addEventListener('click', async () => {
        if(confirm(`确定删除口径「${cal.name}」及其所有子弹吗？`)) {
          const res = await window.bridge.removeCaliber(cal.id);
          if (res && res.code === 200) {
            addLog('success', `已删除口径：${cal.name}`);
            if(state.currentCaliberId === cal.id) {
              state.currentCaliberId = null;
              dom.selectedCaliber.textContent = '请选择口径 →';
              dom.btnAddVariant.style.display = 'none';
              dom.variantsGrid.innerHTML = '<div class="variants-empty"><span>👈 从左侧选择子弹口径</span></div>';
            }
            await loadBulletLibrary();
          } else {
            addLog('error', res.message || '删除失败');
          }
        }
      });

      dom.caliberTree.appendChild(div);
    });
  }

  function renderVariants(caliber) {
    const tierLabels = { 1:'Lv.1', 2:'Lv.2', 3:'Lv.3', 4:'Lv.4', 5:'Lv.5' };
    dom.variantsGrid.innerHTML = '';
    caliber.variants.forEach(v => {
      const inQueue = state.todayBullets.some(b => b.name === v.name);
      const tier = v.tier || 1;
      const card = document.createElement('div');
      card.className = `bullet-card bullet-card--tier-${tier}`;
      card.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <div style="display:flex;align-items:center;gap:8px;">
            <div class="bullet-card__name">${v.name}</div>
            <span class="bullet-tier bullet-tier--${tier}">${tierLabels[tier]}</span>
          </div>
          <div style="display:flex;gap:4px;">
            <button class="btn-edit-var" style="background:none;border:none;cursor:pointer;font-size:12px;opacity:0.6;" title="编辑">✏️</button>
            <button class="btn-del-var" style="background:none;border:none;cursor:pointer;font-size:12px;opacity:0.6;" title="删除">🗑</button>
          </div>
        </div>
        <div class="bullet-card__caliber">${caliber.name}</div>
        <div class="bullet-card__actions">
          <button class="btn-add-queue" ${inQueue ? 'disabled' : ''}>
            ${inQueue ? '✓ 已加入' : '+ 加入今日清单'}
          </button>
        </div>`;
      
      card.querySelector('.btn-edit-var').addEventListener('click', () => {
        state.editVariantId = v.id;
        dom.variantModalTitle.textContent = '编辑子弹';
        dom.variantModalName.value = v.name;
        dom.variantModalTier.value = v.tier;
        dom.variantModalOverlay.classList.add('modal-overlay--active');
      });

      card.querySelector('.btn-del-var').addEventListener('click', async () => {
        if(confirm(`确定删除子弹「${v.name}」吗？`)) {
          const res = await window.bridge.removeVariant(caliber.id, v.id);
          if (res && res.code === 200) {
            addLog('success', `已删除子弹：${v.name}`);
            await loadBulletLibrary();
          } else {
            addLog('error', res.message || '删除失败');
          }
        }
      });

      if (!inQueue) {
        card.querySelector('.btn-add-queue').addEventListener('click', () => {
          openAddModal(v.name, caliber.name);
        });
      }
      dom.variantsGrid.appendChild(card);
    });
  }

  // ═══════════════════════════════════════
  // 百科 CRUD 弹窗逻辑
  // ═══════════════════════════════════════

  // --- 口径弹窗 ---
  dom.btnAddCaliber.addEventListener('click', () => {
    state.editCaliberId = null;
    dom.caliberModalTitle.textContent = '添加口径';
    dom.caliberModalName.value = '';
    dom.caliberModalOverlay.classList.add('modal-overlay--active');
  });

  const closeCaliberModal = () => dom.caliberModalOverlay.classList.remove('modal-overlay--active');
  dom.caliberModalClose.addEventListener('click', closeCaliberModal);
  dom.caliberModalCancel.addEventListener('click', closeCaliberModal);

  dom.caliberModalConfirm.addEventListener('click', async () => {
    const name = dom.caliberModalName.value.trim();
    if(!name) return addLog('warning', '口径名称不能为空');
    let res;
    if (state.editCaliberId) {
      res = await window.bridge.updateCaliber(state.editCaliberId, name);
    } else {
      res = await window.bridge.addCaliber(name);
    }
    if (res && res.code === 200) {
      addLog('success', state.editCaliberId ? '口径已更新' : '口径已添加');
      closeCaliberModal();
      await loadBulletLibrary();
    } else {
      addLog('error', res.message || '保存失败');
    }
  });

  // --- 子弹变体弹窗 ---
  dom.btnAddVariant.addEventListener('click', () => {
    if(!state.currentCaliberId) return addLog('warning', '请先选择口径');
    state.editVariantId = null;
    dom.variantModalTitle.textContent = '添加子弹';
    dom.variantModalName.value = '';
    dom.variantModalTier.value = '1';
    dom.variantModalOverlay.classList.add('modal-overlay--active');
  });

  const closeVariantModal = () => dom.variantModalOverlay.classList.remove('modal-overlay--active');
  dom.variantModalClose.addEventListener('click', closeVariantModal);
  dom.variantModalCancel.addEventListener('click', closeVariantModal);

  dom.variantModalConfirm.addEventListener('click', async () => {
    const name = dom.variantModalName.value.trim();
    const tier = parseInt(dom.variantModalTier.value);
    if(!name) return addLog('warning', '子弹名称不能为空');
    if(!state.currentCaliberId) return addLog('error', '未选中口径');

    let res;
    if (state.editVariantId) {
      res = await window.bridge.updateVariant(state.currentCaliberId, state.editVariantId, {name, tier});
    } else {
      res = await window.bridge.addVariant(state.currentCaliberId, name, tier);
    }
    if (res && res.code === 200) {
      addLog('success', state.editVariantId ? '子弹已更新' : '子弹已添加');
      closeVariantModal();
      await loadBulletLibrary();
    } else {
      addLog('error', res.message || '保存失败');
    }
  });

  // ═══════════════════════════════════════
  // 添加子弹弹窗
  // ═══════════════════════════════════════

  function openAddModal(name, caliber) {
    dom.modalName.value = name;
    dom.modalCaliber.value = caliber;
    dom.modalMaxPrice.value = 1000;
    dom.modalOverlay.classList.add('modal-overlay--active');
  }

  function closeModal() {
    dom.modalOverlay.classList.remove('modal-overlay--active');
  }

  dom.modalClose.addEventListener('click', closeModal);
  dom.modalCancel.addEventListener('click', closeModal);
  dom.modalOverlay.addEventListener('click', e => {
    if (e.target === dom.modalOverlay) closeModal();
  });

  dom.modalConfirm.addEventListener('click', async () => {
    const name    = dom.modalName.value;
    const caliber = dom.modalCaliber.value;
    const price   = parseInt(dom.modalMaxPrice.value) || 1000;
    if (!window.bridge) return;
    const res = await window.bridge.addTodayBullet(name, caliber, price);
    if (res && res.code === 200) {
      addLog('success', `✅ 已加入今日清单：${name}（预算 ${price.toLocaleString()}）`);
      closeModal();
      await refreshTodayBullets();
      // 刷新百科视图中的按钮状态
      if (state.bulletLibrary) {
        const cal = state.bulletLibrary.calibers.find(c => c.name === caliber);
        if (cal) renderVariants(cal);
      }
    } else {
      addLog('warning', res ? res.message : '添加失败');
    }
  });

  // ═══════════════════════════════════════
  // 今日清单
  // ═══════════════════════════════════════

  async function refreshTodayBullets() {
    if (!window.bridge) return;
    const res = await window.bridge.getTodayBullets();
    if (res && res.code === 200) {
      state.todayBullets = res.data || [];
      renderQueue();
    }
  }

  function renderQueue() {
    const list = state.todayBullets;
    if (!list.length) {
      dom.queueEmpty.style.display = '';
      dom.queueList.innerHTML = '';
      return;
    }
    dom.queueEmpty.style.display = 'none';
    dom.queueList.innerHTML = '';
    list.forEach((b, idx) => {
      const statusClass = b.status === 'running' ? 'queue-card--running'
        : b.status === 'done'  ? 'queue-card--done'
        : b.status === 'empty' ? 'queue-card--empty' : '';
      const statusEmoji = b.status === 'running' ? '🟢'
        : b.status === 'done'  ? '✅'
        : b.status === 'empty' ? '💀' : '🔵';
      const card = document.createElement('div');
      card.className = `queue-card ${statusClass}`;
      card.style.animationDelay = `${idx * 50}ms`;
      card.innerHTML = `
        <span class="queue-card__status"></span>
        <div class="queue-card__info">
          <div class="queue-card__name">${statusEmoji} ${b.name}</div>
          <div class="queue-card__meta">${b.caliber} · 预算 ${(b.max_price||0).toLocaleString()}</div>
        </div>
        <button class="queue-card__delete" data-id="${b.id}" title="删除">🗑</button>`;
      card.querySelector('.queue-card__delete').addEventListener('click', async (e) => {
        e.stopPropagation();
        card.classList.add('queue-card--removing');
        setTimeout(async () => {
          await window.bridge.removeTodayBullet(b.id);
          await refreshTodayBullets();
          addLog('info', `已移除：${b.name}`);
        }, 300);
      });
      dom.queueList.appendChild(card);
    });
  }

  // ═══════════════════════════════════════
  // 机器人控制
  // ═══════════════════════════════════════

  dom.btnStart.addEventListener('click', async () => {
    if (!window.bridge) return;
    const res = await window.bridge.startBot();
    if (res && res.code === 200) {
      setRunningUI(true);
    } else {
      addLog('warning', res ? res.message : '启动失败');
    }
  });

  dom.btnStop.addEventListener('click', async () => {
    if (!window.bridge) return;
    await window.bridge.stopBot();
    setRunningUI(false);
  });

  dom.btnEmergency.addEventListener('click', async () => {
    if (!window.bridge) return;
    await window.bridge.stopBot();
    setRunningUI(false);
    addLog('error', '🚨 紧急退出！');
  });

  function setRunningUI(running) {
    state.isRunning = running;
    dom.btnStart.disabled = running;
    dom.btnStop.disabled  = !running;
    dom.statusIndicator.classList.toggle('active', running);
    dom.statusText.textContent = running ? '扫货中...' : '待命中';
    dom.monitorBadge.textContent = running ? 'ACTIVE' : 'STANDBY';
    dom.monitorBadge.classList.toggle('active', running);
    if (running) {
      state.startTime = Date.now();
      state.timerInterval = setInterval(updateTimer, 1000);
    } else {
      clearInterval(state.timerInterval);
    }
  }

  function updateTimer() {
    if (!state.startTime) return;
    const s = Math.floor((Date.now() - state.startTime) / 1000);
    const m = Math.floor(s / 60);
    dom.elapsedTime.textContent = `${String(m).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
  }

  // ═══════════════════════════════════════
  // 配置保存
  // ═══════════════════════════════════════

  dom.btnSaveConfig.addEventListener('click', async () => {
    if (!window.bridge) return;
    const data = {
      ui_coords: readCoordsFromUI(),
      scheduled_time: dom.inputScheduledTime.value || '',
      delays: {
        sold_out_timeout: parseFloat(dom.inputSoldOutTimeout.value) || 30
      }
    };
    const res = await window.bridge.saveConfig(data);
    if (res && res.code === 200) {
      dom.btnSaveConfig.classList.add('saved');
      dom.btnSaveConfig.textContent = '✓ 已保存';
      setTimeout(() => {
        dom.btnSaveConfig.classList.remove('saved');
        dom.btnSaveConfig.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg> 保存坐标配置`;
      }, 2000);
      addLog('success', '配置已保存');
    }
  });

  // ═══════════════════════════════════════
  // 日志
  // ═══════════════════════════════════════

  function addLog(level, message) {
    const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    const icons = { success:'✅', error:'❌', warning:'⚠️', info:'ℹ️' };
    const entry = document.createElement('div');
    entry.className = `log-entry log-entry--${level}`;
    entry.innerHTML = `<span class="log-entry__time">${ts}</span>
      <span class="log-entry__icon">${icons[level]||'•'}</span>
      <span class="log-entry__msg">${message}</span>`;
    dom.logStream.prepend(entry);
    if (dom.logStream.children.length > 100) dom.logStream.lastChild.remove();
  }

  // ═══════════════════════════════════════
  // 图表
  // ═══════════════════════════════════════

  function initChart() {
    const ctx = document.getElementById('priceChart');
    if (!ctx || typeof Chart === 'undefined') return;
    chart = new Chart(ctx, {
      type: 'line',
      data: { labels: [], datasets: [{ data: [], borderColor: '#4ade80', borderWidth: 1.5, fill: false, pointRadius: 0, tension: 0.3 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { display: false }, y: { ticks: { color: '#666', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } } } }
    });
  }

  function pushChartPrice(price) {
    if (!chart || price == null) return;
    chart.data.labels.push('');
    chart.data.datasets[0].data.push(price);
    if (chart.data.labels.length > 50) { chart.data.labels.shift(); chart.data.datasets[0].data.shift(); }
    chart.update('none');
  }

  // ═══════════════════════════════════════
  // 后端事件监听
  // ═══════════════════════════════════════

  window.addEventListener('bot-log', e => {
    const d = e.detail;
    addLog(d.level.toLowerCase(), d.message);
  });

  window.addEventListener('bot-status', e => {
    const d = e.detail;
    if (d.last_price != null) {
      state.ocrHitCount++;
      dom.ocrCount.textContent = state.ocrHitCount;
      dom.currentPrice.textContent = d.last_price.toLocaleString();
      pushChartPrice(d.last_price);
    }
    if (d.total_purchases != null) dom.boughtCount.textContent = d.total_purchases.toLocaleString();
    if (d.current_bullet) {
      dom.currentBulletName.textContent = d.current_bullet;
    }
    if (d.max_price != null) {
      dom.currentBulletBudget.textContent = d.max_price.toLocaleString();
    }
    if (d.is_running === true && !state.isRunning)  setRunningUI(true);
    if (d.is_running === false && state.isRunning) setRunningUI(false);
    // 刷新任务卡片状态
    if (d.bullet_statuses) {
      state.todayBullets.forEach(b => {
        if (d.bullet_statuses[b.id]) b.status = d.bullet_statuses[b.id];
      });
      renderQueue();
    }
  });


  // ═══════════════════════════════════════
  // 系统时钟
  // ═══════════════════════════════════════

  setInterval(() => {
    dom.systemTime.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  }, 1000);

  // ═══════════════════════════════════════
  // 初始化
  // ═══════════════════════════════════════

  async function init() {
    if (window.bridge) {
      await window.bridge.init();
      // 加载配置
      const cfgRes = await window.bridge.getConfig();
      if (cfgRes && cfgRes.code === 200) {
        const cfg = cfgRes.data;
        loadCoordsToUI(cfg.ui_coords);
        if (cfg.scheduled_time) dom.inputScheduledTime.value = cfg.scheduled_time;
        if (cfg.delays && cfg.delays.sold_out_timeout) {
          dom.inputSoldOutTimeout.value = cfg.delays.sold_out_timeout;
        }
      }
      // 加载子弹百科
      await loadBulletLibrary();
      // 加载今日清单
      await refreshTodayBullets();
    }
    initChart();
    addLog('info', '🎮 系统就绪，等待指令...');
  }

  // 延迟初始化，等待 pywebview bridge
  if (window.bridge) {
    init();
  } else {
    window.addEventListener('pywebviewready', init);
  }

})();
