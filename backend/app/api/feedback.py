"""ORM feedback CRUD; PostgreSQL procedure resolves feedback without changing model output."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import column, func, select, table, text
from sqlalchemy.orm import Session

from app.api.routes import visible_review
from app.db import get_db
from app.models import AuditLog, Review, ReviewFeedback, Role, User
from app.security import current_user, require_roles

router = APIRouter(prefix="/api/v1")


class FeedbackInput(BaseModel):
    review_id: int = Field(gt=0)
    feedback_type: Literal['label_correction', 'review_quality', 'other']
    ground_truth_label: Literal[0, 1] | None = None
    comment: str = Field(min_length=3, max_length=2000)


class ResolutionInput(BaseModel):
    status: Literal['triaged', 'resolved', 'rejected']


def payload(item):
    return {k: getattr(item, k) for k in ('feedback_id', 'review_id', 'submitted_by_user_id',
            'feedback_type', 'ground_truth_label', 'comment', 'status', 'created_at')}


def audit_actor(db, user):
    if db.bind.dialect.name == 'postgresql':
        db.execute(select(func.set_config('neurograph.actor_id', str(user.user_id), True)))


def visible_item(db, user, item_id):
    statement = select(ReviewFeedback).where(ReviewFeedback.feedback_id == item_id)
    if db.get(Role, user.role_id).role_key != 'ADMIN':
        statement = statement.where(ReviewFeedback.submitted_by_user_id == user.user_id)
    item = db.scalar(statement.with_for_update())
    if item is None:
        raise HTTPException(404, detail={'code': 'not_found', 'message': 'Feedback not found.'})
    return item


def writable(item, user):
    if item.submitted_by_user_id != user.user_id or item.status != 'submitted':
        raise HTTPException(409, detail={'code': 'feedback_locked', 'message': 'Only your own submitted feedback can be edited or removed.'})


@router.get('/feedback')
def list_feedback(status: Literal['submitted', 'triaged', 'resolved', 'rejected'] | None = None,
                  q: str = Query('', max_length=120), limit: int = Query(20, ge=1, le=100),
                  offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    filters = []
    if db.get(Role, user.role_id).role_key != 'ADMIN':
        filters.append(ReviewFeedback.submitted_by_user_id == user.user_id)
    if status:
        filters.append(ReviewFeedback.status == status)
    if q:
        filters.append(ReviewFeedback.comment.ilike('%' + q.replace('%', r'\%').replace('_', r'\_') + '%', escape='\\'))
    total = db.scalar(select(func.count()).select_from(ReviewFeedback).where(*filters))
    items = db.scalars(select(ReviewFeedback).where(*filters).order_by(ReviewFeedback.created_at.desc(), ReviewFeedback.feedback_id.desc()).limit(limit).offset(offset))
    return {'items': [payload(i) for i in items], 'total': total, 'limit': limit, 'offset': offset}


@router.post('/feedback', status_code=201)
def create_feedback(body: FeedbackInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.scalar(select(Review.review_id).where(Review.review_id == body.review_id, visible_review(db, user))) is None:
        raise HTTPException(404, detail={'code': 'not_found', 'message': 'Review not found.'})
    audit_actor(db, user)
    item = ReviewFeedback(**body.model_dump(), submitted_by_user_id=user.user_id, status='submitted')
    db.add(item)
    db.commit()
    db.refresh(item)
    return payload(item)


@router.patch('/feedback/{feedback_id}')
def update_feedback(feedback_id: int, body: FeedbackInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = visible_item(db, user, feedback_id)
    writable(item, user)
    if body.review_id != item.review_id:
        raise HTTPException(422, detail={'code': 'review_immutable', 'message': 'Feedback must remain attached to the original review.'})
    audit_actor(db, user)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return payload(item)


@router.delete('/feedback/{feedback_id}', status_code=204)
def delete_feedback(feedback_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = visible_item(db, user, feedback_id)
    writable(item, user)
    audit_actor(db, user)
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.post('/feedback/{feedback_id}/resolve')
def resolve_feedback(feedback_id: int, body: ResolutionInput, user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    item = visible_item(db, user, feedback_id)
    if db.bind.dialect.name == 'postgresql':
        # CALL is the intentional exception to ORM CRUD for a PostgreSQL procedure.
        db.execute(text('CALL resolve_review_feedback(:feedback_id, :actor_id, :status)'),
                   {'feedback_id': feedback_id, 'actor_id': user.user_id, 'status': body.status})
        db.expire(item)
    else:
        item.status = body.status
        db.add(AuditLog(actor_user_id=user.user_id, action='feedback.resolve', entity_type='review_feedback', entity_key=str(feedback_id)))
    db.commit()
    return payload(item)


@router.get('/database/summary')
def database_summary(user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    # SQLAlchemy Core reads the migration-owned aggregate views, without raw query interpolation.
    batches = table('vw_batch_analysis_summary', column('batch_analysis_id'), column('scored_count'), column('flagged_count'))
    products = table('vw_product_review_summary', column('product_id'), column('review_count'))
    batch_counts = db.execute(select(func.count(), func.coalesce(func.sum(batches.c.scored_count), 0), func.coalesce(func.sum(batches.c.flagged_count), 0)).select_from(batches)).one()
    product_counts = db.execute(select(func.count(), func.coalesce(func.sum(products.c.review_count), 0)).select_from(products)).one()
    return {'batches': batch_counts[0], 'scored': batch_counts[1], 'flagged': batch_counts[2], 'products': product_counts[0], 'reviews': product_counts[1],
            'views': ['vw_batch_analysis_summary', 'vw_product_review_summary']}
