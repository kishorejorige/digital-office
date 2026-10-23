import json

import httpx
import pytest

from app.memory.config import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_EMBEDDING_MODEL,
    ConfigurationError,
    EmbeddingConfig,
    load_config,
)
from app.memory.embeddings import (
    EmbeddingServiceUnavailableError,
    EmbeddingUpstreamError,
    InvalidEmbeddingResponseError,
    OllamaEmbeddingClient,
)

BASE_CONFIG = EmbeddingConfig(
    base_url="http://127.0.0.1:11434",
    embedding_model="nomic-embed-text:latest",
    connect_timeout=1.5,
    read_timeout=2.5,
    write_timeout=3.5,
    pool_timeout=4.5,
)


def _response(
    payload: object,
    *,
    status_code: int = 200,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(payload).encode("utf-8"),
    )


def _ok_response(
    vector: list[object],
    *,
    model: object = "nomic-embed-text",
) -> httpx.Response:
    return _response(
        {
            "model": model,
            "embeddings": [vector],
        },
    )


def _client(
    handler: object,
    config: EmbeddingConfig = BASE_CONFIG,
) -> OllamaEmbeddingClient:
    return OllamaEmbeddingClient(
        config,
        transport=httpx.MockTransport(handler),
    )


def test_load_config_uses_safe_defaults() -> None:
    config = load_config({})

    assert config.base_url == DEFAULT_OLLAMA_BASE_URL
    assert config.embedding_model == DEFAULT_OLLAMA_EMBEDDING_MODEL
    assert config.connect_timeout == 2.0
    assert config.read_timeout == 30.0
    assert config.write_timeout == 10.0
    assert config.pool_timeout == 2.0


def test_load_config_reads_environment_overrides() -> None:
    config = load_config(
        {
            "OLLAMA_BASE_URL": "http://localhost:11435/",
            "OLLAMA_EMBEDDING_MODEL": "custom-embed:latest",
            "OLLAMA_CONNECT_TIMEOUT_SECONDS": "1.25",
            "OLLAMA_READ_TIMEOUT_SECONDS": "3",
            "OLLAMA_WRITE_TIMEOUT_SECONDS": "4.5",
            "OLLAMA_POOL_TIMEOUT_SECONDS": "5",
        },
    )

    assert config.base_url == "http://localhost:11435"
    assert config.embedding_model == "custom-embed:latest"
    assert config.connect_timeout == 1.25
    assert config.read_timeout == 3.0
    assert config.write_timeout == 4.5
    assert config.pool_timeout == 5.0


def test_legacy_embed_model_name_is_preserved() -> None:
    from app.memory import config

    assert config.OLLAMA_EMBED_MODEL == config.OLLAMA_EMBEDDING_MODEL


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "not-a-url",
        "ftp://127.0.0.1:11434",
        "https://127.0.0.1:11434",
        "http://example.com:11434",
        "http://user:secret@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
        "http://127.0.0.1:11434?debug=1",
        "http://127.0.0.1:11434#fragment",
        "http://127.0.0.1:0",
        "http://127.0.0.1:99999",
    ],
)
def test_invalid_base_urls_are_rejected(base_url: str) -> None:
    with pytest.raises(ConfigurationError):
        EmbeddingConfig(base_url=base_url)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("OLLAMA_CONNECT_TIMEOUT_SECONDS", "0"),
        ("OLLAMA_READ_TIMEOUT_SECONDS", "-1"),
        ("OLLAMA_WRITE_TIMEOUT_SECONDS", "not-a-number"),
        ("OLLAMA_POOL_TIMEOUT_SECONDS", "301"),
        ("OLLAMA_CONNECT_TIMEOUT_SECONDS", "nan"),
        ("OLLAMA_READ_TIMEOUT_SECONDS", "inf"),
    ],
)
def test_invalid_environment_timeouts_are_rejected(
    name: str,
    value: str,
) -> None:
    with pytest.raises(ConfigurationError):
        load_config({name: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("connect_timeout", 0),
        ("connect_timeout", True),
        ("read_timeout", -1.0),
        ("write_timeout", 301.0),
        ("pool_timeout", float("inf")),
    ],
)
def test_invalid_direct_timeouts_are_rejected(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ConfigurationError):
        EmbeddingConfig(**{field: value})


@pytest.mark.parametrize(
    "dimension",
    [0, -1, 4_097, True, "3"],
)
def test_invalid_max_vector_dimensions_are_rejected(
    dimension: object,
) -> None:
    with pytest.raises(ConfigurationError):
        EmbeddingConfig(max_vector_dimension=dimension)


def test_blank_embedding_model_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        load_config({"OLLAMA_EMBEDDING_MODEL": "   "})


def test_load_config_does_not_create_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("HTTP client created during configuration")

    monkeypatch.setattr(httpx, "Client", fail)

    config = load_config({"OLLAMA_BASE_URL": "http://localhost:11434"})

    assert config.base_url == "http://localhost:11434"


def test_embed_posts_expected_payload_and_returns_valid_vector() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _ok_response([0.1, 0.2, 0.3])

    with _client(handler) as client:
        result = client.embed("remember this")

    assert result.vector == pytest.approx((0.1, 0.2, 0.3))
    assert result.dimension == 3
    assert result.model == "nomic-embed-text:latest"

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "http://127.0.0.1:11434/api/embed"
    assert json.loads(request.content) == {
        "model": "nomic-embed-text:latest",
        "input": "remember this",
    }


def test_client_uses_configured_timeouts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response([1.0])

    with _client(handler) as client:
        assert client.timeout.connect == 1.5
        assert client.timeout.read == 2.5
        assert client.timeout.write == 3.5
        assert client.timeout.pool == 4.5


def test_client_does_not_use_environment_proxy_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("http_proxy", "http://proxy.invalid:8080")
    monkeypatch.setenv("https_proxy", "http://proxy.invalid:8080")
    monkeypatch.setenv("all_proxy", "http://proxy.invalid:8080")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("NO_PROXY", "")

    client = OllamaEmbeddingClient(BASE_CONFIG)
    try:
        assert client._client.trust_env is False
        assert client._client._mounts == {}
    finally:
        client.close()


def test_embed_accepts_response_without_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response({"embeddings": [[1.0, 2.0]]})

    with _client(handler) as client:
        result = client.embed("x")

    assert result.vector == (1.0, 2.0)
    assert result.dimension == 2
    assert result.model == "nomic-embed-text:latest"


@pytest.mark.parametrize(
    "model",
    [
        "nomic-embed-text",
        "NOMIC-EMBED-TEXT:LATEST",
        "nomic-embed-text:latest@sha256:abc",
    ],
)
def test_embed_accepts_equivalent_model_names(model: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response([1.0], model=model)

    with _client(handler) as client:
        result = client.embed("x")

    assert result.model == "nomic-embed-text:latest"


@pytest.mark.parametrize(
    "model",
    [
        "other-model",
        123,
        "",
        "   ",
    ],
)
def test_embed_rejects_invalid_or_mismatched_model(
    model: object,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response([1.0], model=model)

    with (
        _client(handler) as client,
        pytest.raises(InvalidEmbeddingResponseError),
    ):
        client.embed("x")


@pytest.mark.parametrize(
    "status_code",
    [400, 401, 429, 500, 502],
)
def test_http_error_raises_safe_upstream_error(
    status_code: int,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=b"secret upstream body")

    with (
        _client(handler) as client,
        pytest.raises(EmbeddingUpstreamError) as exc_info,
    ):
        client.embed("x")

    assert exc_info.value.status_code == status_code
    assert "secret" not in str(exc_info.value)


def test_http_error_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    with (
        _client(handler) as client,
        pytest.raises(EmbeddingUpstreamError),
    ):
        client.embed("x")

    assert calls == 1


def test_not_found_raises_service_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"model not found")

    with (
        _client(handler) as client,
        pytest.raises(
            EmbeddingServiceUnavailableError,
            match="model is unavailable",
        ),
    ):
        client.embed("x")


def test_connection_error_raises_service_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with (
        _client(handler) as client,
        pytest.raises(
            EmbeddingServiceUnavailableError,
            match="service unavailable",
        ),
    ):
        client.embed("x")


def test_timeout_raises_service_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with (
        _client(handler) as client,
        pytest.raises(
            EmbeddingServiceUnavailableError,
            match="timed out",
        ),
    ):
        client.embed("x")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, content=b"[]"),
        _response({}),
        _response({"embeddings": []}),
        _response({"embeddings": [[0.1], [0.2]]}),
        _response({"embeddings": "not-a-list"}),
        _response({"embeddings": [123]}),
        _response({"embeddings": [[]]}),
    ],
)
def test_invalid_response_shape_is_rejected(
    response: httpx.Response,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    with (
        _client(handler) as client,
        pytest.raises(InvalidEmbeddingResponseError),
    ):
        client.embed("x")


@pytest.mark.parametrize(
    "vector",
    [
        [0.1, "bad"],
        [0.1, None],
        [0.1, True],
        [float("nan")],
        [float("inf")],
    ],
)
def test_invalid_vector_values_are_rejected(
    vector: list[object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response(vector)

    with (
        _client(handler) as client,
        pytest.raises(InvalidEmbeddingResponseError),
    ):
        client.embed("x")


def test_vector_exceeding_configured_dimension_is_rejected() -> None:
    config = EmbeddingConfig(max_vector_dimension=2)

    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response([0.1, 0.2, 0.3])

    with (
        _client(handler, config) as client,
        pytest.raises(InvalidEmbeddingResponseError),
    ):
        client.embed("x")


@pytest.mark.parametrize(
    "text",
    ["", "   ", None, 123],
)
def test_blank_or_non_string_input_is_rejected(text: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response([1.0])

    with (
        _client(handler) as client,
        pytest.raises(ValueError),
    ):
        client.embed(text)
