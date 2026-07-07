"""Backend helpers for resolving and invoking an existing workflow runner."""

from __future__ import annotations

import importlib
import inspect
from typing import Any, Callable


WorkflowRunner = Callable[..., Any]


def resolve_workflow_runner(import_path: str) -> WorkflowRunner:
    """Resolve a workflow runner from a module path like module:function."""
    if ":" not in import_path:
        raise ValueError("Runner path must look like 'module:function'.")
    module_name, function_name = import_path.split(":", maxsplit=1)
    module = importlib.import_module(module_name)
    runner = getattr(module, function_name, None)
    if runner is None or not callable(runner):
        raise ValueError(f"Runner '{function_name}' was not found or is not callable.")
    return runner


def invoke_workflow_runner(
    runner: WorkflowRunner,
    *,
    question: str,
    runtime: Any,
    context: Any,
) -> Any:
    """Invoke a resolved runner using the narrowest supported signature."""
    signature = inspect.signature(runner)
    kwargs: dict[str, Any] = {}
    if "question" in signature.parameters:
        kwargs["question"] = question
    if "runtime" in signature.parameters:
        kwargs["runtime"] = runtime
    if "context" in signature.parameters:
        kwargs["context"] = context

    if kwargs:
        return runner(**kwargs)
    return runner(question, runtime, context)
