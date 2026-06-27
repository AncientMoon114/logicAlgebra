#!/usr/bin/env python3
"""逻辑代数化简器 — 启动入口（自动打开浏览器）"""

import webbrowser
import threading
import time
import sys
import os

# 确保 PyInstaller 打包后能正确找到 templates 目录
if getattr(sys, 'frozen', False):
    # 打包后的环境
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

os.chdir(base_path)

# 现在 app 才能正确找到 templates/
from app import app


def open_browser():
    time.sleep(1.2)
    webbrowser.open('http://127.0.0.1:8080')


if __name__ == '__main__':
    print("🧠 逻辑代数化简器启动中 ...")
    print(f"   当前目录: {base_path}")
    print("   浏览器将在 1.5 秒后自动打开\n")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=8080, debug=False)
