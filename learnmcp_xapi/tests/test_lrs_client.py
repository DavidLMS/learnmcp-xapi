"""Tests for LRS client module with retry logic."""

import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock

from learnmcp_xapi.mcp.lrs_client import LRSClient, get_lrs_client
from learnmcp_xapi.config import Config


class TestLRSClient:
    """Test LRS client functionality and retry logic."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = MagicMock(spec=Config)
        config.LRS_ENDPOINT = "https://test-lrs.example.com"
        config.LRS_KEY = "test_key"
        config.LRS_SECRET = "test_secret"
        return config
    
    @pytest.fixture
    def lrs_client(self, mock_config):
        """Create LRS client instance for testing."""
        with patch('learnmcp_xapi.mcp.lrs_client.config', mock_config):
            return LRSClient()
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_success(self, lrs_client):
        """Test successful statement posting."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.example.com/xapi/statements").respond(
            201, json={"id": "test-statement-id"}
        )
        
        result = await lrs_client.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_retry_on_server_error(self, lrs_client):
        """Test retry logic on server errors."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # First two requests fail with 500, third succeeds
        respx.post("https://test-lrs.example.com/xapi/statements").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(201, json={"id": "test-statement-id"})
            ]
        )
        
        result = await lrs_client.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @respx.mock
    async def test_post_statement_max_retries_exceeded(self, lrs_client):
        """Test that max retries are respected."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # All requests fail with 500
        respx.post("https://test-lrs.example.com/xapi/statements").respond(500)
        
        with pytest.raises(httpx.HTTPStatusError):
            await lrs_client.post_statement(statement)
    
    @respx.mock
    async def test_post_statement_no_retry_on_client_error(self, lrs_client):
        """Test that client errors (4xx) are not retried."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.example.com/xapi/statements").respond(
            400, json={"error": "bad request"}
        )
        
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await lrs_client.post_statement(statement)
        
        assert exc_info.value.response.status_code == 400
    
    @respx.mock
    async def test_get_statements_success(self, lrs_client):
        """Test successful statements retrieval."""
        respx.get("https://test-lrs.example.com/xapi/statements").respond(
            200, json={
                "statements": [
                    {"id": "stmt1", "actor": {"name": "test"}},
                    {"id": "stmt2", "actor": {"name": "test"}}
                ]
            }
        )
        
        result = await lrs_client.get_statements(actor_uuid="test-uuid")
        assert len(result) == 2
        assert result[0]["id"] == "stmt1"
    
    @respx.mock
    async def test_get_statements_with_filters(self, lrs_client):
        """Test statements retrieval with query filters."""
        respx.get("https://test-lrs.example.com/xapi/statements").respond(
            200, json={"statements": []}
        )
        
        from datetime import datetime
        
        await lrs_client.get_statements(
            actor_uuid="test-uuid",
            verb="http://example.com/verb",
            object_id="http://example.com/activity",
            since=datetime.fromisoformat("2023-01-01T00:00:00+00:00"),
            until=datetime.fromisoformat("2023-12-31T23:59:59+00:00"),
            limit=10
        )
        
        # Verify request was made with correct query parameters
        request = respx.calls[0].request
        assert "agent=" in str(request.url)
        assert "verb=" in str(request.url)
        assert "activity=" in str(request.url)
        assert "since=" in str(request.url)
        assert "until=" in str(request.url)
        assert "limit=" in str(request.url)
    
    @respx.mock
    async def test_get_statements_retry_on_server_error(self, lrs_client):
        """Test retry logic for GET requests."""
        # First request fails, second succeeds
        respx.get("https://test-lrs.example.com/xapi/statements").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(200, json={"statements": []})
            ]
        )
        
        result = await lrs_client.get_statements(actor_uuid="test-uuid")
        assert result == []
    
    @respx.mock
    async def test_connection_timeout_retry(self, lrs_client):
        """Test retry on connection timeouts."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # First request times out, second succeeds
        respx.post("https://test-lrs.example.com/xapi/statements").mock(
            side_effect=[
                httpx.TimeoutException("Connection timeout"),
                httpx.Response(201, json={"id": "test-statement-id"})
            ]
        )
        
        result = await lrs_client.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @respx.mock
    async def test_request_timeout_max_retries(self, lrs_client):
        """Test that timeouts respect max retry limit."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # All requests timeout
        respx.post("https://test-lrs.example.com/xapi/statements").mock(
            side_effect=httpx.TimeoutException("Connection timeout")
        )
        
        with pytest.raises(httpx.TimeoutException):
            await lrs_client.post_statement(statement)
    
    def test_authentication_headers(self, lrs_client):
        """Test that authentication headers are correctly set."""
        headers = lrs_client.headers
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["X-Experience-API-Version"] == "1.0.3"
        assert headers["Content-Type"] == "application/json"


class TestGetLRSClient:
    """Test LRS client factory function."""
    
    @patch('learnmcp_xapi.mcp.lrs_client.config')
    def test_get_lrs_client_returns_singleton(self, mock_config):
        """Test that get_lrs_client returns the same instance."""
        mock_config.LRS_ENDPOINT = "https://test.com"
        mock_config.LRS_KEY = "key"
        mock_config.LRS_SECRET = "secret"
        
        client1 = get_lrs_client()
        client2 = get_lrs_client()
        
        assert client1 is client2
    
    @patch('learnmcp_xapi.mcp.lrs_client.config')
    def test_get_lrs_client_creates_instance(self, mock_config):
        """Test that get_lrs_client creates LRSClient instance."""
        mock_config.LRS_ENDPOINT = "https://test.com"
        mock_config.LRS_KEY = "key"
        mock_config.LRS_SECRET = "secret"
        
        client = get_lrs_client()
        
        assert isinstance(client, LRSClient)