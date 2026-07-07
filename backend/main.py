"""FastAPI backend exposing workflow runs and real-time observability streams."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.application import create_application_context
from backend.run_manager import RunManager
from backend.schemas import HealthResponse, RunRequest, RunResponse, RunSnapshotResponse


context = create_application_context()
run_manager = RunManager(context)

app = FastAPI(title="ERP AI Agent Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return backend health status."""
    return HealthResponse(status="ok")


@app.post("/api/runs", response_model=RunResponse)
def create_run(request: RunRequest) -> RunResponse:
    """Start a workflow run for a user question."""
    run = run_manager.create_run(request.question.strip())
    return RunResponse(run_id=run.run_id, status=run.status)


@app.get("/api/runs/{run_id}", response_model=RunSnapshotResponse)
def get_run(run_id: str) -> RunSnapshotResponse:
    """Return the latest snapshot for a workflow run."""
    run = run_manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return RunSnapshotResponse(
        run_id=run.run_id,
        status=run.status,
        snapshot=run.snapshot_payload(),
    )


@app.get("/api/runs/{run_id}/events")
def stream_run_events(run_id: str) -> StreamingResponse:
    """Stream run events to the React frontend using server-sent events."""
    run = run_manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return StreamingResponse(
        run_manager.event_stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
