from typing import Tuple, List, Dict

from autogen_core import (
    SingleThreadedAgentRuntime,
)

from src.agents.pedestrian_crossing import PedestrianCrossingAgent
from src.agents.traffic_light import TrafficLightAgent
from src.agents.veichle import VehicleAgent
from src.simulation.grid import RoadGrid


async def register_traffic_lights(runtime: SingleThreadedAgentRuntime, traffic_light_positions: List[Tuple[int, int]],
                                  timing: Tuple[int, int]) -> List[str]:
    """Register traffic light agents."""
    traffic_light_agents = []
    for i, pos in enumerate(traffic_light_positions):
        agent_id = f"traffic_light_{i + 1}"
        await TrafficLightAgent.register(
            runtime,
            agent_id,
            lambda i_val=i, red=timing[0], green=timing[1]:
            TrafficLightAgent(i_val + 1, red_duration=red, green_duration=green)
        )
        traffic_light_agents.append(agent_id)
    return traffic_light_agents


async def register_pedestrian_crossings(runtime: SingleThreadedAgentRuntime, grid: RoadGrid,
                                        crossing_positions: List[Tuple[int, int]],
                                        timing: Tuple[int, int]) -> List[str]:
    """Register pedestrian crossing agents."""
    crossing_agents = []
    for i, pos in enumerate(crossing_positions):
        agent_id = f"crossing_{i + 1}"
        r, c = pos
        lanes = grid.grid[r][c].lanes
        duration = timing[1] if lanes > 1 else timing[0]
        await PedestrianCrossingAgent.register(
            runtime,
            agent_id,
            lambda i_val=i, lanes_val=lanes, active_duration=duration:
            PedestrianCrossingAgent(i_val + 1, lanes=lanes_val, active_duration=active_duration)
        )
        crossing_agents.append(agent_id)
    return crossing_agents


async def create_new_vehicle(runtime: SingleThreadedAgentRuntime, grid: RoadGrid, vehicle_id: int,
                             vehicle_ids: List[str], vehicle_pending: List[str],
                             vehicle_wait_times: Dict[str, int]) -> None:
    """Create a new vehicle and register it."""
    vehicle_key = f"vehicle_{vehicle_id}"
    await VehicleAgent.register(runtime, vehicle_key, lambda: VehicleAgent(vehicle_id, grid))
    vehicle_ids.append(vehicle_key)
    vehicle_pending.append(vehicle_key)
    vehicle_wait_times[vehicle_key] = 0