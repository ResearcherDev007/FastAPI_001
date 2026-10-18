"""
Automated tests. Run with:  pytest -v
TestClient calls the API in-process - no server needs to be running.
These same tests will run automatically in the GitHub CI pipeline.
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Hello from FastAPI!"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_path_parameter():
    response = client.get("/hello/Elie")
    assert response.json() == {"message": "Hello, Elie!"}


def test_query_parameters():
    response = client.get("/add", params={"a": 3, "b": 4})
    assert response.json()["result"] == 7


def test_query_validation_error():
    response = client.get("/add", params={"a": "abc", "b": 1})
    assert response.status_code == 422


def test_calculate_divide():
    response = client.get("/calculate", params={"a": 10, "b": 3, "operation": "divide", "precision": 3})
    assert response.json()["result"] == 3.333


def test_calculate_divide_by_zero():
    response = client.get("/calculate", params={"a": 1, "b": 0, "operation": "divide"})
    assert response.status_code == 400


def test_item_crud():
    created = client.post("/items", json={"name": "Laptop", "price": 500, "quantity": 2})
    assert created.status_code == 201
    item = created.json()
    assert item["total"] == 1000

    assert client.get(f"/items/{item['id']}").json()["name"] == "Laptop"

    updated = client.put(f"/items/{item['id']}", json={"name": "Laptop", "price": 400, "quantity": 2})
    assert updated.json()["total"] == 800

    assert client.delete(f"/items/{item['id']}").status_code == 204
    assert client.get(f"/items/{item['id']}").status_code == 404


def test_item_validation_error():
    response = client.post("/items", json={"name": "", "price": -5})
    assert response.status_code == 422
