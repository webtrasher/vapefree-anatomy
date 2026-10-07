"""Сгенерировать app/static/img/body-map.svg из декларативной геометрии.

Запуск:
    python tools/build_body_svg.py            # записать SVG
    python tools/build_body_svg.py --check    # только проверить корректность
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

from body_render import build_svg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "app" / "static" / "img" / "body-map.svg"


def main() -> int:
    svg = build_svg()
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as exc:  # pragma: no cover
        print(f"SVG невалиден: {exc}", file=sys.stderr)
        return 1

    organs = [el.get("data-organ") for el in root.iter() if el.get("data-organ")]
    print(f"SVG корректен. Интерактивных органов: {len(organs)} -> {', '.join(organs)}")

    if "--check" in sys.argv:
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(svg, encoding="utf-8")
    print(f"Записано: {TARGET} ({TARGET.stat().st_size} байт)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
