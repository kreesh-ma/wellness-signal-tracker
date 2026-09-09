# Wellness Signal Tracker

Real-time facial analysis dashboard that tracks blink rate, brow tension, and expression to compute a live "wellness score" — built to flag early signs of screen fatigue and stress during long work sessions.

![Status](https://img.shields.io/badge/status-hackathon%20submission-blueviolet)

## What it does

Point your webcam at the dashboard and it tracks, in real time:

- **Wellness Score (0–100)** — composite metric that drops with abnormal blink rate, high brow tension, or a stressed expression
- **Blink Rate** — blinks per minute, detected from eye-region motion
- **Brow Tension (0–100)** — how tightly your eyebrows are drawn toward your eyes
- **Expression** — neutral / focused / stressed, classified from brow tension + eye aspect ratio
- **Live chart** — wellness score and blink rate plotted over the session
- **Wellness tips** — contextual nudges based on current state
- **Historical data** — readings saved to database for trend analysis

## How it works

```
Browser webcam → frame capture → base64 encode → POST /api/analyze/
                                                         ↓
Backend: YuNet detects face → dlib predicts 68 landmarks → metrics calculated
                                                         ↓
Response: overlay image + wellness data ← OpenCV draws landmarks
                                                         ↓
                                Django Channels (WebSocket) → live dashboard update
```

### Face & landmark detection

- **YuNet (OpenCV DNN)** for face detection — auto-downloaded on first run
- **dlib 68-point landmark predictor** for facial landmarks
  - dlib's built-in frontal face detector didn't run on the dev machine, so YuNet handles detection and dlib is used purely for landmark prediction on the detected face region

### Metric calculation

**Blink rate (blinks/min)**
Motion-based — frame differences in the eye region are used to detect close/open transitions, which are then converted to a per-minute rate.

**Brow tension (0–100)**
Distance between eyebrow landmarks (17–26) and eye landmarks (36–47), normalized to a 0–100 scale. Shorter distance (brows drawn down) → higher tension.

**Expression (neutral / focused / stressed)**
Composite of brow tension and Eye Aspect Ratio (EAR):
- `brow_tension > 60` and `EAR < 0.25` → **stressed**
- `brow_tension > 40` → **focused**
- otherwise → **neutral**

**Wellness score (0–100)**
```
100 - blink_penalty - brow_penalty - expression_penalty
```
- Abnormal blink rate → −20
- High brow tension → up to −30
- Stressed expression → −25

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Django + Django Channels |
| Real-time | WebSocket (Django Channels) |
| Face detection | OpenCV DNN (YuNet) |
| Landmarks | dlib 68-point predictor |
| Frontend | HTML / CSS / JavaScript + Chart.js |
| Database | SQLite (dev) — MySQL (production) |

**Why Django?** It was the required stack for the CodeStorm hackathon. Django Channels gave us WebSocket support for the real-time dashboard without switching frameworks.

## Getting started

### Prerequisites
- Python 3.9+
- Webcam

### Setup

```bash
# clone and enter the project
git clone <your-repo-url>
cd codestorm

# create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# apply migrations
python manage.py migrate

# run the server
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser, click **Start Camera**, and allow camera access.

**Note:** The YuNet face detection model (~230KB) will be auto-downloaded on first run. The dlib landmark model (~99MB) is included in the `models/` directory.

## Project structure

```
codestorm/
├── manage.py
├── requirements.txt
├── core/
│   ├── __init__.py
│   ├── admin.py              # Admin registration
│   ├── apps.py
│   ├── consumers.py          # WebSocket consumer
│   ├── face_analyzer.py      # YuNet + dlib pipeline
│   ├── models.py             # WellnessReading model
│   ├── urls.py               # API endpoints
│   ├── views.py              # /api/analyze/ endpoint
│   └── wellness_engine.py    # Metric calculations
├── wellness/
│   ├── __init__.py
│   ├── asgi.py               # ASGI config for WebSocket
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── static/
│   ├── css/style.css         # UI styling + animations
│   └── js/dashboard.js       # Webcam, Chart.js, WebSocket client
├── templates/
│   └── dashboard.html        # Main dashboard page
├── models/
│   ├── shape_predictor_68_face_landmarks.dat  # dlib model
│   ├── face_detection_yunet_2023mar.onnx      # YuNet model (auto-downloaded)
│   ├── deploy.prototxt
│   └── res10_300x300_ssd_iter_140000.caffemodel
└── db.sqlite3                # SQLite database
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard page |
| `/api/analyze/` | POST | Analyze webcam frame |
| `/api/latest/` | GET | Get latest reading |
| `/api/history/` | GET | Get historical readings |
| `/ws/wellness/` | WebSocket | Real-time updates |

## Known limitations

- dlib's frontal face detector isn't used (system-specific issue); YuNet handles detection instead
- Blink detection is motion-based, not landmark-based — sensitive to camera shake
- Single-face tracking only
- Approximate landmarks used when dlib predictor fails

## Roadmap (post-hackathon)

- ML-based pattern classification over historical session data
- Smarter, personalized wellness tip triggers
- Multi-session history and trends
- Multi-face support
- Mobile app version

## Team / Hackathon

Built for **CodeStorm** hackathon.

---
*Questions or feedback — open an issue or reach out.*