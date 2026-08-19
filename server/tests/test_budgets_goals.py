def test_budget_create_update_delete(client, auth_headers):
    created = client.post("/api/budgets", headers=auth_headers, json={"category": "Food & Dining", "limit": 500})
    assert created.status_code == 201
    budget_id = created.get_json()["id"]

    updated = client.patch(f"/api/budgets/{budget_id}", headers=auth_headers, json={"limit": 650})
    assert updated.status_code == 200
    assert updated.get_json()["limit"] == 650

    deleted = client.delete(f"/api/budgets/{budget_id}", headers=auth_headers)
    assert deleted.status_code == 200


def test_rejects_oversized_budget(client, auth_headers):
    response = client.post("/api/budgets", headers=auth_headers, json={
        "category": "Housing", "limit": 1_000_000_000
    })
    assert response.status_code == 400
    assert "999,999,999.99" in response.get_json()["error"]


def test_goal_contribution_and_delete(client, auth_headers):
    created = client.post("/api/goals", headers=auth_headers, json={"name": "Emergency fund", "target": 5000, "saved": 1000})
    assert created.status_code == 201
    goal_id = created.get_json()["id"]

    contributed = client.post(f"/api/goals/{goal_id}/contribute", headers=auth_headers, json={"amount": 250})
    assert contributed.status_code == 200
    assert contributed.get_json()["saved"] == 1250

    updated = client.patch(f"/api/goals/{goal_id}", headers=auth_headers, json={"name": "Emergency reserve", "target": 6000})
    assert updated.status_code == 200
    assert updated.get_json()["name"] == "Emergency reserve"

    deleted = client.delete(f"/api/goals/{goal_id}", headers=auth_headers)
    assert deleted.status_code == 200


def test_rejects_oversized_goal_values(client, auth_headers):
    target = client.post("/api/goals", headers=auth_headers, json={
        "name": "Moon fund", "target": 1_000_000_000, "saved": 0
    })
    assert target.status_code == 400

    saved = client.post("/api/goals", headers=auth_headers, json={
        "name": "Moon fund", "target": 5000, "saved": 1_000_000_000
    })
    assert saved.status_code == 400


def test_rejects_oversized_goal_contribution(client, auth_headers):
    created = client.post("/api/goals", headers=auth_headers, json={"name": "Emergency fund", "target": 5000, "saved": 1000})
    goal_id = created.get_json()["id"]

    response = client.post(f"/api/goals/{goal_id}/contribute", headers=auth_headers, json={"amount": 1_000_000_000})
    assert response.status_code == 400
    assert "999,999,999.99" in response.get_json()["error"]
