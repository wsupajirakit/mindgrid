import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mindgrid.core.errors import ApiError, install_error_handlers


def test_api_error_shape_and_code_rule() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise ApiError(409, "project.exists", "project exists", params={"name": "x"})

    @app.get("/typed")
    def typed(n: int) -> int:
        return n

    client = TestClient(app)
    assert client.get("/boom").json() == {
        "error": {"code": "project.exists", "message": "project exists", "params": {"name": "x"}}
    }
    bad = client.get("/typed?n=secret-value")
    assert bad.status_code == 422
    assert "secret-value" not in bad.text
    with pytest.raises(ValueError, match="dotted lowercase"):
        ApiError(400, "BadCode", "x")
