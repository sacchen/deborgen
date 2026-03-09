from datetime import datetime

from deborgen.worker.agent import is_within_work_hours

def test_no_work_hours() -> None:
    now = datetime(2026, 1, 1, 12, 0)
    assert is_within_work_hours(now, None) is True
    assert is_within_work_hours(now, "") is True

def test_invalid_work_hours() -> None:
    now = datetime(2026, 1, 1, 12, 0)
    # Should fall back to True on invalid format
    assert is_within_work_hours(now, "invalid") is True
    assert is_within_work_hours(now, "12-14") is True
    assert is_within_work_hours(now, "25:00-26:00") is True

def test_same_day_window() -> None:
    window = "09:00-17:00"
    
    # Before window
    assert is_within_work_hours(datetime(2026, 1, 1, 8, 59), window) is False
    
    # Inside window
    assert is_within_work_hours(datetime(2026, 1, 1, 9, 0), window) is True
    assert is_within_work_hours(datetime(2026, 1, 1, 12, 0), window) is True
    assert is_within_work_hours(datetime(2026, 1, 1, 17, 0), window) is True
    
    # After window
    assert is_within_work_hours(datetime(2026, 1, 1, 17, 1), window) is False

def test_spanning_midnight_window() -> None:
    window = "22:00-08:00"
    
    # Before window (daytime)
    assert is_within_work_hours(datetime(2026, 1, 1, 21, 59), window) is False
    
    # Inside window (evening before midnight)
    assert is_within_work_hours(datetime(2026, 1, 1, 22, 0), window) is True
    assert is_within_work_hours(datetime(2026, 1, 1, 23, 59), window) is True
    
    # Inside window (morning after midnight)
    assert is_within_work_hours(datetime(2026, 1, 2, 0, 0), window) is True
    assert is_within_work_hours(datetime(2026, 1, 2, 7, 59), window) is True
    assert is_within_work_hours(datetime(2026, 1, 2, 8, 0), window) is True
    
    # After window (daytime)
    assert is_within_work_hours(datetime(2026, 1, 2, 8, 1), window) is False
