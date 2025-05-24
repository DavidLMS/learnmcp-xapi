"""Tests for record_statement functionality."""

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
async def test_record_statement_success(test_client, mock_jwt_token):
    """Test successful statement recording."""
    # Mock LRS response
    respx.post("https://test-lrs.example.com/xAPI/statements").respond(
        200, json={"id": "test-statement-id"}
    )
    
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "record_xapi_statement",
            "params": {
                "verb": "practiced",
                "object_id": "https://example.com/activity/1",
                "level": 2
            }
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["result"]["id"] == "test-statement-id"


@respx.mock
async def test_record_statement_with_extras(test_client, mock_jwt_token):
    """Test statement recording with extras."""
    respx.post("https://test-lrs.example.com/xAPI/statements").respond(
        200, json={"id": "test-statement-id"}
    )
    
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "record_xapi_statement",
            "params": {
                "verb": "achieved",
                "object_id": "https://example.com/activity/2",
                "level": 85.5,
                "extras": {
                    "score_max": 100,
                    "comment": "Great work!"
                }
            }
        }
    )
    
    assert response.status_code == 200


async def test_record_statement_invalid_verb(test_client, mock_jwt_token):
    """Test statement recording with invalid verb."""
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "record_xapi_statement",
            "params": {
                "verb": "invalid_verb",
                "object_id": "https://example.com/activity/1"
            }
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert "Unknown verb" in result["error"]["message"]


async def test_record_statement_invalid_object_id(test_client, mock_jwt_token):
    """Test statement recording with invalid object ID."""
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "record_xapi_statement",
            "params": {
                "verb": "practiced",
                "object_id": "not-a-valid-iri"
            }
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert "valid IRI" in result["error"]["message"]


async def test_record_statement_no_auth(test_client):
    """Test statement recording without authentication."""
    response = test_client.post(
        "/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "record_xapi_statement",
            "params": {
                "verb": "practiced",
                "object_id": "https://example.com/activity/1"
            }
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == 401


@respx.mock
async def test_lrs_unavailable(test_client, mock_jwt_token):
    """Test handling of LRS unavailability."""
    respx.post("https://test-lrs.example.com/xAPI/statements").respond(503)
    
    response = test_client.post(
        "/rpc",
        headers={"Authorization": f"Bearer {mock_jwt_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "record_xapi_statement",
            "params": {
                "verb": "practiced",
                "object_id": "https://example.com/activity/1"
            }
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == 503