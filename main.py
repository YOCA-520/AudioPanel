# -*- coding: utf-8 -*-
"""
AudioPanel - Windows 多音频设备音量控制面板

功能:
    系统托盘常驻, 单击展开音量面板
    枚举所有活跃音频输出设备, 独立调节音量和静音
    支持浅色/暗色/自动三种主题, 三层透明度视觉风格

依赖:
    pip install pycaw PySide6 comtypes

启动:
    python main.py
"""
from __future__ import annotations

import sys
import warnings

from PySide6.QtCore import Qt, QSharedMemory
from PySide6.QtWidgets import QApplication

from audio_engine import AudioEngine
from theme_manager import ThemeManager
from ui.main_panel import MainPanel

# 抑制 pycaw 在控制台输出的 COM 属性警告 (不影响功能)
warnings.filterwarnings("ignore", message="COMError attempting to get property")


def main() -> None:
    """程序入口: 单实例锁 -> 初始化引擎和主题 -> 启动 Qt 事件循环."""

    # ---- 高 DPI 适配 ----
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # ---- 单实例锁 (防止重复启动) ----
    lock = QSharedMemory("AudioPanel_SingleInstance")
    if not lock.create(1):
        return  # 已有实例在运行, 静默退出

    # ---- 创建 Qt 应用 ----
    app = QApplication(sys.argv)
    app.setApplicationName("AudioPanel")
    app.setQuitOnLastWindowClosed(False)  # 关闭面板不退出, 保持托盘运行

    # ---- 初始化核心模块 ----
    engine = AudioEngine()                      # 音频设备管理
    theme_mgr = ThemeManager()                  # 主题管理 (浅色/暗色/自动)
    panel = MainPanel(engine, theme_mgr)        # 主界面 (托盘 + 面板)

    # ---- 进入事件循环 ----
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
