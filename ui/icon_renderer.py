# -*- coding: utf-8 -*-
"""
图标绘制工具 - QPainter 手绘矢量图标

包含:
    - 托盘喇叭图标 (16x16)
    - 隐藏图标 (圆圈内一横)
    - 显示图标 (圆圈内一竖)
    - 设备类型色标字典 (预留, 当前设备圆点已改为主题反色)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QIcon, QPixmap, QPainterPath


# ─── 托盘小喇叭图标 ─────────────────────────────────

def make_tray_icon(hex_color: str) -> QIcon:
    """绘制托盘喇叭图标, 颜色自适应主题. 使用 16x16 适配托盘标准尺寸."""
    pix = QPixmap(16, 16)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(hex_color)
    pen = QPen(c, 1.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    cx, cy, s = 8, 8, 6

    # 喇叭体 (矩形)
    body = QRectF(cx - s * 0.7, cy - s * 0.35, s * 0.45, s * 0.7)
    p.drawRoundedRect(body, 1.0, 1.0)

    # 喇叭口 (梯形)
    path = QPainterPath()
    path.moveTo(cx - s * 0.25, cy - s * 0.45)
    path.lineTo(cx + s * 0.3, cy - s * 0.7)
    path.lineTo(cx + s * 0.3, cy + s * 0.7)
    path.lineTo(cx - s * 0.25, cy + s * 0.45)
    path.closeSubpath()
    p.drawPath(path)

    # 声波弧
    p.drawArc(
        QRectF(cx + s * 0.15, cy - s * 0.38, s * 0.5, s * 0.76),
        -60 * 16, 120 * 16,
    )

    p.end()
    return QIcon(pix)


# ─── 隐藏/显示 线框图标 ─────────────────────────────

def make_hide_icon(hex_color: str) -> QIcon:
    """绘制隐藏图标: 圆圈内一横 (⊖)."""
    pix = QPixmap(14, 14)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(hex_color)
    pen = QPen(c, 1.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    # 圆圈
    p.drawEllipse(QRectF(1.5, 1.5, 11, 11))
    # 横线
    p.drawLine(4, 7, 10, 7)

    p.end()
    return QIcon(pix)


def make_show_icon(hex_color: str) -> QIcon:
    """绘制显示图标: 圆圈内一竖 (⊘ 无斜线)."""
    pix = QPixmap(14, 14)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(hex_color)
    pen = QPen(c, 1.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    # 圆圈
    p.drawEllipse(QRectF(1.5, 1.5, 11, 11))
    # 竖线
    p.drawLine(7, 4, 7, 10)

    p.end()
    return QIcon(pix)