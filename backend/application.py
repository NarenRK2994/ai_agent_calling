"""Backend application bootstrap and shared runtime wiring."""

from __future__ import annotations

from dataclasses import dataclass

from config import AppConfig, get_config
from utils.cache import TTLCache
from utils.history import ConversationMemoryStore, ExecutionLogStore, SQLHistoryStore
from utils.logging_config import configure_logging, get_logger
from utils.metrics import MetricsCollector
from utils.observability import ObservabilityManager, TraceOptions
from utils.prompt_versioning import PromptVersionManager
from utils.rate_limit import SlidingWindowRateLimiter
from utils.runtime import RuntimeServices


@dataclass(slots=True)
class ApplicationContext:
    """Top-level backend application context with shared configuration and services."""

    config: AppConfig
    runtime: RuntimeServices


def bootstrap() -> AppConfig:
    """Initialize backend configuration and logging."""
    config = get_config()
    configure_logging(config.logging)
    logger = get_logger(__name__)
    logger.info("ERP AI Agent backend bootstrap completed")
    return config


def build_runtime_services(config: AppConfig) -> RuntimeServices:
    """Create backend runtime services from application configuration."""
    return RuntimeServices(
        cache=TTLCache(config.runtime.cache_ttl_seconds),
        conversation_memory=ConversationMemoryStore(config.runtime.max_conversation_turns),
        sql_history=SQLHistoryStore(config.runtime.sql_history_limit),
        execution_logs=ExecutionLogStore(config.runtime.logs_dir / "execution.jsonl"),
        metrics=MetricsCollector(),
        prompt_versions=PromptVersionManager(config.prompt_dir),
        rate_limiter=SlidingWindowRateLimiter(
            config.runtime.rate_limit_requests,
            config.runtime.rate_limit_window_seconds,
        ),
        observability=ObservabilityManager(TraceOptions.from_config(config.runtime)),
    )


def create_application_context() -> ApplicationContext:
    """Build the backend application context used by API and workflow wiring."""
    config = bootstrap()
    return ApplicationContext(config=config, runtime=build_runtime_services(config))


def main() -> None:
    """Run the backend bootstrap sequence."""
    create_application_context()


if __name__ == "__main__":
    main()
