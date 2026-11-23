import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger("smartcar.exceptions")


def _build_error_payload(
    status_code: int,
    error: str,
    detail,
    path: str,
) -> dict:
    return {
        "status_code": status_code,
        "error": error,
        "detail": detail,
        "path": path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Rejestruje globalne handlery wyjątków zapewniające spójny format odpowiedzi błędów JSON."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        error_titles = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            409: "Conflict",
            422: "Unprocessable Entity",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_payload(
                status_code=exc.status_code,
                error=error_titles.get(exc.status_code, "HTTP Error"),
                detail=exc.detail,
                path=request.url.path,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        formatted_errors = []
        for err in exc.errors():
            field_path = ".".join(str(loc) for loc in err.get("loc", []) if loc != "body")
            formatted_errors.append(
                {
                    "field": field_path or "body",
                    "message": err.get("msg", "Nieprawidłowa wartość pola"),
                    "type": err.get("type", "validation_error"),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_build_error_payload(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                error="Validation Error",
                detail=formatted_errors,
                path=request.url.path,
            ),
        )

    @app.exception_handler(IntegrityError)
    async def db_integrity_error_handler(request: Request, exc: IntegrityError):
        logger.warning("Database integrity error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_build_error_payload(
                status_code=status.HTTP_409_CONFLICT,
                error="Database Conflict",
                detail="Operacja narusza ograniczenia spójności bazy danych (np. duplikat unikalnego pola).",
                path=request.url.path,
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_general_error_handler(request: Request, exc: SQLAlchemyError):
        logger.error("Database error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_build_error_payload(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error="Database Unavailable",
                detail="Błąd komunikacji z bazą danych PostgreSQL. Spróbuj ponownie później.",
                path=request.url.path,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_error_payload(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error="Internal Server Error",
                detail="Wystąpił nieoczekiwany błąd wewnętrzny serwera.",
                path=request.url.path,
            ),
        )
