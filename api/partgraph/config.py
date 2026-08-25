from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = getenv(
        "PARTGRAPH_DATABASE_URL",
        "postgresql+psycopg://partgraph:partgraph@localhost:5432/partgraph",
    )
    web_origin: str = getenv("PARTGRAPH_WEB_ORIGIN", "http://localhost:5173")


settings = Settings()
