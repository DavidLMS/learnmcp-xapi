"""Tests for LRS SQL plugin."""

import pytest
import respx
import httpx
from unittest.mock import patch

from learnmcp_xapi.plugins.lrsql import LRSSQLPlugin, LRSSQLConfig


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
    def lrsql_plugin(self, mock_config):
        """Create LRS SQL plugin instance for testing."""
        return LRSSQLPlugin(mock_config)
    
    def test_plugin_metadata(self):
        """Test plugin metadata is correct."""
        assert LRSSQLPlugin.name == "lrsql"
        assert "SQLite-based" in LRSSQLPlugin.description
        assert LRSSQLPlugin.version == "1.0.0"
    
    def test_config_model(self):
        """Test plugin returns correct config model."""
        assert LRSSQLPlugin.get_config_model() == LRSSQLConfig
    
    def test_config_validation_success(self):
        """Test successful configuration validation."""
        config = {
            "endpoint": "https://test.example.com",
            "key": "test_key",
            "secret": "test_secret"
        }
        plugin = LRSSQLPlugin(config)
        plugin.validate_config()  # Should not raise
    
    def test_config_validation_missing_credentials(self):
        """Test configuration validation fails with missing credentials."""
        config = {
            "endpoint": "https://test.example.com"
        }
        with pytest.raises(Exception):  # Pydantic validation error
            LRSSQLPlugin(config)
    
    def test_authentication_headers(self, lrsql_plugin):
        """Test that authentication headers are correctly set."""
        headers = lrsql_plugin.headers
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["X-Experience-API-Version"] == "1.0.3"
        assert headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_success_dict_response(self, lrsql_plugin):
        """Test successful statement posting with dict response."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.example.com/xapi/statements").respond(
            201, json={"id": "test-statement-id"}
        )
        
        result = await lrsql_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_success_list_response(self, lrsql_plugin):
        """Test successful statement posting with list response."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.example.com/xapi/statements").respond(
            201, json=["test-statement-id"]
        )
        
        result = await lrsql_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
        assert result["stored"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_fallback_response(self, lrsql_plugin):
        """Test statement posting with non-standard response format."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.example.com/xapi/statements").respond(
            201, json="test-statement-id"
        )
        
        result = await lrsql_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
        assert result["stored"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_retry_on_server_error(self, lrsql_plugin):
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
        
        result = await lrsql_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_max_retries_exceeded(self, lrsql_plugin):
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
            await lrsql_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_no_retry_on_client_error(self, lrsql_plugin):
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
            await lrsql_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503  # Converted to service unavailable
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_success(self, lrsql_plugin):
        """Test successful statements retrieval."""
        respx.get("https://test-lrs.example.com/xapi/statements").respond(
            200, json={
                "statements": [
                    {"id": "stmt1", "actor": {"name": "test"}, "timestamp": "2023-01-02T00:00:00Z"},
                    {"id": "stmt2", "actor": {"name": "test"}, "timestamp": "2023-01-01T00:00:00Z"}
                ]
            }
        )
        
        result = await lrsql_plugin.get_statements(actor_uuid="test-uuid")
        assert len(result) == 2
        # Should be sorted by timestamp descending
        assert result[0]["id"] == "stmt1"
        assert result[1]["id"] == "stmt2"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_empty_result(self, lrsql_plugin):
        """Test statements retrieval with empty result."""
        respx.get("https://test-lrs.example.com/xapi/statements").respond(
            200, json={"statements": []}
        )
        
        result = await lrsql_plugin.get_statements(actor_uuid="test-uuid")
        assert result == []
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_with_filters(self, lrsql_plugin):
        """Test statements retrieval with query filters."""
        respx.get("https://test-lrs.example.com/xapi/statements").respond(
            200, json={"statements": []}
        )
        
        from datetime import datetime
        
        await lrsql_plugin.get_statements(
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
    async def test_get_statements_limit_enforcement(self, lrsql_plugin):
        """Test that statement limit is enforced."""
        respx.get("https://test-lrs.example.com/xapi/statements").respond(
            200, json={"statements": []}
        )
        
        await lrsql_plugin.get_statements(
            actor_uuid="test-uuid",
            limit=100  # Should be capped at 50
        )
        
        # Verify limit was enforced
        request = respx.calls[0].request
        assert "limit=50" in str(request.url)
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_retry_on_server_error(self, lrsql_plugin):
        """Test retry logic for GET requests."""
        # First request fails, second succeeds
        respx.get("https://test-lrs.example.com/xapi/statements").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(200, json={"statements": []})
            ]
        )
        
        result = await lrsql_plugin.get_statements(actor_uuid="test-uuid")
        assert result == []
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_timeout_retry(self, lrsql_plugin):
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
        
        result = await lrsql_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_request_timeout_max_retries(self, lrsql_plugin):
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
            await lrsql_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    async def test_close_client(self, lrsql_plugin):
        """Test closing HTTP client."""
        await lrsql_plugin.close()
        # Should not raise any exceptions


class TestLRSSQLConfig:
    """Test LRS SQL plugin configuration model."""
    
    def test_valid_config_creation(self):
        """Test valid configuration creation."""
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
    
    def test_config_env_prefix(self):
        """Test configuration environment prefix."""
        assert LRSSQLConfig.Config.env_prefix == "LRSQL_"
    
    def test_config_with_env_variables(self):
        """Test configuration with environment variables."""
        import os
        from learnmcp_xapi.plugins.lrsql import LRSSQLPlugin
        
        env_vars = {
            "LRSQL_ENDPOINT": "https://env.example.com",
            "LRSQL_KEY": "env_key",
            "LRSQL_SECRET": "env_secret"
        }
        
        with patch.dict(os.environ, env_vars):
            config_dict = LRSSQLPlugin.load_config_from_env("lrsql")
            
            assert config_dict["endpoint"] == "https://env.example.com"
            assert config_dict["key"] == "env_key"
            assert config_dict["secret"] == "env_secret"
    
    def test_config_endpoint_validation(self):
        """Test endpoint validation."""
        # Valid HTTPS endpoint
        config = LRSSQLConfig(
            endpoint="https://example.com",
            key="key",
            secret="secret"
        )
        assert config.endpoint == "https://example.com"
        
        # Valid HTTP endpoint
        config = LRSSQLConfig(
            endpoint="http://localhost:8080",
            key="key",
            secret="secret"
        )
        assert config.endpoint == "http://localhost:8080"
        
        # Invalid endpoint
        with pytest.raises(ValueError, match="must start with http"):
            LRSSQLConfig(
                endpoint="invalid-url",
                key="key",
                secret="secret"
            )
    
    def test_config_endpoint_trailing_slash_removal(self):
        """Test that trailing slash is removed from endpoint."""
        config = LRSSQLConfig(
            endpoint="https://example.com/",
            key="key",
            secret="secret"
        )
        assert config.endpoint == "https://example.com"
    
    def test_config_required_fields(self):
        """Test that required fields are enforced."""
        # Missing key
        with pytest.raises(ValueError):
            LRSSQLConfig(
                endpoint="https://example.com",
                secret="secret"
            )
        
        # Missing secret
        with pytest.raises(ValueError):
            LRSSQLConfig(
                endpoint="https://example.com",
                key="key"
            )
        
        # Missing endpoint
        with pytest.raises(ValueError):
            LRSSQLConfig(
                key="key",
                secret="secret"
            )


class TestLRSSQLPluginIntegration:
    """Test LRS SQL plugin integration with the plugin system."""
    
    def test_plugin_implements_interface(self):
        """Test that plugin properly implements the base interface."""
        from learnmcp_xapi.plugins.base import LRSPlugin
        
        assert issubclass(LRSSQLPlugin, LRSPlugin)
        
        # Test required class attributes
        assert hasattr(LRSSQLPlugin, 'name')
        assert hasattr(LRSSQLPlugin, 'description')
        assert hasattr(LRSSQLPlugin, 'version')
        
        # Test required methods
        assert hasattr(LRSSQLPlugin, 'get_config_model')
        assert hasattr(LRSSQLPlugin, 'validate_config')
        assert hasattr(LRSSQLPlugin, 'post_statement')
        assert hasattr(LRSSQLPlugin, 'get_statements')
        assert hasattr(LRSSQLPlugin, 'close')
    
    def test_plugin_registration(self):
        """Test that plugin can be registered in the registry."""
        from learnmcp_xapi.plugins.registry import PluginRegistry
        
        registry = PluginRegistry()
        registry.register(LRSSQLPlugin)
        
        assert 'lrsql' in registry
        assert registry.get('lrsql') == LRSSQLPlugin
    
    def test_plugin_factory_creation(self):
        """Test that plugin can be created via factory."""
        from learnmcp_xapi.plugins.factory import PluginFactory
        from learnmcp_xapi.plugins.registry import PluginRegistry
        
        # Setup registry
        registry = PluginRegistry()
        registry.register(LRSSQLPlugin)
        
        config = {
            "endpoint": "https://test.com",
            "key": "test_key",
            "secret": "test_secret"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', registry):
            plugin = PluginFactory.create_plugin('lrsql', additional_config=config)
            assert isinstance(plugin, LRSSQLPlugin)
            assert plugin.config.endpoint == "https://test.com"
    
    def test_backward_compatibility(self):
        """Test backward compatibility with legacy LRS client behavior."""
        config = {
            "endpoint": "https://test.example.com",
            "key": "test_key",
            "secret": "test_secret",
            "timeout": 30,
            "retry_attempts": 3
        }
        
        plugin = LRSSQLPlugin(config)
        
        # Test that plugin has properties expected by legacy code
        assert hasattr(plugin, 'client')
        assert hasattr(plugin, 'headers')
        
        # Test header format matches legacy expectations
        assert plugin.headers["X-Experience-API-Version"] == "1.0.3"
        assert plugin.headers["Content-Type"] == "application/json"
        assert "Authorization" in plugin.headers
        assert plugin.headers["Authorization"].startswith("Basic ")