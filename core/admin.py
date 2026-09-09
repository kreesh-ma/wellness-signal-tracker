from django.contrib import admin
from .models import WellnessReading

@admin.register(WellnessReading)
class WellnessReadingAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'blink_rate', 'brow_tension', 'expression', 'wellness_score']
    list_filter = ['expression', 'timestamp']
    search_fields = ['expression']
    ordering = ['-timestamp']
