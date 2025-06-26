from typing import List, Tuple

from shapely import Point, Polygon


def main(
        polygon_coords: List[Tuple[float, float]],
        coord: Tuple[float, float],
):
    polygon = Polygon(polygon_coords)
    point = Point(coord)
    return point.within(polygon)
