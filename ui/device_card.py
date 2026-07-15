# -*- coding: utf-8 -*-
"""
设备卡片组件 - 单个音频设备的控制行

布局:
    [ 圆点(8px) ] [ 设备名称(stretch) ] [ 滑块(90px) ] [ 百分比(26px) ] [ M(静音) ] [ 隐藏 ]

交互:
    - 拖动滑块: 调节音量, 音量>0 时自动取消 Windows 系统静音
    - 点击 M:   音量>0 拉到 0; 音量=0 恢复到上次音量; 音量=0 时 M 变红
    - 点击隐藏:  将设备移入/移出"已隐藏的设备"分区
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget,
)

from audio_engine import AudioDevice
from theme_manager import ThemeColors
from ui.icon_renderer import make_hide_icon, make_show_icon
from sound_notify import play_beep


class DeviceCard(QFrame):
    """单个音频设备卡片."""

    volume_changed = Signal(str, float)
    hide_requested = Signal(str)

    def __init__(
        self, device: AudioDevice, hidden: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._device = device
        self._hidden = hidden
        self._updating = False
        self._last_volume: float = 0.5  # M 恢复时的默认音量

        self.setObjectName("deviceCard")
        self.setFixedHeight(44)
        self._build_ui()
        self.refresh_volume()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # ── 设备类型色标圆点 (随主题反色) ──
        self._dot = QLabel("")
        self._dot.setObjectName("deviceDot")
        self._dot.setFixedSize(8, 8)
        layout.addWidget(self._dot)

        # ── 设备名称 ──
        name = self._device.friendly_name
        if not name or not name.strip():
            name = self._device.device_id.split("{")[0].rstrip(".#_ ") or "(未知设备)"
        if len(name) > 24:
            name = name[:22] + "…"
        self._name_label = QLabel(name)
        self._name_label.setObjectName("deviceName")
        layout.addWidget(self._name_label, 1)

        # ── 滑块 ──
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setFixedWidth(90)
        self._slider.valueChanged.connect(self._on_slider)
        self._slider.sliderReleased.connect(self._on_slider_release)
        layout.addWidget(self._slider)

        # ── 音量数字 ──
        self._vol_label = QLabel("0%")
        self._vol_label.setObjectName("volumeLabel")
        self._vol_label.setFixedWidth(26)
        self._vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._vol_label)

        # ── 静音 M ──
        self._mute_btn = QPushButton("M")
        self._mute_btn.setObjectName("muteBtn")
        self._mute_btn.setToolTip("静音")
        self._mute_btn.clicked.connect(self._on_mute)
        self._mute_btn.setProperty("muted", False)
        layout.addWidget(self._mute_btn)

        # ── 隐藏 (线框图标: ⊖ 隐藏 / 竖线 显示) ──
        self._hide_btn = QPushButton("")
        self._hide_btn.setObjectName("hideBtn")
        self._hide_btn.setToolTip("取消隐藏" if self._hidden else "隐藏设备")
        self._hide_btn.clicked.connect(self._on_hide)
        self._update_hide_icon()
        layout.addWidget(self._hide_btn)

    # ─── 同步 ────────────────────────────────────────

    def refresh_volume(self) -> None:
        """从硬件读取音量, 音量=0 时 M 变红."""
        self._updating = True
        vol = self._device.get_volume()
        if vol >= 0:
            val = int(vol * 100)
            self._slider.setValue(val)
            self._vol_label.setText(f"{val}%")
        else:
            self._vol_label.setText("--")
        # 音量=0 时 M 变红; 音量>0 时恢复
        is_zero = vol <= 0.001 if vol >= 0 else False
        self._mute_btn.setProperty("muted", is_zero)
        self._mute_btn.style().unpolish(self._mute_btn)
        self._mute_btn.style().polish(self._mute_btn)
        self._updating = False

    def apply_theme_style(self, colors: ThemeColors) -> None:
        """由主面板调用, 在主题切换时刷新样式."""
        self.setStyleSheet("")
        self._name_label.setStyleSheet("")
        self._vol_label.setStyleSheet("")
        # 圆点跟随主题反色
        self._dot.setStyleSheet(
            f"QLabel {{ background-color: {colors.text_primary}; "
            f"border-radius: 4px; }}"
        )
        self._update_hide_icon()
        self._mute_btn.style().unpolish(self._mute_btn)
        self._mute_btn.style().polish(self._mute_btn)

    def _update_hide_icon(self) -> None:
        """根据隐藏状态设置线框图标."""
        from PySide6.QtGui import QColor
        # 用 muted 色, 在亮/暗主题都可见
        icon_color = "#999999"  # 灰色, 在亮暗主题都清晰
        if self._hidden:
            self._hide_btn.setIcon(make_show_icon(icon_color))
        else:
            self._hide_btn.setIcon(make_hide_icon(icon_color))

    # ─── 事件 ────────────────────────────────────────

    def _on_slider(self, value: int) -> None:
        if self._updating:
            return
        vol = value / 100.0
        self._vol_label.setText(f"{value}%")
        # 滑块>0 时取消红 M
        self._mute_btn.setProperty("muted", value == 0)
        self._mute_btn.style().unpolish(self._mute_btn)
        self._mute_btn.style().polish(self._mute_btn)
        if value > 0:
            self._last_volume = vol
        self.volume_changed.emit(self._device.device_id, vol)

    def _on_slider_release(self) -> None:
        """滑块松手时 MME 直推提示音到当前设备."""
        play_beep(self._device.friendly_name)

    def _on_mute(self) -> None:
        """M 按钮: 音量>0 时拉到 0, 音量=0 时恢复到上次音量."""
        cur_vol = self._device.get_volume()
        if cur_vol > 0.001:
            # 保存当前音量, 然后拉到 0
            self._last_volume = cur_vol
            self._slider.setValue(0)
            self._vol_label.setText("0%")
            self._mute_btn.setProperty("muted", True)
            self._mute_btn.style().unpolish(self._mute_btn)
            self._mute_btn.style().polish(self._mute_btn)
            self.volume_changed.emit(self._device.device_id, 0.0)
        else:
            # 恢复到上次音量
            restore = max(0.01, self._last_volume)
            val = int(restore * 100)
            self._slider.setValue(val)
            self._vol_label.setText(f"{val}%")
            self._mute_btn.setProperty("muted", False)
            self._mute_btn.style().unpolish(self._mute_btn)
            self._mute_btn.style().polish(self._mute_btn)
            self.volume_changed.emit(self._device.device_id, restore)

    def _on_hide(self) -> None:
        self.hide_requested.emit(self._device.device_id)

    # ─── 公共 ────────────────────────────────────────

    @property
    def device_id(self) -> str:
        return self._device.device_id

    def set_hidden_state(self, hidden: bool) -> None:
        self._hidden = hidden
        self._hide_btn.setToolTip("取消隐藏" if hidden else "隐藏设备")
        self._update_hide_icon()

