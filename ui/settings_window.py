# -*- coding: utf-8 -*-
"""
设置窗口模块 — 无边框玻璃风格, 左右分栏布局, 单实例管理

页面:
    - 通用: 主题切换, 窗口置顶, 开机自启
    - 面板: 三层透明度, 高斯模糊, 自动收起延迟, 屏幕边距
    - 高级: 设备刷新间隔, 音量同步间隔
    - 关于: 版本与技术栈信息

组件:
    - ToggleSwitch: iOS 风格滑动开关
    - FaderRow: 推子滑块行 (与音量推子同款样式)
    - SliderInput: 滑块+数值输入组合控件
    - Toast: 浮动圆角通知条
"""
from __future__ import annotations

import winreg
import sys as _sys

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QTimer
from PySide6.QtGui import QMouseEvent, QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QSpinBox, QPushButton, QComboBox, QSlider,
    QStackedWidget, QApplication,
)

from theme_manager import ThemeManager, ThemeColors
from config import (
    get_theme, set_theme,
    get_always_on_top, set_always_on_top,
    get_panel_margins,
    load_config, save_config, reset_config, DEFAULT_CONFIG,
)
from ui.styles import build_stylesheet, _rgba


# ─── 滑动开关组件 ────────────────────────────────────

class ToggleSwitch(QWidget):
    """iOS 风格滑动开关, 替代朴素 QCheckBox."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setObjectName("toggleSwitch")
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        self._checked = checked
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = 44, 24
        if self._checked:
            # 开启: 强调色背景
            track_color = QColor("#333333")  # 深色主题用暗色, 会自动跟随
            knob_x = 22
        else:
            track_color = QColor("#BBBBBB")
            knob_x = 2

        # 轨道
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(0, 2, w, 20, 10, 10)

        # 圆形滑块
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#DDDDDD"), 0.5))
        p.drawEllipse(knob_x, 0, 20, 20)

        p.end()

    def mousePressEvent(self, event) -> None:
        self._checked = not self._checked
        self.toggled.emit(self._checked)
        self.update()

    def update_theme_colors(self, accent: str) -> None:
        self.update()


# ─── 推子滑块行 ──────────────────────────────────────

class FaderRow(QWidget):
    """推子行: [====滑块====] [100%], 与音量推子同款样式."""

    valueChanged = Signal(int)

    def __init__(self, value: int = 100, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(value)
        self._slider.setMinimumWidth(120)

        self._label = QLabel(f"{value}%")
        self._label.setObjectName("faderLabel")
        self._label.setFixedWidth(40)
        self._label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._slider, 1)
        layout.addWidget(self._label)
        layout.addStretch()

        self._slider.valueChanged.connect(self._on_change)

    def _on_change(self, v: int) -> None:
        self._label.setText(f"{v}%")
        self.valueChanged.emit(v)

    def value(self) -> int:
        return self._slider.value()

    def setValue(self, v: int) -> None:
        self._slider.setValue(v)

    def slider(self) -> QSlider:
        """暴露内部 QSlider, 用于连接 sliderReleased."""
        return self._slider


# ─── 滑块+数值输入行 ──────────────────────────────────

class SliderInput(QWidget):
    """滑块+数值输入: [====滑块====] [spinner] 后缀, 拖拽或输入均可."""

    valueChanged = Signal(int)

    def __init__(self, lo: int, hi: int, val: int, suffix: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lo = lo
        self._hi = hi
        self._suffix = suffix
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(lo, hi)
        self._slider.setValue(val)
        self._slider.setMinimumWidth(100)

        self._spin = QSpinBox()
        self._spin.setRange(lo, hi)
        self._spin.setValue(val)
        self._spin.setSuffix(suffix)
        self._spin.setFixedWidth(72 if suffix else 56)

        layout.addWidget(self._slider, 1)
        layout.addWidget(self._spin)
        layout.addStretch()

        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)

    def _on_slider(self, v: int) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(v)
        self._spin.blockSignals(False)
        self.valueChanged.emit(v)

    def _on_spin(self, v: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._slider.blockSignals(False)
        self.valueChanged.emit(v)

    def value(self) -> int:
        return self._spin.value()

    def setValue(self, v: int) -> None:
        self._slider.setValue(v)

    def slider(self) -> QSlider:
        return self._slider


# ─── Toast 通知 ──────────────────────────────────────

class Toast(QWidget):
    """浮动圆角通知条 — 叠加层, 不挤占布局, 随主题反色."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toastBar")
        self.setFixedHeight(30)
        self.hide()
        self._label = QLabel("", self)
        self._label.setObjectName("toastLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._is_dark = True  # 默认深色底白字
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._fade_anim: QPropertyAnimation | None = None

    def set_dark_theme(self, dark: bool) -> None:
        self._is_dark = dark
        self.update()

    def show_msg(self, text: str, duration_ms: int = 1500) -> None:
        self._label.setText(text)
        self._timer.stop()
        # 定位: 标题栏下方, 左右留边距
        pw = self.parentWidget()
        if pw:
            self.setGeometry(12, 38, pw.width() - 24, 30)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(180)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
        self._timer.start(duration_ms)

    def _fade_out(self) -> None:
        if self._fade_anim:
            self._fade_anim.stop()
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(350)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self.hide)
        self._fade_anim.start()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._is_dark:
            p.setBrush(QColor(44, 44, 44, 235))   # 深色底
        else:
            p.setBrush(QColor(245, 245, 245, 235))  # 浅色底
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect().adjusted(4, 2, -4, -2), 8, 8)
        p.end()

# ─── 单实例 ──────────────────────────────────────────

_instance: SettingsWindow | None = None


# ─── 开机自启 ────────────────────────────────────────

_STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_STARTUP_NAME = "AudioPanel"


def _is_startup() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_KEY)
        v, _ = winreg.QueryValueEx(k, _STARTUP_NAME)
        winreg.CloseKey(k)
        return bool(v)
    except OSError:
        return False


def _set_startup(on: bool) -> None:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_KEY, 0,
                           winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        if on:
            exe = _sys.executable
            script = _sys.argv[0] if _sys.argv else ""
            cmd = f'"{exe}" "{script}"'
            winreg.SetValueEx(k, _STARTUP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, _STARTUP_NAME)
            except OSError:
                pass
        winreg.CloseKey(k)
    except OSError:
        pass


# ─── 设置窗口 ────────────────────────────────────────

class SettingsWindow(QWidget):
    """无边框玻璃设置窗口, 左右分栏."""

    applied = Signal()  # 应用设置时发出
    _W = 640
    _H = 440

    def __init__(self, theme_mgr: ThemeManager, parent=None):
        global _instance
        if _instance is not None:
            _instance.raise_()
            _instance.activateWindow()
            return
        _instance = self

        super().__init__(parent)
        self._theme_mgr = theme_mgr
        self._drag_pos: QPoint | None = None

        self.setWindowTitle("AudioPanel 设置")
        self.setFixedSize(self._W, self._H)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui()
        self._apply_theme()
        self._theme_mgr.effective_theme_changed.connect(self._apply_theme)
        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            g = screen.availableGeometry()
            self.move((g.width() - self._W) // 2 + g.x(),
                       (g.height() - self._H) // 2 + g.y())

    # ─── UI ───────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 标题栏
        root.addWidget(self._title_bar())
        # Toast 浮动层 (不在布局中, 不挤占空间)
        self._toast = Toast(self)

        # 主区域: 左栏 + 右内容
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # ── 左侧导航 ──
        nav = QWidget()
        nav.setObjectName("sideNav")
        nav.setFixedWidth(160)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(0, 12, 0, 12)
        nav_layout.setSpacing(2)

        self._nav_btns: list[QPushButton] = []
        pages = ["通用", "面板", "高级", "关于"]
        for i, name in enumerate(pages):
            btn = QPushButton(f"  {name}")
            btn.setObjectName("navBtn")
            btn.setFixedHeight(36)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._switch_page(idx))
            nav_layout.addWidget(btn)
            self._nav_btns.append(btn)
        nav_layout.addStretch()
        body.addWidget(nav)

        # ── 右侧内容 ──
        self._stack = QStackedWidget()
        self._stack.setObjectName("contentStack")
        self._stack.addWidget(self._page_general())
        self._stack.addWidget(self._page_panel())
        self._stack.addWidget(self._page_advanced())
        self._stack.addWidget(self._page_about())
        body.addWidget(self._stack, 1)

        root.addLayout(body, 1)

        # 底部操作栏
        bottom = QWidget()
        bottom.setObjectName("bottomBar")
        bottom.setFixedHeight(38)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(16, 0, 12, 0)

        self._status = QLabel("")
        self._status.setObjectName("statusText")
        bl.addWidget(self._status)
        bl.addStretch()

        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("actionBtn")
        reset_btn.setToolTip("恢复所有设置为默认值")
        reset_btn.clicked.connect(self._reset_defaults)
        bl.addWidget(reset_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("actionBtn")
        cancel_btn.clicked.connect(self.close)
        bl.addWidget(cancel_btn)

        apply_btn = QPushButton("应用")
        apply_btn.setObjectName("applyBtn")
        apply_btn.clicked.connect(self._apply)
        bl.addWidget(apply_btn)

        root.addWidget(bottom)

        self._nav_btns[0].setChecked(True)

    def _title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(36)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 4, 0)

        title = QLabel("⚙  AudioPanel 设置")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        bar.mousePressEvent = self._title_press
        bar.mouseMoveEvent = self._title_move
        return bar

    # ─── 页面 ─────────────────────────────────────────

    def _page_general(self) -> QWidget:
        theme_cb = self._combo(["浅色", "暗色", "自动"],
                                {"light":0,"dark":1,"auto":2}.get(get_theme(),2))
        theme_cb.currentIndexChanged.connect(self._on_theme_changed)

        self._top_switch = ToggleSwitch(get_always_on_top())
        self._startup_switch = ToggleSwitch(_is_startup())

        return self._form_page("通用设置", [
            ("主题:", theme_cb),
            ("窗口置顶:", self._top_switch),
            ("开机自启:", self._startup_switch),
        ])

    def _on_theme_changed(self, idx: int):
        m = {0: "light", 1: "dark", 2: "auto"}
        self._theme_mgr.set_theme(m.get(idx, "auto"))

    def _page_panel(self) -> QWidget:
        cfg = load_config()
        mx, my = get_panel_margins()

        self._outer_fader  = FaderRow(int(cfg.get("glass_outer", 1.0) * 100))
        self._mid_fader    = FaderRow(int(cfg.get("glass_mid", 1.0) * 100))
        self._inner_fader  = FaderRow(int(cfg.get("glass_inner", 1.0) * 100))
        self._collapse_si  = SliderInput(1, 30, cfg.get("auto_collapse_ms", 5000) // 1000, " 秒")
        self._margin_x_si  = SliderInput(0, 200, mx, " px")
        self._margin_y_si  = SliderInput(0, 200, my, " px")

        all_ctls = [self._outer_fader, self._mid_fader, self._inner_fader,
                    self._collapse_si, self._margin_x_si, self._margin_y_si]
        for c in all_ctls:
            c.slider().sliderReleased.connect(self._apply)
            c.slider().valueChanged.connect(lambda v, ctrl=c: self._check_bounds(ctrl, v))

        return self._form_page("面板设置", [
            ("面板透明度:",  self._outer_fader),
            ("标题栏透明度:", self._mid_fader),
            ("卡片透明度:",   self._inner_fader),
            ("自动收起延迟:", self._collapse_si),
            ("屏幕右边距:",   self._margin_x_si),
            ("屏幕下边距:",   self._margin_y_si),
        ])

    def _page_advanced(self) -> QWidget:
        cfg = load_config()
        self._refresh_si = SliderInput(3, 30, cfg.get("refresh_interval_ms", 8000) // 1000, " 秒")
        self._sync_si    = SliderInput(5, 60, cfg.get("sync_interval_ms", 10000) // 1000, " 秒")
        for c in [self._refresh_si, self._sync_si]:
            c.slider().sliderReleased.connect(self._apply)
            c.slider().valueChanged.connect(lambda v, ctrl=c: self._check_bounds(ctrl, v))
        return self._form_page("高级设置", [
            ("设备刷新间隔:", self._refresh_si),
            ("音量同步间隔:", self._sync_si),
        ])

    def _check_bounds(self, ctrl, val: int) -> None:
        """滑块到达边界时弹出 Toast."""
        lo = ctrl.slider().minimum()
        hi = ctrl.slider().maximum()
        if val == lo:
            self._toast.show_msg(f"已达最小值: {lo}")
        elif val == hi:
            self._toast.show_msg(f"已达最大值: {hi}")

    def _page_about(self) -> QWidget:
        w = QWidget()
        w.setObjectName("pageWidget")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        title = QLabel("AudioPanel")
        title.setObjectName("aboutTitle")
        layout.addWidget(title)

        for line in [
            "Windows 多音频设备音量控制面板",
            "",
            "技术栈: Python 3 + PySide6 + pycaw",
            "音频 API: Windows CoreAudio (MME waveOut)",
            "主题: 浅色 / 暗色 / 自动跟随系统",
        ]:
            lbl = QLabel(line)
            lbl.setObjectName("aboutLine")
            layout.addWidget(lbl)
        layout.addStretch()
        return w

    # ─── 辅助 ─────────────────────────────────────────

    def _form_page(self, title: str, rows: list) -> QWidget:
        w = QWidget()
        w.setObjectName("pageWidget")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        hdr = QLabel(title)
        hdr.setObjectName("pageHeader")
        layout.addWidget(hdr)
        layout.addSpacing(8)

        for row in rows:
            card = QFrame()
            card.setObjectName("settingCard")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(10, 5, 10, 5)
            cl.setSpacing(10)
            lbl = QLabel(row[0])
            lbl.setObjectName("formLabel")
            cl.addWidget(lbl)
            cl.addWidget(row[1], 1)
            layout.addWidget(card)

        layout.addStretch()
        return w

    def _combo(self, items: list[str], idx: int) -> QComboBox:
        cb = QComboBox()
        cb.addItems(items)
        cb.setCurrentIndex(idx)
        return cb

    # ─── 导航 ─────────────────────────────────────────

    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)

    # ─── 主题 ─────────────────────────────────────────

    def _apply_theme(self):
        c = self._theme_mgr.colors
        self.setStyleSheet(self._qss(c))
        for switch in self.findChildren(ToggleSwitch):
            switch.update_theme_colors(c.accent)
        # Toast 跟随主题色
        is_dark = self._theme_mgr.effective_theme == "dark"
        self._toast.set_dark_theme(is_dark)

    def _qss(self, c: ThemeColors) -> str:
        g = c.glass_tint
        cfg = load_config()
        outer_a = cfg.get("glass_outer", 1.0)
        mid_a   = cfg.get("glass_mid", 1.0)
        inner_a = cfg.get("glass_inner", 1.0)
        return build_stylesheet(c, outer_a, mid_a, inner_a) + f"""
        QWidget#SettingsWindow {{
            background: transparent;
            border: 1px solid rgba({_rgba(c.border, 0.3)});
            border-radius: 10px;
        }}
        /* 设置标题栏 — mid_alpha */
        QWidget#SettingsWindow > QWidget#titleBar {{
            background-color: rgba({_rgba(g, mid_a)});
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border-bottom: 1px solid rgba({_rgba(c.border, 0.25)});
        }}
        /* 设置底栏 — mid_alpha */
        QWidget#SettingsWindow > QWidget#bottomBar {{
            background-color: rgba({_rgba(g, mid_a)});
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
            border-top: 1px solid rgba({_rgba(c.border, 0.25)});
        }}
        /* 左栏 — inner_alpha */
        QWidget#sideNav {{
            background-color: rgba({_rgba(g, inner_a)});
            border-right: 1px solid rgba({_rgba(c.border, 0.2)});
        }}
        /* 右栏 — outer_alpha */
        QStackedWidget#contentStack {{
            background-color: rgba({_rgba(g, outer_a)});
        }}
        QPushButton#navBtn {{
            background: transparent; border: none; border-radius: 6px;
            color: {c.text_secondary}; font-size: 12px; text-align: left;
            padding: 8px 20px; margin: 1px 8px;
        }}
        QPushButton#navBtn:hover {{ background: rgba({_rgba(c.surface_hover, 0.5)}); color: {c.text_primary}; }}
        QPushButton#navBtn:checked {{
            background: rgba({_rgba(c.accent, 0.2)});
            color: {c.text_primary}; font-weight: 600;
            border-left: 2px solid {c.accent};
        }}
        QPushButton#applyBtn {{
            background: {c.accent}; color: {c.bg}; border: none;
            border-radius: 4px; padding: 6px 18px; font-size: 12px; font-weight: 600;
        }}
        QPushButton#applyBtn:hover {{ background: {c.accent_hover}; }}
        QPushButton#actionBtn {{
            background: transparent; color: {c.text_secondary};
            border: 1px solid rgba({_rgba(c.border, 0.4)}); border-radius: 4px;
            padding: 6px 14px; font-size: 12px;
        }}
        QPushButton#actionBtn:hover {{
            background: rgba({_rgba(c.surface_hover, 0.5)}); color: {c.text_primary};
        }}
        QLabel#statusText {{
            color: {c.text_muted}; font-size: 11px;
        }}
        QWidget#pageWidget {{ background: transparent; }}
        QLabel#pageHeader {{
            color: {c.text_primary}; font-size: 15px; font-weight: 700;
            padding-bottom: 4px;
            border-bottom: 1px solid rgba({_rgba(c.border, 0.25)});
        }}
        QLabel#aboutTitle {{ color: {c.text_primary}; }}
        QComboBox {{
            background: rgba({_rgba(c.surface, 0.6)}); color: {c.text_primary};
            border: 1px solid rgba({_rgba(c.border, 0.4)}); border-radius: 4px;
            padding: 5px 8px; min-width: 100px;
        }}
        QComboBox:hover {{ border-color: rgba({_rgba(c.border, 0.6)}); }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background: rgba({_rgba(c.surface, 0.92)}); color: {c.text_primary};
            border: 1px solid rgba({_rgba(c.border, 0.35)}); border-radius: 4px;
            selection-background-color: {c.accent}; selection-color: {c.bg};
        }}
        QSpinBox {{
            background: rgba({_rgba(c.surface, 0.6)}); color: {c.text_primary};
            border: 1px solid rgba({_rgba(c.border, 0.4)}); border-radius: 4px;
            padding: 5px 6px; min-width: 80px;
        }}
        QSpinBox:hover {{ border-color: rgba({_rgba(c.border, 0.6)}); }}
        QLabel#faderLabel {{
            color: {c.text_primary}; font-size: 12px; font-weight: 500;
            background: transparent;
        }}
        QLabel#formLabel {{
            color: {c.text_primary}; font-size: 12px; font-weight: 500;
            background: transparent;
        }}
        QLabel#aboutTitle {{
            color: {c.text_primary}; font-size: 18px; font-weight: 700;
        }}
        QLabel#aboutLine {{
            color: {c.text_secondary}; font-size: 12px;
        }}
        /* Toast 通知条 — 浮动叠加, 主题反色 */
        QWidget#toastBar {{
            background: transparent;
        }}
        QLabel#toastLabel {{
            color: {c.text_primary}; font-size: 12px; font-weight: 600;
            background: transparent;
        }}
        """

    # ─── 拖拽 ─────────────────────────────────────────

    def _title_press(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _title_move(self, e: QMouseEvent):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    # ─── 保存 ─────────────────────────────────────────

    def _collect(self):
        """收集所有设置值并保存."""
        cfg = load_config()

        # 通用 (page 0)
        page0 = self._stack.widget(0)
        for w in page0.findChildren(QWidget):
            if isinstance(w, QComboBox):
                m = {0: "light", 1: "dark", 2: "auto"}
                set_theme(m.get(w.currentIndex(), "auto"))
        cfg["always_on_top"] = self._top_switch.isChecked()
        set_always_on_top(self._top_switch.isChecked())
        _set_startup(self._startup_switch.isChecked())

        # 面板 (page 1): FaderRow + SliderInput
        cfg["glass_outer"] = self._outer_fader.value() / 100.0
        cfg["glass_mid"]   = self._mid_fader.value() / 100.0
        cfg["glass_inner"] = self._inner_fader.value() / 100.0
        cfg["auto_collapse_ms"] = self._collapse_si.value() * 1000
        cfg["panel_margin_x"]   = self._margin_x_si.value()
        cfg["panel_margin_y"]   = self._margin_y_si.value()

        # 高级 (page 2): SliderInput
        cfg["refresh_interval_ms"] = self._refresh_si.value() * 1000
        cfg["sync_interval_ms"]    = self._sync_si.value() * 1000

        save_config(cfg)
        self.applied.emit()

    def _apply(self):
        """应用并保存, 同时刷新设置窗口自身样式."""
        self._collect()
        self._apply_theme()
        self._status.setText("已应用 ✓")

    def _reset_defaults(self):
        """恢复默认设置并刷新 UI."""
        reset_config()
        self._outer_fader.setValue(int(DEFAULT_CONFIG["glass_outer"] * 100))
        self._mid_fader.setValue(int(DEFAULT_CONFIG["glass_mid"] * 100))
        self._inner_fader.setValue(int(DEFAULT_CONFIG["glass_inner"] * 100))
        self._collapse_si.setValue(DEFAULT_CONFIG["auto_collapse_ms"] // 1000)
        self._margin_x_si.setValue(DEFAULT_CONFIG["panel_margin_x"])
        self._margin_y_si.setValue(DEFAULT_CONFIG["panel_margin_y"])
        self._refresh_si.setValue(DEFAULT_CONFIG["refresh_interval_ms"] // 1000)
        self._sync_si.setValue(DEFAULT_CONFIG["sync_interval_ms"] // 1000)
        self._top_switch.setChecked(DEFAULT_CONFIG["always_on_top"])
        self._startup_switch.setChecked(False)
        self._apply_theme()
        self.applied.emit()
        self._status.setText("已恢复默认 ✓")

    def closeEvent(self, event):
        global _instance
        _instance = None
        super().closeEvent(event)

    def paintEvent(self, event) -> None:
        """设置窗口手绘背景, 确保 glass_outer alpha 正确渲染."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cfg = load_config()
        outer = cfg.get("glass_outer", 1.0)
        c = self._theme_mgr.colors
        bg = QColor(c.glass_tint)
        bg.setAlphaF(max(0.0, min(1.0, outer)))
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 10, 10)
        p.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)


# ─── 工具 ────────────────────────────────────────────

def _rgba(h: str, a: float) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r}, {g}, {b}, {a}"
