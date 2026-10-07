"""Сгенерировать иконки PWA (192, 512, maskable) без внешних ассетов.

Запуск: python tools/make_icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "static" / "icons"


def rounded_gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (size, size), top)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color)
    return img


def draw_lungs(draw: ImageDraw.ImageDraw, size: int, color=(255, 255, 255)) -> None:
    """Стилизованные лёгкие — тот же силуэт, что и на схеме тела."""
    s = size / 512.0
    mid = 256 * s
    # Трахея (соединяется с лёгкими)
    draw.rounded_rectangle([mid - 14 * s, 96 * s, mid + 14 * s, 214 * s], radius=14 * s, fill=color)
    # Правое и левое лёгкое
    for sign in (-1, 1):
        left = mid + sign * 20 * s
        right = mid + sign * 172 * s
        box = [min(left, right), 172 * s, max(left, right), 412 * s]
        draw.rounded_rectangle(box, radius=68 * s, fill=color)


def make_icon(size: int, *, maskable: bool = False) -> Image.Image:
    pad = int(size * 0.14) if maskable else 0
    base = rounded_gradient(size, (111, 174, 144), (116, 169, 201))
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    inner = size - 2 * pad
    if inner > 0:
        tmp = Image.new("RGBA", (inner, inner), (0, 0, 0, 0))
        draw_lungs(ImageDraw.Draw(tmp), inner)
        bbox = tmp.getbbox()
        if bbox:
            tmp = tmp.crop(bbox)
            target_h = int(inner * 0.52)
            ratio = target_h / max(1, tmp.height)
            tmp = tmp.resize((max(1, int(tmp.width * ratio)), target_h), Image.LANCZOS)
            layer.alpha_composite(tmp, (pad + (inner - tmp.width) // 2, pad + (inner - tmp.height) // 2))

    base = base.convert("RGBA")
    base.alpha_composite(layer)

    if not maskable:
        # Скруглённый квадрат
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(base, (0, 0), mask)
        return out
    return base


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        make_icon(size).save(OUT / f"icon-{size}.png")
        print(f"icon-{size}.png")
    make_icon(512, maskable=True).save(OUT / "icon-maskable-512.png")
    print("icon-maskable-512.png")

    # Мелкая иконка-фавикон
    make_icon(64).save(OUT / "icon-64.png")
    print("icon-64.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
