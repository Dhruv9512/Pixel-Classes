import json
from urllib.parse import unquote
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Message
import hashlib


def get_safe_group_name(room_name):
    # Convert any room name to a safe ASCII string using SHA-256
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
        data = json.loads(text_data)

        # Handle new chat message
        if data.get("type") == "chat":
            sender_username = data['sender']
            receiver_username = data['receiver']
            message = data['message']

            # Save to DB
            saved_message = await self.save_message(sender_username, receiver_username, message)

            # Broadcast to the group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'id': saved_message.id,
                    'sender': sender_username,
                    'receiver': receiver_username,
                    'message': message
                }
            )

        # Handle message seen event
        elif data.get("type") == "seen":
            message_id = data['message_id']
            await self.mark_message_seen(message_id)

            # Notify all group members that this message is seen
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_seen',
                    'message_id': message_id
                }
            )

    async def chat_message(self, event):
        """Send a new chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'id': event['id'],
            'sender': event['sender'],
            'receiver': event['receiver'],
            'message': event['message']
        }))

    async def message_seen(self, event):
        """Send a seen event to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'seen',
            'message_id': event['message_id']
        }))

    @database_sync_to_async
    def save_message(self, sender_username, receiver_username, message):
        """Store the message in the DB"""
        sender = User.objects.filter(username=sender_username).first()
        receiver = User.objects.filter(username=receiver_username).first()

        if not sender:
            raise ValueError(f"Sender '{sender_username}' does not exist.")
        if not receiver:
            raise ValueError(f"Receiver '{receiver_username}' does not exist.")

        return Message.objects.create(
            sender=sender,
            receiver=receiver,
            content=message
        )

    @database_sync_to_async
    def mark_message_seen(self, message_id):
        """Update a message as seen"""
        msg = Message.objects.filter(id=message_id).first()
        if msg and not msg.is_seen:
            msg.is_seen = True
            msg.seen_at = timezone.now()
            msg.save()
