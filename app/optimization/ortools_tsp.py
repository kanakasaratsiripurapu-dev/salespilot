"""OR-Tools TSP solver for route optimization."""

from dataclasses import dataclass

from app.optimization.distance_provider import DistanceProvider


@dataclass
class RouteResult:
    ordered_indices: list[int]
    total_distance_km: float


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

    # Build integer distance matrix (km * 1000 for precision)
    dist_matrix_km = distance_provider.matrix(points)
    scale = 1000
    int_matrix = (dist_matrix_km * scale).astype(int).tolist()

    # OR-Tools setup (lazy import to avoid protobuf descriptor conflict with pandas/pyarrow)
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    manager = pywrapcp.RoutingIndexManager(n, 1, 0)  # 1 vehicle, depot=0
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Search parameters
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = 5

    solution = routing.SolveWithParameters(search_params)

    if solution is None:
        # Fallback: return points in original order
        total = sum(dist_matrix_km[i][(i + 1) % n] for i in range(n))
        return RouteResult(ordered_indices=list(range(n)), total_distance_km=total)

    # Extract route
    ordered_indices = []
    index = routing.Start(0)
    total_distance_scaled = 0

    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        ordered_indices.append(node)
        next_index = solution.Value(routing.NextVar(index))
        total_distance_scaled += routing.GetArcCostForVehicle(index, next_index, 0)
        index = next_index

    total_distance_km = total_distance_scaled / scale

    return RouteResult(ordered_indices=ordered_indices, total_distance_km=round(total_distance_km, 1))
