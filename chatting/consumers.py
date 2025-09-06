import json
from urllib.parse import unquote
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Message
import hashlib
from .tasks import send_unseen_message_email_task
import pytz
from django.core.cache import cache

# Utility functions
def get_current_datetime():
    """Return current IST datetime as string."""
    ist = pytz.timezone('Asia/Kolkata')
    return timezone.now().astimezone(ist).strftime("%Y-%m-%d %I:%M %p")

def get_safe_group_name(room_name):
    """Convert any room name to a safe ASCII string using SHA-256"""
    hashed = hashlib.sha256(room_name.encode()).hexdigest()
    return f"chat_{hashed}"


# Chat room-level consumer
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        raw_room_name = unquote(self.scope['url_route']['kwargs']['room_name'])
        self.room_name = raw_room_name
        self.room_group_name = get_safe_group_name(self.room_name)

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
        try:
            data = json.loads(text_data)
            event_type = data.get("type")

            if event_type == "chat":
                await self.handle_chat_message(data)

            elif event_type == "seen":
                await self.handle_seen_event(data)

            else:
                await self.send(text_data=json.dumps({"error": "Invalid event type"}))

        except Exception as e:
            await self.send(text_data=json.dumps({"error": str(e)}))

    # ----------------- Handlers -----------------
    async def handle_chat_message(self, data):
        sender_username = data.get('sender')
        receiver_username = data.get('receiver')
        message = data.get('message')
        temp_id = data.get('tempId')

        if not sender_username or not receiver_username or not message:
            await self.send(json.dumps({"error": "Missing sender, receiver, or message"}))
            return

        saved_message = await self.save_message(sender_username, receiver_username, message)

        # Broadcast to chat room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'id': saved_message.id,
                'sender': sender_username,
                'receiver': receiver_username,
                'message': message,
                'temp_id': temp_id
            }
        )

        # Broadcast to sender & receiver user notifications
        await self.send_user_notifications(saved_message)

    async def handle_seen_event(self, data):
        message_id = data.get('message_id')
        if not message_id:
            await self.send(json.dumps({"error": "Missing message_id"}))
            return

        await self.mark_message_seen(message_id)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'message_seen',
                'message_id': message_id
            }
        )

    # ----------------- WebSocket event handlers -----------------
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'id': event['id'],
            'sender': event['sender'],
            'receiver': event['receiver'],
            'message': event['message'],
            'temp_id': event.get('temp_id')
        }))

    async def message_seen(self, event):
        await self.send(text_data=json.dumps({
            'type': 'seen',
            'message_id': event['message_id']
        }))

    async def edit_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "edit",
            "id": event["id"],
            "new_content": event["new_content"]
        }))

    async def delete_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "delete",
            "id": event["id"]
        }))

    # ----------------- DB operations -----------------
    @database_sync_to_async
    def save_message(self, sender_username, receiver_username, message):
        sender = User.objects.filter(username=sender_username).first()
        receiver = User.objects.filter(username=receiver_username).first()

        if not sender:
            raise ValueError(f"Sender '{sender_username}' does not exist.")
        if not receiver:
            raise ValueError(f"Receiver '{receiver_username}' does not exist.")

        msg = Message.objects.create(
            sender=sender,
            receiver=receiver,
            content=message
        )

        # Schedule email if not already scheduled
        cache_key = f"email_scheduled_receiver_{receiver.id}"
        if not cache.get(cache_key):
            send_unseen_message_email_task.apply_async(
                args=(sender.id, receiver.id),
                countdown=3600
            )
            cache.set(cache_key, True, timeout=4500)

        return msg

    @database_sync_to_async
    def mark_message_seen(self, message_id):
        msg = Message.objects.filter(id=message_id).first()
        if msg and not msg.is_seen:
            msg.is_seen = True
            msg.seen_at = get_current_datetime()
            msg.save()

    async def send_user_notifications(self, message_obj):
        sender = message_obj.sender
        receiver = message_obj.receiver

        for user in [sender, receiver]:
            await self.channel_layer.group_send(
                f"user_notifications_{user.id}",
                {
                    'type': 'new_message_notification',
                    'id': message_obj.id,
                    'sender': sender.username,
                    'receiver': receiver.username,
                    'message': message_obj.content,
                    'timestamp': str(message_obj.timestamp),
                    'is_seen': message_obj.is_seen,
                    'unseen_count': await self.get_unseen_count(user)
                }
            )

    @database_sync_to_async
    def get_unseen_count(self, user):
        return Message.objects.filter(receiver=user, is_seen=False).count()


# ----------------- User-level notifications -----------------
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        self.group_name = f"user_notifications_{self.user.id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def new_message_notification(self, event):
        payload = {
            'type': 'new_message_notification',
            'id': event.get('id'),
            'sender': event.get('sender'),
            'receiver': event.get('receiver'),
            'message': event.get('message'),
            'timestamp': event.get('timestamp'),
            'is_seen': event.get('is_seen', False),
            'unseen_count': event.get('unseen_count', 0),
        }
        await self.send(text_data=json.dumps(payload))


