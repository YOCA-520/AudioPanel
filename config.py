# -*- coding: utf-8 -*-
"""
配置管理模块 - 持久化用户偏好设置

存储位置:
    C:\\Users\\<用户名>\\.audiopanel\\config.json

设计原则:
    - DEFAULT_CONFIG 声明所有默认值, 新增字段自动合并
    - 内存缓存避免每次读写磁盘
    - 每个配置项提供独立的 get/set 函数
    - 扩展: 在 DEFAULT_CONFIG 加键即可, 无需迁移旧文件
"""
from __future__ import annotations

import json
import os
from typing import Any

# ============================================================
# 文件路径
# ============================================================

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".audiopanel")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# ============================================================
# 默认配置 (扩展: 直接在此字典添加新字段)
# ============================================================

DEFAULT_CONFIG: dict[str, Any] = {
    "theme": "light",
    "hidden_devices": [],
    "always_on_top": True,
    "panel_margin_x": 12,
    "panel_margin_y": 12,
    "panel_width": 380,
    "panel_height": 0,
    # 三层透明度 (0.0=全透, 1.0=不透明)
    "glass_outer": 0.5,          # 面板内容区 / 设置右栏
    "glass_mid": 1.0,            # 标题栏+底栏
    "glass_inner": 0.5,          # 设备卡片 / 设置左栏+选项框
    "auto_collapse_ms": 2000,
    "refresh_interval_ms": 3000,
    "sync_interval_ms": 5000,
}

# ============================================================
# 内存缓存
# ============================================================

_config_cache: dict[str, Any] | None = None


def _ensure_config_dir() -> None:
    """确保配置目录存在."""
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _load_config_uncached() -> dict[str, Any]:
    """从磁盘加载配置并合并默认值."""
    _ensure_config_dir()
    if not os.path.exists(CONFIG_FILE):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {}
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def load_config() -> dict[str, Any]:
    """加载配置 (带内存缓存)."""
    global _config_cache
    if _config_cache is None:
        _config_cache = _load_config_uncached()
    return _config_cache


def save_config(config: dict[str, Any]) -> None:
    """保存配置并刷新缓存."""
    global _config_cache
    _ensure_config_dir()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
    _config_cache = dict(config)


def invalidate_cache() -> None:
    """清除缓存 (供外部进程修改配置后刷新)."""
    global _config_cache
    _config_cache = None


# ============================================================
# 内部读写
# ============================================================

def _get(key: str) -> Any:
    return load_config().get(key, DEFAULT_CONFIG.get(key))


def _set(key: str, value: Any) -> None:
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


# ============================================================
# 公共 API
# ============================================================

def get_theme() -> str:
    """获取当前主题设置."""
    return _get("theme")


def set_theme(theme: str) -> None:
    """保存主题设置."""
    _set("theme", theme)


def get_hidden_devices() -> list[str]:
    """获取已隐藏设备 ID 列表."""
    return _get("hidden_devices")


def hide_device(device_id: str) -> None:
    """将设备加入隐藏列表."""
    ids = get_hidden_devices()
    if device_id not in ids:
        ids.append(device_id)
        _set("hidden_devices", ids)


def unhide_device(device_id: str) -> None:
    """将设备从隐藏列表移除."""
    ids = get_hidden_devices()
    if device_id in ids:
        ids.remove(device_id)
        _set("hidden_devices", ids)


def get_always_on_top() -> bool:
    """获取窗口是否置顶."""
    return _get("always_on_top")


def set_always_on_top(value: bool) -> None:
    """保存窗口置顶状态."""
    _set("always_on_top", value)


def get_panel_margins() -> tuple[int, int]:
    """获取面板屏幕边距 (x, y)."""
    cfg = load_config()
    return cfg.get("panel_margin_x", 12), cfg.get("panel_margin_y", 12)


def get_panel_size() -> tuple[int, int]:
    """获取面板尺寸 (width, height)."""
    cfg = load_config()
    return cfg.get("panel_width", 380), cfg.get("panel_height", 0)


def reset_config() -> None:
    """恢复所有设置为默认值 (不透明, 模糊关闭)."""
    global _config_cache
    _config_cache = dict(DEFAULT_CONFIG)
    save_config(dict(DEFAULT_CONFIG))
