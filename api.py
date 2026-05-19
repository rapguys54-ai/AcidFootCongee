import json
import os
import sys
import threading
import time
import datetime
import logging

# keyboard 库仅在 Windows 上安全（macOS 下与 Cocoa 主线程冲突导致 bus error）
if sys.platform == 'win32':
    try:
        import keyboard
    except ImportError:
        keyboard = None
else:
    keyboard = None

logger = logging.getLogger("AcidFootCongee")


class BackendAPI:
    """暴露给前端 JS 调用的后端 API"""

    def __init__(self):
        self._window    = None
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._lock      = threading.Lock()
        self._bot_thread = None

        # 配置路径
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(__file__)
        self.config_path = os.path.abspath(os.path.join(base_dir, "keys.json"))

        # 子弹数据库路径
        self.bullet_data_path = os.path.abspath(
            os.path.join(base_dir, "bullet_data.json"))

        self.status = {
            "is_running":     False,
            "total_purchases": 0,
            "last_price":     None,
            "current_bullet": None,
            "bullet_statuses": {},
            "logs": []
        }

        # 注册热键（仅 Windows）
        if keyboard:
            try:
                keyboard.add_hotkey('f8', self._hotkey_grab_coord)
                keyboard.add_hotkey('f9', self._hotkey_stop)
            except Exception as e:
                logger.warning(f"热键注册失败: {e}")

        # 定时启动守护线程
        threading.Thread(target=self._auto_start_daemon, daemon=True).start()

    # ════════════════════════════════════════
    # 窗口绑定
    # ════════════════════════════════════════

    def set_window(self, window):
        self._window = window

    # ════════════════════════════════════════
    # 机器人控制
    # ════════════════════════════════════════

    def start_bot(self):
        if not self._stop_event.is_set():
            return {"code": 400, "message": "已在运行中"}
        self._stop_event.clear()
        with self._lock:
            self.status["is_running"]      = True
            self.status["total_purchases"] = 0
        self._bot_thread = threading.Thread(target=self._bot_loop, daemon=True)
        self._bot_thread.start()
        return {"code": 200, "message": "启动成功"}

    def stop_bot(self):
        if self._stop_event.is_set():
            return {"code": 400, "message": "未在运行"}
        self._stop_event.set()
        with self._lock:
            self.status["is_running"] = False
        self._push_status_to_frontend()
        return {"code": 200, "message": "已停止"}

    def get_status(self):
        with self._lock:
            copy = dict(self.status)
            copy["logs"] = list(self.status["logs"])
        return {"code": 200, "data": copy}

    # ════════════════════════════════════════
    # 配置 API
    # ════════════════════════════════════════

    def get_config(self):
        """返回完整配置（ui_coords + delays + today_bullets + scheduled_time）"""
        try:
            from bot_core.config_manager import ConfigManager
            cm = ConfigManager(self.config_path)
            cm.load()
            return {"code": 200, "data": cm.config}
        except Exception as e:
            logger.error(f"加载配置失败: {e}", exc_info=True)
            return {"code": 500, "message": str(e)}

    def save_config(self, config_data: dict):
        """保存坐标配置 + delays（不触碰 today_bullets）"""
        try:
            from bot_core.config_manager import ConfigManager
            cm = ConfigManager(self.config_path)
            cm.load()
            if "ui_coords" in config_data:
                cm.config["ui_coords"] = config_data["ui_coords"]
            if "delays" in config_data:
                cm.config["delays"] = config_data["delays"]
            if "scheduled_time" in config_data:
                cm.config["scheduled_time"] = config_data["scheduled_time"]
            if "run_duration" in config_data:
                cm.config["run_duration"] = config_data["run_duration"]
            cm.save()
            return {"code": 200, "message": "保存成功"}
        except Exception as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)
            return {"code": 500, "message": str(e)}

    # ════════════════════════════════════════
    # 子弹数据库 API（CRUD）
    # ════════════════════════════════════════

    def _load_bullet_data(self):
        if not os.path.exists(self.bullet_data_path):
            return {"calibers": []}
        with open(self.bullet_data_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_bullet_data(self, data):
        with open(self.bullet_data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_bullet_library(self):
        """返回全部子弹口径 + 变体数据"""
        try:
            return {"code": 200, "data": self._load_bullet_data()}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def add_caliber(self, name: str):
        """新增口径"""
        try:
            data = self._load_bullet_data()
            cid = name.lower().replace(' ', '').replace('.', '').replace('x', 'x')
            # 防重复
            for c in data['calibers']:
                if c['name'] == name:
                    return {"code": 409, "message": f"口径「{name}」已存在"}
            entry = {"id": cid, "name": name, "variants": []}
            data['calibers'].append(entry)
            self._save_bullet_data(data)
            return {"code": 200, "data": entry}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def update_caliber(self, caliber_id: str, name: str):
        """修改口径名称"""
        try:
            data = self._load_bullet_data()
            for c in data['calibers']:
                if c['id'] == caliber_id:
                    c['name'] = name
                    self._save_bullet_data(data)
                    return {"code": 200}
            return {"code": 404, "message": "口径不存在"}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def remove_caliber(self, caliber_id: str):
        """删除口径及其全部变体"""
        try:
            data = self._load_bullet_data()
            before = len(data['calibers'])
            data['calibers'] = [c for c in data['calibers'] if c['id'] != caliber_id]
            if len(data['calibers']) < before:
                self._save_bullet_data(data)
                return {"code": 200}
            return {"code": 404, "message": "口径不存在"}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def add_variant(self, caliber_id: str, name: str, tier: int):
        """在指定口径下新增子弹变体"""
        try:
            data = self._load_bullet_data()
            for c in data['calibers']:
                if c['id'] == caliber_id:
                    # 防重复
                    for v in c['variants']:
                        if v['name'] == name:
                            return {"code": 409, "message": f"子弹「{name}」已存在"}
                    vid = name.lower().replace(' ', '_').replace('.', '')
                    entry = {"id": vid, "name": name, "tier": max(1, min(5, int(tier)))}
                    c['variants'].append(entry)
                    self._save_bullet_data(data)
                    return {"code": 200, "data": entry}
            return {"code": 404, "message": "口径不存在"}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def update_variant(self, caliber_id: str, variant_id: str, fields: dict):
        """修改子弹变体（name / tier）"""
        try:
            data = self._load_bullet_data()
            for c in data['calibers']:
                if c['id'] == caliber_id:
                    for v in c['variants']:
                        if v['id'] == variant_id:
                            if 'name' in fields:
                                v['name'] = fields['name']
                            if 'tier' in fields:
                                v['tier'] = max(1, min(5, int(fields['tier'])))
                            self._save_bullet_data(data)
                            return {"code": 200}
            return {"code": 404, "message": "未找到目标"}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def remove_variant(self, caliber_id: str, variant_id: str):
        """删除子弹变体"""
        try:
            data = self._load_bullet_data()
            for c in data['calibers']:
                if c['id'] == caliber_id:
                    before = len(c['variants'])
                    c['variants'] = [v for v in c['variants'] if v['id'] != variant_id]
                    if len(c['variants']) < before:
                        self._save_bullet_data(data)
                        return {"code": 200}
            return {"code": 404, "message": "未找到目标"}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    # ════════════════════════════════════════
    # 今日清单 API
    # ════════════════════════════════════════

    def get_today_bullets(self):
        try:
            from bot_core.config_manager import ConfigManager
            cm = ConfigManager(self.config_path)
            cm.load()
            return {"code": 200, "data": cm.get_today_bullets()}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def add_today_bullet(self, name: str, caliber: str, max_price):
        try:
            from bot_core.config_manager import ConfigManager
            cm = ConfigManager(self.config_path)
            cm.load()
            entry = cm.add_today_bullet(name, caliber, int(max_price))
            if entry is None:
                return {"code": 409, "message": f"「{name}」已在今日清单中"}
            return {"code": 200, "data": entry}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def remove_today_bullet(self, bullet_id: str):
        try:
            from bot_core.config_manager import ConfigManager
            cm = ConfigManager(self.config_path)
            cm.load()
            ok = cm.remove_today_bullet(bullet_id)
            return {"code": 200 if ok else 404, "message": "删除成功" if ok else "未找到"}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def update_today_bullet(self, bullet_id: str, fields: dict):
        try:
            from bot_core.config_manager import ConfigManager
            cm = ConfigManager(self.config_path)
            cm.load()
            ok = cm.update_today_bullet(bullet_id, fields)
            return {"code": 200 if ok else 404}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    def reorder_today_bullets(self, ordered_ids: list):
        """按给定 id 列表重新排序今日清单"""
        try:
            from bot_core.config_manager import ConfigManager
            cm = ConfigManager(self.config_path)
            cm.load()
            bullets = cm.get_today_bullets()
            id_map  = {b['id']: b for b in bullets}
            reordered = [id_map[i] for i in ordered_ids if i in id_map]
            cm.config['today_bullets'] = reordered
            cm.save()
            return {"code": 200}
        except Exception as e:
            return {"code": 500, "message": str(e)}

    # ════════════════════════════════════════
    # 热键回调
    # ════════════════════════════════════════

    def _hotkey_stop(self):
        if not self._stop_event.is_set():
            self.stop_bot()
            self.push_log("INFO", "[F9] 紧急停止")

    def _hotkey_grab_coord(self):
        """F8: 抓取当前鼠标位置作为坐标（推送到前端显示）"""
        try:
            import pyautogui
            from bot_core.automation import GameAutomation
            auto   = GameAutomation()
            coords = auto.get_coordinates()
            if not coords:
                self.push_log("ERROR", "F8: 未找到游戏窗口")
                return
            ax, ay = pyautogui.position()
            rx = round((ax - coords['offset_x']) / coords['width'],  4)
            ry = round((ay - coords['offset_y']) / coords['height'], 4)
            if 0 <= rx <= 1 and 0 <= ry <= 1:
                self.push_log("SUCCESS", f"[F8] 抓取坐标: [{rx}, {ry}]")
                self._push_event('coord-grab', {"rx": rx, "ry": ry})
            else:
                self.push_log("WARNING", "F8: 鼠标不在游戏窗口内")
        except Exception as e:
            self.push_log("ERROR", f"F8 异常: {e}")

    # ════════════════════════════════════════
    # 自动启动守护线程
    # ════════════════════════════════════════

    def _auto_start_daemon(self):
        from bot_core.config_manager import ConfigManager
        last_triggered = ""
        while True:
            time.sleep(1)
            if not self._stop_event.is_set():
                continue
            try:
                cm = ConfigManager(self.config_path)
                cm.load()
                sched = cm.config.get('scheduled_time', '')
                if not sched:
                    continue
                now_str = datetime.datetime.now().strftime("%H:%M")
                if now_str == sched and now_str != last_triggered:
                    last_triggered = now_str
                    self.push_log("WARNING", f"⏰ 定时 {sched} 触发自动启动！")
                    self.start_bot()
            except Exception:
                pass

    # ════════════════════════════════════════
    # 机器人主循环
    # ════════════════════════════════════════

    def _bot_loop(self):
        self.push_log("INFO", "🚀 自动化脚本启动")
        try:
            from bot_core.config_manager import ConfigManager
            from bot_core.state_machine  import BotStateMachine
            cm = ConfigManager(self.config_path)
            cm.load()

            sm = BotStateMachine(
                config       = cm.config,
                push_log     = self.push_log,
                push_status  = self._push_status_dict,
                stop_event   = self._stop_event
            )
            sm.run()
        except Exception as e:
            logger.error(f"bot_loop 异常: {e}", exc_info=True)
            self.push_log("ERROR", f"运行异常: {e}")
        finally:
            self._stop_event.set()
            with self._lock:
                self.status["is_running"] = False
            self.push_log("INFO", "✅ 自动化脚本已停止")
            self._push_status_to_frontend()

    # ════════════════════════════════════════
    # 日志 & 状态推送
    # ════════════════════════════════════════

    def push_log(self, level: str, message: str):
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] [{level}] {message}"
        with self._lock:
            self.status["logs"].append(entry)
            if len(self.status["logs"]) > 200:
                self.status["logs"].pop(0)
        self._push_event('bot-log', {"level": level, "message": message})
        logger.info(entry)

    def _push_status_dict(self, data: dict):
        with self._lock:
            self.status.update(data)
        self._push_status_to_frontend()

    def _push_status_to_frontend(self):
        if not self._window:
            return
        try:
            with self._lock:
                copy = dict(self.status)
            self._push_event('bot-status', copy)
        except Exception as e:
            logger.debug(f"推送状态失败: {e}")

    def _push_event(self, event_name: str, detail: dict):
        if not self._window:
            return
        try:
            payload = json.dumps(detail, ensure_ascii=False)
            self._window.evaluate_js(
                f"window.dispatchEvent(new CustomEvent({json.dumps(event_name)}, "
                f"{{detail: {payload}}}))"
            )
        except Exception as e:
            logger.debug(f"推送事件 {event_name} 失败: {e}")
