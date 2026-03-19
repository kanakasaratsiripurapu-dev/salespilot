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


class MetaResponse(BaseModel):
    service: str
    version: str
    model_version: str


class AccountCreate(BaseModel):
    account_name: str
    industry: str = ""
    company_size: int = 0
    revenue: float = 0.0
    region: str = ""
    latitude: float | None = None
    longitude: float | None = None
    deal_value: float = 0.0
    sales_stage: str = "Prospecting"


class AccountResponse(BaseModel):
    account_id: int
    account_name: str
    industry: str | None = None
    company_size: int | None = None
    revenue: float | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class AccountListResponse(BaseModel):
    accounts: list[AccountResponse]
