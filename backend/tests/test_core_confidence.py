# tests/test_core_confidence.py
from app.services.core.confidence import ConfidenceSystem


def test_combine_perfect():
    assert ConfidenceSystem.combine({"a": 1.0, "b": 1.0}) == 1.0


def test_combine_zero_factor():
    assert ConfidenceSystem.combine({"a": 1.0, "b": 0.0}) == 0.0


def test_combine_mixed_is_between():
    s = ConfidenceSystem.combine({"verification": 0.9, "model": 0.6})
    assert 0.6 < s < 0.9


def test_combine_empty():
    assert ConfidenceSystem.combine({}) == 0.0


def test_combine_clamps_out_of_range():
    assert ConfidenceSystem.combine({"a": 2.0}) == 1.0
    assert ConfidenceSystem.combine({"a": -1.0}) == 0.0


def test_combine_weights():
    s1 = ConfidenceSystem.combine({"a": 1.0, "b": 0.5}, weights={"a": 10.0, "b": 1.0})
    s2 = ConfidenceSystem.combine({"a": 1.0, "b": 0.5}, weights={"a": 1.0, "b": 10.0})
    assert s1 > s2


def test_escalate_threshold():
    assert ConfidenceSystem.escalate(0.5) is True
    assert ConfidenceSystem.escalate(0.8) is False
    assert ConfidenceSystem.escalate(0.7) is False
    assert ConfidenceSystem.escalate(0.5, threshold=0.4) is False
