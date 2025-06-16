import time
from app.handlers.utils import format_duration


def test_format_duration_seconds(monkeypatch):
    fake_start = 100.0
    # Simulate time.monotonic() returns 105.7 (5.7 seconds later)
    monkeypatch.setattr(time, "monotonic", lambda: 105.7)
    assert format_duration(fake_start) == "5 сек."


def test_format_duration_exact_minute(monkeypatch):
    fake_start = 50.0
    # Simulate time.monotonic() returns 110.0 (60 seconds later)
    monkeypatch.setattr(time, "monotonic", lambda: 110.0)
    assert format_duration(fake_start) == "1 мин. 0 сек."


def test_format_duration_minutes_and_seconds(monkeypatch):
    fake_start = 0.0
    # Simulate time.monotonic() returns 125.0 (2 min 5 sec)
    monkeypatch.setattr(time, "monotonic", lambda: 125.0)
    assert format_duration(fake_start) == "2 мин. 5 сек."


def test_format_duration_zero_seconds(monkeypatch):
    fake_start = 200.0
    # Simulate time.monotonic() returns 200.0 (0 seconds later)
    monkeypatch.setattr(time, "monotonic", lambda: 200.0)
    assert format_duration(fake_start) == "0 сек."
