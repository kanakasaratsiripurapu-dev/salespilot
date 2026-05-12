from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str = "sqlite:///salespilot.db"
    DATA_DIR: str = "data/raw"
    MODEL_PATH: str = "app/ml/artifacts/model.joblib"
    DISTANCE_MODE: str = "haversine"
    GOOGLE_MAPS_API_KEY: str = ""
    MODEL_VERSION: str = "xgb_v1"

    @model_validator(mode="after")
    def fix_db_url(self):
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            self.DATABASE_URL = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and "+psycopg2" not in url:
            self.DATABASE_URL = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


settings = Settings()
