from dataclasses import dataclass
from typing import Dict


@dataclass
class UpdateCommand:
    # A generic update command for agents (for TrafficLight, PedestrianCrossing, etc.)
    pass


@dataclass
class UpdateVehicleCommand:
    def __init__(self, traffic_light_states: Dict[str, str], crossing_states: Dict[str, bool] = None, occupied_cells=None):
        self.traffic_light_states = traffic_light_states
        self.crossing_states = crossing_states or {}
        self.occupied_cells = occupied_cells or {}