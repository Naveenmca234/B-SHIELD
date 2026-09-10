from ai.intrusion import point_in_polygon, check_fence_crossing


def test_point_in_polygon_square():
    # Square from (0.2, 0.2) to (0.8, 0.8)
    square = [
        {"x": 0.2, "y": 0.2},
        {"x": 0.8, "y": 0.2},
        {"x": 0.8, "y": 0.8},
        {"x": 0.2, "y": 0.8},
    ]

    # Center point is inside
    assert point_in_polygon(0.5, 0.5, square) is True

    # Far point is outside
    assert point_in_polygon(0.1, 0.5, square) is False
    assert point_in_polygon(0.9, 0.9, square) is False


def test_point_in_polygon_invalid():
    assert point_in_polygon(0.5, 0.5, []) is False
    assert point_in_polygon(0.5, 0.5, [{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}]) is False


def test_check_fence_crossing():
    fence = [
        {"x": 0.25, "y": 0.5},
        {"x": 0.75, "y": 0.5},
        {"x": 0.75, "y": 1.0},
        {"x": 0.25, "y": 1.0},
    ]
    frame_w = 1000
    frame_h = 1000

    # Person with feet at (500, 750) -> normalized (0.5, 0.75) -> inside fence
    # x=450, w=100 -> foot_x = 500
    # y=600, h=150 -> foot_y = 750
    inside_bbox = {"x": 450, "y": 600, "w": 100, "h": 150}
    assert check_fence_crossing(inside_bbox, frame_w, frame_h, fence) is True

    # Person with feet at (100, 300) -> normalized (0.1, 0.3) -> outside fence
    outside_bbox = {"x": 50, "y": 100, "w": 100, "h": 200}
    assert check_fence_crossing(outside_bbox, frame_w, frame_h, fence) is False


def test_loitering_detector():
    from ai.intrusion import LoiteringDetector

    detector = LoiteringDetector(dwell_threshold_seconds=5.0)
    fence = [
        {"x": 0.2, "y": 0.2},
        {"x": 0.8, "y": 0.2},
        {"x": 0.8, "y": 0.8},
        {"x": 0.2, "y": 0.8},
    ]

    # Inside bbox
    inside_bbox = {"x": 450, "y": 450, "w": 100, "h": 100}
    # Outside bbox
    outside_bbox = {"x": 50, "y": 50, "w": 100, "h": 100}

    # Time 100.0: enters
    res = detector.update(track_id=1, bbox=inside_bbox, frame_w=1000, frame_h=1000, fence_polygon=fence, timestamp=100.0)
    assert res["is_loitering"] is False
    assert res["dwell_seconds"] == 0.0

    # Time 104.0: still inside (4 seconds, threshold 5.0)
    res = detector.update(track_id=1, bbox=inside_bbox, frame_w=1000, frame_h=1000, fence_polygon=fence, timestamp=104.0)
    assert res["is_loitering"] is False
    assert res["dwell_seconds"] == 4.0

    # Time 106.0: threshold exceeded
    res = detector.update(track_id=1, bbox=inside_bbox, frame_w=1000, frame_h=1000, fence_polygon=fence, timestamp=106.0)
    assert res["is_loitering"] is True
    assert res["dwell_seconds"] == 6.0

    # Leaves zone -> reset
    res = detector.update(track_id=1, bbox=outside_bbox, frame_w=1000, frame_h=1000, fence_polygon=fence, timestamp=107.0)
    assert res["is_loitering"] is False
    assert res["dwell_seconds"] == 0.0

    # Re-enters -> new dwell period
    res = detector.update(track_id=1, bbox=inside_bbox, frame_w=1000, frame_h=1000, fence_polygon=fence, timestamp=108.0)
    assert res["is_loitering"] is False
    assert res["dwell_seconds"] == 0.0


