import json
from urllib.parse import unquote
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Message
import hashlib
from .tasks import send_unseen_message_email_task
from datetime import datetime
import pytz
from django.core.cache import cache
from user.utils import user_cache_key
from datetime import timedelta
from django.utils.timezone import now


def get_current_datetime():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).strftime("%Y-%m-%d %I:%M %p")

def get_safe_group_name(room_name):
    """Convert any room name to a safe ASCII string using SHA-256"""
    hashed = hashlib.sha256(room_name.encode()).hexdigest()
    return f"chat_{hashed}"


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        raw_room_name = unquote(self.scope['url_route']['kwargs']['room_name'])
        self.room_name = raw_room_name  # Display/DB version
        self.room_group_name = get_safe_group_name(self.room_name)  # Channels-safe version

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
                await self.send(text_data=json.dumps({
                    "error": "Invalid event type"
                }))

        except Exception as e:
            await self.send(text_data=json.dumps({
                "error": str(e)
            }))

    async def handle_chat_message(self, data):
        sender_username = data.get('sender')
        receiver_username = data.get('receiver')
        message = data.get('message')
        temp_id = data.get('tempId') 

        if not sender_username or not receiver_username or not message:
            await self.send(json.dumps({"error": "Missing sender, receiver, or message"}))
            return

        saved_message = await self.save_message(sender_username, receiver_username, message)

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
        
        
        # ✅ Schedule email if not already scheduled for this receiver
        cache_key = f"email_scheduled_receiver_{receiver.id}"
        if not cache.get(cache_key):
            send_unseen_message_email_task.apply_async(
                args=(sender.id, receiver.id),  # we only need sender and receiver id now
                countdown=15  # wait 15 seconds to batch messages
            )
            cache.set(cache_key, True, timeout=30)


        return msg

    @database_sync_to_async
    def mark_message_seen(self, message_id):
        msg = Message.objects.filter(id=message_id).first()
        if msg and not msg.is_seen:
            msg.is_seen = True
            msg.seen_at = get_current_datetime()
            msg.save()