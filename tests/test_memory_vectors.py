import math
import struct

import pytest

from app.memory.config import MAX_VECTOR_DIMENSION
from app.memory.vectors import (
    VectorDecodeError,
    VectorDimensionError,
    VectorError,
    cosine_similarity,
    decode_vector,
    encode_vector,
    validate_vector,
    vector_norm,
)


def test_vector_round_trip():
    values = [0.0, 1.0, -2.5, 1e-6]

    payload = encode_vector(values)

    assert len(payload) == len(values) * 4
    assert decode_vector(payload, len(values)) == pytest.approx(
        tuple(values),
    )


def test_encoding_uses_little_endian_float32():
    payload = encode_vector([1.0])

    assert payload == struct.pack("<f", 1.0)
    assert payload != struct.pack(">f", 1.0)


def test_vector_norm():
    assert vector_norm([3, 4]) == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], 1.0),
        ([1.0, 0.0], [0.0, 1.0], 0.0),
        ([1.0, 0.0], [-1.0, 0.0], -1.0),
    ],
    ids=["identical", "orthogonal", "opposite"],
)
def test_cosine_similarity(left, right, expected):
    assert cosine_similarity(left, right) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ([0.0, 0.0], [1.0, 0.0]),
        ([0.0, 0.0], [0.0, 0.0]),
    ],
    ids=["one-zero-vector", "both-zero-vectors"],
)
def test_cosine_similarity_with_zero_vectors(left, right):
    assert cosine_similarity(left, right) == 0.0


def test_cosine_similarity_rejects_dimension_mismatch():
    with pytest.raises(VectorDimensionError):
        cosine_similarity([1.0], [1.0, 2.0])


@pytest.mark.parametrize(
    "values",
    [
        [math.nan],
        [math.inf],
        [-math.inf],
    ],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_non_finite_values_are_rejected(values):
    with pytest.raises(VectorError):
        validate_vector(values)

    with pytest.raises(VectorError):
        encode_vector(values)


@pytest.mark.parametrize(
    "value",
    [
        10**100,
        10**400,
        1e39,
        1e300,
    ],
    ids=[
        "huge-integer",
        "integer-beyond-float",
        "float32-overflow",
        "huge-float",
    ],
)
def test_values_outside_float32_range_are_rejected(value):
    with pytest.raises(VectorError):
        validate_vector([value])

    with pytest.raises(VectorError):
        encode_vector([value])


def test_empty_vector_is_rejected():
    with pytest.raises(VectorError):
        encode_vector([])


@pytest.mark.parametrize(
    "value",
    [
        "1.0",
        None,
        True,
    ],
    ids=["string", "none", "boolean"],
)
def test_non_numeric_values_are_rejected(value):
    with pytest.raises(VectorError):
        encode_vector([value])


def test_expected_dimension_mismatch_is_rejected():
    with pytest.raises(VectorDimensionError):
        validate_vector([1.0, 2.0], expected_dimension=3)


def test_malformed_payload_length_is_rejected():
    payload = encode_vector([1.0, 2.0])

    with pytest.raises(VectorDecodeError):
        decode_vector(payload[:-1], 2)

    with pytest.raises(VectorDecodeError):
        decode_vector(payload, 3)


def test_non_bytes_payload_is_rejected():
    with pytest.raises(VectorDecodeError):
        decode_vector("not bytes", 1)


def test_non_finite_stored_values_are_rejected():
    payload = struct.pack("<f", math.nan)

    with pytest.raises(VectorError):
        decode_vector(payload, 1)


@pytest.mark.parametrize(
    "dimension",
    [0, -1, MAX_VECTOR_DIMENSION + 1],
    ids=["zero", "negative", "oversized"],
)
def test_invalid_decode_dimensions_are_rejected(dimension):
    with pytest.raises(VectorError):
        decode_vector(b"", dimension)


def test_oversized_vector_is_rejected():
    values = [0.0] * (MAX_VECTOR_DIMENSION + 1)

    with pytest.raises(VectorError):
        validate_vector(values)

    with pytest.raises(VectorError):
        encode_vector(values)
