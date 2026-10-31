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


@pytest.mark.parametrize('changed', [False, True])
def test_uploader_namespaces_are_isolated_even_with_identical_filename_and_ids(client, reader_token, admin_token, changed):
    def upload(token, content):
        response = client.post('/api/v1/batch-analyses',
                               headers={"Authorization": f"Bearer {token}"},
                               data={"source_system": "shared-csv"},
                               files={"file": ("reviews.csv", content, "text/csv")})
        assert response.status_code == 201
        return response.json()

    original = upload(admin_token, CSV)
    content = CSV.replace(b'Comfortable fit', b'A different review') if changed else CSV
    imported = upload(reader_token, content)
    assert imported['batch_analysis_id'] != original['batch_analysis_id']
    assert imported['accepted_count'] == 1 and imported['rejected_count'] == 0
    retried = upload(reader_token, content)
    assert retried['batch_analysis_id'] == imported['batch_analysis_id']
    headers = {"Authorization": f"Bearer {reader_token}"}
    assert client.get(f"/api/v1/batch-analyses/{original['batch_analysis_id']}/results", headers=headers).status_code == 404
    assert client.get(f"/api/v1/batch-analyses/{imported['batch_analysis_id']}/results", headers=headers).status_code == 200
    with client._testing_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 2
        receipts = db.scalars(select(BatchAnalysis).order_by(BatchAnalysis.batch_analysis_id)).all()
        assert receipts[0].requested_by_user_id != receipts[1].requested_by_user_id
        reviews = db.scalars(select(Review).order_by(Review.review_id)).all()
        assert reviews[0].source_system != reviews[1].source_system
        assert reviews[0].reviewer_id != reviews[1].reviewer_id
        assert reviews[0].product_id != reviews[1].product_id
        assert [r.submitted_by_user_id for r in reviews] == [b.requested_by_user_id for b in receipts]
        assert list(db.scalars(select(BatchAnalysisRow.review_id))) == [r.review_id for r in reviews]
    visible = client.get('/api/v1/reviews', headers=headers).json()['items']
    assert [r['review_id'] for r in visible] == [reviews[1].review_id]
    # Supplying another user's stored namespace cannot escape the owner prefix.
    spoof = client.post('/api/v1/batch-analyses', headers=headers,
                        data={'source_system': original['source_system']},
                        files={'file': ('reviews.csv', content, 'text/csv')})
    assert spoof.status_code == 201 and spoof.json()['accepted_count'] == 1
    assert spoof.json()['source_system'] != original['source_system']


def test_long_source_names_remain_bounded_and_distinct():
    from app.services.upload_namespace import upload_source
    labels = ['a' * 100, 'b' + 'a' * 99]
    sources = [upload_source(123, label) for label in labels]
    assert all(len(source) <= 100 for source in sources)
    assert sources[0] != sources[1]
    assert upload_source(123, 'a' * 85 + '-limited-authors').endswith('-limited-authors')


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
