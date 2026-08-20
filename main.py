#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NIFTI转DICOM工具 - 主程序入口
"""

import sys
import os

# 兼容打包后和开发环境的路径处理
if getattr(sys, 'frozen', False):
    # 打包后的环境
    application_path = os.path.dirname(sys.executable)
else:
    # 开发环境
    application_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, application_path)

# 导入GUI
from gui import main

if __name__ == '__main__':
    main()
