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
from Profile.models import Follow

# ---------------- Logging ----------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------- Utility functions ----------------
def get_current_datetime():
    """Return current IST datetime as string."""
    ist = pytz.timezone("Asia/Kolkata")
    return timezone.now().astimezone(ist).strftime("%Y-%m-%d %I:%M %p")

def get_room_name(user1_id, user2_id):
    """Generate deterministic room name for private chat."""
    return f"chat_{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"

# ---------------- ChatConsumer ----------------
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
            logger.info(f"[WS DISCONNECT] {self.user.username} left {self.room_group_name}")

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

        # Broadcast to user notifications
        await self.send_user_notifications(saved_message)
        # Broadcast inbox update to both users
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
            {
                "type": "message_seen",
                "message_id": message_id,
            },
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
        await self.send(
            text_data=json.dumps(
                {
                    "type": "seen",
                    "message_id": event["message_id"],
                }
            )
        )

    # ---------------- DB operations ----------------
    @database_sync_to_async
    def save_message(self, sender_username, receiver_username, message):
        sender = User.objects.filter(username=sender_username).first()
        receiver = User.objects.filter(username=receiver_username).first()

        if not sender or not receiver:
            raise ValueError("Sender or receiver does not exist")

        msg = Message.objects.create(sender=sender, receiver=receiver, content=message)

        # Schedule unseen email
        cache_key = f"email_scheduled_receiver_{receiver.id}"
        if not cache.get(cache_key):
            send_unseen_message_email_task.apply_async(args=(sender.id, receiver.id), countdown=3600)
            cache.set(cache_key, True, timeout=4500)

        return msg

    @database_sync_to_async
    def mark_message_seen(self, message_id):
        msg = Message.objects.filter(id=message_id).first()
        if msg and not msg.is_seen:
            msg.is_seen = True
            msg.seen_at = get_current_datetime()
            msg.save()

    # ---------------- User notifications ----------------
    async def send_user_notifications(self, msg):
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
    
    # Update MessageInboxConsumer
    # ---------------- Utility: Broadcast inbox update ----------------
    async def broadcast_inbox_update(self, user_id):
        """
        Broadcasts an inbox update event to the user's message inbox group.
        """
        await self.channel_layer.group_send(
            f"message_inbox_{user_id}",
            {
                "type": "inbox_update"  # This will call inbox_update in MessageInboxConsumer
            }
        )



    @database_sync_to_async
    def get_total_unseen_count(self, user_id):
        unseen_messages = Message.objects.filter(receiver_id=user_id, is_seen=False)
        senders = set(unseen_messages.values_list("sender_id", flat=True))
        return len(senders)

    @database_sync_to_async
    def get_user_by_username(self, username):
        return User.objects.filter(username=username).first()
    
    @database_sync_to_async
    def get_user_from_token(self, token_key):
        if not token_key:
            return None
        try:
            validated_token = AccessToken(token_key)
            user_id = validated_token["user_id"]
            return User.objects.get(id=user_id)
        except Exception as e:
            logger.error(f"[TOKEN ERROR] Invalid token: {e}", exc_info=True)
            return None




# ---------------- NotificationConsumer ----------------
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
       # Extract cookies from headers
       
        query_string = self.scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        
        # Get token from ?token=... in ws url
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
        await self.send(text_data=json.dumps({
            "type": "total_unseen_count",
            "total_unseen_count": unseen_count
        }))
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
            return User.objects.get(id=user_id)
        except Exception as e:
            logger.error(f"[TOKEN ERROR] Invalid token: {e}", exc_info=True)
            return None
    @database_sync_to_async
    def get_total_unseen_count(self, user_id):
        unseen_messages = Message.objects.filter(
            receiver_id=user_id, is_seen=False
        )

        # group by sender_id (or any other logic you want)
        groups = {}
        for msg in unseen_messages:
            key = msg.sender_id   
            groups[key] = True

        return len(groups)  






class MessageInboxConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # ---------------- 1. Get token ----------------
        query_string = self.scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token_key = query_params.get("token", [None])[0]

        self.user = await self.get_user_from_token(token_key)
        if not self.user:
            logger.warning("[MESSAGE INBOX CONNECT] Invalid token, closing connection")
            await self.close()
            return

        # ---------------- 2. Add to user-specific channel ----------------
        self.group_name = f"message_inbox_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # ---------------- 3. Fetch inbox ----------------
        inbox_data = await self.get_user_inbox(self.user.id)

        # ---------------- 4. Send inbox to frontend ----------------
        await self.send(text_data=json.dumps({
            "type": "inbox_data",
            "inbox": inbox_data
        }))

        logger.info(f"[MESSAGE INBOX CONNECT] Sent inbox to user {self.user.username}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"[MESSAGE INBOX DISCONNECT] User {self.user.username} disconnected, code: {close_code}")


    
    # ---------------- Handle inbox updates ----------------
    async def inbox_update(self, event):
        inbox_data = await self.get_user_inbox(self.user.id)
        await self.send(text_data=json.dumps({
            "type": "inbox_data",
            "inbox": inbox_data
        }))


    # ---------------- DB Operations ----------------
    @database_sync_to_async
    def get_user_from_token(self, token_key):
        if not token_key:
            return None
        try:
            validated_token = AccessToken(token_key)
            user_id = validated_token["user_id"]
            return User.objects.get(id=user_id)
        except Exception as e:
            logger.error(f"[TOKEN ERROR] Invalid token: {e}", exc_info=True)
            return None

    

    @database_sync_to_async
    def get_user_inbox(self, user_id):
        """
        Returns a list of unique users (followers + following)
        with their latest message with the authenticated user.
        """
        try:
            user = User.objects.get(id=user_id)
            follow_obj = Follow.objects.filter(user=user).first()

            following_ids = set(follow_obj.following.values_list('id', flat=True)) if follow_obj else set()
            follower_ids = set(user.followers.values_list('id', flat=True))  # Reverse relation from Follow model

            # Merge & remove duplicates
            unique_user_ids = list(following_ids.union(follower_ids))

            inbox = []
            for other_user_id in unique_user_ids:
                other_user = User.objects.get(id=other_user_id)
                
                # Get profile pic
                profile_obj = getattr(other_user, "profile", None)  # profile is related name if not set, default is 'profile_set'
                profile_pic = profile_obj.profile_pic if profile_obj else "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp"

                # Get latest message between user and other_user
                latest_msg = Message.objects.filter(
                    sender_id__in=[user_id, other_user_id],
                    receiver_id__in=[user_id, other_user_id]
                ).order_by('-timestamp').first()

                inbox.append({
                    "user_id": other_user.id,
                    "username": other_user.username,
                    "profile_pic": profile_pic,  # Add profile pic here
                    "latest_message": latest_msg.content if latest_msg else None,
                    "timestamp": str(latest_msg.timestamp) if latest_msg else None,
                    "is_seen": latest_msg.is_seen if latest_msg else None
                })


            # Sort by latest message timestamp (descending)
            inbox.sort(key=lambda x: x['timestamp'] or '', reverse=True)
            return inbox

        except Exception as e:
            logger.error(f"[INBOX ERROR] {e}", exc_info=True)
            return []
