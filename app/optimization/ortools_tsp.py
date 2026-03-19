"""OR-Tools TSP solver for route optimization.

Falls back to a nearest-neighbour heuristic when OR-Tools cannot be
imported (e.g. protobuf/pyarrow binary conflict on Python 3.13).
"""

import logging
from dataclasses import dataclass

from app.optimization.distance_provider import DistanceProvider

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    ordered_indices: list[int]
    total_distance_km: float


def _nearest_neighbour(dist_matrix, n: int) -> tuple[list[int], float]:
    """Simple nearest-neighbour TSP heuristic starting from node 0."""
    visited = {0}
    order = [0]
    total = 0.0
    current = 0
    for _ in range(n - 1):
        best_dist = float("inf")
        best_node = -1
        for j in range(n):
            if j not in visited and dist_matrix[current][j] < best_dist:
                best_dist = dist_matrix[current][j]
                best_node = j
        if best_node == -1:
            break
        visited.add(best_node)
        order.append(best_node)
        total += best_dist
        current = best_node
    # Return to depot
    total += dist_matrix[current][0]
    return order, round(total, 1)


def solve_tsp(points: list[tuple[float, float]], distance_provider: DistanceProvider) -> RouteResult:
    """Solve TSP for a set of points. points[0] is always the depot.

    Returns a RouteResult with ordered indices forming a closed tour
    (starts and ends at depot).
    """
    n = len(points)

    if n <= 1:
        return RouteResult(ordered_indices=[0], total_distance_km=0.0)

    if n == 2:
        dist_matrix = distance_provider.matrix(points)
        round_trip = dist_matrix[0][1] + dist_matrix[1][0]
        return RouteResult(ordered_indices=[0, 1], total_distance_km=round_trip)

    # Build distance matrix
    dist_matrix_km = distance_provider.matrix(points)

    # Try OR-Tools in a subprocess (segfaults on Python 3.13 due to protobuf/pyarrow conflict)
    result = _try_ortools_subprocess(dist_matrix_km, n)
    if result is not None:
        return result

    # Fallback: nearest-neighbour heuristic
    logger.info("Using nearest-neighbour heuristic for TSP")
    order, total = _nearest_neighbour(dist_matrix_km, n)
    return RouteResult(ordered_indices=order, total_distance_km=total)


def _try_ortools_subprocess(dist_matrix_km, n: int) -> RouteResult | None:
    """Run OR-Tools TSP solver in an isolated subprocess to avoid segfault."""
    import json
    import subprocess
    import sys

    # Serialise the distance matrix as nested list
    matrix_list = dist_matrix_km.tolist()

    script = '''
import json, sys
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

data = json.loads(sys.stdin.read())
matrix = data["matrix"]
n = data["n"]
scale = 1000
int_matrix = [[int(matrix[i][j] * scale) for j in range(n)] for i in range(n)]

manager = pywrapcp.RoutingIndexManager(n, 1, 0)
routing = pywrapcp.RoutingModel(manager)

def distance_callback(from_index, to_index):
    return int_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

transit_cb = routing.RegisterTransitCallback(distance_callback)
routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

params = pywrapcp.DefaultRoutingSearchParameters()
params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
params.time_limit.seconds = 5

solution = routing.SolveWithParameters(params)
if solution is None:
    print(json.dumps(None))
else:
    order = []
    idx = routing.Start(0)
    total = 0
    while not routing.IsEnd(idx):
        order.append(manager.IndexToNode(idx))
        nxt = solution.Value(routing.NextVar(idx))
        total += routing.GetArcCostForVehicle(idx, nxt, 0)
        idx = nxt
    print(json.dumps({"order": order, "total_km": round(total / scale, 1)}))
'''

    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            input=json.dumps({"matrix": matrix_list, "n": n}),
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            logger.warning("OR-Tools subprocess failed (rc=%d): %s", proc.returncode, proc.stderr[:200])
            return None
        result = json.loads(proc.stdout.strip())
        if result is None:
            return None
        return RouteResult(ordered_indices=result["order"], total_distance_km=result["total_km"])
    except Exception as e:
        logger.warning("OR-Tools subprocess error: %s", e)
        return None
