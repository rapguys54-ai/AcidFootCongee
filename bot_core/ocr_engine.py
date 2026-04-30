import pytesseract
import cv2
import numpy as np
import pyautogui
import os
import sys
import logging
import base64

logger = logging.getLogger("AcidFootCongee.ocr")

class OcrEngine:
    """OCR 识别引擎，处理截图和价格/文字识别"""
    def __init__(self, tesseract_cmd=None):
        # 截图目录放在项目根目录下
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.screenshots_dir = os.path.join(base_dir, "screenshots")
        if not os.path.exists(self.screenshots_dir):
            try:
                os.makedirs(self.screenshots_dir)
            except OSError as e:
                logger.warning(f"创建截图目录失败: {e}")

        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        else:
            # 自动寻找 Tesseract 路径（按优先级排列）
            # 1. exe 同级目录（打包分发场景）
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
            else:
                exe_dir = base_dir
            
            possible_paths = [
                # 打包后 exe 同级的 Tesseract 目录
                os.path.join(exe_dir, "Tesseract", "tesseract.exe"),
                # 项目根目录下的 Tesseract
                os.path.join(base_dir, "Tesseract", "tesseract.exe"),
                # Windows 系统安装路径
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                # macOS / Linux 常见路径
                "/usr/local/bin/tesseract",
                "/usr/bin/tesseract",
                "/opt/homebrew/bin/tesseract",
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    tessdata = os.path.join(os.path.dirname(p), 'tessdata')
                    if os.path.exists(tessdata):
                        os.environ["TESSDATA_PREFIX"] = tessdata
                    break
                    
    def take_screenshot(self, region):
        """指定区域截图并转为OpenCV格式"""
        try:
            screenshot = pyautogui.screenshot(region=region)
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.debug(f"截图失败: {e}")
            return None

    def preprocess_image(self, img):
        """图像预处理以提升识别率"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        return cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    def get_price(self, region_tuple):
        """根据屏幕区域识别价格，并返回价格和截图预览"""
        img = self.take_screenshot(region_tuple)
        if img is None:
            return {"price": None, "preview": None}
            
        processed_img = self.preprocess_image(img)
        
        # 提取用于前端预览的 Base64 (使用原图，质量设为 60)
        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        preview_b64 = base64.b64encode(buffer).decode('utf-8')
        
        configs = [
            "--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789,",
            "--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789,",
            "--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789,"
        ]
        
        images = [img, processed_img]
        
        for i in images:
            for config in configs:
                try:
                    text = pytesseract.image_to_string(i, lang='eng', config=config)
                    cleaned = text.replace(",", "").replace(" ", "").replace("\n", "").strip()
                    if cleaned and cleaned.isdigit():
                        price = int(cleaned)
                        if 1 <= price <= 100000000:
                            return {"price": price, "preview": preview_b64}
                except Exception as e:
                    logger.debug(f"OCR 识别尝试失败: {e}")
                    continue
                    
        return {"price": None, "preview": preview_b64}
