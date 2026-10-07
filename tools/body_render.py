"""Рендереры анатомической схемы: SVG для приложения и PNG для проверки.

PNG-рендер нужен, чтобы можно было убедиться в правильности геометрии без
запуска браузера: он рисует те же самые примитивы через Pillow.
"""

from __future__ import annotations

from pathlib import Path

from body_geometry import (
    BASE_SHAPES,
    ORGAN_LABELS,
    ORGAN_ORDER,
    ORGAN_SHAPES,
    VIEWBOX_H,
    VIEWBOX_W,
    Ellipse,
    PathShape,
    Shape,
    StrokeShape,
)

# ---------------------------------------------------------------------------
# Разбор SVG-path
# ---------------------------------------------------------------------------
_ARITY = {"M": 2, "L": 2, "C": 6, "Q": 4, "Z": 0}


def _cubic(p0, p1, p2, p3, steps: int = 26):
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        out.append((x, y))
    return out


def _quad(p0, p1, p2, steps: int = 20):
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        out.append((mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0],
                    mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1]))
    return out


def flatten_path(d: str) -> list[tuple[float, float]]:
    """Разложить path в ломаную (только абсолютные M, L, C, Q, Z)."""
    tokens = d.replace(",", " ").split()
    pts: list[tuple[float, float]] = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    i = 0
    while i < len(tokens):
        cmd = tokens[i].upper()
        if cmd not in _ARITY:
            raise ValueError(f"Неподдерживаемая команда path: {tokens[i]!r}")
        i += 1
        n = _ARITY[cmd]
        if cmd == "Z":
            if start != cur:
                pts.append(start)
                cur = start
            continue
        nums = [float(t) for t in tokens[i : i + n]]
        i += n
        if cmd == "M":
            cur = (nums[0], nums[1])
            start = cur
            pts.append(cur)
        elif cmd == "L":
            cur = (nums[0], nums[1])
            pts.append(cur)
        elif cmd == "C":
            p1, p2, p3 = (nums[0], nums[1]), (nums[2], nums[3]), (nums[4], nums[5])
            pts.extend(_cubic(cur, p1, p2, p3))
            cur = p3
        elif cmd == "Q":
            p1, p2 = (nums[0], nums[1]), (nums[2], nums[3])
            pts.extend(_quad(cur, p1, p2))
            cur = p2
    return pts


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------
def _svg_attrs(shape: Shape, shape_class: str, color: str | None) -> str:
    fill = "none" if shape.fill is None else (color if shape.fill != "organ-detail" else color)
    parts = [f'class="{shape_class}"']
    if shape.fill is None:
        parts.append('fill="none"')
    parts.append(f'fill="{fill}"' if shape.fill is not None else 'fill="none"')
    if shape.stroke:
        parts.append(f'stroke="{shape.stroke}" stroke-width="{shape.stroke_width:g}"')
        parts.append('stroke-linejoin="round" stroke-linecap="round"')
    return " ".join(parts)


def _shape_to_svg(shape: Shape, shape_class: str) -> str:
    if isinstance(shape, Ellipse):
        style = []
        style.append(f'fill="{shape.fill or "none"}"')
        if shape.stroke:
            style.append(f'stroke="{shape.stroke}" stroke-width="{shape.stroke_width:g}"')
        return (
            f'<ellipse class="{shape_class}" cx="{shape.cx:g}" cy="{shape.cy:g}" '
            f'rx="{shape.rx:g}" ry="{shape.ry:g}" {" ".join(style)}/>'
        )
    if isinstance(shape, PathShape):
        style = [f'fill="{shape.fill or "none"}"']
        if shape.stroke:
            style.append(
                f'stroke="{shape.stroke}" stroke-width="{shape.stroke_width:g}" '
                'stroke-linejoin="round" stroke-linecap="round"'
            )
        return f'<path class="{shape_class}" d="{shape.d}" {" ".join(style)}/>'
    # StrokeShape
    d = "M " + " L ".join(f"{x:g},{y:g}" for x, y in shape.points)
    return (
        f'<path class="{shape_class}" d="{d}" fill="none" stroke="{shape.stroke}" '
        f'stroke-width="{shape.width:g}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def build_svg(*, interactive: bool = True, title: str = "Анатомическая схема восстановления") -> str:
    """Собрать SVG. Цвета органов задаются через CSS-переменные --c-<organ>."""
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEWBOX_W:g} {VIEWBOX_H:g}" '
        f'class="body-map" role="group" aria-label="{title}" preserveAspectRatio="xMidYMid meet">'
    )
    parts.append(
        "<defs>"
        '<linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#8FD3E8" stop-opacity="0"/>'
        '<stop offset="55%" stop-color="#8FD3E8" stop-opacity="0.35"/>'
        '<stop offset="100%" stop-color="#8FD3E8" stop-opacity="0"/>'
        "</linearGradient>"
        '<radialGradient id="organGlow" cx="50%" cy="50%" r="50%">'
        '<stop offset="60%" stop-color="#ffffff" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#ffffff" stop-opacity="0.55"/>'
        "</radialGradient>"
        "</defs>"
    )

    # Силуэт
    parts.append('<g class="body-base" aria-hidden="true">')
    for shape in BASE_SHAPES:
        parts.append(_shape_to_svg(shape, "body-shape"))
    parts.append("</g>")

    # Органы
    parts.append('<g class="body-organs">')
    for key in ORGAN_ORDER:
        label = ORGAN_LABELS.get(key, key)
        attrs = (
            f'class="organ" data-organ="{key}"'
            if interactive
            else f'class="organ organ-static" data-organ="{key}"'
        )
        if interactive:
            attrs += ' role="button" tabindex="0"'
        attrs += f' aria-label="{label}"'
        parts.append(f"<g {attrs}>")
        parts.append(f"<title>{label}</title>")
        for shape in ORGAN_SHAPES[key]:
            parts.append(_shape_to_svg(shape, "organ-shape"))
        parts.append("</g>")
    parts.append("</g>")

    # Анимация сканирования
    parts.append(
        '<g class="scan-overlay" aria-hidden="true" pointer-events="none">'
        f'<rect class="scan-bar" x="-20" y="-60" width="{VIEWBOX_W + 40:g}" height="60" '
        'fill="url(#scanGrad)"/>'
        "</g>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# PNG (превью)
# ---------------------------------------------------------------------------
DEFAULT_PREVIEW_COLORS = {
    "brain": "#B9A7D6",
    "lungs": "#93C9A8",
    "heart": "#D98E8E",
    "vessels": "#E0A2A2",
    "blood": "#C97F7F",
    "mouth": "#E8C48F",
}

SKIN = "#EFE6E0"
ORGAN_DETAIL = "#FFFFFF"


def render_png(
    path: str | Path,
    *,
    colors: dict[str, str] | None = None,
    scale: int = 3,
    background: str = "#FBFDFE",
    labels: bool = True,
) -> Path:
    """Отрисовать схему в PNG для визуальной проверки."""
    from PIL import Image, ImageDraw, ImageFont

    colors = {**DEFAULT_PREVIEW_COLORS, **(colors or {})}
    PAD_RIGHT = 150.0
    W, H = int((VIEWBOX_W + PAD_RIGHT) * scale), int(VIEWBOX_H * scale)
    img = Image.new("RGB", (W, H), background)
    draw = ImageDraw.Draw(img, "RGBA")

    def s(v: float) -> float:
        return v * scale

    def resolve(name: str) -> str:
        if name in ("skin", "organ"):
            return SKIN if name == "skin" else "#CCCCCC"
        if name == "organ-detail":
            return ORGAN_DETAIL
        return name

    def draw_shape(shape: Shape, body_key: str | None) -> None:
        if isinstance(shape, Ellipse):
            box = [s(shape.cx - shape.rx), s(shape.cy - shape.ry), s(shape.cx + shape.rx), s(shape.cy + shape.ry)]
            draw.ellipse(box, fill=resolve(shape.fill) if shape.fill else None,
                         outline=resolve(shape.stroke) if shape.stroke else None,
                         width=max(1, int(s(shape.stroke_width))))
        elif isinstance(shape, PathShape):
            pts = [(s(x), s(y)) for x, y in flatten_path(shape.d)]
            draw.polygon(pts, fill=resolve(shape.fill) if shape.fill else None)
            if shape.stroke:
                draw.line(pts + [pts[0]], fill=resolve(shape.stroke),
                          width=max(1, int(s(shape.stroke_width))), joint="curve")
        else:  # StrokeShape
            pts = [(s(x), s(y)) for x, y in shape.points]
            w = max(1, int(s(shape.width)))
            draw.line(pts, fill=resolve(shape.stroke), width=w, joint="curve")
            r = w / 2
            for (px, py) in (pts[0], pts[-1]):
                draw.ellipse([px - r, py - r, px + r, py + r], fill=resolve(shape.stroke))

    for shape in BASE_SHAPES:
        draw_shape(shape, None)

    for key in ORGAN_ORDER:
        color = colors.get(key, "#CCCCCC")
        for shape in ORGAN_SHAPES[key]:
            if isinstance(shape, StrokeShape):
                pts = [(s(x), s(y)) for x, y in shape.points]
                w = max(1, int(s(shape.width)))
                draw.line(pts, fill=color, width=w, joint="curve")
                r = w / 2
                for (px, py) in (pts[0], pts[-1]):
                    draw.ellipse([px - r, py - r, px + r, py + r], fill=color)
            elif isinstance(shape, PathShape):
                pts = [(s(x), s(y)) for x, y in flatten_path(shape.d)]
                draw.polygon(pts, fill=color)
                draw.line(pts + [pts[0]], fill=resolve(shape.stroke or "skin"),
                          width=max(1, int(s(shape.stroke_width))), joint="curve")
            else:
                box = [s(shape.cx - shape.rx), s(shape.cy - shape.ry), s(shape.cx + shape.rx), s(shape.cy + shape.ry)]
                draw.ellipse(box, fill=color)

    if labels:
        try:
            font = ImageFont.truetype("segoeui.ttf", int(11 * scale))
        except OSError:
            font = ImageFont.load_default()
        anchors = {
            "brain": (232, 42),
            "lungs": (250, 150),
            "heart": (232, 208),
            "vessels": (250, 300),
            "blood": (250, 400),
            "mouth": (232, 92),
        }
        for key, (ax, ay) in anchors.items():
            draw.line([(ax - 12 * scale, ay * scale + 5 * scale), (ax * scale, ay * scale + 5 * scale)],
                      fill="#8A9BA8", width=max(1, scale))
            draw.text((ax * scale, ay * scale), ORGAN_LABELS[key], fill="#3C4A54", font=font)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img = img.resize((int(VIEWBOX_W + PAD_RIGHT), int(VIEWBOX_H)), Image.LANCZOS)
    img.save(out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "body_preview.png"
    print(render_png(target))
