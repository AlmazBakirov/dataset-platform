from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/dataset_platform"
    )
    storage_dir: str = "./storage"
    jwt_secret: str = "change_me"
    jwt_alg: str = "HS256"
    access_token_expire_minutes: int = 120

    class Config:
        env_file = ".env"


settings = Settings()
