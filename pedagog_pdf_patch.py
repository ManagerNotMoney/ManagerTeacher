"""
ПАТЧ pedagog.py — добавление кнопок «📄 PDF»
=============================================

Три места где нужно добавить код. Ищи по комментарию # PATCH и вставляй.

Предварительно убедись что pdf_export.py лежит в той же папке.
"""

# ══════════════════════════════════════════════════════════════════════
# ПАТЧ 1: Импорт в начало файла (после блока импортов openpyxl ~строка 27)
# ══════════════════════════════════════════════════════════════════════

PATCH_1_IMPORT = """
try:
    from pdf_export import export_student_pdf, export_class_pdf, export_ai_analysis_pdf
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
"""

# Куда вставить: после строки
#   except ImportError:
#       HAS_XLSX = False


# ══════════════════════════════════════════════════════════════════════
# ПАТЧ 2: Кнопка PDF в StudentProfile._build()
# ══════════════════════════════════════════════════════════════════════
#
# Найди в классе StudentProfile метод _build().
# В нём есть строка с кнопкой «Закрыть»:
#
#   btn(top, "✕  Закрыть", self.destroy, ...)
#
# ДОБАВЬ перед ней:

PATCH_2_STUDENT_BUTTON = """
        if HAS_PDF:
            btn(top, "📄 PDF", self._export_pdf,
                color=C["card"], fg=C["text"]).pack(side="right", padx=4)
"""

# И добавь метод _export_pdf в класс StudentProfile:

PATCH_2_STUDENT_METHOD = """
    def _export_pdf(self):
        from tkinter import filedialog
        with db() as con:
            row = con.execute("SELECT last, first, class FROM students WHERE id=?",
                              (self.student_id,)).fetchone()
            if not row:
                return
            name = f"{row[0]} {row[1]}"
            cls  = row[2]
            avg_row = con.execute(
                "SELECT AVG(grade), COUNT(grade) FROM grades WHERE student_id=?",
                (self.student_id,)
            ).fetchone()
            topics_raw = con.execute(\"\"\"
                SELECT t.name, AVG(g.grade), COUNT(g.grade) FROM grades g
                JOIN topics t ON t.id = g.topic_id
                WHERE g.student_id = ?
                GROUP BY t.id
            \"\"\", (self.student_id,)).fetchall()

        topics = [{"name": r[0], "avg": r[1], "count": r[2]} for r in topics_raw]
        sorted_t = sorted(topics, key=lambda x: x["avg"])

        data = {
            "name":            name,
            "class":           cls,
            "subject":         "",
            "avg_grade":       avg_row[0] if avg_row else None,
            "grade_count":     avg_row[1] if avg_row else 0,
            "topics":          topics,
            "weakest_topic":   sorted_t[0]  if sorted_t else None,
            "strongest_topic": sorted_t[-1] if sorted_t else None,
            "recent_trend":    "stable",
            "topic_dynamics":  analyze_topic_dynamics(get_topic_histories(self.student_id)),
            "topic_dynamics_recs": [],
        }

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"профиль_{name.replace(' ', '_')}.pdf",
            title="Сохранить PDF",
        )
        if not path:
            return
        try:
            export_student_pdf(data, path)
            messagebox.showinfo("PDF", f"Сохранено:\\n{path}")
        except Exception as e:
            messagebox.showerror("Ошибка PDF", str(e))
"""


# ══════════════════════════════════════════════════════════════════════
# ПАТЧ 3: Кнопка PDF в AIAnalyticsTab._build()
# ══════════════════════════════════════════════════════════════════════
#
# Найди в _build() строку с кнопкой «📋 Копировать»:
#
#   self._copy_btn = btn(result_lbl, "📋 Копировать", self._copy, ...)
#   self._copy_btn.pack(side="right")
#
# ДОБАВЬ после неё:

PATCH_3_AI_BUTTON = """
        if HAS_PDF:
            self._pdf_btn = btn(result_lbl, "📄 PDF", self._export_pdf,
                                color=C["card"], fg=C["text"])
            self._pdf_btn.pack(side="right", padx=4)
"""

# И добавь метод _export_pdf в класс AIAnalyticsTab:

PATCH_3_AI_METHOD = """
    def _export_pdf(self):
        from tkinter import filedialog
        text = self.result_text.get("1.0", "end").strip()
        if not text or text.startswith("⏳"):
            messagebox.showwarning("PDF", "Сначала сгенерируйте анализ.")
            return

        mode    = self.mode_var.get()
        subject = self.subject_var.get()
        if subject == "Все":
            subject = ""

        name = ""
        if mode in ("student", "next"):
            name = self.student_var.get()

        meta = {"mode": mode, "name": name, "subject": subject}

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"анализ_{name or 'класс'}_{mode}.pdf".replace(" ", "_"),
            title="Сохранить PDF",
        )
        if not path:
            return
        try:
            export_ai_analysis_pdf(text, meta, path)
            messagebox.showinfo("PDF", f"Сохранено:\\n{path}")
        except Exception as e:
            messagebox.showerror("Ошибка PDF", str(e))
"""

# ══════════════════════════════════════════════════════════════════════
# ПАТЧ 4 (опционально): Кнопка PDF сводки класса в AnalyticsTab
# ══════════════════════════════════════════════════════════════════════
#
# Если хочешь PDF и для вкладки «📊 Аналитика» (AnalyticsTab),
# добавь туда аналогичную кнопку и метод:

PATCH_4_ANALYTICS_METHOD = """
    def _export_class_pdf(self):
        from tkinter import filedialog
        subject = self.subject_var.get() if hasattr(self, 'subject_var') else None
        if subject == "Все":
            subject = None

        with db() as con:
            if subject:
                students_raw = con.execute(\"\"\"
                    SELECT s.last||' '||s.first, AVG(g.grade), COUNT(g.grade)
                    FROM students s
                    JOIN grades g ON g.student_id = s.id
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                    GROUP BY s.id
                \"\"\", (subject,)).fetchall()
                topic_gaps = con.execute(\"\"\"
                    SELECT t.name, AVG(g.grade), COUNT(DISTINCT g.student_id)
                    FROM grades g
                    JOIN topics t ON t.id = g.topic_id
                    JOIN subjects subj ON subj.id = t.subject_id AND subj.name = ?
                    GROUP BY t.id HAVING AVG(g.grade) < 4.0
                    ORDER BY AVG(g.grade) ASC LIMIT 8
                \"\"\", (subject,)).fetchall()
            else:
                students_raw = con.execute(\"\"\"
                    SELECT s.last||' '||s.first, AVG(g.grade), COUNT(g.grade)
                    FROM students s JOIN grades g ON g.student_id = s.id
                    GROUP BY s.id
                \"\"\").fetchall()
                topic_gaps = con.execute(\"\"\"
                    SELECT t.name, AVG(g.grade), COUNT(DISTINCT g.student_id)
                    FROM grades g JOIN topics t ON t.id = g.topic_id
                    GROUP BY t.id HAVING AVG(g.grade) < 4.0
                    ORDER BY AVG(g.grade) ASC LIMIT 8
                \"\"\").fetchall()

        data = {
            "subject": subject or "все предметы",
            "students": [{"name": r[0], "avg": r[1], "count": r[2]} for r in students_raw],
            "topic_gaps": [{"name": r[0], "avg": r[1], "student_count": r[2]} for r in topic_gaps],
        }

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"сводка_класса_{subject or 'все'}.pdf".replace(" ", "_"),
            title="Сохранить PDF",
        )
        if not path:
            return
        try:
            export_class_pdf(data, path)
            messagebox.showinfo("PDF", f"Сохранено:\\n{path}")
        except Exception as e:
            messagebox.showerror("Ошибка PDF", str(e))
"""
