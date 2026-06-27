"""
hca_pedagog.py — педагогический мост к HybridCognitiveArchitecture
===================================================================
Этот модуль НЕ меняет main.py. Он импортирует HCA как есть и добавляет
педагогическую логику сверху:

  PedagogHCA.analyze_student(data)  -> педагогический анализ ученика
  PedagogHCA.class_summary(data)    -> сводка по классу
  PedagogHCA.suggest_next(data)     -> рекомендация следующего шага
  PedagogHCA.compare_students(a, b) -> сравнение двух учеников

ВСЕ методы используют СТРУКТУРИРОВАННЫЙ режим LLMStub,
а НЕ чатовый pipeline hca.chat().

Если main.py/HCA недоступны — модуль работает в STUB-режиме:
generates analytical text directly without LLM.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------------------
#  Загрузка LLMStub (структурированный генератор)
# ------------------------------------------------------------------------------

_LLMSTUB_AVAILABLE = False
_llm_stub = None
_llmstub_error = ""

def _try_load_llmstub():
    global _LLMSTUB_AVAILABLE, _llm_stub, _llmstub_error
    try:
        here = Path(__file__).parent
        if str(here) not in sys.path:
            sys.path.insert(0, str(here))
        from llm_stub import LLMStub
        _llm_stub = LLMStub()
        _LLMSTUB_AVAILABLE = True
    except Exception as e:
        _llmstub_error = str(e)
        _LLMSTUB_AVAILABLE = False

_try_load_llmstub()


# ------------------------------------------------------------------------------
#  Загрузка HCA (с graceful fallback, только для памяти/контекста)
# ------------------------------------------------------------------------------

_HCA_AVAILABLE = False
_hca_instance = None
_hca_error = ""

def _try_load_hca():
    global _HCA_AVAILABLE, _hca_instance, _hca_error
    try:
        here = Path(__file__).parent
        if str(here) not in sys.path:
            sys.path.insert(0, str(here))
        from main import HybridCognitiveArchitecture, MEMORY_FILE
        hca = HybridCognitiveArchitecture()
        mem = Path(here / MEMORY_FILE)
        if mem.exists():
            hca.load_memory(mem)
        _hca_instance = hca
        _HCA_AVAILABLE = True
    except Exception as e:
        _hca_error = str(e)
        _HCA_AVAILABLE = False

_try_load_hca()


def hca_status() -> dict:
    return {
        "hca_available": _HCA_AVAILABLE,
        "llmstub_available": _LLMSTUB_AVAILABLE,
        "hca_error": _hca_error if not _HCA_AVAILABLE else "",
        "llmstub_error": _llmstub_error if not _LLMSTUB_AVAILABLE else "",
    }


# ------------------------------------------------------------------------------
#  Stub-генератор (работает без HCA и LLMStub)
# ------------------------------------------------------------------------------

def _stub_analyze(data: dict) -> str:
    name = data.get("name", "Ученик")
    avg = data.get("avg_grade")
    topics = data.get("topics", [])
    subject = data.get("subject", "")

    lines = [f"📋 Анализ: {name}" + (f" | {subject}" if subject else "")]

    if avg is None:
        return lines[0] + "\n\nОценок пока нет — анализ недоступен."

    # Общий уровень
    if avg >= 4.5:
        lines.append(f"\nСредний балл {avg:.2f} — ученик демонстрирует уверенное владение материалом.")
    elif avg >= 3.5:
        lines.append(f"\nСредний балл {avg:.2f} — уровень удовлетворительный, есть пространство для роста.")
    else:
        lines.append(f"\nСредний балл {avg:.2f} — ученик испытывает систематические затруднения.")

    # Пробелы
    weak = [t for t in topics if t["avg"] < 3.5]
    strong = [t for t in topics if t["avg"] >= 4.5]

    if weak:
        lines.append("\n⚠ Проблемные темы:")
        for t in sorted(weak, key=lambda x: x["avg"])[:3]:
            lines.append(f"  • {t['name']} — средний балл {t['avg']:.1f} ({t['count']} оценок)")

    if strong:
        lines.append("\n✓ Сильные стороны:")
        for t in sorted(strong, key=lambda x: -x["avg"])[:3]:
            lines.append(f"  • {t['name']} — {t['avg']:.1f}")

    # Динамика по темам
    dynamics = data.get("topic_dynamics", [])
    if dynamics:
        lines.append("\n📈 Динамика по темам:")
        for obs in dynamics:
            lines.append(f"  {obs}")

    # XAI рекомендации
    xai_recs = data.get("topic_dynamics_recs", [])
    if xai_recs:
        lines.append("\n💡 Рекомендации с обоснованием:")
        for rec in xai_recs[:3]:
            lines.append(f"\n  [{rec['priority'].upper()}] {rec['recommendation']}")
            lines.append(f"  Причина: {rec['reason']}")
            lines.append(f"  Основание: {rec['evidence']}")

    # Рекомендация
    if weak and not xai_recs:
        worst = sorted(weak, key=lambda x: x["avg"])[0]
        lines.append(f"\n💡 Рекомендация: сосредоточить внимание на теме «{worst['name']}».")
        if avg < 3.0:
            lines.append("   Рассмотреть индивидуальные занятия или коррекционные задания базового уровня.")

    return "\n".join(lines)


def _stub_class_summary(data: dict) -> str:
    students = data.get("students", [])
    subject = data.get("subject", "все предметы")
    topic_gaps = data.get("topic_gaps", [])

    if not students:
        return "Данных по классу нет."

    avgs = [s["avg"] for s in students if s["avg"] is not None]
    class_avg = sum(avgs) / len(avgs) if avgs else None
    low = [s for s in students if s["avg"] is not None and s["avg"] < 3.0]
    watch = [s for s in students if s["avg"] is not None and 3.0 <= s["avg"] < 3.5]

    lines = [f"📊 Сводка класса | {subject}"]
    if class_avg is not None:
        lines.append(f"\nСредний балл по классу: {class_avg:.2f}")
    lines.append(f"Всего учеников с оценками: {len(avgs)}")

    if low:
        lines.append(f"\n🔴 Отстающие ({len(low)} чел.) — средний балл ниже 3,0:")
        for s in sorted(low, key=lambda x: x["avg"])[:5]:
            lines.append(f"  • {s['name']} ({s['avg']:.1f})")

    if watch:
        lines.append(f"\n🟡 Под наблюдением ({len(watch)} чел.) — 3,0–3,5:")
        for s in sorted(watch, key=lambda x: x["avg"])[:5]:
            lines.append(f"  • {s['name']} ({s['avg']:.1f})")

    if topic_gaps:
        lines.append("\n📌 Темы с наибольшими пробелами в классе:")
        for t in sorted(topic_gaps, key=lambda x: x["avg"])[:4]:
            lines.append(f"  • {t['name']} — ср. {t['avg']:.1f} у {t['student_count']} уч.")

    return "\n".join(lines)


def _stub_suggest_next(data: dict) -> str:
    name = data.get("name", "Ученик")
    avg = data.get("avg_grade")
    weak = data.get("weakest_topic")
    strong = data.get("strongest_topic")

    if avg is None:
        return f"По {name} недостаточно данных для рекомендации."

    lines = [f"🎯 Следующий шаг для {name}"]

    if weak and weak["avg"] < 3.0:
        lines.append(f"\nПриоритет — устранить пробел по теме «{weak['name']}» (балл: {weak['avg']:.1f}).")
        lines.append("Рекомендую:")
        lines.append("  1. Повторное объяснение с другим подходом (визуальный или пошаговый разбор).")
        lines.append("  2. Контрольные задания базового уровня сложности.")
        lines.append("  3. Проверка через 2 урока.")
    elif weak and weak["avg"] < 3.5:
        lines.append(f"\nТема «{weak['name']}» требует дополнительной практики (балл: {weak['avg']:.1f}).")
        lines.append("Рекомендую задания среднего уровня с разбором ошибок.")
    else:
        lines.append(f"\nТекущий уровень стабильный (ср. {avg:.1f}).")
        if strong:
            lines.append(f"Можно предложить углублённые задания по теме «{strong['name']}».")

    # XAI рекомендации с динамикой
    xai_recs = data.get("topic_dynamics_recs", [])
    if xai_recs:
        lines.append("\n\n💡 Приоритетные рекомендации:")
        for rec in xai_recs[:3]:
            priority_label = {"high": "❗", "medium": "⚡", "low": "✅"}.get(
                rec["priority"], "•"
            )
            lines.append(f"\n{priority_label} {rec['recommendation']}")
            lines.append(f"   Причина: {rec['reason']}")
            lines.append(f"   Основание: {rec['evidence']}")

    # Динамика
    dynamics = data.get("topic_dynamics", [])
    if dynamics and not xai_recs:
        lines.append("\n📈 Динамика по темам:")
        for obs in dynamics:
            lines.append(f"  {obs}")

        improving = [d for d in dynamics if d.startswith("↑")]
        stagnating = [d for d in dynamics if d.startswith("⚠")]
        if improving:
            lines.append(
                "\n✅ Зафиксированный прогресс стоит поощрить — это повышает мотивацию ученика."
            )
        if stagnating and not improving:
            lines.append(
                "\n❗ Отсутствие прогресса по проблемным темам — рекомендую сменить формат подачи материала."
            )

    return "\n".join(lines)


# ------------------------------------------------------------------------------
#  Основной класс — педагогический мост
# ------------------------------------------------------------------------------

class PedagogHCA:
    """
    Обёртка над HCA с педагогическими методами.

    КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: педагогические запросы НЕ идут через hca.chat().
    Вместо этого используется LLMStub.generate_structured() — отдельный
    структурированный режим, который формирует аналитический ответ.

    Если LLMStub недоступен — используется встроенный stub-генератор.
    """

    MEMORY_FILE = "hca_pedagog_memory.json"

    def __init__(self):
        self._hca = _hca_instance  # может быть None
        self._stub = _llm_stub    # может быть None
        self._hca_available = _HCA_AVAILABLE
        self._stub_available = _LLMSTUB_AVAILABLE

    @property
    def available(self) -> bool:
        """Доступен ли хотя бы один из механизмов (HCA или LLMStub)."""
        return self._hca_available or self._stub_available

    def _generate_structured(self, analysis_type: str, data: dict) -> dict[str, Any]:
        """
        Генерация структурированного педагогического анализа.

        Приоритет:
        1. LLMStub.generate_structured() — если доступен
        2. Встроенный stub — если LLMStub недоступен

        Returns:
            dict с ключами: text, structured, mode, confidence
        """
        # Попытка 1: LLMStub.generate_structured()
        if self._stub_available and self._stub is not None:
            try:
                result = self._stub.generate_structured(
                    analysis_type=analysis_type,
                    data=data,
                    hca=self._hca,
                )
                if result and isinstance(result, dict) and result.get("text"):
                    return result
            except Exception:
                pass

        # Попытка 2: Встроенный stub-генератор
        text = ""
        if analysis_type == "analyze_student":
            text = _stub_analyze(data)
        elif analysis_type == "class_summary":
            text = _stub_class_summary(data)
        elif analysis_type == "suggest_next":
            text = _stub_suggest_next(data)
        elif analysis_type == "compare_students":
            name_a = data.get("student_a", {}).get("name", "Ученик А")
            name_b = data.get("student_b", {}).get("name", "Ученик Б")
            avg_a = data.get("student_a", {}).get("avg_grade")
            avg_b = data.get("student_b", {}).get("avg_grade")
            if avg_a is None or avg_b is None:
                text = "Недостаточно данных для сравнения."
            else:
                better = name_a if avg_a >= avg_b else name_b
                diff = abs((avg_a or 0) - (avg_b or 0))
                text = (
                    f"Сравнение: {name_a} ({avg_a:.1f}) vs {name_b} ({avg_b:.1f})\n"
                    f"Разница в среднем балле: {diff:.1f}\n"
                    f"Успевает лучше: {better}"
                )
        else:
            text = f"[Неизвестный тип анализа: {analysis_type}]"

        return {
            "text": text,
            "structured": {},
            "mode": "pedagogical",
            "confidence": 0.5,
        }

    # -- Публичные методы -------------------------------------------------------

    def analyze_student(self, data: dict) -> str:
        """
        Педагогический анализ одного ученика.

        data = {
          "name": "Иванов Александр",
          "subject": "Математика",
          "avg_grade": 3.2,
          "grade_count": 8,
          "topics": [
              {"name": "Дроби", "avg": 2.5, "count": 3},
              {"name": "Уравнения", "avg": 4.0, "count": 2},
          ],
          "class": "9А",
        }

        Returns: текстовый ответ (человекочитаемый)
        """
        result = self._generate_structured("analyze_student", data)
        return result.get("text", "")

    def class_summary(self, data: dict) -> str:
        """
        Сводный анализ класса.

        data = {
          "subject": "Математика",
          "students": [{"name": ..., "avg": ..., "count": ...}],
          "topic_gaps": [{"name": ..., "avg": ..., "student_count": ...}],
        }
        """
        result = self._generate_structured("class_summary", data)
        return result.get("text", "")

    def suggest_next(self, data: dict) -> str:
        """
        Рекомендация следующего педагогического шага для ученика.

        data = {
          "name": ...,
          "avg_grade": ...,
          "weakest_topic": {"name": ..., "avg": ...},
          "strongest_topic": {"name": ..., "avg": ...},
          "recent_trend": "improving" | "declining" | "stable",
        }
        """
        result = self._generate_structured("suggest_next", data)
        return result.get("text", "")

    def compare_students(self, a: dict, b: dict) -> str:
        """Краткое сравнение двух учеников."""
        data = {
            "student_a": a,
            "student_b": b,
        }
        result = self._generate_structured("compare_students", data)
        return result.get("text", "")

    def get_structured_analysis(self, analysis_type: str, data: dict) -> dict[str, Any]:
        """
        Получить структурированный результат анализа (dict).

        Returns:
            {
                "text": str,           # человекочитаемый текст
                "structured": dict,   # разбивка по пунктам
                "mode": "pedagogical",
                "confidence": float,   # 0.0–1.0
            }
        """
        return self._generate_structured(analysis_type, data)

    def save(self):
        """Сохранить память HCA (если доступна)."""
        if self._hca:
            try:
                self._hca.save_memory(self.MEMORY_FILE)
            except Exception:
                pass

    def hca_status_text(self) -> str:
        parts = []
        if self._stub_available:
            parts.append("✓ LLMStub (структурированный режим)")
        else:
            parts.append(f"⚠ LLMStub недоступен ({_llmstub_error[:40]})")

        if self._hca_available:
            parts.append("✓ HCA подключена (контекст/память)")
        else:
            parts.append(f"⚠ HCA недоступна ({_hca_error[:40]})")

        return " | ".join(parts)
