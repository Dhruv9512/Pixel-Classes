import json
import logging
from urllib.parse import unquote, parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Message
import hashlib
from .tasks import send_unseen_message_email_task
import pytz
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ObjectDoesNotExist
from asgiref.sync import async_to_sync

# ---------------- Logging ----------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ---------------- Utility functions ----------------
def get_current_datetime():
    """Return current IST datetime as string."""
    ist = pytz.timezone('Asia/Kolkata')
    return timezone.now().astimezone(ist).strftime("%Y-%m-%d %I:%M %p")

def get_safe_group_name(room_name):
    """Convert any room name to a safe ASCII string using SHA-256"""
    hashed = hashlib.sha256(room_name.encode()).hexdigest()
    return f"chat_{hashed}"


# ---------------- ChatConsumer ----------------
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        raw_room_name = unquote(self.scope['url_route']['kwargs']['room_name'])
        self.room_name = raw_room_name
        self.room_group_name = get_safe_group_name(self.room_name)
        logger.info(f"[WS CONNECT] Connecting to room: {self.room_name} -> Group: {self.room_group_name}")

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info(f"[WS CONNECT] Connection accepted for room: {self.room_name}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info(f"[WS DISCONNECT] Disconnected from room: {self.room_name}, code: {close_code}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get("type")
            logger.info(f"[WS RECEIVE] Event type: {event_type}, Data: {data}")

            if event_type == "chat":
                await self.handle_chat_message(data)
            elif event_type == "seen":
                await self.handle_seen_event(data)
            else:
                await self.send(text_data=json.dumps({"error": "Invalid event type"}))
                logger.warning(f"[WS RECEIVE] Invalid event type: {event_type}")

        except Exception as e:
            await self.send(text_data=json.dumps({"error": str(e)}))
            logger.error(f"[WS RECEIVE] Exception: {e}", exc_info=True)

    # ---------------- Handlers ----------------
    async def handle_chat_message(self, data):
        sender_username = data.get('sender')
        receiver_username = data.get('receiver')
        message = data.get('message')
        temp_id = data.get('tempId')

        if not sender_username or not receiver_username or not message:
            await self.send(json.dumps({"error": "Missing sender, receiver, or message"}))
            logger.warning(f"[CHAT MESSAGE] Missing fields: {data}")
            return

        saved_message = await self.save_message(sender_username, receiver_username, message)
        logger.info(f"[CHAT MESSAGE] Saved message ID: {saved_message.id} from {sender_username} to {receiver_username}")

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

        # Broadcast to user notifications
        await self.send_user_notifications(saved_message)

    async def handle_seen_event(self, data):
        message_id = data.get('message_id')
        if not message_id:
            await self.send(json.dumps({"error": "Missing message_id"}))
            logger.warning("[SEEN EVENT] Missing message_id")
            return

        await self.mark_message_seen(message_id)
        logger.info(f"[SEEN EVENT] Message marked as seen: {message_id}")

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'message_seen',
                'message_id': message_id
            }
        )

    # ---------------- WebSocket event handlers ----------------
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'id': event['id'],
            'sender': event['sender'],
            'receiver': event['receiver'],
            'message': event['message'],
            'temp_id': event.get('temp_id')
        }))
        logger.info(f"[CHAT BROADCAST] Sent message ID: {event['id']} to WebSocket")

    async def message_seen(self, event):
        await self.send(text_data=json.dumps({
            'type': 'seen',
            'message_id': event['message_id']
        }))
        logger.info(f"[SEEN BROADCAST] Sent seen event for message ID: {event['message_id']}")

    async def edit_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "edit",
            "id": event["id"],
            "new_content": event["new_content"]
        }))
        logger.info(f"[EDIT BROADCAST] Edited message ID: {event['id']}")

    async def delete_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "delete",
            "id": event["id"]
        }))
        logger.info(f"[DELETE BROADCAST] Deleted message ID: {event['id']}")

    # ---------------- DB operations ----------------
    @database_sync_to_async
    def save_message(self, sender_username, receiver_username, message):
        sender = User.objects.filter(username=sender_username).first()
        receiver = User.objects.filter(username=receiver_username).first()

        if not sender or not receiver:
            logger.warning(f"[SAVE MESSAGE] Invalid sender or receiver: {sender_username}, {receiver_username}")
            raise ValueError("Sender or receiver does not exist")

        msg = Message.objects.create(sender=sender, receiver=receiver, content=message)

        # Schedule email if not already scheduled
        cache_key = f"email_scheduled_receiver_{receiver.id}"
        if not cache.get(cache_key):
            send_unseen_message_email_task.apply_async(args=(sender.id, receiver.id), countdown=3600)
            cache.set(cache_key, True, timeout=4500)
            logger.info(f"[SAVE MESSAGE] Scheduled unseen message email for receiver {receiver.username}")

        # Broadcast to user
        async_to_sync(self.channel_layer.group_send)(
            f"user_notifications_{receiver.id}",
            {
                'type': 'total_unseen_count',
                'id': msg.id,
                'sender': sender.username,
                'receiver': receiver.username,
                'message': msg.content,
                'timestamp': str(msg.timestamp),
                'is_seen': msg.is_seen,
                'total_unseen_count': Message.objects.filter(receiver=receiver, is_seen=False).count()
            }
        )
        logger.info(f"[SAVE MESSAGE] Broadcasted total_unseen_count for receiver {receiver.username}")
        return msg

    @database_sync_to_async
    def mark_message_seen(self, message_id):
        msg = Message.objects.filter(id=message_id).first()
        if msg and not msg.is_seen:
            msg.is_seen = True
            msg.seen_at = get_current_datetime()
            msg.save()
            logger.info(f"[MARK SEEN] Message ID {message_id} marked as seen")


# ---------------- NotificationConsumer ----------------
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope["query_string"].decode()
        query_params = parse_qs(query_string)
        token_key = query_params.get("token", [None])[0]

        self.user = await self.get_user_from_token(token_key)
        if not self.user:
            logger.warning("[NOTIFICATION CONNECT] Invalid token, closing connection")
            await self.close()
            return

        self.group_name = f"user_notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"[NOTIFICATION CONNECT] User {self.user.username} connected to notifications")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"[NOTIFICATION DISCONNECT] User {self.user.username} disconnected, code: {close_code}")

    async def total_unseen_count(self, event):
        await self.send(text_data=json.dumps({
            "type": "total_unseen_count",
            "user_id": self.user.id,
            "total_unseen_count": event.get("total_unseen_count", 0)
        }))
        logger.info(f"[NOTIFICATION BROADCAST] Sent total_unseen_count to user {self.user.username}")

    @database_sync_to_async
    def get_user_from_token(self, token_key):
        if not token_key:
            return None
        try:
            validated_token = RefreshToken(token_key)
            user_id = validated_token["user_id"]
            user = User.objects.get(id=user_id)
            return user
        except Exception as e:
            logger.error(f"[TOKEN ERROR] Invalid token: {e}", exc_info=True)
            return None
