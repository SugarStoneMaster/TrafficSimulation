import asyncio
import os
import platform
import pygame
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple

from autogen_core import (
    AgentId,
    SingleThreadedAgentRuntime,
)

from agents.intelligent import IntelligentAgent
from agents.messages import UpdateCommand, UpdateVehicleCommand
from agents.pedestrian_crossing import PedestrianCrossingAgent
from agents.traffic_light import TrafficLightAgent
from agents.veichle import VehicleAgent
from grid import RoadGrid
from visualizer import PyGameVisualizer


async def run_simulation(runtime: SingleThreadedAgentRuntime, simulation_time: int = 10, road_size = "small",
                         traffic_light_timing=(5, 4), pedestrian_crossing_timing=(1, 3)) -> None:

    # Initialize the grid
    if road_size == "small":
        grid = RoadGrid(rows=10, cols=15)
    elif road_size == "medium":
        grid = RoadGrid(rows=15, cols=20)
    elif road_size == "large":
        grid = RoadGrid(rows=20, cols=30)
    grid.display()

    # Initialize PyGame visualizer
    visualizer = PyGameVisualizer(grid)

    # Metrics tracking
    total_vehicles = 0
    exited_vehicles = 0
    vehicle_wait_times = {}  # {vehicle_id: total_wait_time}

    # Track vehicle positions
    vehicles = {}  # {vehicle_id: (row, col, direction)}

    # Extract traffic light and pedestrian crossing positions from the grid
    traffic_light_positions = []
    crossing_positions = []

    for r in range(grid.rows):
        for c in range(grid.cols):
            cell = grid.grid[r][c]
            if "traffic_light" in cell.features:
                traffic_light_positions.append((r, c))
            if "pedestrian_crossing" in cell.features:
                crossing_positions.append((r, c))

    # Register traffic light agents
    traffic_light_agents = []
    for i, pos in enumerate(traffic_light_positions):
        agent_id = f"traffic_light_{i + 1}"
        await TrafficLightAgent.register(
            runtime,
            agent_id,
            lambda i_val=i, red=traffic_light_timing[0], green=traffic_light_timing[1]:
            TrafficLightAgent(i_val + 1, red_duration=red, green_duration=green)
        )
        traffic_light_agents.append(agent_id)

    # Register pedestrian crossing agents
    crossing_agents = []
    for i, pos in enumerate(crossing_positions):
        agent_id = f"crossing_{i + 1}"
        r, c = pos
        lanes = grid.grid[r][c].lanes
        # Use one-lane or two-lane timing based on number of lanes
        duration = pedestrian_crossing_timing[1] if lanes > 1 else pedestrian_crossing_timing[0]
        await PedestrianCrossingAgent.register(
            runtime,
            agent_id,
            lambda i_val=i, lanes_val=lanes, active_duration=duration:
            PedestrianCrossingAgent(i_val + 1, lanes=lanes_val, active_duration=active_duration)
        )
        crossing_agents.append(agent_id)

    # Register intelligent agent
    await IntelligentAgent.register(runtime, "intelligent_agent", lambda: IntelligentAgent())

    vehicle_ids = []
    vehicle_pending = []  # Track vehicles that need position initialization
    vehicles_exiting = {}  # {vehicle_id: time_step_to_remove}

    # Simulation loop
    for t in range(simulation_time):
        # Check for PyGame quit event
        if not visualizer.check_events():
            break

        # Process vehicles that were marked for removal in the previous step
        vehicles_to_remove = []
        for vid, removal_time in list(vehicles_exiting.items()):
            if t >= removal_time:
                vehicles_to_remove.append(vid)
                vehicles_exiting.pop(vid)
                print(f"Vehicle {vid} has been removed from the simulation")

        # Remove vehicles marked for removal
        for vid in vehicles_to_remove:
            if vid in vehicle_ids:
                vehicle_ids.remove(vid)
            if vid in vehicles:
                del vehicles[vid]

        # Create a new vehicle every step
        if t > 0:
            total_vehicles += 1
            new_vehicle_id = t
            vehicle_key = f"vehicle_{new_vehicle_id}"
            await VehicleAgent.register(runtime, vehicle_key, lambda: VehicleAgent(new_vehicle_id, grid))
            vehicle_ids.append(vehicle_key)
            vehicle_pending.append(vehicle_key)
            vehicle_wait_times[vehicle_key] = 0  # Initialize wait time


        # Update traffic lights
        traffic_light_states = {}  # {agent_id: state}
        for agent_id in traffic_light_agents:
            # Store output before sending command (to capture state info)
            old_stdout = os.dup(1)
            r, w = os.pipe()
            os.dup2(w, 1)

            # Send update command
            await runtime.send_message(UpdateCommand(), AgentId(agent_id, "default"))

            # Restore stdout
            os.dup2(old_stdout, 1)
            os.close(old_stdout)
            os.close(w)

            # Read captured output
            output = os.read(r, 10000).decode().strip()
            os.close(r)

            # Parse state from output
            if "state=" in output:
                state_part = output.split("state=")[1].split(",")[0]
                traffic_light_states[agent_id] = state_part

        # Update pedestrian crossings
        crossing_states = {}  # {agent_id: active}
        for agent_id in crossing_agents:
            # Store output before sending command
            old_stdout = os.dup(1)
            r, w = os.pipe()
            os.dup2(w, 1)

            # Send update command
            await runtime.send_message(UpdateCommand(), AgentId(agent_id, "default"))

            # Restore stdout
            os.dup2(old_stdout, 1)
            os.close(old_stdout)
            os.close(w)

            # Read captured output
            output = os.read(r, 10000).decode().strip()
            os.close(r)

            # Parse active state from output
            if "active=" in output:
                active_part = output.split("active=")[1].split(",")[0]
                crossing_states[agent_id] = active_part == "True"


        # Update vehicles
        for vid in vehicle_ids:
            # Store output before sending command (to capture position info)
            old_stdout = os.dup(1)
            r, w = os.pipe()
            os.dup2(w, 1)

            # Send command to vehicle
            await runtime.send_message(UpdateVehicleCommand(traffic_light_states, crossing_states),
                                       AgentId(vid, "default"))
            # Restore stdout
            os.dup2(old_stdout, 1)
            os.close(old_stdout)
            os.close(w)

            # Read captured output
            output = os.read(r, 10000).decode().strip()
            os.close(r)

            # Check if vehicle has reached an exit point
            if "exiting=True" in output and vid not in vehicles_exiting:
                vehicles_exiting[vid] = t + 1
                exited_vehicles += 1
                print(f"Vehicle {vid} has reached exit point, will be removed at step {t + 1}")

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

        # Format vehicle positions for display - only for vehicles with known positions
        vehicle_display = []
        for vid in vehicle_ids:
            if vid in vehicles and vid not in vehicle_pending:  # Only display vehicles with positions
                row, col, direction = vehicles[vid]
                vehicle_display.append((vid, row, col, direction))

        # Update visualization
        visualizer.update(vehicle_display, traffic_light_states, crossing_states)

        # Wait for the next time step
        await asyncio.sleep(0.1)

    # Analyze and display metrics
    all_wait_times = list(vehicle_wait_times.values())

    print("\n===== SIMULATION METRICS =====")
    print(f"Total vehicles created: {total_vehicles}")
    print(f"Vehicles that completed the circuit: {exited_vehicles}")
    print(f"Completion rate: {exited_vehicles / total_vehicles * 100:.1f}%")

    if all_wait_times:
        print("\n--- Waiting Time Statistics ---")
        print(f"Maximum wait time: {max(all_wait_times)} steps")
        print(f"Minimum wait time: {min(all_wait_times)} steps")
        print(f"Average wait time: {sum(all_wait_times) / len(all_wait_times):.2f} steps")

    # Optional: Visualize with matplotlib
    try:

        # Wait time distribution
        plt.figure(figsize=(10, 6))
        plt.hist(all_wait_times, bins=20, color='skyblue', edgecolor='black')
        plt.title('Distribution of Vehicle Wait Times')
        plt.xlabel('Wait Time (steps)')
        plt.ylabel('Number of Vehicles')
        plt.grid(True, alpha=0.3)
        plt.savefig('wait_time_distribution.png')

        print("\nMetrics visualization saved to 'wait_time_distribution.png'")
    except ImportError:
        print("\nMatplotlib not installed. Skipping visualization.")

    print("Simulation complete.")
    pygame.quit()


async def main():
    runtime = SingleThreadedAgentRuntime()
    runtime.start()

    await run_simulation(runtime, simulation_time=50, road_size="large", traffic_light_timing=(9, 4), pedestrian_crossing_timing=(1, 3))

    await runtime.stop()
    await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())