"""
主面板 - Windows 11 风格音量控制面板

功能:
    - 系统托盘图标, 单击展开/折叠面板
    - 从屏幕右下角以位移动画滑入/滑出
    - 设备列表: 音量滑块 + 静音 + 隐藏
    - 置顶切换, 主题切换 (浅色/暗色/自动)
"""
from __future__ import annotations

from PySide6.QtCore import (
    Qt, Signal, QTimer, QRect, QPoint, QEasingCurve,
    QPropertyAnimation,
)
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor, QPen, QBrush
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMenu,
    QPushButton, QScrollArea, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from audio_engine import AudioEngine
from config import (
    get_hidden_devices, hide_device, unhide_device,
    get_always_on_top, set_always_on_top,
    get_theme as cfg_get_theme, set_theme as cfg_set_theme,
    get_panel_margins, load_config,
)
from theme_manager import (
    ThemeManager, THEME_AUTO,
    THEME_ORDER, THEME_ICONS,
)
from ui.device_card import DeviceCard
from ui.icon_renderer import make_tray_icon
from ui.styles import build_stylesheet


class MainPanel(QWidget):
    """音量控制面板 - 单例, 通过托盘图标控制显隐.

    信号:
        panel_expanded:   面板展开时发出
        panel_collapsed:  面板折叠时发出
    """

    panel_expanded = Signal()
    panel_collapsed = Signal()

    # ---- 布局常量 ----
    _ANIM_DURATION = 180
    _MAX_HEIGHT = 580
    _MIN_HEIGHT = 160
    _CARD_HEIGHT = 44

    def __init__(self, engine: AudioEngine, theme_mgr: ThemeManager) -> None:
        super().__init__()
        self._engine = engine
        self._theme_mgr = theme_mgr
        self._device_cards: dict[str, DeviceCard] = {}
        self._hidden_ids: list[str] = list(get_hidden_devices())
        self._show_hidden = False
        self._expanded = False
        self._anim: QPropertyAnimation | None = None
        self._target_geo: QRect | None = None

        self._setup_window()
        self._setup_ui()
        self._setup_tray()
        self._populate_devices()

        cfg = load_config()

        # 设备自动刷新
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(cfg.get("refresh_interval_ms", 3000))
        self._refresh_timer.timeout.connect(self._check_device_change)
        self._refresh_timer.start()

        # 音量同步
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(cfg.get("sync_interval_ms", 5000))
        self._sync_timer.timeout.connect(self._sync_volumes)
        self._sync_timer.start()

        # 无操作自动收起
        self._auto_collapse_timer = QTimer(self)
        self._auto_collapse_timer.setSingleShot(True)
        self._auto_collapse_timer.setInterval(cfg.get("auto_collapse_ms", 2000))
        self._auto_collapse_timer.timeout.connect(self.collapse)

        # 主题信号 — 只连一个槽, 避免双重触发
        self._theme_mgr.theme_changed.connect(self._on_theme_changed)
        self._theme_mgr.effective_theme_changed.connect(self._on_effective_theme_changed)

        # 初始主题
        saved = cfg_get_theme()
        if saved in THEME_ORDER:
            self._theme_mgr.set_theme(saved)
        else:
            self._theme_mgr.set_theme(THEME_AUTO)
        # 确保按钮图标和样式在初始化时正确 (set_theme 在同值时不发信号)
        self._update_theme_button()
        self._apply_theme()

    # ═══════════════════════════════════════════════════
    #  窗口设置
    # ═══════════════════════════════════════════════════

    def _setup_window(self) -> None:
        self.setObjectName("mainPanel")
        self.setWindowTitle("音量控制")
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if get_always_on_top():
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

        self._calc_geometry()
        # 预设位置, 避免首次 show() 时从 (0,0) 闪现到右下角
        if self._target_geo:
            self.setGeometry(self._target_geo)
        self.hide()

    # ═══ 系统主题检测 (独立于 app 主题) ═══

    @staticmethod
    def _is_system_light() -> bool:
        """读注册表判断 Windows 系统主题, 不受 app 主题影响."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return bool(value)
        except OSError:
            return True

    @classmethod
    def _system_tray_color(cls) -> str:
        """托盘图标色: 系统亮色→黑, 系统暗色→白."""
        return "#111111" if cls._is_system_light() else "#F0F0F0"

    def _calc_geometry(self) -> None:
        """计算面板位置: 屏幕右下角, 任务栏上方."""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        avail = screen.availableGeometry()
        mx, my = get_panel_margins()
        pw = load_config().get("panel_width", 380)

        x = avail.right() - pw - mx
        y = avail.bottom() - self._MAX_HEIGHT - my

        screen_geo = screen.geometry()
        x = max(screen_geo.left() + mx, x)
        y = max(screen_geo.top() + my, y)

        self._target_geo = QRect(x, y, pw, self._MAX_HEIGHT)

    def _recalc_and_apply_height(self) -> None:
        """根据设备数量重算面板高度."""
        visible_count = sum(
            1 for cid, card in self._device_cards.items()
            if cid not in self._hidden_ids
        )
        hidden_count = sum(
            1 for cid in self._hidden_ids if cid in self._device_cards
        )
        hdr_h = 36   # 标题栏
        btm_h = 34   # 底栏
        hdr2 = 28 if hidden_count > 0 else 0      # 隐藏分区头
        h2 = hidden_count * self._CARD_HEIGHT if self._show_hidden else 0

        target_h = hdr_h + visible_count * self._CARD_HEIGHT + hdr2 + h2 + btm_h + 12
        target_h = max(self._MIN_HEIGHT, min(self._MAX_HEIGHT, target_h))

        if self._target_geo:
            old_bottom = self._target_geo.bottom()
            self._target_geo.setHeight(target_h)
            self._target_geo.moveBottom(old_bottom)
            if self._expanded:
                self.setGeometry(self._target_geo)

    # ═══════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 标题栏 ──
        self._title_bar = self._create_title_bar()
        root.addWidget(self._title_bar)

        # ── 滚动内容区 ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setObjectName("contentScroll")
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # 不在此处 setStyleSheet — 全部样式由主面板 build_stylesheet 统一管理

        self._content = QWidget()
        self._content.setObjectName("contentArea")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 6, 10, 6)
        self._content_layout.setSpacing(4)

        # 可见设备区
        self._visible_layout = QVBoxLayout()
        self._visible_layout.setSpacing(4)
        self._content_layout.addLayout(self._visible_layout)

        # 隐藏设备头
        self._hidden_header = QPushButton("已隐藏的设备  ▸")
        self._hidden_header.setObjectName("hiddenHeaderBtn")
        self._hidden_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hidden_header.clicked.connect(self._toggle_hidden)
        self._hidden_header.hide()
        self._content_layout.addWidget(self._hidden_header)

        # 隐藏设备区
        self._hidden_layout = QVBoxLayout()
        self._hidden_layout.setSpacing(4)
        self._content_layout.addLayout(self._hidden_layout)

        self._content_layout.addStretch()
        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll, 1)

        # ── 底部栏 ──
        self._bottom_bar = self._create_bottom_bar()
        root.addWidget(self._bottom_bar)

    def _create_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(4)

        title = QLabel("音量控制")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        layout.addStretch()

        # 置顶按钮 (手绘线框 ↑ 图标)
        self._pin_btn = QPushButton()
        self._pin_btn.setObjectName("pinBtn")
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(get_always_on_top())
        self._pin_btn.setToolTip("取消置顶" if get_always_on_top() else "置顶")
        self._pin_btn.setFixedSize(24, 24)
        self._pin_btn.clicked.connect(self._toggle_pin)
        self._update_pin_icon()
        layout.addWidget(self._pin_btn)

        # 最小化 (收起面板)
        min_btn = QPushButton("—")
        min_btn.setObjectName("titleBtn")
        min_btn.setToolTip("收起面板")
        min_btn.clicked.connect(self.collapse)
        layout.addWidget(min_btn)

        return bar

    def _create_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("bottomBar")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self._count_label = QLabel("")
        self._count_label.setObjectName("hintLabel")
        layout.addWidget(self._count_label)
        layout.addStretch()

        # 设置按钮
        settings_btn = QPushButton("⚙︎")
        settings_btn.setObjectName("titleBtn")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip("设置")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)

        # 主题切换按钮
        self._theme_btn = QPushButton("◎")
        self._theme_btn.setObjectName("titleBtn")
        self._theme_btn.setFixedSize(28, 28)
        self._theme_btn.setToolTip("切换主题")
        self._theme_btn.clicked.connect(self._cycle_theme)
        layout.addWidget(self._theme_btn)

        return bar

    # ═══════════════════════════════════════════════════
    #  系统托盘
    # ═══════════════════════════════════════════════════

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[AudioPanel] 系统托盘不可用")
            return

        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("AudioPanel — 单击展开")

        menu = QMenu()
        show_act = QAction("显示/隐藏面板", self)
        show_act.triggered.connect(self._toggle_panel)
        menu.addAction(show_act)
        menu.addSeparator()
        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(quit_act)
        self._tray.setContextMenu(menu)

        self._tray.activated.connect(self._on_tray_activated)
        self._update_tray_icon()
        self._tray.show()

    def _update_tray_icon(self) -> None:
        if not hasattr(self, '_tray') or self._tray is None:
            return
        # 托盘图标始终跟随 Windows 系统主题, 不受 app 主题切换影响
        color = self._system_tray_color()
        try:
            icon = make_tray_icon(color)
            if icon.isNull():
                raise ValueError("icon is null")
            self._tray.setIcon(icon)
        except Exception:
            fallback = QApplication.style().standardIcon(
                QApplication.style().StandardPixmap.SP_MediaVolume
            )
            if fallback:
                self._tray.setIcon(fallback)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_panel()

    def _toggle_panel(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    # ═══════════════════════════════════════════════════
    #  展开 / 折叠动画 (位移动画: 从屏幕底部滑入/滑出)
    # ═══════════════════════════════════════════════════

    def expand(self) -> None:
        if self._expanded:
            return
        self._expanded = True

        self._calc_geometry()
        self._recalc_and_apply_height()

        if self._target_geo is None:
            return

        # 始终保持完整尺寸, 只改变 Y 位置 (从屏幕底部滑入)
        screen = QApplication.primaryScreen()
        screen_bottom = screen.geometry().bottom() if screen else self._target_geo.bottom()

        self.setGeometry(self._target_geo)  # 完整尺寸 + 正确 X
        self.move(self._target_geo.x(), screen_bottom)  # 起点: 屏幕底部

        self.show()
        self.raise_()
        self.activateWindow()

        # 动画: 从屏幕底部滑动到目标 Y
        self._anim_pos(self._target_geo.x(), self._target_geo.y())
        self._auto_collapse_timer.start()
        self.panel_expanded.emit()

    def collapse(self) -> None:
        if not self._expanded:
            return
        self._expanded = False

        if self._target_geo is None:
            self.hide()
            self.panel_collapsed.emit()
            return

        screen = QApplication.primaryScreen()
        target_y = screen.geometry().bottom() if screen else self._target_geo.bottom()

        self._anim_pos(self.x(), target_y, on_finish=self._finish_collapse)
        self.panel_collapsed.emit()

    def _finish_collapse(self) -> None:
        if not self._expanded:
            self._auto_collapse_timer.stop()
            self.hide()

    # ─── 自动收起 ─────────────────────────────────────

    def enterEvent(self, event) -> None:
        """鼠标进入面板区域, 取消自动收起."""
        self._auto_collapse_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """鼠标离开面板区域, 启动自动收起倒计时."""
        if self._expanded:
            self._auto_collapse_timer.start()
        super().leaveEvent(event)

    def _anim_pos(self, x: int, y: int, on_finish: callable | None = None) -> None:
        """动画移动面板到目标 (x, y), 不改变尺寸."""
        if self._anim and self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()

        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(self._ANIM_DURATION)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(x, y))

        if on_finish:
            self._anim.finished.connect(on_finish)

        self._anim.start()

    # ═══════════════════════════════════════════════════
    #  主题
    # ═══════════════════════════════════════════════════

    def _apply_theme(self) -> None:
        """应用当前有效主题色到样式表."""
        c = self._theme_mgr.colors
        cfg = load_config()
        self.setStyleSheet(build_stylesheet(
            c,
            cfg.get("glass_outer", 1.0),
            cfg.get("glass_mid", 1.0),
            cfg.get("glass_inner", 1.0),
        ))
        self._scroll.setStyleSheet("")
        self._scroll.viewport().setStyleSheet("")
        self._content.setStyleSheet("")
        self._update_tray_icon()
        self._update_pin_icon()
        self._update_mute_button_styles()
        self.repaint()

    def _update_theme_button(self) -> None:
        if hasattr(self, '_theme_btn'):
            self._theme_btn.setText(THEME_ICONS.get(self._theme_mgr.theme, "◎"))
            self._theme_btn.setToolTip(
                f"主题: {self._theme_mgr.get_effective_label()}"
            )

    def _update_mute_button_styles(self) -> None:
        """刷新所有设备卡片的静音按钮样式 (用主题色替代内联样式)."""
        for card in self._device_cards.values():
            card.apply_theme_style(self._theme_mgr.colors)

    def _on_theme_changed(self, _theme: str) -> None:
        """主题切换 (light/dark/auto) — 更新按钮图标."""
        self._update_theme_button()

    def _on_effective_theme_changed(self, _effective: str) -> None:
        """有效主题变化 (light/dark) — 重新应用整个样式."""
        self._apply_theme()

    def _cycle_theme(self) -> None:
        self._theme_mgr.cycle()
        cfg_set_theme(self._theme_mgr.theme)
        self._update_theme_button()

    def _open_settings(self) -> None:
        """打开设置窗口."""
        from ui.settings_window import SettingsWindow
        dlg = SettingsWindow(self._theme_mgr, self)
        dlg.applied.connect(self._on_settings_closed)
        dlg.show()

    def _on_settings_closed(self) -> None:
        """设置关闭后同步变更."""
        cfg = load_config()
        # 应用主题和透明度
        self._apply_theme()
        # 强制重建所有卡片样式和滚动区
        for card in self._device_cards.values():
            card.apply_theme_style(self._theme_mgr.colors)
            card.update()
        self._scroll.viewport().update()
        self.repaint()
        # 定时器间隔
        self._auto_collapse_timer.setInterval(cfg.get("auto_collapse_ms", 5000))
        self._refresh_timer.setInterval(cfg.get("refresh_interval_ms", 8000))
        self._sync_timer.setInterval(cfg.get("sync_interval_ms", 10000))
        # 置顶状态
        self._pin_btn.setChecked(get_always_on_top())
        self._pin_btn.setToolTip("取消置顶" if get_always_on_top() else "置顶")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, get_always_on_top())
        if self._expanded:
            self.show()

    # ═══════════════════════════════════════════════════
    #  设备管理
    # ═══════════════════════════════════════════════════

    def _populate_devices(self) -> None:
        """填充设备列表 (增量更新, 不销毁已有卡片)."""
        devices = self._engine.get_all_devices()
        current_ids = {d.device_id for d in devices}

        # 移除已经不存在的设备卡片
        stale = [cid for cid in self._device_cards if cid not in current_ids]
        for cid in stale:
            card = self._device_cards.pop(cid)
            card.setParent(None)
            card.deleteLater()

        # 添加新设备
        for dev in devices:
            if dev.device_id not in self._device_cards:
                is_hidden = dev.device_id in self._hidden_ids
                card = DeviceCard(dev, hidden=is_hidden)
                card.volume_changed.connect(self._on_volume)
                card.hide_requested.connect(self._on_hide)
                card.apply_theme_style(self._theme_mgr.colors)
                self._device_cards[dev.device_id] = card

        # 重建布局
        self._relayout_cards()

    def _relayout_cards(self) -> None:
        """将卡片放入可见/隐藏布局."""
        # 清空布局
        for lo in (self._visible_layout, self._hidden_layout):
            while lo.count():
                item = lo.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)

        visible_count = 0
        for dev_id, card in self._device_cards.items():
            is_hidden = dev_id in self._hidden_ids
            card.set_hidden_state(is_hidden)  # 同步隐藏状态 & 更新图标
            if is_hidden:
                self._hidden_layout.addWidget(card)
                card.setVisible(self._show_hidden)
            else:
                self._visible_layout.addWidget(card)
                card.setVisible(True)
                visible_count += 1

        self._update_hidden_header()
        self._update_counts()
        self._recalc_and_apply_height()

    def _update_hidden_header(self) -> None:
        cnt = sum(1 for cid in self._hidden_ids if cid in self._device_cards)
        if cnt > 0:
            arrow = "▾" if self._show_hidden else "▸"
            self._hidden_header.setText(f"已隐藏的设备 ({cnt})  {arrow}")
            self._hidden_header.show()
        else:
            self._hidden_header.hide()

    def _update_counts(self) -> None:
        total = len(self._device_cards)
        hidden = sum(1 for cid in self._hidden_ids if cid in self._device_cards)
        self._count_label.setText(f"{total - hidden}/{total} 个设备")

    # ═══════════════════════════════════════════════════
    #  交互事件
    # ═══════════════════════════════════════════════════

    def _on_volume(self, did: str, vol: float) -> None:
        dev = self._engine.get_device_by_id(did)
        if dev:
            dev.set_volume(vol)

    def _on_hide(self, did: str) -> None:
        if did in self._hidden_ids:
            self._hidden_ids.remove(did)
            unhide_device(did)
        else:
            self._hidden_ids.append(did)
            hide_device(did)
        self._relayout_cards()

    def _toggle_hidden(self) -> None:
        self._show_hidden = not self._show_hidden
        for cid, card in self._device_cards.items():
            if cid in self._hidden_ids:
                card.setVisible(self._show_hidden)
        self._update_hidden_header()
        self._recalc_and_apply_height()

    # ═══ 置顶按钮手绘线框图标 ═══

    def _make_pin_icon(self, checked: bool) -> QIcon:
        """手绘 ↑ 箭头: 未选中=线框, 选中=内部填充."""
        pix = QPixmap(14, 14)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(self._system_tray_color())
        pen = QPen(color, 1.3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        if checked:
            p.setBrush(color)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)

        # 简洁箭头: 顶点在 (7,2), 底部在 (7,12)
        from PySide6.QtGui import QPainterPath
        from PySide6.QtCore import QPointF
        cx, sz = 7, 5
        path = QPainterPath()
        path.moveTo(cx, 2)              # 顶点
        path.lineTo(cx - sz * 0.7, 7)   # 左下
        path.lineTo(cx - sz * 0.2, 7)   # 左内
        path.lineTo(cx - sz * 0.2, 12)  # 左底
        path.lineTo(cx + sz * 0.2, 12)  # 右底
        path.lineTo(cx + sz * 0.2, 7)   # 右内
        path.lineTo(cx + sz * 0.7, 7)   # 右下
        path.closeSubpath()
        p.drawPath(path)

        p.end()
        return QIcon(pix)

    def _update_pin_icon(self) -> None:
        """根据置顶状态更新按钮图标."""
        if hasattr(self, '_pin_btn'):
            self._pin_btn.setIcon(
                self._make_pin_icon(self._pin_btn.isChecked())
            )

    def _toggle_pin(self) -> None:
        new = not get_always_on_top()
        set_always_on_top(new)
        self._pin_btn.setChecked(new)
        self._pin_btn.setToolTip("取消置顶" if new else "置顶")
        self._update_pin_icon()
        # setWindowFlag 不会触发窗口重建, 避免闪烁
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, new)
        if self._expanded:
            self.show()

    # ═══════════════════════════════════════════════════
    #  自动刷新
    # ═══════════════════════════════════════════════════

    def _check_device_change(self) -> None:
        if self._engine.refresh_devices():
            self._populate_devices()

    def _sync_volumes(self) -> None:
        """同步所有卡片音量 (仅当面板可见时)."""
        if not self._expanded:
            return
        for card in self._device_cards.values():
            card.refresh_volume()

    # ═══════════════════════════════════════════════════
    #  退出
    # ═══════════════════════════════════════════════════

    def _quit(self) -> None:
        if hasattr(self, '_tray') and self._tray is not None:
            self._tray.hide()
        QApplication.quit()

    # ═══════════════════════════════════════════════════
    #  窗口事件
    # ═══════════════════════════════════════════════════

    def paintEvent(self, event) -> None:
        """手绘半透明背景 — 解决 WA_TranslucentBackground + QSS alpha 不生效问题."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cfg = load_config()
        outer = cfg.get("glass_outer", 1.0)
        c = self._theme_mgr.colors
        bg = QColor(c.glass_tint)
        bg.setAlphaF(max(0.0, min(1.0, outer)))
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 12, 12)
        p.end()

    def showEvent(self, event) -> None:
        """面板显示时确保位置正确 (不干扰展开动画)."""
        if not self._expanded:
            self._calc_geometry()
        super().showEvent(event)

