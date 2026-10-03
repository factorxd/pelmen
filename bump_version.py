#!/usr/bin/env python3
"""bump_version.py — обновляет номер версии во всех нужных файлах.

Использование:
    python bump_version.py 1.3.3
    python bump_version.py            # спросит интерактивно
"""
import re
import sys
from pathlib import Path


# Куда вписывать версию.
# Плейсхолдеры: {v} — "1.3.3", {v4} — "1.3.3.0", {v4_tuple} — "1, 3, 3, 0".
TARGETS = [
    (
        "version.py",
        [
            (r'__version__\s*=\s*["\'][^"\']*["\']', '__version__ = "{v}"'),
        ],
    ),
    (
        "version_info.txt",
        [
            (r'filevers=\([^)]*\)', 'filevers=({v4_tuple})'),
            (r'prodvers=\([^)]*\)', 'prodvers=({v4_tuple})'),
            (r"'FileVersion',\s*'[^']*'", "'FileVersion', '{v4}'"),
            (r"'ProductVersion',\s*'[^']*'", "'ProductVersion', '{v4}'"),
        ],
    ),
    (
        "README.md",
        [
            (r'version-\d+\.\d+\.\d+-blue', 'version-{v}-blue'),
        ],
    ),
]


def parse_version(text):
    """Принимает '1.3.3' или '1.3.3.1'. Возвращает (1, 3, 3, 0)."""
    text = text.strip().lstrip("vV")
    parts = text.split(".")
    if len(parts) == 3:
        parts.append("0")
    if len(parts) != 4:
        raise ValueError(
            f"Ожидается X.Y.Z или X.Y.Z.W, получено: {text!r}"
        )
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        raise ValueError(f"Все части должны быть числами: {text!r}")


def update_file(path, replacements, ctx):
    p = Path(path)
    if not p.exists():
        print(f"  ✗ {path} — не найден")
        return False
    text = p.read_text(encoding="utf-8")
    original = text
    for pattern, template in replacements:
        text, n = re.subn(
            pattern,
            lambda m, t=template: t.format(**ctx),
            text,
        )
        if n == 0:
            print(f"  ⚠ {path} — шаблон не найден: {pattern}")
    if text != original:
        p.write_text(text, encoding="utf-8")
        print(f"  ✓ {path}")
        return True
    print(f"  · {path} — без изменений")
    return False


def main():
    if len(sys.argv) > 1:
        version = sys.argv[1]
    else:
        version = input("Новая версия (например, 1.3.3): ").strip()

    try:
        v4_tuple = parse_version(version)
    except ValueError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    v = ".".join(str(x) for x in v4_tuple[:3])             # "1.3.3"
    v4 = ".".join(str(x) for x in v4_tuple)                # "1.3.3.0"
    v4_tuple_str = ", ".join(str(x) for x in v4_tuple)     # "1, 3, 3, 0"

    ctx = {"v": v, "v4": v4, "v4_tuple": v4_tuple_str}

    print(f"Обновление версии до {v4}:")
    changed = 0
    for path, replacements in TARGETS:
        if update_file(path, replacements, ctx):
            changed += 1

    if changed:
        print(f"\nГотово. Обновлено файлов: {changed}.")
        print("Не забудь добавить запись в CHANGELOG.md.")
    else:
        print("\nНичего не изменилось.")


if __name__ == "__main__":
    main()