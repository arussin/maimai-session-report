"""Domain exceptions with messages safe for command-line display."""

from __future__ import annotations


class MaimaiReportError(Exception):
    """Base class for expected application failures."""


class ConfigError(MaimaiReportError):
    """Configuration is absent, malformed, or unsafe."""


class MissingTokenError(ConfigError):
    """The environment does not contain the required Kamaitachi token."""


class APIError(MaimaiReportError):
    """A Kamaitachi HTTP request or response failed."""


class APIHTTPError(APIError):
    """Kamaitachi returned a non-successful HTTP response."""

    def __init__(self, method: str, path: str, status: int) -> None:
        self.method = method
        self.path = path
        self.status = status
        super().__init__(f"Kamaitachi returned HTTP {status} for {method} {path}")


class APITransportError(APIError):
    """Kamaitachi could not be reached within the configured limits."""


class APIResponseError(APIError):
    """Kamaitachi returned an unexpected response shape."""


class ImportError(MaimaiReportError):
    """An explicitly requested Kamaitachi import failed."""


class ImportFailedError(ImportError):
    """The import progress stream reported a terminal failure."""


class ImportStreamError(ImportError):
    """The import progress stream could not be read."""


class ImportStreamEndedError(ImportStreamError):
    """The import stream ended without a terminal completion event."""


class CalculationError(MaimaiReportError):
    """Score data could not be converted into a report model."""


class OutputError(MaimaiReportError):
    """A private local input or output file could not be handled safely."""


# Compatibility spelling for callers that prefer conventional title casing.
ApiError = APIError
