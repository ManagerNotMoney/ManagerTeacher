"""
Педагогическая аналитика — standalone приложение для учителя
=============================================================
Функции:
  - Загрузка учеников вручную или из CSV/Excel
  - Ввод оценок по темам
  - Аналитика: кто отстаёт, пробелы в знаниях, динамика
  - Профиль каждого ученика
  - ИИ-анализ (структурированный stub-режим)
Хранение: SQLite (локально, без интернета)
Зависимости: pip install openpyxl --break-system-packages
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
import os
import datetime
from collections import defaultdict

try:
    import openpyxl
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

# ─────────────────────────────────────────────
#  Цвета
# ─────────────────────────────────────────────
C = {
    "bg":         "#0F1117",
    "panel":      "#16181F",
    "card":       "#1C1E28",
    "border":     "#2A2D3A",
    "accent":     "#5B8DEF",
    "accent2":    "#3DD68C",
    "warn":       "#F0A500",
    "danger":     "#E05C5C",
    "text":       "#E8EAF0",
    "muted":      "#6B6F80",
    "input_bg":   "#1E2130",
    "header_bg":  "#131520",
    "row_even":   "#1A1C26",
    "row_odd":    "#16181F",
    "row_sel":    "#1E2D4A",
}

FONT_MAIN  = ("Segoe UI", 10)
FONT_BOLD  = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 10)

DB_PATH = "pedagog.db"


# ─────────────────────────────────────────────
#  TopicHistory — история оценок по теме
# ─────────────────────────────────────────────

class TopicHistory:
    """
    История оценок ученика по конкретной теме.

    Атрибуты:
        topic      (str)   — название темы
        subject    (str)   — предмет
        timestamps (list)  — даты оценок (str ISO)
        scores     (list)  — оценки в том же порядке (float)
    """
    __slots__ = ("topic", "subject", "timestamps", "scores")

    def __init__(self, topic: str, subject: str):
        self.topic = topic
        self.subject = subject
        self.timestamps: list[str] = []
        self.scores: list[float] = []

    def add(self, timestamp: str, score: float):
        self.timestamps.append(timestamp)
        self.scores.append(score)

    @property
    def count(self) -> int:
        return len(self.scores)

    @property
    def avg(self) -> float | None:
        return sum(self.scores) / len(self.scores) if self.scores else None

    @property
    def latest(self) -> float | None:
        return self.scores[-1] if self.scores else None

    @property
    def earliest(self) -> float | None:
        return self.scores[0] if self.scores else None


def get_topic_histories(student_id: int, subject_filter: str | None = None) -> list[TopicHistory]:
    """
    Вернуть список TopicHistory для ученика.
    Каждая запись — хронологически упорядоченные оценки по одной теме.
    """
    with db() as con:
        if subject_filter:
            rows = con.execute("""
                SELECT t.name, subj.name, g.date, g.grade
                FROM grades g
                JOIN topics t   ON t.id = g.topic_id
                JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                WHERE g.student_id = ?
                ORDER BY t.name, g.date ASC, g.id ASC
            """, (subject_filter, student_id)).fetchall()
        else:
            rows = con.execute("""
                SELECT t.name, subj.name, g.date, g.grade
                FROM grades g
                JOIN topics t   ON t.id = g.topic_id
                JOIN subjects subj ON subj.id = t.subject_id
                WHERE g.student_id = ?
                ORDER BY t.name, g.date ASC, g.id ASC
            """, (student_id,)).fetchall()

    histories: dict[str, TopicHistory] = {}
    for topic_name, subj_name, date, grade in rows:
        key = f"{subj_name}::{topic_name}"
        if key not in histories:
            histories[key] = TopicHistory(topic=topic_name, subject=subj_name)
        histories[key].add(date, float(grade))

    return list(histories.values())


def analyze_topic_dynamics(histories: list[TopicHistory]) -> list[str]:
    """
    Анализирует динамику по каждой теме и возвращает список
    человекочитаемых строк-наблюдений.

    Логика:
    - «Улучшение»: последние N оценок в среднем выше первых N
    - «Ухудшение»: наоборот
    - «Стагнация ошибок»: несколько подряд плохих оценок за длительный период
    - «Стабильно высокий уровень»: все оценки ≥ 4.5
    """
    observations = []
    import datetime

    for h in histories:
        if h.count < 2:
            continue  # недостаточно данных для динамики

        scores = h.scores
        dates = h.timestamps
        n = h.count
        label_topic = f'«{h.topic}»'

        # --- Улучшение / ухудшение (сравниваем первую половину со второй) ---
        half = max(1, n // 2)
        early_avg = sum(scores[:half]) / half
        late_avg  = sum(scores[n - half:]) / half
        delta = late_avg - early_avg

        # --- Длительность периода (в днях) ---
        try:
            d0 = datetime.date.fromisoformat(dates[0][:10])
            d1 = datetime.date.fromisoformat(dates[-1][:10])
            span_days = (d1 - d0).days
        except Exception:
            span_days = 0

        span_str = ""
        if span_days >= 28:
            months = span_days // 28
            span_str = f" на протяжении {'месяца' if months == 1 else f'{months} месяцев'}"
        elif span_days >= 7:
            weeks = span_days // 7
            span_str = f" на протяжении {'недели' if weeks == 1 else f'{weeks} недель'}"
        elif span_days > 0:
            span_str = f" за {span_days} {'день' if span_days == 1 else 'дня' if span_days < 5 else 'дней'}"

        # Последние N работ для формулировки
        last_n = min(n, 4)
        last_scores = scores[-last_n:]
        last_avg = sum(last_scores) / len(last_scores)

        if delta >= 0.5:
            # Улучшение
            observations.append(
                f"↑ За последние {last_n} {'работу' if last_n == 1 else 'работы' if last_n < 5 else 'работ'} "
                f"наблюдается улучшение по теме {label_topic} "
                f"(ср. балл вырос с {early_avg:.1f} до {late_avg:.1f})."
            )
        elif delta <= -0.5:
            # Ухудшение
            observations.append(
                f"↓ По теме {label_topic} зафиксировано ухудшение{span_str}: "
                f"ср. балл снизился с {early_avg:.1f} до {late_avg:.1f}."
            )
        elif all(s < 3.5 for s in scores) and n >= 3:
            # Стагнация ошибок — слабые оценки без улучшения
            observations.append(
                f"⚠ Ошибки сохраняются{span_str} по теме {label_topic} "
                f"(ср. балл {h.avg:.1f} — без видимого прогресса)."
            )
        elif all(s >= 4.5 for s in scores) and n >= 3:
            # Стабильно высокий уровень
            observations.append(
                f"✓ Стабильно высокий результат по теме {label_topic} "
                f"({n} оценок, ср. {h.avg:.1f})."
            )
        elif abs(delta) < 0.2 and last_avg < 3.5 and n >= 3:
            # Стагнация без улучшения на слабом уровне
            observations.append(
                f"⚠ Результат по теме {label_topic} не улучшается{span_str} "
                f"(ср. {last_avg:.1f})."
            )

    return observations


# ─────────────────────────────────────────────
#  База данных
# ─────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            last    TEXT NOT NULL,
            first   TEXT NOT NULL,
            class   TEXT DEFAULT '',
            notes   TEXT DEFAULT '',
            created TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subjects (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS topics (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            name       TEXT NOT NULL,
            UNIQUE(subject_id, name),
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        );

        CREATE TABLE IF NOT EXISTS grades (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            topic_id   INTEGER NOT NULL,
            grade      REAL NOT NULL,
            date       TEXT NOT NULL,
            comment    TEXT DEFAULT '',
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(topic_id)   REFERENCES topics(id)
        );
    """)
    # Дефолтный предмет
    cur.execute("INSERT OR IGNORE INTO subjects(name) VALUES ('Математика')")
    cur.execute("INSERT OR IGNORE INTO subjects(name) VALUES ('Русский язык')")
    cur.execute("INSERT OR IGNORE INTO subjects(name) VALUES ('Физика')")
    con.commit()
    return con


def db():
    return sqlite3.connect(DB_PATH)


# ─────────────────────────────────────────────
#  Вспомогательные виджеты
# ─────────────────────────────────────────────

def styled_frame(parent, **kw):
    kw.setdefault("bg", C["panel"])
    return tk.Frame(parent, **kw)


def label(parent, text, font=FONT_MAIN, fg=None, **kw):
    kw["bg"] = kw.get("bg", parent["bg"])
    kw["fg"] = fg or C["text"]
    return tk.Label(parent, text=text, font=font, **kw)


def entry(parent, width=20, **kw):
    kw.setdefault("bg", C["input_bg"])
    kw.setdefault("fg", C["text"])
    kw.setdefault("insertbackground", C["accent"])
    kw.setdefault("relief", "flat")
    kw.setdefault("bd", 0)
    kw.setdefault("highlightthickness", 1)
    kw.setdefault("highlightbackground", C["border"])
    kw.setdefault("highlightcolor", C["accent"])
    kw.setdefault("font", FONT_MAIN)
    return tk.Entry(parent, width=width, **kw)


def btn(parent, text, command, color=None, fg=None, **kw):
    bg = color or C["accent"]
    fg = fg or C["bg"]
    b = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg,
        activebackground=bg, activeforeground=fg,
        relief="flat", bd=0, padx=14, pady=6,
        font=FONT_BOLD, cursor="hand2", **kw
    )
    return b


def separator(parent, orient="horizontal"):
    return tk.Frame(
        parent,
        bg=C["border"],
        height=1 if orient == "horizontal" else None,
        width=None if orient == "horizontal" else 1
    )


def make_tree(parent, columns, heights=14):
    """Создать стилизованный Treeview."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Dark.Treeview",
        background=C["card"],
        foreground=C["text"],
        fieldbackground=C["card"],
        rowheight=28,
        borderwidth=0,
        font=FONT_MAIN,
    )
    style.configure("Dark.Treeview.Heading",
        background=C["header_bg"],
        foreground=C["muted"],
        relief="flat",
        font=FONT_BOLD,
    )
    style.map("Dark.Treeview",
        background=[("selected", C["row_sel"])],
        foreground=[("selected", C["text"])],
    )

    frame = tk.Frame(parent, bg=C["panel"])
    vsb = ttk.Scrollbar(frame, orient="vertical")
    hsb = ttk.Scrollbar(frame, orient="horizontal")
    tree = ttk.Treeview(
        frame,
        columns=columns,
        show="headings",
        style="Dark.Treeview",
        yscrollcommand=vsb.set,
        xscrollcommand=hsb.set,
        height=heights,
    )
    vsb.config(command=tree.yview)
    hsb.config(command=tree.xview)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    # Чередующиеся строки
    tree.tag_configure("even", background=C["row_even"])
    tree.tag_configure("odd",  background=C["row_odd"])
    tree.tag_configure("warn", background="#2A1F0A", foreground=C["warn"])
    tree.tag_configure("danger", background="#2A0F0F", foreground=C["danger"])
    tree.tag_configure("good", background="#0A2A18", foreground=C["accent2"])
    return tree, frame


# ─────────────────────────────────────────────
#  Вкладка: Ученики
# ─────────────────────────────────────────────

class StudentsTab(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self._build()
        self.refresh()

    def _build(self):
        # Верхняя панель
        top = styled_frame(self, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(16, 0))

        label(top, "Ученики", font=FONT_TITLE, bg=C["bg"]).pack(side="left")

        right = tk.Frame(top, bg=C["bg"])
        right.pack(side="right")
        btn(right, "+ Добавить", self._add_dialog, color=C["accent"]).pack(side="left", padx=4)
        btn(right, "📂 CSV", self._import_csv, color=C["card"], fg=C["text"]).pack(side="left", padx=4)
        if HAS_XLSX:
            btn(right, "📊 Excel", self._import_xlsx, color=C["card"], fg=C["text"]).pack(side="left", padx=4)
        btn(right, "🗑 Удалить", self._delete_selected, color=C["card"], fg=C["danger"]).pack(side="left", padx=4)

        separator(self).pack(fill="x", padx=20, pady=10)

        # Поиск
        sf = tk.Frame(self, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=(0, 8))
        label(sf, "Поиск:", bg=C["bg"], fg=C["muted"]).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self.refresh())
        e = entry(sf, width=30)
        e.pack(side="left", padx=8, ipady=4)
        e.config(textvariable=self._search_var)

        # Таблица
        cols = ("id", "Фамилия", "Имя", "Класс", "Ср. оценка", "Статус")
        self.tree, tree_frame = make_tree(self, cols)
        self.tree.heading("id",        text="№")
        self.tree.heading("Фамилия",   text="Фамилия")
        self.tree.heading("Имя",       text="Имя")
        self.tree.heading("Класс",     text="Класс")
        self.tree.heading("Ср. оценка",text="Ср. оценка")
        self.tree.heading("Статус",    text="Статус")
        self.tree.column("id",         width=40,  anchor="center")
        self.tree.column("Фамилия",    width=160)
        self.tree.column("Имя",        width=130)
        self.tree.column("Класс",      width=80,  anchor="center")
        self.tree.column("Ср. оценка", width=100, anchor="center")
        self.tree.column("Статус",     width=160)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self.tree.bind("<Double-1>", lambda e: self.app.open_student_profile(self._selected_id()))

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        q = self._search_var.get().lower() if hasattr(self, "_search_var") else ""
        with db() as con:
            students = con.execute("SELECT id, last, first, class FROM students ORDER BY last, first").fetchall()
            for i, (sid, last, first, cls) in enumerate(students):
                if q and q not in last.lower() and q not in first.lower():
                    continue
                # Средняя оценка
                row = con.execute(
                    "SELECT AVG(grade), COUNT(grade) FROM grades WHERE student_id=?", (sid,)
                ).fetchone()
                avg, cnt = row if row else (None, 0)
                avg_str = f"{avg:.1f}" if avg is not None else "—"
                # Статус
                status, tag = self._status(avg, cnt)
                tag_row = "even" if i % 2 == 0 else "odd"
                if tag == "danger": tag_row = "danger"
                elif tag == "warn": tag_row = "warn"
                elif tag == "good": tag_row = "good"
                self.tree.insert("", "end", values=(sid, last, first, cls, avg_str, status), tags=(tag_row,))

    def _status(self, avg, cnt):
        if cnt == 0:
            return "Нет оценок", "odd"
        if avg < 3.0:
            return "⚠ Отстаёт (< 3)", "danger"
        if avg < 3.5:
            return "△ Под наблюдением", "warn"
        if avg >= 4.5:
            return "✓ Успевает хорошо", "good"
        return "Норма", "odd"

    def _add_dialog(self):
        StudentDialog(self, on_save=self.refresh)

    def _delete_selected(self):
        sid = self._selected_id()
        if not sid:
            messagebox.showwarning("Выбор", "Выберите ученика.")
            return
        if messagebox.askyesno("Удалить", "Удалить ученика и все его оценки?"):
            with db() as con:
                con.execute("DELETE FROM grades WHERE student_id=?", (sid,))
                con.execute("DELETE FROM students WHERE id=?", (sid,))
                con.commit()
            self.refresh()

    def _import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Все файлы", "*.*")])
        if not path:
            return
        count = 0
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            with db() as con:
                for row in reader:
                    last = row.get("Фамилия", row.get("last", "")).strip()
                    first = row.get("Имя", row.get("first", "")).strip()
                    cls = row.get("Класс", row.get("class", "")).strip()
                    if last and first:
                        con.execute(
                            "INSERT OR IGNORE INTO students(last, first, class) VALUES (?,?,?)",
                            (last, first, cls)
                        )
                        count += 1
                con.commit()
        self.refresh()
        messagebox.showinfo("Импорт", f"Добавлено: {count} учеников.")

    def _import_xlsx(self):
        if not HAS_XLSX:
            messagebox.showerror("Ошибка", "Установите openpyxl:\npip install openpyxl")
            return
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
        if not path:
            return
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return
        # Определяем заголовки
        headers = [str(c).strip() if c else "" for c in rows[0]]
        def col(names):
            for n in names:
                if n in headers:
                    return headers.index(n)
            return None
        i_last  = col(["Фамилия", "last", "Last"])
        i_first = col(["Имя", "first", "First"])
        i_cls   = col(["Класс", "class", "Class"])
        count = 0
        with db() as con:
            for row in rows[1:]:
                last  = str(row[i_last]).strip()  if i_last  is not None and row[i_last]  else ""
                first = str(row[i_first]).strip() if i_first is not None and row[i_first] else ""
                cls   = str(row[i_cls]).strip()   if i_cls   is not None and row[i_cls]   else ""
                if last and first:
                    con.execute(
                        "INSERT OR IGNORE INTO students(last, first, class) VALUES (?,?,?)",
                        (last, first, cls)
                    )
                    count += 1
            con.commit()
        self.refresh()
        messagebox.showinfo("Импорт", f"Добавлено: {count} учеников.")


# ─────────────────────────────────────────────
#  Диалог добавления ученика
# ─────────────────────────────────────────────

class StudentDialog(tk.Toplevel):
    def __init__(self, parent, student_id=None, on_save=None):
        super().__init__(parent)
        self.student_id = student_id
        self.on_save = on_save
        self.title("Добавить ученика" if not student_id else "Редактировать")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self._build()
        if student_id:
            self._load()
        self.grab_set()

    def _build(self):
        p = tk.Frame(self, bg=C["bg"], padx=24, pady=20)
        p.pack()

        label(p, "Фамилия", bg=C["bg"], fg=C["muted"]).grid(row=0, column=0, sticky="w", pady=4)
        self.e_last = entry(p, width=24)
        self.e_last.grid(row=0, column=1, padx=(8, 0), ipady=5)

        label(p, "Имя", bg=C["bg"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=4)
        self.e_first = entry(p, width=24)
        self.e_first.grid(row=1, column=1, padx=(8, 0), ipady=5)

        label(p, "Класс", bg=C["bg"], fg=C["muted"]).grid(row=2, column=0, sticky="w", pady=4)
        self.e_class = entry(p, width=24)
        self.e_class.grid(row=2, column=1, padx=(8, 0), ipady=5)

        label(p, "Заметки", bg=C["bg"], fg=C["muted"]).grid(row=3, column=0, sticky="nw", pady=4)
        self.e_notes = tk.Text(p, width=24, height=3,
            bg=C["input_bg"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", bd=0, font=FONT_MAIN,
            highlightthickness=1, highlightbackground=C["border"])
        self.e_notes.grid(row=3, column=1, padx=(8, 0), pady=4)

        row_btn = tk.Frame(p, bg=C["bg"])
        row_btn.grid(row=4, column=0, columnspan=2, pady=(14, 0))
        btn(row_btn, "Сохранить", self._save).pack(side="left", padx=4)
        btn(row_btn, "Отмена", self.destroy, color=C["card"], fg=C["text"]).pack(side="left", padx=4)

    def _load(self):
        with db() as con:
            row = con.execute("SELECT last,first,class,notes FROM students WHERE id=?", (self.student_id,)).fetchone()
        if row:
            self.e_last.insert(0, row[0])
            self.e_first.insert(0, row[1])
            self.e_class.insert(0, row[2])
            self.e_notes.insert("1.0", row[3])

    def _save(self):
        last  = self.e_last.get().strip()
        first = self.e_first.get().strip()
        cls   = self.e_class.get().strip()
        notes = self.e_notes.get("1.0", "end").strip()
        if not last or not first:
            messagebox.showwarning("Ошибка", "Фамилия и имя обязательны.", parent=self)
            return
        with db() as con:
            if self.student_id:
                con.execute("UPDATE students SET last=?,first=?,class=?,notes=? WHERE id=?",
                            (last, first, cls, notes, self.student_id))
            else:
                con.execute("INSERT INTO students(last,first,class,notes) VALUES (?,?,?,?)",
                            (last, first, cls, notes))
            con.commit()
        if self.on_save:
            self.on_save()
        self.destroy()


# ─────────────────────────────────────────────
#  Вкладка: Оценки
# ─────────────────────────────────────────────

class GradesTab(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self._build()
        self.refresh_students()

    def _build(self):
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(16, 0))
        label(top, "Ввод оценок", font=FONT_TITLE, bg=C["bg"]).pack(side="left")
        separator(self).pack(fill="x", padx=20, pady=10)

        # Форма ввода
        form = tk.Frame(self, bg=C["card"], padx=16, pady=14,
                        highlightthickness=1, highlightbackground=C["border"])
        form.pack(fill="x", padx=20, pady=(0, 12))

        # Строка 1: ученик + предмет + тема
        r1 = tk.Frame(form, bg=C["card"])
        r1.pack(fill="x", pady=4)

        label(r1, "Ученик:", bg=C["card"], fg=C["muted"]).pack(side="left")
        self.student_var = tk.StringVar()
        self.student_cb = ttk.Combobox(r1, textvariable=self.student_var, width=22, state="readonly")
        self.student_cb.pack(side="left", padx=(6, 18), ipady=3)

        label(r1, "Предмет:", bg=C["card"], fg=C["muted"]).pack(side="left")
        self.subject_var = tk.StringVar()
        self.subject_cb = ttk.Combobox(r1, textvariable=self.subject_var, width=16, state="readonly")
        self.subject_cb.pack(side="left", padx=(6, 4), ipady=3)
        btn(r1, "+", self._add_subject, color=C["panel"], fg=C["accent"]).pack(side="left", padx=(0, 18))

        label(r1, "Тема:", bg=C["card"], fg=C["muted"]).pack(side="left")
        self.topic_var = tk.StringVar()
        self.topic_cb = ttk.Combobox(r1, textvariable=self.topic_var, width=20)
        self.topic_cb.pack(side="left", padx=(6, 4), ipady=3)
        btn(r1, "+", self._add_topic, color=C["panel"], fg=C["accent"]).pack(side="left")

        # Строка 2: оценка + дата + комментарий + кнопка
        r2 = tk.Frame(form, bg=C["card"])
        r2.pack(fill="x", pady=4)

        label(r2, "Оценка:", bg=C["card"], fg=C["muted"]).pack(side="left")
        self.grade_var = tk.StringVar()
        grade_spin = tk.Spinbox(r2, from_=1, to=5, increment=1,
            textvariable=self.grade_var, width=4,
            bg=C["input_bg"], fg=C["text"], buttonbackground=C["panel"],
            relief="flat", font=FONT_BOLD, justify="center")
        grade_spin.pack(side="left", padx=(6, 18), ipady=4)
        self.grade_var.set("5")

        label(r2, "Дата:", bg=C["card"], fg=C["muted"]).pack(side="left")
        self.date_var = tk.StringVar(value=datetime.date.today().strftime("%Y-%m-%d"))
        date_entry = entry(r2, width=12)
        date_entry.config(textvariable=self.date_var)
        date_entry.pack(side="left", padx=(6, 18), ipady=4)

        label(r2, "Комментарий:", bg=C["card"], fg=C["muted"]).pack(side="left")
        self.comment_var = tk.StringVar()
        ce = entry(r2, width=28)
        ce.config(textvariable=self.comment_var)
        ce.pack(side="left", padx=(6, 18), ipady=4)

        btn(r2, "Добавить оценку", self._add_grade, color=C["accent2"], fg=C["bg"]).pack(side="left")

        # Таблица оценок
        cols = ("id", "Ученик", "Предмет", "Тема", "Оценка", "Дата", "Комментарий")
        self.tree, tree_frame = make_tree(self, cols, heights=16)
        for col in cols:
            self.tree.heading(col, text=col)
        self.tree.column("id",          width=40,  anchor="center")
        self.tree.column("Ученик",      width=160)
        self.tree.column("Предмет",     width=120)
        self.tree.column("Тема",        width=180)
        self.tree.column("Оценка",      width=70, anchor="center")
        self.tree.column("Дата",        width=100, anchor="center")
        self.tree.column("Комментарий", width=200)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        del_btn = btn(self, "🗑 Удалить выбранную оценку", self._delete_grade,
                      color=C["card"], fg=C["danger"])
        del_btn.pack(anchor="w", padx=20, pady=(0, 12))

        # Обновляем предметы
        self.subject_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_topics())
        self._refresh_subjects()
        self._refresh_grades()

    def refresh_students(self):
        with db() as con:
            rows = con.execute("SELECT id, last, first FROM students ORDER BY last, first").fetchall()
        self._student_map = {f"{r[1]} {r[2]}": r[0] for r in rows}
        if hasattr(self, "student_cb"):
            self.student_cb["values"] = list(self._student_map.keys())
            if self._student_map:
                self.student_cb.current(0)

    def _refresh_subjects(self):
        with db() as con:
            rows = con.execute("SELECT id, name FROM subjects ORDER BY name").fetchall()
        self._subject_map = {r[1]: r[0] for r in rows}
        self.subject_cb["values"] = list(self._subject_map.keys())
        if self._subject_map:
            self.subject_cb.current(0)
            self._refresh_topics()

    def _refresh_topics(self):
        subj_name = self.subject_var.get()
        sid = self._subject_map.get(subj_name)
        if sid is None:
            return
        with db() as con:
            rows = con.execute("SELECT name FROM topics WHERE subject_id=? ORDER BY name", (sid,)).fetchall()
        self._topics = [r[0] for r in rows]
        self.topic_cb["values"] = self._topics

    def _add_subject(self):
        name = _ask_string(self, "Новый предмет", "Название предмета:")
        if not name:
            return
        with db() as con:
            con.execute("INSERT OR IGNORE INTO subjects(name) VALUES (?)", (name,))
            con.commit()
        self._refresh_subjects()

    def _add_topic(self):
        subj_name = self.subject_var.get()
        sid = self._subject_map.get(subj_name)
        if not sid:
            messagebox.showwarning("Ошибка", "Сначала выберите предмет.")
            return
        name = _ask_string(self, "Новая тема", f"Тема для '{subj_name}':")
        if not name:
            return
        with db() as con:
            con.execute("INSERT OR IGNORE INTO topics(subject_id, name) VALUES (?,?)", (sid, name))
            con.commit()
        self._refresh_topics()

    def _add_grade(self):
        student_name = self.student_var.get()
        topic_name   = self.topic_var.get().strip()
        subj_name    = self.subject_var.get()
        grade_str    = self.grade_var.get().strip()
        date_str     = self.date_var.get().strip()

        if not student_name or student_name not in self._student_map:
            messagebox.showwarning("Ошибка", "Выберите ученика."); return
        if not topic_name:
            messagebox.showwarning("Ошибка", "Укажите тему."); return
        try:
            grade = float(grade_str)
            if not (1 <= grade <= 5):
                raise ValueError
        except ValueError:
            messagebox.showwarning("Ошибка", "Оценка: число от 1 до 5."); return

        sid_subj = self._subject_map.get(subj_name)
        if sid_subj is None:
            messagebox.showwarning("Ошибка", "Выберите предмет."); return

        with db() as con:
            con.execute("INSERT OR IGNORE INTO topics(subject_id, name) VALUES (?,?)", (sid_subj, topic_name))
            topic_id = con.execute("SELECT id FROM topics WHERE subject_id=? AND name=?",
                                   (sid_subj, topic_name)).fetchone()[0]
            student_id = self._student_map[student_name]
            con.execute(
                "INSERT INTO grades(student_id, topic_id, grade, date, comment) VALUES (?,?,?,?,?)",
                (student_id, topic_id, grade, date_str, self.comment_var.get().strip())
            )
            con.commit()
        self._refresh_grades()
        self._refresh_topics()
        self.app.tabs["analytics"].refresh()
        self.comment_var.set("")

    def _refresh_grades(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        with db() as con:
            rows = con.execute("""
                SELECT g.id,
                       s.last || ' ' || s.first,
                       subj.name,
                       t.name,
                       g.grade,
                       g.date,
                       g.comment
                FROM grades g
                JOIN students s ON s.id = g.student_id
                JOIN topics t ON t.id = g.topic_id
                JOIN subjects subj ON subj.id = t.subject_id
                ORDER BY g.date DESC, g.id DESC
                LIMIT 300
            """).fetchall()
        for i, row in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            grade = row[4]
            if grade < 3:   tag = "danger"
            elif grade < 4: tag = "warn"
            self.tree.insert("", "end", values=row, tags=(tag,))

    def _delete_grade(self):
        sel = self.tree.selection()
        if not sel:
            return
        gid = int(self.tree.item(sel[0])["values"][0])
        with db() as con:
            con.execute("DELETE FROM grades WHERE id=?", (gid,))
            con.commit()
        self._refresh_grades()


# ─────────────────────────────────────────────
#  Вкладка: Аналитика
# ─────────────────────────────────────────────

class AnalyticsTab(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self._build()
        self.refresh()

    def _build(self):
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(16, 0))
        label(top, "Аналитика класса", font=FONT_TITLE, bg=C["bg"]).pack(side="left")
        btn(top, "↺ Обновить", self.refresh, color=C["card"], fg=C["accent"]).pack(side="right")
        separator(self).pack(fill="x", padx=20, pady=10)

        # Фильтр по предмету
        ff = tk.Frame(self, bg=C["bg"])
        ff.pack(fill="x", padx=20, pady=(0, 10))
        label(ff, "Предмет:", bg=C["bg"], fg=C["muted"]).pack(side="left")
        self.filter_subj = tk.StringVar(value="Все")
        self.subj_cb = ttk.Combobox(ff, textvariable=self.filter_subj, width=18, state="readonly")
        self.subj_cb.pack(side="left", padx=8, ipady=3)
        self.subj_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # Карточки-сводки
        self.cards_frame = tk.Frame(self, bg=C["bg"])
        self.cards_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Таблица отстающих
        lf = tk.Frame(self, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        left = tk.Frame(lf, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        label(left, "Отстающие ученики", font=FONT_BOLD, bg=C["bg"], fg=C["danger"]).pack(anchor="w", pady=(0, 4))
        cols = ("Ученик", "Ср. оценка", "Кол-во оценок", "Худшая тема")
        self.low_tree, low_frame = make_tree(left, cols, heights=8)
        for c in cols:
            self.low_tree.heading(c, text=c)
        self.low_tree.column("Ученик",        width=160)
        self.low_tree.column("Ср. оценка",    width=90, anchor="center")
        self.low_tree.column("Кол-во оценок", width=110, anchor="center")
        self.low_tree.column("Худшая тема",   width=180)
        low_frame.pack(fill="both", expand=True)

        right = tk.Frame(lf, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)
        label(right, "Проблемные темы", font=FONT_BOLD, bg=C["bg"], fg=C["warn"]).pack(anchor="w", pady=(0, 4))
        cols2 = ("Тема", "Предмет", "Ср. оценка", "Кол-во уч.")
        self.topic_tree, topic_frame = make_tree(right, cols2, heights=8)
        for c in cols2:
            self.topic_tree.heading(c, text=c)
        self.topic_tree.column("Тема",        width=160)
        self.topic_tree.column("Предмет",     width=100)
        self.topic_tree.column("Ср. оценка",  width=90, anchor="center")
        self.topic_tree.column("Кол-во уч.",  width=80, anchor="center")
        topic_frame.pack(fill="both", expand=True)

    def refresh(self):
        self._refresh_subjects()
        self._refresh_cards()
        self._refresh_low()
        self._refresh_topics()

    def _refresh_subjects(self):
        with db() as con:
            rows = con.execute("SELECT name FROM subjects ORDER BY name").fetchall()
        names = ["Все"] + [r[0] for r in rows]
        self.subj_cb["values"] = names

    def _get_subject_filter(self):
        v = self.filter_subj.get()
        return None if v == "Все" else v

    def _refresh_cards(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()

        subj = self._get_subject_filter()
        with db() as con:
            if subj:
                total = con.execute("""
                    SELECT COUNT(DISTINCT s.id) FROM students s
                    JOIN grades g ON g.student_id = s.id
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                """, (subj,)).fetchone()[0]
                avg = con.execute("""
                    SELECT AVG(g.grade) FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                """, (subj,)).fetchone()[0]
                low = con.execute("""
                    SELECT COUNT(DISTINCT g.student_id) FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects s ON s.id = t.subject_id AND s.name = ?
                    GROUP BY g.student_id HAVING AVG(g.grade) < 3
                """, (subj,)).rowcount
                # Пересчитать нормально
                low_students = con.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT g.student_id FROM grades g
                        JOIN topics t ON t.id = g.topic_id
                        JOIN subjects s ON s.id = t.subject_id AND s.name = ?
                        GROUP BY g.student_id HAVING AVG(g.grade) < 3
                    )
                """, (subj,)).fetchone()[0]
            else:
                total = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
                avg = con.execute("SELECT AVG(grade) FROM grades").fetchone()[0]
                low_students = con.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT student_id FROM grades
                        GROUP BY student_id HAVING AVG(grade) < 3
                    )
                """).fetchone()[0]
                total_grades = con.execute("SELECT COUNT(*) FROM grades").fetchone()[0]

        cards = [
            ("Всего учеников", str(total), C["accent"]),
            ("Средний балл",   f"{avg:.2f}" if avg else "—", C["accent2"]),
            ("Отстающих", str(low_students), C["danger"] if low_students > 0 else C["muted"]),
        ]

        for title, value, color in cards:
            card = tk.Frame(self.cards_frame, bg=C["card"], padx=20, pady=12,
                            highlightthickness=1, highlightbackground=C["border"])
            card.pack(side="left", padx=(0, 12))
            label(card, title, bg=C["card"], fg=C["muted"], font=FONT_SMALL).pack(anchor="w")
            label(card, value, bg=C["card"], fg=color, font=("Segoe UI", 20, "bold")).pack(anchor="w")

    def _refresh_low(self):
        for row in self.low_tree.get_children():
            self.low_tree.delete(row)
        subj = self._get_subject_filter()
        with db() as con:
            if subj:
                query = """
                    SELECT s.id, s.last || ' ' || s.first,
                           AVG(g.grade), COUNT(g.id)
                    FROM students s
                    JOIN grades g ON g.student_id = s.id
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                    GROUP BY s.id
                    HAVING AVG(g.grade) < 3.5
                    ORDER BY AVG(g.grade) ASC
                    LIMIT 30
                """
                rows = con.execute(query, (subj,)).fetchall()
            else:
                query = """
                    SELECT s.id, s.last || ' ' || s.first,
                           AVG(g.grade), COUNT(g.id)
                    FROM students s
                    JOIN grades g ON g.student_id = s.id
                    GROUP BY s.id
                    HAVING AVG(g.grade) < 3.5
                    ORDER BY AVG(g.grade) ASC
                    LIMIT 30
                """
                rows = con.execute(query).fetchall()

            for i, (sid, name, avg, cnt) in enumerate(rows):
                # Найти худшую тему
                if subj:
                    worst = con.execute("""
                        SELECT t.name, AVG(g.grade) FROM grades g
                        JOIN topics t ON t.id = g.topic_id
                        JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                        WHERE g.student_id = ?
                        GROUP BY t.id ORDER BY AVG(g.grade) ASC LIMIT 1
                    """, (subj, sid)).fetchone()
                else:
                    worst = con.execute("""
                        SELECT t.name, AVG(g.grade) FROM grades g
                        JOIN topics t ON t.id = g.topic_id
                        WHERE g.student_id = ?
                        GROUP BY t.id ORDER BY AVG(g.grade) ASC LIMIT 1
                    """, (sid,)).fetchone()
                worst_str = f"{worst[0]} ({worst[1]:.1f})" if worst else "—"
                tag = "danger" if avg < 3.0 else "warn"
                self.low_tree.insert("", "end",
                    values=(name, f"{avg:.2f}", cnt, worst_str),
                    tags=(tag,))

    def _refresh_topics(self):
        for row in self.topic_tree.get_children():
            self.topic_tree.delete(row)
        subj = self._get_subject_filter()
        with db() as con:
            if subj:
                rows = con.execute("""
                    SELECT t.name, subj.name, AVG(g.grade), COUNT(DISTINCT g.student_id)
                    FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                    GROUP BY t.id
                    HAVING AVG(g.grade) < 3.8
                    ORDER BY AVG(g.grade) ASC
                    LIMIT 20
                """, (subj,)).fetchall()
            else:
                rows = con.execute("""
                    SELECT t.name, subj.name, AVG(g.grade), COUNT(DISTINCT g.student_id)
                    FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id
                    GROUP BY t.id
                    HAVING AVG(g.grade) < 3.8
                    ORDER BY AVG(g.grade) ASC
                    LIMIT 20
                """).fetchall()
        for i, row in enumerate(rows):
            avg = row[2]
            tag = "danger" if avg < 3.0 else "warn"
            self.topic_tree.insert("", "end",
                values=(row[0], row[1], f"{avg:.2f}", row[3]),
                tags=(tag,))


# ─────────────────────────────────────────────
#  Профиль ученика
# ─────────────────────────────────────────────

class StudentProfile(tk.Toplevel):
    def __init__(self, parent, student_id):
        super().__init__(parent)
        self.student_id = student_id
        self.configure(bg=C["bg"])
        self.minsize(700, 500)
        self._build()
        self.grab_set()

    def _build(self):
        with db() as con:
            row = con.execute(
                "SELECT last, first, class, notes FROM students WHERE id=?",
                (self.student_id,)
            ).fetchone()
        if not row:
            self.destroy()
            return
        last, first, cls, notes = row
        self.title(f"{last} {first}")

        header = tk.Frame(self, bg=C["header_bg"], padx=20, pady=14)
        header.pack(fill="x")
        label(header, f"{last} {first}", font=FONT_TITLE, bg=C["header_bg"]).pack(side="left")
        if cls:
            label(header, f"  {cls} класс", font=FONT_MAIN, bg=C["header_bg"], fg=C["muted"]).pack(side="left")

        separator(self).pack(fill="x")

        # Карточки
        cards_f = tk.Frame(self, bg=C["bg"])
        cards_f.pack(fill="x", padx=20, pady=12)
        self._populate_cards(cards_f)

        # Оценки по темам
        label(self, "Оценки по темам", font=FONT_BOLD, bg=C["bg"]).pack(anchor="w", padx=20)
        cols = ("Предмет", "Тема", "Ср. оценка", "Кол-во", "Последняя", "Дата")
        tree, frame = make_tree(self, cols, heights=12)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Предмет",   width=120)
        tree.column("Тема",      width=200)
        tree.column("Ср. оценка",width=90, anchor="center")
        tree.column("Кол-во",    width=70, anchor="center")
        tree.column("Последняя", width=90, anchor="center")
        tree.column("Дата",      width=100, anchor="center")
        frame.pack(fill="both", expand=True, padx=20, pady=(4, 8))

        with db() as con:
            rows = con.execute("""
                SELECT subj.name, t.name,
                       AVG(g.grade), COUNT(g.id),
                       (SELECT grade FROM grades WHERE student_id=? AND topic_id=t.id ORDER BY date DESC LIMIT 1),
                       (SELECT date  FROM grades WHERE student_id=? AND topic_id=t.id ORDER BY date DESC LIMIT 1)
                FROM grades g
                JOIN topics t ON t.id = g.topic_id
                JOIN subjects subj ON subj.id = t.subject_id
                WHERE g.student_id = ?
                GROUP BY t.id
                ORDER BY AVG(g.grade) ASC
            """, (self.student_id, self.student_id, self.student_id)).fetchall()

        for i, row in enumerate(rows):
            avg = row[2]
            tag = "danger" if avg < 3.0 else ("warn" if avg < 3.5 else ("good" if avg >= 4.5 else ("even" if i%2==0 else "odd")))
            tree.insert("", "end", values=(row[0], row[1], f"{avg:.2f}", row[3], row[4], row[5]), tags=(tag,))

        # Динамика по темам
        dynamics = analyze_topic_dynamics(get_topic_histories(self.student_id))
        if dynamics:
            label(self, "Динамика по темам", font=FONT_BOLD, bg=C["bg"]).pack(
                anchor="w", padx=20, pady=(8, 2))
            dyn_frame = tk.Frame(self, bg=C["card"], padx=14, pady=10,
                                 highlightthickness=1, highlightbackground=C["border"])
            dyn_frame.pack(fill="x", padx=20, pady=(0, 8))
            for line in dynamics:
                # Выбираем цвет по первому символу строки
                if line.startswith("↑") or line.startswith("✓"):
                    fg = C["accent2"]
                elif line.startswith("↓"):
                    fg = C["danger"]
                else:
                    fg = C["warn"]
                label(dyn_frame, line, bg=C["card"], fg=fg,
                      font=FONT_SMALL, wraplength=620, justify="left").pack(
                    anchor="w", pady=2)

        # Заметки
        if notes:
            label(self, "Заметки учителя", font=FONT_BOLD, bg=C["bg"]).pack(anchor="w", padx=20, pady=(4, 2))
            note_frame = tk.Frame(self, bg=C["card"], padx=12, pady=8)
            note_frame.pack(fill="x", padx=20, pady=(0, 12))
            label(note_frame, notes, bg=C["card"], fg=C["muted"], wraplength=600, justify="left").pack(anchor="w")

    def _populate_cards(self, parent):
        with db() as con:
            avg = con.execute(
                "SELECT AVG(grade), COUNT(grade) FROM grades WHERE student_id=?",
                (self.student_id,)
            ).fetchone()
            best = con.execute("""
                SELECT t.name, AVG(g.grade) FROM grades g
                JOIN topics t ON t.id = g.topic_id
                WHERE g.student_id=? GROUP BY t.id ORDER BY AVG(g.grade) DESC LIMIT 1
            """, (self.student_id,)).fetchone()
            worst = con.execute("""
                SELECT t.name, AVG(g.grade) FROM grades g
                JOIN topics t ON t.id = g.topic_id
                WHERE g.student_id=? GROUP BY t.id ORDER BY AVG(g.grade) ASC LIMIT 1
            """, (self.student_id,)).fetchone()

        data = [
            ("Средний балл", f"{avg[0]:.2f}" if avg[0] else "—", C["accent"]),
            ("Оценок всего", str(avg[1]), C["muted"]),
            ("Лучшая тема",  f"{best[0]} ({best[1]:.1f})" if best else "—", C["accent2"]),
            ("Слабая тема",  f"{worst[0]} ({worst[1]:.1f})" if worst else "—", C["danger"]),
        ]
        for title, val, color in data:
            c = tk.Frame(parent, bg=C["card"], padx=16, pady=10,
                         highlightthickness=1, highlightbackground=C["border"])
            c.pack(side="left", padx=(0, 10))
            label(c, title, bg=C["card"], fg=C["muted"], font=FONT_SMALL).pack(anchor="w")
            label(c, val, bg=C["card"], fg=color, font=("Segoe UI", 14, "bold")).pack(anchor="w")


# ─────────────────────────────────────────────
#  Утилита: простой диалог ввода строки
# ─────────────────────────────────────────────

def _ask_string(parent, title, prompt):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=C["bg"])
    dlg.resizable(False, False)
    dlg.grab_set()
    result = [None]

    f = tk.Frame(dlg, bg=C["bg"], padx=20, pady=16)
    f.pack()
    label(f, prompt, bg=C["bg"]).pack(anchor="w", pady=(0, 6))
    e = entry(f, width=28)
    e.pack(ipady=5)
    e.focus_set()

    def ok():
        result[0] = e.get().strip()
        dlg.destroy()

    e.bind("<Return>", lambda _: ok())
    btn(f, "OK", ok).pack(pady=(10, 0))
    dlg.wait_window()
    return result[0]


# ─────────────────────────────────────────────
#  Загрузка HCA моста
# ─────────────────────────────────────────────

try:
    from hca_pedagog import PedagogHCA
    _PHCA = PedagogHCA()
except Exception as _e:
    _PHCA = None
    print(f"[pedagog] hca_pedagog не загружен: {_e}")

try:
    from analytics import enrich_student_data as _enrich_student_data
    _ANALYTICS_AVAILABLE = True
except Exception as _ae:
    _ANALYTICS_AVAILABLE = False
    print(f"[pedagog] analytics не загружен: {_ae}")


# ─────────────────────────────────────────────
#  Вкладка: ИИ-анализ
# ─────────────────────────────────────────────

class AIAnalyticsTab(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(16, 0))
        label(top, "ИИ-анализ (структурированный stub)", font=FONT_TITLE, bg=C["bg"]).pack(side="left")

        # Статус HCA
        if _PHCA:
            status_txt = _PHCA.hca_status_text()
            status_color = C["accent2"] if _PHCA.available else C["warn"]
        else:
            status_txt = "⚠ hca_pedagog.py не найден"
            status_color = C["danger"]
        label(top, status_txt, bg=C["bg"], fg=status_color, font=FONT_SMALL).pack(side="right")

        separator(self).pack(fill="x", padx=20, pady=10)

        # Панель выбора режима
        mode_f = tk.Frame(self, bg=C["card"], padx=16, pady=12,
                          highlightthickness=1, highlightbackground=C["border"])
        mode_f.pack(fill="x", padx=20, pady=(0, 12))

        label(mode_f, "Режим анализа:", bg=C["card"], fg=C["muted"]).grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="student")
        modes = [
            ("Анализ ученика",   "student"),
            ("Сводка по классу", "class"),
            ("Следующий шаг",    "next"),
        ]
        for i, (txt, val) in enumerate(modes):
            rb = tk.Radiobutton(
                mode_f, text=txt, variable=self.mode_var, value=val,
                bg=C["card"], fg=C["text"], selectcolor=C["input_bg"],
                activebackground=C["card"], activeforeground=C["text"],
                font=FONT_MAIN, command=self._on_mode_change
            )
            rb.grid(row=0, column=i + 1, padx=12, sticky="w")

        # Выбор ученика (для режима student/next)
        label(mode_f, "Ученик:", bg=C["card"], fg=C["muted"]).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.student_var = tk.StringVar()
        self.student_cb = ttk.Combobox(mode_f, textvariable=self.student_var, width=25, state="readonly")
        self.student_cb.grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(10, 0), ipady=3)

        # Выбор предмета
        label(mode_f, "Предмет:", bg=C["card"], fg=C["muted"]).grid(row=1, column=3, sticky="w", pady=(10, 0), padx=(16, 0))
        self.subject_var = tk.StringVar(value="Все")
        self.subject_cb = ttk.Combobox(mode_f, textvariable=self.subject_var, width=16, state="readonly")
        self.subject_cb.grid(row=1, column=4, sticky="w", padx=(8, 0), pady=(10, 0), ipady=3)

        # Кнопка
        run_btn = btn(mode_f, "▶  Сгенерировать анализ", self._run,
                      color=C["accent"], fg=C["bg"])
        run_btn.grid(row=1, column=5, padx=(20, 0), pady=(8, 0))

        # Результат
        result_lbl = tk.Frame(self, bg=C["bg"])
        result_lbl.pack(fill="x", padx=20, pady=(0, 4))
        label(result_lbl, "Результат:", font=FONT_BOLD, bg=C["bg"]).pack(side="left")
        self._copy_btn = btn(result_lbl, "📋 Копировать", self._copy,
                             color=C["card"], fg=C["text"])
        self._copy_btn.pack(side="right")

        result_frame = tk.Frame(self, bg=C["input_bg"],
                                highlightthickness=1, highlightbackground=C["border"])
        result_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        vsb = ttk.Scrollbar(result_frame, orient="vertical")
        self.result_text = tk.Text(
            result_frame, wrap="word",
            bg=C["input_bg"], fg=C["text"],
            insertbackground=C["accent"],
            relief="flat", bd=0, padx=14, pady=12,
            font=FONT_MAIN,
            yscrollcommand=vsb.set,
            state="disabled",
        )
        vsb.config(command=self.result_text.yview)
        self.result_text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._refresh_selectors()

    def _on_mode_change(self):
        mode = self.mode_var.get()
        state = "readonly" if mode in ("student", "next") else "disabled"
        self.student_cb.config(state=state)

    def _refresh_selectors(self):
        with db() as con:
            students = con.execute("SELECT id, last, first FROM students ORDER BY last, first").fetchall()
            subjects = con.execute("SELECT name FROM subjects ORDER BY name").fetchall()
        self._student_map = {f"{r[1]} {r[2]}": r[0] for r in students}
        self.student_cb["values"] = list(self._student_map.keys())
        if self._student_map:
            self.student_cb.current(0)
        self.subject_cb["values"] = ["Все"] + [r[0] for r in subjects]
        self.subject_cb.current(0)

    def _get_student_data(self, student_id: int, subject_filter: str | None) -> dict:
        """Собрать данные ученика для передачи в HCA."""
        with db() as con:
            row = con.execute(
                "SELECT last, first, class FROM students WHERE id=?", (student_id,)
            ).fetchone()
            if not row:
                return {}
            name = f"{row[0]} {row[1]}"
            cls  = row[2]

            if subject_filter:
                avg_row = con.execute("""
                    SELECT AVG(g.grade), COUNT(g.grade) FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects s ON s.id = t.subject_id AND s.name = ?
                    WHERE g.student_id = ?
                """, (subject_filter, student_id)).fetchone()
                topics_raw = con.execute("""
                    SELECT t.name, AVG(g.grade), COUNT(g.grade) FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects s ON s.id = t.subject_id AND s.name = ?
                    WHERE g.student_id = ?
                    GROUP BY t.id
                """, (subject_filter, student_id)).fetchall()
            else:
                avg_row = con.execute(
                    "SELECT AVG(grade), COUNT(grade) FROM grades WHERE student_id=?",
                    (student_id,)
                ).fetchone()
                topics_raw = con.execute("""
                    SELECT t.name, AVG(g.grade), COUNT(g.grade) FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    WHERE g.student_id = ?
                    GROUP BY t.id
                """, (student_id,)).fetchall()

            # Тренд: сравниваем последние 3 оценки с предыдущими 3
            recent = con.execute(
                "SELECT grade FROM grades WHERE student_id=? ORDER BY date DESC, id DESC LIMIT 6",
                (student_id,)
            ).fetchall()

        topics = [{"name": r[0], "avg": r[1], "count": r[2]} for r in topics_raw]
        avg    = avg_row[0] if avg_row else None
        cnt    = avg_row[1] if avg_row else 0

        trend = "stable"
        if len(recent) >= 4:
            new_avg = sum(r[0] for r in recent[:3]) / 3
            old_avg = sum(r[0] for r in recent[3:]) / len(recent[3:])
            if new_avg - old_avg > 0.3:   trend = "improving"
            elif old_avg - new_avg > 0.3: trend = "declining"

        sorted_t = sorted(topics, key=lambda x: x["avg"])

        data = {
            "name":            name,
            "class":           cls,
            "subject":         subject_filter or "",
            "avg_grade":       avg,
            "grade_count":     cnt,
            "topics":          topics,
            "weakest_topic":   sorted_t[0]  if sorted_t else None,
            "strongest_topic": sorted_t[-1] if sorted_t else None,
            "recent_trend":    trend,
            # Совместимость: плоский список строк-наблюдений из pedagog.py
            "topic_dynamics":  analyze_topic_dynamics(
                get_topic_histories(student_id, subject_filter)
            ),
        }

        # Обогащаем данными от DynamicsAnalyzer (XAI, детальная динамика)
        if _ANALYTICS_AVAILABLE:
            data = _enrich_student_data(data, student_id, subject_filter)

        return data

    def _get_class_data(self, subject_filter: str | None) -> dict:
        """Собрать данные по всему классу."""
        with db() as con:
            if subject_filter:
                students_raw = con.execute("""
                    SELECT s.last||' '||s.first, AVG(g.grade), COUNT(g.grade)
                    FROM students s
                    JOIN grades g ON g.student_id = s.id
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                    GROUP BY s.id
                """, (subject_filter,)).fetchall()
                topic_gaps = con.execute("""
                    SELECT t.name, AVG(g.grade), COUNT(DISTINCT g.student_id)
                    FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                    GROUP BY t.id HAVING AVG(g.grade) < 4.0
                    ORDER BY AVG(g.grade) ASC LIMIT 8
                """, (subject_filter,)).fetchall()
            else:
                students_raw = con.execute("""
                    SELECT s.last||' '||s.first, AVG(g.grade), COUNT(g.grade)
                    FROM students s JOIN grades g ON g.student_id = s.id
                    GROUP BY s.id
                """).fetchall()
                topic_gaps = con.execute("""
                    SELECT t.name, AVG(g.grade), COUNT(DISTINCT g.student_id)
                    FROM grades g JOIN topics t ON t.id = g.topic_id
                    GROUP BY t.id HAVING AVG(g.grade) < 4.0
                    ORDER BY AVG(g.grade) ASC LIMIT 8
                """).fetchall()

        return {
            "subject":    subject_filter or "все предметы",
            "students":   [{"name": r[0], "avg": r[1], "count": r[2]} for r in students_raw],
            "topic_gaps": [{"name": r[0], "avg": r[1], "student_count": r[2]} for r in topic_gaps],
        }

    def _run(self):
        if not _PHCA:
            self._set_result("❌ Модуль hca_pedagog.py не найден.\nПоместите hca_pedagog.py в ту же папку.")
            return

        mode    = self.mode_var.get()
        subject = self.subject_var.get()
        if subject == "Все":
            subject = None

        self._set_result("⏳ Генерирую анализ...")
        self.update_idletasks()

        try:
            if mode in ("student", "next"):
                student_name = self.student_var.get()
                sid = self._student_map.get(student_name)
                if not sid:
                    self._set_result("Выберите ученика.")
                    return
                data = self._get_student_data(sid, subject)
                if not data:
                    self._set_result("Данных по ученику нет.")
                    return
                if mode == "student":
                    result = _PHCA.analyze_student(data)
                else:
                    result = _PHCA.suggest_next(data)

            else:  # class
                data   = self._get_class_data(subject)
                result = _PHCA.class_summary(data)

        except Exception as e:
            result = f"Ошибка при генерации анализа:\n{e}"

        self._set_result(result)

    def _set_result(self, text: str):
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.config(state="disabled")

    def _copy(self):
        text = self.result_text.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)

    def refresh(self):
        self._refresh_selectors()


# ─────────────────────────────────────────────
#  Главное окно
# ─────────────────────────────────────────────

class PedagogApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Педагогическая аналитика")
        self.configure(bg=C["bg"])
        self.minsize(900, 620)
        self.geometry("1100x720")

        init_db()
        self._build()

    def _build(self):
        # Заголовок
        header = tk.Frame(self, bg=C["header_bg"], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        label(header, "📚  Педагогическая аналитика",
              font=FONT_TITLE, bg=C["header_bg"]).pack(side="left", padx=18, pady=12)

        separator(self).pack(fill="x")

        # Tabs
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TNotebook",
            background=C["bg"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("Dark.TNotebook.Tab",
            background=C["panel"], foreground=C["muted"],
            padding=[18, 8], font=FONT_MAIN, borderwidth=0)
        style.map("Dark.TNotebook.Tab",
            background=[("selected", C["card"])],
            foreground=[("selected", C["text"])],
        )

        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill="both", expand=True)

        self.tabs = {}

        students_tab = StudentsTab(nb, self)
        nb.add(students_tab, text="  👥 Ученики  ")
        self.tabs["students"] = students_tab

        grades_tab = GradesTab(nb, self)
        nb.add(grades_tab, text="  📝 Оценки  ")
        self.tabs["grades"] = grades_tab

        analytics_tab = AnalyticsTab(nb, self)
        nb.add(analytics_tab, text="  📊 Аналитика  ")
        self.tabs["analytics"] = analytics_tab

        ai_tab = AIAnalyticsTab(nb, self)
        nb.add(ai_tab, text="  🤖 ИИ-анализ  ")
        self.tabs["ai"] = ai_tab

        # Обновляем ученика в форме оценок при смене вкладки
        def on_tab_change(e):
            tab = nb.index(nb.select())
            if tab == 1:
                self.tabs["grades"].refresh_students()
            elif tab == 2:
                self.tabs["analytics"].refresh()
            elif tab == 3:
                self.tabs["ai"].refresh()

        nb.bind("<<NotebookTabChanged>>", on_tab_change)

    def open_student_profile(self, student_id):
        if student_id:
            StudentProfile(self, student_id)


# ─────────────────────────────────────────────
#  Запуск
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app = PedagogApp()
    app.mainloop()
