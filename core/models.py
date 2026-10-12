from django.db import models

class WellnessReading(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    blink_rate = models.FloatField()
    brow_tension = models.FloatField()
    expression = models.CharField(max_length=20)
    wellness_score = models.FloatField()
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.timestamp} - Score: {self.wellness_score}"


class SessionRecord(models.Model):
    """One completed monitoring session (computed client-side from real data)."""
    timestamp = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.PositiveIntegerField()
    focus_score = models.FloatField()
    attention_stability = models.FloatField()
    blink_rate = models.FloatField()
    blink_rate_label = models.CharField(max_length=20)
    drowsiness_events = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - focus: {self.focus_score:.0f}%"

    def as_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'duration_seconds': self.duration_seconds,
            'focus_score': round(self.focus_score, 1),
            'attention_stability': round(self.attention_stability, 1),
            'blink_rate': round(self.blink_rate, 1),
            'blink_rate_label': self.blink_rate_label,
            'drowsiness_events': self.drowsiness_events,
        }
