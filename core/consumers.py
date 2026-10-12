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
        # Client sends wellness data - just broadcast to group
        # Don't save to DB here (analysis view handles persistence)
        # Don't trust client data for anything critical
        data = json.loads(text_data)
        
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
