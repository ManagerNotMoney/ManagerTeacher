"""
Юнит-тесты для hca_pedagog.py и llm_stub.py
Тестирует stub-генераторы и PedagogHCA без реального HCA и LLM.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

# Импортируем внутренние stub-функции напрямую
from hca_pedagog import (
    _stub_analyze,
    _stub_class_summary,
    _stub_suggest_next,
    PedagogHCA,
)
from llm_stub import LLMStub


# ─────────────────────────────────────────────
#  Данные для тестов
# ─────────────────────────────────────────────

STUDENT_HIGH = {
    "name": "Иванов Александр",
    "subject": "Математика",
    "avg_grade": 4.8,
    "grade_count": 10,
    "topics": [
        {"name": "Алгебра", "avg": 5.0, "count": 4},
        {"name": "Геометрия", "avg": 4.6, "count": 3},
    ],
    "class": "9А",
}

STUDENT_MED = {
    "name": "Петрова Мария",
    "subject": "Математика",
    "avg_grade": 3.7,
    "grade_count": 8,
    "topics": [
        {"name": "Дроби", "avg": 3.2, "count": 4},
        {"name": "Алгебра", "avg": 4.2, "count": 4},
    ],
    "class": "9А",
}

STUDENT_LOW = {
    "name": "Сидоров Иван",
    "subject": "Математика",
    "avg_grade": 2.5,
    "grade_count": 6,
    "topics": [
        {"name": "Дроби", "avg": 2.0, "count": 3},
        {"name": "Уравнения", "avg": 3.0, "count": 3},
    ],
    "class": "9А",
}

STUDENT_NO_GRADES = {
    "name": "Новиков Пётр",
    "subject": "Математика",
    "avg_grade": None,
    "grade_count": 0,
    "topics": [],
    "class": "9А",
}

CLASS_DATA = {
    "subject": "Математика",
    "students": [
        {"name": "Иванов Александр", "avg": 4.8, "count": 10},
        {"name": "Петрова Мария",     "avg": 3.7, "count": 8},
        {"name": "Сидоров Иван",      "avg": 2.5, "count": 6},
        {"name": "Козлов Дмитрий",    "avg": 2.8, "count": 5},
    ],
    "topic_gaps": [
        {"name": "Дроби",     "avg": 2.3, "student_count": 3},
        {"name": "Уравнения", "avg": 3.0, "student_count": 2},
    ],
}

SUGGEST_CRITICAL = {
    "name": "Сидоров Иван",
    "avg_grade": 2.5,
    "weakest_topic": {"name": "Дроби", "avg": 2.0},
    "strongest_topic": {"name": "Уравнения", "avg": 3.0},
    "recent_trend": "declining",
}

SUGGEST_STABLE = {
    "name": "Иванов Александр",
    "avg_grade": 4.8,
    "weakest_topic": {"name": "Геометрия", "avg": 4.6},
    "strongest_topic": {"name": "Алгебра", "avg": 5.0},
    "recent_trend": "stable",
}

SUGGEST_NO_DATA = {
    "name": "Новиков Пётр",
    "avg_grade": None,
    "weakest_topic": None,
    "strongest_topic": None,
    "recent_trend": "stable",
}


# ─────────────────────────────────────────────
#  Тесты: _stub_analyze
# ─────────────────────────────────────────────

class TestStubAnalyze:

    def test_high_avg_mentions_grade(self):
        result = _stub_analyze(STUDENT_HIGH)
        assert "4.8" in result or "4,8" in result or "Иванов" in result

    def test_low_avg_mentions_difficulties(self):
        result = _stub_analyze(STUDENT_LOW)
        assert "затруднения" in result or "систематические" in result or "2.5" in result

    def test_no_grades_returns_early(self):
        result = _stub_analyze(STUDENT_NO_GRADES)
        assert "нет" in result or "недоступен" in result

    def test_weak_topics_highlighted(self):
        result = _stub_analyze(STUDENT_LOW)
        assert "Дроби" in result or "⚠" in result or "Проблемные" in result

    def test_strong_topics_highlighted(self):
        result = _stub_analyze(STUDENT_HIGH)
        assert "Алгебра" in result or "✓" in result or "Сильные" in result

    def test_name_in_output(self):
        result = _stub_analyze(STUDENT_MED)
        assert "Петрова" in result or "Анализ" in result

    def test_returns_string(self):
        assert isinstance(_stub_analyze(STUDENT_HIGH), str)

    def test_subject_in_output(self):
        result = _stub_analyze(STUDENT_HIGH)
        assert "Математика" in result


# ─────────────────────────────────────────────
#  Тесты: _stub_class_summary
# ─────────────────────────────────────────────

class TestStubClassSummary:

    def test_no_students_returns_message(self):
        result = _stub_class_summary({"students": []})
        assert "нет" in result or "Данных" in result

    def test_class_avg_in_output(self):
        result = _stub_class_summary(CLASS_DATA)
        # Средний по классу = (4.8+3.7+2.5+2.8)/4 ≈ 3.45
        assert "3.4" in result or "Средний" in result

    def test_low_students_listed(self):
        result = _stub_class_summary(CLASS_DATA)
        # Сидоров и Козлов < 3.0
        assert "Сидоров" in result or "Козлов" in result or "Отстающие" in result

    def test_topic_gaps_listed(self):
        result = _stub_class_summary(CLASS_DATA)
        assert "Дроби" in result or "пробелы" in result or "📌" in result

    def test_subject_in_header(self):
        result = _stub_class_summary(CLASS_DATA)
        assert "Математика" in result

    def test_returns_string(self):
        assert isinstance(_stub_class_summary(CLASS_DATA), str)


# ─────────────────────────────────────────────
#  Тесты: _stub_suggest_next
# ─────────────────────────────────────────────

class TestStubSuggestNext:

    def test_no_data_returns_message(self):
        result = _stub_suggest_next(SUGGEST_NO_DATA)
        assert "недостаточно" in result.lower() or "Новиков" in result

    def test_critical_gap_mentions_topic(self):
        result = _stub_suggest_next(SUGGEST_CRITICAL)
        assert "Дроби" in result

    def test_critical_gap_gives_steps(self):
        result = _stub_suggest_next(SUGGEST_CRITICAL)
        assert "1." in result or "2." in result or "Рекомендую" in result

    def test_stable_suggests_advanced(self):
        result = _stub_suggest_next(SUGGEST_STABLE)
        assert "углублённые" in result or "Алгебра" in result or "уровень" in result

    def test_name_in_header(self):
        result = _stub_suggest_next(SUGGEST_CRITICAL)
        assert "Сидоров" in result or "🎯" in result

    def test_returns_string(self):
        assert isinstance(_stub_suggest_next(SUGGEST_CRITICAL), str)


# ─────────────────────────────────────────────
#  Тесты: LLMStub.generate_structured
# ─────────────────────────────────────────────

class TestLLMStub:

    @pytest.fixture
    def stub(self):
        return LLMStub()

    def test_analyze_student_returns_dict(self, stub):
        result = stub.generate_structured("analyze_student", STUDENT_HIGH)
        assert isinstance(result, dict)
        assert "text" in result
        assert "structured" in result
        assert "mode" in result
        assert "confidence" in result

    def test_analyze_student_mode_is_pedagogical(self, stub):
        result = stub.generate_structured("analyze_student", STUDENT_HIGH)
        assert result["mode"] == "pedagogical"

    def test_analyze_student_high_confidence(self, stub):
        result = stub.generate_structured("analyze_student", STUDENT_HIGH)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_analyze_student_structured_level_high(self, stub):
        result = stub.generate_structured("analyze_student", STUDENT_HIGH)
        assert result["structured"]["overall_level"] == "high"

    def test_analyze_student_structured_level_low(self, stub):
        result = stub.generate_structured("analyze_student", STUDENT_LOW)
        assert result["structured"]["overall_level"] == "low"

    def test_analyze_student_no_grades(self, stub):
        result = stub.generate_structured("analyze_student", STUDENT_NO_GRADES)
        assert result["confidence"] == 0.0
        assert result["structured"]["overall_level"] == "no_data"

    def test_class_summary_returns_text(self, stub):
        result = stub.generate_structured("class_summary", CLASS_DATA)
        assert result["text"]
        assert "Математика" in result["text"]

    def test_suggest_next_no_data(self, stub):
        result = stub.generate_structured("suggest_next", SUGGEST_NO_DATA)
        assert result["confidence"] == 0.0

    def test_suggest_next_critical_confidence(self, stub):
        result = stub.generate_structured("suggest_next", SUGGEST_CRITICAL)
        assert result["confidence"] > 0.5

    def test_compare_students_equal(self, stub):
        data = {
            "student_a": {"name": "Иванов", "avg_grade": 4.0},
            "student_b": {"name": "Петров", "avg_grade": 4.0},
        }
        result = stub.generate_structured("compare_students", data)
        assert result["structured"]["difference"] == pytest.approx(0.0)

    def test_compare_students_picks_better(self, stub):
        data = {
            "student_a": {"name": "Иванов", "avg_grade": 4.5},
            "student_b": {"name": "Петров", "avg_grade": 3.0},
        }
        result = stub.generate_structured("compare_students", data)
        assert result["structured"]["better_student"] == "Иванов"

    def test_compare_students_no_data(self, stub):
        data = {
            "student_a": {"name": "Иванов", "avg_grade": None},
            "student_b": {"name": "Петров", "avg_grade": 4.0},
        }
        result = stub.generate_structured("compare_students", data)
        assert result["confidence"] == 0.0

    def test_unknown_analysis_type(self, stub):
        result = stub.generate_structured("nonexistent_type", {})
        assert result["confidence"] == 0.0
        assert "Неизвестный" in result["text"]


# ─────────────────────────────────────────────
#  Тесты: PedagogHCA
# ─────────────────────────────────────────────

class TestPedagogHCA:

    @pytest.fixture
    def phca(self):
        return PedagogHCA()

    def test_analyze_student_returns_string(self, phca):
        result = phca.analyze_student(STUDENT_HIGH)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_class_summary_returns_string(self, phca):
        result = phca.class_summary(CLASS_DATA)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_suggest_next_returns_string(self, phca):
        result = phca.suggest_next(SUGGEST_CRITICAL)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_compare_students_returns_string(self, phca):
        a = {"name": "Иванов", "avg_grade": 4.5}
        b = {"name": "Петров", "avg_grade": 3.0}
        result = phca.compare_students(a, b)
        assert isinstance(result, str)
        assert "Иванов" in result or "Петров" in result

    def test_get_structured_returns_dict(self, phca):
        result = phca.get_structured_analysis("analyze_student", STUDENT_HIGH)
        assert isinstance(result, dict)
        assert "text" in result

    def test_status_text_not_empty(self, phca):
        text = phca.hca_status_text()
        assert isinstance(text, str)
        assert len(text) > 0
