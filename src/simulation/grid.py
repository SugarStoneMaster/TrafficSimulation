from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class RoadCell:
    cell_type: str
    lanes: int
    features: List[str] = field(default_factory=list)
    capacity: int = 0
    parking_type: str = None
    parking_capacity: int = 0

    def short_repr(self) -> str:
        """
        Return a concise string that indicates:
         - Cell type (road/building/empty)
         - Arrows for direction
         - Lane count if > 1
         - Special features (traffic light, pedestrian crossing, etc.)
        """
        # 1) Handle empty cells
        if self.cell_type == "empty":
            return "."

        # 2) Handle building cells (not used in this example, but left here if needed)
        if self.cell_type == "building":
            if "aparcamiento" in self.features:
                return "[AP]"  # short for "aparcamiento"
            else:
                return "[B]"   # generic building

        # 3) Handle road cells
        direction_symbol = ""
        if "northbound" in self.features:
            direction_symbol = "↑"
        elif "southbound" in self.features:
            direction_symbol = "↓"
        elif "eastbound" in self.features:
            direction_symbol = "→"
        elif "westbound" in self.features:
            direction_symbol = "←"
        else:
            direction_symbol = "?"  # fallback if no direction

        # Show lane count if more than 1
        if self.lanes > 1:
            direction_symbol += f"({self.lanes})"

        # Append special features: T for traffic light, X for crossing, etc.
        suffix = ""
        if "traffic_light" in self.features:
            suffix += "T"
        if "pedestrian_crossing" in self.features:
            suffix += "X"

        if suffix:
            direction_symbol += f"[{suffix}]"

        return direction_symbol

class RoadGrid:
    """
    A grid that places roads, traffic lights, and pedestrian crossings
    using relative (fraction-based) positions, so that changing the
    total rows/cols preserves the general layout proportions.
    """

    def __init__(self, rows: int = 10, cols: int = 15):
        self.rows = rows
        self.cols = cols
        self.grid = self._build_grid()

    def _frac_row(self, fraction: float) -> int:
        """
        Convert a fraction (0.0..1.0) into an integer row index
        within [0, rows-1].
        """
        return max(0, min(self.rows - 1, int(round(fraction * (self.rows - 1)))))

    def _frac_col(self, fraction: float) -> int:
        """
        Convert a fraction (0.0..1.0) into an integer column index
        within [0, cols-1].
        """
        return max(0, min(self.cols - 1, int(round(fraction * (self.cols - 1)))))

    def _build_grid(self) -> List[List[RoadCell]]:
        """
        Builds the grid with roads placed at fractional positions:
          - Top road at ~10% of the rows
          - Bottom road at ~90% of the rows
          - Left road at column 0
          - Right road at column cols-1
          - Middle horizontal road at ~50% of rows
          - Two vertical roads at ~20% and ~80% of columns
          - Traffic lights at corners and selected intersections
          - Pedestrian crossings at fraction-based intervals
        """
        # 1) Initialize all cells as empty
        grid = [[RoadCell("empty", 0) for _ in range(self.cols)]
                for _ in range(self.rows)]

        # 2) Define key row/col positions by fraction
        top_r = self._frac_row(0.1)
        bottom_r = self._frac_row(0.9)
        mid_r = self._frac_row(0.5)

        left_c = 0
        right_c = self.cols - 1
        left_mid_c = self._frac_col(0.2)
        right_mid_c = self._frac_col(0.8)

        # 3) Place roads
        # 3a) Single-lane top road (westbound)
        for c in range(self.cols):
            grid[top_r][c] = RoadCell("road", 1, ["westbound"], 1)  # Capacity = lanes (1)

        # 3b) Single-lane bottom road (eastbound)
        for c in range(self.cols):
            grid[bottom_r][c] = RoadCell("road", 1, ["eastbound"], 1)  # Capacity = lanes (1)

        # 3c) Left column road (2-lane, southbound)
        for r in range(self.rows):
            grid[r][left_c] = RoadCell("road", 2, ["southbound"], 2)  # Capacity = lanes (2)

        # 3d) Right column road (2-lane, northbound)
        for r in range(self.rows):
            grid[r][right_c] = RoadCell("road", 2, ["northbound"], 2)  # Capacity = lanes (2)

        # 3e) Middle horizontal road (1-lane, eastbound)
        for c in range(self.cols - 2):
            grid[mid_r][c+1] = RoadCell("road", 1, ["eastbound"], 1)  # Capacity = lanes (1)

        # 3f) Two vertical roads (1-lane each)
        for r in range(self.rows):
            grid[r][left_mid_c] = RoadCell("road", 1, ["northbound"], 1)  # Capacity = lanes (1)
            grid[r][right_mid_c] = RoadCell("road", 1, ["southbound"], 1)  # Capacity = lanes (1)

        # 4) Traffic lights at corners
        grid[0][0].features.append("traffic_light")
        grid[0][right_c].features.append("traffic_light")
        grid[self.rows - 1][0].features.append("traffic_light")

        # Traffic lights at key intersections
        grid[self.rows - 1][right_mid_c].features.append("traffic_light")

        # 5) Pedestrian crossings at fraction-based intervals
        crossing_cols_fractions = [0.1, 0.3, 0.7, 0.9]
        for frac in crossing_cols_fractions:
            c = self._frac_col(frac)
            grid[top_r][c].features.append("pedestrian_crossing")

        # Another set of pedestrian crossings on the bottom road
        for frac in crossing_cols_fractions:
            c = self._frac_col(frac)
            grid[bottom_r][c].features.append("pedestrian_crossing")

        # Crossings on the middle horizontal road
        for frac in crossing_cols_fractions:
            c = self._frac_col(frac)
            grid[mid_r][c].features.append("pedestrian_crossing")

        # Crossings on the vertical two lanes roads
        r = self._frac_row(0.25)
        grid[r][left_c].features.append("pedestrian_crossing")

        r = self._frac_row(0.75)
        grid[r][right_c].features.append("pedestrian_crossing")

        def add_street_parking(grid):
            # Identify intersection points
            intersections = set()
            for r in [top_r, bottom_r, mid_r]:
                for c in [left_c, right_c, left_mid_c, right_mid_c]:
                    intersections.add((r, c))

            # Add street parking to horizontal roads, excluding intersections and special cells
            for r in [top_r, bottom_r, mid_r]:
                for c in range(0, self.cols):
                    cell = grid[r][c]
                    if (r, c) not in intersections and cell.cell_type == "road" and \
                            "traffic_light" not in cell.features and "pedestrian_crossing" not in cell.features:
                        lanes = cell.lanes
                        capacity = lanes
                        cell.features.append("parking")
                        cell.parking_type = "street"
                        cell.parking_capacity = capacity

            # Add street parking to vertical roads, excluding intersections and special cells
            for c in [left_c, right_c, left_mid_c, right_mid_c]:
                for r in range(0, self.rows):
                    cell = grid[r][c]
                    if (r, c) not in intersections and cell.cell_type == "road" and \
                            "traffic_light" not in cell.features and "pedestrian_crossing" not in cell.features:
                        lanes = cell.lanes
                        capacity = lanes
                        cell.features.append("parking")
                        cell.parking_type = "street"
                        cell.parking_capacity = capacity

            # Add a parking building near the center
            building_r = self._frac_row(0.45)
            building_c = self._frac_col(0.53)
            grid[building_r][building_c].cell_type = "building"
            grid[building_r][building_c].features.append("parking")
            grid[building_r][building_c].parking_type = "building"
            grid[building_r][building_c].parking_capacity = 10  # Large capacity for the building


        add_street_parking(grid)

        return grid



    def display(self) -> None:
        """
        Print the grid in an aligned manner. Each cell is shown via
        its short_repr() (e.g. ←[T] for a westbound road with a traffic light).
        """
        # Determine the maximum width needed for each column
        col_widths = [0] * self.cols
        for r in range(self.rows):
            for c in range(self.cols):
                cell_str = self.grid[r][c].short_repr()
                col_widths[c] = max(col_widths[c], len(cell_str))

        # Print each row with aligned columns
        for r in range(self.rows):
            row_str = " | ".join(
                self.grid[r][c].short_repr().ljust(col_widths[c])
                for c in range(self.cols)
            )
            print(row_str)


def initialize_grid(road_size: str) -> RoadGrid:
    """Initialize the road grid based on size."""
    if road_size == "small":
        grid = RoadGrid(rows=10, cols=15)
    elif road_size == "medium":
        grid = RoadGrid(rows=15, cols=20)
    elif road_size == "large":
        grid = RoadGrid(rows=20, cols=30)
    else:
        grid = RoadGrid(rows=10, cols=15)  # Default to small

    grid.display()
    return grid


def extract_special_positions(grid: RoadGrid) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """Extract traffic light and pedestrian crossing positions from the grid."""
    traffic_light_positions = []
    crossing_positions = []

    for r in range(grid.rows):
        for c in range(grid.cols):
            cell = grid.grid[r][c]
            if "traffic_light" in cell.features:
                traffic_light_positions.append((r, c))
            if "pedestrian_crossing" in cell.features:
                crossing_positions.append((r, c))

    return traffic_light_positions, crossing_positions

# --- Example Usage ---
if __name__ == "__main__":
    # Try different sizes to see how it scales
    grid_small = RoadGrid(rows=8, cols=12)
    print("=== SMALL GRID (8 x 12) ===")
    grid_small.display()

    print("\n\n=== LARGER GRID (12 x 20) ===")
    grid_large = RoadGrid(rows=12, cols=20)
    grid_large.display()

