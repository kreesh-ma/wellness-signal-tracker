# Wellness Signal Tracker

Real-time facial analysis dashboard that tracks blink rate, brow tension, and expression to compute a live "wellness score" — built to flag early signs of screen fatigue and stress during long work sessions. Adds a smart drowsiness alert system, an end-of-session AI report, and persisted session history with before/after comparison.

![Status](https://img.shields.io/badge/status-hackathon%20submission-blueviolet)

## What it does

Point your webcam at the dashboard and it tracks, in real time:

- **Wellness Score (0–100)** — composite metric that drops with abnormal blink rate, high brow tension, or a stressed expression
- **Blink Rate** — blinks per minute, detected from Eye Aspect Ratio (EAR) dips with hysteresis
- **Brow Tension (0–100)** — how far the brows have dropped below your calibrated neutral height
- **Expression** — neutral / focused / stressed, classified from brow tension + eye aspect ratio
- **Live chart** — wellness score and blink rate plotted over the session
- **Wellness tips** — contextual nudges based on current state
- **Historical data** — readings saved to database for trend analysis

Plus the three session-level features:

- **Smart Drowsiness Alert** — flags *sustained* eye closure (≥1.5 s) or a repeated slow-closure pattern (3+ in 30 s) and shows an animated "⚠️ Drowsiness Detected — Take a Short Break" banner with an optional Web Audio sound alert (mute/unmute control, persisted). Single blinks and face loss never trigger it; the alert clears automatically once the user's eyes stay open.
- **End-of-Session Report** — stopping the camera generates a SESSION SUMMARY computed from real per-second session samples: focus score, attention stability, blink rate (normal/low/high), drowsiness events, session duration, recommended break, and a personalized recommendation — displayed with animated SVG progress rings and "Start New Session" / "Close Report" actions.
- **Session History & Comparison** — every completed session is persisted; a Session History section shows focus/stability/drowsiness/duration trend charts, a session table, and a before-vs-after comparison of any two sessions with deltas and an improving/decreasing verdict. History survives a page refresh and can be cleared.

## How it works

```
Browser webcam → frame capture → base64 encode → POST /api/analyze/
                                                         ↓
Backend: YuNet detects face → dlib predicts 68 landmarks → metrics calculated
                                                         ↓
Response: overlay image + wellness data ← OpenCV draws landmarks
                                                         ↓
                        Dashboard JS → live metric/chart update (WebSocket
                        channel kept open for future server broadcasts)
```

### Face & landmark detection

- **YuNet (OpenCV DNN)** for face detection — auto-downloaded on first run
- **dlib 68-point landmark predictor** for facial landmarks
  - dlib's built-in frontal face detector didn't run on the dev machine, so YuNet handles detection and dlib is used purely for landmark prediction on the detected face region

### Metric calculation

**Blink rate (blinks/min)**
Landmark-based — the Eye Aspect Ratio (EAR) of both eyes is computed every frame. Thresholds come from a per-user adaptive baseline: the running median of EAR over the last 10 s of frontal, open-eye frames (alert-active and closed frames are ignored), so a wide/narrow calibration moment can't skew detection. Dips below 75% of that baseline count as a closing eye; reopening above 85% (hysteresis) completes the blink. A blink is a 1–5 frame dip lasting ≤0.4 s; longer closures are tracked separately (see below). Blinks are kept in a rolling 60 s window and converted to a per-minute rate (scaled by observed time during the first 15 s, so it never reads 0 while warming up).

**Brow tension (0–100)**
Percentage drop from the user's calibrated neutral brow height × 3.0 gain, capped at 100. Neutral height is the median brow height recorded during the 4 s calibration.

**Expression (neutral / focused / stressed)**
Composite of average brow tension and EAR ratio (EAR / baseline):
- `brow_tension > 25` and `ratio < 0.85` → **stressed**
- `brow_tension > 12` → **focused**
- otherwise → **neutral**

**Wellness score (0–100)**
```
100 − blink penalty − (brow tension × 0.4) − expression penalty − squint penalty
```
- Abnormal blink rate: `>25/min` → −25, `>20` → −15, `<8` → −20, `<10` → −15, `<12` → −5
- Brow tension: −0.4 per point (up to −40)
- Stressed → −20, focused → −8
- EAR below 85% of baseline (squinting / heavy eyelids) → −5

**Drowsiness detection (alert system)**
Reuses the same adaptive EAR hysteresis state as blink detection — no extra model:
- eyes held below the close threshold (75% of the adaptive baseline) for **≥1.5 s** → sustained event
- or **3+ slow closures (0.4–1.5 s each) within 30 s** → repeated-pattern event
- clears after the eyes stay open for 4 s; face loss resets tracking so stale timestamps can never fake an episode; events are rate-limited to 1 per 10 s
- the client requires 2 consecutive drowsy readings before showing the banner (single-frame flicker protection) and hides it on the first reading with the alert cleared

**Session report metrics** (all computed client-side from 1-sample-per-second session data):
- *Focus Score* — mean wellness score of the session
- *Attention Stability* — % of tracked seconds with focus ≥ 70
- *Drowsiness-Free* — % of the session without an active alert
- *Recommended Break* — 2/3/5/10 min based on duration, focus, stability, and drowsiness events

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Django + Django Channels |
| Real-time | HTTP frame pipeline (+ WebSocket channel for broadcasts) |
| Face detection | OpenCV DNN (YuNet) |
| Landmarks | dlib 68-point predictor |
| Frontend | HTML / CSS / JavaScript + Chart.js |
| Session storage | Django ORM — SQLite (dev) — MySQL (production) |

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
│   ├── models.py             # WellnessReading + SessionRecord models
│   ├── migrations/
│   │   ├── 0001_initial.py       # WellnessReading
│   │   └── 0002_sessionrecord.py # SessionRecord (session history)
│   ├── urls.py               # API endpoints
│   ├── views.py              # /api/analyze/ + session history endpoints
│   └── wellness_engine.py    # Metric + drowsiness calculations
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
| `/api/analyze/` | POST | Analyze webcam frame (returns overlay + wellness incl. `drowsy`) |
| `/api/latest/` | GET | Get latest reading |
| `/api/history/` | GET | Get historical readings |
| `/api/readings/` | GET | Last hour of readings |
| `/api/sessions/` | GET | Completed session history (chronological) |
| `/api/sessions/save/` | POST | Persist a completed session report |
| `/api/sessions/clear/` | DELETE | Clear all session history |
| `/ws/wellness/` | WebSocket | Real-time update channel |

## Known limitations

- dlib's frontal face detector isn't used (system-specific issue); YuNet handles detection instead
- Single-face tracking only
- Approximate landmarks used when dlib predictor fails
- Drowsiness is inferred from eye closure only (no head-pose/yawn detection)

## Roadmap (post-hackathon)

- ML-based pattern classification over historical session data
- Smarter, personalized wellness tip triggers
- Multi-face support
- Mobile app version

## Team / Hackathon

Built for **CodeStorm** hackathon.

---
*Questions or feedback — open an issue or reach out.*