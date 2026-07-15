# -*- coding: utf-8 -*-
"""
Qt 样式表 (QSS) - 三层磨砂玻璃 + 纯黑白灰配色

层级 (由外到内):
    第一层: 主面板 + 标题栏 + 底栏 (透明/半透, 面板边框)
    第二层: 内容滚动区 (与第一层同透明度)
    第三层: 设备卡片 (磨砂玻璃, 更不透)

所有颜色通过 ThemeColors 驱动, 支持浅色/暗色切换.
"""
from __future__ import annotations
from theme_manager import ThemeColors


def build_stylesheet(c: ThemeColors, outer: float = 1.0, mid: float = 1.0, inner: float = 1.0) -> str:
    """三参数独立透明度: outer(面板), mid(标题栏), inner(卡片)."""
    panel_alpha = outer
    mid_alpha = mid
    card_alpha = inner
    card_hover = min(1.0, inner + 0.1)

    g = c.glass_tint
    return f"""
    * {{
        font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
        font-size: 12px;
    }}

    /* ═══ 主面板 (最外层) ═══ */
    QWidget#mainPanel {{
        background: transparent;
        border: 1px solid rgba({_rgba(c.border, 0.35)});
        border-radius: 12px;
    }}

    /* ═══ 标题栏/底栏 — mid_alpha 绑定 ═══ */
    QWidget#titleBar {{
        background-color: rgba({_rgba(g, mid_alpha)});
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        border-bottom: 1px solid rgba({_rgba(c.border, 0.25)});
    }}
    QWidget#bottomBar {{
        background-color: rgba({_rgba(g, mid_alpha)});
        border-bottom-left-radius: 12px;
        border-bottom-right-radius: 12px;
        border-top: 1px solid rgba({_rgba(c.border, 0.25)});
    }}

    /* ═══ 滚动区域 ═══ */
    QScrollArea#contentScroll {{
        background: transparent;
        border: none;
    }}
    QScrollArea#contentScroll > QWidget {{
        background: transparent;
    }}

    /* ═══ 内容区 — outer_alpha 绑定 ═══ */
    QWidget#contentArea {{
        background-color: rgba({_rgba(g, panel_alpha)});
    }}

    /* ═══ 设备卡片 — inner_alpha 绑定 ═══ */
    QFrame#deviceCard {{
        background-color: rgba({_rgba(g, card_alpha)});
        border: 1px solid rgba({_rgba(c.border, 0.25)});
        border-radius: 6px;
    }}
    QFrame#deviceCard:hover {{
        border-color: rgba({_rgba(c.border, 0.5)});
        background-color: rgba({_rgba(g, card_hover)});
    }}

    /* ═══ 设置选项卡片 — 同 inner_alpha ═══ */
    QFrame#settingCard {{
        background-color: rgba({_rgba(g, card_alpha)});
        border: 1px solid rgba({_rgba(c.border, 0.25)});
        border-radius: 6px;
    }}

    /* ═══ 设备类型色标 (6px 圆点) ═══ */
    QLabel#deviceDot {{
        min-width: 8px; max-width: 8px;
        min-height: 8px; max-height: 8px;
        border-radius: 4px;
        background: transparent;
    }}

    /* ═══ 标题栏按钮 ═══ */
    QPushButton#titleBtn {{
        background: transparent; border: none; border-radius: 4px;
        padding: 2px 6px; font-size: 13px;
        color: {c.text_secondary};
    }}
    QPushButton#titleBtn:hover {{
        background-color: rgba({_rgba(c.surface_hover, 0.5)});
        color: {c.text_primary};
    }}
    /* ═══ 置顶按钮: 未按下=线框, 按下=图标实心(按钮背景保持透明) ═══ */
    QPushButton#pinBtn {{
        background: transparent;
        border: 1px solid rgba({_rgba(c.text_secondary, 0.5)});
        border-radius: 4px;
        padding: 2px; font-size: 12px;
        color: {c.text_secondary};
        min-width: 24px; max-width: 24px;
        min-height: 24px; max-height: 24px;
    }}
    QPushButton#pinBtn:hover {{
        background-color: rgba({_rgba(c.surface_hover, 0.5)});
        border-color: {c.text_primary};
    }}
    QPushButton#pinBtn:checked {{
        background-color: rgba({_rgba(c.surface_hover, 0.5)});
        border: 1px solid {c.text_primary};
    }}

    /* ═══ 推子 (fader) ═══ */
    QSlider::groove:horizontal {{
        background: rgba({_rgba(c.slider_track, 0.55)});
        height: 6px; border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: {c.slider_filled};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {c.slider_filled};
        width: 12px; height: 18px;
        margin: -6px 0; border-radius: 2px;
        border: 1px solid rgba({_rgba(c.border, 0.5)});
    }}
    QSlider::handle:horizontal:hover {{
        background: {c.text_primary};
        width: 14px; height: 20px;
        margin: -7px 0; border-radius: 2px;
    }}

    /* ═══ 滚动条 ═══ */
    QScrollBar:vertical {{
        background: transparent; width: 5px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: rgba({_rgba(c.scrollbar_handle, 0.45)});
        min-height: 20px; border-radius: 2px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba({_rgba(c.text_muted, 0.55)});
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    /* ═══ 标签 — 高对比度 ═══ */
    QLabel#deviceName {{
        color: {c.text_primary}; font-size: 11px; font-weight: 500;
        background: transparent;
    }}
    QLabel#volumeLabel {{
        color: {c.text_secondary}; font-size: 10px; font-weight: 500;
        background: transparent;
    }}
    QLabel#titleLabel {{
        color: {c.text_primary}; font-size: 12px; font-weight: 600;
        background: transparent;
    }}
    QLabel#hintLabel {{
        color: {c.text_secondary}; font-size: 10px; font-weight: 500;
        background: transparent;
    }}

    /* ═══ 小按钮 ═══ */
    QPushButton#muteBtn {{
        background: transparent; border: none; border-radius: 3px;
        padding: 1px; font-size: 11px; font-weight: 600;
        min-width: 18px; max-width: 18px;
        min-height: 18px; max-height: 18px;
        color: {c.text_secondary};
    }}
    QPushButton#muteBtn:hover {{
        background-color: rgba({_rgba(c.surface_hover, 0.5)});
        color: {c.text_primary};
    }}
    QPushButton#muteBtn[muted="true"] {{
        color: {c.danger};
        font-weight: bold;
    }}

    QPushButton#hideBtn {{
        background: transparent; border: 1px solid rgba({_rgba(c.text_muted, 0.4)});
        border-radius: 3px;
        padding: 1px;
        min-width: 18px; max-width: 18px;
        min-height: 18px; max-height: 18px;
        color: {c.text_muted};
    }}
    QPushButton#hideBtn:hover {{
        background-color: rgba({_rgba(c.surface_hover, 0.5)});
        border-color: {c.text_secondary};
        color: {c.text_primary};
    }}

    /* ═══ 折叠头部 ═══ */
    QPushButton#hiddenHeaderBtn {{
        background: transparent; border: none;
        color: {c.text_muted}; font-size: 10px; font-weight: 500;
        text-align: left; padding: 4px 6px;
    }}
    QPushButton#hiddenHeaderBtn:hover {{ color: {c.text_primary}; }}

    /* ═══ 滑动开关 (ToggleSwitch) ═══ */
    QWidget#toggleSwitch {{
        background: transparent;
    }}

    /* ═══ 工具提示 / 菜单 ═══ */
    QToolTip {{
        background-color: rgba({_rgba(c.surface, 0.94)});
        color: {c.text_primary};
        border: 1px solid rgba({_rgba(c.border, 0.5)});
        border-radius: 6px; padding: 4px 8px;
    }}
    QMenu {{
        background-color: rgba({_rgba(c.surface, 0.92)});
        color: {c.text_primary};
        border: 1px solid rgba({_rgba(c.border, 0.4)});
        border-radius: 8px; padding: 4px;
    }}
    QMenu::item {{ padding: 6px 28px; border-radius: 4px; }}
    QMenu::item:selected {{ background-color: {c.accent}; color: {c.bg}; }}
    QMenu::separator {{
        height: 1px; background: rgba({_rgba(c.border, 0.3)});
        margin: 4px 8px;
    }}
    """


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r}, {g}, {b}, {alpha}"


