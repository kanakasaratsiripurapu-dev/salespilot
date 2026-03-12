from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str = "postgresql://salespilot:salespilot@localhost:5432/salespilot"
    DATA_DIR: str = "data/raw"
    MODEL_PATH: str = "app/ml/artifacts/model.joblib"
    DISTANCE_MODE: str = "haversine"
    GOOGLE_MAPS_API_KEY: str = ""
    MODEL_VERSION: str = "xgb_v1"


settings = Settings()
