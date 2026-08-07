import pytest
import aiohttp
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from genspark_cli.server import handle_models, handle_health, ClientPool
from genspark_cli.models import list_models

@pytest.fixture
def mock_app():
    app = web.Application()
    app["client_pool"] = ClientPool()
    return app

async def test_health_route(mock_app):
    """Layer 2: Verify /health API Route response structure."""
    request = make_mocked_request("GET", "/health", app=mock_app)
    response = await handle_health(request)
    
    assert response.status == 200
    import json
    data = json.loads(response.text)
    assert data["status"] == "ok"
    assert "backend" in data
    assert "chat_models" in data
    assert "image_models" in data

async def test_models_route(mock_app):
    """Layer 2: Verify /v1/models API Route response structure (OpenAI compatible)."""
    request = make_mocked_request("GET", "/v1/models", app=mock_app)
    response = await handle_models(request)
    
    assert response.status == 200
    import json
    data = json.loads(response.text)
    assert data["object"] == "list"
    assert len(data["data"]) == len(list_models())
    assert data["data"][0]["object"] == "model"
