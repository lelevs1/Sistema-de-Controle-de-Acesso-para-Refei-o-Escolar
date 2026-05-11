import json
from channels.generic.websocket import AsyncWebsocketConsumer

class LiberacaoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'liberacoes'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def nova_liberacao(self, event):
        # Envia a mensagem para o WebSocket
        await self.send(text_data=json.dumps(event['data']))