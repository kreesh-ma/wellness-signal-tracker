import logging
import math
import ssl
import urllib.request
from pathlib import Path

import cv2
import dlib
import numpy as np

log = logging.getLogger(__name__)


class FaceAnalyzer:
    def __init__(self):
        self.LEFT_EYE = list(range(36, 42))
        self.RIGHT_EYE = list(range(42, 48))
        self.LEFT_BROW = list(range(17, 22))
        self.RIGHT_BROW = list(range(22, 27))
        self.NOSE = list(range(27, 36))
        self.MOUTH = list(range(48, 68))
        self.FACE_OVAL = list(range(0, 17))

        model_dir = Path(__file__).parent.parent / 'models'
        yunet_path = model_dir / 'face_detection_yunet_2023mar.onnx'

        if not yunet_path.exists():
            self._download_yunet(model_dir, yunet_path)

        self.fd = cv2.FaceDetectorYN_create(str(yunet_path), '', (320, 320))
        # OpenCV's default 0.9 cut-off is borderline for webcam frames
        # (real faces often score 0.85-0.9), which made detection flicker.
        self.fd.setScoreThreshold(0.6)
        print("YuNet face detector loaded")

        self.predictor = None
        predictor_path = model_dir / 'shape_predictor_68_face_landmarks.dat'
        try:
            if predictor_path.exists():
                self.predictor = dlib.shape_predictor(str(predictor_path))
                print("dlib predictor loaded")
            else:
                print(f"WARNING: {predictor_path} not found - landmarks will be FAKE "
                      f"and blink/brow metrics are disabled")
        except Exception as e:
            print(f"dlib predictor failed: {e}")

    def _download_yunet(self, model_dir, dest):
        # NOTE: certificate verification is disabled here; prefer download_model.py
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
               "face_detection_yunet/face_detection_yunet_2023mar.onnx")
        print("Downloading YuNet face detection model...")
        urllib.request.urlretrieve(url, str(dest))
        print("Download complete!")

    # ------------------------------------------------------------------
    # Detection / landmarks
    # ------------------------------------------------------------------
    def detect_faces(self, frame):
        h, w = frame.shape[:2]
        # YuNet runs on a downscaled copy: 640x480 costs ~20ms, 320x240 ~6ms,
        # and the score for a webcam face barely changes. dlib still runs on
        # the full-resolution frame so landmark accuracy is unaffected.
        scale = min(1.0, 320.0 / max(w, h))
        if scale < 1.0:
            dw, dh = int(round(w * scale)), int(round(h * scale))
            small = cv2.resize(frame, (dw, dh), interpolation=cv2.INTER_AREA)
        else:
            dw, dh, small, scale = w, h, frame, 1.0

        self.fd.setInputSize((dw, dh))
        ret, faces = self.fd.detect(small)

        dlib_faces = []
        if faces is not None:
            inv = 1.0 / scale
            # largest face first, so the main user wins over people in the background
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            for face in faces:
                x, y, fw, fh = face[0] * inv, face[1] * inv, face[2] * inv, face[3] * inv
                x1, y1 = int(max(0, x)), int(max(0, y))
                x2, y2 = int(min(w, x + fw)), int(min(h, y + fh))
                if x2 > x1 and y2 > y1:
                    dlib_faces.append(dlib.rectangle(x1, y1, x2, y2))
        return dlib_faces

    def get_landmarks(self, frame, face):
        """Returns (landmarks, is_real). is_real is False for the approximate fallback."""
        if self.predictor is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = np.ascontiguousarray(gray, dtype=np.uint8)
                shape = self.predictor(gray, face)
                pts = np.array([[shape.part(i).x, shape.part(i).y] for i in range(68)],
                               dtype=np.int32)
                return pts, True
            except Exception as e:
                log.warning("dlib predictor failed: %s", e)
        return self._approximate_landmarks(face), False

    def _approximate_landmarks(self, face):
        x, y = face.left(), face.top()
        w, h = face.width(), face.height()
        landmarks = np.zeros((68, 2), dtype=np.int32)

        for i in range(17):
            angle = np.pi * (i / 16)
            lx = int(x + w/2 + w/2 * np.cos(angle + np.pi/2))
            ly = int(y + h/2 - h/2 * np.sin(angle + np.pi/2))
            landmarks[i] = [lx, ly]

        for i in range(5):
            landmarks[17+i] = [int(x + w*0.2 + i*w*0.1), int(y + h*0.25)]
        for i in range(5):
            landmarks[22+i] = [int(x + w*0.5 + i*w*0.1), int(y + h*0.25)]

        landmarks[27] = [int(x + w/2), int(y + h*0.35)]
        landmarks[28] = [int(x + w/2), int(y + h*0.45)]
        for i in range(3):
            landmarks[29+i] = [int(x + w*0.35 + i*w*0.15), int(y + h*0.55)]
        for i in range(3):
            landmarks[32+i] = [int(x + w*0.35 + i*w*0.15), int(y + h*0.65)]

        lcx = x + w * 0.35
        lcy = y + h * 0.40
        ew = w * 0.10
        eh = h * 0.025
        landmarks[36] = [int(lcx - ew), int(lcy)]
        landmarks[37] = [int(lcx - ew*0.4), int(lcy - eh)]
        landmarks[38] = [int(lcx + ew*0.4), int(lcy - eh)]
        landmarks[39] = [int(lcx + ew), int(lcy)]
        landmarks[40] = [int(lcx + ew*0.4), int(lcy + eh)]
        landmarks[41] = [int(lcx - ew*0.4), int(lcy + eh)]

        rcx = x + w * 0.65
        rcy = y + h * 0.40
        landmarks[42] = [int(rcx - ew), int(rcy)]
        landmarks[43] = [int(rcx - ew*0.4), int(rcy - eh)]
        landmarks[44] = [int(rcx + ew*0.4), int(rcy - eh)]
        landmarks[45] = [int(rcx + ew), int(rcy)]
        landmarks[46] = [int(rcx + ew*0.4), int(rcy + eh)]
        landmarks[47] = [int(rcx - ew*0.4), int(rcy + eh)]

        mouth_w = w * 0.25
        mouth_h = h * 0.08
        cx, cy = x + w/2, y + h*0.75
        for i in range(20):
            angle = np.pi * 2 * (i / 20) - np.pi/2
            rw = mouth_w if i < 10 else mouth_w * 0.7
            rh = mouth_h if i < 10 else mouth_h * 0.5
            landmarks[48+i] = [int(cx + rw*np.cos(angle)), int(cy + rh*np.sin(angle))]

        return landmarks

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def eye_aspect_ratio(self, eye):
        A = np.linalg.norm(eye[1] - eye[5])
        B = np.linalg.norm(eye[2] - eye[4])
        C = np.linalg.norm(eye[0] - eye[3])
        if C == 0:
            return 0.0   # invalid; the engine ignores ear <= 0
        return (A + B) / (2.0 * C)

    def brow_height(self, landmarks):
        """Brow-to-upper-eyelid distance divided by inter-ocular distance, x100.

        Scale-independent (leaning toward the camera doesn't change it). It is
        LOWER when brows are pulled down/furrowed, so the engine measures the
        drop from the user's neutral value to get 'tension'.
        """
        pts = landmarks.astype(np.float64)
        iod = np.linalg.norm(pts[36] - pts[45])      # outer corner to outer corner
        if iod == 0:
            return None
        left = np.linalg.norm(pts[18:21].mean(axis=0) - pts[37:39].mean(axis=0))
        right = np.linalg.norm(pts[23:26].mean(axis=0) - pts[43:45].mean(axis=0))
        return float((left + right) / 2.0 / iod * 100.0)

    # coarse head-pose heuristics (see estimate_head_pose)
    YAW_NOSE_DEPTH = 0.8     # nose protrusion as a fraction of inter-ocular distance
    PITCH_BASE_RATIO = 0.35  # nose-below-eye-line / eye-line-to-chin when frontal
    PITCH_SCALE = 3.5

    def estimate_head_pose(self, landmarks):
        """Coarse yaw/pitch in degrees from the 2D landmarks (roll-corrected).

        yaw   = nose shift ALONG the eye line, normalised by inter-ocular
                distance (> 0 = head turned toward image right)
        pitch = nose drop BELOW the eye line, normalised by eye-line-to-chin
                height (> 0 = looking down)

        Neck rolls / looking away distort the eye landmarks enough to fake a
        long eye closure, so the engine skips drowsiness tracking beyond
        POSE_MAX_YAW / POSE_MAX_PITCH.
        """
        pts = np.asarray(landmarks, dtype=np.float64)
        left, right = pts[36], pts[45]
        eye_vec = right - left
        iod = float(np.linalg.norm(eye_vec))
        if iod < 1.0:
            return 0.0, 0.0
        eye_dir = eye_vec / iod
        perp = np.array([-eye_dir[1], eye_dir[0]])  # unit, downward at zero roll
        mid = (left + right) / 2.0
        d = pts[30] - mid                           # nose tip vs eye-line midpoint
        along = float(d @ eye_dir)
        vert = float(d @ perp)
        face_h = float((pts[8] - mid) @ perp)       # eye line to chin
        if face_h < iod * 0.5:
            return 0.0, 0.0
        yaw = math.degrees(math.asin(
            max(-1.0, min(1.0, along / (self.YAW_NOSE_DEPTH * iod)))))
        pitch = math.degrees(math.atan(
            (vert / face_h - self.PITCH_BASE_RATIO) * self.PITCH_SCALE))
        return yaw, pitch

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw_landmarks(self, frame, landmarks, face_rect=None):
        overlay = frame.copy()
        landmarks = np.asarray(landmarks, dtype=np.int32)

        if face_rect is not None:
            cv2.rectangle(overlay,
                          (face_rect.left(), face_rect.top()),
                          (face_rect.right(), face_rect.bottom()),
                          (0, 255, 0), 2)

        for i in self.FACE_OVAL[:-1]:
            cv2.line(overlay, tuple(landmarks[i]), tuple(landmarks[i + 1]), (200, 200, 200), 1)

        for eye_indices in [self.LEFT_EYE, self.RIGHT_EYE]:
            cv2.polylines(overlay, [landmarks[eye_indices]], True, (0, 255, 255), 2)

        for brow_indices in [self.LEFT_BROW, self.RIGHT_BROW]:
            cv2.polylines(overlay, [landmarks[brow_indices]], True, (255, 200, 0), 2)

        for i in self.NOSE[:-1]:
            cv2.line(overlay, tuple(landmarks[i]), tuple(landmarks[i + 1]), (200, 200, 200), 1)

        cv2.polylines(overlay, [landmarks[self.MOUTH]], True, (0, 100, 255), 2)

        for point in landmarks:
            cv2.circle(overlay, tuple(point), 2, (0, 255, 0), -1)

        return overlay

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def analyze_frame(self, frame):
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)

        faces = self.detect_faces(frame)
        if len(faces) == 0:
            return None

        face = faces[0]
        landmarks, is_real = self.get_landmarks(frame, face)

        if is_real:
            ear_left = self.eye_aspect_ratio(landmarks[36:42])
            ear_right = self.eye_aspect_ratio(landmarks[42:48])
            avg_ear = (ear_left + ear_right) / 2.0
            brow = self.brow_height(landmarks)
        else:
            # Fake landmarks would give a constant EAR/brow and poison calibration
            avg_ear, brow = None, None

        log.debug("ear=%s brow_height=%s real_landmarks=%s", avg_ear, brow, is_real)

        yaw, pitch = self.estimate_head_pose(landmarks)

        return {
            'face_detected': True,
            'ear': avg_ear,
            'brow_height': brow,
            'brow_tension': brow,   # alias so existing views keep working; engine converts it
            'head_pose': {'yaw': round(yaw, 1), 'pitch': round(pitch, 1)},
            'landmarks': landmarks.tolist(),
            'face_rect': {
                'left': face.left(),
                'top': face.top(),
                'right': face.right(),
                'bottom': face.bottom()
            }
        }
