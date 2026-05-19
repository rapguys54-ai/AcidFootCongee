"""
state_machine.py — 子弹自动购买状态机

状态流转：
  IDLE → SEARCHING → IN_LIST → OCR_PRICE
       ↓ price<=max                    ↓ price>max
     BUYING → ESC → 点击卡片 → IN_LIST   WAITING_SOLD_OUT
                                        ↓ 30s无弹窗
                                      SWITCHING → SEARCHING (下一款)
"""

import sys
import time
import re
import logging

logger = logging.getLogger("AcidFootCongee.state_machine")

# ──────────────────────────────────────────
# 状态常量
# ──────────────────────────────────────────
IDLE               = 'idle'
SEARCHING          = 'searching'
IN_LIST            = 'in_list'
OCR_PRICE          = 'ocr_price'
BUYING             = 'buying'
WAITING_SOLD_OUT   = 'waiting_sold_out'
SWITCHING          = 'switching'

# 用于判定"库存存在"的弹窗文字
POPUP_KEYWORDS = ["价格更新", "已用更低价格成交"]


class BotStateMachine:
    def __init__(self, config: dict, push_log, push_status, stop_event):
        """
        config      : 完整 keys.json dict（已 load）
        push_log    : fn(level, msg) 推送日志到前端
        push_status : fn(data) 推送状态到前端
        stop_event  : threading.Event，set() 时停止
        """
        self.config       = config
        self.push_log     = push_log
        self.push_status  = push_status
        self.stop_event   = stop_event

        self.coords  = config.get('ui_coords', {})
        self.delays  = config.get('delays', {})
        self.bullets = [b for b in config.get('today_bullets', []) if b.get('enabled', True)]

        self.state            = IDLE
        self.bullet_idx       = 0          # 当前购买的子弹索引
        self.total_purchased  = 0
        self.current_price    = None
        self.sold_out_timer   = None       # 等待卖光计时开始时间
        self.popup_detected   = False

        # 延迟参数（极速模式，最小必要延迟）
        self.delay_search   = float(self.delays.get('after_search_input', 0.3))
        self.delay_card     = float(self.delays.get('after_click_card',   0.4))
        self.delay_ocr      = float(self.delays.get('ocr_interval',       0.05))
        self.sold_out_sec   = float(self.delays.get('sold_out_timeout',   30))

    # ──────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────

    def run(self):
        if not self.bullets:
            self.push_log("WARNING", "今日购买清单为空！请先在「子弹百科」中添加要购买的子弹。")
            return

        self.push_log("INFO", f"🚀 开始扫货，今日目标：{len(self.bullets)} 款子弹")
        self.state = SEARCHING

        # 延迟导入（仅 Windows 可用）
        try:
            import pyautogui
            import keyboard as kb
        except ImportError as e:
            self.push_log("ERROR", f"依赖缺失: {e}")
            return

        try:
            from bot_core.automation import GameAutomation
            from bot_core.ocr_engine  import OcrEngine
        except ImportError as e:
            self.push_log("ERROR", f"模块缺失: {e}")
            return

        auto = GameAutomation()
        ocr  = OcrEngine()

        while not self.stop_event.is_set():
            if self.bullet_idx >= len(self.bullets):
                # 所有子弹轮询一遍，再从头开始
                self.bullet_idx = 0
                self.push_log("INFO", "🔄 本轮轮询结束，重新从第一款开始...")

            bullet = self.bullets[self.bullet_idx]
            self._update_bullet_status(bullet['id'], 'running')

            try:
                self._run_one_bullet(bullet, auto, ocr, pyautogui, kb)
            except Exception as e:
                logger.exception(f"子弹 {bullet['name']} 执行异常")
                self.push_log("ERROR", f"[{bullet['name']}] 异常: {e}")

            self.bullet_idx += 1

    # ──────────────────────────────────────────
    # 单款子弹完整流程
    # ──────────────────────────────────────────

    def _run_one_bullet(self, bullet, auto, ocr, pyautogui, kb):
        name      = bullet['name']
        max_price = int(bullet.get('max_price', 0))
        self.push_log("INFO", f"🎯 目标子弹: {name}（预算: {max_price:,}）")

        coords = auto.get_coordinates()
        if not coords and sys.platform == 'win32':
            self.push_log("WARNING", "未找到游戏窗口，跳过本款")
            return

        # ① 搜索进入
        if not self._do_search(bullet, auto, pyautogui, kb, coords):
            return

        # ② 设置数量 200
        self._click_rel(auto, pyautogui, coords, self.coords.get('slider_max', [0.932, 0.725]))
        self.push_log("INFO", f"[{name}] ✅ 数量已设为 200")

        # ③ 进入内层扫货循环
        self.sold_out_timer  = None
        self.popup_detected  = False
        bought_this_round    = 0

        while not self.stop_event.is_set():
            # OCR 读取价格
            price = self._read_price(ocr, auto, coords)
            self.current_price = price
            self._push_price(price, bullet)

            if price is not None and price <= max_price:
                # ── 价格满足：极速购买 ──
                self.sold_out_timer = None  # 重置卖光计时
                self._click_rel(auto, pyautogui, coords,
                                self.coords.get('price_button', [0.845, 0.795]))
                self.total_purchased += 200
                bought_this_round   += 200
                self.push_log("SUCCESS",
                    f"⚡ [{name}] 成功购买 200 发！本轮累计: {bought_this_round}，总计: {self.total_purchased}")
                self.push_status({"total_purchases": self.total_purchased,
                                   "current_bullet": name,
                                   "last_price": price})

                # 极速退出再进入（ESC 后仍在搜索结果页，只需重新点卡片）
                kb.press('esc')
                time.sleep(0.05)
                self._click_rel(auto, pyautogui, coords,
                                self.coords.get('first_card', [0.35, 0.22]))
                time.sleep(self.delay_card)
                self._click_rel(auto, pyautogui, coords,
                                self.coords.get('slider_max', [0.932, 0.725]))

            else:
                # ── 价格过高或识别失败：检测是否卖光 ──
                if self.sold_out_timer is None:
                    self.sold_out_timer = time.time()
                    self.push_log("INFO",
                        f"[{name}] 价格 {price or '?'} > 预算 {max_price}，"
                        f"开始 {self.sold_out_sec}s 卖光检测窗口...")

                # 扫描弹窗 OCR
                popup_text = self._read_popup(ocr, auto, coords)
                if popup_text and any(kw in popup_text for kw in POPUP_KEYWORDS):
                    self.push_log("INFO", f"[{name}] 检测到补货弹窗，库存仍有！继续守候...")
                    self.sold_out_timer = time.time()  # 重置计时器
                    time.sleep(self.delay_ocr)
                    continue

                elapsed = time.time() - self.sold_out_timer
                if elapsed >= self.sold_out_sec:
                    self.push_log("WARNING",
                        f"💀 [{name}] {self.sold_out_sec}s 内无补货迹象，判定此波已卖光！切换下一款。")
                    self._update_bullet_status(bullet['id'], 'empty')
                    break

                time.sleep(self.delay_ocr)

        # 退出当前子弹详情页
        kb.press('esc')
        time.sleep(0.1)

    # ──────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────

    def _do_search(self, bullet, auto, pyautogui, kb, coords):
        """点击搜索框 → 输入名称 → 等待 → 点击第一张卡片 → 等待"""
        try:
            self._click_rel(auto, pyautogui, coords,
                            self.coords.get('search_box', [0.13, 0.165]))
            time.sleep(0.05)
            # 清空当前搜索框内容
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.typewrite(bullet['name'], interval=0.03)
            time.sleep(self.delay_search)

            self._click_rel(auto, pyautogui, coords,
                            self.coords.get('first_card', [0.35, 0.22]))
            time.sleep(self.delay_card)
            return True
        except Exception as e:
            self.push_log("ERROR", f"搜索进入失败: {e}")
            return False

    def _click_rel(self, auto, pyautogui, coords, rel_xy):
        """相对坐标点击"""
        if not coords:
            return
        x = coords['offset_x'] + int(coords['width']  * rel_xy[0])
        y = coords['offset_y'] + int(coords['height'] * rel_xy[1])
        pyautogui.click(x, y)

    def _read_price(self, ocr, auto, coords):
        """OCR 读取价格区域，返回 int 或 None"""
        pr = self.coords.get('price_region', [0.78, 0.752, 0.95, 0.785])
        if not coords:
            return None
        x1 = coords['offset_x'] + int(coords['width']  * pr[0])
        y1 = coords['offset_y'] + int(coords['height'] * pr[1])
        w  = int(coords['width']  * (pr[2] - pr[0]))
        h  = int(coords['height'] * (pr[3] - pr[1]))
        result = ocr.get_price((x1, y1, w, h))
        if isinstance(result, dict):
            return result.get('price')
        return result

    def _read_popup(self, ocr, auto, coords):
        """OCR 读取弹窗区域文字"""
        pr = self.coords.get('popup_region', [0.30, 0.40, 0.70, 0.65])
        if not coords:
            return ""
        x1 = coords['offset_x'] + int(coords['width']  * pr[0])
        y1 = coords['offset_y'] + int(coords['height'] * pr[1])
        w  = int(coords['width']  * (pr[2] - pr[0]))
        h  = int(coords['height'] * (pr[3] - pr[1]))
        try:
            result = ocr.get_text((x1, y1, w, h))
            return result or ""
        except Exception:
            return ""

    def _push_price(self, price, bullet):
        self.push_status({
            "last_price":     price,
            "current_bullet": bullet['name'],
            "max_price":      bullet.get('max_price'),
        })

    def _update_bullet_status(self, bullet_id, status):
        for b in self.bullets:
            if b.get('id') == bullet_id:
                b['status'] = status
                break
        self.push_status({"bullet_statuses": {b['id']: b['status'] for b in self.bullets}})
