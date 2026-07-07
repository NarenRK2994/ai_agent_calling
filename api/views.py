"""Django views exposing workflow runs and live event streaming."""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from backend.application import create_application_context
from backend.run_manager import RunManager


context = create_application_context()
run_manager = RunManager(context)


def health(_request: HttpRequest) -> JsonResponse:
    """Return backend health status."""
    return JsonResponse({"status": "ok"})


@csrf_exempt
def create_run(request: HttpRequest) -> JsonResponse:
    """Start a workflow run for a user question."""
    if request.method == "OPTIONS":
        return JsonResponse({}, status=204)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST", "OPTIONS"])

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    question = str(payload.get("question", "")).strip()
    if not question:
        return JsonResponse({"detail": "Question is required."}, status=400)

    run = run_manager.create_run(question)
    return JsonResponse({"run_id": run.run_id, "status": run.status})


def get_run(_request: HttpRequest, run_id: str) -> JsonResponse:
    """Return the latest snapshot for a workflow run."""
    run = run_manager.get_run(run_id)
    if run is None:
        return JsonResponse({"detail": "Run not found."}, status=404)
    return JsonResponse(
        {
            "run_id": run.run_id,
            "status": run.status,
            "snapshot": run.snapshot_payload(),
        }
    )


def stream_run_events(_request: HttpRequest, run_id: str) -> StreamingHttpResponse | JsonResponse:
    """Stream run events to the React frontend using server-sent events."""
    run = run_manager.get_run(run_id)
    if run is None:
        return JsonResponse({"detail": "Run not found."}, status=404)

    response = StreamingHttpResponse(
        streaming_content=run_manager.event_stream(run_id),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
