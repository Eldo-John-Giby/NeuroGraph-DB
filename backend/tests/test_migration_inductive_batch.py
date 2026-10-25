"""Migration and schema integrity tests for inductive batch scoring support (revision 0005)."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    FraudPrediction,
    GraphSnapshot,
    InductiveInferenceJob,
    InductivePredictionEvidence,
    InferenceRun,
    ModelVersion,
    PreprocessingVersion,
    Product,
    Review,
    Reviewer,
    Role,
    User,
)


@pytest.fixture()
def alembic_sqlite_db(monkeypatch):
    """Provides a temporary SQLite database initialized and migrated via Alembic."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    backend_dir = Path(__file__).resolve().parents[1]
    alembic_ini = backend_dir / "alembic.ini"

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        dbapi_connection.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    yield cfg, engine, db_url

    engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_alembic_upgrade_and_downgrade_cycle(alembic_sqlite_db):
    """Test full upgrade to head, downgrade to 0004, and re-upgrade to head."""
    cfg, engine, _ = alembic_sqlite_db

    # 1. Upgrade to head (0005)
    command.upgrade(cfg, "head")
    insp = inspect(engine)
    table_names = insp.get_table_names()
    assert "inductive_inference_jobs" in table_names
    assert "inductive_prediction_evidence" in table_names

    columns = {col["name"] for col in insp.get_columns("graph_snapshots")}
    assert "context_scope_key" in columns

    # 2. Downgrade to 0004_synthetic_campaigns
    command.downgrade(cfg, "0004_synthetic_campaigns")
    insp = inspect(engine)
    table_names_downgraded = insp.get_table_names()
    assert "inductive_inference_jobs" not in table_names_downgraded
    assert "inductive_prediction_evidence" not in table_names_downgraded

    columns_downgraded = {col["name"] for col in insp.get_columns("graph_snapshots")}
    assert "context_scope_key" not in columns_downgraded

    # 3. Re-upgrade to head
    command.upgrade(cfg, "head")
    insp = inspect(engine)
    assert "inductive_inference_jobs" in insp.get_table_names()
    assert "inductive_prediction_evidence" in insp.get_table_names()


def test_historical_rows_preserved_without_alteration(alembic_sqlite_db):
    """Test that existing pre-0005 rows migrate cleanly without data alteration."""
    cfg, engine, _ = alembic_sqlite_db

    # Migrate up to 0004
    command.upgrade(cfg, "0004_synthetic_campaigns")

    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        # Insert historical preprocessing version
        conn.execute(
            text("""
            INSERT INTO preprocessing_versions
            (preprocessing_version_id, version_key, preprocessing_sha256, preprocessing_config, code_revision, lifecycle_status, created_at)
            VALUES (1, 'prep-v1', :sha_a, '{}', 'rev-1', 'verified', :now)
        """),
            {"now": now, "sha_a": "a" * 64},
        )
        # Insert historical model version with known_node_only
        conn.execute(
            text("""
            INSERT INTO model_versions
            (model_version_id, version_key, model_name, architecture_version, architecture_config, config_sha256,
             checkpoint_uri, checkpoint_sha256, preprocessing_version_id, input_contract_version, supported_inference_mode,
             recommended_threshold, threshold_source, lifecycle_status, provenance, verification_at, created_at)
            VALUES (1, 'mv-v1', 'baseline-gnn', 'v1', '{}', :sha_b,
                    'uri://chk', :sha_c, 1, 'in-v1', 'known_node_only',
                    0.5, 'val_f1', 'verified', 'real', :now, :now)
        """),
            {"now": now, "sha_b": "b" * 64, "sha_c": "c" * 64},
        )
        # Insert historical graph snapshot with batch_context_permitted = false
        conn.execute(
            text("""
            INSERT INTO graph_snapshots
            (graph_snapshot_id, snapshot_key, dataset_name, dataset_sha256, artifact_uri, artifact_sha256,
             graph_builder_version, relation_schema_version, split_protocol_key, node_count, edge_counts,
             storage_status, batch_context_permitted, provenance, created_at)
            VALUES (1, 'snap-hist', 'yelpchi', :sha_d,
                    'uri://art', :sha_e,
                    'gb-v1', 'rel-v1', 'split-v1', 100, '{}', 'available', 0, 'real', :now)
        """),
            {"now": now, "sha_d": "d" * 64, "sha_e": "e" * 64},
        )

    # Now run upgrade to 0005
    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT snapshot_key, batch_context_permitted, context_scope_key FROM graph_snapshots WHERE graph_snapshot_id = 1")
        ).fetchone()
        assert row is not None
        assert row[0] == "snap-hist"
        assert row[1] in (0, False)
        assert row[2] is None  # context_scope_key remains NULL for historical non-permitted snapshot

        mv_row = conn.execute(
            text("SELECT version_key, supported_inference_mode FROM model_versions WHERE model_version_id = 1")
        ).fetchone()
        assert mv_row is not None
        assert mv_row[1] == "known_node_only"


def test_graph_snapshot_context_scope_key_constraint(alembic_sqlite_db):
    """Test that context_scope_key is required when batch_context_permitted is true."""
    cfg, engine, _ = alembic_sqlite_db
    command.upgrade(cfg, "head")
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        # 1. Permitted=False with context_scope_key=None -> OK
        s1 = GraphSnapshot(
            snapshot_key="snap-not-permitted",
            dataset_name="yelpchi",
            dataset_sha256="1" * 64,
            artifact_uri="uri://1",
            artifact_sha256="2" * 64,
            graph_builder_version="v1",
            relation_schema_version="v1",
            split_protocol_key="split1",
            node_count=10,
            batch_context_permitted=False,
            context_scope_key=None,
        )
        db.add(s1)
        db.commit()

        # 2. Permitted=True with context_scope_key="valid-scope" -> OK
        s2 = GraphSnapshot(
            snapshot_key="snap-permitted-valid",
            dataset_name="yelpchi",
            dataset_sha256="3" * 64,
            artifact_uri="uri://2",
            artifact_sha256="4" * 64,
            graph_builder_version="v1",
            relation_schema_version="v1",
            split_protocol_key="split1",
            node_count=20,
            batch_context_permitted=True,
            context_scope_key="yelpchi-inductive-context-v1",
        )
        db.add(s2)
        db.commit()

        # 3. Permitted=True with context_scope_key=None -> VIOLATES ck_snapshot_context_scope
        s3 = GraphSnapshot(
            snapshot_key="snap-permitted-invalid-null",
            dataset_name="yelpchi",
            dataset_sha256="5" * 64,
            artifact_uri="uri://3",
            artifact_sha256="6" * 64,
            graph_builder_version="v1",
            relation_schema_version="v1",
            split_protocol_key="split1",
            node_count=30,
            batch_context_permitted=True,
            context_scope_key=None,
        )
        db.add(s3)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 4. Permitted=True with empty/whitespace context_scope_key -> VIOLATES ck_snapshot_context_scope
        s4 = GraphSnapshot(
            snapshot_key="snap-permitted-invalid-blank",
            dataset_name="yelpchi",
            dataset_sha256="7" * 64,
            artifact_uri="uri://4",
            artifact_sha256="8" * 64,
            graph_builder_version="v1",
            relation_schema_version="v1",
            split_protocol_key="split1",
            node_count=40,
            batch_context_permitted=True,
            context_scope_key="   ",
        )
        db.add(s4)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_model_version_supported_inference_mode_constraint(alembic_sqlite_db):
    """Test that model_versions supports 'known_node_only' and 'inductive_batch_v1'."""
    cfg, engine, _ = alembic_sqlite_db
    command.upgrade(cfg, "head")
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        prep = PreprocessingVersion(
            version_key="prep-test",
            preprocessing_sha256="a" * 64,
            preprocessing_config={},
            code_revision="rev-1",
            lifecycle_status="verified",
        )
        db.add(prep)
        db.flush()

        # 1. known_node_only is supported
        mv1 = ModelVersion(
            version_key="mv-known-node",
            model_name="GNN-Known",
            architecture_version="v1",
            architecture_config={},
            config_sha256="b" * 64,
            preprocessing_version_id=prep.preprocessing_version_id,
            input_contract_version="c1",
            supported_inference_mode="known_node_only",
            lifecycle_status="registered",
            provenance="real",
        )
        db.add(mv1)
        db.commit()

        # 2. inductive_batch_v1 is supported
        mv2 = ModelVersion(
            version_key="mv-inductive-batch",
            model_name="GNN-Inductive",
            architecture_version="v2",
            architecture_config={},
            config_sha256="c" * 64,
            preprocessing_version_id=prep.preprocessing_version_id,
            input_contract_version="c2",
            supported_inference_mode="inductive_batch_v1",
            lifecycle_status="registered",
            provenance="real",
        )
        db.add(mv2)
        db.commit()

        # 3. Arbitrary/unsupported mode is rejected
        mv3 = ModelVersion(
            version_key="mv-invalid-mode",
            model_name="GNN-Invalid",
            architecture_version="v3",
            architecture_config={},
            config_sha256="d" * 64,
            preprocessing_version_id=prep.preprocessing_version_id,
            input_contract_version="c3",
            supported_inference_mode="streaming_unsupported_mode",
            lifecycle_status="registered",
            provenance="real",
        )
        db.add(mv3)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_provenance_and_synthetic_demo_ineligibility(alembic_sqlite_db):
    """Test that synthetic_demo models cannot be verified for real inference."""
    cfg, engine, _ = alembic_sqlite_db
    command.upgrade(cfg, "head")
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        prep = PreprocessingVersion(
            version_key="prep-prov-test",
            preprocessing_sha256="e" * 64,
            preprocessing_config={},
            code_revision="rev-1",
            lifecycle_status="verified",
        )
        db.add(prep)
        db.commit()

        # 1. Synthetic demo model CANNOT have lifecycle_status='verified'
        now = datetime.now(timezone.utc)
        demo_model = ModelVersion(
            version_key="demo-mv-invalid-verified",
            model_name="Demo-GNN",
            architecture_version="v1",
            architecture_config={},
            config_sha256="f" * 64,
            checkpoint_uri="test://chk",
            checkpoint_sha256="0" * 64,
            preprocessing_version_id=prep.preprocessing_version_id,
            input_contract_version="c1",
            supported_inference_mode="inductive_batch_v1",
            recommended_threshold=0.5,
            threshold_source="manual",
            verification_at=now,
            lifecycle_status="verified",  # Ineligible!
            provenance="synthetic_demo",
        )
        db.add(demo_model)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 2. Synthetic demo CAN be registered or unavailable
        demo_model_ok = ModelVersion(
            version_key="demo-mv-registered",
            model_name="Demo-GNN",
            architecture_version="v1",
            architecture_config={},
            config_sha256="f" * 64,
            preprocessing_version_id=prep.preprocessing_version_id,
            input_contract_version="c1",
            supported_inference_mode="inductive_batch_v1",
            lifecycle_status="registered",
            provenance="synthetic_demo",
        )
        db.add(demo_model_ok)
        db.commit()

        # 3. Real inference run cannot point to synthetic_demo model
        snap = GraphSnapshot(
            snapshot_key="snap-prov",
            dataset_name="yelpchi",
            dataset_sha256="1" * 64,
            artifact_uri="uri://1",
            artifact_sha256="2" * 64,
            graph_builder_version="v1",
            relation_schema_version="v1",
            split_protocol_key="split1",
            node_count=10,
            batch_context_permitted=False,
            provenance="real",
        )
        db.add(snap)
        db.flush()

        run_mismatched = InferenceRun(
            model_version_id=demo_model_ok.model_version_id,
            provenance="real",  # Mismatched! Demo model is synthetic_demo
            graph_snapshot_id=snap.graph_snapshot_id,
            threshold=0.5,
            requested_count=1,
            completed_count=0,
            status="queued",
        )
        db.add(run_mismatched)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_inductive_inference_jobs_durable_leasing(alembic_sqlite_db):
    """Test inductive_inference_jobs table, one-to-one link to inference_runs, and worker leasing."""
    cfg, engine, _ = alembic_sqlite_db
    command.upgrade(cfg, "head")
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        prep = PreprocessingVersion(
            version_key="prep-job-test",
            preprocessing_sha256="1" * 64,
            preprocessing_config={},
            code_revision="rev-1",
            lifecycle_status="verified",
        )
        snap = GraphSnapshot(
            snapshot_key="snap-job-test",
            dataset_name="yelpchi",
            dataset_sha256="2" * 64,
            artifact_uri="uri://art",
            artifact_sha256="3" * 64,
            graph_builder_version="v1",
            relation_schema_version="v1",
            split_protocol_key="split1",
            node_count=100,
            batch_context_permitted=True,
            context_scope_key="scope-test",
            provenance="real",
        )
        db.add_all([prep, snap])
        db.flush()

        mv = ModelVersion(
            version_key="mv-job-test",
            model_name="Inductive-GNN",
            architecture_version="v1",
            architecture_config={},
            config_sha256="4" * 64,
            checkpoint_uri="test://chk",
            checkpoint_sha256="5" * 64,
            preprocessing_version_id=prep.preprocessing_version_id,
            input_contract_version="c1",
            supported_inference_mode="inductive_batch_v1",
            recommended_threshold=0.75,
            threshold_source="validation",
            verification_at=datetime.now(timezone.utc),
            lifecycle_status="verified",
            provenance="real",
        )
        db.add(mv)
        db.flush()

        run = InferenceRun(
            model_version_id=mv.model_version_id,
            provenance="real",
            graph_snapshot_id=snap.graph_snapshot_id,
            threshold=0.75,
            requested_count=5,
            completed_count=0,
            status="queued",
        )
        db.add(run)
        db.flush()

        # 1. Create durable leased job
        now = datetime.now(timezone.utc)
        job = InductiveInferenceJob(
            inference_run_id=run.inference_run_id,
            status="running",
            worker_id="worker-gpu-node-01",
            lease_token="lease-token-abc-123",
            lease_expires_at=now + timedelta(minutes=10),
            attempt_count=1,
            max_attempts=3,
            priority=10,
            started_at=now,
            provenance="real",
        )
        db.add(job)
        db.commit()

        # 2. One-to-one constraint: inserting another job for same inference_run_id fails
        duplicate_job = InductiveInferenceJob(
            inference_run_id=run.inference_run_id,
            status="queued",
            provenance="real",
        )
        db.add(duplicate_job)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 3. Invalid status fails
        invalid_job = InductiveInferenceJob(
            inference_run_id=run.inference_run_id,
            status="unknown_status",
            provenance="real",
        )
        db.add(invalid_job)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_inductive_prediction_evidence_integrity(alembic_sqlite_db):
    """Test inductive_prediction_evidence linked one-to-one to fraud_predictions and SHA256 fields."""
    cfg, engine, _ = alembic_sqlite_db
    command.upgrade(cfg, "head")
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        prep = PreprocessingVersion(
            version_key="prep-ev-test",
            preprocessing_sha256="a" * 64,
            preprocessing_config={},
            code_revision="rev-1",
            lifecycle_status="verified",
        )
        snap = GraphSnapshot(
            snapshot_key="snap-ev-test",
            dataset_name="yelpchi",
            dataset_sha256="b" * 64,
            artifact_uri="uri://art",
            artifact_sha256="c" * 64,
            graph_builder_version="v1",
            relation_schema_version="inductive-rur-rsr-rtr-v1",
            split_protocol_key="split1",
            node_count=100,
            batch_context_permitted=True,
            context_scope_key="scope-ev-test",
            provenance="real",
        )
        rev = Review(
            source_system="yelpchi",
            source_review_key="rev-101",
            rating=5,
            review_text="Sample text",
        )
        db.add_all([prep, snap, rev])
        db.flush()

        mv = ModelVersion(
            version_key="mv-ev-test",
            model_name="Inductive-GNN",
            architecture_version="v1",
            architecture_config={},
            config_sha256="d" * 64,
            checkpoint_uri="test://chk",
            checkpoint_sha256="e" * 64,
            preprocessing_version_id=prep.preprocessing_version_id,
            input_contract_version="c1",
            supported_inference_mode="inductive_batch_v1",
            recommended_threshold=0.75,
            threshold_source="validation",
            verification_at=datetime.now(timezone.utc),
            lifecycle_status="verified",
            provenance="real",
        )
        db.add(mv)
        db.flush()

        run = InferenceRun(
            model_version_id=mv.model_version_id,
            provenance="real",
            graph_snapshot_id=snap.graph_snapshot_id,
            threshold=0.75,
            requested_count=1,
            completed_count=1,
            status="completed",
        )
        db.add(run)
        db.flush()

        pred = FraudPrediction(
            inference_run_id=run.inference_run_id,
            review_id=rev.review_id,
            risk_score=0.8845,
            predicted_label=1,
        )
        db.add(pred)
        db.flush()

        # 1. Valid evidence record with all required fields
        now = datetime.now(timezone.utc)
        evidence = InductivePredictionEvidence(
            fraud_prediction_id=pred.fraud_prediction_id,
            graph_snapshot_id=snap.graph_snapshot_id,
            relation_schema_version="inductive-rur-rsr-rtr-v1",
            context_cutoff_at=now,
            neighbor_counts={"rur": 5, "rsr": 12, "rtr": 3},
            historic_review_ids=[101, 102, 103],
            stitched_graph_sha256="1" * 64,
            input_feature_sha256="2" * 64,
            embedding_sha256="3" * 64,
            bundle_manifest_sha256="4" * 64,
            provenance="real",
        )
        db.add(evidence)
        db.commit()

        # 2. One-to-one constraint: duplicate evidence for same prediction fails
        dup_evidence = InductivePredictionEvidence(
            fraud_prediction_id=pred.fraud_prediction_id,
            graph_snapshot_id=snap.graph_snapshot_id,
            relation_schema_version="inductive-rur-rsr-rtr-v1",
            context_cutoff_at=now,
            neighbor_counts={},
            historic_review_ids=[],
            stitched_graph_sha256="5" * 64,
            input_feature_sha256="6" * 64,
            embedding_sha256="7" * 64,
            bundle_manifest_sha256="8" * 64,
            provenance="real",
        )
        db.add(dup_evidence)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 3. Invalid SHA256 (uppercase or invalid length) fails check constraint
        bad_sha_evidence = InductivePredictionEvidence(
            fraud_prediction_id=pred.fraud_prediction_id,
            graph_snapshot_id=snap.graph_snapshot_id,
            relation_schema_version="inductive-rur-rsr-rtr-v1",
            context_cutoff_at=now,
            neighbor_counts={},
            historic_review_ids=[],
            stitched_graph_sha256="INVALID_UPPERCASE_SHA256" + "0" * 40,
            input_feature_sha256="2" * 64,
            embedding_sha256="3" * 64,
            bundle_manifest_sha256="4" * 64,
            provenance="real",
        )
        db.add(bad_sha_evidence)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
