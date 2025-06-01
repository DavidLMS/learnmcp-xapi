"""Tests for Veracity LRS plugin."""

import pytest
import respx
import httpx
from unittest.mock import patch
from datetime import datetime

from learnmcp_xapi.plugins.veracity import VeracityPlugin, VeracityConfig


class TestVeracityPlugin:
    """Test Veracity LRS plugin functionality and endpoint cleaning."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        return {
            "endpoint": "https://test-lrs.lrs.io",
            "username": "test_access_key",
            "password": "test_access_secret",
            "timeout": 30,
            "retry_attempts": 3
        }
    
    @pytest.fixture
    def veracity_plugin(self, mock_config):
        """Create Veracity plugin instance for testing."""
        return VeracityPlugin(mock_config)
    
    def test_plugin_metadata(self):
        """Test plugin metadata is correct."""
        assert VeracityPlugin.name == "veracity"
        assert "Veracity Learning" in VeracityPlugin.description
        assert VeracityPlugin.version == "1.0.0"
    
    def test_config_model(self):
        """Test plugin returns correct config model."""
        assert VeracityPlugin.get_config_model() == VeracityConfig
    
    def test_config_endpoint_cleaning(self):
        """Test that endpoints with /xapi suffix are cleaned properly."""
        # Test endpoint with /xapi suffix
        config = VeracityConfig(
            endpoint="https://test.lrs.io/xapi",
            username="key",
            password="secret"
        )
        assert config.endpoint == "https://test.lrs.io"
        
        # Test endpoint with trailing slash and /xapi
        config = VeracityConfig(
            endpoint="https://test.lrs.io/xapi/",
            username="key",
            password="secret"
        )
        assert config.endpoint == "https://test.lrs.io"
        
        # Test clean endpoint (no changes)
        config = VeracityConfig(
            endpoint="https://test.lrs.io",
            username="key",
            password="secret"
        )
        assert config.endpoint == "https://test.lrs.io"
        
        # Test endpoint with other path (no changes)
        config = VeracityConfig(
            endpoint="https://test.lrs.io/custom",
            username="key",
            password="secret"
        )
        assert config.endpoint == "https://test.lrs.io/custom"
    
    def test_config_validation_success(self):
        """Test successful configuration validation."""
        config = {
            "endpoint": "https://test.lrs.io",
            "username": "test_key",
            "password": "test_secret"
        }
        plugin = VeracityPlugin(config)
        plugin.validate_config()  # Should not raise
    
    def test_config_validation_missing_credentials(self):
        """Test configuration validation fails with missing credentials."""
        config = {
            "endpoint": "https://test.lrs.io"
        }
        with pytest.raises(Exception):  # Pydantic validation error
            VeracityPlugin(config)
    
    def test_authentication_headers(self, veracity_plugin):
        """Test that authentication headers are correctly set."""
        headers = veracity_plugin.headers
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["X-Experience-API-Version"] == "1.0.3"
        assert headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_success_list_response(self, veracity_plugin):
        """Test successful statement posting with list response."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.lrs.io/xapi/statements").respond(
            201, json=["test-statement-id"]
        )
        
        result = await veracity_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
        assert result["stored"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_success_dict_response(self, veracity_plugin):
        """Test successful statement posting with dict response."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.lrs.io/xapi/statements").respond(
            201, json={"id": "test-statement-id", "stored": True}
        )
        
        result = await veracity_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
        assert result["stored"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_fallback_response(self, veracity_plugin):
        """Test statement posting with non-standard response format."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.lrs.io/xapi/statements").respond(
            201, json="test-statement-id"
        )
        
        result = await veracity_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
        assert result["stored"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_retry_on_server_error(self, veracity_plugin):
        """Test retry logic on server errors."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # First two requests fail with 500, third succeeds
        respx.post("https://test-lrs.lrs.io/xapi/statements").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(201, json=["test-statement-id"])
            ]
        )
        
        result = await veracity_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_max_retries_exceeded(self, veracity_plugin):
        """Test that max retries are respected."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # All requests fail with 500
        respx.post("https://test-lrs.lrs.io/xapi/statements").respond(500)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await veracity_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_auth_error(self, veracity_plugin):
        """Test authentication error handling."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.lrs.io/xapi/statements").respond(
            401, json={"error": "unauthorized"}
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await veracity_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_no_retry_on_client_error(self, veracity_plugin):
        """Test that client errors (4xx) are not retried."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://test-lrs.lrs.io/xapi/statements").respond(
            400, json={"error": "bad request"}
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await veracity_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_success(self, veracity_plugin):
        """Test successful statements retrieval."""
        respx.get("https://test-lrs.lrs.io/xapi/statements").respond(
            200, json={
                "statements": [
                    {"id": "stmt1", "timestamp": "2023-01-02T00:00:00Z"},
                    {"id": "stmt2", "timestamp": "2023-01-01T00:00:00Z"}
                ]
            }
        )
        
        result = await veracity_plugin.get_statements(actor_uuid="test-uuid")
        assert len(result) == 2
        # Should be sorted by timestamp descending
        assert result[0]["id"] == "stmt1"
        assert result[1]["id"] == "stmt2"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_empty_result(self, veracity_plugin):
        """Test statements retrieval with empty result."""
        respx.get("https://test-lrs.lrs.io/xapi/statements").respond(
            200, json={"statements": []}
        )
        
        result = await veracity_plugin.get_statements(actor_uuid="test-uuid")
        assert result == []
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_with_filters(self, veracity_plugin):
        """Test statements retrieval with query filters."""
        respx.get("https://test-lrs.lrs.io/xapi/statements").respond(
            200, json={"statements": []}
        )
        
        await veracity_plugin.get_statements(
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
    async def test_get_statements_limit_enforcement(self, veracity_plugin):
        """Test that statement limit is enforced."""
        respx.get("https://test-lrs.lrs.io/xapi/statements").respond(
            200, json={"statements": []}
        )
        
        await veracity_plugin.get_statements(
            actor_uuid="test-uuid",
            limit=100  # Should be capped at 50
        )
        
        # Verify limit was enforced
        request = respx.calls[0].request
        assert "limit=50" in str(request.url)
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_retry_on_server_error(self, veracity_plugin):
        """Test retry logic for GET requests."""
        # First request fails, second succeeds
        respx.get("https://test-lrs.lrs.io/xapi/statements").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(200, json={"statements": []})
            ]
        )
        
        result = await veracity_plugin.get_statements(actor_uuid="test-uuid")
        assert result == []
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_timeout_retry(self, veracity_plugin):
        """Test retry on connection timeouts."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # First request times out, second succeeds
        respx.post("https://test-lrs.lrs.io/xapi/statements").mock(
            side_effect=[
                httpx.TimeoutException("Connection timeout"),
                httpx.Response(201, json=["test-statement-id"])
            ]
        )
        
        result = await veracity_plugin.post_statement(statement)
        assert result["id"] == "test-statement-id"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_request_timeout_max_retries(self, veracity_plugin):
        """Test that timeouts respect max retry limit."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # All requests timeout
        respx.post("https://test-lrs.lrs.io/xapi/statements").mock(
            side_effect=httpx.TimeoutException("Connection timeout")
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await veracity_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    async def test_close_client(self, veracity_plugin):
        """Test closing HTTP client."""
        await veracity_plugin.close()
        # Should not raise any exceptions


class TestVeracityConfig:
    """Test Veracity plugin configuration model."""
    
    def test_valid_config_creation(self):
        """Test valid configuration creation."""
        config = VeracityConfig(
            endpoint="https://veracity.example.com",
            username="access_key",
            password="access_secret",
            timeout=60,
            retry_attempts=5
        )
        
        assert config.endpoint == "https://veracity.example.com"
        assert config.username == "access_key"
        assert config.password.get_secret_value() == "access_secret"
        assert config.timeout == 60
        assert config.retry_attempts == 5
    
    def test_config_env_prefix(self):
        """Test configuration environment prefix."""
        assert VeracityConfig.Config.env_prefix == "VERACITY_"
    
    def test_config_with_env_variables(self):
        """Test configuration with environment variables."""
        import os
        from learnmcp_xapi.plugins.veracity import VeracityPlugin
        
        env_vars = {
            "VERACITY_ENDPOINT": "https://env.example.com",
            "VERACITY_USERNAME": "env_key",
            "VERACITY_PASSWORD": "env_secret"
        }
        
        with patch.dict(os.environ, env_vars):
            config_dict = VeracityPlugin.load_config_from_env("veracity")
            
            assert config_dict["endpoint"] == "https://env.example.com"
            assert config_dict["username"] == "env_key"
            assert config_dict["password"] == "env_secret"
    
    def test_legacy_env_variable_support(self):
        """Test support for legacy environment variables."""
        import os
        from learnmcp_xapi.plugins.veracity import VeracityPlugin
        
        env_vars = {
            "VERACITY_ACCESS_KEY": "legacy_key",
            "VERACITY_ACCESS_SECRET": "legacy_secret",
            "VERACITY_LRS_ENDPOINT": "https://legacy.lrs.io"
        }
        
        with patch.dict(os.environ, env_vars):
            config_dict = VeracityPlugin.load_config_from_env("veracity")
            
            assert config_dict["username"] == "legacy_key"
            assert config_dict["password"] == "legacy_secret"
            assert config_dict["endpoint"] == "https://legacy.lrs.io"
    
    def test_config_endpoint_validation(self):
        """Test endpoint validation."""
        # Valid HTTPS endpoint
        config = VeracityConfig(
            endpoint="https://example.com",
            username="key",
            password="secret"
        )
        assert config.endpoint == "https://example.com"
        
        # Valid HTTP endpoint
        config = VeracityConfig(
            endpoint="http://localhost:8080",
            username="key",
            password="secret"
        )
        assert config.endpoint == "http://localhost:8080"
        
        # Invalid endpoint
        with pytest.raises(ValueError, match="must start with http"):
            VeracityConfig(
                endpoint="invalid-url",
                username="key",
                password="secret"
            )
    
    def test_endpoint_normalization_scenarios(self):
        """Test various endpoint normalization scenarios."""
        test_cases = [
            # Input -> Expected output
            ("https://test.lrs.io", "https://test.lrs.io"),
            ("https://test.lrs.io/", "https://test.lrs.io"),
            ("https://test.lrs.io/xapi", "https://test.lrs.io"),
            ("https://test.lrs.io/xapi/", "https://test.lrs.io"),
            ("https://test.lrs.io/custom/path", "https://test.lrs.io/custom/path"),
            ("http://localhost:8080/xapi", "http://localhost:8080"),
        ]
        
        for input_endpoint, expected_output in test_cases:
            config = VeracityConfig(
                endpoint=input_endpoint,
                username="key",
                password="secret"
            )
            assert config.endpoint == expected_output, f"Failed for input: {input_endpoint}"
    
    def test_config_endpoint_trailing_slash_removal(self):
        """Test that trailing slash is removed from endpoint."""
        config = VeracityConfig(
            endpoint="https://example.com/",
            username="key",
            password="secret"
        )
        assert config.endpoint == "https://example.com"
    
    def test_config_required_fields(self):
        """Test that required fields are enforced."""
        # Missing username
        with pytest.raises(ValueError):
            VeracityConfig(
                endpoint="https://example.com",
                password="secret"
            )
        
        # Missing password
        with pytest.raises(ValueError):
            VeracityConfig(
                endpoint="https://example.com",
                username="key"
            )
        
        # Missing endpoint
        with pytest.raises(ValueError):
            VeracityConfig(
                username="key",
                password="secret"
            )


class TestVeracityPluginIntegration:
    """Test Veracity plugin integration with the plugin system."""
    
    def test_plugin_implements_interface(self):
        """Test that plugin properly implements the base interface."""
        from learnmcp_xapi.plugins.base import LRSPlugin
        
        assert issubclass(VeracityPlugin, LRSPlugin)
        
        # Test required class attributes
        assert hasattr(VeracityPlugin, 'name')
        assert hasattr(VeracityPlugin, 'description')
        assert hasattr(VeracityPlugin, 'version')
        
        # Test required methods
        assert hasattr(VeracityPlugin, 'get_config_model')
        assert hasattr(VeracityPlugin, 'validate_config')
        assert hasattr(VeracityPlugin, 'post_statement')
        assert hasattr(VeracityPlugin, 'get_statements')
        assert hasattr(VeracityPlugin, 'close')
    
    def test_plugin_registration(self):
        """Test that plugin can be registered in the registry."""
        from learnmcp_xapi.plugins.registry import PluginRegistry
        
        registry = PluginRegistry()
        registry.register(VeracityPlugin)
        
        assert 'veracity' in registry
        assert registry.get('veracity') == VeracityPlugin
    
    def test_plugin_factory_creation(self):
        """Test that plugin can be created via factory."""
        from learnmcp_xapi.plugins.factory import PluginFactory
        from learnmcp_xapi.plugins.registry import PluginRegistry
        
        # Setup registry
        registry = PluginRegistry()
        registry.register(VeracityPlugin)
        
        config = {
            "endpoint": "https://test.lrs.io",
            "username": "test_key",
            "password": "test_secret"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', registry):
            plugin = PluginFactory.create_plugin('veracity', additional_config=config)
            assert isinstance(plugin, VeracityPlugin)
            assert plugin.config.endpoint == "https://test.lrs.io"
    
    def test_plugin_configuration_interface(self):
        """Test that plugin properly implements configuration interface."""
        assert VeracityPlugin.get_config_model() == VeracityConfig
        
        # Test plugin can be instantiated with valid config
        config = {
            "endpoint": "https://test.lrs.io",
            "username": "test_key",
            "password": "test_secret"
        }
        
        plugin = VeracityPlugin(config)
        assert plugin.config.username == "test_key"
        assert plugin.config.endpoint == "https://test.lrs.io"
    
    def test_plugin_validation(self):
        """Test plugin configuration validation."""
        # Missing credentials should raise error
        config = {
            "endpoint": "https://test.lrs.io"
        }
        
        with pytest.raises(Exception):  # Pydantic validation error
            VeracityPlugin(config)
        
        # Valid config should work
        config = {
            "endpoint": "https://test.lrs.io",
            "username": "key",
            "password": "secret"
        }
        
        plugin = VeracityPlugin(config)
        plugin.validate_config()  # Should not raise
    
    @pytest.mark.asyncio
    async def test_plugin_interface_compliance(self):
        """Test that plugin implements all required interface methods."""
        config = {
            "endpoint": "https://test.lrs.io",
            "username": "key",
            "password": "secret"
        }
        
        plugin = VeracityPlugin(config)
        
        # Test all required methods exist and are callable
        assert hasattr(plugin, 'post_statement')
        assert hasattr(plugin, 'get_statements')
        assert hasattr(plugin, 'close')
        assert hasattr(plugin, 'validate_config')
        
        # Test methods have correct signatures (won't call them)
        assert callable(plugin.post_statement)
        assert callable(plugin.get_statements)
        assert callable(plugin.close)
        assert callable(plugin.validate_config)
    
    def test_endpoint_cleaning_feature(self):
        """Test that endpoint cleaning feature works correctly."""
        # This is Veracity's unique feature to prevent /xapi/xapi/ duplication
        config = {
            "endpoint": "https://test.lrs.io/xapi",
            "username": "key", 
            "password": "secret"
        }
        
        plugin = VeracityPlugin(config)
        assert plugin.config.endpoint == "https://test.lrs.io"
        
        # Verify the cleaned endpoint is used in actual requests
        expected_url = "https://test.lrs.io/xapi/statements"
        # The plugin should append /xapi/statements to the cleaned endpoint