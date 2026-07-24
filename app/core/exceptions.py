import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

logger = logging.getLogger("app")

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        log_level = logging.WARNING if exc.status_code < 500 else logging.ERROR
        logger.log(
            log_level,
            f"HTTP exception: {exc.detail}",
            extra={"extra_info": {"status_code": exc.status_code, "path": request.url.path}}
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        error_messages = []
        for error in exc.errors():
            loc = " -> ".join(str(x) for x in error.get("loc", []))
            msg = error.get("msg", "invalid value")
            error_messages.append(f"{loc}: {msg}")
        
        message = "Validation error: " + "; ".join(error_messages)
        logger.warning(
            f"Validation error: {message}",
            extra={"extra_info": {"path": request.url.path}}
        )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": message,
                "status_code": 422
            }
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        error_messages = []
        for error in exc.errors():
            loc = " -> ".join(str(x) for x in error.get("loc", []))
            msg = error.get("msg", "invalid value")
            error_messages.append(f"{loc}: {msg}")
        
        message = "Validation error: " + "; ".join(error_messages)
        logger.warning(
            f"Pydantic validation error: {message}",
            extra={"extra_info": {"path": request.url.path}}
        )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": message,
                "status_code": 422
            }
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(
            f"Database error: {str(exc)}",
            exc_info=exc,
            extra={"extra_info": {"path": request.url.path}}
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Database error occurred",
                "status_code": 500
            }
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception: {str(exc)}",
            exc_info=exc,
            extra={"extra_info": {"path": request.url.path}}
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error",
                "status_code": 500
            }
        )
