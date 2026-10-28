"""Executed PostgreSQL evidence. Requires an empty disposable TEST_POSTGRES_URL database."""
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, Review, ReviewFeedback, Role, User
from app.security import hash_password


@pytest.fixture(scope='module')
def postgres():
    url = os.getenv('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL must identify a disposable PostgreSQL database')
    engine = create_engine(url)
    with engine.connect() as conn:
        assert not inspect(conn).has_table('users'), 'Refusing to migrate a nonempty test database'
    previous = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = url
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    try:
        command.upgrade(config, 'head')
        yield engine
    finally:
        if previous is None: os.environ.pop('DATABASE_URL', None)
        else: os.environ['DATABASE_URL'] = previous
        engine.dispose()


def test_postgres_schema_views_and_constraints(postgres):
    schema = inspect(postgres)
    tables = set(schema.get_table_names()) - {'alembic_version'}
    assert len(tables) >= 8
    assert all(schema.get_pk_constraint(t)['constrained_columns'] for t in tables)
    assert {'vw_batch_analysis_summary', 'vw_product_review_summary'} <= set(schema.get_view_names())
    with postgres.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM vw_batch_analysis_summary')).scalar() == 0
        assert conn.execute(text('SELECT count(*) FROM vw_product_review_summary')).scalar() == 0
    with Session(postgres) as db:
        db.add(Review(rating=9))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        db.add(Review(product_id=999999))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()


def test_postgres_trigger_procedure_and_transaction_rollback(postgres):
    with Session(postgres) as db:
        admin_role = Role(role_key='ADMIN', display_name='Administrator')
        reader_role = Role(role_key='RESEARCHER', display_name='Researcher')
        db.add_all([admin_role, reader_role]); db.flush()
        admin = User(role_id=admin_role.role_id, email='pg-admin@example.test', email_normalized='pg-admin@example.test', password_hash=hash_password('disposable-test-password'))
        reader = User(role_id=reader_role.role_id, email='pg-reader@example.test', email_normalized='pg-reader@example.test', password_hash=hash_password('disposable-test-password'))
        review = Review(rating=4, review_text='Disposable database evidence')
        db.add_all([admin, reader, review]); db.flush()
        admin_id, reader_id = admin.user_id, reader.user_id
        db.execute(select(func.set_config('neurograph.actor_id', str(reader_id), True)))
        feedback = ReviewFeedback(review_id=review.review_id, submitted_by_user_id=reader_id, feedback_type='other', comment='Sensitive note must never appear in audit JSON', status='submitted')
        db.add(feedback); db.commit(); fid = feedback.feedback_id
        audit = db.scalar(select(AuditLog).where(AuditLog.action == 'feedback.insert'))
        assert audit.actor_user_id == reader_id
        assert 'Sensitive' not in str(audit.after_data) and 'comment' not in audit.after_data
        db.execute(text('CALL resolve_review_feedback(:fid, :actor, :status)'), {'fid':fid,'actor':admin_id,'status':'resolved'})
        db.commit(); db.refresh(feedback)
        assert feedback.status == 'resolved'
        assert db.scalar(select(AuditLog).where(AuditLog.action == 'feedback.update')).actor_user_id == admin_id
        for actor, status in [(reader_id,'triaged'), (admin_id,'invalid')]:
            with pytest.raises(DBAPIError):
                db.execute(text('CALL resolve_review_feedback(:fid,:actor,:status)'), {'fid':fid,'actor':actor,'status':status})
            db.rollback()
        count = db.query(AuditLog).count()
        db.execute(text('CALL resolve_review_feedback(:fid,:actor,:status)'), {'fid':fid,'actor':admin_id,'status':'triaged'})
        db.rollback(); db.refresh(feedback)
        assert feedback.status == 'resolved' and db.query(AuditLog).count() == count
        db.delete(feedback); db.commit()
        assert db.scalar(select(AuditLog).where(AuditLog.action == 'feedback.delete')) is not None
