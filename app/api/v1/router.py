from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.agent_runs import router as agent_runs_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.companies import router as companies_router
from app.api.v1.endpoints.contacts import router as contacts_router
from app.api.v1.endpoints.evidence import router as evidence_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.intelligence import router as intelligence_router
from app.api.v1.endpoints.intent_signals import router as intent_signals_router
from app.api.v1.endpoints.intelligence_scores import router as intelligence_scores_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.outreach_messages import router as outreach_messages_router
from app.api.v1.endpoints.technologies import router as technologies_router
from app.api.v1.endpoints.websites import router as websites_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(health_router)
router.include_router(companies_router)
router.include_router(contacts_router)
router.include_router(evidence_router)
router.include_router(intelligence_router)
router.include_router(websites_router)
router.include_router(technologies_router)
router.include_router(intent_signals_router)
router.include_router(intelligence_scores_router)
router.include_router(outreach_messages_router)
router.include_router(agent_runs_router)
router.include_router(jobs_router)
