from fastapi.testclient import TestClient

from app.main import app


def test_health_is_available_without_external_services() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_openapi_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    output = schema["paths"]["/health"]["get"]["responses"]["200"]
    assert output["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthResponse"
    }
    health = schema["components"]["schemas"]["HealthResponse"]
    assert health["required"] == ["status"]
    assert health["properties"]["status"]["const"] == "ok"
