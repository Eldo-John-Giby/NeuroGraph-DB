from datetime import datetime, timedelta, timezone

from sqlalchemy import event
from app.models import GraphSnapshot, GraphSnapshotReview, Review
from app.services.batch_csv import BatchReviewInput, PermittedHistoricContext
from app.services.batch_graph import LabelFreeBatchRelationBuilder, load_permitted_historic_context


def test_batch_relations_include_uploaded_nodes_and_are_label_free():
    now = datetime(2025, 1, 10, tzinfo=timezone.utc)
    historic = BatchReviewInput(100, 1, 5, 5, now - timedelta(days=1), "history")
    uploaded = [
        BatchReviewInput(1, 1, 5, 5, now, "uploaded by same reviewer/rating"),
        BatchReviewInput(2, 2, 5, 2, now + timedelta(days=60), "another uploaded review"),
    ]
    context = PermittedHistoricContext(7, "train", [historic])
    edges = LabelFreeBatchRelationBuilder().build(uploaded, historic_context=context)
    assert (0, 2) in edges.rur and (2, 0) in edges.rur  # uploaded review to permitted history
    assert (0, 2) in edges.rsr
    assert (1, 2) not in edges.rsr  # same product, different rating
    assert (0, 2) in edges.rtr and (2, 0) in edges.rtr
    assert (0, 1) not in edges.rtr  # same product but over 30 days
    assert edges.relation_schema_version == "batch-rur-rsr-rtr-v1"
    assert "ground_truth_label" not in BatchReviewInput.__dataclass_fields__


def test_history_loader_selects_only_explicit_snapshot_split_without_label_columns(client):
    # The test is intentionally an actual SQL-backed load. A labelled review is
    # stored, but the label is not projected into the context passed to builders.
    with client._testing_session_factory() as db:
        snapshot = GraphSnapshot(snapshot_key="batch-context-test", dataset_name="test",
                                 dataset_sha256="a" * 64, artifact_uri="test://snapshot",
                                 artifact_sha256="b" * 64, graph_builder_version="test-v1",
                                 relation_schema_version="test-v1", split_protocol_key="test-split",
                                 node_count=2, batch_context_permitted=True,
                                 context_scope_key="batch-context-scope")
        db.add(snapshot)
        db.flush()
        train = Review(source_system="test", source_review_key="history-train", reviewer_id=None,
                       rating=5, reviewed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                       review_text="train", ground_truth_label=1)
        omitted = Review(source_system="test", source_review_key="history-test", reviewer_id=None,
                         rating=1, reviewed_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                         review_text="test", ground_truth_label=0)
        # Need reviewer/product ids for relation input; create valid source records.
        from app.models import Product, Reviewer
        reviewer = Reviewer(source_system="test", external_reviewer_key="reviewer")
        product = Product(source_system="test", external_product_key="product")
        db.add_all([reviewer, product])
        db.flush()
        train.reviewer_id = omitted.reviewer_id = reviewer.reviewer_id
        train.product_id = omitted.product_id = product.product_id
        db.add_all([train, omitted])
        db.flush()
        db.add_all([
            GraphSnapshotReview(graph_snapshot_id=snapshot.graph_snapshot_id, review_id=train.review_id, split="train"),
            GraphSnapshotReview(graph_snapshot_id=snapshot.graph_snapshot_id, review_id=omitted.review_id, split="test"),
        ])
        db.commit()
        captured_sql = []
        def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            captured_sql.append(statement.lower())
        event.listen(db.bind, "before_cursor_execute", capture)
        loaded = load_permitted_historic_context(db, snapshot.graph_snapshot_id, split="train")
        event.remove(db.bind, "before_cursor_execute", capture)
        assert loaded.split == "train"
        assert [row.review_id for row in loaded.reviews] == [train.review_id]
        assert "ground_truth_label" not in loaded.reviews[0].__dataclass_fields__
        history_select = next(sql for sql in captured_sql if sql.lstrip().startswith("select"))
        assert "ground_truth_label" not in history_select
        assert "label_source" not in history_select
        uploaded_row = Review(source_system="batch", source_review_key="uploaded-1",
                              reviewer_id=reviewer.reviewer_id, product_id=product.product_id,
                              rating=5, reviewed_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
                              review_text="uploaded review")
        db.add(uploaded_row)
        db.flush()
        uploaded_input = BatchReviewInput(uploaded_row.review_id, uploaded_row.reviewer_id,
                                          uploaded_row.product_id, uploaded_row.rating,
                                          uploaded_row.reviewed_at.replace(tzinfo=timezone.utc),
                                          uploaded_row.review_text)
        edges = LabelFreeBatchRelationBuilder().build([uploaded_input], historic_context=loaded)
        assert edges.rur == ((0, 1), (1, 0))
        assert edges.rsr == ((0, 1), (1, 0))
        assert edges.rtr == ((0, 1), (1, 0))
