import time
from collections import deque
import numpy as np

class WellnessEngine:
    def __init__(self):
        self.blink_history = deque(maxlen=300)
        self.brow_history = deque(maxlen=300)
        self.last_blink_time = time.time()
        self.blink_count = 0
        self.blink_rate = 0
        self.blinking = False
        self.prev_eye_mean = None
        self.frame_count = 0
        self.last_blink_trigger = 0
        self.MIN_BLINK_INTERVAL = 0.3
        self.ear_history = deque(maxlen=10)
        
    def update_blink(self, ear, eye_region=None):
        current_time = time.time()
        self.ear_history.append(ear)
        
        if eye_region is not None and eye_region.size > 0:
            current_mean = np.mean(eye_region)
            if self.prev_eye_mean is not None:
                diff = current_mean - self.prev_eye_mean
                time_since_last = current_time - self.last_blink_trigger
                
                if diff < -3 and not self.blinking and time_since_last > self.MIN_BLINK_INTERVAL:
                    self.blinking = True
                    self.blink_count += 1
                    self.last_blink_trigger = current_time
                elif diff > 1.5:
                    self.blinking = False
                    
            self.prev_eye_mean = current_mean
        
        # EAR-based detection as primary method
        avg_ear = np.mean(self.ear_history) if self.ear_history else ear
        time_since_last = current_time - self.last_blink_trigger
        
        if avg_ear < 0.20 and not self.blinking and time_since_last > self.MIN_BLINK_INTERVAL:
            self.blinking = True
            self.blink_count += 1
            self.last_blink_trigger = current_time
        elif avg_ear > 0.25 and self.blinking:
            self.blinking = False
            
        elapsed = current_time - self.last_blink_time
        if elapsed >= 2.0:
            self.blink_rate = round((self.blink_count / elapsed) * 60)
            self.blink_count = 0
            self.last_blink_time = current_time
            
        self.blink_history.append(self.blink_rate)
        
    def classify_expression(self, brow_tension, ear):
        if brow_tension > 50 and ear < 0.25:
            return 'Stressed'
        elif brow_tension > 25:
            return 'Focused'
        else:
            return 'Neutral'
    
    def calculate_wellness_score(self, blink_rate, brow_tension, expression):
        score = 100
        
        if blink_rate == 0:
            pass
        elif blink_rate > 20 or blink_rate < 10:
            score -= 15
        elif blink_rate > 15 or blink_rate < 12:
            score -= 8
            
        score -= brow_tension * 0.25
        
        if expression == 'Stressed':
            score -= 20
        elif expression == 'Focused':
            score -= 5
            
        return max(0, min(100, round(score)))
    
    def get_wellness_tip(self, score, expression):
        if score < 50:
            return "Take a deep breath. Roll your shoulders back."
        elif expression == 'Stressed':
            return "Try the 20-20-20 rule: Look 20ft away for 20 sec."
        elif expression == 'Focused':
            return "Great focus! Consider a short break soon."
        else:
            return "You're doing well. Keep it up!"
    
    def process_reading(self, ear, brow_tension, eye_region=None):
        self.update_blink(ear, eye_region)
        expression = self.classify_expression(brow_tension, ear)
        
        # normalize brow tension: raw is typically 15-50, map to 0-100
        normalized_brow = max(0, min(100, (brow_tension - 15) * 2.5))
        
        score = self.calculate_wellness_score(self.blink_rate, normalized_brow, expression)
        tip = self.get_wellness_tip(score, expression)
        
        return {
            'blink_rate': self.blink_rate,
            'brow_tension': round(normalized_brow, 1),
            'expression': expression,
            'wellness_score': score,
            'tip': tip
        }
