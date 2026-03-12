"""Distance provider abstraction for TSP solver."""

from abc import ABC, abstractmethod

import numpy as np

from app.optimization.haversine import build_distance_matrix


class DistanceProvider(ABC):
    @abstractmethod
    def matrix(self, points: list[tuple[float, float]]) -> np.ndarray:
        """Return an NxN distance matrix for the given points."""
        ...


class HaversineProvider(DistanceProvider):
    def matrix(self, points: list[tuple[float, float]]) -> np.ndarray:
        return build_distance_matrix(points)


class GoogleDistanceMatrixProvider(DistanceProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def matrix(self, points: list[tuple[float, float]]) -> np.ndarray:
        raise NotImplementedError("Google Distance Matrix API integration not yet implemented")


def get_provider(mode: str = "haversine", api_key: str = "") -> DistanceProvider:
    """Factory function to get a distance provider."""
    if mode == "haversine":
        return HaversineProvider()
    elif mode == "google":
        return GoogleDistanceMatrixProvider(api_key)
    else:
        raise ValueError(f"Unknown distance mode: {mode}")
