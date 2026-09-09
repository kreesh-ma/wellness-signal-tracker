import cv2
import dlib
import numpy as np
from pathlib import Path
import urllib.request
import ssl

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
        print("YuNet face detector loaded")

        self.predictor = None
        try:
            predictor_path = model_dir / 'shape_predictor_68_face_landmarks.dat'
            if predictor_path.exists():
                self.predictor = dlib.shape_predictor(str(predictor_path))
                print("dlib predictor loaded")
        except Exception as e:
            print(f"dlib predictor failed: {e}")

    def _download_yunet(self, model_dir, dest):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
        print("Downloading YuNet face detection model...")
        urllib.request.urlretrieve(url, str(dest))
        print("Download complete!")

    def detect_faces(self, frame):
        h, w = frame.shape[:2]
        self.fd.setInputSize((w, h))
        ret, faces = self.fd.detect(frame)
        
        dlib_faces = []
        if faces is not None:
            for face in faces:
                x, y, fw, fh = face[0], face[1], face[2], face[3]
                x1, y1 = int(max(0, x)), int(max(0, y))
                x2, y2 = int(min(w, x + fw)), int(min(h, y + fh))
                dlib_faces.append(dlib.rectangle(x1, y1, x2, y2))
        return dlib_faces

    def get_landmarks(self, frame, face):
        if self.predictor is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if not gray.flags['C_CONTIGUOUS']:
                    gray = np.ascontiguousarray(gray)
                landmarks = self.predictor(gray, face)
                return np.array([[landmarks.part(i).x, landmarks.part(i).y] for i in range(68)])
            except Exception as e:
                print(f"dlib predictor failed: {e}")
        return self._approximate_landmarks(face)

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

        # left eye (36-41) - almond shape for blink detection
        lcx = x + w * 0.35
        lcy = y + h * 0.40
        ew = w * 0.10
        eh = h * 0.025  # reduced height for better blink detection
        landmarks[36] = [int(lcx - ew), int(lcy)]
        landmarks[37] = [int(lcx - ew*0.4), int(lcy - eh)]
        landmarks[38] = [int(lcx + ew*0.4), int(lcy - eh)]
        landmarks[39] = [int(lcx + ew), int(lcy)]
        landmarks[40] = [int(lcx + ew*0.4), int(lcy + eh)]
        landmarks[41] = [int(lcx - ew*0.4), int(lcy + eh)]

        # right eye (42-47) - almond shape for blink detection
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

    def eye_aspect_ratio(self, eye):
        A = np.linalg.norm(eye[1] - eye[5])
        B = np.linalg.norm(eye[2] - eye[4])
        C = np.linalg.norm(eye[0] - eye[3])
        if C == 0:
            return 0.3
        ear = (A + B) / (2.0 * C)
        return ear

    def brow_tension(self, landmarks):
        left_brow = landmarks[17:22]
        left_eye = landmarks[36:42]
        right_brow = landmarks[22:27]
        right_eye = landmarks[42:48]

        left_dist = np.mean([np.linalg.norm(brow - eye) for brow, eye in zip(left_brow, left_eye)])
        right_dist = np.mean([np.linalg.norm(brow - eye) for brow, eye in zip(right_brow, right_eye)])

        return (left_dist + right_dist) / 2.0

    def draw_landmarks(self, frame, landmarks, face_rect=None):
        overlay = frame.copy()

        if face_rect is not None:
            cv2.rectangle(overlay,
                         (face_rect.left(), face_rect.top()),
                         (face_rect.right(), face_rect.bottom()),
                         (0, 255, 0), 2)

        for i in self.FACE_OVAL:
            pt1 = tuple(landmarks[i])
            pt2 = tuple(landmarks[(i + 1) % 17])
            cv2.line(overlay, pt1, pt2, (200, 200, 200), 1)

        for eye_indices in [self.LEFT_EYE, self.RIGHT_EYE]:
            pts = landmarks[eye_indices]
            cv2.polylines(overlay, [pts], True, (0, 255, 255), 2)

        for brow_indices in [self.LEFT_BROW, self.RIGHT_BROW]:
            pts = landmarks[brow_indices]
            cv2.polylines(overlay, [pts], True, (255, 200, 0), 2)

        for i in self.NOSE[:-1]:
            pt1 = tuple(landmarks[i])
            pt2 = tuple(landmarks[i + 1])
            cv2.line(overlay, pt1, pt2, (200, 200, 200), 1)

        cv2.polylines(overlay, [landmarks[self.MOUTH]], True, (0, 100, 255), 2)

        for i, point in enumerate(landmarks):
            cv2.circle(overlay, tuple(point), 2, (0, 255, 0), -1)

        return overlay

    def analyze_frame(self, frame):
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)

        faces = self.detect_faces(frame)
        if len(faces) == 0:
            return None

        face = faces[0]
        landmarks = self.get_landmarks(frame, face)

        left_eye = landmarks[36:42]
        right_eye = landmarks[42:48]

        left_ear = self.eye_aspect_ratio(left_eye)
        right_ear = self.eye_aspect_ratio(right_eye)
        avg_ear = (left_ear + right_ear) / 2.0

        brow = self.brow_tension(landmarks)

        return {
            'face_detected': True,
            'ear': avg_ear,
            'brow_tension': brow,
            'landmarks': landmarks.tolist(),
            'face_rect': {
                'left': face.left(),
                'top': face.top(),
                'right': face.right(),
                'bottom': face.bottom()
            }
        }
