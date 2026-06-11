#!/usr/bin/env python3
# export.py — скрипт для чистой сборки exe
import os
import shutil
import subprocess

# ----- Конфигурация -----
APP_NAME = "Пельмень"
ICON_PATH = "icons/pelmen2.ico"
UPX_DIR = "."          # если UPX не используется, можно закомментировать
DATA_DIRS = ["data", "icons"] # папки, которые копируются в сборку
EXCLUDE_MODULES = [
    "PySide6.QtWebEngine", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender", "PySide6.QtHelp",
    "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtMultimedia", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtVirtualKeyboard",
    "tkinter", "asyncio", "email", "unittest", "xml.sax", "pydoc", "idlelib", "http.server", "distutils"
]
# -------------------------

def clean_build_dirs():
    """Удаляет старые сборки и временные файлы"""
    dirs_to_remove = ["build", "dist"]
    files_to_remove = ["*.spec"]
    for d in dirs_to_remove:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"Удалена папка {d}")
    for pattern in files_to_remove:
        for f in os.listdir("."):
            if f.endswith(pattern.rstrip("*")):
                os.remove(f)
                print(f"Удалён {f}")

def clean_data():
    """Очищает пользовательские данные, оставляя только необходимые (help.html)"""
    data_dir = "data"
    if not os.path.exists(data_dir):
        return
    # Файлы, которые нужно оставить (все остальные удаляем)
    keep_files = {"help.html"}
    for item in os.listdir(data_dir):
        path = os.path.join(data_dir, item)
        if os.path.isfile(path):
            if item not in keep_files:
                os.remove(path)
                print(f"Удалён {path}")
        elif os.path.isdir(path):
            shutil.rmtree(path)
            print(f"Удалена папка {path}")

def build_exe():
    """Запускает PyInstaller с нужными параметрами"""
    cmd = [
        "pyinstaller",
        "--onedir",
        "--windowed",
        f"--name={APP_NAME}",
        f"--icon={ICON_PATH}",
    ]
    # Добавляем данные
    for d in DATA_DIRS:
        cmd.append(f"--add-data={d};{d}")
    # Исключаем модули
    for mod in EXCLUDE_MODULES:
        cmd.append(f"--exclude-module={mod}")
    # UPX (опционально, если папка существует)
    if os.path.exists(UPX_DIR):
        cmd.append(f"--upx-dir={UPX_DIR}")
        cmd.append("--upx-exclude=*.dll")
    # Очистка и без подтверждения
    cmd.append("--noconfirm")
    cmd.append("--clean")
    cmd.append("main.py")

    print("Запуск PyInstaller...")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    print("=== Начало сборки Пельменя ===\n")
    clean_build_dirs()
    clean_data()
    build_exe()
    print("\n✅ Сборка завершена. EXE находится в папке dist/Пельмень/")