import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_EMBEDDING_MODEL = "nomic-embed-text:latest"

DEFAULT_OLLAMA_CONNECT_TIMEOUT_SECONDS = 2.0
DEFAULT_OLLAMA_READ_TIMEOUT_SECONDS = 30.0
DEFAULT_OLLAMA_WRITE_TIMEOUT_SECONDS = 10.0
DEFAULT_OLLAMA_POOL_TIMEOUT_SECONDS = 2.0

MAX_TIMEOUT_SECONDS = 300.0

MAX_MEMORY_CONTENT_LENGTH = 10_000
MAX_MEMORY_TITLE_LENGTH = 200
MAX_MEMORY_SOURCE_LENGTH = 100
MAX_MEMORY_TAGS = 20
MAX_MEMORY_TAG_LENGTH = 50
MAX_MEMORY_METADATA_LENGTH = 4_096

MAX_VECTOR_DIMENSION = 4_096

DEFAULT_TOP_K = 10
MAX_TOP_K = 50

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

DEFAULT_RESEARCH_MEMORY_MIN_SCORE = 0.0
MIN_RESEARCH_MEMORY_MIN_SCORE = -1.0
MAX_RESEARCH_MEMORY_MIN_SCORE = 1.0


class ConfigurationError(ValueError):
    pass


def _validate_research_min_score(
    value: float | str | None,
    *,
    name: str = "RESEARCH_MEMORY_MIN_SCORE",
) -> float:
    if value is None:
        return DEFAULT_RESEARCH_MEMORY_MIN_SCORE

    if isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a number between -1.0 and 1.0")

    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            raise ConfigurationError(f"{name} must be a number between -1.0 and 1.0")
        try:
            score = float(raw)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                f"{name} must be a number between -1.0 and 1.0",
            ) from exc
    else:
        try:
            score = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                f"{name} must be a number between -1.0 and 1.0",
            ) from exc

    if not math.isfinite(score):
        raise ConfigurationError(f"{name} must be a number between -1.0 and 1.0")

    if score < MIN_RESEARCH_MEMORY_MIN_SCORE or score > MAX_RESEARCH_MEMORY_MIN_SCORE:
        raise ConfigurationError(f"{name} must be between -1.0 and 1.0")

    return float(score)


def _validate_timeout(
    value: float | str,
    *,
    name: str,
) -> float:
    if isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a positive number")

    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"{name} must be a positive number",
        ) from exc

    if not math.isfinite(timeout) or timeout <= 0.0:
        raise ConfigurationError(f"{name} must be a positive number")

    if timeout > MAX_TIMEOUT_SECONDS:
        raise ConfigurationError(
            f"{name} must not exceed {MAX_TIMEOUT_SECONDS:g} seconds",
        )

    return timeout


def _validate_base_url(value: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(
            "OLLAMA_BASE_URL must be an HTTP loopback URL",
        )

    raw = value.strip()

    if not raw:
        raise ConfigurationError(
            "OLLAMA_BASE_URL must be an HTTP loopback URL",
        )

    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError(
            "OLLAMA_BASE_URL must be an HTTP loopback URL",
        ) from exc

    if parsed.scheme != "http":
        raise ConfigurationError(
            "OLLAMA_BASE_URL must use http",
        )

    if parsed.username is not None or parsed.password is not None:
        raise ConfigurationError(
            "OLLAMA_BASE_URL must not contain credentials",
        )

    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ConfigurationError(
            "OLLAMA_BASE_URL must use 127.0.0.1 or localhost",
        )

    if parsed.path not in {"", "/"}:
        raise ConfigurationError(
            "OLLAMA_BASE_URL must not contain a path",
        )

    if "?" in raw or parsed.query:
        raise ConfigurationError(
            "OLLAMA_BASE_URL must not contain a query string",
        )

    if "#" in raw or parsed.fragment:
        raise ConfigurationError(
            "OLLAMA_BASE_URL must not contain a fragment",
        )

    if port is not None and not 1 <= port <= 65_535:
        raise ConfigurationError(
            "OLLAMA_BASE_URL port must be between 1 and 65535",
        )

    host = parsed.hostname

    if port is None:
        return f"http://{host}"

    return f"http://{host}:{port}"


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    embedding_model: str = DEFAULT_OLLAMA_EMBEDDING_MODEL
    connect_timeout: float = DEFAULT_OLLAMA_CONNECT_TIMEOUT_SECONDS
    read_timeout: float = DEFAULT_OLLAMA_READ_TIMEOUT_SECONDS
    write_timeout: float = DEFAULT_OLLAMA_WRITE_TIMEOUT_SECONDS
    pool_timeout: float = DEFAULT_OLLAMA_POOL_TIMEOUT_SECONDS
    max_vector_dimension: int = MAX_VECTOR_DIMENSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "base_url",
            _validate_base_url(self.base_url),
        )

        model = self.embedding_model

        if not isinstance(model, str) or not model.strip():
            raise ConfigurationError(
                "OLLAMA_EMBEDDING_MODEL must be a non-blank string",
            )

        object.__setattr__(self, "embedding_model", model.strip())

        object.__setattr__(
            self,
            "connect_timeout",
            _validate_timeout(
                self.connect_timeout,
                name="OLLAMA_CONNECT_TIMEOUT_SECONDS",
            ),
        )
        object.__setattr__(
            self,
            "read_timeout",
            _validate_timeout(
                self.read_timeout,
                name="OLLAMA_READ_TIMEOUT_SECONDS",
            ),
        )
        object.__setattr__(
            self,
            "write_timeout",
            _validate_timeout(
                self.write_timeout,
                name="OLLAMA_WRITE_TIMEOUT_SECONDS",
            ),
        )
        object.__setattr__(
            self,
            "pool_timeout",
            _validate_timeout(
                self.pool_timeout,
                name="OLLAMA_POOL_TIMEOUT_SECONDS",
            ),
        )

        dimension = self.max_vector_dimension

        if (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or not 1 <= dimension <= MAX_VECTOR_DIMENSION
        ):
            raise ConfigurationError(
                "max_vector_dimension must be between 1 and "
                f"{MAX_VECTOR_DIMENSION}",
            )


def load_config(
    environ: Mapping[str, str] | None = None,
) -> EmbeddingConfig:
    source = os.environ if environ is None else environ

    return EmbeddingConfig(
        base_url=source.get(
            "OLLAMA_BASE_URL",
            DEFAULT_OLLAMA_BASE_URL,
        ),
        embedding_model=source.get(
            "OLLAMA_EMBEDDING_MODEL",
            DEFAULT_OLLAMA_EMBEDDING_MODEL,
        ),
        connect_timeout=_validate_timeout(
            source.get(
                "OLLAMA_CONNECT_TIMEOUT_SECONDS",
                str(DEFAULT_OLLAMA_CONNECT_TIMEOUT_SECONDS),
            ),
            name="OLLAMA_CONNECT_TIMEOUT_SECONDS",
        ),
        read_timeout=_validate_timeout(
            source.get(
                "OLLAMA_READ_TIMEOUT_SECONDS",
                str(DEFAULT_OLLAMA_READ_TIMEOUT_SECONDS),
            ),
            name="OLLAMA_READ_TIMEOUT_SECONDS",
        ),
        write_timeout=_validate_timeout(
            source.get(
                "OLLAMA_WRITE_TIMEOUT_SECONDS",
                str(DEFAULT_OLLAMA_WRITE_TIMEOUT_SECONDS),
            ),
            name="OLLAMA_WRITE_TIMEOUT_SECONDS",
        ),
        pool_timeout=_validate_timeout(
            source.get(
                "OLLAMA_POOL_TIMEOUT_SECONDS",
                str(DEFAULT_OLLAMA_POOL_TIMEOUT_SECONDS),
            ),
            name="OLLAMA_POOL_TIMEOUT_SECONDS",
        ),
    )


def load_research_config(
    environ: Mapping[str, str] | None = None,
) -> float:
    source = os.environ if environ is None else environ
    value = source.get("RESEARCH_MEMORY_MIN_SCORE")
    return _validate_research_min_score(value)


DEFAULT_CONFIG = load_config()
RESEARCH_MEMORY_MIN_SCORE = load_research_config()

OLLAMA_BASE_URL = DEFAULT_CONFIG.base_url
OLLAMA_EMBEDDING_MODEL = DEFAULT_CONFIG.embedding_model
OLLAMA_EMBED_MODEL = OLLAMA_EMBEDDING_MODEL

OLLAMA_CONNECT_TIMEOUT_SECONDS = DEFAULT_CONFIG.connect_timeout
OLLAMA_READ_TIMEOUT_SECONDS = DEFAULT_CONFIG.read_timeout
OLLAMA_WRITE_TIMEOUT_SECONDS = DEFAULT_CONFIG.write_timeout
OLLAMA_POOL_TIMEOUT_SECONDS = DEFAULT_CONFIG.pool_timeout
