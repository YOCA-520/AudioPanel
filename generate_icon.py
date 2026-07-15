# -*- coding: utf-8 -*-
"""生成应用图标 — 现代化音量喇叭图标，多尺寸 .ico 文件。"""
from __future__ import annotations

import struct
import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("请先安装: pip install Pillow")
    raise SystemExit(1)


def draw_speaker(draw: ImageDraw.ImageDraw, size: int, color: tuple, bg: tuple):
    """在正方形画布上绘制喇叭图标。"""
    m = size * 0.08  # 边距
    cx, cy = size / 2, size / 2
    s = size * 0.32  # 喇叭半径

    # 喇叭主体 (矩形 + 梯形)
    body_l = cx - s * 0.55
    body_r = body_l + s * 0.42
    body_t = cy - s * 0.28
    body_b = cy + s * 0.28

    # 喇叭锥形口
    cone_points = [
        (cx + s * 0.28, cy - s * 0.55),
        (cx + s * 0.70, cy - s * 0.85),
        (cx + s * 0.70, cy + s * 0.85),
        (cx + s * 0.28, cy + s * 0.55),
    ]

    # 绘制
    w = max(1, int(size * 0.12))
    # 主体矩形
    draw.rounded_rectangle(
        [body_l, body_t, body_r, body_b],
        radius=max(1, int(s * 0.1)),
        fill=color, outline=None,
    )
    # 锥形口
    draw.polygon(cone_points, fill=color)

    # 声波弧线
    arc_l = cx + s * 0.45
    arc_t = cy - s * 0.50
    arc_r = cx + s * 0.65
    arc_b = cy + s * 0.50
    draw.arc(
        [arc_l, arc_t, arc_r, arc_b],
        start=290, end=70, fill=color, width=w,
    )


def make_ico(output_path: str):
    """生成多分辨率 .ico 文件。"""
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []

    # 配色：深色背景 + 白色图标，现代简洁
    BG = (30, 30, 30)       # 深灰背景
    FG = (240, 240, 240)    # 浅白图标

    for s in sizes:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 圆角方形背景
        r = max(1, int(s * 0.2))
        draw.rounded_rectangle(
            [0, 0, s - 1, s - 1],
            radius=r, fill=BG,
        )
        draw_speaker(draw, s, FG, BG)

        images.append(img)

    # 保存为 .ico（包含所有尺寸）
    images[0].save(
        output_path, format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"图标已生成: {output_path} ({len(sizes)} 个尺寸)")


if __name__ == "__main__":
    make_ico(str(Path(__file__).parent / "assets" / "app.ico"))
