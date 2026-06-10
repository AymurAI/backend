import pytest
from fastapi.testclient import TestClient

from aymurai.api.main import api
from aymurai.settings import settings


@pytest.fixture(scope="function")
def client(tmp_path, monkeypatch):
    # Setup a fake frontend build
    frontend_dir = tmp_path / "frontend-dist"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<html><body>SPA</body></html>")
    (frontend_dir / "logo.png").write_bytes(b"fakeimg")
    monkeypatch.setattr(settings, "FRONTEND_DIST_DIR", str(frontend_dir))
    with TestClient(api) as c:
        yield c


def test_serves_index_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "SPA" in r.text
    assert r.headers["content-type"].startswith("text/html")


def test_serves_static_asset(client):
    r = client.get("/logo.png")
    assert r.status_code == 200
    assert r.content == b"fakeimg"
    assert (
        "image" in r.headers["content-type"]
        or r.headers["content-type"] == "application/octet-stream"
    )


def test_fallback_to_index_for_spa_route(client):
    r = client.get("/some/spa/route")
    assert r.status_code == 200
    assert "SPA" in r.text


def test_redirects_legacy_app_prefix_to_lowercase_feature_route(client):
    r = client.get("/app/ANONYMIZER/validation", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/anonymizer/validation"


def test_redirects_uppercase_feature_route_to_lowercase(client):
    r = client.get("/DATA_SET/onboarding", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/data_set/onboarding"


def test_api_healthcheck_is_available_under_api_prefix(client):
    r = client.get("/api/server/healthcheck")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_unknown_api_route_does_not_fallback_to_spa(client):
    r = client.get("/api/no-existe")
    assert r.status_code == 404
    assert r.json()["detail"] == "API route not found."


def test_404_for_missing_asset(client):
    r = client.get("/missing.png")
    assert r.status_code == 404
    assert r.json()["detail"] == "Frontend asset not found."


def test_404_for_path_traversal(client):
    r = client.get("/%2e%2e/%2e%2e/etc/passwd")
    assert r.status_code == 404
    assert r.json()["detail"] == "Frontend asset not found."


@pytest.mark.parametrize(
    "path",
    [
        "/anonymizer/no-existe",
        "/datapublic/no-existe",
        "/database/no-existe",
        "/docs",
        "/document-extract",
        "/misc/no-existe",
        "/openapi.json",
        "/redoc",
        "/server/no-existe",
    ],
)
def test_does_not_fallback_to_spa_for_api_prefixes(client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert r.json()["detail"] == "API route not found."
