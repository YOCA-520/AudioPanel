# -*- coding: utf-8 -*-
"""
音频引擎模块 - 封装 Windows CoreAudio API (通过 pycaw)

功能:
    - 枚举活跃的音频输出设备
    - 读取/设置音量和静音状态
    - 检测设备热插拔

性能:
    仅使用 EnumAudioEndpoints (非 GetAllDevices), 轻量快速
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from pycaw.pycaw import (
    AudioUtilities,
    IAudioEndpointVolume,
    IMMDevice,
    EDataFlow,
    DEVICE_STATE,
)


class AudioDevice:
    """单个音频输出设备的封装.

    属性:
        device_id:      设备唯一标识符
        friendly_name:  设备友好名称 (如 "扬声器 (Realtek)")
        device_type:    设备类型 (speaker/headphone/hdmi/usb/bluetooth/digital)
    """

    def __init__(self, mm_device: IMMDevice, friendly_name: str = "") -> None:
        self._mm_device = mm_device
        self._endpoint_volume: Optional[IAudioEndpointVolume] = None
        self._id: str = mm_device.GetId()
        self._friendly_name: str = friendly_name or self._extract_name()
        self._device_type: str = self._guess_device_type()

    # ============================================================
    # 设备名称提取
    # ============================================================

    def _extract_name(self) -> str:
        """从 Windows 属性存储读取 PKEY_Device_FriendlyName.

        优先使用 pycaw 内置 PROPERTYKEY (传值调用).
        失败时回退到从设备 ID 解析.
        """
        try:
            from pycaw.pycaw import PROPERTYKEY
            from comtypes import GUID

            key = PROPERTYKEY()
            key.fmtid = GUID("{a45c254e-df1c-4efd-8020-67d146a850e0}")
            key.pid = 14  # PKEY_Device_FriendlyName

            prop_store = self._mm_device.OpenPropertyStore(0)
            pv = prop_store.GetValue(key)  # COM 接口要求传值, 非指针
            name = str(pv.GetValue())
            if name and name.strip():
                return name.strip()
        except Exception:
            pass

        # ---- 回退: 从设备 ID 提取可读片段 ----
        did = self._id
        for sep in ("#", "\\"):
            if sep in did:
                parts = did.split(sep)
                for p in parts:
                    p = p.strip()
                    if p and "{" not in p and len(p) > 3:
                        return p

        brace = did.find("{")
        if brace > 0:
            return did[:brace].rstrip(".#_\\ ")
        return did.rsplit(".", 1)[0] if "." in did else did

    def _guess_device_type(self) -> str:
        """根据设备名称关键词推断设备类型."""
        name = self._friendly_name.lower()
        if "headphone" in name or "headset" in name or "\u8033\u673a" in name:
            return "headphone"
        if "hdmi" in name or "display" in name or "monitor" in name:
            return "hdmi"
        if "usb" in name:
            return "usb"
        if "bluetooth" in name or "\u84dd\u7259" in name:
            return "bluetooth"
        if "speaker" in name or "\u626c\u58f0\u5668" in name or "realtek" in name:
            return "speaker"
        if "spdif" in name or "digital" in name or "\u5149\u7ea4" in name:
            return "digital"
        return "speaker"

    # ============================================================
    # 属性
    # ============================================================

    @property
    def device_id(self) -> str:
        return self._id

    @property
    def friendly_name(self) -> str:
        return self._friendly_name

    @property
    def device_type(self) -> str:
        return self._device_type

    @property
    def raw_ptr(self) -> int:
        """IMMDevice 原生指针, 供 WASAPI 直推."""
        import ctypes
        return ctypes.cast(self._mm_device, ctypes.c_void_p).value or 0

    @property
    def endpoint_volume(self) -> Optional[IAudioEndpointVolume]:
        """延迟激活 IAudioEndpointVolume 接口."""
        if self._endpoint_volume is None:
            try:
                interface = self._mm_device.Activate(
                    IAudioEndpointVolume._iid_, 0, None,
                )
                self._endpoint_volume = interface.QueryInterface(IAudioEndpointVolume)
            except Exception:
                return None
        return self._endpoint_volume

    # ============================================================
    # 音量控制
    # ============================================================

    def get_volume(self) -> float:
        """读取当前音量 (0.0 ~ 1.0), 失败返回 -1."""
        ev = self.endpoint_volume
        if ev is None:
            return -1.0
        try:
            return ev.GetMasterVolumeLevelScalar()
        except Exception:
            return -1.0

    def set_volume(self, level: float) -> bool:
        """设置音量.

        自动取消系统静音: 当用户在面板中拖动滑块时,
        如果设备在 Windows 系统设置中被静音, 会自动解除.
        """
        ev = self.endpoint_volume
        if ev is None:
            return False
        try:
            if level > 0.001 and ev.GetMute():
                ev.SetMute(False, None)
            ev.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level)), None)
            return True
        except Exception:
            return False

    def get_mute(self) -> bool:
        """读取静音状态."""
        ev = self.endpoint_volume
        if ev is None:
            return False
        try:
            return ev.GetMute()
        except Exception:
            return False

    def set_mute(self, mute: bool) -> bool:
        """设置静音状态."""
        ev = self.endpoint_volume
        if ev is None:
            return False
        try:
            ev.SetMute(mute, None)
            return True
        except Exception:
            return False

    def is_default(self) -> bool:
        """判断是否为系统默认播放设备."""
        try:
            default = AudioUtilities.GetSpeakers()
            if default:
                return self._id == default.GetId()
        except Exception:
            pass
        return False

    def __repr__(self) -> str:
        return f"AudioDevice({self._friendly_name!r})"


# ============================================================
# 音频引擎
# ============================================================

class AudioEngine:
    """音频引擎: 设备管理 + 音量控制.

    用法:
        engine = AudioEngine()
        devices = engine.get_all_devices()
        dev = engine.get_device_by_id("...")
    """

    def __init__(self) -> None:
        self._devices: dict[str, AudioDevice] = {}
        self._device_ids_snapshot: list[str] = []
        self._lock = threading.Lock()
        self._on_device_change: Optional[Callable[[], None]] = None
        self.refresh_devices()

    def set_on_device_change(self, callback: Optional[Callable[[], None]]) -> None:
        """注册设备变更回调 (热插拔时触发)."""
        self._on_device_change = callback

    def refresh_devices(self) -> bool:
        """刷新活跃设备列表 (仅 EnumAudioEndpoints, 不调 GetAllDevices).

        返回:
            True  设备列表发生变化
            False 无变化
        """
        new_devices: dict[str, AudioDevice] = {}

        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            if enumerator is None:
                return False

            collection = enumerator.EnumAudioEndpoints(
                EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value
            )
            if collection is None:
                return False

            for i in range(collection.GetCount()):
                mm_device = collection.Item(i)
                if mm_device:
                    dev = AudioDevice(mm_device)
                    new_devices[dev.device_id] = dev
        except Exception:
            return False

        new_ids = sorted(new_devices.keys())
        changed = new_ids != self._device_ids_snapshot

        with self._lock:
            self._devices = new_devices
            self._device_ids_snapshot = new_ids

        if changed and self._on_device_change:
            self._on_device_change()

        return changed

    def get_all_devices(self) -> list[AudioDevice]:
        """获取所有活跃设备 (线程安全)."""
        with self._lock:
            return list(self._devices.values())

    def get_device_by_id(self, device_id: str) -> Optional[AudioDevice]:
        """根据 ID 查找设备 (线程安全)."""
        with self._lock:
            return self._devices.get(device_id)

