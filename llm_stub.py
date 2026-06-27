"""
LLMStub — структурированный педагогический генератор (stub-режим)
═══════════════════════════════════════════════════════════════
Без нейросети. Использует шаблоны + реальные данные для формирования
педагогического анализа.

Режимы:
  generate_structured() — структурированный педагогический анализ

ПРИНЦИП:
  Не шаблон → реальные данные из памяти архитектуры.
  Если данных нет — честный "не знаю" + предложение рассказать.
  Если данные есть — компилирует их в читаемый ответ.
"""

import random
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
#  ПЕДАГОГИЧЕСКИЕ ШАБЛОНЫ АНАЛИЗА
# ═══════════════════════════════════════════════════════════════════════════

_PEDAGOGICAL_TEMPLATES = {
    "analyze_student": {
        "high": [
            "Ученик демонстрирует уверенное владение материалом (средний балл {avg:.1f}).",
            "{name} показывает стабильные результаты. Можно предложить углублённые задания.",
        ],
        "medium": [
            "Уровень успеваемости удовлетворительный (средний балл {avg:.1f}), есть пространство для роста.",
            "{name} справляется с базовым материалом, но требуется закрепление.",
        ],
        "low": [
            "Ученик испытывает систематические затруднения (средний балл {avg:.1f}).",
            "{name} нуждается в дополнительной поддержке и индивидуальном подходе.",
        ],
    },
    "gaps": {
        "header": "\n⚠ Выявленные пробелы:",
        "item": "  • {topic} — средний балл {avg:.1f} ({count} оценок)",
        "recommendation": "\n💡 Рекомендация: сосредоточить внимание на теме «{topic}».",
        "extra": "   Рассмотреть индивидуальные занятия или коррекционные задания базового уровня.",
    },
    "strengths": {
        "header": "\n✓ Сильные стороны:",
        "item": "  • {topic} — {avg:.1f}",
    },
    "class_summary": {
        "header": "📊 Сводка класса | {subject}",
        "avg": "\nСредний балл по классу: {avg:.2f}",
        "count": "Всего учеников с оценками: {count}",
        "low_header": "\n🔴 Отстающие ({count} чел.) — средний балл ниже 3,0:",
        "low_item": "  • {name} ({avg:.1f})",
        "watch_header": "\n🟡 Под наблюдением ({count} чел.) — 3,0–3,5:",
        "watch_item": "  • {name} ({avg:.1f})",
        "gaps_header": "\n📌 Темы с наибольшими пробелами в классе:",
        "gaps_item": "  • {topic} — ср. {avg:.1f} у {count} уч.",
    },
    "suggest_next": {
        "header": "🎯 Следующий шаг для {name}",
        "critical": [
            "\nПриоритет — устранить пробел по теме «{topic}» (балл: {avg:.1f}).",
            "Рекомендую:",
            "  1. Повторное объяснение с другим подходом (визуальный или пошаговый разбор).",
            "  2. Контрольные задания базового уровня сложности.",
            "  3. Проверка через 2 урока.",
        ],
        "weak": [
            "\nТема «{topic}» требует дополнительной практики (балл: {avg:.1f}).",
            "Рекомендую задания среднего уровня с разбором ошибок.",
        ],
        "stable": [
            "\nТекущий уровень стабильный (ср. {avg:.1f}).",
            "Можно предложить углублённые задания по теме «{topic}».",
        ],
    },
    "compare": {
        "header": "Сравнение: {name_a} ({avg_a:.1f}) vs {name_b} ({avg_b:.1f})",
        "diff": "Разница в среднем балле: {diff:.1f}",
        "better": "Успевает лучше: {better}",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  Основной класс
# ═══════════════════════════════════════════════════════════════════════════

class LLMStub:
    """
    Генератор структурированных педагогических ответов без LLM.
    """

    def __init__(self):
        self._rng = random.Random()

    # ═══════════════════════════════════════════════════════════════════════
    #  СТРУКТУРИРОВАННЫЙ ПЕДАГОГИЧЕСКИЙ АНАЛИЗ
    # ═══════════════════════════════════════════════════════════════════════

    def generate_structured(
        self,
        analysis_type: str,
        data: dict[str, Any],
        hca=None,
    ) -> dict[str, Any]:
        """
        Структурированный педагогический анализ.

        Args:
            analysis_type: тип анализа — "analyze_student", "class_summary",
                          "suggest_next", "compare_students"
            data: структурированные данные для анализа
            hca: не используется (оставлен для совместимости интерфейса)

        Returns:
            dict с полями:
                - text: человекочитаемый ответ
                - structured: словарь с разбивкой по пунктам
                - mode: "pedagogical"
                - confidence: уверенность в анализе (0.0–1.0)
        """
        if analysis_type == "analyze_student":
            return self._structured_analyze_student(data)
        elif analysis_type == "class_summary":
            return self._structured_class_summary(data)
        elif analysis_type == "suggest_next":
            return self._structured_suggest_next(data)
        elif analysis_type == "compare_students":
            return self._structured_compare(data)
        else:
            return {
                "text": f"[Неизвестный тип анализа: {analysis_type}]",
                "structured": {},
                "mode": "pedagogical",
                "confidence": 0.0,
            }

    def _structured_analyze_student(self, data: dict) -> dict[str, Any]:
        """Структурированный анализ одного ученика."""
        name = data.get("name", "Ученик")
        avg = data.get("avg_grade")
        topics = data.get("topics", [])
        subject = data.get("subject", "")

        structured = {
            "student_name": name,
            "subject": subject,
            "overall_level": None,
            "gaps": [],
            "strengths": [],
            "recommendation": None,
            "explanation_for_teacher": None,
        }

        lines = [f"📋 Анализ: {name}" + (f" | {subject}" if subject else "")]

        if avg is None:
            text = lines[0] + "\n\nОценок пока нет — анализ недоступен."
            structured["overall_level"] = "no_data"
            return {
                "text": text,
                "structured": structured,
                "mode": "pedagogical",
                "confidence": 0.0,
            }

        # Общий уровень
        if avg >= 4.5:
            level_text = self._rng.choice(_PEDAGOGICAL_TEMPLATES["analyze_student"]["high"])
            structured["overall_level"] = "high"
        elif avg >= 3.5:
            level_text = self._rng.choice(_PEDAGOGICAL_TEMPLATES["analyze_student"]["medium"])
            structured["overall_level"] = "medium"
        else:
            level_text = self._rng.choice(_PEDAGOGICAL_TEMPLATES["analyze_student"]["low"])
            structured["overall_level"] = "low"

        level_text = level_text.format(name=name, avg=avg)
        lines.append(f"\n{level_text}")

        # Пробелы
        weak = [t for t in topics if t["avg"] < 3.5]
        strong = [t for t in topics if t["avg"] >= 4.5]

        if weak:
            lines.append(_PEDAGOGICAL_TEMPLATES["gaps"]["header"])
            for t in sorted(weak, key=lambda x: x["avg"])[:3]:
                lines.append(_PEDAGOGICAL_TEMPLATES["gaps"]["item"].format(
                    topic=t["name"], avg=t["avg"], count=t["count"]
                ))
                structured["gaps"].append({
                    "topic": t["name"],
                    "avg": t["avg"],
                    "count": t["count"],
                })

        if strong:
            lines.append(_PEDAGOGICAL_TEMPLATES["strengths"]["header"])
            for t in sorted(strong, key=lambda x: -x["avg"])[:3]:
                lines.append(_PEDAGOGICAL_TEMPLATES["strengths"]["item"].format(
                    topic=t["name"], avg=t["avg"]
                ))
                structured["strengths"].append({
                    "topic": t["name"],
                    "avg": t["avg"],
                })

        # Детальная динамика по темам
        dynamics_results = data.get("topic_dynamics_results", [])
        if dynamics_results:
            lines.append("\n📈 Динамика по темам:")
            for r in dynamics_results:
                seq   = r.get("score_sequence", [])
                count = r.get("count", 0)
                n_show = min(count, 4)
                seq_str = " → ".join(
                    str(int(s)) if s == int(s) else f"{s:.1f}"
                    for s in seq[-n_show:]
                )
                old_a = r.get("old_avg")
                new_a = r.get("new_avg")
                status = r.get("status", "")

                if status == "improvement":
                    lines.append(
                        f"  ↑ {r['topic']} — средний балл {old_a:.1f} → {new_a:.1f} "
                        f"(последние {n_show} работ: {seq_str})."
                    )
                elif status == "decline":
                    lines.append(
                        f"  ↓ {r['topic']} — средний балл снизился с {old_a:.1f} до {new_a:.1f} "
                        f"(последние {n_show} работ: {seq_str})."
                    )
                elif status == "stagnation":
                    lines.append(
                        f"  ⚠ {r['topic']} — прогресс отсутствует "
                        f"(ср. {new_a:.1f}, последние {n_show} работ: {seq_str})."
                    )
                elif status == "stable_high":
                    lines.append(
                        f"  ✓ {r['topic']} — стабильно высокий уровень (ср. {new_a:.1f})."
                    )
        elif data.get("topic_dynamics_text"):
            lines.append("\n📈 Динамика по темам:")
            for obs in data["topic_dynamics_text"]:
                lines.append(f"  {obs}")

        # Explainable AI рекомендации
        xai_recs = data.get("topic_dynamics_recs", [])
        if xai_recs:
            lines.append("\n💡 Рекомендации с обоснованием:")
            for rec in xai_recs[:3]:
                lines.append(f"\n  [{rec['priority'].upper()}] {rec['recommendation']}")
                lines.append(f"  Причина: {rec['reason']}")
                lines.append(f"  Основание: {rec['evidence']}")
        elif weak:
            worst = sorted(weak, key=lambda x: x["avg"])[0]
            lines.append(_PEDAGOGICAL_TEMPLATES["gaps"]["recommendation"].format(
                topic=worst["name"]
            ))
            structured["recommendation"] = {
                "action": "focus_on_topic",
                "topic": worst["name"],
                "reason": f"Самый низкий балл: {worst['avg']:.1f}",
            }
            if avg < 3.0:
                lines.append(_PEDAGOGICAL_TEMPLATES["gaps"]["extra"])
                structured["recommendation"]["intensity"] = "intensive"
            else:
                structured["recommendation"]["intensity"] = "moderate"

        if not structured.get("recommendation"):
            if weak:
                worst = sorted(weak, key=lambda x: x["avg"])[0]
                structured["recommendation"] = {
                    "action": "focus_on_topic",
                    "topic": worst["name"],
                    "reason": f"Самый низкий балл: {worst['avg']:.1f}",
                    "intensity": "intensive" if avg < 3.0 else "moderate",
                }
            else:
                structured["recommendation"] = {
                    "action": "deepen",
                    "reason": "Нет критических пробелов",
                }

        # Объяснение для учителя
        structured["explanation_for_teacher"] = (
            f"Ученик {name} имеет средний балл {avg:.1f}. "
            f"{'Есть критические пробелы' if weak else 'Пробелов нет'}. "
            f"{'Рекомендуется индивидуальная работа' if avg < 3.0 else 'Рекомендуется закрепление материала'}."
        )

        text = "\n".join(lines)
        confidence = min(1.0, len(topics) / 5.0) if topics else 0.3

        return {
            "text": text,
            "structured": structured,
            "mode": "pedagogical",
            "confidence": confidence,
        }

    def _structured_class_summary(self, data: dict) -> dict[str, Any]:
        """Структурированная сводка по классу."""
        students = data.get("students", [])
        subject = data.get("subject", "все предметы")
        topic_gaps = data.get("topic_gaps", [])

        structured = {
            "subject": subject,
            "class_avg": None,
            "total_students": 0,
            "low_performers": [],
            "watch_list": [],
            "topic_gaps": [],
        }

        if not students:
            return {
                "text": "Данных по классу нет.",
                "structured": structured,
                "mode": "pedagogical",
                "confidence": 0.0,
            }

        avgs = [s["avg"] for s in students if s["avg"] is not None]
        class_avg = sum(avgs) / len(avgs) if avgs else None
        low = [s for s in students if s["avg"] is not None and s["avg"] < 3.0]
        watch = [s for s in students if s["avg"] is not None and 3.0 <= s["avg"] < 3.5]

        structured["class_avg"] = class_avg
        structured["total_students"] = len(avgs)
        structured["low_performers"] = [{"name": s["name"], "avg": s["avg"]} for s in low]
        structured["watch_list"] = [{"name": s["name"], "avg": s["avg"]} for s in watch]
        structured["topic_gaps"] = [{"name": t["name"], "avg": t["avg"]} for t in topic_gaps]

        lines = [_PEDAGOGICAL_TEMPLATES["class_summary"]["header"].format(subject=subject)]

        if class_avg is not None:
            lines.append(_PEDAGOGICAL_TEMPLATES["class_summary"]["avg"].format(avg=class_avg))
        lines.append(_PEDAGOGICAL_TEMPLATES["class_summary"]["count"].format(count=len(avgs)))

        if low:
            lines.append(_PEDAGOGICAL_TEMPLATES["class_summary"]["low_header"].format(count=len(low)))
            for s in sorted(low, key=lambda x: x["avg"])[:5]:
                lines.append(_PEDAGOGICAL_TEMPLATES["class_summary"]["low_item"].format(
                    name=s["name"], avg=s["avg"]
                ))

        if watch:
            lines.append(_PEDAGOGICAL_TEMPLATES["class_summary"]["watch_header"].format(count=len(watch)))
            for s in sorted(watch, key=lambda x: x["avg"])[:5]:
                lines.append(_PEDAGOGICAL_TEMPLATES["class_summary"]["watch_item"].format(
                    name=s["name"], avg=s["avg"]
                ))

        if topic_gaps:
            lines.append(_PEDAGOGICAL_TEMPLATES["class_summary"]["gaps_header"])
            for t in sorted(topic_gaps, key=lambda x: x["avg"])[:4]:
                lines.append(_PEDAGOGICAL_TEMPLATES["class_summary"]["gaps_item"].format(
                    topic=t["name"], avg=t["avg"], count=t["student_count"]
                ))

        text = "\n".join(lines)
        confidence = min(1.0, len(students) / 10.0)

        return {
            "text": text,
            "structured": structured,
            "mode": "pedagogical",
            "confidence": confidence,
        }

    def _structured_suggest_next(self, data: dict) -> dict[str, Any]:
        """Структурированная рекомендация следующего шага."""
        name = data.get("name", "Ученик")
        avg = data.get("avg_grade")
        weak = data.get("weakest_topic")
        strong = data.get("strongest_topic")
        trend = data.get("recent_trend", "stable")

        structured = {
            "student_name": name,
            "current_avg": avg,
            "trend": trend,
            "priority_topic": None,
            "recommended_tasks": [],
            "reasoning": None,
        }

        if avg is None:
            return {
                "text": f"По {name} недостаточно данных для рекомендации.",
                "structured": structured,
                "mode": "pedagogical",
                "confidence": 0.0,
            }

        lines = [_PEDAGOGICAL_TEMPLATES["suggest_next"]["header"].format(name=name)]

        # Базовая рекомендация по слабейшей теме
        if weak and weak["avg"] < 3.0:
            for line in _PEDAGOGICAL_TEMPLATES["suggest_next"]["critical"]:
                lines.append(line.format(topic=weak["name"], avg=weak["avg"]))
            structured["priority_topic"] = weak["name"]
            structured["recommended_tasks"] = [
                "Повторное объяснение с другим подходом",
                "Контрольные задания базового уровня",
                "Проверка через 2 урока",
            ]
            structured["reasoning"] = f"Критический пробел по теме {weak['name']} (балл {weak['avg']:.1f})"
        elif weak and weak["avg"] < 3.5:
            for line in _PEDAGOGICAL_TEMPLATES["suggest_next"]["weak"]:
                lines.append(line.format(topic=weak["name"], avg=weak["avg"]))
            structured["priority_topic"] = weak["name"]
            structured["recommended_tasks"] = [
                "Задания среднего уровня",
                "Разбор типичных ошибок",
            ]
            structured["reasoning"] = f"Тема {weak['name']} требует дополнительной практики"
        else:
            topic_name = strong["name"] if strong else "текущим темам"
            for line in _PEDAGOGICAL_TEMPLATES["suggest_next"]["stable"]:
                lines.append(line.format(avg=avg, topic=topic_name))
            structured["priority_topic"] = topic_name
            structured["recommended_tasks"] = [
                "Углублённые задания",
                "Задачи повышенной сложности",
            ]
            structured["reasoning"] = "Уровень стабильный, можно углубляться"

        # XAI рекомендации с динамикой
        xai_recs  = data.get("topic_dynamics_recs", [])
        dyn_results = data.get("topic_dynamics_results", [])

        improving   = [r for r in dyn_results if r.get("status") == "improvement"]
        declining   = [r for r in dyn_results if r.get("status") == "decline"]
        stagnating  = [r for r in dyn_results if r.get("status") == "stagnation"]

        if xai_recs:
            lines.append("\n\n💡 Приоритетные рекомендации:")
            for rec in xai_recs[:3]:
                priority_label = {"high": "❗", "medium": "⚡", "low": "✅"}.get(
                    rec["priority"], "•"
                )
                lines.append(f"\n{priority_label} {rec['recommendation']}")
                lines.append(f"   Причина: {rec['reason']}")
                lines.append(f"   Основание: {rec['evidence']}")

        # Адаптивный итоговый совет в зависимости от динамики
        if improving and not declining and not stagnating:
            lines.append(
                "\n\n✅ Ученик демонстрирует положительную динамику по ключевым темам. "
                "Поддержите мотивацию: отметьте прогресс и предложите задачи следующего уровня."
            )
            structured["recommended_tasks"].append("Задачи следующего уровня сложности")
            structured["recommended_tasks"].append("Поощрение прогресса")

        elif declining:
            topics_str = ", ".join(f"«{r['topic']}»" for r in declining[:2])
            lines.append(
                f"\n\n❗ Зафиксировано ухудшение по темам: {topics_str}. "
                "Рекомендуется выяснить причину снижения (пробел в понимании, "
                "внешние факторы) и скорректировать план."
            )
            structured["recommended_tasks"].insert(0, "Диагностическая беседа с учеником")

        elif stagnating and not improving:
            lines.append(
                "\n\n⚠ Прогресс по проблемным темам отсутствует. "
                "Текущий формат подачи материала не даёт результата — "
                "рекомендуется сменить метод (визуальные схемы, разбор с нуля, "
                "парная работа)."
            )
            structured["recommended_tasks"].insert(0, "Смена формата подачи материала")

        elif improving and (declining or stagnating):
            impr_str = ", ".join(f"«{r['topic']}»" for r in improving[:2])
            prob_str  = ", ".join(
                f"«{r['topic']}»" for r in (declining + stagnating)[:2]
            )
            lines.append(
                f"\n\nСмешанная динамика: прогресс есть по {impr_str}, "
                f"но сохраняются трудности по {prob_str}. "
                "Уделите дополнительное время проблемным темам, "
                "не теряя набранного темпа по успешным."
            )

        text = "\n".join(lines)
        confidence = 0.9 if xai_recs else (0.8 if weak else 0.6)

        return {
            "text": text,
            "structured": structured,
            "mode": "pedagogical",
            "confidence": confidence,
        }

    def _structured_compare(self, data: dict) -> dict[str, Any]:
        """Структурированное сравнение двух учеников."""
        a = data.get("student_a", {})
        b = data.get("student_b", {})
        name_a = a.get("name", "Ученик А")
        name_b = b.get("name", "Ученик Б")
        avg_a = a.get("avg_grade")
        avg_b = b.get("avg_grade")

        structured = {
            "student_a": {"name": name_a, "avg": avg_a},
            "student_b": {"name": name_b, "avg": avg_b},
            "difference": None,
            "better_student": None,
        }

        if avg_a is None or avg_b is None:
            return {
                "text": "Недостаточно данных для сравнения.",
                "structured": structured,
                "mode": "pedagogical",
                "confidence": 0.0,
            }

        diff = abs(avg_a - avg_b)
        better = name_a if avg_a >= avg_b else name_b

        structured["difference"] = diff
        structured["better_student"] = better

        lines = [
            _PEDAGOGICAL_TEMPLATES["compare"]["header"].format(
                name_a=name_a, avg_a=avg_a, name_b=name_b, avg_b=avg_b
            ),
            _PEDAGOGICAL_TEMPLATES["compare"]["diff"].format(diff=diff),
            _PEDAGOGICAL_TEMPLATES["compare"]["better"].format(better=better),
        ]

        text = "\n".join(lines)
        confidence = 0.7

        return {
            "text": text,
            "structured": structured,
            "mode": "pedagogical",
            "confidence": confidence,
        }
