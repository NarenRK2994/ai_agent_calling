"""Centralized configuration management for the ERP AI Agent."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _get_optional_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return None


def _build_sid_dsn(host: str, port: int, sid: str) -> str:
    """Build an Oracle Net connect descriptor for SID-based connections."""
    return (
        "(DESCRIPTION="
        f"(ADDRESS=(PROTOCOL=TCP)(HOST={host})(PORT={port}))"
        f"(CONNECT_DATA=(SID={sid}))"
        ")"
    )


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    log_file: Path | None = None


@dataclass(frozen=True, slots=True)
class LLMConfig:
    model_name: str
    device: str
    context_window: int
    max_new_tokens: int
    temperature: float


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    model_name: str
    device: str
    collection_name: str
    top_k: int
    persist_directory: Path


@dataclass(frozen=True, slots=True)
class OracleConfig:
    username: str
    password: str
    dsn: str
    host: str | None
    port: int
    sid: str | None
    service_name: str | None
    min_connections: int
    max_connections: int
    increment: int
    timeout_seconds: int
    statement_timeout_ms: int
    retry_attempts: int
    retry_backoff_seconds: float
    read_only: bool
    thick_mode: bool
    client_lib_dir: Path | None
    config_dir: Path | None


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    debug: bool
    trace_sql: bool
    trace_prompts: bool
    trace_state: bool
    trace_timing: bool
    cache_ttl_seconds: int
    metrics_enabled: bool
    sql_validation_retries: int
    max_conversation_turns: int
    sql_history_limit: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    data_dir: Path
    logs_dir: Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    app_name: str
    environment: str
    debug: bool
    metadata_dir: Path
    prompt_dir: Path
    logging: LoggingConfig
    llm: LLMConfig
    embedding: EmbeddingConfig
    oracle: OracleConfig
    runtime: RuntimeConfig


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Load application configuration from environment variables."""
    oracle_username = _get_optional_env("ORACLE_USERNAME", "ORACLE_USER") or "system"
    oracle_password = _get_optional_env("ORACLE_PASSWORD") or "oracle"
    oracle_host = _get_optional_env("ORACLE_HOST")
    oracle_port = _get_int("ORACLE_PORT", 1521)
    oracle_sid = _get_optional_env("ORACLE_SID")
    oracle_service_name = _get_optional_env("ORACLE_SERVICE_NAME")
    oracle_dsn = _get_optional_env("ORACLE_DSN")
    if oracle_dsn is None:
        if oracle_host and oracle_service_name:
            oracle_dsn = f"{oracle_host}:{oracle_port}/{oracle_service_name}"
        elif oracle_host and oracle_sid:
            oracle_dsn = _build_sid_dsn(oracle_host, oracle_port, oracle_sid)
        else:
            oracle_dsn = "localhost/XEPDB1"

    return AppConfig(
        app_name=_get_env("ERP_AGENT_APP_NAME", "erp-ai-agent"),
        environment=_get_env("ERP_AGENT_ENV", "development"),
        debug=_get_bool("ERP_AGENT_DEBUG", False),
        metadata_dir=Path(_get_env("ERP_AGENT_METADATA_DIR", str(BASE_DIR / "data" / "metadata"))),
        prompt_dir=Path(_get_env("ERP_AGENT_PROMPT_DIR", str(BASE_DIR / "prompts"))),
        logging=LoggingConfig(
            level=_get_env("ERP_AGENT_LOG_LEVEL", "INFO"),
            log_file=Path(log_path) if (log_path := os.getenv("ERP_AGENT_LOG_FILE")) else None,
        ),
        llm=LLMConfig(
            model_name=_get_env("ERP_AGENT_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
            device=_get_env("ERP_AGENT_LLM_DEVICE", "auto"),
            context_window=_get_int("ERP_AGENT_LLM_CONTEXT_WINDOW", 8192),
            max_new_tokens=_get_int("ERP_AGENT_LLM_MAX_NEW_TOKENS", 512),
            temperature=float(_get_env("ERP_AGENT_LLM_TEMPERATURE", "0.1")),
        ),
        embedding=EmbeddingConfig(
            model_name=_get_env("ERP_AGENT_EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5"),
            device=_get_env("ERP_AGENT_EMBEDDING_DEVICE", "cuda"),
            collection_name=_get_env("ERP_AGENT_VECTOR_COLLECTION", "erp_metadata"),
            top_k=_get_int("ERP_AGENT_VECTOR_TOP_K", 5),
            persist_directory=Path(
                _get_env(
                    "ERP_AGENT_VECTOR_PERSIST_DIR",
                    str(BASE_DIR / "data" / "vector_store"),
                )
            ),
        ),
        oracle=OracleConfig(
            username=oracle_username,
            password=oracle_password,
            dsn=oracle_dsn,
            host=oracle_host,
            port=oracle_port,
            sid=oracle_sid,
            service_name=oracle_service_name,
            min_connections=_get_int("ORACLE_POOL_MIN", 1),
            max_connections=_get_int("ORACLE_POOL_MAX", 5),
            increment=_get_int("ORACLE_POOL_INCREMENT", 1),
            timeout_seconds=_get_int("ORACLE_TIMEOUT_SECONDS", 30),
            statement_timeout_ms=_get_int("ORACLE_STATEMENT_TIMEOUT_MS", 30000),
            retry_attempts=_get_int("ORACLE_RETRY_ATTEMPTS", 3),
            retry_backoff_seconds=float(_get_env("ORACLE_RETRY_BACKOFF_SECONDS", "1.0")),
            read_only=_get_bool("ORACLE_READ_ONLY", True),
            thick_mode=_get_bool("ORACLE_THICK_MODE", False),
            client_lib_dir=Path(client_lib_dir)
            if (client_lib_dir := os.getenv("ORACLE_CLIENT_LIB_DIR"))
            else None,
            config_dir=Path(config_dir)
            if (config_dir := os.getenv("ORACLE_CONFIG_DIR"))
            else None,
        ),
        runtime=RuntimeConfig(
            debug=_get_bool("DEBUG", _get_bool("ERP_AGENT_DEBUG", False)),
            trace_sql=_get_bool("TRACE_SQL", False),
            trace_prompts=_get_bool("TRACE_PROMPTS", False),
            trace_state=_get_bool("TRACE_STATE", False),
            trace_timing=_get_bool("TRACE_TIMING", False),
            cache_ttl_seconds=_get_int("ERP_AGENT_CACHE_TTL_SECONDS", 300),
            metrics_enabled=_get_bool("ERP_AGENT_METRICS_ENABLED", True),
            sql_validation_retries=_get_int("ERP_AGENT_SQL_VALIDATION_RETRIES", 2),
            max_conversation_turns=_get_int("ERP_AGENT_MAX_CONVERSATION_TURNS", 10),
            sql_history_limit=_get_int("ERP_AGENT_SQL_HISTORY_LIMIT", 100),
            rate_limit_requests=_get_int("ERP_AGENT_RATE_LIMIT_REQUESTS", 30),
            rate_limit_window_seconds=_get_int("ERP_AGENT_RATE_LIMIT_WINDOW_SECONDS", 60),
            data_dir=Path(_get_env("ERP_AGENT_DATA_DIR", str(BASE_DIR / "data"))),
            logs_dir=Path(_get_env("ERP_AGENT_LOGS_DIR", str(BASE_DIR / "logs"))),
        ),
    )
