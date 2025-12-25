from typing import Any

from .errors import CacheValidationError

MAX_KEY_LENGTH = 250


def validate_key(key: str) -> None:
    if not isinstance(key, str):
        raise CacheValidationError("Key must be a string")
    if not key:
        raise CacheValidationError("Key cannot be empty")
    if len(key) > MAX_KEY_LENGTH:
        raise CacheValidationError(f"Key too long (max {MAX_KEY_LENGTH} characters)")


def coerce_text_value(value: Any) -> str:
    if value is None:
        raise CacheValidationError("Value cannot be None")

    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CacheValidationError("Bytes value must be valid UTF-8") from exc

    try:
        return str(value)
    except Exception as exc:
        raise CacheValidationError(f"Cannot convert value to string: {exc}") from exc


def normalize_bytes_value(value: Any) -> bytes:
    if value is None:
        raise CacheValidationError("Value cannot be None")
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise CacheValidationError("Value must be bytes")
    return bytes(value)

