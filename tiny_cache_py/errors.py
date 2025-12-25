class CacheError(Exception):
    """Base exception for cache operations"""


class CacheConnectionError(CacheError):
    """Raised when cache service is unavailable"""


class CacheValidationError(CacheError):
    """Raised when input validation fails"""


class CacheTimeoutError(CacheError):
    """Raised when request times out"""


class CacheInvalidArgumentError(CacheError):
    """Raised when invalid arguments are provided"""

