import json
import logging
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Message
from rest_framework_simplejwt.tokens import AccessToken
from .tasks import send_unseen_message_email_task
import pytz
from django.core.cache import cache
from Profile.models import Follow, profile

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def get_current_datetime():
    """Return current IST datetime as string."""
    ist = pytz.timezone("Asia/Kolkata")
    return timezone.now().astimezone(ist).strftime("%Y-%m-%d %I:%M %p")

def get_room_name(user1_id, user2_id):
    """Generate deterministic room name for private chat."""
    a, b = (user1_id, user2_id) if user1_id <= user2_id else (user2_id, user1_id)
    return f"chat_{a}_{b}"

def _chat_cache_key(a_username, b_username, query=None):
    # normalize to avoid duplicates; include query fragment when present
    u1, u2 = (a_username, b_username) if a_username <= b_username else (b_username, a_username)
    return f"chat_messages:{u1}__{u2}:{query or ''}"

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Parse query params
        query_string = self.scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)

        token_key = query_params.get("token", [None])[0]
        receiver_username = query_params.get("receiver", [None])[0]

        if not token_key or not receiver_username:
            logger.warning("[WS CONNECT] Missing token or receiver")
            await self.close()
            return

        # Authenticate user from token
        self.user = await self.get_user_from_token(token_key)
        if not self.user:
            logger.warning("[WS CONNECT] Invalid token")
            await self.close()
            return

        # Validate receiver
        self.receiver = await self.get_user_by_username(receiver_username)
        if not self.receiver:
            logger.warning(f"[WS CONNECT] No user with username {receiver_username}")
            await self.close()
            return

        # Generate deterministic room name
        self.room_group_name = get_room_name(self.user.id, self.receiver.id)

        # Add to group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info(f"[WS CONNECT] {self.user.username} connected to {self.room_group_name}")

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            logger.info(f"[WS DISCONNECT] {getattr(self.user, 'username', 'anon')} left {self.room_group_name}")

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
        message = data.get("message")
        temp_id = data.get("tempId")

        if not message:
            await self.send(json.dumps({"error": "Message is required"}))
            logger.warning("[CHAT MESSAGE] Missing message field")
            return

        saved_message = await self.save_message(self.user.username, self.receiver.username, message)
        logger.info(f"[CHAT MESSAGE] Saved message ID: {saved_message.id}")

        # Broadcast to chat room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "id": saved_message.id,
                "sender": self.user.username,
                "receiver": self.receiver.username,
                "message": message,
                "temp_id": temp_id,
            },
        )

        # Broadcast notifications and inbox updates
        await self.send_user_notifications(saved_message)
        await self.broadcast_inbox_update(self.user.id)
        await self.broadcast_inbox_update(self.receiver.id)

    async def handle_seen_event(self, data):
        message_id = data.get("message_id")
        if not message_id:
            await self.send(json.dumps({"error": "Missing message_id"}))
            logger.warning("[SEEN EVENT] Missing message_id")
            return

        await self.mark_message_seen(message_id)
        logger.info(f"[SEEN EVENT] Message marked as seen: {message_id}")

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "message_seen", "message_id": message_id},
        )

    # ---------------- WebSocket event handlers ----------------
    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat",
                    "id": event["id"],
                    "sender": event["sender"],
                    "receiver": event["receiver"],
                    "message": event["message"],
                    "temp_id": event.get("temp_id"),
                }
            )
        )

    async def message_seen(self, event):
        await self.send(text_data=json.dumps({"type": "seen", "message_id": event["message_id"]}))

    async def edit_message(self, event):
        await self.send(text_data=json.dumps({"type": "edit", "id": event["id"], "new_content": event["new_content"]}))

    async def delete_message(self, event):
        await self.send(text_data=json.dumps({"type": "delete", "id": event["id"]}))

    # ---------------- DB operations ----------------
    @database_sync_to_async
    def save_message(self, sender_username, receiver_username, message):
        # Minimal lookups [web:27]
        sender = User.objects.only('id', 'username').filter(username=sender_username).first()
        receiver = User.objects.only('id', 'username').filter(username=receiver_username).first()
        if not sender or not receiver:
            raise ValueError("Sender or receiver does not exist")

        msg = Message.objects.create(sender=sender, receiver=receiver, content=message)

        # Schedule unseen email (keep same lock semantics)
        cache_key = f"email_scheduled_receiver_{receiver.id}"
        if not cache.get(cache_key):
            send_unseen_message_email_task.apply_async(args=(sender.id, receiver.id), countdown=3600)
            cache.set(cache_key, True, timeout=4500)

        # Invalidate both directional caches (no query param suffix here)
        cache.delete(_chat_cache_key(sender.username, receiver.username, ""))
        cache.delete(_chat_cache_key(receiver.username, sender.username, ""))

        return msg

    @database_sync_to_async
    def mark_message_seen(self, message_id):
        # Minimal fetch then targeted update [web:27]
        msg = Message.objects.only('id', 'is_seen').filter(id=message_id).first()
        if msg and not msg.is_seen:
            msg.is_seen = True
            msg.seen_at = get_current_datetime()
            msg.save(update_fields=['is_seen', 'seen_at'])

    # ---------------- User notifications ----------------
    async def send_user_notifications(self, msg):
        # sender and receiver are already available on msg instance
        for user in [msg.sender, msg.receiver]:
            total_unseen = await self.get_total_unseen_count(user.id)
            await self.channel_layer.group_send(
                f"user_notifications_{user.id}",
                {
                    "type": "total_unseen_count",
                    "id": msg.id,
                    "sender": msg.sender.username,
                    "receiver": msg.receiver.username,
                    "message": msg.content,
                    "timestamp": str(msg.timestamp),
                    "is_seen": msg.is_seen,
                    "total_unseen_count": total_unseen,
                },
            )

    async def broadcast_inbox_update(self, user_id):
        await self.channel_layer.group_send(f"message_inbox_{user_id}", {"type": "inbox_update"})

    @database_sync_to_async
    def get_total_unseen_count(self, user_id):
        # Count distinct senders to match existing logic more efficiently [web:27]
        return (
            Message.objects
            .filter(receiver_id=user_id, is_seen=False)
            .values('sender_id')
            .distinct()
            .count()
        )

    @database_sync_to_async
    def get_user_by_username(self, username):
        return User.objects.only('id', 'username').filter(username=username).first()

    @database_sync_to_async
    def get_user_from_token(self, token_key):
        if not token_key:
            return None
        try:
            validated_token = AccessToken(token_key)
            user_id = validated_token["user_id"]
            return User.objects.only('id', 'username').get(id=user_id)
        except Exception as e:
            logger.error(f"[TOKEN ERROR] Invalid token: {e}", exc_info=True)
            return None

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
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

        unseen_count = await self.get_total_unseen_count(self.user.id)
        await self.send(text_data=json.dumps({"type": "total_unseen_count", "total_unseen_count": unseen_count}))
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
            validated_token = AccessToken(token_key)
            user_id = validated_token["user_id"]
            return User.objects.only('id', 'username').get(id=user_id)
        except Exception as e:
            logger.error(f"[TOKEN ERROR] Invalid token: {e}", exc_info=True)
            return None

    @database_sync_to_async
    def get_total_unseen_count(self, user_id):
        # Efficient distinct sender count for unseen messages [web:27]
        return (
            Message.objects
            .filter(receiver_id=user_id, is_seen=False)
            .values('sender_id')
            .distinct()
            .count()
        )

class MessageInboxConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token_key = query_params.get("token", [None])[0]

        self.user = await self.get_user_from_token(token_key)
        if not self.user:
            logger.warning("[MESSAGE INBOX CONNECT] Invalid token, closing connection")
            await self.close()
            return

        self.group_name = f"message_inbox_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        inbox_data = await self.get_user_inbox(self.user.id)
        await self.send(text_data=json.dumps({"type": "inbox_data", "inbox": inbox_data}))
        logger.info(f"[MESSAGE INBOX CONNECT] Sent inbox to user {self.user.username}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"[MESSAGE INBOX DISCONNECT] User {self.user.username} disconnected, code: {close_code}")

    async def inbox_update(self, event):
        inbox_data = await self.get_user_inbox(self.user.id)
        await self.send(text_data=json.dumps({"type": "inbox_data", "inbox": inbox_data}))

    @database_sync_to_async
    def get_user_from_token(self, token_key):
        if not token_key:
            return None
        try:
            validated_token = AccessToken(token_key)
            user_id = validated_token["user_id"]
            return User.objects.only('id', 'username').get(id=user_id)
        except Exception as e:
            logger.error(f"[TOKEN ERROR] Invalid token: {e}", exc_info=True)
            return None

    @database_sync_to_async
    def get_user_inbox(self, user_id):
        try:
            user = User.objects.only('id', 'username').get(id=user_id)
            follow_obj = Follow.objects.select_related('user').filter(user=user).first()

            following_ids = set()
            follower_ids = set()

            if follow_obj:
                following_ids = set(follow_obj.following.values_list("user__id", flat=True))
                follower_ids = set(Follow.objects.filter(following=follow_obj).values_list("user__id", flat=True))

            unique_user_ids = list(following_ids.union(follower_ids))
            if not unique_user_ids:
                return []

            # Fetch all needed users and profiles in batches to avoid N+1 [web:138]
            other_users = {u.id: u for u in User.objects.only('id', 'username').filter(id__in=unique_user_ids)}
            profiles = {
                p.user_obj_id: p
                for p in profile.objects.only('user_obj_id', 'profile_pic').filter(user_obj_id__in=unique_user_ids)
            }

            inbox = []
            # Get latest message for each pair efficiently by ordering and first() per pair
            # (keeps original logic). For further optimization, a subquery can be used. [web:27]
            for other_user_id in unique_user_ids:
                other_user = other_users.get(other_user_id)
                prof = profiles.get(other_user_id)
                profile_pic = prof.profile_pic if prof else "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp"

                latest_msg = (
                    Message.objects
                    .filter(sender_id__in=[user_id, other_user_id], receiver_id__in=[user_id, other_user_id])
                    .only('content', 'timestamp', 'is_seen')
                    .order_by("-timestamp")
                    .first()
                )

                inbox.append({
                    "user_id": other_user.id if other_user else other_user_id,
                    "username": other_user.username if other_user else "",
                    "profile_pic": profile_pic,
                    "latest_message": latest_msg.content if latest_msg else None,
                    "timestamp": str(latest_msg.timestamp) if latest_msg else None,
                    "is_seen": latest_msg.is_seen if latest_msg else None,
                })

            inbox.sort(key=lambda x: x["timestamp"] or "", reverse=True)
            return inbox

        except Exception as e:
            logger.error(f"[INBOX ERROR] {e}", exc_info=True)
            return []
