from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

import httpx

from app.memory.config import DEFAULT_CONFIG, EmbeddingConfig
from app.memory.vectors import VectorError, validate_vector


class EmbeddingError(Exception):
    pass


class EmbeddingServiceUnavailableError(EmbeddingError):
    pass


class EmbeddingUpstreamError(EmbeddingError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(
            f"embedding request failed with status {status_code}",
        )


class InvalidEmbeddingResponseError(EmbeddingError):
    pass


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vector: tuple[float, ...]
    model: str
    dimension: int


def _normalize_model_name(value: str) -> str:
    normalized = value.strip().lower().split("@", 1)[0]
    return normalized.removesuffix(":latest")


class OllamaEmbeddingClient:
    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config or DEFAULT_CONFIG
        self._client = httpx.Client(
            timeout=httpx.Timeout(
                connect=self.config.connect_timeout,
                read=self.config.read_timeout,
                write=self.config.write_timeout,
                pool=self.config.pool_timeout,
            ),
            transport=transport,
            trust_env=False,
        )

    @property
    def timeout(self) -> httpx.Timeout:
        return self._client.timeout

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def embed(self, text: str) -> EmbeddingResult:
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                "embedding input must be a non-blank string",
            )

        try:
            response = self._client.post(
                f"{self.config.base_url}/api/embed",
                json={
                    "model": self.config.embedding_model,
                    "input": text,
                },
            )
        except httpx.TimeoutException as exc:
            raise EmbeddingServiceUnavailableError(
                "embedding service timed out",
            ) from exc
        except httpx.TransportError as exc:
            raise EmbeddingServiceUnavailableError(
                "embedding service unavailable",
            ) from exc

        if response.status_code == 404:
            raise EmbeddingServiceUnavailableError(
                "embedding model is unavailable",
            )

        if not response.is_success:
            raise EmbeddingUpstreamError(response.status_code)

        return self._parse_response(response)

    def _parse_response(
        self,
        response: httpx.Response,
    ) -> EmbeddingResult:
        try:
            payload = response.json()
        except ValueError as exc:
            raise InvalidEmbeddingResponseError(
                "embedding response was not valid JSON",
            ) from exc

        if not isinstance(payload, dict):
            raise InvalidEmbeddingResponseError(
                "embedding response must be a JSON object",
            )

        returned_model = payload.get("model")

        if returned_model is not None:
            if (
                not isinstance(returned_model, str)
                or not returned_model.strip()
            ):
                raise InvalidEmbeddingResponseError(
                    "embedding response model is invalid",
                )

            if _normalize_model_name(
                returned_model,
            ) != _normalize_model_name(
                self.config.embedding_model,
            ):
                raise InvalidEmbeddingResponseError(
                    "embedding response model does not match configured model",
                )

        embeddings = payload.get("embeddings")

        if not isinstance(embeddings, list) or len(embeddings) != 1:
            raise InvalidEmbeddingResponseError(
                "embedding response must contain exactly one vector",
            )

        raw_vector: Any = embeddings[0]

        if not isinstance(raw_vector, list):
            raise InvalidEmbeddingResponseError(
                "embedding vector must be a list",
            )

        try:
            vector = validate_vector(
                raw_vector,
                max_dimension=self.config.max_vector_dimension,
            )
        except VectorError as exc:
            raise InvalidEmbeddingResponseError(
                "embedding vector is invalid",
            ) from exc

        return EmbeddingResult(
            vector=vector,
            model=self.config.embedding_model,
            dimension=len(vector),
        )
