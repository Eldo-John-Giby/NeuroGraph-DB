"""Read-only and explicit prediction API for the verified raw YelpChi multimodal benchmark."""

from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.schemas import VerifiedMultimodalPredictionRequest
from app.security import current_user
from app.services.yelpchi_multimodal import UnknownGraphNodeError, get_verified_multimodal

router = APIRouter(prefix="/api/v1/verified-multimodal", tags=["verified-multimodal"])


@router.get("/status")
def multimodal_status(_: User = Depends(current_user)):
    return get_verified_multimodal().status()


@router.post("/predict")
def multimodal_predict(payload: VerifiedMultimodalPredictionRequest, _: User = Depends(current_user)):
    service = get_verified_multimodal()
    status = service.status()
    if not status["available"]:
        raise HTTPException(
            status_code=503,
            detail={"code": "verified_multimodal_unavailable", "message": status["details"]},
        )
    try:
        return service.predict(payload.review_ids)
    except UnknownGraphNodeError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unknown_graph_node",
                "message": f"Review ID '{exc.missing_ids[0]}' is not part of verified graph snapshot.",
                "unknown_review_ids": exc.missing_ids,
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "verified_multimodal_runtime_failed", "message": str(exc)},
        ) from exc


@router.get("/results")
def multimodal_results(limit: int = 12, offset: int = 0, _: User = Depends(current_user)):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_pagination", "message": "limit must be 1..100 and offset nonnegative."},
        )
    service = get_verified_multimodal()
    status = service.status()
    if not status["available"]:
        raise HTTPException(
            status_code=503,
            detail={"code": "verified_multimodal_unavailable", "message": status["details"]},
        )
    try:
        return service.top_results(limit, offset)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "verified_multimodal_runtime_failed", "message": str(exc)},
        ) from exc
