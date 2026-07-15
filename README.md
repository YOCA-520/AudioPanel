# 🎛️ AudioPanel

> Windows 多音频设备音量控制面板 — 系统托盘常驻，独立调节每个输出设备的音量。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey.svg)]()

---

## ✨ 功能

- 🔊 **多设备独立音量** — 枚举所有活跃音频输出设备，每个设备独立推子 0-100%
- 🔇 **一键静音** — M 按钮静音/恢复，静音时变红
- 🙈 **隐藏设备** — 不常用的设备折叠到"已隐藏的设备"分区
- 🔌 **热插拔检测** — 设备插拔自动刷新列表
- 🔔 **音量提示音** — 拖动滑块松手时在当前设备播放反馈音
- 📌 **窗口置顶** — 面板始终浮在其他窗口之上
- 🌓 **主题切换** — 浅色 / 暗色 / 自动跟随 Windows 系统主题
- 🪟 **三层透明度** — 面板 / 标题栏 / 设备卡片各自独立调节
- 📋 **系统托盘** — 单击托盘图标展开面板，右键菜单退出
- ⚙️ **设置面板** — 无边框玻璃风格，透明度、边距、刷新间隔皆可调

---

## 🚀 快速开始

### 环境要求

- Windows 10 / 11
- Python 3.9+

### 安装与运行

```powershell
# 1. 克隆仓库
git clone https://github.com/YOCA-520/AudioPanel.git
cd AudioPanel

# 2. 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动
python main.py
```

### 打包为 EXE

```powershell
pip install pyinstaller
pyinstaller AudioPanel.spec --distpath .\dist --workpath .\build
```

---

## 📁 项目结构

```
├── main.py              # 入口，单实例锁
├── audio_engine.py      # 音频引擎（CoreAudio via pycaw）
├── config.py            # 配置持久化（~/.audiopanel/config.json）
├── theme_manager.py     # 主题系统（浅色/暗色/自动）
├── sound_notify.py      # 音量反馈音（MME waveOut 5层冗余）
├── requirements.txt     # Python 依赖
├── AudioPanel.spec      # PyInstaller 打包配置
├── assets/
│   └── notify.wav       # 提示音文件
└── ui/
    ├── main_panel.py    # 主面板（托盘、展开动画、自动收起）
    ├── device_card.py   # 设备卡片（推子、静音、隐藏）
    ├── icon_renderer.py # 手绘矢量图标
    ├── styles.py        # QSS 样式表
    └── settings_window.py # 设置窗口
```

---

## 🎮 操作指南

| 操作 | 方式 |
|------|------|
| 展开面板 | 单击托盘喇叭图标 |
| 收起面板 | 点击 `—` 或鼠标移出面板 |
| 调节音量 | 拖动推子滑块 |
| 静音/恢复 | 点击 `M` 按钮 |
| 隐藏设备 | 点击 `⊖` 按钮 |
| 置顶切换 | 点击标题栏 `↑` 按钮 |
| 切换主题 | 点击底部 `◎` 按钮 |
| 打开设置 | 点击底部 `⚙` 按钮 |
| 退出程序 | 右键托盘 → 退出 |

---

## ⚙️ 配置

配置文件位于 `%USERPROFILE%\.audiopanel\config.json`：

```json
{
  "theme": "auto",
  "always_on_top": false,
  "panel_margin_x": 12,
  "panel_margin_y": 12,
  "glass_outer": 1.0,
  "glass_mid": 1.0,
  "glass_inner": 1.0,
  "auto_collapse_ms": 5000,
  "refresh_interval_ms": 8000,
  "sync_interval_ms": 10000
}
```

新增字段会自动合并默认值，无需手动迁移。

---

## 🛠️ 技术栈

- [PySide6](https://pypi.org/project/PySide6/) — Qt6 Python 绑定
- [pycaw](https://github.com/AndreMiras/pycaw) — Windows CoreAudio API
- [comtypes](https://pypi.org/project/comtypes/) — COM 类型系统
- Windows MME waveOut（ctypes）— 低延迟音频反馈
- Windows Registry — 系统主题检测

---
