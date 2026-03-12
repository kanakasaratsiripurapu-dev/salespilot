"""Pydantic v2 request/response models."""

from pydantic import BaseModel


class ScoreRequest(BaseModel):
    account_ids: list[int]


class AccountScore(BaseModel):
    account_id: int
    priority_score: float


class ScoreResponse(BaseModel):
    scores: list[AccountScore]
    model_version: str


class RouteRequest(BaseModel):
    start_account_id: int
    account_ids: list[int]
    top_n: int = 5
    distance_mode: str = "haversine"


class RouteStop(BaseModel):
    stop_index: int
    account_id: int
    label: str


class RouteResponse(BaseModel):
    selected_accounts: list[AccountScore]
    route: list[RouteStop]
    total_distance_km: float
    distance_mode: str


class HealthResponse(BaseModel):
    status: str
