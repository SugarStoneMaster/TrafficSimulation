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


    def __init__(self, vehicle_id: int, grid: RoadGrid, parking_probability: float = 0.05, parking_duration: int = 5, start_position: Optional[Tuple[int, int]] = None):
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

        # Opposite directions (to prevent U-turns)
        opposite_directions = {
            "northbound": "southbound",
            "southbound": "northbound",
            "eastbound": "westbound",
            "westbound": "eastbound"
        }

        # Current cell's allowed directions
        current_allowed_directions = [d for d in current_cell.features
                                      if d in direction_offsets.keys()]

        logging.debug(
            f"VehicleAgent-{self.vehicle_id} at ({row}, {col}) - Current cell allows: {current_allowed_directions}")

        # Check all adjacent cells
        valid_adjacent_cells = {}
        for direction, (dr, dc) in direction_offsets.items():
            next_row, next_col = row + dr, col + dc

            # Skip U-turns unless it's the only option
            if direction == opposite_directions.get(self.direction):
                logging.debug(f"VehicleAgent-{self.vehicle_id}: Skipping {direction} as it would be a U-turn")
                continue

            if 0 <= next_row < grid.rows and 0 <= next_col < grid.cols:
                next_cell = grid.grid[next_row][next_col]

                logging.debug(f"VehicleAgent-{self.vehicle_id}: Checking {direction} -> ({next_row}, {next_col})")
                logging.debug(f"  Cell type: {next_cell.cell_type}, Features: {next_cell.features}")

                if next_cell.cell_type == "road":
                    vehicles_in_cell = len(VehicleAgent._all_vehicle_positions.get((next_row, next_col), []))
                    logging.debug(f"  Vehicles in cell: {vehicles_in_cell}, Cell lanes: {next_cell.lanes}")

                    # Check capacity
                    has_capacity = (vehicles_in_cell < next_cell.lanes or
                                    self.id in VehicleAgent._all_vehicle_positions.get((next_row, next_col), []))

                    # Check direction compatibility
                    direction_valid = False

                    # At intersection, be more permissive with direction choices
                    is_intersection = len([d for d in current_cell.features
                                           if d in direction_offsets.keys()]) >= 2

                    # Direction is valid if it matches next cell's allowed directions
                    if any(d == direction for d in next_cell.features if d in direction_offsets.keys()):
                        direction_valid = True
                        logging.debug(f"  Direction {direction} is explicitly supported by next cell")

                    # OR if we're following our current direction
                    elif direction == self.direction:
                        direction_valid = True
                        logging.debug(f"  Direction {direction} matches current vehicle direction")

                    # OR if we're at an intersection and the direction is reasonable
                    elif is_intersection:
                        direction_valid = True
                        logging.debug(f"  At intersection - direction {direction} is considered valid")

                    if has_capacity and direction_valid:
                        valid_adjacent_cells[direction] = (next_row, next_col, next_cell)
                        logging.debug(f"  Valid direction: {direction} -> ({next_row}, {next_col})")
                    else:
                        reasons = []
                        if not has_capacity:
                            reasons.append("no capacity")
                        if not direction_valid:
                            reasons.append("invalid direction")
                        logging.debug(f"  Invalid move to ({next_row}, {next_col}): {', '.join(reasons)}")
                else:
                    logging.debug(f"  Cell at ({next_row}, {next_col}) is not a road")

        is_intersection = len(valid_adjacent_cells) >= 2
        logging.debug(
            f"VehicleAgent-{self.vehicle_id} at ({row}, {col}) is at intersection: {is_intersection} with {len(valid_adjacent_cells)} valid cells")

        # Prioritize continuing in current direction
        if self.direction in valid_adjacent_cells:
            next_row, next_col, next_cell = valid_adjacent_cells[self.direction]
            directions[self.direction] = (next_row, next_col)
            logging.debug(f"VehicleAgent-{self.vehicle_id} continuing in direction {self.direction}")

        # Add other valid directions
        for direction, (next_row, next_col, next_cell) in valid_adjacent_cells.items():
            if direction not in directions:
                directions[direction] = (next_row, next_col)
                logging.debug(f"VehicleAgent-{self.vehicle_id} added alternative direction {direction}")

        # Emergency fallback for intersections with no valid directions
        if not directions and current_cell.cell_type == "road":
            logging.warning(
                f"VehicleAgent-{self.vehicle_id} at ({row}, {col}) found no valid directions - using fallback")

            # Consider any adjacent road cell as last resort
            for direction, (dr, dc) in direction_offsets.items():
                if direction != opposite_directions.get(self.direction):  # Still avoid U-turns
                    next_row, next_col = row + dr, col + dc
                    if 0 <= next_row < grid.rows and 0 <= next_col < grid.cols:
                        next_cell = grid.grid[next_row][next_col]
                        if next_cell.cell_type == "road":
                            vehicles_in_cell = len(VehicleAgent._all_vehicle_positions.get((next_row, next_col), []))
                            if vehicles_in_cell < next_cell.lanes:
                                directions[direction] = (next_row, next_col)
                                logging.debug(f"VehicleAgent-{self.vehicle_id} using fallback direction {direction}")
                                self.direction = direction  # Update vehicle direction to match movement
                                break

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

            # Get the next position in the current direction
            direction_offsets = {
                "northbound": (-1, 0),
                "southbound": (1, 0),
                "eastbound": (0, 1),
                "westbound": (0, -1)
            }
            dr, dc = direction_offsets.get(self.direction, (0, 0))
            next_row, next_col = self.row + dr, self.col + dc

            # Check if CURRENT position is at a traffic light
            if (self.row, self.col) in traffic_light_positions:
                # Find the index of this position in traffic light positions
                position_index = traffic_light_positions.index((self.row, self.col))

                # Form the traffic light ID using the position index
                traffic_light_id = f"traffic_light_{position_index + 1}"

                # Get the state of this traffic light
                traffic_light_state = traffic_light_states.get(traffic_light_id, "red")  # Default to red if unknown

                # Stop the vehicle if the light is red
                if traffic_light_state == "red":
                    can_move = False
                    print(f"{self.id}: Stopped at red traffic light at position ({self.row}, {self.col})")

            # ALSO check if the NEXT position has a traffic light
            elif (next_row, next_col) in traffic_light_positions:
                # Check if next position is within grid bounds
                if 0 <= next_row < self.grid.rows and 0 <= next_col < self.grid.cols:
                    # Find the index of next position in traffic light positions
                    position_index = traffic_light_positions.index((next_row, next_col))

                    # Form the traffic light ID using the position index
                    traffic_light_id = f"traffic_light_{position_index + 1}"

                    # Get the state of this traffic light
                    traffic_light_state = traffic_light_states.get(traffic_light_id, "red")  # Default to red if unknown

                    # Stop the vehicle if the next traffic light is red
                    if traffic_light_state == "red":
                        can_move = False
                        print(f"{self.id}: Stopping before red traffic light at position ({next_row}, {next_col})")

        # Check pedestrian crossings
        if can_move:
            # Get all pedestrian crossing positions in the grid
            crossing_positions = self._get_pedestrian_crossing_positions()

            # Get the next position in the current direction
            direction_offsets = {
                "northbound": (-1, 0),
                "southbound": (1, 0),
                "eastbound": (0, 1),
                "westbound": (0, -1)
            }
            dr, dc = direction_offsets.get(self.direction, (0, 0))
            next_row, next_col = self.row + dr, self.col + dc

            # Check if the NEXT position is a pedestrian crossing
            if (next_row, next_col) in crossing_positions:
                # Find the index of this position in the crossing positions
                position_index = crossing_positions.index((next_row, next_col))

                # Form the crossing ID using the position index
                crossing_id = f"crossing_{position_index + 1}"

                # Get the state of this crossing
                crossing_active = crossing_states.get(crossing_id, False)  # Default to inactive if unknown

                # Stop the vehicle if the crossing ahead is active
                if crossing_active:
                    can_move = False
                    print(f"{self.id}: Stopped at active pedestrian crossing ahead at position ({next_row}, {next_col})")

        # Move if possible
        if can_move and not getattr(self, 'exiting_delay', False):
            # First, remove current position from registry
            if (self.row, self.col) in VehicleAgent._all_vehicle_positions:
                if self.id in VehicleAgent._all_vehicle_positions[(self.row, self.col)]:
                    VehicleAgent._all_vehicle_positions[(self.row, self.col)].remove(self.id)
                    if not VehicleAgent._all_vehicle_positions[(self.row, self.col)]:
                        del VehicleAgent._all_vehicle_positions[(self.row, self.col)]

            # Check if can move forward in current direction
            forward_blocked = not self._can_move_forward(traffic_light_states, crossing_states)

            # Get next position (this may change direction if needed)
            old_row, old_col = self.row, self.col
            new_row, new_col = self._get_next_position()

            # Only actually move if new position is different
            if (new_row, new_col) != (old_row, old_col):
                self.row, self.col = new_row, new_col

                # Register new position
                if (self.row, self.col) not in VehicleAgent._all_vehicle_positions:
                    VehicleAgent._all_vehicle_positions[(self.row, self.col)] = []
                VehicleAgent._all_vehicle_positions[(self.row, self.col)].append(self.id)

            # Check for exiting
            exiting = self._is_exit_point(self.row, self.col)
            if exiting and can_move:
                # Immediately remove position from _all_vehicle_positions when reaching an exit
                if (self.row, self.col) in VehicleAgent._all_vehicle_positions and self.id in \
                        VehicleAgent._all_vehicle_positions[(self.row, self.col)]:
                    VehicleAgent._all_vehicle_positions[(self.row, self.col)].remove(self.id)
                    if not VehicleAgent._all_vehicle_positions[(self.row, self.col)]:
                        del VehicleAgent._all_vehicle_positions[(self.row, self.col)]
        else:
            # Not moving this step
            self.wait_time += 1
            exiting = False

        # Print status
        print(
            f"{self.id}: position=({self.row},{self.col}), wait_time={self.wait_time}, direction={self.direction}, is_parked={self.is_parked}, exiting_delay={getattr(self, 'exiting_delay', False)}, exiting={exiting}")