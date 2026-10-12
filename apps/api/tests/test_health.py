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


def test_readiness_checks_storage_and_sanitizes_failures():
    from unittest.mock import MagicMock

    from sqlalchemy.exc import SQLAlchemyError

    from app.account_routes import runtime_engine

    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = False
    app.dependency_overrides[runtime_engine] = lambda: engine
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
            assert response.status_code == 200 and response.json() == {"status": "ok"}
            assert "LIMIT 0" in str(connection.execute.call_args.args[0])
            connection.execute.return_value.scalar_one.return_value = True
            assert client.get("/ready").status_code == 503
            connection.execute.side_effect = SQLAlchemyError("private-dsn")
            response = client.get("/ready")
            assert response.status_code == 503 and "private-dsn" not in response.text
            assert client.get("/health").status_code == 200
    finally:
        app.dependency_overrides.clear()
