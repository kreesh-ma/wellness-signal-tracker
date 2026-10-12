from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import base64
import time
import numpy as np
import cv2
import dlib
from .models import WellnessReading, SessionRecord
from .face_analyzer import FaceAnalyzer
from .wellness_engine import WellnessEngine
from django.utils import timezone
from datetime import timedelta

face_analyzer = FaceAnalyzer()

# Wellness state is kept in-process, keyed by session id. Round-tripping it
# through the session DB on every frame (serialise + UPDATE) added latency and
# made calibration restart-prone. One worker process - fine for dev/daphne.
_ENGINE_CACHE = {}
_ENGINE_CACHE_MAX = 64

def get_wellness_engine(session):
    if session.session_key is None:
        session.create()
    key = session.session_key

    cached = _ENGINE_CACHE.get(key)
    if cached is not None:
        cached[1] = time.time()
        return cached[0]

    engine = WellnessEngine()
    engine.frame_count = 0
    engine.session_start_time = time.time()

    if len(_ENGINE_CACHE) >= _ENGINE_CACHE_MAX:
        stalest = min(_ENGINE_CACHE, key=lambda k: _ENGINE_CACHE[k][1])
        _ENGINE_CACHE.pop(stalest, None)
    _ENGINE_CACHE[key] = [engine, time.time()]
    return engine

def dashboard(request):
    return render(request, 'dashboard.html')

def get_readings(request):
    last_hour = timezone.now() - timedelta(hours=1)
    readings = WellnessReading.objects.filter(timestamp__gte=last_hour)
    
    data = {
        'timestamps': [r.timestamp.strftime('%H:%M:%S') for r in readings],
        'blink_rates': [r.blink_rate for r in readings],
        'brow_tensions': [r.brow_tension for r in readings],
        'scores': [r.wellness_score for r in readings],
    }
    return JsonResponse(data)

def get_latest(request):
    reading = WellnessReading.objects.order_by('-timestamp').first()
    if reading:
        data = {
            'blink_rate': reading.blink_rate,
            'brow_tension': reading.brow_tension,
            'expression': reading.expression,
            'wellness_score': reading.wellness_score,
            'timestamp': reading.timestamp.strftime('%H:%M:%S'),
        }
    else:
        data = {
            'blink_rate': 0,
            'brow_tension': 0,
            'expression': 'neutral',
            'wellness_score': 100,
            'timestamp': '--:--:--',
        }
    return JsonResponse(data)

def get_history(request):
    readings = WellnessReading.objects.all()[:50]
    data = {
        'timestamps': [r.timestamp.strftime('%H:%M:%S') for r in readings],
        'blink_rates': [r.blink_rate for r in readings],
        'brow_tensions': [r.brow_tension for r in readings],
        'scores': [r.wellness_score for r in readings],
        'expressions': [r.expression for r in readings],
    }
    return JsonResponse(data)

# --- Session history (completed monitoring sessions) ---

def get_sessions(request):
    """Chronological list of completed sessions (oldest first for trends)."""
    sessions = list(SessionRecord.objects.all().order_by('timestamp'))
    return JsonResponse({'sessions': [s.as_dict() for s in sessions]})

@csrf_exempt
def save_session(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
        duration = int(float(data.get('duration_seconds', 0)))
        if duration <= 0:
            return JsonResponse({'error': 'Invalid session duration'}, status=400)

        record = SessionRecord.objects.create(
            duration_seconds=min(duration, 24 * 3600),
            focus_score=max(0.0, min(100.0, float(data.get('focus_score', 0)))),
            attention_stability=max(0.0, min(100.0, float(data.get('attention_stability', 0)))),
            blink_rate=max(0.0, float(data.get('blink_rate', 0))),
            blink_rate_label=str(data.get('blink_rate_label', 'Normal'))[:20],
            drowsiness_events=max(0, int(data.get('drowsiness_events', 0))),
        )
        return JsonResponse({'session': record.as_dict()})
    except Exception as e:
        print(f"Session save error: {e}")
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def clear_sessions(request):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)
    deleted, _ = SessionRecord.objects.all().delete()
    return JsonResponse({'deleted': deleted})

@csrf_exempt
@require_POST
def analyze_frame(request):
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        
        if not image_data:
            print("No image data")
            return JsonResponse({'error': 'No image data'}, status=400)
        
        image_data = image_data.split(',')[1] if ',' in image_data else image_data
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            print("Invalid image")
            return JsonResponse({'error': 'Invalid image'}, status=400)
        
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        
        result = face_analyzer.analyze_frame(frame)

        if result is None:
            # Face was lost: reset the engine's closure timer on the next frame
            # so a lost face can never fake a drowsy episode.
            get_wellness_engine(request.session).note_face_lost()
            return JsonResponse({
                'face_detected': False,
                'landmarks': []
            })
        
        ear = result['ear']

        wellness_engine = get_wellness_engine(request.session)

        if data.get('reset_session'):
            wellness_engine.reset_drowsiness()

        wellness = wellness_engine.process_reading(
            ear, result['brow_tension'], face_rect=result['face_rect'],
            head_pose=result.get('head_pose'))

        wellness_engine.frame_count += 1

        if wellness_engine.frame_count % 50 == 0:
            WellnessReading.objects.create(
                blink_rate=wellness['blink_rate'],
                brow_tension=wellness['brow_tension'],
                expression=wellness['expression'],
                wellness_score=wellness['wellness_score']
            )
        
        landmarks = np.array(result['landmarks'])
        face_rect = dlib.rectangle(
            result['face_rect']['left'],
            result['face_rect']['top'],
            result['face_rect']['right'],
            result['face_rect']['bottom']
        )
        overlay = face_analyzer.draw_landmarks(frame, landmarks, face_rect)
        
        _, buffer = cv2.imencode('.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, 80])
        overlay_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return JsonResponse({
            'face_detected': True,
            'landmarks': result['landmarks'],
            'face_rect': result['face_rect'],
            'overlay': f'data:image/jpeg;base64,{overlay_base64}',
            'wellness': wellness
        })
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
