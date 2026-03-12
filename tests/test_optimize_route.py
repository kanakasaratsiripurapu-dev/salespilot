"""Tests for distance calculation, TSP solver, and synthetic geo — no DB required."""

import numpy as np
import pytest

from app.optimization.haversine import haversine_km, build_distance_matrix
from app.optimization.distance_provider import HaversineProvider
from app.optimization.ortools_tsp import solve_tsp
from app.data.synthetic_geo import assign_coordinates


class TestHaversine:
    def test_san_jose_to_san_francisco(self):
        """SJ to SF should be approximately 67 km."""
        d = haversine_km(37.3382, -121.8863, 37.7749, -122.4194)
        assert 60 <= d <= 80, f"Expected 60-80 km, got {d}"

    def test_los_angeles_to_san_diego(self):
        """LA to SD should be approximately 179 km."""
        d = haversine_km(34.0522, -118.2437, 32.7157, -117.1611)
        assert 160 <= d <= 200, f"Expected 160-200 km, got {d}"

    def test_distance_matrix_symmetric_and_zero_diagonal(self):
        """Distance matrix should be symmetric with zero diagonal."""
        points = [
            (37.3382, -121.8863),  # San Jose
            (37.7749, -122.4194),  # San Francisco
            (34.0522, -118.2437),  # Los Angeles
        ]
        matrix = build_distance_matrix(points)
        assert matrix.shape == (3, 3)
        # Zero diagonal
        for i in range(3):
            assert matrix[i][i] == 0.0
        # Symmetric
        for i in range(3):
            for j in range(3):
                assert abs(matrix[i][j] - matrix[j][i]) < 1e-6


class TestTSP:
    def test_route_starts_at_depot(self):
        """Route should always start at index 0 (depot)."""
        points = [
            (37.3382, -121.8863),  # San Jose (depot)
            (37.7749, -122.4194),  # San Francisco
            (34.0522, -118.2437),  # Los Angeles
            (32.7157, -117.1611),  # San Diego
        ]
        provider = HaversineProvider()
        result = solve_tsp(points, provider)
        assert result.ordered_indices[0] == 0

    def test_route_visits_all_nodes(self):
        """Route should visit all nodes exactly once."""
        points = [
            (37.3382, -121.8863),
            (37.7749, -122.4194),
            (34.0522, -118.2437),
            (32.7157, -117.1611),
        ]
        provider = HaversineProvider()
        result = solve_tsp(points, provider)
        assert sorted(result.ordered_indices) == list(range(len(points)))

    def test_total_distance_reasonable(self):
        """Total distance should match a reasonable round-trip calculation."""
        points = [
            (37.3382, -121.8863),  # San Jose
            (37.7749, -122.4194),  # San Francisco
        ]
        provider = HaversineProvider()
        result = solve_tsp(points, provider)
        # Round trip SJ-SF-SJ ≈ 134 km
        assert 120 <= result.total_distance_km <= 160

    def test_two_points_edge_case(self):
        """Edge case: 2 points should give a valid round trip."""
        points = [
            (37.3382, -121.8863),
            (34.0522, -118.2437),
        ]
        provider = HaversineProvider()
        result = solve_tsp(points, provider)
        assert len(result.ordered_indices) == 2
        assert result.total_distance_km > 0

    def test_one_point_edge_case(self):
        """Edge case: 1 point should return depot only with 0 distance."""
        points = [(37.3382, -121.8863)]
        provider = HaversineProvider()
        result = solve_tsp(points, provider)
        assert result.ordered_indices == [0]
        assert result.total_distance_km == 0.0

    def test_fifteen_points_performance(self):
        """Performance: 15 points should solve within the time limit."""
        rng = np.random.RandomState(42)
        points = [(rng.uniform(32, 39), rng.uniform(-122, -115)) for _ in range(15)]
        provider = HaversineProvider()
        result = solve_tsp(points, provider)
        assert len(result.ordered_indices) == 15
        assert result.total_distance_km > 0


class TestSyntheticGeo:
    def test_reproducibility(self):
        """Same inputs should always produce same coordinates."""
        lat1, lon1 = assign_coordinates("United States", 12345)
        lat2, lon2 = assign_coordinates("United States", 12345)
        assert lat1 == lat2
        assert lon1 == lon2

    def test_valid_coordinate_range(self):
        """Coordinates should be within valid ranges for the anchor cities."""
        for region in ["United States", "Kenya", "Philippines"]:
            for aid in [1, 100, 9999]:
                lat, lon = assign_coordinates(region, aid)
                assert 25 <= lat <= 45, f"Latitude {lat} out of range for {region}"
                assert -130 <= lon <= -100, f"Longitude {lon} out of range for {region}"

    def test_different_accounts_different_coords(self):
        """Different account_ids should produce different coordinates (noise)."""
        lat1, lon1 = assign_coordinates("United States", 1)
        lat2, lon2 = assign_coordinates("United States", 2)
        assert (lat1, lon1) != (lat2, lon2)
