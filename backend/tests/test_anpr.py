import numpy as np
from ai.anpr import (
    locate_plate_region,
    process_vehicle_for_plate,
)


def test_locate_plate_region_empty():
    assert locate_plate_region(None) is None
    assert locate_plate_region(np.zeros((0, 0, 3), dtype=np.uint8)) is None


def test_process_vehicle_no_plate():
    # Solid black vehicle crop with no plate features
    frame = np.zeros((400, 400, 3), dtype=np.uint8)
    vehicle_bbox = {"x": 50, "y": 50, "w": 300, "h": 300}
    res = process_vehicle_for_plate(frame, vehicle_bbox)

    assert res["plateNumber"] is None
    assert res["ocrConfidence"] == 0.0
    assert res["status"] in ("PLATE_NOT_LOCATED", "OCR_UNAVAILABLE")
    assert "reason" in res


def test_process_vehicle_synthetic_plate():
    # Draw a synthetic high-contrast plate rectangle
    frame = np.ones((400, 600, 3), dtype=np.uint8) * 120
    # Vehicle bbox
    vx, vy, vw, vh = 50, 50, 500, 300
    # Plate rectangle inside vehicle: aspect ratio 3:1 (width 120, height 40)
    px, py, pw, ph = 200, 200, 120, 40
    frame[vy + py : vy + py + ph, vx + px : vx + px + pw] = 255
    # Dark border
    frame[vy + py : vy + py + 2, vx + px : vx + px + pw] = 0
    frame[vy + py + ph - 2 : vy + py + ph, vx + px : vx + px + pw] = 0

    vehicle_bbox = {"x": vx, "y": vy, "w": vw, "h": vh}
    res = process_vehicle_for_plate(frame, vehicle_bbox)

    assert res["status"] in ("RECOGNIZED", "LOW_CONFIDENCE", "PLATE_NOT_READ", "OCR_UNAVAILABLE", "PLATE_NOT_LOCATED")
    # Must never fabricate an arbitrary plate number when OCR cannot discern
    if res["status"] in ("PLATE_NOT_READ", "OCR_UNAVAILABLE", "PLATE_NOT_LOCATED"):
        assert res["plateNumber"] is None
