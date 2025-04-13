import pygame

from src.simulation.grid import RoadGrid

# PyGame visualization constants
CELL_SIZE = 40  # Size of each cell in pixels
PADDING = 5  # Padding inside cells
FPS = 5  # Frames per second

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (160, 32, 240)


class PyGameVisualizer:
    def __init__(self, grid: RoadGrid, with_parking: bool = False):
        self.grid = grid
        self.width = grid.cols * CELL_SIZE
        self.height = grid.rows * CELL_SIZE
        self.with_parking = with_parking  # Track if parking is enabled
        self.frame_counter = 0

        # Initialize PyGame
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Traffic Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)

        # Arrow polygons for directions
        self.arrows = {
            "northbound": [(CELL_SIZE // 2, PADDING),
                           (CELL_SIZE // 4, CELL_SIZE // 2),
                           (3 * CELL_SIZE // 4, CELL_SIZE // 2)],
            "southbound": [(CELL_SIZE // 2, CELL_SIZE - PADDING),
                           (CELL_SIZE // 4, CELL_SIZE // 2),
                           (3 * CELL_SIZE // 4, CELL_SIZE // 2)],
            "eastbound": [(CELL_SIZE - PADDING, CELL_SIZE // 2),
                          (CELL_SIZE // 2, CELL_SIZE // 4),
                          (CELL_SIZE // 2, 3 * CELL_SIZE // 4)],
            "westbound": [(PADDING, CELL_SIZE // 2),
                          (CELL_SIZE // 2, CELL_SIZE // 4),
                          (CELL_SIZE // 2, 3 * CELL_SIZE // 4)]
        }

    def draw_grid(self):
        self.screen.fill(WHITE)

        # Draw grid lines
        for r in range(self.grid.rows + 1):
            pygame.draw.line(self.screen, BLACK, (0, r * CELL_SIZE),
                             (self.width, r * CELL_SIZE))
        for c in range(self.grid.cols + 1):
            pygame.draw.line(self.screen, BLACK, (c * CELL_SIZE, 0),
                             (c * CELL_SIZE, self.height))

        # Draw cells
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                cell = self.grid.grid[r][c]
                rect = pygame.Rect(c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE)

                # Draw road cells
                if cell.cell_type == "road":
                    pygame.draw.rect(self.screen, GRAY, rect)

                    # Draw direction arrows
                    for feature in cell.features:
                        if feature in self.arrows:
                            # Get center of cell
                            center_x = c * CELL_SIZE + CELL_SIZE // 2
                            center_y = r * CELL_SIZE + CELL_SIZE // 2

                            # For two-lane roads, draw two arrows with offsets
                            if cell.lanes == 2:
                                # Set offsets based on direction
                                if feature in ["northbound", "southbound"]:
                                    # Horizontal offsets for vertical roads
                                    offsets = [(-CELL_SIZE // 6, 0), (CELL_SIZE // 6, 0)]
                                else:
                                    # Vertical offsets for horizontal roads
                                    offsets = [(0, -CELL_SIZE // 6), (0, CELL_SIZE // 6)]

                                # Draw first arrow (lane 1)
                                arrow1_vertices = [(c * CELL_SIZE + x + offsets[0][0],
                                                    r * CELL_SIZE + y + offsets[0][1])
                                                   for x, y in self.arrows[feature]]
                                pygame.draw.polygon(self.screen, BLACK, arrow1_vertices)

                                # Draw second arrow (lane 2)
                                arrow2_vertices = [(c * CELL_SIZE + x + offsets[1][0],
                                                    r * CELL_SIZE + y + offsets[1][1])
                                                   for x, y in self.arrows[feature]]
                                pygame.draw.polygon(self.screen, BLACK, arrow2_vertices)
                            else:
                                # Single lane - draw one arrow
                                arrow_vertices = [(c * CELL_SIZE + x, r * CELL_SIZE + y)
                                                  for x, y in self.arrows[feature]]
                                pygame.draw.polygon(self.screen, BLACK, arrow_vertices)

                # Draw parking building
                if cell.cell_type == "building" and "parking" in cell.features and self.with_parking:
                    # Draw parking building with a distinctive color
                    pygame.draw.rect(self.screen, (70, 130, 180), rect)  # Steel blue color

                    # Add a "P" label
                    font = pygame.font.SysFont(None, 36)
                    text = font.render("P", True, WHITE)
                    text_rect = text.get_rect(center=(c * CELL_SIZE + CELL_SIZE // 2,
                                                      r * CELL_SIZE + CELL_SIZE // 2))
                    self.screen.blit(text, text_rect)

                # Draw parking areas
                if "parking" in cell.features and self.with_parking:
                    if getattr(cell, 'parking_type', None) == "street":
                        lanes = cell.lanes
                        if "northbound" in cell.features:
                            # Northbound - draw on right side (east)
                            pygame.draw.rect(self.screen, BLUE,
                                             (c * CELL_SIZE + 4 * CELL_SIZE // 5, r * CELL_SIZE,
                                              CELL_SIZE // 5, CELL_SIZE))
                            # Draw second parking spot if 2+ lanes
                            if lanes >= 2:
                                pygame.draw.rect(self.screen, BLUE,
                                                 (c * CELL_SIZE, r * CELL_SIZE,
                                                  CELL_SIZE // 5, CELL_SIZE))

                        elif "southbound" in cell.features:
                            # Southbound - draw on right side (west)
                            pygame.draw.rect(self.screen, BLUE,
                                             (c * CELL_SIZE, r * CELL_SIZE,
                                              CELL_SIZE // 5, CELL_SIZE))
                            # Draw second parking spot if 2+ lanes
                            if lanes >= 2:
                                pygame.draw.rect(self.screen, BLUE,
                                                 (c * CELL_SIZE + 4 * CELL_SIZE // 5, r * CELL_SIZE,
                                                  CELL_SIZE // 5, CELL_SIZE))

                        elif "eastbound" in cell.features:
                            # Eastbound - draw on right side (south)
                            pygame.draw.rect(self.screen, BLUE,
                                             (c * CELL_SIZE, r * CELL_SIZE + 4 * CELL_SIZE // 5,
                                              CELL_SIZE, CELL_SIZE // 5))
                            # Draw second parking spot if 2+ lanes
                            if lanes >= 2:
                                pygame.draw.rect(self.screen, BLUE,
                                                 (c * CELL_SIZE, r * CELL_SIZE,
                                                  CELL_SIZE, CELL_SIZE // 5))

                        elif "westbound" in cell.features:
                            # Westbound - draw on right side (north)
                            pygame.draw.rect(self.screen, BLUE,
                                             (c * CELL_SIZE, r * CELL_SIZE,
                                              CELL_SIZE, CELL_SIZE // 5))
                            # Draw second parking spot if 2+ lanes
                            if lanes >= 2:
                                pygame.draw.rect(self.screen, BLUE,
                                                 (c * CELL_SIZE, r * CELL_SIZE + 4 * CELL_SIZE // 5,
                                                  CELL_SIZE, CELL_SIZE // 5))

    def draw_vehicles(self, vehicles):
        # Group vehicles by position
        vehicles_by_position = {}
        for data in vehicles:
            vid, row, col, direction, is_parked, in_parking_delay, exit_delay = data if len(data) >= 7 else (
                *data, False, False)
            pos = (row, col)
            if pos not in vehicles_by_position:
                vehicles_by_position[pos] = []
            vehicles_by_position[pos].append((vid, direction, is_parked, in_parking_delay, exit_delay))

        flash_state = (self.frame_counter // 1) % 2 == 0

        # Draw vehicles with offsets when multiple are in same cell
        for (row, col), vehicles_here in vehicles_by_position.items():
            cell = self.grid.grid[row][col]

            # For each vehicle at this position
            for idx, (vid, direction, is_parked, in_parking_delay, exit_delay) in enumerate(vehicles_here):
                vehicle_num = vid.split('_')[-1]  # Extract number from "vehicle_X"

                center_x = col * CELL_SIZE + CELL_SIZE // 2
                center_y = row * CELL_SIZE + CELL_SIZE // 2

                # Apply offset when multiple vehicles in same cell
                offset_x, offset_y = 0, 0
                if len(vehicles_here) > 1 and cell.lanes >= 2:
                    if direction in ["northbound", "southbound"]:
                        # Horizontal offset for vertical roads
                        if idx == 0:
                            offset_x = -CELL_SIZE // 4
                        else:
                            offset_x = CELL_SIZE // 4
                    else:
                        # Vertical offset for horizontal roads
                        if idx == 0:
                            offset_y = -CELL_SIZE // 4
                        else:
                            offset_y = CELL_SIZE // 4

                # Adjust size and position if parked
                width, height = CELL_SIZE // 5, CELL_SIZE // 3
                if is_parked:
                    width, height = CELL_SIZE // 6, CELL_SIZE // 4  # Smaller size
                    if direction in ["northbound"]:
                        # Northbound - move to the left side
                        offset_x = -CELL_SIZE // 3
                        offset_y = 0
                    elif direction in ["southbound"]:
                        # Southbound - move to the right side
                        offset_x = CELL_SIZE // 3
                        offset_y = 0
                    elif direction in ["eastbound"]:
                        # Eastbound - move to the top side
                        offset_x = 0
                        offset_y = -CELL_SIZE // 3
                    elif direction in ["westbound"]:
                        # Westbound - move to the bottom side
                        offset_x = 0
                        offset_y = CELL_SIZE // 3

                center_x += offset_x
                center_y += offset_y

                # Set rectangle size based on direction
                if direction in ["northbound", "southbound"]:
                    # Taller rectangle for vertical movement
                    width, height = CELL_SIZE // 5, CELL_SIZE // 3
                else:
                    # Wider rectangle for horizontal movement
                    width, height = CELL_SIZE // 3, CELL_SIZE // 5

                # Calculate rectangle position (centered)
                rect_x = center_x - width // 2
                rect_y = center_y - height // 2

                # Determine vehicle color
                if exit_delay or in_parking_delay:
                    # Solid red for both entering and exiting parking
                    vehicle_color = RED
                elif is_parked:
                    vehicle_color = GREEN  # Keep parked vehicles green
                else:
                    vehicle_color = PURPLE  # Regular vehicles remain purple

                # Draw vehicle as rectangle
                vehicle_rect = pygame.Rect(rect_x, rect_y, width, height)
                pygame.draw.rect(self.screen, vehicle_color, vehicle_rect)

                # Draw vehicle ID
                text = self.font.render(f"V{vehicle_num}", True, WHITE)
                text_rect = text.get_rect(center=(center_x, center_y))
                self.screen.blit(text, text_rect)


    def draw_traffic_lights(self, traffic_light_states):
        """
        Draw traffic lights with independent states.

        Args:
            traffic_light_states: Dictionary mapping agent_id to state ("red" or "green")
        """
        # Find all traffic light positions
        traffic_lights = []
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                if "traffic_light" in self.grid.grid[r][c].features:
                    traffic_lights.append((r, c))

        # Draw each traffic light with its own state
        for idx, (r, c) in enumerate(traffic_lights):
            agent_id = f"traffic_light_{idx + 1}"
            state = traffic_light_states.get(agent_id, "red")  # Default to red if unknown

            color = GREEN if state == "green" else RED
            pygame.draw.circle(
                self.screen, color,
                (c * CELL_SIZE + 3 * CELL_SIZE // 4, r * CELL_SIZE + CELL_SIZE // 4),
                CELL_SIZE // 4
            )

    def draw_crossings(self, crossing_states):
        """
        Draw pedestrian crossings with independent states.

        Args:
            crossing_states: Dictionary mapping agent_id to boolean (True for active)
        """
        # Find all crossing positions
        crossings = []
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                if "pedestrian_crossing" in self.grid.grid[r][c].features:
                    crossings.append((r, c))

        # Draw each crossing with its own state
        for idx, (r, c) in enumerate(crossings):
            agent_id = f"crossing_{idx + 1}"
            active = crossing_states.get(agent_id, False)  # Default to inactive if unknown

            crossing_color = YELLOW if active else WHITE
            rect = pygame.Rect(
                c * CELL_SIZE + CELL_SIZE // 4,
                r * CELL_SIZE + CELL_SIZE // 4,
                CELL_SIZE // 2,
                CELL_SIZE // 2
            )
            pygame.draw.rect(self.screen, crossing_color, rect)

    def update(self, vehicles, traffic_light_states, crossing_states):
        self.frame_counter += 1
        self.draw_grid()
        self.draw_traffic_lights(traffic_light_states)
        self.draw_crossings(crossing_states)
        self.draw_vehicles(vehicles)
        pygame.display.flip()
        self.clock.tick(FPS)

    def check_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False
        return True