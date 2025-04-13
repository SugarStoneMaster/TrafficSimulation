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
from src.agents.veichle import VehicleAgent
from src.simulation.agent_factory import register_traffic_lights, register_pedestrian_crossings, create_new_vehicle, register_parking_agents
from src.simulation.grid import extract_special_positions, initialize_grid
from src.simulation.metrics import display_metrics
from src.simulation.visualizer import PyGameVisualizer


async def run_simulation_without_parking(runtime: SingleThreadedAgentRuntime, simulation_time: int = 10,
                                         road_size="small",
                                         traffic_light_timing=(5, 4), pedestrian_crossing_timing=(1, 3)) -> None:
    """Run the traffic simulation without parking functionality."""
    # Initialize components
    grid = initialize_grid(road_size)
    visualizer = PyGameVisualizer(grid, with_parking=False)
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
            (vid, row, col, direction, is_parked, in_parking_delay, exit_delay)
            # Unpack all values from the vehicles dictionary
            for vid, (row, col, direction, is_parked, in_parking_delay, exit_delay) in vehicles.items()
            if vid not in vehicle_pending
        ]

        # Update visualization
        visualizer.update(vehicle_display, traffic_light_states, crossing_states)
        await asyncio.sleep(0.1)

    # Show final metrics
    display_metrics(total_vehicles, exited_vehicles, vehicle_wait_times)
    pygame.quit()
    print("Simulation complete.")


async def run_simulation_with_parking(runtime: SingleThreadedAgentRuntime, simulation_time: int = 10, road_size="small",
                                      traffic_light_timing=(5, 4), pedestrian_crossing_timing=(1, 3),
                                      avg_parking_time: int = 5, parking_initial_occupancy: float = 0.3, parking_delay_steps: int = 1) -> None:
    """Run the traffic simulation with parking functionality."""
    # Initialize components
    grid = initialize_grid(road_size)
    visualizer = PyGameVisualizer(grid, with_parking=True)
    traffic_light_positions, crossing_positions = extract_special_positions(grid)

    VehicleAgent.PARKING_DELAY_STEPS = parking_delay_steps


    # Register agents
    traffic_light_agents = await register_traffic_lights(runtime, traffic_light_positions, traffic_light_timing)
    crossing_agents = await register_pedestrian_crossings(runtime, grid, crossing_positions, pedestrian_crossing_timing)
    parking_agents = await register_parking_agents(runtime, grid, avg_parking_time, parking_initial_occupancy)

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
        parking_status = await update_parking_agents(runtime, parking_agents, t)

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


        # Decrement parking delay counters after each full update cycle
        if t > 0:  # Only do this once per step (with first vehicle)
            cells_to_clear = []
            for cell, delay_steps in VehicleAgent._parking_delay_cells.items():
                VehicleAgent._parking_delay_cells[cell] -= 1
                if VehicleAgent._parking_delay_cells[cell] <= 0:
                    cells_to_clear.append(cell)

            # Remove cells with no more delay
            for cell in cells_to_clear:
                del VehicleAgent._parking_delay_cells[cell]

        # Format vehicle positions for display
        vehicle_display = [
            (vid, row, col, direction, is_parked, in_delay, exit_delay)
            for vid, (row, col, direction, is_parked, in_delay, exit_delay) in vehicles.items()
            if vid not in vehicle_pending
        ]

        # Update visualization
        visualizer.update(vehicle_display, traffic_light_states, crossing_states)
        await asyncio.sleep(0.1)

    # Show final metrics
    display_metrics(total_vehicles, exited_vehicles, vehicle_wait_times)
    pygame.quit()
    print("Simulation complete.")


async def run_simulation(runtime: SingleThreadedAgentRuntime, simulation_time: int = 10, road_size="small",
                         traffic_light_timing=(5, 4), pedestrian_crossing_timing=(1, 3),
                         with_parking: bool = False, avg_parking_time: int = 5,
                         parking_initial_occupancy: float = 0.3,
                         parking_delay_steps: int = 1) -> None:
    """
    Dispatcher function to run the appropriate simulation based on parameters.

    Args:
        with_parking: If True, runs simulation with parking functionality
    """
    if with_parking:
        await run_simulation_with_parking(
            runtime, simulation_time, road_size,
            traffic_light_timing, pedestrian_crossing_timing,
            avg_parking_time, parking_initial_occupancy, parking_delay_steps
        )
    else:
        await run_simulation_without_parking(
            runtime, simulation_time, road_size,
            traffic_light_timing, pedestrian_crossing_timing
        )


# In src/simulation/simulation.py
async def process_vehicle_update(runtime: SingleThreadedAgentRuntime, vid: str,
                                 traffic_light_states: Dict[str, str],
                                 crossing_states: Dict[str, bool],
                                 vehicles: Dict[str, Tuple[int, int, str, bool]],
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
        try:
            direction_part = output.split("direction=")[1].split(",")[0]
        except IndexError:
            direction_part = "unknown"  # Provide a default value

        is_parked = "is_parked=True" in output
        exiting_delay = False

        # Parse the exiting_delay info from output
        if "exiting_delay=True" in output:
            exiting_delay = True

        # Parse row and column from position string "(row,col)"
        position_part = position_part.strip("()")
        row, col = map(int, position_part.split(","))

        # Check if this cell has a parking delay
        in_parking_delay = (row, col) in VehicleAgent._parking_delay_cells

        # Update vehicle position
        vehicles[vid] = (row, col, direction_part, is_parked, in_parking_delay, exiting_delay)

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


# Add this function to src/simulation/simulation.py
async def update_parking_agents(runtime: SingleThreadedAgentRuntime,
                               parking_agents: List[str],
                               current_time: int) -> None:
    """Update all parking agents with the current time."""
    for agent_id in parking_agents:
        await update_agent_state(runtime, agent_id, UpdateCommand(current_time=current_time), "None")