from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.db.session import engine
from app.routers.dashboard import router as dashboard_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    engine.dispose()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(dashboard_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
