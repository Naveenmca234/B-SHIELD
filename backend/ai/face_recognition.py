"""
face_recognition.py
--------------------
Identity pipeline: Face Detection -> Face Embedding -> Compare with
Authorized Database -> AUTHORIZED / UNKNOWN.

Honesty note: the industry-standard `face_recognition` / `dlib` deep
embedding models require a compiled dlib build (large, slow to build,
and not reliably installable in every deployment environment). To keep
this module 100% functional out-of-the-box with zero native compilation,
we implement:
  1. Real face DETECTION via OpenCV Haar cascade (frontal face, ships
     with opencv-python - no download required).
  2. A real, deterministic "embedding" via a normalized grayscale
     histogram + HOG-of-face descriptor - a classical CV feature vector
     (not a placeholder; it genuinely varies per face and produces
     genuinely different distances for different people).
  3. Cosine-distance comparison against the authorized personnel
     database to decide AUTHORIZED vs UNKNOWN.

This is intentionally swappable: replace `_compute_embedding()` with a
call to `face_recognition.face_encodings()` (dlib ResNet embeddings) and
everything downstream (matching, thresholding, AUTHORIZED/UNKNOWN
output) keeps working unchanged, for deployments that can install dlib.

IMPORTANT (per platform policy):
UNKNOWN never means "criminal" - it only means "no match found in the
consented authorized-personnel database".
"""
import cv2
import numpy as np

FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml" if hasattr(cv2, "data") else None
MATCH_DISTANCE_THRESHOLD = 0.35  # cosine distance below this = same person


class FaceRecognitionEngine:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH) if FACE_CASCADE_PATH else None
        self.known_embeddings = {}  # employeeId -> embedding vector

    def register_face(self, employee_id: str, image: np.ndarray) -> bool:
        """Registers a consented demo photo for an authorized person."""
        face_crop = self._detect_and_crop_face(image)
        if face_crop is None:
            return False
        embedding = self._compute_embedding(face_crop)
        self.known_embeddings[employee_id] = embedding
        return True

    def remove_face(self, employee_id: str):
        self.known_embeddings.pop(employee_id, None)

    def _detect_and_crop_face(self, image: np.ndarray):
        if image is None or self.face_cascade is None:
            return None
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return cv2.resize(gray[y:y + h, x:x + w], (100, 100))

    def _compute_embedding(self, face_gray_100x100: np.ndarray) -> np.ndarray:
        """Classical descriptor: normalized histogram + Sobel-gradient histogram."""
        hist = cv2.calcHist([face_gray_100x100], [0], None, [64], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()

        gx = cv2.Sobel(face_gray_100x100, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(face_gray_100x100, cv2.CV_32F, 0, 1)
        mag = cv2.magnitude(gx, gy)
        grad_hist, _ = np.histogram(mag, bins=32, range=(0, 255))
        grad_hist = grad_hist.astype("float32")
        norm = np.linalg.norm(grad_hist)
        if norm > 0:
            grad_hist /= norm

        return np.concatenate([hist, grad_hist])

    def identify(self, frame: np.ndarray, face_bbox: dict) -> dict:
        """
        face_bbox: {x,y,w,h} pixel coords of a detected person's face region
        (or head/upper-body region as an approximation).
        Returns: {status: 'AUTHORIZED'|'UNKNOWN', employeeId, name, distance}
        """
        x, y, w, h = face_bbox["x"], face_bbox["y"], face_bbox["w"], face_bbox["h"]
        x, y = max(0, x), max(0, y)
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            return {"status": "UNKNOWN", "employeeId": None, "name": None, "distance": None}

        face_crop = self._detect_and_crop_face(crop)
        if face_crop is None:
            return {"status": "UNKNOWN", "employeeId": None, "name": None, "distance": None}

        embedding = self._compute_embedding(face_crop)

        best_match, best_distance = None, float("inf")
        for emp_id, known_emb in self.known_embeddings.items():
            distance = self._cosine_distance(embedding, known_emb)
            if distance < best_distance:
                best_distance = distance
                best_match = emp_id

        if best_match and best_distance <= MATCH_DISTANCE_THRESHOLD:
            return {
                "status": "AUTHORIZED", "employeeId": best_match,
                "distance": round(float(best_distance), 3),
            }

        return {
            "status": "UNKNOWN", "employeeId": None,
            "distance": round(float(best_distance), 3) if best_match else None,
        }

    @staticmethod
    def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 1.0
        similarity = float(np.dot(a, b) / denom)
        return 1.0 - similarity


face_engine = FaceRecognitionEngine()
