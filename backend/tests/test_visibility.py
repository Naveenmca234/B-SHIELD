import pytest
import numpy as np
import cv2
from ai.visibility import (
    compute_brightness,
    compute_contrast,
    compute_blur_score,
    analyze_visibility,
)


def test_compute_brightness():
    black = np.zeros((100, 100), dtype=np.uint8)
    white = np.ones((100, 100), dtype=np.uint8) * 255
    mid = np.ones((100, 100), dtype=np.uint8) * 128

    assert compute_brightness(black) == pytest.approx(0.0, abs=0.1)
    assert compute_brightness(white) == pytest.approx(100.0, abs=0.1)
    assert compute_brightness(mid) == pytest.approx(50.2, abs=0.5)


def test_compute_contrast():
    uniform = np.ones((100, 100), dtype=np.uint8) * 128
    assert compute_contrast(uniform) == pytest.approx(0.0, abs=0.1)

    # Checkerboard high contrast
    checker = np.zeros((100, 100), dtype=np.uint8)
    checker[::2, ::2] = 255
    checker[1::2, 1::2] = 255
    contrast = compute_contrast(checker)
    assert contrast > 50.0


def test_compute_blur():
    uniform = np.ones((100, 100), dtype=np.uint8) * 128
    assert compute_blur_score(uniform) == pytest.approx(0.0, abs=0.1)

    # Image with sharp alternating lines
    sharp = np.zeros((100, 100), dtype=np.uint8)
    sharp[:, ::2] = 255
    sharp_score = compute_blur_score(sharp)
    assert sharp_score > 20.0


def test_analyze_visibility_empty_or_none():
    res_none = analyze_visibility(None)
    assert res_none["visibilityStatus"] == "POOR"
    assert res_none["visibilityScore"] == 0

    res_empty = analyze_visibility(np.array([]))
    assert res_empty["visibilityStatus"] == "POOR"


def test_analyze_visibility_valid_frame():
    # Synthetic clean image: high contrast, sharp features, good brightness
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (180, 180), (200, 200, 200), -1)
    cv2.putText(img, "IBVAP", (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

    res = analyze_visibility(img)
    assert 0 <= res["brightnessScore"] <= 100
    assert 0 <= res["contrastScore"] <= 100
    assert 0 <= res["blurScore"] <= 100
    assert 0 <= res["visibilityScore"] <= 100
    assert res["visibilityStatus"] in ("CLEAR", "MODERATE", "POOR")
