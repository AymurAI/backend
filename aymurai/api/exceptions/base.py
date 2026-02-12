class AymuraiAPIException(Exception):
    """Base exception for Aymurai API errors."""

    detail: str = "Aymurai API exception"

    def __init__(self, detail: str | None = None):
        super().__init__(detail or self.detail)


class UnsupportedFileType(AymuraiAPIException):
    detail = "Unsupported file type"


class ConfigurationError(AymuraiAPIException):
    detail = "Configuration error"


class UpstreamServiceError(AymuraiAPIException):
    detail = "Upstream service error"
