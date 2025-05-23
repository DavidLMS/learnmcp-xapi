"""Tests for get_statements functionality."""

import pytest
from unittest.mock import patch

import respx
from fastapi.testclient import TestClient

from ..main import app
from ..config import config


@pytest.fixture
def test_client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token for testing."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3YjBjNGYzZS0wZDdiLTQxYzYtYjhhMS0xZWRhYzY0YjRiM2EiLCJhdWQiOiJsZWFybm1jcC14YXBpIiwiZXhwIjoxNzUxMzQxMjAwfQ.test"


@pytest.fixture(autouse=True)
def setup_test_config():
    """Setup test configuration."""
    with patch.object(config, 'LRS_ENDPOINT', 'https://test-lrs.example.com'):
        with patch.object(config, 'LRS_KEY', 'test_key'):
            with patch.object(config, 'LRS_SECRET', 'test_secret'):
                with patch.object(config, 'JWT_ALGORITHM', 'HS256'):
                    with patch.object(config, 'JWT_SECRET', 'test_secret'):
                        yield


@pytest.fixture(autouse=True)
def mock_jwt_verify():
    """Mock JWT verification."""
    with patch('learnmcp_xapi.mcp.auth.verify_jwt') as mock:
        mock.return_value = "7b0c4f3e-0d7b-41c6-b8a1-1edac64b4b3a"
        yield mock


@respx.mock
async def test_get_statements_success(test_client, mock_jwt_token):
    """Test successful statement retrieval."""
    mock_statements = {
        "statements": [
            {
                "id": "stmt-1",
                "actor": {
                    "account": {
                        "homePage": "urn:learnmcp",
                        "name": "7b0c4f3e-0d7b-41c6-b8a1-1edac64b4b3a"
                    }
                },
                "verb": {
                    "id": "http://adlnet.gov/expapi/verbs/practiced",
                    "display": {"en-US": "practiced"}
                },
                "object": {"id": "https://example.com/activity/1"},
                "timestamp": "2023-12-01T10:00:00Z"
            }
        ]
    }
    
    respx.get("https://test-lrs.example.com/xAPI/statements").respond(
        200, json=mock_statements
    )
    
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "get_xapi_statements",
            "params": {}
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert len(result["result"]) == 1
    assert result["result"][0]["id"] == "stmt-1"


@respx.mock
async def test_get_statements_with_filters(test_client, mock_jwt_token):
    """Test statement retrieval with filters."""
    respx.get("https://test-lrs.example.com/xAPI/statements").respond(
        200, json={"statements": []}
    )
    
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "get_xapi_statements",
            "params": {
                "verb": "practiced",
                "object_id": "https://example.com/activity/1",
                "since": "2023-12-01T00:00:00Z",
                "until": "2023-12-31T23:59:59Z",
                "limit": 10
            }
        }
    )
    
    assert response.status_code == 200


async def test_get_statements_invalid_verb(test_client, mock_jwt_token):
    """Test statement retrieval with invalid verb."""
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "get_xapi_statements",
            "params": {
                "verb": "invalid_verb"
            }
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert "Unknown verb" in result["error"]["message"]


async def test_get_statements_invalid_date(test_client, mock_jwt_token):
    """Test statement retrieval with invalid date format."""
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "get_xapi_statements",
            "params": {
                "since": "not-a-date"
            }
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert "Invalid since datetime" in result["error"]["message"]


async def test_list_verbs(test_client):
    """Test listing available verbs."""
    response = test_client.post(
        "/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "list_available_verbs",
            "params": {}
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "experienced" in result["result"]
    assert "practiced" in result["result"]
    assert "achieved" in result["result"]
    assert "mastered" in result["result"]
    assert result["result"]["practiced"] == "http://adlnet.gov/expapi/verbs/practiced"