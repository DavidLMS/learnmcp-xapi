"""Tests for LRS SQL plugin (legacy LRS client functionality)."""

import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock

from learnmcp_xapi.plugins.lrsql import LRSSQLPlugin


class TestLRSSQLPlugin:
    """Test LRS SQL plugin functionality and retry logic."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        return {
            "endpoint": "https://test-lrs.example.com",
            "key": "test_key",
            "secret": "test_secret",
            "timeout": 30,
            "retry_attempts": 3
        }
    
    @pytest.fixture
    def lrs_plugin(self, mock_config):
        """Create LRS SQL plugin instance for testing."""
        return LRSSQLPlugin(mock_config)
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_success(self, lrs_plugin):
        """Test successful statement posting."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.example.com/xapi/statements").respond(
            201, json={"id": "test-statement-id"}
        )
        
        result = await lrs_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_list_response(self, lrs_plugin):
        """Test statement posting with list response."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.example.com/xapi/statements").respond(
            201, json=["test-statement-id"]
        )
        
        result = await lrs_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
        assert result["stored"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_retry_on_server_error(self, lrs_plugin):
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
        
        result = await lrs_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_max_retries_exceeded(self, lrs_plugin):
        """Test that max retries are respected."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # All requests fail with 500
        respx.post("https://test-lrs.example.com/xapi/statements").respond(500)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await lrs_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_no_retry_on_client_error(self, lrs_plugin):
        """Test that client errors (4xx) are not retried."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.example.com/xapi/statements").respond(
            400, json={"error": "bad request"}
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await lrs_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503  # Converted to service unavailable
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_success(self, lrs_plugin):
        """Test successful statements retrieval."""
        respx.get("https://test-lrs.example.com/xapi/statements").respond(
            200, json={
                "statements": [
                    {"id": "stmt1", "actor": {"name": "test"}, "timestamp": "2023-01-02T00:00:00Z"},
                    {"id": "stmt2", "actor": {"name": "test"}, "timestamp": "2023-01-01T00:00:00Z"}
                ]
            }
        )
        
        result = await lrs_plugin.get_statements(actor_uuid="test-uuid")
        assert len(result) == 2
        # Should be sorted by timestamp descending
        assert result[0]["id"] == "stmt1"
        assert result[1]["id"] == "stmt2"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_with_filters(self, lrs_plugin):
        """Test statements retrieval with query filters."""
        respx.get("https://test-lrs.example.com/xapi/statements").respond(
            200, json={"statements": []}
        )
        
        from datetime import datetime
        
        await lrs_plugin.get_statements(
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
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_retry_on_server_error(self, lrs_plugin):
        """Test retry logic for GET requests."""
        # First request fails, second succeeds
        respx.get("https://test-lrs.example.com/xapi/statements").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(200, json={"statements": []})
            ]
        )
        
        result = await lrs_plugin.get_statements(actor_uuid="test-uuid")
        assert result == []
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_timeout_retry(self, lrs_plugin):
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
        
        result = await lrs_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_request_timeout_max_retries(self, lrs_plugin):
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
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await lrs_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    def test_authentication_headers(self, lrs_plugin):
        """Test that authentication headers are correctly set."""
        headers = lrs_plugin.headers
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["X-Experience-API-Version"] == "1.0.3"
        assert headers["Content-Type"] == "application/json"
    
    def test_config_validation(self):
        """Test plugin configuration validation."""
        # Valid config
        valid_config = {
            "endpoint": "https://example.com",
            "key": "test_key",
            "secret": "test_secret"
        }
        plugin = LRSSQLPlugin(valid_config)
        assert plugin.config.key == "test_key"
        
        # Missing key
        with pytest.raises(Exception):  # Should raise validation error
            LRSSQLPlugin({
                "endpoint": "https://example.com",
                "secret": "test_secret"
            })
    
    @pytest.mark.asyncio
    async def test_close_client(self, lrs_plugin):
        """Test closing HTTP client."""
        await lrs_plugin.close()
        # Should not raise any exceptions


class TestLRSSQLPluginConfig:
    """Test LRS SQL plugin configuration model."""
    
    def test_valid_config_creation(self):
        """Test valid configuration creation."""
        from learnmcp_xapi.plugins.lrsql import LRSSQLConfig
        
        config = LRSSQLConfig(
            endpoint="https://lrsql.example.com",
            key="test_key",
            secret="test_secret",
            timeout=60,
            retry_attempts=5
        )
        
        assert config.endpoint == "https://lrsql.example.com"
        assert config.key == "test_key"
        assert config.secret.get_secret_value() == "test_secret"
        assert config.timeout == 60
        assert config.retry_attempts == 5
    
    def test_config_with_env_prefix(self):
        """Test configuration with environment prefix."""
        import os
        from learnmcp_xapi.plugins.lrsql import LRSSQLConfig
        
        env_vars = {
            "LRSQL_ENDPOINT": "https://env.example.com",
            "LRSQL_KEY": "env_key",
            "LRSQL_SECRET": "env_secret"
        }
        
        with patch.dict(os.environ, env_vars):
            # This would be loaded by the plugin's load_config_from_env method
            config_dict = LRSSQLPlugin.load_config_from_env("lrsql")
            
            assert config_dict["endpoint"] == "https://env.example.com"
            assert config_dict["key"] == "env_key"
            assert config_dict["secret"] == "env_secret"


# Backward compatibility test
class TestLegacyLRSClientCompatibility:
    """Test that the plugin system maintains compatibility with legacy LRS client usage."""
    
    @pytest.mark.asyncio
    async def test_plugin_matches_legacy_behavior(self):
        """Test that plugin behavior matches legacy LRS client."""
        # This test ensures that moving from lrs_client to lrsql plugin
        # doesn't break existing functionality
        
        config = {
            "endpoint": "https://test.example.com",
            "key": "test_key",
            "secret": "test_secret",
            "timeout": 30,
            "retry_attempts": 3
        }
        
        plugin = LRSSQLPlugin(config)
        
        # Test basic properties that legacy code might depend on
        assert hasattr(plugin, 'client')
        assert hasattr(plugin, 'headers')
        assert hasattr(plugin, 'post_statement')
        assert hasattr(plugin, 'get_statements')
        assert hasattr(plugin, 'close')
        
        # Test header format matches legacy
        assert plugin.headers["X-Experience-API-Version"] == "1.0.3"
        assert plugin.headers["Content-Type"] == "application/json"
        assert "Authorization" in plugin.headers