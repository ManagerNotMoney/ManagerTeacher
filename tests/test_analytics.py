"""
Юнит-тесты для analytics.py
Покрывает: DynamicsAnalyzer, ExplainableRec, склонения, enrich_student_data
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from analytics import (
    DynamicsAnalyzer,
    TopicDynamicResult,
    ExplainableRec,
    DynamicStatus,
    _work_form,
    _day_form,
    _week_form,
    _month_form,
    IMPROVEMENT_DELTA,
    DECLINE_DELTA,
    WEAK_THRESHOLD,
    STRONG_THRESHOLD,
)


# ─────────────────────────────────────────────
#  Фикстуры — заглушки TopicHistory
# ─────────────────────────────────────────────

class FakeHistory:
    """Минимальная заглушка TopicHistory без SQLite."""
    def __init__(self, topic, subject, scores, dates=None):
        self.topic = topic
        self.subject = subject
        self.scores = scores
        self.timestamps = dates or [f"2024-01-{i+1:02d}" for i in range(len(scores))]

    @property
    def count(self):
        return len(self.scores)

    @property
    def avg(self):
        return sum(self.scores) / len(self.scores) if self.scores else None


def make_analyzer(*args):
    """Создать DynamicsAnalyzer из списков (topic, subject, scores)."""
    histories = [FakeHistory(t, s, sc) for t, s, sc in args]
    return DynamicsAnalyzer(histories)


# ─────────────────────────────────────────────
#  Тесты: статусы динамики
# ─────────────────────────────────────────────

class TestDynamicStatuses:

    def test_improvement_detected(self):
        """Рост среднего ≥ IMPROVEMENT_DELTA → статус improvement."""
        # Первая половина: [2, 2], вторая: [4, 5] → delta = 4.5 - 2 = 2.5
        analyzer = make_analyzer(("Дроби", "Математика", [2, 2, 4, 5]))
        results = analyzer.analyze()
        assert len(results) == 1
        assert results[0].status == DynamicStatus.IMPROVEMENT

    def test_decline_detected(self):
        """Падение среднего ≥ DECLINE_DELTA → статус decline."""
        # [5, 5, 2, 2] → delta = 2 - 5 = -3
        analyzer = make_analyzer(("Уравнения", "Математика", [5, 5, 2, 2]))
        results = analyzer.analyze()
        assert results[0].status == DynamicStatus.DECLINE

    def test_stagnation_all_weak(self):
        """Все оценки < WEAK_THRESHOLD (3.5), ≥ 3 оценок → стагнация."""
        analyzer = make_analyzer(("Дроби", "Математика", [2, 3, 2]))
        results = analyzer.analyze()
        assert results[0].status == DynamicStatus.STAGNATION

    def test_stable_high(self):
        """Все оценки ≥ STRONG_THRESHOLD (4.5), ≥ 3 оценок → stable_high."""
        analyzer = make_analyzer(("Алгебра", "Математика", [5, 5, 5, 4.5]))
        results = analyzer.analyze()
        assert results[0].status == DynamicStatus.STABLE_HIGH

    def test_stable_normal(self):
        """Нет выраженного изменения, оценки нормальные → stable."""
        # delta ≈ 0, avg нормальный — не стагнация и не stable_high
        analyzer = make_analyzer(("Физика", "Физика", [3.5, 4.0, 3.5, 4.0]))
        results = analyzer.analyze()
        assert results[0].status == DynamicStatus.STABLE

    def test_single_score_skipped(self):
        """Одна оценка — нет динамики, пропускается."""
        analyzer = make_analyzer(("Химия", "Химия", [4.0]))
        results = analyzer.analyze()
        assert results == []

    def test_empty_history_skipped(self):
        """Пустая история — пропускается."""
        analyzer = make_analyzer(("Биология", "Биология", []))
        results = analyzer.analyze()
        assert results == []

    def test_multiple_topics(self):
        """Несколько тем — каждая анализируется независимо."""
        analyzer = make_analyzer(
            ("Дроби", "Математика", [2, 2, 4, 5]),    # improvement
            ("Уравнения", "Математика", [5, 5, 2, 2]), # decline
        )
        results = analyzer.analyze()
        assert len(results) == 2
        statuses = {r.topic: r.status for r in results}
        assert statuses["Дроби"] == DynamicStatus.IMPROVEMENT
        assert statuses["Уравнения"] == DynamicStatus.DECLINE


# ─────────────────────────────────────────────
#  Тесты: дельта и avg
# ─────────────────────────────────────────────

class TestDeltaAndAvg:

    def test_delta_calculated_correctly(self):
        """delta = new_avg - old_avg."""
        # Половина по 2 числа: old=[2,2] avg=2, new=[4,4] avg=4 → delta=2
        analyzer = make_analyzer(("Тема", "Предмет", [2, 2, 4, 4]))
        result = analyzer.analyze()[0]
        assert result.old_avg == pytest.approx(2.0)
        assert result.new_avg == pytest.approx(4.0)
        assert result.delta == pytest.approx(2.0)

    def test_odd_count_split(self):
        """3 оценки: half=1 → old=[2], new=[4], средняя [3] не учитывается."""
        analyzer = make_analyzer(("Тема", "Предмет", [2, 3, 4]))
        result = analyzer.analyze()[0]
        assert result.old_avg == pytest.approx(2.0)
        assert result.new_avg == pytest.approx(4.0)

    def test_result_fields_populated(self):
        """Все поля TopicDynamicResult заполнены."""
        analyzer = make_analyzer(("Алгебра", "Математика", [3, 3, 5, 5]))
        result = analyzer.analyze()[0]
        assert result.topic == "Алгебра"
        assert result.subject == "Математика"
        assert result.count == 4
        assert len(result.score_sequence) == 4
        assert len(result.score_dates) == 4


# ─────────────────────────────────────────────
#  Тесты: рекомендации (XAI)
# ─────────────────────────────────────────────

class TestRecommendations:

    def test_decline_gives_high_priority(self):
        """Падение → рекомендация с приоритетом high."""
        analyzer = make_analyzer(("Тема", "Математика", [5, 5, 2, 2]))
        recs = analyzer.recommendations()
        assert len(recs) == 1
        assert recs[0].priority == "high"
        assert recs[0].status == DynamicStatus.DECLINE

    def test_stagnation_below_3_gives_high(self):
        """Стагнация ниже 3.0 → high приоритет."""
        analyzer = make_analyzer(("Дроби", "Математика", [2, 2, 2]))
        recs = analyzer.recommendations()
        assert recs[0].priority == "high"

    def test_stagnation_above_3_gives_medium(self):
        """Стагнация 3.0–3.5 → medium приоритет."""
        analyzer = make_analyzer(("Дроби", "Математика", [3.2, 3.0, 3.1]))
        recs = analyzer.recommendations()
        assert recs[0].priority == "medium"

    def test_improvement_gives_low_priority(self):
        """Улучшение → рекомендация с приоритетом low."""
        analyzer = make_analyzer(("Алгебра", "Математика", [2, 2, 5, 5]))
        recs = analyzer.recommendations()
        assert recs[0].priority == "low"

    def test_stable_high_gives_no_rec(self):
        """Стабильно высокий результат → рекомендации нет."""
        analyzer = make_analyzer(("Алгебра", "Математика", [5, 5, 5, 5]))
        recs = analyzer.recommendations()
        assert recs == []

    def test_stable_gives_no_rec(self):
        """Стабильный нормальный уровень → рекомендации нет."""
        analyzer = make_analyzer(("Алгебра", "Математика", [3.5, 4.0, 3.5, 4.0]))
        recs = analyzer.recommendations()
        assert recs == []

    def test_sort_order_high_before_medium(self):
        """Рекомендации отсортированы: high перед medium."""
        analyzer = make_analyzer(
            ("Тема А", "Предмет", [5, 5, 2, 2]),    # decline → high
            ("Тема Б", "Предмет", [3.2, 3.0, 3.1]),  # stagnation → medium
        )
        recs = analyzer.recommendations()
        priorities = [r.priority for r in recs]
        assert priorities.index("high") < priorities.index("medium")

    def test_rec_has_all_fields(self):
        """Рекомендация содержит все поля ExplainableRec."""
        analyzer = make_analyzer(("Дроби", "Математика", [2, 2, 2]))
        rec = analyzer.recommendations()[0]
        assert rec.recommendation
        assert rec.reason
        assert rec.evidence
        assert rec.topic == "Дроби"
        assert rec.priority in ("high", "medium", "low")
        assert rec.status

    def test_rec_format_text(self):
        """format_text() возвращает непустую строку."""
        rec = ExplainableRec(
            recommendation="Повторить тему.",
            reason="Балл снизился.",
            evidence="Последние работы: 2 → 2.",
            priority="high",
            topic="Дроби",
            status=DynamicStatus.DECLINE,
        )
        text = rec.format_text()
        assert "Рекомендация" in text
        assert "Причина" in text
        assert "Основание" in text


# ─────────────────────────────────────────────
#  Тесты: observations() — текстовые строки
# ─────────────────────────────────────────────

class TestObservations:

    def test_improvement_observation_contains_arrow(self):
        analyzer = make_analyzer(("Алгебра", "Математика", [2, 2, 5, 5]))
        obs = analyzer.observations()
        assert any("↑" in o for o in obs)

    def test_decline_observation_contains_arrow(self):
        analyzer = make_analyzer(("Алгебра", "Математика", [5, 5, 2, 2]))
        obs = analyzer.observations()
        assert any("↓" in o for o in obs)

    def test_stagnation_observation_contains_warning(self):
        analyzer = make_analyzer(("Дроби", "Математика", [2, 2, 2]))
        obs = analyzer.observations()
        assert any("⚠" in o for o in obs)

    def test_stable_high_observation_contains_check(self):
        analyzer = make_analyzer(("Алгебра", "Математика", [5, 5, 5, 5]))
        obs = analyzer.observations()
        assert any("✓" in o for o in obs)

    def test_stable_no_observation(self):
        """Статус stable не генерирует строку-наблюдение."""
        analyzer = make_analyzer(("Тема", "Предмет", [3.5, 4.0, 3.5, 4.0]))
        obs = analyzer.observations()
        assert obs == []

    def test_observations_mention_topic_name(self):
        """В наблюдении упоминается название темы."""
        analyzer = make_analyzer(("ТемаАBC", "Предмет", [2, 2, 5, 5]))
        obs = analyzer.observations()
        assert any("ТемаАBC" in o for o in obs)


# ─────────────────────────────────────────────
#  Тесты: get_topic_dynamics_dict
# ─────────────────────────────────────────────

class TestTopicDynamicsDict:

    def test_returns_all_topics(self):
        analyzer = make_analyzer(
            ("Дроби", "Математика", [2, 3, 4]),
            ("Алгебра", "Математика", [4, 5]),
        )
        d = analyzer.get_topic_dynamics_dict()
        assert "Дроби" in d
        assert "Алгебра" in d

    def test_values_are_date_score_pairs(self):
        dates = ["2024-01-01", "2024-01-08"]
        h = FakeHistory("Дроби", "Математика", [3.0, 4.0], dates)
        analyzer = DynamicsAnalyzer([h])
        d = analyzer.get_topic_dynamics_dict()
        assert d["Дроби"] == [("2024-01-01", 3.0), ("2024-01-08", 4.0)]


# ─────────────────────────────────────────────
#  Тесты: DynamicStatus.label
# ─────────────────────────────────────────────

class TestDynamicResultLabel:

    @pytest.mark.parametrize("status,expected", [
        (DynamicStatus.IMPROVEMENT, "улучшение"),
        (DynamicStatus.DECLINE,     "ухудшение"),
        (DynamicStatus.STAGNATION,  "стагнация"),
        (DynamicStatus.STABLE_HIGH, "стабильно высокий"),
        (DynamicStatus.STABLE,      "стабильно"),
        (DynamicStatus.NO_DATA,     "недостаточно данных"),
    ])
    def test_label(self, status, expected):
        result = TopicDynamicResult(
            topic="T", subject="S", status=status,
            old_avg=3.0, new_avg=3.5, score_sequence=[3, 4],
            score_dates=["2024-01-01", "2024-01-02"],
            count=2, delta=0.5,
        )
        assert result.label == expected


# ─────────────────────────────────────────────
#  Тесты: склонения (утилиты)
# ─────────────────────────────────────────────

class TestInflection:

    @pytest.mark.parametrize("n,expected", [
        (1, "работу"), (2, "работы"), (4, "работы"),
        (5, "работ"), (11, "работ"), (21, "работу"),
    ])
    def test_work_form(self, n, expected):
        assert _work_form(n) == expected

    @pytest.mark.parametrize("n,expected", [
        (1, "день"), (2, "дня"), (4, "дня"),
        (5, "дней"), (11, "дней"), (21, "день"),
    ])
    def test_day_form(self, n, expected):
        assert _day_form(n) == expected

    @pytest.mark.parametrize("n,expected", [
        (1, "неделю"), (2, "недели"), (4, "недели"),
        (5, "недель"), (11, "недель"), (21, "неделю"),
    ])
    def test_week_form(self, n, expected):
        assert _week_form(n) == expected

    @pytest.mark.parametrize("n,expected", [
        (1, "месяц"), (2, "месяца"), (4, "месяца"),
        (5, "месяцев"), (12, "месяцев"), (21, "месяц"),
    ])
    def test_month_form(self, n, expected):
        assert _month_form(n) == expected
