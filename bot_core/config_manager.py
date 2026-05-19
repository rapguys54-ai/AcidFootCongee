import json
import os
import sys
import uuid
import logging

logger = logging.getLogger("AcidFootCongee.config")

# 默认坐标配置
DEFAULT_UI_COORDS = {
    "search_box":   [0.13, 0.165],
    "first_card":   [0.35, 0.22],
    "slider_max":   [0.932, 0.725],
    "price_region": [0.78, 0.752, 0.95, 0.785],
    "price_button": [0.845, 0.795],
    "popup_region": [0.30, 0.40, 0.70, 0.65]
}

DEFAULT_DELAYS = {
    "after_search_input": 0.3,
    "after_click_card":   0.4,
    "ocr_interval":       0.05,
    "sold_out_timeout":   30
}


class ConfigManager:
    """管理 keys.json 配置文件（新结构）"""

    def __init__(self, config_path=None):
        if config_path is None:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_path = os.path.join(base_dir, "keys.json")
        else:
            self.config_path = config_path

        self.config = None

    # ─────────────────────────────────────────
    # 基础 IO
    # ─────────────────────────────────────────

    def get_config_path(self):
        return self.config_path

    def load(self):
        """加载配置文件，若不存在则创建默认配置"""
        if not os.path.exists(self.config_path):
            self.config = self._default_config()
            self._write()
            logger.info("配置文件不存在，已创建默认配置")
        else:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            # 迁移旧格式 → 新格式
            self._migrate_if_needed()
        return self.config

    def save(self, new_config=None):
        """保存配置（传入 dict 则替换，不传则保存当前 self.config）"""
        if new_config is not None:
            self.config = new_config
        if self.config is None:
            raise ValueError("没有可保存的配置数据")
        self._write()
        logger.info(f"配置已保存: {self.config_path}")
        return True

    def _write(self):
        os.makedirs(os.path.dirname(self.config_path) or '.', exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    # ─────────────────────────────────────────
    # 坐标配置
    # ─────────────────────────────────────────

    def get_ui_coords(self):
        if self.config is None:
            self.load()
        return self.config.get('ui_coords', DEFAULT_UI_COORDS.copy())

    def update_ui_coord(self, key, value):
        """更新单个坐标项并持久化
        key:   坐标名称 (search_box / first_card / slider_max / price_button)
        value: [x, y] 或 [x1, y1, x2, y2]
        """
        if self.config is None:
            self.load()
        if 'ui_coords' not in self.config:
            self.config['ui_coords'] = DEFAULT_UI_COORDS.copy()
        self.config['ui_coords'][key] = value
        self._write()
        return True

    # ─────────────────────────────────────────
    # 今日购买清单
    # ─────────────────────────────────────────

    def get_today_bullets(self):
        if self.config is None:
            self.load()
        return self.config.get('today_bullets', [])

    def add_today_bullet(self, name, caliber, max_price):
        """添加子弹到今日清单，返回新条目"""
        if self.config is None:
            self.load()
        # 防重复
        for b in self.config.get('today_bullets', []):
            if b['name'] == name:
                return None  # 已存在
        entry = {
            "id":        str(uuid.uuid4())[:8],
            "name":      name,
            "caliber":   caliber,
            "max_price": int(max_price),
            "enabled":   True,
            "status":    "pending"   # pending / running / done / empty
        }
        self.config.setdefault('today_bullets', []).append(entry)
        self._write()
        return entry

    def remove_today_bullet(self, bullet_id):
        """按 id 删除"""
        if self.config is None:
            self.load()
        before = len(self.config.get('today_bullets', []))
        self.config['today_bullets'] = [
            b for b in self.config.get('today_bullets', [])
            if b.get('id') != bullet_id
        ]
        self._write()
        return len(self.config['today_bullets']) < before

    def update_today_bullet(self, bullet_id, fields: dict):
        """更新今日清单中某条目的字段（max_price / enabled / status）"""
        if self.config is None:
            self.load()
        for b in self.config.get('today_bullets', []):
            if b.get('id') == bullet_id:
                b.update(fields)
                self._write()
                return True
        return False

    # ─────────────────────────────────────────
    # 延迟配置
    # ─────────────────────────────────────────

    def get_delays(self):
        if self.config is None:
            self.load()
        delays = DEFAULT_DELAYS.copy()
        delays.update(self.config.get('delays', {}))
        return delays

    # ─────────────────────────────────────────
    # 内部工具
    # ─────────────────────────────────────────

    @staticmethod
    def _default_config():
        return {
            "ui_coords":     DEFAULT_UI_COORDS.copy(),
            "today_bullets": [],
            "delays":        DEFAULT_DELAYS.copy(),
            "scheduled_time": "",
            "run_duration":   240
        }

    def _migrate_if_needed(self):
        """将旧格式（含 keys[] 字段）迁移到新格式"""
        if 'keys' in self.config and 'ui_coords' not in self.config:
            logger.info("检测到旧版配置格式，正在迁移...")
            old_keys = self.config.get('keys', [])
            self.config['ui_coords'] = DEFAULT_UI_COORDS.copy()
            self.config['today_bullets'] = []
            self.config['delays'] = DEFAULT_DELAYS.copy()
            # 尝试迁移旧 price_region
            if old_keys:
                old = old_keys[0]
                pr = old.get('detail_price_region', {})
                tl = pr.get('top_left', [])
                br = pr.get('bottom_right', [])
                if len(tl) == 2 and len(br) == 2:
                    self.config['ui_coords']['price_region'] = [
                        tl[0], tl[1], br[0], br[1]
                    ]
                if old.get('buy_button_position'):
                    self.config['ui_coords']['price_button'] = old['buy_button_position']
            del self.config['keys']
            self._write()
            logger.info("配置迁移完成")
