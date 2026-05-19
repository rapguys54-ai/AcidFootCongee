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
        """多维度图像预处理以提升极小字体的识别率"""
        # 1. 强制无损缩放 3 倍 (Tesseract 识别 30px 高度最佳，游戏 UI 往往只有 12px)
        scaled = cv2.resize(img, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        
        # 2. 增加对比度 (CLAHE 对游戏 UI 效果极佳)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced_gray = clahe.apply(gray)
        
        # 3. 生成正向 OTSU 二值化 (黑底白字 -> 白底黑字)
        _, thresh = cv2.threshold(enhanced_gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        
        # 4. 生成反向 OTSU 二值化 (防白底黑字)
        _, thresh_inv = cv2.threshold(enhanced_gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        
        # 返回预处理后的图片矩阵
        return [enhanced_gray, thresh_inv, thresh]

    def get_price(self, region_tuple):
        """根据屏幕区域识别价格，并返回价格和截图预览"""
        img = self.take_screenshot(region_tuple)
        if img is None:
            return {"price": None, "preview": None}
            
        # 提取用于前端预览的 Base64 (使用原图，质量设为 60)
        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        preview_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # 获取预处理后的多形态图片矩阵
        processed_images = self.preprocess_image(img)
        images_to_test = [img] + processed_images
        
        # 宽容的多层次识别配置矩阵
        configs = [
            "--psm 7 -c tessedit_char_whitelist=0123456789,", # 单行纯数字
            "--psm 8 -c tessedit_char_whitelist=0123456789,", # 单个词块纯数字
            "--psm 7", # 不限制白名单，允许识别出杂质字母，依靠后置正则清洗
            "--psm 6"  # 假设有多行杂乱文本的宽容模式
        ]
        
        import re
        
        # 矩阵式交叉识别，命中即停
        for i in images_to_test:
            for config in configs:
                try:
                    text = pytesseract.image_to_string(i, lang='eng', config=config)
                    # 暴力清洗：剔除所有非数字字符（比如千分位逗号、误识别的字母等）
                    digits_only = re.sub(r'\D', '', text)
                    if digits_only:
                        price = int(digits_only)
                        # 最低门槛设定为 1
                        if 1 <= price <= 100000000:
                            return {"price": price, "preview": preview_b64}
                except Exception as e:
                    logger.debug(f"OCR 识别尝试失败: {e}")
                    continue
                    
        # 全部策略失败
        return {"price": None, "preview": preview_b64}

    def get_text(self, region_tuple) -> str:
        """识别区域内的任意文字（用于弹窗检测），返回字符串"""
        img = self.take_screenshot(region_tuple)
        if img is None:
            return ""
        try:
            # 放大 + 灰度处理
            scaled = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            gray   = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
            _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            text   = pytesseract.image_to_string(
                thr, lang='chi_sim+eng',
                config='--psm 6'
            )
            return text.strip()
        except Exception as e:
            logger.debug(f"get_text 失败: {e}")
            return ""

