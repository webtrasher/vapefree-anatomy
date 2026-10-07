"""Статическая защита от «тофу»-эмодзи в интерфейсе.

Полноценная проверка требует браузера (tools/check_emoji.py), но эти случаи
известны заранее и ловятся без рендеринга.
"""

from __future__ import annotations

from app.core.engagement import TIME_BADGES
from app.core.organs import ORGAN_MODULES

#: Отсутствуют в Segoe UI Emoji на Windows 10 -> пустой прямоугольник.
MISSING_GLYPHS = {
    "\U0001fac0": "U+1FAC0 анатомическое сердце",
    "\U0001fac1": "U+1FAC1 лёгкие",
}

#: Имеют текстовое представление по умолчанию; без U+FE0F рисуются монохромно.
NEEDS_VS16 = {
    "\U0001f32c": "U+1F32C ветер",
    "\u2764": "U+2764 сердце",
    "\u23f1": "U+23F1 секундомер",
    "\u26a0": "U+26A0 предупреждение",
    "\u2744": "U+2744 снежинка",
    "\U0001f324": "U+1F324 солнце за облаком",
}

VS16 = "\ufe0f"


def all_ui_emoji() -> list[tuple[str, str]]:
    """Пары (где используется, эмодзи)."""
    items: list[tuple[str, str]] = []
    for module in ORGAN_MODULES:
        items.append((f"organ:{module.key}", module.emoji))
    for key, emoji, *_ in TIME_BADGES:
        items.append((f"badge:{key}", emoji))
    return items


def test_no_missing_glyph_emoji():
    for where, emoji in all_ui_emoji():
        for ch in emoji:
            assert ch not in MISSING_GLYPHS, (
                f"{where}: {MISSING_GLYPHS.get(ch)} отсутствует в системном шрифте — "
                "замените эмодзи"
            )


def test_text_presentation_emoji_have_vs16_selector():
    for where, emoji in all_ui_emoji():
        for index, ch in enumerate(emoji):
            if ch not in NEEDS_VS16:
                continue
            following = emoji[index + 1] if index + 1 < len(emoji) else ""
            assert following == VS16, (
                f"{where}: {NEEDS_VS16[ch]} требует селектор U+FE0F, "
                "иначе глиф отрисуется монохромно"
            )


def test_emoji_are_single_graphemes():
    """Каждый эмодзи — один визуальный символ (базовый знак + опциональный VS16)."""
    for where, emoji in all_ui_emoji():
        assert emoji, f"{where}: пустой эмодзи"
        stripped = emoji.replace(VS16, "")
        assert len(stripped) <= 2, f"{where}: похоже на склейку из нескольких эмодзи — {emoji!r}"
