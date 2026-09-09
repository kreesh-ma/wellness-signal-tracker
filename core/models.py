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
