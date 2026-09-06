"""
visibility.py
--------------
Analyzes a video frame for image quality: brightness, contrast, blur.
Produces a combined visibility score (0-100) and a status of
CLEAR / MODERATE / POOR.

This is REAL, working image analysis (not simulated) using OpenCV.
It does not (and cannot) claim to detect a person hidden by fog/rain -
it only reports how reliable direct object detection is likely to be
in the current frame, per the platform's core design principle:
"Rain/fog alone must NEVER generate a critical intrusion alert."
"""
import cv2
import numpy as np


def compute_brightness(gray_frame: np.ndarray) -> float:
    """Mean pixel intensity, normalized to 0-100."""
    return float(np.mean(gray_frame)) / 255.0 * 100.0


def compute_contrast(gray_frame: np.ndarray) -> float:
    """Standard deviation of pixel intensity, normalized to 0-100."""
    std = float(np.std(gray_frame))
    # Typical std for a well-exposed frame is ~40-70; scale accordingly.
    return min(100.0, (std / 64.0) * 100.0)


def compute_blur_score(gray_frame: np.ndarray) -> float:
    """
    Variance of the Laplacian - a common, real, well-established sharpness
    metric. Higher = sharper. Normalized to a 0-100 'sharpness' score.
    """
    lap_var = cv2.Laplacian(gray_frame, cv2.CV_64F).var()
    # Empirically, lap_var > 300 is quite sharp, < 50 is very blurry.
    score = min(100.0, (lap_var / 300.0) * 100.0)
    return float(score)


def analyze_visibility(frame: np.ndarray, clear_threshold: int = 70, moderate_threshold: int = 40) -> dict:
    """
    Returns:
    {
        brightnessScore, contrastScore, blurScore,
        visibilityScore, visibilityStatus
    }
    """
    if frame is None or frame.size == 0:
        return {
            "brightnessScore": 0, "contrastScore": 0, "blurScore": 0,
            "visibilityScore": 0, "visibilityStatus": "POOR",
        }

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    brightness = compute_brightness(gray)
    contrast = compute_contrast(gray)
    blur = compute_blur_score(gray)

    # Penalize both over- and under-exposure (brightness far from mid-range).
    brightness_quality = 100.0 - abs(brightness - 50.0) * 1.6
    brightness_quality = max(0.0, min(100.0, brightness_quality))

    visibility_score = (brightness_quality * 0.35) + (contrast * 0.25) + (blur * 0.40)
    visibility_score = round(max(0.0, min(100.0, visibility_score)), 1)

    if visibility_score >= clear_threshold:
        status = "CLEAR"
    elif visibility_score >= moderate_threshold:
        status = "MODERATE"
    else:
        status = "POOR"

    return {
        "brightnessScore": round(brightness, 1),
        "contrastScore": round(contrast, 1),
        "blurScore": round(blur, 1),
        "visibilityScore": visibility_score,
        "visibilityStatus": status,
    }
