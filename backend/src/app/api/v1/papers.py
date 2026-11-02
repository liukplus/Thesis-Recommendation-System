"""Paper CRUD API endpoints.

Simple REST endpoints for managing papers in the database.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DBSessionDep
from app.core.exceptions import NotFoundError
from app.db.repositories.paper_repo import PaperRepository
from app.schemas.paper import (
    PaperCreate,
    PaperResponse,
    PaperSearchResponse,
    PaperUpdate,
)

router = APIRouter(prefix="/papers", tags=["papers"])

_paper_repo = PaperRepository()


@router.get("", response_model=PaperSearchResponse)
async def list_papers(
    db: DBSessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="Search query"),
) -> PaperSearchResponse:
    """List papers with optional search."""
    if search:
        papers = _paper_repo.search(db, search, skip=skip, limit=limit)
        total = len(papers)  # simplified — real impl would count
    else:
        papers = _paper_repo.list_all(db, skip=skip, limit=limit)
        total = _paper_repo.count(db)

    return PaperSearchResponse(
        papers=[PaperResponse.model_validate(p) for p in papers],
        total=total,
        query=search or "",
    )


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: str,
    db: DBSessionDep,
) -> PaperResponse:
    """Get a single paper by ID."""
    paper = _paper_repo.get_by_id(db, paper_id)
    if paper is None:
        raise NotFoundError(f"Paper not found: {paper_id}")
    return PaperResponse.model_validate(paper)


@router.post("", response_model=PaperResponse, status_code=201)
async def create_paper(
    paper_in: PaperCreate,
    db: DBSessionDep,
) -> PaperResponse:
    """Create a new paper."""
    paper = _paper_repo.create(db, **paper_in.model_dump())
    return PaperResponse.model_validate(paper)


@router.patch("/{paper_id}", response_model=PaperResponse)
async def update_paper(
    paper_id: str,
    paper_in: PaperUpdate,
    db: DBSessionDep,
) -> PaperResponse:
    """Update a paper."""
    paper = _paper_repo.get_by_id(db, paper_id)
    if paper is None:
        raise NotFoundError(f"Paper not found: {paper_id}")

    update_data = paper_in.model_dump(exclude_unset=True)
    paper = _paper_repo.update(db, paper, **update_data)
    return PaperResponse.model_validate(paper)


@router.delete("/{paper_id}")
async def delete_paper(
    paper_id: str,
    db: DBSessionDep,
) -> dict:
    """Delete a paper."""
    deleted = _paper_repo.delete_by_id(db, paper_id)
    if not deleted:
        raise NotFoundError(f"Paper not found: {paper_id}")
    return {"success": True, "message": "Paper deleted"}
