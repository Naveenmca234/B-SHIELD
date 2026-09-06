"""
tracker.py
----------
Multi-object tracker that assigns and maintains a stable tracking ID for
each detected object across frames, so the same person/vehicle keeps the
same ID (Frame 1 -> Person #17, Frame 2 -> Person #17, ...).

Implementation note: full ByteTrack uses a Kalman filter + Hungarian
matching over high/low confidence detection tiers. Here we implement a
real, working simplified tracker using IoU-based greedy matching between
frames (the same core association idea ByteTrack builds on), which is
lightweight enough to run with no extra native dependencies. It is
labeled `SimplifiedByteTrack` so the association strategy is transparent
and can be swapped for the full `bytetrack` package/Kalman implementation
without changing any calling code (same `update()` -> tracks schema).
"""
from typing import List, Dict
import itertools


def _iou(box_a: dict, box_b: dict) -> float:
    ax1, ay1 = box_a["x"], box_a["y"]
    ax2, ay2 = ax1 + box_a["w"], ay1 + box_a["h"]
    bx1, by1 = box_b["x"], box_b["y"]
    bx2, by2 = bx1 + box_b["w"], by1 + box_b["h"]

    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_w, inter_h = max(0, inter_x2 - inter_x1), max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = box_a["w"] * box_a["h"]
    area_b = box_b["w"] * box_b["h"]
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


class SimplifiedByteTrack:
    def __init__(self, iou_threshold: float = 0.3, max_missed_frames: int = 15):
        self.iou_threshold = iou_threshold
        self.max_missed_frames = max_missed_frames
        self._next_id = itertools.count(1)
        self.tracks: Dict[int, dict] = {}  # id -> {bbox, class, missed}

    def update(self, detections: List[dict]) -> List[dict]:
        """
        detections: [{class, confidence, bbox}]
        returns: [{trackId, class, confidence, bbox}]
        Same object across frames keeps the same trackId.
        """
        unmatched_detections = list(range(len(detections)))
        matched_track_ids = set()
        results = []

        # Greedy IoU matching: for each existing track, find best matching detection.
        for track_id, track in list(self.tracks.items()):
            best_iou, best_idx = 0.0, -1
            for i in unmatched_detections:
                if detections[i]["class"] != track["class"]:
                    continue
                iou = _iou(track["bbox"], detections[i]["bbox"])
                if iou > best_iou:
                    best_iou, best_idx = iou, i

            if best_iou >= self.iou_threshold and best_idx != -1:
                det = detections[best_idx]
                self.tracks[track_id] = {"bbox": det["bbox"], "class": det["class"], "missed": 0}
                results.append({
                    "trackId": track_id, "class": det["class"],
                    "confidence": det["confidence"], "bbox": det["bbox"],
                })
                unmatched_detections.remove(best_idx)
                matched_track_ids.add(track_id)
            else:
                track["missed"] += 1

        # Remove stale tracks
        self.tracks = {
            tid: t for tid, t in self.tracks.items()
            if t["missed"] <= self.max_missed_frames
        }

        # Create new tracks for unmatched detections
        for i in unmatched_detections:
            det = detections[i]
            new_id = next(self._next_id)
            self.tracks[new_id] = {"bbox": det["bbox"], "class": det["class"], "missed": 0}
            results.append({
                "trackId": new_id, "class": det["class"],
                "confidence": det["confidence"], "bbox": det["bbox"],
            })

        return results
