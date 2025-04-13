import logging
from autogen_core import RoutedAgent, message_handler, MessageContext, AgentId
import random
from typing import List, Tuple, Dict, Optional

from src.agents.messages import UpdateVehicleCommand, ParkingResponseCommand, ParkingRequestCommand
from src.simulation.grid import RoadGrid, RoadCell

# Configure logging
logging.basicConfig(filename='vehicle_agent.log', level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class VehicleAgent(RoutedAgent):
    _all_vehicle_positions = {}
    _parking_positions_to_agent_ids = {}
    _parking_delay_cells = {}  # Track cells with parking delays
    PARKING_DELAY_STEPS = 1    # Default value, will be updated by simulation


    def __init__(self, vehicle_id: int, grid: RoadGrid, parking_probability: float = 0.1, parking_duration: int = 15, start_position: Optional[Tuple[int, int]] = None):
        super().__init__(f"VehicleAgent-{vehicle_id}")
        self.vehicle_id = vehicle_id
        self.grid = grid
        self.wait_time = 0
        self.current_lane = 0
        self.parking_probability = parking_probability
        self.parking_duration = parking_duration
        self.is_parked = False
        self.parking_timer = 0
        self.parking_agent_id: Optional[str] = None
        self.exiting_parking_timer = 0  # Track time spent exiting a parking spot


        if start_position:
            self.row, self.col = start_position
        else:
            self.row, self.col = self._find_random_entry_point()

        self.direction = self._get_direction_from_cell(self.grid.grid[self.row][self.col])

        # Register this vehicle in the position tracking dictionary
        if (self.row, self.col) not in VehicleAgent._all_vehicle_positions:
            VehicleAgent._all_vehicle_positions[(self.row, self.col)] = []
        VehicleAgent._all_vehicle_positions[(self.row, self.col)].append(self.id)


        logging.debug(f"Initialized VehicleAgent-{self.vehicle_id} at position ({self.row}, {self.col}) with direction {self.direction}")

    def _find_random_entry_point(self) -> Tuple[int, int]:
        """Find a valid entry point that matches exactly with the road layout."""
        entry_points = []

        # Scan the edges of the grid for road cells with appropriate directions

        # Top edge (row 0)
        for c in range(self.grid.cols):
            cell = self.grid.grid[0][c]
            if cell.cell_type == "road" and any(d in ["southbound"] for d in cell.features):
                entry_points.append((0, c))

        # Bottom edge (last row)
        for c in range(self.grid.cols):
            cell = self.grid.grid[self.grid.rows - 1][c]
            if cell.cell_type == "road" and any(d in ["northbound"] for d in cell.features):
                entry_points.append((self.grid.rows - 1, c))

        # Left and right edges (for horizontal roads, if any)
        for r in range(1, self.grid.rows - 1):  # Skip corners which are already checked
            # Left edge
            if self.grid.grid[r][0].cell_type == "road" and any(
                    d in ["eastbound"] for d in self.grid.grid[r][0].features):
                entry_points.append((r, 0))
            # Right edge
            if self.grid.grid[r][self.grid.cols - 1].cell_type == "road" and any(
                    d in ["westbound"] for d in self.grid.grid[r][self.grid.cols - 1].features):
                entry_points.append((r, self.grid.cols - 1))

        # If no proper entry points found, fall back to the default ones
        if not entry_points:
            left_c = 0
            right_c = self.grid.cols - 1
            left_mid_c = max(0, min(self.grid.cols - 1, int(round(0.2 * (self.grid.cols - 1)))))
            right_mid_c = max(0, min(self.grid.cols - 1, int(round(0.8 * (self.grid.cols - 1)))))

            entry_points = [
                (0, left_c),
                (self.grid.rows - 1, right_c),
                (self.grid.rows - 1, left_mid_c),
                (0, right_mid_c)
            ]

        chosen_entry = random.choice(entry_points)
        logging.debug(f"VehicleAgent-{self.vehicle_id} found entry point at {chosen_entry}")
        return chosen_entry


    def _get_direction_from_cell(self, cell: RoadCell) -> str:
        directions = [d for d in cell.features if d in ["northbound", "southbound", "eastbound", "westbound"]]
        chosen_direction = random.choice(directions) if directions else "eastbound"
        logging.debug(f"VehicleAgent-{self.vehicle_id} got direction {chosen_direction} from cell features {cell.features}")
        return chosen_direction


    def _can_move_forward(self, traffic_light_states: Dict[str, str], crossing_states: Dict[str, bool]) -> bool:
        direction_offsets = {
            "northbound": (-1, 0),
            "southbound": (1, 0),
            "eastbound": (0, 1),
            "westbound": (0, -1)
        }

        # Check the cell in the direction we're heading
        dr, dc = direction_offsets.get(self.direction, (0, 0))
        next_row, next_col = self.row + dr, self.col + dc

        # Check if next position is within grid bounds
        if 0 <= next_row < self.grid.rows and 0 <= next_col < self.grid.cols:
            next_cell = self.grid.grid[next_row][next_col]

            # Check for parking delay - block movement if there's a parking maneuver
            if (next_row, next_col) in VehicleAgent._parking_delay_cells:
                return False

            # Check for red traffic light
            if "traffic_light" in next_cell.features:
                # Find the traffic light ID for this position
                for i, (r, c) in enumerate(self._get_traffic_light_positions()):
                    if r == next_row and c == next_col:
                        tl_id = f"traffic_light_{i + 1}"
                        if traffic_light_states.get(tl_id, "red") == "red":
                            return False

            # Check for active pedestrian crossing
            if "pedestrian_crossing" in next_cell.features:
                # Find the pedestrian crossing ID for this position
                for i, (r, c) in enumerate(self._get_pedestrian_crossing_positions()):
                    if r == next_row and c == next_col:
                        crossing_id = f"crossing_{i + 1}"
                        if crossing_states.get(crossing_id, False):
                            logging.debug(
                                f"VehicleAgent-{self.vehicle_id} stopped for active crossing at ({next_row}, {next_col})")
                            return False

        return True

    def _get_next_position(self) -> Tuple[int, int]:
        possible_directions = self._get_possible_directions(self.row, self.col, self.grid)
        logging.debug(f"VehicleAgent-{self.vehicle_id} possible directions from ({self.row}, {self.col}): {possible_directions}")

        if not possible_directions:
            logging.debug(f"VehicleAgent-{self.vehicle_id} has no possible directions from ({self.row}, {self.col})")
            return self.row, self.col

        if len(possible_directions) > 1:
            if random.random() < 0.5:
                turn_options = {d: pos for d, pos in possible_directions.items() if d != self.direction}
                if turn_options:
                    new_direction = random.choice(list(turn_options.keys()))
                    self.direction = new_direction
                    logging.debug(f"VehicleAgent-{self.vehicle_id} turning to new direction {new_direction}")
                    return possible_directions[new_direction]

        if self.direction in possible_directions:
            logging.debug(f"VehicleAgent-{self.vehicle_id} continuing in current direction {self.direction}")
            return possible_directions[self.direction]

        new_direction = random.choice(list(possible_directions.keys()))
        self.direction = new_direction
        logging.debug(f"VehicleAgent-{self.vehicle_id} changing to new direction {new_direction}")
        return possible_directions[new_direction]

    def _get_possible_directions(self, row, col, grid) -> Dict[str, Tuple[int, int]]:
        directions = {}
        current_cell = grid.grid[row][col]

        # Direction mapping
        direction_offsets = {
            "northbound": (-1, 0),
            "southbound": (1, 0),
            "eastbound": (0, 1),
            "westbound": (0, -1)
        }

        # First check all adjacent road cells
        valid_adjacent_cells = {}
        for direction, (dr, dc) in direction_offsets.items():
            next_row, next_col = row + dr, col + dc
            if 0 <= next_row < grid.rows and 0 <= next_col < grid.cols:
                next_cell = grid.grid[next_row][next_col]

                # Check if cell is a road and has capacity
                if next_cell.cell_type == "road":
                    # Check if the cell has room based on lanes
                    vehicles_in_cell = len(VehicleAgent._all_vehicle_positions.get((next_row, next_col), []))
                    if vehicles_in_cell < next_cell.lanes or self.id in VehicleAgent._all_vehicle_positions.get(
                            (next_row, next_col), []):
                        # Only add directions that are explicitly supported in the next cell
                        if direction in next_cell.features:
                            valid_adjacent_cells[direction] = (next_row, next_col, next_cell)

        is_intersection = len(valid_adjacent_cells) >= 3
        logging.debug(
            f"VehicleAgent-{self.vehicle_id} at ({row}, {col}) is at intersection: {is_intersection} with {len(valid_adjacent_cells)} valid cells")

        # Always prioritize continuing in the current direction if possible
        if self.direction in valid_adjacent_cells:
            next_row, next_col, next_cell = valid_adjacent_cells[self.direction]
            directions[self.direction] = (next_row, next_col)
            logging.debug(f"VehicleAgent-{self.vehicle_id} can continue in current direction {self.direction}")

        # Add other valid directions
        for direction, (next_row, next_col, next_cell) in valid_adjacent_cells.items():
            if direction in directions:
                continue
            directions[direction] = (next_row, next_col)

        # Fallback if no directions found
        if not directions and current_cell.cell_type == "road":
            logging.warning(
                f"VehicleAgent-{self.vehicle_id} at ({row}, {col}) found no valid directions despite being on a road")

        return directions


    def _is_exit_point(self, row: int, col: int) -> bool:
        """Check if the current position is an exit point (endpoint) of the map."""
        # Define the exit points
        left_c = 0  # Left column (bottom of southbound two-lane road)
        right_c = self.grid.cols - 1  # Right column (top of northbound road)

        # Use the same calculation method as in entry points
        left_mid_c = max(0, min(self.grid.cols - 1, int(round(0.2 * (self.grid.cols - 1)))))
        right_mid_c = max(0, min(self.grid.cols - 1, int(round(0.8 * (self.grid.cols - 1)))))

        # Exit points based on direction
        exit_points = [
            (self.grid.rows - 1, left_c, "southbound"),  # Bottom of southbound two-lane road
            (0, right_c, "northbound"),  # Top of northbound road
            (0, left_mid_c, "northbound"),  # Top of vertical northbound road
            (self.grid.rows - 1, right_mid_c, "southbound")  # Bottom of vertical southbound road
        ]

        for exit_row, exit_col, exit_dir in exit_points:
            if row == exit_row and col == exit_col and self.direction == exit_dir:
                logging.info(f"VehicleAgent-{self.vehicle_id} reached exit point at ({row}, {col})")
                return True
        return False

    def _get_pedestrian_crossing_positions(self) -> List[Tuple[int, int]]:
        """Return a list of (row, col) for all pedestrian crossings in the grid."""
        positions = []
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                if "pedestrian_crossing" in self.grid.grid[r][c].features:
                    positions.append((r, c))
        return positions

    def _get_traffic_light_positions(self) -> List[Tuple[int, int]]:
        """Return a list of (row, col) for all traffic lights in the grid."""
        positions = []
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                if "traffic_light" in self.grid.grid[r][c].features:
                    positions.append((r, c))
        return positions

    def _should_attempt_parking(self) -> bool:
        """Determine whether the vehicle should attempt to park."""
        return random.random() < self.parking_probability and not self.is_parked

    @message_handler
    async def handle_parking_response(self, message: ParkingResponseCommand, ctx: MessageContext) -> None:
        """Handle the response from a parking agent."""
        if message.accepted:
            self.is_parked = True
            self.parking_timer = self.parking_duration
            self.parking_agent_id = ctx.sender

            # Remove this position from parking delay cells if it's there
            if (self.row, self.col) in VehicleAgent._parking_delay_cells:
                del VehicleAgent._parking_delay_cells[(self.row, self.col)]

            print(f"{self.id}: Parked successfully at {self.row}, {self.col} for {self.parking_duration} steps")
        else:
            print(f"{self.id}: Parking request rejected.")

    @message_handler
    async def handle_update(self, message: UpdateVehicleCommand, ctx: MessageContext) -> None:
        """Process updates for vehicle movement and parking behavior."""
        # Check if vehicle is currently parked
        if self.is_parked:
            self.parking_timer -= 1
            if self.parking_timer <= 0:
                # When parking time is over, start the exiting process
                self.is_parked = False
                self.parking_agent_id = None

                # Set exit delay for this cell and for the vehicle itself
                VehicleAgent._parking_delay_cells[(self.row, self.col)] = VehicleAgent.PARKING_DELAY_STEPS
                self.exiting_delay = True
                print(f"{self.id}: Starting to exit parking at ({self.row}, {self.col})")

                # Re-register position since we're staying here during the exit delay
                if (self.row, self.col) not in VehicleAgent._all_vehicle_positions:
                    VehicleAgent._all_vehicle_positions[(self.row, self.col)] = []
                VehicleAgent._all_vehicle_positions[(self.row, self.col)].append(self.id)

            # While parked, just print status and don't move
            print(
                f"{self.id}: position=({self.row},{self.col}), wait_time={self.wait_time}, direction={self.direction}, is_parked={self.is_parked}, exiting_delay={getattr(self, 'exiting_delay', False)}")
            return

        # If we have an exiting delay active, count it down
        if getattr(self, 'exiting_delay', False):
            if not hasattr(self, 'exiting_delay_counter'):
                self.exiting_delay_counter = VehicleAgent.PARKING_DELAY_STEPS

            self.exiting_delay_counter -= 1
            if self.exiting_delay_counter <= 0:
                self.exiting_delay = False
                delattr(self, 'exiting_delay_counter')
                print(f"{self.id}: Finished exit delay at ({self.row}, {self.col})")

        # Get occupied cells from the message if provided
        occupied_cells = getattr(message, 'occupied_cells', {})
        traffic_light_states = message.traffic_light_states
        crossing_states = message.crossing_states

        # Attempt to park if near a parking spot and randomly decide to try parking
        if not getattr(self, 'exiting_delay', False) and self._should_attempt_parking():
            parking_position = (self.row, self.col)
            if parking_position in VehicleAgent._parking_positions_to_agent_ids:
                parking_agent_id = VehicleAgent._parking_positions_to_agent_ids[parking_position]
                await self.send_message(
                    ParkingRequestCommand(self.id.__str__(), 0), AgentId(parking_agent_id, "default")
                )
                # Add this position to parking delay cells
                VehicleAgent._parking_delay_cells[parking_position] = VehicleAgent.PARKING_DELAY_STEPS
                print(f"{self.id}: Requesting parking at {parking_position}")

        # Check if we can move (not blocked by other vehicles)
        can_move = True
        if (self.row, self.col) in occupied_cells:
            # If other vehicles are here, wait
            if occupied_cells[(self.row, self.col)] > 1:
                can_move = False
                self.wait_time += 1

        # Check traffic lights
        if can_move:
            # Get all traffic light positions in the grid
            traffic_light_positions = self._get_traffic_light_positions()
            # Check if we're at a traffic light position
            if (self.row, self.col) in traffic_light_positions:
                # Get the traffic light ID
                light_id = f"traffic_light_{traffic_light_positions.index((self.row, self.col)) + 1}"
                # Check if we're allowed to move (green light)
                if light_id in traffic_light_states and traffic_light_states[light_id] != "green":
                    can_move = False
                    self.wait_time += 1

        # Check pedestrian crossings
        if can_move:
            # Get all pedestrian crossing positions
            crossing_positions = self._get_pedestrian_crossing_positions()
            # Check if we're at a pedestrian crossing
            if (self.row, self.col) in crossing_positions:
                # Get the crossing ID
                crossing_id = f"crossing_{crossing_positions.index((self.row, self.col)) + 1}"
                # Check if we're allowed to move (inactive crossing)
                if crossing_id in crossing_states and crossing_states[crossing_id]:
                    can_move = False
                    self.wait_time += 1

        # Move if possible
        if can_move and not getattr(self, 'exiting_delay', False) and self._can_move_forward(traffic_light_states,
                                                                                             crossing_states):
            # Remove current position from registry before potentially moving
            if (self.row, self.col) in VehicleAgent._all_vehicle_positions:
                if self.id in VehicleAgent._all_vehicle_positions[(self.row, self.col)]:
                    VehicleAgent._all_vehicle_positions[(self.row, self.col)].remove(self.id)
                    # Clean up empty lists
                    if not VehicleAgent._all_vehicle_positions[(self.row, self.col)]:
                        del VehicleAgent._all_vehicle_positions[(self.row, self.col)]

            # Get next position
            old_row, old_col = self.row, self.col
            new_row, new_col = self._get_next_position()
            self.row, self.col = new_row, new_col

            # Register new position
            if (self.row, self.col) not in VehicleAgent._all_vehicle_positions:
                VehicleAgent._all_vehicle_positions[(self.row, self.col)] = []
            VehicleAgent._all_vehicle_positions[(self.row, self.col)].append(self.id)

            # Check if we've reached an exit point
            exiting = self._is_exit_point(self.row, self.col)
        else:
            # Not moving this step
            exiting = False

        # Print status
        print(
            f"{self.id}: position=({self.row},{self.col}), wait_time={self.wait_time}, direction={self.direction}, is_parked={self.is_parked}, exiting_delay={getattr(self, 'exiting_delay', False)}, exiting={exiting}")