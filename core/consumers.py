import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import WellnessReading

class WellnessConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'wellness'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        await self.save_reading(data)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'wellness_update',
                'data': data
            }
        )
    
    async def wellness_update(self, event):
        data = event['data']
        await self.send(text_data=json.dumps(data))
    
    @database_sync_to_async
    def save_reading(self, data):
        WellnessReading.objects.create(
            blink_rate=data.get('blink_rate', 0),
            brow_tension=data.get('brow_tension', 0),
            expression=data.get('expression', 'neutral'),
            wellness_score=data.get('wellness_score', 100)
        )
