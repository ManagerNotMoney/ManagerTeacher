"""
pdf_export.py — экспорт педагогических отчётов в PDF
=====================================================
Зависимости: pip install reportlab --break-system-packages

Публичный API:
    export_student_pdf(data, filepath)   — профиль одного ученика
    export_class_pdf(data, filepath)     — сводка по классу
    export_ai_analysis_pdf(text, meta, filepath) — текст ИИ-анализа

Внутри pedagog.py добавь кнопки «📄 PDF» и вызывай эти функции.
Шрифт: DejaVu Sans (поставляется с системой, поддерживает кириллицу).
Если не найден — fallback на Helvetica (кириллица не гарантирована).
"""

from __future__ import annotations

import os
import sys
import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ─────────────────────────────────────────────
#  Шрифты (кириллица)
# ─────────────────────────────────────────────

_FONT_REGISTERED = False
_FONT_NORMAL = "Helvetica"
_FONT_BOLD   = "Helvetica-Bold"

def _exe_base() -> Path:
    """
    Вернуть базовую папку для поиска ресурсов.
    При запуске из PyInstaller EXE — папка с распакованными файлами (_MEIPASS).
    При обычном запуске — папка рядом с pdf_export.py.
    """
    if getattr(sys, "frozen", False):
        # Мы внутри PyInstaller EXE
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def _register_fonts():
    global _FONT_REGISTERED, _FONT_NORMAL, _FONT_BOLD
    if _FONT_REGISTERED:
        return

    base = _exe_base()

    # Сначала ищем шрифты внутри EXE (папка fonts/, добавленная в .spec)
    candidates = [
        str(base / "fonts" / "DejaVuSans.ttf"),
        str(base / "fonts" / "DejaVuSans-Bold.ttf"),
        str(base / "fonts" / "arial.ttf"),
        str(base / "fonts" / "arialbd.ttf"),
        # Linux системные
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        # Windows системные
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        # macOS
        "/Library/Fonts/Arial.ttf",
    ]

    normal_path = None
    bold_path   = None

    for p in candidates:
        if Path(p).exists():
            if "Bold" in p or "bd" in p:
                bold_path = p
            else:
                normal_path = p

    try:
        if normal_path:
            pdfmetrics.registerFont(TTFont("DejaVu", normal_path))
            _FONT_NORMAL = "DejaVu"
        if bold_path:
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold_path))
            _FONT_BOLD = "DejaVu-Bold"
    except Exception:
        pass  # Используем Helvetica как fallback

    _FONT_REGISTERED = True

_register_fonts()


# ─────────────────────────────────────────────
#  Цветовая палитра (близко к теме приложения)
# ─────────────────────────────────────────────

CLR_ACCENT   = colors.HexColor("#5B8DEF")
CLR_GREEN    = colors.HexColor("#3DD68C")
CLR_WARN     = colors.HexColor("#F0A500")
CLR_DANGER   = colors.HexColor("#E05C5C")
CLR_BG_DARK  = colors.HexColor("#1C1E28")
CLR_MUTED    = colors.HexColor("#6B6F80")
CLR_TEXT     = colors.HexColor("#1A1A2E")
CLR_ROW_A    = colors.HexColor("#F0F4FF")
CLR_ROW_B    = colors.white
CLR_HEADER   = colors.HexColor("#2A2D3A")


# ─────────────────────────────────────────────
#  Стили параграфов
# ─────────────────────────────────────────────

def _styles():
    """Вернуть словарь именованных стилей."""
    def s(name, font=None, size=10, leading=14, color=CLR_TEXT, bold=False, space_before=0, space_after=4):
        f = font or (_FONT_BOLD if bold else _FONT_NORMAL)
        return ParagraphStyle(
            name=name,
            fontName=f,
            fontSize=size,
            leading=leading,
            textColor=color,
            spaceAfter=space_after,
            spaceBefore=space_before,
        )

    return {
        "title":    s("title",   size=18, leading=22, bold=True,  color=CLR_ACCENT, space_after=6),
        "subtitle": s("sub",     size=11, leading=14, color=CLR_MUTED, space_after=12),
        "h2":       s("h2",      size=13, leading=16, bold=True,  color=CLR_TEXT,   space_before=12, space_after=6),
        "h3":       s("h3",      size=11, leading=13, bold=True,  color=CLR_MUTED,  space_before=8, space_after=4),
        "body":     s("body",    size=10, leading=14, color=CLR_TEXT),
        "small":    s("small",   size=9,  leading=12, color=CLR_MUTED),
        "good":     s("good",    size=10, leading=14, color=colors.HexColor("#1B7A45")),
        "warn":     s("warn",    size=10, leading=14, color=colors.HexColor("#8B5500")),
        "danger":   s("danger",  size=10, leading=14, color=colors.HexColor("#8B1A1A")),
        "mono":     s("mono",    font="Courier", size=9, leading=13, color=CLR_TEXT),
    }


# ─────────────────────────────────────────────
#  Вспомогательные компоненты
# ─────────────────────────────────────────────

def _header_row(columns: list[str]) -> list[Paragraph]:
    """Строка заголовка таблицы."""
    st = ParagraphStyle("th", fontName=_FONT_BOLD, fontSize=9,
                        leading=12, textColor=colors.white)
    return [Paragraph(c, st) for c in columns]


def _grade_color(avg: float | None) -> colors.Color:
    if avg is None:
        return CLR_MUTED
    if avg < 3.0:
        return CLR_DANGER
    if avg < 3.5:
        return CLR_WARN
    if avg >= 4.5:
        return CLR_GREEN
    return CLR_TEXT


def _footer(canvas_obj, doc):
    """Колонтитул на каждой странице."""
    canvas_obj.saveState()
    canvas_obj.setFont(_FONT_NORMAL, 8)
    canvas_obj.setFillColor(CLR_MUTED)
    date_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    canvas_obj.drawString(20 * mm, 12 * mm, f"Педагогическая аналитика  |  {date_str}")
    canvas_obj.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Стр. {doc.page}")
    canvas_obj.restoreState()


def _build_doc(filepath: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title="Педагогическая аналитика",
        author="pedagog.py",
    )


# ─────────────────────────────────────────────
#  Экспорт профиля ученика
# ─────────────────────────────────────────────

def export_student_pdf(data: dict, filepath: str) -> str:
    """
    Создать PDF с профилем ученика.

    Args:
        data: словарь с данными ученика (тот же формат, что передаётся в PedagogHCA):
            {
              "name": "Иванов Александр",
              "class": "9А",
              "subject": "Математика",
              "avg_grade": 3.8,
              "grade_count": 12,
              "topics": [{"name": ..., "avg": ..., "count": ...}],
              "weakest_topic": {...},
              "strongest_topic": {...},
              "recent_trend": "stable" | "improving" | "declining",
              "topic_dynamics": [...],      # список строк из analyze_topic_dynamics
              "topic_dynamics_recs": [...], # список XAI-рекомендаций
            }
        filepath: путь для сохранения PDF

    Returns:
        Путь к сохранённому файлу.
    """
    doc  = _build_doc(filepath)
    st   = _styles()
    W    = A4[0] - 40 * mm  # полезная ширина страницы
    story = []

    name    = data.get("name", "Ученик")
    cls     = data.get("class", "")
    subject = data.get("subject", "")
    avg     = data.get("avg_grade")
    cnt     = data.get("grade_count", 0)
    trend   = data.get("recent_trend", "stable")

    # ── Заголовок ──────────────────────────────
    subtitle_parts = []
    if cls:     subtitle_parts.append(f"Класс: {cls}")
    if subject: subtitle_parts.append(f"Предмет: {subject}")
    subtitle_parts.append(f"Отчёт от {datetime.date.today().strftime('%d.%m.%Y')}")

    story.append(Paragraph(f"Профиль ученика: {name}", st["title"]))
    story.append(Paragraph("  |  ".join(subtitle_parts), st["subtitle"]))
    story.append(HRFlowable(width=W, thickness=1, color=CLR_ACCENT, spaceAfter=12))

    # ── Сводка (карточки) ──────────────────────
    story.append(Paragraph("Общая успеваемость", st["h2"]))

    avg_str   = f"{avg:.2f}" if avg is not None else "—"
    trend_map = {"improving": "↑ Растёт", "declining": "↓ Снижается", "stable": "→ Стабильно"}
    trend_str = trend_map.get(trend, trend)

    weakest  = data.get("weakest_topic")
    strongest = data.get("strongest_topic")

    summary_data = [
        _header_row(["Показатель", "Значение"]),
        ["Средний балл", avg_str],
        ["Оценок всего", str(cnt)],
        ["Тренд", trend_str],
        ["Слабая тема",    f"{weakest['name']} ({weakest['avg']:.1f})"    if weakest  else "—"],
        ["Лучшая тема",    f"{strongest['name']} ({strongest['avg']:.1f})" if strongest else "—"],
    ]

    summary_style = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  CLR_HEADER),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  _FONT_BOLD),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("FONTNAME",    (0, 1), (0, -1),  _FONT_BOLD),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CLR_ROW_A, CLR_ROW_B]),
        ("GRID",        (0, 0), (-1, -1), 0.4, CLR_MUTED),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0,0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ])

    story.append(Table(summary_data, colWidths=[W * 0.45, W * 0.55], style=summary_style))
    story.append(Spacer(1, 10))

    # ── Оценки по темам ────────────────────────
    topics = data.get("topics", [])
    if topics:
        story.append(Paragraph("Оценки по темам", st["h2"]))

        rows = [_header_row(["Тема", "Ср. балл", "Оценок", "Уровень"])]
        for t in sorted(topics, key=lambda x: x["avg"]):
            avg_t = t["avg"]
            level = (
                "⚠ Критично"    if avg_t < 3.0 else
                "△ Слабо"       if avg_t < 3.5 else
                "✓ Хорошо"      if avg_t >= 4.5 else
                "Норма"
            )
            color = _grade_color(avg_t)
            avg_p = Paragraph(f"{avg_t:.2f}", ParagraphStyle("td", fontName=_FONT_BOLD,
                fontSize=10, leading=13, textColor=color))
            rows.append([t["name"], avg_p, str(t["count"]), level])

        col_w = [W * 0.45, W * 0.18, W * 0.15, W * 0.22]
        ts = TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  CLR_HEADER),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  _FONT_BOLD),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CLR_ROW_A, CLR_ROW_B]),
            ("GRID",        (0, 0), (-1, -1), 0.4, CLR_MUTED),
            ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE",    (0, 1), (-1, -1), 10),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0,0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (0, -1),  8),
        ])
        story.append(Table(rows, colWidths=col_w, style=ts))
        story.append(Spacer(1, 10))

    # ── Динамика по темам ──────────────────────
    dynamics = data.get("topic_dynamics", [])
    if dynamics:
        story.append(Paragraph("Динамика по темам", st["h2"]))
        for line in dynamics:
            if line.startswith("↑") or line.startswith("✓"):
                sty = st["good"]
            elif line.startswith("↓"):
                sty = st["danger"]
            else:
                sty = st["warn"]
            story.append(Paragraph(line, sty))
        story.append(Spacer(1, 6))

    # ── XAI-рекомендации ───────────────────────
    recs = data.get("topic_dynamics_recs", [])
    if recs:
        story.append(Paragraph("Рекомендации с обоснованием", st["h2"]))
        priority_labels = {"high": "❗ Высокий", "medium": "⚡ Средний", "low": "✅ Низкий"}
        for rec in recs:
            priority = priority_labels.get(rec.get("priority", ""), "")
            block = [
                Paragraph(f"{priority}  {rec['recommendation']}", st["h3"]),
                Paragraph(f"Причина: {rec['reason']}", st["body"]),
                Paragraph(f"Основание: {rec['evidence']}", st["small"]),
                Spacer(1, 4),
            ]
            story.append(KeepTogether(block))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return filepath


# ─────────────────────────────────────────────
#  Экспорт сводки по классу
# ─────────────────────────────────────────────

def export_class_pdf(data: dict, filepath: str) -> str:
    """
    Создать PDF со сводкой по классу.

    Args:
        data: {
            "subject": "Математика",
            "students": [{"name": ..., "avg": ..., "count": ...}],
            "topic_gaps": [{"name": ..., "avg": ..., "student_count": ...}],
        }
    """
    doc   = _build_doc(filepath)
    st    = _styles()
    W     = A4[0] - 40 * mm
    story = []

    subject  = data.get("subject", "все предметы")
    students = data.get("students", [])
    gaps     = data.get("topic_gaps", [])

    avgs = [s["avg"] for s in students if s["avg"] is not None]
    class_avg = sum(avgs) / len(avgs) if avgs else None

    # ── Заголовок ──────────────────────────────
    story.append(Paragraph(f"Сводка по классу", st["title"]))
    story.append(Paragraph(
        f"Предмет: {subject}  |  Отчёт от {datetime.date.today().strftime('%d.%m.%Y')}",
        st["subtitle"]
    ))
    story.append(HRFlowable(width=W, thickness=1, color=CLR_ACCENT, spaceAfter=12))

    # ── Статистика ──────────────────────────────
    low   = [s for s in students if s["avg"] is not None and s["avg"] < 3.0]
    watch = [s for s in students if s["avg"] is not None and 3.0 <= s["avg"] < 3.5]
    good  = [s for s in students if s["avg"] is not None and s["avg"] >= 4.5]

    stat_data = [
        _header_row(["Показатель", "Значение"]),
        ["Средний балл по классу", f"{class_avg:.2f}" if class_avg else "—"],
        ["Учеников с оценками",    str(len(avgs))],
        ["Отстающих (< 3,0)",      str(len(low))],
        ["Под наблюдением (3,0–3,5)", str(len(watch))],
        ["Успевают хорошо (≥ 4,5)",str(len(good))],
    ]
    stat_style = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  CLR_HEADER),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  _FONT_BOLD),
        ("FONTNAME",    (0, 1), (0, -1),  _FONT_BOLD),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CLR_ROW_A, CLR_ROW_B]),
        ("GRID",        (0, 0), (-1, -1), 0.4, CLR_MUTED),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0,0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ])
    story.append(Paragraph("Статистика", st["h2"]))
    story.append(Table(stat_data, colWidths=[W * 0.6, W * 0.4], style=stat_style))
    story.append(Spacer(1, 12))

    # ── Таблица учеников ───────────────────────
    if students:
        story.append(Paragraph("Успеваемость учеников", st["h2"]))
        rows = [_header_row(["Ученик", "Ср. балл", "Оценок", "Статус"])]
        for s in sorted(students, key=lambda x: (x["avg"] or 99)):
            avg_v = s["avg"]
            status = (
                "⚠ Отстаёт"     if avg_v is not None and avg_v < 3.0 else
                "△ Наблюдение"  if avg_v is not None and avg_v < 3.5 else
                "✓ Хорошо"      if avg_v is not None and avg_v >= 4.5 else
                "Норма"
            )
            color = _grade_color(avg_v)
            avg_p = Paragraph(
                f"{avg_v:.2f}" if avg_v else "—",
                ParagraphStyle("td", fontName=_FONT_BOLD, fontSize=10, leading=13, textColor=color)
            )
            rows.append([s["name"], avg_p, str(s["count"]), status])

        col_w = [W * 0.45, W * 0.17, W * 0.13, W * 0.25]
        ts = TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  CLR_HEADER),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  _FONT_BOLD),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CLR_ROW_A, CLR_ROW_B]),
            ("GRID",        (0, 0), (-1, -1), 0.4, CLR_MUTED),
            ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ("FONTSIZE",    (0, 1), (-1, -1), 10),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0,0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (0, -1),  8),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ])
        story.append(Table(rows, colWidths=col_w, style=ts))
        story.append(Spacer(1, 12))

    # ── Тематические пробелы ───────────────────
    if gaps:
        story.append(Paragraph("Темы с наибольшими пробелами", st["h2"]))
        gap_rows = [_header_row(["Тема", "Ср. балл по теме", "Учеников"])]
        for g in sorted(gaps, key=lambda x: x["avg"]):
            color = _grade_color(g["avg"])
            avg_p = Paragraph(
                f"{g['avg']:.2f}",
                ParagraphStyle("td", fontName=_FONT_BOLD, fontSize=10, leading=13, textColor=color)
            )
            gap_rows.append([g["name"], avg_p, str(g["student_count"])])

        col_w = [W * 0.55, W * 0.25, W * 0.20]
        ts2 = TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  CLR_HEADER),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  _FONT_BOLD),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CLR_ROW_A, CLR_ROW_B]),
            ("GRID",        (0, 0), (-1, -1), 0.4, CLR_MUTED),
            ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ("FONTSIZE",    (0, 1), (-1, -1), 10),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0,0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (0, -1),  8),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ])
        story.append(Table(gap_rows, colWidths=col_w, style=ts2))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return filepath


# ─────────────────────────────────────────────
#  Экспорт ИИ-анализа (текст)
# ─────────────────────────────────────────────

def export_ai_analysis_pdf(text: str, meta: dict, filepath: str) -> str:
    """
    Создать PDF с текстом ИИ-анализа.

    Args:
        text: текст из AIAnalyticsTab (result_text.get())
        meta: {
            "mode": "student" | "class" | "next",
            "name": "Иванов Александр",  # если mode == student/next
            "subject": "Математика",
        }
        filepath: путь для сохранения
    """
    doc   = _build_doc(filepath)
    st    = _styles()
    W     = A4[0] - 40 * mm
    story = []

    mode    = meta.get("mode", "")
    name    = meta.get("name", "")
    subject = meta.get("subject", "")

    mode_titles = {
        "student": "Анализ ученика",
        "class":   "Сводка по классу",
        "next":    "Рекомендации",
    }
    title = mode_titles.get(mode, "ИИ-анализ")
    if name:
        title += f": {name}"

    subtitle_parts = []
    if subject: subtitle_parts.append(f"Предмет: {subject}")
    subtitle_parts.append(f"Отчёт от {datetime.date.today().strftime('%d.%m.%Y')}")

    story.append(Paragraph(title, st["title"]))
    story.append(Paragraph("  |  ".join(subtitle_parts), st["subtitle"]))
    story.append(HRFlowable(width=W, thickness=1, color=CLR_ACCENT, spaceAfter=14))

    # Разбираем текст построчно, выбираем стиль по первому символу
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue

        if line.startswith("↑") or line.startswith("✓"):
            sty = st["good"]
        elif line.startswith("↓") or line.startswith("❌") or line.startswith("❗"):
            sty = st["danger"]
        elif line.startswith("⚠") or line.startswith("🟡") or line.startswith("🔴"):
            sty = st["warn"]
        elif line.startswith("📋") or line.startswith("📊") or line.startswith("🎯"):
            sty = st["h2"]
        elif line.startswith("💡") or line.startswith("📈") or line.startswith("📌"):
            sty = st["h3"]
        elif line.startswith("[") and "]" in line:
            # [HIGH] / [MEDIUM] — приоритеты
            sty = st["h3"]
        else:
            sty = st["body"]

        story.append(Paragraph(line, sty))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return filepath


# ─────────────────────────────────────────────
#  Хелпер для получения пути сохранения
# ─────────────────────────────────────────────

def suggest_filepath(prefix: str, name: str = "") -> str:
    """
    Предложить путь для сохранения PDF рядом с pedagog.db.
    Используется когда filedialog не нужен (например, авто-экспорт).
    """
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
    date_str  = datetime.date.today().strftime("%Y%m%d")
    filename  = f"{prefix}_{safe_name}_{date_str}.pdf".replace("  ", " ").replace(" ", "_")
    return str(Path.cwd() / filename)
