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
        self.last_blink_trigger = 0  # debounce
        self.MIN_BLINK_INTERVAL = 0.25  # minimum 250ms between blinks
        
    def update_blink(self, ear, eye_region=None):
        current_time = time.time()
        
        # motion-based blink detection
        if eye_region is not None and eye_region.size > 0:
            current_mean = np.mean(eye_region)
            if self.prev_eye_mean is not None:
                diff = current_mean - self.prev_eye_mean  # direction matters
                time_since_last = current_time - self.last_blink_trigger
                
                # blink = quick darkening (diff < -threshold) then brightening
                if diff < -5 and not self.blinking and time_since_last > self.MIN_BLINK_INTERVAL:
                    self.blinking = True
                    self.blink_count += 1
                    self.last_blink_trigger = current_time
                elif diff > 2:
                    self.blinking = False
                    
            self.prev_eye_mean = current_mean
        else:
            # fallback to EAR-based detection
            time_since_last = current_time - self.last_blink_trigger
            if ear < 0.18 and not self.blinking and time_since_last > self.MIN_BLINK_INTERVAL:
                self.blinking = True
                self.blink_count += 1
                self.last_blink_trigger = current_time
            elif ear > 0.22 and self.blinking:
                self.blinking = False
            
        # calculate rate every 2 seconds for smoother updates
        elapsed = current_time - self.last_blink_time
        if elapsed >= 2.0:
            self.blink_rate = round((self.blink_count / elapsed) * 60)
            self.blink_count = 0
            self.last_blink_time = current_time
            
        self.blink_history.append(self.blink_rate)
        
    def classify_expression(self, brow_tension, ear):
        if brow_tension > 60 and ear < 0.25:
            return 'stressed'
        elif brow_tension > 40:
            return 'focused'
        else:
            return 'neutral'
    
    def calculate_wellness_score(self, blink_rate, brow_tension, expression):
        score = 100
        
        if blink_rate > 20 or (blink_rate > 0 and blink_rate < 10):
            score -= 20
        elif blink_rate > 15 or (blink_rate > 0 and blink_rate < 12):
            score -= 10
            
        normalized_brow = brow_tension / 100.0
        score -= normalized_brow * 30
        
        if expression == 'stressed':
            score -= 25
        elif expression == 'focused':
            score -= 10
            
        return max(0, min(100, score))
    
    def get_wellness_tip(self, score, expression):
        if score < 50:
            return "Take a deep breath. Roll your shoulders back."
        elif expression == 'stressed':
            return "Try the 20-20-20 rule: Look 20ft away for 20 sec."
        elif expression == 'focused':
            return "Great focus! Consider a short break soon."
        else:
            return "You're doing well. Keep it up!"
    
    def process_reading(self, ear, brow_tension, eye_region=None):
        self.update_blink(ear, eye_region)
        expression = self.classify_expression(brow_tension, ear)
        
        # normalize brow tension: raw is typically 30-60, map to 0-100
        normalized_brow = max(0, min(100, (brow_tension - 30) * 3.33))
        
        score = self.calculate_wellness_score(self.blink_rate, normalized_brow, expression)
        tip = self.get_wellness_tip(score, expression)
        
        return {
            'blink_rate': self.blink_rate,
            'brow_tension': round(normalized_brow, 1),
            'expression': expression,
            'wellness_score': round(score),
            'tip': tip
        }
