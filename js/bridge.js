/**
 * 与 Python 核心层通信的桥接 API
 */
window.bridge = {
    isReady: false,
    
    init() {
        return new Promise((resolve) => {
            window.addEventListener('pywebviewready', () => {
                this.isReady = true;
                resolve();
            });
            // 兜底超时，比如在普通浏览器中打开
            setTimeout(() => {
                if (!this.isReady) resolve();
            }, 500);
        });
    },

    async startBot(settings) {
        if (window.pywebview && window.pywebview.api) {
            return await window.pywebview.api.start_bot(settings);
        } else {
            console.warn("pywebview not available, using mock");
            return {code: 200, message: "模拟启动成功"};
        }
    },

    async stopBot() {
        if (window.pywebview && window.pywebview.api) {
            return await window.pywebview.api.stop_bot();
        } else {
            return {code: 200, message: "模拟停止成功"};
        }
    },

    async getStatus() {
        if (window.pywebview && window.pywebview.api) {
            return await window.pywebview.api.get_status();
        }
        return {code: 500};
    },

    async getConfig() {
        if (window.pywebview && window.pywebview.api) {
            return await window.pywebview.api.get_config();
        }
        return {code: 500};
    },

    async saveConfig(config) {
        if (window.pywebview && window.pywebview.api) {
            return await window.pywebview.api.save_config(config);
        }
        return {code: 500};
    }
};
