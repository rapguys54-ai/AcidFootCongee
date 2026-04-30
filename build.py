#!/usr/bin/env python3
"""
DeltaForceAutoBuy 一键构建脚本
用法：python build.py
输出：dist/DeltaForceAutoBuy/ 目录 + DeltaForceAutoBuy.zip
"""

import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path

# === 配置 ===
APP_NAME = "DeltaForceAutoBuy"
ENTRY_SCRIPT = "app.py"
SPEC_FILE = f"{APP_NAME}.spec"
FRONTEND_SRC = Path("../AcidFootCongee-frontend")
FRONTEND_DEST = Path("web")
DIST_DIR = Path("dist") / APP_NAME
TESSERACT_DIR = Path("Tesseract")  # 如果存在，会一并复制

def check_environment():
    """检查构建环境"""
    print("=" * 50)
    print(f"  {APP_NAME} 构建工具")
    print("=" * 50)
    
    # 检查操作系统
    if sys.platform != 'win32':
        print("⚠️  警告：当前运行在非 Windows 系统上")
        print("   PyInstaller 只能为当前操作系统生成可执行文件")
        print("   生成的文件将是当前系统的可执行文件，而非 .exe")
        print()
    
    # 检查 Python 版本
    print(f"✅ Python {sys.version.split()[0]}")
    
    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller 未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])
        print("✅ PyInstaller 安装完成")
    
    # 检查入口脚本
    if not Path(ENTRY_SCRIPT).exists():
        print(f"❌ 入口脚本 {ENTRY_SCRIPT} 不存在")
        sys.exit(1)
    print(f"✅ 入口脚本 {ENTRY_SCRIPT}")


def prepare_frontend():
    """复制前端资源到 web/ 目录"""
    print("\n📦 准备前端资源...")
    
    if not FRONTEND_SRC.exists():
        print(f"❌ 前端目录不存在: {FRONTEND_SRC}")
        print("   请确保 AcidFootCongee-frontend 目录与 backend 同级")
        sys.exit(1)
    
    # 清空并重建 web/ 目录
    if FRONTEND_DEST.exists():
        shutil.rmtree(FRONTEND_DEST)
    
    # 复制前端文件（排除 .git、node_modules 等）
    exclude_patterns = {'.git', 'node_modules', '__pycache__', '.DS_Store', 'README.md'}
    
    def ignore_patterns(directory, files):
        return {f for f in files if f in exclude_patterns}
    
    shutil.copytree(FRONTEND_SRC, FRONTEND_DEST, ignore=ignore_patterns)
    
    # 统计复制的文件
    file_count = sum(1 for _ in FRONTEND_DEST.rglob('*') if _.is_file())
    print(f"✅ 前端资源已复制到 {FRONTEND_DEST}/ ({file_count} 个文件)")


def generate_spec():
    """生成 PyInstaller spec 文件"""
    print("\n📝 生成 spec 配置...")
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# {APP_NAME} PyInstaller 配置
# 自动生成，请通过 build.py 修改

import os

block_cipher = None

a = Analysis(
    ['{ENTRY_SCRIPT}'],
    pathex=[],
    binaries=[],
    datas=[
        # 前端资源打包到 web/ 目录
        ('web', 'web'),
    ],
    hiddenimports=[
        # pywebview 依赖（Windows 后端）
        'webview',
        'bottle',
        'clr',
        'pythonnet',
        # 业务模块
        'bot_core',
        'bot_core.automation',
        'bot_core.ocr_engine',
        'bot_core.config_manager',
        # 第三方核心依赖（防遗漏）
        'cv2',
        'numpy',
        'pyautogui',
        'pytesseract',
        # Windows API 依赖（必须在 hiddenimports 强制声明，否则条件导入可能会被 PyInstaller 忽略）
        'win32gui',
        'win32con',
        'win32api',
        # 标准库
        'json',
        'threading',
        'logging',
        'datetime',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型模块，减小体积
        'tkinter',
        '_tkinter',
        'unittest',
        'email',
        'html',
        'http',
        'xml',
        'pydoc',
        'doctest',
        'argparse',
        'difflib',
        'inspect',
        'pdb',
        'profile',
        'pstats',
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'notebook',
        'setuptools',
        'pkg_resources',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir 模式
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 启用 UPX 压缩（如果可用）
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='app.ico',  # 取消注释并替换为实际图标路径
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{APP_NAME}',
)
'''
    
    with open(SPEC_FILE, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✅ spec 文件已生成: {SPEC_FILE}")


def run_pyinstaller():
    """执行 PyInstaller 打包"""
    print("\n🔨 开始 PyInstaller 打包...")
    print("   这可能需要 1-3 分钟，请耐心等待...\n")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        SPEC_FILE,
        "--clean",           # 清理临时文件
        "--noconfirm",       # 覆盖已有输出
    ]
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("\n❌ PyInstaller 打包失败")
        sys.exit(1)
    
    print("\n✅ PyInstaller 打包完成")


def copy_runtime_files():
    """复制运行时需要的文件到输出目录"""
    print("\n📋 复制运行时文件...")
    
    # 复制 keys.json
    keys_src = Path("keys.json")
    if keys_src.exists():
        shutil.copy2(keys_src, DIST_DIR / "keys.json")
        print(f"✅ keys.json 已复制到输出目录")
    else:
        print("⚠️  keys.json 不存在，跳过")
    
    # 复制 Tesseract 目录（如果存在）
    if TESSERACT_DIR.exists():
        dest = DIST_DIR / "Tesseract"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(TESSERACT_DIR, dest)
        file_count = sum(1 for _ in dest.rglob('*') if _.is_file())
        total_size = sum(f.stat().st_size for f in dest.rglob('*') if f.is_file())
        print(f"✅ Tesseract 已复制 ({file_count} 个文件, {total_size / 1024 / 1024:.1f} MB)")
    else:
        print(f"⚠️  {TESSERACT_DIR}/ 目录不存在，跳过 Tesseract 打包")
        print(f"   用户需自行安装 Tesseract 或将其放置在 exe 同级目录")
    
    # 创建 screenshots 目录
    screenshots_dir = DIST_DIR / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    print("✅ screenshots/ 目录已创建")


def create_zip():
    """创建分发用的 zip 压缩包"""
    print("\n📦 创建分发压缩包...")
    
    zip_path = Path("dist") / f"{APP_NAME}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in DIST_DIR.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(Path("dist"))
                zf.write(file_path, arcname)
    
    zip_size = zip_path.stat().st_size / 1024 / 1024
    print(f"✅ 压缩包已生成: {zip_path} ({zip_size:.1f} MB)")


def print_summary():
    """打印构建摘要"""
    print("\n" + "=" * 50)
    print("  构建完成!")
    print("=" * 50)
    
    if DIST_DIR.exists():
        total_size = sum(f.stat().st_size for f in DIST_DIR.rglob('*') if f.is_file())
        file_count = sum(1 for _ in DIST_DIR.rglob('*') if _.is_file())
        print(f"\n📁 输出目录: {DIST_DIR}/")
        print(f"   文件数量: {file_count}")
        print(f"   总体积:   {total_size / 1024 / 1024:.1f} MB")
    
    exe_path = DIST_DIR / f"{APP_NAME}.exe"
    if exe_path.exists():
        print(f"\n🚀 可执行文件: {exe_path}")
        print(f"   双击运行即可使用!")
    
    zip_path = Path("dist") / f"{APP_NAME}.zip"
    if zip_path.exists():
        print(f"\n📦 分发压缩包: {zip_path}")
    
    print()


def main():
    """主构建流程"""
    # 确保在项目根目录执行
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)
    
    # 检查是否为 dry-run 模式
    dry_run = "--dry-run" in sys.argv
    
    check_environment()
    prepare_frontend()
    generate_spec()
    
    if dry_run:
        print("\n🔍 Dry-run 模式：跳过实际打包步骤")
        print("✅ 所有预检查通过，可以执行实际打包")
        return
    
    run_pyinstaller()
    copy_runtime_files()
    create_zip()
    print_summary()


if __name__ == "__main__":
    main()
