from channels.generic.websocket import AsyncWebsocketConsumer
import json

class LiberacaoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'liberacoes'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"✅ Conectado ao grupo {self.group_name}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        print("🔌 Desconectado")

    async def nova_liberacao(self, event):
        await self.send(text_data=json.dumps(event['data']))