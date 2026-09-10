from ai.prediction import TrajectoryPredictor, _line_intersects_segment


def test_line_intersects_segment():
    # Crossing plus: (0, 1)-(2, 1) and (1, 0)-(1, 2)
    assert _line_intersects_segment((0.0, 1.0), (2.0, 1.0), (1.0, 0.0), (1.0, 2.0)) is True

    # Parallel lines: (0, 0)-(1, 0) and (0, 1)-(1, 1)
    assert _line_intersects_segment((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)) is False


def test_trajectory_predictor_single_observation():
    predictor = TrajectoryPredictor()
    fence = [{"x": 0.5, "y": 0.5}, {"x": 0.9, "y": 0.5}, {"x": 0.9, "y": 0.9}, {"x": 0.5, "y": 0.9}]

    res = predictor.update_and_predict(
        track_id=1,
        bbox={"x": 100, "y": 100, "w": 50, "h": 100},
        frame_w=1000,
        frame_h=1000,
        fence_polygon=fence,
        timestamp=1.0,
    )
    # Needs at least 2 points to calculate velocity vector
    assert res["status"] == "NO_CONFLICT"
    assert res["velocity"] == 0.0


def test_trajectory_predictor_approaching_fence():
    predictor = TrajectoryPredictor(projection_horizon=3.0)
    # Fence in lower half: (0.4, 0.6) to (0.8, 0.8)
    fence = [{"x": 0.4, "y": 0.6}, {"x": 0.8, "y": 0.6}, {"x": 0.8, "y": 0.9}, {"x": 0.4, "y": 0.9}]

    # 3 Observations moving downwards towards fence
    predictor.update_and_predict(
        track_id=10,
        bbox={"x": 500, "y": 200, "w": 50, "h": 100},
        frame_w=1000,
        frame_h=1000,
        fence_polygon=fence,
        timestamp=1.0,
    )
    predictor.update_and_predict(
        track_id=10,
        bbox={"x": 500, "y": 300, "w": 50, "h": 100},
        frame_w=1000,
        frame_h=1000,
        fence_polygon=fence,
        timestamp=1.5,
    )
    res3 = predictor.update_and_predict(
        track_id=10,
        bbox={"x": 500, "y": 400, "w": 50, "h": 100},
        frame_w=1000,
        frame_h=1000,
        fence_polygon=fence,
        timestamp=2.0,
    )

    assert res3["velocity"] > 0.0
    assert res3["status"] in ("PREDICTED_ZONE_ENTRY", "APPROACHING_RESTRICTED_ZONE")
    assert "trajectory" in res3["explanation"].lower()


def test_trajectory_predictor_moving_away():
    predictor = TrajectoryPredictor(projection_horizon=2.0)
    fence = [{"x": 0.4, "y": 0.6}, {"x": 0.8, "y": 0.6}, {"x": 0.8, "y": 0.9}, {"x": 0.4, "y": 0.9}]

    # Object moving upwards away from fence across 3 observations
    predictor.update_and_predict(
        track_id=20,
        bbox={"x": 500, "y": 400, "w": 50, "h": 100},
        frame_w=1000,
        frame_h=1000,
        fence_polygon=fence,
        timestamp=1.0,
    )
    predictor.update_and_predict(
        track_id=20,
        bbox={"x": 500, "y": 300, "w": 50, "h": 100},
        frame_w=1000,
        frame_h=1000,
        fence_polygon=fence,
        timestamp=1.5,
    )
    res = predictor.update_and_predict(
        track_id=20,
        bbox={"x": 500, "y": 200, "w": 50, "h": 100},
        frame_w=1000,
        frame_h=1000,
        fence_polygon=fence,
        timestamp=2.0,
    )
    assert res["status"] == "NO_CONFLICT"
    assert res["velocity"] > 0.0
