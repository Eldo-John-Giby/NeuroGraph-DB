from sqlalchemy import select

from app.models import BatchAnalysis

CSV = b"review_id,reviewer_id,product_id,rating,review_date,review_text\nr1,u1,p1,4,2026-10-20,A comfortable pair of headphones.\n"


def upload(client, token, filename="headphones.csv", content=CSV):
    response = client.post('/api/v1/batch-analyses', headers={'Authorization': f'Bearer {token}'},
                           data={'source_system': 'history-test'}, files={'file': (filename, content, 'text/csv')})
    assert response.status_code == 201
    return response.json()


def test_history_is_private_by_default_even_for_admins(client, reader_token, admin_token):
    reader_batch = upload(client, reader_token)
    admin_batch = upload(client, admin_token, 'admin.csv', CSV.replace(b'r1,', b'r2,'))
    for token, expected in [(reader_token, reader_batch), (admin_token, admin_batch)]:
        data = client.get('/api/v1/batch-analyses', headers={'Authorization': f'Bearer {token}'}).json()
        assert data['total'] == 1
        assert [row['batch_analysis_id'] for row in data['items']] == [expected['batch_analysis_id']]
    headers = {'Authorization': f'Bearer {reader_token}'}
    assert client.get('/api/v1/batch-analyses?scope=all', headers=headers).status_code == 403
    for suffix in ['', '/results', '/graph']:
        method = client.post if suffix == '/graph' else client.get
        assert method(f"/api/v1/batch-analyses/{admin_batch['batch_analysis_id']}{suffix}", headers=headers).status_code == 404
    data = client.get('/api/v1/batch-analyses?scope=all', headers={'Authorization': f'Bearer {admin_token}'}).json()
    assert data['total'] == 2
    reader_reviews = client.get('/api/v1/reviews?source_system=history-test', headers={'Authorization': f'Bearer {reader_token}'}).json()
    assert [r['source_review_key'] for r in reader_reviews['items']] == ['r1']
    admin_reviews = client.get('/api/v1/reviews?source_system=history-test', headers={'Authorization': f'Bearer {admin_token}'}).json()
    private_review = next(r for r in admin_reviews['items'] if r['source_review_key'] == 'r2')
    assert client.get(f"/api/v1/reviews/{private_review['review_id']}/predictions", headers={'Authorization': f'Bearer {reader_token}'}).status_code == 404


def test_saved_filename_search_status_and_pagination(client, reader_token):
    first = upload(client, reader_token, 'first.csv')
    second = upload(client, reader_token, 'second_100%.csv', CSV.replace(b'r1,', b'r2,'))
    headers = {'Authorization': f'Bearer {reader_token}'}
    page = client.get('/api/v1/batch-analyses?limit=1&offset=1', headers=headers).json()
    assert page['total'] == 2 and page['items'][0]['batch_analysis_id'] == first['batch_analysis_id']
    data = client.get('/api/v1/batch-analyses', params={'q': '100%', 'status': 'blocked'}, headers=headers).json()
    assert data['total'] == 1 and data['summary']['submitted_rows'] == 1
    assert data['items'][0]['source_filename'] == 'second_100%.csv'
    assert data['items'][0]['batch_analysis_id'] == second['batch_analysis_id']
    assert client.get('/api/v1/batch-analyses?status=completed', headers=headers).json()['total'] == 0


def test_old_receipt_gets_filename_on_retry_without_duplicate_import(client, reader_token):
    batch = upload(client, reader_token)
    with client._testing_session_factory() as db:
        db.scalar(select(BatchAnalysis)).source_filename = None
        db.commit()
    retry = upload(client, reader_token, '../private/original.csv')
    assert retry['batch_analysis_id'] == batch['batch_analysis_id']
    assert retry['source_filename'] == 'original.csv'
    assert retry['reused_existing_batch']


def test_inductive_status_uses_verified_bundle_metrics(client, reader_token, inductive_bundle):
    status = client.get('/api/v1/verified-inductive/status', headers={'Authorization': f'Bearer {reader_token}'}).json()
    assert status['available'] and status['reproduction_verified']
    assert status['evaluation_protocol'] == 'inductive_temporal_replay'
    assert status['metrics']['roc_auc'] == 0.8104861254551642
    assert status['manifest_sha256'] == '9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd'


def test_inductive_status_fails_closed_when_bundle_is_unavailable(client, reader_token, monkeypatch):
    import app.services.inductive_yelpchi as service
    monkeypatch.setattr(service, 'get_inductive_runtime', lambda: (_ for _ in ()).throw(RuntimeError('missing bundle')))
    status = client.get('/api/v1/verified-inductive/status', headers={'Authorization': f'Bearer {reader_token}'}).json()
    assert status['available'] is False
    assert 'metrics' not in status


def test_legacy_receipt_retry_is_preserved_only_for_its_original_owner(client, reader_token, admin_token):
    original = upload(client, reader_token)
    with client._testing_session_factory() as db:
        db.get(BatchAnalysis, original['batch_analysis_id']).source_system = 'history-test'
        db.commit()
    retried = upload(client, reader_token)
    assert retried['batch_analysis_id'] == original['batch_analysis_id']
    assert retried['reused_existing_batch']
    separate = upload(client, admin_token)
    assert separate['batch_analysis_id'] != original['batch_analysis_id']
    assert separate['source_system'] != 'history-test'
