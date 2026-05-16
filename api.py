import json
import os
import threading
import time
import sys
import datetime
import logging

# keyboard 库仅在 Windows 上可用且安全
# macOS 上 keyboard 的 Quartz Event Tap 会与 pywebview 的 Cocoa 主线程冲突导致 bus error
if sys.platform == 'win32':
    try:
        import keyboard
    except ImportError:
        keyboard = None
else:
    keyboard = None

# 配置日志框架替代 print()
logger = logging.getLogger("AcidFootCongee")

class BackendAPI:
    """暴露给前端JS调用的后端API对象"""
    def __init__(self):
        self._window = None
        # 线程安全：使用 Event 替代布尔标志，自带 Memory Barrier
        self._stop_event = threading.Event()
        self._stop_event.set()  # 初始状态：已停止
        # 线程安全：使用 Lock 保护共享状态
        self._lock = threading.Lock()
        self._bot_thread = None

        # 兼容 PyInstaller 打包环境，确保 keys.json 和 exe 文件在同级目录
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(__file__)
        self.config_path = os.path.abspath(os.path.join(base_dir, "keys.json"))
        
        # 将一些共享状态存放在此处（通过 _lock 保护读写）
        self.status = {
            "is_running": False,
            "runtime_minutes": 0,
            "total_purchases": 0,
            "last_price": None,
            "logs": []
        }
        
        # 注册全局热键
        if keyboard:
            try:
                keyboard.add_hotkey('f9', self._hotkey_stop)
                keyboard.add_hotkey('f8', self._hotkey_grab_coord)
            except Exception as e:
                logger.warning(f"无法注册全局热键: {e}")
                
        # 启动后台守护线程，用于精准的定时启动
        threading.Thread(target=self._auto_start_daemon, daemon=True).start()

    def set_window(self, window):
        """保存webview窗口实例"""
        self._window = window

    # ==========================
    # 供前端调用的 API 方法
    # ==========================

    def get_status(self):
        """前端获取当前后端状态"""
        with self._lock:
            # 返回状态的浅拷贝，避免前端读取时被子线程修改
            status_copy = dict(self.status)
            status_copy["logs"] = list(self.status["logs"])
        return {
            "code": 200,
            "data": status_copy
        }

    def start_bot(self, settings):
        """前端发起启动自动化"""
        if not self._stop_event.is_set():
            return {"code": 400, "message": "程序已经在运行中"}
        
        # 应用前端传入的配置到 keys.json
        if settings:
            self._apply_settings(settings)

        self._stop_event.clear()
        with self._lock:
            self.status["is_running"] = True
        
        # 启动自动化线程
        self._bot_thread = threading.Thread(target=self._bot_loop, daemon=True)
        self._bot_thread.start()
        
        return {"code": 200, "message": "启动成功"}

    def stop_bot(self):
        """前端发起停止自动化"""
        if self._stop_event.is_set():
            return {"code": 400, "message": "程序并未运行"}
            
        self._stop_event.set()
        with self._lock:
            self.status["is_running"] = False
        return {"code": 200, "message": "停止成功"}

    # ==========================
    # 后端热键与守护线程
    # ==========================
    
    def _hotkey_stop(self):
        """全局热键 F9 回调：紧急停止"""
        if not self._stop_event.is_set():
            self.stop_bot()
            self._push_status_to_frontend()
            self.push_log("INFO", "[系统热键] 已通过 F9 紧急停止自动化。")
            
    def _hotkey_grab_coord(self):
        """全局热键 F8 回调：抓取鼠标在游戏内的相对坐标，并更新到第一个配置项"""
        try:
            import pyautogui
            from bot_core.automation import GameAutomation
            from bot_core.config_manager import ConfigManager
            
            auto = GameAutomation()
            window_info = auto.get_coordinates()
            if not window_info:
                self.push_log("ERROR", "未找到游戏窗口！请确保游戏处于前台，再按 F8。")
                return
                
            abs_x, abs_y = pyautogui.position()
            
            # 换算为相对游戏窗口内部的百分比坐标
            rel_x = (abs_x - window_info['offset_x']) / window_info['width']
            rel_y = (abs_y - window_info['offset_y']) / window_info['height']
            
            if 0 <= rel_x <= 1 and 0 <= rel_y <= 1:
                rel_x = round(rel_x, 4)
                rel_y = round(rel_y, 4)
                
                # 直接按索引更新第一个配置项的 position
                cm = ConfigManager(self.config_path)
                updated = cm.update_position(0, [rel_x, rel_y])
                if updated:
                    self.push_log("SUCCESS", f"[F8 抓取] 子弹位置坐标已更新为: [{rel_x}, {rel_y}]")
                    # 同步推送到前端以刷新坐标显示
                    self._push_coord_update_to_frontend(rel_x, rel_y)
                else:
                    self.push_log("WARNING", "[F8 抓取] 更新失败：配置文件中没有可用的配置项。请先保存一次配置。")
            else:
                self.push_log("WARNING", f"[F8 抓取] 鼠标不在游戏窗口内，当前坐标({abs_x}, {abs_y})无效。")
        except Exception as e:
            self.push_log("ERROR", f"抓取坐标时发生异常: {e}")

    def _push_coord_update_to_frontend(self, rel_x, rel_y):
        """将 F8 抓取的坐标推送到前端 UI"""
        if not self._window:
            return
        try:
            detail = json.dumps({"rel_x": rel_x, "rel_y": rel_y}, ensure_ascii=False)
            self._window.evaluate_js(
                f"window.dispatchEvent(new CustomEvent('coord-update', {{detail: {detail}}}))"
            )
        except Exception as e:
            logger.debug(f"推送坐标更新到前端失败: {e}")

    def _auto_start_daemon(self):
        """后台守护线程：精准触发定时启动"""
        last_checked = ""
        from bot_core.config_manager import ConfigManager
        
        while True:
            time.sleep(1)
            # 如果正在运行则不检测
            if not self._stop_event.is_set():
                continue
                
            try:
                cm = ConfigManager(self.config_path)
                cm.load()
                scheduled_time = cm.config.get('scheduledTime', '')
                if not scheduled_time:
                    continue
                    
                now = datetime.datetime.now()
                current_time_str = f"{now.hour:02d}:{now.minute:02d}"
                
                if current_time_str == scheduled_time and current_time_str != last_checked:
                    last_checked = current_time_str
                    self.push_log("WARNING", f"定时时间 {current_time_str} 到达，后台底层触发自动启动！")
                    
                    self._stop_event.clear()
                    with self._lock:
                        self.status["is_running"] = True
                        
                    self._bot_thread = threading.Thread(target=self._bot_loop, daemon=True)
                    self._bot_thread.start()
                    self._push_status_to_frontend()
            except Exception as e:
                # 忽略加载配置文件时的临时异常
                pass

    def get_config(self):
        """加载配置文件"""
        try:
            from bot_core import ConfigManager
            cm = ConfigManager(self.config_path)
            keys = cm.load()
            return {"code": 200, "data": {"keys": keys, "delays": cm.delays}}
        except Exception as e:
            logger.error(f"加载配置失败: {e}", exc_info=True)
            return {"code": 500, "message": f"加载配置失败: {str(e)}"}

    def save_config(self, config_data):
        """保存配置文件"""
        try:
            from bot_core import ConfigManager
            cm = ConfigManager(self.config_path)
            # 先加载现有配置以保留其他字段
            try:
                cm.load()
                existing = cm.config if cm.config else {}
            except FileNotFoundError:
                existing = {}
            
            # 合并配置：前端传入的覆盖已有的
            if "keys" in config_data:
                existing["keys"] = config_data["keys"]
            if "delays" in config_data:
                existing["delays"] = config_data["delays"]
            
            cm.save(existing)
            return {"code": 200, "message": "保存成功"}
        except Exception as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)
            return {"code": 500, "message": f"保存配置失败: {str(e)}"}

    # ==========================
    # 内部业务逻辑方法
    # ==========================

    def _apply_settings(self, settings):
        """将前端传入的 settings 应用到 keys.json 配置"""
        try:
            from bot_core import ConfigManager
            cm = ConfigManager(self.config_path)
            try:
                cm.load()
                config = cm.config if cm.config else {"keys": [], "delays": {}}
            except FileNotFoundError:
                config = {"keys": [], "delays": {}}
            
            # 将前端配置映射到后端 keys.json 格式
            if config.get("keys") and len(config["keys"]) > 0:
                first_key = config["keys"][0]
                if "maxPrice" in settings:
                    first_key["max_price"] = int(settings["maxPrice"])
                if "buyAmount" in settings:
                    first_key["buyAmount"] = int(settings["buyAmount"])
                if "scheduledTime" in settings:
                    first_key["scheduledTime"] = settings["scheduledTime"]
                if "runDuration" in settings:
                    first_key["runDuration"] = float(settings["runDuration"])
            
            cm.save(config)
        except Exception as e:
            logger.warning(f"应用前端配置失败（非致命）: {e}")

    def _bot_loop(self):
        """真实的自动化循环逻辑 — 购买子弹"""
        from bot_core import ConfigManager, GameAutomation, OcrEngine
        
        # 兼容 macOS 下的测试运行（跳过 win32gui）
        if sys.platform != 'win32':
            self.push_log("WARNING", "⚠️ 当前运行在非 Windows 系统，自动化点击与游戏窗口识别功能将被受限或模拟")
        import pyautogui
            
        self.push_log("INFO", "自动化脚本已启动，开始监控子弹价格...")
        
        try:
            cm = ConfigManager(self.config_path)
            keys_config = cm.load()
            delays = cm.delays
            
            auto = GameAutomation()
            ocr = OcrEngine()
            
            while not self._stop_event.is_set():
                # 遍历所有配置项
                for card_info in keys_config:
                    if self._stop_event.is_set():
                        break
                        
                    # 查找游戏窗口
                    window_info = auto.find_game_window()
                    if not window_info and sys.platform == 'win32':
                        self.push_log("WARNING", "未找到游戏窗口，请确保《三角洲行动》已运行")
                        # 使用 Event.wait 替代 time.sleep，支持即时响应停止信号
                        if self._stop_event.wait(timeout=2):
                            break
                        continue
                        
                    coords = auto.get_coordinates()
                    
                    # 1. 点击子弹物品位置
                    position = card_info.get("position")
                    if position and len(position) >= 2:
                        auto.click_relative(position[0], position[1], delays)
                    else:
                        self.push_log("WARNING", "配置文件中未设置子弹点击位置 (position)，请先通过 F8 抓取或在界面中设置")
                        continue
                        
                    # 2. 识别价格（OCR 区域）
                    price_region = card_info.get('detail_price_region')
                    
                    if price_region and 'top_left' in price_region and 'bottom_right' in price_region:
                        top_left = price_region['top_left']
                        bottom_right = price_region['bottom_right']
                        region_left = coords['offset_x'] + int(coords['width'] * top_left[0])
                        region_top = coords['offset_y'] + int(coords['height'] * top_left[1])
                        region_width = int(coords['width'] * (bottom_right[0] - top_left[0]))
                        region_height = int(coords['height'] * (bottom_right[1] - top_left[1]))
                        region_tuple = (region_left, region_top, region_width, region_height)
                    else:
                        # 默认区域
                        region_left = coords['offset_x'] + int(coords['width'] * 0.35)
                        region_top = coords['offset_y'] + int(coords['height'] * 0.27)
                        region_width = int(coords['width'] * 0.15)
                        region_height = int(coords['height'] * 0.08)
                        region_tuple = (region_left, region_top, region_width, region_height)

                    current_price = None
                    current_preview = None
                    for _ in range(10):  # 最多尝试 10 次识别
                        if self._stop_event.is_set():
                            break
                        
                        ocr_result = ocr.get_price(region_tuple)
                        if isinstance(ocr_result, dict):
                            current_price = ocr_result.get("price")
                            current_preview = ocr_result.get("preview")
                        else:
                            current_price = ocr_result
                            
                        # 如果拿到最新截图了，随时更新到前端（即使没识别出价格）
                        if current_preview:
                            with self._lock:
                                self.status["ocr_preview"] = current_preview
                            self._push_status_to_frontend()
                            
                        if current_price is not None:
                            break
                            
                    if current_price is None:
                        pyautogui.press('esc')
                        self.push_log("WARNING", "⚠️ 目标区视野受阻或未发现有效目标，执行战术规避(ESC)并重新搜寻...")
                        import random
                        time.sleep(random.uniform(0.15, 0.45))  # 拟人化：按完 ESC 后观察一下
                        if self._stop_event.wait(timeout=delays.get('esc_key', 0.01)):
                            break
                        continue
                    
                    # 线程安全地更新状态
                    with self._lock:
                        self.status["last_price"] = current_price
                    self.push_log("INFO", f"🎯 [雷达确认] 锁定子弹价格: {current_price:,} 金币")
                    
                    # 每次识别到价格都推送 bot-status 事件（不只是购买时）
                    self._push_status_to_frontend()
                    
                    # 3. 比较价格并购买
                    max_price = int(card_info.get('max_price', 0))
                    
                    if max_price > 0 and current_price <= max_price:
                        self.push_log("SUCCESS", f"⚡ [致命一击] 价格({current_price:,}) <= 预算({max_price:,})，条件满足，立刻执行战术购买！")
                        
                        # 从配置读取购买按钮位置（可自定义），默认值上移到合理位置
                        buy_btn = card_info.get("buy_button_position", [0.825, 0.85])
                        auto.click_relative(buy_btn[0], buy_btn[1], delays)
                        import random
                        time.sleep(random.uniform(0.1, 0.3)) # 拟人化停顿
                        if self._stop_event.wait(timeout=delays.get('buy_button', 0.01)):
                            break
                        
                        # 从配置读取确认按钮位置（可自定义）
                        confirm_btn = card_info.get("confirm_button_position", [0.55, 0.65])
                        auto.click_relative(confirm_btn[0], confirm_btn[1], delays)
                        time.sleep(random.uniform(0.3, 0.8)) # 拟人化：确认弹窗也需要反应时间
                        if self._stop_event.wait(timeout=delays.get('buy_complete', 0.01)):
                            break
                        
                        with self._lock:
                            self.status["total_purchases"] += 1
                            current_purchases = self.status["total_purchases"]
                        
                        target_amount = int(card_info.get('buyAmount', 1))
                        self.push_log("SUCCESS", f"✅ [收网] 成功购买子弹！当前进度: {current_purchases} / {target_amount}")
                        self._push_status_to_frontend()
                        
                        if current_purchases >= target_amount:
                            self.push_log("INFO", "🏆 [任务完成] 购买配额已满，本轮潜伏作战圆满结束。撤退！")
                            self.stop_bot()
                            break
                            
                    else:
                        self.push_log("INFO", f"☕ [静默潜伏] 价格 {current_price:,} 超过预算 {max_price:,}，放弃攻击。")
                        pyautogui.press('esc')
                        import random
                        time.sleep(random.uniform(0.15, 0.45)) # 拟人化：按 ESC 也需要时间
                        if self._stop_event.wait(timeout=delays.get('esc_key', 0.01)):
                            break

                # 每一轮完整循环后延迟（拟人化：模拟人类呼吸节奏的随机间隔）
                import random
                sleep_time = random.uniform(0.2, 0.8)
                if self._stop_event.wait(timeout=sleep_time):
                    break
                
        except FileNotFoundError as e:
            # 不可恢复错误：配置文件缺失
            self.push_log("ERROR", f"致命错误 - 配置文件缺失: {str(e)}")
        except ValueError as e:
            # 不可恢复错误：配置格式错误
            self.push_log("ERROR", f"致命错误 - 配置格式错误: {str(e)}")
        except ImportError as e:
            # 不可恢复错误：依赖缺失
            self.push_log("ERROR", f"致命错误 - 依赖缺失: {str(e)}")
        except Exception as e:
            # 其他未预期错误
            logger.error(f"自动化循环异常: {e}", exc_info=True)
            self.push_log("ERROR", f"运行异常: {str(e)}")
        finally:
            self._stop_event.set()
            with self._lock:
                self.status["is_running"] = False
            self.push_log("INFO", "自动化脚本已停止")
            # 通知前端状态已变更
            self._push_status_to_frontend()

    def push_log(self, level, message):
        """主动推送日志到前端（线程安全）"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        # 线程安全地更新日志列表
        with self._lock:
            self.status["logs"].append(log_entry)
            if len(self.status["logs"]) > 100:
                self.status["logs"].pop(0)
            
        # 推送 bot-log 事件到前端，使用 json.dumps 构造安全的 JS 对象
        if self._window:
            try:
                detail = json.dumps({"level": level, "message": message}, ensure_ascii=False)
                self._window.evaluate_js(
                    f"window.dispatchEvent(new CustomEvent('bot-log', {{detail: {detail}}}))"
                )
            except Exception as e:
                logger.debug(f"推送日志到前端失败: {e}")
        
        logger.info(log_entry)

    def _push_status_to_frontend(self):
        """将当前状态推送到前端（线程安全）"""
        if not self._window:
            return
        try:
            with self._lock:
                status_copy = dict(self.status)
            detail_str = json.dumps(status_copy, ensure_ascii=False)
            self._window.evaluate_js(
                f"window.dispatchEvent(new CustomEvent('bot-status', {{detail: {detail_str}}}))"
            )
        except Exception as e:
            logger.debug(f"推送状态到前端失败: {e}")
