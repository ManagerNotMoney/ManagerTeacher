# pedagog.spec
# PyInstaller spec-файл для сборки pedagog.exe
#
# Запуск:
#   pyinstaller pedagog.spec
#
# Результат: dist/pedagog.exe (Windows) или dist/pedagog (Linux)
#
# ВАЖНО: запускать из папки проекта, где лежат все .py файлы

import sys
from pathlib import Path

block_cipher = None

# ─────────────────────────────────────────────
#  Дополнительные файлы (datas)
#  Формат: (источник, папка_внутри_exe)
# ─────────────────────────────────────────────

datas = [
    # Модули проекта (PyInstaller может не подхватить их сам,
    # если они импортируются динамически через try/except)
    ("hca_pedagog.py",  "."),
    ("analytics.py",    "."),
    ("llm_stub.py",     "."),
    ("pdf_export.py",   "."),
]

# Шрифт для PDF — ищем автоматически
# На Windows пути будут другими, поэтому ищем динамически
_font_dirs = [
    # Linux
    Path("/usr/share/fonts/truetype/dejavu"),
    # Windows
    Path("C:/Windows/Fonts"),
    # macOS
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
]

for _d in _font_dirs:
    _normal = _d / "DejaVuSans.ttf"
    _bold   = _d / "DejaVuSans-Bold.ttf"
    # Windows fallback
    if not _normal.exists():
        _normal = _d / "arial.ttf"
        _bold   = _d / "arialbd.ttf"

    if _normal.exists():
        datas.append((str(_normal), "fonts"))
    if _bold.exists():
        datas.append((str(_bold), "fonts"))
    if _normal.exists():
        break  # нашли, хватит


# ─────────────────────────────────────────────
#  Скрытые импорты
#  (модули которые PyInstaller не видит статически)
# ─────────────────────────────────────────────

hiddenimports = [
    # reportlab
    "reportlab",
    "reportlab.lib",
    "reportlab.lib.pagesizes",
    "reportlab.lib.units",
    "reportlab.lib.colors",
    "reportlab.lib.styles",
    "reportlab.platypus",
    "reportlab.platypus.tables",
    "reportlab.pdfgen",
    "reportlab.pdfgen.canvas",
    "reportlab.pdfbase",
    "reportlab.pdfbase.pdfmetrics",
    "reportlab.pdfbase.ttfonts",
    "reportlab.pdfbase._fontdata",
    "reportlab.pdfbase.cidfonts",
    # tkinter (обычно находит сам, но на всякий случай)
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",
    # стандартные
    "sqlite3",
    "csv",
    "json",
    "pathlib",
    "collections",
    "dataclasses",
    # openpyxl (опционально, для импорта Excel)
    "openpyxl",
]

a = Analysis(
    ["pedagog.py"],          # главный файл
    pathex=["."],            # папка проекта
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Исключаем тяжёлые ненужные пакеты
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "PIL",
        "cv2",
        "torch",
        "tensorflow",
        "sklearn",
        "IPython",
        "jupyter",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="pedagog",                  # имя exe-файла
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                        # сжать (нужен upx, необязательно)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                   # False = без чёрного окна консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="icon.ico",               # раскомментируй если есть иконка
)
