from autogen_core import RoutedAgent, MessageContext, message_handler

from src.agents.messages import UpdateCommand


class TrafficLightAgent(RoutedAgent):
    def __init__(self, light_id: int, red_duration: int = 5, green_duration: int = 4):
        super().__init__(f"TrafficLightAgent-{light_id}")
        self.light_id = light_id
        self.red_duration = red_duration
        self.green_duration = green_duration

        # Set initial state based on light_id
        self.current_state = 'green' if light_id % 3 == 0 else 'red'

        # Set initial timer with offset based on light_id
        if self.current_state == 'red':
            self.timer = light_id % self.red_duration
        else:
            self.timer = light_id % self.green_duration

    @message_handler
    async def handle_update(self, message: UpdateCommand, ctx: MessageContext) -> None:
        self.timer += 1
        if self.current_state == 'red' and self.timer >= self.red_duration:
            self.current_state = 'green'
            self.timer = 0
        elif self.current_state == 'green' and self.timer >= self.green_duration:
            self.current_state = 'red'
            self.timer = 0
        print(f"{self.id}: state={self.current_state}, timer={self.timer}")