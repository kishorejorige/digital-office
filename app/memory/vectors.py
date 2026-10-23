import math
import struct
from collections.abc import Sequence
from numbers import Real

from app.memory.config import MAX_VECTOR_DIMENSION


class VectorError(ValueError):
    pass


class VectorDimensionError(VectorError):
    pass


class VectorDecodeError(VectorError):
    pass


def _validate_max_dimension(max_dimension: int) -> int:
    if (
        isinstance(max_dimension, bool)
        or not isinstance(max_dimension, int)
        or max_dimension <= 0
    ):
        raise VectorError(
            "maximum vector dimension must be a positive integer",
        )

    return max_dimension


def _validate_dimension(
    dimension: int,
    *,
    max_dimension: int,
) -> int:
    if isinstance(dimension, bool) or not isinstance(dimension, int):
        raise VectorError("vector dimension must be an integer")

    if dimension <= 0:
        raise VectorError("vector dimension must be positive")

    if dimension > max_dimension:
        raise VectorError("vector dimension exceeds maximum")

    return dimension


def _as_finite_float(value: Real) -> float:
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise VectorError("vector values must be finite") from exc

    if not math.isfinite(number):
        raise VectorError("vector values must be finite")

    try:
        struct.pack("<f", number)
    except (OverflowError, struct.error) as exc:
        raise VectorError("vector values must be finite") from exc

    return number


def validate_vector(
    values: Sequence[float],
    *,
    expected_dimension: int | None = None,
    max_dimension: int = MAX_VECTOR_DIMENSION,
) -> tuple[float, ...]:
    _validate_max_dimension(max_dimension)

    try:
        items = tuple(values)
    except TypeError as exc:
        raise VectorError(
            "vector must be a sequence of numbers",
        ) from exc

    dimension = len(items)

    if dimension == 0:
        raise VectorError("vector must not be empty")

    if dimension > max_dimension:
        raise VectorError("vector dimension exceeds maximum")

    if expected_dimension is not None:
        expected = _validate_dimension(
            expected_dimension,
            max_dimension=max_dimension,
        )

        if dimension != expected:
            raise VectorDimensionError(
                "vector dimension does not match expected dimension",
            )

    validated = []

    for value in items:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise VectorError("vector values must be numeric")

        validated.append(_as_finite_float(value))

    return tuple(validated)


def encode_vector(
    values: Sequence[float],
    *,
    expected_dimension: int | None = None,
    max_dimension: int = MAX_VECTOR_DIMENSION,
) -> bytes:
    validated = validate_vector(
        values,
        expected_dimension=expected_dimension,
        max_dimension=max_dimension,
    )

    try:
        return struct.pack(
            f"<{len(validated)}f",
            *validated,
        )
    except (OverflowError, struct.error) as exc:
        raise VectorError("unable to encode vector") from exc


def decode_vector(
    payload: bytes | bytearray | memoryview,
    dimension: int,
    *,
    max_dimension: int = MAX_VECTOR_DIMENSION,
) -> tuple[float, ...]:
    _validate_max_dimension(max_dimension)

    validated_dimension = _validate_dimension(
        dimension,
        max_dimension=max_dimension,
    )

    try:
        raw = bytes(payload)
    except (TypeError, ValueError) as exc:
        raise VectorDecodeError(
            "vector payload must be bytes",
        ) from exc

    expected_length = validated_dimension * 4

    if len(raw) != expected_length:
        raise VectorDecodeError(
            "vector payload length does not match dimension",
        )

    try:
        values = struct.unpack(
            f"<{validated_dimension}f",
            raw,
        )
    except struct.error as exc:
        raise VectorDecodeError(
            "unable to decode vector payload",
        ) from exc

    return validate_vector(
        values,
        expected_dimension=validated_dimension,
        max_dimension=max_dimension,
    )


def _finite_norm(values: tuple[float, ...]) -> float:
    norm = math.hypot(*values)

    if not math.isfinite(norm):
        raise VectorError("vector norm must be finite")

    return norm


def vector_norm(
    values: Sequence[float],
    *,
    max_dimension: int = MAX_VECTOR_DIMENSION,
) -> float:
    validated = validate_vector(
        values,
        max_dimension=max_dimension,
    )

    return _finite_norm(validated)


def cosine_similarity(
    left: Sequence[float],
    right: Sequence[float],
    *,
    max_dimension: int = MAX_VECTOR_DIMENSION,
) -> float:
    left_vector = validate_vector(
        left,
        max_dimension=max_dimension,
    )
    right_vector = validate_vector(
        right,
        max_dimension=max_dimension,
    )

    if len(left_vector) != len(right_vector):
        raise VectorDimensionError(
            "vectors must have the same dimension",
        )

    left_norm = _finite_norm(left_vector)
    right_norm = _finite_norm(right_vector)

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    left_normalized = tuple(
        value / left_norm
        for value in left_vector
    )
    right_normalized = tuple(
        value / right_norm
        for value in right_vector
    )

    score = math.fsum(
        left_value * right_value
        for left_value, right_value in zip(
            left_normalized,
            right_normalized,
            strict=True,
        )
    )

    return max(-1.0, min(1.0, score))
