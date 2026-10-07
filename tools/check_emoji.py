"""Проверка, что эмодзи интерфейса реально отрисовываются системным шрифтом.

Некоторые эмодзи (например U+1FAC1 «лёгкие», U+1FAC0 «анатомическое сердце»)
отсутствуют в Segoe UI Emoji на Windows 10 и превращаются в «тофу» — пустой
прямоугольник. Другие (U+1F32C «ветер») по умолчанию имеют текстовое
представление и без селектора U+FE0F рисуются монохромно.

Скрипт собирает эмодзи прямо из данных приложения, рендерит их headless-браузером
в том же шрифтовом стеке, что и интерфейс, и проверяет результат.

Запуск:
    python tools/check_emoji.py            # снять и проверить
    python tools/check_emoji.py --analyse  # только анализ существующего PNG
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PREVIEW = ROOT / "tools" / "_preview"
HTML_PATH = PREVIEW / "emoji-test.html"
PNG_PATH = PREVIEW / "emoji-test.png"

EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)

CELL = 64
FONT_SIZE = 44

#: Порог «чернил»: настоящий эмодзи даёт заметно больше пикселей, чем контур тофу.
INK_TOFU_MAX = 500


def collect_emoji() -> dict[str, str]:
    """Собрать эмодзи, которые реально показываются пользователю."""
    from app.core.engagement import TIME_BADGES
    from app.core.organs import ORGAN_MODULES

    used: dict[str, str] = {}

    for module in ORGAN_MODULES:
        used[f"organ:{module.key}"] = module.emoji
    for key, emoji, _title, _detail, _need in TIME_BADGES:
        used[f"badge:{key}"] = emoji

    used.update(
        {
            "notification:motivational": "\U0001f389",
            "notification:warning": "\u26a0\ufe0f",
            "notification:info": "\U0001f4a1",
            "phase:acute": "\U0001f534",
            "phase:regeneration": "\U0001f7e0",
            "phase:active": "\U0001f7e1",
            "phase:restored": "\U0001f7e2",
            "timer": "\u23f1\ufe0f",
            "checkin:water": "\U0001f4a7",
            "checkin:activity": "\U0001f3c3",
        }
    )
    return used


def build_html(emoji: dict[str, str]) -> str:
    # Шрифтовой стек повторяет --font из app.css: важно, что эмодзи-шрифт
    # здесь НЕ указан явно — иначе проверка не воспроизводит реальные условия.
    stack = '"Inter", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif'
    cells = "".join(f'<span class="c">{ch}</span>' for ch in emoji.values())
    return (
        "<!doctype html><meta charset='utf-8'>"
        f"<style>body{{margin:0;background:#fff;font-family:{stack}}}"
        f".c{{display:inline-block;width:{CELL}px;height:{CELL}px;"
        f"font-size:{FONT_SIZE}px;line-height:{CELL}px;text-align:center}}</style>"
        f"{cells}"
    )


def render(emoji: dict[str, str]) -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(build_html(emoji), encoding="utf-8")

    browser = next((p for p in EDGE_CANDIDATES if Path(p).exists()), None)
    if browser is None:
        raise SystemExit("Не найден headless-браузер (Edge/Chrome)")

    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            f"--user-data-dir={Path.home() / '.vf-emoji-check'}",
            f"--window-size={len(emoji) * CELL},{CELL + 20}",
            f"--screenshot={PNG_PATH}",
            "--virtual-time-budget=3000",
            HTML_PATH.as_uri(),
        ],
        check=False,
        capture_output=True,
    )


def analyse(emoji: dict[str, str]) -> int:
    from PIL import Image

    if not PNG_PATH.exists():
        raise SystemExit(f"Нет снимка {PNG_PATH}. Запустите без --analyse.")

    img = Image.open(PNG_PATH).convert("RGB")
    failures: list[str] = []

    print(f"Снимок {img.size}, проверяем {len(emoji)} эмодзи\n")
    for index, (name, char) in enumerate(emoji.items()):
        x0 = index * CELL
        box = img.crop((x0 + 6, 6, x0 + CELL - 6, CELL - 6))
        ink = sum(1 for p in box.get_flattened_data() if sum(p) < 730)

        if ink >= INK_TOFU_MAX:
            verdict = f"OK ({ink} px)"
        else:
            verdict = f"ТОФУ — глиф отсутствует ({ink} px)"
            failures.append(f"{name} U+{ord(char[0]):04X}")

        print(f"  {name:28} {verdict}")

    print()
    if failures:
        print("Проблемные эмодзи:")
        for item in failures:
            print(f"  - {item}")
        print(
            "\nРешение: заменить на поддерживаемый эмодзи или добавить "
            "селектор U+FE0F (\\ufe0f) для принудительного эмодзи-представления."
        )
        return 1

    print("Все эмодзи интерфейса отрисовываются корректно.")
    return 0


def main() -> int:
    emoji = collect_emoji()
    if "--analyse" not in sys.argv:
        render(emoji)
    return analyse(emoji)


if __name__ == "__main__":
    raise SystemExit(main())
