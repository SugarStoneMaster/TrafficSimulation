import pygame

from grid import RoadGrid

# PyGame visualization constants
CELL_SIZE = 30  # Size of each cell in pixels
PADDING = 10  # Padding inside cells
FPS = 5  # Frames per second

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)


class PyGameVisualizer:
    def __init__(self, grid: RoadGrid):
        self.grid = grid
        self.width = grid.cols * CELL_SIZE
        self.height = grid.rows * CELL_SIZE

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



    def draw_vehicles(self, vehicles):
        for vid, row, col, direction in vehicles:
            vehicle_num = vid[-1]  # Extract number from "vehicle_X"

            # Draw vehicle
            center_x = col * CELL_SIZE + CELL_SIZE // 2
            center_y = row * CELL_SIZE + CELL_SIZE // 2
            pygame.draw.circle(self.screen, BLUE, (center_x, center_y), CELL_SIZE // 3)

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
