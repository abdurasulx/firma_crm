import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # In our middleware, we split by subdomain. 
        # But Channels scope doesn't automatically have 'subdomain'.
        # We can extract it from the 'host' header.
        headers = dict(self.scope['headers'])
        host = headers.get(b'host', b'').decode()
        subdomain = host.split('.')[0] if '.' in host else 'default'
        logger.debug(
            "WS connect attempt user=%s authenticated=%s host=%s",
            self.scope['user'],
            self.scope['user'].is_authenticated,
            host,
        )
        
        if self.scope["user"].is_authenticated:
            self.group_name = f"notifications_{subdomain}"
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                lat = data.get('lat')
                lng = data.get('lng')
                if lat and lng:
                    await self.update_deliverer_location(lat, lng)
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except Exception as e:
            print(f"WS Receive Error: {e}")

    @database_sync_to_async
    def update_deliverer_location(self, lat, lng):
        from .models import YetkazibBeruvchi, LocationHistory
        from django.utils import timezone
        try:
            user = self.scope["user"]
            if user.is_authenticated:
                # Use filter().first() to avoid exception if not a deliverer
                yt = YetkazibBeruvchi.objects.filter(user=user).first()
                if yt:
                    yt.last_lat = float(lat)
                    yt.last_lng = float(lng)
                    yt.last_active = timezone.now()
                    yt.save(update_fields=['last_lat', 'last_lng', 'last_active'])
                    
                    # Create location history
                    LocationHistory.objects.create(
                        yetkazib_beruvchi=yt,
                        company=yt.company,
                        lat=float(lat),
                        lng=float(lng)
                    )
                else:
                    pass
        except Exception as e:
            print(f"Error updating location: {e}")

    # Receive message from room group
    async def send_notification(self, event):
        message = event['message']
        title = event['title']
        notif_type = event.get('notification_type', 'info') # 'success', 'info', 'warning'

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'title': title,
            'message': message,
            'type': notif_type
        }))
