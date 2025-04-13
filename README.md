# Traffic Simulation System

This project is a multi-agent traffic simulation system that models the interaction between vehicles, traffic lights, pedestrian crossings, and parking spaces in a grid-based urban environment.

## Features

- Grid-based road network with configurable size (small, medium, large)
- Multiple agent types:
  - Vehicles that navigate roads following traffic rules
  - Traffic lights with configurable timing
  - Pedestrian crossings that activate randomly
  - Parking spaces (street parking and parking buildings)
- Visualization using PyGame
- Metrics collection and visualization (wait times, completion rates)
- Two simulation modes: with and without parking functionality

## How It Works

The simulation uses an agent-based approach where each entity (vehicle, traffic light, crossing, parking space) is an independent agent that makes decisions based on its local state and environment.

- Vehicles follow roads, respect traffic lights and pedestrian crossings
- Traffic lights cycle between red and green states with configurable timing
- Pedestrian crossings activate randomly but only when clear of vehicles
- In the parking scenario, vehicles can randomly decide to park and occupy parking spots for a duration

## Running the Simulation

To run the simulation:

1. Set up your environment:
   ```bash
   # Create a virtual environment
   python -m venv venv
   
   # Activate the virtual environment
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   # venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. Run the simulation with default settings:
   ```bash
   python main.py
   ```

3. Command line options:
   ```bash
   # Run with specific parameters
   python main.py --time 20 --road-size medium --with-parking
   
   # For help with all available options
   python main.py --help
   ```

4. Available parameters:
   - `--time`: Simulation duration in steps (default: 10)
   - `--road-size`: Road size - small, medium, large (default: small)
   - `--with-parking`: Enable parking functionality
   - `--traffic-light-timing`: Tuple for red/green durations (default: 5,4)
   - `--pedestrian-crossing-timing`: Tuple for crossing durations (default: 1,3)
   - `--avg-parking-time`: Average time vehicles remain parked (default: 5)
   - `--parking-delay-steps`: Steps needed to enter/exit parking (default: 1)

5. After running, metrics will be displayed and saved as a chart image in the current directory.



## Current Status

- **Without Parking Scenario**: Fully functional. Vehicles navigate the road network respecting traffic lights and pedestrian crossings.

- **With Parking Scenario**: Currently contains bugs in both the logic and visualization:
  - Some issues with vehicle movement when entering/exiting parking spots
  - Visualization glitches when displaying parked vehicles
  - Potential deadlocks in high-traffic situations around parking areas

## Metrics

The simulation collects metrics on:
- Total vehicles created
- Vehicles that completed their journey
- Average and maximum wait times

These metrics are displayed after the simulation ends and are also visualized using matplotlib.

## Visualization

The visualization shows:
- Road network with directional indicators
- Vehicles color-coded by state:
  - Purple: Regular moving vehicles
  - Red: Vehicles entering/exiting parking
  - Green: Parked vehicles
- Traffic lights (red/green)
- Active pedestrian crossings (yellow when active)

## Future Improvements

- Fix bugs in the parking scenario
- Add intelligent agent to manage traffic flow and optimize wait times