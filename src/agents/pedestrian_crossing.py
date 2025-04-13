from autogen_core import RoutedAgent, message_handler, MessageContext
import random
from typing import Tuple

from src.agents.messages import UpdateCommand
from src.agents.veichle import VehicleAgent


class PedestrianCrossingAgent(RoutedAgent):
    def __init__(self, crossing_id: int, position: Tuple[int, int] = None, lanes: int = 1, active_duration: int = None):
        super().__init__(f"PedestrianCrossingAgent-{crossing_id}")
        self.crossing_id = crossing_id
        self.position = position  # Store the crossing's position
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
            # Only attempt to activate if we have position info
            if self.position:
                # Check if position is clear of vehicles before activating
                position_is_clear = self.position not in VehicleAgent._all_vehicle_positions

                # Random activation with 30% probability, but only if clear of vehicles
                if position_is_clear and random.random() < 0.3:
                    self.active = True
                    self.timer = 0
                    print(f"{self.id}: Activated crossing at {self.position} (clear of vehicles)")
            else:
                # Fallback to original behavior if position unknown
                if random.random() < 0.3:
                    self.active = True
                    self.timer = 0

        print(f"{self.id}: active={self.active}, timer={self.timer}, lanes={self.lanes}")