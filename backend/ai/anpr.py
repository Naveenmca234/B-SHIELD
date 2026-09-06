"""
anpr.py
-------
Automatic Number Plate Recognition pipeline:
Vehicle bbox -> plate region candidate (edge/contour based plate localization)
-> crop -> preprocessing (grayscale, threshold, denoise) -> OCR (pytesseract)
-> plate text (regex-cleaned).

Requires the `tesseract-ocr` system binary for pytesseract to work. If it is
not installed on the host, `run_ocr()` catches the failure and returns None
with a clear reason so the API layer can surface a real error state instead
of fabricating a plate number (per spec section 34: gracefully handle OCR
failure; section 39: never fake functionality).
"""
import re
import cv2
import numpy as np

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False

PLATE_CLEAN_RE = re.compile(r"[^A-Z0-9]")


def locate_plate_region(vehicle_crop: np.ndarray):
    """
    Real candidate localization using edge detection + contour geometry
    (classic plate-finding heuristic: look for a rectangular high-edge-density
    region with a plausible plate aspect ratio ~2:1 to 5:1).
    """
    if vehicle_crop is None or vehicle_crop.size == 0:
        return None

    gray = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(gray, 30, 200)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if h == 0:
            continue
        aspect_ratio = w / float(h)
        if 2.0 <= aspect_ratio <= 6.0 and w > 40 and h > 12:
            return {"x": x, "y": y, "w": w, "h": h}

    return None


def preprocess_plate(plate_crop: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def run_ocr(preprocessed_plate: np.ndarray):
    """Returns (plate_text, confidence) or (None, 0) on failure."""
    if not TESSERACT_AVAILABLE:
        return None, 0.0
    try:
        config = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        data = pytesseract.image_to_data(
            preprocessed_plate, config=config, output_type=pytesseract.Output.DICT
        )
        texts, confs = [], []
        for t, c in zip(data["text"], data["conf"]):
            t = t.strip()
            if t:
                texts.append(t)
                try:
                    confs.append(float(c))
                except ValueError:
                    pass
        raw_text = PLATE_CLEAN_RE.sub("", "".join(texts).upper())
        avg_conf = round(sum(confs) / len(confs), 1) if confs else 0.0
        if len(raw_text) < 4:
            return None, 0.0
        return raw_text, avg_conf
    except Exception:
        return None, 0.0


def process_vehicle_for_plate(frame: np.ndarray, vehicle_bbox: dict):
    """
    Full pipeline for one detected vehicle bounding box.
    Returns dict: {plateNumber, ocrConfidence, plateBbox} or
    {plateNumber: None, ocrConfidence: 0, reason: '...'} on failure.
    """
    x, y, w, h = vehicle_bbox["x"], vehicle_bbox["y"], vehicle_bbox["w"], vehicle_bbox["h"]
    x, y = max(0, x), max(0, y)
    vehicle_crop = frame[y:y + h, x:x + w]

    plate_region = locate_plate_region(vehicle_crop)
    if plate_region is None:
        return {
            "plateNumber": None,
            "ocrConfidence": 0.0,
            "status": "PLATE_NOT_LOCATED",
            "reason": "No plate candidate region detected on vehicle",
        }

    px, py, pw, ph = plate_region["x"], plate_region["y"], plate_region["w"], plate_region["h"]
    plate_crop = vehicle_crop[py:py + ph, px:px + pw]
    if plate_crop.size == 0:
        return {
            "plateNumber": None,
            "ocrConfidence": 0.0,
            "status": "PLATE_NOT_LOCATED",
            "reason": "Empty plate candidate crop",
        }

    if not TESSERACT_AVAILABLE:
        return {
            "plateNumber": None,
            "ocrConfidence": 0.0,
            "status": "OCR_UNAVAILABLE",
            "reason": "Tesseract OCR engine not installed on host",
        }

    preprocessed = preprocess_plate(plate_crop)
    plate_text, confidence = run_ocr(preprocessed)

    if plate_text is None:
        return {
            "plateNumber": None,
            "ocrConfidence": 0.0,
            "status": "PLATE_NOT_READ",
            "reason": "OCR could not discern alphanumeric characters",
        }

    status = "RECOGNIZED" if confidence >= 50.0 else "LOW_CONFIDENCE"
    return {
        "plateNumber": plate_text,
        "ocrConfidence": confidence,
        "status": status,
        "reason": f"Optical reading completed with {confidence}% confidence",
        "plateBbox": {"x": x + px, "y": y + py, "w": pw, "h": ph},
    }

