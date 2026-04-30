/**
 * Delta Force AutoBuy — 前端控制逻辑
 * 负责 UI 交互、模拟数据展示、图表渲染
 * 后续将对接后端 WebSocket / REST API
 */

(function () {
  'use strict';

  // ===== 状态管理 =====
  const state = {
    isRunning: false,
    isPaused: false,
    debugMode: false,
    startTime: null,
    elapsedSeconds: 0,
    boughtCount: 0,
    totalTarget: 3,
    prices: [],
    config: {
      maxPrice: 50000,
      buyAmount: 3,
      scheduledTime: '17:49',
      runDuration: 10,
    },
  };

  // ===== DOM 引用 =====
  const dom = {
    statusIndicator: document.getElementById('statusIndicator'),
    statusText: document.querySelector('.status-text'),
    statusDot: document.querySelector('.status-dot'),
    systemTime: document.getElementById('systemTime'),
    btnStart: document.getElementById('btnStart'),
    btnStop: document.getElementById('btnStop'),
    btnEmergency: document.getElementById('btnEmergency'),
    btnSettings: document.getElementById('btnSettings'),
    btnClearLogs: document.getElementById('btnClearLogs'),
    monitorBadge: document.getElementById('monitorBadge'),
    currentPrice: document.getElementById('currentPrice'),
    priceTrend: document.getElementById('priceTrend'),
    maxPriceDisplay: document.getElementById('maxPriceDisplay'),
    boughtCount: document.getElementById('boughtCount'),
    totalTarget: document.getElementById('totalTarget'),
    elapsedTime: document.getElementById('elapsedTime'),
    toggleDebug: document.getElementById('toggleDebug'),
    logStream: document.getElementById('logStream'),
    avgPrice: document.getElementById('avgPrice'),
    highPrice: document.getElementById('highPrice'),
    lowPrice: document.getElementById('lowPrice'),
    checkCount: document.getElementById('checkCount'),
    inputMaxPrice: document.getElementById('inputMaxPrice'),
    inputBuyAmount: document.getElementById('inputBuyAmount'),
    inputScheduledTime: document.getElementById('inputScheduledTime'),
    inputRunDuration: document.getElementById('inputRunDuration'),
    priceChart: document.getElementById('priceChart'),
    // 延迟配置输入框
    delayWindowFocus: document.getElementById('delayWindowFocus'),
    delayMouseMove: document.getElementById('delayMouseMove'),
    delayMouseDown: document.getElementById('delayMouseDown'),
    delayBuyButton: document.getElementById('delayBuyButton'),
    delayBuyComplete: document.getElementById('delayBuyComplete'),
    delayEscKey: document.getElementById('delayEscKey'),
    delayLoopInterval: document.getElementById('delayLoopInterval'),
    btnSaveConfig: document.getElementById('btnSaveConfig'),
  };

  // ===== 时钟 =====
  function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    dom.systemTime.textContent = `${h}:${m}:${s}`;
  }
  setInterval(updateClock, 1000);
  updateClock();

  // ===== 运行计时器 =====
  let timerInterval = null;

  function startTimer() {
    state.startTime = Date.now();
    timerInterval = setInterval(() => {
      state.elapsedSeconds = Math.floor((Date.now() - state.startTime) / 1000);
      const mins = String(Math.floor(state.elapsedSeconds / 60)).padStart(2, '0');
      const secs = String(state.elapsedSeconds % 60).padStart(2, '0');
      dom.elapsedTime.textContent = `${mins}:${secs}`;

      // 检查运行时长
      const durationSec = state.config.runDuration * 60;
      if (durationSec > 0 && state.elapsedSeconds >= durationSec) {
        addLog('warning', `已运行 ${state.config.runDuration} 分钟，自动停止`);
        stopMonitoring();
      }
    }, 1000);
  }

  function stopTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  // ===== 日志系统 =====
  function addLog(level, message) {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

    const icons = {
      info: '\u2139',
      success: '\u2713',
      warning: '\u26A0',
      error: '\u2717',
    };

    const entry = document.createElement('div');
    entry.className = `log-entry log-entry--${level} log-entry--new`;
    entry.innerHTML = `
      <span class="log-entry__time">${time}</span>
      <span class="log-entry__icon">${icons[level] || '\u25C6'}</span>
      <span class="log-entry__msg">${message}</span>
    `;

    dom.logStream.appendChild(entry);
    dom.logStream.scrollTop = dom.logStream.scrollHeight;

    // 移除动画类
    setTimeout(() => entry.classList.remove('log-entry--new'), 300);

    // 限制日志条数
    while (dom.logStream.children.length > 200) {
      dom.logStream.removeChild(dom.logStream.firstChild);
    }
  }

  // ===== 状态切换 =====
  function setRunningState(running) {
    state.isRunning = running;

    dom.statusIndicator.classList.toggle('active', running);
    dom.statusText.textContent = running ? '监控中' : '待命中';
    dom.monitorBadge.textContent = running ? 'ACTIVE' : 'STANDBY';
    dom.monitorBadge.classList.toggle('active', running);

    dom.btnStart.disabled = running;
    dom.btnStop.disabled = !running;

    if (running) {
      dom.btnStart.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        监控中...`;
    } else {
      dom.btnStart.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        开始监控`;
    }
  }

  // ===== 启动监控 =====
  async function startMonitoring() {
    // 读取最新配置
    syncConfigFromInputs();

    if (window.bridge) {
      const res = await window.bridge.startBot(state.config);
      if (res && res.code !== 200) {
        addLog('error', '启动失败: ' + res.message);
        return;
      }
    }

    setRunningState(true);
    startTimer();
    addLog('success', '开始自动购买监控');
    addLog('info', `最高价格: ${state.config.maxPrice.toLocaleString()} | 数量: ${state.config.buyAmount}`);

    // 启动模拟价格循环（如果没有检测到 pywebview 环境）
    if (!window.pywebview) {
        startPriceSimulation();
    }
  }

  // ===== 停止监控 =====
  async function stopMonitoring() {
    if (window.bridge) {
      await window.bridge.stopBot();
    }
    setRunningState(false);
    stopTimer();
    stopPriceSimulation();
    addLog('info', '停止循环');
    updateStats();
  }

  // ===== 紧急退出 =====
  // 紧急退出：confirm-on-click 模式（首次点击变为确认状态，3秒内再次点击才执行）
  let emergencyConfirmTimer = null;

  async function emergencyExit() {
    // 如果已经在确认状态，执行退出
    if (dom.btnEmergency.classList.contains('confirming')) {
      clearTimeout(emergencyConfirmTimer);
      dom.btnEmergency.classList.remove('confirming');
      dom.btnEmergency.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        紧急退出`;

      if (window.bridge) {
        await window.bridge.stopBot();
      }
      setRunningState(false);
      stopTimer();
      stopPriceSimulation();
      addLog('error', '程序已紧急终止');
      return;
    }

    // 首次点击：进入确认状态
    dom.btnEmergency.classList.add('confirming');
    dom.btnEmergency.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      确认退出？`;
    addLog('warning', '请在 3 秒内再次点击确认紧急退出');

    // 3秒后自动取消确认状态
    emergencyConfirmTimer = setTimeout(() => {
      dom.btnEmergency.classList.remove('confirming');
      dom.btnEmergency.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        紧急退出`;
    }, 3000);
  }

  // ===== 同步输入到配置 =====
  function syncConfigFromInputs() {
    const raw = dom.inputMaxPrice.value.replace(/,/g, '').trim();
    state.config.maxPrice = parseInt(raw, 10) || 50000;
    state.config.buyAmount = parseInt(dom.inputBuyAmount.value, 10) || 3;
    state.config.scheduledTime = dom.inputScheduledTime.value || '';
    state.config.runDuration = parseFloat(dom.inputRunDuration.value) || 10;

    // 收集延迟配置
    state.config.delays = collectDelaysFromUI();

    state.totalTarget = state.config.buyAmount;
    dom.totalTarget.textContent = state.totalTarget;
    dom.maxPriceDisplay.textContent = state.config.maxPrice.toLocaleString();
  }

  // ===== 收集延迟配置 =====
  function collectDelaysFromUI() {
    return {
      window_focus: parseFloat(dom.delayWindowFocus?.value) || 0,
      mouse_move: parseFloat(dom.delayMouseMove?.value) || 0,
      mouse_down: parseFloat(dom.delayMouseDown?.value) || 0,
      buy_button: parseFloat(dom.delayBuyButton?.value) || 0,
      buy_complete: parseFloat(dom.delayBuyComplete?.value) || 0,
      esc_key: parseFloat(dom.delayEscKey?.value) || 0,
      loop_interval: parseFloat(dom.delayLoopInterval?.value) || 0,
    };
  }

  // ===== 从后端配置应用到 UI =====
  function applyConfigToUI(data) {
    if (!data) return;

    // 缓存原始后端配置，保存时保留 position/region 等 UI 不编辑的字段
    state._rawBackendConfig = data;

    // 应用 keys 配置（取第一个门卡的配置）
    const keys = data.keys;
    if (keys && keys.length > 0) {
      const first = keys[0];
      if (first.max_price !== undefined) {
        const price = Number(first.max_price);
        // 过滤掉不合理的超大值
        if (price < 100000000) {
          dom.inputMaxPrice.value = price.toLocaleString();
          state.config.maxPrice = price;
        }
      }
      if (first.buyAmount !== undefined) {
        dom.inputBuyAmount.value = first.buyAmount;
        state.config.buyAmount = parseInt(first.buyAmount, 10);
      }
      if (first.scheduledTime !== undefined) {
        dom.inputScheduledTime.value = first.scheduledTime;
        state.config.scheduledTime = first.scheduledTime;
      }
      if (first.runDuration !== undefined) {
        dom.inputRunDuration.value = first.runDuration;
        state.config.runDuration = parseFloat(first.runDuration);
      }
    }

    // 应用延迟配置
    const delays = data.delays;
    if (delays) {
      const delayMap = {
        window_focus: dom.delayWindowFocus,
        mouse_move: dom.delayMouseMove,
        mouse_down: dom.delayMouseDown,
        buy_button: dom.delayBuyButton,
        buy_complete: dom.delayBuyComplete,
        esc_key: dom.delayEscKey,
        loop_interval: dom.delayLoopInterval,
      };
      for (const [key, input] of Object.entries(delayMap)) {
        if (input && delays[key] !== undefined) {
          input.value = delays[key];
        }
      }
    }

    // 同步状态和 UI 显示
    state.totalTarget = state.config.buyAmount;
    dom.totalTarget.textContent = state.totalTarget;
    dom.maxPriceDisplay.textContent = state.config.maxPrice.toLocaleString();

    addLog('success', '后端配置已加载并同步到界面');
  }

  // ===== 保存配置到后端（持久化 keys.json） =====
  async function saveConfigToBackend() {
    // 先同步最新的前端输入
    syncConfigFromInputs();

    // 构建符合后端 keys.json 格式的配置对象
    const configData = {
      keys: [
        {
          max_price: state.config.maxPrice,
          position: [0.3517, 0.2678],  // 保留已有的位置配置
          detail_price_region: {
            top_left: [0.7795, 0.8211],
            bottom_right: [0.8862, 0.882],
          },
          buyAmount: state.config.buyAmount,
          scheduledTime: state.config.scheduledTime,
          runDuration: state.config.runDuration,
        },
      ],
      delays: {
        window_focus: { value: state.config.delays?.window_focus || 0 },
        mouse_move: { value: state.config.delays?.mouse_move || 0 },
        mouse_down: { value: state.config.delays?.mouse_down || 0 },
        buy_button: { value: state.config.delays?.buy_button || 0 },
        buy_complete: { value: state.config.delays?.buy_complete || 0 },
        esc_key: { value: state.config.delays?.esc_key || 0 },
        loop_interval: { value: state.config.delays?.loop_interval || 0 },
      },
    };

    // 如果后端已加载过配置，尝试保留原始 position 和 region
    if (state._rawBackendConfig) {
      const origKeys = state._rawBackendConfig.keys;
      if (origKeys && origKeys.length > 0) {
        if (origKeys[0].position) configData.keys[0].position = origKeys[0].position;
        if (origKeys[0].detail_price_region) configData.keys[0].detail_price_region = origKeys[0].detail_price_region;
      }
    }

    if (!window.bridge) {
      addLog('warning', '未连接后端，无法保存配置');
      return;
    }

    // 禁用按钮防止重复点击
    dom.btnSaveConfig.disabled = true;

    try {
      const res = await window.bridge.saveConfig(configData);
      if (res && res.code === 200) {
        addLog('success', '✅ 配置已保存到 keys.json');
        // 按钮短暂变绿色反馈
        dom.btnSaveConfig.classList.add('saved');
        setTimeout(() => {
          dom.btnSaveConfig.classList.remove('saved');
        }, 1500);
      } else {
        addLog('error', '保存配置失败: ' + (res?.message || '未知错误'));
      }
    } catch (e) {
      addLog('error', '保存配置异常: ' + e.message);
    } finally {
      dom.btnSaveConfig.disabled = false;
    }
  }

  // ===== 模拟价格数据（v0 原型演示用） =====
  let priceSimInterval = null;

  function startPriceSimulation() {
    const basePrice = 35000;
    const variance = 25000;

    priceSimInterval = setInterval(() => {
      if (!state.isRunning) return;

      // 生成随机价格
      const price = Math.floor(basePrice + Math.random() * variance);
      state.prices.push(price);

      // 更新 UI
      dom.currentPrice.textContent = price.toLocaleString();

      // 趋势
      if (state.prices.length > 1) {
        const prev = state.prices[state.prices.length - 2];
        const diff = price - prev;
        if (diff > 0) {
          dom.priceTrend.textContent = `+${diff.toLocaleString()}`;
          dom.priceTrend.style.color = 'var(--clr-danger-light)';
        } else if (diff < 0) {
          dom.priceTrend.textContent = diff.toLocaleString();
          dom.priceTrend.style.color = 'var(--clr-success)';
        } else {
          dom.priceTrend.textContent = '0';
          dom.priceTrend.style.color = 'var(--clr-text-muted)';
        }
      }

      // 判断购买
      if (price <= state.config.maxPrice) {
        addLog('success', `已购买门卡, 价格: ${price.toLocaleString()}`);
        state.boughtCount++;
        dom.boughtCount.textContent = state.boughtCount;

        if (state.boughtCount >= state.totalTarget) {
          addLog('success', '门卡已购买完成!');
          stopMonitoring();
          return;
        }
      } else {
        addLog('info', `价格 ${price.toLocaleString()} > ${state.config.maxPrice.toLocaleString()}，跳过`);
      }

      // 更新实时统计
      dom.checkCount.textContent = state.prices.length;
      updateChart(price);
      updateStats();
    }, 2000);
  }

  function stopPriceSimulation() {
    clearInterval(priceSimInterval);
    priceSimInterval = null;
  }

  // ===== 统计更新 =====
  function updateStats() {
    if (state.prices.length === 0) return;

    const avg = state.prices.reduce((a, b) => a + b, 0) / state.prices.length;
    const high = Math.max(...state.prices);
    const low = Math.min(...state.prices);

    dom.avgPrice.textContent = Math.round(avg).toLocaleString();
    dom.highPrice.textContent = high.toLocaleString();
    dom.lowPrice.textContent = low.toLocaleString();
    dom.checkCount.textContent = state.prices.length;
  }

  // ===== 价格图表（Chart.js） =====
  let chart = null;

  function initChart() {
    // 检查 Chart.js 是否加载
    if (typeof Chart === 'undefined') {
      // 本地优先、CDN 降级策略
      const script = document.createElement('script');
      script.src = 'js/lib/chart.min.js';
      script.onload = () => createChart();
      script.onerror = () => {
        // 本地加载失败，尝试 CDN 降级
        console.warn('本地 Chart.js 加载失败，尝试 CDN...');
        const cdnScript = document.createElement('script');
        cdnScript.src = 'https://cdn.jsdelivr.net/npm/chart.js';
        cdnScript.onload = () => createChart();
        cdnScript.onerror = () => {
          console.error('Chart.js 加载失败（本地和 CDN 均不可用）');
          addLog('warning', '价格走势图表组件加载失败，图表功能不可用');
        };
        document.head.appendChild(cdnScript);
      };
      document.head.appendChild(script);
    } else {
      createChart();
    }
  }

  function createChart() {
    const ctx = dom.priceChart.getContext('2d');

    // 军事绿主题色
    const primaryColor = 'rgba(76, 175, 110, 1)';
    const primaryBg = 'rgba(76, 175, 110, 0.1)';
    const gridColor = 'rgba(255, 255, 255, 0.05)';

    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: '价格',
            data: [],
            borderColor: primaryColor,
            backgroundColor: primaryBg,
            borderWidth: 2,
            tension: 0.3,
            fill: true,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
          {
            label: '最高价格线',
            data: [],
            borderColor: 'rgba(239, 83, 80, 0.5)',
            borderWidth: 1,
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(30, 30, 35, 0.95)',
            titleFont: { family: "'JetBrains Mono', monospace", size: 11 },
            bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
            padding: 10,
            cornerRadius: 6,
          },
        },
        scales: {
          x: {
            display: false,
          },
          y: {
            grid: { color: gridColor },
            ticks: {
              font: { family: "'JetBrains Mono', monospace", size: 10 },
              color: 'rgba(255,255,255,0.3)',
              callback: (v) => (v / 1000).toFixed(0) + 'k',
            },
          },
        },
      },
    });
  }

  function updateChart(price) {
    if (!chart) return;

    const label = new Date().toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(price);
    chart.data.datasets[1].data.push(state.config.maxPrice);

    // 最多保留 30 个数据点
    if (chart.data.labels.length > 30) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
      chart.data.datasets[1].data.shift();
    }

    chart.update('none');
  }


  // ===== 事件绑定 =====
  dom.btnStart.addEventListener('click', startMonitoring);
  dom.btnStop.addEventListener('click', stopMonitoring);
  dom.btnEmergency.addEventListener('click', emergencyExit);

  dom.btnClearLogs.addEventListener('click', () => {
    dom.logStream.innerHTML = '';
    addLog('info', '日志已清除');
  });

  dom.toggleDebug.addEventListener('change', (e) => {
    state.debugMode = e.target.checked;
    addLog('info', `调试模式: ${state.debugMode ? '开启' : '关闭'}`);
  });

  // 配置变更时实时同步
  dom.inputMaxPrice.addEventListener('change', syncConfigFromInputs);
  dom.inputBuyAmount.addEventListener('change', syncConfigFromInputs);
  dom.inputScheduledTime.addEventListener('change', () => {
    syncConfigFromInputs();
    addLog('info', `定时启动更新: ${state.config.scheduledTime || '未设置'}`);
  });
  dom.inputRunDuration.addEventListener('change', syncConfigFromInputs);

  // 保存配置按钮
  if (dom.btnSaveConfig) {
    dom.btnSaveConfig.addEventListener('click', saveConfigToBackend);
  }

  // 设置按钮：快速滚动到高级配置区域
  if (dom.btnSettings) {
    dom.btnSettings.addEventListener('click', () => {
      const panelBody = document.querySelector('.panel--control .panel__body');
      if (panelBody) {
        panelBody.scrollTo({
          top: panelBody.scrollHeight,
          behavior: 'smooth'
        });
      }
      addLog('info', '已定位到高级配置面板');
    });
  }



  // ===== Python 后端通信事件 =====
  window.addEventListener('bot-log', (e) => {
    const data = e.detail;
    const mapLevel = { 'INFO': 'info', 'SUCCESS': 'success', 'WARNING': 'warning', 'ERROR': 'error' };
    addLog(mapLevel[data.level] || 'info', data.message);
  });

  window.addEventListener('bot-status', (e) => {
    const data = e.detail;
    
    // 更新 OCR 预览图
    if (data.ocr_preview) {
        const ocrCanvas = document.getElementById('ocrCanvas');
        if (ocrCanvas) {
            ocrCanvas.innerHTML = `<img src="data:image/jpeg;base64,${data.ocr_preview}" style="width: 100%; height: 100%; object-fit: contain; border-radius: var(--radius-sm);">`;
        }
    }

    if (data.last_price !== null && data.last_price !== state.last_price) {
        state.last_price = data.last_price;
        state.prices.push(data.last_price);
        dom.currentPrice.textContent = data.last_price.toLocaleString();
        
        if (state.prices.length > 1) {
            const prev = state.prices[state.prices.length - 2];
            const diff = data.last_price - prev;
            if (diff > 0) {
              dom.priceTrend.textContent = `+${diff.toLocaleString()}`;
              dom.priceTrend.style.color = 'var(--clr-danger-light)';
            } else if (diff < 0) {
              dom.priceTrend.textContent = diff.toLocaleString();
              dom.priceTrend.style.color = 'var(--clr-success)';
            } else {
              dom.priceTrend.textContent = '0';
              dom.priceTrend.style.color = 'var(--clr-text-muted)';
            }
        }
        
        dom.checkCount.textContent = state.prices.length;
        updateChart(data.last_price);
        updateStats();

        // 价格更新脉冲动画
        const priceCard = dom.currentPrice.closest('.metric-card');
        if (priceCard) {
          priceCard.classList.remove('metric-card--pulse');
          // 触发 reflow 以重启动画
          void priceCard.offsetWidth;
          priceCard.classList.add('metric-card--pulse');
        }
    }
    if (data.total_purchases !== undefined) {
        state.boughtCount = data.total_purchases;
        dom.boughtCount.textContent = state.boughtCount;
        if (state.boughtCount >= state.totalTarget && state.isRunning) {
            stopMonitoring();
        }
    }
    if (data.is_running === true && !state.isRunning) {
        state.isRunning = true;
        dom.btnStart.disabled = true;
        dom.btnStop.disabled = false;
        dom.btnStart.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> 监控中...`;
        addLog('warning', '[后台触发] 后端定时任务已启动监控！');
    }
    
    if (data.is_running === false && state.isRunning) {
        stopMonitoring();
    }
  });

  // ===== 初始化 =====
  async function init() {
    if (window.bridge) {
      await window.bridge.init();

      // 从后端加载配置并应用到 UI
      try {
        const configRes = await window.bridge.getConfig();
        if (configRes && configRes.code === 200) {
          applyConfigToUI(configRes.data);
        } else {
          addLog('warning', '加载后端配置失败: ' + (configRes?.message || '未知错误'));
        }
      } catch (e) {
        addLog('warning', '无法连接后端加载配置: ' + e.message);
      }
    }

    syncConfigFromInputs();
    initChart();

    // 更新底部状态栏
    const ocrStatusEl = document.getElementById('ocrStatus');
    const configStatusEl = document.getElementById('configStatus');
    const gameWindowDot = document.getElementById('gameWindowDot');
    const gameWindowStatus = document.getElementById('gameWindowStatus');

    if (window.bridge) {
      gameWindowDot.classList.add('bottom-bar__dot--active');
      gameWindowStatus.textContent = '游戏窗口: 已连接后端';
      if (ocrStatusEl) ocrStatusEl.textContent = 'Tesseract OCR: 就绪';
      if (configStatusEl) configStatusEl.textContent = '配置: keys.json (已加载)';
    } else {
      gameWindowStatus.textContent = '游戏窗口: 未连接后端';
      if (ocrStatusEl) ocrStatusEl.textContent = 'Tesseract OCR: 离线';
      if (configStatusEl) configStatusEl.textContent = '配置: 前端演示模式';
    }

    addLog('info', '控制面板已就绪');
  }

  init();
})();
