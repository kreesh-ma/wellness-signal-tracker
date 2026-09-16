# Wellness Signal Tracker — Demo Script

**Duration:** ~2:45

---

## Opening (0:00 - 0:15)
"Hi, I'm Kreeshma. Today I'll demo the Wellness Signal Tracker, a real-time facial analysis system that monitors screen fatigue and stress indicators during long work sessions."

## Show Dashboard (0:15 - 0:30)
"This is the main dashboard. It shows real-time metrics from your webcam. We have Wellness Score, Blink Rate, Brow Tension, Expression, and FPS counter."

## Start Camera (0:30 - 1:00)
"Now I'll start the camera. When I click Start Camera, the system begins tracking my face. You can see the green box around my face and the facial landmarks - eyes in cyan, eyebrows in blue, and mouth in orange."

## Blink Rate Demo (1:00 - 1:15)
"Let me demonstrate blink detection. I'll blink a few times. Watch the blink rate metric. It counts blinks per minute. Normal is 12 to 20 blinks per minute."

## Brow Tension Demo (1:15 - 1:30)
"Now I'll raise my eyebrows. See how the brow tension increases? It measures the distance between eyebrows and eyes. Higher tension means more stress."

## Expression Demo (1:30 - 1:45)
"When I look stressed, the expression changes to stressed and the wellness score drops. The system classifies expressions as neutral, focused, or stressed."

## Wellness Score Demo (1:45 - 2:00)
"The wellness score is a composite of all these metrics. It starts at 100 and drops with abnormal patterns. It helps users identify when to take breaks."

## Chart Demo (2:00 - 2:15)
"This chart shows the wellness score and blink rate over time. You can see trends and patterns during the session."

## Technical Overview (2:15 - 2:30)
"Under the hood, we use YuNet for face detection, dlib for 68 facial landmarks, Django Channels for real-time WebSocket updates, and all processing happens server-side."

## Closing (2:30 - 2:45)
"The Wellness Signal Tracker helps users identify early signs of screen fatigue and take breaks before burnout. Thank you for watching."
