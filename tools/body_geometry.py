"""Геометрия стилизованной анатомической схемы тела.

Схема описана декларативно, чтобы из одного источника получать:
  * интерактивный SVG для приложения (tools/build_body_svg.py);
  * PNG-превью для визуальной проверки без браузера (tools/preview_body.py).

Система координат: viewBox 320 x 680, фигура анфас по центру.
"""

from __future__ import annotations

from dataclasses import dataclass

VIEWBOX_W = 320.0
VIEWBOX_H = 680.0
MID = 160.0


# ---------------------------------------------------------------------------
# Примитивы
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Ellipse:
    cx: float
    cy: float
    rx: float
    ry: float
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float = 0.0


@dataclass(frozen=True)
class PathShape:
    d: str
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float = 0.0


@dataclass(frozen=True)
class StrokeShape:
    points: tuple[tuple[float, float], ...]
    width: float
    stroke: str
    opacity: float = 1.0


Shape = Ellipse | PathShape | StrokeShape


def droplet(cx: float, cy: float, r: float) -> PathShape:
    """Капля (условное обозначение крови/капилляров)."""
    k = r
    d = (
        f"M {cx:.1f},{cy - k:.1f} "
        f"C {cx + 0.36 * k:.1f},{cy - 0.52 * k:.1f} {cx + k:.1f},{cy + 0.08 * k:.1f} {cx + k:.1f},{cy + 0.44 * k:.1f} "
        f"C {cx + k:.1f},{cy + 0.86 * k:.1f} {cx + 0.55 * k:.1f},{cy + k:.1f} {cx:.1f},{cy + k:.1f} "
        f"C {cx - 0.55 * k:.1f},{cy + k:.1f} {cx - k:.1f},{cy + 0.86 * k:.1f} {cx - k:.1f},{cy + 0.44 * k:.1f} "
        f"C {cx - k:.1f},{cy + 0.08 * k:.1f} {cx - 0.36 * k:.1f},{cy - 0.52 * k:.1f} {cx:.1f},{cy - k:.1f} Z"
    )
    return PathShape(d=d)


def mirror_x(d: str) -> str:
    """Отразить SVG-path относительно вертикальной оси x=MID.

    Поддерживаются только абсолютные команды M, L, C, Q, Z (все координаты —
    пары чисел), что покрывает всю геометрию этого файла.
    """
    tokens = d.replace(",", " ").split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        out.append(cmd)
        i += 1
        if cmd in ("Z", "z"):
            continue
        arity = {"M": 2, "L": 2, "C": 6, "Q": 4, "T": 2, "S": 4}[cmd.upper()]
        while i + arity <= len(tokens) and tokens[i] not in "MLCQTSZz":
            nums = [float(tokens[i + j]) for j in range(arity)]
            for j in range(0, arity, 2):
                nums[j] = 2 * MID - nums[j]
            out.extend(f"{n:.1f}" for n in nums)
            i += arity
    return " ".join(out)


# ---------------------------------------------------------------------------
# Базовый силуэт (не кликабельный)
# ---------------------------------------------------------------------------
BASE_SHAPES: tuple[Shape, ...] = (
    # Ноги
    StrokeShape(points=((138, 372), (134, 424), (130, 476), (128, 528), (126, 578), (126, 620)), width=36, stroke="skin"),
    StrokeShape(points=((182, 372), (186, 424), (190, 476), (192, 528), (194, 578), (194, 620)), width=36, stroke="skin"),
    # Ступни
    Ellipse(cx=124, cy=632, rx=21, ry=11, fill="skin"),
    Ellipse(cx=196, cy=632, rx=21, ry=11, fill="skin"),
    # Руки
    StrokeShape(points=((114, 148), (96, 172), (82, 210), (74, 252), (68, 300), (64, 340)), width=26, stroke="skin"),
    StrokeShape(points=((206, 148), (224, 172), (238, 210), (246, 252), (252, 300), (256, 340)), width=26, stroke="skin"),
    # Кисти
    Ellipse(cx=63, cy=350, rx=11, ry=13, fill="skin"),
    Ellipse(cx=257, cy=350, rx=11, ry=13, fill="skin"),
    # Шея
    PathShape(d="M 147,98 L 146,128 L 174,128 L 173,98 Z", fill="skin"),
    # Торс
    PathShape(
        d=(
            "M 160,116 "
            "C 138,116 116,122 104,132 "
            "C 97,140 95,155 97,172 "
            "C 101,204 110,240 112,282 "
            "C 113,312 106,336 104,356 "
            "C 103,369 107,378 114,380 "
            "L 206,380 "
            "C 213,378 217,369 216,356 "
            "C 214,336 207,312 208,282 "
            "C 210,240 219,204 223,172 "
            "C 225,155 223,140 216,132 "
            "C 204,122 182,116 160,116 Z"
        ),
        fill="skin",
    ),
    # Голова
    Ellipse(cx=MID, cy=64, rx=38, ry=47, fill="skin"),
    # Уши
    Ellipse(cx=122, cy=68, rx=6.5, ry=11, fill="skin"),
    Ellipse(cx=198, cy=68, rx=6.5, ry=11, fill="skin"),
)


# ---------------------------------------------------------------------------
# Органы (кликабельные)
# ---------------------------------------------------------------------------
_LUNG_LEFT_D = (
    "M 151,148 "
    "C 139,136 117,141 109,165 "
    "C 101,189 105,224 116,244 "
    "C 125,260 145,258 150,241 "
    "C 153,229 151,190 151,148 Z"
)
_LUNG_RIGHT_D = mirror_x(_LUNG_LEFT_D)

_HEART_D = (
    "M 160,207 "
    "C 147,196 141,187 141,178 "
    "C 141,169 146,164 153,164 "
    "C 158,164 160,168 160,172 "
    "C 160,168 162,164 167,164 "
    "C 174,164 179,169 179,178 "
    "C 179,187 173,196 160,207 Z"
)

_BRAIN_D = (
    "M 160,31 "
    "C 150,26 139,30 134,40 "
    "C 129,50 131,62 138,68 "
    "C 143,72 151,71 156,67 "
    "C 158,65 162,65 164,67 "
    "C 169,71 177,72 182,68 "
    "C 189,62 191,50 186,40 "
    "C 181,30 170,26 160,31 Z"
)
_BRAIN_GYRI: tuple[Shape, ...] = (
    StrokeShape(points=((160, 31), (160, 50), (160, 67)), width=2.2, stroke="organ-detail"),
    StrokeShape(points=((139, 42), (145, 51), (141, 63)), width=2.0, stroke="organ-detail"),
    StrokeShape(points=((150, 37), (153, 50), (149, 65)), width=2.0, stroke="organ-detail"),
    StrokeShape(points=((181, 42), (175, 51), (179, 63)), width=2.0, stroke="organ-detail"),
    StrokeShape(points=((170, 37), (167, 50), (171, 65)), width=2.0, stroke="organ-detail"),
)

ORGAN_SHAPES: dict[str, tuple[Shape, ...]] = {
    "brain": (PathShape(d=_BRAIN_D, fill="organ", stroke="skin", stroke_width=1.5),) + _BRAIN_GYRI,
    "lungs": (
        PathShape(d=_LUNG_LEFT_D, fill="organ", stroke="skin", stroke_width=1.5),
        PathShape(d=_LUNG_RIGHT_D, fill="organ", stroke="skin", stroke_width=1.5),
    ),
    "heart": (PathShape(d=_HEART_D, fill="organ", stroke="skin", stroke_width=1.5),),
    "vessels": (
        StrokeShape(points=((158, 205), (157, 240), (154, 272), (152, 300)), width=3.4, stroke="organ"),
        StrokeShape(points=((148, 160), (126, 168), (106, 190), (92, 220), (78, 264), (68, 316), (64, 340)), width=2.8, stroke="organ"),
        StrokeShape(points=((172, 160), (194, 168), (214, 190), (228, 220), (242, 264), (252, 316), (256, 340)), width=2.8, stroke="organ"),
        StrokeShape(points=((152, 300), (146, 344), (138, 392), (133, 448), (130, 512), (128, 578), (127, 610)), width=2.8, stroke="organ"),
        StrokeShape(points=((168, 300), (174, 344), (182, 392), (187, 448), (190, 512), (192, 578), (193, 610)), width=2.8, stroke="organ"),
    ),
    "blood": (
        droplet(78, 316, 8.5),
        droplet(242, 316, 8.5),
        droplet(134, 548, 8.0),
        droplet(186, 548, 8.0),
    ),
    "mouth": (
        StrokeShape(points=((160, 112), (160, 124), (160, 136)), width=8.0, stroke="organ"),
        Ellipse(cx=160, cy=99, rx=15, ry=7.0, fill="organ"),
        Ellipse(cx=160, cy=86, rx=4.5, ry=3.5, fill="organ"),
    ),
}

#: Порядок отрисовки: снизу вверх.
ORGAN_ORDER: tuple[str, ...] = ("vessels", "lungs", "brain", "blood", "mouth", "heart")

#: Подписи для SVG (title / aria-label).
ORGAN_LABELS: dict[str, str] = {
    "brain": "Мозг и нервная система",
    "lungs": "Лёгкие и дыхательные пути",
    "heart": "Сердце",
    "vessels": "Сосуды и эндотелий",
    "blood": "Кровь и кислород",
    "mouth": "Вкус, обоняние и оральный ритуал",
}


def mirror_pair(shape: Shape) -> Shape:
    """Отразить фигуру по горизонтали (для симметричных элементов)."""
    if isinstance(shape, PathShape):
        return PathShape(mirror_x(shape.d), shape.fill, shape.stroke, shape.stroke_width)
    if isinstance(shape, Ellipse):
        return Ellipse(2 * MID - shape.cx, shape.cy, shape.rx, shape.ry, shape.fill, shape.stroke, shape.stroke_width)
    return StrokeShape(tuple((2 * MID - x, y) for x, y in shape.points), shape.width, shape.stroke, shape.opacity)
