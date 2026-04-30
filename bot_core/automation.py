import sys
import pyautogui
import time
import logging

if sys.platform == 'win32':
    import win32gui
    import win32con

logger = logging.getLogger("AcidFootCongee.automation")

class GameAutomation:
    """处理与游戏窗口交互的自动化逻辑"""
    def __init__(self):
        self.game_window = None
        self._cached_window = None  # 窗口句柄缓存
        self._cache_time = 0        # 缓存时间戳
        self._cache_ttl = 5         # 缓存有效期（秒）
        self.screen_width, self.screen_height = pyautogui.size()
        
    def find_game_window(self):
        """查找游戏窗口并缓存（带 TTL）"""
        if sys.platform != 'win32':
            return None
        
        # 如果缓存有效且窗口仍然存在，直接返回缓存
        now = time.time()
        if self._cached_window and (now - self._cache_time) < self._cache_ttl:
            try:
                # 验证缓存的窗口句柄是否仍然有效
                if win32gui.IsWindow(self._cached_window['hwnd']):
                    self.game_window = self._cached_window
                    return self.game_window
            except Exception:
                pass
            
        game_titles = ["三角洲行动", "Delta Force", "DeltaForce", "UnrealWindow"]
        exclude_titles = ["Cursor", "Visual Studio", "Code", "Explorer", "Chrome", 
                          "Firefox", "Edge", "Discord", "QQ", "WeChat", "Steam", 
                          "Epic Games", "TaskManager", "cmd", "PowerShell", "Python"]
                          
        windows = []
        def enum_windows_callback(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                
                if any(ex.lower() in title.lower() for ex in exclude_titles):
                    return True
                    
                if any(t.lower() in title.lower() for t in game_titles):
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    
                    if width >= 800 and height >= 600:
                        windows.append({
                            'hwnd': hwnd,
                            'title': title,
                            'rect': rect,
                            'width': width,
                            'height': height
                        })
            return True

        win32gui.EnumWindows(enum_windows_callback, None)
        if windows:
            self.game_window = max(windows, key=lambda w: w['width'] * w['height'])
            # 更新缓存
            self._cached_window = self.game_window
            self._cache_time = now
            return self.game_window
        
        # 清除无效缓存
        self._cached_window = None
        return None
        
    def get_coordinates(self):
        """获取游戏内的相对坐标和尺寸信息（复用缓存的窗口句柄）"""
        window = self.game_window or self.find_game_window()
        if window and sys.platform == 'win32':
            try:
                hwnd = window['hwnd']
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.1)
                
                rect = win32gui.GetWindowRect(hwnd)
                return {
                    'offset_x': rect[0],
                    'offset_y': rect[1],
                    'width': rect[2] - rect[0],
                    'height': rect[3] - rect[1],
                    'mode': 'windowed'
                }
            except Exception as e:
                logger.debug(f"获取窗口坐标失败: {e}")
                # 窗口可能已关闭，清除缓存
                self._cached_window = None
                self.game_window = None
                
        return {
            'offset_x': 0,
            'offset_y': 0,
            'width': self.screen_width,
            'height': self.screen_height,
            'mode': 'fullscreen'
        }

    def click_relative(self, rel_x, rel_y, delays):
        """在游戏窗口相对坐标点击（加入拟人化特征，避免防封）"""
        import random
        
        coords = self.get_coordinates()
        base_abs_x = coords['offset_x'] + int(coords['width'] * rel_x)
        base_abs_y = coords['offset_y'] + int(coords['height'] * rel_y)
        
        # 拟人化：加入像素级随机抖动（防止每次点击同一个绝对像素点）
        abs_x = base_abs_x + random.randint(-4, 4)
        abs_y = base_abs_y + random.randint(-4, 4)
        
        try:
            if self.game_window and sys.platform == 'win32':
                win32gui.SetForegroundWindow(self.game_window['hwnd'])
                time.sleep(delays.get("window_focus", 0.05))
        except Exception as e:
            logger.debug(f"前置窗口失败: {e}")
            
        # 拟人化：使用带有缓动动画（先快后慢）的鼠标移动，而不是瞬间闪烁
        # 持续时间在 0.1 到 0.25 秒之间随机
        move_duration = random.uniform(0.1, 0.25)
        pyautogui.moveTo(abs_x, abs_y, duration=move_duration, tween=pyautogui.easeOutQuad)
        
        # 拟人化：到达目标后稍微停顿一下再按下去
        time.sleep(random.uniform(0.02, 0.08))
        pyautogui.click(abs_x, abs_y)
        
        # 尝试发送底层点击事件以防游戏拦截
        try:
            if self.game_window and sys.platform == 'win32':
                hwnd = self.game_window['hwnd']
                client_x = abs_x - coords['offset_x']
                client_y = abs_y - coords['offset_y']
                lparam = (client_y << 16) | (client_x & 0xFFFF)
                win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                # 拟人化：按下鼠标到松开之间，有一个真实的点击时长
                time.sleep(random.uniform(0.03, 0.09))
                win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        except Exception as e:
            logger.debug(f"底层点击事件发送失败: {e}")
