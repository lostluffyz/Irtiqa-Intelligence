from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_evidence_service
from app.schemas.evidence import EvidenceList, EvidenceRead, EvidenceSummary
from app.services.evidence_service import EvidenceService


router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/by-target/{target_type}/{target_id}", response_model=EvidenceList)
def list_evidence_by_target(
    target_type: str,
    target_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceList:
    records = service.get_target_evidence(target_type, target_id, limit=limit, offset=offset)
    return EvidenceList(
        items=[EvidenceRead.model_validate(r) for r in records],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/by-source/{source_type}/{source_id}", response_model=EvidenceList)
def list_evidence_by_source(
    source_type: str,
    source_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceList:
    records = service.get_source_targets(source_type, source_id, limit=limit, offset=offset)
    return EvidenceList(
        items=[EvidenceRead.model_validate(r) for r in records],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/by-company/{company_id}", response_model=EvidenceList)
def list_evidence_by_company(
    company_id: str,
    target_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceList:
    records = service.get_company_evidence(
        company_id,
        target_type=target_type,
        limit=limit,
        offset=offset,
    )
    return EvidenceList(
        items=[EvidenceRead.model_validate(r) for r in records],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/by-agent-run/{agent_run_id}", response_model=EvidenceList)
def list_evidence_by_agent_run(
    agent_run_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceList:
    records = service.get_agent_run_evidence(agent_run_id, limit=limit, offset=offset)
    return EvidenceList(
        items=[EvidenceRead.model_validate(r) for r in records],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/summary/{target_type}/{target_id}", response_model=EvidenceSummary)
def get_evidence_summary(
    target_type: str,
    target_id: str,
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceSummary:
    return service.get_evidence_summary(target_type, target_id)


@router.get("/{evidence_id}", response_model=EvidenceRead)
def get_evidence(
    evidence_id: str,
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceRead:
    evidence = service.get_required(evidence_id)
    return EvidenceRead.model_validate(evidence)
