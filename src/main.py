import asyncio

from autogen_core import (
    SingleThreadedAgentRuntime,
)
from src.simulation.simulation import run_simulation







async def main():
    runtime = SingleThreadedAgentRuntime()
    runtime.start()

    await run_simulation(runtime, simulation_time=50, road_size="large",
                         traffic_light_timing=(9, 4), pedestrian_crossing_timing=(1, 3),
                         with_parking=False, parking_delay_steps=4)

    await runtime.stop()
    await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())