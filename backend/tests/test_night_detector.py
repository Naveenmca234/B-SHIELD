import numpy as np
from ai.night_detector import detect_night_condition, _is_clock_night


def test_detect_night_condition_empty():
    res = detect_night_condition(None)
    assert res["isNight"] is False
    assert "No frame data" in res["reason"]


def test_detect_night_condition_day():
    # Bright daylight frame (luminance > 55)
    day = np.ones((100, 100, 3), dtype=np.uint8) * 200
    res = detect_night_condition(day)
    assert res["isNight"] is False
    assert res["luminance"] > 55.0
    assert "daylight" in res["reason"].lower()


def test_detect_night_condition_night():
    # Dark night frame (luminance < 35)
    night = np.ones((100, 100, 3), dtype=np.uint8) * 30
    res = detect_night_condition(night)
    assert res["isNight"] is True
    assert res["luminance"] < 35.0
    assert "night/low-light" in res["reason"].lower()


def test_is_clock_night():
    # Normal overnight range 18:30 -> 06:00
    assert _is_clock_night("00:00", "23:59") is True
