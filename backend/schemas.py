"""Pydantic schemas for the ERP AI Agent backend API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Request body for starting a new workflow run."""

    question: str = Field(..., min_length=1)


class RunResponse(BaseModel):
    """Response returned after creating a workflow run."""

    run_id: str
    status: str


class RunSnapshotResponse(BaseModel):
    """Serializable run snapshot returned to the frontend."""

    run_id: str
    status: str
    snapshot: dict[str, Any]


class HealthResponse(BaseModel):
    """Simple health endpoint payload."""

    status: str
