import random
from typing import Dict, Tuple
from autogen_core import RoutedAgent, message_handler, MessageContext

from src.agents.messages import UpdateCommand, ParkingRequestCommand, ParkingResponseCommand


class ParkingAgent(RoutedAgent):
    def __init__(self, parking_id: int, parking_type: str, capacity: int,
                 avg_parking_time: int, position: Tuple[int, int], initial_occupancy: int = 0):
        super().__init__(f"ParkingAgent-{parking_id}")
        self.parking_id = parking_id
        self.parking_type = parking_type  # "street" or "building"
        self.capacity = capacity
        self.avg_parking_time = avg_parking_time
        self.position = position
        self.parked_vehicles = {}  # vehicle_id -> parking_end_time

        # Initialize with some parked vehicles if specified
        for i in range(initial_occupancy):
            self.parked_vehicles[f"initial_vehicle_{i}_{parking_id}"] = random.randint(1, avg_parking_time * 2)

    @message_handler
    async def handle_parking_request(self, message: ParkingRequestCommand, ctx: MessageContext) -> None:
        # Check if there's space available
        has_space = len(self.parked_vehicles) < self.capacity

        if has_space:
            # Calculate random parking duration based on average
            parking_duration = int(random.gauss(self.avg_parking_time, self.avg_parking_time / 3))
            parking_end_time = message.current_time + max(1, parking_duration)

            # Add vehicle to parked vehicles
            self.parked_vehicles[message.vehicle_id] = parking_end_time
            print(
                f"{self.id}: Accepted parking request from {message.vehicle_id}, will exit at time {parking_end_time}")
        else:
            print(f"{self.id}: Rejected parking request from {message.vehicle_id}, no capacity available")

        # Send response back to vehicle
        await self.send_message(
            ParkingResponseCommand(accepted=has_space, space_id=self.parking_id if has_space else None),
            ctx.sender
        )

    @message_handler
    async def handle_update(self, message: UpdateCommand, ctx: MessageContext) -> None:
        # Update parking status, remove vehicles that have finished parking
        current_time = getattr(message, 'current_time', 0)
        vehicles_to_remove = []

        for vehicle_id, exit_time in self.parked_vehicles.items():
            if current_time >= exit_time:
                vehicles_to_remove.append(vehicle_id)

        for vehicle_id in vehicles_to_remove:
            del self.parked_vehicles[vehicle_id]
            print(f"{self.id}: Vehicle {vehicle_id} exited parking")

        # Report status
        print(f"{self.id}: type={self.parking_type}, capacity={self.capacity}, occupied={len(self.parked_vehicles)}")