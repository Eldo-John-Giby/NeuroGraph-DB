import uuid
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.batches import router as batch_router
from app.api.campaigns import router as campaign_router
from app.api.feedback import router as feedback_router
from app.api.routes import router
from app.api.verified_baseline import router as verified_baseline_router
from app.api.verified_multimodal import router as verified_multimodal_router
from app.config import get_settings
from app.db import make_engine
from app.models import ModelVersion, PreprocessingVersion

app = FastAPI(title="NeuroGraph-DB API", version="0.1.0")
logger = logging.getLogger("neurograph.api")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in get_settings().cors_origins.split(',') if origin.strip() and origin.strip() != '*'],
                   allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])
app.include_router(router)
app.include_router(batch_router)
app.include_router(campaign_router)
app.include_router(feedback_router)
app.include_router(verified_baseline_router)
app.include_router(verified_multimodal_router)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": {**detail, "request_id": getattr(request.state, "request_id", None), "details": {}}}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    fields = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Request fields are invalid.", "request_id": getattr(request.state, "request_id", None), "details": {"fields": fields}}})


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled API error request_id=%s method=%s path=%s",
                         request_id, request.method, request.url.path)
        response = JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "An unexpected error occurred.", "request_id": request_id, "details": {}}})
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unexpected_error(_: Request, __: Exception):
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "An unexpected error occurred.", "request_id": str(uuid.uuid4()), "details": {}}})


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready():
    checks = {"postgresql": "unavailable", "verified_model": "unavailable", "neo4j": "unconfigured"}
    engine = None
    try:
        engine = make_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["postgresql"] = "available"
        with Session(engine) as db:
            verified_real = db.scalar(
                select(func.count()).select_from(ModelVersion)
                .join(PreprocessingVersion,
                      PreprocessingVersion.preprocessing_version_id == ModelVersion.preprocessing_version_id)
                .where(ModelVersion.provenance == "real",
                       ModelVersion.lifecycle_status == "verified",
                       ModelVersion.checkpoint_uri.is_not(None),
                       ModelVersion.checkpoint_sha256.is_not(None),
                       ModelVersion.recommended_threshold.is_not(None),
                       PreprocessingVersion.lifecycle_status == "verified")
            ) or 0
            # A database registration is necessary, but not sufficient: this
            # process currently has no verified model runtime loader.
            if verified_real:
                checks["verified_model"] = "registered_runtime_unavailable"
    except Exception:
        pass
    finally:
        if engine is not None:
            engine.dispose()
    settings = get_settings()
    if settings.neo4j_uri:
        checks["neo4j"] = "configured_unverified"
    if checks["postgresql"] == "available" and checks["verified_model"] == "available":
        return {"status": "ready", "checks": checks}
    return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
