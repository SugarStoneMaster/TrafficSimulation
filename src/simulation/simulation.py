import asyncio
import os
import pygame
from typing import Dict, List, Tuple, Any

from autogen_core import (
    AgentId,
    SingleThreadedAgentRuntime,
)

from src.agents.intelligent import IntelligentAgent
from src.agents.messages import UpdateVehicleCommand, UpdateCommand
from src.simulation.agent_factory import register_traffic_lights, register_pedestrian_crossings, create_new_vehicle
from src.simulation.grid import extract_special_positions, initialize_grid
from src.simulation.metrics import display_metrics
from src.simulation.visualizer import PyGameVisualizer


async def run_simulation(runtime: SingleThreadedAgentRuntime, simulation_time: int = 10, road_size="small",
                         traffic_light_timing=(5, 4), pedestrian_crossing_timing=(1, 3)) -> None:
    """Run the traffic simulation with the given parameters."""
    # Initialize components
    grid = initialize_grid(road_size)
    visualizer = PyGameVisualizer(grid)
    traffic_light_positions, crossing_positions = extract_special_positions(grid)

    # Register agents
    traffic_light_agents = await register_traffic_lights(runtime, traffic_light_positions, traffic_light_timing)
    crossing_agents = await register_pedestrian_crossings(runtime, grid, crossing_positions, pedestrian_crossing_timing)
    await IntelligentAgent.register(runtime, "intelligent_agent", lambda: IntelligentAgent())

    # Metrics tracking
    total_vehicles = 0
    exited_vehicles = 0
    vehicle_wait_times = {}
    vehicles = {}
    vehicle_ids = []
    vehicle_pending = []
    vehicles_exiting = {}

    # Simulation loop
    for t in range(simulation_time):
        # Check for PyGame quit event
        if not visualizer.check_events():
            break

        # Process vehicles that were marked for removal in the previous step
        vehicles_to_remove = [vid for vid, removal_time in list(vehicles_exiting.items()) if t >= removal_time]
        for vid in vehicles_to_remove:
            if vid in vehicle_ids:
                vehicle_ids.remove(vid)
            if vid in vehicles:
                del vehicles[vid]
            vehicles_exiting.pop(vid)
            print(f"Vehicle {vid} has been removed from the simulation")

        # Create a new vehicle every step
        if t > 0:
            total_vehicles += 1
            await create_new_vehicle(runtime, grid, t, vehicle_ids, vehicle_pending, vehicle_wait_times)

        # Update traffic lights and pedestrian crossings
        traffic_light_states = await update_traffic_lights(runtime, traffic_light_agents)
        crossing_states = await update_pedestrian_crossings(runtime, crossing_agents)

        # Update vehicles
        for vid in vehicle_ids:
            exiting, exit_time = await process_vehicle_update(
                runtime, vid, traffic_light_states, crossing_states,
                vehicles, vehicle_wait_times, vehicle_pending, t
            )

            if exiting and vid not in vehicles_exiting:
                vehicles_exiting[vid] = exit_time
                exited_vehicles += 1
                print(f"Vehicle {vid} has reached exit point, will be removed at step {t + 1}")

        # Format vehicle positions for display
        vehicle_display = [
            (vid, row, col, direction)
            for vid, (row, col, direction) in vehicles.items()
            if vid not in vehicle_pending
        ]

        # Update visualization
        visualizer.update(vehicle_display, traffic_light_states, crossing_states)
        await asyncio.sleep(0.1)

    # Show final metrics
    display_metrics(total_vehicles, exited_vehicles, vehicle_wait_times)
    pygame.quit()
    print("Simulation complete.")


async def process_vehicle_update(runtime: SingleThreadedAgentRuntime, vid: str,
                                 traffic_light_states: Dict[str, str],
                                 crossing_states: Dict[str, bool],
                                 vehicles: Dict[str, Tuple[int, int, str]],
                                 vehicle_wait_times: Dict[str, int],
                                 vehicle_pending: List[str],
                                 t: int) -> Tuple[bool, int]:
    """Process updates for a single vehicle and return exiting status."""
    old_stdout = os.dup(1)
    r, w = os.pipe()
    os.dup2(w, 1)

    await runtime.send_message(UpdateVehicleCommand(traffic_light_states, crossing_states),
                               AgentId(vid, "default"))

    os.dup2(old_stdout, 1)
    os.close(old_stdout)
    os.close(w)

    output = os.read(r, 10000).decode().strip()
    os.close(r)

    # Check if vehicle has reached an exit point
    exiting = "exiting=True" in output
    exit_time = t + 1 if exiting else -1

    # Update wait time if vehicle waited
    if "wait_time=" in output:
        wait_time_part = output.split("wait_time=")[1].split(",")[0]
        try:
            current_wait = int(wait_time_part)
            # Only count the incremental wait time
            if vid in vehicle_wait_times and current_wait > vehicle_wait_times[vid]:
                vehicle_wait_times[vid] = current_wait
        except ValueError:
            pass

    # Parse position from output
    if "position=" in output:
        position_part = output.split("position=")[1].split("),")[0] + ")"
        direction_part = output.split("direction=")[1].split(",")[0]

        # Parse row and column from position string "(row,col)"
        position_part = position_part.strip("()")
        row, col = map(int, position_part.split(","))

        # Update vehicle position
        vehicles[vid] = (row, col, direction_part)

        # Remove from pending list if it was there
        if vid in vehicle_pending:
            vehicle_pending.remove(vid)

    return exiting, exit_time


async def update_agent_state(runtime: SingleThreadedAgentRuntime, agent_id: str,
                             command: Any, state_key: str) -> str:
    """Send update command to an agent and capture its state output."""
    old_stdout = os.dup(1)
    r, w = os.pipe()
    os.dup2(w, 1)

    await runtime.send_message(command, AgentId(agent_id, "default"))

    os.dup2(old_stdout, 1)
    os.close(old_stdout)
    os.close(w)

    output = os.read(r, 10000).decode().strip()
    os.close(r)

    # Parse state from output
    if state_key in output:
        state_part = output.split(f"{state_key}=")[1].split(",")[0]
        return state_part
    return ""


async def update_traffic_lights(runtime: SingleThreadedAgentRuntime,
                                traffic_light_agents: List[str]) -> Dict[str, str]:
    """Update all traffic light agents and return their states."""
    traffic_light_states = {}
    for agent_id in traffic_light_agents:
        state = await update_agent_state(runtime, agent_id, UpdateCommand(), "state")
        if state:
            traffic_light_states[agent_id] = state
    return traffic_light_states


async def update_pedestrian_crossings(runtime: SingleThreadedAgentRuntime,
                                      crossing_agents: List[str]) -> Dict[str, bool]:
    """Update all pedestrian crossing agents and return their states."""
    crossing_states = {}
    for agent_id in crossing_agents:
        active = await update_agent_state(runtime, agent_id, UpdateCommand(), "active")
        if active:
            crossing_states[agent_id] = active == "True"
    return crossing_states
