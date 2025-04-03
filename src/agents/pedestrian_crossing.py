from autogen_core import RoutedAgent, message_handler, MessageContext
import random

from src.agents.messages import UpdateCommand


class PedestrianCrossingAgent(RoutedAgent):
    def __init__(self, crossing_id: int, lanes: int = 1, active_duration: int = None):
        super().__init__(f"PedestrianCrossingAgent-{crossing_id}")
        self.crossing_id = crossing_id
        self.lanes = lanes

        # Use provided duration or default based on lanes
        if active_duration is not None:
            self.active_duration = active_duration
        else:
            self.active_duration = 3 if lanes > 1 else 1

        self.active = False
        self.timer = 0

    @message_handler
    async def handle_update(self, message: UpdateCommand, ctx: MessageContext) -> None:
        # If active, count down timer
        if self.active:
            self.timer += 1
            # Deactivate after duration expires
            if self.timer >= self.active_duration:
                self.active = False
                self.timer = 0
        else:
            # Random activation with 1/10 probability
            if random.random() < 0.3:  # 30% chance to activate
                self.active = True
                self.timer = 0

        print(f"{self.id}: active={self.active}, timer={self.timer}, lanes={self.lanes}")