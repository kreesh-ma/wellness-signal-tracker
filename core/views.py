from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import base64
import numpy as np
import cv2
import dlib
from .models import WellnessReading
from .face_analyzer import FaceAnalyzer
from .wellness_engine import WellnessEngine
from django.utils import timezone
from datetime import timedelta

# initialize analyzer and engine
face_analyzer = FaceAnalyzer()
wellness_engine = WellnessEngine()

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
    reading = WellnessReading.objects.first()
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

@csrf_exempt
@require_POST
def analyze_frame(request):
    try:
        print("Received analyze request")
        data = json.loads(request.body)
        image_data = data.get('image')
        
        if not image_data:
            print("No image data")
            return JsonResponse({'error': 'No image data'}, status=400)
        
        # decode base64 image
        image_data = image_data.split(',')[1] if ',' in image_data else image_data
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            print("Invalid image")
            return JsonResponse({'error': 'Invalid image'}, status=400)
        
        # ensure frame is correct type
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        
        print(f"Frame shape: {frame.shape}, dtype: {frame.dtype}")
        
        # analyze frame
        result = face_analyzer.analyze_frame(frame)
        
        if result is None:
            print("No face detected")
            return JsonResponse({
                'face_detected': False,
                'landmarks': []
            })
        
        print(f"Face detected, EAR: {result['ear']:.3f}")
        
        # process wellness data
        # extract eye region for motion-based blink detection
        landmarks = np.array(result['landmarks'])
        left_eye = landmarks[36:42]
        right_eye = landmarks[42:48]
        
        # get bounding box of eyes
        all_eye_pts = np.concatenate([left_eye, right_eye])
        ex, ey = all_eye_pts.min(axis=0)
        ew, eh = all_eye_pts.max(axis=0) - all_eye_pts.min(axis=0)
        
        # extract eye region from frame with padding
        ey = max(0, int(ey) - 10)
        ex = max(0, int(ex) - 10)
        eh = int(eh) + 20
        ew = int(ew) + 20
        
        eye_region = None
        if eh > 0 and ew > 0 and ey + eh <= frame.shape[0] and ex + ew <= frame.shape[1]:
            eye_region = frame[ey:ey+eh, ex:ex+ew]
        
        wellness = wellness_engine.process_reading(result['ear'], result['brow_tension'], eye_region)
        
        # save to database every 5 seconds
        wellness_engine.frame_count += 1
        if wellness_engine.frame_count % 50 == 0:  # ~every 5 sec at 10fps
            WellnessReading.objects.create(
                blink_rate=wellness['blink_rate'],
                brow_tension=wellness['brow_tension'],
                expression=wellness['expression'],
                wellness_score=wellness['wellness_score']
            )
        
        # draw landmarks on frame
        landmarks = np.array(result['landmarks'])
        face_rect = dlib.rectangle(
            result['face_rect']['left'],
            result['face_rect']['top'],
            result['face_rect']['right'],
            result['face_rect']['bottom']
        )
        overlay = face_analyzer.draw_landmarks(frame, landmarks, face_rect)
        
        # encode overlay to base64
        _, buffer = cv2.imencode('.jpg', overlay)
        overlay_base64 = base64.b64encode(buffer).decode('utf-8')
        
        print("Returning result with overlay")
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
