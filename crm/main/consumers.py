import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


def optional_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

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
                location_saved = False
                location_error = None
                if lat and lng:
                    location_saved, location_error = await self.update_deliverer_location(data)
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'location_saved': location_saved,
                    'location_error': location_error,
                }))
        except Exception as e:
            print(f"WS Receive Error: {e}")

    @database_sync_to_async
    def update_deliverer_location(self, data):
        from .models import YetkazibBeruvchi, LocationHistory
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime
        try:
            user = self.scope["user"]
            if user.is_authenticated:
                # Use filter().first() to avoid exception if not a deliverer
                yt = YetkazibBeruvchi.objects.filter(user=user).first()
                if yt:
                    lat = float(data.get('lat'))
                    lng = float(data.get('lng'))
                    client_timestamp = parse_datetime(data.get('client_timestamp') or '') if data.get('client_timestamp') else None
                    if client_timestamp and timezone.is_naive(client_timestamp):
                        client_timestamp = timezone.make_aware(client_timestamp, timezone.get_current_timezone())
                    yt.last_lat = float(lat)
                    yt.last_lng = float(lng)
                    yt.last_active = timezone.now()
                    yt.save(update_fields=['last_lat', 'last_lng', 'last_active'])
                    
                    # Create location history
                    if not client_timestamp or not LocationHistory.objects.filter(
                        yetkazib_beruvchi=yt,
                        client_timestamp=client_timestamp,
                    ).exists():
                        LocationHistory.objects.create(
                            yetkazib_beruvchi=yt,
                            company=yt.company,
                            lat=lat,
                            lng=lng,
                            timestamp=client_timestamp or timezone.now(),
                            client_timestamp=client_timestamp,
                            accuracy=optional_float(data.get('accuracy')),
                            speed=optional_float(data.get('speed')),
                            source=data.get('source') or 'websocket',
                        )
                    return True, None
                else:
                    return False, "deliverer_profile_not_found"
        except Exception as e:
            print(f"Error updating location: {e}")
            return False, str(e)
        return False, "unauthenticated"

    # Receive message from room group
    async def send_notification(self, event):
        message = event['message']
        title = event['title']
        notif_type = event.get('notification_type', 'info') # 'success', 'info', 'warning'
        refresh = event.get('refresh', False)

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'title': title,
            'message': message,
            'type': notif_type,
            'refresh': refresh,
        }))


class SuperAdminConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not (user.is_authenticated and user.is_superuser):
            await self.close()
            return

        self.group_name = "superadmin"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_superadmin_update({
            "payload": await self.get_payload()
        })

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get("type") in {"ping", "refresh"}:
            await self.send_superadmin_update({
                "payload": await self.get_payload()
            })

    async def send_superadmin_update(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def get_payload(self):
        from landing.realtime import get_superadmin_payload
        return get_superadmin_payload()
