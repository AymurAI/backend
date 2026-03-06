from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from aymurai.api.exceptions.base import (
    AymuraiAPIException,
    ConfigurationError,
    UnsupportedFileType,
    UpstreamServiceError,
)


def register_exceptions_handlers(app: FastAPI) -> None:
    # --- General exception handlers -----------------------------------------
    @app.exception_handler(Exception)
    async def handle_general_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    @app.exception_handler(AymuraiAPIException)
    async def handle_general_api_exception(
        request: Request,
        exc: AymuraiAPIException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": exc.detail},
        )

    # --- basic handlers -----------------------------------------------------
    @app.exception_handler(UnsupportedFileType)
    async def handle_unsupported_file_type(
        request: Request,
        exc: UnsupportedFileType,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.detail},
        )

    @app.exception_handler(ConfigurationError)
    async def handle_configuration_error(
        request: Request,
        exc: ConfigurationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": exc.detail},
        )

    @app.exception_handler(UpstreamServiceError)
    async def handle_upstream_service_error(
        request: Request,
        exc: UpstreamServiceError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": exc.detail},
        )
