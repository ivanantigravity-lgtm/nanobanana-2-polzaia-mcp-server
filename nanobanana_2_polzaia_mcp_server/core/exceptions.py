"""Custom exceptions for the Nano Banana 2 Polza MCP Server."""

from dataclasses import dataclass
from typing import Any


class NanoBananaError(Exception):
    """Base exception class for all Nano Banana errors."""

    pass


class ConfigurationError(NanoBananaError):
    """Raised when there's a configuration issue."""

    pass


class ValidationError(NanoBananaError):
    """Raised when input validation fails."""

    pass


class GeminiAPIError(NanoBananaError):
    """Raised when upstream media API calls fail."""

    pass


class ImageProcessingError(NanoBananaError):
    """Raised when image processing fails."""

    pass


class FileOperationError(NanoBananaError):
    """Raised when file operations fail."""

    pass


class AuthenticationError(NanoBananaError):
    """Base exception for authentication errors."""

    pass


class ADCConfigurationError(AuthenticationError):
    """Raised when an unsupported legacy authentication mode is requested."""

    pass


@dataclass
class AsyncGenerationPending(NanoBananaError):
    """Raised when a generation is still running and should be polled, not restarted."""

    media_id: str
    status: str
    response: dict[str, Any]

    def __str__(self) -> str:
        return f"Generation {self.media_id} is still {self.status}"
