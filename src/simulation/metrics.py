from typing import Dict
import matplotlib.pyplot as plt


def display_metrics(total_vehicles: int, exited_vehicles: int, vehicle_wait_times: Dict[str, int],
                    with_parking: bool = False) -> None:
    """Display and visualize simulation metrics."""
    all_wait_times = list(vehicle_wait_times.values())

    print("\n===== SIMULATION METRICS =====")
    print(f"Simulation type: {'With Parking' if with_parking else 'Without Parking'}")
    print(f"Total vehicles created: {total_vehicles}")
    print(f"Vehicles that completed the circuit: {exited_vehicles}")
    print(f"Completion rate: {exited_vehicles / total_vehicles * 100:.1f}%")

    if all_wait_times:
        print("\n--- Waiting Time Statistics ---")
        print(f"Maximum wait time: {max(all_wait_times)} steps")
        print(f"Average wait time: {sum(all_wait_times) / len(all_wait_times):.2f} steps")

    # Visualize with matplotlib
    try:
        plt.figure(figsize=(10, 6))
        plt.hist(all_wait_times, bins=20, color='skyblue', edgecolor='black')

        # Add parking information to the title
        sim_type = "With Parking" if with_parking else "Without Parking"
        plt.title(f'Distribution of Vehicle Wait Times ({sim_type})')
        plt.xlabel('Wait Time (steps)')
        plt.ylabel('Number of Vehicles')
        plt.grid(True, alpha=0.3)

        # Create different filenames based on parking status
        filename = 'wait_time_with_parking.png' if with_parking else 'wait_time_without_parking.png'
        plt.savefig(filename)

        print(f"\nMetrics visualization saved to '{filename}'")
    except ImportError:
        print("\nMatplotlib not installed. Skipping visualization.")