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
from asgiref.sync import async_to_sync
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ObjectDoesNotExist
import logging

logger = logging.getLogger(__name__)

# ----------------- DB cache key -----------------
ONLINE_USERS_KEY = "online_users"  # store list of online user IDs

# ----------------- Utility functions -----------------
def get_current_datetime():
    """Return current IST datetime as string."""
    ist = pytz.timezone('Asia/Kolkata')
    return timezone.now().astimezone(ist).strftime("%Y-%m-%d %I:%M %p")

def get_safe_group_name(room_name):
    """Convert room name to safe ASCII string using SHA-256"""
    hashed = hashlib.sha256(room_name.encode()).hexdigest()
    return f"chat_{hashed}"

# ----------------- DB cache helpers -----------------
from asgiref.sync import sync_to_async

# Async versions
add_online_user = sync_to_async(lambda user_id: _add_online_user(user_id))
remove_online_user = sync_to_async(lambda user_id: _remove_online_user(user_id))
get_online_users = sync_to_async(lambda: _get_online_users())

# Original synchronous implementations
def _add_online_user(user_id):
    users = cache.get("online_users", [])
    if user_id not in users:
        users.append(user_id)
        cache.set("online_users", users)

def _remove_online_user(user_id):
    users = cache.get("online_users", [])
    if user_id in users:
        users.remove(user_id)
        cache.set("online_users", users)

def _get_online_users():
    return cache.get("online_users", [])


# ----------------- Chat Room Consumer -----------------
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        raw_room_name = unquote(self.scope['url_route']['kwargs']['room_name'])
        self.room_name = raw_room_name
        self.room_group_name = get_safe_group_name(self.room_name)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

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

        # Broadcast to chat room (chat window)
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

    # ----------------- DB operations -----------------
    @database_sync_to_async
    def save_message(self, sender_username, receiver_username, message):
        sender = User.objects.filter(username=sender_username).first()
        receiver = User.objects.filter(username=receiver_username).first()

        if not sender or not receiver:
            raise ValueError("Sender or Receiver does not exist.")

        msg = Message.objects.create(sender=sender, receiver=receiver, content=message)

        # Schedule unseen email if not already scheduled
        cache_key = f"email_scheduled_receiver_{receiver.id}"
        if not cache.get(cache_key):
            send_unseen_message_email_task.apply_async(
                args=(sender.id, receiver.id),
                countdown=3600
            )
            cache.set(cache_key, True, timeout=4500)

        # Broadcast user notifications to sender & receiver
        for user in [sender, receiver]:
            async_to_sync(self.channel_layer.group_send)(
                f"user_notifications_{user.id}",
                {
                    'type': 'new_message_notification',
                    'id': msg.id,
                    'sender': sender.username,
                    'receiver': receiver.username,
                    'message': msg.content,
                    'timestamp': str(msg.timestamp),
                    'is_seen': msg.is_seen,
                    'total_unseen_count': Message.objects.filter(receiver=user, is_seen=False).count()
                }
            )
        return msg

    @database_sync_to_async
    def mark_message_seen(self, message_id):
        msg = Message.objects.filter(id=message_id).first()
        if msg and not msg.is_seen:
            msg.is_seen = True
            msg.seen_at = get_current_datetime()
            msg.save()

# ----------------- User Notifications Consumer -----------------
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info("[WS CONNECT] New connection attempt")
        self.group_name = None

        try:
            query_string = self.scope["query_string"].decode()
            logger.info(f"[WS CONNECT] Query string: {query_string}")

            from urllib.parse import parse_qs
            query_params = parse_qs(query_string)
            token_key = query_params.get("token", [None])[0]
            logger.info(f"[WS CONNECT] Token key extracted: {token_key}")

            self.user = await self.get_user_from_token(token_key)
            if not self.user:
                logger.warning("[WS CONNECT] Invalid or missing user, closing connection")
                await self.close()
                return

            self.group_name = f"user_notifications_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(f"[WS CONNECT] User {self.user.username} connected successfully")

            # Mark user online
            await add_online_user(self.user.id)
            await self.broadcast_status()

        except Exception as e:
            logger.exception(f"[WS CONNECT] Exception during connect: {e}")
            await self.close()

    async def disconnect(self, close_code):
        logger.info(f"[WS DISCONNECT] User {getattr(self, 'user', None)} disconnected, code: {close_code}")

        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        if hasattr(self, "user") and self.user:
            await remove_online_user(self.user.id)
            await self.broadcast_status()

    async def broadcast_status(self):
        try:
            online_ids = await get_online_users()  # <-- await here
            logger.info(f"[BROADCAST STATUS] Online users: {online_ids}")

            all_users = await self.get_all_users()
            all_users = list(all_users)  # force evaluation, safe for async

            for user in all_users:
                await self.channel_layer.group_send(
                    f"user_notifications_{user.id}",
                    {
                        "type": "online_status",
                        "online_ids": online_ids
                    }
                )
            logger.info("[BROADCAST STATUS] Status broadcast completed")
        except Exception as e:
            logger.exception(f"[BROADCAST STATUS] Exception: {e}")


    @database_sync_to_async
    def get_user_from_token(self, token_key):
        if not token_key:
            logger.warning("[TOKEN] No token provided")
            return None
        try:
            validated_token = RefreshToken(token_key)
            user_id = validated_token["user_id"]
            user = User.objects.get(id=user_id)
            logger.info(f"[TOKEN] Token valid. User ID: {user_id}, Username: {user.username}")
            return user
        except ObjectDoesNotExist:
            logger.warning(f"[TOKEN] User with ID {user_id} does not exist")
            return None
        except Exception as e:
            logger.exception(f"[TOKEN] Exception decoding token: {e}")
            return None

    @database_sync_to_async
    def get_all_users(self):
        users = list(User.objects.all())
        logger.info(f"[USERS] Fetched {len(users)} users from DB")
        return users
