from sqlalchemy import select
from app.models import Review, ReviewFeedback, User


def test_feedback_crud_and_resolved_lock(client, reader_token, admin_token):
    reader = {'Authorization': 'Bearer ' + reader_token}
    admin = {'Authorization': 'Bearer ' + admin_token}
    with client._testing_session_factory() as db:
        review = Review(review_text='Shared evidence review', rating=4)
        db.add(review); db.commit(); review_id = review.review_id
    body = {'review_id': review_id, 'feedback_type': 'review_quality', 'comment': 'Please inspect context', 'ground_truth_label': None}
    response = client.post('/api/v1/feedback', json=body, headers=reader)
    assert response.status_code == 201
    item_id = response.json()['feedback_id']
    assert client.get('/api/v1/feedback?q=inspect&status=submitted', headers=reader).json()['total'] == 1
    assert client.patch(f'/api/v1/feedback/{item_id}', json={**body, 'comment': 'Updated reviewer context'}, headers=reader).status_code == 200
    assert client.post(f'/api/v1/feedback/{item_id}/resolve', json={'status': 'resolved'}, headers=reader).status_code == 403
    assert client.post(f'/api/v1/feedback/{item_id}/resolve', json={'status': 'resolved'}, headers=admin).json()['status'] == 'resolved'
    assert client.patch(f'/api/v1/feedback/{item_id}', json=body, headers=reader).status_code == 409
    assert client.delete(f'/api/v1/feedback/{item_id}', headers=reader).status_code == 409
    second = client.post('/api/v1/feedback', json=body, headers=reader).json()['feedback_id']
    assert client.delete(f'/api/v1/feedback/{second}', headers=reader).status_code == 204
    with client._testing_session_factory() as db:
        assert db.get(ReviewFeedback, second) is None
        assert db.get(Review, review_id).rating == 4


def test_feedback_privacy_validation_and_injection(client, reader_token, admin_token):
    reader = {'Authorization': 'Bearer ' + reader_token}
    admin = {'Authorization': 'Bearer ' + admin_token}
    with client._testing_session_factory() as db:
        admin_user = db.scalar(select(User).where(User.email == 'admin@example.edu'))
        review = Review(submitted_by_user_id=admin_user.user_id, rating=3)
        db.add(review); db.commit(); review_id = review.review_id
    body = {'review_id': review_id, 'feedback_type': 'other', 'comment': 'Private note'}
    assert client.post('/api/v1/feedback', json=body, headers=reader).status_code == 404
    item_id = client.post('/api/v1/feedback', json=body, headers=admin).json()['feedback_id']
    assert client.get('/api/v1/feedback', headers=reader).json()['total'] == 0
    assert client.delete(f'/api/v1/feedback/{item_id}', headers=reader).status_code == 404
    assert client.get('/api/v1/feedback?q=%27%20OR%201=1--', headers=admin).json()['total'] == 0
    assert client.get('/api/v1/feedback?limit=0', headers=reader).status_code == 422
    assert client.post('/api/v1/feedback', json={**body, 'comment': ''}, headers=admin).status_code == 422
    assert client.post(f'/api/v1/feedback/{item_id}/resolve', json={'status': 'unknown'}, headers=admin).status_code == 422
    assert client.get('/api/v1/database/summary', headers=reader).status_code == 403
