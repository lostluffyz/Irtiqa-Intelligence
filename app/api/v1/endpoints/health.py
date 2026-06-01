from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings
from app.core.config import Settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(settings: Settings = Depends(get_app_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": "irtiqa-intelligence",
        "database": "sqlite" if settings.database.is_sqlite else "external",
    }
