# -*- coding: utf-8 -*-
"""
主题管理器 - 浅色/暗色/自动 三种主题模式

自动模式:
    读取 Windows 注册表 AppsUseLightTheme, 每 2 秒轮询变更,
    跟随系统主题自动切换.

性能:
    使用模块级字符串常量代替 Enum, 避免元类属性查找开销.

扩展:
    set_custom_colors(theme, ThemeColors) 可自定义主题色.
"""
from __future__ import annotations

import winreg
from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer

# ============================================================
# 主题常量 (字符串, 比 Enum 更轻量)
# ============================================================

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_AUTO = "auto"
THEME_ORDER = [THEME_LIGHT, THEME_DARK, THEME_AUTO]

THEME_LABELS = {
    THEME_LIGHT: "light mode",
    THEME_DARK: "dark mode",
    THEME_AUTO: "auto",
}
THEME_ICONS = {
    THEME_LIGHT: "\u25d0",    # 半圆 (浅色)
    THEME_DARK: "\u25d1",    # 半圆 (暗色)
    THEME_AUTO: "\u25ce",    # 双圆 (自动)
}


def _theme_valid(value: str) -> bool:
    """检查主题值是否合法."""
    return value in (THEME_LIGHT, THEME_DARK, THEME_AUTO)


# ============================================================
# 主题色彩定义
# ============================================================

class ThemeColors:
    """一组主题的颜色定义 (纯黑白灰 + 透明度分层).

    字段说明:
        bg:              背景色
        surface:          表面色 (卡片/面板底色)
        surface_hover:    悬浮态颜色
        border:           边框颜色
        accent:           强调色
        accent_hover:     强调悬浮态
        text_primary:     主文字颜色
        text_secondary:   次要文字颜色
        text_muted:       弱化文字颜色
        slider_track:     滑块轨道颜色
        slider_filled:    滑块已填充颜色
        scrollbar_handle: 滚动条手柄颜色
        danger:           危险/警告色 (静音红)
        glass_tint:       玻璃底色 (默认同 surface)
    """

    def __init__(
        self,
        bg: str,
        surface: str,
        surface_hover: str,
        border: str,
        accent: str,
        accent_hover: str,
        text_primary: str,
        text_secondary: str,
        text_muted: str,
        slider_track: str,
        slider_filled: str,
        scrollbar_handle: str,
        danger: str,
        glass_tint: str = "",
    ) -> None:
        self.bg = bg
        self.surface = surface
        self.surface_hover = surface_hover
        self.border = border
        self.accent = accent
        self.accent_hover = accent_hover
        self.text_primary = text_primary
        self.text_secondary = text_secondary
        self.text_muted = text_muted
        self.slider_track = slider_track
        self.slider_filled = slider_filled
        self.scrollbar_handle = scrollbar_handle
        self.danger = danger
        self.glass_tint = glass_tint or surface  # 默认同 surface, 可替换改玻璃色调


# ---- 浅色主题 (高对比度, 易阅读) ----
LIGHT_COLORS = ThemeColors(
    bg="#F2F2F2",
    surface="#FCFCFC",
    surface_hover="#F0F0F0",
    border="#C8C8C8",
    accent="#2B2B2B",
    accent_hover="#4A4A4A",
    text_primary="#0D0D0D",
    text_secondary="#4A4A4A",
    text_muted="#777777",
    slider_track="#CCCCCC",
    slider_filled="#1E1E1E",
    scrollbar_handle="#AAAAAA",
    danger="#D01B2E",
)

# ---- 暗色主题 (高对比度, 易阅读) ----
DARK_COLORS = ThemeColors(
    bg="#181818",
    surface="#252525",
    surface_hover="#303030",
    border="#3E3E3E",
    accent="#D4D4D4",
    accent_hover="#EAEAEA",
    text_primary="#F5F5F5",
    text_secondary="#C0C0C0",
    text_muted="#888888",
    slider_track="#484848",
    slider_filled="#D4D4D4",
    scrollbar_handle="#5A5A5A",
    danger="#FF5555",
)


# ============================================================
# 主题管理器
# ============================================================

class ThemeManager(QObject):
    """主题管理器.

    用法:
        tm = ThemeManager()
        tm.theme_changed.connect(on_theme_changed)      # 用户切换主题
        tm.effective_theme_changed.connect(on_effective) # 实际生效主题变化
        colors = tm.colors                               # 当前 ThemeColors
        tm.cycle()                                       # light -> dark -> auto

    信号:
        theme_changed(str)          用户选择的主题名 (light/dark/auto)
        effective_theme_changed(str) 实际生效的主题名 (light/dark, auto已解析)
    """

    theme_changed = Signal(str)
    effective_theme_changed = Signal(str)

    # Windows 注册表路径 (系统主题)
    _REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    _REG_VALUE = "AppsUseLightTheme"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._theme: str = THEME_AUTO
        self._last_system_light: Optional[bool] = None
        self._custom_colors: dict[str, Optional[ThemeColors]] = {
            THEME_LIGHT: None,
            THEME_DARK: None,
        }

        # 每 2 秒轮询系统主题变化
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._check_system_theme)
        self._poll_timer.start()

    # ============================================================
    # 属性
    # ============================================================

    @property
    def theme(self) -> str:
        """用户选择的主题名."""
        return self._theme

    @property
    def colors(self) -> ThemeColors:
        """当前生效的 ThemeColors (自定义 > 默认)."""
        effective = self.effective_theme
        custom = self._custom_colors.get(effective)
        if custom is not None:
            return custom
        return DARK_COLORS if effective == THEME_DARK else LIGHT_COLORS

    @property
    def effective_theme(self) -> str:
        """解析 AUTO 后的实际主题 (light 或 dark)."""
        if self._theme == THEME_AUTO:
            return THEME_DARK if not self._read_system_light() else THEME_LIGHT
        return self._theme

    # ============================================================
    # 公共 API
    # ============================================================

    def set_theme(self, theme: str) -> None:
        """设置主题. 同值不重复发信号."""
        if not _theme_valid(theme):
            return
        if theme == self._theme:
            return

        old_effective = self.effective_theme
        self._theme = theme
        self.theme_changed.emit(theme)

        new_effective = self.effective_theme
        if new_effective != old_effective:
            self.effective_theme_changed.emit(new_effective)

    def cycle(self) -> None:
        """循环切换: light -> dark -> auto -> light."""
        idx = THEME_ORDER.index(self._theme) if self._theme in THEME_ORDER else 0
        self.set_theme(THEME_ORDER[(idx + 1) % len(THEME_ORDER)])

    def get_theme_label(self) -> str:
        """获取当前主题的显示标签."""
        return THEME_LABELS.get(self._theme, "?")

    def get_effective_label(self) -> str:
        """获取有效主题的显示标签."""
        eff = self.effective_theme
        labels = {THEME_LIGHT: "light", THEME_DARK: "dark"}
        base = labels.get(eff, "?")
        if self._theme == THEME_AUTO:
            return f"{base} (auto)"
        return base

    def get_theme_icon(self) -> str:
        """获取当前主题的图标字符."""
        return THEME_ICONS.get(self._theme, "\u25ce")

    def set_custom_colors(
        self, theme: str, colors: Optional[ThemeColors]
    ) -> None:
        """扩展接口: 设置自定义主题色, None 恢复默认."""
        if _theme_valid(theme):
            self._custom_colors[theme] = colors
            self.effective_theme_changed.emit(self.effective_theme)

    # ============================================================
    # 内部: 系统主题检测
    # ============================================================

    def _read_system_light(self) -> bool:
        """读 Windows 注册表 AppsUseLightTheme.

        True  = 浅色主题
        False = 暗色主题
        异常时默认返回 True (浅色).
        """
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._REG_KEY)
            value, _ = winreg.QueryValueEx(key, self._REG_VALUE)
            winreg.CloseKey(key)
            return bool(value)
        except OSError:
            return True

    def _check_system_theme(self) -> None:
        """轮询系统主题变化 (仅在 AUTO 模式下生效)."""
        if self._theme != THEME_AUTO:
            return
        current = self._read_system_light()
        if self._last_system_light is not None and current != self._last_system_light:
            self.effective_theme_changed.emit(
                THEME_LIGHT if current else THEME_DARK
            )
        self._last_system_light = current
