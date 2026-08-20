from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://repurpose:repurpose@localhost:5432/repurpose"
    ncbi_email: str = ""
    ncbi_api_key: str = ""
    disease_focus_areas: str = "Alzheimer's disease,Type 2 diabetes"
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def focus_areas_list(self):
        return [a.strip() for a in self.disease_focus_areas.split(",") if a.strip()]

    @property
    def cors_origins_list(self):
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings():
    return Settings()
