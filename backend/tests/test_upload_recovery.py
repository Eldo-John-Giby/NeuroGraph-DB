"""Regression coverage for retrying a saved CSV and authentic text encoding."""
import sys

import pytest
from sqlalchemy import func, select

from app.models import BatchAnalysis, BatchAnalysisRow, Review
from app.services.inductive_yelpchi import BundleVerificationError, InductiveYelpChiRuntime


CSV = b"review_id,reviewer_id,product_id,rating,review_date,review_text\nnew-1,u-1,p-1,4,2026-10-20T09:00:00Z,Comfortable fit but the case is bulky.\n"


def test_reupload_recovers_saved_batch_without_duplicate_rows(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    first = client.post('/api/v1/batch-analyses', headers=headers,
                        data={"source_system": "csv-review-test"},
                        files={"file": ("reviews.csv", CSV, "text/csv")})
    second = client.post('/api/v1/batch-analyses', headers=headers,
                         data={"source_system": "csv-review-test"},
                         files={"file": ("reviews.csv", CSV, "text/csv")})
    assert first.status_code == second.status_code == 201
    assert first.json()['accepted_count'] == second.json()['accepted_count'] == 1
    assert second.json()['rejected_count'] == 0
    assert second.json()['batch_analysis_id'] == first.json()['batch_analysis_id']
    assert second.json()['reused_existing_batch'] is True
    with client._testing_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 1
        assert db.scalar(select(func.count()).select_from(BatchAnalysis)) == 1


def test_modified_csv_cannot_overwrite_existing_review(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    for content in (CSV, CSV.replace(b'Comfortable fit', b'Changed text')):
        response = client.post('/api/v1/batch-analyses', headers=headers,
                               data={"source_system": "csv-review-test"},
                               files={"file": ("reviews.csv", content, "text/csv")})
        assert response.status_code == 201
    assert response.json()['accepted_count'] == 0
    assert response.json()['rejected_count'] == 1
    with client._testing_session_factory() as db:
        assert db.scalar(select(Review.review_text)).startswith('Comfortable fit')


def test_another_uploader_can_analyze_identical_reviews_in_their_own_batch(client, reader_token, admin_token):
    def upload(token, content):
        response = client.post('/api/v1/batch-analyses',
                               headers={"Authorization": f"Bearer {token}"},
                               data={"source_system": "shared-csv"},
                               files={"file": ("reviews.csv", content, "text/csv")})
        assert response.status_code == 201
        return response.json()

    original = upload(admin_token, CSV)
    imported = upload(reader_token, CSV)
    assert imported['batch_analysis_id'] != original['batch_analysis_id']
    assert imported['accepted_count'] == 1 and imported['rejected_count'] == 0
    retried = upload(reader_token, CSV)
    assert retried['batch_analysis_id'] == imported['batch_analysis_id']
    headers = {"Authorization": f"Bearer {reader_token}"}
    assert client.get(f"/api/v1/batch-analyses/{original['batch_analysis_id']}/results", headers=headers).status_code == 404
    assert client.get(f"/api/v1/batch-analyses/{imported['batch_analysis_id']}/results", headers=headers).status_code == 200
    with client._testing_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 1
        receipts = db.scalars(select(BatchAnalysis).order_by(BatchAnalysis.batch_analysis_id)).all()
        assert receipts[0].requested_by_user_id != receipts[1].requested_by_user_id
        review = db.scalar(select(Review))
        assert review.submitted_by_user_id == receipts[0].requested_by_user_id
        assert list(db.scalars(select(BatchAnalysisRow.review_id))) == [review.review_id, review.review_id]


def test_line_endings_and_mixed_existing_new_rows_do_not_duplicate_reviews(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    for content in (CSV, CSV.replace(b'\n', b'\r\n'),
                    CSV + CSV.split(b'\n')[1].replace(b'new-1', b'new-2') + b'\n'):
        response = client.post('/api/v1/batch-analyses', headers=headers,
                               data={"source_system": "csv-format-test"},
                               files={"file": ("reviews.csv", content, "text/csv")})
        assert response.status_code == 201
        assert response.json()['rejected_count'] == 0
    assert response.json()['accepted_count'] == 2
    with client._testing_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 2


@pytest.mark.parametrize('old,new', [(b'u-1', b'u-2'), (b'p-1', b'p-2'), (b',4,', b',5,'),
                                      (b'2026-10-20', b'2026-10-21'), (b'Comfortable fit', b'Changed text')])
def test_reused_review_id_with_changed_fields_is_rejected(client, reader_token, old, new):
    headers = {"Authorization": f"Bearer {reader_token}"}
    for content in (CSV, CSV.replace(old, new)):
        response = client.post('/api/v1/batch-analyses', headers=headers,
                               data={"source_system": "csv-field-conflict"},
                               files={"file": ("reviews.csv", content, "text/csv")})
        assert response.status_code == 201
    assert response.json()['accepted_count'] == 0
    assert response.json()['rejected_count'] == 1
    with client._testing_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 1
        assert db.scalar(select(Review.review_text)) == 'Comfortable fit but the case is bulky.'


def test_unavailable_roberta_blocks_scoring_instead_of_random_vectors(monkeypatch):
    runtime = InductiveYelpChiRuntime()
    runtime._prep_config = {"text": {"model_name": "FacebookAI/roberta-base", "resolved_revision": "a" * 40}}
    monkeypatch.setitem(sys.modules, 'transformers', None)
    with pytest.raises(BundleVerificationError, match='pinned RoBERTa encoder could not be loaded'):
        runtime.encode_texts(['A new review requiring an actual text embedding.'])
    assert runtime._tokenizer is None
    assert runtime._hf_roberta is None
