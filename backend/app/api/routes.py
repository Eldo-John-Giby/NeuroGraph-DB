import secrets
import uuid
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import func, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import (AuditLog, BatchAnalysis, BatchAnalysisRow, FraudPrediction, GraphSnapshot, GraphSnapshotReview,
                        GraphSyncJob, InferenceRun, ModelVersion, PreprocessingVersion,
                        Product, Reviewer, Review, Role, SessionToken, User)
from app.schemas import GraphSyncCreate, InferenceRequest, LoginRequest, ReviewCreate, UserCreate
from app.security import (as_utc, current_user, digest, hash_password, issue_session,
                          require_roles, verify_password)
from app.services.yelpchi_baseline import get_verified_baseline
from app.services.yelpchi_multimodal import get_verified_multimodal

router = APIRouter(prefix="/api/v1")


def visible_review(db: Session, user: User):
    role = db.get(Role, user.role_id)
    if role and role.role_key == "ADMIN":
        return true()
    reused = select(BatchAnalysisRow.review_id).join(
        BatchAnalysis, BatchAnalysis.batch_analysis_id == BatchAnalysisRow.batch_analysis_id
    ).where(BatchAnalysis.requested_by_user_id == user.user_id, BatchAnalysisRow.review_id.is_not(None))
    return or_(Review.submitted_by_user_id.is_(None), Review.source_system == "synthetic_demo",
               Review.submitted_by_user_id == user.user_id, Review.review_id.in_(reused))


def user_payload(db: Session, user: User) -> dict:
    role = db.get(Role, user.role_id)
    return {"user_id": user.user_id, "email": user.email, "username": user.username,
            "role_key": role.role_key if role else None, "is_active": user.is_active}


def validate_pagination(limit: int, offset: int) -> None:
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail={"code": "invalid_pagination", "message": "limit must be 1..100 and offset nonnegative."})


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=get_settings().cookie_secure,
                        samesite="strict", path="/api/v1/auth", max_age=60 * 60 * 24 * get_settings().refresh_token_days)


@router.post("/auth/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email_normalized == str(payload.email).strip().lower()))
    if user is None or not user.is_active or not verify_password(user.password_hash, payload.password):
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Email or password is incorrect."})
    try:
        _, access, refresh = issue_session(db, user)
        user.last_login_at = datetime.now(timezone.utc)
        db.add(AuditLog(actor_user_id=user.user_id, action="auth.login", entity_type="user", entity_key=str(user.user_id)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    set_refresh_cookie(response, refresh)
    return {"access_token": access, "token_type": "bearer", "user": user_payload(db, user)}


@router.post("/auth/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_value = request.cookies.get("refresh_token")
    if not refresh_value:
        raise HTTPException(status_code=401, detail={"code": "refresh_required", "message": "Refresh credential is missing."})
    prior = db.scalar(select(SessionToken).where(SessionToken.refresh_token_hash == digest(refresh_value)).with_for_update())
    now = datetime.now(timezone.utc)
    if prior is None or prior.revoked_at is not None or as_utc(prior.refresh_expires_at) <= now:
        raise HTTPException(status_code=401, detail={"code": "invalid_refresh", "message": "Refresh credential is invalid or expired."})
    user = db.scalar(select(User).where(User.user_id == prior.user_id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "inactive_account", "message": "Account is inactive."})
    try:
        old_id = prior.session_token_id
        prior.revoked_at = now
        new_session, access, new_refresh = issue_session(db, user)
        prior.replaced_by_session_id = new_session.session_token_id
        db.add(AuditLog(actor_user_id=user.user_id, action="auth.refresh", entity_type="session", entity_key=old_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    set_refresh_cookie(response, new_refresh)
    return {"access_token": access, "token_type": "bearer"}


@router.post("/auth/logout", status_code=204)
def logout(response: Response, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "").split(" ", 1)[-1]
    claims = jwt.decode(auth, get_settings().jwt_secret_key, algorithms=["HS256"])
    session = db.get(SessionToken, claims["sid"])
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.add(AuditLog(actor_user_id=user.user_id, action="auth.logout", entity_type="session", entity_key=session.session_token_id))
        db.commit()
    response.delete_cookie("refresh_token", path="/api/v1/auth", secure=get_settings().cookie_secure, httponly=True, samesite="strict")
    response.status_code = 204


@router.post("/auth/logout-all", status_code=204)
def logout_all(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(SessionToken).filter(SessionToken.user_id == user.user_id, SessionToken.revoked_at.is_(None)).update({"revoked_at": datetime.now(timezone.utc)})
    db.add(AuditLog(actor_user_id=user.user_id, action="auth.logout_all", entity_type="user", entity_key=str(user.user_id)))
    db.commit()
    response.delete_cookie("refresh_token", path="/api/v1/auth", secure=get_settings().cookie_secure, httponly=True, samesite="strict")
    response.status_code = 204


@router.get("/auth/sessions")
def list_sessions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    sessions = db.scalars(select(SessionToken).where(SessionToken.user_id == user.user_id,
                                                       SessionToken.revoked_at.is_(None)).order_by(SessionToken.created_at.desc()))
    return {"items": [{"session_id": item.session_token_id, "created_at": item.created_at,
                       "last_used_at": item.last_used_at, "access_expires_at": item.access_expires_at,
                       "refresh_expires_at": item.refresh_expires_at} for item in sessions]}


@router.delete("/auth/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = db.get(SessionToken, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": "Session was not found."})
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.add(AuditLog(actor_user_id=user.user_id, action="auth.session_revoke", entity_type="session", entity_key=session_id))
        db.commit()
    response.status_code = 204


@router.get("/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_payload(db, user)


@router.post("/users", status_code=201)
def create_user(payload: UserCreate, actor: User = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    role = db.scalar(select(Role).where(Role.role_key == payload.role_key))
    if role is None:
        raise HTTPException(status_code=422, detail={"code": "unknown_role", "message": "Role does not exist."})
    normalized = str(payload.email).strip().lower()
    user = User(role_id=role.role_id, email=str(payload.email), email_normalized=normalized,
                username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.flush()
        db.add(AuditLog(actor_user_id=actor.user_id, action="user.create", entity_type="user", entity_key=str(user.user_id)))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "user_conflict", "message": "Email or username is already registered."})
    return user_payload(db, user)


@router.get("/users")
def list_users(limit: int = 25, offset: int = 0, _: User = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    validate_pagination(limit, offset)
    return {"items": [user_payload(db, u) for u in db.scalars(select(User).order_by(User.user_id).offset(offset).limit(limit))], "limit": limit, "offset": offset}


@router.get("/reviews")
def list_reviews(limit: int = 25, offset: int = 0, source_system: str | None = None,
                 reviewer_id: int | None = None, product_id: int | None = None,
                 reviewed_after: datetime | None = None, reviewed_before: datetime | None = None,
                 ground_truth_available: bool | None = None,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    validate_pagination(limit, offset)
    if reviewed_after and reviewed_before and reviewed_after > reviewed_before:
        raise HTTPException(status_code=422, detail={"code": "invalid_date_range", "message": "reviewed_after must be before reviewed_before."})
    filters = [visible_review(db, user)]
    if source_system is not None:
        filters.append(Review.source_system == source_system)
    if reviewer_id is not None:
        filters.append(Review.reviewer_id == reviewer_id)
    if product_id is not None:
        filters.append(Review.product_id == product_id)
    if reviewed_after is not None:
        filters.append(Review.reviewed_at >= reviewed_after)
    if reviewed_before is not None:
        filters.append(Review.reviewed_at <= reviewed_before)
    if ground_truth_available is True:
        filters.append(Review.ground_truth_label.is_not(None))
    elif ground_truth_available is False:
        filters.append(Review.ground_truth_label.is_(None))
    total = db.scalar(select(func.count()).select_from(Review).where(*filters)) or 0
    rows = db.scalars(select(Review).where(*filters).order_by(Review.review_id).offset(offset).limit(limit))
    items = [{"review_id": r.review_id, "source_system": r.source_system,
              "source_review_key": r.source_review_key, "reviewer_id": r.reviewer_id,
              "product_id": r.product_id, "rating": r.rating, "review_text": r.review_text,
              "reviewed_at": r.reviewed_at, "has_ground_truth": r.ground_truth_label is not None}
             for r in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/reviewers")
def list_reviewers(limit: int = 25, offset: int = 0,
                   _: User = Depends(current_user), db: Session = Depends(get_db)):
    validate_pagination(limit, offset)
    total = db.scalar(select(func.count()).select_from(Reviewer)) or 0
    rows = db.scalars(select(Reviewer).order_by(Reviewer.reviewer_id).offset(offset).limit(limit))
    items = [{"reviewer_id": reviewer.reviewer_id,
              "source_system": reviewer.source_system,
              "external_reviewer_key": reviewer.external_reviewer_key,
              "created_at": reviewer.created_at}
             for reviewer in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/products")
def list_products(limit: int = 25, offset: int = 0,
                  _: User = Depends(current_user), db: Session = Depends(get_db)):
    validate_pagination(limit, offset)
    total = db.scalar(select(func.count()).select_from(Product)) or 0
    rows = db.scalars(select(Product).order_by(Product.product_id).offset(offset).limit(limit))
    items = [{"product_id": product.product_id,
              "source_system": product.source_system,
              "external_product_key": product.external_product_key,
              "display_name": product.display_name,
              "created_at": product.created_at}
             for product in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/reviews", status_code=201)
def create_review(payload: ReviewCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if (payload.source_system is None) != (payload.source_review_key is None):
        raise HTTPException(status_code=422, detail={"code": "source_pair_required", "message": "source_system and source_review_key must be supplied together."})
    review = Review(**payload.model_dump(), submitted_by_user_id=user.user_id)
    db.add(review)
    try:
        db.flush()
        db.add(AuditLog(actor_user_id=user.user_id, action="review.create", entity_type="review", entity_key=str(review.review_id)))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "review_conflict", "message": "Review source key is duplicated or a reference is invalid."})
    return {"review_id": review.review_id}


@router.get("/models/status")
def model_status(db: Session = Depends(get_db)):
    provenance_counts = dict(db.execute(
        select(ModelVersion.provenance, func.count()).group_by(ModelVersion.provenance)
    ).all())
    verified_real_count = db.scalar(
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
    baseline = get_verified_baseline().status()
    multimodal = get_verified_multimodal().status()
    if baseline["available"] or multimodal["available"]:
        return {"status": "available", "inference_available": True,
                "reason": "verified_yelpchi_baseline_ready" if baseline["available"] else "verified_yelpchi_multimodal_ready",
                "supported_modes": ["known_node_only"],
                "verified_baseline": baseline,
                "verified_multimodal": multimodal,
                "verified_real_model_count": verified_real_count,
                "model_version_counts_by_provenance": provenance_counts,
                "runtime_loaded": baseline["runtime_loaded"] or multimodal["runtime_loaded"],
                "details": baseline["details"] if baseline["available"] else multimodal["details"]}
    reason = "no_verified_real_model" if not verified_real_count else "verified_runtime_not_loaded"
    return {"status": "unavailable", "inference_available": False,
            "reason": reason, "supported_modes": [],
            "verified_baseline": baseline,
            "verified_multimodal": multimodal,
            "verified_real_model_count": verified_real_count,
            "model_version_counts_by_provenance": provenance_counts,
            "runtime_loaded": False,
            "details": "Database provenance and lifecycle are checked, but this API has no compatible verified inference runtime loaded."}


@router.get("/model-versions")
def list_model_versions(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ModelVersion).order_by(ModelVersion.model_version_id.desc()))
    return {"items": [{"model_version_id": row.model_version_id, "version_key": row.version_key,
                       "model_name": row.model_name, "architecture_version": row.architecture_version,
                       "lifecycle_status": row.lifecycle_status, "supported_inference_mode": row.supported_inference_mode,
                       "provenance": row.provenance,
                       "checkpoint_sha256": row.checkpoint_sha256,
                       "preprocessing_version_id": row.preprocessing_version_id,
                       "recommended_threshold": float(row.recommended_threshold) if row.recommended_threshold is not None else None}
                      for row in rows]}


@router.get("/preprocessing-versions")
def list_preprocessing_versions(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(PreprocessingVersion).order_by(PreprocessingVersion.preprocessing_version_id.desc()))
    return {"items": [{"preprocessing_version_id": row.preprocessing_version_id,
                       "version_key": row.version_key, "preprocessing_sha256": row.preprocessing_sha256,
                       "lifecycle_status": row.lifecycle_status} for row in rows]}


@router.get("/graph-snapshots")
def list_graph_snapshots(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(GraphSnapshot).order_by(GraphSnapshot.graph_snapshot_id.desc())).all()
    return {"items": [{
        "graph_snapshot_id": s.graph_snapshot_id,
        "snapshot_key": s.snapshot_key,
        "dataset_name": s.dataset_name,
        "dataset_sha256": s.dataset_sha256,
        "artifact_sha256": s.artifact_sha256,
        "relation_schema_version": s.relation_schema_version,
        "split_protocol_key": s.split_protocol_key,
        "storage_status": s.storage_status,
        "node_count": s.node_count,
        "batch_context_permitted": s.batch_context_permitted,
        "context_scope_key": s.context_scope_key,
        "provenance": s.provenance,
    } for s in rows]}


@router.get("/graph-snapshots/{snapshot_id}")
def get_graph_snapshot(snapshot_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    snapshot = db.get(GraphSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"code": "snapshot_not_found", "message": "Graph snapshot was not found."})
    return {"graph_snapshot_id": snapshot.graph_snapshot_id, "snapshot_key": snapshot.snapshot_key,
            "dataset_name": snapshot.dataset_name, "dataset_sha256": snapshot.dataset_sha256,
            "artifact_sha256": snapshot.artifact_sha256, "split_protocol_key": snapshot.split_protocol_key,
            "storage_status": snapshot.storage_status, "node_count": snapshot.node_count,
            "batch_context_permitted": snapshot.batch_context_permitted}


@router.post("/inference-runs")
def create_inference(payload: InferenceRequest, user: User = Depends(current_user),
                     db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if not idempotency_key:
        raise HTTPException(status_code=422, detail={"code": "idempotency_key_required", "message": "Idempotency-Key is required for inference requests."})
    model = db.get(ModelVersion, payload.model_version_id)
    if model is None:
        raise HTTPException(status_code=503, detail={"code": "model_unavailable", "message": "The requested model version does not exist; inference was not created."})
    if model.provenance == "synthetic_demo":
        raise HTTPException(status_code=503, detail={"code": "synthetic_demo_runtime_unavailable", "message": "Synthetic demo models are not eligible for real inference and no demo scoring runtime is loaded; inference was not created."})
    preprocessing = db.get(PreprocessingVersion, model.preprocessing_version_id)
    if (model.provenance != "real" or model.lifecycle_status != "verified" or
            model.checkpoint_uri is None or model.checkpoint_sha256 is None or
            model.recommended_threshold is None or model.threshold_source is None or
            model.verification_at is None or preprocessing is None or
            preprocessing.lifecycle_status != "verified"):
        raise HTTPException(status_code=503, detail={"code": "model_unavailable", "message": "The requested model version is not registered as verified; inference was not created."})
    # A verified database row is necessary but not sufficient. The runtime bundle
    # still needs to be loaded and verified before any run or prediction is written.
    raise HTTPException(status_code=503, detail={"code": "model_runtime_unavailable", "message": "The requested model is marked verified, but no compatible verified runtime bundle is loaded; inference was not created."})


@router.get("/inference-runs")
def list_inference_runs(limit: int = 25, offset: int = 0, status: str | None = None,
                        model_version_id: int | None = None, graph_snapshot_id: int | None = None,
                        _: User = Depends(current_user), db: Session = Depends(get_db)):
    validate_pagination(limit, offset)
    allowed_statuses = {"queued", "running", "completed", "failed", "cancelled"}
    if status is not None and status not in allowed_statuses:
        raise HTTPException(status_code=422, detail={"code": "invalid_run_status", "message": "status filter is invalid."})
    filters = []
    if status is not None:
        filters.append(InferenceRun.status == status)
    if model_version_id is not None:
        filters.append(InferenceRun.model_version_id == model_version_id)
    if graph_snapshot_id is not None:
        filters.append(InferenceRun.graph_snapshot_id == graph_snapshot_id)
    total = db.scalar(select(func.count()).select_from(InferenceRun).where(*filters)) or 0
    rows = db.execute(
        select(InferenceRun, ModelVersion, GraphSnapshot)
        .join(ModelVersion, ModelVersion.model_version_id == InferenceRun.model_version_id)
        .join(GraphSnapshot, GraphSnapshot.graph_snapshot_id == InferenceRun.graph_snapshot_id)
        .where(*filters).order_by(InferenceRun.created_at.desc(), InferenceRun.inference_run_id.desc())
        .offset(offset).limit(limit)
    ).all()
    items = [{"inference_run_id": run.inference_run_id, "run_key": run.run_key,
              "status": run.status, "provenance": run.provenance, "requested_count": run.requested_count,
              "completed_count": run.completed_count, "threshold": float(run.threshold),
              "created_at": run.created_at, "completed_at": run.completed_at,
              "model": {"model_version_id": model.model_version_id, "version_key": model.version_key,
                        "model_name": model.model_name, "checkpoint_sha256": model.checkpoint_sha256,
                        "preprocessing_version_id": model.preprocessing_version_id},
              "graph_snapshot": {"graph_snapshot_id": snapshot.graph_snapshot_id,
                                 "snapshot_key": snapshot.snapshot_key,
                                 "artifact_sha256": snapshot.artifact_sha256}}
             for run, model, snapshot in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/reviews/{review_id}/predictions")
def list_review_predictions(review_id: int, limit: int = 25, offset: int = 0,
                            user: User = Depends(current_user), db: Session = Depends(get_db)):
    validate_pagination(limit, offset)
    if db.scalar(select(Review.review_id).where(Review.review_id == review_id, visible_review(db, user))) is None:
        raise HTTPException(status_code=404, detail={"code": "review_not_found", "message": "Review was not found."})
    filters = [FraudPrediction.review_id == review_id]
    role = db.get(Role, user.role_id)
    if not role or role.role_key != "ADMIN":
        filters.append(or_(InferenceRun.requested_by_user_id == user.user_id,
                           InferenceRun.requested_by_user_id.is_(None)))
    total = db.scalar(select(func.count()).select_from(FraudPrediction).join(InferenceRun,
        InferenceRun.inference_run_id == FraudPrediction.inference_run_id).where(*filters)) or 0
    rows = db.execute(
        select(FraudPrediction, InferenceRun, ModelVersion, PreprocessingVersion,
               GraphSnapshot, GraphSnapshotReview.split)
        .join(InferenceRun, InferenceRun.inference_run_id == FraudPrediction.inference_run_id)
        .join(ModelVersion, ModelVersion.model_version_id == InferenceRun.model_version_id)
        .join(PreprocessingVersion, PreprocessingVersion.preprocessing_version_id == ModelVersion.preprocessing_version_id)
        .join(GraphSnapshot, GraphSnapshot.graph_snapshot_id == InferenceRun.graph_snapshot_id)
        .outerjoin(GraphSnapshotReview, (GraphSnapshotReview.graph_snapshot_id == InferenceRun.graph_snapshot_id) &
                   (GraphSnapshotReview.review_id == FraudPrediction.review_id))
        .where(*filters).order_by(FraudPrediction.created_at.desc(), FraudPrediction.fraud_prediction_id.desc())
        .offset(offset).limit(limit)
    ).all()
    items = [{"prediction_id": prediction.fraud_prediction_id,
              "review_id": prediction.review_id, "inference_run_id": run.inference_run_id,
              "fraud_score": float(prediction.risk_score), "predicted_label": prediction.predicted_label,
              "threshold_used": float(run.threshold), "created_at": prediction.created_at,
              "attention": prediction.attention_weights, "graph_status": prediction.graph_status,
              "provenance": {"model_version_id": model.model_version_id,
                             "model_version_key": model.version_key,
                             "model_provenance": model.provenance,
                             "run_provenance": run.provenance,
                             "checkpoint_sha256": model.checkpoint_sha256,
                             "preprocessing_version_id": preprocessing.preprocessing_version_id,
                             "preprocessing_version_key": preprocessing.version_key,
                             "preprocessing_sha256": preprocessing.preprocessing_sha256,
                             "graph_snapshot_id": snapshot.graph_snapshot_id,
                             "graph_snapshot_sha256": snapshot.artifact_sha256,
                             "split_protocol_key": snapshot.split_protocol_key,
                             "review_split": split}}
             for prediction, run, model, preprocessing, snapshot, split in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/graph-sync/status")
def graph_sync_status(_: User = Depends(current_user), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(GraphSyncJob.status, func.count()).group_by(GraphSyncJob.status)).all())
    configured = bool(get_settings().neo4j_uri)
    return {"neo4j": "configured_unverified" if configured else "unconfigured",
            "connection_verified": False, "queue_counts": counts,
            "message": "No Neo4j connection check or worker has been run by this backend."}


@router.post("/graph-sync-jobs", status_code=202)
def create_graph_sync_job(payload: GraphSyncCreate, user: User = Depends(require_roles("ADMIN")),
                          db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if not idempotency_key:
        raise HTTPException(status_code=422, detail={"code": "idempotency_key_required", "message": "Idempotency-Key is required for graph sync requests."})
    review_scoped = payload.operation in ("review_upsert", "review_delete")
    if review_scoped != (payload.review_id is not None and payload.graph_snapshot_id is None):
        raise HTTPException(status_code=422, detail={"code": "invalid_graph_job_scope", "message": "Review jobs require only review_id; snapshot rebuilds require only graph_snapshot_id."})
    if not review_scoped and (payload.graph_snapshot_id is None or payload.review_id is not None):
        raise HTTPException(status_code=422, detail={"code": "invalid_graph_job_scope", "message": "Snapshot rebuilds require only graph_snapshot_id."})
    if idempotency_key:
        existing = db.scalar(select(GraphSyncJob).where(GraphSyncJob.requested_by_user_id == user.user_id,
                                                        GraphSyncJob.idempotency_key == idempotency_key))
        if existing:
            if (existing.operation, existing.review_id, existing.graph_snapshot_id) != (payload.operation, payload.review_id, payload.graph_snapshot_id):
                raise HTTPException(status_code=409, detail={"code": "idempotency_conflict", "message": "Idempotency key was already used for a different graph sync request."})
            return {"graph_sync_job_id": existing.graph_sync_job_id, "status": existing.status, "deduplicated": True}
    job = GraphSyncJob(operation=payload.operation, review_id=payload.review_id,
                       graph_snapshot_id=payload.graph_snapshot_id,
                       requested_by_user_id=user.user_id, idempotency_key=idempotency_key,
                       status="queued")
    db.add(job)
    try:
        db.flush()
        db.add(AuditLog(actor_user_id=user.user_id, action="graph_sync.enqueue", entity_type="graph_sync_job", entity_key=str(job.graph_sync_job_id)))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "graph_job_conflict", "message": "The idempotency key already identifies a different sync request."})
    return {"graph_sync_job_id": job.graph_sync_job_id, "status": job.status, "deduplicated": False}

