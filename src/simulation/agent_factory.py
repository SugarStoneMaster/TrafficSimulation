from typing import Tuple, List, Dict

from autogen_core import (
    SingleThreadedAgentRuntime,
)

from src.agents.parking import ParkingAgent
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


# Add to src/simulation/agent_factory.py
async def register_parking_agents(runtime: SingleThreadedAgentRuntime, grid: RoadGrid,
                                  avg_parking_time: int, initial_occupancy: float = 0.3) -> List[str]:
    """Register parking agents for all parking spots in the grid."""
    parking_agents = []
    parking_id = 1

    for r in range(grid.rows):
        for c in range(grid.cols):
            cell = grid.grid[r][c]
            if "parking" in cell.features:
                agent_id = f"parking_{parking_id}"
                capacity = getattr(cell, 'parking_capacity', 1)
                parking_type = getattr(cell, 'parking_type', "street")

                # Calculate initial vehicles (randomized but proportional to capacity)
                initial_vehicles = min(capacity, int(capacity * initial_occupancy))

                await ParkingAgent.register(
                    runtime,
                    agent_id,
                    lambda pid=parking_id, ptype=parking_type, pcap=capacity,
                           pos=(r, c), init=initial_vehicles:
                    ParkingAgent(pid, ptype, pcap, avg_parking_time, pos, init)
                )
                parking_agents.append(agent_id)
                parking_id += 1

    return parking_agents