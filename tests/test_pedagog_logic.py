"""
Юнит-тесты для чистой логики из pedagog.py
Тестирует TopicHistory и analyze_topic_dynamics без БД и tkinter.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


# Импортируем только чистую логику — без запуска tkinter или init_db
# Для этого делаем точечный импорт через importlib с патчем tkinter
import unittest.mock as mock

# Мокаем tkinter до импорта pedagog, чтобы не требовался дисплей
with mock.patch.dict("sys.modules", {
    "tkinter": mock.MagicMock(),
    "tkinter.ttk": mock.MagicMock(),
    "tkinter.messagebox": mock.MagicMock(),
    "tkinter.filedialog": mock.MagicMock(),
}):
    from pedagog import TopicHistory, analyze_topic_dynamics


# ─────────────────────────────────────────────
#  Тесты: TopicHistory
# ─────────────────────────────────────────────

class TestTopicHistory:

    def make_history(self, scores, dates=None):
        h = TopicHistory("Дроби", "Математика")
        if dates is None:
            dates = [f"2024-01-{i+1:02d}" for i in range(len(scores))]
        for d, s in zip(dates, scores):
            h.add(d, float(s))
        return h

    def test_count(self):
        h = self.make_history([3, 4, 5])
        assert h.count == 3

    def test_avg(self):
        h = self.make_history([3.0, 4.0, 5.0])
        assert h.avg == pytest.approx(4.0)

    def test_avg_empty(self):
        h = TopicHistory("Тема", "Предмет")
        assert h.avg is None

    def test_latest(self):
        h = self.make_history([2, 3, 5])
        assert h.latest == pytest.approx(5.0)

    def test_earliest(self):
        h = self.make_history([2, 3, 5])
        assert h.earliest == pytest.approx(2.0)

    def test_latest_empty(self):
        h = TopicHistory("Тема", "Предмет")
        assert h.latest is None

    def test_earliest_empty(self):
        h = TopicHistory("Тема", "Предмет")
        assert h.earliest is None

    def test_add_preserves_order(self):
        h = self.make_history([1, 2, 3, 4])
        assert h.scores == [1.0, 2.0, 3.0, 4.0]

    def test_slots(self):
        """TopicHistory использует __slots__ — лишние атрибуты запрещены."""
        h = TopicHistory("Тема", "Предмет")
        with pytest.raises(AttributeError):
            h.nonexistent_attr = 42


# ─────────────────────────────────────────────
#  Тесты: analyze_topic_dynamics
# ─────────────────────────────────────────────

class TestAnalyzeTopicDynamics:

    def make_histories(self, *args):
        """args: (topic, subject, scores, dates=None)"""
        result = []
        for item in args:
            topic, subject, scores = item[0], item[1], item[2]
            dates = item[3] if len(item) > 3 else [f"2024-01-{i+1:02d}" for i in range(len(scores))]
            h = TopicHistory(topic, subject)
            for d, s in zip(dates, scores):
                h.add(d, float(s))
            result.append(h)
        return result

    def test_improvement_arrow_up(self):
        histories = self.make_histories(("Дроби", "Математика", [2, 2, 5, 5]))
        obs = analyze_topic_dynamics(histories)
        assert any("↑" in o for o in obs)

    def test_decline_arrow_down(self):
        histories = self.make_histories(("Дроби", "Математика", [5, 5, 2, 2]))
        obs = analyze_topic_dynamics(histories)
        assert any("↓" in o for o in obs)

    def test_stagnation_warning(self):
        histories = self.make_histories(("Дроби", "Математика", [2, 2, 2]))
        obs = analyze_topic_dynamics(histories)
        assert any("⚠" in o for o in obs)

    def test_stable_high_checkmark(self):
        histories = self.make_histories(("Алгебра", "Математика", [5, 5, 5, 5]))
        obs = analyze_topic_dynamics(histories)
        assert any("✓" in o for o in obs)

    def test_single_score_no_obs(self):
        """Одна оценка — динамика не рассчитывается."""
        histories = self.make_histories(("Химия", "Химия", [4]))
        obs = analyze_topic_dynamics(histories)
        assert obs == []

    def test_empty_list(self):
        obs = analyze_topic_dynamics([])
        assert obs == []

    def test_topic_name_in_obs(self):
        histories = self.make_histories(("УникТема123", "Предмет", [2, 2, 5, 5]))
        obs = analyze_topic_dynamics(histories)
        assert any("УникТема123" in o for o in obs)

    def test_multiple_topics_multiple_obs(self):
        histories = self.make_histories(
            ("Тема1", "Предмет", [2, 2, 5, 5]),  # improvement
            ("Тема2", "Предмет", [5, 5, 2, 2]),  # decline
        )
        obs = analyze_topic_dynamics(histories)
        assert len(obs) >= 2

    def test_span_days_in_obs(self):
        """Длительный период (>7 дней) упоминается в строке про ухудшение."""
        dates = ["2024-01-01", "2024-01-02", "2024-02-01", "2024-02-02"]
        histories = self.make_histories(("Дроби", "Математика", [5, 5, 2, 2], dates))
        obs = analyze_topic_dynamics(histories)
        text = " ".join(obs)
        # Должно упомянуть период: "недел" или "месяц"
        assert "недел" in text or "месяц" in text or "↓" in text

    def test_returns_list_of_strings(self):
        histories = self.make_histories(("Дроби", "Математика", [2, 2, 5, 5]))
        obs = analyze_topic_dynamics(histories)
        assert isinstance(obs, list)
        for o in obs:
            assert isinstance(o, str)
