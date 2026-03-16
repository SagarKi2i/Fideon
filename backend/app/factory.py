import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.logger import setup_logging
from app.routes.admin import router as admin_router
from app.routes.chat import router as chat_router
from app.routes.device import router as device_router
from app.routes.federated_learning import router as federated_router
from app.routes.health import router as health_router
from app.routes.help_assistant import router as help_router
from app.routes.pod_activation import router as pod_activation_router
from app.routes.workflow_ai import router as workflow_router


def create_app() -> FastAPI:
    app = FastAPI(title="Fideon FastAPI Backend")
    _origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(help_router)
    app.include_router(workflow_router)
    app.include_router(device_router)
    app.include_router(federated_router)
    app.include_router(admin_router)
    app.include_router(pod_activation_router)

    # Configure structured logging and HTTP request audit logs
    setup_logging(app)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    return app
