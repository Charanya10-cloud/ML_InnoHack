from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import search, signals
from app.schemas import HealthResponse

settings = get_settings()

app = FastAPI(
    title="Drug Repurposing Signal API",
    description="Serves literature/trial search and scored repurposing signals to the frontend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(signals.router)


@app.on_event("startup")
def on_startup():
    # create_all is fine for a hackathon timeline; switch to Alembic migrations
    # (already in requirements.txt) if the schema needs to evolve post-demo.
    Base.metadata.create_all(bind=engine)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", env=settings.app_env)
