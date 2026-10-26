from unittest.mock import MagicMock

from sqlalchemy.exc import OperationalError

from app.core.database import DatabaseNotConfigured, get_db
from app.main import app


def test_liveness_does_not_access_database(client):
    def unexpected_db_access():
        raise AssertionError("Liveness must not access the database")

    app.dependency_overrides[get_db] = unexpected_db_access
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health").status_code == 200


def test_database_health_executes_query(client):
    session = MagicMock()
    app.dependency_overrides[get_db] = lambda: session
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
    assert str(session.execute.call_args.args[0]) == "SELECT 1"


def test_database_query_failure_is_sanitized(client):
    session = MagicMock()
    session.execute.side_effect = OperationalError("secret connection data", {}, Exception("secret"))
    app.dependency_overrides[get_db] = lambda: session
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}


def test_database_connection_failure_is_sanitized(client):
    def unavailable_db():
        raise OperationalError("secret", {}, Exception("password"))

    app.dependency_overrides[get_db] = unavailable_db
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}


def test_database_not_configured(client):
    def missing_db():
        raise DatabaseNotConfigured()

    app.dependency_overrides[get_db] = missing_db
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not configured"}


def test_allowed_cors_origin(client):
    response = client.options("/health", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unlisted_cors_origin(client):
    response = client.options("/health", headers={
        "Origin": "https://unlisted.example", "Access-Control-Request-Method": "GET"
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
