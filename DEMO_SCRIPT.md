# Demo Script - Wellness Signal Tracker

## Duration: 2-3 minutes

---

### Opening (15 seconds)
"Hi, I'm [Name]. Today I'll demo the Wellness Signal Tracker — a real-time facial analysis system that monitors screen fatigue and stress indicators during long work sessions."

### Show Dashboard (30 seconds)
1. Open `http://127.0.0.1:8000`
2. "This is the main dashboard. It shows real-time metrics from your webcam."
3. Point out: Wellness Score, Blink Rate, Brow Tension, Expression, FPS

### Start Camera (45 seconds)
1. Click "Start Camera"
2. "When I enable the camera, the system starts tracking my face."
3. Show: Green face box, landmarks (eyes, eyebrows, mouth)
4. "The 68 facial landmarks are detected using dlib, and metrics are calculated in real-time."

### Demonstrate Metrics (60 seconds)

**Blink Rate:**
1. "Watch the blink rate. When I blink normally..."
2. Blink 5-6 times
3. "See? The blink rate updates. Normal is 12-20 blinks per minute."

**Brow Tension:**
1. "Now let me raise my eyebrows..."
2. Raise eyebrows
3. "The brow tension increases as my eyebrows move closer to my eyes."

**Expression:**
1. "When I look stressed..."
2. Frown slightly
3. "The expression changes to 'stressed' and the wellness score drops."

**Wellness Score:**
1. "The wellness score is a composite of all these metrics."
2. "It starts at 100 and drops with abnormal patterns."

### Show Chart (30 seconds)
1. "This chart shows the wellness score and blink rate over time."
2. "You can see the trends and patterns during the session."

### Show Tips (15 seconds)
1. "Based on the current state, the system provides wellness tips."
2. Show the tip card at the bottom

### Technical Overview (30 seconds)
"Under the hood:
- YuNet for face detection
- dlib for 68 facial landmarks
- Django Channels for real-time WebSocket updates
- All processing happens server-side"

### Closing (15 seconds)
"The Wellness Signal Tracker helps users identify early signs of screen fatigue and take breaks before burnout. Thank you!"

---

## Key Points to Highlight
- Real-time processing (12+ FPS)
- Accurate face detection
- Responsive dashboard
- Wellness tips
- Historical data tracking

## Troubleshooting
- If camera doesn't start: Check browser permissions
- If low FPS: Close other apps using camera
- If no face detected: Ensure good lighting