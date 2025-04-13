import asyncio
import argparse

from autogen_core import SingleThreadedAgentRuntime
from src.simulation.simulation import run_simulation


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Traffic Simulation System')

    parser.add_argument('--time', type=int, default=100,
                        help='Simulation duration in steps (default: 100)')
    parser.add_argument('--road-size', type=str, default='large', choices=['small', 'medium', 'large'],
                        help='Road size - small, medium, large (default: large)')
    parser.add_argument('--with-parking', action='store_true',
                        help='Enable parking functionality')

    # Parse tuples as strings and convert them
    parser.add_argument('--traffic-light-timing', type=str, default='5,4',
                        help='Tuple for red/green durations (default: 5,4)')
    parser.add_argument('--pedestrian-crossing-timing', type=str, default='1,3',
                        help='Tuple for crossing durations (default: 1,3)')

    parser.add_argument('--avg-parking-time', type=int, default=5,
                        help='Average time vehicles remain parked (default: 5)')
    parser.add_argument('--parking-delay-steps', type=int, default=4,
                        help='Steps needed to enter/exit parking (default: 4)')

    args = parser.parse_args()

    # Convert string tuples to actual tuples
    traffic_light_timing = tuple(map(int, args.traffic_light_timing.split(',')))
    pedestrian_crossing_timing = tuple(map(int, args.pedestrian_crossing_timing.split(',')))

    # Initialize the runtimes
    runtime_no_parking = SingleThreadedAgentRuntime()
    runtime_with_parking = SingleThreadedAgentRuntime()

    # If with_parking is specified, run only the parking scenario
    if args.with_parking:
        runtime_with_parking.start()
        print("\nRunning simulation WITH parking...")
        await run_simulation(
            runtime_with_parking,
            simulation_time=args.time,
            road_size=args.road_size,
            traffic_light_timing=traffic_light_timing,
            pedestrian_crossing_timing=pedestrian_crossing_timing,
            with_parking=True,
            avg_parking_time=args.avg_parking_time,
            parking_delay_steps=args.parking_delay_steps
        )
        await runtime_with_parking.stop()
        await runtime_with_parking.close()
    else:
        # Otherwise, run both scenarios sequentially
        runtime_no_parking.start()
        print("\nRunning simulation WITHOUT parking...")
        await run_simulation(
            runtime_no_parking,
            simulation_time=args.time,
            road_size=args.road_size,
            traffic_light_timing=traffic_light_timing,
            pedestrian_crossing_timing=pedestrian_crossing_timing,
            with_parking=False
        )
        await runtime_no_parking.stop()
        await runtime_no_parking.close()


        runtime_with_parking.start()
        print("\nRunning simulation WITH parking...")
        await run_simulation(
            runtime_with_parking,
            simulation_time=args.time,
            road_size=args.road_size,
            traffic_light_timing=traffic_light_timing,
            pedestrian_crossing_timing=pedestrian_crossing_timing,
            with_parking=True,
            avg_parking_time=args.avg_parking_time,
            parking_delay_steps=args.parking_delay_steps
        )
        await runtime_with_parking.stop()
        await runtime_with_parking.close()


if __name__ == "__main__":
    asyncio.run(main())