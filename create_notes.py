from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

doc = Document()

style = doc.styles['Normal']
font = style.font
font.name = 'Calibri'
font.size = Pt(11)

def add_title(text):
    p = doc.add_heading(text, level=0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

def add_heading1(text):
    doc.add_heading(text, level=1)

def add_heading2(text):
    doc.add_heading(text, level=2)

def add_text(text):
    doc.add_paragraph(text)

def add_bold(text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True

def add_code(text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = 'Consolas'
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0, 100, 0)

def add_bullet(text):
    doc.add_paragraph(text, style='List Bullet')

def add_table(headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Light Grid Accent 1'
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
    for row_data in rows:
        row = table.add_row().cells
        for i, val in enumerate(row_data):
            row[i].text = val

# ============================================================
# TITLE
# ============================================================
add_title("Wellness Signal Tracker")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("Real-Time Facial Analysis for Screen Fatigue Detection")
run.italic = True
run.font.size = Pt(12)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("CodeStorm Hackathon Project")
run.font.size = Pt(10)
run.font.color.rgb = RGBColor(100, 100, 100)

doc.add_page_break()

# ============================================================
# TABLE OF CONTENTS
# ============================================================
add_heading1("Table of Contents")
toc_items = [
    "1. What is this project?",
    "2. Tech Stack",
    "3. Project Structure",
    "4. How it Works (Flow Diagram)",
    "5. Backend Files Explained",
    "6. Frontend Files Explained",
    "7. Face Detection & Landmarks",
    "8. How Blink Detection Works",
    "9. How Expression is Classified",
    "10. How Wellness Score is Calculated",
    "11. API Endpoints",
    "12. Database Model",
    "13. WebSocket Flow",
    "14. How to Run the Project",
    "15. Key Numbers to Remember",
]
for item in toc_items:
    add_text(item)

doc.add_page_break()

# ============================================================
# 1. WHAT IS THIS PROJECT?
# ============================================================
add_heading1("1. What is this project?")

add_text("This is a web application that uses your laptop webcam to watch your face in real time. It detects your facial features like eyes, eyebrows, mouth and calculates a Wellness Score from 0 to 100.")

add_text("The purpose of this app is to detect early signs of screen fatigue and stress during long work sessions. When you sit in front of a computer for hours, you blink less, your brows get tense, and your eyes strain. This app tracks all of that and gives you a score with tips.")

add_bold("What it tracks:")
add_bullet("Blink Rate - how many times you blink per minute")
add_bullet("Brow Tension - how tight your eyebrows are")
add_bullet("Expression - neutral, focused, or stressed")
add_bullet("Wellness Score - overall score out of 100")
add_bullet("Drowsiness Alert - sustained eye closure or a repeated slow-closure pattern")

# ============================================================
# 2. TECH STACK
# ============================================================
add_heading1("2. Tech Stack")

add_table(
    ["Layer", "Technology", "Why"],
    [
        ["Backend", "Django + Django Channels", "Required stack for hackathon, WebSocket support"],
        ["Real-time", "WebSocket (Django Channels)", "Live dashboard updates without page refresh"],
        ["Face Detection", "OpenCV DNN (YuNet)", "Fast and lightweight face detector"],
        ["Landmarks", "dlib 68-point predictor", "Precise facial landmark detection"],
        ["Frontend", "HTML + CSS + JavaScript", "User interface and webcam capture"],
        ["Chart", "Chart.js", "Live chart plotting"],
        ["Database", "SQLite (dev)", "Store historical readings"],
    ]
)

# ============================================================
# 3. PROJECT STRUCTURE
# ============================================================
add_heading1("3. Project Structure")

add_code("""
codestorm/
├── manage.py                  # Django entry point
├── requirements.txt           # Python dependencies
├── core/
│   ├── face_analyzer.py       # YuNet + dlib face pipeline
│   ├── wellness_engine.py     # All metric calculations
│   ├── views.py               # API endpoint /api/analyze/
│   ├── models.py              # Database model
│   ├── consumers.py           # WebSocket consumer
│   ├── routing.py             # WebSocket URL routing
│   └── urls.py                # URL patterns
├── wellness/
│   ├── settings.py            # Django settings
│   ├── urls.py                # Root URL config
│   └── asgi.py                # ASGI config for WebSocket
├── templates/
│   └── dashboard.html         # Main page
├── static/
│   ├── css/style.css          # Dark theme UI
│   └── js/dashboard.js        # Webcam + Chart + WebSocket
└── models/
    ├── shape_predictor_68_face_landmarks.dat  # dlib model (99MB)
    └── face_detection_yunet_2023mar.onnx      # YuNet model
""")

# ============================================================
# 4. HOW IT WORKS (FLOW)
# ============================================================
add_heading1("4. How it Works (Flow Diagram)")

add_bold("Step by step flow:")
add_text("1. User opens the app in browser and clicks Start Camera")
add_text("2. Browser captures webcam frame (320x200 pixels)")
add_text("3. Frame is encoded to base64 and sent to server via POST /api/analyze/")
add_text("4. Server decodes the image to OpenCV format")
add_text("5. YuNet face detector finds the face bounding box")
add_text("6. dlib predictor finds 68 facial landmark points")
add_text("7. Wellness Engine calculates EAR, brow tension, blink rate, expression")
add_text("8. Wellness Score is computed with penalties and bonuses")
add_text("9. Server draws landmarks on the frame (overlay image)")
add_text("10. Server returns JSON with score + overlay image to browser")
add_text("11. Browser updates dashboard: metrics, chart, tips, session log")
add_text("12. This cycle repeats 10-12 times per second")

add_bold("")
add_bold("Visual Flow:")
add_code("""
Browser Webcam
      |
      v
Capture Frame (320x200)
      |
      v
Base64 Encode
      |
      v
POST /api/analyze/  ──────→  Server receives image
                                    |
                                    v
                              YuNet detects face
                                    |
                                    v
                              dlib finds 68 landmarks
                                    |
                                    v
                              Calculate EAR, Brow Tension
                                    |
                                    v
                              Calculate Blink Rate
                                    |
                                    v
                              Classify Expression
                                    |
                                    v
                              Calculate Wellness Score
                                    |
                                    v
                              Draw landmarks on overlay
                                    |
                                    v
                              Return JSON response
                                    |
                                    v
Browser updates dashboard
      - Score number
      - Chart line
      - Tips
      - Session log
""")

# ============================================================
# 5. BACKEND FILES
# ============================================================
doc.add_page_break()
add_heading1("5. Backend Files Explained")

add_heading2("5.1 face_analyzer.py - Face Detection + Landmarks")
add_text("This file is responsible for finding the face and facial features in each frame.")
add_text("It uses two models: YuNet for face detection and dlib for 68-point landmark prediction.")

add_bold("Key Methods:")
add_bullet("detect_faces(frame) - Uses YuNet DNN to find face rectangles in the frame")
add_bullet("get_landmarks(frame, face) - Uses dlib predictor to find 68 facial points (eyes, brows, nose, mouth, jaw)")
add_bullet("eye_aspect_ratio(eye) - Calculates EAR value: (A+B)/(2*C) from 6 eye landmarks. ~0.30 with eyes open; compared against the user's adaptive baseline, not a fixed number")
add_bullet("brow_height(landmarks) - Brow-to-upper-eyelid distance divided by inter-ocular distance, x100. Lower = brows pulled down (the engine turns the drop into tension)")
add_bullet("analyze_frame(frame) - Full pipeline: detect face, get landmarks, calculate EAR and brow tension")
add_bullet("draw_landmarks(frame, landmarks) - Draws face outline, eyes, brows, mouth on the overlay image")
add_bullet("_approximate_landmarks(face) - Fallback if dlib fails. Calculates approximate landmarks from face rect proportions")

add_heading2("5.2 wellness_engine.py - Metric Calculations")
add_text("This file takes the face data and calculates all wellness metrics.")

add_bold("Blink Rate (blinks per minute):")
add_bullet("EAR-based detection with hysteresis - no motion/brightness tricks")
add_bullet("Adaptive baseline: running median of EAR over the last 10 s of frontal open-eye frames (4 s calibration only seeds the first thresholds)")
add_bullet("Eye closing = EAR below 75% of baseline; eye reopened = EAR above 85% of baseline (hysteresis stops flicker)")
add_bullet("A blink = a 1-5 frame dip lasting <= 0.4 s, then recovery; longer closures are tracked separately for drowsiness")
add_bullet("Rate = blinks in the last 60 s window; during the first 15 s it is scaled by observed time so it never reads 0")
add_bullet("Normal blink rate: 12-20 per minute")

add_bold("Brow Tension (0-100):")
add_bullet("Input is brow HEIGHT (brow-to-eyelid gap / inter-ocular distance), not a raw pixel distance - scale independent")
add_bullet("Tension = % drop below the user's calibrated neutral brow height x 3.0 gain, capped at 100")
add_bullet("Lower height (brows drawn down toward eyes) = higher tension")
add_bullet("Smoothed with history average for stability")

add_bold("Expression Classification:")
add_bullet("Stressed: brow_tension > 25 AND EAR below 85% of baseline (ratio < 0.85)")
add_bullet("Focused: brow_tension > 12")
add_bullet("Neutral: brow_tension <= 12")

add_bold("Wellness Score (0-100):")
add_bullet("Starts at 100")
add_bullet("Blink rate > 25/min: -25, > 20: -15 (over-blinking)")
add_bullet("Blink rate < 8: -20, < 10: -15, < 12: -5 (under-blinking); blink penalties paused during the first 15 s warm-up")
add_bullet("Brow tension: tension value x 0.4 as penalty (up to -40)")
add_bullet("Stressed expression: -20 points")
add_bullet("Focused expression: -8 points")
add_bullet("EAR below 85% of baseline (squinting / heavy eyelids): -5 points")
add_bullet("Result clamped between 0 and 100")

add_heading2("5.3 views.py - API Endpoints")
add_text("This file handles all HTTP requests from the browser.")

add_bullet("dashboard() - Renders the main HTML page")
add_bullet("analyze_frame() - Main endpoint. Receives webcam frame, runs analysis, returns results. Saves to DB every 50 frames")
add_bullet("get_latest() - Returns the most recent reading from database")
add_bullet("get_history() - Returns last 50 readings for session log")
add_bullet("get_readings() - Returns last 1 hour of readings")

add_text("Each user's wellness engine state is kept in-process in an LRU cache (up to 64 engines) keyed by their session id - round-tripping it through the session DB on every frame added latency and made calibration restart-prone. This means each user has their own blink tracking and history separately.")

add_heading2("5.4 models.py - Database Model")
add_text("Defines the WellnessReading model that stores each reading in the database.")

add_bullet("timestamp - automatically set when record is created")
add_bullet("blink_rate - float value (blinks per minute)")
add_bullet("brow_tension - float value (0-100 scale)")
add_bullet("expression - text: neutral, focused, or stressed")
add_bullet("wellness_score - float value (0-100)")

add_heading2("5.5 consumers.py - WebSocket Consumer")
add_text("Handles WebSocket connections for real-time updates.")
add_bullet("Connects client to wellness group channel")
add_bullet("Broadcasts wellness data to all connected clients")
add_bullet("Does NOT save to database (the view handles persistence)")

add_heading2("5.6 asgi.py - ASGI Configuration")
add_text("Configures Django to handle both HTTP and WebSocket connections.")
add_bullet("HTTP requests go to Django views")
add_bullet("WebSocket requests go to WellnessConsumer via URLRouter")

# ============================================================
# 6. FRONTEND FILES
# ============================================================
doc.add_page_break()
add_heading1("6. Frontend Files Explained")

add_heading2("6.1 dashboard.html - Page Layout")
add_text("Two-column layout:")
add_bullet("Left panel: Webcam video, overlay canvas, Start/Stop button, FPS counter, tracking status")
add_bullet("Right panel: Metric cards (score, blink, tension, expression), live chart, wellness tips, session log table")

add_heading2("6.2 dashboard.js - Client Logic")
add_bold("Camera flow:")
add_bullet("User clicks Start Camera button")
add_bullet("Browser requests webcam permission")
add_bullet("detectFace() runs via requestAnimationFrame (10-12 times per second)")
add_bullet("Each frame: capture -> resize to 320x200 -> base64 encode -> POST to /api/analyze/")
add_bullet("Response: draw overlay image, update metrics, update chart")

add_bold("Chart (Chart.js):")
add_bullet("Dual Y-axes: Left axis = Wellness Score (0-100, green), Right axis = Blink Rate (0-50, cyan)")
add_bullet("Keeps last 30 data points, shifts old ones out")
add_bullet("Updates in real-time with each analysis response")

add_bold("Session log:")
add_bullet("New entry added every 2 seconds (debounced to avoid spam)")
add_bullet("Shows time, score, blink rate, expression badge")
add_bullet("Maximum 10 entries visible")

add_bold("Keyboard shortcut:")
add_bullet("Spacebar toggles camera on/off")

add_heading2("6.3 style.css - Dark Theme")
add_bullet("Dark blue background (#0a1628)")
add_bullet("Cyan accent colors (#00b4d8)")
add_bullet("Neon green for wellness score (#00ff88)")
add_bullet("Glassmorphism cards with subtle borders")
add_bullet("Responsive: 2-column on desktop, 1-column on mobile")
add_bullet("Animated status dot (pulsing green)")

# ============================================================
# 7. FACE DETECTION & LANDMARKS
# ============================================================
doc.add_page_break()
add_heading1("7. Face Detection & Landmarks")

add_text("The app uses two models together for face analysis:")

add_bold("YuNet (Face Detection):")
add_bullet("Lightweight neural network model (~230KB)")
add_bullet("Detects face bounding box (x, y, width, height)")
add_bullet("Fast and accurate for real-time use")
add_bullet("Auto-downloaded on first run")

add_bold("dlib 68-point Landmark Predictor:")
add_bullet("Predicts 68 specific points on the face (~99MB model)")
add_bullet("Points 0-16: Jaw line")
add_bullet("Points 17-21: Left eyebrow")
add_bullet("Points 22-26: Right eyebrow")
add_bullet("Points 27-35: Nose")
add_bullet("Points 36-41: Left eye")
add_bullet("Points 42-47: Right eye")
add_bullet("Points 48-67: Mouth")

add_bold("68 Landmarks Map:")
add_code("""
        17----21   22----26        <- Eyebrows
         \\     |   |     /
          36-41   42-47            <- Eyes
              \\   /
               27-35              <- Nose
              /   \\
           48-------68            <- Mouth
           0-----------16         <- Jaw line
""")

# ============================================================
# 8. BLINK DETECTION
# ============================================================
add_heading1("8. How Blink Detection Works")

add_text("Blinks are detected from the Eye Aspect Ratio (EAR) with an adaptive baseline - one method, no brightness tricks:")

add_bold("Calibration + adaptive baseline:")
add_bullet("First 4 s: the engine collects EAR samples (seed phase) to get the first usable thresholds")
add_bullet("After that: baseline = running median of EAR over the last 10 s of frontal, open-eye frames")
add_bullet("Frames are skipped while a drowsiness alert is active and whenever the eye is deeply closed (EAR < 60% of baseline), so closures can never poison the median")
add_bullet("The window starts empty at calibration end and takes over within ~0.5 s, so a wide/narrow calibration moment stops mattering almost immediately")

add_bold("Thresholds (ratios of the baseline):")
add_bullet("Close: EAR < 0.75 x baseline = eye closing")
add_bullet("Open: EAR > 0.85 x baseline = eye reopened (hysteresis exit)")
add_bullet("Deep: EAR < 0.60 x baseline = closed eye, excluded from the baseline window")
add_bullet("Sanity clip: baseline is kept within 0.18-0.40 against garbage landmarks")

add_bold("Blink classification:")
add_bullet("A blink = 1-5 frames below the close threshold, lasting <= 0.4 s, then recovery above the open threshold")
add_bullet("Minimum 0.15 s gap between two counted blinks (debounce)")
add_bullet("0.4-1.5 s closure = slow closure (too long for a blink, feeds the drowsiness pattern rule)")
add_bullet("A turned/tilted head (yaw > 30 deg or pitch > 25 deg), a face-box jump, or a long face loss resets the timers - unreliable frames can never fake a closure")

add_bold("Rate Calculation:")
add_bullet("Blinks are kept in a rolling 60 s window")
add_bullet("Rate = (blinks in window / observed seconds) x 60 = blinks per minute")
add_bullet("During the first 15 s the window is the elapsed time, so the rate scales up instead of reading 0")

add_bold("Visual Example (baseline = 0.30):")
add_code("""
Frame 1: EAR = 0.30  eyes OPEN        (above open_thr 0.255)
Frame 2: EAR = 0.18  eye CLOSING      (below close_thr 0.225 - dip starts)
Frame 3: EAR = 0.15  eye CLOSED       (still below close_thr)
Frame 4: EAR = 0.26  eye REOPENED     (above open_thr) -> 3 frames, 0.3 s = BLINK
Frame 5: EAR = 0.31  eyes OPEN again

1 blink counted. The rolling 60 s window turns the count into blinks/min.
""")

add_bold("Drowsiness alert (same hysteresis, no extra model):")
add_bullet("Eyes held below the close threshold for >= 1.5 s -> sustained alert")
add_bullet("Or 3+ slow closures (0.4-1.5 s each) within 30 s -> repeated-pattern alert")
add_bullet("Banner hides after the eyes stay open for 4 s; events are rate-limited to 1 per 10 s")
add_bullet("The client requires 2 consecutive drowsy readings before showing the banner (flicker protection)")
add_bullet("Head-pose, shake and face-loss resets guarantee that looking down at the keyboard or turning away can never raise a false alert")

# ============================================================
# 9. EXPRESSION CLASSIFICATION
# ============================================================
doc.add_page_break()
add_heading1("9. How Expression is Classified")

add_text("Expression is determined by combining brow tension and eye openness (EAR):")

add_bold("Classification Rules:")
add_table(
    ["Brow Tension", "EAR (Eye Openness)", "Expression", "Meaning"],
    [
        ["> 25", "< 0.85 x baseline", "Stressed", "Tight brows + squinting = stress"],
        ["> 12", "Any", "Focused", "Slightly tight brows = concentrating"],
        ["<= 12", "Any", "Neutral", "Relaxed face = no stress"],
    ]
)

add_text("")
add_text("Brow tension is averaged over history for stability. This prevents expression from flickering between states rapidly.")

# ============================================================
# 10. WELLNESS SCORE
# ============================================================
add_heading1("10. How Wellness Score is Calculated")

add_bold("Starting score: 100 points")
add_text("")

add_bold("Penalties and Bonuses:")
add_table(
    ["Condition", "Penalty/Bonus", "Range"],
    [
        ["Blink rate > 25/min", "-25 points", "Over-blinking (irritation)"],
        ["Blink rate > 20/min", "-15 points", "Slightly fast blinks"],
        ["Blink rate < 8/min", "-20 points", "Barely blinking (screen staring)"],
        ["Blink rate < 10/min", "-15 points", "Under-blinking (screen fatigue)"],
        ["Blink rate < 12/min", "-5 points", "Slightly low blinks"],
        ["Brow tension (0-100)", "-0.4 per point", "Up to -40; more tension = more penalty"],
        ["Stressed expression", "-20 points", "Face shows stress"],
        ["Focused expression", "-8 points", "Face shows concentration"],
        ["EAR < 0.85 x baseline", "-5 points", "Squinting / heavy eyelids detected"],
    ]
)
add_text("Blink-rate penalties are paused during the first 15 s warm-up, before there is enough data to judge the rate.")

add_text("")
add_bold("Score Interpretation:")
add_table(
    ["Score Range", "Meaning", "Action"],
    [
        ["85-100", "Excellent", "Keep going, you are doing great"],
        ["70-84", "Good", "Consider a short break soon"],
        ["50-69", "Moderate", "Take a break, rest your eyes"],
        ["30-49", "Poor", "Stop working, take a real break"],
        ["0-29", "Critical", "You are very strained, rest now"],
    ]
)

# ============================================================
# 11. API ENDPOINTS
# ============================================================
doc.add_page_break()
add_heading1("11. API Endpoints")

add_table(
    ["Endpoint", "Method", "Description"],
    [
        ["/", "GET", "Dashboard page (main UI)"],
        ["/api/analyze/", "POST", "Send webcam frame, get wellness data + overlay image"],
        ["/api/latest/", "GET", "Get the most recent wellness reading"],
        ["/api/history/", "GET", "Get last 50 readings for session log"],
        ["/api/readings/", "GET", "Get readings from last 1 hour"],
        ["/api/sessions/", "GET", "Completed session history (chronological)"],
        ["/api/sessions/save/", "POST", "Persist a completed session report"],
        ["/api/sessions/clear/", "DELETE", "Clear all session history"],
        ["/ws/wellness/", "WebSocket", "Real-time wellness updates broadcast"],
    ]
)

# ============================================================
# 12. DATABASE
# ============================================================
add_heading1("12. Database Model")

add_bold("WellnessReading Table:")
add_table(
    ["Field", "Type", "Description"],
    [
        ["id", "AutoField", "Primary key"],
        ["timestamp", "DateTimeField", "Auto-set when record is created"],
        ["blink_rate", "FloatField", "Blinks per minute at time of reading"],
        ["brow_tension", "FloatField", "Brow tension value (0-100)"],
        ["expression", "CharField(20)", "neutral, focused, or stressed"],
        ["wellness_score", "FloatField", "Overall wellness score (0-100)"],
    ]
)

add_text("")
add_text("Readings are saved every 50 frames (approximately every 5 seconds) to avoid too many database writes. The session log in the frontend shows these saved readings.")

# ============================================================
# 13. WEBSOCKET
# ============================================================
add_heading1("13. WebSocket Flow")

add_bold("How real-time updates work:")
add_bullet("Browser connects to ws://127.0.0.1:8000/ws/wellness/")
add_bullet("Django Channels accepts the connection")
add_bullet("Client is added to wellness group channel")
add_bullet("When analysis is done, results are broadcast to all connected clients")
add_bullet("Each client receives the update and updates their dashboard")

add_text("")
add_text("WebSocket is used for broadcasting updates. The main analysis happens via HTTP POST to /api/analyze/. The WebSocket just relays the results to keep the dashboard live.")

# ============================================================
# 14. HOW TO RUN
# ============================================================
doc.add_page_break()
add_heading1("14. How to Run the Project")

add_bold("Prerequisites:")
add_bullet("Python 3.9 or higher")
add_bullet("Webcam connected to laptop")
add_bullet("pip (Python package manager)")

add_bold("Setup Steps:")
add_code("""
# Step 1: Open terminal and go to project folder
cd codestorm

# Step 2: Create virtual environment
python -m venv venv

# Step 3: Activate virtual environment
venv\\Scripts\\activate

# Step 4: Install dependencies
pip install -r requirements.txt

# Step 5: Apply database migrations
python manage.py migrate

# Step 6: Run the server
python manage.py runserver
""")

add_text("")
add_bold("Then:")
add_bullet("Open browser and go to http://127.0.0.1:8000/")
add_bullet("Click Start Camera button")
add_bullet("Allow webcam permission when browser asks")
add_bullet("You will see your face with green landmark dots")
add_bullet("Dashboard shows live score, chart, and tips")
add_bullet("Press Spacebar to start/stop camera")

# ============================================================
# 15. KEY NUMBERS
# ============================================================
add_heading1("15. Key Numbers to Remember")

add_table(
    ["What", "Value", "Notes"],
    [
        ["Normal blink rate", "12-20 per minute", "Below 10 = screen fatigue"],
        ["EAR when eyes open", "~0.30", "Eye Aspect Ratio"],
        ["EAR close threshold", "0.75 x baseline", "Adaptive per user (~0.22 at baseline 0.30)"],
        ["Blink definition", "1-5 frames, <=0.4 s", "Below close threshold, then reopened"],
        ["Calibration", "4 s seed + 10 s median", "Adaptive baseline takes over in ~0.5 s"],
        ["Rate window", "60 s rolling", "Scaled by observed time in first 15 s"],
        ["Drowsy alert", ">=1.5 s closure", "Or 3 slow closures (0.4-1.5 s) in 30 s"],
        ["Brow tension range", "0-100", "% drop from neutral x 3.0 gain"],
        ["Wellness score range", "0-100", "100 = perfect health"],
        ["Frame rate (FPS)", "10-12", "Captures per second"],
        ["Frame size sent", "320 x 200", "Resized for faster processing"],
        ["DB save frequency", "Every 50 frames", "About every 5 seconds"],
        ["Chart data points", "30 max", "Oldest shifted out"],
        ["Session log entries", "10 max", "Newest on top"],
        ["Session entry interval", "2 seconds", "Debounced"],
    ]
)

# ============================================================
# END
# ============================================================
doc.add_page_break()
add_heading1("End of Document")
add_text("This document covers the complete Wellness Signal Tracker project. All files, all logic, all calculations are explained above.")
add_text("")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("Built for CodeStorm Hackathon")
run.italic = True

output_path = r"C:\Users\Kreeshma\OneDrive\Desktop\Wellness_Signal_Tracker_Project_Notes.docx"
doc.save(output_path)
print(f"Document saved to: {output_path}")
