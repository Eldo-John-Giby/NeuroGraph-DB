"""Read-only and explicit prediction API for the verified YelpChi baseline."""

from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.schemas import VerifiedBaselinePredictionRequest
from app.security import current_user
from app.services.yelpchi_baseline import get_verified_baseline


router = APIRouter(prefix="/api/v1/verified-baseline", tags=["verified-baseline"])


@router.get("/status")
def baseline_status(_: User = Depends(current_user)):
    return get_verified_baseline().status()


@router.post("/predict")
def baseline_predict(payload: VerifiedBaselinePredictionRequest, _: User = Depends(current_user)):
    baseline = get_verified_baseline()
    status = baseline.status()
    if not status["available"]:
        raise HTTPException(status_code=503, detail={"code": "verified_baseline_unavailable", "message": status["details"]})
    try:
        return baseline.predict(payload.review_ids)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail={"code": "unknown_yelpchi_node", "message": "Review IDs must belong to the verified YelpChi graph.", "unknown_review_ids": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "verified_baseline_runtime_failed", "message": str(exc)}) from exc


@router.get("/results")
def baseline_results(limit: int = 12, offset: int = 0, _: User = Depends(current_user)):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail={"code": "invalid_pagination", "message": "limit must be 1..100 and offset nonnegative."})
    baseline = get_verified_baseline()
    status = baseline.status()
    if not status["available"]:
        raise HTTPException(status_code=503, detail={"code": "verified_baseline_unavailable", "message": status["details"]})
    try:
        return baseline.top_results(limit, offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "verified_baseline_runtime_failed", "message": str(exc)}) from exc
