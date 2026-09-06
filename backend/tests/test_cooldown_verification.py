import pytest
from config import settings


def test_per_intruder_cooldown_behavior():
    cooldown_map = {}

    def check_alert(cam_id, event_type, track_id, current_time):
        tid = track_id if track_id is not None else "cam"
        key = f"{cam_id}:{event_type}:{tid}"
        last = cooldown_map.get(key, 0)
        if current_time - last < settings.ALERT_COOLDOWN_SECONDS:
            return False, key
        cooldown_map[key] = current_time
        return True, key

    t0 = 1000.0

    # 1. Person A (track 1) enters
    allowed_a1, key_a = check_alert("BOP-01", "INTRUSION_DETECTED", 1, t0)
    assert allowed_a1 is True
    assert key_a == "BOP-01:INTRUSION_DETECTED:1"

    # 2. Person B (track 2) enters 3 seconds later (well within 20s cooldown)
    t1 = t0 + 3.0
    allowed_b, key_b = check_alert("BOP-01", "INTRUSION_DETECTED", 2, t1)
    assert allowed_b is True
    assert key_b == "BOP-01:INTRUSION_DETECTED:2"

    # 3. Person A duplicate detected 5 seconds after initial detection
    t2 = t0 + 5.0
    allowed_a2, _ = check_alert("BOP-01", "INTRUSION_DETECTED", 1, t2)
    assert allowed_a2 is False  # Suppressed!

    # 4. Person A detected after cooldown window has elapsed (25 seconds later)
    t3 = t0 + 25.0
    allowed_a3, _ = check_alert("BOP-01", "INTRUSION_DETECTED", 1, t3)
    assert allowed_a3 is True  # Allowed!
