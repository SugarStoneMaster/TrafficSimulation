import random

from autogen_core import RoutedAgent, message_handler, MessageContext, AgentId

from src.agents.messages import UpdateCommand


class IntelligentAgent(RoutedAgent):
    def __init__(self):
        super().__init__("IntelligentAgent")

    @message_handler
    async def handle_update(self, message: UpdateCommand, ctx: MessageContext) -> None:
        # For demonstration, the intelligent agent may decide to force a traffic light update.
        # Here we randomly decide to send an update command to the traffic light.
        if random.random() > 0.5:
            print(f"{self.id}: Forcing traffic light to green.")
            # Send a generic update command to the traffic light agent.
            await self.send_message(UpdateCommand(), AgentId("traffic_light_1", "default"))
        else:
            print(f"{self.id}: No adjustment this cycle.")