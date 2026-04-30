import webview
import os
import sys
import logging
from api import BackendAPI

# 配置日志框架
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("AcidFootCongee")

# 环境感知：判断是否为打包后的生产环境
IS_PRODUCTION = getattr(sys, 'frozen', False)
DEBUG_MODE = os.environ.get('ACIDFOOT_DEBUG', 'false').lower() == 'true'

def get_web_path():
    """获取前端构建后的资源路径或者开发环境路径"""
    # 兼容 PyInstaller 打包环境
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller 单文件模式运行时，会将文件解压到 _MEIPASS 临时目录
        bundle_dir = sys._MEIPASS
        local_path = os.path.join(bundle_dir, "web", "index.html")
        if os.path.exists(local_path):
            return local_path
            
    # 如果是在开发环境中，尝试找到前端工作区目录
    dev_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../AcidFootCongee-frontend/index.html"))
    if os.path.exists(dev_path):
        return dev_path  # 直接返回本地绝对路径
        
    # 如果没打包且前端静态文件直接放在后端 web/ 目录下
    local_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "web/index.html"))
    if os.path.exists(local_path):
        return local_path
        
    logger.warning(f"未找到前端资源，查找路径:\n1. {dev_path}\n2. {local_path}")
    return dev_path

def main():
    """程序入口"""
    logger.info("🚀 正在启动 Delta Force AutoBuy 后端服务...")
    logger.info(f"运行模式: {'生产环境' if IS_PRODUCTION else '开发环境'}")
    logger.info(f"调试模式: {'开启' if DEBUG_MODE else '关闭'}")
    
    # 实例化API，供前端调用
    api = BackendAPI()
    logger.info(f"配置文件路径: {api.config_path}")
    
    # 获取前端路径
    web_path = get_web_path()
    logger.info(f"前端资源路径: {web_path}")
    
    # 创建 WebView 窗口
    window = webview.create_window(
        title='Delta Force AutoBuy — 作战控制台',
        url=web_path,
        js_api=api,
        width=1200,
        height=818,
        min_size=(1000, 700),
        frameless=False,  # 如果前端自己画标题栏，可以设为True
        easy_drag=True,
        background_color='#0f172a'  # 深色背景防白屏
    )
    
    # 将窗口引用保存到 api 中，以便后端主动推送消息给前端
    api.set_window(window)
    
    # 启动应用（环境感知 debug 模式）
    webview.start(
        debug=DEBUG_MODE or not IS_PRODUCTION,
        http_server=True  # 启用本地HTTP服务器加载静态资源，解决CORS和本地文件读取问题
    )

if __name__ == '__main__':
    main()
