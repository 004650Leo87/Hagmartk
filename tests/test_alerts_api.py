from fastapi.testclient import TestClient

from backend.api.app import app


client = TestClient(app)


def test_unified_alerts_endpoint_is_paper_only():
    response = client.get('/api/alerts/recent?limit=10')
    assert response.status_code == 200
    payload = response.json()
    assert payload['timezone'] == 'America/Sao_Paulo'
    assert payload['paper_only'] is True
    assert payload['real_order_execution_enabled'] is False
    assert isinstance(payload['alerts'], list)


def test_unified_alerts_accepts_strategy_filter():
    for strategy in ('DVP', 'TC', 'ORB'):
        response = client.get(f'/api/alerts/recent?limit=5&strategy={strategy}')
        assert response.status_code == 200
        payload = response.json()
        assert all(row['strategy_key'] == strategy for row in payload['alerts'])
