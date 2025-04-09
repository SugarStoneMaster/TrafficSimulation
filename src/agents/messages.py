from dataclasses import dataclass
from typing import Dict


@dataclass
class UpdateCommand:
    # A generic update command for agents (for TrafficLight, PedestrianCrossing, etc.)
    current_time: int = 0

@dataclass
class UpdateVehicleCommand:
    def __init__(self, traffic_light_states: Dict[str, str], crossing_states: Dict[str, bool] = None, occupied_cells=None):
        self.traffic_light_states = traffic_light_states
        self.crossing_states = crossing_states or {}
        self.occupied_cells = occupied_cells or {}


@dataclass
class ParkingRequestCommand:
    vehicle_id: str
    current_time: int


@dataclass
class ParkingResponseCommand:
    accepted: bool
    space_id: int = None