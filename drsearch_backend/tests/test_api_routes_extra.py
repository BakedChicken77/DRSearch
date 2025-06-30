import urllib.parse

from fastapi.testclient import TestClient  # type: ignore


def test_file_proxy_unauthorized_path(fastapi_client: TestClient):
    """Accessing an absolute path outside *BASE_DIR* should yield **403**."""
    # URL-encode an absolute path (e.g. "/etc/passwd") so that the router decodes it first.
    abs_path = urllib.parse.quote("/etc/passwd", safe="")
    resp = fastapi_client.get(f"/files/{abs_path}")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access to this file is forbidden"