"""Отрисовать PNG-превью анатомической схемы для визуальной проверки.

Запуск:
    python tools/preview_body.py [путь.png]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from body_render import render_png  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "tools" / "_preview" / "body_preview.png"


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    out = render_png(target)
    print(f"Превью: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
