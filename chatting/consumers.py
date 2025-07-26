import json
from urllib.parse import unquote
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from .models import Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = unquote(self.scope['url_route']['kwargs']['room_name'])
        self.room_group_name = f'chat_{self.room_name}'

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
        sender_username = data['sender']
        receiver_username = data['receiver']
        message = data['message']

        # Save the message to DB
        await self.save_message(sender_username, receiver_username, message)

        # Broadcast to the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'sender': sender_username,
                'receiver': receiver_username,
                'message': message
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'sender': event['sender'],
            'receiver': event['receiver'],
            'message': event['message']
        }))

    @database_sync_to_async
    def save_message(self, sender_username, receiver_username, message):
        # Ensure both users already exist
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
