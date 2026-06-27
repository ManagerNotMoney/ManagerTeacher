"""
analytics.py — аналитический модуль педагогической системы
============================================================

Отвечает за:
  • DynamicsAnalyzer   — анализ динамики оценок по темам
  • ExplainableRec     — рекомендации с объяснением (XAI)
  • enrich_student_data — обогащение данных перед передачей в LLMStub

Архитектура (правильная):

    Database
     ↓
    TopicHistory          (pedagog.py)
     ↓
    DynamicsAnalyzer      (analytics.py)  ← этот файл
     ↓
    ExplainableRec        (analytics.py)
     ↓
    StudentProfile / data dict
     ↓
    PedagogHCA / LLMStub  (hca_pedagog.py / llm_stub.py)

LLMStub только красиво форматирует вывод — не анализирует оценки сам.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────
#  Константы
# ─────────────────────────────────────────────────────────────

# Минимум оценок для расчёта динамики по теме
MIN_SCORES_FOR_DYNAMICS = 2

# Окно «последних» работ при расчёте new_avg
RECENT_WINDOW = 4

# Порог дельты для определения improvement / decline
IMPROVEMENT_DELTA = 0.5
DECLINE_DELTA     = 0.5

# Порог «слабого» среднего балла
WEAK_THRESHOLD  = 3.5
STRONG_THRESHOLD = 4.5


# ─────────────────────────────────────────────────────────────
#  Статусы динамики
# ─────────────────────────────────────────────────────────────

class DynamicStatus:
    IMPROVEMENT = "improvement"
    DECLINE     = "decline"
    STAGNATION  = "stagnation"
    STABLE_HIGH = "stable_high"
    STABLE      = "stable"
    NO_DATA     = "no_data"


# ─────────────────────────────────────────────────────────────
#  Результат анализа одной темы
# ─────────────────────────────────────────────────────────────

@dataclass
class TopicDynamicResult:
    topic: str
    subject: str
    status: str                    # DynamicStatus.*
    old_avg: Optional[float]
    new_avg: Optional[float]
    score_sequence: list[float]    # все оценки по хронологии
    score_dates: list[str]         # даты в том же порядке
    count: int
    delta: Optional[float]         # new_avg - old_avg, если есть

    @property
    def label(self) -> str:
        """Короткий человекочитаемый статус."""
        return {
            DynamicStatus.IMPROVEMENT: "улучшение",
            DynamicStatus.DECLINE:     "ухудшение",
            DynamicStatus.STAGNATION:  "стагнация",
            DynamicStatus.STABLE_HIGH: "стабильно высокий",
            DynamicStatus.STABLE:      "стабильно",
            DynamicStatus.NO_DATA:     "недостаточно данных",
        }.get(self.status, self.status)


# ─────────────────────────────────────────────────────────────
#  Explainable рекомендация
# ─────────────────────────────────────────────────────────────

@dataclass
class ExplainableRec:
    """
    Рекомендация с объяснением (XAI).

    Пример:
        recommendation = "Повторить тему «Арифметика»."
        reason         = "Средний балл по теме остаётся ниже 3."
        evidence       = "Последние 4 работы: 2 → 2 → 3 → 2. Прогресса нет."
        priority       = "high" | "medium" | "low"
        topic          = "Арифметика"
    """
    recommendation: str
    reason: str
    evidence: str
    priority: str       # "high" | "medium" | "low"
    topic: str
    status: str         # DynamicStatus.*

    def format_text(self) -> str:
        """Форматированный текст для вывода учителю."""
        lines = [
            f"Рекомендация:",
            f"  {self.recommendation}",
            f"",
            f"Причина:",
            f"  {self.reason}",
            f"",
            f"Основание:",
            f"  {self.evidence}",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  DynamicsAnalyzer
# ─────────────────────────────────────────────────────────────

class DynamicsAnalyzer:
    """
    Анализирует динамику обучения по списку TopicHistory.

    Использование:
        from pedagog import get_topic_histories
        from analytics import DynamicsAnalyzer

        histories = get_topic_histories(student_id)
        analyzer  = DynamicsAnalyzer(histories)

        results   = analyzer.analyze()          # list[TopicDynamicResult]
        recs      = analyzer.recommendations()  # list[ExplainableRec]
        obs_text  = analyzer.observations()     # list[str] (для совместимости с pedagog.py)
    """

    def __init__(self, histories: list):
        # histories: list[TopicHistory] из pedagog.py
        self._histories = histories

    # ── публичный API ─────────────────────────────────────────

    def analyze(self) -> list[TopicDynamicResult]:
        """Вернуть список TopicDynamicResult по всем темам с ≥ 2 оценками."""
        results = []
        for h in self._histories:
            r = self._analyze_one(h)
            if r is not None:
                results.append(r)
        return results

    def recommendations(self) -> list[ExplainableRec]:
        """
        Сформировать список XAI-рекомендаций.
        Возвращаются только темы, требующие внимания учителя.
        Отсортированы по приоритету: high → medium → low.
        """
        results = self.analyze()
        recs: list[ExplainableRec] = []

        for r in results:
            rec = self._make_recommendation(r)
            if rec is not None:
                recs.append(rec)

        # Сортировка: high → medium → low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recs.sort(key=lambda x: priority_order.get(x.priority, 9))
        return recs

    def observations(self) -> list[str]:
        """
        Вернуть список строк-наблюдений (совместимость с pedagog.analyze_topic_dynamics).
        Используется там, где нужен простой текстовый список.
        """
        import datetime
        results = self.analyze()
        lines: list[str] = []

        for r in results:
            if r.status == DynamicStatus.IMPROVEMENT:
                n = min(r.count, RECENT_WINDOW)
                seq = " → ".join(str(int(s)) if s == int(s) else f"{s:.1f}"
                                 for s in r.score_sequence[-n:])
                lines.append(
                    f"↑ За последние {n} {_work_form(n)} улучшение по теме «{r.topic}» "
                    f"(ср. вырос с {r.old_avg:.1f} до {r.new_avg:.1f}): {seq}."
                )

            elif r.status == DynamicStatus.DECLINE:
                span = self._span_str(r.score_dates)
                lines.append(
                    f"↓ По теме «{r.topic}» зафиксировано ухудшение{span}: "
                    f"ср. снизился с {r.old_avg:.1f} до {r.new_avg:.1f}."
                )

            elif r.status == DynamicStatus.STAGNATION:
                span = self._span_str(r.score_dates)
                lines.append(
                    f"⚠ Ошибки сохраняются{span} по теме «{r.topic}» "
                    f"(ср. {r.new_avg:.1f} — без видимого прогресса)."
                )

            elif r.status == DynamicStatus.STABLE_HIGH:
                lines.append(
                    f"✓ Стабильно высокий результат по теме «{r.topic}» "
                    f"({r.count} оценок, ср. {r.new_avg:.1f})."
                )

        return lines

    def get_topic_dynamics_dict(self) -> dict[str, list[tuple]]:
        """
        Возвращает динамику в виде:
            { "Арифметика": [(date, score), ...] }
        """
        result: dict[str, list[tuple]] = {}
        for h in self._histories:
            key = h.topic
            result[key] = list(zip(h.timestamps, h.scores))
        return result

    # ── внутренние методы ─────────────────────────────────────

    def _analyze_one(self, h) -> Optional[TopicDynamicResult]:
        """Анализ динамики одной темы."""
        if h.count < MIN_SCORES_FOR_DYNAMICS:
            return None

        scores = h.scores
        dates  = h.timestamps
        n      = h.count

        # Разбиваем на раннюю и позднюю половины
        half      = max(1, n // 2)
        old_avg   = sum(scores[:half]) / half
        new_avg   = sum(scores[n - half:]) / half
        delta     = new_avg - old_avg

        # Определяем статус
        if delta >= IMPROVEMENT_DELTA:
            status = DynamicStatus.IMPROVEMENT
        elif delta <= -DECLINE_DELTA:
            status = DynamicStatus.DECLINE
        elif all(s >= STRONG_THRESHOLD for s in scores) and n >= 3:
            status = DynamicStatus.STABLE_HIGH
        elif all(s < WEAK_THRESHOLD for s in scores) and n >= 3:
            status = DynamicStatus.STAGNATION
        elif abs(delta) < 0.2 and new_avg < WEAK_THRESHOLD and n >= 3:
            status = DynamicStatus.STAGNATION
        else:
            status = DynamicStatus.STABLE

        return TopicDynamicResult(
            topic          = h.topic,
            subject        = h.subject,
            status         = status,
            old_avg        = round(old_avg, 2),
            new_avg        = round(new_avg, 2),
            score_sequence = list(scores),
            score_dates    = list(dates),
            count          = n,
            delta          = round(delta, 2),
        )

    def _make_recommendation(self, r: TopicDynamicResult) -> Optional[ExplainableRec]:
        """Сформировать XAI-рекомендацию для одного результата динамики."""
        n    = min(r.count, RECENT_WINDOW)
        seq  = " → ".join(
            str(int(s)) if s == int(s) else f"{s:.1f}"
            for s in r.score_sequence[-n:]
        )
        evidence_suffix = f"Последние {n} {_work_form(n)}: {seq}."

        if r.status == DynamicStatus.DECLINE:
            return ExplainableRec(
                recommendation = f"Срочно повторить тему «{r.topic}».",
                reason         = (
                    f"Средний балл снизился с {r.old_avg:.1f} до {r.new_avg:.1f} "
                    f"(падение на {abs(r.delta):.1f})."
                ),
                evidence       = evidence_suffix,
                priority       = "high",
                topic          = r.topic,
                status         = r.status,
            )

        if r.status == DynamicStatus.STAGNATION:
            return ExplainableRec(
                recommendation = f"Изменить подход к теме «{r.topic}».",
                reason         = (
                    f"Средний балл по теме остаётся ниже {WEAK_THRESHOLD:.0f} "
                    f"на протяжении {r.count} {_work_form(r.count)}."
                ),
                evidence       = evidence_suffix + " Прогресса нет.",
                priority       = "high" if r.new_avg < 3.0 else "medium",
                topic          = r.topic,
                status         = r.status,
            )

        if r.status == DynamicStatus.IMPROVEMENT:
            return ExplainableRec(
                recommendation = f"Закрепить успех по теме «{r.topic}».",
                reason         = (
                    f"Ученик демонстрирует устойчивый прогресс: "
                    f"ср. балл вырос с {r.old_avg:.1f} до {r.new_avg:.1f}."
                ),
                evidence       = evidence_suffix,
                priority       = "low",
                topic          = r.topic,
                status         = r.status,
            )

        # STABLE / STABLE_HIGH — не требуют действий учителя
        return None

    @staticmethod
    def _span_str(dates: list[str]) -> str:
        """Вернуть строку вида ' на протяжении 3 недель' или ''."""
        if len(dates) < 2:
            return ""
        try:
            import datetime
            d0 = datetime.date.fromisoformat(dates[0][:10])
            d1 = datetime.date.fromisoformat(dates[-1][:10])
            days = (d1 - d0).days
        except Exception:
            return ""

        if days >= 28:
            m = days // 28
            return f" на протяжении {m} {_month_form(m)}"
        if days >= 7:
            w = days // 7
            return f" на протяжении {w} {_week_form(w)}"
        if days > 0:
            return f" за {days} {_day_form(days)}"
        return ""


# ─────────────────────────────────────────────────────────────
#  enrich_student_data — обогащение data dict перед LLMStub
# ─────────────────────────────────────────────────────────────

def enrich_student_data(data: dict, student_id: int, subject_filter: str | None = None) -> dict:
    """
    Дополняет словарь data (используемый в PedagogHCA / LLMStub)
    полноценной аналитикой от DynamicsAnalyzer.

    Добавляет ключи:
        topic_dynamics_results  : list[dict] — сырые результаты анализа
        topic_dynamics_text     : list[str]  — человекочитаемые строки
        topic_dynamics_recs     : list[dict] — XAI-рекомендации
        topic_dynamics_dict     : dict       — {topic: [(date, score)]}

    Используется в AIAnalyticsTab._get_student_data() вместо вызова
    analyze_topic_dynamics() напрямую.
    """
    try:
        # Импортируем здесь, чтобы не было циклических зависимостей
        from pedagog import get_topic_histories

        histories = get_topic_histories(student_id, subject_filter)
        analyzer  = DynamicsAnalyzer(histories)

        results = analyzer.analyze()
        recs    = analyzer.recommendations()

        data["topic_dynamics_results"] = [
            {
                "topic":          r.topic,
                "subject":        r.subject,
                "status":         r.status,
                "label":          r.label,
                "old_avg":        r.old_avg,
                "new_avg":        r.new_avg,
                "score_sequence": r.score_sequence,
                "score_dates":    r.score_dates,
                "count":          r.count,
                "delta":          r.delta,
            }
            for r in results
        ]

        data["topic_dynamics_text"] = analyzer.observations()

        data["topic_dynamics_recs"] = [
            {
                "topic":          rec.topic,
                "priority":       rec.priority,
                "status":         rec.status,
                "recommendation": rec.recommendation,
                "reason":         rec.reason,
                "evidence":       rec.evidence,
                "formatted":      rec.format_text(),
            }
            for rec in recs
        ]

        data["topic_dynamics_dict"] = analyzer.get_topic_dynamics_dict()

    except Exception as e:
        # Если pedagog.py недоступен — не ломаем работу
        data.setdefault("topic_dynamics_results", [])
        data.setdefault("topic_dynamics_text", [])
        data.setdefault("topic_dynamics_recs", [])
        data.setdefault("topic_dynamics_dict", {})

    return data


# ─────────────────────────────────────────────────────────────
#  Утилиты: склонения
# ─────────────────────────────────────────────────────────────

def _work_form(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "работу"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "работы"
    return "работ"


def _month_form(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "месяц"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "месяца"
    return "месяцев"


def _week_form(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "неделю"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "недели"
    return "недель"


def _day_form(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "дня"
    return "дней"
